"""W5 V2, Fase C -- correccion del modelo de evidencia provisional
(2026-07-23). Cubre las garantias duras pedidas explicitamente por Cesar:
una fuente PENDING_REVERIFICATION puede ejecutar analisis provisional, no
puede producir una conclusion final, no puede pasar el
FORMAL_RELEASE_GATE, puede generar un REVIEW_DRAFT trazable, no puede
generar un CLEAN_CANDIDATE liberable, y ningun pendiente queda omitido
del paquete QA."""
from __future__ import annotations

import pytest

from factory.regulatory.requirement_catalog import provisional_evidence_model as mod


# ---------------------------------------------------------------------------
# PART11_APPLICABILITY_V1
# ---------------------------------------------------------------------------

def test_out_of_scope_resolves_to_not_applicable():
    assert mod.resolve_part11_applicability("OUT_OF_SCOPE", "any") == "NOT_APPLICABLE"


def test_in_scope_with_predicate_rule_determined_resolves_to_applicable():
    assert mod.resolve_part11_applicability("IN_SCOPE", "21_CFR_211_SUBPART_J") == "APPLICABLE"


def test_in_scope_without_predicate_rule_resolves_to_not_determined():
    assert mod.resolve_part11_applicability("IN_SCOPE", "NOT_DETERMINED") == "NOT_DETERMINED"
    assert mod.resolve_part11_applicability("IN_SCOPE", "") == "NOT_DETERMINED"


def test_not_determined_scope_resolves_to_not_determined():
    assert mod.resolve_part11_applicability("NOT_DETERMINED", "whatever") == "NOT_DETERMINED"


def test_applicability_never_returns_conditional():
    for scope in ("IN_SCOPE", "OUT_OF_SCOPE", "NOT_DETERMINED"):
        for predicate in ("NOT_DETERMINED", "", "21_CFR_211"):
            result = mod.resolve_part11_applicability(scope, predicate)
            assert result in mod._VALID_APPLICABILITY_STATUS
            assert result != "CONDITIONAL"


def test_invalid_scope_status_raises():
    with pytest.raises(mod.ProvisionalEvidenceModelError):
        mod.resolve_part11_applicability("SOMETHING_ELSE", "x")


# ---------------------------------------------------------------------------
# Analisis provisional permitido, conclusion final prohibida
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("allowed_result", sorted(mod.ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION - {"NOT_APPLICABLE"}))
def test_pending_reverification_source_can_run_provisional_analysis(allowed_result):
    mod.validate_result_status_allowed(allowed_result, "PENDING_REVERIFICATION")


def test_not_applicable_requires_independent_rule_determination():
    with pytest.raises(mod.ProvisionalEvidenceModelError):
        mod.validate_result_status_allowed("NOT_APPLICABLE", "PENDING_REVERIFICATION")
    mod.validate_result_status_allowed(
        "NOT_APPLICABLE", "PENDING_REVERIFICATION",
        applicability_determined_by_independent_rule=True,
    )


@pytest.mark.parametrize("prohibited_result", sorted(mod.PROHIBITED_FINAL_RESULTS_WHILE_PENDING))
def test_pending_reverification_source_cannot_produce_final_conclusion(prohibited_result):
    with pytest.raises(mod.ProvisionalEvidenceModelError, match="prohibido"):
        mod.validate_result_status_allowed(prohibited_result, "PENDING_REVERIFICATION")


def test_unknown_result_rejected_while_pending():
    with pytest.raises(mod.ProvisionalEvidenceModelError):
        mod.validate_result_status_allowed("SOMETHING_MADE_UP", "PENDING_REVERIFICATION")


def test_locally_verified_source_is_not_restricted_by_this_guard():
    # LOCAL_CANONICAL_COPY_VERIFIED no pasa por esta lista -- otros gates
    # (FORMAL_RELEASE_GATE) siguen aplicando por separado.
    mod.validate_result_status_allowed("DOCUMENTED_AND_SUPPORTED", "LOCAL_CANONICAL_COPY_VERIFIED")


def test_never_evaluated_not_determined_pending_never_become_pass():
    for status in ("NOT_EVALUATED", "NOT_DETERMINED", "PENDING_REVERIFICATION"):
        with pytest.raises(mod.ProvisionalEvidenceModelError):
            mod.assert_never_silently_promoted_to_pass(status)
    mod.assert_never_silently_promoted_to_pass("PASS")  # no debe lanzar


# ---------------------------------------------------------------------------
# Anotacion obligatoria en salidas dependientes de fuente pendiente
# ---------------------------------------------------------------------------

def test_provisional_annotation_present_when_pending():
    ann = mod.build_provisional_annotation(
        source_verification_status="PENDING_REVERIFICATION",
        source_id="ecfr_21cfr_part11",
        source_sha256="e41aa1b33dd09397352820b6568b0619d8b61a7f340f550a09553e6fdd82c21e",
        official_url="https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11",
    )
    assert ann is not None
    assert ann.limitation_code == "SOURCE_PENDING_REVERIFICATION"
    assert ann.result_authority == "PROVISIONAL"
    assert ann.requires_source_reverification is True
    assert ann.source_id == "ecfr_21cfr_part11"


def test_provisional_annotation_absent_when_source_verified():
    ann = mod.build_provisional_annotation(
        source_verification_status="LOCAL_CANONICAL_COPY_VERIFIED",
        source_id="x", source_sha256="a" * 64, official_url="https://example.org",
    )
    assert ann is None


# ---------------------------------------------------------------------------
# EXECUTION_GATE -- una fuente pendiente NO lo bloquea
# ---------------------------------------------------------------------------

def test_execution_gate_passes_with_pending_reverification_source():
    result = mod.evaluate_execution_gate(
        has_local_copy=True, has_sha256=True, has_clause=True,
        has_canonical_text=True, has_valid_schema=True,
    )
    assert result.gate_passed is True
    assert result.failed_criteria == []


def test_execution_gate_fails_when_missing_real_artifact():
    result = mod.evaluate_execution_gate(
        has_local_copy=True, has_sha256=False, has_clause=True,
        has_canonical_text=True, has_valid_schema=True,
    )
    assert result.gate_passed is False
    assert "sha256_disponible" in result.failed_criteria


# ---------------------------------------------------------------------------
# FORMAL_RELEASE_GATE -- fuente pendiente SIEMPRE lo bloquea
# ---------------------------------------------------------------------------

def _all_criteria_ok(**overrides):
    base = dict(
        source_verification_status="LOCAL_CANONICAL_COPY_VERIFIED",
        official_url_verified=True, local_copy_exists=True,
        source_sha256_matches=True, canonical_text_validated=True,
        clause_validated=True, citation_sha256_valid=True,
        evidence_pack_approved_by_human=True,
        golden_dataset_no_critical_regressions=True,
        gate_0_green=True, open_critical_contradictions=0,
        unresolved_critical_exceptions=0,
    )
    base.update(overrides)
    return base


def test_formal_release_gate_passes_when_all_criteria_real():
    result = mod.evaluate_formal_release_gate(**_all_criteria_ok())
    assert result.gate_passed is True


def test_formal_release_gate_blocked_by_pending_reverification():
    result = mod.evaluate_formal_release_gate(
        **_all_criteria_ok(source_verification_status="PENDING_REVERIFICATION")
    )
    assert result.gate_passed is False
    assert "source_verification_status_verificado" in result.failed_criteria


def test_formal_release_gate_evaluates_all_criteria_without_short_circuit():
    result = mod.evaluate_formal_release_gate(
        **_all_criteria_ok(
            source_verification_status="PENDING_REVERIFICATION",
            gate_0_green=False,
            open_critical_contradictions=2,
        )
    )
    assert set(result.failed_criteria) == {
        "source_verification_status_verificado", "gate_0_en_verde",
        "cero_contradicciones_criticas_abiertas",
    }


# ---------------------------------------------------------------------------
# Elegibilidad de remediacion sobre fuente provisional
# ---------------------------------------------------------------------------

def test_low_risk_provisional_source_generates_traceable_review_draft():
    result = mod.classify_remediation_eligibility(
        change_risk="LOW_RISK", has_uncertainty=False, provisional_source=True,
    )
    assert result.status == "AUTO_APPLIED_TO_REVIEW_DRAFT"
    assert result.provisional_source is True
    assert result.source_reverification_required is True
    assert result.eligible_for_clean_candidate is False
    assert result.eligible_for_release is False


def test_low_risk_provisional_source_never_eligible_for_clean_candidate_or_release():
    result = mod.classify_remediation_eligibility(
        change_risk="LOW_RISK", has_uncertainty=False, provisional_source=True,
    )
    assert result.eligible_for_clean_candidate is False
    assert result.eligible_for_release is False


def test_low_risk_non_provisional_source_is_eligible_for_clean_candidate():
    result = mod.classify_remediation_eligibility(
        change_risk="LOW_RISK", has_uncertainty=False, provisional_source=False,
    )
    assert result.eligible_for_clean_candidate is True


def test_medium_risk_or_uncertain_is_proposed_not_applied():
    assert mod.classify_remediation_eligibility(
        change_risk="MEDIUM_RISK", has_uncertainty=False, provisional_source=True,
    ).status == "PROPOSED_NOT_APPLIED"
    assert mod.classify_remediation_eligibility(
        change_risk="LOW_RISK", has_uncertainty=True, provisional_source=True,
    ).status == "PROPOSED_NOT_APPLIED"


def test_high_risk_is_always_exception_required():
    result = mod.classify_remediation_eligibility(
        change_risk="HIGH_RISK", has_uncertainty=False, provisional_source=False,
    )
    assert result.status == "EXCEPTION_REQUIRED"


def test_unknown_change_risk_raises():
    with pytest.raises(mod.ProvisionalEvidenceModelError):
        mod.classify_remediation_eligibility(
            change_risk="WHATEVER", has_uncertainty=False, provisional_source=True,
        )


# ---------------------------------------------------------------------------
# operational_processing_coverage -- ningun pendiente omitido en silencio
# ---------------------------------------------------------------------------

def test_coverage_reaches_target_with_documented_pending():
    applicable = [f"REQ_{i}" for i in range(20)]
    processed = applicable[:19]
    report = mod.compute_operational_processing_coverage(
        applicable, processed, pending_with_reason={applicable[19]: "esperando reverificacion de fuente"},
    )
    assert report.coverage == pytest.approx(0.95)
    assert report.meets_target is True
    assert report.silent_omissions == []
    assert report.pending_ids == [applicable[19]]


def test_coverage_flags_silent_omission_when_pending_has_no_reason():
    applicable = ["A", "B", "C"]
    processed = ["A", "B"]
    report = mod.compute_operational_processing_coverage(applicable, processed, pending_with_reason={})
    assert report.silent_omissions == ["C"]


def test_coverage_ignores_processed_ids_outside_applicable_set():
    applicable = ["A", "B"]
    processed = ["A", "B", "NOT_APPLICABLE_TO_THIS_SCOPE"]
    report = mod.compute_operational_processing_coverage(applicable, processed, {})
    assert report.processed_total == 2
    assert report.coverage == 1.0


# ---------------------------------------------------------------------------
# Promocion provisional -> final: nunca automatica
# ---------------------------------------------------------------------------

def test_reverification_diff_report_never_promotes_automatically():
    report = mod.build_reverification_diff_report(
        "21_CFR_11.10(a)", "PROVISIONALLY_DOCUMENTED", "DOCUMENTED_AND_SUPPORTED",
    )
    assert report.changed is True
    assert report.requires_human_authorization is True
    assert report.promoted is False


def test_reverification_diff_report_flags_unchanged_result_too():
    report = mod.build_reverification_diff_report(
        "21_CFR_11.10(a)", "PROVISIONAL_GAP", "PROVISIONAL_GAP",
    )
    assert report.changed is False
    assert report.promoted is False  # incluso sin cambios, la promocion sigue siendo un acto humano aparte
