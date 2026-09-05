"""SHADOW · CF-6 v1.2 · CF6-2.5 (v3) — paquete del HUMAN_QUALITY_GATE para v3.

Igual que `cf6_human_gate` pero sobre los artefactos v3
(`CF6_2_5_v3_B_OUTPUTS.jsonl`), en `CF6_2_5_v3_HUMAN_QUALITY_GATE.md`.
A = evidencia determinista L2 · B = resultado CF6 v3 · rúbrica §4.2 vacía por
sección. Claude Code NO puntúa ni declara PASS/FAIL. CERO LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg
from factory.regulatory.shadow import composer_prompt_v3 as _cp3
from factory.regulatory.shadow.cf6_human_gate import _report_A, _rubric_block

_FORBIDDEN_TF = set(_cp3._TECH_FINDING_FORBIDDEN)


def _comparison_table(v2_run: dict, v2_b: dict, v3_b: dict, section_ids: list[str]) -> list[str]:
    """Tabla FACTUAL v2 → v3, derivada de los artefactos (no escrita a mano)."""
    v2_mode = {p["section_id"]: p["mode"] for p in v2_run.get("per_section", [])}
    L = ["## Resumen comparativo v2 → v3 (factual)", "",
         "| Sección | v2 | v3 | Cambio observado |", "|---|---|---|---|"]
    for sid in section_ids:
        m2 = v2_mode.get(sid, "?")
        r3 = v3_b.get(sid, {})
        m3 = r3.get("mode", "?")
        b2 = (v2_b.get(sid, {}).get("structured_llm") or {})
        tf2, ra2 = b2.get("technical_findings"), b2.get("reviewer_action") or ""
        tf3 = r3.get("technical_findings")
        ra3 = r3.get("reviewer_action") or ""
        allowed = set(r3.get("allowed_technical_findings") or [])
        notes = []
        if m2 == "SAFE_MODE" and m3 == "RENDERED":
            notes.append("modo seguro anterior superado (v3 pasa contrato v3 + Q-STATE)")
        elif m2 == "RENDERED" and m3 == "SAFE_MODE":
            why = r3.get("structure_contract_violations") or []
            short = "; ".join(w.split(":")[0] for w in why) if isinstance(why, list) and why else (r3.get("reason") or "")
            notes.append(f"v3 detiene antes de publicar ({short}) — seguridad, no regresión")
        elif m2 == "RENDERED" and m3 == "RENDERED":
            if isinstance(tf2, list) and any(x in _FORBIDDEN_TF for x in tf2) and \
               isinstance(tf3, list) and set(tf3) <= allowed:
                notes.append("technical_findings corregidos")
            if _cp3._PAGE_RE.search(ra2) and not _cp3._PAGE_RE.search(ra3):
                notes.append("página inventada eliminada")
            if not notes:
                notes.append("sin cambio material")
        elif m2 == "SAFE_MODE" and m3 == "SAFE_MODE":
            notes.append("modo seguro en v2 y v3")
        else:
            notes.append("—")
        L.append(f"| {sid} | {m2} | {m3} | {' + '.join(notes)} |")
    L += ["", "> Los `SAFE_MODE` **nuevos** en v3 (v2 RENDERED → v3 SAFE_MODE) son el gate "
          "determinista deteniendo salida insegura del modelo — **mejor seguridad, no regresión**.",
          "", "---", ""]
    return L


def build(shadow_dir: str | Path = "docs_plan/shadow_llm",
          manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
          b_outputs: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_v3_B_OUTPUTS.jsonl",
          v2_run: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_PILOT_RUN.json",
          v2_b_outputs: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_B_OUTPUTS.jsonl") -> str:
    SL = Path(shadow_dir)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2 = {f["finding_record_id"]: f for f in findings}
    by_id = {s["section_id"]: s for s in _skel.build_composer_skeleton(findings)["sections"]}
    B = {json.loads(l)["section_id"]: json.loads(l)
         for l in Path(b_outputs).read_text(encoding="utf-8").splitlines() if l.strip()}
    v2run = json.loads(Path(v2_run).read_text(encoding="utf-8"))
    v2B = {json.loads(l)["section_id"]: json.loads(l)
           for l in Path(v2_b_outputs).read_text(encoding="utf-8").splitlines() if l.strip()}

    freeze_tag = manifest.get("freeze_tag") or "cf6-G2.5-manifest"
    L = ["# CF-6 v1.2 · CF6-2.5 (v3) — HUMAN_QUALITY_GATE (paquete para Capa 9)", "",
         f"PROMPT_VERSION `shadow-cf6-composer-struct-v3` (SIGNED, tag cf6-G2-r1) · "
         f"SAMPLE_MANIFEST `{manifest['status']}` (congelado en tag **{freeze_tag}**, commit e356b3f) · "
         f"hash `{manifest['sample_manifest_hash']}` · scope ADDENDUM PILOT_EXECUTION-2026-039/-040 "
         f"(tag cf6-G2G-r1). `cf6-G2G` fue el cierre de scope previo, no la congelación del manifest.", "",
         "> **Regla §4.2:** PASS del conjunto solo si CADA sección pasa TODOS los umbrales; "
         "`Sobreafirmación regulatoria` = 0 por sección (cero tolerancia). PASS (todas) → "
         "autoriza CF6-3. FAIL (alguna) → STOP; reportar sección/dimensión; decisión de Capa 9.",
         ">", "> El revisor adjudica sobre los **findings L2** (columna A), nunca sobre la narrativa.",
         "", "> Claude Code **no** puntúa ni declara PASS/FAIL. La rúbrica va vacía.", "",
         "---", ""]
    L += _comparison_table(v2run, v2B, B, manifest["sections_selected"])

    for sid in manifest["sections_selected"]:
        section = by_id[sid]
        b = B.get(sid, {})
        L.append(f"## {sid} · {section['document']} · {section['regulation']}  "
                 f"(section_type {b.get('section_type')} · regulatory_state {b.get('regulatory_state')} · "
                 f"B = **{b.get('mode','?')}**{' — '+str(b['reason']) if b.get('reason') else ''})")
        L.append("")
        L.append(f"`allowed_technical_findings` = {b.get('allowed_technical_findings')} · "
                 f"`technical_findings` (v3) = {b.get('technical_findings')} · "
                 f"`duplicate_quotes_raw` = {b.get('duplicate_quotes_raw')}")
        L.append("")
        L.append(_report_A(section, l2))
        L.append("")
        L.append("**B — resultado CF6 v3**")
        L.append("")
        L.append("```")
        L.append(b.get("B_text", "(sin B)"))
        L.append("```")
        if b.get("structure_contract_violations") and b["structure_contract_violations"] != "OK":
            L.append(f"\n_structure_contract_violations (v3): {b['structure_contract_violations']}_")
        if b.get("blacklist_hits"):
            L.append(f"\n_blacklist hits automáticos: {b['blacklist_hits']}_")
        if b.get("qstate") and not (b["qstate"] or {}).get("passed") and b.get("mode") != "SAFE_MODE":
            L.append(f"\n_Q-STATE violations: {b['qstate']['violations']}_")
        L.append("")
        L.append("`reviewer_action` (v3, emitido por el modelo, pre-render): "
                 f"{b.get('reviewer_action')!r}")
        L.append("")
        L.append(_rubric_block(sid))
        L.append("")
        L.append("---")
        L.append("")

    L.append("## Veredicto del HUMAN_QUALITY_GATE (v3)")
    L.append("")
    L.append("```")
    L.append("HUMAN_QUALITY_GATE (v3) = PENDIENTE   (evaluación de Capa 9, por sección)")
    L.append("por_seccion:")
    for sid in manifest["sections_selected"]:
        L.append(f"  {sid}: PASS | FAIL  (si FAIL: dimensión(es) = ____)")
    L.append("resultado_conjunto = PASS solo si TODAS las secciones = PASS")
    L.append("firma: ____________  fecha: __________")
    L.append("```")
    return "\n".join(L)


if __name__ == "__main__":  # pragma: no cover
    out = Path("docs_plan/shadow_llm/CF6/CF6_2_5_v3_HUMAN_QUALITY_GATE.md")
    out.write_text(build(), encoding="utf-8")
    print("WROTE", out)
