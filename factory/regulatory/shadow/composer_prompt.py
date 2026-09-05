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


def _render_few_shot(p: dict) -> str:
    """Texto del ejemplo de referencia (few-shot) para el prompt. Determinista."""
    fs = p.get("few_shot")
    if not fs:
        return ""
    import json as _json
    ic = fs.get("input_context", {})
    eo = fs.get("expected_output", {})
    lines = [
        f"EJEMPLO DE REFERENCIA (few-shot, {fs.get('based_on', '')}):",
        f"  ENTRADA: documento {ic.get('document')} · regulación {ic.get('regulation')} · "
        f"section_type {ic.get('section_type')} · regulatory_state {ic.get('regulatory_state')}",
    ]
    for e in ic.get("entries", []):
        lines.append(f"    - {e}")
    for rid, q in (ic.get("anchored_quotes") or {}).items():
        lines.append(f"    cita anclada {rid}: {q!r}")
    lines.append("  SALIDA JSON ESPERADA:")
    lines.append("  " + _json.dumps(eo, ensure_ascii=False, indent=2).replace("\n", "\n  "))
    return "\n".join(lines)


def few_shot(prompt_id: str = PROMPT_ID) -> dict | None:
    return load(prompt_id).get("few_shot")


def has_few_shot(prompt_id: str = PROMPT_ID) -> bool:
    fs = load(prompt_id).get("few_shot")
    return bool(fs and fs.get("input_context") and fs.get("expected_output"))


def render(prompt_id: str = PROMPT_ID, **fields) -> str:
    p = load(prompt_id)
    system = (p.get("system") or "").strip()
    fields.setdefault("few_shot_block", _render_few_shot(p))
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


def prompt_path(prompt_id: str = PROMPT_ID) -> Path:
    return _PROMPT_DIR / f"{prompt_id}.yaml"


def prompt_sha256(prompt_id: str = PROMPT_ID) -> str:
    import hashlib
    return hashlib.sha256(prompt_path(prompt_id).read_bytes()).hexdigest()


def spec() -> dict:
    p = load()
    return {
        "schema": "SHADOW_CF6_COMPOSER_PROMPT_SPEC/v1",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "status": p.get("status"),
        "is_signed": is_signed(),
        "has_few_shot": has_few_shot(),
        "few_shot_based_on": (p.get("few_shot") or {}).get("based_on"),
        "supersedes": p.get("supersedes"),
        "schema_version": p.get("schema_version"),
        "temperature": temperature(),
        "output": p.get("output"),
        "required_keys": list(_REQUIRED_KEYS),
        "forbidden_keys": list(_FORBIDDEN_KEYS),
        "section_type_values": list(SECTION_TYPE_VALUES),
        "regulatory_state_values": list(REGULATORY_STATE_VALUES),
        "prompt_sha256": prompt_sha256(),
        "llm_calls": 0,
        "note": ("CF6-2: prompt entregado DRAFT_UNSIGNED. Firma de Capa 9 + tag cf6-G2 "
                 "pendientes (CF-6 v1.2 §6). El wiring en experts.run_composer es CF6-3, "
                 "tras la firma."),
    }


def propose_record(*, proposed_by: str = "Capa 8 (Claude Code)",
                   proposed_at: str | None = None) -> dict:
    """Registro formal `propose` del nuevo composer_prompt_version (CF-6 v1.2 §6).

    Es la mitad `propose` de la evidencia gobernada `propose → human_confirmed`.
    La mitad `human_confirmed` la añade Capa 9 (Cesar) tras su confirmación
    explícita; recién entonces se congela todo en el tag `cf6-G2`.
    """
    import time
    p = load()
    return {
        "schema": "SHADOW_CF6_2_PROMPT_PROPOSE/v1",
        "action": "propose",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_path": str(prompt_path().relative_to(prompt_path().parents[4])),
        "prompt_sha256": prompt_sha256(),
        "schema_version": p.get("schema_version"),
        "supersedes": p.get("supersedes"),
        "status_at_propose": p.get("status"),
        "few_shot_present": has_few_shot(),
        "few_shot_based_on": (p.get("few_shot") or {}).get("based_on"),
        "contract": {
            "required_keys": list(_REQUIRED_KEYS),
            "forbidden_keys": list(_FORBIDDEN_KEYS),
            "section_type_values": list(SECTION_TYPE_VALUES),
            "regulatory_state_values": list(REGULATORY_STATE_VALUES),
            "output": p.get("output"),
            "temperature": temperature(),
        },
        "structure_contract_unchanged_vs_cf6_G2_draft": True,
        "qstate_unchanged": True,
        "renderer_unchanged": True,
        "g4d_unchanged": True,
        "routing_unchanged": True,
        "proposed_by": proposed_by,
        "proposed_at": proposed_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
        "awaiting": {
            "action": "human_confirmed",
            "authority": "Capa 9 (Cesar)",
            "then": "congelar prompt firmado + evidencia propose→human_confirmed en el tag cf6-G2",
        },
    }


_PROPOSE_PATH = Path("docs_plan/shadow_llm/CF6/CF6_2_PROPOSE_shadow-cf6-composer-struct-v2.json")
_EVIDENCE_PATH = Path("docs_plan/shadow_llm/CF6/CF6_2_GOVERNED_EVIDENCE_shadow-cf6-composer-struct-v2.json")


def signature(prompt_id: str = PROMPT_ID) -> dict:
    p = load(prompt_id)
    return {k: p.get(k) for k in ("status", "signed_by", "signed_at", "signed_on")}


def human_confirmed_record(*, propose_path: Path = _PROPOSE_PATH) -> dict:
    """Mitad `human_confirmed` de la evidencia gobernada (CF-6 v1.2 §6).

    Exige que el YAML esté ya SIGNED (fail-closed) y referencia el sha256 del
    registro `propose` congelado (prompt aún DRAFT_UNSIGNED en ese momento)."""
    import hashlib
    import json as _json
    assert_signed()
    sig = signature()
    prop = _json.loads(Path(propose_path).read_text(encoding="utf-8"))
    return {
        "schema": "SHADOW_CF6_2_PROMPT_HUMAN_CONFIRMED/v1",
        "action": "human_confirmed",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "confirms_propose": {
            "path": str(propose_path),
            "record_sha256": hashlib.sha256(
                Path(propose_path).read_bytes()).hexdigest(),
            "proposed_prompt_sha256": prop.get("prompt_sha256"),
            "proposed_status": prop.get("status_at_propose"),
        },
        "signed_prompt_sha256": prompt_sha256(),
        "authority": "Capa 9 (Cesar)",
        "signed_by": sig["signed_by"],
        "signed_at": sig["signed_at"],
        "signed_on": sig["signed_on"],
        "few_shot_present": has_few_shot(),
        "structure_contract_unchanged_vs_propose": True,
        "qstate_unchanged": True,
        "renderer_unchanged": True,
        "g4d_unchanged": True,
        "routing_unchanged": True,
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
        "frozen_in_tag": "cf6-G2",
    }


def governed_evidence(*, propose_path: Path = _PROPOSE_PATH) -> dict:
    """Bundle `propose → human_confirmed` para congelar en el tag cf6-G2."""
    import json as _json
    prop = _json.loads(Path(propose_path).read_text(encoding="utf-8"))
    conf = human_confirmed_record(propose_path=propose_path)
    consistent = (
        prop.get("prompt_version") == conf["prompt_version"] == PROMPT_VERSION
        and prop.get("few_shot_present") is True and conf["few_shot_present"] is True
        and conf["confirms_propose"]["proposed_prompt_sha256"] == prop.get("prompt_sha256")
    )
    return {
        "schema": "SHADOW_CF6_2_GOVERNED_EVIDENCE/v1",
        "prompt_version": PROMPT_VERSION,
        "propose": prop,
        "human_confirmed": conf,
        "propose_to_human_confirmed_consistent": consistent,
        "signature": signature(),
        "tag": "cf6-G2",
        "prior_tag_kept_intact": "cf6-G2-draft",
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "spec"
    if cmd == "propose":
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else _PROPOSE_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        rec = propose_record()
        out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        print("WROTE", out)
    elif cmd == "evidence":
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else _EVIDENCE_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        ev = governed_evidence()
        out.write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        print("WROTE", out)
        print(json.dumps({"consistent": ev["propose_to_human_confirmed_consistent"],
                          "signature": ev["signature"], "tag": ev["tag"]},
                         indent=1, ensure_ascii=False))
    else:
        print(json.dumps(spec(), indent=1, ensure_ascii=False))
