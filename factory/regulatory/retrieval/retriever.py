"""R2 (docs_plan/R2_DESIGN_DETALLADO.md) -- recuperación top-k
determinista, sin juicio. NUNCA llama a un LLM. NUNCA decide si un
candidato es evidencia válida -- eso sigue siendo trabajo exclusivo de
evaluate_chunked()/verify_llm_output/absence_consolidator; R2 no los
toca ni los antecede en autoridad, solo en orden de presentación."""
from __future__ import annotations

from factory.regulatory.retrieval.bm25 import bm25_score, build_idf_table, tokenize
from factory.regulatory.retrieval.indexer import load_index
from factory.regulatory.retrieval.query_builder import build_retrieval_query


def retrieve_top_k(document_sha256: str, req_id: str, k: int = 5) -> list[dict]:
    """Retorna hasta k chunks candidatos: {chunk_index, page_start,
    page_end, text, bm25_score}, ordenados descendente por score. []
    (nunca una excepción) si el documento no está indexado -- el llamador
    decide si eso es un error real o simplemente "todavía no indexado".
    La query se construye internamente vía build_retrieval_query(req_id)
    -- nunca acepta texto libre de un llamador (evita que alguien pase
    weak_keywords sueltas por fuera de la regla dura de query_builder)."""
    index = load_index(document_sha256)
    if index is None:
        return []
    query = build_retrieval_query(req_id)
    query_terms = tokenize(query)
    if not query_terms:
        return []
    corpus_idf = build_idf_table(query_terms, index["chunks"])
    avg_chunk_len = index["avg_chunk_len"]

    scored = [
        {
            "chunk_index": c["chunk_index"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "text": c["text"],
            "bm25_score": bm25_score(query_terms, c, corpus_idf, avg_chunk_len),
        }
        for c in index["chunks"]
    ]
    scored.sort(key=lambda r: r["bm25_score"], reverse=True)
    return scored[:k]
