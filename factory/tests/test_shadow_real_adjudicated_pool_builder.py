"""Tests — CF-6 v2.0 · R4 (ampliación) — pool expandido de REAL_ADJUDICATED. SHADOW, sin LLM."""
from __future__ import annotations

import hashlib

from factory.regulatory.shadow import real_adjudicated_pool_builder as pb


class TestExpansion:
    def test_more_candidates_than_original_sample(self):
        d = pb.build_expanded_pool()
        assert d["n_candidates_total"] > 27

    def test_preserves_existing_human_labels_exactly(self):
        d = pb.build_expanded_pool()
        preserved = {c["finding_record_id"]: c["human_label"]
                    for c in d["all_candidates"] if c["already_adjudicated_in_r2"]}
        assert preserved.get("rec-33acbc832665ade8") == "RELEVANT"
        assert preserved.get("rec-f2c131db4e52163d") == "RELEVANT"
        assert d["n_already_adjudicated_preserved_from_r2"] == 27

    def test_pending_candidates_have_no_label(self):
        d = pb.build_expanded_pool()
        pending = [c for c in d["all_candidates"] if not c["already_adjudicated_in_r2"]]
        assert all(c["human_label"] is None for c in pending)
        assert len(pending) == d["n_pending_adjudication"]

    def test_only_in_scope_entries_included(self):
        d = pb.build_expanded_pool()
        from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
            has_decomposition,
        )
        for c in d["all_candidates"]:
            assert has_decomposition(c["requirement_id"])


class TestPrioritySubset:
    def test_priority_subset_capped_at_100(self):
        d = pb.build_expanded_pool()
        assert d["priority_subset_for_labeling"]["n"] <= 100

    def test_priority_subset_excludes_already_adjudicated(self):
        d = pb.build_expanded_pool()
        for c in d["priority_subset_for_labeling"]["candidates"]:
            assert c["already_adjudicated_in_r2"] is False

    def test_priority_subset_diversity_cap(self):
        d = pb.build_expanded_pool()
        counts: dict[str, int] = {}
        for c in d["priority_subset_for_labeling"]["candidates"]:
            combo = f"{c['document']}::{c['requirement_id']}"
            counts[combo] = counts.get(combo, 0) + 1
        assert all(n <= 3 for n in counts.values())


class TestZeroLLMAndIntegrity:
    def test_module_never_calls_llm(self):
        import inspect
        src = inspect.getsource(pb)
        assert "ollama_client" not in src
        assert "_call_llm" not in src

    def test_does_not_touch_decomposition_yaml(self):
        from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
            DECOMPOSITION_PATH,
        )
        before = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        pb.build_expanded_pool()
        after = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        assert before == after

    def test_does_not_touch_r2_findings(self):
        from pathlib import Path
        p = Path("docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json")
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        pb.build_expanded_pool()
        after = hashlib.sha256(p.read_bytes()).hexdigest()
        assert before == after
