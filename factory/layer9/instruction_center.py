"""
Capa 9 — Instruction Center.

Recibe y gestiona requerimientos de cliente asociados a una misión.
Almacenamiento: factory/layer9/requirements/<req_id>.json
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer9.requirement_schema import RequirementPayload

REQUIREMENTS_DIR = Path(__file__).parent / "requirements"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _req_path(req_id: str) -> Path:
    REQUIREMENTS_DIR.mkdir(parents=True, exist_ok=True)
    return REQUIREMENTS_DIR / f"{req_id}.json"


def submit_requirement(payload: dict) -> dict:
    """
    Registra un requerimiento nuevo. Retorna el requerimiento con req_id asignado.
    Valida la estructura mínima con RequirementPayload.
    """
    rp = RequirementPayload.from_dict(payload)
    errors = rp.validate()
    if errors:
        raise ValueError(f"Payload de requerimiento inválido: {errors}")

    req_id = str(uuid.uuid4())
    req: dict = {
        "req_id": req_id,
        "project_id": rp.project_id,
        "title": rp.title,
        "description": rp.description,
        "domains": rp.domains,
        "regulatory_refs": rp.regulatory_refs,
        "priority": rp.priority,
        "status": "pending",
        "submitted_at": _ts(),
        "processed_at": None,
    }
    _req_path(req_id).write_text(
        json.dumps(req, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    write_event("layer9_requirement_submitted", rp.project_id, {
        "req_id": req_id,
        "title": rp.title,
        "priority": rp.priority,
    })
    return req


def get_requirement(req_id: str) -> dict:
    """Retorna un requerimiento por su ID."""
    path = _req_path(req_id)
    if not path.exists():
        raise FileNotFoundError(f"Requerimiento no encontrado: {req_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_requirements(project_id: str | None = None) -> list[dict]:
    """Lista todos los requerimientos, opcionalmente filtrados por project_id."""
    REQUIREMENTS_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for json_file in sorted(REQUIREMENTS_DIR.glob("*.json")):
        try:
            req = json.loads(json_file.read_text(encoding="utf-8"))
            if project_id is None or req.get("project_id") == project_id:
                result.append(req)
        except Exception:
            continue
    result.sort(key=lambda r: r.get("submitted_at", ""))
    return result
