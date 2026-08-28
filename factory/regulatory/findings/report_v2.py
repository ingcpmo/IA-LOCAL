"""Render del informe V2 por CLASE de Finding (B5) -- FASE 7.

Módulo NUEVO -- `tier1_report.py` de CURRENT NO se toca. Agrupa los
Findings de las 7 clases y renderiza markdown + JSON con la cabecera
GxP obligatoria (BORRADOR ASISTIDO, no es declaración de cumplimiento,
sin aprobación automática).
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from factory.regulatory.findings.taxonomy import FINDING_CLASSES, Finding, as_dict

_HEADER = (
    "> Este informe es un BORRADOR ASISTIDO, generado por máquina. NO es una "
    "declaración de cumplimiento GMP, NO aprueba documentos, NO cierra CAPA, NO "
    "libera lote. `MACHINE_CONFIRMED_FINDING` significa que el verificador ancló "
    "una cita textual real -- sigue pendiente de sign-off humano. Todo Finding "
    "nace `human_state=UNREVIEWED` y solo un revisor humano con nombre real lo "
    "cambia (CLAUDE.md, sin excepción)."
)

_CLASS_TITLE = {
    "RegulatoryFinding": "Hallazgos regulatorios",
    "FunctionalFinding": "Hallazgos funcionales",
    "TechnicalFinding": "Hallazgos técnicos",
    "TraceabilityFinding": "Hallazgos de trazabilidad",
    "DataIntegrityFinding": "Hallazgos de integridad de datos",
    "SecurityFinding": "Hallazgos de seguridad",
    "TestCoverageFinding": "Hallazgos de cobertura de pruebas",
}

_BAND_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, None: 4}


def _sort_key(f: Finding):
    band = (f.risk or {}).get("band")
    return (_BAND_ORDER.get(band, 4), f.finding_class, f.subtype, f.page)


def build_report(findings: list[Finding], *, document_id: str,
                 run_id: str | None = None) -> dict:
    by_class: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_class[f.finding_class].append(f)

    summary = {
        "document_id": document_id,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": len(findings),
        "by_class": {k: len(v) for k, v in by_class.items()},
        "by_machine_state": _count(findings, lambda f: f.machine_state),
        "by_risk_band": _count(findings, lambda f: (f.risk or {}).get("band", "n/a")),
        "human_review_required": sum(1 for f in findings if f.human_state == "UNREVIEWED"),
        "governance_statement": _HEADER.replace("> ", ""),
    }
    return {
        "summary": summary,
        "findings": [as_dict(f) for f in sorted(findings, key=_sort_key)],
    }


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"# Informe V2 por hallazgo -- {s['document_id']}",
        "",
        f"Run: `{s.get('run_id') or 'n/a'}` - Generado: {s['generated_at']}",
        "",
        _HEADER,
        "",
        "## Resumen",
        "",
        f"- Total de hallazgos: {s['total_findings']}",
        f"- Requieren revisión humana (`UNREVIEWED`): {s['human_review_required']}",
        f"- Por clase: {s['by_class']}",
        f"- Por estado de máquina: {s['by_machine_state']}",
        f"- Por banda de riesgo: {s['by_risk_band']}",
        "",
    ]
    by_class: dict[str, list] = defaultdict(list)
    for f in report["findings"]:
        by_class[f["finding_class"]].append(f)
    for cls in FINDING_CLASSES:
        items = by_class.get(cls, [])
        if not items:
            continue
        lines.append(f"## {_CLASS_TITLE.get(cls, cls)} ({len(items)})")
        lines.append("")
        lines.append("| Subtipo | Riesgo | Estado máquina | Req | Pág | Evidencia (cita) | Fundamento |")
        lines.append("|---|---|---|---|---|---|---|")
        for f in items:
            band = (f.get("risk") or {}).get("band", "n/a")
            score = (f.get("risk") or {}).get("score", "")
            pipe = "\\|"
            quote = (f["source_text"] or "").replace("|", pipe)
            if len(quote) > 140:
                quote = quote[:140] + "…"
            req = f.get("requirement_id") or ""
            rationale = f["rationale"].replace("|", pipe)[:180]
            lines.append(
                f"| {f['subtype']} | {band} ({score}) | {f['machine_state']} | "
                f"{req} | {f['page']} | {quote} | {rationale} |"
            )
        lines.append("")
    return "\n".join(lines)


def _count(findings, keyfn) -> dict:
    out: dict = defaultdict(int)
    for f in findings:
        out[keyfn(f)] += 1
    return dict(out)


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=1, default=str)
