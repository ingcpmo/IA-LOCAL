"""Migración de los dos almacenes históricos — V-1..V-6 de
EXTENSIBLE_DECISION_MODEL_SPEC.md §8.2.

Corre sobre los ficheros REALES en modo lectura. La garantía más importante
(V-2) es que sus sha256 son idénticos antes y después: la migración proyecta,
nunca reescribe.
"""
import hashlib
import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.scripts.ops import migrate_decisions_to_v2 as mig
from factory.services import decision_legacy_adapter as adapter
from factory.services import decision_store_v2 as store

PART211 = "ecfr_21cfr_part211"
PART11 = "ecfr_21cfr_part11"
# `ecfr_21cfr_part11` salio de este conjunto el 2026-08-03: la re-gobernanza
# real de G3 (`human_source_regovernance.py`) le dio un `copied_at` nuevo,
# posterior a la firma D1 (2026-07-29) -- mismo motivo por el que Part 211
# ya estaba excluido. Las dos fuentes recien copiadas viven ahora en
# LATER_INGESTED_NOT_COVERED, no en el snapshot reconstruido.
TWO_ORIGINALS = {"eu_gmp_annex11", "mhra_gxp_di_guidance_2018"}
LATER_INGESTED_NOT_COVERED = {PART211, PART11}


def _legacy_record_count() -> int:
    """Lineas reales de los dos almacenes legacy. Se mide, no se fija."""
    return sum(
        len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
        for p in (adapter.LEGACY_A_FILE, adapter.LEGACY_B_FILE) if p.is_file())


@pytest.fixture()
def migrated(tmp_path):
    """Migración real (entradas reales) a un fichero temporal, sin auditoría."""
    out = tmp_path / "decisions_v2.jsonl"
    summary = mig.run(apply=True, out_file=out, emit_audit=False)
    return out, summary


# --- V-1 / V-3 --------------------------------------------------------------

def test_v1_no_record_is_lost(migrated):
    """V-1 es "nada se pierde", y eso es `records_in == records_projected`.

    El `== 14` que habia aqui congelaba el tamano de dos almacenes que viven
    FUERA del repo y pueden crecer legitimamente: en cuanto Cesar corrigio la
    cadencia de D1 por la UI, el conteo paso a 15 y el build se puso rojo por
    una accion humana correcta. Misma leccion que ya estaba escrita en
    test_document_generation_strategy y test_source_baseline_allowlist, y que
    aqui se repitio.
    """
    _, s = migrated
    assert s["records_in"] == s["records_projected"]
    assert s["records_projected"] == _legacy_record_count()


def test_v3_every_projected_record_passes_the_invariants(migrated):
    _, s = migrated
    assert s["records_invalid"] == 0, s["invalid_detail"]


def test_the_four_targetless_decisions_are_flagged_not_hidden(migrated):
    """D2/D3/D4/D5 se firmaron APPROVE sin decir sobre qué. Que aparezcan como
    pendientes de re-firma no es una regresión: es el sistema diciendo la
    verdad sobre lo que se firmó."""
    _, s = migrated
    assert set(s["pending_resignature"]) == {
        "D2-2026-001", "D3-2026-001", "D4-2026-001", "D5-2026-001"}


def test_non_governance_decisions_are_legacy_unmapped_not_forced(migrated):
    """Forzarlas a una familia real sería fabricar cobertura.

    El `== 4` que había aquí congelaba el tamaño de un almacén legacy que
    sigue vivo (mismo patrón ya corregido en `test_v1_no_record_is_lost`):
    en cuanto `human_source_update.py` propuso y confirmó la corrección de
    URL de MHRA (G3, 2026-08-03), aparecieron 2 decisiones legítimas más de
    una acción no gobernada (`regulatory_source_url_update`), y el conteo
    pasó a 6 por una acción humana/de agente correcta, no por una regresión.
    Después, el ciclo real propose(x2, la primera propuesta quedó huérfana
    al reemplazarse por una segunda que sí apuntaba al fichero durable) +
    confirm de `human_source_regovernance.py` para `ecfr_21cfr_part11`
    (misma sesión) agregó 3 decisiones más de otra acción no gobernada
    (`regulatory_source_regovernance`), subiendo el conteo real a 9.
    """
    _, s = migrated
    assert len(s["legacy_unmapped"]) == 9


# --- V-2: las entradas no se tocan ------------------------------------------

def test_v2_input_files_are_byte_identical_after_migration(migrated):
    _, s = migrated
    assert s["inputs_untouched"] is True
    assert s["input_sha256_before"] == s["input_sha256_after"]
    assert all(v is not None for v in s["input_sha256_before"].values())


def test_migration_writes_nothing_in_dry_run(tmp_path):
    out = tmp_path / "decisions_v2.jsonl"
    s = mig.run(apply=False, out_file=out, emit_audit=False)
    assert not out.exists()
    assert s["applied"] is False
    assert s["output_sha256"]          # sí calcula el resultado, solo no lo escribe


def test_dry_run_is_the_default(tmp_path, monkeypatch):
    import sys
    out = tmp_path / "decisions_v2.jsonl"
    monkeypatch.setattr(store, "STORE_FILE", out)
    monkeypatch.setattr(sys, "argv", ["migrate_decisions_to_v2"])
    mig.main()
    assert not out.exists()


# --- V-4: la cobertura resultante -------------------------------------------

def test_v4_part211_is_not_covered_by_d1_after_migration(migrated):
    """El hallazgo de la auditoría, ahora comprobable por código."""
    out, _ = migrated
    res = resolver.resolve("D1", PART211, store_file=out)
    assert res.authorized is False
    assert res.coverage_basis == resolver.NOT_COVERED

    c = resolver.coverage_report("D1", store_file=out)
    assert PART211 in c.uncovered_ids


def test_v4_the_three_originals_are_reconstructed_not_authorized(migrated):
    """Tras migrar, NINGUNA fuente queda formalmente cubierta: las dos que
    siguen con su copia original de 2026-07 solo las respalda un snapshot
    reconstruido. `ecfr_21cfr_part11` se unió a Part 211 en NOT_COVERED
    (ver `test_v4_part211_is_not_covered_by_d1_after_migration` y
    `test_d1_reconstruction_excludes_sources_copied_after_the_signature`)
    tras su re-gobernanza real de G3 (2026-08-03): su `copied_at` es ahora
    posterior a la firma D1, así que queda excluido del snapshot igual que
    Part 211."""
    out, _ = migrated
    for sid in TWO_ORIGINALS:
        res = resolver.resolve("D1", sid, store_file=out)
        assert res.authorized is False
        assert res.coverage_basis == resolver.RECONSTRUCTED_PENDING_FORMAL_CORRECTION

    res_part11 = resolver.resolve("D1", PART11, store_file=out)
    assert res_part11.authorized is False
    assert res_part11.coverage_basis == resolver.NOT_COVERED

    c = resolver.coverage_report("D1", store_file=out)
    assert set(c.reconstructed_only_ids) == TWO_ORIGINALS
    assert c.covered_ids == ()
    assert PART11 in c.uncovered_ids


def test_the_registration_of_part211_WAS_authorized(migrated):
    """Corrige la premisa del plan: el alta sí tenía decisión humana. Lo que
    falta es cobertura de ciclo de vida (D1), que es otra cosa."""
    out, _ = migrated
    res = resolver.resolve("SOURCE_REGISTRATION", PART211, store_file=out)
    assert res.authorized is True
    assert res.coverage_basis == resolver.HUMAN_CONFIRMED_EXPLICIT
    assert res.covering_instances


# --- V-5 / V-6: determinismo ------------------------------------------------

def test_v5_migration_is_deterministic(tmp_path):
    a = mig.run(apply=True, out_file=tmp_path / "a.jsonl", emit_audit=False)
    b = mig.run(apply=True, out_file=tmp_path / "b.jsonl", emit_audit=False)
    assert a["output_sha256"] == b["output_sha256"]
    assert (tmp_path / "a.jsonl").read_bytes() == (tmp_path / "b.jsonl").read_bytes()


def test_v6_status_projection_regenerates_identically(migrated):
    out, _ = migrated
    records = store.read_all(out)
    assert store.project_status(records) == store.project_status(store.read_all(out))


def test_rollback_is_deleting_one_derived_file(migrated):
    out, s = migrated
    before = s["input_sha256_before"]
    out.unlink()
    assert not out.exists()
    # Las entradas siguen exactamente igual: el rollback no tiene más pasos.
    assert hashlib.sha256(adapter.LEGACY_A_FILE.read_bytes()).hexdigest() == before["a"]
    assert hashlib.sha256(adapter.LEGACY_B_FILE.read_bytes()).hexdigest() == before["b"]


# --- reconstrucción del snapshot D1 -----------------------------------------

def test_d1_reconstruction_excludes_sources_copied_after_the_signature():
    ids, evidence = adapter.reconstruct_d1_snapshot("2026-07-29T00:15:15.595831+00:00")
    assert set(ids) == TWO_ORIGINALS
    assert PART211 not in ids
    assert PART11 not in ids
    assert set(evidence["excluded_as_later"]) >= LATER_INGESTED_NOT_COVERED
    assert evidence["confidence"] == "HIGH"


def test_d1_reconstruction_carries_its_evidence_into_the_record(migrated):
    out, _ = migrated
    d1 = [r for r in store.read_all(out) if r["decision_instance_id"] == "D1-2026-001"][0]
    assert d1["provenance"] == "RECONSTRUCTED_SNAPSHOT"
    assert d1["reconstruction_evidence"]["method"]
    assert d1["selection_mode"] == "ALL_SNAPSHOT"
    # "ALL" nunca queda almacenado como comodín: el conjunto está materializado.
    assert "ALL" not in d1["resolved_target_ids"]
    assert set(d1["resolved_target_ids"]) == TWO_ORIGINALS


def test_legacy_ids_are_preserved_in_the_payload(migrated):
    """MC-0001 y los uuid4 históricos deben seguir siendo rastreables."""
    out, _ = migrated
    legacy_ids = {r["payload"].get("legacy_decision_id") for r in store.read_all(out)}
    assert "MC-0001" in legacy_ids
    assert "caa2421d-d56b-4f23-927d-5d7d752e02d7" in legacy_ids
    assert "D1_regulatory_sources" in legacy_ids


def test_the_redo_registration_is_typed_as_a_correction(migrated):
    """Los dos ciclos de alta de Part 211 dejan de ser dos hechos sueltos:
    el segundo declara REHACER el primero (hallazgo A-7)."""
    out, _ = migrated
    corrections = [r for r in store.read_all(out)
                   if r["decision_family"] == "SOURCE_REGISTRATION"
                   and r["decision_type"] == "CORRECTION"]
    assert corrections
    assert all(c["supersedes_instance_id"] for c in corrections)


def test_apply_emits_exactly_one_audit_event(tmp_path, isolated_audit):
    before = len(isolated_audit.read_text(encoding="utf-8").splitlines()) \
        if isolated_audit.exists() else 0
    mig.run(apply=True, out_file=tmp_path / "d.jsonl", emit_audit=True)
    lines = isolated_audit.read_text(encoding="utf-8").splitlines()
    assert len(lines) - before == 1
    event = json.loads(lines[-1])
    assert event["event_type"] == "layer9_decision_store_migrated"
    assert event["data"]["inputs_untouched"] is True


# ===========================================================================
# Correcciones legacy — defecto destapado por una accion humana real
# ===========================================================================

def test_a_legacy_correction_projects_as_a_correction(migrated):
    """El adaptador tipaba TODA proyeccion del Sistema B como ORIGINAL.

    Salio a la luz cuando Cesar corrigio la cadencia de D1 (1 -> 3 meses) por
    la UI legacy DESPUES de migrar: el registro traia `record_type=correction`,
    `supersedes_recorded_at` y `correction_reason`, y el adaptador descartaba
    los tres. Se emitia un segundo ORIGINAL, con lo que la relacion de
    supersesion se perdia y quedaban DOS D1 ACTIVE -- "cual es la vigente"
    pasaba a ser ambiguo en v2 mientras el almacen legacy lo sabia.
    """
    out, _ = migrated
    recs = store.read_all(out)
    correcciones = [r for r in recs
                    if r["decision_family"] == "D1"
                    and r["decision_type"] == "CORRECTION"]
    if not correcciones:
        pytest.skip("no hay ninguna correccion legacy de D1 en este entorno")

    c = correcciones[-1]
    assert c["supersedes_instance_id"], "una CORRECTION sin a quien supersede"
    assert c["reason"], "el motivo vive en `correction_reason`, no en `reason`"
    assert c["payload"].get("legacy_corrected_fields"), "se perdio que campos cambiaron"


def test_only_one_d1_stays_active_after_a_legacy_correction(migrated):
    """La consecuencia que importa: la vigencia deja de ser ambigua."""
    out, _ = migrated
    recs = store.read_all(out)
    estados = store.project_status(recs)
    d1_activas = [r["decision_instance_id"] for r in recs
                  if r["decision_family"] == "D1"
                  and estados.get(r["decision_instance_id"]) == "ACTIVE"]
    assert len(d1_activas) == 1, f"D1 tiene {len(d1_activas)} registros ACTIVE: {d1_activas}"


def test_a_correction_that_cannot_resolve_its_original_degrades_and_declares_it(tmp_path):
    """Si `supersedes_recorded_at` no resuelve, se conserva como ORIGINAL y se
    DECLARA -- en vez de emitir una CORRECTION apuntando al vacio, que I-6
    marcaria invalida y nos haria perder tambien el registro.
    """
    legacy_b = tmp_path / "w5.jsonl"
    legacy_b.write_text(json.dumps({
        "decision_id": "D1_regulatory_sources", "record_type": "correction",
        "supersedes_recorded_at": "1999-01-01T00:00:00+00:00",
        "correction_reason": "motivo", "corrected_by": "cesar",
        "decision": "APPROVE", "approved_by": "cesar",
        "decision_date": "2026-07-29T00:15:15+00:00",
        "decision_origin": "human_confirmed",
        "recorded_at": "2026-07-29T22:00:00+00:00",
        "approved_source_ids": ["ecfr_21cfr_part11"],
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    recs = adapter.project_all(legacy_a=tmp_path / "no_existe.jsonl", legacy_b=legacy_b)
    r = recs[0]
    assert r["decision_type"] == "ORIGINAL"
    assert "correction_unresolved" in r["payload"]


# ===========================================================================
# Re-migrar no puede borrar una firma humana
# ===========================================================================

def test_reapplying_refuses_to_discard_native_records(tmp_path):
    """`--apply` sobrescribe el fichero entero.

    Hoy el almacen solo tiene proyecciones y re-migrar es inocuo; en cuanto
    Cesar firme la Correccion D1 por la UI deja de serlo. La guardia se pone
    ANTES de que exista el problema.
    """
    out = tmp_path / "d.jsonl"
    mig.run(apply=True, out_file=out, emit_audit=False)

    nativo = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["ecfr_21cfr_part11"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-900", store_file=out)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(nativo, ensure_ascii=False) + "\n")

    assert mig.native_records(out) == ["D1-2026-900"]
    with pytest.raises(mig.WouldDiscardNativeRecords):
        mig.run(apply=True, out_file=out, emit_audit=False)

    # Y la firma sigue ahi: abortar no puede dejar el fichero a medias.
    assert "D1-2026-900" in {r["decision_instance_id"] for r in store.read_all(out)}


def test_force_is_the_only_way_to_discard_them(tmp_path):
    """Existe la salida, pero hay que pedirla explicitamente."""
    out = tmp_path / "d.jsonl"
    mig.run(apply=True, out_file=out, emit_audit=False)
    nativo = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["ecfr_21cfr_part11"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-900", store_file=out)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(nativo, ensure_ascii=False) + "\n")

    mig.run(apply=True, force=True, out_file=out, emit_audit=False)
    assert "D1-2026-900" not in {r["decision_instance_id"] for r in store.read_all(out)}


def test_staleness_is_detectable(tmp_path):
    """La migracion es un disparo unico y los almacenes legacy siguen vivos.

    Una escritura legacy posterior deja el v2 desincronizado y nada lo notaba:
    es como se descubrio que faltaba el registro 15.
    """
    out = tmp_path / "d.jsonl"
    mig.run(apply=True, out_file=out, emit_audit=False)
    assert mig.is_stale(out)["stale"] is False

    out.write_text("", encoding="utf-8")
    assert mig.is_stale(out)["stale"] is True


def test_a_native_signature_does_not_make_the_store_stale(tmp_path):
    """Firmar por la UI no es desincronizar. G2.1.

    `is_stale` comparaba el TEXTO COMPLETO del fichero contra la proyeccion, asi
    que el primer registro nativo la dejaba en rojo PARA SIEMPRE -- y un rojo
    permanente no puede senalar nada. La guardia se volvia incapaz justo de lo
    que existe para detectar: una escritura legacy sin re-migrar.
    """
    out = tmp_path / "d.jsonl"
    mig.run(apply=True, out_file=out, emit_audit=False)
    assert mig.is_stale(out)["stale"] is False

    nativo = store.build_record(
        decision_family="D1", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["ecfr_21cfr_part11"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D1-2026-900", store_file=out)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(nativo, ensure_ascii=False) + "\n")

    st = mig.is_stale(out)
    assert st["stale"] is False, "una firma nativa no desincroniza nada"
    assert st["native_records"] == ["D1-2026-900"]
    # Los dos conteos son DISTINTOS y por eso se reportan por separado: el
    # mensaje de la guardia comparaba el total contra la proyeccion y por tanto
    # describia una discrepancia que no era la que medía.
    assert st["records_in_store"] == st["records_migrated_in_store"] + 1

    # Y sigue detectando lo de verdad: se toca un registro MIGRADO.
    registros = store.read_all(out)
    migrado = next(r for r in registros
                   if r["provenance"] in mig.MIGRATION_PROVENANCES)
    migrado["reason"] = "manoseado a mano sin re-migrar"
    out.write_text("".join(
        json.dumps(r, ensure_ascii=False) + "\n"
        for r in registros), encoding="utf-8")
    assert mig.is_stale(out)["stale"] is True


def test_adding_a_family_does_not_desync_the_store(tmp_path, monkeypatch):
    """La REGLA DURA de decision_families.yaml, comprobada. G2.1.

    `families_registry_hash` es una foto del registro de familias al grabar, asi
    que al recomputar la proyeccion con una familia nueva los 15 registros
    migrados salian desincronizados de golpe. Eso hacia de "anadir una familia"
    una operacion que obliga a re-migrar el almacen -- exactamente lo que el
    fichero de familias promete que no pasa. Se descubrio anadiendo
    RECORD_ANNOTATION.
    """
    out = tmp_path / "d.jsonl"
    mig.run(apply=True, out_file=out, emit_audit=False)
    assert mig.is_stale(out)["stale"] is False

    familias = store.load_families()
    familias["FAMILIA_NUEVA_DE_PRUEBA"] = {
        "label": "familia inventada por el test",
        "target_kind": "none", "target_registry": None,
        "target_registry_id_path": None,
        "selection_modes": ["EXPLICIT_LIST"], "consumers": [],
        "requires_human_confirmation": False, "never_authorizes": True,
    }
    monkeypatch.setattr(store, "load_families", lambda *a, **k: familias)
    monkeypatch.setattr(
        store, "families_registry_hash",
        lambda *a, **k: "0" * 64)

    st = mig.is_stale(out)
    assert st["stale"] is False, (
        "anadir una familia cambia families_registry_hash pero no cambia "
        "ninguna decision: el almacen no esta desincronizado")


def test_the_real_store_is_in_sync_with_the_legacy_stores():
    """Guardia sobre el estado real: si alguien escribe en un almacen legacy sin
    re-migrar, este test lo dice en vez de dejar que el resolver lea un estado
    que ya no existe."""
    if not store.STORE_FILE.exists():
        pytest.skip("almacen v2 no migrado en este entorno")
    st = mig.is_stale()
    assert not st["stale"], (
        f"el almacen v2 esta desincronizado: {st['records_migrated_in_store']} "
        f"registros migrados en el almacen frente a {st['records_projected']} "
        f"proyectados. Re-ejecuta la migracion. (Los {len(st['native_records'])} "
        "registros NATIVOS quedan fuera de la comparacion a proposito: la "
        "migracion no los produjo.)")
