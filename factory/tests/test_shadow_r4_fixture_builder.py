"""Tests — CF-6 v2.0 · R4/E2 — construcción del fixture expandido. SHADOW, sin LLM."""
from __future__ import annotations

import hashlib

from factory.regulatory.shadow import r4_fixture_builder as fb


class TestFixtureSize:
    def test_total_at_least_150(self):
        fx = fb.build_fixture()
        assert len(fx["pairs"]) >= 150

    def test_every_category_at_least_15(self):
        fx = fb.build_fixture()
        counts = {}
        for p in fx["pairs"]:
            counts[p.category] = counts.get(p.category, 0) + 1
        assert set(counts) == set(fb._CATEGORY_LABELS)
        for cat, n in counts.items():
            assert n >= 15, f"{cat}: solo {n} pares"


class TestShapeStratification:
    def test_both_profiles_present_in_every_category(self):
        fx = fb.build_fixture()
        by_cat_profile = {}
        for p in fx["pairs"]:
            by_cat_profile.setdefault(p.category, set()).add(p.requirement_shape_profile)
        for cat, profiles in by_cat_profile.items():
            assert profiles == {"MANY_SHORT", "FEW_LONG"}, f"{cat}: perfiles {profiles}"

    def test_canonical_examples_in_expected_profile(self):
        fx = fb.build_fixture()
        assert fx["shapes"]["21_CFR_11.10(d)"] == "MANY_SHORT"
        assert fx["shapes"]["21_CFR_11.50_11.70"] == "FEW_LONG"


class TestLabelByConstruction:
    def test_labels_match_declared_category_mapping(self):
        fx = fb.build_fixture()
        for p in fx["pairs"]:
            assert p.label == fb._CATEGORY_LABELS[p.category]


class TestReproducibility:
    def test_same_seed_same_hash(self):
        d1 = fb.build_and_freeze(out_path="/tmp/_r4_fixture_test1.json")
        d2 = fb.build_and_freeze(out_path="/tmp/_r4_fixture_test2.json")
        assert d1["fixture_hash"] == d2["fixture_hash"]

    def test_does_not_touch_decomposition_yaml(self):
        from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
            DECOMPOSITION_PATH,
        )
        before = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        fb.build_and_freeze(out_path="/tmp/_r4_fixture_test3.json")
        after = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        assert before == after


class TestPartition:
    def test_calibration_heldout_disjoint_by_requirement(self):
        fx = fb.build_fixture()
        part = fb._partition_calibration_heldout(fx["pairs"], fb.SEED)
        assert set(part["CALIBRATION"]) & set(part["HELDOUT"]) == set()

    def test_both_partitions_nonempty(self):
        fx = fb.build_fixture()
        part = fb._partition_calibration_heldout(fx["pairs"], fb.SEED)
        assert len(part["CALIBRATION"]) > 0
        assert len(part["HELDOUT"]) > 0

    def test_both_partitions_have_both_shape_profiles(self):
        fx = fb.build_fixture()
        part = fb._partition_calibration_heldout(fx["pairs"], fb.SEED)
        for side in ("CALIBRATION", "HELDOUT"):
            profiles = {fx["shapes"][rid] for rid in part[side]}
            assert profiles == {"MANY_SHORT", "FEW_LONG"}, f"{side}: {profiles}"


class TestZeroLLM:
    def test_module_never_imports_ollama_client(self):
        import inspect
        src = inspect.getsource(fb)
        assert "ollama_client" not in src
        assert "_call_llm" not in src
