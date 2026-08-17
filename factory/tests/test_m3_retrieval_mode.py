"""FASE M3 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`) -- `corpus_runner.
run_corpus_batch(retrieval_mode=...)`. Cero llamadas reales a Ollama ni a
embeddings en este archivo: `evaluate_chunked`/`build_fusion_candidate_
pool`/`run_embed_batch` están mockeados -- lo que se prueba es el
CABLEADO (qué se llama, con qué argumentos, en qué orden, qué detiene el
lote antes de gastar), no el recall en sí. El recall real de
`build_fusion_candidate_pool` (la misma función que aquí se mockea) ya
está medido end-to-end en `docs_plan/V1_RECALL_SECTION_AWARE_CHUNKING_
RESULTADO.md` (7/7, camino real, sin mocks) -- este archivo prueba que
`run_corpus_batch` reproduce EXACTAMENTE esa llamada, no vuelve a medir
recall gastando presupuesto de nuevo."""
from __future__ import annotations

import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.retrieval import embed_index, embed_runner, indexer, judgment_candidate_pool as jcp


class FakeCorpusProvider:
    @property
    def model_name(self):
        return "modelo-test-m3"

    @property
    def context_window(self):
        return 16384

    def show_digest(self):
        return "digest-m3"

    def runtime_version(self):
        return "test-0.0.0"


class _AuthorizedScope:
    def __init__(self, authorized=True, covering_instances=("INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


def _unit(document_id="DOC-1", agent_id="fda_part11_agent"):
    return runner.CorpusRunUnit(
        document_id=document_id, document_type="FS",
        document_path=runner.PROMPTS_DIR, document_sha256="0" * 64, agent_id=agent_id,
        prompt_path=runner._PROMPT_PATH_BY_AGENT[agent_id], expected_calls=1,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(runner, "DEFAULT_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _AuthorizedScope())
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 999, "hard_stop_wall_time_hours": 999.0,
    })


def _run(units, tmp_path, **kw):
    return runner.run_corpus_batch(
        units, provider=FakeCorpusProvider(),
        checkpoint_dir=tmp_path / "ckpt", manifest_dir=tmp_path / "manifest", **kw)


# ---------------------------------------------------------------------------
# full_chunk (default): cero cambio de comportamiento
# ---------------------------------------------------------------------------

def test_retrieval_mode_default_is_full_chunk_and_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto." * 20])
    captured = {}

    def _fake_evaluate_chunked(*a, **kw):
        captured.update(kw)
        return {
            "run_id": "run-1", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
            "technical_execution_failures": [],
        }

    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    summary = _run([_unit()], tmp_path)
    assert summary.retrieval_mode == "full_chunk"
    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert "retrieval_mode" not in captured  # el llamador de siempre no lo pasa


def test_top_k_fusion_never_activates_implicitly():
    import inspect
    sig = inspect.signature(runner.run_corpus_batch)
    assert sig.parameters["retrieval_mode"].default == "full_chunk"


# ---------------------------------------------------------------------------
# preflight de EMBED_EXECUTION -- nunca gasta una llamada de juicio si no
# hay presupuesto de embedding suficiente para el lote completo
# ---------------------------------------------------------------------------

def test_top_k_fusion_hard_stops_before_any_judgment_call_if_embed_budget_insufficient(
        monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 100, "max_calls": 60, "remaining": 10, "fits": False,
        "selected_embed_instance_id": "EMBED_EXECUTION-2026-002",
        "per_document_pending_chunks": {}, "unique_query_pairs": 0,
    })
    judgment_calls = {"n": 0}
    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", lambda *a, **kw: judgment_calls.__setitem__(
        "n", judgment_calls["n"] + 1))

    summary = _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")

    assert summary.stop_reason == "HARD_STOP_EMBED_CALLS"
    assert summary.units[0].status == "NOT_STARTED_HARD_STOP"
    assert judgment_calls["n"] == 0, "ninguna llamada de juicio si el preflight de embedding no cabe"


def test_preflight_embed_budget_fits_when_needed_within_remaining(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})
    monkeypatch.setattr(embed_index, "chunks_pending_embedding", lambda sha, **k: [1, 2, 3])
    monkeypatch.setattr(embed_runner, "_select_embed_execution_instance", lambda doc_ids, **k: {
        "selected_instance_id": "EMBED_EXECUTION-2026-002", "payload": {"max_calls": 60},
    })
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(e)", "label": "x"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    result = runner._preflight_embed_budget([_unit()], calls_already_used_for_embed=10)
    assert result["needed"] == 4  # 3 chunks pendientes + 1 consulta unica
    assert result["remaining"] == 50
    assert result["fits"] is True


def test_preflight_embed_budget_does_not_fit_when_needed_exceeds_remaining(monkeypatch):
    monkeypatch.setattr(indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})
    monkeypatch.setattr(embed_index, "chunks_pending_embedding", lambda sha, **k: list(range(55)))
    monkeypatch.setattr(embed_runner, "_select_embed_execution_instance", lambda doc_ids, **k: {
        "selected_instance_id": "EMBED_EXECUTION-2026-002", "payload": {"max_calls": 60},
    })
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(e)", "label": "x"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    result = runner._preflight_embed_budget([_unit()], calls_already_used_for_embed=10)
    assert result["fits"] is False


# ---------------------------------------------------------------------------
# cableado real de una unidad en modo top_k_fusion
# ---------------------------------------------------------------------------

def test_top_k_fusion_calls_evaluate_chunked_once_per_admitted_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-2026-002",
        "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(a)", "label": "a"}, {"req_id": "21_CFR_11.10(d)", "label": "d"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    pool_by_req = {
        "21_CFR_11.10(a)": [{"chunk_index": 0, "page_start": 46, "page_end": 46, "text": "evidencia a"}],
        "21_CFR_11.10(d)": [{"chunk_index": 1, "page_start": 40, "page_end": 40, "text": "evidencia d"}],
    }
    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool",
                        lambda doc_id, sha, req_id, **k: pool_by_req[req_id])

    captured_calls = []

    def _fake_evaluate_chunked(*a, **kw):
        captured_calls.append(kw)
        return {
            "run_id": f"run-{len(captured_calls)}", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
            "technical_execution_failures": [],
        }

    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    summary = _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")

    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert len(captured_calls) == 2  # 1 por requirement_id admitido
    assert summary.units[0].status == "COMPLETED"
    assert summary.units[0].run_ids == ["run-1", "run-2"]

    for kw, req_id in zip(captured_calls, ["21_CFR_11.10(a)", "21_CFR_11.10(d)"]):
        assert kw["full_document_coverage"] is False
        assert kw["evaluation_profile"] == "H2H4"
        assert kw["target_requirement_ids"] == [req_id]
        assert kw["retrieval_mode"] == "top_k_fusion"
        assert kw["per_unit_text"] == [c["text"] for c in pool_by_req[req_id]]
        assert kw["candidate_metadata"] == pool_by_req[req_id]
        assert kw["page_numbers"] == [c["page_start"] for c in pool_by_req[req_id]]


def test_top_k_fusion_hard_stops_if_chunk_embedding_batch_did_not_complete(monkeypatch, tmp_path):
    """Defensa en profundidad: aunque el preflight del LOTE haya dicho que
    cabe, si `run_embed_batch` de una unidad concreta reporta
    HARD_STOP_CALLS (p.ej. por una reconciliación manual desactualizada),
    la unidad falla explícito -- nunca sigue con un candidate pool
    construido sobre chunks sin embeddings completos."""
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "x", "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 5
        stop_reason = "HARD_STOP_CALLS"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())

    with pytest.raises(runner.EmbedBudgetInsufficientError):
        _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")


# ---------------------------------------------------------------------------
# fingerprint: un checkpoint top_k_fusion nunca se confunde con full_chunk
# ---------------------------------------------------------------------------

def test_fingerprint_differs_between_retrieval_modes():
    meta = {"prompt_version": "1.0.0", "schema_version": "checkpoint_llm_response_v1"}
    common = dict(model_digest="d", document_sha256="s" * 64, agent_version="v1", use_verified_pipeline=True)
    fp_full = ce.build_run_fingerprint(meta, **common, retrieval_mode="full_chunk")
    fp_topk = ce.build_run_fingerprint(meta, **common, retrieval_mode="top_k_fusion")
    assert fp_full != fp_topk
    assert fp_full["retrieval_mode"] == "full_chunk"
    assert fp_topk["retrieval_mode"] == "top_k_fusion"


def test_fingerprint_default_retrieval_mode_is_full_chunk_backward_compatible():
    meta = {"prompt_version": "1.0.0", "schema_version": "checkpoint_llm_response_v1"}
    fp = ce.build_run_fingerprint(
        meta, model_digest="d", document_sha256="s" * 64, agent_version="v1",
        use_verified_pipeline=True)
    assert fp["retrieval_mode"] == "full_chunk"
