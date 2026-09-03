"""SHADOW · CF-6 v1.2 — Gate de estado semántico + render determinista del Composer.

Implementa las piezas SIN LLM de CF-6 v1.2 (`docs_plan/CF6_v1_1_REDISENO_COMPOSER.md`
+ precisiones v1.2):

  1. infer_section_type()      — clasificación 100% determinista de cada sección
                                 del esqueleto G3.1 en
                                 { REGULATORY | FUNCTIONAL_TRACEABILITY | TECHNICAL |
                                   CROSS_DOMAIN } + si tiene componente regulatorio.
  2. expected_regulatory_state() — estado regulatorio forzado por L2
                                 { INCONCLUSIVE | NOT_ANALYZABLE | NOT_APPLICABLE }.
  3. normalize_g4d()           — capa determinista de normalización de la
                                 representación de G4d (§5). G4d NO se re-ejecuta.
  4. verify_qstate()           — verificador Q-STATE-1..6, fail-closed. Reusa el
                                 anclaje de cita de G2 (`verifier`). Cualquier check
                                 no evaluable -> RECHAZO.
  5. render_section()          — plantilla fija por section_type × regulatory_state.
                                 CERO texto libre, byte-reproducible. Es el
                                 PUNTO DE NO-RETORNO: no hay LLM después de Q-STATE.
  6. blacklist_scan()          — red de seguridad léxica Q1..Q5 sobre el render.
  7. safe_mode_section()       — modo determinista seguro (fallback §3.5).
  8. compose_section()         — orquestador: Q-STATE -> render -> blacklist ; a
                                 modo seguro si algo rechaza.
  9. measure_v1_baseline()     — mide la narrativa v1 (`G4/g4e_composer.jsonl`)
                                 contra el blacklist y las violaciones de estado:
                                 línea base del fallo de CF-6.

CERO LLM · CERO red · determinista · NO muta L2 / human_state / fingerprint.
"""
from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import verifier as _v

# markers de regulación del esqueleto G3.1 (reusados, no redefinidos)
NO_REGULATION = _skel._NO_REGULATION            # "(trazabilidad — sin regulación directa)"
NOT_ANALYZABLE_MARK = _skel._NOT_ANALYZABLE     # "(documento NOT_ANALYZABLE — requiere revisión humana)"

SECTION_TYPES = ("REGULATORY", "FUNCTIONAL_TRACEABILITY", "TECHNICAL", "CROSS_DOMAIN")
REGULATORY_STATES = ("INCONCLUSIVE", "NOT_ANALYZABLE", "NOT_APPLICABLE")

CF6_CONTRACT_VERSION = "SHADOW_CF6_COMPOSER_CONTRACT/v1.2"
RENDER_TEMPLATE_VERSION = "cf6-render-det-v1.2"

# ── estados L2 que cuentan como "inconcluso" para Q-STATE-1 ─────────────
_INCONCLUSIVE_MACHINE_STATES = ("MACHINE_INCONCLUSIVE", "INCONCLUSIVE")

# ── tokens de conclusión humana prohibidos en esta fase (human_state == UNREVIEWED) ──
_FORBIDDEN_HUMAN_CONCLUSION = re.compile(
    r"\b(confirmad[oa]s?|compliant|non[-_ ]?compliant|no\s+conforme|conforme\s+a|"
    r"cumple\s+con|no\s+cumple|incumple|incumplimiento\s+de|desviaci[oó]n\s+confirmada|"
    r"hallazgo\s+confirmado|se\s+confirma)\b",
    re.IGNORECASE,
)
_FORBIDDEN_CAPA = re.compile(
    r"\b(acci[oó]n(?:es)?\s+correctivas?|medidas?\s+correctivas?|"
    r"acci[oó]n(?:es)?\s+preventivas?|plan\s+de\s+acci[oó]n\s+correctiv\w*|CAPA)\b",
    re.IGNORECASE,
)


# ─────────────────────────── 1 · section_type ──────────────────────────

def _bucket_set(section: dict) -> set[str]:
    mix = section.get("primary_bucket_mix")
    if isinstance(mix, dict) and mix:
        return set(mix.keys())
    return {e.get("primary_bucket") for e in section.get("entries", [])}


def infer_section_type(section: dict) -> tuple[str, bool]:
    """(section_type, has_regulatory_component) — 100% determinista desde el
    esqueleto G3.1. No consulta ningún modelo."""
    buckets = _bucket_set(section)
    reg = section.get("regulation") or ""

    if reg == NOT_ANALYZABLE_MARK or buckets == {"HUMAN_ONLY"}:
        # documento no analizable por máquina: sección regulatoria pendiente de
        # análisis humano (el estado será NOT_ANALYZABLE vía Q-STATE-3).
        return "REGULATORY", True

    has_reg = ("REGULATORY" in buckets) or (reg not in (NO_REGULATION, NOT_ANALYZABLE_MARK))

    if "REGULATORY" in buckets and ("TECHNICAL" in buckets or "FUNCTIONAL_TRACEABILITY" in buckets):
        return "CROSS_DOMAIN", True
    if buckets == {"REGULATORY"}:
        return "REGULATORY", True
    if buckets == {"FUNCTIONAL_TRACEABILITY"}:
        return "FUNCTIONAL_TRACEABILITY", False
    if buckets == {"TECHNICAL"}:
        return "TECHNICAL", False
    # mezclas sin componente regulatorio explícito
    if "REGULATORY" in buckets:
        return "REGULATORY", True
    if "TECHNICAL" in buckets:
        return "TECHNICAL", has_reg
    return "FUNCTIONAL_TRACEABILITY", has_reg


def _section_docs_not_analyzable(section: dict) -> bool:
    if (section.get("regulation") or "") == NOT_ANALYZABLE_MARK:
        return True
    docs = {section.get("document")} | {e.get("document") for e in section.get("entries", [])}
    return any(d in _skel._x._r._HUMAN_ONLY_DOCUMENTS for d in docs if d)


def expected_regulatory_state(section: dict) -> str:
    """Estado regulatorio forzado por L2 (nunca por el modelo)."""
    if _section_docs_not_analyzable(section):
        return "NOT_ANALYZABLE"
    _st, has_reg = infer_section_type(section)
    return "INCONCLUSIVE" if has_reg else "NOT_APPLICABLE"


# ───────────────────────── 2 · normalización G4d ──────────────────────

_G4D_NORMALISATION = OrderedDict([
    ("CANDIDATE_RANKING_PROVIDED",
     "se recuperaron pasajes potencialmente relevantes que requieren revisión humana"),
    ("NO_USEFUL_CANDIDATE",
     "no se recuperaron pasajes relevantes para este sub-criterio"),
    ("NEEDS_HUMAN_SEARCH",
     "el revisor debe buscar evidencia fuera del paquete recuperado"),
    ("BEHAVIOR_NOT_FOUND_IN_SCOPE",
     "el comportamiento requerido no se localizó en el alcance documental revisado "
     "(no implica ausencia real)"),
    ("BEHAVIOR_LIKELY_PRESENT_PARAPHRASED",
     "el comportamiento requerido parece estar presente de forma parafraseada; requiere "
     "confirmación humana"),
    ("LIKELY_REAL_GAP",
     "la ausencia observada parece un hueco real de trazabilidad; requiere confirmación humana"),
    ("LIKELY_EXTRACTION_LIMIT",
     "la ausencia observada parece un límite de extracción, no un hueco real"),
    ("INDETERMINATE",
     "la señal es indeterminada; requiere revisión humana"),
])


def normalize_g4d(assessment: str | None) -> str:
    """Traduce el `assessment` interno de un experto (G4a/G4c/G4d) a lenguaje
    neutro para el revisor. SIN LLM. G4d NO se re-ejecuta."""
    return _G4D_NORMALISATION.get(
        (assessment or "").strip().upper(),
        "señal sin normalización explícita; revisar el finding directamente",
    )


# ───────────────────────── 3 · verificador Q-STATE ────────────────────

@dataclass
class QStateResult:
    section_id: str
    passed: bool
    section_type: str
    regulatory_state_expected: str
    regulatory_state_declared: str | None
    violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "passed": self.passed,
            "section_type": self.section_type,
            "regulatory_state_expected": self.regulatory_state_expected,
            "regulatory_state_declared": self.regulatory_state_declared,
            "violations": list(self.violations),
        }


_STRUCT_REQUIRED_KEYS = (
    "section_type", "regulatory_state", "evidence_observed", "evidence_limitation",
    "technical_findings", "reviewer_action", "prohibited_conclusion",
)


def _iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def verify_qstate(structured: dict, section: dict, l2_by_rid: dict) -> QStateResult:
    """Q-STATE-1..6, fail-closed. `structured` es el contrato JSON del Composer
    (§3.1). Cualquier check no evaluable -> RECHAZO."""
    sid = section.get("section_id", "?")
    st_type, has_reg = infer_section_type(section)
    exp_state = expected_regulatory_state(section)
    v: list[str] = []

    if not isinstance(structured, dict):
        return QStateResult(sid, False, st_type, exp_state, None,
                            ["estructura ausente o no es objeto"])

    missing = [k for k in _STRUCT_REQUIRED_KEYS if k not in structured]
    if missing:
        v.append(f"contrato incompleto: faltan {missing}")

    declared = structured.get("regulatory_state")
    if declared not in REGULATORY_STATES:
        v.append(f"regulatory_state {declared!r} no ∈ {REGULATORY_STATES}")

    # section_type declarado debe coincidir con la clasificación determinista
    if structured.get("section_type") != st_type:
        v.append(f"section_type declarado {structured.get('section_type')!r} != "
                 f"determinista {st_type!r}")

    section_rids = set(section.get("finding_record_ids")
                       or [e["finding_record_id"] for e in section.get("entries", [])])
    machine_states = {(l2_by_rid.get(r) or {}).get("machine_state") for r in section_rids}
    any_inconclusive = any(m in _INCONCLUSIVE_MACHINE_STATES for m in machine_states)

    # Q-STATE-3 (evaluado primero: NOT_ANALYZABLE domina)
    if exp_state == "NOT_ANALYZABLE":
        if declared != "NOT_ANALYZABLE":
            v.append("Q-STATE-3: documento NOT_ANALYZABLE -> regulatory_state DEBE ser NOT_ANALYZABLE")
    else:
        # Q-STATE-1
        if has_reg and any_inconclusive and declared != "INCONCLUSIVE":
            v.append("Q-STATE-1: sección con componente regulatorio e inconcluso en L2 -> "
                     "regulatory_state DEBE ser INCONCLUSIVE")
        # Q-STATE-2
        if not has_reg and st_type in ("FUNCTIONAL_TRACEABILITY", "TECHNICAL"):
            if declared != "NOT_APPLICABLE":
                v.append("Q-STATE-2: sección funcional/técnica sin componente regulatorio -> "
                         "regulatory_state DEBE ser NOT_APPLICABLE")

    # Q-STATE-4 — human_state == UNREVIEWED (siempre en esta fase)
    for s in _iter_strings({k: structured.get(k) for k in _STRUCT_REQUIRED_KEYS
                            if k != "prohibited_conclusion"}):
        if _FORBIDDEN_HUMAN_CONCLUSION.search(s):
            v.append(f"Q-STATE-4: campo declara conclusión humana no autorizada: {s[:80]!r}")
            break

    # Q-STATE-5 — sin desviación humana confirmada -> sin acción correctiva/CAPA
    ra = structured.get("reviewer_action")
    if isinstance(ra, str) and _FORBIDDEN_CAPA.search(ra):
        v.append("Q-STATE-5: reviewer_action contiene acción correctiva/CAPA (prohibido en esta fase)")

    # prohibited_conclusion debe autodeclararse NONE
    if str(structured.get("prohibited_conclusion")).upper() != "NONE":
        v.append(f"prohibited_conclusion != NONE: {structured.get('prohibited_conclusion')!r}")

    # Q-STATE-6 — cada evidence_observed ancla en la sección L2
    eo = structured.get("evidence_observed")
    if not isinstance(eo, list):
        v.append("Q-STATE-6: evidence_observed ausente o no es lista")
    else:
        for i, item in enumerate(eo):
            if not isinstance(item, dict):
                v.append(f"Q-STATE-6: evidence_observed[{i}] no es objeto")
                continue
            rid = item.get("finding_record_id")
            quote = (item.get("quote") or item.get("anchored_quote") or "").strip()
            if rid not in section_rids:
                v.append(f"Q-STATE-6: evidence_observed[{i}] finding_record_id {rid!r} "
                         f"no pertenece a la sección")
                continue
            f = l2_by_rid.get(rid) or {}
            ev_text = (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""
            if not quote:
                v.append(f"Q-STATE-6: evidence_observed[{i}] cita vacía (fail-closed)")
            elif not ev_text:
                v.append(f"Q-STATE-6: evidence_observed[{i}] sin texto L2 para verificar anclaje "
                         f"(fail-closed)")
            elif not _v._quote_anchors(quote, [ev_text]):
                v.append(f"Q-STATE-6: evidence_observed[{i}] cita NO ancla en L2: {quote[:60]!r}")

    return QStateResult(sid, not v, st_type, exp_state, declared, v)


# ───────────────────────── 4 · render determinista ────────────────────

_STATE_LINE = {
    "INCONCLUSIVE": ("ESTADO REGULATORIO: permanece INCONCLUSIVE. "
                     "No se concluye cumplimiento ni incumplimiento."),
    "NOT_ANALYZABLE": ("ESTADO REGULATORIO: NOT_ANALYZABLE. El documento no es analizable "
                       "por máquina; requiere revisión humana."),
    "NOT_APPLICABLE": ("Esta sección no emite un estado regulatorio; agrupa hallazgos "
                       "deterministas para el revisor."),
}


def _fmt_evidence(evidence_observed: list[dict]) -> list[str]:
    out = []
    for item in evidence_observed or []:
        q = " ".join((item.get("quote") or item.get("anchored_quote") or "").split())
        page = item.get("page")
        if not q:
            continue
        out.append(f'- "{q}"' + (f" (pág. {page})" if page not in (None, "") else ""))
    return out


def _heading(section: dict, section_type: str) -> str:
    doc = section.get("document", "?")
    reg = section.get("regulation", "")
    if section_type == "FUNCTIONAL_TRACEABILITY":
        return f"## {doc} · Trazabilidad (sin regulación directa)"
    if section_type == "TECHNICAL":
        return f"## {doc} · Hallazgos técnicos (sin conclusión regulatoria)"
    return f"## {doc} · {reg}"


def render_section(structured: dict, section: dict) -> str:
    """Plantilla fija por section_type × regulatory_state. CERO texto libre del
    modelo: solo los CAMPOS ya validados se insertan en la forma. Byte-reproducible.

    PUNTO DE NO-RETORNO: no se llama a ningún LLM aquí ni después."""
    st_type = structured["section_type"]
    state = structured["regulatory_state"]
    L: list[str] = [_heading(section, st_type), ""]

    L.append(_STATE_LINE[state])
    L.append("")

    ev = _fmt_evidence(structured.get("evidence_observed"))
    L.append("EVIDENCIA OBSERVADA:")
    L.extend(ev if ev else ["- (sin evidencia anclada listada para esta sección)"])

    lim = [f"- {x}" for x in (structured.get("evidence_limitation") or []) if str(x).strip()]
    if lim:
        L.append("")
        L.append("LIMITACIÓN DE EVIDENCIA:")
        L.extend(lim)

    tech = [f"- {x}" for x in (structured.get("technical_findings") or []) if str(x).strip()]
    if tech:
        L.append("")
        L.append("HALLAZGOS TÉCNICOS RELACIONADOS:" if st_type != "TECHNICAL" else "HALLAZGOS TÉCNICOS:")
        L.extend(tech)

    ra = " ".join((structured.get("reviewer_action") or "").split())
    L.append("")
    L.append(f"ACCIÓN PARA EL REVISOR: {ra or 'revisar directamente los findings L2 de esta sección.'}")
    return "\n".join(L)


# ───────────────────────── 5 · blacklist Q1..Q5 ──────────────────────

_BLACKLIST = OrderedDict([
    ("Q1_compliance_conclusion", re.compile(
        r"(no\s+cumple|incumple|incumplimiento\s+de|no\s+(?:es\s+)?conforme|s[ií]\s+cumple|"
        r"cumple\s+con\s+(?:el|los|la|las)|satisface\s+(?:el|los|las)\s+requisito|"
        r"inconsistencias?\s+en\s+el\s+cumplimiento|"
        r"evidencia\s+.{0,30}?insuficiente\s+para\s+satisfacer)", re.IGNORECASE)),
    ("Q2_corrective_action", _FORBIDDEN_CAPA),
    ("Q3_internal_vocab", re.compile(
        r"(candidate[_\s]rank\w*|ranking\s+de\s+candidatos|CANDIDATE_RANKING_PROVIDED|"
        r"NO_USEFUL_CANDIDATE|NEEDS_HUMAN_SEARCH|BEHAVIOR_(?:NOT_FOUND_IN_SCOPE|LIKELY_PRESENT_PARAPHRASED)|"
        r"LIKELY_(?:REAL_GAP|EXTRACTION_LIMIT)|audit[oó]lico)")),
    ("Q4_record_id_leak", re.compile(r"\brec-[0-9a-f]{8,}\b")),
    ("Q5_machine_token_leak", re.compile(
        r"(MACHINE_INCONCLUSIVE|MACHINE_DEVIATION_CANDIDATE|MACHINE_CONFIRMED|EVIDENCE_NOT_FOUND|"
        r"NARRATIVE_(?:BLOCKED|DRAFTED)|\[\[\s*SHADOW|prohibited_conclusion|\bassessment\b)")),
])


def blacklist_scan(text: str) -> list[dict]:
    """Red de seguridad léxica final sobre el render determinista. Devuelve la
    lista de hits (vacía = limpio)."""
    hits = []
    for rule, rx in _BLACKLIST.items():
        for m in rx.finditer(text or ""):
            hits.append({"rule": rule, "match": m.group(0)})
    return hits


# ───────────────────────── 6 · modo determinista seguro ──────────────

_SAFE_STATE_GLOSS = {
    "INCONCLUSIVE": "permanece INCONCLUSIVE. No se concluye cumplimiento ni incumplimiento.",
    "NOT_ANALYZABLE": "NOT_ANALYZABLE. El documento requiere revisión humana.",
    "NOT_APPLICABLE": "no aplica; la sección no emite estado regulatorio.",
}


def safe_mode_section(section: dict, l2_by_rid: dict) -> str:
    """Fallback §3.5: plantilla conservadora (0 LLM). Declara el estado
    determinista, lista evidencia L2 verbatim, y marca la sección."""
    st_type, _ = infer_section_type(section)
    state = expected_regulatory_state(section)
    L = [_heading(section, st_type), "",
         "[NARRATIVA LLM NO DISPONIBLE — no superó el control]",
         f"ESTADO REGULATORIO: {_SAFE_STATE_GLOSS[state]}", "",
         "EVIDENCIA ANCLADA (L2, verbatim):"]
    rids = section.get("finding_record_ids") or [e["finding_record_id"] for e in section.get("entries", [])]
    listed = 0
    for rid in rids:
        f = l2_by_rid.get(rid) or {}
        q = " ".join(((f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or "").split())
        if not q:
            continue
        page = f.get("page")
        L.append(f'- "{q}"' + (f" (pág. {page})" if page not in (None, "") else ""))
        listed += 1
    if not listed:
        L.append("- (sin cita anclada en L2 para esta sección)")
    L.append("")
    L.append("ACCIÓN PARA EL REVISOR: revisar directamente los findings L2 de esta sección.")
    return "\n".join(L)


# ───────────────────────── 7 · orquestador por sección ───────────────

def compose_section(structured: dict | None, section: dict, l2_by_rid: dict) -> dict:
    """Q-STATE -> render determinista -> blacklist. A modo seguro si algo rechaza.
    `structured` = contrato JSON del Composer, o None (aún sin LLM -> modo seguro)."""
    sid = section.get("section_id", "?")
    if structured is None:
        return {
            "section_id": sid, "mode": "SAFE_MODE", "reason": "no_structured_input",
            "section_type": infer_section_type(section)[0],
            "regulatory_state": expected_regulatory_state(section),
            "qstate": None, "blacklist_hits": [],
            "post_qstate_llm_calls": 0,
            "text": safe_mode_section(section, l2_by_rid),
        }

    q = verify_qstate(structured, section, l2_by_rid)
    if not q.passed:
        return {
            "section_id": sid, "mode": "SAFE_MODE", "reason": "qstate_reject",
            "section_type": q.section_type, "regulatory_state": q.regulatory_state_expected,
            "qstate": q.as_dict(), "blacklist_hits": [],
            "post_qstate_llm_calls": 0,
            "text": safe_mode_section(section, l2_by_rid),
        }

    text = render_section(structured, section)
    hits = blacklist_scan(text)
    if hits:
        return {
            "section_id": sid, "mode": "SAFE_MODE", "reason": "blacklist_reject",
            "section_type": q.section_type, "regulatory_state": q.regulatory_state_expected,
            "qstate": q.as_dict(), "blacklist_hits": hits,
            "post_qstate_llm_calls": 0,
            "text": safe_mode_section(section, l2_by_rid),
        }

    return {
        "section_id": sid, "mode": "RENDERED", "reason": None,
        "section_type": q.section_type, "regulatory_state": structured["regulatory_state"],
        "qstate": q.as_dict(), "blacklist_hits": [],
        "post_qstate_llm_calls": 0,
        "text": text,
    }


# ───────────────────────── 8 · línea base v1 ─────────────────────────

# heurística de "violación de estado" para narrativa v1 en prosa libre (no hay
# contrato estructurado en v1): la narrativa v1 no puede afirmar cumplimiento /
# incumplimiento / desviación confirmada ni proponer CAPA.
_V1_STATE_VIOLATION = re.compile(
    r"(no\s+cumple|incumple|incumplimiento|no\s+(?:es\s+)?conforme|s[ií]\s+cumple|"
    r"cumple\s+con|satisface\s+(?:el|los|las)\s+requisito|inconsistencias?\s+en\s+el\s+cumplimiento|"
    r"desviaci[oó]n\s+confirmada|se\s+confirma\s+(?:la\s+)?desviaci[oó]n|"
    r"acci[oó]n(?:es)?\s+correctivas?|medidas?\s+correctivas?|\bCAPA\b)",
    re.IGNORECASE,
)


def measure_v1_baseline(shadow_dir: str | Path) -> dict:
    """Mide la narrativa v1 (`G4/g4e_composer.jsonl`) — línea base del fallo CF-6.
    No re-ejecuta nada, no llama a ningún modelo."""
    SL = Path(shadow_dir)
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    skeleton = json.loads((SL / "G3_1_composer_skeleton.json").read_text(encoding="utf-8"))
    sec_by_id = {s["section_id"]: s for s in skeleton["sections"]}

    g4e_rows = [json.loads(l) for l in
                (SL / "G4" / "g4e_composer.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    section_type_counts: Counter = Counter()
    reg_state_counts: Counter = Counter()
    for s in skeleton["sections"]:
        st, _ = infer_section_type(s)
        section_type_counts[st] += 1
        reg_state_counts[expected_regulatory_state(s)] += 1

    per_section = []
    v1_blacklist_total: Counter = Counter()
    n_state_violation = n_blocked = n_recid_leak = n_double_mark = 0
    for row in g4e_rows:
        sid = row.get("section_id") or row.get("_unit")
        narrative = row.get("narrative") or ""
        blocked = row.get("assessment") == "NARRATIVE_BLOCKED" or not narrative.strip()
        hits = blacklist_scan(narrative)
        for h in hits:
            v1_blacklist_total[h["rule"]] += 1
        state_violation = bool(_V1_STATE_VIOLATION.search(narrative))
        recid_leak = bool(re.search(r"\brec-[0-9a-f]{8,}\b", narrative))
        double_mark = "[[SHADOW" in narrative
        n_blocked += blocked
        n_state_violation += state_violation
        n_recid_leak += recid_leak
        n_double_mark += double_mark
        sec = sec_by_id.get(sid, {})
        per_section.append({
            "section_id": sid,
            "section_type": infer_section_type(sec)[0] if sec else None,
            "regulatory_state_expected": expected_regulatory_state(sec) if sec else None,
            "v1_assessment": row.get("assessment"),
            "v1_blocked": blocked,
            "v1_state_violation": state_violation,
            "v1_record_id_leak": recid_leak,
            "v1_double_shadow_mark": double_mark,
            "v1_blacklist_hits": hits,
        })

    return {
        "schema": "SHADOW_CF6_1_V1_BASELINE/v1",
        "generated_without_llm": True,
        "source": {
            "g4e_composer": str(SL / "G4" / "g4e_composer.jsonl"),
            "skeleton": str(SL / "G3_1_composer_skeleton.json"),
            "l2_findings": str(SL / "FINAL_GMP_CORPUS_FINDINGS.json"),
        },
        "SECTION_TYPE_COUNTS": dict(section_type_counts),
        "REGULATORY_STATE_COUNTS_EXPECTED": dict(reg_state_counts),
        "v1_sections_total": len(g4e_rows),
        "v1_sections_narrative_blocked": n_blocked,
        "v1_sections_with_state_violation": n_state_violation,
        "v1_sections_with_record_id_leak": n_recid_leak,
        "v1_sections_with_double_shadow_mark": n_double_mark,
        "v1_blacklist_hits_by_rule": dict(v1_blacklist_total),
        "post_qstate_llm_calls": 0,
        "per_section": per_section,
    }


# ───────────────────────── contrato machine-readable ─────────────────

def contract_spec() -> dict:
    return {
        "schema": "SHADOW_CF6_COMPOSER_GATE_SPEC/v1.2",
        "contract_version": CF6_CONTRACT_VERSION,
        "render_template_version": RENDER_TEMPLATE_VERSION,
        "section_types": list(SECTION_TYPES),
        "regulatory_states": list(REGULATORY_STATES),
        "structured_contract_keys": list(_STRUCT_REQUIRED_KEYS),
        "qstate_checks": ["Q-STATE-1", "Q-STATE-2", "Q-STATE-3", "Q-STATE-4",
                          "Q-STATE-5", "Q-STATE-6"],
        "blacklist_rules": list(_BLACKLIST.keys()),
        "g4d_normalisation": dict(_G4D_NORMALISATION),
        "post_qstate_llm_calls": 0,
        "g4d_reexecuted": False,
        "notes": ("El LLM emite SOLO la estructura JSON (§3.1). Tras Q-STATE no hay "
                  "ninguna llamada LLM: render y blacklist son 100% deterministas. "
                  "No muta L2 / human_state / FINDINGS_FINGERPRINT."),
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    sd = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs_plan/shadow_llm")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs_plan/shadow_llm/CF6/CF6_1_BASELINE.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    base = measure_v1_baseline(sd)
    out.write_text(json.dumps(base, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out)
    print(json.dumps({k: base[k] for k in (
        "SECTION_TYPE_COUNTS", "REGULATORY_STATE_COUNTS_EXPECTED", "v1_sections_total",
        "v1_sections_narrative_blocked", "v1_sections_with_state_violation",
        "v1_sections_with_record_id_leak", "v1_sections_with_double_shadow_mark",
        "v1_blacklist_hits_by_rule")}, indent=1, ensure_ascii=False))
