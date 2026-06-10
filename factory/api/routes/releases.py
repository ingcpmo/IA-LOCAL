import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.release_manager import create_release, list_releases, get_release

router = APIRouter(prefix="/api/v1/releases", tags=["releases"])


class ReleaseCreate(BaseModel):
    workspace_path: str = ""


@router.get("")
def get_all_releases():
    return list_releases()


@router.get("/{project_id}")
def get_project_releases(project_id: str):
    return list_releases(project_id)


@router.post("/{project_id}/{version}", status_code=201)
def post_release(project_id: str, version: str, body: ReleaseCreate):
    from factory.core.workspace_manager import WORKSPACES_DIR
    ws_path = body.workspace_path or str(WORKSPACES_DIR / project_id)
    if not Path(ws_path).exists():
        raise HTTPException(404, f"Workspace no encontrado: {ws_path}")
    try:
        return create_release(project_id, version, ws_path)
    except ValueError as e:
        raise HTTPException(409, str(e))
