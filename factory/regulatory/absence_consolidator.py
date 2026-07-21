"""Consolidacion documento-nivel de observaciones chunk-nivel. Deterministico
(W5 Ciclo 1, Fase 2, Bloque 2.2).

Regla central (P3): DOCUMENTATION_GAP solo puede emitirse cuando TODOS los
chunks relevantes del documento para un requisito reportan
not_observed_in_chunk y la matriz marca la evidencia como 'expected' en ese
tipo documental. El LLM (finding_llm_v1) nunca emite esta conclusion --
la produce exclusivamente esta funcion, agregando finding_record_v1 ya
verificados.

Regla reforzada (W5.5, tras el hallazgo de ETAPA 3/Fase 5.4.4: un
DOCUMENTATION_GAP se emitio con solo 2/29 chunks reales evaluados porque el
3er chunk quedo rejected_by_verifier y el modulo no tenia forma de saberlo
ni de saber si esos 2 eran todos los chunks relevantes): `coverage_complete`
es ahora un parametro obligatorio, sin default -- el llamador debe declarar
explicitamente si `records` cubre TODOS los chunks relevantes del documento
para este requisito. DOCUMENTATION_GAP nunca se emite si `coverage_complete`
es False, o si algun chunk quedo `rejected_by_verifier` (un chunk rechazado
nunca fue observado con exito -- no puede contar como "ausencia
confirmada"). En cualquiera de los dos casos la conclusion es
EVALUATION_INCOMPLETE, nunca DOCUMENTATION_GAP. Esta regla reforzada aplica
solo a DOCUMENTATION_GAP (P3), no a CROSS_REFERENCE_MISSING ni
NOT_OBSERVED_OPTIONAL -- fuera de alcance de este fix.

Regla reforzada (W5.6, ETAPA 4): DOCUMENTED_AND_SUPPORTED/PARTIALLY_
DOCUMENTED exigen al menos un registro observed/partially_observed con
status verified o verified_with_deviation -- un requisito cuya UNICA
evidencia observada esta en status review_required (sin verificar aun)
concluye SUPPORTING_EVIDENCE_UNDER_REVIEW, nunca un estado que implique
soporte documental confirmado (mismo principio P1 que la regla reforzada de
P3: no afirmar mas de lo que el verificador confirmo)."""
from __future__ import annotations

from dataclasses import dataclass, field

_OBSERVED_STATES = ("observed", "partially_observed")
_VALID_RECORD_STATUSES = ("verified", "verified_with_deviation", "review_required")
_REJECTED_STATUS = "rejected_by_verifier"


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
                 records: list, *, coverage_complete: bool) -> DocumentConclusion:
    """records: finding_record de TODOS los chunks relevantes evaluados
    para este requisito en este documento (status != rejected_by_verifier
    cuentan como evidencia; los rechazados no aportan).

    coverage_complete (obligatorio, sin default): True solo si `records`
    incluye TODOS los chunks relevantes del documento para este requisito
    (evaluados o rechazados) -- no un subconjunto parcial. Determina si
    DOCUMENTATION_GAP puede emitirse (ver regla reforzada W5.5 arriba)."""
    valid = [r for r in records if r["status"] in _VALID_RECORD_STATUSES]
    rejected = [r for r in records if r["status"] == _REJECTED_STATUS]
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
        # W5.6 (hallazgo real, ETAPA 4): "observed" incluye tanto verified/
        # verified_with_deviation como review_required -- antes de este fix,
        # un requisito con evidencia UNICAMENTE en registros review_required
        # (ninguno verificado) igual concluia DOCUMENTED_AND_SUPPORTED, pese
        # a que ningun chunk_observation paso el verificador. Documentar como
        # "soportado" algo que nadie verifico viola P1. Ahora
        # DOCUMENTED_AND_SUPPORTED/PARTIALLY_DOCUMENTED exigen al menos un
        # observed con status verified/verified_with_deviation; si toda la
        # evidencia observada esta sin verificar, la conclusion es
        # SUPPORTING_EVIDENCE_UNDER_REVIEW (pendiente de juicio humano, no
        # una afirmacion de soporte documental).
        observed_verified = [r for r in observed
                              if r["status"] in ("verified", "verified_with_deviation")]
        if observed_verified:
            fully = [r for r in observed_verified
                     if r["llm_output"]["chunk_observation"] == "observed"]
            c.conclusion = ("DOCUMENTED_AND_SUPPORTED" if fully
                             else "PARTIALLY_DOCUMENTED")
            if pending:
                c.review_flags.append("SUPPORTING_EVIDENCE_UNDER_REVIEW")
        else:
            c.conclusion = "SUPPORTING_EVIDENCE_UNDER_REVIEW"
            c.review_flags.append("OBSERVED_ONLY_UNVERIFIED")
        return c

    # ningun chunk observo evidencia
    if pending:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("ABSENCE_BLOCKED_BY_PENDING_REVIEW")
        return c

    if applicability_value == "expected":
        # P3 reforzado (W5.5): cobertura incompleta o chunks rechazados
        # nunca pueden sostener una ausencia confirmada.
        if not coverage_complete:
            c.conclusion = "EVALUATION_INCOMPLETE"
            c.review_flags.append("ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE")
        elif rejected:
            c.conclusion = "EVALUATION_INCOMPLETE"
            c.review_flags.append("ABSENCE_BLOCKED_BY_REJECTED_CHUNKS")
        else:
            c.conclusion = "DOCUMENTATION_GAP"
    elif applicability_value == "cross_reference_expected":
        c.conclusion = "CROSS_REFERENCE_MISSING"
    elif applicability_value == "optional":
        c.conclusion = "NOT_OBSERVED_OPTIONAL"
    else:
        c.conclusion = "EVALUATION_INCOMPLETE"
        c.review_flags.append("APPLICABILITY_UNRESOLVED")
    return c
