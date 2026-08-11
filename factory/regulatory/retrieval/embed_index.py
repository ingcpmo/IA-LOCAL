"""R2.2 §4.3 -- indexación de embeddings de un documento ya indexado por
BM25 (`indexer.py`). Reutiliza el índice BM25 existente como fuente de
chunks (mismo `chunk_index`/`page_start`/`page_end`/`text`, nunca
re-chunking paralelo) -- garantiza que el mapeo de página de la capa
semántica es idéntico al de BM25, requisito explícito de R2.2 §4.4
("page mapping intact").

Persistencia: mismo patrón que `indexer.py` (JSON en disco, un archivo
por `document_sha256`, `factory/regulatory/embedding_index/`, artefacto
de runtime gitignored, regenerable llamando a Ollama de nuevo con el
mismo modelo/digest)."""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.retrieval import embed as embed_mod
from factory.regulatory.retrieval.indexer import load_index

EMBED_INDEX_DIR = Path(__file__).parent.parent / "embedding_index"


class EmbedIndexNotBuiltError(Exception):
    """El índice BM25 del documento no existe todavía -- `embed_index.py`
    nunca indexa un PDF por sí mismo, siempre depende de `indexer.py`
    (evita dos rutas de chunking divergentes)."""


def _embed_index_path(document_sha256: str) -> Path:
    return EMBED_INDEX_DIR / f"{document_sha256}.json"


def load_embed_index(document_sha256: str) -> dict | None:
    path = _embed_index_path(document_sha256)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def chunks_pending_embedding(document_sha256: str) -> list[dict]:
    """Chunks del índice BM25 que todavía NO tienen embedding calculado --
    lo que `embed_runner.py` necesita para calcular el costo real de
    llamadas ANTES de gastar presupuesto de EMBED_EXECUTION (mismo
    principio que `judgment.expected_calls_for_unit`: nunca arrancar sin
    saber el costo)."""
    bm25_index = load_index(document_sha256)
    if bm25_index is None:
        raise EmbedIndexNotBuiltError(
            f"documento {document_sha256!r} sin índice BM25 -- correr "
            "indexer.build_index() primero (embed_index.py nunca chunkea un PDF)")
    existing = load_embed_index(document_sha256)
    already = {e["chunk_index"] for e in existing["chunks"]} if existing else set()
    return [c for c in bm25_index["chunks"] if c["chunk_index"] not in already]


def add_chunk_embeddings(document_sha256: str, embedded_chunks: list[dict], *,
                         embedding_model: str, embedding_model_digest: str) -> dict:
    """Persiste embeddings YA calculados (nunca llama a Ollama -- eso es
    trabajo exclusivo de `embed_runner.py`, que es quien está gobernado
    por EMBED_EXECUTION). `embedded_chunks`: lista de
    `{chunk_index, page_start, page_end, embedding}`, apendeada al índice
    existente (idempotente por `chunk_index`)."""
    existing = load_embed_index(document_sha256) or {
        "document_sha256": document_sha256,
        "embedding_model": embedding_model,
        "embedding_model_digest": embedding_model_digest,
        "chunks": [],
    }
    by_index = {c["chunk_index"]: c for c in existing["chunks"]}
    for c in embedded_chunks:
        by_index[c["chunk_index"]] = c
    existing["chunks"] = sorted(by_index.values(), key=lambda c: c["chunk_index"])
    EMBED_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _embed_index_path(document_sha256).write_text(
        json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    return existing


def embed_query(text: str, *, model: str = embed_mod.EMBED_MODEL) -> list[float]:
    """Embedding de una query (Evidence Pack / `build_retrieval_query`) --
    delega en `embed.embed_text`, expuesto acá para que `embed_runner.py`
    y `fusion.py` no importen `embed.py` directamente (mismo nivel de
    indirección que `retriever.py` sobre `bm25.py`)."""
    return embed_mod.embed_text(text, model=model)
