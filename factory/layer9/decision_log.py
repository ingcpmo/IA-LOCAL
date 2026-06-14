"""
Capa 9 — Decision Log.

Registra decisiones explícitas de la gobernanza (humano o Mission Control).
Almacenamiento: factory/layer9/decisions/decisions.jsonl

Cada línea es un JSON independiente con:
  decision_id, project_id, action, decision (approve|reject|defer),
  rationale, decided_by, timestamp
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

DECISIONS_FILE = Path(__file__).parent / "decisions" / "decisions.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_decision(
    project_id: str,
    action: str,
    decision: str,
    rationale: str = "",
    decided_by: str = "human",
    decision_origin: str = "human_confirmed",
    recorded_by: str = "layer8_agent",
    metadata: dict | None = None,
) -> dict:
    """
    Escribe una decisión en el log.
    decision        ∈ {approve, reject, defer, conditional_approve}
    decision_origin ∈ {agent_proposed, human_confirmed}
      - agent_proposed:  el agente registra una propuesta; requiere confirmación humana.
      - human_confirmed: el humano explícitamente aprobó/rechazó.
    recorded_by: identidad del proceso que escribe la entrada (no el aprobador).
      - "layer8_agent": fue escrita por el agente de Capa 8 / API de fábrica.
      - nombre del usuario (ej. "Cesar"): fue escrita por un humano vía consola o endpoint /confirm.
    decided_by: identidad del actor que toma la decisión (solo válido para human_confirmed).
    """
    valid_decisions = ("approve", "reject", "defer", "conditional_approve")
    if decision not in valid_decisions:
        raise ValueError(f"Decisión inválida: {decision!r}. Válidas: {valid_decisions}")

    valid_origins = ("agent_proposed", "human_confirmed")
    if decision_origin not in valid_origins:
        raise ValueError(f"decision_origin inválido: {decision_origin!r}. Válidos: {valid_origins}")

    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "decision_id": str(uuid.uuid4()),
        "project_id": project_id,
        "action": action,
        "decision": decision,
        "rationale": rationale,
        "decided_by": decided_by,
        "decision_origin": decision_origin,
        "recorded_by": recorded_by,
        "metadata": metadata or {},
        "timestamp": _ts(),
    }

    with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    write_event("layer9_decision_recorded", project_id, {
        "decision_id": entry["decision_id"],
        "action": action,
        "decision": decision,
        "decided_by": decided_by,
    })
    return entry


def list_decisions(project_id: str | None = None, action: str | None = None) -> list[dict]:
    """Lista decisiones, filtradas opcionalmente por project_id y/o action."""
    if not DECISIONS_FILE.exists():
        return []
    result = []
    for line in DECISIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if project_id and entry.get("project_id") != project_id:
            continue
        if action and entry.get("action") != action:
            continue
        result.append(entry)
    return result


def get_project_decisions(project_id: str) -> list[dict]:
    """Alias semántico: retorna todas las decisiones de un proyecto."""
    return list_decisions(project_id=project_id)
