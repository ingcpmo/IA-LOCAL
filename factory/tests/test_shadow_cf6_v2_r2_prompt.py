"""Tests — CF-6 v2.0 · R2 — composer_prompt_v2_0_relevance_filtered.py +
composer_structured_v2_0_relevance_filtered.yaml.

Redactado/validado por autorización explícita de Capa 9 (2026-09-04):
"redactar, validar y congelar... No ejecutar R2 todavía. No realizar
llamadas LLM." Verifica: DRAFT_UNSIGNED (no ejecutable sin firma), forma del
contrato, correspondencia estricta con el contrato requirement-centric de R1
(evidence_basis restringido a relevant_evidence, requirement_text/intent
nunca pedidos como salida), 0 LLM, no toca v2/v3 firmados.
"""
from __future__ import annotations

import hashlib

import pytest

from factory.regulatory.shadow import composer_prompt_v2_0_relevance_filtered as cp
from factory.regulatory.shadow import composer_prompt as cp_v2
from factory.regulatory.shadow import composer_prompt_v3 as cp_v3


class TestDraftUnsigned:
    def test_status_is_draft_unsigned(self):
        assert cp.load()["status"] == "DRAFT_UNSIGNED"
        assert cp.is_signed() is False

    def test_assert_signed_raises(self):
        with pytest.raises(cp.PromptNotSignedError):
            cp.assert_signed()

    def test_temperature_zero(self):
        assert cp.temperature() == 0.0

    def test_output_json_only(self):
        assert cp.load()["output"] == "json_only"

    def test_no_few_shot_yet(self):
        # explícitamente vacío -- ninguna salida real existe todavía para
        # construir few-shot verificado (R2.2 no ejecutado)
        assert cp.few_shot() == []
        assert cp.has_few_shot() is False


class TestDoesNotTouchSignedPrompts:
    def test_v2_still_signed_untouched(self):
        assert cp_v2.PROMPT_VERSION == "shadow-cf6-composer-struct-v2"

    def test_v3_still_signed_untouched(self):
        assert cp_v3.is_signed() is True
        assert cp_v3.PROMPT_VERSION == "shadow-cf6-composer-struct-v3"


class TestContractShape:
    def test_required_keys_match_r1_design(self):
        spec = cp.spec()
        for k in ("assessment_state", "observed_system_capability", "evidence_basis",
                  "evidence_limitation", "technical_assessment", "procedural_responsibility",
                  "gap_or_open_question", "assessment_rationale", "confidence"):
            assert k in spec["required_keys"]

    def test_assessment_state_values_match_v3_regulatory_state(self):
        assert set(cp.ASSESSMENT_STATE_VALUES) == {"INCONCLUSIVE", "NOT_ANALYZABLE", "NOT_APPLICABLE"}

    def test_requirement_text_intent_are_inputs_not_required_outputs(self):
        # requirement_text/requirement_intent NUNCA se piden como salida del LLM
        # (son DATO gobernado de entrada, ver requirement_centric.py)
        assert "requirement_text" not in cp._REQUIRED_KEYS
        assert "requirement_intent" not in cp._REQUIRED_KEYS
        assert "{requirement_text}" in cp.load()["user_template"]
        assert "{requirement_intent}" in cp.load()["user_template"]

    def test_forbidden_keys_include_excluded_evidence(self):
        assert "excluded_evidence" in cp._FORBIDDEN_KEYS
        assert "candidate_evidence" in cp._FORBIDDEN_KEYS


class TestValidateStructureContract:
    def _valid_obj(self, **overrides):
        obj = {
            "assessment_state": "INCONCLUSIVE",
            "observed_system_capability": "El sistema registra cambios de privilegio de cuenta.",
            "evidence_basis": [{"finding_record_id": "rec-aaa", "quote": "account privilege change log"}],
            "evidence_limitation": ["Pasajes de recuperación pendientes de verificación humana."],
            "technical_assessment": "Depende del módulo de control de acceso del sistema.",
            "procedural_responsibility": "Depende del SOP de gestión de cuentas del regulated user.",
            "gap_or_open_question": "Verificar en el documento si el proceso de cambio de privilegios está descrito.",
            "assessment_rationale": "La cita ancla el registro de cambio de privilegio, pertinente al sub-criterio.",
            "confidence": "MEDIUM",
            "prohibited_conclusion": "NONE",
        }
        obj.update(overrides)
        return obj

    def test_valid_object_passes(self):
        v = cp.validate_structure_contract(self._valid_obj(), allowed_evidence_basis_ids=["rec-aaa"])
        assert v == []

    def test_evidence_basis_outside_relevant_evidence_rejected(self):
        obj = self._valid_obj(evidence_basis=[{"finding_record_id": "rec-EXCLUDED", "quote": "x"}])
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("EXCLUDED" in x or "relevant_evidence" in x for x in v)

    def test_missing_keys_detected(self):
        obj = self._valid_obj()
        del obj["technical_assessment"]
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("technical_assessment" in x for x in v)

    def test_forbidden_key_detected(self):
        obj = self._valid_obj()
        obj["compliance"] = "yes"
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("compliance" in x for x in v)

    def test_compliance_wording_rejected_in_free_text(self):
        obj = self._valid_obj(gap_or_open_question="El sistema cumple con el requisito.")
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("cumplimiento" in x for x in v)

    def test_capa_wording_rejected(self):
        obj = self._valid_obj(technical_assessment="Se requiere una acción correctiva inmediata.")
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("CAPA" in x for x in v)

    def test_page_mention_rejected_when_input_has_no_pages(self):
        obj = self._valid_obj(assessment_rationale="Ver página 4 del documento para más detalle.")
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("página" in x for x in v)

    def test_invalid_confidence_rejected(self):
        obj = self._valid_obj(confidence="VERY_HIGH")
        v = cp.validate_structure_contract(obj, allowed_evidence_basis_ids=["rec-aaa"])
        assert any("confidence" in x for x in v)

    def test_duplicate_quotes_deduped_by_normalize(self):
        obj = self._valid_obj(evidence_basis=[
            {"finding_record_id": "rec-aaa", "quote": "same quote"},
            {"finding_record_id": "rec-bbb", "quote": "same quote"},
        ])
        norm = cp.normalize_evidence_basis(obj)
        assert len(norm["evidence_basis"]) == 1


class TestRenderUsesR1Fields:
    def test_render_includes_requirement_and_relevance_filtered_language(self):
        text = cp.render(
            requirement_id="21_CFR_11.10(d)", regulatory_reference="21_CFR_11.10(d)",
            requirement_text="proceso de cambio de privilegios", requirement_intent="account privilege change process",
            document="RW-0006", origin_section_type="REGULATORY", assessment_state="INCONCLUSIVE",
            entries="- rec-aaa | ...", anchored_quotes='rec-aaa: "..."', normalized_opinions="(sin opiniones)",
        )
        assert "21_CFR_11.10(d)" in text
        assert "proceso de cambio de privilegios" in text
        assert "EVIDENCIA PERTINENTE" in text
        assert "excluded_evidence" not in text.lower().replace("_", "")


class TestZeroLLMAndNoDrift:
    def test_prompt_sha256_stable(self):
        h1 = cp.prompt_sha256()
        h2 = cp.prompt_sha256()
        assert h1 == h2

    def test_does_not_touch_decomposition_yaml(self):
        from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
            DECOMPOSITION_PATH,
        )
        before = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        cp.spec()
        cp.render(requirement_id="x", regulatory_reference="x", requirement_text="x",
                 requirement_intent="x", document="x", origin_section_type="x",
                 assessment_state="INCONCLUSIVE", entries="", anchored_quotes="", normalized_opinions="")
        after = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        assert before == after
