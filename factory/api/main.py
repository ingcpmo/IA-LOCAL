"""GMP AI Factory — FastAPI principal (Docker 2, puerto 9000)."""

import asyncio
import json as _json
import logging
import logging.handlers
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.api.routes import projects, workspaces, agents, releases, deployments, approvals, layer9, layer8, status
from factory.core.audit_writer import verify_chain
from factory.core.rate_limit import RateLimitCounter

FACTORY_API_KEY = os.getenv("FACTORY_API_KEY", "")
UI_FILE = Path(__file__).parent.parent / "ui" / "mission_control.html"
_ACCESS_LOG = Path(__file__).parent.parent / "logs" / "access.jsonl"


def _setup_access_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"factory.access.{log_path}")
    if not logger.handlers:
        handler = logging.handlers.TimedRotatingFileHandler(
            str(log_path), when="midnight", backupCount=30, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log timestamp, IP, method, path, status, latency, user-agent. Never logs POST body."""

    def __init__(self, app, log_path: Path = _ACCESS_LOG):
        super().__init__(app)
        self._logger = _setup_access_logger(log_path)

    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ip": request.client.host if request.client else "-",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round((time.time() - start) * 1000, 1),
            "ua": request.headers.get("user-agent", "-")[:200],
        }
        self._logger.info(_json.dumps(entry))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter. Audit endpoints are exempt."""

    _AUDIT_PREFIX = "/api/v1/audit/"

    def __init__(self, app, public_limit: int = 60, auth_limit: int = 600, window: int = 60):
        super().__init__(app)
        self.public_limit = public_limit
        self.auth_limit = auth_limit
        self.window = window
        self._counters: dict[str, RateLimitCounter] = {}
        self._lock = asyncio.Lock()

    def _get_counter(self, key: str, limit: int) -> RateLimitCounter:
        if key not in self._counters:
            self._counters[key] = RateLimitCounter(limit, self.window)
        return self._counters[key]

    async def dispatch(self, request, call_next):
        if request.url.path.startswith(self._AUDIT_PREFIX):
            return await call_next(request)

        api_key = request.headers.get("x-api-key", "")
        if api_key:
            key = f"auth:{api_key}"
            limit = self.auth_limit
        else:
            ip = request.client.host if request.client else "unknown"
            key = f"ip:{ip}"
            limit = self.public_limit

        async with self._lock:
            counter = self._get_counter(key, limit)
            if not counter.allow():
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too Many Requests"},
                    headers={"Retry-After": str(self.window)},
                )

        return await call_next(request)


app = FastAPI(title="GMP AI Factory", version="0.1.0", docs_url="/api/docs", redoc_url=None)

# Middleware order (add_middleware = LIFO; last added = outermost = first to process request)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AccessLogMiddleware)


async def verify_api_key(x_api_key: str = Header(default="")):
    if FACTORY_API_KEY and x_api_key != FACTORY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── UI ────────────────────────────────────────────────────────────────────────

# W5: assets estáticos de la UI (css/ + js/ de Mission Control). Solo archivos
# de presentación — nunca secretos. Mismo nivel de exposición que el HTML que
# ya se servía en /mission-control.
app.mount("/ui", StaticFiles(directory=str(Path(__file__).parent.parent / "ui")), name="ui")


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


@app.get("/api/v1/audit/summary", dependencies=[Depends(verify_api_key)])
def audit_summary():
    """
    Resumen semántico Part-11 de la cadena de auditoría.
    assessment: "OK" | "WARN" (fork concurrente) | "FAIL" (corrupción real).
    """
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
