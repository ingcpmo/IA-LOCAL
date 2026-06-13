"""
Capa 9 — Approval Matrix.

Define las 10 acciones aprobables, su nivel de riesgo, quién puede aprobar
y si la aprobación es requerida (mandatory) o recomendada (advisory).

No gestiona estado de aprobación individual — eso lo hace mission_control.
Este módulo responde: "¿esta acción requiere aprobación humana explícita?"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalEntry:
    action: str
    description: str
    risk_level: str          # low / medium / high / critical
    mandatory: bool          # True = bloquea si no hay aprobación
    approver: str            # human / mission_control / auto


APPROVAL_MATRIX: dict[str, ApprovalEntry] = {
    "mission": ApprovalEntry(
        action="mission",
        description="Crear y activar una misión de Capa 9",
        risk_level="high",
        mandatory=True,
        approver="human",
    ),
    "agent_design": ApprovalEntry(
        action="agent_design",
        description="Decisión de árbol heredar/perfil/nuevo para un agente",
        risk_level="medium",
        mandatory=True,
        approver="human",
    ),
    "new_agent": ApprovalEntry(
        action="new_agent",
        description="Crear un agente custom que no existe en el catálogo base",
        risk_level="high",
        mandatory=True,
        approver="human",
    ),
    "claude_execution": ApprovalEntry(
        action="claude_execution",
        description="Ejecutar claude -p en modo headless controlado",
        risk_level="critical",
        mandatory=True,
        approver="human",
    ),
    "recovery_plan": ApprovalEntry(
        action="recovery_plan",
        description="Activar un plan de recuperación tras fallo de gate o stop_condition",
        risk_level="high",
        mandatory=True,
        approver="human",
    ),
    "port_exposure": ApprovalEntry(
        action="port_exposure",
        description="Asignar y exponer un puerto para una solución custom",
        risk_level="medium",
        mandatory=True,
        approver="human",
    ),
    "release": ApprovalEntry(
        action="release",
        description="Crear el release bundle (tar.gz + metadatos) de una solución",
        risk_level="medium",
        mandatory=True,
        approver="human",
    ),
    "deploy": ApprovalEntry(
        action="deploy",
        description="Levantar los contenedores de una solución custom (Docker 3+)",
        risk_level="critical",
        mandatory=True,
        approver="human",
    ),
    "keep_running": ApprovalEntry(
        action="keep_running",
        description="Decisión final de dejar corriendo un contenedor custom",
        risk_level="high",
        mandatory=True,
        approver="human",
    ),
    "external_exposure": ApprovalEntry(
        action="external_exposure",
        description="Exponer un servicio custom fuera de localhost (nginx, túnel, IP pública)",
        risk_level="critical",
        mandatory=True,
        approver="human",
    ),
}


def requires_approval(action: str) -> bool:
    """True si la acción requiere aprobación humana explícita."""
    entry = APPROVAL_MATRIX.get(action)
    return entry is not None and entry.mandatory


def get_action_info(action: str) -> ApprovalEntry | None:
    """Retorna la entrada completa de la matriz para una acción."""
    return APPROVAL_MATRIX.get(action)


def list_actions(risk_level: str | None = None) -> list[ApprovalEntry]:
    """Lista todas las acciones aprobables, filtrando opcionalmente por riesgo."""
    entries = list(APPROVAL_MATRIX.values())
    if risk_level:
        entries = [e for e in entries if e.risk_level == risk_level]
    return entries


def validate_action_sequence(actions: list[str]) -> list[str]:
    """
    Valida que una secuencia de acciones siga el orden lógico de la matriz.
    Retorna lista de advertencias (vacía si todo OK).
    """
    warnings: list[str] = []
    known = set(APPROVAL_MATRIX.keys())
    for a in actions:
        if a not in known:
            warnings.append(f"Acción '{a}' no está en la matriz de aprobación")
    # deploy solo puede seguir a release
    if "deploy" in actions:
        idx_deploy = actions.index("deploy")
        if "release" not in actions[:idx_deploy]:
            warnings.append("'deploy' requiere 'release' previo en la secuencia")
    # external_exposure solo puede seguir a deploy
    if "external_exposure" in actions:
        idx_ext = actions.index("external_exposure")
        if "deploy" not in actions[:idx_ext]:
            warnings.append("'external_exposure' requiere 'deploy' previo en la secuencia")
    return warnings
