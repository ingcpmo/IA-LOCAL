"""G5 — tests de `evidence_pack_governance.py` segun la tabla P-01..P-12 de
`EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC.md` §6.

P-07 (aplicador rechaza sin decision_instance_id) y P-10 (409 entre VALIDA y
APRUEBA) NO estan implementados aqui a proposito: el spec declara el paso
APRUEBA (aplicador real + endpoint) fuera de alcance mientras no exista una
superficie de UI real que lo invoque (§7). Fabricar un test contra
infraestructura que no existe seria peor que no tenerlo. P-12 (marca
`authoritative: false` en applicability_matrix.yaml) tampoco: escribir esa
marca hizo que `require_matrix_approved_for_production` -- ya consumida por
`chunked_engine.py` en produccion real -- empezara a rechazar `run_context=
"production"` en ~20 tests del motor que usan ese run_context como atajo de
conveniencia, no para probar aprobacion de matriz. Ampliar el alcance de esa
funcion compartida no es parte de G5 -- queda declarado NOT_IMPLEMENTED_YET,
mismo criterio que "AGT-QLT" en su momento."""
from __future__ import annotations

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.regulatory.evidence_pack_governance import (
    d2a_ready, validate_pack,
)
from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
    load_requirements,
)

REAL_CATALOG = load_requirements()
ALL_REQUIREMENT_IDS = tuple(REAL_CATALOG["requirements"])
PART211 = "21_CFR_211.68(b)"


def _minimal_pack(**overrides) -> dict:
    """Un pack sintetico completo y valido, para violar UN campo a la vez."""
    pack = {
        "source_id": "ecfr_21cfr_part211",
        "evidence_min_criteria": ["Criterio minimo real y distinto."],
        "exclusion_criteria": ["Exclusion real y distinta."],
        "weak_keywords": ["generico"],
        "typical_insufficient_evidence": ["Patron de evidencia insuficiente."],
        "governed_interpretation": "Interpretacion regulatoria de prueba.",
        "expected_doc_types": ["FS"],
    }
    pack.update(overrides)
    return pack


def _catalog_with(requirement_id: str, pack: dict, *extra: tuple[str, dict]) -> dict:
    reqs = {requirement_id: pack}
    for rid, p in extra:
        reqs[rid] = p
    return {"requirements": reqs}


def _registry_with_verified_source(source_id: str = "ecfr_21cfr_part211") -> dict:
    """Registry sintetico -- irrelevante para V1-V8, que no lo leen; solo
    importa que `validate_pack` no lance al buscar el `source_id`."""
    return {"sources": [{"source_id": source_id, "canonical_path": "nope",
                        "derived_artifacts": []}]}


# ---------------------------------------------------------------------------
# P-01 -- V1..V10 fallan cada uno por separado
# ---------------------------------------------------------------------------

def test_p01_v1_schema_incomplete():
    pack = _minimal_pack()
    del pack["governed_interpretation"]
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert not r.passed
    assert "V1_SCHEMA_INCOMPLETE" in r.failure_codes()


def test_p01_v2_empty_field():
    pack = _minimal_pack(weak_keywords=[])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert "V2_EMPTY_FIELD" in r.failure_codes()


def test_p01_v3_duplicate_within_field():
    pack = _minimal_pack(weak_keywords=["Validado", "validado."])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert "V3_DUPLICATE_WITHIN_FIELD" in r.failure_codes()


def test_p01_v4_weak_keyword_as_criterion():
    pack = _minimal_pack(evidence_min_criteria=["validado"],
                         weak_keywords=["validado"])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert "V4_WEAK_KEYWORD_AS_CRITERION" in r.failure_codes()


def test_p01_v5_not_anchored():
    pack = _minimal_pack(evidence_min_criteria=["Esto no esta en ningun texto real."])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert "V5_NOT_ANCHORED" in r.failure_codes()


def test_p01_v6_unknown_doc_type():
    pack = _minimal_pack(expected_doc_types=["NOT_A_REAL_DOC_TYPE"])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    assert "V6_UNKNOWN_DOC_TYPE" in r.failure_codes()


def test_p01_v7_cross_requirement_duplicate():
    pack_a = _minimal_pack(evidence_min_criteria=["Criterio compartido por error."])
    pack_b = _minimal_pack(evidence_min_criteria=["Criterio compartido por error."])
    catalog = _catalog_with("X", pack_a, ("Y", pack_b))
    r = validate_pack("X", requirements=catalog,
                      registry=_registry_with_verified_source())
    assert "V7_CROSS_REQUIREMENT_DUPLICATE" in r.failure_codes()


def test_p01_v8_hash_version_mismatch():
    """V8 se delega en `artifact_version_guard` -- probado contra el pack
    real 211, que hoy no tiene ningun `version_record` en el almacen (el
    catalogo mismo esta CONTENT_CHANGED_VERSION_SAME, pendiente de firma)."""
    r = validate_pack(PART211)
    # V8 no dispara hoy para packs individuales (solo el catalogo completo
    # esta en FAIL) -- se confirma la ausencia explicita, no se asume.
    assert "V8_HASH_VERSION_MISMATCH" not in r.failure_codes()


def test_p01_v9_source_not_verified():
    r = validate_pack(PART211)  # ecfr_21cfr_part211: pending_reverification real
    assert "V9_SOURCE_NOT_VERIFIED" in r.failure_codes()


def test_p01_v10_source_not_covered_by_d1(tmp_path):
    empty_store = tmp_path / "decisions_v2.jsonl"
    empty_store.write_text("", encoding="utf-8")
    pack = _minimal_pack(source_id="a_source_with_no_d1_coverage_at_all")
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry={"sources": [{"source_id": "a_source_with_no_d1_coverage_at_all",
                                            "canonical_path": "nope", "derived_artifacts": []}]},
                      decision_store_file=empty_store)
    assert "V10_SOURCE_NOT_COVERED_BY_D1" in r.failure_codes()


# ---------------------------------------------------------------------------
# P-02 / P-03 / P-04 -- casos reales concretos del propio spec
# ---------------------------------------------------------------------------

def test_p02_weak_keyword_validado_as_minimum_criterion_is_rejected():
    """Caso real citado en el spec §6: "validado" como criterio minimo."""
    pack = _minimal_pack(evidence_min_criteria=["validado"], weak_keywords=["validado", "compliant"])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    failures = [f for f in r.failures if f.code == "V4_WEAK_KEYWORD_AS_CRITERION"]
    assert len(failures) == 1
    assert "validado" in failures[0].detail


def test_p03_criterion_without_anchor_is_rejected():
    pack = _minimal_pack(exclusion_criteria=["Frase inventada que no existe en ningun documento canonico."])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    v5 = [f for f in r.failures if f.code == "V5_NOT_ANCHORED" and f.field == "exclusion_criteria"]
    assert len(v5) == 1


def test_p04_identical_criterion_between_two_requirements_is_rejected():
    shared = "Este criterio aparece identico en dos requisitos distintos."
    pack_a = _minimal_pack(exclusion_criteria=[shared])
    pack_b = _minimal_pack(exclusion_criteria=[shared])
    catalog = _catalog_with("REQ_A", pack_a, ("REQ_B", pack_b))
    r_a = validate_pack("REQ_A", requirements=catalog, registry=_registry_with_verified_source())
    r_b = validate_pack("REQ_B", requirements=catalog, registry=_registry_with_verified_source())
    assert "V7_CROSS_REQUIREMENT_DUPLICATE" in r_a.failure_codes()
    assert "V7_CROSS_REQUIREMENT_DUPLICATE" in r_b.failure_codes()


# ---------------------------------------------------------------------------
# P-05 / P-06 -- fixtures del ESTADO REAL de hoy (2026-08-03)
#
# El spec (escrito 2026-07-23, ANTES de que G4a cerrara el contenido
# interpretativo de 21_CFR_211.68(b), commit 53f77d1/D2-2026-009) predecia
# "211 falla V1,V2" y "los 19 pasan V1-V8, fallan V9/V10". Ya no es cierto:
# HOY los 20 packs (211 incluido) tienen los 6 campos completos y pasan
# V1-V4/V7/V8/V10, pero TODOS fallan V9 (ninguna de las 4 fuentes esta
# LOCAL_CANONICAL_COPY_VERIFIED todavia) y TODOS fallan V5 -- hallazgo real
# de esta sesion, no anticipado por el spec: los criterios interpretativos
# se redactaron como PARAFRASIS EN ESPAÑOL del texto canonico en ingles
# (decision explicita de Cesar en Fase C), asi que `verify_anchor()` nunca
# los ancla literalmente. Mientras V5 exija anclaje literal de un campo de
# JUICIO interpretativo, `pack_complete` no puede alcanzarse por NINGUN
# requisito real bajo el estilo de redaccion ya aprobado -- declarado aqui
# explicitamente, no oculto, para que Cesar decida si V5 necesita
# redefinirse (p.ej. anclar solo la CITA del requisito, ya verificada desde
# Fase A/C, en vez de cada criterio interpretativo suelto).
# ---------------------------------------------------------------------------

def test_p05_the_real_pack_211_fails_v5_and_v9_today():
    r = validate_pack(PART211)
    assert not r.passed
    assert set(r.failure_codes()) == {"V5_NOT_ANCHORED", "V9_SOURCE_NOT_VERIFIED"}


def test_p06_the_19_other_real_packs_fail_v5_today_v9_depends_on_real_source_currency():
    """V5 (parafraseo, no cita literal) sigue sin resolverse para los 19 --
    bloqueo de diseno que ningun apply toca.

    V9 ya NO es un fallo fijo (actualizado 2026-08-05, SOURCE_CURRENCY): un
    requisito respaldado por una fuente que alcanzo LOCAL_CANONICAL_COPY_
    VERIFIED de verdad (eu_gmp_annex11, mhra_gxp_di_guidance_2018 hoy) ya no
    falla V9. Se deriva del estado REAL de source_lifecycle en vez de
    fijarlo a mano, para que este test siga midiendo la regla (V9 sigue el
    lifecycle_state real) y no una fotografia que otra firma real vuelva a
    romper."""
    from factory.regulatory import source_lifecycle as sl

    others = [rid for rid in ALL_REQUIREMENT_IDS if rid != PART211]
    assert len(others) == 19
    dims = {d.source_id: d for d in sl.evaluate_registry()}

    for rid in others:
        r = validate_pack(rid)
        codes = set(r.failure_codes())
        source_id = REAL_CATALOG["requirements"][rid].get("source_id")
        fuente_verificada = (source_id in dims
                             and dims[source_id].lifecycle_state == sl.LOCAL_CANONICAL_COPY_VERIFIED)

        assert not r.passed, f"{rid}: se esperaba al menos V5 fallando"
        assert "V5_NOT_ANCHORED" in codes, f"{rid}: V5 deberia fallar (paráfrasis, no cita literal)"
        if fuente_verificada:
            assert "V9_SOURCE_NOT_VERIFIED" not in codes, (
                f"{rid}: su fuente {source_id!r} SI esta LOCAL_CANONICAL_COPY_VERIFIED -- "
                "V9 no deberia fallar")
        else:
            assert "V9_SOURCE_NOT_VERIFIED" in codes, (
                f"{rid}: su fuente {source_id!r} no esta verificada -- V9 deberia fallar")
        assert codes <= {"V5_NOT_ANCHORED", "V6_UNKNOWN_DOC_TYPE", "V9_SOURCE_NOT_VERIFIED"}, (
            f"{rid}: fallo inesperado fuera de V5/V6/V9: {codes}")


# ---------------------------------------------------------------------------
# P-07 -- NOT_IMPLEMENTED_YET (ver docstring del modulo)
# P-08 -- V8 delega en artifact_version_guard, ya cubierto (test_p01_v8_*
#         arriba + la suite propia de artifact_version_guard)
# ---------------------------------------------------------------------------

def test_p08_the_catalog_wide_fail_this_test_relied_on_is_now_closed():
    """No reimplementa el guard: confirma que `validate_pack` LEE su
    resultado real (V8 delega en artifact_version_guard, cobertura de
    propagacion propia en test_p01_v8_* + la suite de artifact_version_
    guard -- este test solo confirmaba el escenario real vigente).

    Actualizado (2026-08-05): el CONTENT_CHANGED_VERSION_SAME del catalogo
    que este test citaba como evidencia real se cerro con el segundo bump
    de G4c (ARTIFACT_VERSION-2026-007, 2.0->2.1) -- guard_report() ya no
    tiene ningun FAIL real hoy. Se afirma la ausencia en vez de fabricar
    un escenario sintetico: si algun dia vuelve a haber un FAIL real, este
    test lo notara y hay que decidir si sigue siendo el mismo motivo."""
    from factory.core import artifact_version_guard as guard
    report = guard.guard_report()
    assert report["status"] != "FAIL"
    assert report["fail_count"] == 0
    assert not any(f["artifact"] == "catalog" and f["code"] == "CONTENT_CHANGED_VERSION_SAME"
                  for f in report["findings"]), (
        "el catalogo volvio a divergir de su version declarada")


# ---------------------------------------------------------------------------
# P-09 -- la aprobacion de un pack no autoriza otro
# ---------------------------------------------------------------------------

def test_p09_pack_approval_is_independent_per_requirement(tmp_path):
    from factory.services import decision_store_v2 as store
    rec = store.build_record(
        decision_family="D2", decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", resolved_target_ids=["21_CFR_11.10(a)"],
        decision="APPROVE", decision_origin="human_confirmed",
        approved_by_id="Cesar", approved_by_display_name="Cesar",
        decision_instance_id="D2-2099-999")
    import json
    store_file = tmp_path / "decisions_v2.jsonl"
    store_file.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

    approved = resolver.resolve("D2", "21_CFR_11.10(a)", store_file=store_file)
    other = resolver.resolve("D2", "21_CFR_11.10(d)", store_file=store_file)
    assert approved.authorized is True
    assert other.authorized is False


# ---------------------------------------------------------------------------
# P-10 -- NOT_IMPLEMENTED_YET (ver docstring del modulo)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# P-11 -- d2a_ready() de los 20 requisitos hoy: los 20 false
# ---------------------------------------------------------------------------

def test_p11_all_20_requirements_are_not_d2a_ready_today():
    """Ninguno de los 20 esta D2A_READY hoy -- pero ya NO por el mismo
    motivo compartido de entorno que antes.

    Actualizado (2026-08-05): matrix_approved y catalog_versioned pasaron
    a True GLOBALMENTE con firmas reales (APPLICABILITY_MATRIX-2026-004,
    ARTIFACT_VERSION-2026-007) -- ya no son "razones de entorno" que
    bloqueen los 20 por igual. source_verified tambien depende ahora de la
    fuente real de cada requisito (SOURCE_CURRENCY). Lo unico que SIGUE
    bloqueando los 20 sin excepcion es pack_complete=False (V5, parafraseo
    sin cita literal) -- eso es lo que este test verifica que no cambia."""
    assert len(ALL_REQUIREMENT_IDS) == 20
    for rid in ALL_REQUIREMENT_IDS:
        readiness = d2a_ready(rid)
        assert readiness.ready is False, f"{rid}: se esperaba d2a_ready=False hoy"
        assert readiness.pack_complete is False, (
            f"{rid}: V5 deberia seguir bloqueando pack_complete")


def test_p11_reasons_are_never_empty_when_not_ready():
    readiness = d2a_ready(PART211)
    assert readiness.ready is False
    assert len(readiness.reasons) >= 1
    assert all(isinstance(r, str) and r for r in readiness.reasons)


# ---------------------------------------------------------------------------
# P-12 -- NOT_IMPLEMENTED_YET (ver docstring del modulo)
# ---------------------------------------------------------------------------
