"""Consolidacion documento-nivel de observaciones chunk-nivel. Deterministico
(W5 Ciclo 1, Fase 2, Bloque 2.2).

Regla central (P3): DOCUMENTATION_GAP solo puede emitirse cuando TODOS los
chunks relevantes del documento para un requisito reportan
not_observed_in_chunk y la matriz marca la evidencia como 'expected' en ese
tipo documental. El LLM (finding_llm_v1) nunca emite esta conclusion --
la produce exclusivamente esta funcion, agregando finding_record_v1 ya
verificados.

Regla adicional obligatoria (cobertura parcial, ver plan): si el conjunto
`records` pasado no cubre TODOS los chunks relevantes segun la matriz de
aplicabilidad (Fase 3), el llamador debe marcar `coverage: partial` en el
informe de cierre -- este modulo no puede detectarlo por si solo (no conoce
cuantos chunks relevantes existen en total, solo los que recibio), por eso
NO se declara aqui: es responsabilidad del orquestador (Bloque 2.3)."""
from __future__ import annotations

from dataclasses import dataclass, field

_OBSERVED_STATES = ("observed", "partially_observed")
_VALID_RECORD_STATUSES = ("verified", "verified_with_deviation", "review_required")


@dataclass
class DocumentConclusion:
    requirement_id: str
    document_type: str
    conclusion: str                 # ver catalogo abajo
    chunks_evaluated: int = 0
    chunks_observed: int = 0
    chunks_review_pending: int = 0
    supporting_records: list = field(default_factory=list)
    review_flags: list = field(default_factory=list)


def consolidate(requirement_id: str, document_type: str, applicability_value: str,
                 records: list) -> DocumentConclusion:
    """records: finding_record de TODOS los chunks relevantes evaluados
    para este requisito en este documento (status != rejected_by_verifier
    cuentan como evidencia; los rechazados no aportan)."""
    valid = [r for r in records if r["status"] in _VALID_RECORD_STATUSES]
    observed = [r for r in valid
                if r["llm_output"]["chunk_observation"] in _OBSERVED_STATES]
    pending = [r for r in valid if r["status"] == "review_required"]

    c = DocumentConclusion(requirement_id, document_type, "",
                            chunks_evaluated=len(valid),
                            chunks_observed=len(observed),
                            chunks_review_pending=len(pending),
                            supporting_records=[r["record_id"] for r in observed])

    if len(valid) == 0:
        # nada evaluable (todo rechazado o sin chunks): jamas concluir ausencia
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("NO_VALID_RECORDS")
        return c

    if observed:
        fully = [r for r in observed
                 if r["llm_output"]["chunk_observation"] == "observed"]
        c.conclusion = ("DOCUMENTED_AND_SUPPORTED" if fully
                         else "PARTIALLY_DOCUMENTED")
        if pending:
            c.review_flags.append("SUPPORTING_EVIDENCE_UNDER_REVIEW")
        return c

    # ningun chunk observo evidencia
    if pending:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("ABSENCE_BLOCKED_BY_PENDING_REVIEW")
        return c

    if applicability_value == "expected":
        c.conclusion = "DOCUMENTATION_GAP"
    elif applicability_value == "cross_reference_expected":
        c.conclusion = "CROSS_REFERENCE_MISSING"
    elif applicability_value == "optional":
        c.conclusion = "NOT_OBSERVED_OPTIONAL"
    else:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("APPLICABILITY_UNRESOLVED")
    return c
