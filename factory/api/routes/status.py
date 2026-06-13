"""
Factory Status — Ruta /api/v1/status/full (F8).

Vista consolidada del estado de todos los stacks activos (Docker 1/2/3+).
Lee deployments/ para descubrir soluciones activas y consulta sus health endpoints.
"""

import json
import sys
import time
from pathlib import Path

import httpx
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import verify_chain

router = APIRouter(prefix="/api/v1/status", tags=["status"])

DEPLOYMENTS_BASE = Path(__file__).parent.parent.parent / "deployments"
REGISTRY_BASE = Path(__file__).parent.parent.parent / "registry"


def _check_health(url: str, timeout: float = 4.0) -> dict:
    try:
        r = httpx.get(url, timeout=timeout)
        return {"reachable": True, "status_code": r.status_code, "body": r.json()}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "timeout"}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)[:80]}


def _discover_custom_deployments() -> list[dict]:
    """Lee factory/registry/ports.yaml para descubrir soluciones custom activas."""
    ports_file = REGISTRY_BASE / "ports.yaml"
    if not ports_file.exists():
        return []
    try:
        import yaml
        with open(ports_file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        allocs = data.get("allocations", {})
        result = []
        for project_id, info in allocs.items():
            api_port = info.get("ports", {}).get("api")
            if api_port:
                result.append({"project_id": project_id, "api_port": api_port})
        return result
    except Exception:
        return []


@router.get("/full")
def get_full_status():
    """
    Estado consolidado de todos los stacks:
    - Docker 1 (base :8000)
    - Docker 2 (factory :9000)
    - Docker 3..N (custom, puertos dinámicos desde registry)
    - Audit chain
    """
    ts = int(time.time())

    # Docker 1 — base GMP AI Copilot
    d1 = _check_health("http://host.docker.internal:8000/health")

    # Docker 2 — factory (self — si este código corre, factory está activo)
    d2 = {"reachable": True, "status_code": 200, "body": {"api": "ok", "service": "factory"}}

    # Docker 3..N — soluciones custom
    customs = []
    for dep in _discover_custom_deployments():
        pid = dep["project_id"]
        port = dep["api_port"]
        health = _check_health(f"http://host.docker.internal:{port}/health")

        # Leer approval.json para estado de release
        approval_path = DEPLOYMENTS_BASE / pid / "approval.json"
        approval_status = "unknown"
        if approval_path.exists():
            try:
                d = json.loads(approval_path.read_text(encoding="utf-8"))
                approval_status = d.get("status", "unknown")
            except Exception:
                pass

        customs.append({
            "project_id": pid,
            "api_port": port,
            "health": health,
            "approval_status": approval_status,
        })

    # Audit chain
    try:
        audit = verify_chain()
    except Exception as exc:
        audit = {"verified": False, "error": str(exc)}

    # Contadores
    all_stacks = [d1, d2] + [c["health"] for c in customs]
    ok_count = sum(1 for s in all_stacks if s.get("reachable") and s.get("status_code", 0) == 200)
    err_count = len(all_stacks) - ok_count

    return {
        "timestamp": ts,
        "summary": {
            "stacks_total": len(all_stacks),
            "stacks_ok": ok_count,
            "stacks_error": err_count,
            "audit_verified": audit.get("verified", False),
            "audit_entries": audit.get("verified_count", 0),
        },
        "docker_1_base": {"port": 8000, "health": d1},
        "docker_2_factory": {"port": 9000, "health": d2},
        "custom_solutions": customs,
        "audit": audit,
    }
