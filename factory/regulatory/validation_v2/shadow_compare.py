"""Comparación lado a lado CURRENT vs V2 shadow (V2, B9) -- FASE 11 §2.

Por (documento x requisito): la conclusión de CURRENT vs el
`machine_state` agregado de V2. Clasifica cada requisito para que Capa 9
vea qué cambia antes del cutover. Determinista, sin LLM.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

# Conclusiones de CURRENT que cuentan como "cerrado positivo".
_CURRENT_POSITIVE = {"DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED",
                     "PROVISIONALLY_DOCUMENTED", "PROVISIONALLY_PARTIALLY_DOCUMENTED"}
_CURRENT_GAP = {"DOCUMENTATION_GAP", "PROVISIONAL_GAP"}
_CURRENT_TO_HUMAN = {"EVALUATION_INCOMPLETE", "SUPPORTING_EVIDENCE_UNDER_REVIEW",
                     "EVIDENCE_NOT_LOCATED_IN_CANDIDATES", "NEEDS_HUMAN_REVIEW"}

_V2_POSITIVE = {"MACHINE_CONFIRMED_FINDING"}
_V2_CANDIDATE = {"MACHINE_DEVIATION_CANDIDATE"}
_V2_TO_HUMAN = {"MACHINE_INCONCLUSIVE"}


@dataclass
class RequirementDelta:
    requirement_id: str
    current_conclusion: str
    v2_state: str
    classification: str
    note: str = ""


def _v2_state_for_requirement(v2_findings: list, requirement_id: str) -> str:
    """El machine_state 'más fuerte' entre los findings V2 de ese requisito."""
    states = [f.machine_state for f in v2_findings if getattr(f, "requirement_id", None) == requirement_id]
    for s in ("MACHINE_CONFIRMED_FINDING", "MACHINE_DEVIATION_CANDIDATE",
              "MACHINE_REMEDIATION_PROPOSAL", "MACHINE_INCONCLUSIVE"):
        if s in states:
            return s
    return "NO_V2_FINDING"


def _classify(current: str, v2: str) -> tuple[str, str]:
    cur_pos = current in _CURRENT_POSITIVE
    cur_gap = current in _CURRENT_GAP
    v2_pos = v2 in _V2_POSITIVE
    v2_hum = v2 in _V2_TO_HUMAN or v2 == "NO_V2_FINDING"

    # más específico primero
    if cur_gap and v2_pos:
        return "CURRENT_GAP_V2_CONFIRMED", "V2 encuentra evidencia donde CURRENT declaró gap -- posible falso gap de CURRENT"
    if cur_gap and v2 in _V2_CANDIDATE:
        return "BOTH_FLAG_GAP", "ambos marcan hueco -- consistente"
    if cur_pos and v2_pos:
        return "AGREEMENT_POSITIVE", "ambos confirman"
    if cur_pos and v2_hum:
        return "CURRENT_CLOSED_V2_TO_HUMAN", "V2 es más conservador -- ¿regresión o CURRENT era optimista?"
    if v2_pos and not cur_pos:
        return "NEW_CONFIRMED_BY_V2", "V2 ancla evidencia que CURRENT no cerró -- revisar la cita"
    if current in _CURRENT_TO_HUMAN and v2_hum:
        return "AGREEMENT_TO_HUMAN", "ambos a revisión humana"
    return "OTHER", f"current={current!r} v2={v2!r}"


def compare(current_conclusions: dict, v2_findings: list) -> dict:
    """`current_conclusions`: {requirement_id: conclusion_str} de una corrida
    CURRENT. `v2_findings`: Finding[] de una corrida shadow V2."""
    deltas: list[RequirementDelta] = []
    all_reqs = set(current_conclusions) | {getattr(f, "requirement_id", None) for f in v2_findings}
    all_reqs.discard(None)
    for req in sorted(all_reqs):
        cur = current_conclusions.get(req, "NOT_EVALUATED")
        v2 = _v2_state_for_requirement(v2_findings, req)
        cls, note = _classify(cur, v2)
        deltas.append(RequirementDelta(req, cur, v2, cls, note))

    counts = Counter(d.classification for d in deltas)
    return {
        "n_requirements": len(deltas),
        "classification_counts": dict(counts),
        "attention": [d.__dict__ for d in deltas
                      if d.classification in ("NEW_CONFIRMED_BY_V2", "CURRENT_CLOSED_V2_TO_HUMAN",
                                              "CURRENT_GAP_V2_CONFIRMED", "OTHER")],
        "deltas": [d.__dict__ for d in deltas],
        "cutover_recommendation": _recommend(counts),
    }


def _recommend(counts: Counter) -> str:
    regressions = counts.get("CURRENT_CLOSED_V2_TO_HUMAN", 0)
    gains = counts.get("NEW_CONFIRMED_BY_V2", 0) + counts.get("CURRENT_GAP_V2_CONFIRMED", 0)
    if regressions == 0 and gains > 0:
        return "V2 mejora sin regresiones aparentes -- candidato a cutover (decisión de Capa 9 + gates A/B/C)"
    if regressions > 0:
        return (f"{regressions} requisito(s) que CURRENT cerraba ahora van a humano -- "
                "revisar caso por caso antes de recomendar cutover")
    return "sin cambios materiales -- shadow no aporta señal para cutover todavía"
