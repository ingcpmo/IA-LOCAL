"""
Capa 9 — Rutas API Mission Control (F4.5d).

Expone las operaciones de Mission Control de Capa 9 en el factory-api.
"""

import json
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
from factory.layer9.human_review_queue import list_pending, get_queue_summary, mark_reviewed
from factory.layer8.release_candidate_builder import get_rc, confirm_rc

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
    approved_by: str                 # nombre real del aprobador humano (obligatorio)
    decision_origin: str = "human_confirmed"
    recorded_by: str = ""            # se hereda de approved_by si vacío


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
    decided_by: str                   # nombre real del actor (obligatorio)
    decision_origin: str = "human_confirmed"
    recorded_by: str = ""             # se hereda de decided_by si vacío
    metadata: dict[str, Any] = {}


class RiskAccept(BaseModel):
    risk_description: str
    severity: str
    mitigation: str = ""
    accepted_by: str = "human"
    metadata: dict[str, Any] = {}


class ReviewDecision(BaseModel):
    approved_by: str
    notes: str = ""


class ReviewReturn(BaseModel):
    approved_by: str
    notes: str = ""
    adjustments_needed: str = ""


class MissionReturn(BaseModel):
    returned_by: str
    reason: str = ""


class MissionReject(BaseModel):
    rejected_by: str
    reason: str = ""


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
            decision_origin=body.decision_origin,
            recorded_by=body.recorded_by,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
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


# ── Cola de revisión humana ────────────────────────────────────────────────────

@router.get("/review-queue")
def get_review_queue():
    """Lista RCs pendientes de revisión humana + resumen por estado."""
    return {
        "pending": list_pending(),
        "summary": get_queue_summary(),
    }


@router.get("/review/{rc_id}")
def get_review_detail(rc_id: str):
    rc = get_rc(rc_id)
    if rc is None:
        raise HTTPException(404, f"RC '{rc_id}' no encontrado")
    return rc


@router.post("/review/{rc_id}/approve")
def post_approve_rc(rc_id: str, body: ReviewDecision):
    try:
        rc = get_rc(rc_id)
        if rc is None:
            raise HTTPException(404, f"RC '{rc_id}' no encontrado")
        if rc.get("status") in ("approved", "rejected"):
            raise HTTPException(409, {
                "error": "rc_already_finalized",
                "rc_id": rc_id,
                "current_status": rc["status"],
                "previously_decided_by": rc.get("approved_by", "?"),
                "previously_decided_at": rc.get("decided_at", "?"),
            })
        result = confirm_rc(rc_id, body.approved_by, "approved", body.notes)
        mark_reviewed(rc_id, "approved", body.approved_by)
        return result
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/review/{rc_id}/reject")
def post_reject_rc(rc_id: str, body: ReviewDecision):
    try:
        rc = get_rc(rc_id)
        if rc is None:
            raise HTTPException(404, f"RC '{rc_id}' no encontrado")
        if rc.get("status") in ("approved", "rejected"):
            raise HTTPException(409, {
                "error": "rc_already_finalized",
                "rc_id": rc_id,
                "current_status": rc["status"],
                "previously_decided_by": rc.get("approved_by", "?"),
                "previously_decided_at": rc.get("decided_at", "?"),
            })
        result = confirm_rc(rc_id, body.approved_by, "rejected", body.notes)
        mark_reviewed(rc_id, "rejected", body.approved_by)
        return result
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/review/{rc_id}/return")
def post_return_rc(rc_id: str, body: ReviewReturn):
    try:
        notes = f"{body.notes}\nAjustes: {body.adjustments_needed}".strip()
        result = confirm_rc(rc_id, body.approved_by, "returned_to_adjustments", notes)
        mark_reviewed(rc_id, "returned", body.approved_by)
        return result
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/return")
def post_return_mission(project_id: str, body: MissionReturn):
    """Devuelve una misión a ajustes."""
    try:
        from factory.layer9.mission_control import _load_mission, _save_mission
        from factory.core.audit_writer import write_event as _we
        from datetime import datetime, timezone
        mission = _load_mission(project_id)
        mission["status"] = "returned_to_adjustments"
        mission["returned_by"] = body.returned_by
        mission["return_reason"] = body.reason
        mission["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_mission(mission)
        _we("layer9_decision_recorded", project_id, {
            "action": "mission_returned",
            "returned_by": body.returned_by,
            "reason": body.reason,
        })
        return {"project_id": project_id, "status": "returned_to_adjustments",
                "returned_by": body.returned_by}
    except FileNotFoundError:
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/reject")
def post_reject_mission(project_id: str, body: MissionReject):
    """Rechaza permanentemente una misión (acción irreversible)."""
    try:
        from factory.layer9.mission_control import _load_mission, _save_mission
        from factory.core.audit_writer import write_event as _we
        from datetime import datetime, timezone
        mission = _load_mission(project_id)
        if mission.get("status") == "rejected":
            raise HTTPException(409, f"Misión '{project_id}' ya fue rechazada.")
        mission["status"] = "rejected"
        mission["rejected_by"] = body.rejected_by
        mission["rejection_reason"] = body.reason
        mission["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_mission(mission)
        _we("layer9_decision_recorded", project_id, {
            "action": "mission_rejected",
            "rejected_by": body.rejected_by,
            "reason": body.reason,
        })
        return {"project_id": project_id, "status": "rejected",
                "rejected_by": body.rejected_by}
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")
    except Exception as e:
        raise HTTPException(500, str(e))


# ── RC Canónico ────────────────────────────────────────────────────────────────

_RESERVED_CANONICAL = {"human", "agent", "system", "admin", "capa8", "capa9", "layer8"}


class MarkCanonical(BaseModel):
    marked_by: str


@router.get("/projects/{project_id}/rcs")
def get_project_rcs(project_id: str):
    """Lista todos los RC manifests de un proyecto (read-only, para Mission Control)."""
    rc_dir = _FACTORY_ROOT / "release_candidates" / project_id
    if not rc_dir.exists():
        return {"project_id": project_id, "rcs": []}
    rcs = []
    for f in sorted(rc_dir.rglob("rc_manifest.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rcs.append({
                "rc_id": d.get("rc_id"),
                "version": d.get("version"),
                "status": d.get("status"),
                "is_canonical": d.get("is_canonical"),
                "approved_by": d.get("approved_by"),
                "decided_at": d.get("decided_at"),
                "proposed_at": d.get("proposed_at"),
            })
        except Exception:
            continue
    return {"project_id": project_id, "rcs": rcs}


@router.get("/projects/{project_id}/canonical")
def get_canonical_rc(project_id: str):
    """Devuelve el RC marcado como canónico para el project_id. 404 si no hay ninguno."""
    import json
    from pathlib import Path
    rc_base = Path(__file__).parent.parent.parent.parent / "factory" / "release_candidates" / project_id
    if not rc_base.exists():
        raise HTTPException(404, f"No hay RCs para '{project_id}'")
    for manifest_file in rc_base.rglob("rc_manifest.json"):
        try:
            d = json.loads(manifest_file.read_text(encoding="utf-8"))
            if d.get("is_canonical") is True:
                return d
        except Exception:
            continue
    raise HTTPException(404, f"Sin RC canónico marcado para '{project_id}'")


@router.post("/review/{rc_id}/mark-canonical")
def post_mark_canonical(rc_id: str, body: MarkCanonical):
    """Marca un RC aprobado como canónico. Solo un RC canónico por project_id a la vez."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from factory.core.audit_writer import write_event as _we

    if body.marked_by.lower().strip() in _RESERVED_CANONICAL:
        raise HTTPException(422, f"marked_by='{body.marked_by}' es reservado. Usa el nombre real.")

    rc = get_rc(rc_id)
    if rc is None:
        raise HTTPException(404, f"RC '{rc_id}' no encontrado")
    if rc.get("status") != "approved":
        raise HTTPException(409, {
            "error": "rc_not_approved",
            "rc_id": rc_id,
            "current_status": rc.get("status"),
            "detail": "Solo se puede marcar como canónico un RC con status=approved",
        })

    project_id = rc["project_id"]
    now = datetime.now(timezone.utc).isoformat()
    rc_base = Path(__file__).parent.parent.parent.parent / "factory" / "release_candidates" / project_id

    prev_canonical_id = None
    for manifest_file in rc_base.rglob("rc_manifest.json"):
        try:
            d = json.loads(manifest_file.read_text(encoding="utf-8"))
            if d.get("is_canonical") is True and d.get("rc_id") != rc_id:
                prev_canonical_id = d.get("rc_id")
            d["is_canonical"] = (d.get("rc_id") == rc_id)
            if d.get("rc_id") == rc_id:
                d["is_canonical_marked_by"] = body.marked_by
                d["is_canonical_marked_at"] = now
            manifest_file.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            continue

    if prev_canonical_id:
        _we("rc_unmarked_canonical", project_id, {
            "rc_id": prev_canonical_id,
            "unmarked_by": body.marked_by,
            "reason": f"superseded by {rc_id}",
        })

    _we("rc_marked_canonical", project_id, {
        "rc_id": rc_id,
        "marked_by": body.marked_by,
        "prev_canonical": prev_canonical_id,
    })

    return {
        "rc_id": rc_id,
        "project_id": project_id,
        "is_canonical": True,
        "marked_by": body.marked_by,
        "marked_at": now,
        "prev_canonical_unmarked": prev_canonical_id,
    }


# ── Revisión de misión ─────────────────────────────────────────────────────────

_RESERVED_REVISE  = {"human", "agent", "system", "admin", "capa8", "capa9", "layer8"}
_EDITABLE_FIELDS  = {"objective", "client_type", "regulatory_scope", "documents",
                     "constraints", "mission_approval", "linked_release"}
_BLOCKED_STATUSES = {"rejected", "closed"}

_FACTORY_ROOT = Path(__file__).parent.parent.parent


class MissionRevise(BaseModel):
    changes: dict[str, Any]
    reason: str
    changed_by: str


def _has_generated_code(project_id: str) -> bool:
    app_dir = _FACTORY_ROOT / "workspaces" / project_id / "app"
    if not app_dir.exists():
        return False
    return any(app_dir.rglob("*.py"))


def _has_approved_rc(project_id: str) -> bool:
    rc_dir = _FACTORY_ROOT / "release_candidates" / project_id
    if not rc_dir.exists():
        return False
    for f in rc_dir.rglob("rc_manifest.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("status") == "approved":
                return True
        except Exception:
            continue
    return False


@router.post("/missions/{project_id}/revise")
def post_revise_mission(project_id: str, body: MissionRevise):
    """
    Modifica campos de una misión según la matriz de estados W1.
    Guarda snapshot previo en missions_history/ y audita el cambio.
    """
    from factory.layer9.mission_control import _load_mission, _save_mission
    from factory.core.audit_writer import write_event as _we
    from datetime import datetime, timezone
    import yaml

    if not body.reason.strip():
        raise HTTPException(422, "El campo 'reason' es obligatorio y no puede estar vacío.")
    if body.changed_by.lower().strip() in _RESERVED_REVISE:
        raise HTTPException(422, f"changed_by='{body.changed_by}' es reservado. Usa el nombre real.")

    invalid_fields = set(body.changes.keys()) - _EDITABLE_FIELDS
    if invalid_fields:
        raise HTTPException(422, {
            "error": "campos_no_editables",
            "fields": sorted(invalid_fields),
            "editable": sorted(_EDITABLE_FIELDS),
        })

    try:
        mission = _load_mission(project_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")

    status = mission.get("status", "")

    if status in _BLOCKED_STATUSES:
        raise HTTPException(409, {
            "error": "mission_not_editable",
            "current_status": status,
            "detail": f"Las misiones en estado '{status}' no pueden modificarse.",
        })

    re_approve_required = False

    if status == "approved":
        if _has_approved_rc(project_id):
            raise HTTPException(409, {
                "error": "rc_approved_exists",
                "current_status": status,
                "detail": "Existe un RC aprobado. Crea una nueva misión para la versión siguiente.",
            })
        if _has_generated_code(project_id):
            raise HTTPException(409, {
                "error": "code_already_generated",
                "current_status": status,
                "detail": "El workspace ya tiene código generado. Crea una nueva misión.",
            })
        re_approve_required = True

    # Guardar snapshot en missions_history/
    now = datetime.now(timezone.utc)
    history_dir = _FACTORY_ROOT / "layer9" / "missions_history" / project_id
    history_dir.mkdir(parents=True, exist_ok=True)
    rev_id = f"rev_{now.strftime('%Y%m%dT%H%M%S')}"
    snapshot = {
        "rev_id": rev_id,
        "changed_by": body.changed_by,
        "reason": body.reason,
        "changed_at": now.isoformat(),
        "previous_version": dict(mission),
    }
    (history_dir / f"{rev_id}.yaml").write_text(
        yaml.dump(snapshot, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # Aplicar cambios
    for field, value in body.changes.items():
        mission[field] = value
    mission["updated_at"] = now.isoformat()
    if re_approve_required:
        mission["status"] = "draft"
        mission["approved_at"] = None

    _save_mission(mission)

    _we("layer9_mission_revised", project_id, {
        "rev_id": rev_id,
        "changed_by": body.changed_by,
        "reason": body.reason,
        "fields_changed": sorted(body.changes.keys()),
        "re_approve_required": re_approve_required,
    })

    return {
        "project_id": project_id,
        "rev_id": rev_id,
        "status": mission["status"],
        "fields_changed": sorted(body.changes.keys()),
        "re_approve_required": re_approve_required,
        "snapshot_saved": str(history_dir / f"{rev_id}.yaml"),
    }
