import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.workspace_manager import (
    create_workspace, get_workspace_status, list_workspaces, close_workspace
)
from factory.api.auth import require_identity

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    project_id: str
    base_tag: str = "base-v1.0.0"
    name: str = ""
    description: str = ""
    requirement: str = ""


@router.get("")
def get_workspaces():
    return list_workspaces()


@router.post("", status_code=201)
def post_workspace(body: WorkspaceCreate):
    try:
        return create_workspace(
            body.project_id, body.base_tag,
            body.name, body.description, body.requirement
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}")
def get_workspace(project_id: str):
    s = get_workspace_status(project_id)
    if not s:
        raise HTTPException(404, f"Workspace '{project_id}' no existe")
    return s


@router.delete("/{project_id}")
def delete_workspace(project_id: str,
                     identity: str = Depends(require_identity)):
    # H-1: cerrar/borrar un workspace es destructivo -> exige identidad autenticada (401 sin ella).
    try:
        return close_workspace(project_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
