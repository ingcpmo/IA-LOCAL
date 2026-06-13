"""
Capa 9 — Rutas API Mission Control (F4.5d).

Expone las operaciones de Mission Control de Capa 9 en el factory-api.
"""

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.layer9.mission_control import (
    create_mission,
    approve_mission,
    get_mission,
    list_missions,
)
from factory.layer9.instruction_center import submit_requirement, list_requirements
from factory.layer9.decision_log import write_decision, list_decisions, get_project_decisions
from factory.layer9.risk_acceptance import accept_risk, list_risks

router = APIRouter(prefix="/api/v1/layer9", tags=["layer9"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class MissionCreate(BaseModel):
    project_id: str
    client_type: str
    objective: str
    regulatory_scope: list[str]
    documents: dict[str, str]
    constraints: list[str]
    mission_approval: dict[str, Any]
    linked_release: dict[str, Any] = {}


class MissionApprove(BaseModel):
    autonomy_level: str | None = None
    allowed_actions: list[str] | None = None
    stop_conditions: list[str] | None = None
    final_human_decision_required: list[str] | None = None
    deploy_docker_if_gates_pass: bool | None = None
    approved_by: str = "human"


class RequirementCreate(BaseModel):
    title: str
    description: str
    domains: list[str] = []
    regulatory_refs: list[str] = []
    priority: str = "normal"


class DecisionCreate(BaseModel):
    action: str
    decision: str
    rationale: str = ""
    decided_by: str = "human"
    metadata: dict[str, Any] = {}


class RiskAccept(BaseModel):
    risk_description: str
    severity: str
    mitigation: str = ""
    accepted_by: str = "human"
    metadata: dict[str, Any] = {}


# ── Misiones ───────────────────────────────────────────────────────────────────

@router.post("/missions", status_code=201)
def post_mission(body: MissionCreate):
    try:
        return create_mission(body.model_dump())
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/approve")
def post_approve_mission(project_id: str, body: MissionApprove):
    try:
        return approve_mission(
            project_id,
            autonomy_level=body.autonomy_level,
            allowed_actions=body.allowed_actions,
            stop_conditions=body.stop_conditions,
            final_human_decision_required=body.final_human_decision_required,
            deploy_docker_if_gates_pass=body.deploy_docker_if_gates_pass,
            approved_by=body.approved_by,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/missions")
def get_missions(status: str | None = Query(default=None)):
    return list_missions(status=status)


@router.get("/missions/{project_id}")
def get_mission_detail(project_id: str):
    try:
        return get_mission(project_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")


# ── Requerimientos ─────────────────────────────────────────────────────────────

@router.post("/requirements/{project_id}", status_code=201)
def post_requirement(project_id: str, body: RequirementCreate):
    try:
        payload = {"project_id": project_id, **body.model_dump()}
        return submit_requirement(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Decisiones ─────────────────────────────────────────────────────────────────

@router.get("/decisions")
def get_decisions(project_id: str | None = Query(default=None)):
    return list_decisions(project_id=project_id)


@router.get("/decisions/{project_id}")
def get_project_decision_list(project_id: str):
    return get_project_decisions(project_id)


# ── Riesgos ────────────────────────────────────────────────────────────────────

@router.post("/risks/{project_id}/accept", status_code=201)
def post_accept_risk(project_id: str, body: RiskAccept):
    try:
        return accept_risk(
            project_id=project_id,
            risk_description=body.risk_description,
            severity=body.severity,
            mitigation=body.mitigation,
            accepted_by=body.accepted_by,
            metadata=body.metadata,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
