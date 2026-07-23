"""
Tests -- W5 V2 Fase G: factory.regulatory.golden_dataset.
semantic_verification_golden_dataset.

Cubre: los 8 casos negativos obligatorios del plan (SEMANTIC_EVIDENCE_
VERIFICATION_SPEC.md §12.2) pasan hoy contra el código real (Fase F +
chunked_engine + absence_consolidator, sin reimplementar nada). Este
archivo es el baseline que cualquier cambio futuro de modelo/prompt/schema
debe seguir cumpliendo (Model Qualification Gate,
MODEL_PROVIDER_AND_LOCAL_AI_RUNTIME_SPEC.md §6).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.golden_dataset import semantic_verification_golden_dataset as gd


def test_all_8_golden_cases_pass_today():
    results = gd.run_all()
    summary = gd.summarize(results)
    assert summary["failed_case_ids"] == []
    assert summary["total"] == 8
    assert summary["passed"] == 8


def test_expected_case_ids_are_all_present():
    expected_ids = {
        "ANNEX11_4_reference_list", "invented_citation", "evidence_from_wrong_document",
        "nonexistent_clause", "partial_evidence_sufficiency", "contradiction_between_sections",
        "incomplete_coverage_never_gap", "evidence_out_of_context",
    }
    results = gd.run_all()
    assert {r.case_id for r in results} == expected_ids


def test_partial_evidence_case_is_honestly_not_applicable_yet():
    """Regla dura de Fase G: el caso D nunca debe fingir haber evaluado
    suficiencia real -- debe declarar explicitamente que esta pendiente."""
    results = gd.run_all()
    d_case = next(r for r in results if r.case_id == "partial_evidence_sufficiency")
    assert d_case.detail["status"] == "NOT_APPLICABLE_YET"
    assert "pendiente" in d_case.detail["reason"].lower()


def test_annex11_4_case_result_matches_real_expected_category():
    results = gd.run_all()
    case = next(r for r in results if r.case_id == "ANNEX11_4_reference_list")
    assert case.category == "C"
    assert case.passed is True


def test_contradiction_case_uses_two_real_separate_chunks():
    """Verifica que el caso de contradiccion realmente ejercita 2 chunks
    distintos (no colapsados en 1) -- si build_page_chunks los fusionara,
    el caso pasaria por casualidad sin probar nada real."""
    results = gd.run_all()
    case = next(r for r in results if r.case_id == "contradiction_between_sections")
    assert "pag 1-1" in case.actual and "pag 2-2" in case.actual


def test_summarize_reports_zero_failures_shape():
    results = gd.run_all()
    summary = gd.summarize(results)
    assert set(summary.keys()) == {"total", "passed", "failed", "failed_case_ids"}
    assert summary["failed"] == 0
