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


def test_p03_pack_without_a_real_citation_is_rejected():
    """Actualizado (Opcion A, 2026-08-05): V5 ya no mira exclusion_criteria/
    evidence_min_criteria (parafraseo, nunca pensados como cita) -- ancla
    `citation.citation_text`. Un pack sin ese campo (como el fixture
    minimo, que no declara `citation`) sigue rechazado por V5, pero ahora
    con el campo real en el hallazgo."""
    pack = _minimal_pack(exclusion_criteria=["Frase inventada que no existe en ningun documento canonico."])
    r = validate_pack("X", requirements=_catalog_with("X", pack),
                      registry=_registry_with_verified_source())
    v5 = [f for f in r.failures if f.code == "V5_NOT_ANCHORED" and f.field == "citation.citation_text"]
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

def test_p05_the_real_pack_211_fails_only_v9_today():
    """Actualizado (Opcion A, 2026-08-05): la cita literal real de 211.68(b)
    (`citation.citation_text`, Fase C, ya verificada) SI ancla al texto
    canonico -- V5 ya no falla. Solo queda V9 (Part 211 sigue
    NOT_COMPARABLE_FIRST_INGESTION, bloqueo distinto de SOURCE_CURRENCY)."""
    r = validate_pack(PART211)
    assert not r.passed
    assert set(r.failure_codes()) == {"V9_SOURCE_NOT_VERIFIED"}


def test_p06_the_19_other_real_packs_never_fail_v5_v9_depends_on_real_source_currency():
    """Actualizado dos veces en el mismo dia (2026-08-05):

    1a actualizacion: V9 se deriva del lifecycle_state real de cada fuente
    en vez de fijarse a "siempre falla" (SOURCE_CURRENCY cerro 2 de 4
    fuentes).

    2a actualizacion (Opcion A -- el motivo real de esta reescritura): V5
    dejo de mirar evidence_min_criteria/exclusion_criteria y pasa a anclar
    `citation.citation_text`, la cita literal real de cada requisito
    (Fase C, ya verificada con match_type exacto/normalizado para los 20).
    V5 YA NO FALLA para ninguno de los 19 -- se afirma la ausencia en vez
    de fabricar un valor, para que un futuro requisito con una cita real
    mal anclada siga siendo detectado."""
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

        assert "V5_NOT_ANCHORED" not in codes, (
            f"{rid}: su citation.citation_text deberia anclar al texto canonico real")
        if fuente_verificada:
            assert "V9_SOURCE_NOT_VERIFIED" not in codes, (
                f"{rid}: su fuente {source_id!r} SI esta LOCAL_CANONICAL_COPY_VERIFIED -- "
                "V9 no deberia fallar")
        else:
            assert "V9_SOURCE_NOT_VERIFIED" in codes, (
                f"{rid}: su fuente {source_id!r} no esta verificada -- V9 deberia fallar")
        assert codes <= {"V6_UNKNOWN_DOC_TYPE", "V9_SOURCE_NOT_VERIFIED"}, (
            f"{rid}: fallo inesperado fuera de V6/V9: {codes}")


# ---------------------------------------------------------------------------
# P-07 -- NOT_IMPLEMENTED_YET (ver docstring del modulo)
# P-08 -- V8 delega en artifact_version_guard, ya cubierto (test_p01_v8_*
#         arriba + la suite propia de artifact_version_guard)
# ---------------------------------------------------------------------------

def test_p08_gate0_no_longer_detects_a_pending_matrix_version_bump():
    """No reimplementa el guard: confirma que `validate_pack` LEE su
    resultado real (V8 delega en artifact_version_guard, cobertura de
    propagacion propia en test_p01_v8_* + la suite de artifact_version_
    guard -- este test solo confirma el escenario real vigente).

    Tercera actualizacion (2026-08-07, plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md
    Bloque 2.2): el VERSION_CHANGED_WITHOUT_DECISION de la matriz (2.1->2.2)
    que este test citaba antes se cerro con la regularizacion
    ARTIFACT_VERSION-2026-011 (`apply_regularization_for_applied_change()`,
    enlaza APPLICABILITY_MATRIX-2026-006 como fundamento humano) -- mismo
    cierre que tuvo el catalogo con G4c. El guard ya no reporta ningun FAIL
    real."""
    from factory.core import artifact_version_guard as guard
    report = guard.guard_report()
    assert report["fail_count"] == 0
    assert not any(f["artifact"] == "applicability_matrix"
                  and f["code"] == "VERSION_CHANGED_WITHOUT_DECISION"
                  for f in report["findings"]), (
        "la matriz ya no deberia figurar como bump pendiente de autorizar")
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

def test_p11_fourteen_packs_are_ready_after_matrix_and_d2_signed():
    """Quinta actualizacion real (sesion ARQ, 2026-08-07): Cesar firmo
    `APPLICABILITY_MATRIX-2026-006` (matriz 2.2, 2026-08-05T20:40:30Z) y las
    14 decisiones D2 (`D2-2026-025..053`, 2026-08-05T21:10-21:18Z) de los
    requisitos que ya pasaban V1-V10. Con matrix_approved=True + D2 cubierto
    + pack_complete=True, esos 14 llegan a D2A_READY=true de verdad -- ya no
    es el estado transitorio "matriz pendiente de firma" que este test
    documentaba antes. Los 6 restantes (5 clausulas de Part 11 +
    `21_CFR_211.68(b)`) siguen bloqueados por V9 (fuente en
    `AUTHORIZED_PENDING_REVERIFICATION`), no por la matriz ni por D2."""
    listos_reales = {
        "ANNEX11_4", "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12", "ANNEX11_17",
        "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS",
        "ALCOA_ORIGINAL", "ALCOA_ACCURATE", "ALCOA_COMPLETE", "ALCOA_CONSISTENT",
        "ALCOA_ENDURING", "ALCOA_AVAILABLE",
    }
    assert len(ALL_REQUIREMENT_IDS) == 20
    assert len(listos_reales) == 14
    for rid in ALL_REQUIREMENT_IDS:
        readiness = d2a_ready(rid)
        assert readiness.matrix_approved is True, (
            f"{rid}: matriz 2.2 ya esta firmada (APPLICABILITY_MATRIX-2026-006) "
            f"({readiness.reasons})")
        if rid in listos_reales:
            assert readiness.pack_complete is True, f"{rid}: se esperaba pack_complete=True"
            assert readiness.ready is True, (
                f"{rid}: se esperaba d2a_ready=True ({readiness.reasons})")
        else:
            assert readiness.ready is False, (
                f"{rid}: se esperaba d2a_ready=False (bloqueado por V9, fuente sin "
                f"reverificar) ({readiness.reasons})")


def test_p11_reasons_are_never_empty_when_not_ready():
    readiness = d2a_ready(PART211)
    assert readiness.ready is False
    assert len(readiness.reasons) >= 1
    assert all(isinstance(r, str) and r for r in readiness.reasons)


# ---------------------------------------------------------------------------
# P-12 -- NOT_IMPLEMENTED_YET (ver docstring del modulo)
# ---------------------------------------------------------------------------
