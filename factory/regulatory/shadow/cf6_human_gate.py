"""SHADOW · CF-6 v1.2 · CF6-2.5 — arma el paquete del HUMAN_QUALITY_GATE (§4.2).

Para cada sección del SAMPLE_MANIFEST congelado, ensambla:
  A = reporte determinista de L2 (hechos verbatim: subtype/riesgo/machine_state/
      página/cita anclada) — SIN LLM;
  B = narrativa de CF6-2.5 (RENDERED o SAFE_MODE) desde CF6_2_5_B_OUTPUTS.jsonl;
  rúbrica §4.2 en blanco, POR SECCIÓN.

NO decide PASS/FAIL — eso lo evalúa un revisor humano de Capa 9. La regla es:
PASS del conjunto SOLO si CADA sección pasa TODOS los umbrales; `Sobreafirmación
regulatoria = 0` por sección, sin excepción.

CERO LLM. No muta L2.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import composer_gate as _cg

_DIMS = [
    ("Fidelidad al finding", "≥ 4/5"),
    ("Precisión GMP", "≥ 4/5"),
    ("Claridad", "≥ 4/5"),
    ("Utilidad para revisión", "≥ 4/5"),
    ("Valor añadido vs determinista", "≥ 4/5"),
    ("Sobreafirmación regulatoria", "= 0 (cero tolerancia)"),
    ("Preferencia B sobre A", "REQUERIDA"),
    ("Reduce carga cognitiva vs leer L2", "SÍ"),
]


def _trim(s: str, n: int = 200) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def _report_A(section: dict, l2_by_rid: dict) -> str:
    rids = section.get("finding_record_ids") or [e["finding_record_id"] for e in section["entries"]]
    L = [f"**A — reporte determinista L2** ({section['document']} · {section['regulation']} · "
         f"{len(rids)} finding{'s' if len(rids) != 1 else ''})", "",
         "| finding | subtype | riesgo | machine_state | pág | cita anclada (L2, verbatim) |",
         "|---|---|---|---|---|---|"]
    for rid in rids:
        f = l2_by_rid.get(rid) or {}
        q = _trim((f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or "", 160).replace("|", "\\|")
        L.append(f"| `{rid[-8:]}` | {f.get('subtype')} | {(f.get('risk') or {}).get('band')} | "
                 f"{f.get('machine_state')} | {f.get('page')} | {q} |")
    L.append("")
    L.append(f"Todos `human_state = UNREVIEWED`. Estado regulatorio determinista de la sección: "
             f"**{_cg.expected_regulatory_state(section)}**.")
    return "\n".join(L)


def _rubric_block(section_id: str) -> str:
    L = [f"**Rúbrica §4.2 — {section_id} (POR SECCIÓN)**", "",
         "| Dimensión | Umbral | Puntuación | ¿Pasa? |", "|---|---|---|---|"]
    for dim, thr in _DIMS:
        L.append(f"| {dim} | {thr} |  |  |")
    L.append("")
    L.append(f"`{section_id}` PASS de sección = TODAS las filas pasan. "
             f"Sobreafirmación regulatoria DEBE ser 0.")
    return "\n".join(L)


def build(shadow_dir: str | Path = "docs_plan/shadow_llm",
          manifest_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_SAMPLE_MANIFEST.json",
          b_outputs: str | Path = "docs_plan/shadow_llm/CF6/CF6_2_5_B_OUTPUTS.jsonl") -> str:
    SL = Path(shadow_dir)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    findings = json.loads((SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    l2 = {f["finding_record_id"]: f for f in findings}
    by_id = {s["section_id"]: s for s in _skel.build_composer_skeleton(findings)["sections"]}
    B = {json.loads(l)["section_id"]: json.loads(l)
         for l in Path(b_outputs).read_text(encoding="utf-8").splitlines() if l.strip()}

    L = ["# CF-6 v1.2 · CF6-2.5 — HUMAN_QUALITY_GATE (paquete para Capa 9)", "",
         f"SAMPLE_MANIFEST `{manifest['status']}` · hash `{manifest['sample_manifest_hash']}` · "
         f"CF6-2.G {manifest.get('cf6_2_g','')}", "",
         "> **Regla de evaluación (§4.2):** el gate es **PASS del conjunto solo si CADA sección "
         "pasa TODOS los umbrales.** `Sobreafirmación regulatoria` debe ser **0 por sección**, "
         "sin excepción. Un promedio alto con una sección peligrosa escondida = **FAIL**.",
         ">", "> PASS (todas) → autoriza CF6-3. FAIL (alguna) → STOP; reportar qué sección y "
         "qué dimensión; decisión de Capa 9 (ajustar prompt → nuevo `composer_prompt_version` "
         "en CF6-2, o MODEL_QUALIFICATION).", "",
         "El revisor humano adjudica sobre los **findings L2** (columna A), nunca sobre la "
         "narrativa. B es asistencia marcada.", "", "---", ""]

    for sid in manifest["sections_selected"]:
        section = by_id[sid]
        b = B.get(sid, {})
        L.append(f"## {sid} · {section['document']} · {section['regulation']}  "
                 f"(section_type {b.get('section_type')} · regulatory_state {b.get('regulatory_state')} · "
                 f"B = **{b.get('mode','?')}**{' — '+b['reason'] if b.get('reason') else ''})")
        L.append("")
        L.append(_report_A(section, l2))
        L.append("")
        L.append("**B — narrativa CF6-2.5**")
        L.append("")
        L.append("```")
        L.append(b.get("B_text", "(sin B)"))
        L.append("```")
        if b.get("blacklist_hits"):
            L.append(f"\n_blacklist hits automáticos: {b['blacklist_hits']}_")
        if b.get("qstate") and not (b["qstate"] or {}).get("passed") and b.get("mode") != "SAFE_MODE":
            L.append(f"\n_Q-STATE violations: {b['qstate']['violations']}_")
        L.append("")
        L.append(_rubric_block(sid))
        L.append("")
        L.append("---")
        L.append("")

    L.append("## Veredicto del HUMAN_QUALITY_GATE")
    L.append("")
    L.append("```")
    L.append("HUMAN_QUALITY_GATE = PENDIENTE   (evaluación de Capa 9, por sección)")
    L.append("por_seccion:")
    for sid in manifest["sections_selected"]:
        L.append(f"  {sid}: PASS | FAIL  (si FAIL: dimensión(es) = ____)")
    L.append("resultado_conjunto = PASS solo si TODAS las secciones = PASS")
    L.append("firma: ____________  fecha: __________")
    L.append("```")
    return "\n".join(L)


if __name__ == "__main__":  # pragma: no cover
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "docs_plan/shadow_llm/CF6/CF6_2_5_HUMAN_QUALITY_GATE.md")
    out.write_text(build(), encoding="utf-8")
    print("WROTE", out)
