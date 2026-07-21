"""
Fase 3 (`factory/docs/document_remediation_evolution/IMPLEMENTATION_ROADMAP.md`,
`TARGET_REGULATORY_ARCHITECTURE.md` §5) — adaptador entre el formato real de
`chunked_engine.evaluate_chunked()` (checkpoint `estado`/`evidencia_exacta`
por chunk, contrato v1) y el contrato `finding_llm_v1` que exige
`evidence_verifier.verify_llm_output()` (`chunk_observation`/
`evidence_quote`/`evidence_page`, contrato v2).

NO reescribe los prompts YAML gobernados (alcoa/annex11/part11/
traceability_prompts.yaml) -- el modelo sigue respondiendo `estado` como
siempre; este modulo traduce la respuesta YA recibida y YA verificada de
anclaje/relevancia por `chunked_engine._is_anchored`/`_is_topically_relevant`.
Mismo principio de "no reescribe prompts" que TARGET_REGULATORY_ARCHITECTURE.md
§5 (cambio de menor superficie posible).

Mapeo de vocabulario: mismo usado y probado en
`factory/tests/test_golden_regression.py._v1_estado_to_v2_observation`,
promovido aqui a codigo de produccion en vez de vivir solo en un test:
  cumple / cumple_parcialmente -> 'observed' (el chunk SI aporto una cita
    que chunked_engine ya valido como anclada y tematicamente relevante)
  no_cumple / evidencia_insuficiente / no_aplica -> 'not_observed_in_chunk'
    ('no_cumple' en el contrato v1 es una afirmacion SIN cita exigida --
    nunca equivale a 'observed' en v2, que exige evidencia positiva citada)
"""
from __future__ import annotations

from factory.regulatory.evidence_verifier import verify_llm_output

_OBSERVED_ESTADOS = {"cumple", "cumple_parcialmente"}


def estado_to_chunk_observation(estado: str) -> str:
    return "observed" if estado in _OBSERVED_ESTADOS else "not_observed_in_chunk"


def candidate_to_llm_output(candidate: dict, requirement_id: str) -> dict:
    """candidate: dict con al menos 'estado', 'evidencia_exacta',
    'page_start' -- ya con anclaje/relevancia resueltos por el llamador
    (mismo criterio que chunked_engine usa para sus propios Finding). Este
    adaptador nunca reevalua anclaje/relevancia, solo traduce vocabulario."""
    observation = estado_to_chunk_observation(candidate["estado"])
    evidencia = candidate.get("evidencia_exacta") or ""
    quote = evidencia if observation != "not_observed_in_chunk" else ""
    return {
        "requirement_id": requirement_id,
        "chunk_observation": observation,
        "evidence_quote": quote,
        "evidence_page": candidate["page_start"],
        "confidence": 0.7,  # no usado por verify_llm_output/consolidate; placeholder declarado
        "rationale": "Traducido desde 'estado' real de chunked_engine.evaluate_chunked() (ver docstring del adaptador).",
        "flags": [],
    }


def build_finding_record(
    record_id: str, candidate: dict, requirement_id: str, chunk: dict,
    known_requirement_ids: set, requirement_terms: list,
) -> dict:
    """finding_record_v1 real, con verificacion real (no simulada) de
    evidence_verifier.verify_llm_output(). `chunk`: dict con 'text' (texto
    fuente completo del chunk) -- necesario para reverificar la cita contra
    el documento real, no solo confiar en el anclaje ya hecho por
    chunked_engine."""
    llm_output = candidate_to_llm_output(candidate, requirement_id)
    verification = verify_llm_output(llm_output, chunk, known_requirement_ids, requirement_terms)
    return {
        "record_id": record_id,
        "llm_output": llm_output,
        "status": verification.status,
        "rejection_reason": verification.rejection_reason,
        "review_flags": verification.review_flags,
    }


def rejected_record(record_id: str, reason: str) -> dict:
    """Un chunk sin respuesta valida para este requisito (fallo tecnico de
    ejecucion, o el modelo no devolvio un checkpoint para este req_id) --
    NUNCA se omite en silencio. Cuenta como rejected_by_verifier: un chunk
    no evaluado jamas puede sostener coverage_complete real (mismo
    principio P3 reforzado de absence_consolidator.py, W5.5)."""
    return {
        "record_id": record_id,
        "llm_output": None,
        "status": "rejected_by_verifier",
        "rejection_reason": reason,
        "review_flags": [],
    }
