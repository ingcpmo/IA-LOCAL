"""Autorización de corpus -- familia CORPUS_AUTHORIZATION (plan
W5V2_ARQ_RETOMAR_Y_FINALIZAR.md Bloque 6).

TODO test usa un almacén de decisiones TEMPORAL (via monkeypatch/param) --
nunca el almacén real. `build_qualification_fingerprint` usa `FakeProvider`
(mismo patrón que test_model_qualification_gate.py) para no depender de
Ollama real."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.regulatory import corpus_authorization as ca
from factory.regulatory import model_qualification_gate as mqg
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

DOCS = ("RW-0005", "RW-0006")


class FakeProvider:
    def __init__(self, digest="digest-A", name="modelo-test"):
        self._digest, self._name = digest, name

    @property
    def model_name(self) -> str:
        return self._name

    def generate(self, prompt, *, num_predict=None) -> dict:
        return {}

    def show_digest(self) -> str:
        return self._digest

    def runtime_version(self) -> str:
        return "test-0.0.0"


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


@pytest.fixture()
def tmp_decisions(tmp_path) -> Path:
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _grant_d4_coverage(tmp_decisions, document_ids=DOCS):
    """Firma D4 real sobre `document_ids` en el almacén temporal -- mismo
    patrón propose->confirm que el resto de la fábrica."""
    prop = gov.propose(
        "D4", target_ids=list(document_ids), decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id="test",
        reason="presupuesto de prueba", payload={"max_calls": 10},
        store_file=tmp_decisions)
    conf = gov.confirm(
        prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
        reason="presupuesto de prueba", family_state_hash=prop["family_state_hash"],
        store_file=tmp_decisions)
    return conf["decision_instance_id"]


def test_propose_rejects_without_d4_coverage(tmp_decisions):
    with pytest.raises(ca.CorpusAuthorizationError, match="no tiene cobertura D4"):
        ca.propose_corpus_authorization(
            DOCS, proposed_by_id="claude", decision_store_file=tmp_decisions,
            provider=FakeProvider())


def test_propose_rejects_documents_split_across_two_different_d4_instances(tmp_decisions):
    _grant_d4_coverage(tmp_decisions, ("RW-0005",))
    _grant_d4_coverage(tmp_decisions, ("RW-0006",))
    with pytest.raises(ca.CorpusAuthorizationError, match="una única decisión D4"):
        ca.propose_corpus_authorization(
            DOCS, proposed_by_id="claude", decision_store_file=tmp_decisions,
            provider=FakeProvider())


def test_propose_derives_fingerprint_from_live_state_never_by_hand(tmp_decisions):
    _grant_d4_coverage(tmp_decisions)
    prop = ca.propose_corpus_authorization(
        DOCS, proposed_by_id="claude", decision_store_file=tmp_decisions,
        provider=FakeProvider())
    live = mqg.build_qualification_fingerprint(FakeProvider())
    assert prop["payload"]["run_fingerprint"] == live
    assert prop["payload"]["document_ids"] == list(DOCS)


def test_propose_honestly_declares_the_live_qualification_status(tmp_decisions):
    _grant_d4_coverage(tmp_decisions)
    prop = ca.propose_corpus_authorization(
        DOCS, proposed_by_id="claude", decision_store_file=tmp_decisions,
        provider=FakeProvider())
    live_status = mqg.evaluate_model_qualification(FakeProvider(), persist=False).status
    assert prop["payload"]["qualification_status_at_proposal"] == live_status


def _propose_y_confirmar(tmp_decisions, provider=None):
    _grant_d4_coverage(tmp_decisions)
    prop = ca.propose_corpus_authorization(
        DOCS, proposed_by_id="claude", decision_store_file=tmp_decisions,
        provider=provider or FakeProvider())
    conf = gov.confirm(
        prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
        reason="autorizado", family_state_hash=prop["family_state_hash"],
        store_file=tmp_decisions)
    return prop, conf


def test_apply_succeeds_and_never_launches_anything(tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_decisions)
    result = ca.apply_corpus_authorization(
        DOCS, decision_instance_id=conf["decision_instance_id"],
        decision_store_file=tmp_decisions, provider=FakeProvider())
    assert result["status"] == "AUTHORIZED_AWAITING_RUNNER"
    assert result["document_ids"] == list(DOCS)


def test_apply_rejects_fingerprint_drift_since_proposal(tmp_decisions):
    """El modelo/digest cambio entre proponer y aplicar -- la autorizacion
    no se hereda, hay que re-proponer sobre el estado actual."""
    _, conf = _propose_y_confirmar(tmp_decisions, provider=FakeProvider(digest="digest-A"))
    with pytest.raises(ca.CorpusAuthorizationError, match="ya no coincide"):
        ca.apply_corpus_authorization(
            DOCS, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions, provider=FakeProvider(digest="digest-B"))


def test_apply_rejects_a_decision_that_does_not_cover_this_scope(tmp_decisions):
    _grant_d4_coverage(tmp_decisions)
    with pytest.raises(ca.CorpusAuthorizationError, match="no es la decisión"):
        ca.apply_corpus_authorization(
            DOCS, decision_instance_id="CORPUS_AUTHORIZATION-2026-999",
            decision_store_file=tmp_decisions, provider=FakeProvider())


def test_verify_fingerprint_matches_passes_when_identical(tmp_decisions):
    """Cierre del gap tecnico (docs_plan, 2026-08-26): fingerprint vivo ==
    firmado -> PASS, devuelve el fingerprint vivo."""
    _, conf = _propose_y_confirmar(tmp_decisions)
    live = ca.verify_fingerprint_matches(
        conf["decision_instance_id"], decision_store_file=tmp_decisions, provider=FakeProvider())
    assert live == mqg.build_qualification_fingerprint(FakeProvider())


def test_verify_fingerprint_matches_blocks_when_catalog_sha256_differs(tmp_decisions, monkeypatch):
    """Catalogo cambiado desde la firma -> BLOCK. Se firma con el
    fingerprint LIMPIO primero, y solo DESPUES se simula el drift para la
    verificacion -- si se mockeara antes, la firma y la verificacion
    quedarian identicas por construccion y el test no probaria nada."""
    _, conf = _propose_y_confirmar(tmp_decisions)
    original = mqg.build_qualification_fingerprint

    def _drifted(provider=None):
        fp = dict(original(provider))
        fp["catalog_sha256"] = "0" * 64
        return fp

    monkeypatch.setattr(mqg, "build_qualification_fingerprint", _drifted)
    with pytest.raises(ca.CorpusAuthorizationError, match="ya no coincide"):
        ca.verify_fingerprint_matches(
            conf["decision_instance_id"], decision_store_file=tmp_decisions, provider=FakeProvider())


def test_verify_fingerprint_matches_blocks_when_a_prompt_version_differs(tmp_decisions, monkeypatch):
    """Un solo prompt_version distinto -- no solo catalog_sha256 -- ya
    basta para bloquear (se compara el dict completo del fingerprint)."""
    _, conf = _propose_y_confirmar(tmp_decisions)
    original = mqg.build_qualification_fingerprint

    def _drifted(provider=None):
        fp = dict(original(provider))
        fp["prompt_versions"] = dict(fp["prompt_versions"])
        key = next(iter(fp["prompt_versions"]))
        fp["prompt_versions"][key] = "9.9.9-drift"
        return fp

    monkeypatch.setattr(mqg, "build_qualification_fingerprint", _drifted)
    with pytest.raises(ca.CorpusAuthorizationError, match="ya no coincide"):
        ca.verify_fingerprint_matches(
            conf["decision_instance_id"], decision_store_file=tmp_decisions, provider=FakeProvider())


def test_verify_fingerprint_matches_blocks_when_decision_not_found(tmp_decisions):
    """decision_instance_id inexistente en el almacen -- caso degenerado
    (el resolver ya no deberia devolverlo como covering_instance si no
    existe, pero se verifica igual, fail-closed)."""
    with pytest.raises(ca.CorpusAuthorizationError, match="no se encuentra en el almacén"):
        ca.verify_fingerprint_matches(
            "CORPUS_AUTHORIZATION-2026-999", decision_store_file=tmp_decisions, provider=FakeProvider())


def test_corpus_authorization_is_a_registered_family_and_governed_family():
    families = store.load_families()
    assert "CORPUS_AUTHORIZATION" in families
    assert "CORPUS_AUTHORIZATION" in gov.GOVERNED_FAMILIES


def test_corpus_authorization_event_is_valid():
    assert "corpus_authorization_applied" in aw.VALID_EVENTS
