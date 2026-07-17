"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.4 — tests del verificador v2."""
from __future__ import annotations

from factory.regulatory.evidence_verifier import (
    match_citation, relevance_score, verify_llm_output,
)

KNOWN_REQS = {"21_CFR_11.10(d)", "ANNEX11_9"}
CHUNK = {
    "text": "El sistema requiere autenticacion de dos factores para el acceso "
            "de operadores. El audit-trail registra cada evento con timestamp.",
    "page_start": 10, "page_end": 11,
}
AUDIT_TERMS = ["audit", "trail", "log", "event", "timestamp", "record"]


def _base_output(**overrides):
    out = {
        "requirement_id": "ANNEX11_9",
        "chunk_observation": "observed",
        "evidence_quote": "El audit-trail registra cada evento con timestamp.",
        "evidence_page": 10,
        "confidence": 0.85,
        "rationale": "Cita explicita de audit trail.",
        "flags": [],
    }
    out.update(overrides)
    return out


def test_exact_citation_is_verified():
    out = _base_output()
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["citation_match_type"] == "exact"


def test_citation_with_spaces_and_dashes_is_normalized_and_verified():
    chunk = dict(CHUNK, text=CHUNK["text"].replace("audit-trail", "audit‐trail  "))
    out = _base_output(evidence_quote="El audit-trail  registra cada evento con timestamp.")
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["citation_match_type"] in ("exact", "normalized")


def test_fuzzy_citation_in_range_is_verified_with_deviation():
    # Cita casi identica (una coma final agregada por el modelo) -> similitud
    # alta (0.9494, verificado con match_citation) pero no exacta/normalizada.
    chunk = dict(CHUNK, text="El sistema requiere autenticacion de dos factores para el "
                              "acceso de operadores. El audit-trail registra cada evento "
                              "con timestamp exacto y preciso segun norma.")
    out = _base_output(evidence_quote="El audit-trail registra cada evento con timestamp "
                                       "exacto y preciso segun norma,")
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.checks["citation_match_type"] == "fuzzy"
    assert result.status == "verified_with_deviation"
    assert "CITATION_DEVIATION" in result.review_flags


def test_low_fuzzy_citation_is_rejected_citation_not_found():
    """Caso tipo C-inventada: cita que no existe en el chunk, ni siquiera
    de forma aproximada."""
    out = _base_output(evidence_quote="El sistema calcula la presion diferencial del autoclave en tiempo real.")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "citation_not_found" in result.rejection_reason
    assert result.checks["citation_match_type"] == "not_found"


def test_real_but_irrelevant_quote_is_review_required_not_rejected():
    """Caso tipo C1/C3 (citas trasladadas): la cita SI existe literalmente
    en el chunk pero no habla del requisito evaluado -- debe quedar en
    revision humana, nunca auto-rechazada ni verificada limpiamente (P6)."""
    chunk = dict(CHUNK, text="La calibracion del sensor de presion se realiza cada 12 meses "
                              "segun el procedimiento SOP-CAL-004.")
    out = _base_output(
        requirement_id="ANNEX11_9",
        evidence_quote="La calibracion del sensor de presion se realiza cada 12 meses "
                       "segun el procedimiento SOP-CAL-004.",
    )
    result = verify_llm_output(out, chunk, KNOWN_REQS, AUDIT_TERMS)
    assert result.checks["citation"] == "PASS"  # la cita SI esta anclada
    assert result.status == "review_required"
    assert "RELEVANCE_REVIEW_REQUIRED" in result.review_flags


def test_not_observed_with_quote_present_is_rejected_incoherence():
    out = _base_output(chunk_observation="not_observed_in_chunk",
                        evidence_quote="El audit-trail registra cada evento.")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "quote_present_on_not_observed" in result.rejection_reason


def test_not_observed_without_quote_is_verified():
    out = _base_output(chunk_observation="not_observed_in_chunk", evidence_quote="",
                        evidence_page=None)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "verified"
    assert result.checks["page"] == "n/a"


def test_missing_page_is_review_required_never_clean_verified():
    out = _base_output(evidence_page=None)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "review_required"
    assert "PAGE_NOT_VERIFIABLE" in result.review_flags


def test_page_out_of_range_is_rejected():
    out = _base_output(evidence_page=999)
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "page_out_of_range" in result.rejection_reason


def test_unknown_requirement_is_rejected():
    out = _base_output(requirement_id="NOT_A_REAL_REQ")
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, AUDIT_TERMS)
    assert result.status == "rejected_by_verifier"
    assert "requirement_unknown" in result.rejection_reason


def test_missing_requirement_terms_is_not_verifiable_never_pass_or_reject():
    out = _base_output()
    result = verify_llm_output(out, CHUNK, KNOWN_REQS, requirement_terms=[])
    assert result.checks["relevance"] == "NOT_VERIFIABLE"
    assert "RELEVANCE_NOT_EVALUABLE" in result.review_flags
    assert result.status == "review_required"  # nunca rejected ni verified limpio


def test_match_citation_taxonomy_exact_normalized_fuzzy_not_found():
    src = "The audit trail is enabled by default."
    assert match_citation("The audit trail is enabled by default.", src)[0] == "exact"
    assert match_citation("the   audit trail is enabled by default", src)[0] == "normalized"
    assert match_citation("completely unrelated text about calibration", src)[0] == "not_found"


def test_relevance_score_returns_negative_one_when_not_evaluable():
    assert relevance_score("some quote", []) == -1.0
    assert relevance_score("", ["audit"]) == -1.0
