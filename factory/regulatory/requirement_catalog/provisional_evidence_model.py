"""W5 V2, Fase C -- correccion del modelo de evidencia provisional
(2026-07-23, a pedido explicito de Cesar sobre la primera version de los
Evidence Packs CFR 11: una fuente PENDING_REVERIFICATION no debe detener
el pipeline completo -- debe habilitar analisis/borrador con trazabilidad
provisional, y bloquear exclusivamente conclusion formal/liberacion).

Dos gates independientes (regla dura, nunca fusionados):

  EXECUTION_GATE       -- permite continuar el pipeline (analisis, busqueda
                           de evidencia, generacion de REVIEW_DRAFT) con
                           copia local + sha256 + numeral + texto canonico +
                           schema validos, aunque la fuente siga
                           PENDING_REVERIFICATION.
  FORMAL_RELEASE_GATE   -- unico gate que habilita baseline formal,
                           candidato limpio y liberacion. Exige
                           source_verification_status=
                           LOCAL_CANONICAL_COPY_VERIFIED entre otros 10
                           criterios reales -- nunca se relaja.

Regla dura repetida en cada funcion de este modulo: NOT_EVALUATED,
NOT_DETERMINED y PENDING_REVERIFICATION nunca se convierten en PASS. Un
resultado "positivo" bajo fuente pendiente de reverificacion solo puede
ser PROVISIONAL -- la promocion a resultado final es siempre un acto
humano explicito (ver build_reverification_diff_report), nunca
automatico."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# PART11_APPLICABILITY_V1 -- perfil de aplicabilidad EXCLUSIVO de la familia
# 21 CFR Part 11. No se aplica a ningun requisito que no lo referencie
# explicitamente via applicability_profile_ref (ANNEX11/ALCOA no lo usan).
# ---------------------------------------------------------------------------

PART11_APPLICABILITY_PROFILE_ID = "PART11_APPLICABILITY_V1"

_VALID_SCOPE_STATUS = {"IN_SCOPE", "OUT_OF_SCOPE", "NOT_DETERMINED"}
_VALID_APPLICABILITY_STATUS = {"APPLICABLE", "NOT_APPLICABLE", "NOT_DETERMINED"}


class ProvisionalEvidenceModelError(Exception):
    """Fail-closed: entrada invalida o intento de violar una regla dura del
    modelo de evidencia provisional."""


def resolve_part11_applicability(part11_scope_status: str, predicate_rule_id: str) -> str:
    """Regla determinista unica -- NO existe CONDITIONAL:
      OUT_OF_SCOPE                                -> NOT_APPLICABLE
      IN_SCOPE + predicate_rule_id determinado     -> APPLICABLE
      IN_SCOPE + predicate_rule_id NOT_DETERMINED  -> NOT_DETERMINED
      NOT_DETERMINED                               -> NOT_DETERMINED
    predicate_rule_id "determinado" = no vacio y distinto de 'NOT_DETERMINED'."""
    if part11_scope_status not in _VALID_SCOPE_STATUS:
        raise ProvisionalEvidenceModelError(f"part11_scope_status invalido: {part11_scope_status!r}")

    if part11_scope_status == "OUT_OF_SCOPE":
        return "NOT_APPLICABLE"
    if part11_scope_status == "NOT_DETERMINED":
        return "NOT_DETERMINED"
    # IN_SCOPE
    predicate_determined = bool(predicate_rule_id) and predicate_rule_id != "NOT_DETERMINED"
    return "APPLICABLE" if predicate_determined else "NOT_DETERMINED"


# ---------------------------------------------------------------------------
# Resultados permitidos/prohibidos mientras la fuente esta PENDING_REVERIFICATION
# ---------------------------------------------------------------------------

ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION = frozenset({
    "PROVISIONALLY_DOCUMENTED",
    "PROVISIONALLY_PARTIALLY_DOCUMENTED",
    "PROVISIONAL_GAP",
    "PROVISIONAL_DEVIATION",
    "SOURCE_REVERIFICATION_REQUIRED",
    "EVALUATION_INCOMPLETE",
    "NOT_APPLICABLE",
})

# NOT_APPLICABLE solo es legal si la aplicabilidad fue determinada por una
# regla independiente y aprobada (resolve_part11_applicability), nunca
# declarado a mano -- validate_result_status_allowed lo exige explicito.
PROHIBITED_FINAL_RESULTS_WHILE_PENDING = frozenset({
    "DOCUMENTED_AND_SUPPORTED",
    "DOCUMENTATION_GAP",
    "GAP_CLOSED",
    "REGULATORY_COMPLIANCE_CONFIRMED",
})

_NEVER_PASS_STATES = frozenset({"NOT_EVALUATED", "NOT_DETERMINED", "PENDING_REVERIFICATION"})


def validate_result_status_allowed(
    result_status: str,
    source_verification_status: str,
    *,
    applicability_determined_by_independent_rule: bool = False,
) -> None:
    """Lanza ProvisionalEvidenceModelError si result_status viola las
    reglas duras del modelo. No retorna nada en el caso valido (fail-closed
    por excepcion, mismo patron que requirement_catalog_loader)."""
    if source_verification_status != "PENDING_REVERIFICATION":
        return  # fuera del alcance de este guardia -- LOCAL_CANONICAL_COPY_VERIFIED no restringe aqui

    if result_status in PROHIBITED_FINAL_RESULTS_WHILE_PENDING:
        raise ProvisionalEvidenceModelError(
            f"resultado final prohibido con source_verification_status=PENDING_REVERIFICATION: "
            f"{result_status!r}"
        )
    if result_status == "NOT_APPLICABLE" and not applicability_determined_by_independent_rule:
        raise ProvisionalEvidenceModelError(
            "NOT_APPLICABLE solo es valido con fuente pendiente de reverificacion cuando la "
            "aplicabilidad fue determinada por una regla independiente y aprobada "
            "(applicability_determined_by_independent_rule=True) -- nunca declarado a mano."
        )
    if result_status not in ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION:
        raise ProvisionalEvidenceModelError(
            f"resultado {result_status!r} no esta en la lista permitida mientras la fuente "
            f"este PENDING_REVERIFICATION: {sorted(ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION)}"
        )


def assert_never_silently_promoted_to_pass(status: str) -> None:
    """Guardia explicita: NOT_EVALUATED/NOT_DETERMINED/PENDING_REVERIFICATION
    nunca son 'PASS'. Se usa como control adicional en cualquier punto del
    pipeline que compute un status final a partir de un status intermedio."""
    if status == "PASS":
        return
    if status in _NEVER_PASS_STATES:
        raise ProvisionalEvidenceModelError(
            f"{status!r} no puede convertirse en PASS -- degradacion silenciosa prohibida."
        )


@dataclass(frozen=True)
class ProvisionalAnnotation:
    source_verification_status: str
    source_id: str
    source_sha256: str
    official_url: str
    limitation_code: str
    result_authority: str
    requires_source_reverification: bool


def build_provisional_annotation(
    *, source_verification_status: str, source_id: str, source_sha256: str, official_url: str,
) -> ProvisionalAnnotation | None:
    """Retorna None si la fuente ya esta LOCAL_CANONICAL_COPY_VERIFIED (no
    hace falta anotar limitacion). Si esta PENDING_REVERIFICATION, retorna
    la anotacion obligatoria que toda salida dependiente debe adjuntar."""
    if source_verification_status != "PENDING_REVERIFICATION":
        return None
    return ProvisionalAnnotation(
        source_verification_status=source_verification_status,
        source_id=source_id,
        source_sha256=source_sha256,
        official_url=official_url,
        limitation_code="SOURCE_PENDING_REVERIFICATION",
        result_authority="PROVISIONAL",
        requires_source_reverification=True,
    )


# ---------------------------------------------------------------------------
# EXECUTION_GATE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateCheckResult:
    criterion: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ExecutionGateResult:
    checks: list[GateCheckResult]

    @property
    def gate_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_criteria(self) -> list[str]:
        return [c.criterion for c in self.checks if not c.passed]


def evaluate_execution_gate(
    *, has_local_copy: bool, has_sha256: bool, has_clause: bool,
    has_canonical_text: bool, has_valid_schema: bool,
    requirement_id: str, source_id: str,
    decision_store_file: Path | None = None,
) -> ExecutionGateResult:
    """A proposito NO evalua source_verification_status -- ese es el punto
    central de aquella correccion: PENDING_REVERIFICATION no debe bloquear
    este gate, y eso NO se revierte aqui.

    W5 V2 G1.8 anade una dimension DISTINTA, que no existia: la cobertura
    humana. Son cosas separadas y no deben colapsarse:

      PENDIENTE DE VERIFICAR   estado tecnico. No bloquea el trabajo
                               provisional -- la copia local esta integra y se
                               puede razonar sobre ella con la limitacion
                               declarada.
      NO AUTORIZADA POR UN HUMANO   estado de gobernanza. Si bloquea, incluso
                               lo provisional: nadie firmo que ese pack o esa
                               fuente se pudieran tocar.

    `requirement_id` y `source_id` son OBLIGATORIOS. Hacerlos opcionales con
    un default permisivo convertiria la guardia en decorativa: bastaria con
    no pasarlos.
    """
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        evaluate_pack_eligibility,
    )
    eligibility = evaluate_pack_eligibility(
        requirement_id, decision_store_file=decision_store_file)

    checks = [
        GateCheckResult("copia_local_disponible", has_local_copy, "local_copy presente"),
        GateCheckResult("sha256_disponible", has_sha256, "source_sha256 presente"),
        GateCheckResult("numeral_identificado", has_clause, "clause presente"),
        GateCheckResult("texto_canonico_disponible", has_canonical_text, "canonical_text presente"),
        GateCheckResult("schema_valido", has_valid_schema, "entrada valida contra requirement_catalog_entry_v1"),
        GateCheckResult(
            "cobertura_de_decision_humana",
            eligibility.pack_use_allowed,
            "; ".join(eligibility.denial_reasons) or
            f"D2={eligibility.pack_coverage_basis} D1={eligibility.source_coverage_basis}",
        ),
    ]
    return ExecutionGateResult(checks=checks)


# ---------------------------------------------------------------------------
# FORMAL_RELEASE_GATE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FormalReleaseGateResult:
    checks: list[GateCheckResult]

    @property
    def gate_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_criteria(self) -> list[str]:
        return [c.criterion for c in self.checks if not c.passed]


def evaluate_formal_release_gate(
    *,
    source_verification_status: str,
    official_url_verified: bool,
    local_copy_exists: bool,
    source_sha256_matches: bool,
    canonical_text_validated: bool,
    clause_validated: bool,
    citation_sha256_valid: bool,
    golden_dataset_no_critical_regressions: bool,
    gate_0_green: bool,
    open_critical_contradictions: int,
    unresolved_critical_exceptions: int,
    requirement_id: str,
    decision_store_file: Path | None = None,
) -> FormalReleaseGateResult:
    """Evalua TODOS los criterios sin detenerse en el primero (mismo patron
    que evaluate_corrected_document_generation_gate, Fase N) -- el caller
    necesita ver la lista completa de lo que falta.

    W5 V2 G1.8: `evidence_pack_approved_by_human` DESAPARECE como parametro.
    Era un booleano que el llamador declaraba, es decir, exactamente el
    anti-patron que la auditoria encontro en `applicability_matrix.yaml`
    (`approval.status: human_confirmed` escrito a mano sobre filas que la
    decision no cubria). Ahora se CALCULA con el resolver: quien invoque este
    gate no puede afirmar que un pack esta aprobado, solo el registro de
    decisiones puede.
    """
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        evaluate_pack_eligibility,
    )
    eligibility = evaluate_pack_eligibility(
        requirement_id, decision_store_file=decision_store_file)
    checks = [
        GateCheckResult(
            "source_verification_status_verificado",
            source_verification_status == "LOCAL_CANONICAL_COPY_VERIFIED",
            f"source_verification_status={source_verification_status!r}",
        ),
        GateCheckResult("url_oficial_verificada", official_url_verified, "official_url_verified"),
        GateCheckResult("local_copy_existente", local_copy_exists, "local_copy_exists"),
        GateCheckResult("source_sha256_coincidente", source_sha256_matches, "source_sha256_matches"),
        GateCheckResult("canonical_text_validado", canonical_text_validated, "canonical_text_validated"),
        GateCheckResult("clause_validada", clause_validated, "clause_validated"),
        GateCheckResult("citation_sha256_valido", citation_sha256_valid, "citation_sha256_valid"),
        GateCheckResult(
            "evidence_pack_aprobado_por_identidad_humana_real",
            eligibility.pack_decision_authorized,
            f"D2/{requirement_id}: {eligibility.pack_coverage_basis}",
        ),
        GateCheckResult(
            "fuente_cubierta_por_decision_humana",
            eligibility.source_decision_authorized,
            f"D1/{eligibility.source_id}: {eligibility.source_coverage_basis}",
        ),
        GateCheckResult(
            "golden_dataset_sin_regresiones_criticas",
            golden_dataset_no_critical_regressions, "golden_dataset_no_critical_regressions",
        ),
        GateCheckResult("gate_0_en_verde", gate_0_green, "gate_0_green"),
        GateCheckResult(
            "cero_contradicciones_criticas_abiertas",
            open_critical_contradictions == 0, f"open_critical_contradictions={open_critical_contradictions}",
        ),
        GateCheckResult(
            "cero_excepciones_criticas_no_resueltas",
            unresolved_critical_exceptions == 0, f"unresolved_critical_exceptions={unresolved_critical_exceptions}",
        ),
    ]
    return FormalReleaseGateResult(checks=checks)


# ---------------------------------------------------------------------------
# Elegibilidad de correcciones/remediaciones sobre fuente provisional
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RemediationEligibilityResult:
    status: str  # AUTO_APPLIED_TO_REVIEW_DRAFT | PROPOSED_NOT_APPLIED | EXCEPTION_REQUIRED
    provisional_source: bool
    source_reverification_required: bool
    eligible_for_clean_candidate: bool
    eligible_for_release: bool
    reason: str


def classify_remediation_eligibility(
    *, change_risk: str, has_uncertainty: bool, provisional_source: bool,
) -> RemediationEligibilityResult:
    """LOW_RISK sin incertidumbre y con todos los controles disponibles en
    PASS -> AUTO_APPLIED_TO_REVIEW_DRAFT (nunca CLEAN_CANDIDATE/RELEASE
    mientras provisional_source=True, sin importar el riesgo). MEDIUM_RISK
    o con incertidumbre -> PROPOSED_NOT_APPLIED. HIGH_RISK -> siempre
    EXCEPTION_REQUIRED, independiente de la fuente."""
    if change_risk == "HIGH_RISK":
        status = "EXCEPTION_REQUIRED"
        reason = "HIGH_RISK exige excepcion individual, independiente del estado de la fuente"
    elif change_risk == "MEDIUM_RISK" or has_uncertainty:
        status = "PROPOSED_NOT_APPLIED"
        reason = "MEDIUM_RISK o incertidumbre real -- no se autoaplica"
    elif change_risk == "LOW_RISK":
        status = "AUTO_APPLIED_TO_REVIEW_DRAFT"
        reason = "LOW_RISK con todos los controles disponibles en PASS -- borrador de revision trazable"
    else:
        raise ProvisionalEvidenceModelError(f"change_risk desconocido: {change_risk!r}")

    return RemediationEligibilityResult(
        status=status,
        provisional_source=provisional_source,
        source_reverification_required=provisional_source,
        eligible_for_clean_candidate=False if provisional_source else (status == "AUTO_APPLIED_TO_REVIEW_DRAFT"),
        eligible_for_release=False if provisional_source else False,  # release siempre requiere FORMAL_RELEASE_GATE aparte
        reason=reason,
    )


# ---------------------------------------------------------------------------
# operational_processing_coverage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoverageReport:
    applicable_total: int
    processed_total: int
    coverage: float
    meets_target: bool
    pending_ids: list[str]
    silent_omissions: list[str]

    TARGET = 0.95


def compute_operational_processing_coverage(
    applicable_requirement_ids: list[str],
    processed_requirement_ids: list[str],
    pending_with_reason: dict[str, str],
) -> CoverageReport:
    """requisitos aplicables procesados con resultado estructurado /
    requisitos aplicables totales. Representa cobertura de PROCESAMIENTO,
    nunca cumplimiento regulatorio. silent_omissions = aplicables NO
    procesados que ademas no tienen motivo registrado en
    pending_with_reason -- si esta lista no esta vacia, el paquete QA es
    invalido por diseno (nunca se permite un pendiente sin estado/motivo)."""
    applicable = set(applicable_requirement_ids)
    processed = set(processed_requirement_ids) & applicable
    pending = applicable - processed
    silent_omissions = sorted(rid for rid in pending if rid not in pending_with_reason)

    total = len(applicable)
    coverage = (len(processed) / total) if total else 0.0

    return CoverageReport(
        applicable_total=total,
        processed_total=len(processed),
        coverage=coverage,
        meets_target=coverage >= CoverageReport.TARGET,
        pending_ids=sorted(pending),
        silent_omissions=silent_omissions,
    )


# ---------------------------------------------------------------------------
# Promocion de resultado provisional a final -- SIEMPRE humana, nunca automatica
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReverificationDiffReport:
    requirement_id: str
    provisional_result: str
    new_result: str
    changed: bool
    requires_human_authorization: bool
    promoted: bool


def build_reverification_diff_report(
    requirement_id: str, provisional_result: str, new_result_after_reverification: str,
) -> ReverificationDiffReport:
    """Se invoca DESPUES de: reejecutar validacion B, invalidar cache del
    estado anterior, y recalcular resultados dependientes (pasos que viven
    fuera de este modulo, en el pipeline real de validacion). Esta funcion
    solo compara y deja constancia -- `promoted` es SIEMPRE False aqui;
    la promocion real a RELEASED es un acto humano separado y explicito,
    nunca un efecto secundario de este calculo."""
    return ReverificationDiffReport(
        requirement_id=requirement_id,
        provisional_result=provisional_result,
        new_result=new_result_after_reverification,
        changed=provisional_result != new_result_after_reverification,
        requires_human_authorization=True,
        promoted=False,
    )
