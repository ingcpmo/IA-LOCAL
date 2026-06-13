"""
Capa 8 — Rutas API Runtime Controlado (F4.5d).

Expone el estado de Capa 8, jobs, ejecución de misiones en modo plan-only/manual_assisted.
NUNCA ejecuta headless. NUNCA ejecuta claude -p.
/deploy-if-authorized bloquea si approval.json sigue pending_approval.
"""

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.layer8.claude_account_status import check_claude_cli, write_status
from factory.layer8.claude_runtime import (
    run_controlled_headless,
    validate_task_safety,
    validate_workspace,
    prepare_manual_command,
)
from factory.layer8.job_queue import list_jobs, get_job
from factory.layer8.layer8_orchestrator import run_mission
from factory.layer8.recovery_manager import detect_partial_f5, create_recovery_plan
from factory.layer8.validation_manager import run_quality_gates
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
