"""
Capa 8 Tier-2 — Code Generation Manager.

Gestiona el plan de generación y la recolección de outputs.
Por defecto opera en modo manual_assisted — nunca lanza claude -p.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.claude_runtime import (
    prepare_manual_command,
    run_controlled_headless,
    validate_task_safety,
    validate_workspace,
)

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def prepare_generation_plan(project_id: str, design_artifacts: dict | None = None) -> dict[str, Any]:
    """
    Prepara el plan de generación a partir de los artefactos de diseño.
    Valida workspace y task safety antes de generar el plan.
    Retorna el plan sin ejecutar nada.
    """
    ws_validation = validate_workspace(project_id)
    safety = validate_task_safety(project_id)

    plan = {
        "project_id": project_id,
        "created_at": _ts(),
        "mode": "manual_assisted",
        "workspace_valid": ws_validation["valid"],
        "workspace_missing": ws_validation.get("missing", []),
        "task_safe": safety["safe"],
        "task_violations": safety.get("violations", []),
        "design_artifacts_provided": design_artifacts is not None,
        "steps": [
            {"step": 1, "action": "validate_workspace", "status": "ok" if ws_validation["valid"] else "fail"},
            {"step": 2, "action": "validate_task_safety", "status": "ok" if safety["safe"] else "fail"},
            {"step": 3, "action": "prepare_manual_command", "status": "pending"},
            {"step": 4, "action": "run_generation", "status": "pending", "note": "manual_assisted — ver comando en step 3"},
            {"step": 5, "action": "collect_generation_outputs", "status": "pending"},
        ],
        "ready_for_manual_run": ws_validation["valid"] and safety["safe"],
    }

    if plan["ready_for_manual_run"]:
        cmd_info = prepare_manual_command(project_id)
        plan["manual_command"] = cmd_info["manual_command"]
        plan["steps"][2]["status"] = "ok"
    else:
        plan["manual_command"] = None
        plan["steps"][2]["status"] = "blocked"

    return plan


def run_generation(project_id: str, plan: dict | None = None, mode: str = "manual_assisted") -> dict[str, Any]:
    """
    Ejecuta la generación en el modo especificado.
    Modo manual_assisted: devuelve el comando y espera ejecución humana.
    Nunca llama a claude -p directamente.
    """
    if mode != "manual_assisted":
        result = run_controlled_headless(project_id)
        if result.get("status") != "running":
            return {
                "project_id": project_id,
                "status": result.get("status", "disabled"),
                "mode": mode,
                "reason": result.get("reason", "headless no disponible"),
            }

    cmd_info = prepare_manual_command(project_id)
    write_event("layer8_claude_execution_started", project_id, {
        "mode": "manual_assisted",
        "workspace_path": cmd_info["workspace_path"],
    })

    return {
        "project_id": project_id,
        "status": "awaiting_manual_execution",
        "mode": "manual_assisted",
        "manual_command": cmd_info["manual_command"],
        "note": (
            "Ejecutar el comando manual en la terminal. "
            "Cuando termine, llamar collect_generation_outputs()."
        ),
    }


def collect_generation_outputs(project_id: str) -> dict[str, Any]:
    """
    Recolecta los outputs generados en el workspace.
    Retorna inventario de archivos .py y de tests.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return {"project_id": project_id, "found": False, "error": f"Workspace '{project_id}' no existe."}

    py_files = [str(f.relative_to(ws_path)) for f in ws_path.rglob("*.py")]
    test_files = [f for f in py_files if "test" in f.lower()]
    yaml_files = [str(f.relative_to(ws_path)) for f in ws_path.rglob("*.yaml")]

    result = {
        "project_id": project_id,
        "workspace_path": str(ws_path),
        "py_files_count": len(py_files),
        "test_files_count": len(test_files),
        "yaml_files_count": len(yaml_files),
        "py_files": py_files[:30],
        "test_files": test_files,
        "collected_at": _ts(),
    }

    write_event("layer8_claude_execution_completed", project_id, {
        "py_files_count": len(py_files),
        "test_files_count": len(test_files),
    })

    return result
