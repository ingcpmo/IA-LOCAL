"""Modo Tier-1 para la clase REGULATORY (V2) --
docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md §9 (Palanca C, adoptada por
Capa 9 el 2026-08-27 tras el 0/7 de B4b en ambas variantes).

El juicio semántico de paráfrasis del 7B local NO funciona (6 vías
independientes). Para la clase Regulatory, el analizador NO automatiza ese
juicio. En modo Tier-1:

  1. eco léxico anclado  -> RegulatoryFinding REGULATORY_COMPLIANT_EVIDENCE
     machine_state MACHINE_CONFIRMED_FINDING (candidato a confirmación
     humana rápida; NUNCA aprobación). El anclaje lo hace evidence_verifier
     (validación A) sobre el mejor candidato del EvidenceBundle contra el
     sub-criterio -- MISMO verificador, sin relajar nada.
  2. todo lo demás       -> RegulatoryFinding REGULATORY_INCONCLUSIVE
     machine_state MACHINE_INCONCLUSIVE, con los candidatos del
     EvidenceBundle adjuntos marcados "RECUPERACIÓN, no evidencia
     validada", y una declaración de cobertura explícita.

CERO llamadas LLM. Determinista. `human_state` de todo finding nace
UNREVIEWED; ningún path lo cambia. Sin declaración de cumplimiento final.
"""
from __future__ import annotations

from dataclasses import dataclass

from factory.regulatory.evidence_verifier import (
    load_requirement_terms, match_citation, relevance_score,
)
from factory.regulatory.findings.risk import compute_risk
from factory.regulatory.findings.taxonomy import FindingProvenance, build_finding
from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria, subcriterion_ref,
)
from factory.regulatory.retrieval.evidence_bundle import build_bundles_for_requirement

COVERAGE_STATEMENT = (
    "MODO TIER-1 (Palanca C). El análisis regulatorio automatizado se limita a: "
    "(a) confirmación de eco léxico anclado por el verificador determinista; "
    "(b) recuperación semántica de candidatos entregada al revisor. "
    "La detección automática de evidencia PARAFRASEADA NO está incluida — el modelo "
    "local no la resuelve (medido 6 veces). Todo sub-criterio sin eco léxico anclado "
    "va a revisión humana. NUNCA hay declaración de cumplimiento ni aprobación automática."
)

# Umbral de eco léxico: el mejor candidato debe (1) anclar textualmente
# alguna frase del sub-criterio (match_citation exact/normalized/despaced)
# O (2) tener solapamiento léxico alto con los términos del requisito.
_LEXICAL_ECHO_RELEVANCE_MIN = 0.60


@dataclass
class Tier1SubResult:
    subcriterion_ref: str
    mode: str                  # "LEXICAL_ECHO_CONFIRMED" | "TO_HUMAN_REVIEW"
    best_claim_id: str | None
    best_quote: str | None
    best_page: int | None
    candidates_seen: int


def _lexical_echo(subcriterion_text: str, candidate: dict, req_terms: list) -> bool:
    src = candidate.get("source_text", "")
    mtype, _ = match_citation(subcriterion_text, src)
    if mtype in ("exact", "normalized", "despaced"):
        return True
    rs = relevance_score(src, req_terms)
    return rs >= _LEXICAL_ECHO_RELEVANCE_MIN


def regulatory_tier1_findings(document_id: str, requirement_ids: list[str], *,
                              extraction_version: str, run_id: str | None = None,
                              canon_dir=None, regulatory_basis_by_req: dict | None = None) -> list:
    """Un RegulatoryFinding por sub-criterio de cada requisito. CERO LLM.
    Requiere canonical_store poblado (B1) para `document_id`."""
    reg_basis = regulatory_basis_by_req or {}
    findings: list = []
    for req_id in requirement_ids:
        req_terms = load_requirement_terms(req_id)
        kw = {"canon_dir": canon_dir} if canon_dir is not None else {}
        bundles = {b.subcriterion_id: b for b in
                   build_bundles_for_requirement(document_id, req_id, **kw)}
        for sc in get_subcriteria(req_id):
            b = bundles.get(sc["id"])
            cands = b.candidate_claims if b else []
            echo = None
            for c in cands:
                if _lexical_echo(sc["text"], c, req_terms) or _lexical_echo(sc.get("text_en", ""), c, req_terms):
                    echo = c
                    break

            if echo is not None:
                subtype, mstate, conf, sev = ("REGULATORY_COMPLIANT_EVIDENCE",
                                              "MACHINE_CONFIRMED_FINDING", "MEDIUM", "LOW")
                rationale = (f"Eco léxico anclado en '{echo['source_text'][:120]}'. "
                             f"CANDIDATO a confirmación humana rápida -- NO es aprobación. "
                             f"{COVERAGE_STATEMENT}")
                src_text, page = echo["source_text"], echo.get("pagina")
            else:
                subtype, mstate, conf, sev = ("REGULATORY_INCONCLUSIVE",
                                              "MACHINE_INCONCLUSIVE", "LOW", "MAJOR")
                top = cands[0] if cands else None
                if top is None:
                    continue  # sin nada que anclar
                src_text, page = top["source_text"], top.get("pagina")
                cand_list = "; ".join(f"[{c['claim_id']} p.{c.get('pagina')}]" for c in cands[:3])
                rationale = (f"Sin eco léxico anclado para {subcriterion_ref(req_id, sc['id'])}. "
                             f"Candidatos de RECUPERACIÓN (no evidencia validada): {cand_list}. "
                             f"A revisión humana. {COVERAGE_STATEMENT}")

            if not isinstance(page, int) or page < 1:
                continue
            prov = FindingProvenance(
                document_id=document_id, extraction_version=extraction_version,
                run_id=run_id, agent_id="regulatory_tier1",
                subcriterion_ref=subcriterion_ref(req_id, sc["id"]),
                adjudicator_state="TIER1",
            )
            findings.append(build_finding(
                "RegulatoryFinding", subtype, severity=sev, document=document_id,
                page=page, source_text=src_text, rationale=rationale, confidence=conf,
                machine_state=mstate, provenance=prov, requirement_id=req_id,
                regulatory_basis=reg_basis.get(req_id),
                risk=compute_risk(subtype, sev, "MEDIUM").as_dict(),
            ))
    return findings
