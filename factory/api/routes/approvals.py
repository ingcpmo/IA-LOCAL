import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import write_event

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

WORKSPACES_DIR  = Path(__file__).parent.parent.parent / "workspaces"
APPROVALS_DIR   = Path(__file__).parent.parent.parent / "approvals"


class ApprovalAction(BaseModel):
    action: str
    approved_by: str = "Cesar"
    notes: str = ""
    version: str = ""
    gates_report_hash: str = ""


@router.post("/{project_id}", status_code=201)
def post_approval(project_id: str, body: ApprovalAction):
    ws_approval = WORKSPACES_DIR / project_id / "approval.json"
    approval = {
        "action": body.action,
        "project_id": project_id,
        "version": body.version,
        "approved_by": body.approved_by,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "gates_report_hash": body.gates_report_hash,
        "notes": body.notes,
        "status": "approved",
    }
    ws_approval.parent.mkdir(parents=True, exist_ok=True)
    ws_approval.write_text(json.dumps(approval, indent=2))

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (APPROVALS_DIR / f"{project_id}_{body.action}_{ts}.json").write_text(
        json.dumps(approval, indent=2)
    )

    write_event("approval_granted", project_id, approval)
    return approval


@router.post("/{project_id}/reject", status_code=201)
def post_rejection(project_id: str, body: ApprovalAction):
    rejection = {
        "action": body.action,
        "project_id": project_id,
        "approved_by": body.approved_by,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "notes": body.notes,
        "status": "rejected",
    }
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    (APPROVALS_DIR / f"{project_id}_{body.action}_rejected_{ts}.json").write_text(
        json.dumps(rejection, indent=2)
    )
    write_event("approval_rejected", project_id, rejection)
    return rejection


@router.get("/{project_id}")
def get_approvals(project_id: str):
    if not APPROVALS_DIR.exists():
        return []
    return [
        json.loads(f.read_text())
        for f in sorted(APPROVALS_DIR.glob(f"{project_id}_*.json"))
    ]
