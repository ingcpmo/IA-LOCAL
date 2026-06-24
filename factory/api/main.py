"""GMP AI Factory — FastAPI principal (Docker 2, puerto 9000)."""

import os
import sys
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.api.routes import projects, workspaces, agents, releases, deployments, approvals, layer9, layer8, status
from factory.core.audit_writer import verify_chain

FACTORY_API_KEY = os.getenv("FACTORY_API_KEY", "")
UI_FILE = Path(__file__).parent.parent / "ui" / "index.html"

app = FastAPI(title="GMP AI Factory", version="0.1.0", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(x_api_key: str = Header(default="")):
    if FACTORY_API_KEY and x_api_key != FACTORY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── UI ────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(str(UI_FILE), media_type="text/html")


# ── Health (público) ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"api": "ok", "service": "factory", "timestamp": int(time.time())}


# ── Audit (protegido) ─────────────────────────────────────────────────────────

@app.get("/api/v1/audit/verify", dependencies=[Depends(verify_api_key)])
def audit_verify():
    return verify_chain()


@app.get("/api/v1/audit/entries", dependencies=[Depends(verify_api_key)])
def audit_entries(limit: int = 50):
    import json as _json
    from factory.core.audit_writer import AUDIT_FILE
    if not AUDIT_FILE.exists():
        return []
    lines = [l.strip() for l in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    entries = []
    for raw in lines[-limit:]:
        try:
            entries.append(_json.loads(raw))
        except Exception:
            pass
    return entries


# ── Rutas protegidas ──────────────────────────────────────────────────────────

@app.get("/mission-control", include_in_schema=False)
async def mission_control_ui():
    from fastapi.responses import FileResponse
    ui = Path(__file__).parent.parent / "ui" / "mission_control.html"
    if ui.exists():
        return FileResponse(str(ui))
    return {"error": "mission_control.html not installed yet", "hint": "cp docs_plan/09_consola_capa9_mission_control.html factory/ui/mission_control.html"}


for router in [
    projects.router,
    workspaces.router,
    agents.router,
    releases.router,
    deployments.router,
    approvals.router,
    layer9.router,
    layer8.router,
    status.router,
]:
    app.include_router(router, dependencies=[Depends(verify_api_key)])
