"""W5 V2, Fase K -- aplicación gobernada de cambios
(GAP_DEVIATION_AND_REMEDIATION_MODEL.md sección 4).

Diagnóstico previo a esta fase: `gap_assessment_finding_mapper.py` fija
`candidate_application_status = "APPLIED_TO_DRAFT"` de forma
INCONDICIONAL para todo cambio mapeado (independiente de change_risk).
`remediation_package_service.record_exception_review()`/
`record_medium_risk_batch_decision()` registran la decisión humana en un
log separado (`exceptions`/`medium_risk_batch_decisions`) -- pero NADA
usaba esa decisión para determinar si un cambio realmente debía
incluirse en el documento candidato final. Sin este módulo, un cambio
HIGH_RISK rechazado individualmente por un humano se habría insertado
igual en `candidate_document_generator.generate_candidate_document()`,
violando la regla dura del plan: "los cambios PROPOSED_NOT_APPLIED /
EXCEPTION_REQUIRED / REJECTED_BY_VALIDATOR van al paquete de excepciones;
jamás se incorporan silenciosamente".

Este módulo resuelve, a partir del estado REAL de un paquete
(`remediation_package_service` state: changes + exceptions +
medium_risk_batch_decisions), el estado final de aplicación de cada
cambio, con estos 4 estados del plan:

  AUTO_APPLIED_TO_DRAFT   -- pasa TODOS los gates deterministas Y (LOW_RISK,
                             o MEDIUM_RISK ya cubierto por decisión de lote,
                             o HIGH_RISK con excepción REVISADA y aceptada).
                             Único estado que el candidato limpio incorpora.
  PROPOSED_NOT_APPLIED    -- MEDIUM_RISK aún sin decisión de lote que lo cubra.
  EXCEPTION_REQUIRED      -- HIGH_RISK aún sin excepción revisada.
  REJECTED_BY_VALIDATOR   -- falla un gate determinista (schema_validation_status
                             =FAILED o citation_anchor_status=NOT_VERIFIED) --
                             nunca se incluye, sin importar change_risk ni
                             decisión humana.

Interpretación explícita de esta fase (el plan no lo desambigua): un
HIGH_RISK con excepción revisada y ACEPTADA también se etiqueta
AUTO_APPLIED_TO_DRAFT -- el nombre denota "estado terminal que autoriza
incluirse en el candidato limpio", no "sin intervención humana"; la
intervención humana ya quedó registrada en el propio registro de
excepción (`exceptions[...]`), auditable por separado.

Convención de `human_review_decision` (antes de esta fase era texto libre
sin interpretación downstream, ver `golden_dataset_criteria.
check_no_pending_high_risk_without_exception`, que solo verificaba
presencia no vacía): un valor que empieza con 'accept' (case-insensitive,
p.ej. 'accept_risk', el único valor real usado hasta hoy) se interpreta
como ACEPTADO; cualquier otro valor no vacío se interpreta como
RECHAZADO explícitamente por el humano.

El ciclo de reintento "1 ciclo AGT-REM → AGT-QLT" (sección 4 del plan)
NO se implementa aquí -- AGT-QLT (validación de calidad del documento
completo) no existe todavía en ningún lado del código (confirmado en
CURRENT_AGENT_RUNTIME_AUDIT.md y en el diagnóstico de esta fase).
Declarado explícitamente NOT_IMPLEMENTED_YET, no simulado."""
from __future__ import annotations

from dataclasses import dataclass, field

RETRY_CYCLE_STATUS = "NOT_IMPLEMENTED_YET"
RETRY_CYCLE_REASON = "AGT-QLT no existe todavia -- el ciclo de reintento AGT-REM -> AGT-QLT no puede ejecutarse con logica real."


@dataclass(frozen=True)
class ChangeApplicationResolution:
    change_id: str
    change_risk: str
    final_status: str
    included_in_clean_candidate: bool
    reason: str


def _gates_pass(change: dict) -> tuple[bool, str]:
    if change.get("schema_validation_status") == "FAILED":
        return (False, "schema_validation_status=FAILED")
    if change.get("citation_anchor_status") == "NOT_VERIFIED":
        return (False, "citation_anchor_status=NOT_VERIFIED")
    return (True, "")


def _human_review_accepted(human_review_decision: str) -> bool:
    return human_review_decision.strip().lower().startswith("accept")


def resolve_change_application(change: dict, package_state: dict) -> ChangeApplicationResolution:
    """change: un RemediationChange real (ver remediation_package_schemas.py).
    package_state: el dict de estado real de remediation_package_service.py
    (con 'exceptions' y 'medium_risk_batch_decisions'; 'package.changes'
    para saber a qué bucket de riesgo pertenece este change_id -- no se
    reinfiere el riesgo aqui, se confia en cambio['change_risk'] ya
    calculado por compute_change_risk())."""
    change_id = change["change_id"]
    risk = change["change_risk"]

    gates_ok, gate_failure_reason = _gates_pass(change)
    if not gates_ok:
        return ChangeApplicationResolution(
            change_id, risk, "REJECTED_BY_VALIDATOR", False,
            f"gate determinista fallido: {gate_failure_reason}",
        )

    if risk == "LOW_RISK":
        return ChangeApplicationResolution(
            change_id, risk, "AUTO_APPLIED_TO_DRAFT", True,
            "LOW_RISK con gates deterministas en PASS -- autoaplicacion gobernada",
        )

    if risk == "MEDIUM_RISK":
        covered = any(
            change_id in batch["covered_change_ids"]
            for batch in package_state.get("medium_risk_batch_decisions", {}).values()
        )
        if covered:
            return ChangeApplicationResolution(
                change_id, risk, "AUTO_APPLIED_TO_DRAFT", True,
                "MEDIUM_RISK cubierto por decision de lote humana",
            )
        return ChangeApplicationResolution(
            change_id, risk, "PROPOSED_NOT_APPLIED", False,
            "MEDIUM_RISK aun sin decision de lote que lo cubra",
        )

    if risk == "HIGH_RISK":
        exception = next(
            (e for e in package_state.get("exceptions", {}).values()
             if e["change_id"] == change_id and e.get("status") == "REVIEWED"),
            None,
        )
        if exception is None:
            return ChangeApplicationResolution(
                change_id, risk, "EXCEPTION_REQUIRED", False,
                "HIGH_RISK aun sin excepcion individual revisada",
            )
        if _human_review_accepted(exception["human_review_decision"]):
            return ChangeApplicationResolution(
                change_id, risk, "AUTO_APPLIED_TO_DRAFT", True,
                f"HIGH_RISK con excepcion revisada y aceptada ({exception['exception_id']})",
            )
        return ChangeApplicationResolution(
            change_id, risk, "PROPOSED_NOT_APPLIED", False,
            f"HIGH_RISK con excepcion revisada y RECHAZADA por el humano ({exception['exception_id']})",
        )

    return ChangeApplicationResolution(
        change_id, risk, "REJECTED_BY_VALIDATOR", False, f"change_risk desconocido: {risk!r}",
    )


def resolve_package_changes(package_state: dict) -> list[ChangeApplicationResolution]:
    return [
        resolve_change_application(change, package_state)
        for change in package_state["changes"].values()
    ]


def select_changes_for_clean_candidate(changes: list[dict], package_state: dict) -> list[dict]:
    """Filtro real para candidate_document_generator.generate_candidate_document()/
    generate_redline_document(): retorna SOLO los changes con estado final
    AUTO_APPLIED_TO_DRAFT -- nunca pasa la lista completa sin filtrar."""
    resolutions_by_id = {r.change_id: r for r in resolve_package_changes(package_state)}
    return [
        change for change in changes
        if resolutions_by_id.get(change["change_id"], ChangeApplicationResolution(
            change["change_id"], change.get("change_risk", "UNKNOWN"), "REJECTED_BY_VALIDATOR", False, "sin resolucion",
        )).included_in_clean_candidate
    ]
