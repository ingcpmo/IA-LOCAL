"""Puente B4 -> B5: SubcriterionVerdict (juicio V2) -> RegulatoryFinding.

Determinista, sin LLM. Mapeo por sub-criterio (NO consolida a nivel de
requisito -- eso, con las 4 condiciones de FASE 6.2, es un paso posterior).
"""
from __future__ import annotations

from factory.regulatory.findings.risk import compute_risk
from factory.regulatory.findings.taxonomy import (
    FindingProvenance, build_finding,
)
from factory.regulatory.v2_judgment.adjudicator import (
    CONTRADICTORY_EVIDENCE, EVIDENCE_NOT_FOUND, INCONCLUSIVE, MACHINE_CONFIRMED,
    MACHINE_PARTIAL, MACHINE_REJECTED,
)

# estado del juicio -> (subtype, machine_state, confidence, severity_default)
_MAP = {
    MACHINE_CONFIRMED: ("REGULATORY_COMPLIANT_EVIDENCE", "MACHINE_CONFIRMED_FINDING", "HIGH", "LOW"),
    MACHINE_PARTIAL:   ("REGULATORY_PARTIAL", "MACHINE_DEVIATION_CANDIDATE", "MEDIUM", "MAJOR"),
    EVIDENCE_NOT_FOUND: ("REGULATORY_INCONCLUSIVE", "MACHINE_INCONCLUSIVE", "LOW", "MAJOR"),
    INCONCLUSIVE:      ("REGULATORY_INCONCLUSIVE", "MACHINE_INCONCLUSIVE", "LOW", "MAJOR"),
    MACHINE_REJECTED:  ("REGULATORY_INCONCLUSIVE", "MACHINE_INCONCLUSIVE", "LOW", "MINOR"),
    CONTRADICTORY_EVIDENCE: ("REGULATORY_INCONCLUSIVE", "MACHINE_INCONCLUSIVE", "LOW", "CRITICAL"),
}


def _anchor(verdict, bundle) -> tuple[str, int, str | None] | None:
    """(source_text, page, section_id) del claim que ancla, o None si no
    hay ninguno."""
    if verdict.best_quote and verdict.best_page:
        return verdict.best_quote, verdict.best_page, None
    if bundle.candidate_claims:
        c = bundle.candidate_claims[0]
        pg = c.get("pagina")
        if c.get("source_text") and isinstance(pg, int) and pg >= 1:
            return c["source_text"], pg, c.get("section_id")
    # último recurso: un outcome con claim
    for o in verdict.candidate_outcomes:
        for c in bundle.candidate_claims:
            if c["claim_id"] == o.claim_id and c.get("source_text") and isinstance(c.get("pagina"), int):
                return c["source_text"], c["pagina"], c.get("section_id")
    return None


def regulatory_findings_from_verdicts(pairs, *, document_id: str, extraction_version: str,
                                      run_id: str | None = None, agent_id: str | None = None,
                                      gxp_impact: str = "MEDIUM",
                                      regulatory_basis_by_req: dict | None = None) -> list:
    """`pairs`: iterable de (SubcriterionVerdict, EvidenceBundle).
    Un Finding por sub-criterio con al menos un candidato anclable.
    """
    out = []
    reg_basis = regulatory_basis_by_req or {}
    for verdict, bundle in pairs:
        mapping = _MAP.get(verdict.state)
        if mapping is None:
            continue
        subtype, machine_state, confidence, severity = mapping
        anchor = _anchor(verdict, bundle)
        if anchor is None:
            # sin nada que anclar: no se fabrica un Finding sin provenance.
            continue
        source_text, page, section_id = anchor
        risk = compute_risk(subtype, severity, gxp_impact).as_dict()
        prov = FindingProvenance(
            document_id=document_id, extraction_version=extraction_version,
            run_id=run_id, agent_id=agent_id, adjudicator_state=verdict.state,
            subcriterion_ref=verdict.subcriterion_ref,
        )
        rationale = _rationale(verdict)
        out.append(build_finding(
            "RegulatoryFinding", subtype, severity=severity, document=document_id,
            page=page, source_text=source_text, section=section_id,
            rationale=rationale, confidence=confidence, machine_state=machine_state,
            provenance=prov, requirement_id=verdict.requirement_id,
            regulatory_basis=reg_basis.get(verdict.requirement_id),
            risk=risk,
        ))
    return out


def _rationale(verdict) -> str:
    n = len(verdict.candidate_outcomes)
    states = ", ".join(sorted({o.state for o in verdict.candidate_outcomes})) or "sin candidatos"
    return (f"Sub-criterio {verdict.subcriterion_ref}: juicio V2 (2 pasos + Critic) sobre "
            f"{n} candidato(s) -> {verdict.state} (estados por candidato: {states}). "
            f"BORRADOR ASISTIDO -- no es declaración de cumplimiento; revisión humana requerida.")
