"""DecisionScopeResolver — T-01..T-19 de DECISION_SCOPE_RESOLVER_SPEC.md §7.

T-01 es el test central de todo este trabajo: reproduce, con Part 211 como
fixture REAL, el defecto que originó el rediseño -- una fuente incorporada al
registry DESPUÉS de una firma ALL no hereda cobertura.
"""
import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store

# Los tres ids que el registry tenía cuando se firmó la D1 real
# (copied_at 2026-07-17T19:32:45Z), y el que llegó 2 h 10 min después.
THREE_ORIGINALS = ["ecfr_21cfr_part11", "eu_gmp_annex11", "mhra_gxp_di_guidance_2018"]
PART211 = "ecfr_21cfr_part211"

D1_SIGNED_AT = "2026-07-29T00:15:15.595831+00:00"


def _write(tmp_store, records):
    tmp_store.parent.mkdir(parents=True, exist_ok=True)
    with tmp_store.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return tmp_store


def _rec(**over):
    base = dict(
        decision_family="D1",
        decision_type="ORIGINAL",
        selection_mode="ALL_SNAPSHOT",
        resolved_target_ids=THREE_ORIGINALS,
        decision="APPROVE",
        decision_origin="human_confirmed",
        approved_by_id="Cesar",
        approved_by_display_name="Cesar",
        decision_date=D1_SIGNED_AT,
        decision_instance_id="D1-2026-001",
    )
    base.update(over)
    return store.build_record(**base)


@pytest.fixture()
def store_path(tmp_path):
    return tmp_path / "decisions_v2.jsonl"


# ===========================================================================
# T-01 -- EL test
# ===========================================================================

def test_t01_source_registered_after_all_snapshot_is_not_covered(store_path):
    """D1 firmada ALL_SNAPSHOT sobre 3 fuentes; Part 211 llegó después.

    Si este test deja de fallar ante la mutación 'ALL_SNAPSHOT se reinterpreta
    como todo el registry actual', el diseño entero queda desprotegido.
    """
    _write(store_path, [_rec()])

    res = resolver.resolve("D1", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.NOT_COVERED
    assert res.denial_reason

    for sid in THREE_ORIGINALS:
        ok = resolver.resolve("D1", sid, store_file=store_path)
        assert ok.authorized is True, f"{sid} sí fue firmada"
        assert ok.coverage_basis == resolver.HUMAN_CONFIRMED_SNAPSHOT


def test_t02_all_snapshot_covers_exactly_the_signed_set(store_path):
    _write(store_path, [_rec()])
    assert resolver.resolve("D1", "id_inventado", store_file=store_path).coverage_basis \
        == resolver.NOT_COVERED


# ===========================================================================
# Cobertura: ADDENDUM / CORRECTION / REVOCATION / SUPERSESSION
# ===========================================================================

def test_t03_addendum_extends_coverage_only_for_its_ids(store_path):
    addendum = _rec(decision_type="ADDENDUM", amendment_sequence=1,
                    selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                    decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), addendum])

    assert resolver.resolve("D1", PART211, store_file=store_path).authorized
    for sid in THREE_ORIGINALS:
        assert resolver.resolve("D1", sid, store_file=store_path).authorized


def test_t04_addendum_does_not_supersede_the_original(store_path):
    addendum = _rec(decision_type="ADDENDUM", amendment_sequence=1,
                    selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                    decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), addendum])
    c = resolver.coverage_report("D1", store_file=store_path)
    assert "D1-2026-001" in c.active_instances
    assert "D1-2026-002" in c.active_instances


def test_t05_correction_supersedes_and_replaces_the_set(store_path):
    correction = _rec(decision_type="CORRECTION", amendment_sequence=1,
                      selection_mode="EXPLICIT_LIST",
                      resolved_target_ids=THREE_ORIGINALS[:2],
                      supersedes_instance_id="D1-2026-001",
                      reason="la tercera fuente no debía estar",
                      decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), correction])

    assert resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path).authorized
    dropped = resolver.resolve("D1", THREE_ORIGINALS[2], store_file=store_path)
    assert dropped.authorized is False
    assert dropped.coverage_basis == resolver.SUPERSEDED_ONLY


def test_t06_revocation_removes_coverage(store_path):
    revocation = _rec(decision_type="REVOCATION", amendment_sequence=1,
                      selection_mode="EXPLICIT_LIST",
                      resolved_target_ids=[THREE_ORIGINALS[1]],
                      supersedes_instance_id="D1-2026-001",
                      reason="fuente retirada por el emisor",
                      decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), revocation])

    res = resolver.resolve("D1", THREE_ORIGINALS[1], store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.REVOKED
    assert resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path).authorized


def test_t07_revocation_wins_over_a_later_addendum(store_path):
    """Retirar autorización es la operación segura y por tanto la que domina,
    con independencia del orden cronológico."""
    revocation = _rec(decision_type="REVOCATION", amendment_sequence=1,
                      selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                      supersedes_instance_id="D1-2026-001", reason="retirada",
                      decision_instance_id="D1-2026-002")
    later_addendum = _rec(decision_type="ADDENDUM", amendment_sequence=2,
                          selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                          decision_instance_id="D1-2026-003")
    _write(store_path, [_rec(), revocation, later_addendum])

    res = resolver.resolve("D1", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.REVOKED


def test_t08_supersession_deactivates_the_whole_family(store_path):
    supersession = _rec(decision_type="SUPERSESSION", amendment_sequence=1,
                        selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                        supersedes_instance_id="D1-2026-001",
                        reason="se rehace la política completa",
                        decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), supersession])
    assert resolver.resolve("D1", PART211, store_file=store_path).authorized
    assert not resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path).authorized


# ===========================================================================
# Fail-closed (R-4)
# ===========================================================================

def test_t09_missing_store_denies_without_raising(tmp_path):
    res = resolver.resolve("D1", PART211, store_file=tmp_path / "no_existe.jsonl")
    assert res.authorized is False
    assert res.coverage_basis == resolver.RESOLVER_UNAVAILABLE
    assert "no encontrado" in res.denial_reason


def test_t10_corrupt_json_line_denies(store_path):
    store_path.write_text('{"decision_family": "D1"\nesto no es json\n', encoding="utf-8")
    res = resolver.resolve("D1", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.RESOLVER_UNAVAILABLE


def test_t11_tampered_target_set_hash_denies(store_path):
    rec = _rec()
    rec["resolved_target_ids"] = THREE_ORIGINALS + [PART211]   # sin recalcular
    _write(store_path, [rec])
    res = resolver.resolve("D1", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.INVALID_RECORD


def test_t12_unknown_family_denies(store_path):
    _write(store_path, [_rec()])
    res = resolver.resolve("FAMILIA_INVENTADA", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.FAMILY_UNKNOWN


def test_t13_empty_target_ids_never_authorizes(store_path):
    """Los 4 registros reales D2/D3/D4/D5: APPROVE sin decir sobre qué."""
    rec = _rec(decision_family="D2", selection_mode="EXPLICIT_LIST",
               resolved_target_ids=[], status="INVALID_PENDING_RESIGNATURE",
               decision_instance_id="D2-2026-001")
    _write(store_path, [rec])
    res = resolver.resolve("D2", "21_CFR_11.10(a)", store_file=store_path)
    assert res.authorized is False
    assert "re-firma" in res.denial_reason


def test_t14_agent_proposed_alone_denies(store_path):
    proposal = _rec(decision_origin="agent_proposed", approved_by_id=None,
                    approved_by_display_name=None, proposed_by_id="layer8_agent",
                    selection_mode="EXPLICIT_LIST", resolved_target_ids=[PART211],
                    decision_instance_id="D1-2026-002")
    _write(store_path, [proposal])
    res = resolver.resolve("D1", PART211, store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.PROPOSAL_ONLY


def test_t15_reserved_identity_record_denies(store_path):
    rec = _rec()
    rec["approved_by_id"] = "human"
    _write(store_path, [rec])
    res = resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.INVALID_RECORD


def test_t16_reconstructed_snapshot_does_not_authorize(store_path):
    """Si un snapshot reconstruido autorizara, la Corrección D1 formal sería
    decorativa y el ciclo entero perdería el sentido."""
    rec = _rec(provenance="RECONSTRUCTED_SNAPSHOT",
               reconstruction_evidence={"method": "copied_at < firma"})
    _write(store_path, [rec])
    res = resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path)
    assert res.authorized is False
    assert res.coverage_basis == resolver.RECONSTRUCTED_PENDING_FORMAL_CORRECTION


def test_legacy_unmapped_never_authorizes(store_path):
    _write(store_path, [])
    res = resolver.resolve("LEGACY_UNMAPPED", "lo-que-sea", store_file=store_path)
    assert res.authorized is False


def test_broken_families_registry_raises_instead_of_denying(tmp_path, monkeypatch):
    """Un despliegue roto NO debe ser indistinguible de una denegación
    legítima: es la única excepción que el resolver propaga."""
    monkeypatch.setattr(store, "FAMILIES_FILE", tmp_path / "no_existe.yaml")
    with pytest.raises(resolver.ResolverConfigurationError):
        resolver.resolve("D1", PART211, store_file=tmp_path / "x.jsonl")


# ===========================================================================
# Read-only (R-5)
# ===========================================================================

def test_t17_resolve_writes_no_audit_event(store_path, isolated_audit):
    _write(store_path, [_rec()])
    before = isolated_audit.read_text(encoding="utf-8") if isolated_audit.exists() else ""
    for _ in range(200):
        resolver.resolve("D1", PART211, store_file=store_path)
        resolver.coverage_report("D1", store_file=store_path)
    after = isolated_audit.read_text(encoding="utf-8") if isolated_audit.exists() else ""
    assert before == after


def test_t18_resolve_does_not_mutate_the_store(store_path):
    import hashlib
    _write(store_path, [_rec()])
    before = hashlib.sha256(store_path.read_bytes()).hexdigest()
    for _ in range(50):
        resolver.resolve("D1", PART211, store_file=store_path)
    assert hashlib.sha256(store_path.read_bytes()).hexdigest() == before


def test_t19_resolve_is_idempotent(store_path):
    _write(store_path, [_rec()])
    results = [resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path)
               for _ in range(20)]
    assert len({(r.authorized, r.coverage_basis, r.covering_instances) for r in results}) == 1


# ===========================================================================
# coverage_report -- la señal de drift
# ===========================================================================

def test_coverage_report_surfaces_the_uncovered_source(store_path):
    """Es lo que habría cazado el alta de Part 211 el mismo 29-jul a las 02:25."""
    _write(store_path, [_rec()])
    c = resolver.coverage_report("D1", store_file=store_path)
    assert PART211 in c.registry_ids          # está en el registry HOY
    assert PART211 in c.uncovered_ids         # y no está cubierto
    assert set(c.covered_ids) == set(THREE_ORIGINALS)


def test_drift_determinable_distinguishes_unknown_from_no_drift(store_path):
    """`registry_drift_since_decision=False` sin más se leería como
    tranquilidad cuando en realidad el dato no existe."""
    rec = _rec()
    rec["registry_hash_at_decision"] = None
    _write(store_path, [rec])
    c = resolver.coverage_report("D1", store_file=store_path)
    assert c.registry_drift_since_decision is False
    assert c.drift_determinable is False

    rec2 = _rec()
    rec2["registry_hash_at_decision"] = "0" * 64
    _write(store_path, [rec2])
    c2 = resolver.coverage_report("D1", store_file=store_path)
    assert c2.drift_determinable is True
    assert c2.registry_drift_since_decision is True


def test_coverage_report_never_lists_a_revoked_id_as_covered(store_path):
    """Hueco encontrado por mutación: `resolve()` corta en REVOKED antes de
    mirar `covered`, así que quitar la resta de revocados no rompía T-06 ni
    T-07 -- pero `coverage_report` sí habría listado el id como cubierto, y
    ese es el objeto que alimenta la UI y el release gate."""
    revocation = _rec(decision_type="REVOCATION", amendment_sequence=1,
                      selection_mode="EXPLICIT_LIST",
                      resolved_target_ids=[THREE_ORIGINALS[1]],
                      supersedes_instance_id="D1-2026-001", reason="retirada",
                      decision_instance_id="D1-2026-002")
    _write(store_path, [_rec(), revocation])

    c = resolver.coverage_report("D1", store_file=store_path)
    assert THREE_ORIGINALS[1] in c.revoked_ids
    assert THREE_ORIGINALS[1] not in c.covered_ids
    assert THREE_ORIGINALS[1] not in c.uncovered_ids   # revocado ≠ sin cubrir
    assert set(c.covered_ids) == {THREE_ORIGINALS[0], THREE_ORIGINALS[2]}


def test_effective_snapshot_hash_excludes_revoked_ids(store_path):
    """El hash efectivo debe reflejar la cobertura REAL, no la firmada."""
    revocation = _rec(decision_type="REVOCATION", amendment_sequence=1,
                      selection_mode="EXPLICIT_LIST",
                      resolved_target_ids=[THREE_ORIGINALS[1]],
                      supersedes_instance_id="D1-2026-001", reason="retirada",
                      decision_instance_id="D1-2026-002")
    _write(store_path, [_rec()])
    full = resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path)
    _write(store_path, [_rec(), revocation])
    reduced = resolver.resolve("D1", THREE_ORIGINALS[0], store_file=store_path)
    assert full.effective_snapshot_hash != reduced.effective_snapshot_hash
    assert reduced.effective_snapshot_hash == store.compute_target_set_hash(
        [THREE_ORIGINALS[0], THREE_ORIGINALS[2]])


def test_resolve_many_matches_individual_resolution(store_path):
    _write(store_path, [_rec()])
    many = resolver.resolve_many("D1", THREE_ORIGINALS + [PART211], store_file=store_path)
    assert [many[s].authorized for s in THREE_ORIGINALS] == [True, True, True]
    assert many[PART211].authorized is False
