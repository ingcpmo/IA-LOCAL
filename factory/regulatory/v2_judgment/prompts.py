"""Carga y render de los 3 prompts BORRADOR de juicio V2 (B4).

prompts/v2_draft/{step_a_neutral_description, step_b_criterion_mapping,
critic}.yaml -- `status: DRAFT_UNSIGNED`. `assert_signed()` falla cerrado
si alguno no está firmado: B4b (corrida real) lo llama; B4a (tests con
LLM mockeado) no.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_DRAFT_DIR = (Path(__file__).resolve().parents[1].parent
              / "engines" / "gmpai_integrity" / "prompts" / "v2_draft")

STEP_A = "step_a_neutral_description"
STEP_B = "step_b_criterion_mapping"
CRITIC = "critic"


class PromptNotSignedError(RuntimeError):
    """Un prompt de juicio V2 sigue en DRAFT_UNSIGNED. Ninguna corrida
    real (B4b) puede usarlo -- requiere firma de Capa 9."""


@lru_cache(maxsize=8)
def load_prompt(prompt_id: str) -> dict:
    path = _DRAFT_DIR / f"{prompt_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    return _yaml.safe_load(path.read_text(encoding="utf-8"))


def is_signed(prompt_id: str) -> bool:
    return str(load_prompt(prompt_id).get("status", "")).upper() not in ("DRAFT_UNSIGNED", "")


def assert_all_signed() -> None:
    unsigned = [p for p in (STEP_A, STEP_B, CRITIC) if not is_signed(p)]
    if unsigned:
        raise PromptNotSignedError(
            f"prompts de juicio V2 sin firmar: {unsigned}. B4b no puede correr "
            f"(ver docs_plan/PROPUESTA_PROMPTS_JUICIO_V2_B4.md).")


def render(prompt_id: str, **fields) -> str:
    p = load_prompt(prompt_id)
    system = p.get("system", "").strip()
    user = p.get("user_template", "").format(**fields).strip()
    return f"{system}\n\n{user}"


def temperature(prompt_id: str) -> float:
    return float(load_prompt(prompt_id).get("temperature", 0.0))
