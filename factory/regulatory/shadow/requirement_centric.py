"""SHADOW · CF-6 v2.0 · R1 — contrato requirement-centric + filtro de
relevancia aplicado ANTES de cualquier llamada al Composer LLM
(diseño §3, §4, §5 paso 1; `docs_plan/... /CF6_v2_REDISENO_AUDITORIA_
PROFESIONAL.md`, instrucciones de ejecución R1).

Alcance estricto de esta fase: SIN LLM. Este módulo construye la estructura
que R2 (gateada por `PILOT_SCOPE_MATCH_CF6`, NO autorizada a ejecutar todavía
sin verificación explícita de scope) usará para invocar el Composer. Aquí
solo se construye, se mide retroactivamente contra las 7 salidas existentes,
y se verifica en código que `excluded_evidence[]` nunca llega al material que
se envía a un modelo.

No modifica `composer_prompt.py` / `composer_prompt_v3.py` (firmados) ni
`composer_gate.py`. No re-ejecuta G4d. No muta L2 / human_state /
FINDINGS_FINGERPRINT. 0 escrituras a `decomposition.yaml`.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import asdict, dataclass, field

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria,
)
from factory.regulatory.shadow import composer_gate as _cg
from factory.regulatory.shadow import relevance_model as _rel

SCHEMA_CONTRACT = "SHADOW_CF6_V2_REQUIREMENT_CENTRIC_CONTRACT/v1"
SCHEMA_RECORD = "SHADOW_CF6_V2_PROFESSIONAL_ASSESSMENT_RECORD/v1"


# ── 1. Agrupamiento requirement-centric (diseño §3, "la clave primaria pasa
#      a ser requirement_id") ─────────────────────────────────────────────

def group_by_requirement_id(skeleton: dict) -> "OrderedDict[str, list[dict]]":
    """Reagrupa las `entries` del composer skeleton (agrupado hoy por
    document×regulation, ver `composer.py`) usando `requirement_id` como
    clave primaria. `section_type`/`document`/`regulation` de origen se
    conservan por entrada como metadato de agrupación visual (diseño §3),
    NO se pierden. NO muta el skeleton de entrada."""
    out: "OrderedDict[str, list[dict]]" = OrderedDict()
    for section in skeleton["sections"]:
        st_type, _ = _cg.infer_section_type(section)
        for entry in section["entries"]:
            rid = entry.get("requirement_id")
            if not rid:
                continue
            out.setdefault(rid, []).append({
                **entry,
                "origin_section_id": section["section_id"],
                "origin_document": section["document"],
                "origin_regulation": section["regulation"],
                "origin_section_type": st_type,
            })
    return out


def requirement_text_and_intent(requirement_id: str) -> dict:
    """`requirement_text`/`requirement_intent`, SOURCED de `decomposition.yaml`
    (GOBERNADO) -- nunca autoría del LLM (diseño §3). Se agrega el texto de
    todos los sub-criterios del requisito como intención regulatoria conjunta;
    el texto de cada sub-criterio individual sigue disponible vía
    `get_subcriteria` para quien necesite el detalle atómico."""
    subs = get_subcriteria(requirement_id)
    return {
        "requirement_text": " · ".join(sc["text"] for sc in subs),
        "requirement_intent": " · ".join(sc.get("text_en", "") for sc in subs if sc.get("text_en")),
        "subcriteria_ids": [sc["id"] for sc in subs],
    }


# ── 2. Filtro de relevancia aplicado ANTES del contexto que vería un LLM
#      (diseño §4, §5 paso 1) ─────────────────────────────────────────────

def _fmt_entry_line(f: dict, rid: str) -> str:
    return f"- {rid} | {f.get('subtype')} | {f.get('risk_band')} | {f.get('shadow_expert_assessment') or '(sin opinión shadow para este finding)'}"


def build_relevance_filtered_context(section: dict, l2_by_rid: dict, g4: dict) -> tuple[dict, dict]:
    """Construye el contexto de sección que un Composer LLM recibiría, PERO
    solo con `relevant_evidence[]` -- `excluded_evidence[]` se calcula y se
    devuelve por separado (para auditoría), NUNCA dentro de `ctx`.

    Devuelve `(ctx, relevance_record)`. `ctx` es deliberadamente
    estructuralmente idéntico al que construye
    `cf6_pilot_runner_v3._section_context_v3` (mismas claves) para que R2
    pueda sustituir esa función sin cambiar el resto del pipeline -- la
    única diferencia es el filtrado de `rids` por relevancia antes de
    formatear `entries`/`anchored_quotes`/`normalized_opinions`.
    """
    partition = _rel.partition_entries(section["entries"])
    relevant_rids = [i["finding_record_id"] for i in partition["relevant_evidence"]]
    excluded_rids = [i["finding_record_id"] for i in partition["excluded_evidence"]]

    st_type, _ = _cg.infer_section_type(section)
    reg_state = _cg.expected_regulatory_state(section)

    entries_lines, quotes, opinions = [], [], []
    for rid in relevant_rids:          # <- SOLO relevant_evidence, por construcción
        f = l2_by_rid.get(rid) or {}
        op = g4.get(rid) or {}
        if op.get("verifier") == "SHADOW_REJECTED":
            norm = "(opinión shadow rechazada por el verificador de anclaje — no se usa)"
        elif op.get("assessment"):
            norm = _cg.normalize_g4d(op["assessment"])
        else:
            norm = "(sin opinión shadow para este finding)"
        entries_lines.append(f"- {rid} | {f.get('subtype')} | {f.get('risk_band') or (f.get('risk') or {}).get('band')} | {norm}")
        q = " ".join(((f.get('evidence') or {}).get('anchored_quote') or f.get('source_text') or "").split())
        if q:
            quotes.append(f'{rid}: "{q}"')
        opinions.append(f"{rid}: {norm}")

    ctx = {
        "document": section["document"],
        "regulation": section["regulation"],
        "section_type": st_type,
        "regulatory_state": reg_state,
        "entries": "\n".join(entries_lines),
        "anchored_quotes": "\n".join(quotes) or "(sin citas ancladas)",
        "normalized_opinions": "\n".join(opinions) or "(sin opiniones)",
        "relevant_finding_record_ids": relevant_rids,
    }

    relevance_record = {
        "schema": "SHADOW_CF6_V2_RELEVANCE_RECORD/v1",
        "section_id": section["section_id"],
        "relevant_evidence": [
            {"finding_record_id": i["finding_record_id"],
             "relevance_state": i["verdict"].relevance_state,
             "matched_subcriterion_id": i["verdict"].matched_subcriterion_id,
             "n_matched": i["verdict"].n_matched, "weighted_ratio": i["verdict"].weighted_ratio,
             "reason": i["verdict"].reason}
            for i in partition["relevant_evidence"]
        ],
        "excluded_evidence": [
            {"finding_record_id": i["finding_record_id"],
             "relevance_state": i["verdict"].relevance_state,
             "matched_subcriterion_id": i["verdict"].matched_subcriterion_id,
             "n_matched": i["verdict"].n_matched, "weighted_ratio": i["verdict"].weighted_ratio,
             "reason": i["verdict"].reason}
            for i in partition["excluded_evidence"]
        ],
        "fail_closed_empty_relevant": len(relevant_rids) == 0,
    }
    return ctx, relevance_record


def ctx_excludes_excluded_evidence(ctx: dict, relevance_record: dict) -> bool:
    """Verificación de código (no solo declaración): confirma que ningún
    `finding_record_id` de `excluded_evidence[]` aparece en el material que
    se enviaría al LLM (`ctx["entries"]`/`anchored_quotes`/`normalized_
    opinions`). Usada por R1.3 / CRIT-FILTER de las instrucciones de
    ejecución y por `test_requirement_centric.py`."""
    haystack = ctx["entries"] + "\n" + ctx["anchored_quotes"] + "\n" + ctx["normalized_opinions"]
    excluded_rids = [e["finding_record_id"] for e in relevance_record["excluded_evidence"]]
    return "excluded_evidence" not in ctx and not any(rid in haystack for rid in excluded_rids)


# ── 3. ProfessionalAssessmentRecord (diseño §10) — esquema interno,
#      SIN renderer externo, SIN ruta de distribución a cliente ──────────

@dataclass(frozen=True)
class ProfessionalAssessmentRecord:
    requirement_id: str
    regulatory_reference: str
    requirement_intent: str
    system_response: str | None            # observed_capability -- LLM, R2
    evidence_basis: list[str]              # finding_record_id de relevant_evidence
    evidence_limitation: list[str] | None  # LLM, R2
    technical_assessment: str | None       # LLM, R2
    procedural_responsibility: str | None  # LLM, R2
    assessment_state: str                  # determinista hoy (regulatory_state existente)
    required_verification: str | None      # gap_or_open_question -- LLM, R2
    provenance: dict = field(default_factory=dict)
    machine_adjudicated: bool = False      # SIEMPRE False en R1-R3; el Adjudicator (§9) no está implementado


def build_professional_assessment_record(section: dict, requirement_id: str,
                                          relevance_record: dict, *,
                                          fingerprint: str | None = None) -> ProfessionalAssessmentRecord:
    """Construye el registro SIN invocar ningún LLM -- los campos que en el
    diseño final vienen del Composer (§3 pasos 2) quedan `None`/pendientes en
    esta fase (R1). Es una extensión de esquema, no una nueva capacidad de
    modelo (diseño §10: 'se diseña y se construye en esta fase')."""
    meta = requirement_text_and_intent(requirement_id)
    return ProfessionalAssessmentRecord(
        requirement_id=requirement_id,
        regulatory_reference=requirement_id,
        requirement_intent=meta["requirement_intent"] or meta["requirement_text"],
        system_response=None,
        evidence_basis=[e["finding_record_id"] for e in relevance_record["relevant_evidence"]],
        evidence_limitation=None,
        technical_assessment=None,
        procedural_responsibility=None,
        assessment_state=_cg.expected_regulatory_state(section),
        required_verification=None,
        provenance={
            "section_id": section["section_id"],
            "document": section["document"],
            "findings_fingerprint": fingerprint,
            "relevance_record_schema": relevance_record["schema"],
            "decomposition_version_used": "1.1",
        },
        machine_adjudicated=False,
    )


def record_to_dict(rec: ProfessionalAssessmentRecord) -> dict:
    d = asdict(rec)
    d["schema"] = SCHEMA_RECORD
    return d


if __name__ == "__main__":  # pragma: no cover
    from pathlib import Path

    from factory.regulatory.shadow import composer as _skel

    SL = Path("docs_plan/shadow_llm")
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    skeleton = _skel.build_composer_skeleton(findings)

    sec = next(s for s in skeleton["sections"] if s["section_id"] == "sec-0016")
    ctx, rel = build_relevance_filtered_context(sec, l2_by_rid, {})
    print("EXCLUDED_EVIDENCE_NEVER_SENT_TO_LLM:", ctx_excludes_excluded_evidence(ctx, rel))
    print(json.dumps(rel, indent=1, ensure_ascii=False))
