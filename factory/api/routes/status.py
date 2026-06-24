"""
Factory Status — Rutas /api/v1/status/* (F8/F9).

Vista consolidada del estado de todos los stacks activos (Docker 1/2/3+),
y monitoreo de recursos del servidor vs resource_policy.yaml.
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import verify_chain

router = APIRouter(prefix="/api/v1/status", tags=["status"])

DEPLOYMENTS_BASE = Path(__file__).parent.parent.parent / "deployments"
REGISTRY_BASE = Path(__file__).parent.parent.parent / "registry"
POLICIES_BASE = Path(__file__).parent.parent.parent / "policies"


def _check_health(url: str, timeout: float = 4.0) -> dict:
    try:
        r = httpx.get(url, timeout=timeout)
        return {"reachable": True, "status_code": r.status_code, "body": r.json()}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "timeout"}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)[:80]}


def _discover_custom_deployments() -> list[dict]:
    """
    Lee factory/registry/ports.yaml y devuelve solo proyectos con deployment
    activo (directorio factory/deployments/{project_id}/ existe).
    Proyectos con puertos reservados pero sin deployment no se incluyen
    en health checks ni en conteo de recursos.
    """
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
            if api_port and (DEPLOYMENTS_BASE / project_id).is_dir():
                result.append({"project_id": project_id, "api_port": api_port})
        return result
    except Exception:
        return []


def _read_meminfo() -> dict:
    """Lee /proc/meminfo y devuelve MemTotal, MemFree, MemAvailable en MB."""
    data = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                val_kb = int(parts[1])
                data[key] = val_kb
    except Exception:
        return {}
    total_mb = data.get("MemTotal", 0) // 1024
    free_mb = data.get("MemFree", 0) // 1024
    available_mb = data.get("MemAvailable", 0) // 1024
    used_mb = total_mb - available_mb
    return {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "available_mb": available_mb,
        "free_mb": free_mb,
        "used_pct": round(used_mb / total_mb * 100, 1) if total_mb else 0,
    }


def _read_disk() -> dict:
    """Lee uso del disco raíz vía os.statvfs."""
    try:
        st = os.statvfs("/")
        total_gb = round(st.f_blocks * st.f_frsize / 1024**3, 1)
        free_gb = round(st.f_bfree * st.f_frsize / 1024**3, 1)
        available_gb = round(st.f_bavail * st.f_frsize / 1024**3, 1)
        used_gb = round(total_gb - free_gb, 1)
        return {
            "total_gb": total_gb,
            "used_gb": used_gb,
            "available_gb": available_gb,
            "used_pct": round(used_gb / total_gb * 100, 1) if total_gb else 0,
        }
    except Exception as exc:
        return {"error": str(exc)}


RUNTIME_CONFIG = Path(__file__).parent.parent.parent / "runtime" / "runtime_config.yaml"


@router.get("/risks")
def get_risks():
    """Deriva riesgos dinámicos del estado actual del sistema."""
    risks = []

    # R1: cadena de auditoría — distingue fork concurrente de hash corrupto
    try:
        audit = verify_chain()
        if not audit.get("part11_compliant"):
            h_err = audit.get("hash_errors", 0)
            c_err = audit.get("chain_errors", 0)
            is_fork_only = h_err == 0 and c_err > 0
            risks.append({
                "id": "RISK_AUDIT_CHAIN",
                "severity": "medio" if is_fork_only else "alto",
                "description": (
                    f"Fork concurrente en cadena de auditoría ({c_err} fork, 0 hash_errors) "
                    f"— contenido auténtico, no hay corrupción de datos"
                    if is_fork_only else
                    f"Cadena de auditoría inválida: "
                    f"{c_err} errores de cadena, {h_err} errores de hash"
                ),
            })
    except Exception:
        pass

    # R2: headless activo
    try:
        if RUNTIME_CONFIG.exists():
            cfg = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {}
            if cfg.get("headless_enabled"):
                risks.append({
                    "id": "RISK_HEADLESS_ON",
                    "severity": "alto",
                    "description": "headless_enabled=true — confirmar que la misión headless terminó y devolver a OFF",
                })
    except Exception:
        pass

    # R3: misiones interrumpidas
    try:
        from factory.layer9.mission_control import list_missions
        for m in list_missions():
            if "interrupted" in (m.get("status") or ""):
                risks.append({
                    "id": f"RISK_INTERRUPTED_{m['project_id'].upper()}",
                    "severity": "medio",
                    "description": f"Misión '{m['project_id']}' en estado '{m['status']}' — requiere revisión manual",
                })
    except Exception:
        pass

    # R4: disco
    try:
        disk = _read_disk()
        if disk.get("used_pct", 0) > 70:
            risks.append({
                "id": "RISK_DISK_USAGE",
                "severity": "medio",
                "description": f"Disco al {disk['used_pct']}% — umbral de alerta: 80%",
            })
    except Exception:
        pass

    # R5: soluciones custom en límite
    try:
        customs = _discover_custom_deployments()
        policy_file = POLICIES_BASE / "resource_policy.yaml"
        max_c = 2
        if policy_file.exists():
            max_c = (yaml.safe_load(policy_file.read_text(encoding="utf-8")) or {}).get("max_active_custom_solutions", 2)
        if len(customs) >= max_c:
            risks.append({
                "id": "RISK_CUSTOM_AT_LIMIT",
                "severity": "info",
                "description": f"Soluciones custom en el límite ({len(customs)}/{max_c}) — sin capacidad de nuevos deploys",
            })
    except Exception:
        pass

    return {"risks": risks, "count": len(risks)}


@router.get("/resources")
def get_resources():
    """
    Monitoreo de recursos del servidor vs resource_policy.yaml.
    Incluye RAM, disco y conteo de soluciones custom activas.
    """
    # Cargar política
    policy_file = POLICIES_BASE / "resource_policy.yaml"
    try:
        with open(policy_file, encoding="utf-8") as f:
            policy = yaml.safe_load(f)
    except Exception as exc:
        policy = {}
        policy_error = str(exc)
    else:
        policy_error = None

    max_custom = policy.get("max_active_custom_solutions", 2)

    mem = _read_meminfo()
    disk = _read_disk()
    customs = _discover_custom_deployments()
    active_custom_count = len(customs)

    # Umbrales de compliance
    mem_warn_pct = 85
    disk_warn_pct = 80
    mem_ok = mem.get("used_pct", 0) < mem_warn_pct
    disk_ok = disk.get("used_pct", 0) < disk_warn_pct
    custom_ok = active_custom_count <= max_custom

    compliant = mem_ok and disk_ok and custom_ok

    result = {
        "compliant": compliant,
        "policy_version": policy.get("version", "unknown"),
        "memory": {
            **mem,
            "ok": mem_ok,
            "threshold_warn_pct": mem_warn_pct,
        },
        "disk": {
            **disk,
            "ok": disk_ok,
            "threshold_warn_pct": disk_warn_pct,
        },
        "custom_solutions": {
            "active": active_custom_count,
            "max_allowed": max_custom,
            "ok": custom_ok,
            "projects": [d["project_id"] for d in customs],
        },
    }
    if policy_error:
        result["policy_error"] = policy_error
    return result


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
            "audit_entries": audit.get("log_count", 0),
            "audit_hash_errors": audit.get("hash_errors", 0),
            "audit_chain_errors": audit.get("chain_errors", 0),
        },
        "docker_1_base": {"port": 8000, "health": d1},
        "docker_2_factory": {"port": 9000, "health": d2},
        "custom_solutions": customs,
        "audit": audit,
    }
