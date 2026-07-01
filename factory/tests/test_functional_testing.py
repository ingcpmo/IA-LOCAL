"""
W4 — Tests de la consola de pruebas funcionales por agente.

Llama las funciones de ruta de factory/api/routes/layer9.py directamente
(mismo patrón que test_layer9_mission_control.py), con httpx y el registry
de puertos mockeados vía monkeypatch — así se prueba la lógica del executor
(anti-inyección, anti-SSRF, auditoría exacta) sin depender del deployment
Docker real ni contaminar la cadena de auditoría real.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import factory.api.routes.layer9 as layer9
import factory.core.port_registry as port_registry


PROJECT = "test_functional_proj"


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text

    def json(self):
        return self._json_body


_CATALOG = {
    "project_id": PROJECT,
    "deployment_base": "http://localhost:9999",  # el executor debe IGNORAR este campo
    "catalog_version": "1.0",
    "agents": [
        {
            "agent_id": "fake_agent",
            "description": "agente de prueba",
            "tests": [
                {
                    "test_id": "fake_pass",
                    "title": "caso feliz",
                    "endpoint": "POST /fake/endpoint",
                    "payload": {"x": 1},
                    "expect": {"status_code": 200, "json_path": "$.ok", "equals": True},
                },
                {
                    "test_id": "fake_other",
                    "title": "segundo caso de la suite",
                    "endpoint": "POST /fake/other",
                    "payload": {"y": 2},
                    "expect": {"status_code": 200, "json_path": "$.ok", "equals": True},
                },
            ],
        }
    ],
}


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


@pytest.fixture()
def functional_test_env(tmp_path, monkeypatch, isolated_audit):
    catalogs_dir = tmp_path / "test_catalogs"
    catalogs_dir.mkdir()
    (catalogs_dir / f"{PROJECT}.yaml").write_text(yaml.safe_dump(_CATALOG), encoding="utf-8")

    results_dir = tmp_path / "test_results"

    dep_base = tmp_path / "deployments"
    dep_dir = dep_base / PROJECT
    dep_dir.mkdir(parents=True)
    (dep_dir / ".env").write_text("GMP_API_KEY=test-secret-key\n", encoding="utf-8")

    monkeypatch.setattr(layer9, "_TEST_CATALOGS_DIR", catalogs_dir)
    monkeypatch.setattr(layer9, "_TEST_RESULTS_DIR", results_dir)
    monkeypatch.setattr(layer9, "_DEP_BASE", dep_base)

    monkeypatch.setattr(
        port_registry, "get_allocated_ports",
        lambda pid: {"api": 9999} if pid == PROJECT else None,
    )

    # Health check OK por defecto — cada test puede sobreescribirlo (409 case).
    monkeypatch.setattr(layer9.httpx, "get", lambda *a, **k: _FakeResponse(200, {"api": "ok"}))

    return {"catalogs_dir": catalogs_dir, "results_dir": results_dir, "dep_dir": dep_dir}


# ── READER: GET test-catalog ─────────────────────────────────────────────────

def test_get_test_catalog_returns_catalog_and_does_not_audit(functional_test_env, isolated_audit):
    before = _count_lines(isolated_audit)
    result = layer9.get_test_catalog(PROJECT)
    assert result["project_id"] == PROJECT
    assert result["deployment_ready"] is True
    assert len(result["agents"]) == 1
    assert len(result["agents"][0]["tests"]) == 2
    assert _count_lines(isolated_audit) == before


def test_get_test_catalog_404_for_unknown_project(functional_test_env):
    with pytest.raises(HTTPException) as exc:
        layer9.get_test_catalog("proyecto_sin_catalogo")
    assert exc.value.status_code == 404


# ── READER: GET test-results ─────────────────────────────────────────────────

def test_get_test_results_empty_and_readonly(functional_test_env, isolated_audit):
    before = _count_lines(isolated_audit)
    result = layer9.get_test_results(PROJECT)
    assert result == {"project_id": PROJECT, "total": 0, "results": []}
    assert _count_lines(isolated_audit) == before


def test_results_reader_reflects_executed_runs(functional_test_env, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "request", lambda *a, **k: _FakeResponse(200, {"ok": True}))
    layer9.post_run_test(PROJECT, layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar"))
    # limit explícito: al llamar la ruta directo en Python (sin ASGI de por medio),
    # el default Query(default=50) no se resuelve a int — sí se resuelve en HTTP real
    # (ya verificado en vivo). Mismo patrón que el resto de esta suite.
    result = layer9.get_test_results(PROJECT, limit=50)
    assert result["total"] == 1
    assert result["results"][0]["test_id"] == "fake_pass"


# ── EXECUTOR: validaciones ───────────────────────────────────────────────────

def test_run_request_schema_has_only_test_id_and_run_by():
    """Garantía a nivel de schema: no hay canal para inyectar un payload arbitrario."""
    assert set(layer9.TestRunRequest.model_fields.keys()) == {"test_id", "run_by"}


@pytest.mark.parametrize("run_by", ["human", "agent", "system", "admin", "user", "factory", "", "   "])
def test_run_rejects_generic_or_empty_run_by(functional_test_env, run_by):
    body = layer9.TestRunRequest(test_id="fake_pass", run_by=run_by)
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test(PROJECT, body)
    assert exc.value.status_code == 422


def test_run_rejects_unknown_test_id(functional_test_env):
    body = layer9.TestRunRequest(test_id="no_existe", run_by="Cesar")
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test(PROJECT, body)
    assert exc.value.status_code == 404


def test_run_rejects_when_deployment_down(functional_test_env, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "get", lambda *a, **k: _FakeResponse(500))
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test(PROJECT, body)
    assert exc.value.status_code == 409


def test_run_rejects_when_health_check_raises(functional_test_env, monkeypatch):
    def _boom(*a, **k):
        raise ConnectionError("refused")
    monkeypatch.setattr(layer9.httpx, "get", _boom)
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test(PROJECT, body)
    assert exc.value.status_code == 409


# ── EXECUTOR: anti-inyección / anti-SSRF ─────────────────────────────────────

def test_run_uses_catalog_payload_not_client_supplied(functional_test_env, monkeypatch):
    captured = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(layer9.httpx, "request", fake_request)
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    layer9.post_run_test(PROJECT, body)
    assert captured["json"] == {"x": 1}  # el payload real del catálogo, no algo inyectado


def test_run_uses_port_from_registry_not_catalog_deployment_base(functional_test_env, monkeypatch):
    captured = {}

    def fake_request(method, url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(layer9.httpx, "request", fake_request)
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    layer9.post_run_test(PROJECT, body)
    # El catálogo declara deployment_base=http://localhost:9999 (otro formato/host);
    # el executor lo ignora y siempre resuelve host:puerto desde el registry.
    assert captured["url"] == "http://host.docker.internal:9999/fake/endpoint"
    assert captured["headers"]["x-api-key"] == "test-secret-key"


# ── EXECUTOR: ejecución real y auditoría ─────────────────────────────────────

def test_run_success_audits_exactly_one_event(functional_test_env, isolated_audit, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "request", lambda *a, **k: _FakeResponse(200, {"ok": True}))
    before = _count_lines(isolated_audit)
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    result = layer9.post_run_test(PROJECT, body)
    assert result["result"] == "PASS"
    assert result["run_by"] == "Cesar"
    assert result["agent_id"] == "fake_agent"
    assert _count_lines(isolated_audit) == before + 1


def test_run_returns_fail_when_assertion_mismatches(functional_test_env, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "request", lambda *a, **k: _FakeResponse(200, {"ok": False}))
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    result = layer9.post_run_test(PROJECT, body)
    assert result["result"] == "FAIL"
    assert result["assertion"]["received_value"] is False
    assert result["assertion"]["expected_value"] is True


def test_run_returns_error_on_timeout(functional_test_env, monkeypatch):
    import httpx as real_httpx

    def _timeout(*a, **k):
        raise real_httpx.TimeoutException("timed out")

    monkeypatch.setattr(layer9.httpx, "request", _timeout)
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Cesar")
    result = layer9.post_run_test(PROJECT, body)
    assert result["result"] == "ERROR"
    assert "Timeout" in result["detail"]


def test_run_persists_result_with_run_by(functional_test_env, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "request", lambda *a, **k: _FakeResponse(200, {"ok": True}))
    body = layer9.TestRunRequest(test_id="fake_pass", run_by="Maria")
    layer9.post_run_test(PROJECT, body)

    results_file = functional_test_env["results_dir"] / f"{PROJECT}.jsonl"
    assert results_file.exists()
    lines = [l for l in results_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["run_by"] == "Maria"
    assert record["test_id"] == "fake_pass"
    assert record["result"] == "PASS"


# ── EXECUTOR: run-suite ──────────────────────────────────────────────────────

def test_run_suite_audits_exactly_one_event_for_n_tests(functional_test_env, isolated_audit, monkeypatch):
    monkeypatch.setattr(layer9.httpx, "request", lambda *a, **k: _FakeResponse(200, {"ok": True}))
    before = _count_lines(isolated_audit)
    body = layer9.TestRunSuiteRequest(agent_id="fake_agent", run_by="Cesar")
    result = layer9.post_run_test_suite(PROJECT, body)
    assert result["total"] == 2
    assert result["passed"] == 2
    assert _count_lines(isolated_audit) == before + 1

    results_file = functional_test_env["results_dir"] / f"{PROJECT}.jsonl"
    lines = [l for l in results_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2  # cada resultado individual SÍ se persiste, aunque la auditoría sea 1 sola


def test_run_suite_rejects_unknown_agent(functional_test_env):
    body = layer9.TestRunSuiteRequest(agent_id="no_existe", run_by="Cesar")
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test_suite(PROJECT, body)
    assert exc.value.status_code == 404


def test_run_suite_rejects_generic_run_by(functional_test_env):
    body = layer9.TestRunSuiteRequest(agent_id="fake_agent", run_by="system")
    with pytest.raises(HTTPException) as exc:
        layer9.post_run_test_suite(PROJECT, body)
    assert exc.value.status_code == 422
