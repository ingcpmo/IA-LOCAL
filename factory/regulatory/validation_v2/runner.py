"""Ensamblado del reporte de validación V2 (B8) -- FASE 10 §3.3.

B8a: dado el resultado POR CASO de cada suite (más los transversales),
produce el reporte completo de gates + la interpretación de Suite A +
markdown. La corrida real que genera esos resultados por caso (B3->B4->B5
sobre el fixture, bajo PILOT_EXECUTION, con prompts firmados) es B8b y no
vive aquí.
"""
from __future__ import annotations

from datetime import datetime, timezone

from factory.regulatory.validation_v2 import gates


def build_full_report(*, regulatory_cases: list[dict], functional_cases: list[dict],
                      technical_cases: list[dict], transversal: dict,
                      generated_at: str | None = None) -> dict:
    a = gates.evaluate_regulatory(regulatory_cases)
    b = gates.evaluate_functional(functional_cases)
    c = gates.evaluate_technical(technical_cases)
    t = gates.evaluate_transversal(**transversal)
    interp = gates.interpret_regulatory(a)
    reports = [a, b, c, t]
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "suite_reports": [r.as_dict() for r in reports],
        "regulatory_interpretation": interp,
        "all_gates_passed": all(r.all_passed for r in reports),
        "note": ("Instrumento único de medición: el fixture. PROHIBIDO aflojar validadores "
                 "para pasar un gate (skill gmp-recall-pipeline). Un gate rojo se reporta "
                 "sin eufemismos; si Suite A no cruza >=6/7, la clase Regulatory adopta "
                 "Palanca C (Tier-1), nunca auto-aprobación."),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Reporte de validación V2 (FASE 10)",
        "",
        f"Generado: {report['generated_at']}",
        "",
        f"**Todos los gates en verde:** {'SÍ' if report['all_gates_passed'] else 'NO'}",
        "",
        f"**Interpretación Suite A (Regulatory):** {report['regulatory_interpretation']}",
        "",
        f"> {report['note']}",
        "",
    ]
    for sr in report["suite_reports"]:
        lines.append(f"## {sr['suite']} -- {'PASS' if sr['all_passed'] else 'FAIL'}")
        lines.append("")
        lines.append("| Gate | Valor | Umbral | Resultado |")
        lines.append("|---|---|---|---|")
        for g in sr["gates"]:
            mark = "verde" if g["passed"] else "ROJO"
            detail = f" -- {g['detail']}" if g.get("detail") else ""
            lines.append(f"| {g['name']} | {g['value']} | {g['threshold']} | {mark}{detail} |")
        lines.append("")
    return "\n".join(lines)
