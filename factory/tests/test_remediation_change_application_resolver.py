"""
Tests -- W5 V2 Fase K: factory.services.remediation_change_application_resolver.

Cubre: los 4 estados del plan (AUTO_APPLIED_TO_DRAFT/PROPOSED_NOT_APPLIED/
EXCEPTION_REQUIRED/REJECTED_BY_VALIDATOR) resueltos correctamente por
change_risk, y la regla dura que motivo esta fase: un cambio HIGH_RISK
rechazado individualmente por un humano NUNCA debe terminar en el
candidato limpio (select_changes_for_clean_candidate lo excluye).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.services import remediation_package_service as svc
from factory.services.remediation_change_application_resolver import (
    resolve_change_application, resolve_package_changes, select_changes_for_clean_candidate,
)


def _change(change_id, risk, *, schema="PASSED", anchor="VERIFIED"):
    return {
        "change_id": change_id, "change_risk": risk,
        "schema_validation_status": schema, "citation_anchor_status": anchor,
    }


def _package_state(changes, exceptions=None, batch_decisions=None):
    return {
        "changes": {c["change_id"]: c for c in changes},
        "exceptions": exceptions or {},
        "medium_risk_batch_decisions": batch_decisions or {},
    }


class TestGatesTakePrecedenceOverRisk:

    def test_schema_failed_is_rejected_regardless_of_risk(self):
        change = _change("C1", "LOW_RISK", schema="FAILED")
        r = resolve_change_application(change, _package_state([change]))
        assert r.final_status == "REJECTED_BY_VALIDATOR"
        assert r.included_in_clean_candidate is False

    def test_citation_not_verified_is_rejected_regardless_of_risk(self):
        change = _change("C1", "LOW_RISK", anchor="NOT_VERIFIED")
        r = resolve_change_application(change, _package_state([change]))
        assert r.final_status == "REJECTED_BY_VALIDATOR"


class TestLowRisk:

    def test_low_risk_with_passing_gates_auto_applies(self):
        change = _change("C1", "LOW_RISK")
        r = resolve_change_application(change, _package_state([change]))
        assert r.final_status == "AUTO_APPLIED_TO_DRAFT"
        assert r.included_in_clean_candidate is True


class TestMediumRisk:

    def test_medium_risk_without_batch_decision_is_proposed_not_applied(self):
        change = _change("C1", "MEDIUM_RISK")
        r = resolve_change_application(change, _package_state([change]))
        assert r.final_status == "PROPOSED_NOT_APPLIED"
        assert r.included_in_clean_candidate is False

    def test_medium_risk_covered_by_batch_decision_auto_applies(self):
        change = _change("C1", "MEDIUM_RISK")
        state = _package_state([change], batch_decisions={
            "BATCH-1": {"covered_change_ids": ["C1"]},
        })
        r = resolve_change_application(change, state)
        assert r.final_status == "AUTO_APPLIED_TO_DRAFT"

    def test_medium_risk_not_covered_by_a_different_batch_stays_pending(self):
        change = _change("C1", "MEDIUM_RISK")
        state = _package_state([change], batch_decisions={
            "BATCH-1": {"covered_change_ids": ["OTRO_CAMBIO"]},
        })
        r = resolve_change_application(change, state)
        assert r.final_status == "PROPOSED_NOT_APPLIED"


class TestHighRisk:

    def test_high_risk_without_exception_requires_exception(self):
        change = _change("C1", "HIGH_RISK")
        r = resolve_change_application(change, _package_state([change]))
        assert r.final_status == "EXCEPTION_REQUIRED"
        assert r.included_in_clean_candidate is False

    def test_high_risk_with_accepted_exception_auto_applies(self):
        change = _change("C1", "HIGH_RISK")
        state = _package_state([change], exceptions={
            "EXC-C1": {"exception_id": "EXC-C1", "change_id": "C1", "status": "REVIEWED",
                       "human_review_decision": "accept_risk"},
        })
        r = resolve_change_application(change, state)
        assert r.final_status == "AUTO_APPLIED_TO_DRAFT"
        assert r.included_in_clean_candidate is True

    def test_high_risk_with_rejected_exception_never_applies(self):
        """Regla dura que motivo esta fase: un HIGH_RISK rechazado
        individualmente NUNCA debe terminar en el candidato."""
        change = _change("C1", "HIGH_RISK")
        state = _package_state([change], exceptions={
            "EXC-C1": {"exception_id": "EXC-C1", "change_id": "C1", "status": "REVIEWED",
                       "human_review_decision": "reject_exclude_from_draft"},
        })
        r = resolve_change_application(change, state)
        assert r.final_status == "PROPOSED_NOT_APPLIED"
        assert r.included_in_clean_candidate is False

    def test_high_risk_exception_not_yet_reviewed_still_requires_exception(self):
        change = _change("C1", "HIGH_RISK")
        state = _package_state([change], exceptions={
            "EXC-C1": {"exception_id": "EXC-C1", "change_id": "C1", "status": "PENDING",
                       "human_review_decision": ""},
        })
        r = resolve_change_application(change, state)
        assert r.final_status == "EXCEPTION_REQUIRED"


class TestSelectChangesForCleanCandidate:

    def test_only_auto_applied_changes_are_selected(self):
        low = _change("LOW-1", "LOW_RISK")
        medium_pending = _change("MED-1", "MEDIUM_RISK")
        high_rejected = _change("HIGH-1", "HIGH_RISK")
        state = _package_state(
            [low, medium_pending, high_rejected],
            exceptions={"EXC-HIGH-1": {"exception_id": "EXC-HIGH-1", "change_id": "HIGH-1",
                                        "status": "REVIEWED", "human_review_decision": "reject"}},
        )
        selected = select_changes_for_clean_candidate([low, medium_pending, high_rejected], state)
        assert [c["change_id"] for c in selected] == ["LOW-1"]

    def test_rejected_by_validator_never_selected_even_if_risk_would_allow(self):
        broken = _change("C1", "LOW_RISK", schema="FAILED")
        state = _package_state([broken])
        selected = select_changes_for_clean_candidate([broken], state)
        assert selected == []

    def test_empty_package_selects_nothing(self):
        assert select_changes_for_clean_candidate([], _package_state([])) == []


class TestRealServiceIntegration:
    """Prueba con package_state producido por el servicio REAL (no un dict
    a mano) -- create_package + record_exception_review reales."""

    def test_high_risk_change_excluded_after_real_rejection(self, tmp_path, monkeypatch):
        from factory.services import paths
        from factory.core import audit_writer

        monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
        monkeypatch.setattr(audit_writer, "AUDIT_FILE", tmp_path / "audit" / "test_factory_audit.jsonl")
        monkeypatch.setattr(audit_writer, "_last_entry_hash", None)

        import hashlib

        def _sha(t):
            return hashlib.sha256(t.encode()).hexdigest()

        def _citation(change_id):
            literal = f"texto literal {change_id}"
            return {
                "citation_id": f"CIT-{change_id}", "regulatory_catalog_entry_id": "ALCOA_CONTEMPORANEOUS",
                "regulatory_source": "ALCOA+", "regulatory_source_sha256": _sha(f"src-{change_id}"),
                "requirement_catalog_sha256": _sha(f"cat-{change_id}"), "run_id": "RUN-1",
                "record_id": f"REC-{change_id}", "document_role": "CANDIDATE_DOCUMENT",
                "document_sha256": _sha(f"doc-{change_id}"), "chunk_sha256": _sha(f"chunk-{change_id}"),
                "citation_locator": f"chunk_1#p1-2-{change_id}", "page_start": 1, "page_end": 2,
                "literal_text": literal, "citation_text_sha256": _sha(literal),
                "evidence_type": "LITERAL_QUOTE", "evidence_location": f"seccion 1, {change_id}",
            }

        risk_factors_high = {
            "change_type": "CONTENT_REPLACEMENT", "requirement_criticality": "CRITICAL",
            "gxp_impact": "DIRECT_GXP_IMPACT", "evidence_status": "ABSENCE_CONFIRMED",
            "functional_impact": "SYSTEM_BEHAVIOR_CHANGE",
        }
        confidence_factors = {
            "coverage_status": "FULL_COVERAGE", "citation_anchor_status": "VERIFIED",
            "relevance_status": "CONFIRMED", "schema_validation_status": "PASSED",
        }
        risk, risk_basis = svc.compute_change_risk(risk_factors_high)
        confidence, confidence_basis = svc.compute_evaluation_confidence(confidence_factors)
        change = {
            "change_id": "CHG-1", "finding_id": "F-1", "requirement_id": "REQ-1",
            "document_location": "chunk_1", "original_content": "texto original",
            "proposed_content": "texto propuesto", "change_reason": "gap detectado",
            "change_type": "CONTENT_REPLACEMENT", "citations": [_citation("CHG-1")],
            "change_risk": risk, "change_risk_basis": risk_basis,
            "evaluation_confidence": confidence, "evaluation_confidence_basis": confidence_basis,
            "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
            "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT",
            "limitations": "",
        }
        assert risk == "HIGH_RISK"

        artifact = {
            "artifact_id": "ART-1", "storage_location": "s3://x", "mime_type": "application/pdf",
            "sha256": _sha("artifact"), "size_bytes": 10, "classification": "CANDIDATE_DRAFT",
            "created_at": "2026-07-23T00:00:00+00:00",
        }
        svc.create_package(
            project_id="test_proj", package_id="PKG-1", package_version=1,
            changes=[change], artifacts={"candidate": artifact},
            automatic_evaluation_basis={"reason": "sintetico"},
            generation_commit_sha="a" * 40,
        )
        svc.record_exception_review(
            project_id="test_proj", package_id="PKG-1", package_version=1, change_id="CHG-1",
            human_review_decision="reject_high_risk_change", responsible="qa_lead",
            justification="riesgo inaceptable para este cambio especifico",
        )

        state = svc._read_state("test_proj", "PKG-1", 1)
        resolution = resolve_change_application(change, state)
        assert resolution.final_status == "PROPOSED_NOT_APPLIED"
        assert resolution.included_in_clean_candidate is False
        assert select_changes_for_clean_candidate([change], state) == []
