"""
Capa 8 Tier-1 — Workspace Builder.

Crea o reanuda workspaces de soluciones custom.
Es IDEMPOTENTE: si el workspace ya existe, entra en modo resume.
Nunca sobrescribe un workspace cerrado ni modifica releases.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.requirement_interpreter import RequirementSpec

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"

REQUIRED_WORKSPACE_DIRS = ["app", "data", "knowledge", "scripts", "tests"]
REQUIRED_WORKSPACE_FILES: list[str] = []  # Se validan en runtime por claude_runtime.py


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_path(project_id: str) -> Path:
    return WORKSPACES_BASE / project_id


def _workspace_exists(project_id: str) -> bool:
    return _workspace_path(project_id).exists()


def _detect_mode(project_id: str) -> str:
    """Retorna 'resume' si el workspace existe, 'create' si no."""
    return "resume" if _workspace_exists(project_id) else "create"


def _collect_workspace_state(project_id: str) -> dict[str, Any]:
    """Inspecciona el workspace existente y reporta su estado."""
    ws_path = _workspace_path(project_id)
    if not ws_path.exists():
        return {"exists": False}

    dirs_present = [d for d in REQUIRED_WORKSPACE_DIRS if (ws_path / d).exists()]
    dirs_missing = [d for d in REQUIRED_WORKSPACE_DIRS if not (ws_path / d).exists()]
    all_files = list(ws_path.rglob("*"))
    py_files = [str(f.relative_to(ws_path)) for f in all_files if f.suffix == ".py"]
    yaml_files = [str(f.relative_to(ws_path)) for f in all_files if f.suffix in (".yaml", ".yml")]
    has_claude_md = (ws_path / "CLAUDE.md").exists()
    has_task_md = (ws_path / "task.md").exists()

    return {
        "exists": True,
        "path": str(ws_path),
        "dirs_present": dirs_present,
        "dirs_missing": dirs_missing,
        "py_files_count": len(py_files),
        "yaml_files_count": len(yaml_files),
        "has_claude_md": has_claude_md,
        "has_task_md": has_task_md,
    }


def _ensure_missing_dirs(project_id: str, missing: list[str]) -> list[str]:
    """Crea directorios faltantes en un workspace existente (modo resume)."""
    ws_path = _workspace_path(project_id)
    created = []
    for d in missing:
        target = ws_path / d
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(d)
    return created


def create_workspace_from_mission(project_id: str, spec: RequirementSpec) -> dict[str, Any]:
    """
    Punto de entrada principal. Idempotente.
    - Si el workspace NO existe: lo crea con estructura estándar.
    - Si ya existe: entra en modo resume (valida, completa faltantes, no sobrescribe).
    Nunca toca releases ni el workspace base del producto.
    """
    mode = _detect_mode(project_id)
    ws_path = _workspace_path(project_id)
    state = _collect_workspace_state(project_id)

    if mode == "resume":
        dirs_missing = state.get("dirs_missing", [])
        created_dirs = _ensure_missing_dirs(project_id, dirs_missing)
        result = {
            "project_id": project_id,
            "mode": "resume",
            "workspace_path": str(ws_path),
            "state": state,
            "dirs_created_on_resume": created_dirs,
            "message": (
                f"Workspace '{project_id}' ya existe — entrando en modo resume. "
                "No se sobrescribió ningún archivo existente."
            ),
        }
        write_event("layer8_workspace_resumed", project_id, {
            "workspace_path": str(ws_path),
            "dirs_present": state.get("dirs_present", []),
            "dirs_created": created_dirs,
            "py_files_count": state.get("py_files_count", 0),
        })
        return result

    # Modo create
    ws_path.mkdir(parents=True, exist_ok=True)
    for d in REQUIRED_WORKSPACE_DIRS:
        (ws_path / d).mkdir(parents=True, exist_ok=True)

    # Placeholder CLAUDE.md
    claude_md = ws_path / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(
            f"# Workspace: {project_id}\n\n"
            f"Dominios: {', '.join(spec.domains)}\n"
            f"Restricciones: ver mission en factory/layer9/missions/{project_id}.yaml\n",
            encoding="utf-8",
        )

    result = {
        "project_id": project_id,
        "mode": "create",
        "workspace_path": str(ws_path),
        "dirs_created": REQUIRED_WORKSPACE_DIRS,
        "message": f"Workspace '{project_id}' creado.",
    }
    write_event("layer8_workspace_created", project_id, {
        "workspace_path": str(ws_path),
        "dirs_created": REQUIRED_WORKSPACE_DIRS,
    })
    return result
