import os
import time

import asyncpg
import httpx
import redis
from fastapi import FastAPI, Request
from pydantic import BaseModel

APP_NAME = os.getenv("APP_NAME", "GMP AI Copilot")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = FastAPI(title=APP_NAME)


class QueryRequest(BaseModel):
    question: str
    agent: str = "general"


@app.get("/")
async def root():
    return {
        "app": APP_NAME,
        "status": "running",
        "ollama_model": OLLAMA_MODEL,
    }


@app.get("/health")
async def health():
    status = {
        "api": "ok",
        "postgres": "unknown",
        "redis": "unknown",
        "ollama": "unknown",
        "timestamp": int(time.time()),
    }

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("SELECT 1")
        await conn.close()
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {type(exc).__name__}"

    try:
        r = redis.from_url(REDIS_URL, socket_connect_timeout=3)
        r.ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {type(exc).__name__}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            response.raise_for_status()
            status["ollama"] = "ok"
    except Exception as exc:
        status["ollama"] = f"error: {type(exc).__name__}"

    return status


@app.post("/ask")
async def ask(payload: QueryRequest):
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": payload.question,
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    return {
        "question": payload.question,
        "model": OLLAMA_MODEL,
        "answer": data.get("response", ""),
    }


@app.post("/api/v1/query")
async def v1_query(payload: QueryRequest, request: Request):
    from app.audit import write_audit_entry
    from knowledge.retriever import retrieve_context

    user_id = request.headers.get("X-User-Id", "anonymous")
    t_start = time.time()
    contexts = await retrieve_context(payload.question, n_results=2)

    if contexts:
        # Limit total context to ~1200 chars to keep Ollama response time reasonable
        context_block = "\n\n".join(c[:400] for c in contexts[:4])
        prompt = (
            f"You are a GMP compliance expert. Use the regulatory context below to answer concisely.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {payload.question}\n\nAnswer:"
        )
    else:
        prompt = (
            f"You are a GMP compliance expert. Answer the following question:\n\n"
            f"{payload.question}"
        )

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
        user_id=user_id,
        action="query",
        agent=payload.agent,
        question=payload.question,
        model=OLLAMA_MODEL,
        context_used=bool(contexts),
        elapsed_seconds=elapsed,
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


@app.get("/api/v1/knowledge/stats")
async def knowledge_stats():
    from knowledge.retriever import get_collection_stats

    return get_collection_stats()


@app.get("/api/v1/audit/verify")
async def audit_verify():
    from app.audit import verify_audit_logs
    return verify_audit_logs()


_PROTOCOL_TEMPLATES = {
    "IQ": {
        "protocol_type": "IQ",
        "title": "Installation Qualification Protocol",
        "version": "1.0",
        "regulatory_basis": ["21 CFR Part 211.68", "EU GMP Annex 15", "GAMP 5"],
        "template": {
            "sections": [
                {"id": "1", "title": "Objective", "content": "Verify equipment is installed correctly per design specifications."},
                {"id": "2", "title": "Scope", "content": "Applies to installation of [SYSTEM NAME] at [FACILITY]."},
                {"id": "3", "title": "Responsibilities", "items": ["Validation Engineer", "QA Representative", "Engineering"]},
                {"id": "4", "title": "Prerequisites", "items": [
                    "Approved URS (User Requirements Specification)",
                    "Approved DQ (Design Qualification)",
                    "Vendor documentation package",
                    "Calibration certificates",
                ]},
                {"id": "5", "title": "Installation Checks", "tests": [
                    {"id": "IQ-001", "description": "Verify equipment identification (serial numbers, model numbers)"},
                    {"id": "IQ-002", "description": "Verify utility connections (electrical, pneumatic, water)"},
                    {"id": "IQ-003", "description": "Verify instrument calibration status"},
                    {"id": "IQ-004", "description": "Verify software version and configuration"},
                    {"id": "IQ-005", "description": "Verify environmental conditions at installation site"},
                ]},
                {"id": "6", "title": "Documentation Review", "items": [
                    "P&ID diagrams", "Installation drawings", "Wiring diagrams", "SOPs", "Maintenance manuals",
                ]},
                {"id": "7", "title": "Acceptance Criteria", "content": "All IQ tests PASS or have acceptable deviation with QA approval."},
            ]
        },
    },
    "OQ": {
        "protocol_type": "OQ",
        "title": "Operational Qualification Protocol",
        "version": "1.0",
        "regulatory_basis": ["21 CFR Part 211.68", "EU GMP Annex 15", "GAMP 5"],
        "template": {
            "sections": [
                {"id": "1", "title": "Objective", "content": "Verify equipment operates within defined limits throughout its operating range."},
                {"id": "2", "title": "Scope", "content": "Applies to operational testing of [SYSTEM NAME] post-IQ approval."},
                {"id": "3", "title": "Prerequisites", "items": [
                    "Approved and completed IQ protocol",
                    "Approved OQ protocol",
                    "Calibrated test instruments",
                    "Trained operators",
                ]},
                {"id": "4", "title": "Operational Tests", "tests": [
                    {"id": "OQ-001", "description": "Alarm activation at defined upper setpoint"},
                    {"id": "OQ-002", "description": "Alarm activation at defined lower setpoint"},
                    {"id": "OQ-003", "description": "Interlock verification at boundary conditions"},
                    {"id": "OQ-004", "description": "Audit trail records all parameter changes with timestamp and user ID"},
                    {"id": "OQ-005", "description": "User access control: unauthorized access rejected"},
                    {"id": "OQ-006", "description": "Emergency stop function verified"},
                    {"id": "OQ-007", "description": "Operating range verification: min, nominal, max"},
                    {"id": "OQ-008", "description": "Worst-case condition testing documented"},
                ]},
                {"id": "5", "title": "Acceptance Criteria", "content": "All OQ tests PASS at min, nominal, and max operating conditions. Min 3 consecutive passes per test."},
            ]
        },
    },
    "PQ": {
        "protocol_type": "PQ",
        "title": "Performance Qualification Protocol",
        "version": "1.0",
        "regulatory_basis": ["21 CFR Part 211.100", "EU GMP Annex 15", "FDA Process Validation Guidance 2011"],
        "template": {
            "sections": [
                {"id": "1", "title": "Objective", "content": "Demonstrate consistent process performance under production conditions meeting all specifications."},
                {"id": "2", "title": "Scope", "content": "Applies to [SYSTEM NAME] operating within validated parameters for [PRODUCT/PROCESS]."},
                {"id": "3", "title": "Prerequisites", "items": [
                    "Approved and completed IQ and OQ protocols",
                    "Approved PQ protocol",
                    "Validated analytical methods",
                    "Approved batch manufacturing records",
                    "Cleaning validation completed (if applicable)",
                ]},
                {"id": "4", "title": "Performance Runs", "content": "Minimum 3 consecutive successful production runs under worst-case conditions.", "tests": [
                    {"id": "PQ-001", "description": "Run 1: All CPPs within validated range, all CQAs within specification"},
                    {"id": "PQ-002", "description": "Run 2: All CPPs within validated range, all CQAs within specification"},
                    {"id": "PQ-003", "description": "Run 3: All CPPs within validated range, all CQAs within specification"},
                    {"id": "PQ-004", "description": "Statistical analysis of CQA results across all runs"},
                    {"id": "PQ-005", "description": "Yield within acceptable limits for all runs"},
                ]},
                {"id": "5", "title": "Acceptance Criteria", "content": "3/3 runs PASS all CPP and CQA criteria. No unexplained deviations. Statistical process capability Cpk ≥ 1.33 recommended."},
            ]
        },
    },
}


@app.get("/api/v1/protocol-template/{protocol_type}")
async def protocol_template(protocol_type: str):
    from fastapi import HTTPException
    template = _PROTOCOL_TEMPLATES.get(protocol_type.upper())
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown protocol type '{protocol_type}'. Valid types: IQ, OQ, PQ",
        )
    return template


@app.post("/api/v1/stream")
async def v1_stream(payload: QueryRequest, request: Request):
    """Streaming SSE — tokens en tiempo real mientras Ollama genera."""
    import json as json_lib
    from app.audit import write_audit_entry
    from fastapi.responses import StreamingResponse
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
        prompt = (
            f"You are a GMP compliance expert.\n\n"
            f"Question: {payload.question}"
        )

    async def generate():
        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_BASE_URL}/api/generate",
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
                user_id=user_id,
                action="stream_query",
                agent=payload.agent,
                question=payload.question,
                model=OLLAMA_MODEL,
                context_used=bool(contexts),
                elapsed_seconds=elapsed,
                response_text=full_response,
            )
            yield f"data: {json_lib.dumps({'done': True, 'elapsed_seconds': elapsed})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
