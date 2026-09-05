"""Tests — CF-6 v2.0 · R4/E1 — Q-STATE-7 (scope drift de salida). SHADOW, sin LLM."""
from __future__ import annotations

from factory.regulatory.shadow import qstate7 as q7


class TestScopeDrift:
    def test_covered_subcriterion_only_passes(self):
        structured = {
            "observed_system_capability": "No se ha identificado un mecanismo de control de acceso.",
            "technical_assessment": "El sistema requiere un mecanismo de control de acceso.",
            "procedural_responsibility": "El usuario regulado debe documentar el control de acceso.",
            "gap_or_open_question": "Verificar el mecanismo de control de acceso.",
            "assessment_rationale": "El razonamiento se limita al control de acceso al sistema.",
        }
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", {"sc1"})
        assert res.passed is True
        assert res.violations == []

    def test_rule_is_conservative_generic_term_pair_can_false_positive(self):
        """Documenta, no oculta: el solapamiento léxico plano (2 términos) puede
        disparar sobre pares de palabras genéricas compartidas entre
        sub-criterios (aquí: 'acceso'+'evidencia' vs sc8, "evidencia de prueba
        de acceso..."). Es ruido conocido de una regla deliberadamente
        conservadora (fail-closed hacia SAFE_MODE), no un defecto oculto."""
        structured = {
            "observed_system_capability": "", "technical_assessment": "",
            "procedural_responsibility": "", "gap_or_open_question": "",
            "assessment_rationale": "La evidencia trata de control de acceso al sistema.",
        }
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", {"sc1"})
        assert res.passed is False
        assert any("sc8" in v for v in res.violations)

    def test_uncovered_subcriterion_content_flagged(self):
        structured = {
            "observed_system_capability": "", "technical_assessment": "",
            "procedural_responsibility": (
                "El usuario regulado debe definir y documentar el proceso de alta de cuentas, "
                "cambio de privilegios, revocación de cuentas, y la gestión de cuentas humanas "
                "e interactivas."),
            "gap_or_open_question": "", "assessment_rationale": "",
        }
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", {"sc1"})
        assert res.passed is False
        assert any("sc2" in v for v in res.violations)
        assert any("sc3" in v for v in res.violations)
        assert any("sc5" in v for v in res.violations)

    def test_reproduces_real_sec0016_finding(self):
        structured = {
            "observed_system_capability": "No se ha identificado un mecanismo de control de acceso "
                "al sistema (propio o federado) en la evidencia entregada.",
            "technical_assessment": "El sistema requiere un mecanismo de control de acceso, pero no "
                "se ha proporcionado evidencia de su implementación.",
            "procedural_responsibility": "El usuario regulado debe definir y documentar el proceso "
                "de alta de cuentas, cambio de privilegios, revocación de cuentas, y la gestión de "
                "cuentas humanas e interactivas.",
            "gap_or_open_question": "Se debe verificar si el sistema tiene un mecanismo de control "
                "de acceso y si este se ha implementado según lo especificado en la sección 3.4.1.",
            "assessment_rationale": "La evidencia proporcionada no demuestra la implementación de "
                "un mecanismo de control de acceso al sistema.",
        }
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", {"sc1"})
        assert res.passed is False
        assert len(res.violations) >= 3

    def test_empty_fields_never_flagged(self):
        structured = {f: "" for f in q7._FREE_TEXT_FIELDS}
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", {"sc1"})
        assert res.passed is True

    def test_all_subcriteria_covered_means_nothing_uncovered(self):
        structured = {
            "observed_system_capability": "control de acceso, alta de cuentas, cambio de "
                "privilegios, revisión periódica, revocación, cuentas individuales, cuentas "
                "técnicas, evidencia de prueba de acceso",
            "technical_assessment": "", "procedural_responsibility": "",
            "gap_or_open_question": "", "assessment_rationale": "",
        }
        all_ids = {"sc1", "sc2", "sc3", "sc4", "sc5", "sc6", "sc7", "sc8"}
        res = q7.check_scope_drift(structured, "21_CFR_11.10(d)", all_ids)
        assert res.passed is True

    def test_does_not_modify_relevance_model(self):
        import inspect
        src = inspect.getsource(q7)
        assert "rm._RELEVANT_MIN_RATIO" not in src
        assert "rm._PARTIAL_MIN_RATIO" not in src
        # solo reutiliza tokenización, nunca reasigna umbrales de relevance_model
        assert "rm._tokenize" in src
