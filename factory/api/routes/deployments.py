import json
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import write_event

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])

DEPLOYMENTS_DIR = Path(__file__).parent.parent.parent / "deployments"


@router.get("")
def get_deployments():
    if not DEPLOYMENTS_DIR.exists():
        return []
    result = []
    for d in DEPLOYMENTS_DIR.iterdir():
        if d.is_dir():
            meta = d / "deployment_meta.json"
            result.append(json.loads(meta.read_text()) if meta.exists() else {"project_id": d.name})
    return result


@router.get("/{project_id}")
def get_deployment(project_id: str):
    meta = DEPLOYMENTS_DIR / project_id / "deployment_meta.json"
    if not meta.exists():
        raise HTTPException(404, f"Deployment '{project_id}' no encontrado")
    return json.loads(meta.read_text())
