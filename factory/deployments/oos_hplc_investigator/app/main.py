"""
OOS HPLC Investigator — FastAPI Application
GMP AI Factory — Capa 8 — Deployment F5
21 CFR Part 11 / FDA OOS 2006 / USP <621>
"""
import os
import time
import uuid
from pathlib import Path

import asyncpg
import httpx
import redis
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

APP_NAME        = "OOS HPLC Investigator"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
OLLAMA_TIMEOUT  = float(os.getenv("OLLAMA_TIMEOUT", "180"))
DATABASE_URL    = os.getenv("DATABASE_URL", "")
REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GMP_API_KEY     = os.getenv("GMP_API_KEY", "")

app = FastAPI(title=APP_NAME, version="1.1.0", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store (producción usaría Postgres)
_OOS_STORE: dict[str, dict] = {}


async def verify_api_key(x_api_key: str = Header(default="")):
    if not GMP_API_KEY:
        return
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if x_api_key != GMP_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


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


# ── OOS Workflow ──────────────────────────────────────────────────────────────

class OOSCreateRequest(BaseModel):
    sample_id: str
    test_method: str
    analyst_id: str
    result_value: float
    spec_min: float
    spec_max: float

class FindingRequest(BaseModel):
    finding: str
    recorded_by: str = "analyst"

class AdvanceRequest(BaseModel):
    authorized_by: str

class CloseRequest(BaseModel):
    disposition: str = Field(..., pattern="^(approved|rejected|retest)$")
    supervisor_id: str
    rationale: str


@app.post("/api/v1/oos/records", dependencies=[Depends(verify_api_key)])
def create_oos_record(body: OOSCreateRequest):
    from app.oos_workflow import create_oos_record as _create, is_oos, record_to_dict
    record = _create(
        sample_id=body.sample_id,
        test_method=body.test_method,
        analyst_id=body.analyst_id,
        result_value=body.result_value,
        spec_min=body.spec_min,
        spec_max=body.spec_max,
    )
    d = record_to_dict(record)
    _OOS_STORE[record.record_id] = d
    return {**d, "is_oos": is_oos(record)}


@app.post("/api/v1/oos/records/{record_id}/findings", dependencies=[Depends(verify_api_key)])
def add_finding(record_id: str, body: FindingRequest):
    from app.oos_workflow import add_finding as _add, record_to_dict
    from app.audit_trail import create_audit_stamp
    if record_id not in _OOS_STORE:
        raise HTTPException(404, f"Record '{record_id}' no encontrado")
    from app.oos_workflow import OOSRecord
    rec_dict = _OOS_STORE[record_id]
    # Reconstruct from dict
    rec = OOSRecord(**{k: v for k, v in rec_dict.items()})
    updated = _add(rec, body.finding)
    d = record_to_dict(updated)
    _OOS_STORE[record_id] = d
    stamp = create_audit_stamp(actor=body.recorded_by, action="finding_added", record=d)
    return {**d, "audit_stamp": stamp}


@app.post("/api/v1/oos/records/{record_id}/advance", dependencies=[Depends(verify_api_key)])
def advance_phase2(record_id: str, body: AdvanceRequest):
    from app.oos_workflow import advance_to_phase2, record_to_dict, OOSRecord
    from app.audit_trail import create_audit_stamp
    if record_id not in _OOS_STORE:
        raise HTTPException(404, f"Record '{record_id}' no encontrado")
    rec_dict = _OOS_STORE[record_id]
    rec = OOSRecord(**{k: v for k, v in rec_dict.items()})
    try:
        updated = advance_to_phase2(rec)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d = record_to_dict(updated)
    _OOS_STORE[record_id] = d
    stamp = create_audit_stamp(actor=body.authorized_by, action="phase2_authorized", record=d)
    return {**d, "audit_stamp": stamp}


@app.post("/api/v1/oos/records/{record_id}/close", dependencies=[Depends(verify_api_key)])
def close_oos_record(record_id: str, body: CloseRequest):
    from app.oos_workflow import close_oos, record_to_dict, OOSRecord
    from app.audit_trail import sign_record
    if record_id not in _OOS_STORE:
        raise HTTPException(404, f"Record '{record_id}' no encontrado")
    rec_dict = _OOS_STORE[record_id]
    rec = OOSRecord(**{k: v for k, v in rec_dict.items()})
    try:
        closed = close_oos(rec, body.disposition, body.supervisor_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d = record_to_dict(closed)
    _OOS_STORE[record_id] = d
    signature = sign_record(d, actor=body.supervisor_id, role="supervisor")
    return {**d, "rationale": body.rationale, "signature": signature}


@app.get("/api/v1/oos/records", dependencies=[Depends(verify_api_key)])
def list_oos_records(phase: str = "", status: str = ""):
    records = list(_OOS_STORE.values())
    if phase:
        records = [r for r in records if r.get("phase") == phase]
    if status:
        records = [r for r in records if r.get("status") == status]
    return {"records": records, "total": len(records)}


# ── HPLC Validator ────────────────────────────────────────────────────────────

class SSTRequest(BaseModel):
    theoretical_plates: float | None = None
    tailing_factor: float | None = None
    resolution: float | None = None
    rsd_retention: float | None = None

class PeaksRequest(BaseModel):
    peaks: list[dict]


@app.post("/api/v1/hplc/sst/validate", dependencies=[Depends(verify_api_key)])
def validate_sst(body: SSTRequest):
    from app.agents.hplc_data_review.hplc_validator import validate_sst as _valsst
    return _valsst(body.model_dump(exclude_none=True))


@app.post("/api/v1/hplc/peaks/anomalies", dependencies=[Depends(verify_api_key)])
def detect_anomalies(body: PeaksRequest):
    from app.agents.hplc_data_review.hplc_validator import detect_peak_anomalies
    anomalies = detect_peak_anomalies(body.peaks)
    return {"anomalies": anomalies, "count": len(anomalies)}


@app.post("/api/v1/hplc/rsd", dependencies=[Depends(verify_api_key)])
def calculate_rsd_endpoint(values: list[float]):
    from app.agents.hplc_data_review.hplc_validator import calculate_rsd
    return {"rsd_percent": calculate_rsd(values), "n": len(values)}


# ── Audit / ALCOA ─────────────────────────────────────────────────────────────

@app.post("/api/v1/audit/alcoa/validate", dependencies=[Depends(verify_api_key)])
def alcoa_validate(record: dict):
    from app.audit_trail import validate_alcoa
    return validate_alcoa(record)


@app.post("/api/v1/audit/stamp", dependencies=[Depends(verify_api_key)])
def audit_stamp(body: dict):
    from app.audit_trail import create_audit_stamp
    actor = body.pop("actor", "unknown")
    action = body.pop("action", "unknown")
    return create_audit_stamp(actor=actor, action=action, record=body)


# ── Batch Disposition ─────────────────────────────────────────────────────────

class DispositionRequest(BaseModel):
    lot_id: str
    oos_record_ids: list[str]
    supervisor_id: str
    decision: str = Field(..., pattern="^(approved|rejected|retest)$")
    rationale: str


@app.post("/api/v1/lot/disposition", dependencies=[Depends(verify_api_key)])
def lot_disposition(body: DispositionRequest):
    from app.batch_disposition import evaluate_disposition
    records = [_OOS_STORE[rid] for rid in body.oos_record_ids if rid in _OOS_STORE]
    if len(records) != len(body.oos_record_ids):
        missing = [r for r in body.oos_record_ids if r not in _OOS_STORE]
        raise HTTPException(404, f"Records no encontrados: {missing}")
    try:
        result = evaluate_disposition(
            lot_id=body.lot_id,
            oos_records=records,
            supervisor_id=body.supervisor_id,
            decision=body.decision,
            rationale=body.rationale,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return result


# ── Ollama Query ──────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    context: str = ""


@app.post("/api/v1/query", dependencies=[Depends(verify_api_key)])
async def query_oos(body: QueryRequest):
    t_start = time.monotonic()
    system_context = (
        "Eres un experto en investigación OOS (Out-of-Specification) para análisis HPLC "
        "en laboratorio farmacéutico QC. Aplicas FDA OOS Guidance 2006, 21 CFR 211.192, "
        "y USP <621>. Respondes en español de forma concisa y precisa."
    )
    prompt = f"{system_context}\n\nContexto adicional: {body.context}\n\nPregunta: {body.question}"
    timeout = httpx.Timeout(connect=5.0, read=OLLAMA_TIMEOUT, write=5.0, pool=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 256, "temperature": 0.2},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", "")
    except httpx.ConnectError as e:
        elapsed = round(time.monotonic() - t_start, 2)
        raise HTTPException(503, {
            "error": "ollama_unreachable",
            "detail": str(e),
            "model": OLLAMA_MODEL,
            "elapsed_seconds": elapsed,
            "ollama_status": "unreachable",
        })
    except httpx.ReadTimeout as e:
        elapsed = round(time.monotonic() - t_start, 2)
        raise HTTPException(504, {
            "error": "ollama_timeout",
            "detail": str(e),
            "model": OLLAMA_MODEL,
            "elapsed_seconds": elapsed,
            "ollama_status": "timeout",
        })
    except Exception as e:
        elapsed = round(time.monotonic() - t_start, 2)
        raise HTTPException(500, {
            "error": "ollama_error",
            "detail": str(e),
            "model": OLLAMA_MODEL,
            "elapsed_seconds": elapsed,
            "ollama_status": "error",
        })
    return {
        "answer": answer,
        "model": OLLAMA_MODEL,
        "elapsed_seconds": round(time.monotonic() - t_start, 2),
        "ollama_status": "ok",
        "used_llm": True,
    }
