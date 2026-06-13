import json
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.project_manager import (
    create_project, get_project, list_projects, add_requirement
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

FACTORY_BASE = Path(__file__).parent.parent.parent
WORKSPACES_DIR = FACTORY_BASE / "workspaces"
RELEASES_DIR = FACTORY_BASE / "releases"
DEPLOYMENTS_DIR = FACTORY_BASE / "deployments"
REGISTRY_FILE = FACTORY_BASE / "registry" / "ports.yaml"


class ProjectCreate(BaseModel):
    id: str
    name: str
    description: str = ""


class RequirementAdd(BaseModel):
    text: str


@router.get("")
def get_projects():
    return list_projects()


@router.post("", status_code=201)
def post_project(body: ProjectCreate):
    try:
        return create_project(body.id, body.name, body.description)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}")
def get_project_detail(project_id: str):
    p = get_project(project_id)
    if not p:
        raise HTTPException(404, f"Proyecto '{project_id}' no encontrado")
    return p


@router.post("/{project_id}/requirements", status_code=201)
def post_requirement(project_id: str, body: RequirementAdd):
    try:
        return add_requirement(project_id, body.text)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{project_id}/pipeline")
def get_project_pipeline(project_id: str):
    """Vista de pipeline completo: workspace → releases → deployment."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, f"Proyecto '{project_id}' no encontrado")

    # Workspace
    ws_path = WORKSPACES_DIR / project_id
    workspace = {
        "exists": ws_path.exists(),
        "path": str(ws_path),
    }
    if ws_path.exists():
        files = list(ws_path.rglob("*"))
        workspace["file_count"] = sum(1 for f in files if f.is_file())
        # Detectar si hay task.md (trabajo activo)
        workspace["has_task"] = (ws_path / "task.md").exists()
        workspace["has_tests"] = (ws_path / "tests").exists()

    # Releases
    releases_path = RELEASES_DIR / project_id
    releases = []
    if releases_path.exists():
        for version_dir in sorted(releases_path.iterdir()):
            if not version_dir.is_dir():
                continue
            manifest_path = version_dir / "manifest.yaml"
            approval_path = version_dir / "approval.json"
            rel_entry = {"version": version_dir.name}
            if manifest_path.exists():
                try:
                    m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                    rel_entry["created_at"] = m.get("created_at", "")
                    rel_entry["gates_passed"] = m.get("quality_gates", {}).get("passed", False)
                except Exception:
                    pass
            if approval_path.exists():
                try:
                    ap = json.loads(approval_path.read_text(encoding="utf-8"))
                    rel_entry["approval_status"] = ap.get("status", "unknown")
                except Exception:
                    pass
            releases.append(rel_entry)

    # Deployment
    dep_path = DEPLOYMENTS_DIR / project_id
    deployment = {"exists": dep_path.exists()}
    if dep_path.exists():
        meta_path = dep_path / "deployment_meta.json"
        if meta_path.exists():
            try:
                deployment["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Registry (puerto asignado)
    registry = {}
    if REGISTRY_FILE.exists():
        try:
            reg_data = yaml.safe_load(REGISTRY_FILE.read_text(encoding="utf-8")) or {}
            alloc = reg_data.get("allocations", {}).get(project_id)
            if alloc:
                registry["ports"] = alloc.get("ports", {})
                registry["allocated_at"] = alloc.get("allocated_at", "")
        except Exception:
            pass

    return {
        "project_id": project_id,
        "project": project,
        "workspace": workspace,
        "releases": releases,
        "deployment": deployment,
        "registry": registry,
    }
