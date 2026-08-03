"""Tests -- factory/regulatory/human_source_regovernance.py (G3, 2026-08-03).

Hermano de human_source_update.py (solo URL/hash-original/descripcion) y de
human_source_registration.py (solo fuentes NUEVAS): este cubre re-gobernar
el ARTEFACTO CANONICO de una fuente ya existente (canonical_path cambia,
p.ej. ecfr_21cfr_part11 de TEXT a XML).

Garantias fijadas:
  - propose_/confirm_ NUNCA escriben registry.json ni copian ficheros
  - apply_ es la UNICA funcion con permiso de escritura
  - propose_ exige que el source_id YA EXISTA (opuesto de human_source_registration)
  - propose_ rechaza un sha256_original identico al ya gobernado (no hay
    artefacto distinto que re-ingerir)
  - apply_ exige human_confirmed+approve
  - apply_ exige que la fuente este REGULATORY_SOURCE_UNVERIFIED o
    ARTIFACT_TYPE_MISMATCH -- mismo guard fail-closed que human_source_update,
    nunca re-gobierna una fuente sana
  - hashes_match se DEMUESTRA: un sha256_original que no cuadra con el
    fichero real aborta la re-gobernanza
  - regulatory_currency_status nunca cambia (sigue pending_reverification)
  - derived_artifacts se reinicia a [] (los del archivo viejo ya no aplican)
  - jurisdiction/normative_type/supersedes/reverification_due se preservan
    de la entrada existente, nunca se re-declaran
  - la entrada resultante valida contra el schema
  - un fallo despues de validar no deja fichero copiado ni registry a medias
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import human_source_regovernance as hsrg
from factory.services import paths as svc_paths

SOURCE_ID = "ecfr_21cfr_part11"
OLD_CONTENT = b"PART 11 TEXT (copia de prueba, formato antiguo)\n"
OLD_SHA256 = hashlib.sha256(OLD_CONTENT).hexdigest()
NEW_CONTENT = b"<?xml version='1.0'?><DIV5 N='11'>PART 11 XML (copia de prueba)</DIV5>\n"
NEW_SHA256 = hashlib.sha256(NEW_CONTENT).hexdigest()


def _existing_entry(**overrides) -> dict:
    base = {
        "source_id": SOURCE_ID,
        "original_path": "factory/regulatory/sources/incoming/old.txt",
        "canonical_path": f"factory/regulatory/sources/sha256/{OLD_SHA256}/old.txt",
        "official_source_url": "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11",
        "official_source_description": "eCFR Title 21 Part 11 (texto completo, viejo)",
        "sha256_original": OLD_SHA256,
        "sha256_copy": OLD_SHA256,
        "hashes_match": True,
        "size_bytes": len(OLD_CONTENT),
        "normative_type": "regulation",
        "jurisdiction": "US",
        "local_integrity_status": "PASS",
        "official_origin_status": "VERIFIED_AGAINST_PRIOR_KNOWN_HASH_2026-07-06_INGESTION",
        "regulatory_currency_status": "pending_reverification",
        "copied_at": "2026-07-17T19:32:45.681367+00:00",
        "derived_artifacts": [{
            "extractor": "old_extractor", "extractor_version": "0.1",
            "source_sha256": OLD_SHA256,
            "artifact_path": "factory/regulatory/sources/derived/old/artifact.json",
            "artifact_sha256": "a" * 64,
        }],
        "version": "NO_DISPONIBLE (eCFR es texto consolidado, sin edicion discreta declarada)",
        "effective_date": "NO_DISPONIBLE (eCFR es texto vivo continuamente actualizado)",
        "supersedes": None,
        "reverification_due": None,
    }
    base.update(overrides)
    return base


def _declared(**overrides) -> dict:
    base = {
        "official_source_url": "https://www.ecfr.gov/api/versioner/v1/full/2026-07-01/title-21.xml?part=11",
        "official_source_description": "eCFR Title 21 Part 11 (snapshot XML de la API versioner, fecha fijada 2026-07-01)",
        "sha256_original": NEW_SHA256,
        "official_origin_status": "FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE",
        "version": "NO_DISPONIBLE (eCFR es texto consolidado, sin edicion discreta declarada)",
        "effective_date": "NO_DISPONIBLE (eCFR es texto vivo continuamente actualizado)",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def regovernance_env(tmp_path, monkeypatch, isolated_decisions):
    registry = {"registry_version": "1.1", "sources": [_existing_entry()]}
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(hsrg, "SOURCES_REGISTRY_FILE", registry_file)

    store_dir = tmp_path / "sha256"
    monkeypatch.setattr(hsrg, "SOURCES_STORE_DIR", store_dir)

    currency_log_file = tmp_path / "source_currency_log.jsonl"
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", currency_log_file)

    canonical_file = tmp_path / "incoming" / "OFFICIAL_ECFR_21CFR_part11_new.xml"
    canonical_file.parent.mkdir(parents=True, exist_ok=True)
    canonical_file.write_bytes(NEW_CONTENT)

    yield registry_file, store_dir, canonical_file, currency_log_file


def _write_artifact_type_mismatch_history(currency_log_file, source_id=SOURCE_ID, n=3):
    entries = [
        {"source_id": source_id, "checked_at": f"2026-08-0{i}T00:00:00+00:00",
         "reachable": True, "comparable": False}
        for i in range(1, n + 1)
    ]
    currency_log_file.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )


def _confirmed(canonical_file, declared=None, source_id=SOURCE_ID):
    proposal = hsrg.propose_source_regovernance(
        source_id, canonical_file, declared or _declared(), rationale="re-gobernanza a XML",
    )
    return hsrg.confirm_source_regovernance(proposal["decision_id"], confirmed_by="Cesar")


# --- propose_ / confirm_ no escriben ---------------------------------------

def test_propose_writes_nothing(regovernance_env):
    registry_file, store_dir, canonical_file, _ = regovernance_env
    before = registry_file.read_text(encoding="utf-8")
    hsrg.propose_source_regovernance(SOURCE_ID, canonical_file, _declared(), rationale="x")
    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_confirm_writes_nothing(regovernance_env):
    registry_file, store_dir, canonical_file, _ = regovernance_env
    proposal = hsrg.propose_source_regovernance(SOURCE_ID, canonical_file, _declared(), rationale="x")
    before = registry_file.read_text(encoding="utf-8")
    hsrg.confirm_source_regovernance(proposal["decision_id"], confirmed_by="Cesar")
    assert registry_file.read_text(encoding="utf-8") == before
    assert not store_dir.exists()


def test_propose_rejects_unknown_source_id(regovernance_env):
    _, _, canonical_file, _ = regovernance_env
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.propose_source_regovernance("no_existe", canonical_file, _declared(), rationale="x")


def test_propose_rejects_identical_hash(regovernance_env):
    _, _, canonical_file, _ = regovernance_env
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.propose_source_regovernance(
            SOURCE_ID, canonical_file, _declared(sha256_original=OLD_SHA256), rationale="x",
        )


def test_propose_rejects_unknown_field(regovernance_env):
    _, _, canonical_file, _ = regovernance_env
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.propose_source_regovernance(
            SOURCE_ID, canonical_file, {**_declared(), "canonical_path": "x"}, rationale="x",
        )


# --- apply_ guard ------------------------------------------------------------

def test_apply_rejects_agent_proposed_without_confirmation(regovernance_env):
    _, _, canonical_file, currency_log_file = regovernance_env
    _write_artifact_type_mismatch_history(currency_log_file)
    proposal = hsrg.propose_source_regovernance(SOURCE_ID, canonical_file, _declared(), rationale="x")
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.apply_source_regovernance(proposal["decision_id"])


def test_apply_rejects_healthy_source_even_with_valid_confirmation(regovernance_env):
    """Sin historial de mismatch/enlace roto -- apply_ nunca escribe, aunque
    la decision este human_confirmed+approve."""
    _, _, canonical_file, _ = regovernance_env
    confirmation = _confirmed(canonical_file)
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.apply_source_regovernance(confirmation["decision_id"])


def test_apply_rejects_hash_mismatch(regovernance_env):
    _, _, canonical_file, currency_log_file = regovernance_env
    _write_artifact_type_mismatch_history(currency_log_file)
    confirmation = _confirmed(canonical_file, declared=_declared(sha256_original="b" * 64))
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.apply_source_regovernance(confirmation["decision_id"])


# --- apply_ camino de exito ---------------------------------------------------

def test_apply_succeeds_for_artifact_type_mismatch_source(regovernance_env):
    registry_file, store_dir, canonical_file, currency_log_file = regovernance_env
    _write_artifact_type_mismatch_history(currency_log_file)
    confirmation = _confirmed(canonical_file)

    result = hsrg.apply_source_regovernance(confirmation["decision_id"])

    assert result["source_id"] == SOURCE_ID
    entry = result["entry"]
    assert entry["sha256_original"] == NEW_SHA256
    assert entry["sha256_copy"] == NEW_SHA256
    assert entry["canonical_path"].endswith(f"{NEW_SHA256}/{canonical_file.name}")
    assert entry["derived_artifacts"] == []
    assert entry["regulatory_currency_status"] == "pending_reverification"
    # Preservados de la entrada existente, nunca re-declarados:
    assert entry["jurisdiction"] == "US"
    assert entry["normative_type"] == "regulation"
    assert entry["supersedes"] is None
    assert entry["reverification_due"] is None

    stored_file = store_dir / NEW_SHA256 / canonical_file.name
    assert stored_file.read_bytes() == NEW_CONTENT

    updated_registry = json.loads(registry_file.read_text(encoding="utf-8"))
    assert updated_registry["sources"][0]["sha256_original"] == NEW_SHA256


def test_apply_immutable_store_collision_aborts(regovernance_env):
    _, store_dir, canonical_file, currency_log_file = regovernance_env
    _write_artifact_type_mismatch_history(currency_log_file)
    # Un fichero YA existe en la ruta destino con contenido DISTINTO.
    collision_dir = store_dir / NEW_SHA256
    collision_dir.mkdir(parents=True)
    (collision_dir / canonical_file.name).write_bytes(b"contenido corrupto, no es el real")

    confirmation = _confirmed(canonical_file)
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.apply_source_regovernance(confirmation["decision_id"])


def test_apply_writes_exactly_one_audit_event(regovernance_env, isolated_audit):
    _, _, canonical_file, currency_log_file = regovernance_env
    _write_artifact_type_mismatch_history(currency_log_file)
    confirmation = _confirmed(canonical_file)
    hsrg.apply_source_regovernance(confirmation["decision_id"])

    from factory.core import audit_writer as aw
    lines = aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in lines]
    regoverned = [e for e in events if e.get("event_type") == "regulatory_source_regoverned"]
    assert len(regoverned) == 1
    assert regoverned[0]["data"]["source_id"] == SOURCE_ID


def test_apply_rejects_unknown_decision_id(regovernance_env):
    with pytest.raises(hsrg.HumanSourceRegovernanceError):
        hsrg.apply_source_regovernance("no-existe")
