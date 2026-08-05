"""Invariantes I-1..I-12 del modelo extensible de decisiones — W5 V2, G1.

Cada test nombra la invariante que protege. Si un test de aqui se puede
borrar sin que falle nada mas, la invariante no estaba protegida.
"""
import json

import pytest

from factory.services import decision_store_v2 as store


@pytest.fixture()
def tmp_store(tmp_path):
    return tmp_path / "decisions_v2.jsonl"


def _record(**over):
    base = dict(
        decision_family="D1",
        decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST",
        resolved_target_ids=["ecfr_21cfr_part11"],
        decision="APPROVE",
        decision_origin="human_confirmed",
        approved_by_id="Cesar",
        approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-001",
    )
    base.update(over)
    return store.build_record(**base)


# --- registro de familias ---------------------------------------------------

def test_families_registry_loads_and_declares_the_expected_families():
    fams = store.load_families()
    for name in ("D1", "D2", "D3", "D4", "D5", "SOURCE_REGISTRATION",
                 "APPLICABILITY_MATRIX", "ARTIFACT_VERSION", "AUDIT_EXCEPTION"):
        assert name in fams


def test_addendum_families_are_not_declared_as_families():
    """D1-A/D2-A/D4-A son ADDENDUM, no familias. Declararlas como familias es
    exactamente como se llego a la tupla cerrada."""
    fams = store.load_families()
    for bad in ("D1-A", "D1_A", "D2-A", "D4-A"):
        assert bad not in fams


def test_families_registry_rejects_unknown_consumer(tmp_path, monkeypatch):
    bad = tmp_path / "families.yaml"
    bad.write_text(
        "known_consumers: [corpus_planner]\n"
        "families:\n"
        "  X:\n"
        "    selection_modes: [EXPLICIT_LIST]\n"
        "    consumers: [inventado]\n",
        encoding="utf-8")
    monkeypatch.setattr(store, "FAMILIES_FILE", bad)
    store.load_families.cache_clear()  # lru_cache: forzar releer el archivo nuevo
    with pytest.raises(store.FamiliesRegistryError, match="no declarados"):
        store.load_families()


# --- I-1 / I-2 --------------------------------------------------------------

def test_i1_unknown_family_is_rejected(tmp_store):
    rec = _record(decision_family="D1")
    rec["decision_family"] = "FAMILIA_INVENTADA"
    res = store.validate_record(rec, store_file=tmp_store)
    assert not res.valid
    assert any("I-1" in v for v in res.violations)


def test_i2_selection_mode_must_be_allowed_for_the_family(tmp_store):
    """D2 prohibe ALL_SNAPSHOT a proposito: cada pack se aprueba por su
    contenido. Un 'apruebo todos' es lo que produjo D2 sin objetivo."""
    rec = _record(decision_family="D2", selection_mode="ALL_SNAPSHOT",
                  resolved_target_ids=["21_CFR_11.10(a)"],
                  decision_instance_id="D2-2026-001")
    res = store.validate_record(rec, store_file=tmp_store)
    assert not res.valid
    assert any("I-2" in v for v in res.violations)


# --- I-3 --------------------------------------------------------------------

def test_i3_empty_target_ids_is_invalid_for_an_active_record(tmp_store):
    rec = _record(resolved_target_ids=[])
    res = store.validate_record(rec, store_file=tmp_store)
    assert not res.valid
    assert any("I-3" in v for v in res.violations)


def test_i3_empty_target_ids_is_allowed_only_as_pending_resignature(tmp_store):
    """Los 4 registros historicos D2/D3/D4/D5 deben poder ALMACENARSE -- si el
    schema los rechazara, la migracion los perderia."""
    rec = _record(resolved_target_ids=[], status="INVALID_PENDING_RESIGNATURE")
    assert store.validate_record(rec, store_file=tmp_store).valid


def test_all_literal_can_never_be_stored_as_a_target_id(tmp_store):
    """El defecto de origen: la D1 real almaceno la cadena 'ALL' y por eso
    nadie pudo decir, 2 h despues, si Part 211 estaba dentro."""
    for wildcard in ("ALL", "all", "*"):
        rec = _record(resolved_target_ids=[wildcard])
        res = store.validate_record(rec, store_file=tmp_store)
        assert not res.valid, f"{wildcard!r} no deberia poder almacenarse"


# --- I-4 --------------------------------------------------------------------

def test_i4_tampered_target_set_hash_is_detected(tmp_store):
    rec = _record(resolved_target_ids=["a", "b"])
    rec["resolved_target_ids"] = ["a", "b", "c"]      # mutado sin recalcular
    res = store.validate_record(rec, store_file=tmp_store)
    assert not res.valid
    assert any("I-4" in v for v in res.violations)


def test_target_set_hash_is_order_independent_and_reproducible():
    import hashlib
    a = store.compute_target_set_hash(["b", "a", "c"])
    b = store.compute_target_set_hash(["c", "b", "a"])
    assert a == b
    # Reproducible a mano: sha256 de los ids ordenados unidos por \n.
    assert a == hashlib.sha256(b"a\nb\nc").hexdigest()


# --- I-5 / I-6 / I-7 --------------------------------------------------------

def test_i5_original_cannot_supersede_nor_have_sequence(tmp_store):
    rec = _record(amendment_sequence=3)
    res = store.validate_record(rec, store_file=tmp_store)
    assert any("I-5" in v for v in res.violations)

    rec2 = _record(supersedes_instance_id="D1-2026-000")
    assert any("I-5" in v for v in store.validate_record(rec2, store_file=tmp_store).violations)


def test_i6_correction_requires_reason_and_a_resolvable_predecessor(tmp_store):
    rec = _record(decision_type="CORRECTION", supersedes_instance_id="D1-2026-999",
                  reason="", decision_instance_id="D1-2026-002")
    res = store.validate_record(rec, store_file=tmp_store, known_instances={"D1-2026-001"})
    assert any("I-6" in v and "reason" in v for v in res.violations)
    assert any("I-6" in v and "no resuelve" in v for v in res.violations)


def test_i6_batch_validation_resolves_predecessors_in_flight(tmp_store):
    """La migracion proyecta una CORRECTION y su predecesora en la misma
    pasada: sin known_instances, I-6 marcaria rota una cadena completa."""
    rec = _record(decision_type="CORRECTION", supersedes_instance_id="D1-2026-001",
                  reason="motivo real", decision_instance_id="D1-2026-002")
    assert store.validate_record(rec, known_instances={"D1-2026-001", "D1-2026-002"}).valid


def test_i7_addendum_extends_and_never_supersedes(tmp_store):
    rec = _record(decision_type="ADDENDUM", amendment_sequence=1,
                  supersedes_instance_id="D1-2026-001",
                  decision_instance_id="D1-2026-002")
    res = store.validate_record(rec, store_file=tmp_store)
    assert any("I-7" in v for v in res.violations)

    ok = _record(decision_type="ADDENDUM", amendment_sequence=1,
                 resolved_target_ids=["ecfr_21cfr_part211"],
                 decision_instance_id="D1-2026-002")
    assert store.validate_record(ok, store_file=tmp_store).valid


def test_i7_addendum_with_sequence_zero_is_rejected(tmp_store):
    rec = _record(decision_type="ADDENDUM", amendment_sequence=0,
                  decision_instance_id="D1-2026-002")
    assert any("I-7" in v for v in store.validate_record(rec, store_file=tmp_store).violations)


# --- I-8 / I-9 --------------------------------------------------------------

@pytest.mark.parametrize("generic", ["human", "agent", "claude", "qa", "", "  ", "Layer8"])
def test_i8_generic_identity_is_rejected(tmp_store, generic):
    """Cierra A-4: el Sistema A aceptaba confirmed_by='human'; el B devolvia
    422. Un solo estandar para el mismo acto."""
    rec = _record(approved_by_id=generic)
    res = store.validate_record(rec, store_file=tmp_store)
    assert not res.valid
    assert any("I-8" in v for v in res.violations)


def test_i9_a_proposal_cannot_carry_a_signature(tmp_store):
    rec = _record(decision_origin="agent_proposed", approved_by_id="Cesar",
                  proposed_by_id="layer8_agent")
    res = store.validate_record(rec, store_file=tmp_store)
    assert any("I-9" in v for v in res.violations)


# --- I-10 -------------------------------------------------------------------

def test_i10_reconstructed_snapshot_requires_its_evidence(tmp_store):
    rec = _record(provenance="RECONSTRUCTED_SNAPSHOT")
    res = store.validate_record(rec, store_file=tmp_store)
    assert any("I-10" in v for v in res.violations)


# --- I-11 -------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    "d1-2026-001",                              # minusculas
    "0192ae1a-e3d9-447d-bebb-11b220f6bd29",     # uuid4 libre (defecto A-10)
    "MC-0001",                                  # el id historico escrito fuera de la API
    "D1-26-1",
])
def test_i11_instance_id_must_be_derived_not_free(tmp_store, bad_id):
    rec = _record()
    rec["decision_instance_id"] = bad_id
    assert not store.validate_record(rec, store_file=tmp_store).valid


def test_i11_instance_id_must_start_with_its_own_family(tmp_store):
    rec = _record(decision_family="D1", decision_instance_id="D2-2026-001")
    res = store.validate_record(rec, store_file=tmp_store)
    assert any("I-11" in v for v in res.violations)


def test_i11_duplicate_instance_id_is_409(tmp_store, isolated_audit):
    store.append_record(_record(), store_file=tmp_store)
    with pytest.raises(store.DecisionConflictError):
        store.append_record(_record(), store_file=tmp_store)


def test_next_instance_id_increments_per_family(tmp_store, isolated_audit):
    assert store.next_instance_id("D1", year=2026, store_file=tmp_store) == "D1-2026-001"
    store.append_record(_record(), store_file=tmp_store)
    assert store.next_instance_id("D1", year=2026, store_file=tmp_store) == "D1-2026-002"
    # Otra familia lleva su propia secuencia.
    assert store.next_instance_id("D2", year=2026, store_file=tmp_store) == "D2-2026-001"


# --- I-12 -------------------------------------------------------------------

def test_i12_append_emits_exactly_one_audit_event(tmp_store, isolated_audit):
    before = len(isolated_audit.read_text(encoding="utf-8").splitlines()) \
        if isolated_audit.exists() else 0
    rec = store.append_record(_record(), store_file=tmp_store)
    after = isolated_audit.read_text(encoding="utf-8").splitlines()
    assert len(after) - before == 1
    event = json.loads(after[-1])
    assert event["event_type"] == "layer9_decision_recorded"
    assert event["data"]["side_effects_applied"] is False
    assert rec["audit_event_id"] == event["entry_id"]


def test_append_rejects_an_invalid_record_without_writing(tmp_store, isolated_audit):
    with pytest.raises(store.DecisionValidationError):
        store.append_record(_record(resolved_target_ids=[]), store_file=tmp_store)
    assert not tmp_store.exists()


# --- proyeccion de vigencia -------------------------------------------------

def test_correction_supersedes_and_addendum_does_not():
    original = _record(resolved_target_ids=["a", "b"])
    addendum = _record(decision_type="ADDENDUM", amendment_sequence=1,
                       resolved_target_ids=["c"], decision_instance_id="D1-2026-002")
    projected = store.project_status([original, addendum])
    assert projected["D1-2026-001"] == "ACTIVE"

    correction = _record(decision_type="CORRECTION", amendment_sequence=1,
                         supersedes_instance_id="D1-2026-001", reason="valor erroneo",
                         resolved_target_ids=["a"], decision_instance_id="D1-2026-003")
    projected = store.project_status([original, addendum, correction])
    assert projected["D1-2026-001"] == "SUPERSEDED"
    assert projected["D1-2026-002"] == "ACTIVE"


def test_projection_is_regenerable_from_scratch():
    """Nada puede depender de una proyeccion persistida que no se pueda
    rederivar -- ese es el test de que no se volvio una segunda fuente."""
    recs = [_record(), _record(decision_type="ADDENDUM", amendment_sequence=1,
                               resolved_target_ids=["z"],
                               decision_instance_id="D1-2026-002")]
    assert store.project_status(recs) == store.project_status(list(recs))


# --- ALL -> snapshot --------------------------------------------------------

def test_all_snapshot_materializes_against_the_real_registry():
    ids, registry_hash = store.resolve_all_snapshot("D1")
    assert "ecfr_21cfr_part11" in ids
    assert "ecfr_21cfr_part211" in ids       # HOY si esta en el registry
    assert len(registry_hash) == 64
    assert "ALL" not in ids


def test_all_snapshot_is_not_resolvable_without_a_target_registry():
    """D4 no tiene registry: inventar un conjunto contra el que comparar
    seria peor que declararlo no resoluble."""
    with pytest.raises(store.DecisionValidationError, match="target_registry"):
        store.resolve_all_snapshot("D4")
