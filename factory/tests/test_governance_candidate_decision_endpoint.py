"""Tests HTTP -- POST /api/v1/layer9/review/candidates/{rc_id}/decide
(Paquete 1a, VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md).

Mismo patron que test_finding_review_decision_endpoint.py: identidad via
X-Identity-Key (Paquete 2, identity_headers/identity_headers_other de
conftest.py). review_queue.jsonl SIEMPRE aislado (autouse)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import layer9
from factory.layer9 import human_review_queue as hrq

BASE = "/api/v1/layer9"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(layer9.router)
    return TestClient(app)


def _enqueue_candidate(suggested_type="NCR", prior_occurrences=0):
    return hrq.enqueue_governance_candidate_for_review(
        run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
        conclusion="DOCUMENTATION_GAP", suggested_type=suggested_type,
        rationale="fixture de test, no un caso real", prior_occurrences=prior_occurrences,
        agent_id="fda_part11_agent",
    )


def test_confirm_governance_candidate_succeeds(client, isolated_review_queue, identity_headers):
    entry = _enqueue_candidate()
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "confirmed", "human_classification": "NCR"},
                     headers=identity_headers)
    assert r.status_code == 200
    assert r.json()["decision"] == "confirmed"
    assert r.json()["human_classification"] == "NCR"
    stored = hrq.get_entry(entry["rc_id"])
    assert stored["status"] == "confirmed"
    assert stored["reviewer"] == "Cesar"


def test_confirm_can_override_suggested_type(client, isolated_review_queue, identity_headers):
    """El humano confirma un tipo DISTINTO al sugerido por la maquina."""
    entry = _enqueue_candidate(suggested_type="NCR")
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "confirmed", "human_classification": "CAPA"},
                     headers=identity_headers)
    assert r.status_code == 200
    assert r.json()["human_classification"] == "CAPA"


def test_confirm_without_human_classification_is_422(client, isolated_review_queue, identity_headers):
    entry = _enqueue_candidate()
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 422
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_reject_never_requires_classification(client, isolated_review_queue, identity_headers):
    entry = _enqueue_candidate()
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "rejected"}, headers=identity_headers)
    assert r.status_code == 200
    assert hrq.get_entry(entry["rc_id"])["status"] == "rejected"


def test_invalid_decision_value_is_422(client, isolated_review_queue, identity_headers):
    entry = _enqueue_candidate()
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "approved_by_mistake"}, headers=identity_headers)
    assert r.status_code == 422
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_missing_identity_key_is_401(client, isolated_review_queue):
    entry = _enqueue_candidate()
    r = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                     json={"decision": "rejected"})
    assert r.status_code == 401
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_already_decided_candidate_is_409(client, isolated_review_queue, identity_headers, identity_headers_other):
    entry = _enqueue_candidate()
    first = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                         json={"decision": "confirmed", "human_classification": "NCR"},
                         headers=identity_headers)
    assert first.status_code == 200
    second = client.post(f"{BASE}/review/candidates/{entry['rc_id']}/decide",
                          json={"decision": "rejected"}, headers=identity_headers_other)
    assert second.status_code == 409
    stored = hrq.get_entry(entry["rc_id"])
    assert stored["status"] == "confirmed"
    assert stored["reviewer"] == "Cesar"


def test_unknown_rc_id_is_404(client, isolated_review_queue, identity_headers):
    r = client.post(f"{BASE}/review/candidates/candidate-no-existe/decide",
                     json={"decision": "rejected"}, headers=identity_headers)
    assert r.status_code == 404


def test_finding_review_entry_rejected_as_governance_candidate(client, isolated_review_queue, identity_headers):
    """Un finding_review real (distinto entry_type) nunca debe poder
    decidirse por este endpoint -- solo entradas governance_candidate."""
    finding = hrq.enqueue_finding_for_review(
        run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
        page=None, evidence_quote="", conclusion="DOCUMENTATION_GAP",
        review_flags=[], agent_id="fda_part11_agent")
    r = client.post(f"{BASE}/review/candidates/{finding['rc_id']}/decide",
                     json={"decision": "rejected"}, headers=identity_headers)
    assert r.status_code == 404
