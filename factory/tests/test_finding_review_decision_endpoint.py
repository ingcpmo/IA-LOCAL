"""Tests HTTP -- POST /api/v1/layer9/review/findings/{rc_id}/decide
(R3-T1.2/F0.4, 2026-08-12).

Hallazgo real que motiva este endpoint: /review/{rc_id}/approve|reject ya
existian pero llaman a get_rc()/confirm_rc() (release_candidate_builder.py),
que buscan un rc_manifest.json real -- una entrada de finding_review
(enqueue_finding_for_review(), rc_id sintetico) NUNCA tiene uno, asi que esos
endpoints 404 antes de llegar a mark_reviewed(): no habia forma de decidir
sobre un finding via HTTP. review_queue.jsonl SIEMPRE aislado
(conftest.py::isolated_review_queue, autouse).

Paquete 2 (hallazgo M, 2026-08-19): `reviewer` ya NO viaja en el body -- el
backend lo resuelve desde `X-Identity-Key` (`identity_headers`/
`identity_headers_other`, fixtures de conftest.py). `test_reserved_identity_is_422`
se repropuso: antes probaba que un nombre reservado en el body fallaba
(422); ya no es posible mandar un nombre en el body, asi que el equivalente
real es que la peticion SIN identidad autenticada (401) tampoco decide
nada."""
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


def _enqueue_sample(candidates=None, conclusion="PROVISIONAL_GAP"):
    return hrq.enqueue_finding_for_review(
        run_id="chunked-test", requirement_id="21_CFR_11.10(d)", document_id="RW-TEST",
        page=12, evidence_quote="cita real", conclusion=conclusion,
        review_flags=["ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE"], agent_id="fda_part11_agent",
        candidates=candidates,
    )


def test_confirm_finding_review_succeeds(client, isolated_review_queue, identity_headers):
    entry = _enqueue_sample()
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 200
    assert r.json()["decision"] == "confirmed"
    stored = hrq.get_entry(entry["rc_id"])
    assert stored["status"] == "confirmed"
    assert stored["reviewer"] == "Cesar"


def test_confirm_with_candidate_evidence_persists_page_and_quote(client, isolated_review_queue, identity_headers):
    # SUPPORTING_EVIDENCE_UNDER_REVIEW: la UNICA conclusion donde "confirmar"
    # significa "esta cita sustenta el requisito" -- confirmed_quote aplica
    # y se exige (R3-T1.8 bloque 1).
    entry = _enqueue_sample(conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW", candidates=[
        {"chunk_index": 3, "page_start": 45, "page_end": 46, "bm25_rank": 9,
         "embedding_rank": 4, "fusion_rank": 2, "excerpt": "texto real del candidato"},
    ])
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed",
                           "confirmed_page": 45, "confirmed_quote": "texto real del candidato"},
                     headers=identity_headers)
    assert r.status_code == 200
    stored = hrq.get_entry(entry["rc_id"])
    assert stored["human_confirmed_evidence"]["page"] == 45
    assert stored["human_confirmed_evidence"]["quote"] == "texto real del candidato"
    assert stored["human_confirmed_evidence"]["confirmed_by"] == "Cesar"


def test_confirm_evidence_conclusion_without_quote_is_422(client, isolated_review_queue, identity_headers):
    """R3-T1.8 bloque 1.2: SUPPORTING_EVIDENCE_UNDER_REVIEW exige la cita
    real -- confirmar sin ella no tiene sentido (¿que evidencia se esta
    confirmando?) y quedaria como texto libre sin valor para el Golden
    Dataset."""
    entry = _enqueue_sample(conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW")
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "confirmed_quote_required"
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_confirm_blocked_conclusion_with_free_text_quote_is_422(client, isolated_review_queue, identity_headers):
    """R3-T1.8 bloque 1.2: el caso real que motivo esta corrida --
    EVALUATION_INCOMPLETE (ausencia/bloqueo, NUNCA evidencia observada) no
    puede aceptar texto libre en confirmed_quote (el caso real:
    quote='mejora' en la entrada de validacion de R3-T1.7 -- un dato sin
    sentido, ahora bloqueado en el origen)."""
    entry = _enqueue_sample(conclusion="EVALUATION_INCOMPLETE")
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed", "confirmed_quote": "mejora"},
                     headers=identity_headers)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "confirmed_quote_not_applicable"
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_confirm_blocked_conclusion_without_quote_succeeds(client, isolated_review_queue, identity_headers):
    """Confirmar EVALUATION_INCOMPLETE sin cita (el uso correcto: aceptar
    el bloqueo/ausencia) sigue funcionando -- la validacion nueva nunca
    bloquea el caso correcto, solo el mal uso del campo."""
    entry = _enqueue_sample(conclusion="EVALUATION_INCOMPLETE")
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 200
    assert hrq.get_entry(entry["rc_id"])["status"] == "confirmed"


def test_reject_never_requires_quote_regardless_of_conclusion(client, isolated_review_queue, identity_headers):
    """Rechazar nunca exige (ni prohibe) confirmed_quote, sin importar la
    conclusion -- la validacion solo aplica a decision='confirmed'."""
    entry = _enqueue_sample(conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW")
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "rejected"}, headers=identity_headers)
    assert r.status_code == 200


def test_reject_finding_review_succeeds(client, isolated_review_queue, identity_headers):
    entry = _enqueue_sample()
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "rejected"}, headers=identity_headers)
    assert r.status_code == 200
    assert hrq.get_entry(entry["rc_id"])["status"] == "rejected"


def test_missing_identity_key_is_401(client, isolated_review_queue):
    """Paquete 2 (hallazgo M): sin X-Identity-Key no hay forma de decidir --
    reemplaza el viejo test de nombre reservado en el body (ya no existe
    ese campo). El registro sigue pending: una peticion sin identidad
    autenticada nunca decide nada."""
    entry = _enqueue_sample()
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"})
    assert r.status_code == 401
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_unknown_identity_key_is_401(client, isolated_review_queue):
    entry = _enqueue_sample()
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "confirmed"},
                     headers={"X-Identity-Key": "una-key-que-no-esta-registrada"})
    assert r.status_code == 401
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_invalid_decision_value_is_422(client, isolated_review_queue, identity_headers):
    entry = _enqueue_sample()
    r = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                     json={"decision": "approved_by_mistake"}, headers=identity_headers)
    assert r.status_code == 422
    assert hrq.get_entry(entry["rc_id"])["status"] == "pending"


def test_already_decided_finding_is_409(client, isolated_review_queue, identity_headers, identity_headers_other):
    """La segunda peticion viene de una identidad autenticada DISTINTA
    (`identity_headers_other` -> 'OtroRevisor') -- ni siquiera una segunda
    persona real puede sobrescribir la primera decision."""
    entry = _enqueue_sample()
    first = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                         json={"decision": "confirmed"}, headers=identity_headers)
    assert first.status_code == 200
    second = client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                          json={"decision": "rejected"}, headers=identity_headers_other)
    assert second.status_code == 409
    # la segunda decision NUNCA sobrescribe la primera
    stored = hrq.get_entry(entry["rc_id"])
    assert stored["status"] == "confirmed"
    assert stored["reviewer"] == "Cesar"


def test_unknown_rc_id_is_404(client, isolated_review_queue, identity_headers):
    r = client.post(f"{BASE}/review/findings/rc-no-existe/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 404


def test_real_rc_id_rejected_as_finding_review(client, isolated_review_queue, identity_headers):
    """Un RC real (entry_type distinto/ausente) nunca debe poder decidirse
    por este endpoint -- solo entradas de finding_review."""
    hrq.enqueue("rc-real-001", "some_project", {"version": "v1.0"})
    r = client.post(f"{BASE}/review/findings/rc-real-001/decide",
                     json={"decision": "confirmed"}, headers=identity_headers)
    assert r.status_code == 404


def test_one_audit_event_per_decision(client, isolated_review_queue, monkeypatch, identity_headers):
    events = []
    monkeypatch.setattr(hrq, "write_event", lambda *a, **k: events.append(a[0]))
    entry = _enqueue_sample()
    events.clear()  # descarta el evento de enqueue, solo interesa la decision
    client.post(f"{BASE}/review/findings/{entry['rc_id']}/decide",
                json={"decision": "confirmed"}, headers=identity_headers)
    assert events.count("finding_superseded") == 0
    # mark_reviewed() escribe "rc_reviewed" -- un solo evento por decision
    assert events == ["rc_reviewed"]
