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
from factory.regulatory.shadow.cf6_human_gate import _report_A, _rubric_block


def build(shadow_dir: str | Path = "docs_plan/shadow_llm",
          manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
          b_outputs: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_v3_B_OUTPUTS.jsonl") -> str:
    SL = Path(shadow_dir)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2 = {f["finding_record_id"]: f for f in findings}
    by_id = {s["section_id"]: s for s in _skel.build_composer_skeleton(findings)["sections"]}
    B = {json.loads(l)["section_id"]: json.loads(l)
         for l in Path(b_outputs).read_text(encoding="utf-8").splitlines() if l.strip()}

    L = ["# CF-6 v1.2 · CF6-2.5 (v3) — HUMAN_QUALITY_GATE (paquete para Capa 9)", "",
         f"PROMPT_VERSION `shadow-cf6-composer-struct-v3` (SIGNED, tag cf6-G2-r1) · "
         f"SAMPLE_MANIFEST `{manifest['status']}` · hash `{manifest['sample_manifest_hash']}` · "
         f"PILOT_EXECUTION-2026-040 (tag cf6-G2G-r1)", "",
         "> **Regla §4.2:** PASS del conjunto solo si CADA sección pasa TODOS los umbrales; "
         "`Sobreafirmación regulatoria` = 0 por sección (cero tolerancia). PASS (todas) → "
         "autoriza CF6-3. FAIL (alguna) → STOP; reportar sección/dimensión; decisión de Capa 9.",
         ">", "> El revisor adjudica sobre los **findings L2** (columna A), nunca sobre la narrativa.",
         "", "> Claude Code **no** puntúa ni declara PASS/FAIL. La rúbrica va vacía.", "",
         "---", ""]

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
