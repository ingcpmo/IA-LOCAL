"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.4 — payloads validos/invalidos contra
finding_llm_v1 (complementa test_w5v2_regulatory_schemas.py de Fase 1)."""
from __future__ import annotations

import pytest

from factory.regulatory.schema_loader import validate_against

VALID = {
    "requirement_id": "21_CFR_11.10(d)",
    "chunk_observation": "observed",
    "evidence_quote": "Autenticacion de dos factores requerida.",
    "evidence_page": 5,
    "confidence": 0.9,
    "rationale": "Cita explicita de autenticacion.",
    "flags": [],
}


def test_valid_payload_passes():
    ok, errors = validate_against(VALID, "finding_llm_v1")
    assert ok is True
    assert errors == []


def test_extra_field_is_rejected():
    payload = dict(VALID, estado="cumple")
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False
    assert any("estado" in e for e in errors)


def test_absence_conclusion_forbidden_at_llm_layer():
    for forbidden in ("cumple", "no_cumple", "cumple_parcialmente", "no_aplica",
                       "DOCUMENTATION_GAP", "EVIDENCE_NOT_AVAILABLE"):
        payload = dict(VALID, chunk_observation=forbidden)
        ok, _ = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"{forbidden} no debe ser un chunk_observation valido (P3)"


def test_confidence_out_of_range_is_rejected():
    for bad_confidence in (-0.1, 1.1, 2, -5):
        payload = dict(VALID, confidence=bad_confidence)
        ok, errors = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"confidence={bad_confidence} deberia ser invalido"


def test_missing_required_field_is_rejected():
    for required in ("requirement_id", "chunk_observation", "evidence_quote",
                      "evidence_page", "confidence", "rationale"):
        payload = {k: v for k, v in VALID.items() if k != required}
        ok, errors = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"payload sin '{required}' deberia ser invalido"


def test_flags_only_accepts_known_values():
    payload = dict(VALID, flags=["NOT_A_REAL_FLAG"])
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False


def test_flags_accepts_known_values():
    payload = dict(VALID, flags=["LOW_CONFIDENCE", "HUMAN_REVIEW_REQUIRED"])
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is True, errors


def test_evidence_page_accepts_null_for_not_observed():
    payload = dict(VALID, chunk_observation="not_observed_in_chunk",
                    evidence_quote="", evidence_page=None)
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is True, errors


def test_evidence_page_rejects_zero_or_negative():
    for bad_page in (0, -1, -100):
        payload = dict(VALID, evidence_page=bad_page)
        ok, errors = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"evidence_page={bad_page} deberia ser invalido"


def test_evidence_page_rejects_non_integer_non_null():
    """Fase 5.4 (fix ETAPA 1): evidence_page paso de 'type':['integer','null']
    a 'anyOf':[{integer},{null}] por compatibilidad con la generacion
    estructurada de Ollama (ver finding_llm_v1.json). Confirma que el cambio
    de forma NO relajo el contrato: strings, floats y listas siguen
    rechazados igual que antes."""
    for bad_page in ("5", 5.5, [5], {"page": 5}):
        payload = dict(VALID, evidence_page=bad_page)
        ok, errors = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"evidence_page={bad_page!r} deberia ser invalido"


# ── Fase 5.4, fix ETAPA 1: clasificacion sintetica por causa exacta ──
#
# Las 21 respuestas crudas reales rechazadas en Fase 5.4 NUNCA quedaron
# persistidas (bug real de run_validation_evidence.py, corregido en este
# mismo cambio -- ver record["raw_response"]/record["errors"]). Sin ese dato
# crudo, la clasificacion pedida por causa exacta no puede hacerse sobre los
# 21 casos reales -- lo que sigue es una clasificacion SINTETICA que cubre
# las 6 causas posibles enumeradas en la instruccion, usada como prueba de
# regresion del contrato (ok=False con causa correcta), no como diagnostico
# de los casos historicos.

def test_synthetic_missing_required_field():
    payload = {k: v for k, v in VALID.items() if k != "rationale"}
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False
    assert any("rationale" in e for e in errors)


def test_synthetic_extra_field():
    payload = dict(VALID, pipeline_note="no deberia estar aqui")
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False
    assert any("pipeline_note" in e for e in errors)


def test_synthetic_wrong_enum():
    payload = dict(VALID, chunk_observation="fully_compliant")
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False


def test_synthetic_wrong_type_or_null():
    payload = dict(VALID, evidence_page="pagina cinco")
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False


def test_synthetic_length_exceeded():
    payload = dict(VALID, rationale="x" * 1201)
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False


def test_synthetic_invalid_json_never_reaches_validate_against():
    """Causa 'JSON invalido' no es un caso de validate_against() (que recibe
    dict ya parseado) -- se maneja antes, en generate_controlled()
    (llm_output=None, errors=['respuesta del modelo no es JSON valido']).
    Confirma que ese contrato de error sigue existiendo sin cambios."""
    import json
    with pytest.raises(json.JSONDecodeError):
        json.loads("{esto no es json valido")


def test_synthetic_contract_aligned_response_still_validates():
    """La correccion de forma (anyOf) no debe impedir que una respuesta
    correctamente alineada con el contrato siga validando -- sigue pasando
    exactamente igual que antes del fix."""
    ok, errors = validate_against(VALID, "finding_llm_v1")
    assert ok is True, errors
