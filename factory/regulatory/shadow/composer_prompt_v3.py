"""SHADOW · CF-6 v1.2 · CF6-2 (corrección) — loader/validador de shadow-cf6-composer-struct-v3.

SUSTITUYE a `shadow-cf6-composer-struct-v2` (firmado, tag cf6-G2) — NO lo modifica.
Añade SOLO las reglas explícitas derivadas del HUMAN_QUALITY_GATE / diagnóstico de
CF6-2.5:

  technical_findings  ⊆ allowed_technical_findings (lista determinista); nunca
                      section_type / regulatory_state / REGULATORY_INCONCLUSIVE;
                      [] si no hay subtypes técnicos reales.
  reviewer_action     solo verificación; sin cumplimiento/"cumple"/CAPA/acción
                      correctiva/desviación/remediación; sin páginas (el input no
                      entrega páginas); sin hechos nuevos no sustentados por L2.
  evidence_observed   solo finding_record_id permitidos; quote = subcadena exacta;
                      SIN citas textualmente duplicadas.
  evidence_limitation lenguaje neutro; sin "gap confirmado"; sin convertir ausencia
                      documental en ausencia real; sin cumplimiento/incumplimiento.

NO toca Q-STATE, el renderer determinista, G4d, L2, el routing, el fingerprint ni
human_state. CERO LLM. `status: DRAFT_UNSIGNED` — fail-closed hasta firma de Capa 9.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_ID = "composer_structured_v3"
PROMPT_VERSION = "shadow-cf6-composer-struct-v3"
SUPERSEDES = "shadow-cf6-composer-struct-v2"

SECTION_TYPE_VALUES = ("REGULATORY", "FUNCTIONAL_TRACEABILITY", "TECHNICAL", "CROSS_DOMAIN")
REGULATORY_STATE_VALUES = ("INCONCLUSIVE", "NOT_ANALYZABLE", "NOT_APPLICABLE")
_REQUIRED_KEYS = ("section_type", "regulatory_state", "evidence_observed", "evidence_limitation",
                  "technical_findings", "reviewer_action", "prohibited_conclusion")
_FORBIDDEN_KEYS = ("narrative", "assessment", "conclusion", "verdict", "compliance", "capa")

_REGULATORY_FINDING_CLASSES = ("RegulatoryFinding",)
_REGULATORY_SUBTYPES = ("REGULATORY_INCONCLUSIVE",)
_TECH_FINDING_FORBIDDEN = set(SECTION_TYPE_VALUES) | set(REGULATORY_STATE_VALUES) | set(_REGULATORY_SUBTYPES)

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
    """shadow-cf6-composer-struct-v3 sigue DRAFT_UNSIGNED — requiere firma de Capa 9."""


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
            f"{prompt_id}: DRAFT_UNSIGNED. Un nuevo CF6-2.5 / CF6-3 no puede usarlo. "
            f"Requiere firma de Capa 9 (Cesar) y congelación de la evidencia propose→"
            f"human_confirmed en su propio tag.")


def temperature(prompt_id: str = PROMPT_ID) -> float:
    return float(load(prompt_id).get("temperature", 0.0))


def prompt_path(prompt_id: str = PROMPT_ID) -> Path:
    return _PROMPT_DIR / f"{prompt_id}.yaml"


def prompt_sha256(prompt_id: str = PROMPT_ID) -> str:
    return hashlib.sha256(prompt_path(prompt_id).read_bytes()).hexdigest()


# ── lista determinista allowed_technical_findings ─────────────────────

def allowed_technical_findings(section: dict, l2_by_rid: dict) -> list[str]:
    """Subtypes técnicos REALES de la sección: distinct `subtype` de findings cuyo
    finding_class NO es regulatorio y cuyo subtype NO es REGULATORY_INCONCLUSIVE."""
    rids = section.get("finding_record_ids") or [e["finding_record_id"] for e in section.get("entries", [])]
    out: set[str] = set()
    for rid in rids:
        f = l2_by_rid.get(rid) or {}
        cls = f.get("class") or f.get("finding_class")
        st = f.get("subtype")
        if not st:
            continue
        if cls in _REGULATORY_FINDING_CLASSES or st in _REGULATORY_SUBTYPES:
            continue
        out.add(st)
    return sorted(out)


# ── few-shot (lista) + render ────────────────────────────────────────

def _render_one_shot(fs: dict) -> str:
    ic = fs.get("input_context", {})
    eo = fs.get("expected_output", {})
    L = [f"EJEMPLO ({fs.get('based_on','')}):",
         f"  ENTRADA: documento {ic.get('document')} · regulación {ic.get('regulation')} · "
         f"section_type {ic.get('section_type')} · regulatory_state {ic.get('regulatory_state')} · "
         f"allowed_technical_findings {ic.get('allowed_technical_findings')}"]
    for e in ic.get("entries", []):
        L.append(f"    - {e}")
    for rid, q in (ic.get("anchored_quotes") or {}).items():
        L.append(f"    cita anclada {rid}: {q!r}")
    L.append("  SALIDA JSON ESPERADA:")
    L.append("  " + json.dumps(eo, ensure_ascii=False, indent=2).replace("\n", "\n  "))
    return "\n".join(L)


def _render_few_shot(p: dict) -> str:
    fs = p.get("few_shot")
    if not fs:
        return ""
    if isinstance(fs, dict):
        fs = [fs]
    return "\n\n".join(_render_one_shot(x) for x in fs)


def few_shot(prompt_id: str = PROMPT_ID) -> list:
    fs = load(prompt_id).get("few_shot") or []
    return [fs] if isinstance(fs, dict) else list(fs)


def has_few_shot(prompt_id: str = PROMPT_ID) -> bool:
    return len(few_shot(prompt_id)) >= 1


def render(prompt_id: str = PROMPT_ID, **fields) -> str:
    p = load(prompt_id)
    atf = fields.get("allowed_technical_findings")
    if isinstance(atf, (list, tuple)):
        fields["allowed_technical_findings"] = json.dumps(list(atf), ensure_ascii=False)
    fields.setdefault("few_shot_block", _render_few_shot(p))
    system = (p.get("system") or "").strip()
    user = (p.get("user_template") or "").format(**fields).strip()
    return f"{system}\n\n{user}"


# ── validador estructural v3 (NO toca Q-STATE) ───────────────────────

def normalize_evidence_observed(obj: dict) -> dict:
    """Devuelve `obj` con `evidence_observed` deduplicado por `quote` textualmente
    idéntica (conserva la primera aparición)."""
    out = dict(obj)
    seen: set[str] = set()
    kept = []
    for it in obj.get("evidence_observed") or []:
        q = (it.get("quote") or "").strip() if isinstance(it, dict) else None
        if q is None:
            kept.append(it)
            continue
        if q in seen:
            continue
        seen.add(q)
        kept.append(it)
    out["evidence_observed"] = kept
    return out


def validate_structure_contract(obj, *, allowed_technical_findings: list[str] | None = None) -> list[str]:
    """Validación ESTRUCTURAL v3 (sin L2 / sin Q-STATE). Lista vacía = ok."""
    allowed = set(allowed_technical_findings or [])
    v: list[str] = []
    if not isinstance(obj, dict):
        return ["salida del Composer no es un objeto JSON"]

    missing = [k for k in _REQUIRED_KEYS if k not in obj]
    if missing:
        v.append(f"faltan claves obligatorias: {missing}")
    forbidden = [k for k in obj if k.lower() in _FORBIDDEN_KEYS]
    if forbidden:
        v.append(f"claves prohibidas presentes: {forbidden}")

    if obj.get("section_type") not in SECTION_TYPE_VALUES:
        v.append(f"section_type {obj.get('section_type')!r} no ∈ {SECTION_TYPE_VALUES}")
    if obj.get("regulatory_state") not in REGULATORY_STATE_VALUES:
        v.append(f"regulatory_state {obj.get('regulatory_state')!r} no ∈ {REGULATORY_STATE_VALUES}")
    if str(obj.get("prohibited_conclusion")).upper() != "NONE":
        v.append(f"prohibited_conclusion != 'NONE': {obj.get('prohibited_conclusion')!r}")

    # evidence_observed
    eo = obj.get("evidence_observed")
    if not isinstance(eo, list):
        v.append("evidence_observed no es lista")
    else:
        quotes = []
        for i, it in enumerate(eo):
            if not isinstance(it, dict):
                v.append(f"evidence_observed[{i}] no es objeto")
                continue
            if not str(it.get("finding_record_id") or "").strip():
                v.append(f"evidence_observed[{i}] sin finding_record_id")
            q = (it.get("quote") or "").strip()
            if not q:
                v.append(f"evidence_observed[{i}] sin quote")
            else:
                quotes.append(q)
        dups = sorted({q for q in quotes if quotes.count(q) > 1})
        if dups:
            v.append(f"evidence_observed: citas textualmente duplicadas: {[d[:50] for d in dups]}")

    # listas de strings
    for key in ("evidence_limitation", "technical_findings"):
        val = obj.get(key)
        if not isinstance(val, list) or any(not isinstance(x, str) for x in (val or [])):
            v.append(f"{key} debe ser lista de strings")

    # technical_findings ⊆ allowed
    tf = obj.get("technical_findings")
    if isinstance(tf, list):
        for x in tf:
            if not isinstance(x, str):
                continue
            xs = x.strip()
            if xs in _TECH_FINDING_FORBIDDEN:
                v.append(f"technical_findings contiene un valor prohibido "
                         f"(section_type/regulatory_state/subtype regulatorio): {xs!r}")
            elif allowed_technical_findings is not None and xs not in allowed:
                v.append(f"technical_findings {xs!r} ∉ allowed_technical_findings {sorted(allowed)}")
        if allowed_technical_findings is not None and not allowed and tf:
            v.append(f"technical_findings debe ser [] (allowed_technical_findings vacío); trae {tf}")

    # reviewer_action
    ra = obj.get("reviewer_action")
    if not str(ra or "").strip():
        v.append("reviewer_action vacío")
    elif isinstance(ra, str):
        if _COMPLIANCE_RE.search(ra):
            v.append(f"reviewer_action menciona cumplimiento/conformidad: "
                     f"{_COMPLIANCE_RE.search(ra).group(0)!r}")
        if _CAPA_RE.search(ra):
            v.append(f"reviewer_action menciona CAPA/acción correctiva/desviación: "
                     f"{_CAPA_RE.search(ra).group(0)!r}")
        if _PAGE_RE.search(ra):
            v.append(f"reviewer_action introduce una página no presente en el input: "
                     f"{_PAGE_RE.search(ra).group(0)!r}")

    # evidence_limitation
    for i, x in enumerate(obj.get("evidence_limitation") or []):
        if not isinstance(x, str):
            continue
        if _GAP_CONFIRMED_RE.search(x):
            v.append(f"evidence_limitation[{i}] declara un gap/hueco confirmado")
        if _REAL_ABSENCE_AFFIRM_RE.search(x) and not re.search(r"\bno\s+(implica|significa|constituye|representa)\b", x, re.IGNORECASE):
            v.append(f"evidence_limitation[{i}] convierte ausencia documental en ausencia real")
        if _COMPLIANCE_RE.search(x):
            v.append(f"evidence_limitation[{i}] usa cumplimiento/conformidad: "
                     f"{_COMPLIANCE_RE.search(x).group(0)!r}")

    return v


def spec() -> dict:
    p = load()
    return {
        "schema": "SHADOW_CF6_COMPOSER_PROMPT_V3_SPEC/v1",
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "supersedes": SUPERSEDES,
        "status": p.get("status"),
        "is_signed": is_signed(),
        "has_few_shot": has_few_shot(),
        "few_shot_count": len(few_shot()),
        "schema_version": p.get("schema_version"),
        "temperature": temperature(),
        "output": p.get("output"),
        "required_keys": list(_REQUIRED_KEYS),
        "forbidden_keys": list(_FORBIDDEN_KEYS),
        "prompt_sha256": prompt_sha256(),
        "new_rules": [
            "technical_findings ⊆ allowed_technical_findings (lista determinista)",
            "technical_findings nunca = section_type / regulatory_state / REGULATORY_INCONCLUSIVE",
            "technical_findings = [] si allowed_technical_findings vacío",
            "reviewer_action sin cumplimiento/'cumple'/comply/compliant",
            "reviewer_action sin CAPA/acción correctiva/desviación/remediación",
            "reviewer_action sin páginas ni referencias documentales fuera del input",
            "evidence_observed deduplicado por quote textual",
            "evidence_limitation neutro: sin gap confirmado, sin ausencia real, sin cumplimiento",
        ],
        "llm_calls": 0,
        "note": "DRAFT_UNSIGNED. Pendiente firma de Capa 9. NO ejecutar CF6-2.5/CF6-3 aún.",
    }


def propose_record(*, proposed_by_id: str = "Capa 8 (Claude Code)",
                   test_results: dict | None = None,
                   correction_reason: str | None = None) -> dict:
    import time
    p = load()
    return {
        "schema": "SHADOW_CF6_2_CORRECTION_PROMPT_PROPOSE/v1",
        "action": "propose",
        "decision_origin": "agent_proposed",
        "written_to_ledger": False,
        "submit_via": "firma de Capa 9 sobre el YAML + evidencia propose→human_confirmed congelada en tag propio",
        "NEW_PROMPT_VERSION": PROMPT_VERSION,
        "OLD_PROMPT_VERSION": SUPERSEDES,
        "prompt_path": "factory/regulatory/shadow/prompts/composer_structured_v3.yaml",
        "prompt_sha256": prompt_sha256(),
        "status_at_propose": p.get("status"),
        "schema_version": p.get("schema_version"),
        "few_shot_count": len(few_shot()),
        "few_shot_based_on": [x.get("based_on") for x in few_shot()],
        "CORRECTION_REASON": correction_reason or (
            "HUMAN_QUALITY_GATE / diagnóstico de CF6-2.5: el prompt v2 no daba reglas "
            "explícitas para technical_findings (volcó section_type / REGULATORY_INCONCLUSIVE "
            "en 5/7 secciones), para páginas en reviewer_action (2 páginas fabricadas), ni "
            "para deduplicación de evidencia (citas repetidas ×3 y ×4). v3 añade SOLO esas "
            "reglas + `allowed_technical_findings` determinista + 2 few-shots (TECHNICAL, "
            "FUNCTIONAL_TRACEABILITY). No toca arquitectura, Q-STATE, renderer, G4d, L2, "
            "routing, fingerprint ni human_state."),
        "does_not_touch": ["arquitectura", "Q-STATE", "renderer determinista", "G4d", "L2",
                           "routing", "FINDINGS_FINGERPRINT", "human_state",
                           "composer_structured_v2.yaml (firmado)", "tags previos"],
        "TEST_RESULTS": test_results or "PENDIENTE (ver test_shadow_composer_prompt_v3.py)",
        "invariants": {
            "LLM_CALLS": 0, "G4D_CALLS": 0, "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
        "proposed_by_id": proposed_by_id,
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "awaiting": {"action": "human_confirmed", "authority": "Capa 9 (Cesar)",
                     "note": "NO firmar aquí. NO ejecutar nuevo CF6-2.5 ni CF6-3."},
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "propose":
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
            "docs_plan/shadow_llm/CF6/CF6_2_CORRECTION_PROPOSE_shadow-cf6-composer-struct-v3.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        rec = propose_record()
        out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        print("WROTE", out)
    else:
        print(json.dumps(spec(), indent=1, ensure_ascii=False))
