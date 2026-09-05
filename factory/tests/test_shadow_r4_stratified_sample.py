"""Tests — CF-6 v2.0 · R4 (ampliación) — muestra estratificada de 40, congelada. SHADOW, sin LLM."""
from __future__ import annotations

import json

from factory.regulatory.shadow import r4_stratified_sample as strat

_DIAG15 = (
    "rec-cb15e1c9d46388bd", "rec-41020224b0ac1d19", "rec-f7eff6b9be225492",
    "rec-bff2bcf00c3551c6", "rec-284aedafa8dddd56", "rec-3369a8711e5f16a3",
    "rec-814e1e0e05380e78", "rec-850828e07185d641", "rec-2bd352f6e733c687",
    "rec-5f59722c74597726", "rec-87279db34937bf9f", "rec-9b9b6b70c63a1f85",
    "rec-e44befac41382590", "rec-39b4c3e7f96aa8b3", "rec-870a752d32280cc4",
)


class TestReproducibility:
    def test_same_seed_same_sample_hash(self, tmp_path):
        f1 = strat.freeze(out_path=tmp_path / "a.json", unblinded_out_path=tmp_path / "a_u.json")
        f2 = strat.freeze(out_path=tmp_path / "b.json", unblinded_out_path=tmp_path / "b_u.json")
        assert f1["sample_hash"] == f2["sample_hash"]

    def test_matches_frozen_artifact_already_committed(self):
        frozen = json.loads(
            open("docs_plan/shadow_llm/CF6/CF6_v2_R4_RANDOM_STRATIFIED_40.json", encoding="utf-8").read())
        assert frozen["sample_hash"] == "fc81505c483a5ca53fea959018c38256232f847e5d3d7480760d504d3506de5d"


class TestExclusion:
    def test_excludes_diagnostic_15(self):
        sample = strat.build_stratified_sample(
            "docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json", set(_DIAG15))
        ids = {c["finding_record_id"] for c in sample}
        assert ids.isdisjoint(set(_DIAG15))

    def test_excludes_previously_adjudicated_27(self):
        sample = strat.build_stratified_sample(
            "docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json", set(_DIAG15))
        assert all(not c["already_adjudicated_in_r2"] for c in sample)


class TestCoverage:
    def test_n_is_40(self, tmp_path):
        f = strat.freeze(out_path=tmp_path / "c.json", unblinded_out_path=tmp_path / "c_u.json")
        assert f["n"] == 40

    def test_covers_12_of_12_requirement_ids(self, tmp_path):
        f = strat.freeze(out_path=tmp_path / "d.json", unblinded_out_path=tmp_path / "d_u.json")
        assert f["n_requirement_ids_covered"] == 12

    def test_covers_5_of_5_documents(self, tmp_path):
        f = strat.freeze(out_path=tmp_path / "e.json", unblinded_out_path=tmp_path / "e_u.json")
        assert f["n_documents_covered"] == 5


class TestBlindArtifactHasNoModelSignal:
    def test_blind_candidates_have_no_model_fields(self, tmp_path):
        f = strat.freeze(out_path=tmp_path / "g.json", unblinded_out_path=tmp_path / "g_u.json")
        for c in f["blind_candidates"]:
            assert "model_relevance_state" not in c
            assert "weighted_ratio" not in c
            assert "n_matched" not in c
            assert "matched_terms" not in c
            assert c["human_label"] is None
            assert c["source_context_sufficient"] is None

    def test_committed_artifact_is_blind(self):
        frozen = json.loads(
            open("docs_plan/shadow_llm/CF6/CF6_v2_R4_RANDOM_STRATIFIED_40.json", encoding="utf-8").read())
        for c in frozen["blind_candidates"]:
            assert "model_relevance_state" not in c
            assert "weighted_ratio" not in c


class TestZeroLLM:
    def test_module_never_calls_llm(self):
        import inspect
        src = inspect.getsource(strat)
        assert "ollama_client" not in src
        assert "_call_llm" not in src
