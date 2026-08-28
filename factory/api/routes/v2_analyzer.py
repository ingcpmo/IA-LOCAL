"""Endpoints Mission Control para el Analizador V2 (B9b / FASE 11).

Read-only. Extiende Mission Control con visibilidad de las corridas V2 sin
crear una segunda UI: sirven los artefactos persistidos por
`v2_runtime.run_v2_pipeline`. Cero inferencia, cero HTTP externo.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from factory.regulatory.validation_v2 import v2_mission_control as _mc

router = APIRouter(prefix="/api/v1/v2-analyzer", tags=["v2-analyzer"])


@router.get("/runs")
def list_runs():
    """Corridas V2 persistidas (resumen: run_id, project, counts, mark)."""
    return {"runs": _mc.list_v2_runs()}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """Manifest + audit metadata + package receipt + estado de revisión
    humana de una corrida V2."""
    try:
        return _mc.get_v2_run(run_id)
    except _mc.V2RunNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/runs/{run_id}/findings")
def get_findings(run_id: str, finding_class: str | None = None):
    """Findings persistidos por clase (regulatory | functional | technical),
    con evidencia anclada, risk, provenance, machine_state y human_state."""
    try:
        return _mc.get_v2_findings(run_id, finding_class)
    except _mc.V2RunNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str):
    try:
        return {"evidence": _mc.get_v2_evidence(run_id)}
    except _mc.V2RunNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/runs/{run_id}/remediation")
def get_remediation(run_id: str):
    """Propuestas de remediación (candidate / redline / manifest), todas
    MACHINE GENERATED -- BORRADOR, NO APROBADO."""
    try:
        return {"remediation": _mc.get_v2_remediation(run_id)}
    except _mc.V2RunNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/runs/{run_id}/report")
def get_report(run_id: str):
    """Informe final de usuario V2 (markdown, BORRADOR ASISTIDO)."""
    try:
        return Response(content=_mc.get_v2_report(run_id),
                        media_type="text/markdown; charset=utf-8")
    except _mc.V2RunNotFound as e:
        raise HTTPException(404, str(e))
