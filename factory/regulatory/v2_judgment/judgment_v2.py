"""Orquestador del juicio V2 por EvidenceBundle (B4) -- FASE 6.

Por cada candidato de un `EvidenceBundle` (B3):
  paso A  -> descripción operativa neutra           (provider)
  paso B  -> mapeo al sub-criterio                   (provider, NO ve el pasaje original)
  Verifier -> evidence_verifier.verify_llm_output    (determinista, SIN CAMBIOS)
  Critic  -> solo si B ∈ {SATISFIES, PARTIAL}        (provider)
  Adjudicator -> estado por candidato                (determinista)
Agrega los candidatos -> un `SubcriterionVerdict`.

B4a: `provider` se pasa MOCKEADO en los tests -> CERO llamadas reales.
B4b: corrida real -> `prompts.assert_all_signed()` + PILOT_EXECUTION (no aquí).

La cita citable es SIEMPRE Claim.source_text literal. El paso A nunca es evidencia.
Un `EVIDENCE_NOT_FOUND` a nivel de sub-criterio NO cierra gap -- eso es B5.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from factory.engines.gmpai_integrity.model_provider import ModelProvider
from factory.regulatory.evidence_verifier import load_requirement_terms, verify_llm_output
from factory.regulatory.v2_judgment import critic as _critic
from factory.regulatory.v2_judgment import prompts
from factory.regulatory.v2_judgment.adjudicator import (
    CONTRADICTORY_EVIDENCE, EVIDENCE_NOT_FOUND, HUNTER_NO, HUNTER_PARTIAL,
    HUNTER_SATISFIES, HUNTER_UNCLEAR, HUNTER_VALUES, INCONCLUSIVE,
    MACHINE_CONFIRMED, MACHINE_PARTIAL, MACHINE_REJECTED, adjudicate,
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Prioridad de agregación de candidatos -> veredicto del sub-criterio.
_PRIORITY = [MACHINE_CONFIRMED, MACHINE_PARTIAL, CONTRADICTORY_EVIDENCE,
             INCONCLUSIVE, MACHINE_REJECTED, EVIDENCE_NOT_FOUND]


@dataclass
class CandidateOutcome:
    claim_id: str
    neutral_description: str
    hunter_verdict: str
    hunter_quote: str
    verifier_status: str
    critic_assessment: str | None
    state: str
    reasons: list


@dataclass
class SubcriterionVerdict:
    subcriterion_ref: str
    requirement_id: str
    state: str
    best_claim_id: str | None = None
    best_quote: str | None = None
    best_page: int | None = None
    candidate_outcomes: list = field(default_factory=list)
    calls_made: int = 0


def _resp_text(resp) -> str:
    if isinstance(resp, dict):
        return resp.get("response", "") or ""
    return str(resp or "")


def _extract_json(raw: str) -> dict | None:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def evaluate_bundle(bundle, *, provider: ModelProvider,
                    has_open_contradiction: bool = False) -> SubcriterionVerdict:
    """`bundle`: un EvidenceBundle de B3. `provider`: ModelProvider
    (mockeado en B4a)."""
    verdict = SubcriterionVerdict(
        subcriterion_ref=bundle.subcriterion_ref,
        requirement_id=bundle.requirement_id, state=EVIDENCE_NOT_FOUND,
    )
    if not bundle.candidate_claims:
        verdict.state = INCONCLUSIVE
        verdict.candidate_outcomes = []
        return verdict

    known_ids = {bundle.requirement_id}
    req_terms = load_requirement_terms(bundle.requirement_id)

    for cand in bundle.candidate_claims:
        # ── paso A ────────────────────────────────────────────────────────
        a_prompt = prompts.render(prompts.STEP_A, claims_source_text=cand["source_text"])
        neutral = _resp_text(provider.generate(a_prompt)).strip()
        verdict.calls_made += 1

        # ── paso B (VARIANTE ESTRICTA: solo sub-criterio + descripción
        #    neutra; el modelo NUNCA ve un Claim ni produce una cita) ─────
        b_prompt = prompts.render(
            prompts.STEP_B, subcriterion_text=bundle.subcriterion_text,
            neutral_description=neutral,
        )
        b_parsed = _extract_json(_resp_text(provider.generate(b_prompt)))
        verdict.calls_made += 1
        if not b_parsed:
            verdict.candidate_outcomes.append(CandidateOutcome(
                cand["claim_id"], neutral, HUNTER_UNCLEAR, "", "n/a", None,
                INCONCLUSIVE, ["step_b_unparseable"]))
            continue

        hunter = str(b_parsed.get("verdict", "")).upper()
        if hunter not in HUNTER_VALUES:
            verdict.candidate_outcomes.append(CandidateOutcome(
                cand["claim_id"], neutral, HUNTER_UNCLEAR, "", "n/a", None,
                INCONCLUSIVE, [f"step_b_invalid_verdict:{hunter!r}"]))
            continue

        # ── paso B2 (DETERMINISTA): la evidencia de un veredicto positivo
        #    es el Claim que originó esta descripción neutra. El modelo no
        #    elige ni produce cita -> no puede fabricar ni parafrasear. ──
        cited_claim = cand
        quote = cand["source_text"] if hunter in (HUNTER_SATISFIES, HUNTER_PARTIAL) else ""

        # ── Verifier (determinista, sin cambios) ─────────────────────────
        observation = ("observed" if hunter in (HUNTER_SATISFIES, HUNTER_PARTIAL)
                       else "not_observed_in_chunk")
        vr = verify_llm_output(
            {"requirement_id": bundle.requirement_id,
             "chunk_observation": observation,
             "evidence_quote": quote,
             "evidence_page": cited_claim.get("pagina")},
            {"text": cited_claim["source_text"],
             "page_start": cited_claim.get("pagina"),
             "page_end": cited_claim.get("pagina")},
            known_ids, req_terms,
        )

        # ── Critic (solo para veredictos positivos) ──────────────────────
        critic_assessment = None
        if hunter in (HUNTER_SATISFIES, HUNTER_PARTIAL):
            cr = _critic.review(bundle.subcriterion_text, cited_claim["source_text"],
                                hunter, provider=provider)
            critic_assessment = cr.assessment
            verdict.calls_made += 1

        # ── Adjudicator ─────────────────────────────────────────────────
        adj = adjudicate(
            hunter_verdict=hunter, critic_assessment=critic_assessment,
            verifier_status=vr.status, evidence_quote_present=bool(quote),
            has_open_contradiction=has_open_contradiction,
        )
        outcome = CandidateOutcome(
            claim_id=cited_claim["claim_id"], neutral_description=neutral,
            hunter_verdict=hunter, hunter_quote=quote, verifier_status=vr.status,
            critic_assessment=critic_assessment, state=adj.state, reasons=adj.reasons,
        )
        verdict.candidate_outcomes.append(outcome)
        if adj.state == MACHINE_CONFIRMED:
            verdict.state = MACHINE_CONFIRMED
            verdict.best_claim_id = cited_claim["claim_id"]
            verdict.best_quote = quote
            verdict.best_page = cited_claim.get("pagina")
            return verdict  # confirmado: no hace falta seguir

    # ── agregación ──────────────────────────────────────────────────────
    states = [o.state for o in verdict.candidate_outcomes] or [INCONCLUSIVE]
    for s in _PRIORITY:
        if s in states:
            verdict.state = s
            break
    if verdict.state in (MACHINE_PARTIAL,):
        winner = next(o for o in verdict.candidate_outcomes if o.state == verdict.state)
        wc = next((c for c in bundle.candidate_claims if c["claim_id"] == winner.claim_id), {})
        verdict.best_claim_id = winner.claim_id
        verdict.best_quote = winner.hunter_quote
        verdict.best_page = wc.get("pagina")
    return verdict
