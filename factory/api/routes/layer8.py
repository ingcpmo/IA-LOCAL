"""
Capa 8 — Rutas API Runtime Controlado (F4.5d/F8).

Expone el estado de Capa 8, jobs, ejecución de misiones.
Desde F7/F8: soporta headless controlado (doble llave: API call + headless_enabled=true).
/deploy-if-authorized bloquea si approval.json sigue pending_approval.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.layer8.claude_account_status import check_claude_cli, write_status
from factory.layer8.claude_runtime import (
    validate_task_safety,
    validate_workspace,
    prepare_manual_command,
)
from factory.layer8.job_queue import list_jobs, get_job, create_job
from factory.layer8.layer8_orchestrator import run_mission
from factory.layer8.recovery_manager import detect_partial_f5, create_recovery_plan
from factory.layer8.validation_manager import run_quality_gates
from factory.layer8.autonomous_build_orchestrator import run_build_mission
from factory.layer8.release_candidate_builder import build_rc, list_pending_rcs
from factory.layer8.diff_manager import collect_diff
from factory.core.audit_writer import write_event

router = APIRouter(prefix="/api/v1/layer8", tags=["layer8"])

RELEASES_BASE = Path(__file__).parent.parent.parent / "releases"

# V2: whitelist explícita de modelos (nunca dinámica)
_ALLOWED_MODELS = [
    {"id": "claude-haiku-4-5-20251001", "label": "Haiku 4.5  — rápido / económico",    "tier": "fast"},
    {"id": "claude-sonnet-4-6",          "label": "Sonnet 4.6 — balance (recomendado)", "tier": "balanced"},
    {"id": "claude-opus-4-6",            "label": "Opus 4.6   — máxima calidad",        "tier": "quality"},
    {"id": "claude-opus-4-8",            "label": "Opus 4.8   — frontier",              "tier": "frontier"},
]
_ALLOWED_MODEL_IDS = {m["id"] for m in _ALLOWED_MODELS}
_GENERIC_NAMES = {"human", "agent", "system", "admin", "user", "factory"}


class ClaudeConfigUpdate(BaseModel):
    model: str
    changed_by: str
RUNTIME_CONFIG = Path(__file__).parent.parent.parent / "runtime" / "runtime_config.yaml"
STATUS_FILE = Path(__file__).parent.parent.parent / "runtime" / "claude_status.json"


def _get_approval_status(project_id: str) -> str:
    """Lee el approval.json del release más reciente para un project_id."""
    release_dir = RELEASES_BASE / project_id
    if not release_dir.exists():
        return "no_release"
    for ver_dir in sorted(release_dir.iterdir(), reverse=True):
        approval_file = ver_dir / "approval.json"
        if approval_file.exists():
            try:
                d = json.loads(approval_file.read_text(encoding="utf-8"))
                return d.get("status", "unknown")
            except Exception:
                return "unknown"
    return "no_release"


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
def get_layer8_status():
    """Resumen del estado de Capa 8: headless, jobs, runtime."""
    try:
        import yaml
        config = {}
        if RUNTIME_CONFIG.exists():
            with open(RUNTIME_CONFIG, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
    except Exception:
        config = {}

    pending = list_jobs(queue="pending")
    running = list_jobs(queue="running")
    completed = list_jobs(queue="completed")
    failed = list_jobs(queue="failed")

    return {
        "layer": 8,
        "headless_enabled": config.get("headless_enabled", False),
        "default_mode": config.get("default_mode", "manual_assisted"),
        "headless_timeout_seconds": config.get("headless_timeout_seconds", 1800),
        "jobs": {
            "pending": len(pending),
            "running": len(running),
            "completed": len(completed),
            "failed": len(failed),
        },
        "status_file_exists": STATUS_FILE.exists(),
    }


# ── Claude Status ──────────────────────────────────────────────────────────────

@router.get("/claude/status")
def get_claude_status():
    """Estado del CLI de Claude + modelo activo. Nunca expone credenciales."""
    # Leer config de modelo desde runtime_config
    try:
        config = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
    except Exception:
        config = {}

    # Base: leer claude_status.json si existe (escrito por host_worker o POST /check)
    base: dict[str, Any] = {}
    if STATUS_FILE.exists():
        try:
            d = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            SENSITIVE = {"token", "password", "credential", "secret", "api_key", "auth_token"}
            base = {k: v for k, v in d.items() if k.lower() not in SENSITIVE}
        except Exception:
            base = {"status": "unreadable"}
    else:
        base = {"status": "not_checked", "note": "Ejecutar POST /claude/status/check para generar."}

    # cli_installed desde el status JSON del host (no desde shutil.which dentro del contenedor)
    cli_installed = base.get("cli_found", False)
    cli_version = base.get("version")

    # V2: agregar info de modelo
    base.update({
        "cli_installed": cli_installed,
        "cli_version": cli_version,
        "active_model": config.get("claude_model", "claude-sonnet-4-6"),
        "headless_enabled": config.get("headless_enabled", False),
        "available_models": _ALLOWED_MODELS,
        # La clave de Anthropic vive en el host — nunca se expone aquí
    })
    return base


@router.post("/claude/status/check")
def post_claude_status_check():
    """Dispara check_claude_cli() y escribe claude_status.json."""
    try:
        result = write_status("factory_status_check")
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/claude/config")
def post_claude_config(body: ClaudeConfigUpdate):
    """
    Actualiza el modelo de Claude Code para próximas ejecuciones headless.
    Requiere nombre real del responsable (Part-11). Auditado en cadena.
    NUNCA expone ni modifica la API key de Anthropic.
    """
    import datetime

    # Validar modelo contra whitelist
    if body.model not in _ALLOWED_MODEL_IDS:
        raise HTTPException(422, f"Modelo no permitido: '{body.model}'. Permitidos: {sorted(_ALLOWED_MODEL_IDS)}")

    # Validar nombre real (no genérico)
    changed_by = body.changed_by.strip()
    if not changed_by or changed_by.lower() in _GENERIC_NAMES:
        raise HTTPException(422, f"changed_by debe ser nombre real, no genérico: '{body.changed_by}'")

    try:
        config = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
    except Exception:
        config = {}

    prev_model = config.get("claude_model", "claude-sonnet-4-6")
    config["claude_model"] = body.model
    config["model_changed_by"] = changed_by
    config["model_changed_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    RUNTIME_CONFIG.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")

    write_event("claude_model_changed", "factory_config", {
        "prev_model": prev_model,
        "new_model": body.model,
        "changed_by": changed_by,
        "decision_origin": "human_confirmed",
    })

    return {
        "status": "updated",
        "prev_model": prev_model,
        "active_model": body.model,
        "changed_by": changed_by,
        "audit": "event registered in chain",
    }


# ── Jobs ───────────────────────────────────────────────────────────────────────

@router.get("/jobs")
def get_jobs(queue: str | None = None, project_id: str | None = None):
    """Lista jobs. Filtrable por cola (pending/running/completed/failed) y project_id."""
    try:
        return list_jobs(queue=queue, project_id=project_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/jobs/{job_id}")
def get_job_detail(job_id: str):
    """Retorna un job por ID."""
    import re
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', job_id):
        raise HTTPException(400, "job_id debe ser un UUID válido")
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' no encontrado")
    return job


# ── Misiones ───────────────────────────────────────────────────────────────────

@router.post("/missions/{project_id}/run")
def post_run_mission(project_id: str):
    """
    Ejecuta la misión en modo plan-only / manual_assisted.
    NUNCA ejecuta headless. NUNCA ejecuta claude -p.
    """
    try:
        result = run_mission(project_id, plan_only=True)
        result["headless_executed"] = False
        result["claude_p_executed"] = False
        result["mode"] = "plan_only_manual_assisted"
        return result
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/recover")
def post_recover_mission(project_id: str):
    """Detecta estado parcial y genera plan de recuperación (sin ejecutar acciones)."""
    try:
        detection = detect_partial_f5(project_id)
        plan = create_recovery_plan(detection)
        write_event("layer8_recovery_required", project_id, {
            "recovery_needed": detection.get("found", False),
            "findings": detection.get("findings", {}),
        })
        return {"detection": detection, "recovery_plan": plan}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/gates")
def post_run_gates(project_id: str):
    """Ejecuta quality gates sobre el workspace del proyecto."""
    try:
        ws_path = str(Path(__file__).parent.parent.parent / "workspaces" / project_id)
        result = run_quality_gates(project_id, workspace_path=ws_path)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/deploy-if-authorized")
def post_deploy_if_authorized(project_id: str):
    """
    Comprueba si la misión tiene release aprobado.
    BLOQUEA si approval.json sigue en pending_approval.
    NUNCA despliega automáticamente — siempre requiere decisión humana final.
    """
    approval_status = _get_approval_status(project_id)

    if approval_status == "no_release":
        raise HTTPException(404, f"No se encontró release para '{project_id}'.")

    if approval_status != "approved":
        raise HTTPException(403, (
            f"Deploy BLOQUEADO: release de '{project_id}' en estado '{approval_status}'. "
            "Se requiere aprobación humana explícita (approval.json status=approved) "
            "antes de cualquier deployment."
        ))

    # Aunque llegue aquí (release aprobado), deploy requiere decisión humana final
    return {
        "project_id": project_id,
        "approval_status": approval_status,
        "deploy_authorized": False,
        "reason": (
            "Deploy requiere decisión humana explícita final (Capa 9). "
            "No se inicia automáticamente. Usar CLI o consola con confirmación humana."
        ),
        "next_step": "Confirmar deploy manualmente con: docker compose -f <workspace>/docker-compose.yml up -d",
    }


# ── Headless (F7/F8) ───────────────────────────────────────────────────────────

class HeadlessConfigPayload(BaseModel):
    enabled: bool
    timeout_seconds: int = 600
    approved_by: str = "human"


class HeadlessRunPayload(BaseModel):
    timeout: int = 600


@router.post("/headless/config")
def post_headless_config(payload: HeadlessConfigPayload):
    """
    Habilita o deshabilita headless en runtime_config.yaml.
    Requiere approved_by para registrar en audit quién autorizó.
    """
    try:
        config = {}
        if RUNTIME_CONFIG.exists():
            with open(RUNTIME_CONFIG, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

        config["headless_enabled"] = payload.enabled
        config["headless_timeout_seconds"] = payload.timeout_seconds

        with open(RUNTIME_CONFIG, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        event = "layer8_headless_enabled" if payload.enabled else "layer8_stop_condition_triggered"
        write_event(event, "factory_headless_config", {
            "headless_enabled": payload.enabled,
            "timeout_seconds": payload.timeout_seconds,
            "approved_by": payload.approved_by,
            "source": "factory_api",
        })

        return {
            "headless_enabled": payload.enabled,
            "timeout_seconds": payload.timeout_seconds,
            "config_file": str(RUNTIME_CONFIG),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/headless")
def post_run_headless(project_id: str, payload: HeadlessRunPayload = HeadlessRunPayload()):
    """
    Encola un job headless_run para ejecución en el HOST (no en el contenedor).
    Requiere headless_enabled=true en runtime_config.yaml.
    El CLI de claude está en el host — el worker host-side lo ejecuta.
    """
    try:
        config = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
        if not config.get("headless_enabled", False):
            return {"status": "disabled", "reason": "headless_enabled=false en runtime_config.yaml"}

        job = create_job(project_id, "headless_run", {"timeout": payload.timeout})
        write_event("layer8_claude_execution_started", project_id, {
            "source": "api_enqueue",
            "job_id": job["job_id"],
            "note": "worker host-side ejecutará el CLI de claude",
        })
        return {
            "status": "enqueued",
            "job_id": job["job_id"],
            "note": "worker host-side ejecuta el CLI. Ver /api/v1/layer8/jobs para estado.",
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/missions/{project_id}/headless/logs")
def get_headless_logs(project_id: str):
    """Lista los logs de ejecuciones headless del workspace."""
    ws = _safe_workspace(project_id)
    logs = sorted(ws.glob("headless_*.log"), reverse=True)
    result = []
    for log in logs[:10]:
        try:
            result.append({
                "filename": log.name,
                "size_bytes": log.stat().st_size,
                "preview": log.read_text(encoding="utf-8", errors="replace")[:400],
            })
        except Exception:
            result.append({"filename": log.name, "error": "no_legible"})
    return {"project_id": project_id, "logs": result}


# ── Build + Release Candidate ──────────────────────────────────────────────────

class RCBuildPayload(BaseModel):
    version: str


@router.post("/missions/{project_id}/build")
def post_build_mission(project_id: str):
    """Lanza el lazo autónomo de build. Requiere headless_enabled=True."""
    config = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
    if not config.get("headless_enabled", False):
        raise HTTPException(400, "headless_enabled=false — habilitar antes de ejecutar build")
    try:
        result = run_build_mission(project_id)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/missions/{project_id}/release-candidate")
def post_build_rc(project_id: str, body: RCBuildPayload):
    """Construye un Release Candidate formal y lo encola para revisión humana."""
    try:
        result = build_rc(project_id, body.version)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/missions/{project_id}/artifacts")
def get_mission_artifacts(project_id: str):
    """Vista previa de artefactos disponibles en el workspace."""
    ws_path = _safe_workspace(project_id)
    artifacts = []
    for fname in ["manifest.yaml", "test_report.json", "quality_gates_report.json"]:
        f = ws_path / fname
        if f.exists():
            artifacts.append({"file": fname, "size_bytes": f.stat().st_size})
    log_dir = ws_path / "logs"
    if log_dir.exists():
        for log in sorted(log_dir.glob("headless_*.log"), reverse=True)[:3]:
            artifacts.append({"file": f"logs/{log.name}", "size_bytes": log.stat().st_size})
    return {"project_id": project_id, "artifacts": artifacts}


_WS_BASE = Path(__file__).parent.parent.parent / "workspaces"
_SAFE_EXTS = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".sh", ".log", ".csv", ".sql"}
_MAX_FILE_BYTES = 50_000


def _safe_workspace(project_id: str) -> Path:
    """Convierte excepciones de path_policy a HTTPException para los endpoints."""
    from factory.core.path_policy import resolve_workspace
    try:
        return resolve_workspace(project_id, _WS_BASE)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))


@router.get("/missions/{project_id}/diff")
def get_mission_diff(project_id: str):
    """Diff del workspace respecto al repositorio."""
    _safe_workspace(project_id)
    try:
        return collect_diff(project_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/workspaces/{project_id}/tree")
def get_workspace_tree(project_id: str):
    ws = _safe_workspace(project_id)
    files = []
    for p in sorted(ws.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ws)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        files.append({"path": str(rel), "size": p.stat().st_size, "ext": p.suffix})
    return {"project_id": project_id, "file_count": len(files), "files": files[:300]}


@router.get("/workspaces/{project_id}/file")
def get_workspace_file(project_id: str, path: str):
    ws = _safe_workspace(project_id)
    try:
        target = (ws / path).resolve()
        target.relative_to(ws)
    except (ValueError, RuntimeError):
        raise HTTPException(400, "Path fuera del workspace")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    if target.suffix.lower() not in _SAFE_EXTS:
        raise HTTPException(400, f"Extension no permitida: {target.suffix}")
    size = target.stat().st_size
    if size > _MAX_FILE_BYTES:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {_MAX_FILE_BYTES})")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


# ── Preflight F5 ───────────────────────────────────────────────────────────────

_RC_BASE      = Path(__file__).parent.parent.parent / "release_candidates"
_WS_BASE      = Path(__file__).parent.parent.parent / "workspaces"
_JOBS_BASE    = Path(__file__).parent.parent.parent / "jobs"
_MISSIONS_DIR = Path(__file__).parent.parent.parent / "layer9" / "missions"


def _check_mission_approved(project_id: str) -> dict:
    mission_file = _MISSIONS_DIR / f"{project_id}.yaml"
    if not mission_file.exists():
        return {"id": "mission_approved", "ok": False, "detail": "Misión no encontrada"}
    m = yaml.safe_load(mission_file.read_text(encoding="utf-8"))
    ok = m.get("status") == "approved"
    approved_by = next(
        (h.get("by", "") for h in (m.get("history") or []) if h.get("event") == "approved"),
        m.get("approved_by", ""),
    )
    return {"id": "mission_approved", "ok": ok,
            "detail": f"approved by {approved_by}" if ok else f"status={m.get('status')}"}


def _check_headless_completed(project_id: str) -> dict:
    best = None
    for f in sorted((_JOBS_BASE / "completed").glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            if j.get("project_id") == project_id and j.get("job_type") == "headless_run":
                best = j
        except Exception:
            continue
    if not best:
        return {"id": "headless_completed", "ok": False, "detail": "Sin job headless completado"}
    rc = (best.get("result") or {}).get("returncode", -1)
    jid = best.get("job_id", "?")[:8]
    return {"id": "headless_completed", "ok": rc == 0, "detail": f"rc={rc}, job {jid}"}


def _check_tests_pass(project_id: str) -> dict:
    report = None
    ws_report = _WS_BASE / project_id / "test_report.json"
    if ws_report.exists():
        report = json.loads(ws_report.read_text(encoding="utf-8"))
    else:
        for f in sorted((_RC_BASE / project_id).rglob("test_report.json"), reverse=True):
            report = json.loads(f.read_text(encoding="utf-8"))
            break
    if not report:
        return {"id": "tests_pass", "ok": False, "detail": "Sin test_report.json"}
    s = report.get("summary", {})
    passed, failed = s.get("passed", 0), s.get("failed", 0)
    ok = failed == 0 and passed > 0
    return {"id": "tests_pass", "ok": ok, "detail": f"{passed}/{passed + failed} PASS"}


def _check_gates_no_fail(project_id: str) -> dict:
    gates_file = _WS_BASE / project_id / "quality_gates_report.json"
    if not gates_file.exists():
        return {"id": "gates_no_fail", "ok": True, "detail": "Sin reporte de quality gates (no bloquea)"}
    d = json.loads(gates_file.read_text(encoding="utf-8"))
    s = d.get("summary", {})
    fail = s.get("FAIL", 0)
    return {"id": "gates_no_fail", "ok": fail == 0,
            "detail": f"PASS={s.get('PASS',0)} FAIL={fail} SKIP={s.get('SKIPPED',0)}"}


def _check_rc_canonical(project_id: str) -> dict:
    rc_dir = _RC_BASE / project_id
    if rc_dir.exists():
        for f in rc_dir.rglob("rc_manifest.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if d.get("is_canonical") is True:
                    return {"id": "rc_canonical_marked", "ok": True,
                            "detail": f"RC {d.get('version','?')} marcado como canónico"}
            except Exception:
                continue
    return {"id": "rc_canonical_marked", "ok": False, "detail": "Sin RC canónico marcado"}


def _check_port(project_id: str) -> tuple[dict, dict]:
    from factory.core.port_registry import get_allocated_ports, validate_port_free
    ports = get_allocated_ports(project_id)
    if not ports:
        return (
            {"id": "port_reserved",    "ok": False, "detail": "Sin puerto reservado"},
            {"id": "no_docker_active", "ok": True,  "detail": "Sin puerto → sin contenedor activo"},
        )
    api_port = ports["api"]
    port_free = validate_port_free(api_port)
    return (
        {"id": "port_reserved",    "ok": True, "detail": str(api_port)},
        {"id": "no_docker_active", "ok": port_free,
         "detail": f"Sin contenedor activo en {api_port}" if port_free else f"Puerto {api_port} en uso"},
    )


def _check_pending_docs(project_id: str) -> dict:
    ws_report = _WS_BASE / project_id / "test_report.json"
    if not ws_report.exists():
        return {"id": "no_pending_documents_blocking", "ok": True, "detail": "Sin test_report"}
    d = json.loads(ws_report.read_text(encoding="utf-8"))
    note = d.get("note", "")
    if "PENDING_DOCUMENT" in note and "resueltos" not in note.lower():
        return {"id": "no_pending_documents_blocking", "ok": False, "detail": note[:100]}
    return {"id": "no_pending_documents_blocking", "ok": True, "detail": "PENDING_DOCUMENT no bloquean"}


@router.get("/missions/{project_id}/f5/preflight")
def get_f5_preflight(project_id: str):
    """
    Checklist read-only para determinar si el proyecto está listo para F5 (deploy Docker).
    No ejecuta nada — solo informa si se PODRÍA ejecutar F5.
    """
    port_check, docker_check = _check_port(project_id)
    checks = [
        _check_mission_approved(project_id),
        _check_headless_completed(project_id),
        _check_tests_pass(project_id),
        _check_gates_no_fail(project_id),
        _check_rc_canonical(project_id),
        port_check,
        docker_check,
        _check_pending_docs(project_id),
    ]
    blockers = [c["id"] for c in checks if not c["ok"]]
    ready = len(blockers) == 0

    next_action = None
    if "rc_canonical_marked" in blockers:
        next_action = "Marcar RC canónico desde Mission Control"
    elif "mission_approved" in blockers:
        next_action = "Aprobar la misión en Layer 9"
    elif "headless_completed" in blockers:
        next_action = "Ejecutar headless run de la misión"
    elif "tests_pass" in blockers:
        next_action = "Corregir tests fallidos en el workspace"
    elif "port_reserved" in blockers:
        next_action = "Reservar puerto con port_registry.assign_ports"
    elif blockers:
        next_action = f"Resolver: {blockers[0]}"
    else:
        next_action = "Listo para F5 — confirmar con Cesar antes de ejecutar"

    return {
        "project_id": project_id,
        "ready_for_f5": ready,
        "checks": checks,
        "blockers": blockers,
        "next_action": next_action,
    }
