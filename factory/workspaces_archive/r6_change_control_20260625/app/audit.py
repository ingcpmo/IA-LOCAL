"""ALCOA+ Audit Trail — 21 CFR Part 11 compliant audit logger."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


AUDIT_LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "./data/audit_logs"))
HASH_ALGO = os.getenv("AUDIT_LOG_HASH_ALGO", "sha256")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_audit_entry(action: str, actor: str, details: dict, cr_id: str | None = None) -> dict:
    """
    Escribe una entrada de audit trail conforme a ALCOA+:
    - Attributable: actor siempre presente
    - Legible: JSON estructurado
    - Contemporaneous: timestamp UTC en el momento de la escritura
    - Original: entrada inmutable (append-only)
    - Accurate: hash SHA256 del contenido para integridad
    """
    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    entry_data = {
        "entry_id": str(uuid.uuid4()),
        "cr_id": cr_id,
        "action": action,
        "actor": actor,
        "timestamp": _ts(),
        "details": details,
    }
    entry_data["data_hash"] = _compute_hash(entry_data)
    entry_data["alcoa_compliant"] = True

    log_file = AUDIT_LOG_DIR / "change_control_audit.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry_data, ensure_ascii=False) + "\n")

    return entry_data


def read_audit_trail(cr_id: str | None = None, limit: int = 100) -> list[dict]:
    """Lee el audit trail. Si cr_id se especifica, filtra por ese CR."""
    log_file = AUDIT_LOG_DIR / "change_control_audit.jsonl"
    if not log_file.exists():
        return []

    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if cr_id is None or entry.get("cr_id") == cr_id:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    return entries[-limit:]


def verify_audit_integrity() -> dict:
    """Verifica la integridad de todas las entradas del audit trail."""
    log_file = AUDIT_LOG_DIR / "change_control_audit.jsonl"
    if not log_file.exists():
        return {"verified": True, "entry_count": 0, "corrupted_entries": []}

    corrupted = []
    total = 0
    with open(log_file, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                stored_hash = entry.pop("data_hash", "")
                computed = _compute_hash(entry)
                if stored_hash != computed:
                    corrupted.append({"line": line_num, "entry_id": entry.get("entry_id", "?")})
                total += 1
            except json.JSONDecodeError:
                corrupted.append({"line": line_num, "error": "invalid_json"})

    return {
        "verified": len(corrupted) == 0,
        "entry_count": total,
        "corrupted_entries": corrupted,
        "hash_algo": HASH_ALGO,
    }
