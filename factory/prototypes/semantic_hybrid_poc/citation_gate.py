"""Gate de verificacion de citas (R5) -- control anti-alucinacion PRIMARIO, determinista.
Reutiliza los primitivos REALES del proyecto (solo lectura, no se modifican):
  factory.regulatory.candidate_validity.is_literally_anchored
  factory.regulatory.evidence_verifier.match_citation  (ternario, umbral 0.93)

FASE 2, aislado. Incorpora los hallazgos del bake-off 2026-09-01:
  H-1: distingue CONFIRMS_ABSENCE (el modelo afirma ausencia en cada elemento, sin
       inventar citas -> coincide con el finding determinista) de INDETERMINATE
       (el modelo no pudo producir evidencia verificable).
  H-2: SOLO `is_literally_anchored` cuenta como verificada. Un match difuso >=0.93
       NO se marca verificado -> se reporta como near_match y se descarta.
  H-3: un `verdict` PRESENT / CONTRADICTORY SIN cita literal verificada se degrada
       a UNCLEAR (R5: sin cita literal no puede afirmarse presencia).
"""
from __future__ import annotations

from factory.regulatory.candidate_validity import is_literally_anchored
from factory.regulatory.evidence_verifier import match_citation

MATCH_THRESHOLD = 0.93          # el que ya usa evidence_verifier (solo para señalar near_match)
VERIFICATION_RATE_FLOOR = 0.80  # < esto -> assessment INDETERMINATE (semantic_mode param)

_POSITIVE_VERDICTS = ("PRESENT", "CONTRADICTORY")


def verify_quote(quote: str, scope_texts: dict[str, str]) -> dict:
    """quote contra cada `source_text` del contexto (por section_id).
    Devuelve {verified, method, score, matched_section, offset, near_match}.
    H-2: `verified` es True EXCLUSIVAMENTE por coincidencia literal
    (`is_literally_anchored`). Un match difuso >=0.93 -> verified=False,
    near_match=True. NO usa ningun modelo."""
    quote = (quote or "").strip()
    if not quote:
        return {"verified": False, "method": "empty", "score": 0.0,
                "matched_section": None, "offset": None, "near_match": False}
    best = {"verified": False, "method": "not_found", "score": 0.0,
            "matched_section": None, "offset": None, "near_match": False}
    for sid, text in scope_texts.items():
        text = text or ""
        if is_literally_anchored(quote, text):
            off = text.find(quote)
            return {"verified": True, "method": "literal", "score": 1.0,
                    "matched_section": sid, "offset": off if off >= 0 else None,
                    "near_match": False}
        kind, score = match_citation(quote, text)
        if score > best["score"]:
            best = {"verified": False,                       # H-2: difuso NUNCA es verificado
                    "method": kind, "score": round(score, 4),
                    "matched_section": None, "offset": None,
                    "near_match": score >= MATCH_THRESHOLD}
    return best


def apply_gate(payload: dict, scope_texts: dict[str, str]) -> dict:
    """Aplica R5 sobre un payload SCTA ya validado por schema.

    - cada cita se verifica (solo literal); la no verificada -> se descarta el
      elemento (supporting_quote=None).
    - H-3: verdict PRESENT/CONTRADICTORY sin cita literal verificada -> UNCLEAR.
    - quote_verification_rate = verificadas / emitidas (None si no se emitio ninguna).
    - rate < floor -> INDETERMINATE.
    - H-1: emitidas == 0 y TODOS los elementos ABSENT -> CONFIRMS_ABSENCE / UNSUPPORTED.
      cualquier otra combinacion con emitidas == 0 o rate insuficiente -> INDETERMINATE.

    Devuelve: elements_gated, grounded_quotes, quotes_emitted, quotes_verified,
    quote_verification_rate, fabricated_quotes[], near_matches, elements_forced_unclear,
    assessment_status, semantic_coverage.
    """
    emitted = 0
    verified = 0
    near_matches = 0
    forced_unclear = 0
    fabricated: list[dict] = []
    grounded: list[dict] = []
    elements_out: list[dict] = []

    for el in payload.get("required_elements", []):
        q = (el.get("supporting_quote") or "").strip()
        new_el = dict(el)
        verified_here = False
        if q:
            emitted += 1
            res = verify_quote(q, scope_texts)
            new_el["quote_match_method"] = res["method"]
            new_el["quote_match_score"] = res["score"]
            new_el["quote_near_match"] = res["near_match"]
            new_el["quote_matched_section"] = res["matched_section"]
            new_el["quote_offset"] = res["offset"]
            new_el["quote_verified"] = res["verified"]
            if res["verified"]:
                verified += 1
                verified_here = True
                grounded.append({"quote": q, "offset": res["offset"],
                                 "section": res["matched_section"],
                                 "for_element": el.get("element_id")})
            else:
                if res["near_match"]:
                    near_matches += 1
                fabricated.append({"quote": q, "for_element": el.get("element_id"),
                                   "score": res["score"], "method": res["method"],
                                   "near_match": res["near_match"]})
                new_el["supporting_quote"] = None          # R5: cita no anclada se descarta
        else:
            new_el["quote_verified"] = None

        # H-3: sin cita literal verificada no puede afirmarse presencia
        if not verified_here and new_el.get("verdict") in _POSITIVE_VERDICTS:
            new_el["verdict_original"] = new_el.get("verdict")
            new_el["verdict"] = "UNCLEAR"
            forced_unclear += 1
        elements_out.append(new_el)

    for coll in ("contradictory_evidence", "supporting_evidence"):
        for item in payload.get(coll, []):
            q = (item.get("quote") or "").strip()
            if not q:
                continue
            emitted += 1
            res = verify_quote(q, scope_texts)
            if res["verified"]:
                verified += 1
                grounded.append({"quote": q, "offset": res["offset"],
                                 "section": res["matched_section"], "for_element": coll})
            else:
                if res["near_match"]:
                    near_matches += 1
                fabricated.append({"quote": q, "for_element": coll,
                                   "score": res["score"], "method": res["method"],
                                   "near_match": res["near_match"]})

    rate = round(verified / emitted, 4) if emitted else None
    rate_ok = rate is not None and rate >= VERIFICATION_RATE_FLOOR
    verdicts = [e.get("verdict") for e in elements_out]

    if rate_ok and emitted > 0:
        status = "COMPLETED"
        coverage = payload.get("semantic_coverage", "INDETERMINATE")
    elif emitted == 0 and verdicts and all(v == "ABSENT" for v in verdicts):
        status = "CONFIRMS_ABSENCE"          # H-1: coincide con el finding, sin citas inventadas
        coverage = "UNSUPPORTED"
    else:
        status = "INDETERMINATE"
        coverage = "INDETERMINATE"

    return {
        "elements_gated": elements_out,
        "grounded_quotes": grounded,
        "quotes_emitted": emitted,
        "quotes_verified": verified,
        "quote_verification_rate": rate,
        "fabricated_quotes": fabricated,
        "near_matches": near_matches,
        "elements_forced_unclear": forced_unclear,
        "assessment_status": status,
        "semantic_coverage": coverage,
    }
