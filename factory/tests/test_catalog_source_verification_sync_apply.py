"""propose_catalog_source_verification_sync / apply_catalog_source_verification_sync
-- R3-T1.2/F0.6 (2026-08-12).

Camino completo real (propose -> confirm -> apply) contra un repo git y
almacenes de decisiones TEMPORALES, nunca contra los reales -- mismo patron
que test_artifact_version_apply.py. Cubre el caso real que motiva esta
funcion: requirements.yaml quedo con source_verification_status=
PENDING_REVERIFICATION congelado tras generarse (2026-07-17), incluso
despues de que la reingesta G3 real (2026-08-07) llevara las fuentes a
LOCAL_CANONICAL_COPY_VERIFIED."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import artifact_version_apply as apply_mod
from factory.core import artifact_version_guard as guard
from factory.services import decision_store_v2 as store
from factory.tests.test_source_lifecycle import _covered_store, _entry

CATALOG_REL = "factory/regulatory/requirement_catalog/requirements.yaml"
REGISTRY_REL = "factory/regulatory/sources/registry.json"

_CATALOG = """\
catalog_version: '1.0'
requirements:
  REQ_A:
    source_id: src_verified
    source_verification_status: PENDING_REVERIFICATION
  REQ_B:
    source_id: src_still_pending
    source_verification_status: PENDING_REVERIFICATION
"""


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path):
    catalog = tmp_path / CATALOG_REL
    catalog.parent.mkdir(parents=True)
    catalog.write_text(_CATALOG, encoding="utf-8")

    registry_path = tmp_path / REGISTRY_REL
    registry_path.parent.mkdir(parents=True)
    verified = _entry(tmp_path, source_id="src_verified", regulatory_currency_status="verified_current")
    still_pending = _entry(tmp_path, source_id="src_still_pending",
                           official_origin_status="FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_2026-01-01")
    registry_path.write_text(json.dumps({"sources": [verified, still_pending]}, ensure_ascii=False),
                             encoding="utf-8")

    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "test", cwd=tmp_path)
    _git("add", CATALOG_REL, REGISTRY_REL, "sources", cwd=tmp_path)
    _git("commit", "-q", "-m", "estado inicial", cwd=tmp_path)
    return tmp_path


@pytest.fixture()
def decisions_file(tmp_path):
    return tmp_path / "decisions_v2.jsonl"


@pytest.fixture()
def covered_store_file(decisions_file, tmp_path):
    """Mismo almacen unico que decisions_file (W5 V2 G1: un solo almacen de
    decisiones para D1/D2/ARTIFACT_VERSION/etc en produccion real) -- se
    le APPENDEA el registro D1 de cobertura de fuentes, en vez de vivir en
    un archivo separado como en test_source_lifecycle.py (ese si aisla
    D1 de todo lo demas a proposito; aqui necesitamos que
    apply_catalog_source_verification_sync() vea AMBOS tipos de decision
    en el mismo store, como en produccion)."""
    d1_store = _covered_store(tmp_path, ["src_verified", "src_still_pending"], name="d1_tmp.jsonl")
    with open(d1_store, encoding="utf-8") as src, open(decisions_file, "a", encoding="utf-8") as dst:
        dst.write(src.read())
    return decisions_file


@pytest.fixture(autouse=True)
def _isolate_audit(monkeypatch, tmp_path):
    from factory.core import audit_writer as aw
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


def test_propose_computes_changes_from_live_registry(repo, decisions_file, covered_store_file):
    proposal = apply_mod.propose_catalog_source_verification_sync(
        to_version="1.1", change_reason="sync G3", proposed_by_id="claude_code_session_f06",
        registry_path=repo / REGISTRY_REL, repo=repo, decision_store_file=decisions_file)
    assert proposal["decision_origin"] == "agent_proposed"
    assert proposal["payload"]["sync_type"] == "source_verification_status"
    assert proposal["payload"]["source_verification_changes"] == {
        "REQ_A": {"from": "PENDING_REVERIFICATION", "to": "LOCAL_CANONICAL_COPY_VERIFIED"},
    }


def test_full_propose_confirm_apply_cycle_writes_only_the_verified_requirement(
        repo, decisions_file, covered_store_file):
    proposal = apply_mod.propose_catalog_source_verification_sync(
        to_version="1.1", change_reason="sync G3", proposed_by_id="claude_code_session_f06",
        registry_path=repo / REGISTRY_REL, repo=repo, decision_store_file=decisions_file)

    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])

    record = apply_mod.apply_catalog_source_verification_sync(
        "1.1", decision_instance_id=confirmed["decision_instance_id"],
        registry_path=repo / REGISTRY_REL, repo=repo, decision_store_file=decisions_file,
        versions_store_file=repo / "factory/registry/artifact_versions.jsonl")
    assert record["version"] == "1.1"
    assert record["source_verification_changes"] == {
        "REQ_A": {"from": "PENDING_REVERIFICATION", "to": "LOCAL_CANONICAL_COPY_VERIFIED"},
    }

    new_text = (repo / CATALOG_REL).read_text(encoding="utf-8")
    assert "REQ_A:\n    source_id: src_verified\n    source_verification_status: LOCAL_CANONICAL_COPY_VERIFIED" in new_text
    assert "REQ_B:\n    source_id: src_still_pending\n    source_verification_status: PENDING_REVERIFICATION" in new_text
    assert "catalog_version: '1.1'" in new_text


def test_apply_rejects_if_registry_drifted_since_proposal(repo, decisions_file, covered_store_file):
    """Si el registry cambia entre proponer y aplicar (otra reingesta, una
    revocacion), aplicar debe fallar -- nunca escribir una sincronizacion
    calculada sobre un estado que ya no es el vivo."""
    proposal = apply_mod.propose_catalog_source_verification_sync(
        to_version="1.1", change_reason="sync G3", proposed_by_id="claude_code_session_f06",
        registry_path=repo / REGISTRY_REL, repo=repo, decision_store_file=decisions_file)

    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])

    # el registry cambia DESPUES de proponer -- p.ej. src_still_pending
    # tambien se verifica en una reingesta posterior, sin re-proponer.
    reg_path = repo / REGISTRY_REL
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    data["sources"][1]["regulatory_currency_status"] = "verified_current"
    reg_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="registry.json cambió"):
        apply_mod.apply_catalog_source_verification_sync(
            "1.1", decision_instance_id=confirmed["decision_instance_id"],
            registry_path=reg_path, repo=repo, decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_apply_rejects_a_plain_version_bump_decision(repo, decisions_file, covered_store_file):
    """Una decision de bump SIMPLE (propose_artifact_version_change, sin
    sync_type) nunca debe poder aplicarse con esta funcion -- son dos
    transiciones distintas, aunque el mismo decision_instance_id pudiera
    coincidir en version."""
    from factory.services import decision_store_v2 as _store
    plain_bump_payload = {
        "artifact_path": CATALOG_REL, "artifact_hash_before": "x", "from_version": "1.0",
        "to_version": "1.1", "expected_hash_after": "x", "change_reason": "bump simple",
    }
    record = _store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[CATALOG_REL],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="cesar", approved_by_display_name="Cesar",
        decision_instance_id="ARTIFACT_VERSION-2026-777", store_file=decisions_file,
        reason="bump simple", payload=plain_bump_payload)
    _store.append_record(record, store_file=decisions_file, emit_audit=False)

    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no es una propuesta de sincronización"):
        apply_mod.apply_catalog_source_verification_sync(
            "1.1", decision_instance_id="ARTIFACT_VERSION-2026-777",
            registry_path=repo / REGISTRY_REL, repo=repo, decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")
