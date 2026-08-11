"""R2.2 §4.3 (docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md) -- capa de
recuperación semántica (embeddings + fusión RRF con BM25). Cero llamadas
reales a Ollama en este archivo: `embed.embed_text` siempre monkeypatcheado
con vectores sintéticos deterministas -- las llamadas reales están
gobernadas por EMBED_EXECUTION y presupuestadas aparte (ver
`docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md` §4.2/§4.4), nunca gastadas
implícitamente por la suite de tests."""
from __future__ import annotations

import math

import pytest

from factory.regulatory.retrieval import embed as embed_mod
from factory.regulatory.retrieval import embed_index, fusion, indexer


# --- fusion.rrf_fuse ---------------------------------------------------

def test_rrf_fuse_boosts_chunk_ranked_high_in_both_lists():
    bm25_ranked = [
        {"chunk_index": 1, "page_start": 1, "page_end": 1, "text": "a"},
        {"chunk_index": 2, "page_start": 2, "page_end": 2, "text": "b"},
        {"chunk_index": 3, "page_start": 3, "page_end": 3, "text": "c"},
    ]
    embedding_ranked = [
        {"chunk_index": 2, "page_start": 2, "page_end": 2, "text": "b"},
        {"chunk_index": 1, "page_start": 1, "page_end": 1, "text": "a"},
        {"chunk_index": 3, "page_start": 3, "page_end": 3, "text": "c"},
    ]
    fused = fusion.rrf_fuse(bm25_ranked, embedding_ranked)
    # chunk 1 y 2 aparecen top-2 en ambas listas -> deben rankear por
    # encima de chunk 3 (rank 3 en ambas)
    assert [f["chunk_index"] for f in fused[:2]] == [1, 2] or [f["chunk_index"] for f in fused[:2]] == [2, 1]
    assert fused[2]["chunk_index"] == 3
    assert fused[0]["rrf_score"] > fused[2]["rrf_score"]


def test_rrf_fuse_chunk_only_in_one_list_still_included():
    bm25_ranked = [{"chunk_index": 5, "page_start": 5, "page_end": 5, "text": "x"}]
    embedding_ranked = [{"chunk_index": 9, "page_start": 9, "page_end": 9, "text": "y"}]
    fused = fusion.rrf_fuse(bm25_ranked, embedding_ranked)
    by_index = {f["chunk_index"]: f for f in fused}
    assert by_index[5]["bm25_rank"] == 1 and by_index[5]["embedding_rank"] is None
    assert by_index[9]["embedding_rank"] == 1 and by_index[9]["bm25_rank"] is None


def test_rrf_fuse_top_n_truncates():
    bm25_ranked = [{"chunk_index": i, "page_start": i, "page_end": i, "text": str(i)} for i in range(5)]
    fused = fusion.rrf_fuse(bm25_ranked, [], top_n=2)
    assert len(fused) == 2


def test_rrf_fuse_dimension_mismatch_never_silently_passes_cosine():
    with pytest.raises(ValueError):
        embed_mod.cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


# --- embed.cosine_similarity --------------------------------------------

def test_cosine_similarity_identical_vectors_is_one():
    v = [0.3, 0.4, 0.5]
    assert math.isclose(embed_mod.cosine_similarity(v, v), 1.0, rel_tol=1e-9)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert embed_mod.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_zero_vector_never_raises_zero_division():
    assert embed_mod.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# --- embed_index (sin llamadas reales) -----------------------------------

@pytest.fixture(autouse=True)
def isolated_indexes(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "INDEX_DIR", tmp_path / "retrieval_index")
    monkeypatch.setattr(embed_index, "EMBED_INDEX_DIR", tmp_path / "embedding_index")


def _fake_bm25_index(doc_sha256: str) -> dict:
    return {
        "document_sha256": doc_sha256,
        "document_path": "fake.pdf",
        "avg_chunk_len": 10.0,
        "chunks": [
            {"chunk_index": 0, "page_start": 1, "page_end": 1, "text": "chunk 0", "term_counts": {}, "token_count": 2},
            {"chunk_index": 1, "page_start": 2, "page_end": 2, "text": "chunk 1", "term_counts": {}, "token_count": 2},
        ],
    }


def test_chunks_pending_embedding_raises_without_bm25_index():
    with pytest.raises(embed_index.EmbedIndexNotBuiltError):
        embed_index.chunks_pending_embedding("no-such-sha")


def test_chunks_pending_embedding_returns_all_chunks_when_none_embedded_yet(monkeypatch):
    sha = "fakesha001"
    indexer.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (indexer.INDEX_DIR / f"{sha}.json").write_text(
        __import__("json").dumps(_fake_bm25_index(sha)), encoding="utf-8")
    pending = embed_index.chunks_pending_embedding(sha)
    assert {c["chunk_index"] for c in pending} == {0, 1}


def test_add_chunk_embeddings_then_pending_excludes_already_embedded():
    sha = "fakesha002"
    indexer.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (indexer.INDEX_DIR / f"{sha}.json").write_text(
        __import__("json").dumps(_fake_bm25_index(sha)), encoding="utf-8")

    embed_index.add_chunk_embeddings(
        sha, [{"chunk_index": 0, "page_start": 1, "page_end": 1, "embedding": [0.1, 0.2]}],
        embedding_model="fake-model", embedding_model_digest="fakedigest")

    pending = embed_index.chunks_pending_embedding(sha)
    assert {c["chunk_index"] for c in pending} == {1}

    idx = embed_index.load_embed_index(sha)
    assert idx["chunks"][0]["chunk_index"] == 0
    assert idx["chunks"][0]["embedding"] == [0.1, 0.2]
    assert idx["embedding_model"] == "fake-model"


def test_embed_text_raises_explicit_error_on_missing_embedding_field(monkeypatch):
    """Fail-closed (mismo principio P1/TE-02 que ollama_client): una
    respuesta de Ollama sin 'embedding' nunca se trata como vector cero
    silencioso."""
    import httpx

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse())
    with pytest.raises(embed_mod.EmbeddingUnavailableError):
        embed_mod.embed_text("hola")
