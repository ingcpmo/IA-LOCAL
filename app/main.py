"""
GMP AI Copilot — FastAPI Application
Actualizado para servir UI web en / y aceptar requests desde IP pública.
Servidor: ing_cpmo@ivr-ia (35.185.57.245)
"""
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
    agent: str = "fda"


@app.get("/", include_in_schema=False)
async def serve_ui():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index), media_type="text/html")
    return {"name": APP_NAME, "ui": "No encontrada", "api_docs": "/api/docs"}


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


@app.post("/api/v1/query")
async def v1_query(payload: QueryRequest, request: Request, _: None = Depends(verify_api_key)):
    from app.audit import write_audit_entry
    from knowledge.retriever import retrieve_context
    user_id = request.headers.get("X-User-Id", "anonymous")
    t_start = time.time()
    contexts = await retrieve_context(payload.question, n_results=2)
    if contexts:
        context_block = "\n\n".join(c[:400] for c in contexts[:4])
        prompt = (
            f"You are a GMP compliance expert. Use the regulatory "
            f"context below to answer concisely.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {payload.question}\n\nAnswer:"
        )
    else:
        prompt = f"You are a GMP compliance expert.\n\nQuestion: {payload.question}"
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        ollama_resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        ollama_resp.raise_for_status()
        data = ollama_resp.json()
    answer_text = data.get("response", "")
    elapsed = round(time.time() - t_start, 2)
    write_audit_entry(
        user_id=user_id, action="query", agent=payload.agent,
        question=payload.question, model=OLLAMA_MODEL,
        context_used=bool(contexts), elapsed_seconds=elapsed,
        response_text=answer_text,
    )
    return {
        "response": answer_text,
        "answer": answer_text,
        "sources": contexts,
        "model": OLLAMA_MODEL,
        "agent": payload.agent,
        "context_used": bool(contexts),
        "elapsed_seconds": elapsed,
    }


@app.post("/api/v1/stream")
async def v1_stream(payload: QueryRequest, request: Request, _: None = Depends(verify_api_key)):
    import json as json_lib
    from app.audit import write_audit_entry
    from knowledge.retriever import retrieve_context
    user_id = request.headers.get("X-User-Id", "anonymous")
    t_start = time.time()
    contexts = await retrieve_context(payload.question, n_results=2)
    context_block = "\n\n".join(c[:400] for c in contexts[:4]) if contexts else ""
    if context_block:
        prompt = (
            f"You are a GMP compliance expert. Use the regulatory "
            f"context below to answer concisely.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {payload.question}\n\nAnswer:"
        )
    else:
        prompt = f"You are a GMP compliance expert.\n\nQuestion: {payload.question}"
    async def generate():
        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
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
                user_id=user_id, action="stream_query", agent=payload.agent,
                question=payload.question, model=OLLAMA_MODEL,
                context_used=bool(contexts), elapsed_seconds=elapsed,
                response_text=full_response,
            )
            yield f"data: {json_lib.dumps({'done': True, 'elapsed_seconds': elapsed})}\n\n"
    return StreamingResponse(
        generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Access-Control-Allow-Origin": "*"},
    )


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
