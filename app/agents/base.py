"""
GMP Agent Registry — Capa 1: definición de los 6 agentes especializados.
"""
from dataclasses import dataclass, field
from fastapi import HTTPException


@dataclass
class AgentConfig:
    id: str
    name: str
    color: str
    icon: str
    description: str
    chroma_collection: str
    system_prompt: str
    capabilities: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


AGENT_REGISTRY: dict[str, AgentConfig] = {
    "csv": AgentConfig(
        id="csv",
        name="CSV/CSA Validation Agent",
        color="#2563eb",
        icon="🖥️",
        description="Computer System Validation / Computer Software Assurance specialist. GAMP5, IQ/OQ/PQ, 21 CFR Part 11.",
        chroma_collection="gmp_fda_regulations",
        system_prompt=(
            "GMP CSV/CSA expert: GAMP5, IQ/OQ/PQ, 21 CFR Part 11, EU GMP Annex 11. "
            "Cite regulation sections. Flag CRITICAL risks."
        ),
        capabilities=[
            "GAMP5 category classification",
            "IQ/OQ/PQ scope determination",
            "21 CFR Part 11 assessment",
            "Validation Master Plan review",
            "CSV gap analysis",
            "Regression test strategy",
        ],
        inputs=["system_description", "software_category", "regulatory_context"],
        outputs=["validation_plan", "gamp5_classification", "part11_assessment", "gap_list"],
    ),

    "qa": AgentConfig(
        id="qa",
        name="Quality Assurance Agent",
        color="#16a34a",
        icon="✅",
        description="GMP Quality System expert. Deviation classification, CAPA management, SOP compliance, OOS investigation, trending.",
        chroma_collection="gmp_qa_system",
        system_prompt=(
            "GMP QA expert: ICH Q10, 21 CFR Part 211, EU GMP Part I. "
            "Classify severity, cite regulation, state if CAPA is mandatory."
        ),
        capabilities=[
            "Deviation classification (Critical/Major/Minor)",
            "CAPA generation with root cause",
            "OOS investigation guidance",
            "Trending and signal detection",
            "SOP compliance review",
            "Change control QA assessment",
        ],
        inputs=["deviation_description", "batch_data", "historical_trend"],
        outputs=["deviation_classification", "capa_plan", "investigation_phase", "regulatory_action"],
    ),

    "audit": AgentConfig(
        id="audit",
        name="FDA Audit Readiness Agent",
        color="#dc2626",
        icon="🔍",
        description="FDA inspection simulation. 483 observations, Warning Letter patterns, regulatory gap assessment, inspection readiness.",
        chroma_collection="gmp_fda_regulations",
        system_prompt=(
            "FDA Inspector simulator: 21 CFR Parts 11, 210, 211, 820; EU GMP Annex 11/15. "
            "Generate 2-5 numbered 483 Observations. Each must contain: "
            "Observation [N]: title | Observation: description | Regulatory Basis: exact CFR section | "
            "Risk Level: CRITICAL/MAJOR/MINOR | Patient/Product Impact | Proposed Remediation. "
            "End with Inspection Summary: total obs, most critical, top 3 actions, "
            "overall risk (CRITICAL/HIGH/MEDIUM/LOW). "
            "Respond in the same language as the user's question."
        ),
        capabilities=[
            "FDA 483 simulation",
            "Warning Letter pattern analysis",
            "Inspection readiness assessment",
            "Regulatory gap identification",
            "483 response adequacy review",
            "Pre-PAI/surveillance preparation",
        ],
        inputs=["facility_description", "process_description", "recent_findings"],
        outputs=["483_observations", "gap_list", "readiness_score", "remediation_priority"],
    ),

    "automation": AgentConfig(
        id="automation",
        name="OT/Automation Validation Agent",
        color="#7c3aed",
        icon="⚙️",
        description="OT systems validation. ISA-88/95, GAMP5 Cat4/5, PLC/SCADA/MES, EEMUA 191, 21 CFR Part 11 for automation.",
        chroma_collection="gmp_automation",
        system_prompt=(
            "OT validation expert: PLC/SCADA/DCS/MES, ISA-88/95, GAMP5 Cat4/5, EEMUA 191, 21 CFR Part 11. "
            "Identify automation layer and cite applicable standard section."
        ),
        capabilities=[
            "ISA-88 batch control compliance",
            "PLC/SCADA validation scope",
            "GAMP5 Cat 4/5 classification",
            "Alarm rationalization (EEMUA 191)",
            "eBR/MES validation",
            "OT cybersecurity assessment",
        ],
        inputs=["system_description", "automation_layer", "alarm_data"],
        outputs=["validation_scope", "isa88_assessment", "alarm_rationalization", "part11_gaps"],
    ),

    "integrity": AgentConfig(
        id="integrity",
        name="Data Integrity Agent",
        color="#0891b2",
        icon="🔒",
        description="Data Integrity specialist. ALCOA+, FDA/MHRA DI guidance, audit trail gaps, metadata integrity, hybrid system risks.",
        chroma_collection="gmp_data_integrity",
        system_prompt=(
            "Data Integrity expert: ALCOA+ = Attributable, Legible, Contemporaneous, Original, "
            "Accurate, Complete, Consistent, Enduring, Available (exactly 9 attributes, no others). "
            "Regulations: FDA DI Guidance 2018, MHRA DI Guidance, 21 CFR Part 11, EU GMP Annex 11. "
            "For each finding: map to exact ALCOA+ attribute, cite specific regulation section, "
            "classify severity (Critical/Major/Minor), provide remediation, flag CAPA items. "
            "Respond in the same language as the user's question."
        ),
        capabilities=[
            "ALCOA+ attribute assessment",
            "Audit trail gap analysis",
            "Metadata integrity review",
            "Raw vs processed data assessment",
            "Hybrid system risk analysis",
            "DI gap report generation",
        ],
        inputs=["system_description", "data_flow", "audit_trail_sample"],
        outputs=["alcoa_assessment", "di_gap_report", "remediation_roadmap", "risk_classification"],
    ),

    "capa": AgentConfig(
        id="capa",
        name="CAPA Management Agent",
        color="#d97706",
        icon="🔧",
        description="CAPA specialist. Root cause analysis (5-Why, Fishbone, FTA), effectiveness criteria, RPN prioritization, closure verification.",
        chroma_collection="gmp_capa",
        system_prompt=(
            "CAPA expert: 21 CFR 820.100, ISO 13485, ICH Q10. "
            "5-Why, Fishbone, FTA, RPN. Show each root cause step. Cite regulation."
        ),
        capabilities=[
            "5-Why root cause analysis",
            "Fishbone/Ishikawa facilitation",
            "Fault Tree Analysis (FTA)",
            "Effectiveness criteria definition",
            "RPN-based prioritization",
            "CAPA closure verification",
        ],
        inputs=["problem_description", "deviation_history", "process_data"],
        outputs=["root_cause", "capa_plan", "effectiveness_criteria", "rpn_score", "closure_checklist"],
    ),
}


def get_agent(agent_id: str) -> AgentConfig:
    cfg = AGENT_REGISTRY.get(agent_id)
    if cfg is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{agent_id}'. Valid: {list(AGENT_REGISTRY.keys())}",
        )
    return cfg
