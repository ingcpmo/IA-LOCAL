"""SHADOW · CF-6 v2.0 · R2 — loader/validador de
`shadow-cf6-composer-v2.0-relevance-filtered`.

Pipeline REQUIREMENT-CENTRIC de R1 (`factory/regulatory/shadow/
requirement_centric.py`) — NO sustituye ni toca `shadow-cf6-composer-struct-
v2`/`-v3` (siguen firmados, intactos, para el pipeline document×regulación
previo). Este prompt corresponde estrictamente al contrato §3 de
`CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md`: `requirement_text`/
`requirement_intent` como DATO gobernado de entrada (nunca salida del LLM),
`evidence_basis` restringido a `relevant_evidence[]`, `technical_assessment`/
`procedural_responsibility` separados, `gap_or_open_question`,
`assessment_state`, `assessment_rationale`, `confidence`.

Redactado y validado por autorización explícita de Capa 9 (2026-09-04):
"redactar, validar y congelar... No ejecutar R2 todavía. No realizar
llamadas LLM." `status: DRAFT_UNSIGNED` -- firmar requiere un
HUMAN_QUALITY_GATE sobre salidas reales, que esta autorización excluye.

CERO LLM en este módulo. No toca Q-STATE, el renderer determinista, G4d, L2,
el routing, el fingerprint ni human_state. No toca `composer_prompt.py` /
`composer_prompt_v3.py`.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_ID = "composer_structured_v2_0_relevance_filtered"
PROMPT_VERSION = "shadow-cf6-composer-v2.0-relevance-filtered"

ASSESSMENT_STATE_VALUES = ("INCONCLUSIVE", "NOT_ANALYZABLE", "NOT_APPLICABLE")
CONFIDENCE_VALUES = ("LOW", "MEDIUM", "HIGH")
_REQUIRED_KEYS = ("assessment_state", "observed_system_capability", "evidence_basis",
                  "evidence_limitation", "technical_assessment", "procedural_responsibility",
                  "gap_or_open_question", "assessment_rationale", "confidence",
                  "prohibited_conclusion")
_FORBIDDEN_KEYS = ("narrative", "conclusion", "verdict", "compliance", "capa",
                   "excluded_evidence", "candidate_evidence")

_FREE_TEXT_KEYS_TO_SCAN = ("gap_or_open_question", "assessment_rationale",
                          "technical_assessment", "procedural_responsibility",
                          "observed_system_capability")

_COMPLIANCE_RE = re.compile(
    r"\b(cumpl\w*|incumpl\w*|conform\w*|complian\w*|noncomplian\w*|comply)\b", re.IGNORECASE)
_CAPA_RE = re.compile(
    r"\b(acci[oó]n\w*\s+correctiv\w*|medidas?\s+correctiv\w*|corrective\s+action|CAPA|"
    r"remediaci[oó]n|desviaci[oó]n\w*)\b", re.IGNORECASE)
_PAGE_RE = re.compile(
    r"(p[áa]g(?:\.|ina)?s?\.?\s*\d|(?<![\w.])\bp\.\s*\d|\bpage\s*\d)", re.IGNORECASE)
_GAP_CONFIRMED_RE = re.compile(
    r"\b(gap\s+confirmad\w*|hueco\s+confirmad\w*|desviaci[oó]n\s+confirmad\w*)\b", re.IGNORECASE)
_REAL_ABSENCE_AFFIRM_RE = re.compile(
    r"\b(implica|constituye|representa|es|hay|existe|confirma)\s+(una\s+)?ausencia\s+real\b", re.IGNORECASE)


class PromptNotSignedError(RuntimeError):
    """shadow-cf6-composer-v2.0-relevance-filtered sigue DRAFT_UNSIGNED -- una
    ejecución real requiere firma de Capa 9, precedida de un HUMAN_QUALITY_GATE
    sobre salidas reales (que esta fase no genera)."""


@lru_cache(maxsize=2)
def load(prompt_id: str = PROMPT_ID) -> dict:
    p = _PROMPT_DIR / f"{prompt_id}.yaml"
    if not p.exists():
        raise FileNotFoundError(p)
    import yaml as _yaml
    return _yaml.safe_load(p.read_text(encoding="utf-8"))


def is_signed(prompt_id: str = PROMPT_ID) -> bool:
    return str(load(prompt_id).get("status", "")).upper() not in ("DRAFT_UNSIGNED", "")


def assert_signed(prompt_id: str = PROMPT_ID) -> None:
    if not is_signed(prompt_id):
        raise PromptNotSignedError(
            f"{prompt_id}: DRAFT_UNSIGNED. Ninguna ejecución (R2.2) puede usarlo sin firma "
            f"de Capa 9, precedida de HUMAN_QUALITY_GATE sobre salidas reales.")


def temperature(prompt_id: str = PROMPT_ID) -> float:
    return float(load(prompt_id).get("temperature", 0.0))


def prompt_path(prompt_id: str = PROMPT_ID) -> Path:
    return _PROMPT_DIR / f"{prompt_id}.yaml"


def prompt_sha256(prompt_id: str = PROMPT_ID) -> str:
    return hashlib.sha256(prompt_path(prompt_id).read_bytes()).hexdigest()


def few_shot(prompt_id: str = PROMPT_ID) -> list:
    fs = load(prompt_id).get("few_shot") or []
    return [fs] if isinstance(fs, dict) else list(fs)


def has_few_shot(prompt_id: str = PROMPT_ID) -> bool:
    return len(few_shot(prompt_id)) >= 1


def render(prompt_id: str = PROMPT_ID, **fields) -> str:
    p = load(prompt_id)
    fields.setdefault("few_shot_block", "")
    system = (p.get("system") or "").strip()
    user = (p.get("user_template") or "").format(**fields).strip()
    return f"{system}\n\n{user}"


# ── validador estructural (NO toca Q-STATE) ───────────────────────────────

def normalize_evidence_basis(obj: dict) -> dict:
    """Devuelve `obj` con `evidence_basis` deduplicado por `quote` textual."""
    out = dict(obj)
    seen: set[str] = set()
    kept = []
    for it in obj.get("evidence_basis") or []:
        q = (it.get("quote") or "").strip() if isinstance(it, dict) else None
        if q is None:
            kept.append(it)
            continue
        if q in seen:
            continue
        seen.add(q)
        kept.append(it)
    out["evidence_basis"] = kept
    return out


def validate_structure_contract(obj, *, allowed_evidence_basis_ids: list[str] | None = None,
                                input_has_pages: bool = False) -> list[str]:
    """Validación ESTRUCTURAL (sin L2 / sin Q-STATE). Lista vacía = ok.

    `allowed_evidence_basis_ids`: la lista de `finding_record_id` de
    `relevant_evidence[]` (R1) -- CRÍTICO: `evidence_basis` solo puede
    referenciar estos ids. Un id fuera de esta lista significa que el LLM
    citó evidencia excluida (o inventada) -- rechazo estructural, no
    interpretación.
    """
    allowed = set(allowed_evidence_basis_ids or [])
    v: list[str] = []
    if not isinstance(obj, dict):
        return ["salida del Composer no es un objeto JSON"]

    missing = [k for k in _REQUIRED_KEYS if k not in obj]
    if missing:
        v.append(f"faltan claves obligatorias: {missing}")
    forbidden = [k for k in obj if k.lower() in _FORBIDDEN_KEYS]
    if forbidden:
        v.append(f"claves prohibidas presentes: {forbidden}")

    if obj.get("assessment_state") not in ASSESSMENT_STATE_VALUES:
        v.append(f"assessment_state {obj.get('assessment_state')!r} no ∈ {ASSESSMENT_STATE_VALUES}")
    if obj.get("confidence") not in CONFIDENCE_VALUES:
        v.append(f"confidence {obj.get('confidence')!r} no ∈ {CONFIDENCE_VALUES}")
    if str(obj.get("prohibited_conclusion")).upper() != "NONE":
        v.append(f"prohibited_conclusion != 'NONE': {obj.get('prohibited_conclusion')!r}")

    # evidence_basis ⊆ relevant_evidence (CRITICO: nunca evidencia excluida/inventada)
    eb = obj.get("evidence_basis")
    if not isinstance(eb, list):
        v.append("evidence_basis no es lista")
    else:
        quotes = []
        for i, it in enumerate(eb):
            if not isinstance(it, dict):
                v.append(f"evidence_basis[{i}] no es objeto")
                continue
            rid = str(it.get("finding_record_id") or "").strip()
            if not rid:
                v.append(f"evidence_basis[{i}] sin finding_record_id")
            elif allowed_evidence_basis_ids is not None and rid not in allowed:
                v.append(f"evidence_basis[{i}] finding_record_id {rid!r} "
                         f"∉ relevant_evidence (posible evidencia EXCLUIDA o inventada)")
            q = (it.get("quote") or "").strip()
            if not q:
                v.append(f"evidence_basis[{i}] sin quote")
            else:
                quotes.append(q)
        dups = sorted({q for q in quotes if quotes.count(q) > 1})
        if dups:
            v.append(f"evidence_basis: citas textualmente duplicadas: {[d[:50] for d in dups]}")

    for key in ("evidence_limitation",):
        val = obj.get(key)
        if not isinstance(val, list) or any(not isinstance(x, str) for x in (val or [])):
            v.append(f"{key} debe ser lista de strings")

    # campos de texto libre: mismas prohibiciones de v3 (compliance/CAPA/páginas)
    for key in _FREE_TEXT_KEYS_TO_SCAN:
        text = obj.get(key)
        if not str(text or "").strip():
            v.append(f"{key} vacío")
            continue
        if not isinstance(text, str):
            continue
        if _COMPLIANCE_RE.search(text):
            v.append(f"{key} menciona cumplimiento/conformidad: {_COMPLIANCE_RE.search(text).group(0)!r}")
        if _CAPA_RE.search(text):
            v.append(f"{key} menciona CAPA/acción correctiva/desviación: {_CAPA_RE.search(text).group(0)!r}")
        if not input_has_pages and _PAGE_RE.search(text):
            v.append(f"{key} introduce una página no presente en el input: {_PAGE_RE.search(text).group(0)!r}")

    for i, x in enumerate(obj.get("evidence_limitation") or []):
        if not isinstance(x, str):
            continue
        if _GAP_CONFIRMED_RE.search(x):
            v.append(f"evidence_limitation[{i}] declara un gap/hueco confirmado")
        if _REAL_ABSENCE_AFFIRM_RE.search(x) and not re.search(r"\bno\s+(implica|significa|constituye|representa)\b", x, re.IGNORECASE):
            v.append(f"evidence_limitation[{i}] convierte ausencia documental en ausencia real")
        if _COMPLIANCE_RE.search(x):
            v.append(f"evidence_limitation[{i}] usa cumplimiento/conformidad: {_COMPLIANCE_RE.search(x).group(0)!r}")

    return v


def spec() -> dict:
    p = load()
    return {
        "schema": "SHADOW_CF6_V2_COMPOSER_PROMPT_SPEC/v1",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "pipeline": p.get("pipeline"),
        "status": p.get("status"),
        "is_signed": is_signed(),
        "has_few_shot": has_few_shot(),
        "few_shot_count": len(few_shot()),
        "schema_version": p.get("schema_version"),
        "temperature": temperature(),
        "output": p.get("output"),
        "required_keys": list(_REQUIRED_KEYS),
        "forbidden_keys": list(_FORBIDDEN_KEYS),
        "assessment_state_values": list(ASSESSMENT_STATE_VALUES),
        "confidence_values": list(CONFIDENCE_VALUES),
        "prompt_sha256": prompt_sha256(),
        "corresponds_to_r1_contract": {
            "requirement_text_requirement_intent": "DATO de entrada (decomposition.yaml vía "
                "requirement_centric.requirement_text_and_intent) -- nunca campo de salida del LLM",
            "evidence_basis_restricted_to": "relevant_evidence[] (requirement_centric."
                "build_relevance_filtered_context) -- validate_structure_contract rechaza "
                "cualquier finding_record_id fuera de esa lista",
            "technical_assessment_procedural_responsibility": "campos separados (diseño §3/§8, "
                "punto 8 de la revisión)",
            "gap_or_open_question": "generaliza reviewer_action (v2/v3)",
            "assessment_state": "mismos 3 valores que regulatory_state (v2/v3), renombrado",
        },
        "llm_calls": 0,
        "note": "DRAFT_UNSIGNED. Congelado (hash fijado), no firmado. NO ejecutar R2.2 con esto "
                "hasta firma de Capa 9 (requiere HUMAN_QUALITY_GATE sobre salidas reales).",
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(spec(), indent=1, ensure_ascii=False))
