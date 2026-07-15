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

    if "LIMS" in domains:
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

    # ── Validación documental OT (Rockwell/SCADA) — sin LIMS de laboratorio ──
    # Los 3 dominios de integridad se separan explícitamente en vez de colapsar
    # en integrity_lims_profile (ese perfil es específico de LIMS de lab, no aplica
    # a documentación de ingeniería OT/PLC/SCADA).

    if "DOC_INVENTORY_VERSION" in domains:
        decisions.append(AgentDecision(
            agent_id="doc_inventory_version_agent",
            decision="new_agent",
            base_agent=None,
            profile_name=None,
            rationale=(
                "Inventario recursivo, verificación SHA-256 contra manifiesto y selección de "
                "versión vigente (revisión/fecha/semver, con marcado de version_conflict ante "
                "ambigüedad) es una capacidad determinista de control de ficheros. Ningún agente "
                "base la cubre: son agentes conversacionales sobre corpus RAG, no herramientas "
                "de inventario/hashing."
            ),
            routing_key="doc_inventory",
        ))

    if "DOC_CLASSIFICATION" in domains:
        decisions.append(AgentDecision(
            agent_id="doc_classification_agent",
            decision="new_agent",
            base_agent=None,
            profile_name=None,
            rationale=(
                "Clasificar documentos de ingeniería OT (URS/FS/DS/arquitectura/narrativa de "
                "control/listado de alarmas/protocolo/SAT/reporte) requiere heurísticas sobre "
                "estructura, nombre y metadatos del archivo — no cubierto por agentes base "
                "orientados a preguntas GMP conversacionales."
            ),
            routing_key="doc_classification",
        ))

    if spec.part11_required and "LIMS" not in domains:
        decisions.append(AgentDecision(
            agent_id="fda_part11_agent",
            decision="profile",
            base_agent="integrity",
            profile_name="integrity_part11_ot_profile",
            rationale=(
                "El agente base integrity ya cubre ALCOA+, audit trail y 21 CFR Part 11 al "
                "~70-75%. El delta especializa el contexto a registros/firmas electrónicas "
                "generados por sistemas OT (PLC/SCADA/HMI) en vez de LIMS de laboratorio."
            ),
            routing_key="part11_ot",
        ))

    if spec.annex11_required:
        decisions.append(AgentDecision(
            agent_id="eu_annex11_agent",
            decision="profile",
            base_agent="integrity",
            profile_name="integrity_annex11_ot_profile",
            rationale=(
                "Annex 11 comparte con Part 11/ALCOA+ el dominio de integridad de registros "
                "electrónicos y controles de sistemas computarizados (~70% de cobertura común). "
                "El delta cubre los clausulados propios de EU GMP Annex 11 (gestión de riesgo "
                "de CSV, personal, proveedores/terceros, ciclo de vida) ausentes en un agente "
                "base orientado a normativa FDA."
            ),
            routing_key="annex11_ot",
        ))

    if spec.alcoa_plus_required and "LIMS" not in domains:
        decisions.append(AgentDecision(
            agent_id="alcoa_plus_agent",
            decision="inherit",
            base_agent="integrity",
            profile_name=None,
            rationale=(
                "La evaluación de los 9 atributos ALCOA+ es la capacidad central ya descrita "
                "del agente base integrity ('ALCOA+ attribute assessment'). Se hereda "
                "directamente sin adaptación — crear un perfil aquí duplicaría al agente "
                "Part 11/Annex 11."
            ),
            routing_key="alcoa_plus",
        ))

    if "TRACEABILITY" in domains:
        decisions.append(AgentDecision(
            agent_id="requirements_traceability_agent",
            decision="profile",
            base_agent="csv",
            profile_name="csv_ot_traceability_profile",
            rationale=(
                "El agente base csv ya cubre IQ/OQ/PQ y clasificación GAMP5 (~70%). El delta "
                "añade trazabilidad explícita URS→FS→DS→IQ→OQ→PQ para documentación OT "
                "Rockwell/SCADA: verifica que cada requisito de URS tenga cobertura en FS/DS "
                "y en el protocolo de prueba correspondiente."
            ),
            routing_key="traceability_ot",
        ))

    if "COMPLIANCE_RISK" in domains:
        decisions.append(AgentDecision(
            agent_id="compliance_risk_agent",
            decision="new_agent",
            base_agent=None,
            profile_name=None,
            rationale=(
                "Consolidar hallazgos de los demás agentes en una matriz de riesgo (severidad × "
                "probabilidad × detectabilidad) y priorizar brechas es una función de síntesis "
                "cruzada entre agentes, no una conversación sobre corpus RAG de un solo dominio. "
                "Ningún agente base la cubre."
            ),
            routing_key="compliance_risk",
        ))

    if "FINAL_REVIEW_GATE" in domains:
        decisions.append(AgentDecision(
            agent_id="final_review_agent",
            decision="new_agent",
            base_agent=None,
            profile_name=None,
            rationale=(
                "El agente de revisión final consolida todos los hallazgos, aplica el gate de "
                "gobierno (no declarar cumplimiento GMP final ni aprobar documentos "
                "automáticamente) y prepara el paquete para decisión humana. Es lógica de "
                "orquestación/gobierno propia de esta misión, no una capacidad de ningún "
                "agente base."
            ),
            routing_key="final_review",
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
