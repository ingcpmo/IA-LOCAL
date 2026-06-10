import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.project_manager import (
    create_project, get_project, list_projects, add_requirement
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


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
