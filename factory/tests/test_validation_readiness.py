"""
W6.1 — Tests del servicio de reportes / paquete de validación / readiness.

Garantías fijadas:
  - toda función exige misión existente (404 antes de tocar rutas)
  - reports: lista solo artefactos de reporte reales; sin dossier no inventa
  - validation-package: sin dossier → 22 docs not_started; dossier parcial
    respetado; estados desconocidos degradan a not_started
  - readiness: dimensión sin dato → sin_evidencia; veredicto no_go salvo
    evidencia total (regla anti-optimismo R7)
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import mission_evidence_service as _evidence
from factory.services import paths as svc_paths
from factory.services import validation_readiness_service as svc


@pytest.fixture()
def mission_env(tmp_path, monkeypatch):
    """Misión mínima en disco + rutas redirigidas a tmp."""
    missions = tmp_path / "missions"; missions.mkdir()
    (missions / "demo.yaml").write_text(
        "status: approved\nhistory:\n  - {event: approved, by: Cesar}\n", encoding="utf-8")
    rc_base = tmp_path / "rcs"; rc_base.mkdir()
    results = tmp_path / "test_results"; results.mkdir()
    validation = tmp_path / "validation"
    monkeypatch.setattr(svc_paths, "MISSIONS_DIR", missions)
    monkeypatch.setattr(svc_paths, "RC_BASE", rc_base)
    monkeypatch.setattr(svc_paths, "TEST_RESULTS_DIR", results)
    monkeypatch.setattr(svc_paths, "VALIDATION_BASE", validation)
    return tmp_path


def test_mission_gate_404(mission_env):
    for fn in (svc.list_reports, svc.read_validation_package):
        with pytest.raises(HTTPException) as e:
            fn("no_existe")
        assert e.value.status_code == 404


# ── Reports ───────────────────────────────────────────────────────────────────

def test_reports_empty_mission(mission_env):
    out = svc.list_reports("demo")
    assert out["stored_reports"] == []
    assert "sin reportes" in out["note"]
    assert len(out["on_demand"]) == 2  # gmp-report + PDF siempre referenciados


def test_reports_lists_rc_artifacts_and_results(mission_env):
    rc = mission_env / "rcs" / "demo" / "demo-rc-v1.0"
    (rc / "artifacts").mkdir(parents=True)
    (rc / "rc_manifest.json").write_text('{"rc_id":"demo-rc-v1.0"}', encoding="utf-8")
    (rc / "artifacts" / "test_report.json").write_text('{"summary":{}}', encoding="utf-8")
    (rc / "artifacts" / "codigo.py").write_text("x=1", encoding="utf-8")  # NO es reporte
    (mission_env / "test_results" / "demo.jsonl").write_text('{"run":1}\n', encoding="utf-8")

    out = svc.list_reports("demo")
    kinds = sorted(r["kind"] for r in out["stored_reports"])
    assert kinds == ["functional_test_results", "release_candidate", "release_candidate"]
    paths_listed = [r["path"] for r in out["stored_reports"]]
    assert not any(p.endswith(".py") for p in paths_listed)
    assert all({"size_bytes", "modified_at", "sha256_12"} <= set(r) for r in out["stored_reports"])


# ── Validation package ────────────────────────────────────────────────────────

def test_validation_package_no_dossier(mission_env):
    out = svc.read_validation_package("demo")
    assert out["dossier_exists"] is False
    assert out["total"] == 22 and len(out["documents"]) == 22
    assert out["counts"] == {"not_started": 22, "draft": 0, "missing_evidence": 0,
                             "needs_human_review": 0, "approved": 0}


def test_validation_package_partial_dossier(mission_env):
    d = mission_env / "validation" / "demo"; d.mkdir(parents=True)
    (d / "dossier.yaml").write_text(
        "documents:\n"
        "  urs: {status: approved, approved_by: Cesar}\n"
        "  iq: {status: generated}\n"          # alias legado → draft
        "  pq: {status: missing_evidence}\n"
        "  oq: {status: estado_invalido}\n",   # degrada a not_started
        encoding="utf-8")
    out = svc.read_validation_package("demo")
    assert out["counts"] == {"not_started": 19, "draft": 1, "missing_evidence": 1,
                             "needs_human_review": 0, "approved": 1}
    by_id = {doc["doc_id"]: doc for doc in out["documents"]}
    assert by_id["urs"]["status"] == "approved" and by_id["urs"]["approved_by"] == "Cesar"
    assert by_id["iq"]["status"] == "draft"
    assert by_id["oq"]["status"] == "not_started"


# ── Readiness ─────────────────────────────────────────────────────────────────

def _summary_fixture(**over):
    base = {
        "mission": {"status": "approved", "approved_by": "Cesar"},
        "design": {"agents_summary": {"agent_ids": ["qa", "capa"]}},
        "tests": {"passed": 10, "failed": 0},
        "rcs": {"canonical": "demo-rc-v1.0", "count": 1},
        "deployment": {"exists": True, "api_port": 8102, "health_ok": True},
        "audit": {"event_count_filtered": 12},
    }
    base.update(over)
    return base


def test_readiness_never_go_without_full_evidence(mission_env, monkeypatch):
    monkeypatch.setattr(_evidence, "build_mission_summary", lambda pid: _summary_fixture())
    out = svc.build_readiness("demo")
    assert out["total"] == 12
    # roles/LIMS/datos representativos no existen en el sistema → sin_evidencia
    sin_ev = [d["id"] for d in out["dimensions"] if d["status"] == "sin_evidencia"]
    assert {"roles_signatures", "lims_cds", "representative_data"} <= set(sin_ev)
    assert out["verdict"] == "no_go"          # regla anti-optimismo
    assert out["ready"] < out["total"]


def test_readiness_reflects_missing_evidence(mission_env, monkeypatch):
    monkeypatch.setattr(_evidence, "build_mission_summary",
                        lambda pid: _summary_fixture(tests=None,
                                                     rcs={"canonical": None, "count": 0}))
    out = svc.build_readiness("demo")
    by_id = {d["id"]: d for d in out["dimensions"]}
    assert by_id["build_tests"]["status"] == "sin_evidencia"
    assert by_id["canonical_rc"]["status"] == "not_ready"
    assert by_id["mission_approved"]["status"] == "ready"
    assert "Cesar" in by_id["mission_approved"]["evidence"]


def test_readiness_functional_tests_from_disk(mission_env, monkeypatch):
    monkeypatch.setattr(_evidence, "build_mission_summary", lambda pid: _summary_fixture())
    (mission_env / "test_results" / "demo.jsonl").write_text(
        '{"r":1}\n{"r":2}\n{"r":3}\n', encoding="utf-8")
    out = svc.build_readiness("demo")
    by_id = {d["id"]: d for d in out["dimensions"]}
    assert by_id["functional_tests"]["status"] == "ready"
    assert "3 ejecuciones" in by_id["functional_tests"]["evidence"]


def test_readiness_every_dimension_has_evidence_text(mission_env, monkeypatch):
    monkeypatch.setattr(_evidence, "build_mission_summary", lambda pid: _summary_fixture())
    out = svc.build_readiness("demo")
    assert all(d["evidence"] for d in out["dimensions"])


# ── Read-only estructural ─────────────────────────────────────────────────────

def test_service_never_writes_or_audits():
    import ast
    tree = ast.parse(Path(svc.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(a.name for a in node.names)
    assert not any("audit_writer" in n or n == "write_event" for n in imported)
    src = Path(svc.__file__).read_text(encoding="utf-8")
    assert "write_text" not in src and "mkdir" not in src  # nunca escribe
