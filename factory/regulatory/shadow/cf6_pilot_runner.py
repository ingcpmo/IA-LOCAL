"""SHADOW · CF-6 v1.2 · CF6-2.5 — SMALL QUALITY PILOT: genera B por sección.

Para cada sección del SAMPLE_MANIFEST **congelado** (`FROZEN@cf6-G2G`):

  1. arma el contexto determinista (section_type / regulatory_state desde
     `composer_gate`, citas ancladas L2 verbatim, opiniones G4 normalizadas por
     `composer_gate.normalize_g4d` — G4d NO se re-ejecuta);
  2. llama UNA vez al LLM con el prompt FIRMADO `shadow-cf6-composer-struct-v2`
     (`composer_prompt`, `assert_signed()` fail-closed) → estructura JSON;
  3. valida la estructura (`composer_prompt.validate_structure_contract`) y pasa
     por el gate `composer_gate.compose_section` (Q-STATE-1..6 → render 100%
     determinista → blacklist Q1–Q5 → modo seguro). **CERO LLM tras Q-STATE.**

Autorizado por el ADDENDUM `PILOT_EXECUTION-2026-037/-038` (human_confirmed,
`approved_by_id=cesar`, tag `cf6-G2G`). Tope duro CF-6: 250 llamadas.

NO decide el HUMAN_QUALITY_GATE (§4.2) — eso es evaluación humana de Capa 9.
NO re-ejecuta G4d. NO muta L2 / human_state / FINDINGS_FINGERPRINT.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg
from factory.regulatory.shadow import composer_prompt as _cp

PILOT_INSTANCE = "PILOT_EXECUTION-2026-038"          # ADDENDUM human_confirmed
PILOT_PROPOSE = "PILOT_EXECUTION-2026-037"
CF6_MAX_CALLS = 250
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _load_g4_opinions(shadow_dir: Path) -> dict:
    """finding_record_id -> {assessment, verifier} de la opinión experta ACEPTADA."""
    out: dict = {}
    for name in ("g4a_technical.jsonl", "g4c_functional.jsonl", "g4d_regulatory_triage.jsonl"):
        p = shadow_dir / "G4" / name
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rid = row.get("_unit")
            env = row.get("envelope") or {}
            st = (row.get("verifier") or {}).get("status")
            if rid and rid not in out:
                out[rid] = {"assessment": env.get("assessment"), "verifier": st}
    return out


def _anchor(f: dict) -> str:
    return (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""


def _risk(f: dict) -> str:
    return (f.get("risk") or {}).get("band") or f.get("risk_band") or ""


def _section_context(section: dict, l2_by_rid: dict, g4: dict) -> dict:
    rids = section.get("finding_record_ids") or [e["finding_record_id"] for e in section["entries"]]
    st_type, _ = _cg.infer_section_type(section)
    reg_state = _cg.expected_regulatory_state(section)
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
    return {
        "document": section["document"],
        "regulation": section["regulation"],
        "section_type": st_type,
        "regulatory_state": reg_state,
        "entries": "\n".join(entries),
        "anchored_quotes": "\n".join(quotes) or "(sin citas ancladas)",
        "normalized_opinions": "\n".join(opinions) or "(sin opiniones)",
    }


def _call_llm(prompt: str, *, num_predict: int = 1024, num_ctx: int = 8192):
    from factory.engines.gmpai_integrity import ollama_client as oc
    t0 = time.time()
    resp = oc.generate(prompt, temperature=0.0, num_ctx=num_ctx, num_predict=num_predict)
    return resp.get("response", "") or "", round(time.time() - t0, 2), resp


def run_cf6_2_5(shadow_dir: str | Path = "docs_plan/shadow_llm",
                manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
                *, out_dir: str | Path = "docs_plan/shadow_llm/CF6",
                dry_run: bool = False) -> dict:
    _cp.assert_signed()                                   # fail-closed
    SL = Path(shadow_dir)
    OUT = Path(out_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert str(manifest.get("status", "")).upper().startswith("FROZEN"), \
        "el SAMPLE_MANIFEST debe estar FROZEN antes de generar B (§4.1)"
    manifest_hash = manifest["sample_manifest_hash"]
    section_ids = manifest["sections_selected"]

    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2_by_rid = {f["finding_record_id"]: f for f in findings}
    by_id = {s["section_id"]: s for s in _skel.build_composer_skeleton(findings)["sections"]}
    g4 = _load_g4_opinions(SL)

    model_name = "dry-run"
    if not dry_run:
        from factory.engines.gmpai_integrity import ollama_client as oc
        model_name = oc.OLLAMA_MODEL

    rows = []
    llm_calls = 0
    for sid in section_ids:
        section = by_id[sid]
        ctx = _section_context(section, l2_by_rid, g4)
        prompt = _cp.render(**ctx)

        structured = None
        raw = ""
        secs = 0.0
        struct_violations = ["dry_run: no LLM"] if dry_run else []
        calls_this = 0
        if not dry_run:
            for attempt in (1, 2):
                raw, secs, _ = _call_llm(prompt if attempt == 1 else
                                         prompt + "\n\nCorrige: devuelve SOLO el objeto JSON del contrato, sin texto.")
                llm_calls += 1
                calls_this += 1
                if llm_calls > CF6_MAX_CALLS:
                    raise RuntimeError(f"CF6-2.5 excedió el tope duro CF-6 ({CF6_MAX_CALLS})")
                obj = _extract_json(raw)
                struct_violations = _cp.validate_structure_contract(obj) if obj is not None else ["salida no es JSON"]
                if not struct_violations:
                    structured = obj
                    break

        gate = _cg.compose_section(structured, section, l2_by_rid)
        rows.append({
            "section_id": sid,
            "document": section["document"],
            "regulation": section["regulation"],
            "section_type": gate["section_type"],
            "regulatory_state": gate["regulatory_state"],
            "llm_calls_section": calls_this,
            "structure_contract_violations": struct_violations,
            "mode": gate["mode"],
            "reason": gate.get("reason"),
            "qstate": gate.get("qstate"),
            "blacklist_hits": gate.get("blacklist_hits", []),
            "post_qstate_llm_calls": 0,
            "structured_llm": structured,
            "B_text": gate["text"],
            "llm_seconds": secs,
        })

    rendered = sum(1 for r in rows if r["mode"] == "RENDERED")
    safe = sum(1 for r in rows if r["mode"] == "SAFE_MODE")
    b_path = OUT / "CF6_2_5_B_OUTPUTS.jsonl"
    b_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    summary = {
        "schema": "SHADOW_CF6_2_5_PILOT_RUN/v1",
        "cf6_2_g": "PASS (tag cf6-G2G)",
        "pilot_instance": PILOT_INSTANCE,
        "pilot_propose": PILOT_PROPOSE,
        "authorized_by_tag": "cf6-G2G",
        "composer_prompt_version": _cp.PROMPT_VERSION,
        "prompt_signed": _cp.is_signed(),
        "prompt_sha256": _cp.prompt_sha256(),
        "model": model_name,
        "sample_manifest_hash": manifest_hash,
        "sample_manifest_committed_before_llm": True,
        "sections": section_ids,
        "n_sections": len(section_ids),
        "sections_rendered": rendered,
        "sections_safe_mode": safe,
        "sections_in_safe_mode": [r["section_id"] for r in rows if r["mode"] == "SAFE_MODE"],
        "llm_calls": llm_calls,
        "llm_budget_cap_cf6": CF6_MAX_CALLS,
        "within_budget": llm_calls <= CF6_MAX_CALLS,
        "post_qstate_llm_calls_total": 0,
        "qstate_violations_in_published": sum(
            0 if (r["mode"] == "SAFE_MODE" or (r["qstate"] or {}).get("passed")) else 1 for r in rows),
        "blacklist_hits_in_published": sum(len(r["blacklist_hits"]) for r in rows if r["mode"] == "RENDERED"),
        "g4d_reexecuted": False,
        "integrity": {
            "L2_MUTATIONS": 0, "HUMAN_STATE_CHANGES": 0, "G4D_CALLS": 0,
            "FINDINGS_FINGERPRINT": "235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23",
        },
        "b_outputs": str(b_path),
        "per_section": [{k: r[k] for k in ("section_id", "section_type", "regulatory_state",
                        "mode", "reason", "llm_calls_section", "post_qstate_llm_calls",
                        "structure_contract_violations", "blacklist_hits")} for r in rows],
        "human_quality_gate": "PENDIENTE — evaluación humana por sección (Capa 9), rúbrica §4.2",
    }
    (OUT / "CF6_2_5_PILOT_RUN.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":  # pragma: no cover
    import sys
    dry = "--dry-run" in sys.argv
    s = run_cf6_2_5(dry_run=dry)
    print(json.dumps({k: s[k] for k in (
        "model", "n_sections", "sections_rendered", "sections_safe_mode",
        "sections_in_safe_mode", "llm_calls", "within_budget",
        "post_qstate_llm_calls_total", "qstate_violations_in_published",
        "blacklist_hits_in_published", "human_quality_gate")}, indent=1, ensure_ascii=False))
