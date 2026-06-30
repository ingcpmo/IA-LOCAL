"""
W3 — Tests de /summary: shape correcto, ETag estable, 304, invariante read-only.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _get_api_key() -> str:
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


PROJECT = "oos_hplc_investigator"


def test_summary_returns_200_and_shape():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={"x-api-key": key}, timeout=15,
    )
    assert r.status_code == 200, f"Esperado 200, got {r.status_code}: {r.text[:200]}"
    d = r.json()
    for field in ["project_id", "mission", "design", "workspace", "tests", "rcs", "deployment", "audit", "etag"]:
        assert field in d, f"Campo faltante en /summary: {field!r}"
    assert d["project_id"] == PROJECT
    assert d["mission"]["status"] == "approved"
    assert d["rcs"]["count"] >= 1


def test_summary_etag_present():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={"x-api-key": key}, timeout=15,
    )
    assert r.status_code == 200
    etag = r.headers.get("etag")
    assert etag, "ETag header ausente en /summary"
    assert etag.startswith('"') and etag.endswith('"'), f"ETag mal formado: {etag}"


def test_summary_etag_stable_on_second_call():
    import httpx
    key = _get_api_key()
    h = {"x-api-key": key}
    r1 = httpx.get(f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary", headers=h, timeout=15)
    r2 = httpx.get(f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary", headers=h, timeout=15)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.headers.get("etag") == r2.headers.get("etag"), "ETag cambia entre llamadas sin modificación"


def test_summary_304_on_if_none_match():
    import httpx
    key = _get_api_key()
    h = {"x-api-key": key}
    r1 = httpx.get(f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary", headers=h, timeout=15)
    assert r1.status_code == 200
    etag = r1.headers.get("etag")
    assert etag
    r2 = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={**h, "if-none-match": etag}, timeout=15,
    )
    assert r2.status_code == 304, f"Esperado 304 con ETag correcto, got {r2.status_code}"


def test_summary_no_stale_etag_on_mismatched_value():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={"x-api-key": key, "if-none-match": '"00000000INVALID"'},
        timeout=15,
    )
    assert r.status_code == 200, "ETag inválido debe retornar 200, no 304"


def test_summary_not_found_returns_404():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        "http://localhost:9000/api/v1/layer9/missions/proyecto_inexistente_xyz/summary",
        headers={"x-api-key": key}, timeout=10,
    )
    assert r.status_code == 404


def test_summary_does_not_write_audit_chain():
    """Invariante: /summary es read-only — no debe crecer la cadena de auditoría."""
    import httpx
    key = _get_api_key()
    audit_file = Path("factory/audit/factory_audit.jsonl")
    c0 = sum(1 for _ in audit_file.open()) if audit_file.exists() else 0
    for _ in range(3):
        httpx.get(
            f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
            headers={"x-api-key": key}, timeout=15,
        )
    c1 = sum(1 for _ in audit_file.open()) if audit_file.exists() else 0
    assert c1 == c0, f"delta cadena tras 3 calls a /summary: {c1 - c0} (DEBE ser 0)"


def test_summary_headless_parsed():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={"x-api-key": key}, timeout=15,
    )
    assert r.status_code == 200
    d = r.json()
    hl = d.get("headless")
    assert hl is not None, "headless block ausente"
    assert hl.get("num_turns", 0) > 0
    assert hl.get("total_cost_usd", 0) > 0


def test_summary_tests_block():
    import httpx
    key = _get_api_key()
    r = httpx.get(
        f"http://localhost:9000/api/v1/layer9/missions/{PROJECT}/summary",
        headers={"x-api-key": key}, timeout=15,
    )
    assert r.status_code == 200
    d = r.json()
    tests = d.get("tests")
    assert tests is not None
    assert tests["failed"] == 0
    assert tests["passed"] >= 12
