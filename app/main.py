"""
GMP AI Copilot — FastAPI Application
Arquitectura multicapa: Auth → Orchestrator → Rules → RAG → LLM → Audit
Servidor: ing_cpmo@ivr-ia (35.185.57.245)
"""
import asyncio
import json as json_lib
import os
import time
from pathlib import Path

import asyncpg
import httpx
import redis
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_NAME        = os.getenv("APP_NAME", "GMP AI Copilot")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host-gateway:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
OLLAMA_TIMEOUT  = float(os.getenv("OLLAMA_TIMEOUT", "180"))
DATABASE_URL    = os.getenv("DATABASE_URL", "")
REDIS_URL       = os.getenv("REDIS_URL", "redis://redis:6379/0")
GMP_API_KEY     = os.getenv("GMP_API_KEY", "")

STATIC_DIR = Path(__file__).parent / "static"

# Serializa llamadas a Ollama: 1 a la vez para evitar que CPU se sature
_OLLAMA_SEM = asyncio.Semaphore(1)

app = FastAPI(title=APP_NAME, docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


async def verify_api_key(x_api_key: str = Header(default="")):
    if GMP_API_KEY and x_api_key != GMP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class QueryRequest(BaseModel):
    question: str
    agent: str = "auto"


# ── UI ────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_ui():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index), media_type="text/html")
    return {"name": APP_NAME, "ui": "No encontrada", "api_docs": "/api/docs"}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    status = {"api": "ok", "postgres": "unknown", "redis": "unknown", "ollama": "unknown"}
    if DATABASE_URL:
        try:
            conn = await asyncpg.connect(DATABASE_URL, timeout=3)
            await conn.fetchval("SELECT 1")
            await conn.close()
            status["postgres"] = "ok"
        except Exception:
            status["postgres"] = "error"
    else:
        status["postgres"] = "ok"
    try:
        r = redis.from_url(REDIS_URL, socket_timeout=2)
        r.ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "error"
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            status["ollama"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        status["ollama"] = "error"
    status["timestamp"] = int(time.time())
    return status


# ── Legacy endpoint (sin cambio) ──────────────────────────────────────────────

@app.post("/ask")
async def ask_legacy(payload: QueryRequest):
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": payload.question, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
    return {"answer": data.get("response", ""), "model": OLLAMA_MODEL}


# ── Agent metadata (sin auth — UI lo consume) ─────────────────────────────────

@app.get("/api/v1/agents")
async def list_agents():
    from app.agents.base import AGENT_REGISTRY
    return {
        aid: {
            "id": ag.id,
            "name": ag.name,
            "color": ag.color,
            "icon": ag.icon,
            "description": ag.description,
            "capabilities": ag.capabilities,
        }
        for aid, ag in AGENT_REGISTRY.items()
    }


# ── Rules evaluation (con auth) ───────────────────────────────────────────────

@app.get("/api/v1/rules/evaluate")
async def rules_evaluate(
    question: str,
    agent: str = "all",
    _: None = Depends(verify_api_key),
):
    from app.rules import evaluate_rules
    rules = evaluate_rules(question, agent)
    return {
        "question": question,
        "agent": agent,
        "rules_triggered": [
            {
                "rule_id": r.rule_id,
                "risk_level": r.risk_level,
                "action": r.action,
                "regulatory_basis": r.regulatory_basis,
            }
            for r in rules
        ],
        "rules_count": len(rules),
        "highest_risk": rules[0].risk_level if rules else None,
    }


# ── v1/query — flujo multicapa completo ──────────────────────────────────────

@app.post("/api/v1/query")
async def v1_query(payload: QueryRequest, request: Request, _: None = Depends(verify_api_key)):
    from app.audit import write_audit_entry
    from app.orchestrator import detect_agent, build_prompt
    from app.rules import evaluate_rules, get_rule_context
    from app.agents.base import get_agent
    from knowledge.retriever import retrieve_context_with_sources

    import logging
    log = logging.getLogger("gmp.query")
    user_id = request.headers.get("X-User-Id", "anonymous")
    t_start = time.time()
    log.warning("DIAG t0: handler invoked q=%r agent=%r", payload.question[:30], payload.agent)

    # Capa 1 — detección de agente
    agent_id = detect_agent(payload.question, payload.agent)
    agent_cfg = get_agent(agent_id)
    log.warning("DIAG t1: agent_id=%s", agent_id)

    # Capa 3 — reglas determinísticas
    rules_triggered = evaluate_rules(payload.question, agent_id)
    rule_ctx = get_rule_context(rules_triggered)
    log.warning("DIAG t2: rules=%d", len(rules_triggered))

    # Capa 1 — RAG con colección del agente detectado
    contexts, source_meta = await retrieve_context_with_sources(
        payload.question,
        n_results=1,
        collection_name=agent_cfg.chroma_collection,
    )
    context_block = "\n\n".join(c[:100] for c in contexts[:1]) if contexts else ""
    log.warning("DIAG t3: RAG done contexts=%d elapsed=%.2f", len(contexts), time.time()-t_start)

    # Capa 2 — prompt multicapa
    prompt = build_prompt(payload.question, agent_cfg, context_block, rule_ctx)
    log.warning("DIAG t4: prompt=%d chars, sending to Ollama", len(prompt))

    # Capa 4 — LLM serializado (semáforo) + timeout 300s
    answer_text = ""
    _client_holder: list = [None]  # mutable para closure

    async def _stream_ollama() -> str:
        buf = ""
        client = httpx.AsyncClient(timeout=httpx.Timeout(OLLAMA_TIMEOUT, connect=10.0))
        _client_holder[0] = client
        try:
            async with client.stream(
                "POST", f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True,
                      "num_predict": 50, "keep_alive": "15m"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            chunk = json_lib.loads(line)
                            buf += chunk.get("response", "")
                            if chunk.get("done"):
                                break
                        except Exception:
                            pass
        except Exception as exc:
            log.warning("DIAG t4 stream error: %s", exc)
        return buf

    async def _run_with_sem() -> str:
        async with _OLLAMA_SEM:
            return await _stream_ollama()

    task = asyncio.create_task(_run_with_sem())
    try:
        # OLLAMA_TIMEOUT cubre la generación; +360 cubre espera de semáforo si hay 1 request previo
        _done, _pending = await asyncio.wait({task}, timeout=OLLAMA_TIMEOUT + 360)
        if _pending:
            log.warning("DIAG t4: LLM timeout %.0fs — cerrando conexión Ollama", OLLAMA_TIMEOUT + 360)
            cl = _client_holder[0]
            if cl:
                try:
                    await cl.aclose()
                except Exception:
                    pass
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            answer_text = ""
        elif task.exception():
            log.warning("DIAG t4 task exc: %s", task.exception())
            answer_text = ""
        else:
            answer_text = task.result()
    finally:
        cl = _client_holder[0]
        _client_holder[0] = None
        if cl:
            try:
                await cl.aclose()
            except Exception:
                pass
    log.warning("DIAG t5: LLM done len=%d elapsed=%.2f", len(answer_text), time.time()-t_start)
    elapsed = round(time.time() - t_start, 2)

    # Capa 5 — audit trail 21 CFR Part 11
    write_audit_entry(
        user_id=user_id, action="query", agent=agent_id,
        question=payload.question, model=OLLAMA_MODEL,
        context_used=bool(contexts), elapsed_seconds=elapsed,
        response_text=answer_text,
    )

    return {
        "response": answer_text,
        "answer": answer_text,
        "sources": source_meta,
        "model": OLLAMA_MODEL,
        "agent_id": agent_id,
        "agent_name": agent_cfg.name,
        "context_used": bool(contexts),
        "elapsed_seconds": elapsed,
        "rules_triggered": [r.rule_id for r in rules_triggered],
        "rules_count": len(rules_triggered),
        "highest_risk": rules_triggered[0].risk_level if rules_triggered else None,
    }


# ── v1/stream — flujo multicapa con SSE ──────────────────────────────────────

@app.post("/api/v1/stream")
async def v1_stream(payload: QueryRequest, request: Request, _: None = Depends(verify_api_key)):
    from app.audit import write_audit_entry
    from app.orchestrator import detect_agent, build_prompt
    from app.rules import evaluate_rules, get_rule_context
    from app.agents.base import get_agent
    from knowledge.retriever import retrieve_context

    user_id = request.headers.get("X-User-Id", "anonymous")
    t_start = time.time()

    agent_id = detect_agent(payload.question, payload.agent)
    agent_cfg = get_agent(agent_id)
    rules_triggered = evaluate_rules(payload.question, agent_id)
    rule_ctx = get_rule_context(rules_triggered)
    contexts = await retrieve_context(
        payload.question,
        n_results=3,
        collection_name=agent_cfg.chroma_collection,
    )
    context_block = "\n\n".join(c[:400] for c in contexts[:4]) if contexts else ""
    prompt = build_prompt(payload.question, agent_cfg, context_block, rule_ctx)

    async def generate():
        full_response = ""
        try:
            async with _OLLAMA_SEM:
                async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                    async with client.stream(
                        "POST", f"{OLLAMA_BASE_URL}/api/generate",
                        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True,
                              "keep_alive": "15m"},
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if line:
                                try:
                                    chunk = json_lib.loads(line)
                                    token = chunk.get("response", "")
                                    if token:
                                        full_response += token
                                        yield f"data: {json_lib.dumps({'token': token})}\n\n"
                                    if chunk.get("done", False):
                                        break
                                except Exception:
                                    continue
        finally:
            elapsed = round(time.time() - t_start, 2)
            write_audit_entry(
                user_id=user_id, action="stream_query", agent=agent_id,
                question=payload.question, model=OLLAMA_MODEL,
                context_used=bool(contexts), elapsed_seconds=elapsed,
                response_text=full_response,
            )
            meta = {
                "done": True,
                "elapsed_seconds": elapsed,
                "agent_id": agent_id,
                "agent_name": agent_cfg.name,
                "rules_triggered": [r.rule_id for r in rules_triggered],
                "rules_count": len(rules_triggered),
                "highest_risk": rules_triggered[0].risk_level if rules_triggered else None,
            }
            yield f"data: {json_lib.dumps(meta)}\n\n"

    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Access-Control-Allow-Origin": "*"},
    )


# ── Knowledge / Audit / Protocols ─────────────────────────────────────────────

@app.get("/api/v1/knowledge/stats")
async def knowledge_stats(_: None = Depends(verify_api_key)):
    from knowledge.retriever import get_collection_stats
    return get_collection_stats()


@app.get("/api/v1/audit/verify")
async def audit_verify(_: None = Depends(verify_api_key)):
    from app.audit import verify_audit_logs
    return verify_audit_logs()


@app.get("/api/v1/protocol-template/{protocol_type}")
async def protocol_template(protocol_type: str, _: None = Depends(verify_api_key)):
    _T = {
        "IQ": {"protocol_type":"IQ","title":"Installation Qualification Protocol","version":"1.0",
               "regulatory_basis":["21 CFR Part 211.68","EU GMP Annex 15","GAMP 5"],
               "template":{"sections":[
                   {"id":"1","title":"Objective","content":"Verify equipment is installed correctly per design specifications."},
                   {"id":"2","title":"Scope","content":"Applies to installation of [SYSTEM NAME] at [FACILITY]."},
                   {"id":"3","title":"Responsibilities","items":["Validation Engineer","QA Representative","Engineering"]},
                   {"id":"4","title":"Prerequisites","items":["Approved URS","Approved DQ","Vendor documentation","Calibration certificates"]},
                   {"id":"5","title":"Installation Checks","tests":[
                       {"id":"IQ-001","description":"Verify equipment identification (serial numbers, model numbers)"},
                       {"id":"IQ-002","description":"Verify utility connections (electrical, pneumatic, water)"},
                       {"id":"IQ-003","description":"Verify instrument calibration status"},
                       {"id":"IQ-004","description":"Verify software version and configuration"},
                       {"id":"IQ-005","description":"Verify environmental conditions at installation site"}]},
                   {"id":"6","title":"Documentation Review","items":["P&ID diagrams","Installation drawings","Wiring diagrams","SOPs","Maintenance manuals"]},
                   {"id":"7","title":"Acceptance Criteria","content":"All IQ tests PASS or have acceptable deviation with QA approval."}]}},
        "OQ": {"protocol_type":"OQ","title":"Operational Qualification Protocol","version":"1.0",
               "regulatory_basis":["21 CFR Part 211.68","EU GMP Annex 15","GAMP 5"],
               "template":{"sections":[
                   {"id":"1","title":"Objective","content":"Verify equipment operates within defined limits."},
                   {"id":"2","title":"Prerequisites","items":["Approved completed IQ","Approved OQ protocol","Calibrated test instruments","Trained operators"]},
                   {"id":"3","title":"Operational Tests","tests":[
                       {"id":"OQ-001","description":"Alarm activation at defined upper setpoint"},
                       {"id":"OQ-002","description":"Alarm activation at defined lower setpoint"},
                       {"id":"OQ-003","description":"Interlock verification at boundary conditions"},
                       {"id":"OQ-004","description":"Audit trail records all parameter changes with timestamp and user ID"},
                       {"id":"OQ-005","description":"User access control: unauthorized access rejected"},
                       {"id":"OQ-006","description":"Emergency stop function verified"},
                       {"id":"OQ-007","description":"Operating range verification: min, nominal, max"},
                       {"id":"OQ-008","description":"Worst-case condition testing documented"}]},
                   {"id":"4","title":"Acceptance Criteria","content":"All OQ tests PASS at min, nominal, and max. Min 3 consecutive passes per test."}]}},
        "PQ": {"protocol_type":"PQ","title":"Performance Qualification Protocol","version":"1.0",
               "regulatory_basis":["21 CFR Part 211.100","EU GMP Annex 15","FDA Process Validation Guidance 2011"],
               "template":{"sections":[
                   {"id":"1","title":"Objective","content":"Demonstrate consistent process performance under production conditions."},
                   {"id":"2","title":"Prerequisites","items":["Approved IQ and OQ","Approved PQ protocol","Validated analytical methods","Approved batch records"]},
                   {"id":"3","title":"Performance Runs","tests":[
                       {"id":"PQ-001","description":"Run 1: All CPPs within validated range, all CQAs within specification"},
                       {"id":"PQ-002","description":"Run 2: All CPPs within validated range, all CQAs within specification"},
                       {"id":"PQ-003","description":"Run 3: All CPPs within validated range, all CQAs within specification"},
                       {"id":"PQ-004","description":"Statistical analysis of CQA results across all runs"},
                       {"id":"PQ-005","description":"Yield within acceptable limits for all runs"}]},
                   {"id":"4","title":"Acceptance Criteria","content":"3/3 runs PASS all CPP and CQA criteria. Cpk >= 1.33 recommended."}]}}
    }
    tmpl = _T.get(protocol_type.upper())
    if tmpl is None:
        raise HTTPException(status_code=404, detail=f"Unknown protocol type '{protocol_type}'. Valid: IQ, OQ, PQ")
    return tmpl


# ── Ingesta de documentos vía API ─────────────────────────────────────────────

class IngestRequest(BaseModel):
    collection: str = "gmp_fda_regulations"
    text: str
    source_name: str = "api_upload"


@app.post("/api/v1/ingest")
async def ingest_text(payload: IngestRequest, _: None = Depends(verify_api_key)):
    """Ingesta texto plano directamente al corpus ChromaDB sin necesidad de archivo."""
    import hashlib
    import chromadb

    try:
        client = chromadb.PersistentClient(
            path=os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
        )
        collection = client.get_or_create_collection(
            payload.collection,
            metadata={"hnsw:space": "cosine"},
        )

        text = payload.text.strip()
        chunk_size, overlap = 500, 80
        chunks, ids, metas = [], [], []
        i, idx = 0, 0
        while i < len(text):
            chunk = text[i : i + chunk_size].strip()
            if len(chunk) >= 30:
                doc_id = hashlib.md5(
                    f"{payload.source_name}_{idx}".encode()
                ).hexdigest()
                chunks.append(chunk)
                ids.append(doc_id)
                metas.append({
                    "source": payload.source_name,
                    "chunk": idx,
                    "api_ingested": True,
                })
                idx += 1
            i += chunk_size - overlap

        if chunks:
            collection.upsert(documents=chunks, ids=ids, metadatas=metas)

        return {
            "status": "ok",
            "collection": payload.collection,
            "chunks_ingested": len(chunks),
            "total_in_collection": collection.count(),
            "source": payload.source_name,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingest error: {exc}")
