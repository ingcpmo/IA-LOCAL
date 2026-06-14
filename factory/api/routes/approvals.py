"""
Flujo de aprobación de fábrica — separación explícita agente vs humano.

REGLA: el agente NUNCA puede escribir status="approved" ni approved_by por su cuenta.
  POST /{project_id}         → agent propose   → status: pending_human_confirmation
  POST /{project_id}/confirm → human confirm   → status: approved, decision_origin: human_confirmed
  POST /{project_id}/reject  → human reject    → status: rejected
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import write_event

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

WORKSPACES_DIR = Path(__file__).parent.parent.parent / "workspaces"
APPROVALS_DIR  = Path(__file__).parent.parent.parent / "approvals"

_RESERVED_APPROVERS = {"human", "agent", "layer8_agent", "auto", "system"}


class ProposeBody(BaseModel):
    """Cuerpo para propuesta del agente — nunca produce status=approved."""
    action: str
    notes: str = ""
    version: str = ""
    gates_report_hash: str = ""
    recorded_by: str = "layer8_agent"


class ConfirmBody(BaseModel):
    """Cuerpo para confirmación humana — único camino a status=approved."""
    action: str
    approved_by: str           # nombre real del humano (no puede ser 'human'/'agent'/etc.)
    notes: str = ""
    version: str = ""
    gates_report_hash: str = ""
    recorded_by: str = ""      # se sobreescribe con approved_by si vacío


# ── Endpoint 1: agente propone ────────────────────────────────────────────────

@router.post("/{project_id}", status_code=201)
def propose_approval(project_id: str, body: ProposeBody):
    """
    El agente propone una aprobación.
    Resultado: status=pending_human_confirmation, decision_origin=agent_proposed.
    El campo approved_by no se rellena — queda en espera de confirmación humana.
    """
    now = datetime.now(timezone.utc).isoformat()
    proposal = {
        "action": body.action,
        "project_id": project_id,
        "version": body.version,
        "approved_by": None,                    # vacío: pendiente de humano
        "proposed_at": now,
        "approved_at": None,
        "gates_report_hash": body.gates_report_hash,
        "notes": body.notes,
        "status": "pending_human_confirmation",
        "decision_origin": "agent_proposed",
        "recorded_by": body.recorded_by or "layer8_agent",
    }

    ws_approval = WORKSPACES_DIR / project_id / "approval.json"
    ws_approval.parent.mkdir(parents=True, exist_ok=True)
    ws_approval.write_text(json.dumps(proposal, indent=2))

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (APPROVALS_DIR / f"{project_id}_{body.action}_proposed_{ts}.json").write_text(
        json.dumps(proposal, indent=2)
    )

    write_event("approval_proposed", project_id, {
        "action": body.action,
        "version": body.version,
        "status": "pending_human_confirmation",
        "decision_origin": "agent_proposed",
        "recorded_by": proposal["recorded_by"],
    })
    return proposal


# ── Endpoint 2: humano confirma ───────────────────────────────────────────────

@router.post("/{project_id}/confirm", status_code=201)
def confirm_approval(project_id: str, body: ConfirmBody):
    """
    Confirmación humana explícita.
    Resultado: status=approved, decision_origin=human_confirmed.
    approved_by no puede ser un identificador reservado (human/agent/system/etc.).
    """
    if not body.approved_by or body.approved_by.lower().strip() in _RESERVED_APPROVERS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"approved_by='{body.approved_by}' es un valor reservado. "
                "Usa el nombre real del aprobador humano (ej. 'Cesar', 'Maria')."
            ),
        )

    now = datetime.now(timezone.utc).isoformat()
    recorded_by = body.recorded_by or body.approved_by

    # Leer propuesta previa si existe para conservar campos
    ws_approval = WORKSPACES_DIR / project_id / "approval.json"
    existing = {}
    if ws_approval.exists():
        try:
            existing = json.loads(ws_approval.read_text())
        except Exception:
            pass

    approval = {
        "action": body.action,
        "project_id": project_id,
        "version": body.version or existing.get("version", ""),
        "approved_by": body.approved_by,
        "proposed_at": existing.get("proposed_at", now),
        "approved_at": now,
        "gates_report_hash": body.gates_report_hash or existing.get("gates_report_hash", ""),
        "notes": body.notes,
        "status": "approved",
        "decision_origin": "human_confirmed",
        "recorded_by": recorded_by,
    }

    ws_approval.parent.mkdir(parents=True, exist_ok=True)
    ws_approval.write_text(json.dumps(approval, indent=2))

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (APPROVALS_DIR / f"{project_id}_{body.action}_confirmed_{ts}.json").write_text(
        json.dumps(approval, indent=2)
    )

    write_event("approval_granted", project_id, {
        "action": body.action,
        "version": approval["version"],
        "approved_by": body.approved_by,
        "status": "approved",
        "decision_origin": "human_confirmed",
        "recorded_by": recorded_by,
    })
    return approval


# ── Endpoint 3: rechazo humano ────────────────────────────────────────────────

@router.post("/{project_id}/reject", status_code=201)
def post_rejection(project_id: str, body: ConfirmBody):
    """Rechazo explícito de una propuesta. Solo humanos pueden rechazar."""
    if not body.approved_by or body.approved_by.lower().strip() in _RESERVED_APPROVERS:
        raise HTTPException(
            status_code=422,
            detail=f"approved_by='{body.approved_by}' es un valor reservado.",
        )

    now = datetime.now(timezone.utc).isoformat()
    rejection = {
        "action": body.action,
        "project_id": project_id,
        "rejected_by": body.approved_by,
        "rejected_at": now,
        "notes": body.notes,
        "status": "rejected",
        "decision_origin": "human_confirmed",
        "recorded_by": body.recorded_by or body.approved_by,
    }
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = now.replace(":", "").replace("-", "").replace("T", "_")[:15]
    (APPROVALS_DIR / f"{project_id}_{body.action}_rejected_{ts}.json").write_text(
        json.dumps(rejection, indent=2)
    )
    write_event("approval_rejected", project_id, rejection)
    return rejection


# ── Endpoint 4: lectura ───────────────────────────────────────────────────────

@router.get("/{project_id}")
def get_approvals(project_id: str):
    if not APPROVALS_DIR.exists():
        return []
    return [
        json.loads(f.read_text())
        for f in sorted(APPROVALS_DIR.glob(f"{project_id}_*.json"))
    ]
