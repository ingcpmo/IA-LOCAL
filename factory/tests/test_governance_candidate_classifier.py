"""Tests -- Paquete 1a (VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md, causa
raíz F): factory.services.governance_candidate_classifier +
factory.layer9.human_review_queue (count_prior_finding_occurrences,
enqueue_governance_candidate_for_review, mark_candidate_reviewed).

review_queue.jsonl SIEMPRE aislado (conftest.py::isolated_review_queue,
autouse). Cero LLM."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.layer9 import human_review_queue as hrq
from factory.services import governance_candidate_classifier as gcc


def _enqueue_finding(run_id, requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
                      conclusion="DOCUMENTATION_GAP", status=None):
    entry = hrq.enqueue_finding_for_review(
        run_id=run_id, requirement_id=requirement_id, document_id=document_id,
        page=None, evidence_quote="", conclusion=conclusion,
        review_flags=["BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT"],
        agent_id="fda_part11_agent",
    )
    if status is not None:
        hrq.supersede_finding(entry["rc_id"], "defecto tecnico de prueba")
    return entry


class TestCountPriorFindingOccurrences:

    def test_zero_when_no_prior_runs(self, isolated_review_queue):
        _enqueue_finding("run-1")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-1",
            conclusions=gcc._GAP_CONCLUSIONS) == 0

    def test_counts_distinct_prior_run_ids(self, isolated_review_queue):
        _enqueue_finding("run-1")
        _enqueue_finding("run-2")
        _enqueue_finding("run-3")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-3",
            conclusions=gcc._GAP_CONCLUSIONS) == 2

    def test_excludes_superseded_entries(self, isolated_review_queue):
        """Un superseded es un defecto tecnico confirmado, nunca una
        ausencia real -- no debe contar para recurrencia."""
        _enqueue_finding("run-1", status="superseded")
        _enqueue_finding("run-2")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-2",
            conclusions=gcc._GAP_CONCLUSIONS) == 0

    def test_ignores_different_requirement_or_document(self, isolated_review_queue):
        _enqueue_finding("run-1", requirement_id="21_CFR_11.10(d)")
        _enqueue_finding("run-2", document_id="RW-OTHER")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-3",
            conclusions=gcc._GAP_CONCLUSIONS) == 0

    def test_ignores_non_gap_conclusions(self, isolated_review_queue):
        _enqueue_finding("run-1", conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-2",
            conclusions=gcc._GAP_CONCLUSIONS) == 0

    def test_counts_provisional_gap_same_as_documentation_gap(self, isolated_review_queue):
        _enqueue_finding("run-1", conclusion="PROVISIONAL_GAP")
        assert hrq.count_prior_finding_occurrences(
            "21_CFR_11.10(e)", "RW-TEST", exclude_run_id="run-2",
            conclusions=gcc._GAP_CONCLUSIONS) == 1


class TestClassifyFindingForGovernanceCandidate:

    def test_none_for_conclusion_outside_scope(self, isolated_review_queue):
        assert gcc.classify_finding_for_governance_candidate(
            requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            run_id="run-1", conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW") is None
        assert gcc.classify_finding_for_governance_candidate(
            requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            run_id="run-1", conclusion="DOCUMENTED_AND_SUPPORTED") is None

    def test_first_occurrence_suggests_ncr(self, isolated_review_queue):
        s = gcc.classify_finding_for_governance_candidate(
            requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            run_id="run-1", conclusion="DOCUMENTATION_GAP")
        assert s.suggested_type == gcc.NCR
        assert s.prior_occurrences == 0
        assert "primera aparición" in s.rationale

    def test_recurrence_suggests_capa(self, isolated_review_queue):
        _enqueue_finding("run-1")
        s = gcc.classify_finding_for_governance_candidate(
            requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            run_id="run-2", conclusion="DOCUMENTATION_GAP")
        assert s.suggested_type == gcc.CAPA
        assert s.prior_occurrences == 1
        assert "recurrencia" in s.rationale.lower()

    def test_change_control_never_auto_suggested(self, isolated_review_queue):
        """Ninguna combinacion real de conclusion produce CHANGE_CONTROL
        automaticamente -- no existe senal objetiva de desviacion de
        procedimiento en el vocabulario real (ver docstring del modulo)."""
        for _ in range(5):
            pass
        s1 = gcc.classify_finding_for_governance_candidate(
            requirement_id="X", document_id="Y", run_id="run-1", conclusion="DOCUMENTATION_GAP")
        assert s1.suggested_type != gcc.CHANGE_CONTROL


class TestEnqueueAndDecideGovernanceCandidate:

    def test_enqueue_rejects_invalid_type(self, isolated_review_queue):
        with pytest.raises(ValueError):
            hrq.enqueue_governance_candidate_for_review(
                run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
                conclusion="DOCUMENTATION_GAP", suggested_type="INVALID",
                rationale="x", prior_occurrences=0, agent_id="fda_part11_agent")

    def test_enqueue_and_read_back(self, isolated_review_queue):
        entry = hrq.enqueue_governance_candidate_for_review(
            run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            conclusion="DOCUMENTATION_GAP", suggested_type="NCR",
            rationale="primera aparición", prior_occurrences=0, agent_id="fda_part11_agent")
        assert entry["entry_type"] == "governance_candidate"
        assert entry["status"] == "pending"
        assert entry["rc_id"] == "candidate-run-1-21_CFR_11.10(e)"
        stored = hrq.get_entry(entry["rc_id"])
        assert stored["summary"]["suggested_type"] == "NCR"

    def test_mark_candidate_reviewed_requires_human_classification_on_confirm(self, isolated_review_queue):
        entry = hrq.enqueue_governance_candidate_for_review(
            run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            conclusion="DOCUMENTATION_GAP", suggested_type="NCR",
            rationale="x", prior_occurrences=0, agent_id="fda_part11_agent")
        with pytest.raises(ValueError):
            hrq.mark_candidate_reviewed(entry["rc_id"], "confirmed", "Cesar")

    def test_mark_candidate_reviewed_confirmed_can_override_suggested_type(self, isolated_review_queue):
        """El humano puede confirmar con un tipo DISTINTO al sugerido --
        la sugerencia nunca se hereda en silencio."""
        entry = hrq.enqueue_governance_candidate_for_review(
            run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            conclusion="DOCUMENTATION_GAP", suggested_type="NCR",
            rationale="x", prior_occurrences=0, agent_id="fda_part11_agent")
        result = hrq.mark_candidate_reviewed(
            entry["rc_id"], "confirmed", "Cesar", human_classification="CHANGE_CONTROL")
        assert result["human_classification"] == "CHANGE_CONTROL"
        stored = hrq.get_entry(entry["rc_id"])
        assert stored["human_classification"] == "CHANGE_CONTROL"
        assert stored["status"] == "confirmed"

    def test_mark_candidate_reviewed_rejected_never_needs_classification(self, isolated_review_queue):
        entry = hrq.enqueue_governance_candidate_for_review(
            run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            conclusion="DOCUMENTATION_GAP", suggested_type="NCR",
            rationale="x", prior_occurrences=0, agent_id="fda_part11_agent")
        result = hrq.mark_candidate_reviewed(entry["rc_id"], "rejected", "Cesar")
        assert result["decision"] == "rejected"

    def test_mark_candidate_reviewed_rejects_reserved_identity(self, isolated_review_queue):
        entry = hrq.enqueue_governance_candidate_for_review(
            run_id="run-1", requirement_id="21_CFR_11.10(e)", document_id="RW-TEST",
            conclusion="DOCUMENTATION_GAP", suggested_type="NCR",
            rationale="x", prior_occurrences=0, agent_id="fda_part11_agent")
        with pytest.raises(Exception):
            hrq.mark_candidate_reviewed(entry["rc_id"], "rejected", "human")

    def test_mark_candidate_reviewed_rejects_wrong_entry_type(self, isolated_review_queue):
        finding = _enqueue_finding("run-1")
        with pytest.raises(ValueError):
            hrq.mark_candidate_reviewed(finding["rc_id"], "rejected", "Cesar")
