"""
Capa 8 — Autonomy Policy Engine.

Traduce la aprobación de misión (Capa 9) en política de autonomía concreta:
- Qué puede hacer el agente (allowed_actions)
- Qué settings.json genera para el workspace
- Cuándo debe detenerse (stop_conditions)

NUNCA genera políticas que permitan --dangerously-skip-permissions.
NUNCA genera políticas que permitan rutas fuera del workspace.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"

FORBIDDEN_PATHS = [
    "/home/ing_cpmo/app",
    "/home/ing_cpmo/.env",
    "/home/ing_cpmo/docker-compose.yml",
    "/home/ing_cpmo/data",
    "/home/ing_cpmo/backups",
    "/home/ing_cpmo/ARIA",
    "/home/ing_cpmo/hotelbot",
]

_BASE_ALLOW = [
    {"type": "Read",  "pattern": "**"},
    {"type": "Write", "pattern": "**"},
    {"type": "Bash",  "pattern": "ls *"},
    {"type": "Bash",  "pattern": "ls -la *"},
    {"type": "Bash",  "pattern": "grep *"},
    {"type": "Bash",  "pattern": "find *"},
    {"type": "Bash",  "pattern": "cat *"},
]


def apply_policy(mission_approval: dict, project_id: str) -> dict:
    """
    Genera la política de autonomía para un workspace y escribe settings.json.
    Retorna {headless_allowed, deploy_allowed, settings_path, policy_summary}.
    """
    allowed_actions = mission_approval.get("allowed_actions", [])
    stop_conditions = mission_approval.get("stop_conditions", [])
    final_human = mission_approval.get("final_human_decision_required", [])

    headless_allowed = "run_claude_code" in allowed_actions
    deploy_allowed = (
        mission_approval.get("deploy_docker_if_gates_pass", False)
        and "deploy_docker" not in final_human
    )

    ws_path = WORKSPACES_BASE / project_id
    claude_dir = ws_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"

    allow_rules = list(_BASE_ALLOW)

    if "generate_code" in allowed_actions:
        allow_rules.append({"type": "Bash", "pattern": "python3 app/*.py"})
    if "run_tests" in allowed_actions:
        allow_rules.append({"type": "Bash", "pattern": "python3 -m pytest tests/*"})

    deny_rules = [{"type": "Bash", "pattern": p} for p in FORBIDDEN_PATHS]
    deny_rules.append({"type": "Bash", "pattern": "--dangerously-skip-permissions"})

    settings = {
        "permissions": {
            "allow": allow_rules,
            "deny": deny_rules,
        }
    }
    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    write_event("layer8_autonomy_policy_applied", project_id, {
        "headless_allowed": headless_allowed,
        "deploy_allowed": deploy_allowed,
        "allowed_actions": allowed_actions,
        "stop_conditions": stop_conditions,
        "settings_path": str(settings_path),
    })

    return {
        "headless_allowed": headless_allowed,
        "deploy_allowed": deploy_allowed,
        "settings_path": str(settings_path),
        "policy_summary": {
            "allowed_actions": allowed_actions,
            "stop_conditions": stop_conditions,
            "final_human_decision_required": final_human,
        },
    }


def validate_action(action: str, mission_approval: dict) -> bool:
    """True si la acción está en allowed_actions de la misión."""
    return action in mission_approval.get("allowed_actions", [])


def check_stop_condition(event: str, mission_approval: dict) -> bool:
    """True si el evento dispara una stop_condition de la misión."""
    return event in mission_approval.get("stop_conditions", [])
