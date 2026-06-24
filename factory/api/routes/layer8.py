"""
Capa 8 — Rutas API Runtime Controlado (F4.5d/F8).

Expone el estado de Capa 8, jobs, ejecución de misiones.
Desde F7/F8: soporta headless controlado (doble llave: API call + headless_enabled=true).
/deploy-if-authorized bloquea si approval.json sigue pending_approval.
"""

import json
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
    """Retorna el último claude_status.json (sin credenciales)."""
    if not STATUS_FILE.exists():
        return {"status": "not_checked", "note": "Ejecutar POST /check para generar."}
    try:
        d = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        SENSITIVE = {"token", "password", "credential", "secret", "api_key", "auth_token"}
        safe = {k: v for k, v in d.items() if k.lower() not in SENSITIVE}
        return safe
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/claude/status/check")
def post_claude_status_check():
    """Dispara check_claude_cli() y escribe claude_status.json."""
    try:
        result = write_status("factory_status_check")
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


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
    ws_path = Path(__file__).parent.parent.parent / "workspaces" / project_id
    if not ws_path.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")

    logs = sorted(ws_path.glob("headless_*.log"), reverse=True)
    result = []
    for log in logs[:10]:
        try:
            content = log.read_text(encoding="utf-8")
            result.append({
                "filename": log.name,
                "path": str(log),
                "size_bytes": log.stat().st_size,
                "preview": content[:400],
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
    from factory.layer8.artifact_collector import WORKSPACES_BASE, RC_BASE
    import os
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")
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


@router.get("/missions/{project_id}/diff")
def get_mission_diff(project_id: str):
    """Diff del workspace respecto al repositorio."""
    try:
        return collect_diff(project_id)
    except Exception as e:
        raise HTTPException(500, str(e))


_WS_BASE = Path(__file__).parent.parent.parent / "workspaces"
_SAFE_EXTS = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".sh", ".log", ".csv", ".sql"}
_MAX_FILE_BYTES = 50_000


@router.get("/workspaces/{project_id}/tree")
def get_workspace_tree(project_id: str):
    ws = _WS_BASE / project_id
    if not ws.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")
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
    ws = _WS_BASE / project_id
    if not ws.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")
    try:
        target = (ws / path).resolve()
        target.relative_to(ws.resolve())
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
