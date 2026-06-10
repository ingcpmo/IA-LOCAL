"""
Bridge que genera task packages por workspace desde las políticas YAML.

Genera en <workspace_path>/:
  - task.md              (desde claude_task_template.md + manifest)
  - CLAUDE.md            (desde claude_md_template.md + manifest)
  - .claude/settings.json (desde settings_template.json + code_agent_policy.yaml)

Registra task_dispatched en factory_audit.jsonl.
CLAUDE.md y settings.json se generan DESDE los YAML para que política
y enforcement nunca diverjan.
"""

import json
import re
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

BRIDGE_DIR  = Path(__file__).parent
FACTORY_DIR = BRIDGE_DIR.parent
POLICIES_DIR = FACTORY_DIR / "policies"

TASK_TEMPLATE   = BRIDGE_DIR / "claude_task_template.md"
CLAUDE_TEMPLATE = BRIDGE_DIR / "claude_md_template.md"
SETTINGS_TEMPLATE = BRIDGE_DIR / "settings_template.json"


def _render(content: str, variables: dict) -> str:
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replacer, content)


def _load_policy(name: str) -> dict:
    path = POLICIES_DIR / f"{name}.yaml"
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _build_deny_rules(project_id: str) -> list[str]:
    """Genera deny rules desde code_agent_policy.yaml para settings.json."""
    policy = _load_policy("code_agent_policy")
    workspace = f"/home/ing_cpmo/factory/workspaces/{project_id}"

    base_denies = [
        "Read(/home/ing_cpmo/.env)",
        f"Edit(/home/ing_cpmo/app/**)",
        f"Write(/home/ing_cpmo/app/**)",
        "Edit(/home/ing_cpmo/docker-compose.yml)",
        "Edit(/home/ing_cpmo/data/**)",
        "Write(/home/ing_cpmo/data/**)",
        "Edit(/home/ing_cpmo/backups/**)",
        "Write(/home/ing_cpmo/backups/**)",
        "Bash(rm -rf*)",
        "Bash(git push*)",
        "Bash(git commit*)",
        "Bash(docker compose -f /home/ing_cpmo/docker-compose.yml*)",
    ]

    forbidden_paths = policy.get("forbidden", [])
    extra = []
    for fp in forbidden_paths:
        if fp.startswith("contenedores"):
            continue
        clean = fp.rstrip("/")
        if not any(clean in d for d in base_denies):
            extra.append(f"Edit(/home/ing_cpmo/{clean}/**)")
            extra.append(f"Write(/home/ing_cpmo/{clean}/**)")

    return base_denies + extra


def generate_task_package(
    project_id: str,
    manifest: dict,
    workspace_path: str | Path,
    requirement_text: str = "",
) -> dict[str, Path]:
    """
    Genera task.md, CLAUDE.md y .claude/settings.json en workspace_path.
    Retorna dict con rutas de los archivos generados.
    """
    workspace_path = Path(workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / ".claude").mkdir(exist_ok=True)

    src = manifest.get("source", {})
    dep = manifest.get("deployment", {})
    agents = manifest.get("agents", {})

    variables = {
        "project_id":          project_id,
        "base_product_tag":    src.get("base_product_tag", "base-v1.0.0"),
        "base_product_commit": src.get("base_product_commit", ""),
        "api_port":            str(dep.get("api_port", "")),
        "postgres_port":       str(dep.get("postgres_port", "")),
        "redis_port":          str(dep.get("redis_port", "")),
        "requirement_text":    requirement_text or manifest.get("project", {}).get("description", ""),
        "agents_to_inherit":   ", ".join(agents.get("inherited", [])),
        "derived_profiles":    ", ".join(agents.get("profiles", {}).keys()) or "ninguno",
        "new_agents":          ", ".join(agents.get("custom", {}).keys()) or "ninguno",
        "acceptance_criteria": "Ver manifest.yaml — sección quality_gates",
        "test_battery_summary": f"G01-G13 + baterías por agente heredado",
    }

    # task.md
    task_content = _render(TASK_TEMPLATE.read_text(), variables)
    task_path = workspace_path / "task.md"
    task_path.write_text(task_content)

    # CLAUDE.md
    claude_content = _render(CLAUDE_TEMPLATE.read_text(), variables)
    claude_path = workspace_path / "CLAUDE.md"
    claude_path.write_text(claude_content)

    # .claude/settings.json — generado DESDE code_agent_policy.yaml
    deny_rules = _build_deny_rules(project_id)
    settings = {"permissions": {"deny": deny_rules}}
    settings_path = workspace_path / ".claude" / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2))

    # Registrar task_dispatched en audit de fábrica
    write_event("task_dispatched", project_id, {
        "workspace": str(workspace_path),
        "base_tag": src.get("base_product_tag", ""),
        "agents_inherited": agents.get("inherited", []),
        "files_generated": ["task.md", "CLAUDE.md", ".claude/settings.json"],
    })

    return {"task_md": task_path, "claude_md": claude_path, "settings_json": settings_path}
