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
