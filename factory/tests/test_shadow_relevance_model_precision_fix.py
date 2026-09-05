"""Tests — CF-6 v2.0 · R4 (precision-fix mínimo, 2026-09-05) — "can" en
stopwords. SHADOW, sin LLM.

Autorización de Capa 9: precision-fix mínimo basado en evidencia observada
(3 FP confirmados en DIAGNOSTIC_15, todos por el término "can"). NO se
añaden "must"/"may" (riesgo de significado regulatorio no descartado). NO
se cambian thresholds ni la fórmula/IDF.
"""
from __future__ import annotations

from factory.regulatory.shadow import relevance_model as rm


class TestCanIsStopword:
    def test_can_is_now_a_stopword(self):
        assert "can" in rm._BASIC_STOPWORDS

    def test_must_and_may_are_not_stopwords(self):
        """Explícitamente NO añadidos -- riesgo de significado regulatorio
        no descartado, por instrucción de Capa 9."""
        assert "must" not in rm._BASIC_STOPWORDS
        assert "may" not in rm._BASIC_STOPWORDS

    def test_tokenize_drops_can(self):
        assert "can" not in rm._tokenize("the operator can acknowledge an alarm")


class TestConfirmedFalsePositivesFixed:
    """Los 3 FP confirmados en DIAGNOSTIC_NEAR_THRESHOLD_15 (2026-09-05),
    todos dirigidos a 21_CFR_11.10(e)::sc9 ("the audit trail can be
    exported or copied for inspection"), coincidían SOLO por "can"."""

    def test_alarm_acknowledge_no_longer_matches(self):
        v = rm.classify(quote_text="The operator can acknowledge an alarm",
                        requirement_id="21_CFR_11.10(e)", subcriterion_id="sc9")
        assert v.relevance_state == "IRRELEVANT"
        assert v.n_matched == 0

    def test_input_points_simulated_no_longer_matches(self):
        v = rm.classify(
            quote_text="previously, with the proper credentials, the input points can be "
                      "simulated for calibration or other",
            requirement_id="21_CFR_11.10(e)", subcriterion_id="sc9")
        assert v.relevance_state == "IRRELEVANT"

    def test_water_delivery_request_no_longer_matches(self):
        v = rm.classify(
            quote_text="The operator can request water delivery (for sample) by pressing "
                      "either of the two hand switch",
            requirement_id="21_CFR_11.10(e)", subcriterion_id="sc9")
        assert v.relevance_state == "IRRELEVANT"


class TestNoRegressionOnKnownCases:
    """sec-0016 (R1, tag cf6-v2-R1) y sec-0005 (R2) no dependen de "can" --
    deben quedar exactamente igual tras el fix."""

    def test_sec0016_positive_control_unchanged(self):
        v = rm.classify(
            quote_text="3.4.1 The system shall implement the security and access control",
            requirement_id="21_CFR_11.10(d)", subcriterion_id="sc1")
        assert v.relevance_state == "PARTIALLY_RELEVANT"
        assert v.n_matched == 2

    def test_sec0016_scope_drift_candidate_still_excluded(self):
        v = rm.classify(
            quote_text="3.1.1 The system shall measure the critical process parameters for the",
            requirement_id="21_CFR_11.10(d)", subcriterion_id="sc3")
        assert v.relevance_state in (rm.IRRELEVANT, rm.INCONCLUSIVE)

    def test_sec0005_electronic_signature_false_negatives_unchanged(self):
        quote = ("With the FactoryTalk View SE electronic signature feature, each entry "
                "into the FactoryTalk View")
        v1 = rm.classify(quote_text=quote, requirement_id="21_CFR_11.50_11.70", subcriterion_id="sc1")
        v2 = rm.classify(quote_text=quote, requirement_id="21_CFR_11.50_11.70", subcriterion_id="sc2")
        assert v1.relevance_state == "INCONCLUSIVE"
        assert v2.relevance_state == "INCONCLUSIVE"


class TestThresholdsAndFormulaUntouched:
    def test_ratio_thresholds_unchanged(self):
        assert rm._RELEVANT_MIN_MATCHED == 2
        assert rm._RELEVANT_MIN_RATIO == 0.30
        assert rm._PARTIAL_MIN_MATCHED == 1
        assert rm._PARTIAL_MIN_RATIO == 0.12
