"""Confirmación gobernada de segunda observación real de origen — familia
SOURCE_ORIGIN_VERIFICATION (G3, DEC-B).

Caso real que motiva este módulo: `ecfr_21cfr_part11`/`ecfr_21cfr_part211`
quedan en ámbar `FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE` tras su
re-gobernanza (cambio de tipo de artefacto) y ningún mecanismo existente
podía promoverlas -- ver docstring de `source_origin_verification.py`.

TODO test usa un registry.json y un log TEMPORALES (via monkeypatch) --
nunca el almacén real."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.regulatory import source_origin_verification as sov
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov
from factory.services import paths as svc_paths

SOURCE_ID = "test_source_x"
AMBER = "FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE"


@pytest.fixture(autouse=True)
def _aislado(tmp_path, monkeypatch):
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


@pytest.fixture()
def tmp_decisions(tmp_path) -> Path:
    path = tmp_path / "decisions_v2.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _registry_payload(*, official_origin_status=AMBER):
    return {
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
            "official_origin_status": official_origin_status,
            "regulatory_currency_status": "pending_reverification",
            "version": "1.0",
            "effective_date": "2020-01-01",
            "supersedes": None,
            "reverification_due": None,
        }],
    }


@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry_payload()), encoding="utf-8")
    monkeypatch.setattr(sov, "REGISTRY_FILE", path)
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


def test_propose_rejects_when_live_status_is_not_the_first_ingestion_amber(
        tmp_path, monkeypatch, tmp_log, tmp_decisions):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(_registry_payload(official_origin_status="VERIFIED_AGAINST_PRIOR_KNOWN_HASH_x")),
                    encoding="utf-8")
    monkeypatch.setattr(sov, "REGISTRY_FILE", path)
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00"))
    with pytest.raises(sov.SourceOriginVerificationError, match="no está en el ámbar"):
        sov.propose_source_origin_verification(
            SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_without_any_log_entry(tmp_registry, tmp_log, tmp_decisions):
    with pytest.raises(sov.SourceOriginVerificationError, match="no tiene ninguna verificación"):
        sov.propose_source_origin_verification(
            SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_non_comparable_latest_entry(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00", comparable=False, matches=None))
    with pytest.raises(sov.SourceOriginVerificationError, match="no hay segunda observación real"):
        sov.propose_source_origin_verification(
            SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_rejects_mismatched_latest_entry(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log, _log_entry(checked_at="2026-08-01T00:00:00+00:00", matches=False))
    with pytest.raises(sov.SourceOriginVerificationError, match="no hay segunda observación real"):
        sov.propose_source_origin_verification(
            SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)


def test_propose_derives_payload_from_latest_entry_never_copied_by_hand(tmp_registry, tmp_log, tmp_decisions):
    _write_log(tmp_log,
               _log_entry(checked_at="2026-08-01T00:00:00+00:00", sha256="a" * 64),
               _log_entry(checked_at="2026-08-03T00:00:00+00:00", sha256="a" * 64))
    prop = sov.propose_source_origin_verification(
        SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)
    assert prop["payload"]["reviewed_log_checked_at"] == "2026-08-03T00:00:00+00:00"
    assert prop["payload"]["source_id"] == SOURCE_ID
    assert prop["payload"]["governed_sha256_original"] == "a" * 64
    assert prop["payload"]["prior_official_origin_status"] == AMBER


def _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions, *, checked_at="2026-08-01T00:00:00+00:00"):
    _write_log(tmp_log, _log_entry(checked_at=checked_at))
    prop = sov.propose_source_origin_verification(
        SOURCE_ID, proposed_by_id="layer8_agent", decision_store_file=tmp_decisions)
    conf = gov.confirm(
        prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
        reason="segunda reingesta real, coincide con el origen", family_state_hash=prop["family_state_hash"],
        store_file=tmp_decisions)
    return prop, conf


def test_apply_writes_verified_against_prior_known_hash(tmp_registry, tmp_log, tmp_decisions):
    from datetime import datetime, timezone
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    result = sov.apply_source_origin_verification(
        SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
        decision_store_file=tmp_decisions, now=datetime(2026, 8, 7, tzinfo=timezone.utc))
    assert result["before"] == AMBER
    assert result["after"] == "VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-08-07_REVERIFICATION"

    registry = json.loads(tmp_registry.read_text(encoding="utf-8"))
    entry = registry["sources"][0]
    assert entry["official_origin_status"] == "VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-08-07_REVERIFICATION"
    # nunca toca otros campos del ciclo de vida
    assert entry["regulatory_currency_status"] == "pending_reverification"
    assert entry["reverification_due"] is None


def test_apply_rejects_a_decision_that_does_not_cover_this_source(
        tmp_registry, tmp_log, tmp_decisions):
    with pytest.raises(sov.SourceOriginVerificationError, match="no está autorizado"):
        sov.apply_source_origin_verification(
            SOURCE_ID, decision_instance_id="SOURCE_ORIGIN_VERIFICATION-2026-999",
            decision_store_file=tmp_decisions)


def test_apply_rejects_when_evidence_regressed_after_signature(
        tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions,
                                   checked_at="2026-08-01T00:00:00+00:00")
    _write_log(tmp_log, _log_entry(checked_at="2026-08-02T00:00:00+00:00", matches=False))
    with pytest.raises(sov.SourceOriginVerificationError, match="ya no es comparable=True"):
        sov.apply_source_origin_verification(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_apply_rejects_registry_sha_drift_since_proposal(tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    registry = json.loads(tmp_registry.read_text(encoding="utf-8"))
    registry["sources"][0]["sha256_original"] = "b" * 64
    tmp_registry.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(sov.SourceOriginVerificationError, match="no coincide con el declarado"):
        sov.apply_source_origin_verification(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_apply_rejects_origin_status_drift_since_proposal(tmp_registry, tmp_log, tmp_decisions):
    """Otro camino ya promovio el origen (o lo cambio) entre proponer y aplicar."""
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    registry = json.loads(tmp_registry.read_text(encoding="utf-8"))
    registry["sources"][0]["official_origin_status"] = "VERIFIED_AGAINST_PRIOR_KNOWN_HASH_manual"
    tmp_registry.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(sov.SourceOriginVerificationError, match="ya no coincide con el declarado"):
        sov.apply_source_origin_verification(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_apply_rejects_double_apply(tmp_registry, tmp_log, tmp_decisions):
    _, conf = _propose_y_confirmar(tmp_registry, tmp_log, tmp_decisions)
    sov.apply_source_origin_verification(
        SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
        decision_store_file=tmp_decisions)
    with pytest.raises(sov.SourceOriginVerificationError, match="ya no coincide con el declarado"):
        sov.apply_source_origin_verification(
            SOURCE_ID, decision_instance_id=conf["decision_instance_id"],
            decision_store_file=tmp_decisions)


def test_source_origin_verification_is_a_registered_family_and_governed_family():
    families = store.load_families()
    assert "SOURCE_ORIGIN_VERIFICATION" in families
    assert "SOURCE_ORIGIN_VERIFICATION" in gov.GOVERNED_FAMILIES


def test_source_origin_verification_event_is_valid():
    assert "regulatory_source_origin_verified" in aw.VALID_EVENTS
