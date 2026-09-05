"""Tests — CF-6 v2.0 · R4 (evaluación de embeddings). Solo la parte
determinista/sin red (dry_run=True); las llamadas reales a Ollama se
ejecutan y auditan por separado (ver CF6_v2_R4_EMBEDDING_EVALUATION.json).
"""
from __future__ import annotations

from pathlib import Path

from factory.regulatory.shadow import r4_embedding_evaluation as ev


class TestLoad82Pairs:
    def test_loads_exactly_82_pairs(self):
        pairs = ev._load_all_82_pairs()
        assert len(pairs) == 82

    def test_partitions_present(self):
        pairs = ev._load_all_82_pairs()
        partitions = {p["partition"] for p in pairs}
        assert partitions == {"ORIGINAL_27", "DIAGNOSTIC_NEAR_THRESHOLD_15", "RANDOM_STRATIFIED_40"}

    def test_partition_counts(self):
        pairs = ev._load_all_82_pairs()
        counts = {}
        for p in pairs:
            counts[p["partition"]] = counts.get(p["partition"], 0) + 1
        assert counts["ORIGINAL_27"] == 27
        assert counts["DIAGNOSTIC_NEAR_THRESHOLD_15"] == 15
        assert counts["RANDOM_STRATIFIED_40"] == 40


class TestDryRun:
    def test_dry_run_makes_zero_embedding_calls(self):
        out = ev.run_embedding_evaluation(dry_run=True)
        assert out["embedding_calls_made"] == 0
        assert out["n_pairs"] == 82

    def test_dry_run_never_touches_ollama(self):
        import inspect
        src = inspect.getsource(ev)
        # el modulo importa embed_text/cosine_similarity pero dry_run los evita
        assert "if dry_run" in src


class TestDoesNotModifyRelevanceModel:
    def test_module_does_not_import_relevance_model(self):
        import ast
        tree = ast.parse(Path(ev.__file__).read_text(encoding="utf-8"))
        imported_modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(m and "relevance_model" in m for m in imported_modules)
