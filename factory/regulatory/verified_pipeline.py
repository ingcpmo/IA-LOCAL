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
factory/docs/W5v2_FASE0_INVENTARIO.md discrepancia #1 y
factory/docs/W5v2_FASE1_CIERRE.md): esta orquestacion NO esta todavia
cableada dentro del POST HTTP de produccion
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
haya pedido explicitamente."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from . import evidence_verifier
from .absence_consolidator import DocumentConclusion, consolidate
from .evidence_verifier import VerificationResult, verify_llm_output


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


def evaluate_requirement_over_chunks(
    requirement_id: str,
    document_type: str,
    applicability_value: str,
    relevant_chunks: list,
    known_requirement_ids: set,
    generate_fn,
    prompt: str,
) -> RequirementEvaluationSummary:
    """generate_fn: callable(prompt, chunk) -> dict identico al contrato de
    ollama_client.generate_controlled() (inyectado para poder probarse sin
    Ollama real, y para no atar este modulo a un cliente concreto)."""
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
                rejection_reason=gen.get("rejection_reason") or "schema_validation_failed",
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

    conclusion = consolidate(requirement_id, document_type, applicability_value, records)

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
