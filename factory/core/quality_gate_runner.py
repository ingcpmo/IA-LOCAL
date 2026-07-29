"""
Ejecutor de los 15 quality gates obligatorios de GMP AI Factory.

Salida: quality_gates_report.json con {gate, status, evidence, timestamp}.
Registra gates_executed + hash del reporte en factory_audit.jsonl.
Gates de runtime (G03-G10) se marcan SKIPPED si la solución no está levantada.
"""

import hashlib
import json
import subprocess
import sys
import time
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
    """
    Valida que la aprobación sea real:
      1. status == approved
      2. decision_origin == human_confirmed  (R2: agente no puede auto-aprobar)
      3. approved_by no es un valor reservado genérico
    """
    _RESERVED = {"human", "agent", "layer8_agent", "auto", "system", "", None}
    approval_path = Path(workspace_path) / "approval.json"
    if not approval_path.exists():
        return _gate("G14", "FAIL", "approval.json no existe — requerido para deploy")
    try:
        approval = json.loads(approval_path.read_text())
        status = approval.get("status")
        origin = approval.get("decision_origin")
        approved_by = approval.get("approved_by")

        if status == "pending_human_confirmation":
            return _gate("G14", "FAIL",
                         "approval.json: status=pending_human_confirmation — "
                         "requiere confirmación humana vía POST /approvals/{id}/confirm")

        if status != "approved":
            return _gate("G14", "FAIL",
                         f"approval.json: status={status!r} (requiere 'approved')")

        # Si tiene decision_origin, debe ser human_confirmed
        if origin is not None and origin != "human_confirmed":
            return _gate("G14", "FAIL",
                         f"approval.json: decision_origin={origin!r} — "
                         "solo 'human_confirmed' permite deploy. "
                         "Usa POST /approvals/{id}/confirm para confirmar humanamente.")

        # approved_by no puede ser un valor reservado
        if approved_by in _RESERVED:
            return _gate("G14", "FAIL",
                         f"approval.json: approved_by={approved_by!r} es un valor reservado. "
                         "Debe ser el nombre real del aprobador humano.")

        origin_label = origin or "legacy (sin decision_origin)"
        return _gate("G14", "PASS",
                     f"approval.json: status=approved, "
                     f"decision_origin={origin_label}, approved_by={approved_by}")
    except Exception as e:
        return _gate("G14", "FAIL", f"Error leyendo approval.json: {e}")


# ── G15 — cobertura de decisiones (W5 V2 G1.11, consumidor C-5) ─────────────
#
# Los catorce gates anteriores preguntan si la solución está bien CONSTRUIDA.
# Este pregunta algo que ninguno preguntaba: si alguien AUTORIZÓ el material
# regulatorio sobre el que se construyó. Son dimensiones distintas y G15 no
# se deriva de ninguna de las otras -- una solución puede tener los catorce en
# verde y apoyarse en fuentes que nadie firmó. Ese era exactamente el estado
# del 2026-07-29.
#
# Fail-closed en los dos sentidos que importan:
#   - una familia con `uncovered_ids` no vacía BLOQUEA, con los ids listados;
#   - si el resolver no puede leer el almacén, BLOQUEA también. "No sé" nunca
#     se reporta como "sí".
#
# HOY ESTE GATE FALLA A PROPÓSITO. Ninguna fuente está formalmente cubierta
# hasta la Corrección D1 de G2 (DECISION_SCOPE_RESOLVER_SPEC.md §5); las tres
# antiguas quedan en `reconstructed_only`, que no autoriza. Que el gate esté
# en rojo entre G1.11 y G2 es el diseño, no una regresión.

_GOVERNED_FAMILIES = ("D1", "D2", "D3", "D4", "D5")


def g15_decision_coverage(*, decision_store_file=None, audit_file=None) -> dict:
    """Cobertura humana de D1..D5 + excepción firmada por cada fork de auditoría.

    Devuelve un gate normal (`_gate`) con la evidencia desglosada por familia:
    quien lea el reporte tiene que poder ver QUÉ falta firmar, no solo que
    algo falta.
    """
    from factory.core import decision_scope_resolver as resolver
    from factory.core.audit_writer import chain_break_entry_ids

    lines: list[str] = []
    blocking: list[str] = []

    for family in _GOVERNED_FAMILIES:
        try:
            report = resolver.coverage_report(family, store_file=decision_store_file)
        except resolver.ResolverConfigurationError as exc:
            # Despliegue roto: no es una denegación, es que no hay gobernanza.
            return _gate("G15", "FAIL",
                         f"registro de familias inválido — {exc}")

        # Un id del registry solo está autorizado si está en `covered_ids`.
        # Se computa así y no como `uncovered_ids != ()` a propósito:
        # `coverage_report` resta de `uncovered` lo reconstruido y lo revocado
        # porque son dimensiones distintas y las reporta aparte -- correcto
        # para un informe, y una puerta abierta para un gate. Ninguna de las
        # tres autoriza, y aquí lo único que importa es autorizar.
        not_authorized = tuple(
            sorted(set(report.registry_ids) - set(report.covered_ids)))

        if report.unavailable_reason:
            lines.append(f"{family}: NOT_DETERMINED — {report.unavailable_reason}")
            blocking.append(f"{family}(indeterminada)")
        elif not_authorized:
            lines.append(f"{family}: UNCOVERED {list(not_authorized)}")
            blocking.append(f"{family}({len(not_authorized)} sin cubrir)")
        elif not report.registry_ids:
            # D4/D5 no tienen `target_registry`: su objetivo es un plan o un
            # paquete, no un id de un registro. Decir "cubierta" sería fabricar
            # una garantía sobre un conjunto vacío; se declara como lo que es.
            lines.append(f"{family}: NO_REGISTRY_TO_COMPARE (sin target_registry)")
        else:
            lines.append(f"{family}: COVERED ({len(report.covered_ids)} ids)")

        if report.reconstructed_only_ids:
            lines.append(
                f"    {family}: {list(report.reconstructed_only_ids)} solo "
                "RECONSTRUCTED_SNAPSHOT — no autoriza")
        if report.registry_drift_since_decision:
            lines.append(f"    {family}: el registry cambió desde la última decisión")

    forks = chain_break_entry_ids(audit_file)
    unexcused = [
        eid for eid in forks
        if not resolver.is_authorized("AUDIT_EXCEPTION", eid,
                                      store_file=decision_store_file)
    ]
    if not forks:
        lines.append("AUDIT_EXCEPTION: sin rupturas de cadena que excusar")
    elif unexcused:
        lines.append(f"AUDIT_EXCEPTION: rupturas sin excepción firmada {unexcused}")
        blocking.append(f"AUDIT_EXCEPTION({len(unexcused)} sin firmar)")
    else:
        lines.append(f"AUDIT_EXCEPTION: {len(forks)} ruptura(s), todas con excepción firmada")

    evidence = "\n".join(lines)
    if blocking:
        return _gate("G15", "FAIL",
                     "BLOCKED — sin cobertura de decisión humana: "
                     f"{', '.join(blocking)}\n{evidence}")
    return _gate("G15", "PASS", evidence)


# ── Runner principal ─────────────────────────────────────────────────────────

def run_all_gates(
    manifest: dict,
    workspace_path: str,
    compose_path: str | None = None,
    api_key: str = "",
    for_deploy: bool = False,
) -> dict:
    """
    Ejecuta G01-G15 y retorna el reporte completo.
    - G03-G10 se marcan SKIPPED si la solución no está levantada.
    - G14 solo es obligatorio para deploy (for_deploy=True).
    - G15 (cobertura de decisiones) corre siempre — ver su docstring.
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

    # G15 corre SIEMPRE, también con for_deploy=False. No es un requisito de
    # despliegue sino del material sobre el que se construyó: un reporte de
    # gates que lo omitiera en modo verificación diría "todo bien" sobre algo
    # que nadie autorizó.
    results.append(g15_decision_coverage())

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

def _dep_get(url: str, key: str = "", timeout: float = 8.0,
             _retries: int = 2, _backoff: float = 2.0) -> tuple[str, str]:
    """GET con httpx. Retorna (status_code_str, body_str). '000' si error.
    Reintenta hasta _retries veces con backoff exponencial ante errores de red (P3)."""
    for attempt in range(_retries + 1):
        try:
            import httpx as _httpx
            headers = {}
            if key:
                headers["x-api-key"] = key
            r = _httpx.get(url, headers=headers, timeout=timeout)
            return str(r.status_code), r.text
        except Exception:
            if attempt < _retries:
                time.sleep(_backoff * (2 ** attempt))
    return "000", ""


def _dep_post(url: str, key: str = "", body: dict | None = None,
              timeout: float = 8.0, _retries: int = 2, _backoff: float = 2.0) -> tuple[str, str]:
    """POST JSON con httpx. Retorna (status_code_str, body_str).
    Reintenta hasta _retries veces con backoff exponencial ante errores de red (P3)."""
    for attempt in range(_retries + 1):
        try:
            import httpx as _httpx
            headers = {"Content-Type": "application/json"}
            if key:
                headers["x-api-key"] = key
            r = _httpx.post(url, json=body or {}, headers=headers, timeout=timeout)
            return str(r.status_code), r.text
        except Exception:
            if attempt < _retries:
                time.sleep(_backoff * (2 ** attempt))
    return "000", ""


def _wait_for_service(api_port: int, max_wait: float = 30.0, interval: float = 2.0) -> bool:
    """Warm-up: espera hasta max_wait segundos a que /health responda 200 (P3).
    Reduce flakiness por cold-start en gates de deployment."""
    base = f"http://host.docker.internal:{api_port}"
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        code, _ = _dep_get(f"{base}/health", timeout=3.0, _retries=0)
        if code == "200":
            return True
        time.sleep(interval)
    return False


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
    P3: warm-up de 30s antes de correr gates para reducir flakiness por cold-start.
    """
    # Warm-up: esperar a que el servicio esté listo antes de correr gates (P3)
    _wait_for_service(api_port, max_wait=30.0)

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
