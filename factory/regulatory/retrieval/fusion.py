"""R2.2 §4.3/§4.4 -- fusión BM25 + embeddings vía Reciprocal Rank Fusion
(RRF). Determinista, sin LLM, sin dependencia nueva (solo aritmética
sobre los rankings que `retriever.py`/`embed_index.py` ya calcularon).

RRF elegido sobre suma ponderada de scores crudos porque BM25 y coseno
viven en escalas incomparables (BM25 no está acotado, coseno está en
[-1,1]) -- mezclar los números directamente exigiría normalizar y
calibrar un peso, una decisión de afinado que R2.2 no pide y que
introduciría un parámetro sin base empírica. RRF solo usa la POSICIÓN de
cada chunk en cada ranking, nunca el valor del score -- estándar de la
literatura de recuperación híbrida (Cormack et al. 2009), constante `k`
de referencia (60), NO calibrada a mano contra el fixture (mismo
principio que `bm25.K1_DEFAULT`/`B_DEFAULT`, ver `bm25.py`)."""
from __future__ import annotations

RRF_K_DEFAULT = 60


def rrf_fuse(bm25_ranked: list[dict], embedding_ranked: list[dict], *,
             k: int = RRF_K_DEFAULT, top_n: int | None = None) -> list[dict]:
    """`bm25_ranked`/`embedding_ranked`: listas ya ordenadas
    descendentemente (rank 1 = primer elemento), cada dict con al menos
    `chunk_index`. Un chunk ausente de una de las dos listas simplemente
    no aporta término RRF de esa lista (no es un error -- BM25 y
    embeddings pueden recuperar top-k distintos).

    Devuelve la lista fusionada, ordenada por `rrf_score` descendente,
    cada entrada con `chunk_index`, `page_start`, `page_end`, `text`,
    `rrf_score`, `bm25_rank` (o None), `embedding_rank` (o None) --
    page_start/page_end/text tomados de cualquiera de las dos fuentes que
    lo tenga (son el mismo chunk, mismo mapeo de página por diseño de
    `embed_index.py`)."""
    scores: dict[int, float] = {}
    ranks_bm25: dict[int, int] = {}
    ranks_embed: dict[int, int] = {}
    meta: dict[int, dict] = {}

    for rank, entry in enumerate(bm25_ranked, start=1):
        ci = entry["chunk_index"]
        ranks_bm25[ci] = rank
        scores[ci] = scores.get(ci, 0.0) + 1.0 / (k + rank)
        meta.setdefault(ci, entry)

    for rank, entry in enumerate(embedding_ranked, start=1):
        ci = entry["chunk_index"]
        ranks_embed[ci] = rank
        scores[ci] = scores.get(ci, 0.0) + 1.0 / (k + rank)
        meta.setdefault(ci, entry)

    fused = [
        {
            "chunk_index": ci,
            "page_start": meta[ci].get("page_start"),
            "page_end": meta[ci].get("page_end"),
            "text": meta[ci].get("text"),
            "rrf_score": score,
            "bm25_rank": ranks_bm25.get(ci),
            "embedding_rank": ranks_embed.get(ci),
        }
        for ci, score in scores.items()
    ]
    fused.sort(key=lambda r: r["rrf_score"], reverse=True)
    return fused[:top_n] if top_n is not None else fused
