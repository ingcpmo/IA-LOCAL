"""Techo real de llamadas de JUICIO (LLM) para `run_corpus_batch(retrieval_
mode='top_k_fusion')` -- familia `JUDGMENT_EXECUTION`
(docs_plan/PASOA_RESOLUCION_K_Y_HARDSTOP.md Bloque 2, 2026-08-22).

Motivada por Paso A (149 llamadas de juicio reales, `docs_plan/
PASOA_RESOLUCION_K_Y_HARDSTOP.md`): el número que Cesar aprueba como techo
("HARD_MAX_CALLS") nunca tenía ningún control técnico real -- D4-A
(`hard_stop_calls`) es el único hard-stop que de hecho corrió, pero mide el
COSTO DE `full_chunk` (n_checkpoints x n_criterios del contrato completo),
no el costo real de `top_k_fusion` (k chunks x requisito admitido). Esta
familia cierra ese hueco: el techo real de juicio bajo `top_k_fusion` viene
de una autorización FIRMADA (`payload.max_calls`), resuelta por
`decision_scope_resolver` -- nunca de un literal en el código ni de una
cifra de chat sin aplicación técnica.

Análoga a `embed_execution.py` (mismo patrón: propone alcance ACOTADO y
explícito, con tope duro de llamadas, nunca autoriza otra familia), pero
deliberadamente SEPARADA: `EMBED_EXECUTION` mide vectores deterministas
(sin juicio LLM); esta familia mide juicio LLM real. `decision_families.
yaml` ya declara que `JUDGMENT_EXECUTION` nunca autoriza `PILOT_EXECUTION`,
`CORPUS_AUTHORIZATION`, `D4` ni `EMBED_EXECUTION` -- ningún resolver de
esas otras familias consulta ésta.

Este módulo NUNCA llama a Ollama -- solo registra la decisión de
gobernanza. `factory/regulatory/corpus_runner.py` es quien la consume en
runtime, vía el mismo `DecisionScopeResolver` que el resto de la fábrica."""
from __future__ import annotations

from pathlib import Path

from factory.services import governance_service as gov

DECISION_FAMILY = "JUDGMENT_EXECUTION"
REQUIRED_PAYLOAD_FIELDS = ("scope", "max_calls", "retrieval_mode",
                           "authorizes_corpus", "authorizes_baseline",
                           "authorizes_pilot_execution", "authorizes_embed_execution")


class JudgmentExecutionError(Exception):
    pass


def propose_judgment_execution(*, scope: list[dict], max_calls: int, retrieval_mode: str,
                               proposed_by_id: str, reason_extra: str = "",
                               decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) el alcance exacto de un techo de llamadas
    de juicio bajo `run_corpus_batch(retrieval_mode=...)`. `scope`: lista
    explícita de dicts `{document_id, purpose, selection_reason}` --
    documentada ANTES de gastar ninguna llamada."""
    if not scope:
        raise JudgmentExecutionError("scope no puede estar vacío")
    if max_calls <= 0:
        raise JudgmentExecutionError("max_calls debe ser > 0")
    document_ids = sorted({u["document_id"] for u in scope})
    payload = {
        "scope": scope,
        "max_calls": max_calls,
        "retrieval_mode": retrieval_mode,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        "authorizes_pilot_execution": False,
        "authorizes_embed_execution": False,
    }
    reason = (
        f"JUDGMENT_EXECUTION sobre {len(scope)} documento(s), retrieval_mode={retrieval_mode!r}. "
        f"Tope duro de llamadas de JUICIO: {max_calls}. "
        "Esta firma NO autoriza PILOT_EXECUTION, CORPUS_AUTHORIZATION, D4 ni EMBED_EXECUTION -- "
        f"familia separada, ningún resolver de esas otras la consulta. {reason_extra}"
    ).strip()
    return gov.propose(
        DECISION_FAMILY, target_ids=document_ids, decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=reason, payload=payload, store_file=decision_store_file)
