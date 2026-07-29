"""W5 Ciclo 1 (v2), Fase 4, Bloque 4.4 — regresion Golden Dataset (C1-C4
reales). Determinista, sin llamar a Ollama: usa llm_output_original de cada
caso como entrada directa al verificador v2.

Solo los casos con complete=true entran al Gate 0 (C1, C3 -- ver
factory/eval/golden_dataset/cases/*.json y sus source_refs). C2/C4 quedan
marcados complete=false (dato no recuperable de los registros persistidos,
ver notas en esos archivos) -- se reportan pero no se ejecutan como
aserciones de regresion, tal como exige el plan ('prohibido rellenar con
contenido plausible')."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.regulatory.evidence_verifier import load_requirement_terms, verify_llm_output

CASES_DIR = Path(__file__).parent.parent / "eval" / "golden_dataset" / "cases"

KNOWN_REQS = {
    "21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)",
    "21_CFR_11.50_11.70", "ANNEX11_4", "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12",
    "ANNEX11_17", "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS",
    "ALCOA_ORIGINAL", "ALCOA_ACCURATE", "ALCOA_COMPLETE", "ALCOA_CONSISTENT",
    "ALCOA_ENDURING", "ALCOA_AVAILABLE",
}


def _load_all_cases() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("*.json"))]


def _v1_estado_to_v2_observation(estado: str) -> str:
    """Adaptacion declarada: los casos reales C1-C4 se registraron con el
    schema v1 (estado directo a nivel de chunk, ANTERIOR a finding_llm_v1
    de Fase 1) -- no existe una grabacion historica en formato
    chunk_observation. 'cumple'/'cumple_parcialmente' -> 'observed' (el
    modelo SI encontro y cito texto en el chunk -- la separacion
    observacion/conclusion es precisamente lo que v2 corrige, ver P3);
    'no_cumple' sin cita -> 'not_observed_in_chunk'; 'evidencia_insuficiente'
    -> 'not_observed_in_chunk' (sin evidencia citada)."""
    return {
        "cumple": "observed",
        "cumple_parcialmente": "observed",
        "no_cumple": "not_observed_in_chunk",
        "evidencia_insuficiente": "not_observed_in_chunk",
    }.get(estado, "not_observed_in_chunk")


ALL_CASES = _load_all_cases()
COMPLETE_CASES = [c for c in ALL_CASES if c.get("complete") is True]
INCOMPLETE_CASES = [c for c in ALL_CASES if c.get("complete") is False]


def test_golden_dataset_keeps_the_four_historical_cases_and_declares_the_rest():
    """C1-C4 son los casos historicos reales: ninguno puede desaparecer, que
    es la regresion que importa. Antes se exigia igualdad exacta, asi que
    ANADIR un caso nuevo -- ampliar el dataset, algo deseable -- rompia el
    test. Un caso nuevo entra sin fricción, pero debe declarar `complete` y
    un req_id conocido como todos los demas."""
    ids = {c["case_id"] for c in ALL_CASES}
    assert {"C1", "C2", "C3", "C4"} <= ids, f"caso historico perdido: {{'C1','C2','C3','C4'}} - {ids}"
    for case in ALL_CASES:
        assert isinstance(case.get("complete"), bool), case["case_id"]
        assert case["requirement_id"] in KNOWN_REQS, (case["case_id"], case["requirement_id"])


def test_incomplete_cases_declare_pending_fields_not_fabricated():
    """Ningun caso complete=false puede tener contenido plausible inventado
    en los campos que declara PENDING -- deben literalmente contener el
    marcador 'PENDING'."""
    for case in INCOMPLETE_CASES:
        chunk = case["chunk"]
        assert "PENDING" in str(chunk.get("source_text", ""))
        llm = case["llm_output_original"]
        assert "PENDING" in str(llm.get("evidencia_exacta", ""))


@pytest.mark.parametrize("case", COMPLETE_CASES, ids=[c["case_id"] for c in COMPLETE_CASES])
def test_golden_case_matches_expected_v2_behavior(case):
    """Caso real C1/C3: la cita ESTA anclada literalmente (era real, no
    inventada) pero es tematicamente irrelevante al requisito evaluado --
    v2 debe producir review_required + RELEVANCE_REVIEW_REQUIRED, NUNCA
    un hallazgo 'verified' limpio (el defecto real que produjo C1/C3) ni
    un rechazo automatico (la cita SI existe, rechazarla seria un falso
    negativo de otro tipo)."""
    original = case["llm_output_original"]
    llm_output = {
        "requirement_id": case["requirement_id"],
        "chunk_observation": _v1_estado_to_v2_observation(original["estado"]),
        "evidence_quote": original["evidencia_exacta"],
        "evidence_page": case["chunk"]["page_start"],
        "confidence": 0.7,
        "rationale": "Reconstruido desde registro real (ver source_refs).",
        "flags": [],
    }
    chunk = {
        "text": case["chunk"]["source_text"],
        "page_start": case["chunk"]["page_start"],
        "page_end": case["chunk"]["page_end"],
    }
    terms = load_requirement_terms(case["requirement_id"])

    result = verify_llm_output(llm_output, chunk, KNOWN_REQS, terms)

    expected = case["expected_behavior_v2"]
    assert result.status == expected["verifier_status"], (
        f"{case['case_id']}: esperado {expected['verifier_status']!r}, "
        f"obtenido {result.status!r} (checks={result.checks})"
    )
    for flag in expected["expected_flags"]:
        assert flag in result.review_flags, (
            f"{case['case_id']}: flag esperado {flag!r} no presente en {result.review_flags}"
        )
    # El defecto real que este caso corrige: NUNCA debe salir 'verified' limpio.
    assert result.status != "verified", (
        f"{case['case_id']}: v2 NO debe reproducir el defecto original "
        f"(hallazgo 'verified' limpio sobre una cita tematicamente irrelevante)"
    )
    # Tampoco un rechazo automatico -- la cita SI existe literalmente.
    assert result.status != "rejected_by_verifier", (
        f"{case['case_id']}: la cita esta anclada literalmente, rechazarla "
        f"automaticamente seria incorrecto -- debe ir a revision, no a rechazo"
    )


def test_c1_and_c3_citation_is_exactly_anchored_not_fabricated():
    """Confirma que, para los casos completos, la cita real SI aparece
    literalmente en el texto real del chunk (prueba de que C1/C3 no son
    casos de cita inventada, sino de relevancia mal evaluada -- la
    distincion central que motiva el check V5 de Fase 2)."""
    from factory.regulatory.evidence_verifier import match_citation

    for case in COMPLETE_CASES:
        original = case["llm_output_original"]
        match_type, score = match_citation(original["evidencia_exacta"], case["chunk"]["source_text"])
        assert match_type in ("exact", "normalized"), (
            f"{case['case_id']}: la cita deberia estar anclada literalmente "
            f"(match_type={match_type}, score={score})"
        )
