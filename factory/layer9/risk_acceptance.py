"""
Capa 9 — Risk Acceptance.

Registra riesgos identificados y su aceptación formal.
Almacenamiento: factory/layer9/risks/risks.jsonl

Cada línea: risk_id, project_id, risk_description, severity,
             mitigation, accepted_by, accepted_at, status
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

RISKS_FILE = Path(__file__).parent / "risks" / "risks.jsonl"

SEVERITY_LEVELS = ("low", "medium", "high", "critical")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def accept_risk(
    project_id: str,
    risk_description: str,
    severity: str,
    mitigation: str = "",
    accepted_by: str = "human",
    metadata: dict | None = None,
) -> dict:
    """
    Registra la aceptación formal de un riesgo.
    severity ∈ {low, medium, high, critical}
    """
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"Severidad inválida: {severity!r}. Válidas: {SEVERITY_LEVELS}")
    if not risk_description:
        raise ValueError("risk_description no puede estar vacío")

    RISKS_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "risk_id": str(uuid.uuid4()),
        "project_id": project_id,
        "risk_description": risk_description,
        "severity": severity,
        "mitigation": mitigation,
        "accepted_by": accepted_by,
        "metadata": metadata or {},
        "status": "accepted",
        "accepted_at": _ts(),
    }

    with open(RISKS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    write_event("layer9_risk_accepted", project_id, {
        "risk_id": entry["risk_id"],
        "severity": severity,
        "accepted_by": accepted_by,
    })
    return entry


def list_risks(
    project_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Lista riesgos, filtrables por project_id, severity y/o status."""
    if not RISKS_FILE.exists():
        return []
    result = []
    for line in RISKS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if project_id and entry.get("project_id") != project_id:
            continue
        if severity and entry.get("severity") != severity:
            continue
        if status and entry.get("status") != status:
            continue
        result.append(entry)
    return result
