"""
Capa 8 Tier-1 — Recovery Manager.

Detecta estados parciales y genera planes de recuperación.
Estrategia para content_filter_block: convertir corpus a placeholders + PENDING, no reintentar seed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"
RELEASES_BASE = Path(__file__).parent.parent / "releases"


def detect_partial_f5(project_id: str) -> dict[str, Any]:
    """
    Detecta si un workspace tiene un estado parcial de F5 (archivos incompletos).
    Clasifica los hallazgos en: globales, workspace, temporales, peligrosos.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return {"found": False, "project_id": project_id}

    findings: dict[str, list[str]] = {"globals": [], "workspace": [], "temporales": [], "peligrosos": []}

    # Detectar archivos de texto regulatorio crudo
    for f in ws_path.rglob("*.txt"):
        content = f.read_text(encoding="utf-8", errors="ignore")
        if "21 cfr" in content.lower() or "usp <" in content.lower():
            if len(content) > 500:
                findings["peligrosos"].append(str(f.relative_to(ws_path)))

    # Detectar colecciones ChromaDB en el workspace (no en data/ base)
    for d in ws_path.rglob("chroma"):
        findings["workspace"].append(str(d.relative_to(ws_path)))

    # Detectar archivos temporales
    for f in ws_path.rglob("*.tmp"):
        findings["temporales"].append(str(f.relative_to(ws_path)))

    return {
        "found": any(findings.values()),
        "project_id": project_id,
        "workspace_path": str(ws_path),
        "findings": findings,
    }


def create_recovery_plan(detection_result: dict[str, Any]) -> dict[str, Any]:
    """
    Genera un plan de recuperación basado en los hallazgos de detección.
    No ejecuta acciones — solo produce el plan.
    """
    plan_steps = []
    findings = detection_result.get("findings", {})

    if findings.get("peligrosos"):
        plan_steps.append({
            "step": "convert_to_pending",
            "description": "Convertir archivos con texto regulatorio a placeholders PENDING_DOCUMENT.",
            "targets": findings["peligrosos"],
            "action": "manual",
        })

    if findings.get("temporales"):
        plan_steps.append({
            "step": "cleanup_temporales",
            "description": "Eliminar archivos temporales.",
            "targets": findings["temporales"],
            "action": "automated",
        })

    if findings.get("workspace"):
        plan_steps.append({
            "step": "review_chroma",
            "description": "Revisar colecciones ChromaDB del workspace — no borrar sin backup.",
            "targets": findings["workspace"],
            "action": "manual",
        })

    return {
        "project_id": detection_result.get("project_id", ""),
        "recovery_needed": detection_result.get("found", False),
        "steps": plan_steps,
        "note": "Plan de recuperación generado. Ninguna acción se ejecutó automáticamente.",
    }


def recover_from_content_filter_block(project_id: str, blocked_file: str) -> dict[str, Any]:
    """
    Estrategia de recuperación cuando el content filter bloqueó una generación.
    Convierte el archivo problemático a placeholder PENDING_DOCUMENT.
    NO reintenta seed normativo.
    """
    ws_path = WORKSPACES_BASE / project_id
    target = ws_path / blocked_file

    if not target.exists():
        return {"status": "file_not_found", "file": blocked_file}

    original_size = target.stat().st_size
    placeholder = (
        "# PENDING_DOCUMENT\n\n"
        "Este archivo fue bloqueado por el content filter al detectar texto regulatorio.\n"
        "Reemplazado con placeholder. Requiere fuente PDF validada para contenido real.\n\n"
        f"Archivo original: {blocked_file}\n"
        f"Acción: No se reintenta generación de seed normativo.\n"
    )
    target.write_text(placeholder, encoding="utf-8")

    return {
        "status": "converted_to_pending",
        "project_id": project_id,
        "file": blocked_file,
        "original_size_bytes": original_size,
        "action": "replaced_with_placeholder",
        "note": "No se reintenta seed normativo. Ver pending_documents para fuentes requeridas.",
    }


def recover_from_gate_fail(project_id: str, gate_result: dict[str, Any]) -> dict[str, Any]:
    """Genera plan de recuperación tras fallo de quality gates."""
    failed_gates = gate_result.get("failed_gates", [])
    return {
        "project_id": project_id,
        "trigger": "gate_fail",
        "failed_gates": failed_gates,
        "recommendation": "Revisar evidencia de gates fallidos antes de continuar.",
        "steps": [{"gate": g, "action": "review_and_fix"} for g in failed_gates],
    }


def recover_from_claude_failure(project_id: str, error_log: str) -> dict[str, Any]:
    """Genera plan de recuperación tras fallo de ejecución Claude Code."""
    return {
        "project_id": project_id,
        "trigger": "claude_execution_failed",
        "error_summary": error_log[:500] if error_log else "sin detalles",
        "recommendation": "Revisar log de ejecución, verificar task.md y workspace antes de reintentar.",
        "steps": [
            {"step": "review_log", "action": "manual"},
            {"step": "validate_task_safety", "action": "automated"},
            {"step": "retry_or_escalate", "action": "human_decision"},
        ],
    }
