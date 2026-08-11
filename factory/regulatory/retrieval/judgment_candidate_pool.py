"""R2.3 §5 D1 (docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md, 2026-08-11 --
FIRMADO por Cesar, 2026-08-11) -- constructor por defecto del candidate
pool de modo JUICIO: fusión RRF (BM25 + embeddings) en vez de BM25 solo,
medido en docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md §4.4 (7/7 recall_at_5)
y verificado en producción real (§5.2 -- no rescató a P2/P5 del límite de
juicio, pero sí es la recuperación mejor medida disponible).

Resuelve el hueco de gobernanza señalado en la propuesta original de D1:
la llamada de embedding de la CONSULTA ahora pasa por
`embed_runner.run_embed_batch()` (mismo hard-stop de presupuesto real que
protege la indexación de chunks) en vez de llamar a
`embed_index.embed_query()`/`embed.embed_text()` directo -- ninguna
llamada real se gasta sin una `EMBED_EXECUTION` vigente con presupuesto
> 0 para el `document_id`. `judgment.py` sigue construyendo
`JudgmentUnit.candidate_chunks` explícitamente -- este módulo es el
constructor recomendado para hacerlo (reemplazo directo de
`retriever.retrieve_top_k()`, mismo contrato de retorno), la adopción
como *default* en el call-site real de producción es una corrida
separada (dimensionada, con su propia `PILOT_EXECUTION`/`EMBED_EXECUTION`
si hace falta indexar un documento nuevo) -- este paquete deja el código
listo y probado, no lanza ninguna corrida."""
from __future__ import annotations

from factory.regulatory.retrieval import embed_index, fusion, query_builder, retriever
from factory.regulatory.retrieval.embed_runner import run_embed_batch


class FusionCandidatePoolError(Exception):
    """El documento no tiene índice de embeddings todavía -- construir el
    pool de fusión requiere que EMBED_EXECUTION ya haya indexado este
    documento (embed_runner.run_embed_batch). Nunca cae en silencio a
    BM25 solo: un pool "de fusión" que en realidad es BM25 solo, sin que
    el llamador lo sepa, sería una regresión disfrazada de mejora."""


def build_fusion_candidate_pool(document_id: str, document_sha256: str, req_id: str, *,
                                 k: int = 5, calls_already_used: int = 0) -> list[dict]:
    """Reemplazo directo, mismo contrato de retorno, de
    `retriever.retrieve_top_k(document_sha256, req_id, k)`: hasta `k`
    candidatos `{chunk_index, page_start, page_end, text, bm25_rank,
    embedding_rank, rrf_score}` -- rankeados por fusión RRF (BM25 +
    coseno de embeddings) en vez de BM25 solo.

    `document_id` (RW-XXXX, el identificador de gobernanza) Y
    `document_sha256` (el identificador de los índices BM25/embeddings)
    -- SE PIDEN LOS DOS porque `embed_runner.run_embed_batch()` (gobierno,
    hard-stop de presupuesto) trabaja por `document_id` mientras que
    `retriever`/`embed_index` trabajan por `document_sha256`; resolverlos
    uno del otro aquí adentro duplicaría `corpus_runner._resolve_document_
    path` sin necesidad -- el llamador (`judgment.py`) ya tiene ambos.

    Costo real: 1 llamada de embedding por invocación (la consulta del
    requisito) -- gobernada por la MISMA `EMBED_EXECUTION` vigente para
    `document_id` que ya protege la indexación de chunks; hard-stop ANTES
    de gastar si no hay presupuesto (mismo mecanismo que `run_embed_batch`
    usa para chunks, ahora también para la consulta). Los chunks del
    documento deben estar YA embebidos por una corrida previa -- esta
    función NUNCA los embebe (ver `FusionCandidatePoolError` si faltan)."""
    eidx = embed_index.load_embed_index(document_sha256)
    if eidx is None:
        raise FusionCandidatePoolError(
            f"documento {document_sha256!r} sin índice de embeddings -- correr "
            "embed_runner.run_embed_batch() primero (gobernado por EMBED_EXECUTION)")

    bm25_results = retriever.retrieve_top_k(document_sha256, req_id, k=10_000)

    query_text = query_builder.build_retrieval_query(req_id)
    embed_summary = run_embed_batch(
        [document_id], queries={req_id: query_text}, calls_already_used=calls_already_used)
    if embed_summary.stop_reason != "BATCH_COMPLETE" or req_id not in embed_summary.query_vectors:
        raise FusionCandidatePoolError(
            f"embedding de la consulta de {req_id!r} no se pudo calcular -- "
            f"stop_reason={embed_summary.stop_reason!r} (presupuesto de EMBED_EXECUTION "
            "agotado o instancia no vigente para este documento)")
    query_vector = embed_summary.query_vectors[req_id]

    embedding_ranked = sorted(
        [
            {
                "chunk_index": c["chunk_index"], "page_start": c["page_start"],
                "page_end": c["page_end"], "text": None,
                "score": _cosine(query_vector, c["embedding"]),
            }
            for c in eidx["chunks"]
        ],
        key=lambda c: c["score"], reverse=True,
    )

    fused = fusion.rrf_fuse(bm25_results, embedding_ranked, top_n=k)
    # rrf_fuse toma el `text` de cualquiera de las dos listas que lo tenga
    # -- embedding_ranked lo deja en None a propósito (embed_index no
    # persiste texto, solo vectores), así que siempre viene de bm25_results
    # para cualquier chunk indexado por BM25 (todo chunk lo está, por
    # construcción de embed_index.py sobre el mismo índice). Verificación
    # explícita, no asumida:
    for f in fused:
        if f["text"] is None:
            raise FusionCandidatePoolError(
                f"chunk_index={f['chunk_index']} sin texto en ninguna de las dos fuentes "
                "-- índice de embeddings desincronizado del índice BM25")
    return fused


def _cosine(a: list[float], b: list[float]) -> float:
    from factory.regulatory.retrieval.embed import cosine_similarity
    return cosine_similarity(a, b)
