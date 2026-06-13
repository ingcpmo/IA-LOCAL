"""
Auditoría de fábrica — JSONL con hash chain SHA-256.

Patrón replicado de app/audit.py (21 CFR Part 11):
- Un archivo único: factory/audit/factory_audit.jsonl
- Cada entrada: entry_body → entry_hash = sha256(json.dumps(body, sort_keys=True))
- prev_entry_hash encadena con la entrada anterior ("GENESIS" al inicio)
- verify_chain() recorre todas las entradas en orden y verifica hashes e integridad

Eventos registrados: project_created, requirement_registered, workspace_created,
task_dispatched, gates_executed, diff_presented, approval_granted, approval_rejected,
release_created, deployment_created, deployment_started,
layer9_mission_created, layer9_mission_approved, layer9_requirement_submitted,
layer9_decision_recorded, layer9_risk_accepted
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path(__file__).parent.parent / "audit" / "factory_audit.jsonl"

_last_entry_hash: str | None = None

VALID_EVENTS = {
    # Eventos de fábrica (F1-F4)
    "project_created", "requirement_registered", "workspace_created",
    "task_dispatched", "gates_executed", "diff_presented",
    "approval_granted", "approval_rejected",
    "release_created", "deployment_created", "deployment_started",
    # Eventos Capa 9 Mission Control (F4.5a)
    "layer9_mission_created", "layer9_mission_approved",
    "layer9_requirement_submitted", "layer9_decision_recorded",
    "layer9_risk_accepted",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _compute_entry_hash(entry_body: dict) -> str:
    canonical = json.dumps(entry_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hash(canonical)


def _get_prev_hash() -> str:
    global _last_entry_hash
    if _last_entry_hash is not None:
        return _last_entry_hash

    if AUDIT_FILE.exists():
        try:
            lines = AUDIT_FILE.read_bytes().splitlines()
            for raw in reversed(lines):
                raw = raw.strip()
                if raw:
                    entry = json.loads(raw)
                    _last_entry_hash = entry.get("entry_hash", "GENESIS")
                    return _last_entry_hash
        except Exception:
            pass

    _last_entry_hash = "GENESIS"
    return "GENESIS"


def write_event(event_type: str, project_id: str, data: dict | None = None) -> dict:
    """
    Registra un evento en factory_audit.jsonl.
    Retorna la entrada escrita. Nunca lanza excepción (mismo patrón que app/audit.py).
    """
    global _last_entry_hash
    if event_type not in VALID_EVENTS:
        raise ValueError(f"Evento desconocido: {event_type}. Válidos: {VALID_EVENTS}")
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = _get_prev_hash()

        entry_body = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry_id": str(uuid.uuid4()),
            "event_type": event_type,
            "project_id": project_id,
            "data": data or {},
            "prev_entry_hash": prev_hash,
        }

        entry_hash = f"sha256:{_compute_entry_hash(entry_body)}"
        entry_body["entry_hash"] = entry_hash

        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_body, separators=(",", ":"), ensure_ascii=False) + "\n")

        _last_entry_hash = entry_hash
        return entry_body

    except Exception as e:
        return {"error": str(e)}


def verify_chain() -> dict:
    """
    Verifica la integridad de factory_audit.jsonl.
    Retorna reporte compatible con el contrato de /api/v1/audit/verify del base.
    """
    if not AUDIT_FILE.exists():
        return {
            "verified": True, "log_count": 0, "verified_count": 0,
            "hash_errors": 0, "chain_errors": 0, "failed_count": 0,
            "part11_compliant": False, "audit_file": str(AUDIT_FILE),
        }

    lines = [ln.strip() for ln in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    total = len(lines)
    verified_count = 0
    hash_errors = 0
    chain_errors = 0
    prev_hash = "GENESIS"

    for raw in lines:
        try:
            entry = json.loads(raw)
        except Exception:
            hash_errors += 1
            continue

        stored_hash = entry.get("entry_hash", "")
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        expected_hash = f"sha256:{_compute_entry_hash(body)}"

        if stored_hash != expected_hash:
            hash_errors += 1
            prev_hash = stored_hash
            continue

        if entry.get("prev_entry_hash") != prev_hash:
            chain_errors += 1
        else:
            verified_count += 1

        prev_hash = stored_hash

    return {
        "verified": hash_errors == 0 and chain_errors == 0,
        "log_count": total,
        "verified_count": verified_count,
        "hash_errors": hash_errors,
        "chain_errors": chain_errors,
        "failed_count": hash_errors + chain_errors,
        "hash_algo": "sha256",
        "part11_compliant": hash_errors == 0 and chain_errors == 0 and total > 0,
        "audit_file": str(AUDIT_FILE),
    }
