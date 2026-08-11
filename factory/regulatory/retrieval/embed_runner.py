"""R2.2 §4.3 -- ejecución gobernada de embeddings reales. Mismo patrón de
guardia que `judgment.run_judgment_batch` sobre `PILOT_EXECUTION`, aquí
sobre `EMBED_EXECUTION` (familia separada, `embed_execution.py`): resuelve
la instancia vigente con presupuesto -> calcula el costo real ANTES de
gastar una llamada -> hard-stop si excedería `max_calls` -> persiste cada
resultado en `embed_index.py` apenas se calcula (nunca espera al batch
completo) -> un evento de auditoría al cierre.

NUNCA toca el presupuesto ni la calificación del modelo de JUICIO
(`PILOT_EXECUTION`/`model_qualification_gate`) -- un embedding es un
vector determinista, no una inferencia de juicio, así que este módulo no
importa `model_qualification_gate` en absoluto."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from factory.core import decision_scope_resolver as resolver
from factory.core.audit_writer import write_event
from factory.regulatory import embed_execution as ee
from factory.regulatory.retrieval import embed as embed_mod
from factory.regulatory.retrieval.embed_index import add_chunk_embeddings, chunks_pending_embedding
from factory.services import decision_store_v2 as decision_store


class EmbedRunNotAuthorizedError(Exception):
    pass


@dataclass
class EmbedBatchSummary:
    calls_made: dict[str, int] = field(default_factory=dict)  # document_id o "__queries__" -> n
    total_calls_made: int = 0
    stop_reason: str = "BATCH_COMPLETE"
    selected_embed_instance_id: str | None = None
    query_vectors: dict[str, list[float]] = field(default_factory=dict)


def _select_embed_execution_instance(document_ids: list[str], *,
                                     decision_store_file: Path | None = None) -> dict:
    """Mismo algoritmo que `corpus_runner._select_pilot_execution_instance`,
    aplicado a `EMBED_EXECUTION` -- deliberadamente NO reutilizado por
    import directo (esa función vive en `corpus_runner.py` acoplada a
    `PILOT_DECISION_FAMILY`), pero misma regla de selección: vigente ∧
    cubre todos los documentos ∧ presupuesto>0 ∧ decision_date más
    reciente."""
    cobertura: dict[str, set[str]] = {}
    for doc_id in document_ids:
        scope = resolver.resolve(ee.DECISION_FAMILY, doc_id, store_file=decision_store_file)
        if not scope.authorized:
            raise EmbedRunNotAuthorizedError(
                f"{doc_id!r} sin EMBED_EXECUTION vigente: {scope.denial_reason}")
        cobertura[doc_id] = set(scope.covering_instances)

    comun = set.intersection(*cobertura.values()) if cobertura else set()
    if not comun:
        raise EmbedRunNotAuthorizedError(
            "los documentos no comparten ninguna EMBED_EXECUTION vigente en común "
            f"(cobertura por documento: {cobertura!r})")

    registros = decision_store.read_all(decision_store_file)
    por_id = {r["decision_instance_id"]: r for r in registros if r.get("decision_instance_id") in comun}
    faltantes = comun - set(por_id)
    if faltantes:
        raise EmbedRunNotAuthorizedError(
            f"instancia(s) {sorted(faltantes)!r} resueltas por el resolver pero ausentes del almacén")

    con_presupuesto = [iid for iid in comun
                       if (por_id[iid].get("payload") or {}).get("max_calls", 0) > 0]
    if not con_presupuesto:
        raise EmbedRunNotAuthorizedError(
            f"{len(comun)} instancia(s) EMBED_EXECUTION vigentes cubren el lote pero ninguna "
            "tiene max_calls > 0")

    seleccionada = max(con_presupuesto, key=lambda iid: por_id[iid].get("decision_date", ""))
    payload = por_id[seleccionada].get("payload") or {}
    return {"selected_instance_id": seleccionada, "payload": payload}


def run_embed_batch(document_ids: list[str], *, queries: dict[str, str] | None = None,
                    decision_store_file: Path | None = None,
                    calls_already_used: int = 0) -> "EmbedBatchSummary":
    """Embebe los chunks pendientes de cada documento en `document_ids`
    (delta contra lo ya indexado -- idempotente, nunca re-embebe lo que ya
    tiene vector) y, si se pasa `queries` (`{requirement_id: query_text}`),
    también sus embeddings, bajo el mismo tope de `EMBED_EXECUTION`.

    `calls_already_used`: llamadas de embedding ya gastadas en una corrida
    previa parcial de esta misma instancia -- mismo principio de
    reconciliación manual que `PILOT_EXECUTION-2026-010` (ver R2.2 §1.1):
    este runner no tiene su propio checkpoint store persistente todavía,
    así que el llamador es responsable de contar lo ya hecho antes de
    invocar de nuevo (nunca asume 0 por default silencioso -- 0 sigue
    siendo el default explícito, pero documentado como tal)."""
    selection = _select_embed_execution_instance(document_ids, decision_store_file=decision_store_file)
    max_calls = selection["payload"]["max_calls"]
    model = selection["payload"]["embedding_model"]
    model_digest = selection["payload"]["embedding_model_digest"]

    summary = EmbedBatchSummary(selected_embed_instance_id=selection["selected_instance_id"])
    remaining = max_calls - calls_already_used

    for doc_id in document_ids:
        from factory.regulatory.corpus_runner import _resolve_document_path
        _, doc_sha256 = _resolve_document_path(doc_id)
        pending = chunks_pending_embedding(doc_sha256)
        made = 0
        for chunk in pending:
            if remaining <= 0:
                summary.stop_reason = "HARD_STOP_CALLS"
                break
            vector = embed_mod.embed_text(chunk["text"], model=model)
            add_chunk_embeddings(
                doc_sha256, [{
                    "chunk_index": chunk["chunk_index"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "embedding": vector,
                }],
                embedding_model=model, embedding_model_digest=model_digest,
            )
            made += 1
            remaining -= 1
        summary.calls_made[doc_id] = made
        summary.total_calls_made += made
        if remaining <= 0:
            break

    if queries and remaining > 0:
        made = 0
        for req_id, text in queries.items():
            if remaining <= 0:
                summary.stop_reason = "HARD_STOP_CALLS"
                break
            summary.query_vectors[req_id] = embed_mod.embed_text(text, model=model)
            made += 1
            remaining -= 1
        summary.calls_made["__queries__"] = made
        summary.total_calls_made += made
    elif queries and remaining <= 0:
        summary.stop_reason = "HARD_STOP_CALLS"

    write_event("r2_embed_batch_completed", "regulatory_intel", {
        "document_ids": document_ids,
        "stop_reason": summary.stop_reason,
        "total_calls_made": summary.total_calls_made,
        "calls_made_by_scope": summary.calls_made,
        "selected_embed_instance_id": summary.selected_embed_instance_id,
        "embedding_model": model,
        "embedding_model_digest": model_digest,
    })
    return summary
