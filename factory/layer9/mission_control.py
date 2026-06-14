"""
Capa 9 — Mission Control.

Gestiona el ciclo de vida de misiones:
  create → draft → approved → closed

Almacenamiento: factory/layer9/missions/<project_id>.yaml
Sin postgres/redis — archivos YAML inmutables por versión.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer9.requirement_schema import (
    ALLOWED_ACTIONS,
    STOP_CONDITIONS,
    MissionApprovalSchema,
    MissionPayload,
)

MISSIONS_DIR = Path(__file__).parent / "missions"

# ── Misiones permitidas ────────────────────────────────────────────────────────

MISSION_STATUSES = ("draft", "approved", "closed", "suspended")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mission_path(project_id: str) -> Path:
    MISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return MISSIONS_DIR / f"{project_id}.yaml"


def _load_mission(project_id: str) -> dict:
    path = _mission_path(project_id)
    if not path.exists():
        raise FileNotFoundError(f"Misión no encontrada: {project_id}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_mission(mission: dict) -> None:
    path = _mission_path(mission["project_id"])
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(mission, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ── API pública ────────────────────────────────────────────────────────────────

def create_mission(payload: dict) -> dict:
    """
    Crea una misión nueva en estado draft.
    Valida el payload con MissionPayload.from_dict().
    Rechaza si ya existe una misión con el mismo project_id.
    """
    mp = MissionPayload.from_dict(payload)
    errors = mp.validate()
    if errors:
        raise ValueError(f"Payload de misión inválido: {errors}")

    path = _mission_path(mp.project_id)
    if path.exists():
        raise FileExistsError(
            f"Misión '{mp.project_id}' ya existe. "
            "Para actualizar usa approve_mission() o close_mission()."
        )

    approval = mp.mission_approval
    mission: dict[str, Any] = {
        "project_id": mp.project_id,
        "client_type": mp.client_type,
        "objective": mp.objective,
        "regulatory_scope": mp.regulatory_scope,
        "documents": mp.documents,
        "constraints": mp.constraints,
        "mission_approval": {
            "autonomy_level": approval.autonomy_level,
            "allowed_actions": approval.allowed_actions,
            "stop_conditions": approval.stop_conditions,
            "final_human_decision_required": approval.final_human_decision_required,
            "deploy_docker_if_gates_pass": approval.deploy_docker_if_gates_pass,
        },
        "linked_release": mp.linked_release,
        "status": "draft",
        "created_at": _ts(),
        "approved_at": None,
        "closed_at": None,
        "history": [],
    }
    _save_mission(mission)

    write_event("layer9_mission_created", mp.project_id, {
        "autonomy_level": approval.autonomy_level,
        "allowed_actions_count": len(approval.allowed_actions),
    })
    return {k: v for k, v in mission.items() if k != "history"}


_RESERVED_APPROVERS = {"human", "agent", "layer8_agent", "auto", "system", ""}


def approve_mission(
    project_id: str,
    autonomy_level: str | None = None,
    allowed_actions: list[str] | None = None,
    stop_conditions: list[str] | None = None,
    final_human_decision_required: list[str] | None = None,
    deploy_docker_if_gates_pass: bool | None = None,
    approved_by: str = "human",
    decision_origin: str = "human_confirmed",
    recorded_by: str = "",
) -> dict:
    """
    Aprueba una misión (draft → approved).
    decision_origin: 'human_confirmed' (única opción válida para aprobación real).
    recorded_by: identidad del proceso que escribe ('layer8_agent' o nombre del usuario).
    approved_by: nombre real del aprobador humano; no puede ser un valor reservado.
    """
    if approved_by.lower().strip() in _RESERVED_APPROVERS:
        raise ValueError(
            f"approved_by='{approved_by}' es un valor reservado. "
            "Usa el nombre real del aprobador humano (ej. 'Cesar', 'Maria')."
        )

    valid_origins = ("agent_proposed", "human_confirmed")
    if decision_origin not in valid_origins:
        raise ValueError(f"decision_origin='{decision_origin}' inválido. Válidos: {valid_origins}")

    _recorded_by = recorded_by or approved_by

    mission = _load_mission(project_id)
    if mission["status"] not in ("draft",):
        raise ValueError(
            f"Solo se puede aprobar una misión en estado 'draft'. Estado actual: {mission['status']}"
        )

    current_approval = mission.get("mission_approval", {})

    # Aplicar overrides opcionales con validación
    new_al = autonomy_level or current_approval.get("autonomy_level", "controlled_full")
    new_aa = allowed_actions or current_approval.get("allowed_actions", [])
    new_sc = stop_conditions or current_approval.get("stop_conditions", STOP_CONDITIONS.copy())
    new_fd = final_human_decision_required or current_approval.get("final_human_decision_required", [])
    new_dd = (
        deploy_docker_if_gates_pass
        if deploy_docker_if_gates_pass is not None
        else current_approval.get("deploy_docker_if_gates_pass", False)
    )

    temp_approval = MissionApprovalSchema(
        autonomy_level=new_al,
        allowed_actions=new_aa,
        stop_conditions=new_sc,
        final_human_decision_required=new_fd,
        deploy_docker_if_gates_pass=new_dd,
    )
    errors = temp_approval.validate()
    if errors:
        raise ValueError(f"Parámetros de aprobación inválidos: {errors}")

    now = _ts()
    mission["mission_approval"]["autonomy_level"] = new_al
    mission["mission_approval"]["allowed_actions"] = new_aa
    mission["mission_approval"]["stop_conditions"] = new_sc
    mission["mission_approval"]["final_human_decision_required"] = new_fd
    mission["mission_approval"]["deploy_docker_if_gates_pass"] = new_dd
    mission["status"] = "approved"
    mission["approved_at"] = now
    mission["history"].append({
        "event": "approved",
        "at": now,
        "by": approved_by,
        "decision_origin": decision_origin,
        "recorded_by": _recorded_by,
    })
    _save_mission(mission)

    write_event("layer9_mission_approved", project_id, {
        "approved_by": approved_by,
        "decision_origin": decision_origin,
        "recorded_by": _recorded_by,
        "autonomy_level": new_al,
        "allowed_actions": new_aa,
    })
    return {k: v for k, v in mission.items() if k != "history"}


def get_mission(project_id: str) -> dict:
    """Retorna la misión completa (incluyendo history)."""
    return _load_mission(project_id)


def list_missions(status: str | None = None) -> list[dict]:
    """Lista todas las misiones, opcionalmente filtradas por status."""
    MISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for yaml_file in sorted(MISSIONS_DIR.glob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                m = yaml.safe_load(f)
            if status is None or m.get("status") == status:
                result.append({k: v for k, v in m.items() if k != "history"})
        except Exception:
            continue
    return result


def close_mission(project_id: str, reason: str = "", closed_by: str = "human") -> dict:
    """Cierra una misión (approved → closed)."""
    mission = _load_mission(project_id)
    if mission["status"] == "closed":
        raise ValueError(f"Misión '{project_id}' ya está cerrada.")

    now = _ts()
    mission["status"] = "closed"
    mission["closed_at"] = now
    mission["history"].append({
        "event": "closed",
        "at": now,
        "by": closed_by,
        "reason": reason,
    })
    _save_mission(mission)
    return {k: v for k, v in mission.items() if k != "history"}


def is_action_allowed(project_id: str, action: str) -> bool:
    """Comprueba si una acción está en allowed_actions de una misión aprobada."""
    try:
        mission = _load_mission(project_id)
    except FileNotFoundError:
        return False
    if mission.get("status") != "approved":
        return False
    return action in mission.get("mission_approval", {}).get("allowed_actions", [])
