"""SHADOW · G4 — agentes expertos LLM (interpretación, no adjudicación).

Ejecuta los 5 sub-agentes de G4 conforme al diseño v1.1, con LLM REAL vía
`ModelProvider` (configurable, `LLM_PROVIDER = LOCAL`). Cada salida:

  - es una envoltura de OPINIÓN L3 conforme al contrato de G2 (`contracts.py`);
  - pasa el verificador fail-closed de G2 (`verifier.verify_expert_envelope`)
    ANTES de entrar al reporte;
  - vive SOLO bajo `docs_plan/shadow_llm/G4/`;
  - NO muta L2 / `human_state` / `related_finding_ids`;
  - NO declara cumplimiento / aprobación / CAPA / release (enums de G2 sin
    esos tokens; el verificador rechaza cualquier envoltura que los lleve).

Reutilización selectiva de `v2_judgment` (evaluación de G2): se toma
`ModelProvider` + `ollama_client.generate` + `_extract_json`; se DESCARTA la
maquinaria de adjudicación (`evaluate_bundle`, `adjudicator`, prompts de
juicio). Prompts de interpretación nuevos, marcados SHADOW / NO GOBERNADO.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field

from factory.engines.gmpai_integrity.model_provider import ModelProvider, OllamaProvider
from factory.regulatory.shadow import contracts as _c
from factory.regulatory.shadow import verifier as _v

PROMPT_VERSION = "shadow-g4-interp-v1"          # NO GOBERNADO — capa L3/L4
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_SYS = ("Eres un ASISTENTE de interpretación para un revisor GMP humano. NUNCA declaras "
        "cumplimiento, aprobación, cierre de CAPA ni liberación de lote. NUNCA conviertes "
        "'inconcluso' en 'observado'. Solo asistes: explicas y priorizas. Respondes SOLO JSON.")

_PROMPTS = {
 "TECHNICAL": (
  "Regla de completitud gobernada. TEMA presente en el documento; se busca si el "
  "COMPORTAMIENTO REQUERIDO está (aunque sea parafraseado) en el pasaje.\n"
  "REGLA/FUENTE: {basis}\nCONTEXTO L2 (rationale determinista): {rationale}\n"
  "PASAJE ANCLA (cita literal del documento): \"\"\"{quote}\"\"\"\n\n"
  "Devuelve JSON: {{\"assessment\": uno de "
  "[\"BEHAVIOR_LIKELY_PRESENT_PARAPHRASED\",\"BEHAVIOR_NOT_FOUND_IN_SCOPE\",\"INDETERMINATE\"], "
  "\"rationale\": <=400 chars, \"cited_quote\": subcadena EXACTA del pasaje ancla que sustente tu "
  "lectura (o \"\"), \"confidence\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}}"),
 "FUNCTIONAL_TRACEABILITY": (
  "Hallazgo de trazabilidad: el grafo determinista NO encontró una arista "
  "({edge}). ¿Es un HUECO REAL de trazabilidad o un LÍMITE DE EXTRACCIÓN (el id existe "
  "pero la arista no se trazó)?\nCONTEXTO L2: {rationale}\n"
  "PASAJE ANCLA: \"\"\"{quote}\"\"\"\n\n"
  "Devuelve JSON: {{\"assessment\": uno de "
  "[\"LIKELY_REAL_GAP\",\"LIKELY_EXTRACTION_LIMIT\",\"INDETERMINATE\"], "
  "\"rationale\": <=400 chars, \"cited_quote\": subcadena EXACTA del pasaje ancla (o \"\"), "
  "\"confidence\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}}"),
 "REGULATORY": (
  "TRIAGE (NO juicio de cumplimiento). El motor determinista NO ancló eco léxico para el "
  "sub-criterio y entregó candidatos de RECUPERACIÓN. Ordénalos por utilidad para que un "
  "REVISOR HUMANO verifique el sub-criterio. NUNCA digas que cumple ni que está observado.\n"
  "SUB-CRITERIO: {subcriterion}\nCANDIDATOS (claim_id :: texto):\n{candidates}\n\n"
  "Devuelve JSON: {{\"assessment\": uno de "
  "[\"CANDIDATE_RANKING_PROVIDED\",\"NO_USEFUL_CANDIDATE\",\"NEEDS_HUMAN_SEARCH\"], "
  "\"ranked_candidate_claim_ids\": [claim_id...] mejor primero (vacío si NO_USEFUL_CANDIDATE), "
  "\"rationale\": <=400 chars, \"cited_quote\": texto EXACTO del candidato mejor situado (o \"\"), "
  "\"confidence\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}}"),
 "CROSS_DOMAIN": (
  "Reconciliación cross-domain. Un hallazgo TÉCNICO afirma un gap concreto sobre la regla "
  "{regs}; el motor regulatorio la marcó INCONCLUSIVE en el MISMO documento. ¿Son señales "
  "COHERENTES o hay DESACUERDO que exige revisión humana?\n"
  "OPINIÓN TÉCNICA (shadow, ya verificada): {tech_op}\n"
  "PASAJE TÉCNICO ANCLA: \"\"\"{quote}\"\"\"\n"
  "CONTRAPARTES REGULATORIAS (INCONCLUSIVE): {reg_ctx}\n\n"
  "Devuelve JSON: {{\"assessment\": uno de "
  "[\"RECONCILED_CONSISTENT\",\"DISAGREEMENT_PERSISTS\",\"INDETERMINATE\"], "
  "\"rationale\": <=400 chars, \"cited_quote\": subcadena EXACTA del pasaje técnico ancla (o \"\"), "
  "\"confidence\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}}"),
 "COMPOSER": (
  "Redacta el PÁRRAFO NARRATIVO [SHADOW / NO GOBERNADO] de una sección (documento × "
  "regulación) de un informe GMP asistido. Cada afirmación debe referirse a un "
  "finding_record_id de la lista. NO declaras cumplimiento/aprobación. Es un borrador para "
  "revisión humana.\nSECCIÓN: documento {doc}, regulación {reg}\n"
  "ENTRADAS (finding_record_id | subtype | risk | opinión shadow verificada):\n{entries}\n\n"
  "Devuelve JSON: {{\"narrative\": texto <=1200 chars que cite finding_record_id explícitos, "
  "\"assessment\": \"NARRATIVE_DRAFTED\"|\"NARRATIVE_BLOCKED\", "
  "\"cited_finding_record_ids\": [rec-...], \"confidence\": \"LOW\"|\"MEDIUM\"|\"HIGH\"}}"),
}


def make_provider(kind: str = "LOCAL") -> ModelProvider:
    if kind != "LOCAL":
        raise ValueError("G0-G5: LLM_PROVIDER = LOCAL (unico permitido)")
    return OllamaProvider()


@dataclass
class CallLog:
    calls: list = field(default_factory=list)

    def record(self, *, expert, unit, prompt_id, ok, secs, raw_len, error=None):
        self.calls.append({"call_id": "llm-" + uuid.uuid4().hex[:12], "expert": expert,
                           "unit": unit, "prompt_id": prompt_id, "ok": ok,
                           "seconds": round(secs, 2), "raw_len": raw_len, "error": error})

    @property
    def n(self):
        return len(self.calls)


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


def _call(provider, prompt_id, prompt, *, expert, unit, clog: CallLog):
    full = _SYS + "\n\n" + prompt
    t0 = time.time()
    try:
        resp = provider.generate(full)
        raw = _resp_text(resp)
        clog.record(expert=expert, unit=unit, prompt_id=prompt_id, ok=True,
                    secs=time.time() - t0, raw_len=len(raw))
        return _extract_json(raw), raw
    except Exception as e:  # noqa: BLE001
        clog.record(expert=expert, unit=unit, prompt_id=prompt_id, ok=False,
                    secs=time.time() - t0, raw_len=0, error=f"{type(e).__name__}: {e}")
        return None, ""


def _model_block(provider):
    try:
        digest = provider.show_digest()
    except Exception:  # noqa: BLE001
        digest = "unavailable"
    return {"provider": "LOCAL", "model_name": provider.model_name, "digest": digest,
            "prompt_id": PROMPT_VERSION, "prompt_version": PROMPT_VERSION}


def _anchor_quote(f):
    return (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""


def _base_envelope(f, expert, assessment, rationale, cited_quote, confidence, provider, extra=None):
    quote = (cited_quote or "").strip() or _anchor_quote(f)[:200]
    env = {
        "schema": "SHADOW_OUTPUT_ENVELOPE/v1", "expert": expert,
        "finding_record_id": f["finding_record_id"], "shadow_layer": "L3",
        "assessment": assessment,
        "rationale": f"{(rationale or '').strip()[:800]} {_c.SHADOW_MARK}",
        "anchored_citations": [{"finding_record_id": f["finding_record_id"], "quote": quote,
                                "page": f.get("page"), "source": _c.CLIENT_EVIDENCE,
                                "source_hash": f.get("source_hash")}],
        "external_reg_references": [],
        "MUST_NOT_CHANGE": dict(_c.must_not_change_block(f)),
        "confidence": confidence if confidence in ("LOW", "MEDIUM", "HIGH") else "LOW",
        "model": _model_block(provider),
        "produced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        env.update(extra)
    return env


def _finalise(env, f, evidence_index=None):
    r = _v.verify_expert_envelope(env, l2_finding=f, evidence_index=evidence_index)
    return {"envelope": env, "verifier": {"status": r.status,
            "structural_violations": r.structural_violations,
            "anchoring_violations": r.anchoring_violations}}


# ── G4a Technical ──────────────────────────────────────────────────────
def run_technical(f, provider, clog):
    p = _PROMPTS["TECHNICAL"].format(basis=f.get("technical_basis") or "",
                                     rationale=(f.get("rationale") or "")[:600],
                                     quote=_anchor_quote(f)[:1200])
    parsed, _ = _call(provider, PROMPT_VERSION, p, expert="TECHNICAL",
                      unit=f["finding_record_id"], clog=clog)
    a = (parsed or {}).get("assessment")
    if a not in _c.ASSESSMENT_VALUES["TECHNICAL"]:
        a = "INDETERMINATE"
    env = _base_envelope(f, "TECHNICAL", a, (parsed or {}).get("rationale", "sin rationale del modelo"),
                         (parsed or {}).get("cited_quote"), (parsed or {}).get("confidence", "LOW"), provider)
    return _finalise(env, f)


# ── G4c Functional / Traceability ─────────────────────────────────────
def run_functional(f, provider, clog):
    gp = f.get("provenance", {}).get("graph_path")
    edge = "arista de trazabilidad"
    if isinstance(gp, list) and len(gp) > 1 and isinstance(gp[1], dict):
        edge = gp[1].get("edge_family_checked") or edge
    p = _PROMPTS["FUNCTIONAL_TRACEABILITY"].format(
        edge=edge, rationale=(f.get("rationale") or "")[:600], quote=_anchor_quote(f)[:1200])
    parsed, _ = _call(provider, PROMPT_VERSION, p, expert="FUNCTIONAL_TRACEABILITY",
                      unit=f["finding_record_id"], clog=clog)
    a = (parsed or {}).get("assessment")
    if a not in _c.ASSESSMENT_VALUES["FUNCTIONAL_TRACEABILITY"]:
        a = "INDETERMINATE"
    env = _base_envelope(f, "FUNCTIONAL_TRACEABILITY", a,
                         (parsed or {}).get("rationale", "sin rationale del modelo"),
                         (parsed or {}).get("cited_quote"), (parsed or {}).get("confidence", "LOW"), provider)
    return _finalise(env, f)


# ── G4d Regulatory triage ────────────────────────────────────────────
def run_regulatory_triage(f, candidate_claims, provider, clog):
    cands = candidate_claims or []
    cand_txt = "\n".join(f"- {c['claim_id']} :: {(c.get('source_text') or '')[:280]}" for c in cands) or "(sin candidatos)"
    sub = f.get("provenance", {}).get("subcriterion_ref") or f.get("requirement") or ""
    p = _PROMPTS["REGULATORY"].format(subcriterion=sub, candidates=cand_txt)
    parsed, _ = _call(provider, PROMPT_VERSION, p, expert="REGULATORY",
                      unit=f["finding_record_id"], clog=clog)
    a = (parsed or {}).get("assessment")
    if a not in _c.ASSESSMENT_VALUES["REGULATORY"]:
        a = "NEEDS_HUMAN_SEARCH"
    ranked = [x for x in (parsed or {}).get("ranked_candidate_claim_ids", [])
              if isinstance(x, str) and any(c["claim_id"] == x for c in cands)]
    cq = (parsed or {}).get("cited_quote") or ""
    # triage nunca convierte INCONCLUSIVE en observed: el finding L2 no se toca (MUST_NOT_CHANGE).
    env = _base_envelope(f, "REGULATORY", a, (parsed or {}).get("rationale", "sin rationale del modelo"),
                         cq, (parsed or {}).get("confidence", "LOW"), provider,
                         extra={"ranked_candidate_claim_ids": ranked})
    ev_index = [{"source_text": c.get("source_text", "")} for c in cands]
    return _finalise(env, f, evidence_index=ev_index)


# ── G4b Cross-domain ─────────────────────────────────────────────────
def run_cross_domain(link, tech_result, reg_results, f_tech, provider, clog):
    tech_op = (tech_result or {}).get("envelope", {}).get("assessment", "n/a")
    reg_ctx = "; ".join(f"{r['finding_record_id']}({r.get('requirement_id','')})"
                        for r in link.get("regulatory_counterparts", []))
    p = _PROMPTS["CROSS_DOMAIN"].format(
        regs=", ".join(link.get("shared_regulations", [])), tech_op=tech_op,
        quote=_anchor_quote(f_tech)[:1000], reg_ctx=reg_ctx or "(ninguna)")
    parsed, _ = _call(provider, PROMPT_VERSION, p, expert="CROSS_DOMAIN",
                      unit=link["link_id"], clog=clog)
    a = (parsed or {}).get("assessment")
    if a not in _c.ASSESSMENT_VALUES["CROSS_DOMAIN"]:
        a = "INDETERMINATE"
    env = _base_envelope(f_tech, "CROSS_DOMAIN", a,
                         (parsed or {}).get("rationale", "sin rationale del modelo"),
                         (parsed or {}).get("cited_quote"), (parsed or {}).get("confidence", "LOW"),
                         provider, extra={"link_id": link["link_id"],
                                          "declared_counterparts": [c["finding_record_id"]
                                                                    for c in link.get("regulatory_counterparts", [])]})
    r = _v.verify_expert_envelope(
        env, l2_finding=f_tech,
        declared_counterparts=[c["finding_record_id"] for c in link.get("regulatory_counterparts", [])])
    return {"envelope": env, "link_id": link["link_id"], "assessment": a,
            "verifier": {"status": r.status, "structural_violations": r.structural_violations,
                         "anchoring_violations": r.anchoring_violations}}


# ── G4e Composer ─────────────────────────────────────────────────────
def run_composer(section, verified_by_rid, provider, clog):
    """⚠ CF-6 v1.2 · CF6-0 — PROTOTIPO. Esta función pide al LLM PROSA LIBRE
    (`narrative`), lo que en v1 elevó `INCONCLUSIVE` a incumplimiento y filtró
    vocabulario interno. En CF-6 v1.2 el Composer emite SOLO estructura JSON,
    verificada por `composer_gate.verify_qstate`, y la prosa se RENDERIZA de forma
    100% determinista (cero LLM tras el gate). No usar esta ruta para salida
    gobernada; se conserva como referencia de la línea base v1 (CF6-1).
    """
    lines = []
    for e in section["entries"]:
        rid = e["finding_record_id"]
        op = verified_by_rid.get(rid)
        op_s = (op or {}).get("assessment", "PENDIENTE/RECHAZADA")
        lines.append(f"- {rid} | {e['subtype']} | {e['risk_band']} | {op_s}")
    p = _PROMPTS["COMPOSER"].format(doc=section["document"], reg=section["regulation"],
                                    entries="\n".join(lines)[:6000])
    parsed, _ = _call(provider, PROMPT_VERSION, p, expert="COMPOSER",
                      unit=section["section_id"], clog=clog)
    narrative = (parsed or {}).get("narrative", "")
    rids_in_section = {e["finding_record_id"] for e in section["entries"]}
    cited = [x for x in (parsed or {}).get("cited_finding_record_ids", []) if x in rids_in_section]
    a = (parsed or {}).get("assessment")
    if a not in _c.ASSESSMENT_VALUES["COMPOSER"]:
        a = "NARRATIVE_BLOCKED"
    if not narrative.strip():
        a = "NARRATIVE_BLOCKED"
    return {
        "section_id": section["section_id"], "document": section["document"],
        "regulation": section["regulation"],
        "narrative": f"[{_c.SHADOW_MARK}] {narrative.strip()}" if narrative.strip() else "",
        "assessment": a, "confidence": (parsed or {}).get("confidence", "LOW"),
        "cited_finding_record_ids": cited,
        "section_finding_record_ids": [e["finding_record_id"] for e in section["entries"]],
        "model": _model_block(provider),
        "produced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
