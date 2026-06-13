"""
Capa 9 — Schemas de validación para misión y requerimiento.

Valida la estructura mínima de los payloads antes de persistir.
No usa librerías de validación externas: solo dataclasses + assertions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Constantes de dominio ──────────────────────────────────────────────────────

ALLOWED_ACTIONS: list[str] = [
    "analyze_requirement",
    "design_agents",
    "create_profiles",
    "create_custom_agents",
    "create_workspace",
    "run_claude_code",
    "generate_code",
    "generate_tests",
    "create_rag_structure",
    "run_temp_docker",
    "run_quality_gates",
    "create_release",
    "deploy_docker_if_gates_pass",
]

STOP_CONDITIONS: list[str] = [
    "product_base_change_detected",
    "forbidden_path_detected",
    "regulatory_source_missing_for_required_claim",
    "quality_gate_fail",
    "docker_runtime_fail",
    "resource_limit_exceeded",
    "claude_execution_failed",
    "content_filter_blocked",
]

FINAL_HUMAN_DECISIONS: list[str] = [
    "keep_docker_running",
    "expose_external_access",
    "deploy_docker",
]

AUTONOMY_LEVELS: list[str] = [
    "manual_only",
    "supervised",
    "controlled_full",
]


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class MissionApprovalSchema:
    autonomy_level: str
    allowed_actions: list[str]
    stop_conditions: list[str]
    final_human_decision_required: list[str]
    deploy_docker_if_gates_pass: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.autonomy_level not in AUTONOMY_LEVELS:
            errors.append(f"autonomy_level inválido: {self.autonomy_level!r}. Válidos: {AUTONOMY_LEVELS}")
        for a in self.allowed_actions:
            if a not in ALLOWED_ACTIONS:
                errors.append(f"allowed_action desconocida: {a!r}")
        for s in self.stop_conditions:
            if s not in STOP_CONDITIONS:
                errors.append(f"stop_condition desconocida: {s!r}")
        for d in self.final_human_decision_required:
            if d not in FINAL_HUMAN_DECISIONS:
                errors.append(f"final_human_decision desconocida: {d!r}")
        return errors


@dataclass
class MissionPayload:
    project_id: str
    client_type: str
    objective: str
    regulatory_scope: list[str]
    documents: dict[str, str]           # nombre → estado ("pending" / "available")
    constraints: list[str]
    mission_approval: MissionApprovalSchema
    linked_release: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.project_id or not self.project_id.replace("_", "").isalnum():
            errors.append("project_id debe ser alfanumérico con guiones bajos")
        if not self.client_type:
            errors.append("client_type es obligatorio")
        if not self.objective:
            errors.append("objective es obligatorio")
        if not self.regulatory_scope:
            errors.append("regulatory_scope debe tener al menos un elemento")
        if not self.documents:
            errors.append("documents no puede estar vacío")
        if not self.constraints:
            errors.append("constraints no puede estar vacío")
        errors.extend(self.mission_approval.validate())
        return errors

    @classmethod
    def from_dict(cls, d: dict) -> "MissionPayload":
        approval_raw = d.get("mission_approval", {})
        approval = MissionApprovalSchema(
            autonomy_level=approval_raw.get("autonomy_level", "manual_only"),
            allowed_actions=approval_raw.get("allowed_actions", []),
            stop_conditions=approval_raw.get("stop_conditions", STOP_CONDITIONS.copy()),
            final_human_decision_required=approval_raw.get("final_human_decision_required", []),
            deploy_docker_if_gates_pass=approval_raw.get("deploy_docker_if_gates_pass", False),
        )
        return cls(
            project_id=d["project_id"],
            client_type=d["client_type"],
            objective=d["objective"],
            regulatory_scope=d.get("regulatory_scope", []),
            documents=d.get("documents", {}),
            constraints=d.get("constraints", []),
            mission_approval=approval,
            linked_release=d.get("linked_release", {}),
        )


@dataclass
class RequirementPayload:
    project_id: str
    title: str
    description: str
    domains: list[str] = field(default_factory=list)
    regulatory_refs: list[str] = field(default_factory=list)
    priority: str = "normal"            # low / normal / high / critical

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.project_id:
            errors.append("project_id es obligatorio")
        if not self.title:
            errors.append("title es obligatorio")
        if not self.description:
            errors.append("description es obligatoria")
        if self.priority not in ("low", "normal", "high", "critical"):
            errors.append(f"priority inválida: {self.priority!r}")
        return errors

    @classmethod
    def from_dict(cls, d: dict) -> "RequirementPayload":
        return cls(
            project_id=d["project_id"],
            title=d["title"],
            description=d["description"],
            domains=d.get("domains", []),
            regulatory_refs=d.get("regulatory_refs", []),
            priority=d.get("priority", "normal"),
        )
