"""Autorización LIGERA de llamadas de EMBEDDING -- familia `EMBED_EXECUTION`
(R2.2 §4.2, `docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md`, orden de Cesar
2026-08-10).

Análoga a `pilot_execution.py` (mismo patrón: propone alcance ACOTADO y
explícito, con tope duro de llamadas, nunca autoriza otra familia), pero
deliberadamente SEPARADA de `PILOT_EXECUTION`: los embeddings son vectores
deterministas (`nomic-embed-text`, sin juicio LLM), nunca deben competir por
ni descontar del presupuesto de juicio (`PILOT_EXECUTION.max_calls`, que mide
llamadas reales al modelo de juicio calificado). `decision_families.yaml`
ya declara que `EMBED_EXECUTION` nunca autoriza `PILOT_EXECUTION`,
`CORPUS_AUTHORIZATION` ni D4 -- ningún resolver de esas otras familias
consulta ésta.

Este módulo NUNCA llama a Ollama -- solo registra la decisión de
gobernanza. `factory/regulatory/retrieval/embed_runner.py` es quien la
consume en runtime, vía el mismo `DecisionScopeResolver` que el resto de
la fábrica."""
from __future__ import annotations

from pathlib import Path

from factory.services import governance_service as gov

DECISION_FAMILY = "EMBED_EXECUTION"
REQUIRED_PAYLOAD_FIELDS = ("scope", "max_calls", "embedding_model",
                           "authorizes_corpus", "authorizes_baseline",
                           "authorizes_pilot_execution")


class EmbedExecutionError(Exception):
    pass


def propose_embed_execution(*, scope: list[dict], max_calls: int, embedding_model: str,
                            embedding_model_digest: str, proposed_by_id: str,
                            reason_extra: str = "",
                            decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) el alcance exacto de una corrida de
    embeddings. `scope`: lista explícita de dicts `{document_id, purpose,
    selection_reason}` -- documentada ANTES de calcular ningún vector."""
    if not scope:
        raise EmbedExecutionError("scope no puede estar vacío")
    if max_calls <= 0:
        raise EmbedExecutionError("max_calls debe ser > 0")
    document_ids = sorted({u["document_id"] for u in scope})
    payload = {
        "scope": scope,
        "max_calls": max_calls,
        "embedding_model": embedding_model,
        "embedding_model_digest": embedding_model_digest,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
        "authorizes_pilot_execution": False,
    }
    reason = (
        f"EMBED_EXECUTION sobre {len(scope)} documento(s). Tope duro de llamadas: "
        f"{max_calls}. Modelo: {embedding_model} (digest {embedding_model_digest}). "
        "Esta firma NO autoriza PILOT_EXECUTION, CORPUS_AUTHORIZATION ni D4 -- "
        f"familia separada, ningún resolver de esas otras la consulta. {reason_extra}"
    ).strip()
    return gov.propose(
        DECISION_FAMILY, target_ids=document_ids, decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=reason, payload=payload, store_file=decision_store_file)
