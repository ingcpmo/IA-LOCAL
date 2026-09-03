"""SHADOW · CF-6 v1.2 · CF6-2 — carga/render/firma del nuevo composer_prompt_version.

El Composer (LLM) emite SOLO la estructura JSON del contrato semántico controlado
(CF-6 v1.2 §3.1). Este módulo:

  - carga `prompts/composer_structured_v2.yaml` (sin LLM);
  - `is_signed()` / `assert_signed()` — fail-closed: mientras
    `status: DRAFT_UNSIGNED`, ninguna corrida LLM (CF6-2.5 / CF6-3) puede usarlo;
  - `render(**fields)` — arma system + user_template;
  - `validate_structure_contract(obj)` — validación ESTRUCTURAL de la salida del
    modelo (claves, enums, tipos, `prohibited_conclusion == "NONE"`, sin claves
    prohibidas). NO verifica el anclaje contra L2 — eso es `composer_gate.verify_qstate`
    (Q-STATE-1..6).

CERO LLM · CERO red. No muta L2 / human_state / FINDINGS_FINGERPRINT.

ESTADO CF6-2: el prompt se entrega DRAFT_UNSIGNED. La firma de Capa 9 (Cesar) y la
congelación de la evidencia propose→human_confirmed en el tag `cf6-G2` son un paso
gobernado posterior (CF-6 v1.2 §6). CF6-2 NO ejecuta ninguna llamada LLM.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_ID = "composer_structured_v2"
PROMPT_VERSION = "shadow-cf6-composer-struct-v2"

SECTION_TYPE_VALUES = ("REGULATORY", "FUNCTIONAL_TRACEABILITY", "TECHNICAL", "CROSS_DOMAIN")
REGULATORY_STATE_VALUES = ("INCONCLUSIVE", "NOT_ANALYZABLE", "NOT_APPLICABLE")
_REQUIRED_KEYS = (
    "section_type", "regulatory_state", "evidence_observed", "evidence_limitation",
    "technical_findings", "reviewer_action", "prohibited_conclusion",
)
_FORBIDDEN_KEYS = ("narrative", "assessment", "conclusion", "verdict", "compliance", "capa")


class PromptNotSignedError(RuntimeError):
    """El composer_prompt_version sigue en DRAFT_UNSIGNED. Ninguna corrida LLM
    (CF6-2.5 / CF6-3) puede usarlo — requiere firma de Capa 9 congelada en cf6-G2."""


@lru_cache(maxsize=2)
def load(prompt_id: str = PROMPT_ID) -> dict:
    path = _PROMPT_DIR / f"{prompt_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    return _yaml.safe_load(path.read_text(encoding="utf-8"))


def is_signed(prompt_id: str = PROMPT_ID) -> bool:
    return str(load(prompt_id).get("status", "")).upper() not in ("DRAFT_UNSIGNED", "")


def assert_signed(prompt_id: str = PROMPT_ID) -> None:
    if not is_signed(prompt_id):
        raise PromptNotSignedError(
            f"{prompt_id}: status DRAFT_UNSIGNED. CF6-2.5/CF6-3 no pueden correr. "
            f"Requiere firma de Capa 9 (Cesar) y evidencia congelada en el tag cf6-G2 "
            f"(CF-6 v1.2 §6).")


def temperature(prompt_id: str = PROMPT_ID) -> float:
    return float(load(prompt_id).get("temperature", 0.0))


def render(prompt_id: str = PROMPT_ID, **fields) -> str:
    p = load(prompt_id)
    system = (p.get("system") or "").strip()
    user = (p.get("user_template") or "").format(**fields).strip()
    return f"{system}\n\n{user}"


def validate_structure_contract(obj) -> list[str]:
    """Validación ESTRUCTURAL de la salida del Composer (sin L2). Lista vacía = ok."""
    v: list[str] = []
    if not isinstance(obj, dict):
        return ["salida del Composer no es un objeto JSON"]

    missing = [k for k in _REQUIRED_KEYS if k not in obj]
    if missing:
        v.append(f"faltan claves obligatorias: {missing}")
    forbidden = [k for k in obj if k.lower() in _FORBIDDEN_KEYS]
    if forbidden:
        v.append(f"claves prohibidas presentes (el Composer no emite prosa/veredicto): {forbidden}")

    if obj.get("section_type") not in SECTION_TYPE_VALUES:
        v.append(f"section_type {obj.get('section_type')!r} no ∈ {SECTION_TYPE_VALUES}")
    if obj.get("regulatory_state") not in REGULATORY_STATE_VALUES:
        v.append(f"regulatory_state {obj.get('regulatory_state')!r} no ∈ {REGULATORY_STATE_VALUES}")
    if str(obj.get("prohibited_conclusion")).upper() != "NONE":
        v.append(f"prohibited_conclusion != 'NONE': {obj.get('prohibited_conclusion')!r}")

    eo = obj.get("evidence_observed")
    if not isinstance(eo, list):
        v.append("evidence_observed no es lista")
    else:
        for i, it in enumerate(eo):
            if not isinstance(it, dict):
                v.append(f"evidence_observed[{i}] no es objeto")
                continue
            if not str(it.get("finding_record_id") or "").strip():
                v.append(f"evidence_observed[{i}] sin finding_record_id")
            if not str(it.get("quote") or "").strip():
                v.append(f"evidence_observed[{i}] sin quote")

    for key in ("evidence_limitation", "technical_findings"):
        val = obj.get(key)
        if not isinstance(val, list) or any(not isinstance(x, str) for x in (val or [])):
            v.append(f"{key} debe ser lista de strings")

    if not str(obj.get("reviewer_action") or "").strip():
        v.append("reviewer_action vacío")

    return v


def spec() -> dict:
    p = load()
    return {
        "schema": "SHADOW_CF6_COMPOSER_PROMPT_SPEC/v1",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "status": p.get("status"),
        "is_signed": is_signed(),
        "supersedes": p.get("supersedes"),
        "schema_version": p.get("schema_version"),
        "temperature": temperature(),
        "output": p.get("output"),
        "required_keys": list(_REQUIRED_KEYS),
        "forbidden_keys": list(_FORBIDDEN_KEYS),
        "section_type_values": list(SECTION_TYPE_VALUES),
        "regulatory_state_values": list(REGULATORY_STATE_VALUES),
        "llm_calls": 0,
        "note": ("CF6-2: prompt entregado DRAFT_UNSIGNED. Firma de Capa 9 + tag cf6-G2 "
                 "pendientes (CF-6 v1.2 §6). El wiring en experts.run_composer es CF6-3, "
                 "tras la firma."),
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(spec(), indent=1, ensure_ascii=False))
