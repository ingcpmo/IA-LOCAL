"""Informe unificado por hallazgo -- Paquete 1 parte (b), cierra hallazgo G
(EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_CIERRE.md): evidencia+pagina
(`factory.regulatory.tier1_report`) + riesgo+recomendacion+trazabilidad
(`factory.services.gap_assessment_finding_mapper`), UN SOLO artefacto por
requisito. Reutiliza ambos modulos integros -- ninguna regla de ninguno
se reimplementa aqui.

POR QUE LA UNION NO ES 1:1 AUTOMATICA
--------------------------------------
`gap_assessment_finding_mapper.map_finding_to_remediation_change()`
consume una FORMA DE FINDING NARRATIVA (`findings_completos_*.json`:
`clasificacion_brecha`/`severidad`/`recomendacion`/
`cambio_documental_propuesto`/`clasificacion_brecha_rationale`) que
`tier1_report.generate_tier1_report()` NO produce -- `chunked_engine.py`
habla un vocabulario distinto (`requisito_regulatorio`/`evidencia_exacta`/
`pagina_o_seccion`), sin traduccion deterministica conocida a la forma
narrativa. Inventar esa traduccion aqui violaria la regla central del
paquete ("sin inventar campos cuando falte el dato") -- una
`clasificacion_brecha`/`severidad` adivinada seria exactamente eso.

Este modulo NO inventa esa traduccion: acepta opcionalmente una lista de
findings narrativos YA EXISTENTES (p.ej. un `findings_completos_*.json`
real, ya curado, para el mismo documento) y los cruza por
`requirement_id` con el `Tier1Report`. Cuando un requisito del
`Tier1Report` no tiene finding narrativo correspondiente -- el caso
normal para una corrida Tier-1 en vivo, todavia no existe ninguna fase
que genere esa forma automaticamente -- el renglon lo declara explicito
(`NO_GAP_ASSESSMENT_DATA`), nunca deja el campo vacio en silencio ni
inventa riesgo/recomendacion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.regulatory.tier1_report import (
    CONFIRMED,
    RequirementOutcome,
    Tier1Report,
    _COMPLIANCE_BANNER,
    _estado_label,
)
from factory.services.gap_assessment_finding_mapper import (
    NotMappableToCurrentSchema,
    map_finding_to_remediation_change,
)

MAPPED = "MAPPED"
NO_GAP_ASSESSMENT_DATA = "NO_GAP_ASSESSMENT_DATA"
NOT_MAPPABLE = "NOT_MAPPABLE"


@dataclass
class UnifiedFindingRow:
    # Campos reales de tier1_report.RequirementOutcome -- nunca reinventados.
    requirement_id: str
    bucket: str
    conclusion: str
    review_flags: list[str] = field(default_factory=list)
    evidence_quote: str | None = None
    page_or_section: str | None = None
    review_queue_rc_id: str | None = None
    cross_reference_target: list[str] | None = None
    # Estado explicito de la union con gap_assessment_finding_mapper -- nunca
    # se omite en silencio cuando no hay dato del lado de riesgo/recomendacion.
    risk_recommendation_status: str = NO_GAP_ASSESSMENT_DATA
    not_mappable_reason: str | None = None
    # Campos reales de gap_assessment_finding_mapper.MappedChange.change --
    # solo poblados cuando risk_recommendation_status == MAPPED.
    change_risk: str | None = None
    change_risk_basis: list[str] | None = None
    proposed_content: str | None = None
    change_reason: str | None = None
    citation_anchor_status: str | None = None
    # Trazabilidad completa del mapeo (campo -> regla que lo derivo), tal
    # cual la produce gap_assessment_finding_mapper -- el "fundamento" que
    # tambien pide la parte (a) del paquete.
    rules: dict[str, str] | None = None


@dataclass
class UnifiedFindingReport:
    document_id: str
    agent_id: str
    run_id: str
    generated_at: str
    rows: list[UnifiedFindingRow] = field(default_factory=list)


def _requirement_id_of(narrative_finding: dict) -> str | None:
    """Mismo criterio que gap_assessment_finding_mapper: el requirement_id
    real es el prefijo de 'requisito' antes de ' — '. None si el campo no
    tiene esa forma -- nunca se asume un id a medias."""
    requisito = narrative_finding.get("requisito")
    if not requisito or " — " not in requisito:
        return None
    return requisito.split(" — ")[0].strip()


def build_unified_finding_report(
    tier1: Tier1Report, *,
    document_name: str, document_sha256: str,
    narrative_findings: list[dict] | None = None,
    source_text: str | None = None,
) -> UnifiedFindingReport:
    """Combina un Tier1Report ya generado con findings narrativos YA
    EXISTENTES (opcional) para el mismo documento -- nunca dispara una
    corrida nueva de ninguno de los dos modulos, nunca invoca un LLM.

    narrative_findings (opcional, default None): lista de dicts con la
    forma que produce `findings_completos_*.json` -- el UNICO formato que
    `gap_assessment_finding_mapper` sabe interpretar hoy. Sin esto, todo
    renglon queda NO_GAP_ASSESSMENT_DATA (comportamiento honesto, no un
    error -- es el estado real de la mayoria de las corridas Tier-1
    actuales, que no tienen un gap-assessment narrativo asociado)."""
    by_requirement: dict[str, dict] = {}
    for nf in (narrative_findings or []):
        req_id = _requirement_id_of(nf)
        if req_id is not None:
            by_requirement[req_id] = nf

    rows: list[UnifiedFindingRow] = []
    for outcome in tier1.requirements:
        row = UnifiedFindingRow(
            requirement_id=outcome.requirement_id, bucket=outcome.bucket,
            conclusion=outcome.conclusion, review_flags=list(outcome.review_flags),
            evidence_quote=outcome.evidence_quote, page_or_section=outcome.page_or_section,
            review_queue_rc_id=outcome.review_queue_rc_id,
            cross_reference_target=outcome.cross_reference_target,
        )
        narrative = by_requirement.get(outcome.requirement_id)
        if narrative is None:
            rows.append(row)
            continue
        try:
            mapped = map_finding_to_remediation_change(
                narrative, document_name=document_name, document_sha256=document_sha256,
                run_id=tier1.run_id, source_text=source_text,
            )
        except NotMappableToCurrentSchema as e:
            row.risk_recommendation_status = NOT_MAPPABLE
            row.not_mappable_reason = str(e)
            rows.append(row)
            continue
        row.risk_recommendation_status = MAPPED
        row.change_risk = mapped.change["change_risk"]
        row.change_risk_basis = mapped.change["change_risk_basis"]
        row.proposed_content = mapped.change["proposed_content"]
        row.change_reason = mapped.change["change_reason"]
        row.citation_anchor_status = mapped.change["citation_anchor_status"]
        row.rules = mapped.rules
        rows.append(row)

    return UnifiedFindingReport(
        document_id=tier1.document_id, agent_id=tier1.agent_id, run_id=tier1.run_id,
        generated_at=tier1.generated_at, rows=rows,
    )


_RISK_STATUS_LABELS = {
    MAPPED: "Riesgo y recomendación disponibles",
    NO_GAP_ASSESSMENT_DATA: "Sin gap-assessment narrativo asociado",
    NOT_MAPPABLE: "Gap-assessment narrativo existe pero no mapea",
}


def render_unified_finding_markdown(report: UnifiedFindingReport) -> str:
    """Funcion pura texto->texto, mismo patron que
    tier1_report.render_tier1_markdown() -- no escribe a disco."""
    lines = [
        f"# Informe unificado por hallazgo — {report.document_id}",
        "",
        f"Agente: `{report.agent_id}` · Run: `{report.run_id}` · Generado: {report.generated_at}",
        "",
        f"> {_COMPLIANCE_BANNER}",
        "",
        "## Detalle por requisito",
        "",
        "| Requisito | Estado | Evidencia / página | Riesgo | Recomendación | Fundamento |",
        "|---|---|---|---|---|---|",
    ]
    for r in report.rows:
        pagina = f" ({r.page_or_section})" if r.page_or_section else ""
        if r.bucket == CONFIRMED and r.evidence_quote:
            evidencia = f"«{r.evidence_quote}»{pagina}"
        elif r.review_queue_rc_id:
            evidencia = f"cola de revisión: `{r.review_queue_rc_id}`{pagina}"
        else:
            evidencia = pagina.strip() or "—"

        if r.risk_recommendation_status == MAPPED:
            riesgo = f"{r.change_risk} ({', '.join(r.change_risk_basis or [])})"
            recomendacion = r.proposed_content or "—"
            fundamento = r.change_reason or "—"
        elif r.risk_recommendation_status == NOT_MAPPABLE:
            riesgo = "—"
            recomendacion = "—"
            fundamento = f"NOT_MAPPABLE: {r.not_mappable_reason}"
        else:
            riesgo = "—"
            recomendacion = "—"
            fundamento = _RISK_STATUS_LABELS[NO_GAP_ASSESSMENT_DATA]

        estado = f"{_estado_label_row(r)} / {_RISK_STATUS_LABELS[r.risk_recommendation_status]}"
        lines.append(f"| {r.requirement_id} | {estado} | {evidencia} | {riesgo} | {recomendacion} | {fundamento} |")
    return "\n".join(lines) + "\n"


def _estado_label_row(row: UnifiedFindingRow) -> str:
    """Reutiliza tier1_report._estado_label() reconstruyendo el
    RequirementOutcome minimo que esa funcion necesita -- nunca duplica
    la logica de la etiqueta PROVISIONAL."""
    return _estado_label(RequirementOutcome(
        requirement_id=row.requirement_id, bucket=row.bucket, conclusion=row.conclusion,
    ))
