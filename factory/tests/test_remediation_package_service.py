"""
Tests — BATCH_AND_EXCEPTION (factory/services/remediation_package_service.py).

Cubre las invariantes de servicio acordadas en diseno: separacion CHANGE_RISK/
EVALUATION_CONFIDENCE, cobertura exacta de HIGH_RISK (con resolucion
exception_id->change_id), rechazo de aplicacion automatica no soportada,
versionamiento append-only, y unicidad/supersedencia de ReleaseRecord.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.services import paths
from factory.services import remediation_package_service as svc


PROJECT_ID = "gmpai_document_validation_test"


@pytest.fixture(autouse=True)
def _isolated_remediation_packages_base(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
    yield


def _change(change_id, *, risk_factors=None, confidence_factors=None, application_status="APPLIED_TO_DRAFT",
            schema="PASSED", anchor="VERIFIED", relevance="CONFIRMED"):
    risk_factors = risk_factors or {
        "change_type": "CONTENT_ADDITION", "requirement_criticality": "MAJOR",
        "gxp_impact": "INDIRECT", "evidence_status": "PARTIAL_EVIDENCE",
        "functional_impact": "DOCUMENTATION_ONLY",
    }
    confidence_factors = confidence_factors or {
        "coverage_status": "FULL_COVERAGE", "citation_anchor_status": anchor,
        "relevance_status": relevance, "schema_validation_status": schema,
    }
    risk, risk_basis = svc.compute_change_risk(risk_factors)
    confidence, confidence_basis = svc.compute_evaluation_confidence(confidence_factors)
    return {
        "change_id": change_id, "finding_id": f"F-{change_id}", "requirement_id": f"REQ-{change_id}",
        "document_location": "chunk_1", "original_content": None, "proposed_content": "texto propuesto",
        "change_reason": "gap detectado", "change_type": risk_factors["change_type"],
        "citations": [], "change_risk": risk, "change_risk_basis": risk_basis,
        "evaluation_confidence": confidence, "evaluation_confidence_basis": confidence_basis,
        "schema_validation_status": schema, "citation_anchor_status": anchor, "relevance_status": relevance,
        "candidate_application_status": application_status, "limitations": "",
    }


def _artifacts():
    return {
        "source_document": {"sha256": "a" * 64}, "candidate_document": {"sha256": "b" * 64},
        "remediation_report": {"sha256": "c" * 64}, "redline_document": {"sha256": "d" * 64},
        "package_manifest": {"sha256": "e" * 64},
    }


def _basis(applicable=1, requirement_ids=("REQ-1",), execution_errors=0, rejected_records=0):
    return {
        "requirements_applicable": applicable,
        "coverage_complete_by_requirement": {r: True for r in requirement_ids},
        "expected_chunks": 10, "evaluated_chunks": 10,
        "execution_errors": execution_errors, "rejected_records": rejected_records,
    }


# ── change_risk / evaluation_confidence separados ───────────────────────────

def test_change_risk_worst_factor_wins_and_reports_basis():
    risk, basis = svc.compute_change_risk({
        "change_type": "COSMETIC", "requirement_criticality": "CRITICAL",
        "gxp_impact": "NONE", "evidence_status": "LITERAL_EVIDENCE_CONFIRMED",
        "functional_impact": "DOCUMENTATION_ONLY",
    })
    assert risk == "HIGH_RISK"
    assert basis == ["requirement_criticality"]


def test_evaluation_confidence_gap_in_coverage_does_not_touch_change_risk():
    """Ajuste clave aprobado: cobertura parcial degrada CONFIDENCE, nunca escala RISK."""
    risk, _ = svc.compute_change_risk({
        "change_type": "COSMETIC", "requirement_criticality": "MINOR",
        "gxp_impact": "NONE", "evidence_status": "LITERAL_EVIDENCE_CONFIRMED",
        "functional_impact": "DOCUMENTATION_ONLY",
    })
    confidence, basis = svc.compute_evaluation_confidence({
        "coverage_status": "GAP_IN_COVERAGE", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "schema_validation_status": "PASSED",
    })
    assert risk == "LOW_RISK"
    assert confidence == "LOW_CONFIDENCE"
    assert basis == ["coverage_status"]


def test_alcoa_chunk20_case_is_medium_confidence_not_not_validated():
    confidence, basis = svc.compute_evaluation_confidence({
        "coverage_status": "FULL_COVERAGE", "citation_anchor_status": "VERIFIED",
        "relevance_status": "UNDER_REVIEW", "schema_validation_status": "PASSED",
    })
    assert confidence == "MEDIUM_CONFIDENCE"
    assert basis == ["relevance_status"]


# ── invariante 5/9: aplicación automática nunca sobre algo no verificado ────

def test_schema_failed_cannot_be_applied_to_draft():
    change = _change("C1", schema="FAILED", application_status="APPLIED_TO_DRAFT")
    with pytest.raises(svc.InvalidApplicationStatusError):
        svc.validate_change_application_status(change)


def test_anchor_not_verified_cannot_be_applied_to_draft():
    change = _change("C1", anchor="NOT_VERIFIED", application_status="APPLIED_TO_DRAFT")
    with pytest.raises(svc.InvalidApplicationStatusError):
        svc.validate_change_application_status(change)


def test_create_package_rejects_invalid_application_status():
    changes = [_change("C1", schema="FAILED", application_status="APPLIED_TO_DRAFT")]
    with pytest.raises(svc.InvalidApplicationStatusError):
        svc.create_package(
            project_id=PROJECT_ID, package_id="PKG1", package_version=1, changes=changes,
            artifacts=_artifacts(), automatic_evaluation_basis=_basis(), generation_commit_sha="deadbeef")


# ── generación automática sin aprobación por chunk ──────────────────────────

def test_create_package_generates_without_any_chunk_level_approval():
    high = _change("C-HIGH", risk_factors={
        "change_type": "CONTENT_REPLACEMENT", "requirement_criticality": "CRITICAL",
        "gxp_impact": "DIRECT_GXP_IMPACT", "evidence_status": "ABSENCE_CONFIRMED",
        "functional_impact": "SYSTEM_BEHAVIOR_CHANGE",
    })
    low = _change("C-LOW", risk_factors={
        "change_type": "COSMETIC", "requirement_criticality": "MINOR", "gxp_impact": "NONE",
        "evidence_status": "LITERAL_EVIDENCE_CONFIRMED", "functional_impact": "DOCUMENTATION_ONLY",
    })
    pkg = svc.create_package(
        project_id=PROJECT_ID, package_id="PKG2", package_version=1, changes=[high, low],
        artifacts=_artifacts(), automatic_evaluation_basis=_basis(), generation_commit_sha="deadbeef")

    assert pkg["status"] == "AWAITING_HUMAN_EXCEPTION_REVIEW"
    assert pkg["changes"]["high_risk"] == ["C-HIGH"]
    assert pkg["changes"]["low_risk"] == ["C-LOW"]
    assert pkg["automatic_evaluation_complete"] is True  # calculado sin ningun humano involucrado


def test_duplicate_package_version_rejected():
    changes = [_change("C1")]
    svc.create_package(project_id=PROJECT_ID, package_id="PKG3", package_version=1, changes=changes,
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C1",)),
                        generation_commit_sha="deadbeef")
    with pytest.raises(svc.DuplicateVersionError):
        svc.create_package(project_id=PROJECT_ID, package_id="PKG3", package_version=1, changes=changes,
                            artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C1",)),
                            generation_commit_sha="deadbeef")


# ── invariante corregida: resolver exception_id -> change_id antes de comparar ──

def _package_with_one_high_risk(package_id, version=1):
    high = _change("C-HIGH", risk_factors={
        "change_type": "CONTENT_REPLACEMENT", "requirement_criticality": "CRITICAL",
        "gxp_impact": "DIRECT_GXP_IMPACT", "evidence_status": "ABSENCE_CONFIRMED",
        "functional_impact": "SYSTEM_BEHAVIOR_CHANGE",
    })
    return svc.create_package(
        project_id=PROJECT_ID, package_id=package_id, package_version=version, changes=[high],
        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C-HIGH",)),
        generation_commit_sha="deadbeef")


def test_approve_with_exceptions_rejected_if_high_risk_incomplete():
    """Aunque la unica excepcion HIGH_RISK ya fue REVIEWED (status paso a
    AWAITING_PACKAGE_DECISION), decidir sin referenciarla debe rechazarse:
    high_risk_exception_ids debe cubrir EXACTAMENTE changes.high_risk."""
    _package_with_one_high_risk("PKG4")
    svc.record_exception_review(
        project_id=PROJECT_ID, package_id="PKG4", package_version=1, change_id="C-HIGH",
        human_review_decision="accept_risk", responsible="qa_lead", justification="riesgo aceptado")
    with pytest.raises(svc.IncompleteExceptionCoverageError):
        svc.record_package_decision(
            project_id=PROJECT_ID, package_id="PKG4", package_version=1,
            decision="APPROVE_WITH_EXCEPTIONS", decided_by="cesar", justification="ok",
            high_risk_exception_ids=[])  # no referencia la excepcion existente -- debe rechazarse


def test_approve_with_exceptions_succeeds_when_exception_id_resolves_to_change_id():
    _package_with_one_high_risk("PKG5")
    exc = svc.record_exception_review(
        project_id=PROJECT_ID, package_id="PKG5", package_version=1, change_id="C-HIGH",
        human_review_decision="accept_risk", responsible="qa_lead", justification="riesgo aceptado")
    decision = svc.record_package_decision(
        project_id=PROJECT_ID, package_id="PKG5", package_version=1,
        decision="APPROVE_WITH_EXCEPTIONS", decided_by="cesar", justification="ok",
        high_risk_exception_ids=[exc["exception_id"]])
    assert decision["decision"] == "APPROVE_WITH_EXCEPTIONS"


def test_exception_review_requires_justification():
    _package_with_one_high_risk("PKG6")
    with pytest.raises(svc.MissingJustificationError):
        svc.record_exception_review(
            project_id=PROJECT_ID, package_id="PKG6", package_version=1, change_id="C-HIGH",
            human_review_decision="accept_risk", responsible="qa_lead", justification="   ")


def test_medium_risk_batch_decision_covers_lote_sin_registro_individual():
    medium = _change("C-MED", risk_factors={
        "change_type": "CONTENT_ADDITION", "requirement_criticality": "MAJOR",
        "gxp_impact": "INDIRECT", "evidence_status": "PARTIAL_EVIDENCE",
        "functional_impact": "CONFIGURATION_CHANGE",
    })
    svc.create_package(project_id=PROJECT_ID, package_id="PKG7", package_version=1, changes=[medium],
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C-MED",)),
                        generation_commit_sha="deadbeef")
    batch = svc.record_medium_risk_batch_decision(
        project_id=PROJECT_ID, package_id="PKG7", package_version=1,
        covered_change_ids=["C-MED"], responsible="qa_lead", justification="lote revisado")
    assert batch["covered_change_ids"] == ["C-MED"]
    assert len(batch["covered_set_sha256"]) == 64


def test_medium_risk_batch_rejects_change_not_in_medium_set():
    _package_with_one_high_risk("PKG8")  # solo tiene high_risk, no medium_risk
    with pytest.raises(svc.InvalidBatchError):
        svc.record_medium_risk_batch_decision(
            project_id=PROJECT_ID, package_id="PKG8", package_version=1,
            covered_change_ids=["C-HIGH"], responsible="qa_lead", justification="x")


# ── package_ready_for_release y liberación como única fuente ────────────────

def _approve_clean_package(package_id):
    low = _change("C-LOW", risk_factors={
        "change_type": "COSMETIC", "requirement_criticality": "MINOR", "gxp_impact": "NONE",
        "evidence_status": "LITERAL_EVIDENCE_CONFIRMED", "functional_impact": "DOCUMENTATION_ONLY",
    })
    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1, changes=[low],
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C-LOW",)),
                        generation_commit_sha="deadbeef")
    return svc.record_package_decision(
        project_id=PROJECT_ID, package_id=package_id, package_version=1,
        decision="APPROVE_CLEAN", decided_by="cesar", justification="sin excepciones")


def test_package_ready_for_release_status_is_the_only_source():
    _approve_clean_package("PKG9")
    state = svc._read_state(PROJECT_ID, "PKG9", 1)
    assert state["package"]["status"] == "PACKAGE_READY_FOR_RELEASE"
    assert "package_ready_for_release" not in state["package"]  # no existe campo booleano paralelo


def test_release_record_created_and_duplicate_rejected():
    _approve_clean_package("PKG10")
    release = svc.create_release_record(project_id=PROJECT_ID, package_id="PKG10", package_version=1,
                                         released_by="cesar")
    assert release["package_version"] == 1
    with pytest.raises(svc.DuplicateReleaseError):
        svc.create_release_record(project_id=PROJECT_ID, package_id="PKG10", package_version=1,
                                   released_by="cesar")


def test_release_requires_package_ready_for_release_status():
    _package_with_one_high_risk("PKG11")  # queda en AWAITING_HUMAN_EXCEPTION_REVIEW
    with pytest.raises(svc.InvalidTransitionError):
        svc.create_release_record(project_id=PROJECT_ID, package_id="PKG11", package_version=1,
                                   released_by="cesar")


def test_release_supersession_never_mutates_prior_release_record():
    _approve_clean_package("PKG12")
    release_v1 = svc.create_release_record(project_id=PROJECT_ID, package_id="PKG12", package_version=1,
                                            released_by="cesar")

    # ciclo de control de cambios posterior: nueva version, tambien aprobada y liberada
    low_v2 = _change("C-LOW-V2", risk_factors={
        "change_type": "COSMETIC", "requirement_criticality": "MINOR", "gxp_impact": "NONE",
        "evidence_status": "LITERAL_EVIDENCE_CONFIRMED", "functional_impact": "DOCUMENTATION_ONLY",
    })
    svc.create_package(project_id=PROJECT_ID, package_id="PKG12", package_version=2, changes=[low_v2],
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C-LOW-V2",)),
                        generation_commit_sha="deadbeef2")
    svc.record_package_decision(project_id=PROJECT_ID, package_id="PKG12", package_version=2,
                                 decision="APPROVE_CLEAN", decided_by="cesar", justification="v2 limpia")
    release_v2 = svc.create_release_record(project_id=PROJECT_ID, package_id="PKG12", package_version=2,
                                            released_by="cesar")

    releases = svc._read_jsonl(svc._releases_path(PROJECT_ID, "PKG12"))
    assert releases[0] == release_v1  # el registro v1 nunca se modifico
    assert releases[1] == release_v2

    effective = svc.get_effective_release(PROJECT_ID, "PKG12")
    assert effective["release_id"] == release_v2["release_id"]


def test_closed_package_rejects_new_exception_review():
    """Una version RETURNED_SUPERSEDED/CLOSED_REJECTED/PACKAGE_READY_FOR_RELEASE
    es inmutable: no admite nuevas ExceptionReviewRecord despues de cerrada."""
    _package_with_one_high_risk("PKG14")
    svc.record_exception_review(
        project_id=PROJECT_ID, package_id="PKG14", package_version=1, change_id="C-HIGH",
        human_review_decision="accept_risk", responsible="qa_lead", justification="riesgo aceptado")
    svc.record_package_decision(
        project_id=PROJECT_ID, package_id="PKG14", package_version=1,
        decision="RETURN_TO_ADJUSTMENTS", decided_by="cesar", justification="ajustar")
    with pytest.raises(svc.InvalidTransitionError):
        svc.record_exception_review(
            project_id=PROJECT_ID, package_id="PKG14", package_version=1, change_id="C-HIGH",
            human_review_decision="accept_risk", responsible="qa_lead", justification="intento tardio")


def test_closed_package_rejects_new_medium_risk_batch_decision():
    medium = _change("C-MED", risk_factors={
        "change_type": "CONTENT_ADDITION", "requirement_criticality": "MAJOR",
        "gxp_impact": "INDIRECT", "evidence_status": "PARTIAL_EVIDENCE",
        "functional_impact": "CONFIGURATION_CHANGE",
    })
    svc.create_package(project_id=PROJECT_ID, package_id="PKG15", package_version=1, changes=[medium],
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C-MED",)),
                        generation_commit_sha="deadbeef")
    svc.record_package_decision(project_id=PROJECT_ID, package_id="PKG15", package_version=1,
                                 decision="APPROVE_CLEAN", decided_by="cesar", justification="sin excepciones")
    with pytest.raises(svc.InvalidTransitionError):
        svc.record_medium_risk_batch_decision(
            project_id=PROJECT_ID, package_id="PKG15", package_version=1,
            covered_change_ids=["C-MED"], responsible="qa_lead", justification="intento tardio")


def test_return_to_adjustments_never_reuses_version_and_keeps_prior_immutable():
    changes = [_change("C1")]
    svc.create_package(project_id=PROJECT_ID, package_id="PKG13", package_version=1, changes=changes,
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C1",)),
                        generation_commit_sha="deadbeef")
    svc.record_package_decision(project_id=PROJECT_ID, package_id="PKG13", package_version=1,
                                 decision="RETURN_TO_ADJUSTMENTS", decided_by="cesar", justification="ajustar")
    state_v1_before = svc._read_state(PROJECT_ID, "PKG13", 1)
    assert state_v1_before["package"]["status"] == "RETURNED_SUPERSEDED"

    svc.create_package(project_id=PROJECT_ID, package_id="PKG13", package_version=2, changes=changes,
                        artifacts=_artifacts(), automatic_evaluation_basis=_basis(requirement_ids=("REQ-C1",)),
                        generation_commit_sha="deadbeef2", superseded_from="PKG13@v1")

    state_v1_after = svc._read_state(PROJECT_ID, "PKG13", 1)
    assert state_v1_after == state_v1_before  # version anterior nunca se toca tras crear la siguiente
