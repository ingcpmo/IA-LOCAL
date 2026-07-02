"""
W5 — Servicio de evidencia por misión (W3), extraído de routes/layer9.py
sin cambio de comportamiento.

Todas las funciones son READ-ONLY: nunca escriben en la cadena de
auditoría. Levantan HTTPException con los mismos códigos que las rutas
originales; el router de layer9 solo delega y maneja ETag/304.

Los tests redirigen rutas con monkeypatch sobre factory.services.paths y
el cliente HTTP con monkeypatch sobre este módulo (httpx).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import yaml as _yaml
from fastapi import HTTPException

from factory.services import paths


def etag_of(path_list: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(str(p) for p in path_list):
        fp = Path(p)
        if fp.exists():
            h.update(f"{p}:{fp.stat().st_mtime_ns}".encode())
    return f'"{h.hexdigest()[:16]}"'


def safe_design(project_id: str) -> Path:
    from factory.core.path_policy import resolve_design
    try:
        return resolve_design(project_id, paths.DESIGNS_BASE)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


def parse_headless_log(ws: Path) -> dict | None:
    logs = sorted(ws.glob("logs/headless_*.log"), reverse=True)
    if not logs:
        return None
    log_path = logs[0]
    try:
        raw = log_path.read_text(encoding="utf-8", errors="replace").strip()
        d = json.loads(raw)
        mu = d.get("modelUsage") or {}
        breakdown = {
            m: {
                "inputTokens": s.get("inputTokens", 0),
                "outputTokens": s.get("outputTokens", 0),
                "costUSD": round(s.get("costUSD", 0), 6),
            }
            for m, s in mu.items()
        }
        return {
            "log_filename": log_path.name,
            "log_size_bytes": log_path.stat().st_size,
            "returncode": 0 if not d.get("is_error") else 1,
            "subtype": d.get("subtype"),
            "duration_ms": d.get("duration_ms"),
            "duration_api_ms": d.get("duration_api_ms"),
            "num_turns": d.get("num_turns"),
            "terminal_reason": d.get("terminal_reason"),
            "total_cost_usd": d.get("total_cost_usd"),
            "models_used": list(mu.keys()),
            "model_breakdown": breakdown,
            "permission_denials": d.get("permission_denials", []),
            "result_text": (d.get("result") or "")[:4096],
            "session_id": d.get("session_id"),
        }
    except Exception:
        return {"log_filename": log_path.name, "log_size_bytes": log_path.stat().st_size, "parse_error": True}


def parse_agents(design_dir: Path) -> dict:
    proposal = design_dir / "agent_design_proposal.yaml"
    if not proposal.exists():
        return {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}}
    try:
        d = _yaml.safe_load(proposal.read_text(encoding="utf-8")) or {}
        agents = []
        for a in (d.get("agents") or []):
            agents.append({
                "agent_id": a.get("agent_id"),
                "decision": a.get("decision"),
                "is_inherited": a.get("decision") == "profile",
                "base_agent": a.get("base_agent"),
                "profile_name": a.get("profile_name"),
                "rationale": a.get("rationale", "")[:200],
                "routing_key": a.get("routing_key"),
            })
        profiles = sum(1 for a in agents if a["is_inherited"])
        new = sum(1 for a in agents if not a["is_inherited"])
        return {
            "agents": agents,
            "summary": {"profiles_inherited": profiles, "new_agents": new},
            "routing_notes": d.get("routing_notes", "")[:300],
        }
    except Exception:
        return {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}, "parse_error": True}


def deployment_health(project_id: str) -> dict:
    dep_dir = paths.DEP_BASE / project_id
    if not dep_dir.exists():
        return {"exists": False}
    # Puerto vía port_registry
    api_port = None
    try:
        from factory.core.port_registry import get_allocated_ports
        ports = get_allocated_ports(project_id)
        api_port = ports.get("api") if ports else None
    except Exception:
        pass
    health_ok = False
    health_body = None
    health_error = None
    if api_port:
        try:
            r = httpx.get(f"http://host.docker.internal:{api_port}/health", timeout=4)
            health_ok = r.status_code == 200
            health_body = r.json() if health_ok else None
        except Exception as e:
            health_error = str(e)[:100]
    # Archivos visibles (sin secretos)
    visible = []
    for p in sorted(dep_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(dep_dir))
        if any(blocked in rel for blocked in paths.FILTER_PARTS):
            continue
        visible.append({"path": rel, "size": p.stat().st_size, "ext": p.suffix})
    return {
        "exists": True,
        "api_port": api_port,
        "health_ok": health_ok,
        "health_body": health_body,
        "health_error": health_error,
        "docs_url": f"http://localhost:{api_port}/docs" if api_port else None,
        "files_visible": len(visible),
        "files": visible[:100],
    }


def build_mission_summary(project_id: str) -> dict:
    """
    Construye el cuerpo del resumen consolidado de la misión (sin manejo de
    ETag/304, que es responsabilidad del endpoint HTTP). Reutilizada por
    otras vistas read-only (ej. W4.1 /gmp-report).
    """
    # ── Misión ──
    mission_file = paths.FACTORY_ROOT / "layer9" / "missions" / f"{project_id}.yaml"
    if not mission_file.exists():
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")
    try:
        m = _yaml.safe_load(mission_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise HTTPException(500, f"Error leyendo misión: {e}")

    approved_by = next(
        (h.get("by", "") for h in (m.get("history") or []) if h.get("event") == "approved"),
        m.get("approved_by", ""),
    )
    mission_block = {
        "status": m.get("status"),
        "client_type": m.get("client_type"),
        "created_at": m.get("created_at"),
        "approved_at": m.get("approved_at"),
        "approved_by": approved_by,
    }

    # ── Design ──
    design_dir = paths.DESIGNS_BASE / project_id
    design_files = []
    agents_summary = {"profiles_inherited": 0, "new_agents": 0, "agent_ids": []}
    pending_docs_count = 0
    if design_dir.exists():
        design_files = [p.name for p in sorted(design_dir.iterdir()) if p.is_file()]
        ag = parse_agents(design_dir)
        agents_summary = ag["summary"]
        agents_summary["agent_ids"] = [a["agent_id"] for a in ag.get("agents", [])]
        pd_file = design_dir / "pending_documents.yaml"
        if pd_file.exists():
            try:
                pd = _yaml.safe_load(pd_file.read_text(encoding="utf-8")) or {}
                pending_docs_count = len(pd.get("documents", pd.get("pending", [])))
            except Exception:
                pass

    # ── Workspace ──
    ws = paths.WS_BASE / project_id
    ws_files_visible = 0
    ws_py_files = 0
    ws_has_test_report = False
    ws_has_headless_log = False
    if ws.exists():
        for p in ws.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(ws))
            if any(bl in rel for bl in paths.FILTER_PARTS):
                continue
            ws_files_visible += 1
            if p.suffix == ".py":
                ws_py_files += 1
        ws_has_test_report = (ws / "test_report.json").exists()
        ws_has_headless_log = bool(list(ws.glob("logs/headless_*.log")))

    # ── Headless ──
    headless_block = None
    if ws.exists():
        hl = parse_headless_log(ws)
        if hl and not hl.get("parse_error"):
            headless_block = {
                "returncode": hl.get("returncode"),
                "duration_seconds": round((hl.get("duration_ms") or 0) / 1000, 1),
                "total_cost_usd": hl.get("total_cost_usd"),
                "num_turns": hl.get("num_turns"),
                "models_used": hl.get("models_used", []),
                "terminal_reason": hl.get("terminal_reason"),
            }

    # ── Tests ──
    tests_block = None
    test_report = ws / "test_report.json" if ws.exists() else None
    if test_report and test_report.exists():
        try:
            td = json.loads(test_report.read_text(encoding="utf-8"))
            s = td.get("summary", {})
            tests_block = {
                "passed": s.get("passed", 0),
                "failed": s.get("failed", 0),
                "returncode": s.get("returncode", -1),
            }
        except Exception:
            pass

    # ── RCs ──
    rc_dir = paths.RC_BASE / project_id
    rc_list = []
    rc_statuses: dict[str, int] = {}
    canonical_id = None
    if rc_dir.exists():
        for f in sorted(rc_dir.rglob("rc_manifest.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                rc_list.append(d)
                st = d.get("status", "unknown")
                rc_statuses[st] = rc_statuses.get(st, 0) + 1
                if d.get("is_canonical"):
                    canonical_id = d.get("rc_id")
            except Exception:
                continue

    # ── Deployment ──
    dep_exists = (paths.DEP_BASE / project_id).exists()
    dep_health_ok = False
    dep_api_port = None
    if dep_exists:
        try:
            from factory.core.port_registry import get_allocated_ports
            ports = get_allocated_ports(project_id)
            dep_api_port = ports.get("api") if ports else None
        except Exception:
            pass
        if dep_api_port:
            try:
                hr = httpx.get(f"http://host.docker.internal:{dep_api_port}/health", timeout=3)
                dep_health_ok = hr.status_code == 200
            except Exception:
                pass

    # ── Audit ──
    audit_count = 0
    last_event_at = None
    last_event_type = None
    if paths.AUDIT_FILE.exists():
        for raw in paths.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(raw)
                if e.get("project_id") == project_id:
                    audit_count += 1
                    last_event_at = e.get("timestamp")
                    last_event_type = e.get("event_type")
            except Exception:
                continue

    # ── ETag ──
    key_files = [
        mission_file,
        ws / "test_report.json" if ws.exists() else Path("/dev/null"),
        *([rc_dir / f for f in []] if not rc_dir.exists() else
          sorted(rc_dir.rglob("rc_manifest.json"))),
    ]
    etag = etag_of(key_files)

    return {
        "project_id": project_id,
        "mission": mission_block,
        "design": {
            "files_count": len(design_files),
            "files": design_files,
            "agents_summary": agents_summary,
            "pending_documents_count": pending_docs_count,
        },
        "workspace": {
            "files_visible": ws_files_visible,
            "py_files": ws_py_files,
            "has_test_report": ws_has_test_report,
            "has_headless_log": ws_has_headless_log,
        },
        "headless": headless_block,
        "tests": tests_block,
        "rcs": {
            "count": len(rc_list),
            "canonical": canonical_id,
            "statuses": rc_statuses,
        },
        "deployment": {
            "exists": dep_exists,
            "api_port": dep_api_port,
            "health_ok": dep_health_ok,
        },
        "audit": {
            "event_count_filtered": audit_count,
            "last_event_at": last_event_at,
            "last_event_type": last_event_type,
        },
        "etag": etag,
    }


# ── Readers de las rutas W3 (mismo shape de respuesta que el router) ─────────

def read_design(project_id: str) -> dict:
    """Lista archivos en factory/designs/{project_id}/. Read-only."""
    design_dir = safe_design(project_id)
    files = []
    for p in sorted(design_dir.iterdir()):
        if not p.is_file():
            continue
        entry: dict[str, Any] = {"name": p.name, "size": p.stat().st_size, "ext": p.suffix}
        if p.suffix in (".yaml", ".yml"):
            try:
                d = _yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                entry["keys"] = list(d.keys())[:10]
            except Exception:
                pass
        files.append(entry)
    return {"project_id": project_id, "files": files, "count": len(files)}


def read_agents(project_id: str) -> dict:
    """agent_design_proposal.yaml como lista estructurada. Read-only."""
    design_dir = safe_design(project_id)
    result = parse_agents(design_dir)
    result["project_id"] = project_id
    result["source_file"] = f"factory/designs/{project_id}/agent_design_proposal.yaml"
    return result


def read_headless(project_id: str) -> dict:
    """Parsea el log JSONL del CLI Claude del workspace. Read-only."""
    from factory.core.path_policy import resolve_workspace
    try:
        ws = resolve_workspace(project_id, paths.WS_BASE)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    parsed = parse_headless_log(ws)
    if parsed is None:
        return {"project_id": project_id, "found": False}
    return {"project_id": project_id, "found": True, "result": parsed}


def read_tests(project_id: str) -> dict:
    """Lee test_report.json del workspace. Read-only."""
    ws = paths.WS_BASE / project_id
    report_path = ws / "test_report.json"
    if not ws.exists():
        raise HTTPException(404, f"Workspace '{project_id}' no encontrado")
    if not report_path.exists():
        return {"project_id": project_id, "found": False}
    try:
        d = json.loads(report_path.read_text(encoding="utf-8"))
        s = d.get("summary", {})
        return {
            "project_id": project_id,
            "found": True,
            "passed": s.get("passed", 0),
            "failed": s.get("failed", 0),
            "returncode": s.get("returncode", -1),
            "note": d.get("note", ""),
            "output": (d.get("output") or "")[:4096],
        }
    except Exception as e:
        raise HTTPException(500, f"Error parseando test_report.json: {e}")


def read_rcs(project_id: str) -> dict:
    """Lista todos los RC manifests de un proyecto con detalle. Read-only."""
    rc_dir = paths.RC_BASE / project_id
    if not rc_dir.exists():
        return {"project_id": project_id, "rcs": [], "count": 0}
    rcs = []
    for f in sorted(rc_dir.rglob("rc_manifest.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            artifacts_path = f.parent / "artifacts"
            artifacts = []
            if artifacts_path.exists():
                for ap in sorted(artifacts_path.iterdir()):
                    if ap.is_file():
                        artifacts.append({"name": ap.name, "size": ap.stat().st_size, "ext": ap.suffix})
            rcs.append({
                "rc_id": d.get("rc_id"),
                "version": d.get("version"),
                "status": d.get("status"),
                "is_canonical": d.get("is_canonical"),
                "approved_by": d.get("approved_by"),
                "decided_at": d.get("decided_at"),
                "proposed_at": d.get("proposed_at"),
                "notes": d.get("notes", ""),
                "sha256sums": d.get("sha256sums", {}),
                "artifacts": artifacts,
            })
        except Exception:
            continue
    return {"project_id": project_id, "rcs": rcs, "count": len(rcs)}


def read_deployment(project_id: str) -> dict:
    """Estado del deployment Docker del proyecto (health en vivo). Read-only."""
    return {"project_id": project_id, **deployment_health(project_id)}


def read_audit(project_id: str, limit: int = 50) -> dict:
    """Eventos de auditoría filtrados por project_id (últimos N). Read-only."""
    if not paths.AUDIT_FILE.exists():
        return {"project_id": project_id, "events": [], "count": 0}
    events = []
    for raw in paths.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(raw)
            if e.get("project_id") == project_id:
                events.append({
                    "timestamp": e.get("timestamp"),
                    "event_type": e.get("event_type"),
                    "entry_hash": e.get("entry_hash"),
                    "data": e.get("data", {}),
                })
        except Exception:
            continue
    events_trimmed = events[-limit:]
    return {
        "project_id": project_id,
        "events": list(reversed(events_trimmed)),
        "count": len(events_trimmed),
        "total": len(events),
    }


# ── Lectores de archivos individuales (política path_policy) ─────────────────

def read_design_file(project_id: str, path: str) -> dict:
    """Archivo de designs/: solo .yaml/.yml/.md — bloquea traversal y secretos."""
    from factory.core.path_policy import resolve_design
    try:
        target = resolve_design(project_id, paths.DESIGNS_BASE, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > paths.MAX_FILE_BYTES:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {paths.MAX_FILE_BYTES})")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


def read_rc_artifact_file(project_id: str, rc_id: str, path: str) -> dict:
    """Artefacto de un RC: solo .json/.log/.txt/.md — sin escapar del rc_id."""
    from factory.core.path_policy import resolve_rc_artifact
    try:
        target = resolve_rc_artifact(project_id, rc_id, paths.RC_BASE, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > paths.MAX_FILE_BYTES:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {paths.MAX_FILE_BYTES})")
    return {
        "project_id": project_id,
        "rc_id": rc_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


def read_deployment_file(project_id: str, path: str) -> dict:
    """Archivo de deployments/: bloquea .env, data/, corpus, releases, secretos."""
    from factory.core.path_policy import resolve_deployment
    try:
        target = resolve_deployment(project_id, paths.DEP_BASE, path)
    except (ValueError, PermissionError) as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Archivo no encontrado: {path}")
    size = target.stat().st_size
    if size > paths.MAX_FILE_BYTES:
        raise HTTPException(400, f"Archivo demasiado grande: {size} bytes (max {paths.MAX_FILE_BYTES})")
    return {
        "project_id": project_id,
        "path": path,
        "size": size,
        "ext": target.suffix,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }
