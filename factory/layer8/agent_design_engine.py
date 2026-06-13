"""
Capa 8 Tier-1 — Agent Design Engine.

Aplica el árbol heredar/perfil/nuevo para proponer la arquitectura de agentes
de una solución custom, documentando la decisión de routing.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.requirement_interpreter import RequirementSpec

# ── Política cargada estáticamente (sin postgres/redis) ───────────────────────

AGENT_CREATION_POLICY = {
    "inherit_base_layer": {
        "description": "Usar la capa base GMP AI Copilot directamente vía routing.",
        "condition": "La necesidad está cubierta por la capa base sin adaptación.",
    },
    "create_profile": {
        "description": "Crear un perfil derivado del agente base.",
        "condition": "La capa base cubre el 70%+ de la necesidad pero requiere vocabulario/contexto especializado.",
    },
    "create_new_agent": {
        "description": "Crear un agente nuevo desde cero.",
        "condition": "La necesidad requiere flujos, tools o razonamiento no presentes en la capa base.",
    },
}


@dataclass
class AgentDecision:
    agent_id: str
    decision: str  # inherit | profile | new_agent
    base_agent: str | None
    profile_name: str | None
    rationale: str
    routing_key: str | None = None


@dataclass
class AgentDesignProposal:
    project_id: str
    agents: list[AgentDecision] = field(default_factory=list)
    routing_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "decision": a.decision,
                    "base_agent": a.base_agent,
                    "profile_name": a.profile_name,
                    "rationale": a.rationale,
                    "routing_key": a.routing_key,
                }
                for a in self.agents
            ],
            "routing_notes": self.routing_notes,
        }


def load_agent_creation_policy() -> dict:
    return AGENT_CREATION_POLICY


def analyze_agent_fit(domain: str, spec: RequirementSpec) -> str:
    """
    Decide inherit / profile / new_agent para un dominio dado.
    Retorna el string de la decisión.
    """
    if domain == "LIMS":
        return "profile"
    if domain == "OOS":
        return "profile"
    if domain == "DATA_INTEGRITY":
        return "profile"
    if domain == "HPLC":
        return "new_agent"
    if domain == "CAPA":
        return "inherit"
    return "inherit"


def decide_inherited_profiles_custom(spec: RequirementSpec) -> list[AgentDecision]:
    """
    Aplica el árbol de decisión completo para todos los dominios de la spec.
    Para lab_qc produce:
      - heredar capa base (CAPA)
      - qa_oos_profile derivado (OOS)
      - integrity_lims_profile derivado (LIMS + DATA_INTEGRITY)
      - hplc_data_review_agent nuevo (HPLC)
    """
    decisions: list[AgentDecision] = []
    domains = set(spec.domains)

    if "CAPA" in domains:
        decisions.append(AgentDecision(
            agent_id="capa_inherited",
            decision="inherit",
            base_agent="gmp_ai_copilot_base",
            profile_name=None,
            rationale=(
                "CAPA (5-Why, Fishbone, FTA) está cubierto por la capa base GMP AI Copilot "
                "sin adaptación adicional. Heredar evita duplicación."
            ),
            routing_key="capa",
        ))

    if "OOS" in domains:
        decisions.append(AgentDecision(
            agent_id="qa_oos_profile",
            decision="profile",
            base_agent="gmp_ai_copilot_base",
            profile_name="qa_oos_profile",
            rationale=(
                "OOS requiere vocabulario QC específico (Fase I/II, FDA OOS Guidance 2022, "
                "cálculos estadísticos). Un perfil derivado añade contexto sin redefinir flujos base."
            ),
            routing_key="oos",
        ))

    if "LIMS" in domains or "DATA_INTEGRITY" in domains:
        decisions.append(AgentDecision(
            agent_id="integrity_lims_profile",
            decision="profile",
            base_agent="gmp_ai_copilot_base",
            profile_name="integrity_lims_profile",
            rationale=(
                "LIMS + Data Integrity comparten el dominio de audit trail y acceso a datos. "
                "Un perfil unificado reduce complejidad de routing y cubre ALCOA+ / Part 11 "
                "con un único agente especializado."
            ),
            routing_key="integrity|lims",
        ))

    if "HPLC" in domains:
        decisions.append(AgentDecision(
            agent_id="hplc_data_review_agent",
            decision="new_agent",
            base_agent=None,
            profile_name=None,
            rationale=(
                "HPLC (SST, integración de picos, secuencias de inyección) requiere lógica "
                "de validación numérica y detección de anomalías cromatográficas no presentes "
                "en la capa base. Se crea agente nuevo con tools propios."
            ),
            routing_key="hplc",
        ))

    return decisions


def generate_agent_design_proposal(project_id: str, spec: RequirementSpec) -> AgentDesignProposal:
    """Genera la propuesta completa de agentes para una misión."""
    agents = decide_inherited_profiles_custom(spec)
    routing_notes = (
        "Routing primario por intent_key. detect_agent analiza el primer mensaje; "
        "si la consulta toca múltiples dominios se prioriza: hplc > integrity/lims > oos > capa. "
        "hplc_data_review_agent y los perfiles qa_oos/integrity_lims no heredan detect_agent "
        "directamente para evitar ambigüedad en clasificación cruzada."
    )
    proposal = AgentDesignProposal(
        project_id=project_id,
        agents=agents,
        routing_notes=routing_notes,
    )
    write_event("layer8_agent_design_generated", project_id, {
        "agents_count": len(agents),
        "decisions": [a.decision for a in agents],
        "agent_ids": [a.agent_id for a in agents],
    })
    return proposal
