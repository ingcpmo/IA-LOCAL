"""Confirmación gobernada de vigencia regulatoria — familia SOURCE_CURRENCY.

Cierra el hallazgo de la auditoría de firma (2026-08-05): un hash idéntico
prueba que la URL sigue sirviendo lo mismo que se archivó, no que la norma
siga vigente -- por eso el schema de registry.json bloquea
`regulatory_currency_status` a un único valor y por eso, hasta este módulo,
no existía forma alguna de que un humano declarara vigencia real.

TODO test usa un registry.json y un log TEMPORALES (via monkeypatch) --
nunca el almacén real."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.regulatory import source_currency_confirmation as sc
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov
from factory.services import paths as svc_paths

SOURCE_ID = "test_source_x"


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


@pytest.fixture()
def tmp_decisions(tmp_path) -> Path:
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch) -> Path:
    registry = {
        "registry_version": "1.1",
        "sources": [{
            "source_id": SOURCE_ID,
            "canonical_path": "irrelevante",
            "official_source_url": "https://example.gov/x",
            "official_source_description": "fuente de prueba",
            "sha256_original": "a" * 64,
            "sha256_copy": "a" * 64,
            "hashes_match": True,
            "size_bytes": 10,
            "normative_type": "regulation",
            "jurisdiction": "US",
            "local_integrity_status": "PASS",
            "official_origin_status": "VERIFIED",
            "regulatory_currency_status": "pending_reverification",
            "version": "1.0",
            "effective_date": "2020-01-01",
            "supersedes": None,
            "reverification_due": None,
        }],
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(sc, "REGISTRY_FILE", path)
    return path


@pytest.fixture()
def tmp_log(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "source_currency_log.jsonl"
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", path)
    return path


def _log_entry(*, checked_at, comparable=True, matches=True, sha256="a" * 64):
    return {
        "source_id": SOURCE_ID, "checked_at": checked_at,
        "downloaded_sha256": sha256, "governed_sha256_original": "a" * 64,
        "content_matches_governed_copy": matches, "comparable": comparable,
        "reachable": True, "authorized_by_decision": True,
    }


def _write_log(tmp_log, *entries):
    with tmp_log.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def test_propose_rejects_without_any_log_entry(tmp_registry, tmp_log, tmp_decisions):
    with pytest.raises(sc.SourceCurrencyError, match="no tiene ninguna verificación"):
        sc.propose_source_currency_confirmation(
            SOURCE_ID, regulatory_judgment_note="sigue vigente",
            proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_non_comparable_latest_entry(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00", comparable=False, matches=None))
    with pytest.raises(sc.SourceCurrencyError, match="no es comparable=True"):
        sc.propose_source_currency_confirmation(
            SOURCE_ID, regulatory_judgment_note="sigue vigente",
            proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_mismatched_latest_entry(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00", matches=False))
    with pytest.raises(sc.SourceCurrencyError, match="no es comparable=True"):
        sc.propose_source_currency_confirmation(
            SOURCE_ID, regulatory_judgment_note="sigue vigente",
            proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_empty_judgment_note(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00"))
    with pytest.raises(sc.SourceCurrencyError, match="regulatory_judgment_note"):
        sc.propose_source_currency_confirmation(
            SOURCE_ID, regulatory_judgment_note="   ",
            proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_derives_payload_from_latest_entry_never_copied_by_hand(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log,
               _log_entry(checked_at="2026-08-01T00:00:00+00:00", sha256="a" * 64),
               _log_entry(checked_at="2026-08-03T00:00:00+00:00", sha256="a" * 64))
    prop = sc.propose_source_currency_confirmation(
        SOURCE_ID, regulatory_judgment_note="revisado, sigue siendo el texto oficial",
        proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)
    assert prop["payload"]["reviewed_log_checked_at"] == "2026-08-03T00:00:00+00:00"
    assert prop["payload"]["source_id"] == SOURCE_ID
    assert prop["payload"]["governed_sha256_original"] == "a" * 64


def _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions, *, checked_at="2026-08-01T00:00:00+00:00"):
    _write_log(tmp_log, _log_entry(checked_at=checked_at))
    prop = sc.propose_source_currency_confirmation(
        SOURCE_ID, regulatory_judgment_note="revisado, sigue vigente",
        proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)
    conf = gov.confirm(
        prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
        reason="revisado, sigue vigente", family_state_hash=prop["family_state_hash"],
        store_file=tmp_decisions)
    return prop, conf


def test_apply_writes_verified_current_and_leaves_reverification_due_untouched(
        tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    result = sc.apply_source_currency_confirmation(
        SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
        decision_store_file=tmp_decisions)
    assert result["before"] == "pending_reverification"
    assert result["after"] == "verified_current"

    registry = json.loads(tmp_registry.read_text(encoding="utf-8"))
    entry = registry["sources"][0]
    assert entry["regulatory_currency_status"] == "verified_current"
    assert entry["reverification_due"] is None  # NUNCA una cadencia inventada


def test_apply_rejects_a_decision_that_does_not_cover_this_source(
        tmp_registry, tmp_log, tmp_decisions):
    with pytest.raises(sc.SourceCurrencyError, match="no está autorizado"):
        sc.apply_source_currency_confirmation(
            SOURCE_ID, decision_instance_id="SOURCE_CURRENCY-2026-999",
            decision_store_file=tmp_decisions)


def test_apply_rejects_when_evidence_regressed_after_signature(
        tmp_registry, tmp_log, tmp_decisions):
    """Firma sobre una verificacion buena; DESPUES el checker corre de nuevo
    y sale mal. El apply no puede aplicar sobre evidencia superada."""
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions,
                                   checked_at="2026-08-01T00:00:00+00:00")
    _write_log(tmp_log, _log_entry(checked_at="2026-08-02T00:00:00+00:00", matches=False))
    with pytest.raises(sc.SourceCurrencyError, match="ya no es comparable=True"):
        sc.apply_source_currency_confirmation(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_apply_rejects_registry_drift_since_proposal(tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    registry = json.loads(tmp_registry.read_text(encoding="utf-8"))
    registry["sources"][0]["sha256_original"] = "b" * 64
    tmp_registry.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(sc.SourceCurrencyError, match="no coincide con el declarado"):
        sc.apply_source_currency_confirmation(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_apply_rejects_double_apply(tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    sc.apply_source_currency_confirmation(
        SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
        decision_store_file=tmp_decisions)
    with pytest.raises(sc.SourceCurrencyError, match="nada que aplicar"):
        sc.apply_source_currency_confirmation(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_source_currency_is_a_registered_family_and_governed_family():
    families = store.load_families()
    assert "SOURCE_CURRENCY" in families
    assert "SOURCE_CURRENCY" in gov.GOVERNED_FAMILIES
