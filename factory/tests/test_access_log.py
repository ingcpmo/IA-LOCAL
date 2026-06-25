"""
Guard U12: access log middleware.
  - Registra IP, método, path, status, latency_ms, ua, ts.
  - NUNCA registra el body de POST (protección PII).
  - Múltiples requests producen múltiples líneas.
Tests vía httpx contra el contenedor en ejecución.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_ACCESS_LOG = Path(__file__).parent.parent / "logs" / "access.jsonl"
_BASE = "http://localhost:9000"


def _get_api_key() -> str:
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


def _last_entries(n: int = 5) -> list[dict]:
    if not _ACCESS_LOG.exists():
        return []
    lines = [l for l in _ACCESS_LOG.read_text().splitlines() if l.strip()]
    return [json.loads(l) for l in lines[-n:]]


def test_access_log_file_created():
    """El archivo de log se crea al recibir la primera petición."""
    import httpx
    key = _get_api_key()
    httpx.get(f"{_BASE}/health", headers={"x-api-key": key}, timeout=5)
    assert _ACCESS_LOG.exists(), "factory/logs/access.jsonl no existe tras la petición"


def test_access_log_required_fields():
    """Cada entrada contiene los campos obligatorios."""
    import httpx
    key = _get_api_key()
    httpx.get(f"{_BASE}/health", headers={"x-api-key": key}, timeout=5)
    entries = _last_entries(3)
    assert entries, "Sin entradas en access.jsonl"
    for field in ("ts", "ip", "method", "path", "status", "latency_ms", "ua"):
        assert field in entries[-1], f"Campo requerido ausente: {field}"


def test_access_log_correct_method_and_path():
    import httpx
    key = _get_api_key()
    before = len(_last_entries(200))
    httpx.get(f"{_BASE}/health", headers={"x-api-key": key}, timeout=5)
    entries = _last_entries(before + 5)
    health_entries = [e for e in entries if e.get("path") == "/health"]
    assert health_entries, "No se encontró entrada de /health en el log"
    e = health_entries[-1]
    assert e["method"] == "GET"
    assert e["status"] == 200
    assert isinstance(e["latency_ms"], (int, float))


def test_access_log_no_body_in_post():
    """El body del POST no debe aparecer en el access log (protección PII)."""
    import httpx
    key = _get_api_key()
    sentinel = f"SENTINEL_PII_{int(time.time())}"
    httpx.post(
        f"{_BASE}/api/v1/layer8/missions",
        headers={"x-api-key": key, "content-type": "application/json"},
        content=f'{{"secret": "{sentinel}"}}',
        timeout=10,
    )
    raw = _ACCESS_LOG.read_text() if _ACCESS_LOG.exists() else ""
    assert sentinel not in raw, "Body del POST expuesto en access log (violación PII)"


def test_access_log_records_4xx():
    """Los errores 4xx también quedan en el log."""
    import httpx
    key = _get_api_key()
    before_count = len(_last_entries(200))
    httpx.get(f"{_BASE}/api/v1/nonexistent_path_xyz", headers={"x-api-key": key}, timeout=5)
    entries = _last_entries(before_count + 5)
    statuses = [e["status"] for e in entries]
    assert any(s >= 400 for s in statuses), f"No se encontró 4xx en el log: {statuses}"
