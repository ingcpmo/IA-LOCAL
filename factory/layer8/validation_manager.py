"""
Capa 8 Tier-1 — Validation Manager.

Envuelve quality_gate_runner existente y agrega validación estática de artefactos.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.quality_gate_runner import run_all_gates as _run_gates


def run_static_validation(artifacts: dict[str, Any]) -> dict[str, Any]:
    """
    Valida artefactos de diseño (no código) antes de pasar al runtime.
    Verifica que los artefactos requeridos existan y tengan los campos mínimos.
    """
    required_keys = ["requirement_spec", "agent_design_proposal", "regulatory_matrix", "corpus_manifest"]
    missing = [k for k in required_keys if k not in artifacts]
    empty = [k for k in required_keys if k in artifacts and not artifacts[k]]

    errors = []
    if missing:
        errors.append(f"Artefactos faltantes: {missing}")
    if empty:
        errors.append(f"Artefactos vacíos: {empty}")

    # Verificar que no hay texto normativo crudo en ningún artefacto
    for key, value in artifacts.items():
        if isinstance(value, str) and len(value) > 200:
            errors.append(
                f"Artefacto '{key}' contiene texto largo. "
                "Verificar que no incluye texto regulatorio sin fuente."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "checked_keys": required_keys,
        "missing": missing,
        "empty": empty,
    }


def run_quality_gates(project_id: str, workspace_path: str | None = None,
                      manifest: dict | None = None, api_key: str = "") -> dict[str, Any]:
    """
    Ejecuta quality gates sobre el workspace de un proyecto.
    Delega en quality_gate_runner.run_all_gates.
    """
    try:
        m = manifest or {"project": {"id": project_id}, "deployment": {}}
        result = _run_gates(manifest=m, workspace_path=workspace_path or "")
        return result
    except Exception as e:
        return {
            "project_id": project_id,
            "gates_passed": False,
            "error": str(e),
            "note": "Gates no ejecutados — workspace o runner no disponible.",
        }


def fail_on_critical_gates(gate_result: dict[str, Any]) -> None:
    """Lanza excepción si algún gate crítico falló."""
    if not gate_result.get("gates_passed", True):
        failed = gate_result.get("failed_gates", [])
        raise RuntimeError(f"Quality gates críticos fallidos: {failed}")
