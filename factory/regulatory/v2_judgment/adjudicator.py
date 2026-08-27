"""Adjudicator determinista (B4) -- FASE 6.1.

Combina Hunter (paso B) + Critic + evidence_verifier con reglas fijas
fail-closed. SIN LLM, sin efectos secundarios. Mismo input -> mismo
estado.

Estados (por candidato de un sub-criterio):
  MACHINE_CONFIRMED      B=SATISFIES ∧ Critic=AGREE ∧ Verifier∈{verified, verified_with_deviation}
  MACHINE_PARTIAL        B=PARTIAL   ∧ Critic≠DISAGREE ∧ Verifier ok
  MACHINE_REJECTED       Verifier=rejected_by_verifier  (cita no ancla / incoherente)
  INCONCLUSIVE           desacuerdo Hunter/Critic, o Verifier=review_required, o B=UNCLEAR,
                         o B∈{SATISFIES,PARTIAL} sin cita anclada
  EVIDENCE_NOT_FOUND     B=NO ∧ Critic∈{AGREE, CANNOT_CONFIRM}   (NUNCA => gap por sí solo)
  CONTRADICTORY_EVIDENCE lo fija el llamador si el grafo (B2) tiene `contradicts`

Un `EVIDENCE_NOT_FOUND` a nivel de sub-criterio se consolida a nivel de
REQUISITO en B5 (con las 4 condiciones de FASE 6.2), nunca aquí.
"""
from __future__ import annotations

from dataclasses import dataclass

# Hunter (paso B)
HUNTER_SATISFIES = "SATISFIES"
HUNTER_PARTIAL = "PARTIAL"
HUNTER_NO = "NO"
HUNTER_UNCLEAR = "UNCLEAR"
HUNTER_VALUES = (HUNTER_SATISFIES, HUNTER_PARTIAL, HUNTER_NO, HUNTER_UNCLEAR)

# Critic
CRITIC_AGREE = "AGREE"
CRITIC_DISAGREE = "DISAGREE"
CRITIC_CANNOT_CONFIRM = "CANNOT_CONFIRM"
CRITIC_VALUES = (CRITIC_AGREE, CRITIC_DISAGREE, CRITIC_CANNOT_CONFIRM)

# Verifier (evidence_verifier.VerificationResult.status)
_VERIFIER_OK = ("verified", "verified_with_deviation")
_VERIFIER_REJECTED = "rejected_by_verifier"
_VERIFIER_REVIEW = "review_required"

# Estados de salida
MACHINE_CONFIRMED = "MACHINE_CONFIRMED"
MACHINE_PARTIAL = "MACHINE_PARTIAL"
MACHINE_REJECTED = "MACHINE_REJECTED"
INCONCLUSIVE = "INCONCLUSIVE"
EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"


@dataclass
class Adjudication:
    state: str
    hunter_verdict: str
    critic_assessment: str | None
    verifier_status: str | None
    evidence_anchored: bool
    reasons: list


def adjudicate(*, hunter_verdict: str, critic_assessment: str | None,
               verifier_status: str | None, evidence_quote_present: bool,
               has_open_contradiction: bool = False) -> Adjudication:
    """`critic_assessment` puede ser None cuando el Critic no se invocó
    (solo se invoca si B∈{SATISFIES,PARTIAL} -- ver judgment_v2)."""
    if hunter_verdict not in HUNTER_VALUES:
        raise ValueError(f"hunter_verdict inválido: {hunter_verdict!r}")
    if critic_assessment is not None and critic_assessment not in CRITIC_VALUES:
        raise ValueError(f"critic_assessment inválido: {critic_assessment!r}")

    reasons: list = []

    if has_open_contradiction:
        return Adjudication(CONTRADICTORY_EVIDENCE, hunter_verdict, critic_assessment,
                            verifier_status, False, ["graph_has_contradicts_edge"])

    # 1. El verificador manda sobre la cita.
    if hunter_verdict in (HUNTER_SATISFIES, HUNTER_PARTIAL):
        if not evidence_quote_present:
            reasons.append("positive_verdict_without_quote")
            return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                                verifier_status, False, reasons)
        if verifier_status == _VERIFIER_REJECTED:
            reasons.append("verifier_rejected_citation")
            return Adjudication(MACHINE_REJECTED, hunter_verdict, critic_assessment,
                                verifier_status, False, reasons)
        anchored = verifier_status in _VERIFIER_OK
        if verifier_status == _VERIFIER_REVIEW or not anchored:
            reasons.append(f"verifier_status={verifier_status}")
            return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                                verifier_status, anchored, reasons)
        # cita anclada. Ahora el Critic.
        if critic_assessment == CRITIC_DISAGREE:
            reasons.append("critic_disagree")
            return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                                verifier_status, True, reasons)
        if critic_assessment == CRITIC_CANNOT_CONFIRM:
            reasons.append("critic_cannot_confirm")
            return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                                verifier_status, True, reasons)
        # Critic AGREE (o None, que no debería pasar para SATISFIES/PARTIAL).
        if critic_assessment != CRITIC_AGREE:
            reasons.append("critic_not_invoked_for_positive")
            return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                                verifier_status, True, reasons)
        if hunter_verdict == HUNTER_SATISFIES:
            reasons.append("hunter_satisfies+critic_agree+verifier_anchored")
            return Adjudication(MACHINE_CONFIRMED, hunter_verdict, critic_assessment,
                                verifier_status, True, reasons)
        reasons.append("hunter_partial+critic_agree+verifier_anchored")
        return Adjudication(MACHINE_PARTIAL, hunter_verdict, critic_assessment,
                            verifier_status, True, reasons)

    # 2. Hunter = UNCLEAR
    if hunter_verdict == HUNTER_UNCLEAR:
        reasons.append("hunter_unclear")
        return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                            verifier_status, False, reasons)

    # 3. Hunter = NO
    if critic_assessment == CRITIC_DISAGREE:
        # el Critic cree que SÍ podría satisfacerse -> no cerramos ausencia
        reasons.append("hunter_no_but_critic_disagree")
        return Adjudication(INCONCLUSIVE, hunter_verdict, critic_assessment,
                            verifier_status, False, reasons)
    reasons.append("hunter_no")
    return Adjudication(EVIDENCE_NOT_FOUND, hunter_verdict, critic_assessment,
                        verifier_status, False, reasons)
