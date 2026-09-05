"""SHADOW · CF-6 v2.0 · R2.2 — regeneración de la muestra CF6-2.5 bajo el
Composer de 4 pasos con Relevance Model (R1) + prompt firmado
`shadow-cf6-composer-v2.0-relevance-filtered`.

Autorizado por Capa 9 (2026-09-04) tras `PILOT_SCOPE_MATCH_CF6 = PASS` (tag
pendiente `cf6-v2-R2`) y firma del prompt (`CF6_v2_R2_REMEDIATION.md`).

Pipeline por sección (diseño §5):
  1. FILTRO DE RELEVANCIA (R1, determinista) — `requirement_centric.
     build_relevance_filtered_context()`. Ya construido, no se toca.
  2. INTERPRETACIÓN (LLM) — UNA sola llamada por sección, sin reintento
     (mismo Fix A que `cf6_pilot_runner_v3`). Recibe SOLO `relevant_evidence[]`.
  3. VERIFICACIÓN DE ESTADO (determinista) — Q-STATE-1..6
     (`composer_gate.verify_qstate`, INTACTO, sin modificar) sobre una vista
     ADAPTADA del contrato R1 a los nombres de campo que Q-STATE ya conoce
     (`_adapt_r1_to_legacy_view`, más abajo) — Q-STATE no se reescribe, se
     reutiliza tal cual sobre datos renombrados.
  4. RENDER (determinista) — `composer_gate.render_section`, igual.

Secciones sin cobertura en `decomposition.yaml` (sec-0026 ANNEX11_7, sin
descomposición; sec-0042, sin regulación/trazabilidad) están FUERA DE
ALCANCE del contrato requirement-centric por construcción -- no se
inventa una descomposición ni se las fuerza al pipeline nuevo. Caen a
SAFE_MODE (`compose_section(None, ...)`, ya existente, fail-closed) con
`reason="out_of_scope_r2_no_decomposition"`.

CERO reintentos · CERO llamadas tras Q-STATE · G4d NO se re-ejecuta · no
muta L2 / human_state / FINDINGS_FINGERPRINT / decomposition.yaml.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    has_decomposition,
)
from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg
from factory.regulatory.shadow import composer_prompt_v2_0_relevance_filtered as _cp
from factory.regulatory.shadow import relevance_model as _rel
from factory.regulatory.shadow import requirement_centric as _rc
from factory.regulatory.shadow.cf6_pilot_runner import _extract_json, _load_g4_opinions, _call_llm

PROMPT_VERSION = _cp.PROMPT_VERSION
_NO_REGULATION = _skel._NO_REGULATION
_NOT_ANALYZABLE = _skel._NOT_ANALYZABLE


def _requirement_id_for(section: dict) -> str | None:
    reg = section.get("regulation") or ""
    if reg in (_NO_REGULATION, _NOT_ANALYZABLE):
        return None
    return reg


def _in_scope_r2(section: dict) -> tuple[bool, str | None]:
    rid = _requirement_id_for(section)
    if rid is None:
        return False, "sin regulación asociada a la sección (trazabilidad / NOT_ANALYZABLE) — "
        "el contrato requirement-centric no aplica"
    if not has_decomposition(rid):
        return False, f"{rid!r} sin descomposición en decomposition.yaml — fuera de alcance de R1/R2"
    return True, None


def _adapt_r1_to_legacy_view(structured: dict, section: dict) -> dict:
    """Traduce el contrato R1 (§3) a las claves que `composer_gate.verify_
    qstate`/`render_section` ya conocen -- NO se modifica Q-STATE ni el
    renderer, se les da una vista con nombres legados de los MISMOS datos.

      assessment_state          -> regulatory_state (mismo valor)
      section_type              -> inyectado determinista (infer_section_type);
                                    R1 NUNCA se lo pide al LLM, así que no hay
                                    riesgo de drift que verificar aquí
      evidence_basis            -> evidence_observed (misma forma: rid+quote)
      evidence_limitation       -> evidence_limitation (sin cambio)
      technical_assessment +
      procedural_responsibility +
      assessment_rationale      -> technical_findings (texto libre, pasan por
                                    el mismo escaneo Q-STATE-4/5 que antes)
      gap_or_open_question      -> reviewer_action
      prohibited_conclusion     -> prohibited_conclusion (sin cambio)
    """
    st_type, _ = _cg.infer_section_type(section)
    tech_free_text = [x for x in (
        structured.get("technical_assessment"), structured.get("procedural_responsibility"),
        structured.get("assessment_rationale")) if str(x or "").strip()]
    return {
        "section_type": st_type,
        "regulatory_state": structured.get("assessment_state"),
        "evidence_observed": [
            {"finding_record_id": e.get("finding_record_id"), "quote": e.get("quote")}
            for e in (structured.get("evidence_basis") or [])
        ],
        "evidence_limitation": structured.get("evidence_limitation") or [],
        "technical_findings": tech_free_text,
        "reviewer_action": structured.get("gap_or_open_question"),
        "prohibited_conclusion": structured.get("prohibited_conclusion"),
        # trazabilidad: se conserva el objeto R1 original para reporte/auditoría
        "_r1_raw": structured,
    }


_REAL_OUT_DIR = "docs_plan/shadow_llm/CF6"
_DRY_RUN_OUT_DIR = "docs_plan/shadow_llm/CF6/_dry_run"


def run_r2(shadow_dir: str | Path = "docs_plan/shadow_llm",
          manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
          *, out_dir: str | Path | None = None,
          dry_run: bool = False) -> dict:
    """`out_dir`: si no se especifica, se elige automáticamente según `dry_run`
    -- `_REAL_OUT_DIR` (artefactos de una corrida real, con LLM) o
    `_DRY_RUN_OUT_DIR` (sub-carpeta separada, NUNCA la misma ruta). Esto es a
    propósito: un `dry_run=True` (p.ej. desde un test) jamás debe poder
    sobrescribir `CF6_v2_R2_RUN.json`/`CF6_v2_R2_B_OUTPUTS.jsonl` de una
    corrida real, sin importar el orden en que se invoquen. Pasar `out_dir`
    explícitamente (p.ej. un `tmp_path` de test) lo respeta siempre, para
    aislamiento total en pruebas."""
    _cp.assert_signed()  # fail-closed
    if out_dir is None:
        out_dir = _DRY_RUN_OUT_DIR if dry_run else _REAL_OUT_DIR
    SL, OUT = Path(shadow_dir), Path(out_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert str(manifest.get("status", "")).upper().startswith("FROZEN"), "SAMPLE_MANIFEST debe estar FROZEN"
    manifest_hash = manifest["sample_manifest_hash"]
    assert manifest_hash.startswith("7422faaf"), f"SAMPLE_MANIFEST_HASH inesperado: {manifest_hash}"
    section_ids = manifest["sections_selected"]

    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    skeleton = _skel.build_composer_skeleton(findings)
    by_id = {s["section_id"]: s for s in skeleton["sections"]}
    g4 = _load_g4_opinions(SL)

    model_name = "dry-run"
    if not dry_run:
        from factory.engines.gmpai_integrity import ollama_client as oc
        model_name = oc.OLLAMA_MODEL

    rows, llm_calls = [], 0
    for sid in section_ids:
        section = by_id[sid]
        in_scope, out_of_scope_reason = _in_scope_r2(section)

        if not in_scope:
            gate = _cg.compose_section(None, section, l2_by_rid)
            rows.append({
                "section_id": sid, "document": section["document"], "regulation": section["regulation"],
                "in_scope_r2": False, "out_of_scope_reason": out_of_scope_reason,
                "requirement_id": None, "relevance_record": None,
                "llm_calls_section": 0, "structure_contract_violations": ["out_of_scope_r2"],
                "mode": gate["mode"], "reason": gate.get("reason"), "qstate": gate.get("qstate"),
                "blacklist_hits": gate.get("blacklist_hits", []), "post_qstate_llm_calls": 0,
                "raw_llm_json": None, "structured_r1": None, "B_text": gate["text"], "llm_seconds": 0.0,
            })
            continue

        requirement_id = _requirement_id_for(section)
        req_meta = _rc.requirement_text_and_intent(requirement_id)
        ctx, relevance_record = _rc.build_relevance_filtered_context(section, l2_by_rid, g4)
        allowed_ids = [i["finding_record_id"] for i in relevance_record["relevant_evidence"]]
        assert _rc.ctx_excludes_excluded_evidence(ctx, relevance_record), \
            f"{sid}: excluded_evidence detectado en el contexto del LLM -- ABORTA (CRIT-FILTER)"

        if not allowed_ids:
            # fail-closed (diseño §4): relevant_evidence vacío -> SAFE_MODE, sin invitar al LLM a especular
            gate = _cg.compose_section(None, section, l2_by_rid)
            rows.append({
                "section_id": sid, "document": section["document"], "regulation": section["regulation"],
                "in_scope_r2": True, "out_of_scope_reason": None,
                "requirement_id": requirement_id, "relevance_record": relevance_record,
                "llm_calls_section": 0, "structure_contract_violations": ["relevant_evidence_empty"],
                "mode": gate["mode"], "reason": "relevant_evidence_empty_fail_closed",
                "qstate": gate.get("qstate"), "blacklist_hits": gate.get("blacklist_hits", []),
                "post_qstate_llm_calls": 0, "raw_llm_json": None, "structured_r1": None,
                "B_text": gate["text"], "llm_seconds": 0.0,
            })
            continue

        prompt = _cp.render(
            requirement_id=requirement_id, regulatory_reference=requirement_id,
            requirement_text=req_meta["requirement_text"], requirement_intent=req_meta["requirement_intent"],
            document=section["document"], origin_section_type=ctx["section_type"],
            assessment_state=ctx["regulatory_state"], entries=ctx["entries"],
            anchored_quotes=ctx["anchored_quotes"], normalized_opinions=ctx["normalized_opinions"],
        )

        structured, raw_llm_obj, secs, calls_this = None, None, 0.0, 0
        struct_violations = ["dry_run: no LLM"] if dry_run else []
        if not dry_run:
            raw, secs, _ = _call_llm(prompt)   # Fix A: UNA sola llamada, sin reintento
            llm_calls += 1
            calls_this += 1
            if llm_calls > 250:
                raise RuntimeError("R2.2 excedió el tope duro CF-6 (250, ADDENDUM -041/-042/-043/-044)")
            raw_llm_obj = _extract_json(raw)
            if raw_llm_obj is None:
                struct_violations = ["salida no es JSON"]
            else:
                normalized = _cp.normalize_evidence_basis(raw_llm_obj)
                struct_violations = _cp.validate_structure_contract(
                    normalized, allowed_evidence_basis_ids=allowed_ids)
                if not struct_violations:
                    structured = normalized
                raw_llm_obj = normalized

        legacy_view = _adapt_r1_to_legacy_view(structured, section) if structured is not None else None
        gate = _cg.compose_section(legacy_view, section, l2_by_rid)

        rows.append({
            "section_id": sid, "document": section["document"], "regulation": section["regulation"],
            "in_scope_r2": True, "out_of_scope_reason": None,
            "requirement_id": requirement_id, "relevance_record": relevance_record,
            "relevant_finding_record_ids": allowed_ids,
            "llm_calls_section": calls_this, "structure_contract_violations": struct_violations,
            "mode": gate["mode"], "reason": gate.get("reason"), "qstate": gate.get("qstate"),
            "blacklist_hits": gate.get("blacklist_hits", []), "post_qstate_llm_calls": 0,
            "raw_llm_json": raw_llm_obj, "structured_r1": structured,
            "B_text": gate["text"], "llm_seconds": secs,
        })

    rendered = sum(1 for r in rows if r["mode"] == "RENDERED")
    safe = sum(1 for r in rows if r["mode"] == "SAFE_MODE")
    out_of_scope = sum(1 for r in rows if not r["in_scope_r2"])

    b_path = OUT / "CF6_v2_R2_B_OUTPUTS.jsonl"
    b_path.write_text("".join(
        json.dumps({k: v for k, v in r.items() if k != "relevance_record"} |
                   ({"relevance_record": {
                       "relevant_evidence": r["relevance_record"]["relevant_evidence"],
                       "excluded_evidence": r["relevance_record"]["excluded_evidence"],
                   }} if r.get("relevance_record") else {}), ensure_ascii=False) + "\n"
        for r in rows), encoding="utf-8")

    # verificación explícita: sec-0016 ya no exhibe el SCOPE_DRIFT (rec-6b0c9965fd2f4e05)
    sec0016 = next((r for r in rows if r["section_id"] == "sec-0016"), None)
    sec0016_scope_drift_absent = None
    if sec0016 is not None:
        bad = "rec-6b0c9965fd2f4e05"
        excluded_rids = {e["finding_record_id"] for e in (sec0016["relevance_record"] or {}).get("excluded_evidence", [])}
        appears_in_output = bad in json.dumps(sec0016.get("structured_r1") or {})
        sec0016_scope_drift_absent = (bad in excluded_rids) and not appears_in_output

    summary = {
        "schema": "SHADOW_CF6_V2_R2_RUN/v1",
        "phase": "R2.2 (regeneración bajo contrato requirement-centric R1)",
        "authorized_by_tag": "cf6-v2-R1 (contrato) + gate PASS (CF6_v2_R2_REMEDIATION.md)",
        "PROMPT_VERSION": PROMPT_VERSION,
        "prompt_signed": _cp.is_signed(),
        "prompt_sha256_frozen_content": _cp._FROZEN_CONTENT_SHA256,
        "model": model_name,
        "SAMPLE_MANIFEST_HASH": manifest_hash,
        "sections": section_ids,
        "LLM_CALLS_TOTAL": llm_calls,
        "LLM_CALLS_BY_SECTION": {r["section_id"]: r["llm_calls_section"] for r in rows},
        "llm_budget_cap_cf6": 250,
        "within_budget": llm_calls <= 250,
        "sections_rendered": rendered, "sections_safe_mode": safe, "sections_out_of_scope_r2": out_of_scope,
        "OUT_OF_SCOPE_SECTIONS": {r["section_id"]: r["out_of_scope_reason"] for r in rows if not r["in_scope_r2"]},
        "STRUCTURE_VALIDATION_BY_SECTION": {r["section_id"]: (r["structure_contract_violations"] or "OK") for r in rows},
        "QSTATE_RESULT_BY_SECTION": {r["section_id"]: ("PASS" if (r["qstate"] or {}).get("passed")
                                     else ((r["qstate"] or {}).get("violations") if r["qstate"] else "n/a (sin estructura)")) for r in rows},
        "BLACKLIST_RESULT_BY_SECTION": {r["section_id"]: (r["blacklist_hits"] or "CLEAN") for r in rows},
        "SAFE_MODE_SECTIONS": [r["section_id"] for r in rows if r["mode"] == "SAFE_MODE"],
        "RELEVANCE_MODEL_BY_SECTION": {
            r["section_id"]: {
                "requirement_id": r["requirement_id"],
                "n_relevant": len(r["relevance_record"]["relevant_evidence"]) if r["relevance_record"] else None,
                "n_excluded": len(r["relevance_record"]["excluded_evidence"]) if r["relevance_record"] else None,
            } for r in rows if r["relevance_record"]
        },
        "SEC_0016_SCOPE_DRIFT_ABSENT": sec0016_scope_drift_absent,
        "sections_rendered_evidence_basis_all_within_relevant": all(
            all(e["finding_record_id"] in (r.get("relevant_finding_record_ids") or [])
                for e in (r["structured_r1"] or {}).get("evidence_basis", []))
            for r in rows if r["mode"] == "RENDERED" and r["structured_r1"]
        ),
        "POST_QSTATE_LLM_CALLS": 0,
        "G4D_CALLS": 0, "g4d_reexecuted": False,
        "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0,
        "b_outputs": str(b_path),
        "human_quality_gate": "PENDIENTE — evaluación humana bidimensional por sección (Capa 9), "
                              "SAFETY/GOVERNANCE + AUDIT QUALITY (diseño §6). Claude Code no evalúa la "
                              "rúbrica ni evidence_relevance_accuracy -- reporta los datos.",
    }
    (OUT / "CF6_v2_R2_RUN.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":  # pragma: no cover
    import sys
    s = run_r2(dry_run=("--dry-run" in sys.argv))
    print(json.dumps({k: s[k] for k in (
        "model", "LLM_CALLS_TOTAL", "sections_rendered", "sections_safe_mode",
        "sections_out_of_scope_r2", "SAFE_MODE_SECTIONS", "OUT_OF_SCOPE_SECTIONS",
        "SEC_0016_SCOPE_DRIFT_ABSENT", "sections_rendered_evidence_basis_all_within_relevant",
        "POST_QSTATE_LLM_CALLS", "within_budget")}, indent=1, ensure_ascii=False))
