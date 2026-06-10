"""Gestión de proyectos sobre factory/projects/projects.json."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

PROJECTS_FILE = Path(__file__).parent.parent / "projects" / "projects.json"


def _load() -> list[dict]:
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PROJECTS_FILE.exists():
        return []
    return json.loads(PROJECTS_FILE.read_text()).get("projects", [])


def _save(projects: list[dict]) -> None:
    PROJECTS_FILE.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False))


def create_project(project_id: str, name: str, description: str = "") -> dict:
    projects = _load()
    if any(p["id"] == project_id for p in projects):
        raise ValueError(f"Proyecto '{project_id}' ya existe")
    project = {
        "id": project_id,
        "name": name,
        "description": description,
        "requirements": [],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    projects.append(project)
    _save(projects)
    write_event("project_created", project_id, {"name": name, "description": description})
    return project


def get_project(project_id: str) -> dict | None:
    return next((p for p in _load() if p["id"] == project_id), None)


def list_projects() -> list[dict]:
    return _load()


def add_requirement(project_id: str, requirement_text: str) -> dict:
    projects = _load()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        raise ValueError(f"Proyecto '{project_id}' no encontrado")
    req = {
        "text": requirement_text,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    project.setdefault("requirements", []).append(req)
    _save(projects)
    write_event("requirement_registered", project_id, {"requirement": requirement_text})
    return project


def update_project(project_id: str, updates: dict) -> dict:
    projects = _load()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        raise ValueError(f"Proyecto '{project_id}' no encontrado")
    project.update(updates)
    _save(projects)
    return project
