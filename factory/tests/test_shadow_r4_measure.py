"""Tests — CF-6 v2.0 · R4/E3-E4 — medición del Relevance Model. SHADOW, sin LLM."""
from __future__ import annotations

from factory.regulatory.shadow import r4_fixture_builder as fb
from factory.regulatory.shadow import r4_measure as rm4


class TestMeasureFixture:
    def test_positive_clear_recall_is_high_at_frozen_threshold(self):
        fx = fb.build_and_freeze(out_path="/tmp/_r4_measure_fixture.json")
        rows = rm4.measure_fixture(fx)
        subset = [r for r in rows if r["category"] == "POSITIVE_CLEAR"]
        positive = sum(1 for r in subset if rm4._is_positive_frozen(r))
        assert positive / len(subset) >= 0.9  # texto verbatim del propio sub-criterio

    def test_does_not_reassign_relevance_model_thresholds(self):
        import inspect
        src = inspect.getsource(rm4)
        assert "_RELEVANT_MIN_RATIO =" not in src
        assert "_PARTIAL_MIN_RATIO =" not in src


class TestConfusionMatrix:
    def test_confusion_totals_match_n(self):
        fx = fb.build_and_freeze(out_path="/tmp/_r4_measure_fixture2.json")
        rows = rm4.measure_fixture(fx)
        conf = rm4.confusion_by(rows, rm4._is_positive_frozen)
        assert conf["TP"] + conf["FP"] + conf["FN"] + conf["TN"] == len(rows)


class TestSweepIsLocalOnly:
    def test_sweep_never_mutates_relevance_model_module(self):
        from factory.regulatory.shadow import relevance_model as real_rm
        before = (real_rm._RELEVANT_MIN_RATIO, real_rm._PARTIAL_MIN_RATIO)
        fx = fb.build_and_freeze(out_path="/tmp/_r4_measure_fixture3.json")
        rows = rm4.measure_fixture(fx)
        rm4.sweep_achievable_optimum(rows, "CALIBRATION")
        after = (real_rm._RELEVANT_MIN_RATIO, real_rm._PARTIAL_MIN_RATIO)
        assert before == after
