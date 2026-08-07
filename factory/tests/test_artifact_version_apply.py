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


def _confirmed_artifact_version_decision(decisions_file, artifact_id, *,
                                         iid="ARTIFACT_VERSION-2026-001",
                                         payload=None):
    """`payload=None` reproduce a propósito el estado real encontrado el
    2026-08-04 (ARTIFACT_VERSION-2026-001/002/003 con `payload={}`) -- los
    tests que necesitan una decisión APLICABLE deben pasar un payload real
    con `_bump_payload()`."""
    record = store.build_record(
        decision_family="ARTIFACT_VERSION", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=[artifact_id],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="cesar", approved_by_display_name="Cesar",
        decision_instance_id=iid, store_file=decisions_file, reason="bump 1.0->2.0",
        payload=payload)
    store.append_record(record, store_file=decisions_file, emit_audit=False)
    return record["decision_instance_id"]


def _bump_payload(artifact_id, *, hash_before, from_version, to_version,
                  hash_after=None):
    """Payload estructurado real (G4c, hallazgo 2026-08-04) -- `hash_after`
    por defecto es igual a `hash_before` porque `catalog_version` está
    excluido del hash canónico (ver `_EXCLUDED`), así que un bump que SOLO
    cambia la etiqueta de versión no mueve el hash."""
    return {
        "artifact_path": artifact_id,
        "artifact_hash_before": hash_before,
        "from_version": from_version,
        "to_version": to_version,
        "expected_hash_after": hash_after if hash_after is not None else hash_before,
        "change_reason": "test",
    }


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
    hash_now = guard.canonical_hash_yaml(repo / CATALOG_REL, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, CATALOG_REL,
        payload=_bump_payload(CATALOG_REL, hash_before=hash_now, from_version="1.0", to_version="1.0"))
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
    hash_now = guard.canonical_hash_yaml(repo / artifact_id, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload(artifact_id, hash_before=hash_now, from_version="1.0", to_version="2.0"))
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

    # el comentario es sintaxis YAML, no contenido semantico -- yaml.safe_load
    # lo descarta, asi que el hash canonico NO se mueve pese al cambio en disco.
    hash_now = guard.canonical_hash_yaml(catalog, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, CATALOG_REL,
        payload=_bump_payload(CATALOG_REL, hash_before=hash_now, from_version="1.0", to_version="2.0"))
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


# ---------------------------------------------------------------------------
# apply_artifact_first_approval -- G6, caso real: golden_dataset bootstrapeado
# sin approved_by_decision.
# ---------------------------------------------------------------------------

GOLDEN_REL = "factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py"
_MINIMAL_GOLDEN = "_ALL_CASES = []\n"


@pytest.fixture()
def repo_with_golden(repo):
    golden = repo / GOLDEN_REL
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text(_MINIMAL_GOLDEN, encoding="utf-8")
    return repo


def _bootstrap_golden_version_record(repo, versions_store) -> dict:
    state = next(s for s in guard.enumerate_artifacts(repo=repo)
                if s.artifact_id == GOLDEN_REL)
    record = guard.build_version_record(state, bootstrap=True,
                                        bootstrap_note="foto inicial de prueba")
    versions_store.parent.mkdir(parents=True, exist_ok=True)
    with versions_store.open("a", encoding="utf-8") as fh:
        fh.write(__import__("json").dumps(record) + "\n")
    return record


def test_first_approval_without_a_version_record_is_rejected(repo_with_golden, decisions_file):
    iid = _confirmed_artifact_version_decision(decisions_file, GOLDEN_REL)
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no tiene version_record"):
        apply_mod.apply_artifact_first_approval(
            GOLDEN_REL, decision_instance_id=iid, repo=repo_with_golden,
            decision_store_file=decisions_file,
            versions_store_file=repo_with_golden / "factory/registry/artifact_versions.jsonl")


def test_first_approval_rejects_content_drift_since_bootstrap(repo_with_golden, decisions_file):
    versions_store = repo_with_golden / "factory/registry/artifact_versions.jsonl"
    _bootstrap_golden_version_record(repo_with_golden, versions_store)
    # el archivo vivo cambia DESPUES del bootstrap con contenido REAL (el hash
    # es del AST, no del texto -- un comentario no lo moveria) -- ya no es
    # "primera aprobacion simple", es contenido nuevo.
    (repo_with_golden / GOLDEN_REL).write_text(_MINIMAL_GOLDEN + "NEW_CASE = 1\n", encoding="utf-8")

    iid = _confirmed_artifact_version_decision(decisions_file, GOLDEN_REL)
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="cambió desde el bootstrap"):
        apply_mod.apply_artifact_first_approval(
            GOLDEN_REL, decision_instance_id=iid, repo=repo_with_golden,
            decision_store_file=decisions_file, versions_store_file=versions_store)


def test_first_approval_twice_is_rejected(repo_with_golden, decisions_file):
    versions_store = repo_with_golden / "factory/registry/artifact_versions.jsonl"
    _bootstrap_golden_version_record(repo_with_golden, versions_store)
    iid = _confirmed_artifact_version_decision(decisions_file, GOLDEN_REL)
    apply_mod.apply_artifact_first_approval(
        GOLDEN_REL, decision_instance_id=iid, repo=repo_with_golden,
        decision_store_file=decisions_file, versions_store_file=versions_store)

    iid2 = _confirmed_artifact_version_decision(decisions_file, GOLDEN_REL, iid="ARTIFACT_VERSION-2026-003")
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="ya tiene approved_by_decision"):
        apply_mod.apply_artifact_first_approval(
            GOLDEN_REL, decision_instance_id=iid2, repo=repo_with_golden,
            decision_store_file=decisions_file, versions_store_file=versions_store)


def test_first_approval_success_never_touches_the_source_file(repo_with_golden, decisions_file):
    versions_store = repo_with_golden / "factory/registry/artifact_versions.jsonl"
    _bootstrap_golden_version_record(repo_with_golden, versions_store)
    before = (repo_with_golden / GOLDEN_REL).read_text(encoding="utf-8")
    before_mtime = (repo_with_golden / GOLDEN_REL).stat().st_mtime

    iid = _confirmed_artifact_version_decision(decisions_file, GOLDEN_REL)
    record = apply_mod.apply_artifact_first_approval(
        GOLDEN_REL, decision_instance_id=iid, repo=repo_with_golden,
        decision_store_file=decisions_file, versions_store_file=versions_store)

    assert record["approved_by_decision"] == iid
    assert record["artifact_id"] == GOLDEN_REL
    assert record["version"] is None
    assert record["previous_version"] is None
    # el archivo fuente -- a diferencia del bump de catalogo -- NUNCA se toca:
    # esta operacion aprueba, no versiona contenido nuevo.
    assert (repo_with_golden / GOLDEN_REL).read_text(encoding="utf-8") == before
    assert (repo_with_golden / GOLDEN_REL).stat().st_mtime == before_mtime

    lines = versions_store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # el bootstrap + esta aprobacion, append-only

    state = next(s for s in guard.enumerate_artifacts(repo=repo_with_golden)
                if s.artifact_id == GOLDEN_REL)
    findings = guard.check_artifact(state, record, decision_store_file=decisions_file)
    assert not any(f.code == guard.NO_APPROVING_DECISION for f in findings)


# ---------------------------------------------------------------------------
# Checklist del panel ARQ (2026-08-04) -- cierre del hallazgo estructural:
# una decision ARTIFACT_VERSION confirmada para UNA transicion no puede
# reutilizarse para aplicar OTRA.
# ---------------------------------------------------------------------------

def test_old_signature_without_structured_payload_is_rejected(repo, decisions_file):
    """El caso real encontrado: ARTIFACT_VERSION-2026-002 (payload={}) NO
    puede usarse para aplicar NINGUN bump -- ni siquiera el que originalmente
    motivo su firma -- porque no declara la transicion exacta."""
    iid = _confirmed_artifact_version_decision(decisions_file, CATALOG_REL)  # payload=None, como -002 real
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="no declara la transición exacta"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_old_signature_cannot_be_reused_for_a_different_transition(repo, decisions_file):
    """Una decision confirmada y APLICABLE para 1.0->2.0 no autoriza 2.0->2.1:
    el decision_id corresponde a otra transicion."""
    artifact_id = CATALOG_REL
    hash_now = guard.canonical_hash_yaml(repo / artifact_id, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload(artifact_id, hash_before=hash_now, from_version="1.0", to_version="2.0"))
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="corresponde a otra transición"):
        apply_mod.apply_catalog_version_bump(
            "2.1", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_hash_mismatch_against_declared_before_is_rejected(repo, decisions_file):
    """El contenido vivo cambio despues de proponer -- artifact_hash_before
    ya no describe el archivo real."""
    artifact_id = CATALOG_REL
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload(artifact_id, hash_before="0" * 64, from_version="1.0", to_version="2.0"))
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="el hash vivo .* no coincide"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_version_mismatch_against_declared_from_is_rejected(repo, decisions_file):
    """La version viva no coincide con from_version declarado -- el estado
    cambio (p.ej. otro bump ya se aplico) desde que se propuso."""
    artifact_id = CATALOG_REL
    hash_now = guard.canonical_hash_yaml(repo / artifact_id, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload(artifact_id, hash_before=hash_now, from_version="1.5", to_version="2.0"))
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="la versión viva .* no coincide"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_decision_for_a_different_artifact_path_is_rejected(repo, decisions_file):
    """La decision SI cubre este artifact_id ante el resolver (mismo
    target_ids), pero su payload declara OTRO artifact_path -- inconsistencia
    que se rechaza explicitamente, no se ignora."""
    artifact_id = CATALOG_REL
    hash_now = guard.canonical_hash_yaml(repo / artifact_id, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload("factory/regulatory/applicability_matrix.yaml",
                              hash_before=hash_now, from_version="1.0", to_version="2.0"))
    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="decisión de otro artefacto"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file,
            versions_store_file=repo / "factory/registry/artifact_versions.jsonl")


def test_exact_transition_via_propose_artifact_version_change_is_accepted(repo, decisions_file):
    """Camino completo real: propose_artifact_version_change() deriva el
    payload del estado vivo (nunca lo acepta como parametro), se confirma
    (mismo patron que -001->-002), y el apply con la transicion EXACTA
    declarada se acepta limpio."""
    artifact_id = CATALOG_REL
    proposal = apply_mod.propose_artifact_version_change(
        artifact_path=artifact_id, to_version="2.0", change_reason="test real",
        proposed_by_id="claude_code_session_g3", repo=repo,
        decision_store_file=decisions_file)
    assert proposal["decision_origin"] == "agent_proposed"
    assert proposal["payload"]["from_version"] == "1.0"
    assert proposal["payload"]["to_version"] == "2.0"
    assert proposal["payload"]["artifact_hash_before"] == proposal["payload"]["expected_hash_after"]

    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])
    assert confirmed["payload"] == proposal["payload"]  # la firma queda atada a los MISMOS valores

    record = apply_mod.apply_catalog_version_bump(
        "2.0", decision_instance_id=confirmed["decision_instance_id"], repo=repo,
        decision_store_file=decisions_file,
        versions_store_file=repo / "factory/registry/artifact_versions.jsonl")
    assert record["version"] == "2.0"
    assert record["approved_by_decision"] == confirmed["decision_instance_id"]


# ---------------------------------------------------------------------------
# propose/apply_regularization_for_applied_change -- caso real: G6,
# applicability_matrix.yaml paso de 2.1 a 2.2 (commit 84a7a58) sin pasar por
# ningun flujo gobernado, porque en ese momento no existia uno para esta
# clase de artefacto. El "antes" viene del bootstrap YA registrado, nunca se
# reconstruye de la nada.
# ---------------------------------------------------------------------------

MATRIX_REL = "factory/regulatory/applicability_matrix.yaml"
_MATRIX_V1 = 'matrix_version: "2.1"\ndocument_types: [URS, FS]\n'
_MATRIX_V2 = 'matrix_version: "2.2"\ndocument_types: [URS, FS, PROTOCOL]\n'


@pytest.fixture()
def repo_with_matrix(repo):
    matrix = repo / MATRIX_REL
    matrix.parent.mkdir(parents=True, exist_ok=True)
    matrix.write_text(_MATRIX_V1, encoding="utf-8")
    return repo


def _bootstrap_matrix_version_record(repo, versions_store) -> dict:
    state = next(s for s in guard.enumerate_artifacts(repo=repo)
                if s.artifact_id == MATRIX_REL)
    record = guard.build_version_record(state, bootstrap=True,
                                        bootstrap_note="foto inicial de prueba")
    versions_store.parent.mkdir(parents=True, exist_ok=True)
    with versions_store.open("a", encoding="utf-8") as fh:
        fh.write(__import__("json").dumps(record) + "\n")
    return record


def test_regularization_proposal_without_a_prior_version_record_is_rejected(
        repo_with_matrix, decisions_file):
    with pytest.raises(apply_mod.ArtifactVersionProposalError, match="ningún version_record previo"):
        apply_mod.propose_regularization_for_applied_change(
            artifact_path=MATRIX_REL, change_reason="test", proposed_by_id="claude",
            repo=repo_with_matrix, decision_store_file=decisions_file,
            versions_store_file=repo_with_matrix / "factory/registry/artifact_versions.jsonl")


def test_regularization_proposal_derives_before_from_bootstrap_and_after_from_live_state(
        repo_with_matrix, decisions_file):
    versions_store = repo_with_matrix / "factory/registry/artifact_versions.jsonl"
    bootstrap = _bootstrap_matrix_version_record(repo_with_matrix, versions_store)
    # el cambio YA esta en disco, como el caso real (84a7a58)
    (repo_with_matrix / MATRIX_REL).write_text(_MATRIX_V2, encoding="utf-8")

    proposal = apply_mod.propose_regularization_for_applied_change(
        artifact_path=MATRIX_REL, change_reason="regularizacion V6 (enlaza APPLICABILITY_MATRIX-2026-006)",
        proposed_by_id="claude_code_session_arq", repo=repo_with_matrix,
        decision_store_file=decisions_file, versions_store_file=versions_store)

    assert proposal["decision_origin"] == "agent_proposed"
    assert proposal["payload"]["from_version"] == bootstrap["version"] == "2.1"
    assert proposal["payload"]["artifact_hash_before"] == bootstrap["sha256"]
    live = next(s for s in guard.enumerate_artifacts(repo=repo_with_matrix)
               if s.artifact_id == MATRIX_REL)
    assert proposal["payload"]["to_version"] == live.version == "2.2"
    assert proposal["payload"]["expected_hash_after"] == live.sha256


def test_regularization_proposal_with_no_real_change_is_rejected(repo_with_matrix, decisions_file):
    versions_store = repo_with_matrix / "factory/registry/artifact_versions.jsonl"
    _bootstrap_matrix_version_record(repo_with_matrix, versions_store)
    with pytest.raises(apply_mod.ArtifactVersionProposalError, match="nada que regularizar"):
        apply_mod.propose_regularization_for_applied_change(
            artifact_path=MATRIX_REL, change_reason="test", proposed_by_id="claude",
            repo=repo_with_matrix, decision_store_file=decisions_file,
            versions_store_file=versions_store)


def test_regularization_apply_never_touches_the_artifact_file(repo_with_matrix, decisions_file):
    versions_store = repo_with_matrix / "factory/registry/artifact_versions.jsonl"
    _bootstrap_matrix_version_record(repo_with_matrix, versions_store)
    (repo_with_matrix / MATRIX_REL).write_text(_MATRIX_V2, encoding="utf-8")
    before = (repo_with_matrix / MATRIX_REL).read_text(encoding="utf-8")

    proposal = apply_mod.propose_regularization_for_applied_change(
        artifact_path=MATRIX_REL, change_reason="test", proposed_by_id="claude",
        repo=repo_with_matrix, decision_store_file=decisions_file,
        versions_store_file=versions_store)
    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])

    record = apply_mod.apply_regularization_for_applied_change(
        MATRIX_REL, decision_instance_id=confirmed["decision_instance_id"],
        repo=repo_with_matrix, decision_store_file=decisions_file,
        versions_store_file=versions_store)

    assert (repo_with_matrix / MATRIX_REL).read_text(encoding="utf-8") == before
    assert record["version"] == "2.2"
    assert record["previous_version"] == "2.1"
    assert record["approved_by_decision"] == confirmed["decision_instance_id"]

    lines = versions_store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # bootstrap + esta regularizacion, append-only

    state = next(s for s in guard.enumerate_artifacts(repo=repo_with_matrix)
                if s.artifact_id == MATRIX_REL)
    findings = guard.check_artifact(state, record, decision_store_file=decisions_file)
    codes = {f.code for f in findings}
    assert guard.VERSION_CHANGED_WITHOUT_DECISION not in codes


def test_regularization_apply_rejects_when_live_state_drifted_since_proposal(
        repo_with_matrix, decisions_file):
    versions_store = repo_with_matrix / "factory/registry/artifact_versions.jsonl"
    _bootstrap_matrix_version_record(repo_with_matrix, versions_store)
    (repo_with_matrix / MATRIX_REL).write_text(_MATRIX_V2, encoding="utf-8")

    proposal = apply_mod.propose_regularization_for_applied_change(
        artifact_path=MATRIX_REL, change_reason="test", proposed_by_id="claude",
        repo=repo_with_matrix, decision_store_file=decisions_file,
        versions_store_file=versions_store)
    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])

    # el archivo sigue cambiando DESPUES de la firma
    (repo_with_matrix / MATRIX_REL).write_text(
        _MATRIX_V2 + "extra: field\n", encoding="utf-8")

    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="ya no coincide"):
        apply_mod.apply_regularization_for_applied_change(
            MATRIX_REL, decision_instance_id=confirmed["decision_instance_id"],
            repo=repo_with_matrix, decision_store_file=decisions_file,
            versions_store_file=versions_store)


def test_regularization_apply_twice_is_rejected(repo_with_matrix, decisions_file):
    versions_store = repo_with_matrix / "factory/registry/artifact_versions.jsonl"
    _bootstrap_matrix_version_record(repo_with_matrix, versions_store)
    (repo_with_matrix / MATRIX_REL).write_text(_MATRIX_V2, encoding="utf-8")

    proposal = apply_mod.propose_regularization_for_applied_change(
        artifact_path=MATRIX_REL, change_reason="test", proposed_by_id="claude",
        repo=repo_with_matrix, decision_store_file=decisions_file,
        versions_store_file=versions_store)
    from factory.services import governance_service as gov
    confirmed = gov.confirm(
        proposal["decision_instance_id"], approved_by_id="cesar",
        approved_by_display_name="Cesar", store_file=decisions_file,
        family_state_hash=proposal["family_state_hash"])
    apply_mod.apply_regularization_for_applied_change(
        MATRIX_REL, decision_instance_id=confirmed["decision_instance_id"],
        repo=repo_with_matrix, decision_store_file=decisions_file,
        versions_store_file=versions_store)

    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="ya tiene approved_by_decision"):
        apply_mod.apply_regularization_for_applied_change(
            MATRIX_REL, decision_instance_id=confirmed["decision_instance_id"],
            repo=repo_with_matrix, decision_store_file=decisions_file,
            versions_store_file=versions_store)


def test_double_apply_of_the_same_decision_is_rejected(repo, decisions_file):
    """Aplicar la MISMA decision dos veces -- la segunda ya no tiene nada que
    aplicar, el artefacto ya esta en to_version."""
    artifact_id = CATALOG_REL
    hash_now = guard.canonical_hash_yaml(repo / artifact_id, "catalog")
    iid = _confirmed_artifact_version_decision(
        decisions_file, artifact_id,
        payload=_bump_payload(artifact_id, hash_before=hash_now, from_version="1.0", to_version="2.0"))
    versions_store = repo / "factory/registry/artifact_versions.jsonl"

    apply_mod.apply_catalog_version_bump(
        "2.0", decision_instance_id=iid, repo=repo,
        decision_store_file=decisions_file, versions_store_file=versions_store)

    with pytest.raises(apply_mod.ArtifactVersionApplyError, match="nada que aplicar"):
        apply_mod.apply_catalog_version_bump(
            "2.0", decision_instance_id=iid, repo=repo,
            decision_store_file=decisions_file, versions_store_file=versions_store)
