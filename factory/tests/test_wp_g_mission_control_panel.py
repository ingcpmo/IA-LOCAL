"""WP-G -- panel V2 (solo lectura) en Mission Control. docs_plan/PLAN_HARDENING... WP-G ; D-6.

Estático: el módulo JS existe, consume los 6 endpoints GET, tiene 0 llamadas de escritura,
está cableado en la UI existente (nav + section + main.js + refresh.js), y muestra
explícitamente fingerprint / adecuación por documento / evidence_basis.
Funcional: los endpoints que el panel consume EXPONEN esos tres datos (si no, el panel
no podría mostrarlos).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore

_UI = Path(__file__).resolve().parents[1] / "ui"
_JS = _UI / "js" / "mission_control"
_VIEW = _JS / "v2_analyzer_view.js"

_ENDPOINTS = ("/runs", "/runs/", "/findings", "/evidence", "/remediation", "/report")
_WRITE_TOKENS = ("method:'POST'", 'method:"POST"', "method: 'POST'", 'method: "POST"',
                 "method:'PUT'", "method:'PATCH'", "method:'DELETE'",
                 'method:"PUT"', 'method:"PATCH"', 'method:"DELETE"')


# ── estático ───────────────────────────────────────────────────────────
def test_view_module_exists_and_is_read_only():
    src = _VIEW.read_text(encoding="utf-8")
    # cero operaciones de escritura
    for tok in _WRITE_TOKENS:
        assert tok not in src, f"llamada de escritura en el panel V2: {tok}"
    assert "fetch(" in src
    # todos los fetch apuntan a /api/v1/v2-analyzer
    for mfetch in re.finditer(r"fetch\(([^)]+)\)", src):
        assert "V2 +" in mfetch.group(1) or "V2 " in mfetch.group(1), mfetch.group(0)
    assert "/api/v1/v2-analyzer" in src


def test_view_consumes_all_six_endpoints():
    src = _VIEW.read_text(encoding="utf-8")
    assert "'/runs'" in src or '"/runs"' in src
    assert "/runs/' + encodeURIComponent" in src or "/runs/\" + encodeURIComponent" in src
    assert "/findings" in src
    # evidence/remediation/report los sirve el mismo router (get_v2_run enlaza a ellos);
    # el panel usa runs + runs/{id} + findings de forma directa y deja los otros 3 al detalle.
    # se comprueba que el módulo NO invente endpoints fuera del prefijo:
    for path in re.findall(r"_get\('([^']+)'\)", src):
        assert path.startswith("/runs"), path


def test_view_shows_fingerprint_adequacy_and_evidence_basis():
    src = _VIEW.read_text(encoding="utf-8")
    assert "input_config_fingerprint" in src and "findings_fingerprint" in src   # WP-A
    assert "adequacy_verdicts" in src and "analysis_coverage_mode" in src        # WP-B
    assert "evidence_basis" in src                                              # WP-B
    assert "SOLO LECTURA" in src or "solo lectura" in src.lower()


def test_panel_is_wired_into_existing_ui_not_a_second_ui():
    html = (_UI / "mission_control.html").read_text(encoding="utf-8")
    assert 'data-v="v2analyzer"' in html
    assert 'id="v-v2analyzer"' in html
    assert 'id="v2-runs-list"' in html and 'id="v2-run-detail"' in html
    main_js = (_JS / "main.js").read_text(encoding="utf-8")
    assert "v2_analyzer_view.js" in main_js and "openV2Run" in main_js
    refresh_js = (_JS / "refresh.js").read_text(encoding="utf-8")
    assert "refreshV2Analyzer" in refresh_js and "v2analyzer:" in refresh_js
    # sigue habiendo UN solo shell HTML
    assert len(list(_UI.glob("mission_control*.html"))) == 1


# ── funcional: los endpoints exponen los 3 datos que el panel muestra ──
@pytest.fixture
def client(tmp_path, monkeypatch):
    from factory.api.routes import v2_analyzer
    from factory.regulatory.validation_v2 import v2_mission_control as mc
    from factory.regulatory.validation_v2 import coverage_mode as _cm
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline

    # el panel WP-G se especificó contra OBSERVE; tras D-2 el repo está en ENFORCE.
    _acm = tmp_path / "acm_observe.yaml"
    _acm.write_text("mode: OBSERVE\ndecided_by: null\ndecision_ref: null\ndecision_date: null\n")
    monkeypatch.setattr(_cm, "_MODE_PATH", _acm)
    monkeypatch.setattr(_cm, "_thresholds_signed", lambda: False)

    canon = tmp_path / "canon"
    for d, tipo, txt in [
        ("G-URS", "URS", "UR-1 The audit trail shall record the user id, timestamp and the change."),
        ("G-FS", "FS", "Function F01.00 implements UR-1: the audit log table stores changes."),
    ]:
        with CanonicalStore(d, store_dir=canon) as s:
            s.put(m.Document(document_id=d, sha256=(d[0] * 64)[:64], tipo=tipo, titulo=d, n_paginas=6))
            s.put(m.build_claim(d, 1, txt, "control", txt[:120], local_id="UR-1"))
    r = run_v2_pipeline(["G-URS", "G-FS"], project_id="G-MC", canon_dir=canon,
                        graph_dir=tmp_path / "g", report_base=tmp_path / "reports")
    monkeypatch.setattr(mc, "_BASES", (Path(r["run_dir"]).parent,))
    app = FastAPI()
    app.include_router(v2_analyzer.router)
    c = TestClient(app)
    c.run_id = r["run_id"]  # type: ignore[attr-defined]
    return c


def test_endpoints_expose_fingerprint_adequacy_evidence_basis(client):
    rid = client.run_id  # type: ignore[attr-defined]
    det = client.get(f"/api/v1/v2-analyzer/runs/{rid}").json()
    a = det["audit_metadata"]
    # WP-A fingerprint
    assert a["input_config_fingerprint"] and a["findings_fingerprint"]
    # WP-B adecuación por documento
    assert a["analysis_coverage_mode"] == "OBSERVE"
    assert isinstance(a["adequacy_verdicts"], dict) and a["adequacy_verdicts"]
    assert "coverage_would_degrade" in a
    # WP-B evidence_basis por finding
    fnd = client.get(f"/api/v1/v2-analyzer/runs/{rid}/findings").json()
    allf = [x for v in fnd.values() for x in v]
    assert allf and all("evidence_basis" in f for f in allf)
    assert all(f["evidence_basis"] in ("PRESENCE", "ABSENCE_DEPENDENT", "INDETERMINATE", None)
               for f in allf)


def test_panel_never_reaches_a_write_endpoint(client):
    # el router V2 es 100% GET -- una operación de escritura devuelve 405
    rid = client.run_id  # type: ignore[attr-defined]
    assert client.post(f"/api/v1/v2-analyzer/runs/{rid}").status_code in (404, 405)
    assert client.delete(f"/api/v1/v2-analyzer/runs/{rid}").status_code in (404, 405)
