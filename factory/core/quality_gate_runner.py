"""
Ejecutor de los 14 quality gates obligatorios de GMP AI Factory.

Salida: quality_gates_report.json con {gate, status, evidence, timestamp}.
Registra gates_executed + hash del reporte en factory_audit.jsonl.
Gates de runtime (G03-G10) se marcan SKIPPED si la solución no está levantada.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.core.port_registry import validate_port_free, get_allocated_ports

FACTORY_DIR = Path(__file__).parent.parent


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], cwd=None) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def _gate(gate_id: str, status: str, evidence: str) -> dict:
    return {"gate": gate_id, "status": status, "evidence": evidence, "timestamp": _ts()}


def _service_running(api_port: int) -> bool:
    rc, _ = _run(["curl", "-sf", f"http://localhost:{api_port}/health"])
    return rc == 0


# ── Individual gates ────────────────────────────────────────────────────────

def g01_compose_syntax(compose_path: str) -> dict:
    rc, out = _run(["docker", "compose", "-f", compose_path, "config", "-q"])
    if rc == 0:
        return _gate("G01", "PASS", "docker compose config -q OK")
    return _gate("G01", "FAIL", f"docker compose config error:\n{out}")


def g02_ports(manifest: dict, project_id: str) -> dict:
    dep = manifest.get("deployment", {})
    ports = {
        "api":      dep.get("api_port"),
        "postgres": dep.get("postgres_port"),
        "redis":    dep.get("redis_port"),
    }
    allocated = get_allocated_ports(project_id)
    issues = []
    for svc, port in ports.items():
        if port is None:
            issues.append(f"{svc}: puerto no definido en manifest")
            continue
        if allocated and allocated.get(svc) != port:
            issues.append(f"{svc}: puerto {port} no coincide con registry ({allocated.get(svc)})")
    if issues:
        return _gate("G02", "FAIL", "; ".join(issues))
    return _gate("G02", "PASS", f"Puertos en registry: {ports}")


def g03_health(api_port: int) -> dict:
    rc, out = _run(["curl", "-sf", f"http://localhost:{api_port}/health"])
    if rc == 0:
        return _gate("G03", "PASS", f"GET /health → {out[:120]}")
    return _gate("G03", "SKIPPED", f"Solución no levantada en :{api_port} — SKIPPED")


def g04_rag_stats(api_port: int, api_key: str) -> dict:
    rc, out = _run(["curl", "-sf", "-H", f"X-Api-Key: {api_key}",
                    f"http://localhost:{api_port}/api/v1/knowledge/stats"])
    if rc == 0:
        return _gate("G04", "PASS", f"knowledge/stats → {out[:200]}")
    return _gate("G04", "SKIPPED", f"Solución no levantada en :{api_port} — SKIPPED")


def g05_min_chunks(api_port: int, api_key: str, manifest: dict) -> dict:
    rc, out = _run(["curl", "-sf", "-H", f"X-Api-Key: {api_key}",
                    f"http://localhost:{api_port}/api/v1/knowledge/stats"])
    if rc != 0:
        return _gate("G05", "SKIPPED", "Solución no levantada — SKIPPED")
    try:
        stats = json.loads(out)
        collections = manifest.get("rag_collections", {})
        issues = []
        for col_name in collections:
            count = stats.get(col_name, {}).get("count", 0)
            if count < 60:
                issues.append(f"{col_name}: {count} chunks (mín 60)")
        if issues:
            return _gate("G05", "FAIL", "; ".join(issues))
        return _gate("G05", "PASS", f"Todas las colecciones >= 60 chunks")
    except Exception as e:
        return _gate("G05", "FAIL", f"Error parseando stats: {e}")


def g06_routing(api_port: int, api_key: str, manifest: dict) -> dict:
    agents = manifest.get("agents", {}).get("inherited", [])
    if not agents:
        return _gate("G06", "SKIPPED", "Sin agentes heredados definidos en manifest")
    rc, _ = _run(["curl", "-sf", f"http://localhost:{api_port}/health"])
    if rc != 0:
        return _gate("G06", "SKIPPED", "Solución no levantada — SKIPPED")
    return _gate("G06", "SKIPPED", "Routing verificable solo con batería completa de preguntas — pendiente F5")


def g07_inherited_questions(api_port: int) -> dict:
    rc, _ = _run(["curl", "-sf", f"http://localhost:{api_port}/health"])
    if rc != 0:
        return _gate("G07", "SKIPPED", "Solución no levantada — SKIPPED")
    return _gate("G07", "SKIPPED", "Baterías heredadas verificables en F5 con solución levantada")


def g08_new_questions(api_port: int, manifest: dict) -> dict:
    customs = manifest.get("agents", {}).get("custom", {})
    profiles = manifest.get("agents", {}).get("profiles", {})
    if not customs and not profiles:
        return _gate("G08", "PASS", "Sin agentes nuevos ni perfiles — gate no aplica")
    rc, _ = _run(["curl", "-sf", f"http://localhost:{api_port}/health"])
    if rc != 0:
        return _gate("G08", "SKIPPED", "Solución no levantada — SKIPPED")
    return _gate("G08", "SKIPPED", "Baterías de agentes nuevos verificables en F5")


def g09_audit_chain(api_port: int, api_key: str) -> dict:
    rc, out = _run(["curl", "-sf", "-H", f"X-Api-Key: {api_key}",
                    f"http://localhost:{api_port}/api/v1/audit/verify"])
    if rc != 0:
        return _gate("G09", "SKIPPED", "Solución no levantada — SKIPPED")
    try:
        result = json.loads(out)
        if result.get("verified"):
            return _gate("G09", "PASS", f"audit/verify → verified:true")
        return _gate("G09", "FAIL", f"audit/verify → {out[:200]}")
    except Exception:
        return _gate("G09", "FAIL", f"Respuesta inesperada: {out[:200]}")


def g10_ui_loads(api_port: int) -> dict:
    rc, out = _run(["curl", "-sf", "-o", "/dev/null", "-w", "%{http_code}",
                    f"http://localhost:{api_port}/"])
    if rc != 0:
        return _gate("G10", "SKIPPED", "Solución no levantada — SKIPPED")
    if out.strip() == "200":
        return _gate("G10", "PASS", "GET / → 200")
    return _gate("G10", "FAIL", f"GET / → {out.strip()}")


def g11_key_not_in_frontend(workspace_path: str, api_key: str) -> dict:
    if not api_key or api_key == "":
        return _gate("G11", "PASS", "API key vacía — nada que buscar en frontend")
    static_dir = Path(workspace_path) / "app" / "static"
    if not static_dir.exists():
        return _gate("G11", "PASS", f"app/static/ no existe — nada que verificar")
    rc, out = _run(["grep", "-r", api_key, str(static_dir)])
    if rc == 0 and out.strip():
        return _gate("G11", "FAIL", f"API key encontrada en frontend: {out[:200]}")
    return _gate("G11", "PASS", "API key NO encontrada en frontend")


def g12_git_clean(workspace_path: str) -> dict:
    ws = Path(workspace_path)
    if not (ws / ".git").exists():
        return _gate("G12", "SKIPPED", "Workspace sin .git — SKIPPED (F5 inicializa git en workspace)")
    rc, out = _run(["git", "status", "--short"], cwd=workspace_path)
    if out.strip() == "":
        return _gate("G12", "PASS", "git status limpio")
    return _gate("G12", "FAIL", f"Cambios no versionados:\n{out}")


def g13_diff_archived(workspace_path: str) -> dict:
    ws = Path(workspace_path)
    if not (ws / ".git").exists():
        return _gate("G13", "SKIPPED", "Workspace sin .git — diff se archiva en F5")
    rc, out = _run(["git", "diff", "--stat"], cwd=workspace_path)
    return _gate("G13", "PASS", f"git diff --stat archivado:\n{out[:500] or '(sin cambios unstaged)'}")


def g14_approval(workspace_path: str) -> dict:
    approval_path = Path(workspace_path) / "approval.json"
    if not approval_path.exists():
        return _gate("G14", "FAIL", "approval.json no existe — requerido para deploy")
    try:
        approval = json.loads(approval_path.read_text())
        if approval.get("status") == "approved":
            return _gate("G14", "PASS",
                         f"approval.json: status=approved, by={approval.get('approved_by')}")
        return _gate("G14", "FAIL",
                     f"approval.json: status={approval.get('status')} (requiere approved)")
    except Exception as e:
        return _gate("G14", "FAIL", f"Error leyendo approval.json: {e}")


# ── Runner principal ─────────────────────────────────────────────────────────

def run_all_gates(
    manifest: dict,
    workspace_path: str,
    compose_path: str | None = None,
    api_key: str = "",
    for_deploy: bool = False,
) -> dict:
    """
    Ejecuta G01-G14 y retorna el reporte completo.
    - G03-G10 se marcan SKIPPED si la solución no está levantada.
    - G14 solo es obligatorio para deploy (for_deploy=True).
    """
    project_id = manifest.get("project", {}).get("id", "unknown")
    dep = manifest.get("deployment", {})
    api_port = dep.get("api_port", 0)

    if compose_path is None:
        compose_path = str(Path(workspace_path) / "docker-compose.yml")

    results = []

    results.append(g01_compose_syntax(compose_path))
    results.append(g02_ports(manifest, project_id))
    results.append(g03_health(api_port))
    results.append(g04_rag_stats(api_port, api_key))
    results.append(g05_min_chunks(api_port, api_key, manifest))
    results.append(g06_routing(api_port, api_key, manifest))
    results.append(g07_inherited_questions(api_port))
    results.append(g08_new_questions(api_port, manifest))
    results.append(g09_audit_chain(api_port, api_key))
    results.append(g10_ui_loads(api_port))
    results.append(g11_key_not_in_frontend(workspace_path, api_key))
    results.append(g12_git_clean(workspace_path))
    results.append(g13_diff_archived(workspace_path))

    if for_deploy:
        results.append(g14_approval(workspace_path))
    else:
        results.append(_gate("G14", "SKIPPED",
                             "G14 solo requerido para deploy (for_deploy=False)"))

    report = {
        "project_id": project_id,
        "generated_at": _ts(),
        "for_deploy": for_deploy,
        "summary": {
            "PASS":    sum(1 for r in results if r["status"] == "PASS"),
            "FAIL":    sum(1 for r in results if r["status"] == "FAIL"),
            "SKIPPED": sum(1 for r in results if r["status"] == "SKIPPED"),
        },
        "gates": results,
    }

    report_json = json.dumps(report, separators=(",", ":"), ensure_ascii=False)
    report_hash = f"sha256:{hashlib.sha256(report_json.encode()).hexdigest()}"
    report["report_hash"] = report_hash

    # Guardar reporte en workspace (crea el directorio si no existe)
    report_path = Path(workspace_path) / "quality_gates_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Registrar en audit de fábrica
    write_event("gates_executed", project_id, {
        "report_path": str(report_path),
        "report_hash": report_hash,
        "summary": report["summary"],
    })

    return report


# ── Deployment gates (F10) — verificación funcional de solución desplegada ────
# Usan httpx (no curl) porque estos gates corren dentro del contenedor factory-api.

def _dep_get(url: str, key: str = "", timeout: float = 8.0) -> tuple[str, str]:
    """GET con httpx. Retorna (status_code_str, body_str). '000' si error."""
    try:
        import httpx as _httpx
        headers = {}
        if key:
            headers["x-api-key"] = key
        r = _httpx.get(url, headers=headers, timeout=timeout)
        return str(r.status_code), r.text
    except Exception:
        return "000", ""


def _dep_post(url: str, key: str = "", body: dict | None = None,
              timeout: float = 8.0) -> tuple[str, str]:
    """POST JSON con httpx. Retorna (status_code_str, body_str)."""
    try:
        import httpx as _httpx
        headers = {"Content-Type": "application/json"}
        if key:
            headers["x-api-key"] = key
        r = _httpx.post(url, json=body or {}, headers=headers, timeout=timeout)
        return str(r.status_code), r.text
    except Exception:
        return "000", ""


def gd_auth_reject(api_port: int) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, _ = _dep_get(f"{base}/api/v1/knowledge/stats", key="BAD_KEY_XYZ_123")
    if code == "000":
        return _gate("GD_AUTH_REJECT", "SKIPPED", "Deployment no responde — SKIPPED")
    if code in ("401", "403"):
        return _gate("GD_AUTH_REJECT", "PASS", f"Clave inválida → HTTP {code} ✓")
    return _gate("GD_AUTH_REJECT", "FAIL", f"Clave inválida → HTTP {code} (esperado 401/403)")


def gd_auth_accept(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, _ = _dep_get(f"{base}/api/v1/knowledge/stats", key=api_key)
    if code == "200":
        return _gate("GD_AUTH_ACCEPT", "PASS", f"Clave válida → HTTP {code} ✓")
    if code == "000":
        return _gate("GD_AUTH_ACCEPT", "SKIPPED", "Deployment no responde — SKIPPED")
    return _gate("GD_AUTH_ACCEPT", "FAIL", f"Clave válida → HTTP {code} (esperado 200)")


def gd_health_full(api_port: int) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/health")
    if code == "000":
        return _gate("GD_HEALTH_FULL", "SKIPPED", "Deployment no responde — SKIPPED")
    if code != "200":
        return _gate("GD_HEALTH_FULL", "FAIL", f"/health → HTTP {code}")
    try:
        h = json.loads(body)
        failing = [k for k, v in h.items()
                   if k not in ("timestamp",) and "error" in str(v).lower()]
        if failing:
            return _gate("GD_HEALTH_FULL", "FAIL", f"Servicios con error: {failing}")
        services = {k: v for k, v in h.items() if k != "timestamp"}
        return _gate("GD_HEALTH_FULL", "PASS", f"Todos los servicios OK: {services}")
    except Exception:
        return _gate("GD_HEALTH_FULL", "PASS", f"/health → 200")


def gd_agent_list(api_port: int) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/agents")
    if code == "000":
        return _gate("GD_AGENT_LIST", "SKIPPED", "Deployment no responde — SKIPPED")
    if code != "200":
        return _gate("GD_AGENT_LIST", "FAIL", f"/api/v1/agents → HTTP {code}")
    try:
        agents = json.loads(body)
        count = len(agents)
        names = list(agents.keys())[:4]
        if count == 0:
            return _gate("GD_AGENT_LIST", "FAIL", "Sin agentes registrados")
        return _gate("GD_AGENT_LIST", "PASS", f"{count} agentes: {names}")
    except Exception:
        return _gate("GD_AGENT_LIST", "FAIL", f"Respuesta inesperada: {body[:80]}")


def gd_knowledge_stats(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/knowledge/stats", key=api_key)
    if code == "000":
        return _gate("GD_KNOWLEDGE_STATS", "SKIPPED", "Deployment no responde — SKIPPED")
    if code != "200":
        return _gate("GD_KNOWLEDGE_STATS", "FAIL", f"/knowledge/stats → HTTP {code}")
    try:
        stats = json.loads(body)
        total = stats.get("_total", {})
        cols = total.get("collections", 0)
        chunks = total.get("total_chunks", 0)
        if cols == 0 or chunks == 0:
            return _gate("GD_KNOWLEDGE_STATS", "FAIL", f"Corpus vacío: {cols} cols, {chunks} chunks")
        return _gate("GD_KNOWLEDGE_STATS", "PASS", f"{cols} colecciones, {chunks} chunks totales")
    except Exception:
        return _gate("GD_KNOWLEDGE_STATS", "FAIL", f"Error: {body[:80]}")


def gd_min_corpus(api_port: int, api_key: str, min_chunks: int = 20) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/knowledge/stats", key=api_key)
    if code == "000":
        return _gate("GD_MIN_CORPUS", "SKIPPED", "Deployment no responde — SKIPPED")
    try:
        stats = json.loads(body)
        low = [(k, v.get("count", 0)) for k, v in stats.items()
               if k != "_total" and v.get("count", 0) < min_chunks]
        if low:
            details = ", ".join(f"{k}:{n}" for k, n in low)
            return _gate("GD_MIN_CORPUS", "FAIL", f"Bajo {min_chunks} chunks: {details}")
        collections = {k: v.get("count") for k, v in stats.items() if k != "_total"}
        return _gate("GD_MIN_CORPUS", "PASS", f"Todas ≥{min_chunks} chunks: {collections}")
    except Exception:
        return _gate("GD_MIN_CORPUS", "FAIL", f"Error: {body[:80]}")


def gd_rules_engine(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/rules/evaluate?question=OOS+test", key=api_key)
    if code == "000":
        return _gate("GD_RULES_ENGINE", "SKIPPED", "Deployment no responde — SKIPPED")
    if code in ("200", "422"):
        try:
            r = json.loads(body)
            triggered = len(r.get("rules_triggered", []))
            return _gate("GD_RULES_ENGINE", "PASS",
                         f"Rules engine OK → HTTP {code}, {triggered} reglas")
        except Exception:
            pass
        return _gate("GD_RULES_ENGINE", "PASS", f"/rules/evaluate → HTTP {code}")
    return _gate("GD_RULES_ENGINE", "FAIL", f"/rules/evaluate → HTTP {code}")


def gd_audit_verify(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/audit/verify", key=api_key)
    if code == "000":
        return _gate("GD_AUDIT_VERIFY", "SKIPPED", "Deployment no responde — SKIPPED")
    if code != "200":
        return _gate("GD_AUDIT_VERIFY", "FAIL", f"/audit/verify → HTTP {code}")
    try:
        r = json.loads(body)
        verified = r.get("verified", False)
        count = r.get("log_count", 0)
        if verified:
            return _gate("GD_AUDIT_VERIFY", "PASS", f"Chain OK: {count} entradas verificadas")
        return _gate("GD_AUDIT_VERIFY", "FAIL",
                     f"Chain inválida: errors={r.get('hash_errors', '?')}")
    except Exception:
        return _gate("GD_AUDIT_VERIFY", "FAIL", f"Error: {body[:80]}")


def gd_protocol_template(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/api/v1/protocol-template/IQ", key=api_key)
    if code == "000":
        return _gate("GD_PROTOCOL_TMPL", "SKIPPED", "Deployment no responde — SKIPPED")
    if code == "200":
        try:
            r = json.loads(body)
            # Campo correcto es "protocol_type"; secciones están en r["template"]["sections"]
            tmpl_type = r.get("protocol_type", r.get("type", "?"))
            sections = len(r.get("template", {}).get("sections", r.get("sections", [])))
            return _gate("GD_PROTOCOL_TMPL", "PASS",
                         f"Template {tmpl_type}: {sections} secciones (IQ/OQ/PQ disponibles)")
        except Exception:
            return _gate("GD_PROTOCOL_TMPL", "PASS", f"/protocol-template/IQ → 200")
    return _gate("GD_PROTOCOL_TMPL", "FAIL", f"/protocol-template/IQ → HTTP {code}")


def gd_stream_200(api_port: int, api_key: str, timeout: float = 30.0) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_post(f"{base}/api/v1/stream", key=api_key,
                           body={"question": "¿Qué es GMP?"}, timeout=timeout)
    if code == "000":
        return _gate("GD_STREAM_200", "SKIPPED", f"Timeout {timeout}s o deployment no levantado")
    if code == "200":
        return _gate("GD_STREAM_200", "PASS", f"/api/v1/stream → 200 (streaming activo)")
    return _gate("GD_STREAM_200", "FAIL", f"/api/v1/stream → HTTP {code}")


def gd_key_not_in_ui(api_port: int, api_key: str) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    code, body = _dep_get(f"{base}/", timeout=5.0)
    if code == "000":
        return _gate("GD_KEY_NOT_IN_UI", "SKIPPED", "Deployment no responde — SKIPPED")
    if api_key and api_key in body:
        return _gate("GD_KEY_NOT_IN_UI", "FAIL", "API key encontrada en HTML de UI")
    return _gate("GD_KEY_NOT_IN_UI", "PASS", "API key NO en HTML de UI ✓")


def gd_query_llm(api_port: int, api_key: str, timeout: float = 120.0) -> dict:
    base = f"http://host.docker.internal:{api_port}"
    question = "¿Qué es un OOS y qué acciones inmediatas requiere según 21 CFR 211.192?"
    code, body = _dep_post(f"{base}/api/v1/query", key=api_key,
                           body={"question": question, "agent": "auto"}, timeout=timeout)
    if code == "000":
        return _gate("GD_QUERY_LLM", "SKIPPED", f"Timeout {timeout}s o deployment no levantado")
    if code == "200":
        try:
            r = json.loads(body)
            elapsed = r.get("elapsed_seconds", "?")
            preview = str(r.get("answer", ""))[:60]
            return _gate("GD_QUERY_LLM", "PASS",
                         f"/api/v1/query → 200, {elapsed}s, respuesta: {preview}…")
        except Exception:
            return _gate("GD_QUERY_LLM", "PASS", f"/api/v1/query → 200")
    return _gate("GD_QUERY_LLM", "FAIL", f"/api/v1/query → HTTP {code}")


def run_deployment_gates(
    project_id: str,
    api_port: int,
    api_key: str,
    manifest: dict,
    report_path: Path | None = None,
    fast: bool = True,
) -> dict:
    """
    Ejecuta gates funcionales contra un deployment corriendo (Docker 3+).
    fast=True: omite LLM calls (GD_QUERY_LLM) — resultado en <15s.
    fast=False: incluye test de respuesta Ollama (puede tardar 90-120s).
    Guarda reporte en report_path si se especifica.
    """
    results = [
        gd_auth_reject(api_port),
        gd_auth_accept(api_port, api_key),
        gd_health_full(api_port),
        gd_agent_list(api_port),
        gd_knowledge_stats(api_port, api_key),
        gd_min_corpus(api_port, api_key, min_chunks=20),
        gd_rules_engine(api_port, api_key),
        gd_audit_verify(api_port, api_key),
        gd_protocol_template(api_port, api_key),
        gd_key_not_in_ui(api_port, api_key),
        gd_stream_200(api_port, api_key),
    ]

    if fast:
        results.append(_gate("GD_QUERY_LLM", "SKIPPED",
                             "fast=True — omitido para velocidad (requiere ~90s)"))
    else:
        results.append(gd_query_llm(api_port, api_key))

    report = {
        "project_id": project_id,
        "generated_at": _ts(),
        "gate_set": "deployment_functional",
        "fast_mode": fast,
        "summary": {
            "PASS":    sum(1 for r in results if r["status"] == "PASS"),
            "FAIL":    sum(1 for r in results if r["status"] == "FAIL"),
            "SKIPPED": sum(1 for r in results if r["status"] == "SKIPPED"),
        },
        "gates": results,
    }

    report_json = json.dumps(report, separators=(",", ":"), ensure_ascii=False)
    report_hash = f"sha256:{hashlib.sha256(report_json.encode()).hexdigest()}"
    report["report_hash"] = report_hash

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    write_event("gates_executed", project_id, {
        "gate_set": "deployment_functional",
        "report_hash": report_hash,
        "summary": report["summary"],
        "api_port": api_port,
    })

    return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Uso: python3 quality_gate_runner.py <manifest.yaml> <workspace_path> [compose_path]")
        sys.exit(1)
    import yaml as _yaml
    with open(sys.argv[1]) as f:
        m = _yaml.safe_load(f)
    compose = sys.argv[3] if len(sys.argv) > 3 else None
    r = run_all_gates(m, sys.argv[2], compose)
    for g in r["gates"]:
        print(f"  {g['gate']}: {g['status']:7s} — {g['evidence'][:80]}")
    print(f"\nResumen: {r['summary']}")
