"""
Capa 8 Tier-2 — Claude Runtime.

Valida workspace y task safety, prepara comandos manuales.
headless_enabled=false por defecto — run_controlled_headless retorna {"status":"disabled"}.

Nunca usa --dangerously-skip-permissions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"
RUNTIME_CONFIG = Path(__file__).parent.parent / "runtime" / "runtime_config.yaml"

REQUIRED_WORKSPACE_FILES = ["CLAUDE.md", "task.md", ".claude/settings.json"]

FORBIDDEN_TASK_PATTERNS = [
    "/home/ing_cpmo/app",
    "/home/ing_cpmo/.env",
    "/home/ing_cpmo/docker-compose.yml",
    "/home/ing_cpmo/data",
    "/home/ing_cpmo/backups/pre_factory",
    "--dangerously-skip-permissions",
    "git push",
    "rm -rf",
]


def _load_runtime_config() -> dict:
    if RUNTIME_CONFIG.exists():
        with open(RUNTIME_CONFIG, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {"headless_enabled": False, "default_mode": "manual_assisted", "headless_timeout_seconds": 1800}


def validate_workspace(project_id: str) -> dict:
    """
    Verifica que el workspace tenga los archivos requeridos:
    CLAUDE.md, task.md, .claude/settings.json.
    Retorna {"valid": bool, "missing": list, "workspace_path": str}.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return {
            "valid": False,
            "workspace_path": str(ws_path),
            "missing": REQUIRED_WORKSPACE_FILES,
            "error": f"Workspace '{project_id}' no existe.",
        }

    missing = [f for f in REQUIRED_WORKSPACE_FILES if not (ws_path / f).exists()]
    return {
        "valid": len(missing) == 0,
        "workspace_path": str(ws_path),
        "missing": missing,
    }


def validate_task_safety(project_id: str) -> dict:
    """
    Lee task.md y rechaza si contiene rutas o comandos prohibidos.
    Retorna {"safe": bool, "violations": list}.
    """
    ws_path = WORKSPACES_BASE / project_id
    task_file = ws_path / "task.md"

    if not task_file.exists():
        return {"safe": True, "violations": [], "note": "task.md no encontrado — sin restricciones que validar."}

    content = task_file.read_text(encoding="utf-8")
    violations = [pattern for pattern in FORBIDDEN_TASK_PATTERNS if pattern in content]

    return {
        "safe": len(violations) == 0,
        "violations": violations,
        "task_file": str(task_file),
    }


def prepare_manual_command(project_id: str) -> dict:
    """
    Devuelve el comando manual esperado para ejecutar Claude Code en el workspace.
    No ejecuta nada — solo prepara el comando.
    """
    ws_path = WORKSPACES_BASE / project_id
    cmd = f"cd {ws_path} && claude"
    return {
        "project_id": project_id,
        "workspace_path": str(ws_path),
        "manual_command": cmd,
        "note": "Ejecutar manualmente en la terminal. NO usar --dangerously-skip-permissions.",
    }


def run_controlled_headless(project_id: str, timeout: int = 1800) -> dict:
    """
    Modo headless controlado.
    Si headless_enabled es false (por defecto), retorna {"status": "disabled"}.
    Nunca ejecuta claude -p.
    Nunca usa --dangerously-skip-permissions.

    Para habilitar headless en el futuro se requiere doble llave:
      1. headless_enabled: true en runtime_config.yaml
      2. misión permite run_claude_code
      3. validate_task_safety OK
    """
    config = _load_runtime_config()

    if not config.get("headless_enabled", False):
        write_event("layer8_stop_condition_triggered", project_id, {
            "condition": "headless_disabled",
            "headless_enabled": False,
            "mode": config.get("default_mode", "manual_assisted"),
        })
        return {
            "status": "disabled",
            "reason": "headless_enabled=false en runtime_config.yaml",
            "action": "Usar prepare_manual_command() para ejecutar manualmente.",
        }

    # Validaciones antes de cualquier ejecución
    ws_validation = validate_workspace(project_id)
    if not ws_validation["valid"]:
        write_event("layer8_claude_execution_failed", project_id, {
            "reason": "workspace_invalid",
            "missing": ws_validation.get("missing", []),
        })
        return {
            "status": "error",
            "reason": "workspace_invalid",
            "missing": ws_validation.get("missing", []),
        }

    safety = validate_task_safety(project_id)
    if not safety["safe"]:
        write_event("layer8_claude_execution_failed", project_id, {
            "reason": "task_safety_violated",
            "violations": safety["violations"],
        })
        return {
            "status": "error",
            "reason": "task_safety_violated",
            "violations": safety["violations"],
        }

    # Reservado para F4.5d — no implementado en esta fase
    return {
        "status": "disabled",
        "reason": "Ejecución headless no implementada en F4.5c.",
        "note": "Disponible en F4.5d con doble llave habilitada.",
    }
