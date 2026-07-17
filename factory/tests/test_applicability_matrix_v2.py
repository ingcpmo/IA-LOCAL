"""W5 Ciclo 1 (v2), Fase 3, Bloque 3.5 — tests de la matriz de
aplicabilidad v2 y sus guardias fail-closed."""
from __future__ import annotations

from unittest import mock

import pytest
import yaml

from factory.regulatory.applicability import (
    MatrixNotApprovedError, applicability, document_type_guard, load_matrix,
    pre_inference_filter, require_matrix_approved_for_production,
)


def test_load_matrix_is_valid():
    data = load_matrix()
    assert data["matrix_version"] == "2.0"
    assert len(data["requirements"]) == 19  # los 19 requirement_id reales de Fase 0


def test_matrix_is_approved_via_checkpoint_b():
    """Checkpoint B confirmado por Cesar (2026-07-17): decision_id MC-0001,
    approved_by Cesar, approver_role project_lead -- ver
    factory/layer9/decisions/decisions.jsonl."""
    approval = load_matrix()["approval"]
    assert approval["status"] == "human_confirmed"
    assert approval["decision_id"] == "MC-0001"
    assert approval["approved_by"] == "Cesar"
    assert approval["approver_role"] == "project_lead"


def test_load_matrix_rejects_default_other_than_review_required(tmp_path, monkeypatch):
    bad = tmp_path / "bad_matrix.yaml"
    bad.write_text(yaml.dump({
        "matrix_version": "2.0",
        "approval": {"status": "pending_human_confirmation"},
        "requirements": {"X": {"FS": "expected", "default": "expected"}},
    }), encoding="utf-8")
    import factory.regulatory.applicability as mod
    load_matrix.cache_clear()
    monkeypatch.setattr(mod, "MATRIX_PATH", bad)
    with pytest.raises(ValueError, match="default debe ser review_required"):
        load_matrix()
    load_matrix.cache_clear()  # restaurar cache para el resto de la suite


def test_out_of_document_scope_produces_pointer_and_no_inference_needed():
    result = pre_inference_filter("21_CFR_11.10(d)", "IQ")
    assert result is not None
    assert result["conclusion"] == "OUT_OF_DOCUMENT_SCOPE"
    assert "FS" in result["evidence_expected_in"]
    assert result["source"] == "applicability_matrix_v2"


def test_out_of_document_scope_means_zero_ollama_calls():
    with mock.patch("httpx.post") as post:
        result = pre_inference_filter("21_CFR_11.10(d)", "IQ")
        assert result["conclusion"] == "OUT_OF_DOCUMENT_SCOPE"
        post.assert_not_called()


def test_unknown_requirement_is_review_required_visible_never_omitted():
    result = pre_inference_filter("NOT_A_REAL_REQUIREMENT", "FS")
    assert result is not None
    assert result["conclusion"] == "APPLICABILITY_REVIEW_REQUIRED"
    assert result["reason"] == "requirement_not_in_matrix"


def test_unmapped_document_type_inherits_default_review_required():
    app = applicability("ALCOA_LEGIBLE", "PQ")  # PQ no mapeado explicitamente
    assert app["value"] == "review_required"
    result = pre_inference_filter("ALCOA_LEGIBLE", "PQ")
    assert result["conclusion"] == "APPLICABILITY_REVIEW_REQUIRED"


def test_expected_and_optional_return_none_from_pre_inference_filter():
    # expected/optional/cross_reference_expected -> sigue a inferencia normal (None)
    assert pre_inference_filter("21_CFR_11.10(d)", "FS") is None
    assert applicability("21_CFR_11.10(d)", "FS")["value"] == "expected"


def test_matrix_not_approved_blocks_production_run_context(monkeypatch):
    """La matriz REAL ya esta aprobada (Checkpoint B, decision_id MC-0001)
    -- este test simula el estado 'pending_human_confirmation' via mock
    para probar la guardia sin depender de editar el archivo real."""
    import factory.regulatory.applicability as mod

    def _unapproved():
        return {"requirements": {}, "approval": {"status": "pending_human_confirmation"}}

    monkeypatch.setattr(mod, "load_matrix", _unapproved)
    with pytest.raises(MatrixNotApprovedError):
        mod.require_matrix_approved_for_production(run_context="production")


def test_matrix_not_approved_allows_validation_run_context(monkeypatch):
    import factory.regulatory.applicability as mod

    def _unapproved():
        return {"requirements": {}, "approval": {"status": "pending_human_confirmation"}}

    monkeypatch.setattr(mod, "load_matrix", _unapproved)
    mod.require_matrix_approved_for_production(run_context="validation")  # no debe lanzar


def test_matrix_approved_allows_production_run_context():
    """La matriz REAL esta aprobada desde el Checkpoint B (MC-0001) --
    verifica el estado real, sin mock."""
    require_matrix_approved_for_production(run_context="production")  # no debe lanzar


def test_document_type_guard_human_assigned_is_confirmed():
    g = document_type_guard("human_assigned", confidence=None)
    assert g["confirmed"] is True
    assert g["flags"] == []


def test_document_type_guard_inferred_low_confidence_is_unconfirmed():
    g = document_type_guard("inferred", confidence=0.5)
    assert g["confirmed"] is False
    assert "DOCUMENT_TYPE_UNCONFIRMED" in g["flags"]


def test_document_type_guard_inferred_missing_confidence_is_unconfirmed():
    g = document_type_guard("inferred", confidence=None)
    assert g["confirmed"] is False
    assert "DOCUMENT_TYPE_UNCONFIRMED" in g["flags"]


def test_document_type_guard_inferred_high_confidence_is_confirmed():
    g = document_type_guard("inferred", confidence=0.95)
    assert g["confirmed"] is True
    assert g["flags"] == []


def test_document_type_unconfirmed_propagates_to_all_conclusions():
    from factory.regulatory.verified_pipeline import evaluate_document

    def fake_generate(prompt, chunk):
        return {
            "llm_output": {
                "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
                "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
                "rationale": "n/a", "flags": [],
            },
            "execution_manifest": {
                "model": "m", "model_digest": "d", "prompt_sha256": "p",
                "schema_name": "finding_llm_v1", "schema_sha256": "s",
                "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
                "manifest_incomplete": False,
            },
            "ok": True, "errors": [], "status": "verified", "rejection_reason": None,
        }

    result = evaluate_document(
        document_type="FS",
        document_type_source="inferred",
        document_type_confidence=0.4,  # bajo -> DOCUMENT_TYPE_UNCONFIRMED
        relevant_chunks_by_requirement={
            "21_CFR_11.10(d)": [{"text": "no menciona el tema", "page_start": 1, "page_end": 1}],
        },
        generate_fn=fake_generate,
        prompt_by_requirement={"21_CFR_11.10(d)": "prompt"},
        requirement_ids={"21_CFR_11.10(d)"},
    )
    assert result.document_type_confirmed is False
    assert "DOCUMENT_TYPE_UNCONFIRMED" in result.document_level_flags
    assert len(result.requirement_summaries) == 1
    assert "DOCUMENT_TYPE_UNCONFIRMED" in result.requirement_summaries[0].conclusion.review_flags


def test_review_queue_never_silently_drops_unmapped_requirements():
    from factory.regulatory.verified_pipeline import evaluate_document

    result = evaluate_document(
        document_type="CS",  # tipo con pocas filas mapeadas -> muchos review_required
        document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={},
        generate_fn=lambda p, c: (_ for _ in ()).throw(AssertionError("no deberia llamarse")),
        prompt_by_requirement={},
        requirement_ids={"21_CFR_11.10(a)"},  # CS no mapeado explicitamente para este req
    )
    assert "21_CFR_11.10(a)" in result.review_queue
