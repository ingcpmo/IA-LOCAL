"""SHADOW · CF-6 v1.2 · CF6-2.5 (v3) — SMALL QUALITY PILOT con shadow-cf6-composer-struct-v3.

Igual que `cf6_pilot_runner` pero:
  - prompt FIRMADO `shadow-cf6-composer-struct-v3` (`composer_prompt_v3`, assert_signed);
  - pasa `allowed_technical_findings` (determinista) al prompt;
  - **Fix A (CF-6 v1.2 §3.1): UNA sola llamada LLM por sección — sin reintento**;
  - **Fix B: orden `normalize_evidence_observed` (dedupe) → `validate_structure_contract`
    v3 (con `technical_findings ⊆ allowed_technical_findings`) → Q-STATE**. La dedup
    corre ANTES de validar, para que el validador vea la estructura ya deduplicada
    (si no, rechaza los duplicados y la dedup nunca actúa);
  - Q-STATE-1..6 SIN CAMBIOS (`composer_gate.verify_qstate`), render determinista,
    blacklist Q1–Q5, modo seguro; CERO LLM tras Q-STATE; G4d NO se re-ejecuta.

Autorizado por el ADDENDUM `PILOT_EXECUTION-2026-039/-040` (human_confirmed, `cesar`,
tag cf6-G2G-r1). Tope duro CF-6: 250 llamadas.

NO sobrescribe los artefactos del piloto v2: escribe `CF6_2_5_v3_*`.
NO decide el HUMAN_QUALITY_GATE. NO muta L2 / human_state / FINDINGS_FINGERPRINT.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg
from factory.regulatory.shadow import composer_prompt_v3 as _cp3
from factory.regulatory.shadow.cf6_pilot_runner import (
    _extract_json, _load_g4_opinions, _anchor, _risk, _call_llm,
)

PILOT_INSTANCE = "PILOT_EXECUTION-2026-040"
PILOT_PROPOSE = "PILOT_EXECUTION-2026-039"
CF6_MAX_CALLS = 250
PROMPT_VERSION = _cp3.PROMPT_VERSION


def _section_context_v3(section: dict, l2_by_rid: dict, g4: dict) -> tuple[dict, list[str]]:
    rids = section.get("finding_record_ids") or [e["finding_record_id"] for e in section["entries"]]
    st_type, _ = _cg.infer_section_type(section)
    reg_state = _cg.expected_regulatory_state(section)
    allowed = _cp3.allowed_technical_findings(section, l2_by_rid)
    entries, quotes, opinions = [], [], []
    for rid in rids:
        f = l2_by_rid.get(rid) or {}
        op = g4.get(rid) or {}
        if op.get("verifier") == "SHADOW_REJECTED":
            norm = "(opinión shadow rechazada por el verificador de anclaje — no se usa)"
        elif op.get("assessment"):
            norm = _cg.normalize_g4d(op["assessment"])
        else:
            norm = "(sin opinión shadow para este finding)"
        entries.append(f"- {rid} | {f.get('subtype')} | {_risk(f)} | {norm}")
        q = " ".join(_anchor(f).split())
        if q:
            quotes.append(f'{rid}: "{q}"')
        opinions.append(f"{rid}: {norm}")
    ctx = {
        "document": section["document"],
        "regulation": section["regulation"],
        "section_type": st_type,
        "regulatory_state": reg_state,
        "allowed_technical_findings": allowed,
        "entries": "\n".join(entries),
        "anchored_quotes": "\n".join(quotes) or "(sin citas ancladas)",
        "normalized_opinions": "\n".join(opinions) or "(sin opiniones)",
    }
    return ctx, allowed


def _dupe_quotes(obj: dict | None) -> list[str]:
    if not isinstance(obj, dict):
        return []
    qs = [(" ".join((it.get("quote") or "").split()))
          for it in (obj.get("evidence_observed") or []) if isinstance(it, dict)]
    return sorted({q for q in qs if q and qs.count(q) > 1})


def run_cf6_2_5_v3(shadow_dir: str | Path = "docs_plan/shadow_llm",
                   manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
                   *, out_dir: str | Path = "docs_plan/shadow_llm/CF6",
                   dry_run: bool = False) -> dict:
    _cp3.assert_signed()
    SL, OUT = Path(shadow_dir), Path(out_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert str(manifest.get("status", "")).upper().startswith("FROZEN"), "SAMPLE_MANIFEST debe estar FROZEN (§4.1)"
    manifest_hash = manifest["sample_manifest_hash"]
    assert manifest_hash.startswith("7422faaf"), f"SAMPLE_MANIFEST_HASH inesperado: {manifest_hash}"
    section_ids = manifest["sections_selected"]

    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    by_id = {s["section_id"]: s for s in _skel.build_composer_skeleton(findings)["sections"]}
    g4 = _load_g4_opinions(SL)

    model_name = "dry-run"
    if not dry_run:
        from factory.engines.gmpai_integrity import ollama_client as oc
        model_name = oc.OLLAMA_MODEL

    rows, llm_calls = [], 0
    for sid in section_ids:
        section = by_id[sid]
        ctx, allowed = _section_context_v3(section, l2_by_rid, g4)
        prompt = _cp3.render(**ctx)

        structured, raw, secs, calls_this = None, "", 0.0, 0
        struct_violations = ["dry_run: no LLM"] if dry_run else []
        raw_llm_obj = None
        if not dry_run:
            # Fix A (CF-6 v1.2 §3.1): UNA sola llamada LLM por sección. Sin reintento.
            raw, secs, _ = _call_llm(prompt)
            llm_calls += 1
            calls_this += 1
            if llm_calls > CF6_MAX_CALLS:
                raise RuntimeError(f"CF6-2.5 v3 excedió el tope duro CF-6 ({CF6_MAX_CALLS})")
            raw_llm_obj = _extract_json(raw)
            if raw_llm_obj is None:
                struct_violations = ["salida no es JSON"]
            else:
                # Fix B: normalizar (dedupe determinista) ANTES de validar el contrato,
                # para que `validate_structure_contract` vea la estructura ya deduplicada.
                normalized = _cp3.normalize_evidence_observed(raw_llm_obj)
                struct_violations = _cp3.validate_structure_contract(
                    normalized, allowed_technical_findings=allowed)
                if not struct_violations:
                    structured = normalized

        gate = _cg.compose_section(structured, section, l2_by_rid)
        rows.append({
            "section_id": sid,
            "document": section["document"],
            "regulation": section["regulation"],
            "section_type": gate["section_type"],
            "regulatory_state": gate["regulatory_state"],
            "allowed_technical_findings": allowed,
            "llm_calls_section": calls_this,
            "structure_contract_violations": struct_violations,
            "mode": gate["mode"],
            "reason": gate.get("reason"),
            "qstate": gate.get("qstate"),
            "blacklist_hits": gate.get("blacklist_hits", []),
            "post_qstate_llm_calls": 0,
            "raw_llm_json": raw_llm_obj,
            "structured_llm": structured,
            "duplicate_quotes_raw": _dupe_quotes(raw_llm_obj),
            "technical_findings": (structured or raw_llm_obj or {}).get("technical_findings")
                                  if isinstance(structured or raw_llm_obj, dict) else None,
            "reviewer_action": (structured or raw_llm_obj or {}).get("reviewer_action")
                               if isinstance(structured or raw_llm_obj, dict) else None,
            "B_text": gate["text"],
            "llm_seconds": secs,
        })

    rendered = sum(1 for r in rows if r["mode"] == "RENDERED")
    safe = sum(1 for r in rows if r["mode"] == "SAFE_MODE")
    b_path = OUT / "CF6_2_5_v3_B_OUTPUTS.jsonl"
    b_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    summary = {
        "schema": "SHADOW_CF6_2_5_v3_PILOT_RUN/v1",
        "cf6_2_g_v3": "PASS (tag cf6-G2G-r1)",
        "prompt_v3_signed_tag": "cf6-G2-r1",
        "pilot_instance": PILOT_INSTANCE,
        "pilot_propose": PILOT_PROPOSE,
        "authorized_by_tag": "cf6-G2G-r1",
        "PROMPT_VERSION": PROMPT_VERSION,
        "prompt_signed": _cp3.is_signed(),
        "prompt_sha256": _cp3.prompt_sha256(),
        "model": model_name,
        "SAMPLE_MANIFEST_HASH": manifest_hash,
        "sample_manifest_committed_before_llm": True,
        "sections": section_ids,
        "LLM_CALLS_TOTAL": llm_calls,
        "LLM_CALLS_BY_SECTION": {r["section_id"]: r["llm_calls_section"] for r in rows},
        "llm_budget_cap_cf6": CF6_MAX_CALLS,
        "within_budget": llm_calls <= CF6_MAX_CALLS,
        "STRUCTURE_VALIDATION_BY_SECTION": {r["section_id"]: (r["structure_contract_violations"] or "OK") for r in rows},
        "QSTATE_RESULT_BY_SECTION": {r["section_id"]: ("PASS" if (r["qstate"] or {}).get("passed")
                                     else ((r["qstate"] or {}).get("violations") if r["qstate"] else "n/a (sin estructura)")) for r in rows},
        "BLACKLIST_RESULT_BY_SECTION": {r["section_id"]: (r["blacklist_hits"] or "CLEAN") for r in rows},
        "SAFE_MODE_SECTIONS": [r["section_id"] for r in rows if r["mode"] == "SAFE_MODE"],
        "TECHNICAL_FINDINGS_BY_SECTION": {r["section_id"]: r["technical_findings"] for r in rows},
        "ALLOWED_TECHNICAL_FINDINGS_BY_SECTION": {r["section_id"]: r["allowed_technical_findings"] for r in rows},
        "DUPLICATE_QUOTES_BY_SECTION": {r["section_id"]: r["duplicate_quotes_raw"] for r in rows},
        "REVIEWER_ACTION_BY_SECTION": {r["section_id"]: r["reviewer_action"] for r in rows},
        "sections_rendered": rendered,
        "sections_safe_mode": safe,
        "POST_QSTATE_LLM_CALLS": 0,
        "G4D_CALLS": 0,
        "g4d_reexecuted": False,
        "L2_MUTATIONS": 0,
        "HUMAN_STATE_CHANGES": 0,
        "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        "qstate_violations_in_published": sum(
            0 if (r["mode"] == "SAFE_MODE" or (r["qstate"] or {}).get("passed")) else 1 for r in rows),
        "blacklist_hits_in_published": sum(len(r["blacklist_hits"]) for r in rows if r["mode"] == "RENDERED"),
        "b_outputs": str(b_path),
        "human_quality_gate": "PENDIENTE — evaluación humana por sección (Capa 9), rúbrica §4.2",
        "note": "NO sobrescribe los artefactos del piloto v2 (CF6_2_5_B_OUTPUTS.jsonl / CF6_2_5_PILOT_RUN.json).",
    }
    (OUT / "CF6_2_5_v3_PILOT_RUN.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":  # pragma: no cover
    import sys
    s = run_cf6_2_5_v3(dry_run=("--dry-run" in sys.argv))
    print(json.dumps({k: s[k] for k in (
        "model", "LLM_CALLS_TOTAL", "LLM_CALLS_BY_SECTION", "sections_rendered", "sections_safe_mode",
        "SAFE_MODE_SECTIONS", "POST_QSTATE_LLM_CALLS", "qstate_violations_in_published",
        "blacklist_hits_in_published", "within_budget")}, indent=1, ensure_ascii=False))
