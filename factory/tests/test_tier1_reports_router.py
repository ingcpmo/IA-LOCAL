"""Tests HTTP -- endpoints /api/v1/layer9/tier1-reports/* (R2.3/D2).

Read-only sobre factory/services/tier1_report_service.py: monta SOLO el
router (auth via API key vive en factory/api/main.py, fuera de este
router -- mismo patrón que test_remediation_packages_router.py) y
monkeypatchea TIER1_REPORTS_BASE a tmp_path para no depender de
informes reales persistidos en disco."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import layer9
from factory.regulatory import tier1_report as t1
from factory.regulatory import tier1_report_writer as writer

BASE = "/api/v1/layer9"
VALID_RUN_ID = "chunked-abcdef012345"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(writer, "TIER1_REPORTS_BASE", tmp_path)
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


def _persist_sample():
    report = t1.Tier1Report(
        document_id="RW-0005", agent_id="fda_part11_agent", run_id=VALID_RUN_ID,
        generated_at="2026-08-11T00:00:00+00:00",
        requirements=[
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(d)", bucket=t1.CONFIRMED,
                                   conclusion="PROVISIONALLY_DOCUMENTED",
                                   review_flags=["SOURCE_PENDING_REVERIFICATION"],
                                   evidence_quote="cita real anclada", page_or_section="p.3"),
        ],
    )
    return writer.persist_tier1_report(report)


def test_list_reports_empty(client):
    resp = client.get(f"{BASE}/tier1-reports")
    assert resp.status_code == 200
    assert resp.json() == {"reports": []}


def test_list_reports_after_persist(client):
    _persist_sample()
    resp = client.get(f"{BASE}/tier1-reports")
    assert resp.status_code == 200
    reports = resp.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["run_id"] == VALID_RUN_ID
    assert reports[0]["document_id"] == "RW-0005"


def test_get_report_json_found(client):
    _persist_sample()
    resp = client.get(f"{BASE}/tier1-reports/{VALID_RUN_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == VALID_RUN_ID
    assert len(body["requirements"]) == 1
    assert body["requirements"][0]["evidence_quote"] == "cita real anclada"


def test_get_report_json_not_found_returns_404(client):
    resp = client.get(f"{BASE}/tier1-reports/chunked-000000000000")
    assert resp.status_code == 404


def test_get_report_markdown_found(client):
    _persist_sample()
    resp = client.get(f"{BASE}/tier1-reports/{VALID_RUN_ID}/markdown")
    assert resp.status_code == 200
    assert "cita real anclada" in resp.text
    assert "borrador asistido" in resp.text.lower()
    assert resp.headers["content-type"].startswith("text/markdown")


def test_get_report_markdown_not_found_returns_404(client):
    resp = client.get(f"{BASE}/tier1-reports/chunked-000000000000/markdown")
    assert resp.status_code == 404


def test_get_report_json_rejects_path_traversal_run_id(client):
    resp = client.get(f"{BASE}/tier1-reports/..%2F..%2Fetc%2Fpasswd")
    # FastAPI/Starlette normaliza el path antes de llegar al handler --
    # nunca debe devolver 200 con contenido ajeno al árbol de informes.
    assert resp.status_code in (404, 400)
