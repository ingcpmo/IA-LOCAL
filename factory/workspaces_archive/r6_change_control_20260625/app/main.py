"""
GMP Change Control Module — FastAPI application.
Módulo de gestión de cambios conforme a 21 CFR Part 11 y ALCOA+.

NOTA REGULATORIA: Los documentos ICH Q10, FDA Process Validation 2011, e ISPE GAMP 5
están en estado PENDING_DOCUMENT. No se afirma cumplimiento completo hasta ingesta.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

from app.models import (
    ChangeRequestCreate, ChangeRequestResponse, ImpactAssessment,
    ApprovalRequest, AuditEntry, CRStatus, CRPriority
)
from app.audit import write_audit_entry, read_audit_trail, verify_audit_integrity

APP_NAME = os.getenv("APP_NAME", "GMP Change Control Module")
API_KEY = os.getenv("API_KEY", "")
AUDIT_LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "./data/audit_logs"))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

app = FastAPI(
    title=APP_NAME,
    version="0.1.0",
    description="Módulo GMP de gestión de cambios — 21 CFR Part 11 / ALCOA+",
)

# Almacenamiento en memoria (reemplazar por DB en producción)
_change_requests: dict[str, dict] = {}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cr_hash(cr: dict) -> str:
    payload = json.dumps({k: v for k, v in cr.items() if k != "audit_hash"}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _verify_api_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "api": "ok",
        "service": APP_NAME,
        "version": "0.1.0",
        "timestamp": int(time.time()),
        "pending_documents": [
            "ICH Q10 Pharmaceutical Quality System",
            "FDA Process Validation Guidance 2011",
            "ISPE GAMP 5 Computer System Validation",
        ],
        "corpus_status": "PENDING_DOCUMENT — go-live requiere ingesta completa",
    }


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/status", dependencies=[Depends(_verify_api_key)])
def get_status():
    return {
        "service": APP_NAME,
        "regulatory_scope": ["21 CFR Part 11", "21 CFR Part 211", "ALCOA+"],
        "pending_documents": {
            "ICH Q10": "PENDING_DOCUMENT",
            "FDA_Process_Validation_2011": "PENDING_DOCUMENT",
            "ISPE_GAMP5": "PENDING_DOCUMENT",
        },
        "change_requests_count": len(_change_requests),
        "audit_trail_active": True,
        "note": "Corpus vacío hasta ingesta de PDFs regulatorios oficiales",
    }


# ── Change Requests ───────────────────────────────────────────────────────────

@app.post("/api/v1/change-request", dependencies=[Depends(_verify_api_key)])
def create_change_request(payload: ChangeRequestCreate):
    """Registra un change request con audit trail ALCOA+ (21 CFR Part 11)."""
    cr_id = f"CR-{uuid.uuid4().hex[:8].upper()}"
    now = _ts()

    cr = {
        "cr_id": cr_id,
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": CRStatus.DRAFT,
        "initiator": payload.initiator,
        "department": payload.department,
        "affected_systems": payload.affected_systems,
        "justification": payload.justification,
        "created_at": now,
        "updated_at": now,
    }
    cr["audit_hash"] = _cr_hash(cr)
    _change_requests[cr_id] = cr

    write_audit_entry(
        action="CR_CREATED",
        actor=payload.initiator,
        details={"cr_id": cr_id, "title": payload.title, "priority": payload.priority},
        cr_id=cr_id,
    )

    return ChangeRequestResponse(**cr)


@app.get("/api/v1/change-request/{cr_id}", dependencies=[Depends(_verify_api_key)])
def get_change_request(cr_id: str):
    if cr_id not in _change_requests:
        raise HTTPException(status_code=404, detail=f"Change request '{cr_id}' no encontrado")
    return ChangeRequestResponse(**_change_requests[cr_id])


@app.get("/api/v1/change-request/{cr_id}/impact", dependencies=[Depends(_verify_api_key)])
def get_impact_assessment(cr_id: str):
    """Evaluación de impacto automática. Requiere revisión humana antes de aprobación."""
    if cr_id not in _change_requests:
        raise HTTPException(status_code=404, detail=f"Change request '{cr_id}' no encontrado")

    cr = _change_requests[cr_id]
    priority = cr.get("priority", CRPriority.MEDIUM)
    affected = cr.get("affected_systems", [])

    risk_map = {
        CRPriority.CRITICAL: "HIGH",
        CRPriority.HIGH: "HIGH",
        CRPriority.MEDIUM: "MEDIUM",
        CRPriority.LOW: "LOW",
    }
    risk_level = risk_map.get(priority, "MEDIUM")
    validation_required = priority in (CRPriority.HIGH, CRPriority.CRITICAL) or len(affected) > 2
    capa_required = risk_level == "HIGH"

    write_audit_entry(
        action="IMPACT_ASSESSED",
        actor="system_auto",
        details={"risk_level": risk_level, "validation_required": validation_required},
        cr_id=cr_id,
    )

    return ImpactAssessment(
        cr_id=cr_id,
        risk_level=risk_level,
        affected_processes=[f"Proceso relacionado con {s}" for s in affected] or ["Proceso genérico"],
        validation_required=validation_required,
        capa_required=capa_required,
        estimated_effort_days={"LOW": 2, "MEDIUM": 5, "HIGH": 10}.get(risk_level, 5),
        notes=f"Evaluación automática basada en prioridad={priority}. Revisión humana requerida.",
        assessed_at=datetime.now(timezone.utc),
        regulatory_note="PENDING_DOCUMENT: evaluación completa requiere PDFs regulatorios oficiales ingestados",
    )


@app.post("/api/v1/change-request/{cr_id}/approve", dependencies=[Depends(_verify_api_key)])
def approve_change_request(cr_id: str, payload: ApprovalRequest):
    """Aprueba o rechaza un CR. Firma electrónica requerida (Part 11)."""
    if cr_id not in _change_requests:
        raise HTTPException(status_code=404, detail=f"Change request '{cr_id}' no encontrado")

    cr = _change_requests[cr_id]
    if cr["status"] not in (CRStatus.DRAFT, CRStatus.UNDER_REVIEW):
        raise HTTPException(status_code=409, detail=f"CR en estado '{cr['status']}' no puede ser modificado")

    new_status = CRStatus.APPROVED if payload.decision == "APPROVED" else CRStatus.REJECTED
    cr["status"] = new_status
    cr["updated_at"] = _ts()
    cr["audit_hash"] = _cr_hash(cr)

    write_audit_entry(
        action=f"CR_{payload.decision}",
        actor=payload.approver,
        details={
            "decision": payload.decision,
            "comments": payload.comments,
            "capa_required": payload.capa_required,
        },
        cr_id=cr_id,
    )

    response = {
        "cr_id": cr_id,
        "new_status": new_status,
        "approver": payload.approver,
        "decision": payload.decision,
        "capa_generated": payload.capa_required,
        "timestamp": _ts(),
    }

    if payload.capa_required:
        capa_id = f"CAPA-{cr_id}"
        response["capa_id"] = capa_id
        write_audit_entry(
            action="CAPA_LINKED",
            actor=payload.approver,
            details={"capa_id": capa_id, "triggered_by": cr_id},
            cr_id=cr_id,
        )

    return response


# ── Audit Trail ───────────────────────────────────────────────────────────────

@app.get("/api/v1/audit-trail", dependencies=[Depends(_verify_api_key)])
def get_audit_trail(cr_id: Optional[str] = None, limit: int = 50):
    """Audit trail ALCOA+ completo. Append-only, hash SHA256 por entrada."""
    entries = read_audit_trail(cr_id=cr_id, limit=limit)
    return {
        "entries": entries,
        "count": len(entries),
        "alcoa_plus": True,
        "hash_algo": "sha256",
        "note": "Audit trail inmutable conforme a 21 CFR Part 11",
    }


# ── Knowledge ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/knowledge/stats", dependencies=[Depends(_verify_api_key)])
def get_knowledge_stats():
    """Estado del corpus regulatorio. PENDING hasta ingesta de PDFs oficiales."""
    return {
        "collections": {
            "change_control_regs": {
                "status": "PENDING_DOCUMENT",
                "count": 0,
                "note": "Requiere PDFs: ICH Q10, FDA Process Validation 2011",
            },
            "capa_procedures": {
                "status": "PENDING_DOCUMENT",
                "count": 0,
                "note": "Requiere PDFs: ISPE GAMP 5, procedimientos CAPA internos",
            },
        },
        "corpus_ready": False,
        "go_live_blocked": True,
        "reason": "Corpus vacío — ingestar PDFs regulatorios oficiales antes de go-live",
    }
