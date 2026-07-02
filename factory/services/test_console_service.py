"""
W5 — Servicio de la consola de pruebas funcionales por agente (W4),
extraído de routes/layer9.py sin cambio de comportamiento.

Separación estricta reader/executor (regla U5):
  read_catalog / read_results  → READER, nunca audita
  run_test     / run_suite     → EXECUTOR, audita exactamente 1 evento
    (run_suite audita 1 evento de RESUMEN, aunque corra N tests)

El payload y el endpoint destino SIEMPRE vienen del catálogo curado
(factory/test_catalogs/{project_id}.yaml); el body del request del usuario
solo trae test_id/agent_id + run_by — así se impide inyectar payloads
arbitrarios. El host:port destino SIEMPRE se resuelve server-side desde el
registry de puertos de la misión (get_allocated_ports), nunca desde
'deployment_base' del catálogo ni de ningún campo del request — así se
impide SSRF hacia una URL arbitraria.

Los tests redirigen rutas con monkeypatch sobre factory.services.paths y
el cliente HTTP con monkeypatch sobre este módulo (httpx).
"""

import json
import time
from typing import Any

import httpx
import yaml as _yaml
from fastapi import HTTPException

from factory.services import paths

RESERVED_RUN_BY = {"human", "agent", "system", "admin", "user", "factory"}
MISSING = object()


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def validate_run_by(run_by: str) -> str:
    name = (run_by or "").strip()
    if not name:
        raise HTTPException(422, "run_by es obligatorio: indica el nombre real del operador.")
    if name.lower() in RESERVED_RUN_BY:
        raise HTTPException(
            422, f"run_by='{run_by}' es un nombre genérico reservado. Usa el nombre real del operador."
        )
    return name


def get_deployment_api_key(project_id: str) -> str | None:
    env_file = paths.DEP_BASE / project_id / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("GMP_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_test_catalog(project_id: str) -> dict | None:
    catalog_file = paths.TEST_CATALOGS_DIR / f"{project_id}.yaml"
    if not catalog_file.exists():
        return None
    return _yaml.safe_load(catalog_file.read_text(encoding="utf-8")) or {}


def find_test_in_catalog(catalog: dict, test_id: str) -> tuple[str, dict] | None:
    for agent in catalog.get("agents", []):
        for test in agent.get("tests", []):
            if test.get("test_id") == test_id:
                return agent.get("agent_id"), test
    return None


def find_agent_tests(catalog: dict, agent_id: str) -> list[dict] | None:
    for agent in catalog.get("agents", []):
        if agent.get("agent_id") == agent_id:
            return agent.get("tests", [])
    return None


def require_live_deployment(project_id: str) -> tuple[int, str]:
    """Resuelve puerto+api_key server-side y exige health OK. 409 si no está vivo."""
    from factory.core.port_registry import get_allocated_ports
    ports = get_allocated_ports(project_id)
    port = ports.get("api") if ports else None
    if not port:
        raise HTTPException(404, f"Puerto no asignado para la misión '{project_id}'")
    try:
        r = httpx.get(f"http://host.docker.internal:{port}/health", timeout=4.0)
        alive = r.status_code == 200
    except Exception:
        alive = False
    if not alive:
        raise HTTPException(409, f"Deployment de '{project_id}' no está activo (health check falló)")
    api_key = get_deployment_api_key(project_id)
    if not api_key:
        raise HTTPException(500, "No se pudo leer la API key del deployment")
    return port, api_key


def eval_json_path(body: Any, json_path: str):
    """Acceso simple '$.a.b.c' sobre dicts anidados (sin arrays/wildcards:
    los catálogos W4 solo evalúan campos planos de la respuesta)."""
    path = json_path.strip()
    if path == "$":
        return body
    if path.startswith("$."):
        path = path[2:]
    current = body
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return MISSING
    return current


def execute_catalog_test(port: int, api_key: str, test_entry: dict) -> dict:
    """Ejecuta UN caso del catálogo. payload/endpoint vienen solo de test_entry."""
    test_id = test_entry["test_id"]
    endpoint = test_entry["endpoint"]
    method, path = endpoint.split(" ", 1)
    payload = test_entry.get("payload")
    expect = test_entry.get("expect", {})
    url = f"http://host.docker.internal:{port}{path}"

    t0 = time.monotonic()
    try:
        r = httpx.request(method, url, json=payload, headers={"x-api-key": api_key}, timeout=15.0)
    except httpx.TimeoutException:
        return {
            "test_id": test_id, "endpoint": endpoint, "payload": payload,
            "response_status": None, "response_excerpt": "",
            "assertion": expect, "result": "ERROR",
            "detail": "Timeout: el deployment no respondió en 15s",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {
            "test_id": test_id, "endpoint": endpoint, "payload": payload,
            "response_status": None, "response_excerpt": "",
            "assertion": expect, "result": "ERROR",
            "detail": f"Error de conexión: {str(exc)[:150]}",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    try:
        response_json = r.json()
        response_excerpt = json.dumps(response_json, ensure_ascii=False)[:2000]
    except Exception:
        response_json = None
        response_excerpt = r.text[:2000]

    expected_status = expect.get("status_code")
    status_ok = expected_status is None or r.status_code == expected_status

    received_value = MISSING
    assertion_ok = status_ok
    if status_ok and "json_path" in expect:
        received_value = eval_json_path(response_json, expect["json_path"])
        assertion_ok = received_value is not MISSING and received_value == expect.get("equals")

    return {
        "test_id": test_id,
        "endpoint": endpoint,
        "payload": payload,
        "response_status": r.status_code,
        "response_excerpt": response_excerpt,
        "assertion": {
            "expected_status": expected_status,
            "json_path": expect.get("json_path"),
            "expected_value": expect.get("equals"),
            "received_value": None if received_value is MISSING else received_value,
        },
        "result": "PASS" if assertion_ok else "FAIL",
        "detail": None,
        "latency_ms": latency_ms,
    }


def persist_test_result(project_id: str, record: dict) -> None:
    import fcntl
    paths.TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = paths.TEST_RESULTS_DIR / f"{project_id}.jsonl"
    lock_path = results_file.with_suffix(".lock")
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


# ── Readers (nunca auditan) ───────────────────────────────────────────────────

def read_catalog(project_id: str) -> dict:
    """READER — catálogo curado de pruebas de la misión. No ejecuta nada, no audita."""
    catalog = load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")

    from factory.core.port_registry import get_allocated_ports
    ports = get_allocated_ports(project_id)
    port = ports.get("api") if ports else None
    deployment_ready = False
    health_body = None
    if port:
        try:
            r = httpx.get(f"http://host.docker.internal:{port}/health", timeout=4.0)
            deployment_ready = r.status_code == 200
            health_body = r.json() if deployment_ready else None
        except Exception:
            deployment_ready = False

    return {
        "project_id": project_id,
        "catalog_version": catalog.get("catalog_version"),
        "deployment_ready": deployment_ready,
        "deployment": {"api_port": port, "health": health_body},
        "agents": catalog.get("agents", []),
    }


def read_results(project_id: str, limit: int = 50) -> dict:
    """READER — historial de pruebas ya ejecutadas (read-only). No audita."""
    results_file = paths.TEST_RESULTS_DIR / f"{project_id}.jsonl"
    if not results_file.exists():
        return {"project_id": project_id, "total": 0, "results": []}
    lines = [ln for ln in results_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records = []
    for ln in lines[-limit:]:
        try:
            records.append(json.loads(ln))
        except Exception:
            continue
    records.reverse()
    return {"project_id": project_id, "total": len(lines), "results": records}


# ── Executors (auditan exactamente 1 evento) ──────────────────────────────────

def run_test(project_id: str, test_id: str, run_by: str) -> dict:
    """
    EXECUTOR — ejecuta UN caso de prueba del catálogo curado contra el
    deployment real de la misión. Audita exactamente 1 evento.
    """
    from factory.core.audit_writer import write_event as _we

    run_by = validate_run_by(run_by)

    catalog = load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")
    found = find_test_in_catalog(catalog, test_id)
    if found is None:
        raise HTTPException(404, f"Test '{test_id}' no existe en el catálogo de '{project_id}'")
    agent_id, test_entry = found

    port, api_key = require_live_deployment(project_id)

    result = execute_catalog_test(port, api_key, test_entry)
    record = {**result, "agent_id": agent_id, "run_by": run_by, "run_at": now_iso()}
    persist_test_result(project_id, record)

    _we("agent_functional_test_executed", project_id, {
        "test_id": test_id,
        "agent_id": agent_id,
        "result": result["result"],
        "run_by": run_by,
        "decision_origin": "human_confirmed",
    })

    return record


def run_suite(project_id: str, agent_id: str, run_by: str) -> dict:
    """
    EXECUTOR — ejecuta todos los casos de un agente en secuencia.
    Un solo evento de auditoría agent_suite_tested con resumen N/M PASS
    (cada resultado individual también se persiste en test_results).
    """
    from factory.core.audit_writer import write_event as _we

    run_by = validate_run_by(run_by)

    catalog = load_test_catalog(project_id)
    if catalog is None:
        raise HTTPException(404, f"No hay catálogo de pruebas para la misión '{project_id}'")
    tests = find_agent_tests(catalog, agent_id)
    if tests is None:
        raise HTTPException(404, f"Agente '{agent_id}' no existe en el catálogo de '{project_id}'")
    if not tests:
        raise HTTPException(404, f"Agente '{agent_id}' no tiene casos de prueba en el catálogo")

    port, api_key = require_live_deployment(project_id)

    results = []
    passed = 0
    run_at = now_iso()
    for test_entry in tests:
        result = execute_catalog_test(port, api_key, test_entry)
        record = {**result, "agent_id": agent_id, "run_by": run_by, "run_at": run_at}
        persist_test_result(project_id, record)
        results.append(record)
        if result["result"] == "PASS":
            passed += 1

    _we("agent_suite_tested", project_id, {
        "agent_id": agent_id,
        "total": len(tests),
        "passed": passed,
        "run_by": run_by,
        "decision_origin": "human_confirmed",
    })

    return {
        "project_id": project_id,
        "agent_id": agent_id,
        "total": len(tests),
        "passed": passed,
        "results": results,
    }
