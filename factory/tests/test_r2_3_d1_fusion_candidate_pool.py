"""R2.3 §5 D1 (docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md, 2026-08-11 --
FIRMADO por Cesar) -- `judgment_candidate_pool.build_fusion_candidate_pool()`.
`embed_runner.run_embed_batch()` (la parte gobernada -- hard-stop de
presupuesto real, ya probada en producción real por PILOT_EXECUTION-
2026-012) se MOCKEA aquí: este archivo prueba la LÓGICA de fusión de
esta función (contrato de retorno, manejo de stop_reason, detección de
desincronización), no vuelve a probar la gobernanza de EMBED_EXECUTION
en sí. Cero llamadas reales a Ollama."""
from __future__ import annotations

import json

import pytest

from factory.regulatory.retrieval import embed_index, indexer, judgment_candidate_pool as jcp
from factory.regulatory.retrieval.embed_runner import EmbedBatchSummary


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "INDEX_DIR", tmp_path / "retrieval_index")
    monkeypatch.setattr(embed_index, "EMBED_INDEX_DIR", tmp_path / "embedding_index")


def _fake_bm25_index(sha: str) -> dict:
    return {
        "document_sha256": sha, "document_path": "fake.pdf", "avg_chunk_len": 10.0,
        "chunks": [
            {"chunk_index": 0, "page_start": 1, "page_end": 1,
             "text": "controles de auditoria y trazabilidad del sistema", "term_counts": {}, "token_count": 8},
            {"chunk_index": 1, "page_start": 2, "page_end": 2,
             "text": "informacion sin relacion con el requisito", "term_counts": {}, "token_count": 6},
        ],
    }


def _seed_indexes(sha: str) -> None:
    indexer.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (indexer.INDEX_DIR / f"{sha}.json").write_text(json.dumps(_fake_bm25_index(sha)), encoding="utf-8")
    embed_index.add_chunk_embeddings(
        sha, [
            {"chunk_index": 0, "page_start": 1, "page_end": 1, "embedding": [1.0, 0.0]},
            {"chunk_index": 1, "page_start": 2, "page_end": 2, "embedding": [0.0, 1.0]},
        ],
        embedding_model="fake-model", embedding_model_digest="fakedigest",
    )


def test_raises_explicit_error_without_embed_index():
    with pytest.raises(jcp.FusionCandidatePoolError):
        jcp.build_fusion_candidate_pool("RW-9999", "no-such-sha", "21_CFR_11.10(e)")


def test_fuses_bm25_and_embedding_rankings(monkeypatch):
    sha = "fakesha-d1"
    _seed_indexes(sha)
    monkeypatch.setattr(jcp.query_builder, "build_retrieval_query", lambda req_id: "auditoria trazabilidad")
    monkeypatch.setattr(jcp, "run_embed_batch", lambda *a, **k: EmbedBatchSummary(
        query_vectors={"21_CFR_11.10(e)": [1.0, 0.0]}))

    pool = jcp.build_fusion_candidate_pool("RW-9999", sha, "21_CFR_11.10(e)", k=5)

    assert len(pool) == 2
    assert pool[0]["chunk_index"] == 0  # coseno=1.0 con la query -- gana el ranking de embedding
    assert pool[0]["text"] == "controles de auditoria y trazabilidad del sistema"
    assert all(f["text"] is not None for f in pool)


def test_governed_hard_stop_propagates_as_explicit_error(monkeypatch):
    """Si run_embed_batch() para en HARD_STOP_CALLS (presupuesto de
    EMBED_EXECUTION agotado), build_fusion_candidate_pool() NUNCA sigue
    con un vector inventado -- falla explícito."""
    sha = "fakesha-d1-hardstop"
    _seed_indexes(sha)
    monkeypatch.setattr(jcp.query_builder, "build_retrieval_query", lambda req_id: "auditoria")
    monkeypatch.setattr(jcp, "run_embed_batch", lambda *a, **k: EmbedBatchSummary(
        stop_reason="HARD_STOP_CALLS", query_vectors={}))

    with pytest.raises(jcp.FusionCandidatePoolError, match="HARD_STOP_CALLS"):
        jcp.build_fusion_candidate_pool("RW-9999", sha, "21_CFR_11.10(e)", k=5)


def test_desync_between_bm25_and_embed_index_raises_explicit(monkeypatch):
    """Si embed_index tiene un chunk_index que BM25 ya no tiene (índices
    desincronizados -- p.ej. el PDF se re-indexó y los embeddings quedaron
    viejos), nunca debe devolver un candidato con text=None en silencio."""
    sha = "fakesha-d1-desync"
    indexer.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    stale_bm25 = _fake_bm25_index(sha)
    stale_bm25["chunks"] = stale_bm25["chunks"][:1]  # solo chunk_index 0
    (indexer.INDEX_DIR / f"{sha}.json").write_text(json.dumps(stale_bm25), encoding="utf-8")

    embed_index.add_chunk_embeddings(
        sha, [
            {"chunk_index": 0, "page_start": 1, "page_end": 1, "embedding": [1.0, 0.0]},
            {"chunk_index": 1, "page_start": 2, "page_end": 2, "embedding": [0.0, 1.0]},  # huerfano
        ],
        embedding_model="fake-model", embedding_model_digest="fakedigest",
    )
    monkeypatch.setattr(jcp.query_builder, "build_retrieval_query", lambda req_id: "auditoria")
    monkeypatch.setattr(jcp, "run_embed_batch", lambda *a, **k: EmbedBatchSummary(
        query_vectors={"21_CFR_11.10(e)": [0.0, 1.0]}))

    with pytest.raises(jcp.FusionCandidatePoolError, match="desincronizado"):
        jcp.build_fusion_candidate_pool("RW-9999", sha, "21_CFR_11.10(e)", k=5)


def test_calls_already_used_forwarded_to_run_embed_batch(monkeypatch):
    """R2.3 §5 D1: reconciliación manual de llamadas ya gastadas (mismo
    principio que embed_runner.run_embed_batch/PILOT_EXECUTION-2026-010)
    se reenvía tal cual, nunca asumida en 0 por default silencioso."""
    sha = "fakesha-d1-calls"
    _seed_indexes(sha)
    captured = {}

    def _fake_run_embed_batch(document_ids, *, queries=None, decision_store_file=None,
                               calls_already_used=0):
        captured["calls_already_used"] = calls_already_used
        return EmbedBatchSummary(query_vectors={"21_CFR_11.10(e)": [1.0, 0.0]})

    monkeypatch.setattr(jcp.query_builder, "build_retrieval_query", lambda req_id: "auditoria")
    monkeypatch.setattr(jcp, "run_embed_batch", _fake_run_embed_batch)

    jcp.build_fusion_candidate_pool("RW-9999", sha, "21_CFR_11.10(e)", k=5, calls_already_used=7)
    assert captured["calls_already_used"] == 7
