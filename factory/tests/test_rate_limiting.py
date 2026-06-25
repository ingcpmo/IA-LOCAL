"""
Guard U12: rate limiting — lógica de contador y comportamiento de la API real.

Tests unitarios: RateLimitCounter (puro Python, sin ASGI).
Tests de integración: container vía httpx.
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core.rate_limit import RateLimitCounter


# ── Unit: RateLimitCounter ───────────────────────────────────────────────────

def test_counter_allows_up_to_limit():
    c = RateLimitCounter(limit=3, window=60)
    now = time.time()
    assert c.allow(now) is True
    assert c.allow(now) is True
    assert c.allow(now) is True


def test_counter_blocks_at_limit():
    c = RateLimitCounter(limit=3, window=60)
    now = time.time()
    c.allow(now); c.allow(now); c.allow(now)
    assert c.allow(now) is False


def test_counter_resets_after_window():
    c = RateLimitCounter(limit=2, window=10)
    t0 = time.time()
    c.allow(t0); c.allow(t0)
    assert c.allow(t0) is False
    # Avanzar ventana: las entradas anteriores caducan
    t1 = t0 + 11
    assert c.allow(t1) is True


def test_counter_sliding_window_partial_reset():
    """Solo las entradas fuera de la ventana caducan."""
    c = RateLimitCounter(limit=3, window=10)
    t0 = time.time()
    c.allow(t0)          # t=0 — quedará dentro si avanzamos <10s
    c.allow(t0 + 5)      # t=5
    c.allow(t0 + 5)      # t=5 — ahora lleno
    assert c.allow(t0 + 5) is False
    # t=11: la entrada de t=0 caduca, queda 2, hay espacio para 1 más
    assert c.allow(t0 + 11) is True


def test_counter_independent_instances():
    """Dos contadores con distinta clave son independientes."""
    a = RateLimitCounter(limit=2, window=60)
    b = RateLimitCounter(limit=2, window=60)
    now = time.time()
    a.allow(now); a.allow(now)
    assert a.allow(now) is False
    assert b.allow(now) is True  # b no ha sido tocado


# ── Integración: container ────────────────────────────────────────────────────

def _get_api_key():
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


def test_audit_endpoint_exempt_from_rate_limit():
    """/api/v1/audit/* no aplica rate limit (libre para auditores)."""
    import httpx
    key = _get_api_key()
    # Enviar 80 peticiones consecutivas sin API key → audit debe seguir respondiendo
    for i in range(80):
        r = httpx.get(
            "http://localhost:9000/api/v1/audit/summary",
            headers={"x-api-key": key},
            timeout=10,
        )
        assert r.status_code == 200, f"audit rate-limited en petición {i+1}: {r.status_code}"


def test_authenticated_requests_use_separate_bucket():
    """Con API key válida no se aplica el límite de IP pública."""
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/health",
        headers={"x-api-key": key},
        timeout=10,
    )
    assert r.status_code == 200
