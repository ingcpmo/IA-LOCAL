"""Re-firma de D2/D3/D4/D5 — W5 V2 G2'.

Los cuatro registros del 2026-07-29 se firmaron SIN NINGUN OBJETIVO:
`approved_pack_ids` era opcional y no se envio, y D3/D4/D5 no tenian campo de
objetivo. Los cuatro dicen `APPROVE` sin decir sobre que.

Bajo el modelo nuevo eso viola I-3 y quedan `INVALID_PENDING_RESIGNATURE`: no
autorizan nada. No es un tecnicismo -- hoy figuran como "registradas" cuatro
decisiones cuyo alcance nadie puede enunciar.

G2' NO son correcciones: los originales se CONSERVAN como
`INVALID_PENDING_RESIGNATURE` y las nuevas son `SUPERSESSION` de familia. La
distincion importa para el audit trail: una correccion dice "esto estaba mal
escrito"; una supersesion dice "esto se reemplaza por aquello", y aqui lo que
pasa es lo segundo.

LAS CUATRO FIRMAS SON DE CESAR. Estos tests prueban el MECANISMO sobre almacenes
temporales; ninguno escribe en el almacen real.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.core import audit_writer as aw
from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store

PENDIENTES = ("D2-2026-001", "D3-2026-001", "D4-2026-001", "D5-2026-001")


@pytest.fixture()
def migrated(tmp_path, monkeypatch) -> Path:
    """Copia del almacen REAL migrado. Ni un test escribe en el original."""
    if not store.STORE_FILE.exists():
        pytest.skip("almacen v2 no migrado en este entorno")
    audit = tmp_path / "audit" / "a.jsonl"
    audit.parent.mkdir(parents=True)
    monkeypatch.setattr(aw, "AUDIT_FILE", audit)
    monkeypatch.setattr(aw, "_last_entry_hash", None)
    dst = tmp_path / "decisions_v2.jsonl"
    shutil.copy(store.STORE_FILE, dst)
    return dst


def _resign(path: Path, family: str, target_ids, *, predecessor: str,
            approved_by_id: str = "Cesar") -> dict:
    rec = store.build_record(
        decision_family=family, decision_type="SUPERSESSION",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(target_ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id=approved_by_id, approved_by_display_name=approved_by_id,
        supersedes_instance_id=predecessor,
        reason="re-firma G2': el registro original no declaraba alcance",
        store_file=path)
    return store.append_record(rec, store_file=path)


# ===========================================================================
# El estado que G2' existe para cerrar
# ===========================================================================

def test_the_four_migrated_decisions_declare_no_scope(migrated):
    """`APPROVE` sin decir sobre que. El hallazgo, medido sobre el almacen real."""
    by_id = {r["decision_instance_id"]: r for r in store.read_all(migrated)}
    for iid in PENDIENTES:
        r = by_id[iid]
        assert r["decision"] == "APPROVE"
        assert r["resolved_target_ids"] == []
        assert r["status"] == "INVALID_PENDING_RESIGNATURE"


def test_a_decision_without_scope_authorizes_nothing(migrated):
    """Es lo que impide que "ya las aprobé" se traduzca en autorización."""
    for family in ("D2", "D3", "D4", "D5"):
        c = resolver.coverage_report(family, store_file=migrated)
        assert c.covered_ids == (), f"{family} autoriza sin alcance declarado"


def test_pending_resignature_never_grants_even_with_targets(migrated):
    """La guardia es el ESTADO, no la lista vacía.

    Hueco destapado por mutación: los cuatro registros reales tienen
    `resolved_target_ids: []`, así que jamás ejercitan la regla "solo ACTIVE
    otorga" -- no cubren nada por estar vacíos, no por estar inválidos. Si
    alguien relajara ese filtro, ningún test lo habría notado.

    Nada impide escribir un `INVALID_PENDING_RESIGNATURE` CON objetivos: ese
    estado es la exención de I-3 para la lista vacía, no una garantía de que
    esté vacía. Aquí se construye ese caso y se comprueba que sigue sin otorgar.
    """
    rec = store.build_record(
        decision_family="D3", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["RW-0001"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        status="INVALID_PENDING_RESIGNATURE",
        decision_instance_id="D3-2026-900", store_file=migrated)
    store.append_record(rec, store_file=migrated)

    x = resolver.resolve("D3", "RW-0001", store_file=migrated)
    assert not x.authorized, (
        "un registro INVALID_PENDING_RESIGNATURE otorgó cobertura: la guardia "
        "debe mirar el estado proyectado, no si la lista está vacía")
    assert x.coverage_basis == resolver.NOT_COVERED


def test_all_four_are_reported_as_pending_resignature(migrated):
    for family, iid in zip(("D2", "D3", "D4", "D5"), PENDIENTES):
        c = resolver.coverage_report(family, store_file=migrated)
        assert iid in c.pending_resignature_instances


# ===========================================================================
# El mecanismo de re-firma
# ===========================================================================

def test_resigning_d3_supersedes_the_original_and_authorizes(migrated):
    """Ruta completa sobre los 14 file_ids reales del allowlist."""
    ids, _ = store.resolve_all_snapshot("D3")
    nuevo = _resign(migrated, "D3", ids, predecessor="D3-2026-001")

    estados = store.project_status(store.read_all(migrated))
    assert estados["D3-2026-001"] == "SUPERSEDED"
    assert estados[nuevo["decision_instance_id"]] == "ACTIVE"

    c = resolver.coverage_report("D3", store_file=migrated)
    assert set(c.covered_ids) == set(ids)
    assert c.uncovered_ids == ()


def test_the_original_record_is_preserved_not_rewritten(migrated):
    """G2' no son correcciones: el original SE CONSERVA.

    Append-only. Quien audite tiene que poder ver que se firmó algo sin alcance
    y que después se reemplazó, no encontrarse un historial limpio.
    """
    antes = len(store.read_all(migrated))
    ids, _ = store.resolve_all_snapshot("D3")
    _resign(migrated, "D3", ids, predecessor="D3-2026-001")

    registros = store.read_all(migrated)
    assert len(registros) == antes + 1
    original = [r for r in registros if r["decision_instance_id"] == "D3-2026-001"][0]
    assert original["status"] == "INVALID_PENDING_RESIGNATURE", (
        "el registro original fue reescrito: el almacen debe ser append-only")
    assert original["resolved_target_ids"] == []


def test_the_resignature_is_a_supersession_not_a_correction(migrated):
    """Una CORRECTION dice "esto estaba mal escrito"; una SUPERSESSION dice
    "esto se reemplaza". Aqui pasa lo segundo, y el audit trail lo refleja."""
    ids, _ = store.resolve_all_snapshot("D3")
    nuevo = _resign(migrated, "D3", ids, predecessor="D3-2026-001")
    assert nuevo["decision_type"] == "SUPERSESSION"
    assert nuevo["supersedes_instance_id"] == "D3-2026-001"


def test_a_resignature_still_needs_a_real_human_identity(migrated):
    """G2' no relaja I-8. Cuatro firmas, cuatro identidades reales."""
    from factory.core import identity_policy as idp
    ids, _ = store.resolve_all_snapshot("D3")
    with pytest.raises((store.DecisionValidationError, idp.IdentityValidationError)):
        _resign(migrated, "D3", ids, predecessor="D3-2026-001",
                approved_by_id="human")


def test_a_resignature_with_an_empty_scope_is_rejected(migrated):
    """El defecto no se puede repetir: re-firmar sin alcance vuelve a violar I-3.

    Es el test que impide que G2' sea teatro.
    """
    with pytest.raises(store.DecisionValidationError) as exc:
        _resign(migrated, "D3", [], predecessor="D3-2026-001")
    assert "I-3" in str(exc.value)


def test_a_resignature_needs_a_reason(migrated):
    """I-6: toda SUPERSESSION explica por que. Reemplazar sin motivo no es
    gobernanza."""
    ids, _ = store.resolve_all_snapshot("D3")
    rec = store.build_record(
        decision_family="D3", decision_type="SUPERSESSION",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        supersedes_instance_id="D3-2026-001", reason="   ",
        store_file=migrated)
    v = store.validate_record(rec, families=store.load_families(),
                             store_file=migrated)
    assert not v.valid
    assert any("I-6" in x and "reason" in x for x in v.violations)


def test_you_cannot_supersede_a_decision_of_another_family(migrated):
    """I-6. Re-firmar D3 apuntando a D2 mezclaria dos alcances distintos."""
    ids, _ = store.resolve_all_snapshot("D3")
    rec = store.build_record(
        decision_family="D3", decision_type="SUPERSESSION",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=list(ids),
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        supersedes_instance_id="D2-2026-001", reason="cruzada",
        store_file=migrated)
    v = store.validate_record(rec, families=store.load_families(),
                             store_file=migrated)
    assert not v.valid
    assert any("OTRA familia" in x for x in v.violations)


# ===========================================================================
# El defecto que la sonda de G2' destapó
# ===========================================================================

def test_a_resigned_record_stops_being_reported_as_pending(migrated):
    """DEFECTO REAL cazado al probar el mecanismo de G2'.

    `coverage_report` calculaba `pending_resignature_instances` leyendo el campo
    `status` ALMACENADO, mientras `active_instances` -- dos líneas más abajo, en
    el mismo `return` -- usaba la proyección. Resultado: un registro seguía
    figurando como "pendiente de re-firma" DESPUÉS de re-firmarse, y el panel le
    habría dicho a Cesar que le falta firmar algo que acaba de firmar.

    Es el mismo error que este módulo corrige en otros sitios: `status` es el
    estado AL ESCRIBIRSE y la vigencia se DERIVA.
    """
    c_antes = resolver.coverage_report("D3", store_file=migrated)
    assert "D3-2026-001" in c_antes.pending_resignature_instances

    ids, _ = store.resolve_all_snapshot("D3")
    _resign(migrated, "D3", ids, predecessor="D3-2026-001")

    c_despues = resolver.coverage_report("D3", store_file=migrated)
    assert "D3-2026-001" not in c_despues.pending_resignature_instances, (
        "sigue pendiente después de re-firmarse: se está leyendo el campo "
        "almacenado en vez de la proyección")
    assert "D3-2026-001" not in c_despues.active_instances


def test_the_still_pending_ones_keep_being_reported(migrated):
    """La corrección no puede volverse un silenciador: re-firmar D3 no puede
    apagar el aviso de D2, D4 y D5."""
    ids, _ = store.resolve_all_snapshot("D3")
    _resign(migrated, "D3", ids, predecessor="D3-2026-001")

    for family, iid in (("D2", "D2-2026-001"), ("D4", "D4-2026-001"),
                        ("D5", "D5-2026-001")):
        c = resolver.coverage_report(family, store_file=migrated)
        assert iid in c.pending_resignature_instances, f"{iid} dejó de avisar"


# ===========================================================================
# D2 es distinta, y no por un tecnicismo
# ===========================================================================

def test_d2_forbids_all_snapshot_by_design(migrated):
    """D2 no admite `ALL_SNAPSHOT`, y eso condiciona su re-firma.

    Cada pack se aprueba por su CONTENIDO concreto. Un "apruebo los 20" es
    precisamente lo que produjo el registro D2 sin objetivo que G2' viene a
    cerrar; re-firmarlo con la lista completa reproduciría el defecto con mejor
    sintaxis.
    """
    families = store.load_families()
    assert families["D2"]["selection_modes"] == ["EXPLICIT_LIST"]
    assert "ALL_SNAPSHOT" not in families["D2"]["selection_modes"]

    rec = store.build_record(
        decision_family="D2", decision_type="SUPERSESSION",
        selection_mode="ALL_SNAPSHOT",
        resolved_target_ids=["21_CFR_11.10(a)"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        supersedes_instance_id="D2-2026-001", reason="atajo",
        store_file=migrated)
    v = store.validate_record(rec, families=families, store_file=migrated)
    assert not v.valid
    assert any("I-2" in x for x in v.violations)


def test_d2_can_be_resigned_over_an_explicit_subset(migrated):
    """Lo que SÍ es legítimo: una lista explícita, aunque sea parcial.

    `PARTIAL` existe para esto -- se aprueba lo que se ha revisado y se dice
    cuál, en vez de firmar los 20 de golpe.
    """
    rec = store.build_record(
        decision_family="D2", decision_type="SUPERSESSION",
        selection_mode="EXPLICIT_LIST",
        resolved_target_ids=["21_CFR_11.10(a)", "21_CFR_11.10(d)"],
        decision="PARTIAL", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        supersedes_instance_id="D2-2026-001",
        reason="re-firma G2' sobre los packs efectivamente revisados",
        store_file=migrated)
    store.append_record(rec, store_file=migrated)

    c = resolver.coverage_report("D2", store_file=migrated)
    assert set(c.covered_ids) == {"21_CFR_11.10(a)", "21_CFR_11.10(d)"}
    # Y los otros 18 siguen sin cobertura, dicho con nombres.
    assert len(c.uncovered_ids) == 18


# ===========================================================================
# D4 y D5 no tienen registry contra el que comparar
# ===========================================================================

@pytest.mark.parametrize("family,iid", [("D4", "D4-2026-001"), ("D5", "D5-2026-001")])
def test_d4_and_d5_can_be_resigned_but_coverage_is_not_comparable(migrated,
                                                                  family, iid):
    """Su objetivo es un plan o un paquete, no un id de un registry.

    Se pueden re-firmar, y su cobertura sigue sin ser comparable contra un
    conjunto -- el gate lo declara `NO_REGISTRY_TO_COMPARE` en vez de darla por
    cubierta. Re-firmar no inventa un registry que no existe.
    """
    nuevo = _resign(migrated, family, [f"{family.lower()}_scope_2026_07"],
                    predecessor=iid)
    estados = store.project_status(store.read_all(migrated))
    assert estados[iid] == "SUPERSEDED"
    assert estados[nuevo["decision_instance_id"]] == "ACTIVE"

    c = resolver.coverage_report(family, store_file=migrated)
    assert iid not in c.pending_resignature_instances
    # `registry_ids` sale del fallback (cubiertos ∪ revocados), no de un registry.
    assert set(c.covered_ids) == {f"{family.lower()}_scope_2026_07"}


# ===========================================================================
# Nada de esto toca el almacen real
# ===========================================================================

def test_no_test_in_this_file_wrote_to_the_real_store():
    """Las cuatro firmas son de Cesar. Aqui solo se prueba el mecanismo."""
    if not store.STORE_FILE.exists():
        pytest.skip("almacen v2 no migrado en este entorno")
    registros = store.read_all()
    assert len(registros) == 14, (
        f"el almacen real tiene {len(registros)} registros: algun test escribio en el")
    for iid in PENDIENTES:
        r = [x for x in registros if x["decision_instance_id"] == iid][0]
        assert r["status"] == "INVALID_PENDING_RESIGNATURE"
