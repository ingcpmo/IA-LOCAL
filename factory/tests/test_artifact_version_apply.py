"""apply_catalog_version_bump — W5 V2 G4c.

`artifact_version_guard` mide la invariante; este modulo es el UNICO punto
que escribe. Cada test prueba una de las condiciones fail-closed antes de
tocar disco, y el camino de exito verifica los TRES efectos juntos: el
archivo bumpeado, el `version_record` con `approved_by_decision`, y la copia
historica congelada desde HEAD (nunca desde el archivo vivo).
"""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import artifact_version_apply as apply_mod
from factory.core import artifact_version_guard as guard
from factory.services import decision_store_v2 as store

CATALOG_REL = "factory/regulatory/requirement_catalog/requirements.yaml"

_MINIMAL_CATALOG = """\
catalog_version: '1.0'
generated_at: '2026-07-29T00:00:00+00:00'
requirements: {}
"""


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path):
    """Repo git real, con el catalogo minimo commiteado en HEAD."""
    catalog = tmp_path / CATALOG_REL
    catalog.parent.mkdir(parents=True)
    catalog.write_text(_MINIMAL_CATALOG, encoding="utf-8")

    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "test", cwd=tmp_path)
    _git("add", CATALOG_REL, cwd=tmp_path)
    _git("commit", "-q", "-m", "catalogo inicial", cwd=tmp_path)
    return tmp_path


@pytest.fixture()
def decisions_file(tmp_path):
    return tmp_path / "decisions_v2.jsonl"


@pytest.fixture(autouse=True)
def _isolate_audit(monkeypatch, tmp_path):
    from factory.core import audit_writer as aw
    monkeypatch.setattr(aw, "AUDIT_FILE", tmp_path / "audit" / "factory_audit.jsonl")
    monkeypatch.setattr(aw, "_last_entry_hash", None)


def _confirmed_artifact_version_decision(decisions_file, artifact_id, *, iid="ARTIFACT_VERSION-2026-001"):
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[artifact_id],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="cesar", approved_by_display_name="Cesar",
        decision_instance_id=iid, store_file=decisions_file, reason="bump 1.0->2.0")
    store.append_record(record, store_file=decisions_file, emit_audit=False)
    return record["decision_instance_id"]


def _proposed_only_decision(decisions_file, artifact_id, *, iid="ARTIFACT_VERSION-2026-002"):
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[artifact_id],
        decision="APPROVE", decision_origin="agent_proposed",
        proposed_by_id="layer8_agent",
        decision_instance_id=iid, store_file=decisions_file, reason="propuesta sin firmar")
    store.append_record(record, store_file=decisions_file, emit_audit=False)
    return record["decision_instance_id"]


# ---------------------------------------------------------------------------
# Fail-closed: nada de esto debe tocar el disco
# ---------------------------------------------------------------------------

def test_no_decision_at_all_raises_and_touches_nothing(repo, decisions_file):
    before = (repo / CATALOG_REL).read_text(encoding="utf-8")
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no está autorizado"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id="ARTIFACT_VERSION-2026-999",
            repo=repo, decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")
    assert (repo / CATALOG_REL).read_text(encoding="utf-8") == before
    assert not (repo / "factory/registry/artifact_versions.jsonl").exists()


def test_only_a_proposal_never_authorizes(repo, decisions_file):
    artifact_id = CATALOG_REL
    iid = _proposed_only_decision(decisions_file, artifact_id)
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no está autorizado"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_a_decision_id_that_does_not_cover_this_artifact_is_rejected(repo, decisions_file):
    """Existe una decisión ACTIVE y confirmada, pero para OTRO artifact_id --
    covering_instances no la incluye, así que no vale como autorización."""
    _confirmed_artifact_version_decision(decisions_file, "factory/regulatory/applicability_matrix.yaml",
                                         iid="ARTIFACT_VERSION-2026-777")
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no está autorizado"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id="ARTIFACT_VERSION-2026-777", repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_a_covering_decision_id_from_a_different_family_never_authorizes(repo, decisions_file):
    artifact_id = CATALOG_REL
    record = store.build_record(
        decision_family="D2", decision_type="ORIGINAL", selection_mode="EXPLICIT_LIST",
        resolved_target_ids=[artifact_id], decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="cesar", approved_by_display_name="Cesar",
        decision_instance_id="D2-2026-500", store_file=decisions_file, reason="familia equivocada")
    store.append_record(record, store_file=decisions_file, emit_audit=False)
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no está autorizado"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id="D2-2026-500", repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_bumping_to_the_version_already_declared_is_a_noop_error(repo, decisions_file):
    iid = _confirmed_artifact_version_decision(decisions_file, CATALOG_REL)
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="nada que aplicar"):
        apply_mod.apply_catalog_version_bump(
            "1.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


# ---------------------------------------------------------------------------
# Camino de exito: los tres efectos juntos
# ---------------------------------------------------------------------------

def test_successful_bump_writes_file_record_and_historical_copy(repo, decisions_file):
    artifact_id = CATALOG_REL
    iid = _confirmed_artifact_version_decision(decisions_file, artifact_id)
    versions_store = repo / "factory/registry/artifact_versions.jsonl"

    record = apply_mod.apply_catalog_version_bump(
        "2.0", decision_instance_id=iid, repo=repo,
        decision_store_file=decisions_file, versions_store_file=versions_store)

    # (1) el archivo vivo quedo bumpeado
    bumped = (repo / CATALOG_REL).read_text(encoding="utf-8")
    assert "catalog_version: '2.0'" in bumped
    assert yaml.safe_load(bumped)["catalog_version"] == "2.0"

    # (2) el version_record tiene los campos que exige la invariante
    assert record["artifact_id"] == artifact_id
    assert record["version"] == "2.0"
    assert record["previous_version"] == "1.0"
    assert record["approved_by_decision"] == iid
    assert versions_store.is_file()
    lines = versions_store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    # (3) la copia historica se congelo desde HEAD, byte a byte
    assert record["historical_copy"]["status"] == "FROZEN"
    frozen_path = repo / record["historical_copy"]["path"]
    assert frozen_path.is_file()
    assert frozen_path.read_text(encoding="utf-8") == _MINIMAL_CATALOG

    # el guard, tras el bump, ya no reporta version_changed sobre este artefacto
    scope_state = next(s for s in guard.enumerate_artifacts(repo=repo)
                       if s.artifact_id == artifact_id)
    assert scope_state.version == "2.0"
    findings = guard.check_artifact(scope_state, record, decision_store_file=decisions_file)
    codes = {f.code for f in findings}
    assert guard.VERSION_CHANGED_WITHOUT_DECISION not in codes
    assert guard.CONTENT_CHANGED_VERSION_SAME not in codes


def test_freezing_declines_honestly_when_the_working_tree_is_dirty(repo, decisions_file):
    """Si el archivo vivo YA difiere de HEAD antes del bump (edicion sin
    commitear ajena a esta aplicacion), la copia historica NUNCA se fabrica
    desde ese archivo -- se declara UNAVAILABLE_NOT_COMMITTED, honesto."""
    catalog = repo / CATALOG_REL
    catalog.write_text(_MINIMAL_CATALOG + "# comentario sin commitear\n", encoding="utf-8")

    iid = _confirmed_artifact_version_decision(decisions_file, CATALOG_REL)
    record = apply_mod.apply_catalog_version_bump(
        "2.0", decision_instance_id=iid, repo=repo,
        decision_store_file=decisions_file,
        versions_store_file=repo / "factory/registry/artifact_versions.jsonl")

    assert record["historical_copy"]["status"] == "UNAVAILABLE_NOT_COMMITTED"
    assert "reason" in record["historical_copy"]
    # el bump en si SIGUE aplicandose: la falta de copia historica no bloquea
    # el versionado, solo se declara con honestidad
    assert yaml.safe_load(catalog.read_text(encoding="utf-8"))["catalog_version"] == "2.0"


def test_a_second_identical_freeze_reuses_the_same_file(repo, decisions_file):
    """Congelar dos veces la MISMA version historica no debe duplicar ni
    fallar -- mismo contenido, mismo destino."""
    artifact_id = CATALOG_REL
    iid = _confirmed_artifact_version_decision(decisions_file, artifact_id)
    dest = apply_mod._freeze_historical_copy(
        repo, artifact_id, previous_version="1.0",
        previous_sha256=guard.canonical_hash_yaml(repo / artifact_id, "catalog"))
    assert dest["status"] == "FROZEN"
    dest_again = apply_mod._freeze_historical_copy(
        repo, artifact_id, previous_version="1.0",
        previous_sha256=guard.canonical_hash_yaml(repo / artifact_id, "catalog"))
    assert dest_again == dest
