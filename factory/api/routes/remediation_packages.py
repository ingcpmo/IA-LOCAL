"""
BATCH_AND_EXCEPTION — endpoints internos de gestion de CandidatePackage.

Deliberadamente NO expone ningun endpoint de ReleaseRecord todavia (Fase 3
del ajuste aprobado): DOCUMENT_RELEASED permanece false y
PRODUCTION_ENABLEMENT permanece BLOCKED para todo lo que pasa por esta
capa -- create_release_record() existe en el servicio pero no se conecta
aqui a proposito.

  POST /api/v1/remediation-packages/{project_id}/{package_id}/{version}
      crear paquete (generacion automatica, sin aprobacion por chunk)
  GET  /api/v1/remediation-packages/{project_id}/{package_id}/{version}
      consultar estado completo del paquete
  POST .../{version}/exceptions/{change_id}
      registrar ExceptionReviewRecord (solo HIGH_RISK)
  POST .../{version}/medium-risk-batch
      registrar MediumRiskBatchDecision
  POST .../{version}/decision
      registrar PackageDecisionRecord
"""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from factory.services import remediation_package_service as svc
from factory.services.remediation_package_schemas import SchemaValidationError

router = APIRouter(prefix="/api/v1/remediation-packages", tags=["remediation-packages"])

# Errores de invariante/validacion del servicio -> 400 (peticion invalida).
# RemediationPackageNotFound se mapea aparte a 404.
_CLIENT_ERROR_TYPES = (
    SchemaValidationError,
    svc.DuplicateVersionError,
    svc.InvalidApplicationStatusError,
    svc.InvalidTransitionError,
    svc.MissingJustificationError,
    svc.UnknownChangeError,
    svc.InvalidExceptionError,
    svc.InvalidBatchError,
    svc.IncompleteExceptionCoverageError,
)


class CreatePackageBody(BaseModel):
    changes: list[dict]
    artifacts: dict
    automatic_evaluation_basis: dict
    generation_commit_sha: str
    superseded_from: str | None = None


class ExceptionReviewBody(BaseModel):
    human_review_decision: str
    responsible: str
    justification: str


class MediumRiskBatchBody(BaseModel):
    covered_change_ids: list[str]
    responsible: str
    justification: str


class PackageDecisionBody(BaseModel):
    decision: str
    decided_by: str
    justification: str
    medium_risk_batch_decision_id: str | None = None
    high_risk_exception_ids: list[str] | None = None


@router.post("/{project_id}/{package_id}/{version}", status_code=201)
def create_package(project_id: str, package_id: str, version: int, body: CreatePackageBody):
    """Genera el paquete automaticamente -- ningun chunk individual requiere
    aprobacion humana en este paso."""
    try:
        return svc.create_package(
            project_id=project_id, package_id=package_id, package_version=version,
            changes=body.changes, artifacts=body.artifacts,
            automatic_evaluation_basis=body.automatic_evaluation_basis,
            generation_commit_sha=body.generation_commit_sha, superseded_from=body.superseded_from,
        )
    except _CLIENT_ERROR_TYPES as e:
        raise HTTPException(400, str(e))


@router.get("/{project_id}/{package_id}/{version}")
def get_package(project_id: str, package_id: str, version: int):
    try:
        state = svc._read_state(project_id, package_id, version)
    except svc.RemediationPackageNotFound as e:
        raise HTTPException(404, str(e))
    return {
        "package": state["package"],
        "changes": state["changes"],
        "exceptions": state["exceptions"],
        "medium_risk_batch_decisions": state["medium_risk_batch_decisions"],
        "package_decision": state["package_decision"],
    }


@router.post("/{project_id}/{package_id}/{version}/exceptions/{change_id}", status_code=201)
def create_exception_review(project_id: str, package_id: str, version: int, change_id: str,
                             body: ExceptionReviewBody):
    try:
        return svc.record_exception_review(
            project_id=project_id, package_id=package_id, package_version=version, change_id=change_id,
            human_review_decision=body.human_review_decision, responsible=body.responsible,
            justification=body.justification,
        )
    except svc.RemediationPackageNotFound as e:
        raise HTTPException(404, str(e))
    except _CLIENT_ERROR_TYPES as e:
        raise HTTPException(400, str(e))


@router.post("/{project_id}/{package_id}/{version}/medium-risk-batch", status_code=201)
def create_medium_risk_batch_decision(project_id: str, package_id: str, version: int, body: MediumRiskBatchBody):
    try:
        return svc.record_medium_risk_batch_decision(
            project_id=project_id, package_id=package_id, package_version=version,
            covered_change_ids=body.covered_change_ids, responsible=body.responsible,
            justification=body.justification,
        )
    except svc.RemediationPackageNotFound as e:
        raise HTTPException(404, str(e))
    except _CLIENT_ERROR_TYPES as e:
        raise HTTPException(400, str(e))


@router.post("/{project_id}/{package_id}/{version}/decision", status_code=201)
def create_package_decision(project_id: str, package_id: str, version: int, body: PackageDecisionBody):
    try:
        return svc.record_package_decision(
            project_id=project_id, package_id=package_id, package_version=version,
            decision=body.decision, decided_by=body.decided_by, justification=body.justification,
            medium_risk_batch_decision_id=body.medium_risk_batch_decision_id,
            high_risk_exception_ids=body.high_risk_exception_ids,
        )
    except svc.RemediationPackageNotFound as e:
        raise HTTPException(404, str(e))
    # W5 V2 Fase P: doble-aprobacion real (409, idempotencia) se distingue
    # de un InvalidTransitionError generico (400, estado prematuro) --
    # PackageDecisionAlreadyRecordedError es subclase de InvalidTransitionError,
    # por eso debe capturarse ANTES que _CLIENT_ERROR_TYPES.
    except svc.PackageDecisionAlreadyRecordedError as e:
        raise HTTPException(409, str(e))
    except _CLIENT_ERROR_TYPES as e:
        raise HTTPException(400, str(e))
