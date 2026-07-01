"""
W4.1 — Tests del Dashboard GMP + informe PDF (/gmp-report, /gmp-report.pdf).

Mismo patrón que test_functional_testing.py: llama las funciones de ruta
directamente con los paths del módulo monkeypatcheados hacia tmp_path, así
se prueba el agregador real sin depender del deployment Docker ni contaminar
datos de la fábrica.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import factory.api.routes.layer9 as layer9
import factory.layer9.mission_control as mission_control
import factory.core.port_registry as port_registry
from factory.core.report_sanitizer import sanitize_for_report

PROJECT = "test_gmp_report_proj"
GMP_SECRET = "gmp-super-secret-deployment-key-0001"


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self._json_body = json_body

    def json(self):
        return self._json_body


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def _write_mission(missions_dir: Path, project_id: str) -> None:
    mission = {
        "project_id": project_id,
        "status": "approved",
        "client_type": "test_client",
        "objective": "Objetivo de prueba para el dashboard GMP.",
        "regulatory_scope": ["TEST_SCOPE"],
        "created_at": "2026-01-01T00:00:00+00:00",
        "approved_at": "2026-01-02T00:00:00+00:00",
        "history": [{"event": "approved", "by": "TestApprover", "at": "2026-01-02T00:00:00+00:00"}],
    }
    missions_dir.mkdir(parents=True, exist_ok=True)
    (missions_dir / f"{project_id}.yaml").write_text(yaml.dump(mission), encoding="utf-8")


@pytest.fixture()
def gmp_report_env(tmp_path, monkeypatch, isolated_audit):
    root = tmp_path / "factory_root"
    missions_dir = root / "layer9" / "missions"
    designs_dir = root / "designs"
    rc_dir = root / "release_candidates"
    dep_dir = root / "deployments"
    ws_dir = root / "workspaces"
    catalogs_dir = root / "test_catalogs"
    results_dir = root / "test_results"
    for d in (missions_dir, designs_dir, rc_dir, dep_dir, ws_dir, catalogs_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(layer9, "_FACTORY_ROOT", root)
    monkeypatch.setattr(layer9, "_DESIGNS_BASE", designs_dir)
    monkeypatch.setattr(layer9, "_RC_BASE_W3", rc_dir)
    monkeypatch.setattr(layer9, "_DEP_BASE", dep_dir)
    monkeypatch.setattr(layer9, "_WS_BASE_W3", ws_dir)
    monkeypatch.setattr(layer9, "_AUDIT_FILE", isolated_audit)
    monkeypatch.setattr(layer9, "_TEST_CATALOGS_DIR", catalogs_dir)
    monkeypatch.setattr(layer9, "_TEST_RESULTS_DIR", results_dir)
    monkeypatch.setattr(mission_control, "MISSIONS_DIR", missions_dir)

    monkeypatch.setattr(
        port_registry, "get_allocated_ports",
        lambda pid: {"api": 9999} if pid == PROJECT else None,
    )
    monkeypatch.setattr(layer9.httpx, "get", lambda *a, **k: _FakeResponse(200, {"api": "ok"}))

    _write_mission(missions_dir, PROJECT)

    return {
        "missions_dir": missions_dir, "designs_dir": designs_dir, "rc_dir": rc_dir,
        "dep_dir": dep_dir, "ws_dir": ws_dir, "catalogs_dir": catalogs_dir,
        "results_dir": results_dir, "audit_file": isolated_audit,
    }


def _write_full_evidence(env: dict) -> None:
    """Puebla todas las fuentes reales para un caso 'con evidencia completa'."""
    design_dir = env["designs_dir"] / PROJECT
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "requirement_spec.yaml").write_text(yaml.dump({
        "raw_objective": "Caso farmacéutico de prueba.",
        "domains": ["OOS", "HPLC"],
        "client_needs": ["necesidad 1"],
        "part11_required": True,
        "alcoa_plus_required": True,
    }), encoding="utf-8")
    (design_dir / "agent_design_proposal.yaml").write_text(yaml.dump({
        "project_id": PROJECT,
        "agents": [
            {"agent_id": "profile_agent", "decision": "profile", "base_agent": "base",
             "profile_name": "profile_agent", "rationale": "r", "routing_key": "k1"},
            {"agent_id": "new_agent", "decision": "new_agent", "base_agent": None,
             "profile_name": None, "rationale": "r2", "routing_key": "k2"},
        ],
    }), encoding="utf-8")
    (design_dir / "pending_documents.yaml").write_text(yaml.dump({
        "documents": [{"id": "DOC1", "title": "Guía pendiente", "status": "PENDING_DOCUMENT"}],
    }), encoding="utf-8")

    ws_dir = env["ws_dir"] / PROJECT
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "task.md").write_text("# Tarea de prueba\nContenido de ejemplo.", encoding="utf-8")

    dep_dir = env["dep_dir"] / PROJECT
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / ".env").write_text(f"GMP_API_KEY={GMP_SECRET}\n", encoding="utf-8")

    catalog = {
        "project_id": PROJECT,
        "catalog_version": "1.0",
        "agents": [{
            "agent_id": "new_agent",
            "tests": [{
                "test_id": "sample_test",
                "title": "Caso de prueba de ejemplo",
                "endpoint": "POST /api/v1/sample",
                "payload": {"x": 1},
                "expect": {"status_code": 200, "json_path": "$.ok", "equals": True},
            }],
        }],
    }
    (env["catalogs_dir"] / f"{PROJECT}.yaml").write_text(yaml.dump(catalog), encoding="utf-8")

    env["results_dir"].mkdir(parents=True, exist_ok=True)
    record = {
        "test_id": "sample_test", "endpoint": "POST /api/v1/sample", "payload": {"x": 1},
        "response_status": 200, "response_excerpt": '{"ok": true}',
        "assertion": {"expected_status": 200, "json_path": "$.ok", "expected_value": True, "received_value": True},
        "result": "PASS", "detail": None, "latency_ms": 5.0,
        "agent_id": "new_agent", "run_by": "Tester", "run_at": "2026-01-03T00:00:00+00:00",
    }
    (env["results_dir"] / f"{PROJECT}.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    rc_id = f"{PROJECT}-rc-v1.0-20260103T000000"
    rc_path = env["rc_dir"] / PROJECT / rc_id
    rc_path.mkdir(parents=True, exist_ok=True)
    (rc_path / "rc_manifest.json").write_text(json.dumps({
        "rc_id": rc_id, "project_id": PROJECT, "version": "1.0", "status": "approved",
        "is_canonical": True, "approved_by": "Tester", "decided_at": "2026-01-03T00:00:00+00:00",
        "proposed_at": "2026-01-03T00:00:00+00:00", "notes": "",
        "sha256sums": {"test_report.json": "abc123"},
    }), encoding="utf-8")


# ── shape / no_disponible / no-audita ────────────────────────────────────────

def test_gmp_report_shape_with_full_evidence(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    d = layer9._build_gmp_report(PROJECT)

    assert d["meta"]["project_id"] == PROJECT
    assert d["meta"]["client_type"] == "test_client"
    assert d["meta"]["canonical_rc"].startswith(PROJECT)
    assert d["meta"]["deployment_status"] in ("desplegado", "no_desplegado")
    assert set(d.keys()) >= {
        "meta", "executive_summary", "mission_objective", "pharma_case",
        "agents_evaluated", "results_by_agent", "pharma_interpretation",
        "gmp_implication", "rules_vs_llm", "audit_traceability",
        "operational_impact", "limitations", "pending_before_golive", "conclusion",
    }
    assert d["agents_evaluated"]["total"] == 2
    assert d["agents_evaluated"]["profiles_inherited"] == ["profile_agent"]
    assert d["agents_evaluated"]["new_agents"] == ["new_agent"]
    assert len(d["results_by_agent"]) == 1
    assert d["results_by_agent"][0]["tests"][0]["result"] == "PASS"
    assert "no reemplazan la decision" in d["conclusion"].lower() or "no reemplazan la decisión" in d["conclusion"].lower()
    assert "ESTIMACION" in d["operational_impact"] or "ESTIMACIÓN" in d["operational_impact"]
    assert any("PENDING_DOCUMENT" in s for s in d["limitations"])


def test_gmp_report_missing_fields_are_no_disponible_not_invented(gmp_report_env):
    # Sin design, sin catálogo, sin RCs, sin deployment: solo existe la misión.
    d = layer9._build_gmp_report(PROJECT)

    assert d["pharma_case"] == "no_disponible"
    assert d["meta"]["canonical_rc"] == "no_disponible"
    assert d["mission_objective"]["task_summary"] == "no_disponible"
    assert d["results_by_agent"] == []
    assert d["executive_summary"] == "No se han ejecutado pruebas funcionales aun para esta mision."
    assert d["gmp_implication"]["oos"] == "no_disponible"
    assert d["gmp_implication"]["hplc"] == "no_disponible"
    assert d["gmp_implication"]["alcoa"] == "no_disponible"
    assert d["audit_traceability"]["rc_sha256"] == "no_disponible"


def test_gmp_report_empty_results_shows_no_tests_message(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    # Vaciar test-results manteniendo el resto de la evidencia.
    (gmp_report_env["results_dir"] / f"{PROJECT}.jsonl").write_text("", encoding="utf-8")

    d = layer9._build_gmp_report(PROJECT)
    assert d["results_by_agent"] == []
    assert d["pharma_interpretation"] == ["No se han ejecutado pruebas funcionales aun para esta mision."]
    assert d["executive_summary"] == "No se han ejecutado pruebas funcionales aun para esta mision."


def test_get_gmp_report_does_not_audit(gmp_report_env, isolated_audit):
    _write_full_evidence(gmp_report_env)
    before = _count_lines(isolated_audit)
    layer9.get_gmp_report(PROJECT)
    layer9.get_gmp_report(PROJECT)
    layer9.get_gmp_report(PROJECT)
    assert _count_lines(isolated_audit) == before


def test_gmp_report_404_for_unknown_project(gmp_report_env):
    with pytest.raises(HTTPException) as exc:
        layer9._build_gmp_report("proyecto_inexistente")
    assert exc.value.status_code == 404


# ── sanitize_for_report ──────────────────────────────────────────────────────

def test_sanitize_masks_known_secret_value():
    data = {"note": f"la clave real es {GMP_SECRET} y no debe salir"}
    out = sanitize_for_report(data, secret_values=[GMP_SECRET])
    assert GMP_SECRET not in json.dumps(out)
    assert "***REDACTED***" in out["note"]


def test_sanitize_masks_sk_ant_pattern():
    data = {"log": "token usado: sk-ant-api03-abcDEF1234567890xyz"}
    out = sanitize_for_report(data)
    assert "sk-ant-" not in out["log"]


def test_sanitize_masks_sensitive_key_names_regardless_of_value():
    data = {"GMP_API_KEY": "cualquier-valor", "password": "hunter2", "normal_field": "sin cambios"}
    out = sanitize_for_report(data)
    assert out["GMP_API_KEY"] == "***REDACTED***"
    assert out["password"] == "***REDACTED***"
    assert out["normal_field"] == "sin cambios"


def test_gmp_report_json_never_contains_deployment_secret(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    d = layer9._build_gmp_report(PROJECT)
    assert GMP_SECRET not in json.dumps(d)


# ── PDF ───────────────────────────────────────────────────────────────────────

def test_gmp_report_pdf_returns_valid_pdf_bytes(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    resp = layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert resp.media_type == "application/pdf"
    assert len(resp.body) > 0
    assert resp.body[:4] == b"%PDF"
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_gmp_report_pdf_does_not_contain_gmp_api_key(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    resp = layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert GMP_SECRET.encode() not in resp.body


def test_gmp_report_pdf_does_not_audit_by_default(gmp_report_env, isolated_audit):
    _write_full_evidence(gmp_report_env)
    before = _count_lines(isolated_audit)
    layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert _count_lines(isolated_audit) == before


def test_gmp_report_pdf_audits_exactly_one_with_record_by(gmp_report_env, isolated_audit):
    _write_full_evidence(gmp_report_env)
    before = _count_lines(isolated_audit)
    layer9.get_gmp_report_pdf(PROJECT, record_by="Cesar")
    after = _count_lines(isolated_audit)
    assert after == before + 1
    last = json.loads(isolated_audit.read_text(encoding="utf-8").splitlines()[-1])
    assert last["event_type"] == "gmp_report_generated"
    assert last["data"]["record_by"] == "Cesar"


def test_gmp_report_pdf_rejects_generic_record_by(gmp_report_env):
    _write_full_evidence(gmp_report_env)
    with pytest.raises(HTTPException) as exc:
        layer9.get_gmp_report_pdf(PROJECT, record_by="system")
    assert exc.value.status_code == 422
