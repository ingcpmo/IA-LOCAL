"""
Capa 9 — Rutas API Mission Control (F4.5d).

Expone las operaciones de Mission Control de Capa 9 en el factory-api.

W5: capa HTTP fina. La lógica de evidencia (W3), consola de pruebas (W4)
y dashboard GMP (W4.1/W4.1.1) vive en factory/services/ — este módulo
solo define schemas, rutas de gobierno y delegaciones. Ver:
  factory/services/mission_evidence_service.py
  factory/services/test_console_service.py
  factory/services/gmp_report_service.py
"""

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
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
from factory.services import design_mode_service as _design
from factory.services import dossier_generator_service as _dossier
from factory.services import case_presentation_service as _casepres
from factory.services import regulatory_connector_service as _regconn
from factory.services import gmp_report_service
from factory.services import validation_readiness_service as _valready
from factory.services import mission_evidence_service as _evidence
from factory.services import test_console_service as _console

router = APIRouter(prefix="/api/v1/layer9", tags=["layer9"])

_FACTORY_ROOT = Path(__file__).parent.parent.parent

# Alias de compatibilidad (tests y consumidores históricos referencian estos
# nombres en el namespace de layer9; la implementación vive en services/).
_build_mission_summary = _evidence.build_mission_summary
_build_gmp_report = gmp_report_service.build_gmp_report
_validate_run_by = _console.validate_run_by


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


# ── W3: Visor de evidencia por misión ────────────────────────────────────────
# READ-ONLY — no escriben en la cadena de auditoría.
# Lógica en factory/services/mission_evidence_service.py.

@router.get("/missions/{project_id}/summary")
def get_mission_summary(project_id: str, request: Request, response: Response):
    """
    Resumen consolidado de la misión: ~5KB, cacheable con ETag.
    Si If-None-Match coincide con el ETag actual → 304 Not Modified.
    Read-only: no escribe en la cadena de auditoría.
    """
    body = _evidence.build_mission_summary(project_id)
    etag = body["etag"]
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=10"
    return body


@router.get("/missions/{project_id}/design")
def get_mission_design(project_id: str):
    """Lista archivos en factory/designs/{project_id}/. Read-only."""
    return _evidence.read_design(project_id)


@router.get("/missions/{project_id}/agents")
def get_mission_agents(project_id: str):
    """
    Lee agent_design_proposal.yaml y devuelve lista estructurada.
    Distingue profiles heredados de agents nuevos. Read-only.
    """
    return _evidence.read_agents(project_id)


@router.get("/missions/{project_id}/headless")
def get_mission_headless(project_id: str):
    """
    Parsea el log JSONL del CLI Claude del workspace.
    Devuelve estructura plana con costo, turns, modelos. Read-only.
    """
    return _evidence.read_headless(project_id)


@router.get("/missions/{project_id}/tests")
def get_mission_tests(project_id: str):
    """Lee test_report.json del workspace. Read-only."""
    return _evidence.read_tests(project_id)


@router.get("/missions/{project_id}/rcs")
def get_mission_rcs(project_id: str):
    """
    Lista todos los RC manifests de un proyecto con detalle completo.
    Read-only, no requiere escritura en auditoría.
    """
    return _evidence.read_rcs(project_id)


@router.get("/missions/{project_id}/deployment")
def get_mission_deployment(project_id: str):
    """
    Estado del deployment Docker del proyecto.
    Hace health check en vivo vía host.docker.internal. Read-only.
    """
    return _evidence.read_deployment(project_id)


@router.get("/missions/{project_id}/audit")
def get_mission_audit(project_id: str, limit: int = Query(default=50, le=200)):
    """
    Eventos de auditoría filtrados por project_id (últimos N).
    Read-only — no escribe en cadena.
    """
    return _evidence.read_audit(project_id, limit=limit)


@router.get("/missions/{project_id}/design/file")
def get_design_file(project_id: str, path: str = Query(...)):
    """
    Lee un archivo de factory/designs/{project_id}/.
    Política: solo .yaml, .yml, .md — bloquea traversal y secretos.
    """
    return _evidence.read_design_file(project_id, path)


@router.get("/missions/{project_id}/rc/{rc_id}/file")
def get_rc_artifact_file(project_id: str, rc_id: str, path: str = Query(...)):
    """
    Lee un artefacto de factory/release_candidates/{project_id}/{rc_id}/.
    Política: solo .json, .log, .txt, .md — bloquea traversal y secretos.
    El path no puede escapar del rc_id solicitado.
    """
    return _evidence.read_rc_artifact_file(project_id, rc_id, path)


@router.get("/missions/{project_id}/deployment/file")
def get_deployment_file(project_id: str, path: str = Query(...)):
    """
    Lee un archivo de factory/deployments/{project_id}/.
    Política estricta: bloquea .env, data/, knowledge/corpus/, releases/, secretos.
    """
    return _evidence.read_deployment_file(project_id, path)


# ── W4 — Consola de pruebas funcionales por agente ───────────────────────────
# Separación reader/executor (regla U5) y anti-SSRF documentadas en
# factory/services/test_console_service.py, donde vive la lógica.

class TestRunRequest(BaseModel):
    test_id: str
    run_by: str


class TestRunSuiteRequest(BaseModel):
    agent_id: str
    run_by: str


@router.get("/missions/{project_id}/test-catalog")
def get_test_catalog(project_id: str):
    """READER — catálogo curado de pruebas de la misión. No ejecuta nada, no audita."""
    return _console.read_catalog(project_id)


@router.get("/missions/{project_id}/test-results")
def get_test_results(project_id: str, limit: int = Query(default=50, le=200)):
    """READER — historial de pruebas ya ejecutadas (read-only). No audita."""
    return _console.read_results(project_id, limit=limit)


@router.post("/missions/{project_id}/test/run")
def post_run_test(project_id: str, body: TestRunRequest):
    """
    EXECUTOR — ejecuta UN caso de prueba del catálogo curado contra el
    deployment real de la misión. Audita exactamente 1 evento.
    """
    return _console.run_test(project_id, body.test_id, body.run_by)


@router.post("/missions/{project_id}/test/run-suite")
def post_run_test_suite(project_id: str, body: TestRunSuiteRequest):
    """
    EXECUTOR — ejecuta todos los casos de un agente en secuencia.
    Un solo evento de auditoría agent_suite_tested con resumen N/M PASS
    (cada resultado individual también se persiste en test_results).
    """
    return _console.run_suite(project_id, body.agent_id, body.run_by)


# ── W4.1 — Dashboard GMP + informe PDF por misión ────────────────────────────
# Agregador y textos en factory/services/gmp_report_service.py.

@router.get("/missions/{project_id}/gmp-report")
def get_gmp_report(project_id: str):
    """
    W4.1 — Dashboard GMP: consolida TODA la evidencia real de la misión en
    una estructura narrativa de dos niveles (ejecutivo + técnico). Read-only,
    NO audita. Datos faltantes se exponen como "no_disponible".
    """
    return gmp_report_service.build_gmp_report(project_id)


@router.get("/missions/{project_id}/gmp-report.pdf")
def get_gmp_report_pdf(project_id: str, record_by: str | None = Query(default=None)):
    """
    W4.1.1 — Genera el informe PDF robusto (18 secciones) a partir del MISMO
    agregador que /gmp-report. Read-only por defecto (NO audita). Si se pasa
    ?record_by= con un nombre real, audita exactamente 1 evento de
    trazabilidad de "informe generado" (no re-audita nada de W4).
    """
    from datetime import datetime, timezone

    from factory.core.pdf_report_robust import compose_robust_report

    report = gmp_report_service.build_gmp_report(project_id)
    pdf_bytes = compose_robust_report(report, project_id)

    if record_by:
        name = _console.validate_run_by(record_by)
        from factory.core.audit_writer import write_event as _we
        _we("gmp_report_generated", project_id, {
            "record_by": name,
            "canonical_rc": report["meta"]["canonical_rc"],
        })

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    filename = f"informe_gmp_{project_id}_{ts}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── W6 — Vistas MODO DISEÑO (read-only, NUNCA auditan, cero HTTP externo) ─────
# Sirven especificaciones locales (yaml/jsonl) para las vistas de Inteligencia:
# tareas operativas, fuentes regulatorias y memoria de casos. No existe ejecutor
# ni conector real; ver factory/docs/W6_MISSION_CONTROL_ENTERPRISE.md.

@router.get("/agent-tasks")
def get_agent_tasks():
    return _design.read_agent_tasks()


@router.get("/agent-tasks/{task_id}")
def get_agent_task(task_id: str):
    task = _design.read_agent_task(task_id)
    if task is None:
        raise HTTPException(404, f"TaskSpec '{task_id}' no existe")
    return task


@router.get("/regulatory-sources")
def get_regulatory_sources():
    # W6.3 — el estado vivo del conector openFDA se superpone al registry
    return _regconn.annotate_sources(_design.read_source_registry())


@router.get("/case-memory")
def get_case_memory(limit: int = Query(default=100, ge=1, le=1000)):
    # W6.4 — cada caso lleva bloque `presentation` determinista (read-only)
    data = _design.read_case_memory(limit=limit)
    data["cases"] = _casepres.enrich_cases(data["cases"])
    return data


@router.get("/case-memory/search")
def search_case_memory(q: str = Query(default=""), limit: int = Query(default=20, ge=1, le=100)):
    data = _design.search_case_memory(q, limit=limit)
    data["results"] = _casepres.enrich_cases(data["results"])
    return data


# ── W6.4 — Presentación gobernada de la memoria (read-only, NUNCA audita) ─────
# Interpretación determinista sobre datos ya locales: relevancia desde la
# clasificación FDA, routing caso→agente, cita trazable, estado del detalle.
# NO es juicio GMP. El compare es informativo (gmp_decision=False siempre).

@router.get("/case-memory/{case_id}")
def get_case_detail_enriched(case_id: str):
    """Un caso enriquecido (record + presentation). Lectura local, sin auditar."""
    case = _casepres.read_case(case_id)
    if case is None:
        raise HTTPException(404, f"Caso '{case_id}' no está en la memoria")
    return case


@router.get("/case-memory/{case_id}/compare/{project_id}")
def get_case_mission_compare(case_id: str, project_id: str):
    """Cruce informativo caso↔misión: tags, agentes, pruebas, dossier. Solo
    hechos locales — jamás aprueba, decide ni escribe."""
    out = _casepres.compare_with_mission(case_id, project_id)
    if out is None:
        raise HTTPException(404, f"Caso '{case_id}' no está en la memoria")
    if out.get("error") == "mission_not_found":
        raise HTTPException(404, f"Misión '{project_id}' no existe")
    return out


# ── W6.3 — Conector online controlado (openFDA Drug Enforcement) ──────────────
# Un solo sector. Cada llamada online exige nombre real y queda auditada.
# Rate limit duro en el servicio: 60s entre llamadas · 10/día UTC · limit ≤ 10.

class RegQuery(BaseModel):
    search_term: str
    limit: int = 5
    run_by: str          # nombre real (regla run_by de W4)


class CaseFetch(BaseModel):
    run_by: str


@router.post("/regulatory/query")
def post_regulatory_query(body: RegQuery):
    """1 consulta online limitada → memoria ligera (pointer+metadata+summary+hash)."""
    return _regconn.query_recalls(body.search_term, body.limit, body.run_by)


@router.post("/case-memory/{case_id}/fetch")
def post_case_detail_fetch(case_id: str, body: CaseFetch):
    """Selective fetch del detalle de UN caso conocido. NO persiste el detalle."""
    return _regconn.fetch_case_detail(case_id, body.run_by)


# ── W6.1 — Reportes, paquete de validación y readiness (read-only, NO auditan) ─

@router.get("/missions/{project_id}/reports")
def get_mission_reports(project_id: str):
    """V6 — artefactos de reporte ya presentes en disco + generables bajo demanda."""
    return _valready.list_reports(project_id)


@router.get("/missions/{project_id}/validation-package")
def get_validation_package(project_id: str):
    """V10 — estado del dossier CSV/GAMP 5 (22 documentos); sin dossier → todo not_started."""
    return _valready.read_validation_package(project_id)


@router.get("/missions/{project_id}/readiness")
def get_mission_readiness(project_id: str):
    """V9 — checklist go/no-go derivado solo de evidencia; sin dato → 'sin evidencia'."""
    return _valready.build_readiness(project_id)


# ── W6.2 — Dossier CSV: generación asistida + aprobación humana ───────────────
# Generación desde evidencia real (nunca inventa, nunca aprueba sola).
# approved SOLO vía acto humano con nombre real. 1 evento de auditoría por acción.

class DossierGenerate(BaseModel):
    generated_by: str    # nombre real (regla run_by de W4)


class DocApprove(BaseModel):
    approved_by: str     # nombre real — NO es firma electrónica


@router.post("/missions/{project_id}/validation-package/generate")
def post_generate_dossier(project_id: str, body: DossierGenerate):
    return _dossier.generate_dossier(project_id, body.generated_by)


@router.post("/missions/{project_id}/validation-package/documents/{doc_id}/approve")
def post_approve_validation_doc(project_id: str, doc_id: str, body: DocApprove):
    return _dossier.approve_document(project_id, doc_id, body.approved_by)


@router.get("/missions/{project_id}/validation-package/documents/{doc_id}")
def get_validation_document(project_id: str, doc_id: str):
    """Read-only: contenido del borrador. NO audita."""
    return _dossier.read_document(project_id, doc_id)
