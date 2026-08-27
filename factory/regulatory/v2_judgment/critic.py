"""Critic -- segunda lectura adversarial (B4).

Llama al provider con el prompt `critic` y parsea el JSON
{assessment, reason}. El Critic SOLO degrada -- si su salida no es
parseable o el assessment no es válido, devuelve CANNOT_CONFIRM
(fail-closed hacia la duda, nunca hacia AGREE).

B4a: el provider se pasa MOCKEADO en los tests. Cero llamadas reales.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from factory.engines.gmpai_integrity.model_provider import ModelProvider
from factory.regulatory.v2_judgment import prompts
from factory.regulatory.v2_judgment.adjudicator import (
    CRITIC_AGREE, CRITIC_CANNOT_CONFIRM, CRITIC_DISAGREE, CRITIC_VALUES,
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class CriticResult:
    assessment: str            # AGREE | DISAGREE | CANNOT_CONFIRM
    reason: str
    raw: str
    parse_ok: bool


def _extract_json(raw: str) -> dict | None:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def review(subcriterion_text: str, claim_source_text: str, hunter_verdict: str, *,
           provider: ModelProvider) -> CriticResult:
    prompt = prompts.render(
        prompts.CRITIC,
        subcriterion_text=subcriterion_text,
        claim_source_text=claim_source_text,
        hunter_verdict=hunter_verdict,
    )
    resp = provider.generate(prompt)
    raw = (resp or {}).get("response", "") if isinstance(resp, dict) else str(resp)
    parsed = _extract_json(raw)
    if not parsed:
        return CriticResult(CRITIC_CANNOT_CONFIRM, "critic_output_unparseable", raw, False)
    assessment = str(parsed.get("assessment", "")).upper()
    if assessment not in CRITIC_VALUES:
        return CriticResult(CRITIC_CANNOT_CONFIRM,
                            f"critic_invalid_assessment:{assessment!r}", raw, False)
    return CriticResult(assessment, str(parsed.get("reason", ""))[:400], raw, True)
