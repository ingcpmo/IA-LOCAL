"""Tier-1 asistido (D2, docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md §5,
firmado por Cesar 2026-08-11; plan: .claude/plans/wise-bubbling-toucan.md)
-- orquestador del "informe asistido": corre un documento completo contra
UN agente (modo BASELINE, `full_document_coverage=True`, cobertura real
del documento entero) y bucketiza cada requisito en 2 estados reales:

  CONFIRMED          -- DOCUMENTED_AND_SUPPORTED/PARTIALLY_DOCUMENTED, ya
                        anclado A/B/C/D por el verificador existente (esto
                        ES el eco léxico automatizable de D2(a) -- el
                        verificador ya exige match textual real, no hace
                        falta un clasificador nuevo).
  NEEDS_HUMAN_REVIEW -- todo lo demás con una pregunta de evidencia real
                        (SUPPORTING_EVIDENCE_UNDER_REVIEW,
                        DOCUMENTATION_GAP/PROVISIONAL_GAP,
                        EVALUATION_INCOMPLETE,
                        EVIDENCE_NOT_LOCATED_IN_CANDIDATES).
  NOT_APPLICABLE     -- fuera de alcance documental, sin pregunta de
                        evidencia.
  CROSS_REFERENCE    -- remite a otro documento, no es una ausencia.

NO hay bucket de "rechazo automático de falsos positivos" -- ese estado
no existe como conclusión independiente en el código (ANNEX11_4 se
resolvió siempre por adjudicación humana, nunca por un rechazo
estructural automático real); D2 se corrige a lo que el código realmente
soporta en vez de inventar un clasificador nuevo sin medir.

Gobernanza: MISMA familia `PILOT_EXECUTION` que ya usa `judgment.py`/
`corpus_runner.run_pilot_sample_batch` -- NUNCA `CORPUS_AUTHORIZATION`
(esa exige `run_corpus_batch`, regla dura "no corpus formal" sigue
vigente). Este módulo NUNCA se ejecuta contra un documento real por sí
solo -- necesita su propia `PILOT_EXECUTION` vigente con presupuesto,
igual que cualquier otra corrida real de este arco."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER, ModelProvider
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.corpus_runner import (
    PILOT_CHECKPOINT_DIR,
    PILOT_RUN_AGENT_VERSION,
    _PROMPT_PATH_BY_AGENT,
    _default_extractor,
    _resolve_document_path,
    _select_pilot_execution_instance,
)

CONFIRMED = "CONFIRMED"
NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
NOT_APPLICABLE = "NOT_APPLICABLE"
CROSS_REFERENCE = "CROSS_REFERENCE"

# PROVISIONALLY_DOCUMENTED/PROVISIONALLY_PARTIALLY_DOCUMENTED (§10,
# positive_conclusion_eligibility=PROVISIONAL_ONLY -- el estado real de
# gobernanza de fuente de la mayoría de los requisitos hoy) son el MISMO
# ancla de evidencia que DOCUMENTED_AND_SUPPORTED/PARTIALLY_DOCUMENTED,
# con el único caveat de que la fuente regulatoria en sí sigue pendiente
# de reverificación -- eso es ortogonal a si el eco léxico ancló (D2(a)),
# así que cuentan como CONFIRMED igual, con el flag SOURCE_PENDING_
# REVERIFICATION visible en review_flags para que el humano lo vea.
_CONFIRMED_CONCLUSIONS = frozenset({
    "DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED",
    "PROVISIONALLY_DOCUMENTED", "PROVISIONALLY_PARTIALLY_DOCUMENTED",
})
_NEEDS_REVIEW_CONCLUSIONS = frozenset({
    "SUPPORTING_EVIDENCE_UNDER_REVIEW", "DOCUMENTATION_GAP", "PROVISIONAL_GAP",
    "EVALUATION_INCOMPLETE", "EVIDENCE_NOT_LOCATED_IN_CANDIDATES",
})


class Tier1ReportError(Exception):
    pass


@dataclass
class RequirementOutcome:
    requirement_id: str
    bucket: str
    conclusion: str
    review_flags: list[str] = field(default_factory=list)
    evidence_quote: str | None = None
    page_or_section: str | None = None
    review_queue_rc_id: str | None = None


@dataclass
class Tier1Report:
    document_id: str
    agent_id: str
    run_id: str
    generated_at: str
    requirements: list[RequirementOutcome] = field(default_factory=list)

    def counts_by_bucket(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.requirements:
            counts[r.bucket] = counts.get(r.bucket, 0) + 1
        return counts


def _bucket_for_conclusion(conclusion: str) -> str:
    if conclusion in _CONFIRMED_CONCLUSIONS:
        return CONFIRMED
    if conclusion in _NEEDS_REVIEW_CONCLUSIONS:
        return NEEDS_HUMAN_REVIEW
    if conclusion == "NOT_APPLICABLE":
        return NOT_APPLICABLE
    if conclusion == "CROSS_REFERENCE_MISSING":
        return CROSS_REFERENCE
    # Fail-closed (mismo principio P1/TE-02 que el resto del proyecto):
    # una conclusión desconocida NUNCA se asume confirmada -- va a
    # revisión humana, nunca se pierde en silencio.
    return NEEDS_HUMAN_REVIEW


def generate_tier1_report(document_id: str, agent_id: str, *, document_type: str,
                          provider: ModelProvider | None = None,
                          checkpoint_dir: Path = PILOT_CHECKPOINT_DIR,
                          decision_store_file: Path | None = None) -> Tier1Report:
    """Corre el documento COMPLETO (todas sus páginas reales, vía
    `_default_extractor` -- mismo extractor pypdf ya usado por
    `run_pilot_sample_batch`) contra `agent_id`, modo BASELINE
    (`full_document_coverage=True`, sin `target_requirement_ids` -- evalúa
    TODO el catálogo aplicable). Gobernado por `PILOT_EXECUTION` vigente
    (hard-stop ANTES de gastar si no hay presupuesto, mismo mecanismo que
    protege cualquier otra corrida real de este arco)."""
    provider = provider or DEFAULT_PROVIDER
    selection = _select_pilot_execution_instance([document_id], decision_store_file=decision_store_file)
    max_calls = selection["payload"].get("max_calls")
    if not isinstance(max_calls, int) or max_calls <= 0:
        raise Tier1ReportError(f"PILOT_EXECUTION vigente sin max_calls válido: {max_calls!r}")

    status = mqg.evaluate_model_qualification(provider).status
    mqg.require_inference_authorized(status, call_type=mqg.CALL_TYPE_INFERENCE, run_context="pilot")

    path, doc_sha256 = _resolve_document_path(document_id)
    pages = _default_extractor(path)
    expected_calls = len(ce.build_page_chunks(pages))
    if expected_calls > max_calls:
        raise Tier1ReportError(
            f"documento requiere {expected_calls} llamadas, PILOT_EXECUTION vigente solo "
            f"autoriza {max_calls} -- nunca arranca una corrida a medias")

    checkpoint_store = ce.CheckpointStore(checkpoint_dir)
    result = ce.evaluate_chunked(
        _PROMPT_PATH_BY_AGENT[agent_id], agent_id=agent_id, agent_version=PILOT_RUN_AGENT_VERSION,
        per_unit_text=pages, sistema="tier1_report", documento=document_id,
        version="v1", archivo=str(path), document_sha256=doc_sha256,
        run_context="pilot", checkpoint_store=checkpoint_store,
        use_verified_pipeline=True, document_type=document_type,
        retry_technical_failures=True, provider=provider,
    )

    # requisito_regulatorio es "{req_id} — {label}" (chunked_engine.py), no
    # el req_id puro -- separar por el separador real, nunca asumir
    # igualdad exacta.
    findings_by_req = {f["requisito_regulatorio"].split(" — ")[0]: f for f in result["findings"]}

    from factory.layer9.human_review_queue import list_pending
    pending_by_req = {
        e["summary"]["requirement_id"]: e["rc_id"]
        for e in list_pending()
        if e.get("summary", {}).get("run_id") == result["run_id"]
    }

    requirements = []
    for req_id, vc in result["verified_conclusions"].items():
        bucket = _bucket_for_conclusion(vc["conclusion"])
        finding = findings_by_req.get(req_id)
        requirements.append(RequirementOutcome(
            requirement_id=req_id, bucket=bucket, conclusion=vc["conclusion"],
            review_flags=list(vc.get("review_flags") or []),
            evidence_quote=(finding.get("evidencia_exacta") or None) if bucket == CONFIRMED and finding else None,
            page_or_section=(finding.get("pagina_o_seccion") or None) if finding else None,
            review_queue_rc_id=pending_by_req.get(req_id) if bucket == NEEDS_HUMAN_REVIEW else None,
        ))

    return Tier1Report(
        document_id=document_id, agent_id=agent_id, run_id=result["run_id"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        requirements=sorted(requirements, key=lambda r: r.requirement_id),
    )


_COMPLIANCE_BANNER = (
    "Este informe es un BORRADOR ASISTIDO, no una declaración de "
    "cumplimiento. CONFIRMED significa que el verificador ancló una cita "
    "textual real -- sigue pendiente de sign-off humano final. Ningún "
    "requisito de este informe cierra CAPA, libera lote, ni constituye "
    "aprobación automática de documento (CLAUDE.md, sin excepción)."
)

_BUCKET_LABELS = {
    CONFIRMED: "Confirmado (anclado, pendiente de sign-off humano)",
    NEEDS_HUMAN_REVIEW: "Necesita revisión humana",
    NOT_APPLICABLE: "No aplica",
    CROSS_REFERENCE: "Remite a otro documento",
}


def render_tier1_markdown(report: Tier1Report) -> str:
    """Función pura texto→texto -- no escribe a disco (persistencia es
    una decisión de empaquetado posterior, fuera de alcance de este
    módulo). Reutiliza la nota de honestidad ya escrita para la cola R1.8
    (factory/layer9/human_review_queue._CANDIDATES_HONESTY_NOTE) en vez de
    redactar una nueva -- mismo texto, mismo compromiso."""
    from factory.layer9.human_review_queue import _CANDIDATES_HONESTY_NOTE

    lines = [
        f"# Informe Tier-1 asistido — {report.document_id}",
        "",
        f"Agente: `{report.agent_id}` · Run: `{report.run_id}` · Generado: {report.generated_at}",
        "",
        f"> {_COMPLIANCE_BANNER}",
        "",
        f"> Candidatos de recuperación semántica (cuando aplican): {_CANDIDATES_HONESTY_NOTE}",
        "",
        "## Resumen por bucket",
        "",
    ]
    counts = report.counts_by_bucket()
    for bucket, label in _BUCKET_LABELS.items():
        lines.append(f"- **{label}**: {counts.get(bucket, 0)}")
    lines += ["", "## Detalle por requisito", "",
              "| Requisito | Estado | Conclusión | Cita / referencia |",
              "|---|---|---|---|"]
    for r in report.requirements:
        detalle = ""
        if r.bucket == CONFIRMED and r.evidence_quote:
            pagina = f" (pág. {r.page_or_section})" if r.page_or_section else ""
            caveat = " [fuente pendiente de reverificación]" if "SOURCE_PENDING_REVERIFICATION" in r.review_flags else ""
            detalle = f"«{r.evidence_quote}»{pagina}{caveat}"
        elif r.bucket == NEEDS_HUMAN_REVIEW and r.review_queue_rc_id:
            detalle = f"cola de revisión: `{r.review_queue_rc_id}`"
        elif r.bucket == NEEDS_HUMAN_REVIEW:
            detalle = "sin entrada en cola (ver governed_exceptions del run)"
        lines.append(f"| {r.requirement_id} | {_BUCKET_LABELS[r.bucket]} | {r.conclusion} | {detalle} |")
    return "\n".join(lines) + "\n"
