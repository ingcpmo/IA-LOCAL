"""
Capa 8 — Autonomous Build Orchestrator.

Lazo autónomo de generación: lee misión aprobada → aplica política →
valida workspace → encola job headless → ejecuta en host → registra resultado.

Nunca ejecuta sin misión approved y run_claude_code en allowed_actions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.autonomy_policy_engine import apply_policy, validate_action, check_stop_condition
from factory.layer8.claude_runtime import validate_workspace, validate_task_safety
from factory.layer8.host_worker import is_headless_enabled, reset_headless_after_job, poll_and_execute
from factory.layer8.job_queue import create_job
from factory.layer9.mission_control import get_mission

RUNTIME_CONFIG = Path(__file__).parent.parent / "runtime" / "runtime_config.yaml"


def run_build_mission(project_id: str) -> dict:
    """
    Lazo autónomo completo: misión aprobada → política → validación → headless → resultado.
    """
    # 1. Leer misión
    try:
        mission = get_mission(project_id)
    except Exception as exc:
        return {"status": "error", "reason": f"mission_not_found: {exc}"}

    if mission.get("status") != "approved":
        return {
            "status": "error",
            "reason": f"mission_not_approved: status={mission.get('status')}",
        }

    mission_approval = mission.get("mission_approval", {})

    # 2. Validar que run_claude_code está autorizado
    if not validate_action("run_claude_code", mission_approval):
        return {
            "status": "error",
            "reason": "run_claude_code_not_in_allowed_actions",
            "allowed_actions": mission_approval.get("allowed_actions", []),
        }

    # 3. Verificar headless_enabled
    if not is_headless_enabled():
        return {"status": "error", "reason": "headless_disabled"}

    # 4. Aplicar política de autonomía → genera settings.json en workspace
    policy = apply_policy(mission_approval, project_id)

    # 5. Validar workspace y task safety
    ws_result = validate_workspace(project_id)
    if not ws_result["valid"]:
        return {
            "status": "error",
            "reason": "workspace_invalid",
            "missing": ws_result.get("missing", []),
        }

    safety = validate_task_safety(project_id)
    if not safety["safe"]:
        return {
            "status": "error",
            "reason": "task_safety_violated",
            "violations": safety["violations"],
        }

    # 6. Crear job en pending/
    job = create_job(project_id, "headless_run", {
        "source": "autonomous_build_orchestrator",
        "policy": policy,
    })
    job_id = job["job_id"]

    # 7. Registrar inicio
    write_event("layer8_autobuild_started", project_id, {
        "job_id": job_id,
        "allowed_actions": mission_approval.get("allowed_actions", []),
        "headless_allowed": policy.get("headless_allowed", False),
    })

    # 8. Ejecutar en host
    result = poll_and_execute(once=True)

    # 9. Evaluar resultado
    returncode = result.get("returncode")
    if result.get("status") not in ("completed",) or (returncode is not None and returncode != 0):
        write_event("layer8_autobuild_failed", project_id, {
            "job_id": job_id,
            "result": result,
        })
        return {
            "status": "error",
            "reason": "autobuild_failed",
            "job_id": job_id,
            "worker_result": result,
        }

    # 10. Registrar éxito
    write_event("layer8_autobuild_completed", project_id, {
        "job_id": job_id,
        "returncode": returncode,
        "log_file": result.get("log_file"),
    })

    return {
        "status": "completed",
        "job_id": job_id,
        "log_file": result.get("log_file"),
        "returncode": returncode,
    }


def check_and_stop(event: str, project_id: str, mission_approval: dict) -> bool:
    """
    Evalúa si un evento dispara una stop_condition. Si sí, resetea headless.
    """
    if check_stop_condition(event, mission_approval):
        write_event("layer8_stop_condition_triggered", project_id, {
            "event": event,
            "stop_conditions": mission_approval.get("stop_conditions", []),
        })
        reset_headless_after_job(project_id)
        return True
    return False
