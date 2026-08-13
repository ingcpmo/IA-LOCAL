"""R4-T1.0v2 bloque 3 (docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md) --
POST /api/v1/layer9/remediation/directives, vía mínima de captura del
Acto 2. Cero llamadas LLM."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import layer9
from factory.layer9 import human_review_queue as hrq
from factory.services import remediation_directive as rd

BASE = "/api/v1/layer9"
_REAL_ENTRY_ID = "21_CFR_11.10(e)"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


@pytest.fixture()
def isolated_directives(tmp_path, monkeypatch):
    directives_file = tmp_path / "remediation_directives_test.jsonl"
    monkeypatch.setattr(rd, "DIRECTIVES_FILE", directives_file)
    return directives_file


@pytest.fixture()
def fake_document(monkeypatch):
    fixed_path = Path("/fake/RW-TEST.pdf")
    fixed_sha = "a" * 64
    monkeypatch.setattr(rd, "_resolve_document_path", lambda document_id: (fixed_path, fixed_sha))

    class _FakeReader:
        pages = [object()] * 10

    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", lambda path: _FakeReader())
    return fixed_path, fixed_sha


def _enqueue_confirmed(*, conclusion, reviewer="Cesar"):
    entry = hrq.enqueue_finding_for_review(
        run_id="chunked-test", requirement_id=_REAL_ENTRY_ID, document_id="RW-TEST",
        page=None, evidence_quote="", conclusion=conclusion,
        review_flags=[], agent_id="fda_part11_agent",
    )
    hrq.mark_reviewed(entry["rc_id"], "confirmed", reviewer)
    return entry["rc_id"]


def _payload(rc_id, **overrides):
    body = {
        "finding_rc_id": rc_id, "change_type": "ADD",
        "proposed_text": "El SOP debe registrar timestamp de cada cambio critico.",
        "target_location": {"page_start": 3, "page_end": 3, "section": None},
        "regulatory_citation": [_REAL_ENTRY_ID], "rationale": "Cierra la brecha confirmada.",
        "authored_by_id": "Cesar",
    }
    body.update(overrides)
    return body


def test_post_directive_succeeds_for_confirmed_gap(client, isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    r = client.post(f"{BASE}/remediation/directives", json=_payload(rc_id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "SUBMITTED"
    assert body["authored_by_id"] == "Cesar"


def test_post_directive_rejects_supporting_evidence_trigger(client, isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW")
    r = client.post(f"{BASE}/remediation/directives", json=_payload(rc_id))
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "remediation_directive_rejected"


def test_post_directive_rejects_reserved_identity(client, isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    r = client.post(f"{BASE}/remediation/directives", json=_payload(rc_id, authored_by_id="human"))
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_identity"


def test_post_directive_rejects_empty_proposed_text(client, isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    r = client.post(f"{BASE}/remediation/directives", json=_payload(rc_id, proposed_text="   "))
    assert r.status_code == 422


def test_get_directives_lists_created_ones(client, isolated_review_queue, isolated_directives, fake_document):
    rc_id = _enqueue_confirmed(conclusion="DOCUMENTATION_GAP")
    client.post(f"{BASE}/remediation/directives", json=_payload(rc_id))
    r = client.get(f"{BASE}/remediation/directives", params={"finding_rc_id": rc_id})
    assert r.status_code == 200
    assert len(r.json()["directives"]) == 1
