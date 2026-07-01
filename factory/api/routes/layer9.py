"""
Capa 9 — Rutas API Mission Control (F4.5d).

Expone las operaciones de Mission Control de Capa 9 en el factory-api.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml as _yaml
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
from factory.core.report_sanitizer import sanitize_for_report
from factory.core.pdf_report import render_gmp_report_pdf

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


# ── W3: Visor de evidencia por misión ────────────────────────────────────────
# Todos estos endpoints son READ-ONLY — no escriben en la cadena de auditoría.

_DESIGNS_BASE  = _FACTORY_ROOT / "designs"
_RC_BASE_W3    = _FACTORY_ROOT / "release_candidates"
_DEP_BASE      = _FACTORY_ROOT / "deployments"
_WS_BASE_W3    = _FACTORY_ROOT / "workspaces"
_AUDIT_FILE    = _FACTORY_ROOT / "audit" / "factory_audit.jsonl"

_MAX_FILE_W3   = 256 * 1024  # 256 KB

_FILTER_PARTS  = frozenset({
    ".pytest_cache", "__pycache__", ".pyc", ".env", ".claude",
    "data/chroma", "backups", ".ssh", ".key", ".pem", "credentials",
})


def _etag_of(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(str(p) for p in paths):
        fp = Path(p)
        if fp.exists():
            h.update(f"{p}:{fp.stat().st_mtime_ns}".encode())
    return f'"{h.hexdigest()[:16]}"'


def _safe_design(project_id: str) -> Path:
    from factory.core.path_policy import resolve_design
    try:
        return resolve_design(project_id, _DESIGNS_BASE)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


def _parse_headless_log(ws: Path) -> dict | None:
    logs = sorted(ws.glob("logs/headless_*.log"), reverse=True)
    if not logs:
        return None
    log_path = logs[0]
    try:
        raw = log_path.read_text(encoding="utf-8", errors="replace").strip()
        d = json.loads(raw)
        mu = d.get("modelUsage") or {}
        breakdown = {
            m: {
                "inputTokens": s.get("inputTokens", 0),
                "outputTokens": s.get("outputTokens", 0),
                "costUSD": round(s.get("costUSD", 0), 6),
            }
            for m, s in mu.items()
        }
        return {
            "log_filename": log_path.name,
            "log_size_bytes": log_path.stat().st_size,
            "returncode": 0 if not d.get("is_error") else 1,
            "subtype": d.get("subtype"),
            "duration_ms": d.get("duration_ms"),
            "duration_api_ms": d.get("duration_api_ms"),
            "num_turns": d.get("num_turns"),
            "terminal_reason": d.get("terminal_reason"),
            "total_cost_usd": d.get("total_cost_usd"),
            "models_used": list(mu.keys()),
            "model_breakdown": breakdown,
            "permission_denials": d.get("permission_denials", []),
            "result_text": (d.get("result") or "")[:4096],
            "session_id": d.get("session_id"),
        }
    except Exception:
        return {"log_filename": log_path.name, "log_size_bytes": log_path.stat().st_size, "parse_error": True}


def _parse_agents(design_dir: Path) -> dict:
    proposal = design_dir / "agent_design_proposal.yaml"
    if not proposal.exists():
        return {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}}
    try:
        d = _yaml.safe_load(proposal.read_text(encoding="utf-8")) or {}
        agents = []
        for a in (d.get("agents") or []):
            agents.append({
                "agent_id": a.get("agent_id"),
                "decision": a.get("decision"),
                "is_inherited": a.get("decision") == "profile",
                "base_agent": a.get("base_agent"),
                "profile_name": a.get("profile_name"),
                "rationale": a.get("rationale", "")[:200],
                "routing_key": a.get("routing_key"),
            })
        profiles = sum(1 for a in agents if a["is_inherited"])
        new = sum(1 for a in agents if not a["is_inherited"])
        return {
            "agents": agents,
            "summary": {"profiles_inherited": profiles, "new_agents": new},
            "routing_notes": d.get("routing_notes", "")[:300],
        }
    except Exception:
        return {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}, "parse_error": True}


def _deployment_health(project_id: str) -> dict:
    dep_dir = _DEP_BASE / project_id
    if not dep_dir.exists():
        return {"exists": False}
    # Puerto vía port_registry
    api_port = None
    try:
        from factory.core.port_registry import get_allocated_ports
        ports = get_allocated_ports(project_id)
        api_port = ports.get("api") if ports else None
    except Exception:
        pass
    health_ok = False
    health_body = None
    health_error = None
    if api_port:
        try:
            r = httpx.get(f"http://host.docker.internal:{api_port}/health", timeout=4)
            health_ok = r.status_code == 200
            health_body = r.json() if health_ok else None
        except Exception as e:
            health_error = str(e)[:100]
    # Archivos visibles (sin secretos)
    visible = []
    for p in sorted(dep_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(dep_dir))
        if any(blocked in rel for blocked in _FILTER_PARTS):
            continue
        visible.append({"path": rel, "size": p.stat().st_size, "ext": p.suffix})
    return {
        "exists": True,
        "api_port": api_port,
        "health_ok": health_ok,
        "health_body": health_body,
        "health_error": health_error,
        "docs_url": f"http://localhost:{api_port}/docs" if api_port else None,
        "files_visible": len(visible),
        "files": visible[:100],
    }


# ── GET /missions/{project_id}/summary ───────────────────────────────────────

def _build_mission_summary(project_id: str) -> dict:
    """
    Construye el cuerpo del resumen consolidado de la misión (sin manejo de
    ETag/304, que es responsabilidad del endpoint HTTP). Extraído como función
    plana para que otras vistas read-only (ej. W4.1 /gmp-report) puedan
    reutilizar exactamente esta misma lógica sin pasar por FastAPI Request/Response.
    """
    # ── Misión ──
    mission_file = _FACTORY_ROOT / "layer9" / "missions" / f"{project_id}.yaml"
    if not mission_file.exists():
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")
    try:
        m = _yaml.safe_load(mission_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise HTTPException(500, f"Error leyendo misión: {e}")

    approved_by = next(
        (h.get("by", "") for h in (m.get("history") or []) if h.get("event") == "approved"),
        m.get("approved_by", ""),
    )
    mission_block = {
        "status": m.get("status"),
        "client_type": m.get("client_type"),
        "created_at": m.get("created_at"),
        "approved_at": m.get("approved_at"),
        "approved_by": approved_by,
    }

    # ── Design ──
    design_dir = _DESIGNS_BASE / project_id
    design_files = []
    agents_summary = {"profiles_inherited": 0, "new_agents": 0, "agent_ids": []}
    pending_docs_count = 0
    if design_dir.exists():
        design_files = [p.name for p in sorted(design_dir.iterdir()) if p.is_file()]
        ag = _parse_agents(design_dir)
        agents_summary = ag["summary"]
        agents_summary["agent_ids"] = [a["agent_id"] for a in ag.get("agents", [])]
        pd_file = design_dir / "pending_documents.yaml"
        if pd_file.exists():
            try:
                pd = _yaml.safe_load(pd_file.read_text(encoding="utf-8")) or {}
                pending_docs_count = len(pd.get("documents", pd.get("pending", [])))
            except Exception:
                pass

    # ── Workspace ──
    ws = _WS_BASE_W3 / project_id
    ws_files_visible = 0
    ws_py_files = 0
    ws_has_test_report = False
    ws_has_headless_log = False
    if ws.exists():
        for p in ws.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(ws))
            if any(bl in rel for bl in _FILTER_PARTS):
                continue
            ws_files_visible += 1
            if p.suffix == ".py":
                ws_py_files += 1
        ws_has_test_report = (ws / "test_report.json").exists()
        ws_has_headless_log = bool(list(ws.glob("logs/headless_*.log")))

    # ── Headless ──
    headless_block = None
    if ws.exists():
        hl = _parse_headless_log(ws)
        if hl and not hl.get("parse_error"):
            headless_block = {
                "returncode": hl.get("returncode"),
                "duration_seconds": round((hl.get("duration_ms") or 0) / 1000, 1),
                "total_cost_usd": hl.get("total_cost_usd"),
                "num_turns": hl.get("num_turns"),
                "models_used": hl.get("models_used", []),
                "terminal_reason": hl.get("terminal_reason"),
            }

    # ── Tests ──
    tests_block = None
    test_report = ws / "test_report.json" if ws.exists() else None
    if test_report and test_report.exists():
        try:
            td = json.loads(test_report.read_text(encoding="utf-8"))
            s = td.get("summary", {})
            tests_block = {
                "passed": s.get("passed", 0),
                "failed": s.get("failed", 0),
                "returncode": s.get("returncode", -1),
            }
        except Exception:
            pass

    # ── RCs ──
    rc_dir = _RC_BASE_W3 / project_id
    rc_list = []
    rc_statuses: dict[str, int] = {}
    canonical_id = None
    if rc_dir.exists():
        for f in sorted(rc_dir.rglob("rc_manifest.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                rc_list.append(d)
                st = d.get("status", "unknown")
                rc_statuses[st] = rc_statuses.get(st, 0) + 1
                if d.get("is_canonical"):
                    canonical_id = d.get("rc_id")
            except Exception:
                continue

    # ── Deployment ──
    dep_exists = (_DEP_BASE / project_id).exists()
    dep_health_ok = False
    dep_api_port = None
    if dep_exists:
        try:
            from factory.core.port_registry import get_allocated_ports
            ports = get_allocated_ports(project_id)
            dep_api_port = ports.get("api") if ports else None
        except Exception:
            pass
        if dep_api_port:
            try:
                hr = httpx.get(f"http://host.docker.internal:{dep_api_port}/health", timeout=3)
                dep_health_ok = hr.status_code == 200
            except Exception:
                pass

    # ── Audit ──
    audit_count = 0
    last_event_at = None
    last_event_type = None
    if _AUDIT_FILE.exists():
        for raw in _AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
                if e.get("project_id") == project_id:
                    audit_count += 1
                    last_event_at = e.get("timestamp")
                    last_event_type = e.get("event_type")
            except Exception:
                continue

    # ── ETag ──
    key_files = [
        mission_file,
        ws / "test_report.json" if ws.exists() else Path("/dev/null"),
        *([rc_dir / f for f in []] if not rc_dir.exists() else
          sorted(rc_dir.rglob("rc_manifest.json"))),
    ]
    etag = _etag_of(key_files)

    return {
        "project_id": project_id,
        "mission": mission_block,
        "design": {
            "files_count": len(design_files),
            "files": design_files,
            "agents_summary": agents_summary,
            "pending_documents_count": pending_docs_count,
        },
        "workspace": {
            "files_visible": ws_files_visible,
            "py_files": ws_py_files,
            "has_test_report": ws_has_test_report,
            "has_headless_log": ws_has_headless_log,
        },
        "headless": headless_block,
        "tests": tests_block,
        "rcs": {
            "count": len(rc_list),
            "canonical": canonical_id,
            "statuses": rc_statuses,
        },
        "deployment": {
            "exists": dep_exists,
            "api_port": dep_api_port,
            "health_ok": dep_health_ok,
        },
        "audit": {
            "event_count_filtered": audit_count,
            "last_event_at": last_event_at,
            "last_event_type": last_event_type,
        },
        "etag": etag,
    }


@router.get("/missions/{project_id}/summary")
def get_mission_summary(project_id: str, request: Request, response: Response):
    """
    Resumen consolidado de la misión: ~5KB, cacheable con ETag.
    Si If-None-Match coincide con el ETag actual → 304 Not Modified.
    Read-only: no escribe en la cadena de auditoría.
    """
    body = _build_mission_summary(project_id)
    etag = body["etag"]
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=10"
    return body


# ── GET /missions/{project_id}/design ────────────────────────────────────────

@router.get("/missions/{project_id}/design")
def get_mission_design(project_id: str):
    """Lista archivos en factory/designs/{project_id}/. Read-only."""
    design_dir = _safe_design(project_id)
    files = []
    for p in sorted(design_dir.iterdir()):
        if not p.is_file():
            continue
        entry: dict[str, Any] = {"name": p.name, "size": p.stat().st_size, "ext": p.suffix}
        if p.suffix in (".yaml", ".yml"):
            try:
                d = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                entry["keys"] = list(d.keys())[:10]
            except Exception:
                pass
        files.append(entry)
    return {"project_id": project_id, "files": files, "count": len(files)}


# ── GET /missions/{project_id}/agents ────────────────────────────────────────

@router.get("/missions/{project_id}/agents")
def get_mission_agents(project_id: str):
    """
    Lee agent_design_proposal.yaml y devuelve lista estructurada.
    Distingue profiles heredados de agents nuevos. Read-only.
    """
    design_dir = _safe_design(project_id)
    result = _parse_agents(design_dir)
    result["project_id"] = project_id
    result["source_file"] = f"factory/designs/{project_id}/agent_design_proposal.yaml"
    return result


# ── GET /missions/{project_id}/headless ──────────────────────────────────────

@router.get("/missions/{project_id}/headless")
def get_mission_headless(project_id: str):
    """
    Parsea el log JSONL del CLI Claude del workspace.
    Devuelve estructura plana con costo, turns, modelos. Read-only.
    """
    from factory.core.path_policy import resolve_workspace
    try:
        ws = resolve_workspace(project_id, _WS_BASE_W3)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    parsed = _parse_headless_log(ws)
    if parsed is None:
        return {"project_id": project_id, "found": False}
    return {"project_id": project_id, "found": True, "result": parsed}


# ── GET /missions/{project_id}/tests ─────────────────────────────────────────

@router.get("/missions/{project_id}/tests")
def get_mission_tests(project_id: str):
    """Lee test_report.json del workspace. Read-only."""
    ws = _WS_BASE_W3 / project_id
    report_path = ws / "test_report.json"
    if not ws.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")
    if not report_path.exists():
        return {"project_id": project_id, "found": False}
    try:
        d = json.loads(report_path.read_text(encoding="utf-8"))
        s = d.get("summary", {})
        return {
            "project_id": project_id,
            "found": True,
            "passed": s.get("passed", 0),
            "failed": s.get("failed", 0),
            "returncode": s.get("returncode", -1),
            "note": d.get("note", ""),
            "output": (d.get("output") or "")[:4096],
        }
    except Exception as e:
        raise HTTPException(500, f"Error parseando test_report.json: {e}")


# ── GET /missions/{project_id}/rcs ───────────────────────────────────────────

@router.get("/missions/{project_id}/rcs")
def get_mission_rcs(project_id: str):
    """
    Lista todos los RC manifests de un proyecto con detalle completo.
    Read-only, no requiere escritura en auditoría.
    """
    rc_dir = _RC_BASE_W3 / project_id
    if not rc_dir.exists():
        return {"project_id": project_id, "rcs": [], "count": 0}
    rcs = []
    for f in sorted(rc_dir.rglob("rc_manifest.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            artifacts_path = f.parent / "artifacts"
            artifacts = []
            if artifacts_path.exists():
                for ap in sorted(artifacts_path.iterdir()):
                    if ap.is_file():
                        artifacts.append({"name": ap.name, "size": ap.stat().st_size, "ext": ap.suffix})
            rcs.append({
                "rc_id": d.get("rc_id"),
                "version": d.get("version"),
                "status": d.get("status"),
                "is_canonical": d.get("is_canonical"),
                "approved_by": d.get("approved_by"),
                "decided_at": d.get("decided_at"),
                "proposed_at": d.get("proposed_at"),
                "notes": d.get("notes", ""),
                "sha256sums": d.get("sha256sums", {}),
                "artifacts": artifacts,
            })
        except Exception:
            continue
    return {"project_id": project_id, "rcs": rcs, "count": len(rcs)}


# ── GET /missions/{project_id}/deployment ────────────────────────────────────

@router.get("/missions/{project_id}/deployment")
def get_mission_deployment(project_id: str):
    """
    Estado del deployment Docker del proyecto.
    Hace health check en vivo vía host.docker.internal. Read-only.
    """
    return {"project_id": project_id, **_deployment_health(project_id)}


# ── GET /missions/{project_id}/audit ─────────────────────────────────────────

@router.get("/missions/{project_id}/audit")
def get_mission_audit(project_id: str, limit: int = Query(default=50, le=200)):
    """
    Eventos de auditoría filtrados por project_id (últimos N).
    Read-only — no escribe en cadena.
    """
    if not _AUDIT_FILE.exists():
        return {"project_id": project_id, "events": [], "count": 0}
    events = []
    for raw in _AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(raw)
            if e.get("project_id") == project_id:
                events.append({
                    "timestamp": e.get("timestamp"),
                    "event_type": e.get("event_type"),
                    "entry_hash": e.get("entry_hash"),
                    "data": e.get("data", {}),
                })
        except Exception:
            continue
    events_trimmed = events[-limit:]
    return {
        "project_id": project_id,
        "events": list(reversed(events_trimmed)),
        "count": len(events_trimmed),
        "total": len(events),
    }


# ── GET /missions/{project_id}/design/file ───────────────────────────────────

@router.get("/missions/{project_id}/design/file")
def get_design_file(project_id: str, path: str = Query(...)):
    """
    Lee un archivo de factory/designs/{project_id}/.
    Política: solo .yaml, .yml, .md — bloquea traversal y secretos.
    """
    from factory.core.path_policy import resolve_design
    try:
        target = resolve_design(project_id, _DESIGNS_BASE, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > _MAX_FILE_W3:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {_MAX_FILE_W3})")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


# ── GET /missions/{project_id}/rc/{rc_id}/file ───────────────────────────────

@router.get("/missions/{project_id}/rc/{rc_id}/file")
def get_rc_artifact_file(project_id: str, rc_id: str, path: str = Query(...)):
    """
    Lee un artefacto de factory/release_candidates/{project_id}/{rc_id}/.
    Política: solo .json, .log, .txt, .md — bloquea traversal y secretos.
    El path no puede escapar del rc_id solicitado.
    """
    from factory.core.path_policy import resolve_rc_artifact
    try:
        target = resolve_rc_artifact(project_id, rc_id, _RC_BASE_W3, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > _MAX_FILE_W3:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {_MAX_FILE_W3})")
    return {
        "project_id": project_id,
        "rc_id": rc_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


# ── GET /missions/{project_id}/deployment/file ───────────────────────────────

@router.get("/missions/{project_id}/deployment/file")
def get_deployment_file(project_id: str, path: str = Query(...)):
    """
    Lee un archivo de factory/deployments/{project_id}/.
    Política estricta: bloquea .env, data/, knowledge/corpus/, releases/, secretos.
    """
    from factory.core.path_policy import resolve_deployment
    try:
        target = resolve_deployment(project_id, _DEP_BASE, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > _MAX_FILE_W3:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {_MAX_FILE_W3})")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


# ── W4 — Consola de pruebas funcionales por agente ───────────────────────────
#
# Separación estricta reader/executor (regla U5):
#   GET  test-catalog / test-results  → READER, nunca audita
#   POST test/run     / test/run-suite → EXECUTOR, audita exactamente 1 evento
#     (run-suite audita 1 evento de RESUMEN, aunque corra N tests)
#
# El payload y el endpoint destino SIEMPRE vienen del catálogo curado
# (factory/test_catalogs/{project_id}.yaml); el body del request del
# usuario solo trae test_id/agent_id + run_by — así se impide inyectar
# payloads arbitrarios. El host:port destino SIEMPRE se resuelve server-side
# desde el registry de puertos de la misión (get_allocated_ports), nunca
# desde 'deployment_base' del catálogo ni de ningún campo del request —
# así se impide SSRF hacia una URL arbitraria.

_TEST_CATALOGS_DIR = _FACTORY_ROOT / "test_catalogs"
_TEST_RESULTS_DIR = _FACTORY_ROOT / "test_results"
_RESERVED_RUN_BY = {"human", "agent", "system", "admin", "user", "factory"}
_MISSING = object()


class TestRunRequest(BaseModel):
    test_id: str
    run_by: str


class TestRunSuiteRequest(BaseModel):
    agent_id: str
    run_by: str


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _validate_run_by(run_by: str) -> str:
    name = (run_by or "").strip()
    if not name:
        raise HTTPException(422, "run_by es obligatorio: indica el nombre real del operador.")
    if name.lower() in _RESERVED_RUN_BY:
        raise HTTPException(
            422, f"run_by='{run_by}' es un nombre genérico reservado. Usa el nombre real del operador."
        )
    return name


def _get_deployment_api_key(project_id: str) -> str | None:
    env_file = _DEP_BASE / project_id / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("GMP_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _load_test_catalog(project_id: str) -> dict | None:
    catalog_file = _TEST_CATALOGS_DIR / f"{project_id}.yaml"
    if not catalog_file.exists():
        return None
    return _yaml.safe_load(catalog_file.read_text(encoding="utf-8")) or {}


def _find_test_in_catalog(catalog: dict, test_id: str) -> tuple[str, dict] | None:
    for agent in catalog.get("agents", []):
        for test in agent.get("tests", []):
            if test.get("test_id") == test_id:
                return agent.get("agent_id"), test
    return None


def _find_agent_tests(catalog: dict, agent_id: str) -> list[dict] | None:
    for agent in catalog.get("agents", []):
        if agent.get("agent_id") == agent_id:
            return agent.get("tests", [])
    return None


def _require_live_deployment(project_id: str) -> tuple[int, str]:
    """Resuelve puerto+api_key server-side y exige health OK. 409 si no está vivo."""
    from factory.core.port_registry import get_allocated_ports
    ports = get_allocated_ports(project_id)
    port = ports.get("api") if ports else None
    if not port:
        raise HTTPException(404, f"Puerto no asignado para la misión '{project_id}'")
    try:
        r = httpx.get(f"http://host.docker.internal:{port}/health", timeout=4.0)
        alive = r.status_code == 200
    except Exception:
        alive = False
    if not alive:
        raise HTTPException(409, f"Deployment de '{project_id}' no está activo (health check falló)")
    api_key = _get_deployment_api_key(project_id)
    if not api_key:
        raise HTTPException(500, "No se pudo leer la API key del deployment")
    return port, api_key


def _eval_json_path(body: Any, json_path: str):
    """Acceso simple '$.a.b.c' sobre dicts anidados (sin arrays/wildcards:
    los catálogos W4 solo evalúan campos planos de la respuesta)."""
    path = json_path.strip()
    if path == "$":
        return body
    if path.startswith("$."):
        path = path[2:]
    current = body
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def _execute_catalog_test(port: int, api_key: str, test_entry: dict) -> dict:
    """Ejecuta UN caso del catálogo. payload/endpoint vienen solo de test_entry."""
    test_id = test_entry["test_id"]
    endpoint = test_entry["endpoint"]
    method, path = endpoint.split(" ", 1)
    payload = test_entry.get("payload")
    expect = test_entry.get("expect", {})
    url = f"http://host.docker.internal:{port}{path}"

    t0 = time.monotonic()
    try:
        r = httpx.request(method, url, json=payload, headers={"x-api-key": api_key}, timeout=15.0)
    except httpx.TimeoutException:
        return {
            "test_id": test_id, "endpoint": endpoint, "payload": payload,
            "response_status": None, "response_excerpt": "",
            "assertion": expect, "result": "ERROR",
            "detail": "Timeout: el deployment no respondió en 15s",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {
            "test_id": test_id, "endpoint": endpoint, "payload": payload,
            "response_status": None, "response_excerpt": "",
            "assertion": expect, "result": "ERROR",
            "detail": f"Error de conexión: {str(exc)[:150]}",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    try:
        response_json = r.json()
        response_excerpt = json.dumps(response_json, ensure_ascii=False)[:2000]
    except Exception:
        response_json = None
        response_excerpt = r.text[:2000]

    expected_status = expect.get("status_code")
    status_ok = expected_status is None or r.status_code == expected_status

    received_value = _MISSING
    assertion_ok = status_ok
    if status_ok and "json_path" in expect:
        received_value = _eval_json_path(response_json, expect["json_path"])
        assertion_ok = received_value is not _MISSING and received_value == expect.get("equals")

    return {
        "test_id": test_id,
        "endpoint": endpoint,
        "payload": payload,
        "response_status": r.status_code,
        "response_excerpt": response_excerpt,
        "assertion": {
            "expected_status": expected_status,
            "json_path": expect.get("json_path"),
            "expected_value": expect.get("equals"),
            "received_value": None if received_value is _MISSING else received_value,
        },
        "result": "PASS" if assertion_ok else "FAIL",
        "detail": None,
        "latency_ms": latency_ms,
    }


def _persist_test_result(project_id: str, record: dict) -> None:
    import fcntl
    _TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = _TEST_RESULTS_DIR / f"{project_id}.jsonl"
    lock_path = results_file.with_suffix(".lock")
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


@router.get("/missions/{project_id}/test-catalog")
def get_test_catalog(project_id: str):
    """READER — catálogo curado de pruebas de la misión. No ejecuta nada, no audita."""
    catalog = _load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")

    from factory.core.port_registry import get_allocated_ports
    ports = get_allocated_ports(project_id)
    port = ports.get("api") if ports else None
    deployment_ready = False
    health_body = None
    if port:
        try:
            r = httpx.get(f"http://host.docker.internal:{port}/health", timeout=4.0)
            deployment_ready = r.status_code == 200
            health_body = r.json() if deployment_ready else None
        except Exception:
            deployment_ready = False

    return {
        "project_id": project_id,
        "catalog_version": catalog.get("catalog_version"),
        "deployment_ready": deployment_ready,
        "deployment": {"api_port": port, "health": health_body},
        "agents": catalog.get("agents", []),
    }


@router.get("/missions/{project_id}/test-results")
def get_test_results(project_id: str, limit: int = Query(default=50, le=200)):
    """READER — historial de pruebas ya ejecutadas (read-only). No audita."""
    results_file = _TEST_RESULTS_DIR / f"{project_id}.jsonl"
    if not results_file.exists():
        return {"project_id": project_id, "total": 0, "results": []}
    lines = [ln for ln in results_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records = []
    for ln in lines[-limit:]:
        try:
            records.append(json.loads(ln))
        except Exception:
            continue
    records.reverse()
    return {"project_id": project_id, "total": len(lines), "results": records}


@router.post("/missions/{project_id}/test/run")
def post_run_test(project_id: str, body: TestRunRequest):
    """
    EXECUTOR — ejecuta UN caso de prueba del catálogo curado contra el
    deployment real de la misión. Audita exactamente 1 evento.
    """
    from factory.core.audit_writer import write_event as _we

    run_by = _validate_run_by(body.run_by)

    catalog = _load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")
    found = _find_test_in_catalog(catalog, body.test_id)
    if found is None:
        raise HTTPException(404, f"Test '{body.test_id}' no existe en el catálogo de '{project_id}'")
    agent_id, test_entry = found

    port, api_key = _require_live_deployment(project_id)

    result = _execute_catalog_test(port, api_key, test_entry)
    record = {**result, "agent_id": agent_id, "run_by": run_by, "run_at": _now_iso()}
    _persist_test_result(project_id, record)

    _we("agent_functional_test_executed", project_id, {
        "test_id": body.test_id,
        "agent_id": agent_id,
        "result": result["result"],
        "run_by": run_by,
        "decision_origin": "human_confirmed",
    })

    return record


@router.post("/missions/{project_id}/test/run-suite")
def post_run_test_suite(project_id: str, body: TestRunSuiteRequest):
    """
    EXECUTOR — ejecuta todos los casos de un agente en secuencia.
    Un solo evento de auditoría agent_suite_tested con resumen N/M PASS
    (cada resultado individual también se persiste en test_results).
    """
    from factory.core.audit_writer import write_event as _we

    run_by = _validate_run_by(body.run_by)

    catalog = _load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")
    tests = _find_agent_tests(catalog, body.agent_id)
    if tests is None:
        raise HTTPException(404, f"Agente '{body.agent_id}' no existe en el catálogo de '{project_id}'")
    if not tests:
        raise HTTPException(404, f"Agente '{body.agent_id}' no tiene casos de prueba en el catálogo")

    port, api_key = _require_live_deployment(project_id)

    results = []
    passed = 0
    run_at = _now_iso()
    for test_entry in tests:
        result = _execute_catalog_test(port, api_key, test_entry)
        record = {**result, "agent_id": body.agent_id, "run_by": run_by, "run_at": run_at}
        _persist_test_result(project_id, record)
        results.append(record)
        if result["result"] == "PASS":
            passed += 1

    _we("agent_suite_tested", project_id, {
        "agent_id": body.agent_id,
        "total": len(tests),
        "passed": passed,
        "run_by": run_by,
        "decision_origin": "human_confirmed",
    })

    return {
        "project_id": project_id,
        "agent_id": body.agent_id,
        "total": len(tests),
        "passed": passed,
        "results": results,
    }


# ── W4.1 — Dashboard GMP + informe PDF por misión ────────────────────────────
# Capa de PRESENTACIÓN sobre W3/W4: consolida evidencia YA existente (summary,
# agents, test-catalog, test-results, deployment, audit, rcs, workspace files)
# en una estructura narrativa de dos niveles (ejecutivo + técnico). Read-only,
# no re-implementa lectura de datos: llama a los helpers/endpoints de arriba.
# Todo campo sin fuente real se expone como "no_disponible" — nunca se
# inventa un dato ni texto regulatorio. Ambos endpoints comparten el mismo
# agregador y pasan por sanitize_for_report() antes de exponerse.

_NO_DATA = "no_disponible"

_OPERATIONAL_IMPACT_TEXT = (
    "Los agentes evaluados podrian operar de forma continua (7x24) como apoyo "
    "al monitoreo, preclasificacion y validacion funcional de resultados de "
    "laboratorio: deteccion de resultados fuera de especificacion (OOS), "
    "revision de parametros cromatograficos (HPLC/SST) y validacion de "
    "integridad de datos (ALCOA+), generando evidencia trazable y auditada. "
    "En una operacion madura, esto podria reducir de forma estimada entre 30% "
    "y 60% el tiempo dedicado a revision preliminar, validacion repetitiva y "
    "preparacion de evidencia. Esta cifra es una ESTIMACION de mejora "
    "potencial, no una medicion del entorno actual."
)

_CONCLUSION_NO_REPLACE_TEXT = (
    "Estos agentes funcionan como apoyo a QA/QC y NO reemplazan la decision "
    "humana ni liberan lotes de forma automatica. La liberacion de lote y la "
    "disposicion final permanecen bajo responsabilidad del personal QA/QC "
    "calificado. El sistema aporta velocidad, consistencia y evidencia "
    "trazable en las etapas preliminares, manteniendo el control humano en "
    "la decision."
)


def _read_yaml_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def _read_text_excerpt(path: Path, max_chars: int = 2000) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return None


def _is_llm_endpoint(endpoint: str) -> bool:
    return "/api/v1/query" in (endpoint or "")


def _build_gmp_report(project_id: str) -> dict:
    """
    Agregador read-only del Dashboard GMP (W4.1). NO audita. Reutiliza
    _build_mission_summary / get_mission_agents / get_test_catalog /
    get_test_results / get_mission_deployment / get_mission_rcs /
    get_mission_audit — no re-implementa su lógica de lectura.
    """
    from datetime import datetime, timezone

    summary = _build_mission_summary(project_id)  # 404 si la misión no existe
    mission_full = get_mission(project_id)

    try:
        agents_result = get_mission_agents(project_id)
    except HTTPException:
        agents_result = {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}}

    try:
        catalog = get_test_catalog(project_id)
    except HTTPException:
        catalog = None

    test_results = get_test_results(project_id, limit=200)
    deployment = get_mission_deployment(project_id)
    rcs_result = get_mission_rcs(project_id)
    audit_result = get_mission_audit(project_id, limit=100)

    design_dir = _DESIGNS_BASE / project_id
    requirement_spec = _read_yaml_or_none(design_dir / "requirement_spec.yaml")
    pending_docs_yaml = _read_yaml_or_none(design_dir / "pending_documents.yaml") or {}
    task_md = _read_text_excerpt(_WS_BASE_W3 / project_id / "task.md")

    # ── meta ──
    mission_block = summary["mission"]
    canonical_rc = summary["rcs"]["canonical"] or _NO_DATA
    deployment_status = "desplegado" if deployment.get("health_ok") else "no_desplegado"
    now_iso = datetime.now(timezone.utc).isoformat()

    meta = {
        "project_id": project_id,
        "generated_at": now_iso,
        "client_type": mission_block.get("client_type") or _NO_DATA,
        "canonical_rc": canonical_rc,
        "deployment_status": deployment_status,
        "report_source": "evidencia real: summary, agents, test-results, deployment, audit, rcs",
    }

    # ── agentes evaluados ──
    agent_list = agents_result.get("agents", [])
    profiles_inherited = [a["agent_id"] for a in agent_list if a.get("is_inherited")]
    new_agents = [a["agent_id"] for a in agent_list if not a.get("is_inherited")]
    agents_evaluated = {
        "profiles_inherited": profiles_inherited,
        "new_agents": new_agents,
        "total": len(agent_list),
    }

    # ── índice test_id -> (agent_id, test_entry del catálogo) ──
    catalog_index: dict[str, tuple[str, dict]] = {}
    if catalog:
        for agent in catalog.get("agents", []):
            for t in agent.get("tests", []):
                catalog_index[t.get("test_id")] = (agent.get("agent_id"), t)

    # ── resultados por agente (a partir de test-results real, agrupado) ──
    results_by_agent_map: dict[str, list[dict]] = {}
    for rec in test_results.get("results", []):
        agent_id = rec.get("agent_id") or _NO_DATA
        catalog_hit = catalog_index.get(rec.get("test_id"))
        title = catalog_hit[1].get("title") if catalog_hit else None
        endpoint = rec.get("endpoint") or (catalog_hit[1].get("endpoint") if catalog_hit else None)
        assertion = rec.get("assertion") or {}
        relevant_datum = assertion.get("received_value")
        if relevant_datum is None:
            relevant_datum = _NO_DATA
        results_by_agent_map.setdefault(agent_id, []).append({
            "test_id": rec.get("test_id") or _NO_DATA,
            "title": title or _NO_DATA,
            "endpoint": endpoint or _NO_DATA,
            "result": rec.get("result") or _NO_DATA,
            "run_by": rec.get("run_by") or _NO_DATA,
            "run_at": rec.get("run_at") or _NO_DATA,
            "relevant_datum": relevant_datum,
            "uses_llm": _is_llm_endpoint(endpoint if isinstance(endpoint, str) else ""),
            "llm_evidence": rec.get("llm_evidence"),
        })
    results_by_agent = [
        {"agent_id": aid, "uses_llm": any(t["uses_llm"] for t in tests), "tests": tests}
        for aid, tests in results_by_agent_map.items()
    ]

    # ── interpretación farmacéutica (derivada de conteos reales, no inventada) ──
    pharma_interpretation = []
    for block in results_by_agent:
        tests = block["tests"]
        passed = sum(1 for t in tests if t["result"] == "PASS")
        failed = sum(1 for t in tests if t["result"] == "FAIL")
        errored = sum(1 for t in tests if t["result"] == "ERROR")
        pharma_interpretation.append(
            f"Agente {block['agent_id']}: {passed}/{len(tests)} pruebas PASS"
            + (f", {failed} FAIL" if failed else "")
            + (f", {errored} ERROR" if errored else "")
            + "."
        )
    if not pharma_interpretation:
        pharma_interpretation = ["No se han ejecutado pruebas funcionales aun para esta mision."]

    # ── implicación GMP (solo si hay pruebas reales de ese dominio) ──
    def _domain_summary(prefixes: tuple[str, ...]) -> str:
        matched = [
            t for block in results_by_agent for t in block["tests"]
            if any((t.get("test_id") or "").startswith(p) for p in prefixes)
        ]
        if not matched:
            return _NO_DATA
        passed = sum(1 for t in matched if t["result"] == "PASS")
        return f"{passed}/{len(matched)} pruebas PASS sobre evidencia real ejecutada."

    gmp_implication = {
        "oos": _domain_summary(("oos_",)),
        "hplc": _domain_summary(("sst_", "peaks_", "rsd_")),
        "alcoa": _domain_summary(("alcoa_", "audit_")),
    }

    # ── reglas vs LLM ──
    all_catalog_tests = [
        (a.get("agent_id"), t)
        for a in (catalog.get("agents", []) if catalog else [])
        for t in a.get("tests", [])
    ]
    deterministic_endpoints = sorted({
        t.get("endpoint") for _, t in all_catalog_tests if not _is_llm_endpoint(t.get("endpoint", ""))
    })
    llm_endpoints = sorted({
        t.get("endpoint") for _, t in all_catalog_tests if _is_llm_endpoint(t.get("endpoint", ""))
    })
    rules_vs_llm = {
        "deterministic_endpoints": deterministic_endpoints,
        "llm_endpoints": llm_endpoints,
        "explanation": (
            "Los endpoints deterministicos ejecutan logica Python de reglas fijas "
            "(sin LLM); los endpoints LLM invocan Ollama local para inferencia. "
            "El catalogo curado de esta mision se limita a casos aislados y "
            "deterministicos (ver notas del catalogo)."
        ),
    }

    # ── auditoría y trazabilidad ──
    canonical_rc_manifest = next(
        (r for r in rcs_result.get("rcs", []) if r.get("rc_id") == canonical_rc), None
    )
    test_event_types = {"agent_functional_test_executed", "agent_suite_tested"}
    test_events_count = sum(
        1 for e in audit_result.get("events", []) if e.get("event_type") in test_event_types
    )
    audit_traceability = {
        "canonical_rc": canonical_rc,
        "rc_sha256": (canonical_rc_manifest or {}).get("sha256sums") or _NO_DATA,
        "test_events_count": test_events_count,
        "last_audit_events": audit_result.get("events", [])[:10],
    }

    # ── pharma_case / mission_objective ──
    if requirement_spec:
        pharma_case = {
            "raw_objective": requirement_spec.get("raw_objective") or _NO_DATA,
            "domains": requirement_spec.get("domains") or [],
            "client_needs": requirement_spec.get("client_needs") or [],
            "part11_required": requirement_spec.get("part11_required"),
            "alcoa_plus_required": requirement_spec.get("alcoa_plus_required"),
        }
    else:
        pharma_case = _NO_DATA

    mission_objective = {
        "objective": mission_full.get("objective") or _NO_DATA,
        "regulatory_scope": mission_full.get("regulatory_scope") or [],
        "task_summary": task_md or _NO_DATA,
    }

    # ── limitaciones / pendientes go-live (de pending_documents real) ──
    pending_entries = pending_docs_yaml.get("documents", pending_docs_yaml.get("pending", [])) or []
    limitations = [
        f"{d.get('title', d.get('id', 'documento'))}: {d.get('status', 'PENDING_DOCUMENT')}"
        for d in pending_entries
    ]
    if not limitations:
        limitations = [_NO_DATA]

    pending_before_golive = list(limitations) if pending_entries else []
    if canonical_rc == _NO_DATA:
        pending_before_golive.append("Sin RC marcado como canonico para esta mision.")
    if deployment_status != "desplegado":
        pending_before_golive.append("Deployment no esta activo/saludable.")
    if not pending_before_golive:
        pending_before_golive = [_NO_DATA]

    # ── resumen ejecutivo (derivado de conteos reales) ──
    total_tests = sum(len(b["tests"]) for b in results_by_agent)
    total_pass = sum(1 for b in results_by_agent for t in b["tests"] if t["result"] == "PASS")
    total_fail = sum(1 for b in results_by_agent for t in b["tests"] if t["result"] in ("FAIL", "ERROR"))
    if total_tests:
        executive_summary = (
            f"La mision '{project_id}' ha ejecutado {total_tests} pruebas funcionales "
            f"reales sobre {len(agent_list)} agente(s) evaluado(s): {total_pass} PASS, "
            f"{total_fail} FAIL/ERROR. "
            + ("RC canonico marcado. " if canonical_rc != _NO_DATA else "Sin RC canonico marcado. ")
            + ("Deployment activo." if deployment_status == "desplegado" else "Deployment no activo.")
        )
    else:
        executive_summary = "No se han ejecutado pruebas funcionales aun para esta mision."

    # ── conclusión (texto obligatorio + mención de pendientes reales) ──
    conclusion_parts = [executive_summary, _CONCLUSION_NO_REPLACE_TEXT]
    if pending_entries:
        conclusion_parts.append(
            "Existen documentos regulatorios PENDING_DOCUMENT sin confirmar; deben "
            "resolverse antes de un go-live regulatorio."
        )
    conclusion = " ".join(conclusion_parts)

    report = {
        "meta": meta,
        "executive_summary": executive_summary,
        "mission_objective": mission_objective,
        "pharma_case": pharma_case,
        "agents_evaluated": agents_evaluated,
        "results_by_agent": results_by_agent,
        "pharma_interpretation": pharma_interpretation,
        "gmp_implication": gmp_implication,
        "rules_vs_llm": rules_vs_llm,
        "audit_traceability": audit_traceability,
        "operational_impact": _OPERATIONAL_IMPACT_TEXT,
        "limitations": limitations,
        "pending_before_golive": pending_before_golive,
        "conclusion": conclusion,
    }

    secret_values = [
        os.environ.get("FACTORY_API_KEY"),
        os.environ.get("ANTHROPIC_API_KEY"),
        _get_deployment_api_key(project_id),
    ]
    return sanitize_for_report(report, secret_values=secret_values)


@router.get("/missions/{project_id}/gmp-report")
def get_gmp_report(project_id: str):
    """
    W4.1 — Dashboard GMP: consolida TODA la evidencia real de la misión en
    una estructura narrativa de dos niveles (ejecutivo + técnico). Read-only,
    NO audita. Datos faltantes se exponen como "no_disponible".
    """
    return _build_gmp_report(project_id)


@router.get("/missions/{project_id}/gmp-report.pdf")
def get_gmp_report_pdf(project_id: str, record_by: str | None = Query(default=None)):
    """
    W4.1 — Genera el informe PDF congelado a partir del MISMO agregador que
    /gmp-report. Read-only por defecto (NO audita). Si se pasa ?record_by=
    con un nombre real, audita exactamente 1 evento de trazabilidad de
    "informe generado" (no re-audita nada de W4).
    """
    from datetime import datetime, timezone

    report = _build_gmp_report(project_id)
    pdf_bytes = render_gmp_report_pdf(report)

    if record_by:
        name = _validate_run_by(record_by)
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
