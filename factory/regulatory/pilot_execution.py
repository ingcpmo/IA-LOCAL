"""Autorización LIGERA de un piloto de diagnóstico pre-corpus — familia
`PILOT_EXECUTION` (plan `W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md` §2.2).

Distinta de `CORPUS_AUTHORIZATION` (autoriza la corrida formal, atada al
`run_fingerprint` completo) y de `D4` (presupuesto/tiempo de la corrida
formal): `PILOT_EXECUTION` autoriza únicamente un alcance ACOTADO y
EXPLÍCITO (una lista cerrada de unidades documento/agente/requisito, nunca
un barrido) con su propio tope duro de llamadas, y declara en el propio
payload que NUNCA autoriza el corpus ni promueve el baseline formal —
ninguna otra familia lee `PILOT_EXECUTION` (ver `decision_families.yaml`),
así que firmarla no puede, ni por accidente, satisfacer la cobertura que
`corpus_authorization._check_corpus_authorization`/`compute_d4a` exigen.

Este módulo NUNCA lanza ninguna corrida ni hace ninguna llamada a Ollama —
solo registra la decisión de gobernanza. `corpus_runner.run_pilot_*` es
quien la consume en runtime, vía el mismo `DecisionScopeResolver` que el
resto de la fábrica (nunca lógica de cobertura paralela)."""
from __future__ import annotations

from pathlib import Path

from factory.services import governance_service as gov

DECISION_FAMILY = "PILOT_EXECUTION"
REQUIRED_PAYLOAD_FIELDS = ("scope", "max_calls", "authorizes_corpus", "authorizes_baseline")


class PilotExecutionError(Exception):
    pass


def propose_pilot_execution(*, scope: list[dict], max_calls: int, proposed_by_id: str,
                            reason_extra: str = "",
                            decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) el alcance exacto de un piloto.

    `scope`: lista explícita de dicts `{document_id, agent_id,
    requirement_id, purpose, selection_reason}` (§3.1/§4.1 del plan) —
    `purpose` distingue `"sample"` (Piloto 1, representatividad) de
    `"chain"` (Piloto 2, cadena completa sobre un documento). Documentada
    ANTES de ejecutar nada, nunca ajustada después de ver resultados.

    `max_calls`: tope duro explícito de llamadas reales a Ollama para TODO
    el piloto (ambos sub-pilotos combinados) — nunca derivado de D4-A, que
    es el presupuesto de la corrida FORMAL."""
    if not scope:
        raise PilotExecutionError("scope no puede estar vacío")
    if max_calls <= 0:
        raise PilotExecutionError("max_calls debe ser > 0")
    document_ids = sorted({u["document_id"] for u in scope})
    payload = {
        "scope": scope,
        "max_calls": max_calls,
        "authorizes_corpus": False,
        "authorizes_baseline": False,
    }
    reason = (
        f"PILOT_EXECUTION sobre {len(scope)} unidades ({len(document_ids)} documentos, "
        f"{len(sorted({u['agent_id'] for u in scope}))} agentes). Tope duro de llamadas: "
        f"{max_calls}. Esta firma NO autoriza CORPUS_AUTHORIZATION ni D4, ni promueve "
        "FORMAL_BASELINE_READY -- decisión separada y ligera para diagnosticar el "
        f"pipeline antes de comprometer la corrida formal del corpus. {reason_extra}"
    ).strip()
    return gov.propose(
        DECISION_FAMILY, target_ids=document_ids, decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=reason, payload=payload, store_file=decision_store_file)
