"""
Capa 8 — Layer 8 Orchestrator (Tier-1: plan-only).

Orquesta el ciclo de diseño y planificación sin ejecutar Claude Code.
Se detiene antes de run_claude_code (implementado en F4.5c).

Stop conditions de lectura implementadas:
- stop_on_forbidden_path
- stop_on_product_base_change
- stop_on_missing_regulatory_source_for_required_claim
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.requirement_interpreter import generate_requirement_spec
from factory.layer8.agent_design_engine import generate_agent_design_proposal
from factory.layer8.regulatory_compliance_engine import (
    generate_regulatory_matrix,
    generate_corpus_manifest,
    generate_pending_documents,
    generate_compliance_assessment,
    validate_no_unsupported_regulatory_claims,
)
from factory.layer8.workspace_builder import create_workspace_from_mission
from factory.layer8.job_queue import create_job, move_job, complete_job, fail_job

MISSIONS_DIR = Path(__file__).parent.parent / "layer9" / "missions"
DESIGNS_DIR = Path(__file__).parent.parent / "designs"

FORBIDDEN_PATHS = [
    "/home/ing_cpmo/app",
    "/home/ing_cpmo/.env",
    "/home/ing_cpmo/docker-compose.yml",
    "/home/ing_cpmo/data",
    "/home/ing_cpmo/backups/pre_factory",
]

PRODUCT_BASE_MARKERS = ["gmp-api", "gmp-postgres", "gmp-redis", "aria-ollama"]


class StopConditionTriggered(Exception):
    """Condición de parada activada — la misión no puede continuar."""

    def __init__(self, condition: str, detail: str = ""):
        self.condition = condition
        self.detail = detail
        super().__init__(f"[STOP:{condition}] {detail}")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_mission(project_id: str) -> dict:
    path = MISSIONS_DIR / f"{project_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Misión '{project_id}' no encontrada en Capa 9.")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def stop_on_forbidden_path(text: str, project_id: str) -> None:
    """Lanza StopConditionTriggered si el texto referencia rutas prohibidas."""
    for fp in FORBIDDEN_PATHS:
        if fp in text:
            write_event("layer8_stop_condition_triggered", project_id, {
                "condition": "forbidden_path_detected",
                "path": fp,
            })
            raise StopConditionTriggered("forbidden_path_detected", f"Ruta prohibida detectada: {fp}")


def stop_on_product_base_change(text: str, project_id: str) -> None:
    """Lanza StopConditionTriggered si el texto indica cambios en el producto base."""
    text_lower = text.lower()
    for marker in PRODUCT_BASE_MARKERS:
        if marker in text_lower and ("modif" in text_lower or "cambiar" in text_lower or "edit" in text_lower):
            write_event("layer8_stop_condition_triggered", project_id, {
                "condition": "product_base_change_detected",
                "marker": marker,
            })
            raise StopConditionTriggered("product_base_change_detected", f"Cambio en base detectado: {marker}")


def stop_on_missing_regulatory_source(text: str, project_id: str) -> None:
    """Lanza StopConditionTriggered si se requiere fuente regulatoria no disponible."""
    result = validate_no_unsupported_regulatory_claims(text, source_id=project_id)
    if result.get("blocked"):
        write_event("layer8_stop_condition_triggered", project_id, {
            "condition": "regulatory_source_missing_for_required_claim",
            "reason": result.get("reason", ""),
        })
        raise StopConditionTriggered(
            "regulatory_source_missing_for_required_claim",
            result.get("reason", "Texto normativo detectado sin fuente PDF."),
        )


def _save_design_artifacts(project_id: str, artifacts: dict[str, Any]) -> str:
    """Guarda los artefactos de diseño en factory/designs/<project_id>/."""
    design_dir = DESIGNS_DIR / project_id
    design_dir.mkdir(parents=True, exist_ok=True)

    for name, content in artifacts.items():
        f = design_dir / f"{name}.yaml"
        with open(f, "w", encoding="utf-8") as fh:
            yaml.dump(content, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return str(design_dir)


def run_mission(project_id: str, plan_only: bool = True) -> dict[str, Any]:
    """
    Punto de entrada principal del orquestador.

    plan_only=True (default): ejecuta hasta generate_task_package y se DETIENE.
    No llama a run_claude_code (implementado en F4.5c).

    Retorna un dict con todos los artefactos generados y el comando manual.
    """
    job = create_job(project_id, "layer8_run_mission", {"plan_only": plan_only})
    job_id = job["job_id"]

    try:
        write_event("layer8_mission_started", project_id, {
            "plan_only": plan_only,
            "job_id": job_id,
        })
        move_job(job_id, "running")

        # 1. Cargar misión desde Capa 9
        mission = _load_mission(project_id)
        if mission.get("status") != "approved":
            raise StopConditionTriggered(
                "mission_not_approved",
                f"Misión '{project_id}' no está en estado approved (actual: {mission.get('status')}).",
            )

        objective_text = mission.get("objective", "")
        stop_on_forbidden_path(objective_text, project_id)
        stop_on_product_base_change(objective_text, project_id)

        # 2. Interpretar requerimiento
        spec = generate_requirement_spec(project_id, mission)

        # 3. Diseño de agentes
        agent_proposal = generate_agent_design_proposal(project_id, spec)

        # 4. Matriz regulatoria
        reg_matrix = generate_regulatory_matrix(spec)
        corpus_manifest = generate_corpus_manifest(spec)
        pending_docs = generate_pending_documents(spec)
        compliance = generate_compliance_assessment(spec)

        # 5. Workspace (idempotente — resume si existe)
        ws_result = create_workspace_from_mission(project_id, spec)

        # 6. Guardar artefactos de diseño
        artifacts = {
            "requirement_spec": spec.to_dict(),
            "agent_design_proposal": agent_proposal.to_dict(),
            "regulatory_matrix": reg_matrix,
            "corpus_manifest": corpus_manifest,
            "pending_documents": {"documents": pending_docs},
            "compliance_assessment": compliance,
        }
        design_dir = _save_design_artifacts(project_id, artifacts)

        # 7. Plan-only: preparar comando manual
        task_package = {
            "project_id": project_id,
            "workspace_path": ws_result.get("workspace_path", ""),
            "workspace_mode": ws_result.get("mode", "unknown"),
            "design_artifacts_path": design_dir,
            "manual_command": f"cd {ws_result.get('workspace_path', '')} && claude",
            "next_step": "Ejecutar Claude Code manualmente en el workspace con el comando de arriba.",
            "headless_available": False,
        }

        if plan_only:
            task_package["status"] = "plan_generated"
            task_package["note"] = (
                "PLAN-ONLY: orquestador se detiene aquí. "
                "run_claude_code disponible en F4.5c (headless OFF por defecto)."
            )

        result = {
            "project_id": project_id,
            "job_id": job_id,
            "status": "plan_generated" if plan_only else "task_package_ready",
            "requirement_spec": spec.to_dict(),
            "agent_design_proposal": agent_proposal.to_dict(),
            "regulatory_matrix": reg_matrix,
            "corpus_manifest": corpus_manifest,
            "pending_documents": pending_docs,
            "compliance_assessment": compliance,
            "workspace": ws_result,
            "task_package": task_package,
            "design_artifacts_path": design_dir,
        }

        complete_job(job_id, {"status": "plan_generated", "design_dir": design_dir})
        return result

    except StopConditionTriggered as e:
        fail_job(job_id, f"[STOP:{e.condition}] {e.detail}")
        raise

    except Exception as e:
        fail_job(job_id, str(e))
        write_event("layer8_stop_condition_triggered", project_id, {
            "condition": "unexpected_error",
            "error": str(e),
        })
        raise
