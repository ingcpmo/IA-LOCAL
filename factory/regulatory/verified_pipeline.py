"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.3 — orquestacion verificada por
requisito x documento.

Flujo (por requisito, sobre los chunks relevantes ya filtrados por la
matriz de aplicabilidad -- Fase 3):

  1. Por cada chunk relevante:
       generate_controlled()               -> llm_output + execution_manifest
       validate_against(finding_llm_v1)     [fail-closed, ya ocurre DENTRO
                                              de generate_controlled]
       verify_llm_output(...)               -> VerificationResult
       construir finding_record_v1 (dict)
  2. absence_consolidator.consolidate(...)  -> DocumentConclusion
  3. Resumen: verified / with_deviation / review_required / rejected /
     conclusion / flags pendientes

IMPORTANTE -- estado de integracion real (ver
factory/docs/W5v2_FASE0_INVENTARIO.md discrepancia #1): esta orquestacion
NO esta todavia cableada dentro del POST HTTP de produccion
(chunked_engine.evaluate_chunked()). Motivo, verificado, no supuesto:

  (a) Los prompts YAML vigentes (factory/engines/gmpai_integrity/prompts/
      *.yaml) piden al modelo 'estado' (cumple/no_cumple/...) directamente,
      no 'chunk_observation'. Cablear run_verified_evaluation() en el
      endpoint real sin reescribir esos prompts significa pedirle al
      modelo un contrato (finding_llm_v1) que el prompt actual no
      describe -- el modelo seguiria respondiendo con 'estado' y
      generate_controlled() lo rechazaria sistematicamente (0% verified),
      degradando el pipeline de produccion en vez de mejorarlo.
  (b) La matriz de aplicabilidad real (Fase 3, `applicability_value` por
      requisito x tipo documental) todavia no existe como dato
      estructurado -- hoy vive solo como texto narrativo en los reportes
      del piloto B, generado manualmente fuera del motor (ver
      W5v2_FASE0_INVENTARIO.md §5).

Por eso este modulo es funcional y probado de forma aislada (Bloque 2.4),
listo para cablearse en cuanto Fase 3 entregue la matriz de aplicabilidad
y se autorice la reescritura de los prompts YAML -- pero cablearlo HOY
en el POST real violaria P1 (fail-closed no significa 'fallar todo
silenciosamente por un contrato que el prompt no cumple') sin que nadie lo
haya pedido explicitamente.

W5 V2 G1.9 -- CONSUMIDOR C-3 del DecisionScopeResolver
------------------------------------------------------
Este modulo es el que GASTA inferencia (`generate_fn`), asi que la cobertura
de decision se comprueba en los dos sitios donde puede empezar ese gasto:

  - `evaluate_document()`: filtra ANTES del bucle, para que el plan quede
    completo y el requisito excluido aparezca DECLARADO con su motivo.
  - `evaluate_requirement_over_chunks()`: guardia dura donde de verdad se
    llama a `generate_fn`. Sin ella, llamar a esta funcion directamente
    esquivaria el filtro de arriba.

Un requisito sin cobertura sale **EVALUATION_INCOMPLETE** con el flag
`DECISION_COVERAGE_MISSING`. Nunca DOCUMENTATION_GAP: no estar autorizado a
mirar un requisito no es evidencia de que el documento lo incumpla. Y nunca
se omite en silencio -- va a `terminal_results` y a `excluded_by_decision`.

La comprobacion va ANTES de `pre_inference_filter`, no despues: si nadie
firmo que ese pack se pueda usar, no procede consultar siquiera su
aplicabilidad documental -- que ademas se lee de una matriz cuya propia
aprobacion esta en cuestion (hallazgo A-7)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import evidence_verifier
from .absence_consolidator import DocumentConclusion, consolidate
from .applicability import applicability, document_type_guard, known_requirement_ids, pre_inference_filter
from .evidence_verifier import VerificationResult, verify_llm_output

DECISION_COVERAGE_FLAG = "DECISION_COVERAGE_MISSING"


@dataclass
class RequirementEvaluationSummary:
    requirement_id: str
    document_type: str
    conclusion: DocumentConclusion
    records: list = field(default_factory=list)
    verified_count: int = 0
    verified_with_deviation_count: int = 0
    review_required_count: int = 0
    rejected_count: int = 0
    pending_review_flags: list = field(default_factory=list)


def _build_finding_record(record_id: str, llm_output: dict | None,
                           execution_manifest: dict,
                           verification: VerificationResult) -> dict:
    return {
        "record_id": record_id,
        "llm_output": llm_output,
        "execution_manifest": execution_manifest,
        "verification": {
            "checks": verification.checks,
            "review_flags": verification.review_flags,
        },
        "status": verification.status,
        "rejection_reason": verification.rejection_reason,
        "review_flags": verification.review_flags,
    }


def _decision_blocked_summary(requirement_id: str, document_type: str,
                              eligibility) -> RequirementEvaluationSummary:
    """Requisito no autorizado: NO EVALUADO, nunca incumplido.

    EVALUATION_INCOMPLETE y no un valor nuevo porque ya pertenece al
    vocabulario permitido (ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION) y
    los validadores aguas abajo lo conocen. Lo que aporta el flag es el
    MOTIVO real: sin el, `NO_VALID_RECORDS` diria que no hubo evidencia
    valida, cuando lo que pasa es que nadie autorizo mirarla.
    """
    conclusion = DocumentConclusion(
        requirement_id=requirement_id,
        document_type=document_type,
        conclusion="EVALUATION_INCOMPLETE",
        review_flags=[DECISION_COVERAGE_FLAG, *eligibility.denial_reasons],
    )
    return RequirementEvaluationSummary(
        requirement_id=requirement_id,
        document_type=document_type,
        conclusion=conclusion,
        pending_review_flags=[DECISION_COVERAGE_FLAG],
    )


def evaluate_requirement_over_chunks(
    requirement_id: str,
    document_type: str,
    applicability_value: str,
    relevant_chunks: list,
    known_requirement_ids: set,
    generate_fn,
    prompt: str,
    *,
    decision_store_file: Path | None = None,
) -> RequirementEvaluationSummary:
    """generate_fn: callable(prompt, chunk) -> dict identico al contrato de
    ollama_client.generate_controlled() (inyectado para poder probarse sin
    Ollama real, y para no atar este modulo a un cliente concreto).

    Guardia dura: sin cobertura de decision, `generate_fn` no se llama ni una
    vez. Es el punto donde se gasta inferencia, asi que es donde tiene que
    estar la guardia -- igual que en `source_currency_checker` la comprobacion
    precede al acceso HTTP.
    """
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        evaluate_pack_eligibility,
    )
    eligibility = evaluate_pack_eligibility(
        requirement_id, decision_store_file=decision_store_file)
    if not eligibility.pack_use_allowed:
        return _decision_blocked_summary(requirement_id, document_type, eligibility)

    requirement_terms = evidence_verifier.load_requirement_terms(requirement_id)
    records: list[dict] = []

    for chunk in relevant_chunks:
        gen = generate_fn(prompt, chunk)
        llm_output = gen["llm_output"]

        if not gen["ok"] or llm_output is None:
            # Rechazado por schema-gate (Fase 1) antes de llegar al
            # verificador -- se conserva igual para trazabilidad (P1, y
            # Bloque 2.3: "Registros rejected_by_verifier ... SIEMPRE se
            # conservan").
            verification = VerificationResult(
                status="rejected_by_verifier",
                # Fase 5.4.4: gen["rejection_reason"] ya viene clasificado
                # por generate_controlled() (json_parse_failed/
                # schema_validation_failed/ollama_transport_failed) -- el
                # fallback anterior enmascaraba las otras 2 causas.
                rejection_reason=gen.get("rejection_reason"),
            )
            records.append(_build_finding_record(
                f"rec-{uuid.uuid4().hex[:12]}", None,
                gen["execution_manifest"], verification,
            ))
            continue

        verification = verify_llm_output(
            llm_output, chunk, known_requirement_ids, requirement_terms,
        )
        records.append(_build_finding_record(
            f"rec-{uuid.uuid4().hex[:12]}", llm_output,
            gen["execution_manifest"], verification,
        ))

    # W5.5: relevant_chunks es, por contrato de este modulo (ver docstring
    # arriba), el conjunto COMPLETO de chunks relevantes ya filtrados por
    # la matriz de aplicabilidad -- no un subconjunto parcial.
    conclusion = consolidate(requirement_id, document_type, applicability_value, records,
                              coverage_complete=True)

    summary = RequirementEvaluationSummary(
        requirement_id=requirement_id,
        document_type=document_type,
        conclusion=conclusion,
        records=records,
    )
    for r in records:
        if r["status"] == "verified":
            summary.verified_count += 1
        elif r["status"] == "verified_with_deviation":
            summary.verified_with_deviation_count += 1
        elif r["status"] == "review_required":
            summary.review_required_count += 1
            summary.pending_review_flags.extend(r["review_flags"])
        elif r["status"] == "rejected_by_verifier":
            summary.rejected_count += 1

    return summary


# ---------------------------------------------------------------------------
# Fase 3, Bloque 3.2/3.4 — filtro pre-inferencia + guardia de tipo
# documental, a nivel de documento completo.
# ---------------------------------------------------------------------------

@dataclass
class DocumentEvaluationResult:
    document_type: str
    document_type_confirmed: bool
    terminal_results: list = field(default_factory=list)   # OUT_OF_DOCUMENT_SCOPE / APPLICABILITY_REVIEW_REQUIRED / DECISION_COVERAGE_MISSING
    requirement_summaries: list = field(default_factory=list)  # RequirementEvaluationSummary
    review_queue: list = field(default_factory=list)        # requirement_id que quedaron pendientes
    document_level_flags: list = field(default_factory=list)
    # G1.9: requisitos apartados del plan por falta de cobertura humana. Lista
    # propia y no mezclada con review_queue: "pendiente de juicio humano sobre
    # la evidencia" y "nadie firmo que se pueda mirar" son cosas distintas.
    excluded_by_decision: list = field(default_factory=list)

    @property
    def inference_eligible_requirement_ids(self) -> list:
        """Los que de verdad consumiran presupuesto. Lo que el planificador
        debe contar para `max_calls` -- un requisito excluido no cuesta nada
        y no puede inflar la estimacion de D4-A."""
        return [s.requirement_id for s in self.requirement_summaries]


def evaluate_document(
    document_type: str,
    document_type_source: str,
    document_type_confidence: float | None,
    relevant_chunks_by_requirement: dict,
    generate_fn,
    prompt_by_requirement: dict,
    requirement_ids: set | None = None,
    *,
    decision_store_file: Path | None = None,
) -> DocumentEvaluationResult:
    """Orquesta un documento completo: matriz de aplicabilidad (Fase 3)
    ANTES de gastar ninguna llamada a Ollama, guardia de tipo documental
    (Bloque 3.4), y solo entonces evaluate_requirement_over_chunks (Fase 2)
    para los requisitos que sí requieren inferencia.

    relevant_chunks_by_requirement / prompt_by_requirement: dict
    requirement_id -> (chunks / prompt) ya resueltos por el llamador (esta
    función no conoce el motor de chunking, solo orquesta lo que Fase 1/2
    ya construyeron)."""
    guard = document_type_guard(document_type_source, document_type_confidence)
    doc_flags = list(guard["flags"])

    ids = requirement_ids if requirement_ids is not None else known_requirement_ids()
    result = DocumentEvaluationResult(
        document_type=document_type,
        document_type_confirmed=guard["confirmed"],
        document_level_flags=doc_flags,
    )

    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError,
        evaluate_pack_eligibility,
    )

    for requirement_id in sorted(ids):
        # Cobertura humana ANTES que aplicabilidad documental: si nadie firmo
        # que ese pack se pueda usar, no procede consultar su fila de la
        # matriz -- matriz cuya propia aprobacion, ademas, esta en cuestion.
        try:
            eligibility = evaluate_pack_eligibility(
                requirement_id, decision_store_file=decision_store_file)
        except CatalogValidationError:
            # requirement_id fuera del catalogo: no es una denegacion de
            # gobernanza, se deja al filtro de aplicabilidad como antes.
            eligibility = None

        if eligibility is not None and not eligibility.pack_use_allowed:
            result.terminal_results.append({
                "requirement_id": requirement_id,
                "conclusion": "EVALUATION_INCOMPLETE",
                "reason": DECISION_COVERAGE_FLAG,
                "denial_reasons": list(eligibility.denial_reasons),
                "source": "decision_scope_resolver",
                "document_level_flags": doc_flags,
            })
            result.excluded_by_decision.append(requirement_id)
            continue

        terminal = pre_inference_filter(requirement_id, document_type)
        if terminal is not None:
            terminal["document_level_flags"] = doc_flags
            result.terminal_results.append(terminal)
            if terminal["conclusion"] == "APPLICABILITY_REVIEW_REQUIRED":
                # P1: nunca se omite en silencio -- visible en review_queue.
                result.review_queue.append(requirement_id)
            continue

        app = applicability(requirement_id, document_type)

        summary = evaluate_requirement_over_chunks(
            requirement_id=requirement_id,
            document_type=document_type,
            applicability_value=app["value"],
            relevant_chunks=relevant_chunks_by_requirement.get(requirement_id, []),
            known_requirement_ids=ids,
            generate_fn=generate_fn,
            prompt=prompt_by_requirement.get(requirement_id, ""),
            decision_store_file=decision_store_file,
        )
        if not guard["confirmed"]:
            # Bloque 3.4: clasificacion documental dudosa -> TODAS las
            # conclusiones del documento heredan el flag, nunca limpias.
            summary.conclusion.review_flags.append("DOCUMENT_TYPE_UNCONFIRMED")
        result.requirement_summaries.append(summary)

    return result
