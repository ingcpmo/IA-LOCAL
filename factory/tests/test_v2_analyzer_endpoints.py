"""Tests -- Mission Control V2 analyzer endpoints (B9b / FASE 11)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    from factory.regulatory.validation_v2 import v2_mission_control as mc
    from factory.api.routes import v2_analyzer

    canon = tmp_path / "canon"
    with CanonicalStore("E-URS", store_dir=canon) as s:
        s.put(m.Document(document_id="E-URS", sha256="u" * 64, tipo="URS", titulo="URS", n_paginas=3))
        s.put(m.build_claim("E-URS", 1, "UR-9 The audit trail shall record every change with the user id.",
                            "control", "UR-9 audit trail change user id", local_id="UR-9"))
    r = run_v2_pipeline(["E-URS"], project_id="E-MC", canon_dir=canon,
                        graph_dir=tmp_path / "g", report_base=tmp_path / "reports")
    monkeypatch.setattr(mc, "_BASES", (Path(r["run_dir"]).parent,))

    app = FastAPI()
    app.include_router(v2_analyzer.router)
    c = TestClient(app)
    c.run_id = r["run_id"]  # type: ignore[attr-defined]
    return c


def test_v2_endpoints_expose_findings_report_and_remediation(client):
    rid = client.run_id  # type: ignore[attr-defined]

    runs = client.get("/api/v1/v2-analyzer/runs").json()["runs"]
    assert any(x["run_id"] == rid for x in runs)

    det = client.get(f"/api/v1/v2-analyzer/runs/{rid}").json()
    assert det["manifest"]["qa_status"] == "NOT_QA_APPROVED"
    assert det["manifest"]["mark"] == "MACHINE GENERATED -- BORRADOR, NO APROBADO"
    assert det["human_review_state"]["all_unreviewed"] is True
    assert det["human_review_state"]["forbidden_states_present"] is False

    fnd = client.get(f"/api/v1/v2-analyzer/runs/{rid}/findings").json()
    assert set(fnd) == {"regulatory", "functional", "technical"}
    # cada finding lleva evidencia anclada + provenance + risk + human_state
    for cls in fnd.values():
        for row in cls:
            assert row["human_state"] == "UNREVIEWED"
            assert "anchored_quote" in row["evidence"]
            assert row["provenance"]["extraction_version"]

    ev = client.get(f"/api/v1/v2-analyzer/runs/{rid}/evidence").json()["evidence"]
    assert isinstance(ev, list)

    rem = client.get(f"/api/v1/v2-analyzer/runs/{rid}/remediation").json()["remediation"]
    for x in rem:
        assert x["qa_status"] == "NOT_QA_APPROVED"
        assert "MACHINE GENERATED" in x["mark"]
        assert [l["link"] for l in x["manifest"]["chain"]][:2] == ["finding", "remediation_directive"]

    rep = client.get(f"/api/v1/v2-analyzer/runs/{rid}/report")
    assert rep.status_code == 200
    assert "NO es una declaraci" in rep.text

    assert client.get("/api/v1/v2-analyzer/runs/nope/findings").status_code == 404


def test_v2_analyzer_router_is_registered_in_main_app():
    # extiende Mission Control existente, sin segunda UI
    src = (Path(__file__).parent.parent / "api" / "main.py").read_text()
    assert "v2_analyzer" in src and "v2_analyzer.router" in src
