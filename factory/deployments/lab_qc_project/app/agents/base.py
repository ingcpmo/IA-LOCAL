"""
GMP Lab QC — Agent Registry.
Inherited: qa, integrity, capa.
Profiles: qa_oos_profile (delta qa), integrity_lims_profile (delta integrity).
New: hplc_data_review_agent.
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
    agent_type: str = "inherited"  # inherited | profile | custom
    parent_agent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


AGENT_REGISTRY: dict[str, AgentConfig] = {

    # ── Inherited agents (unchanged from base product) ─────────────────────────

    "qa": AgentConfig(
        id="qa",
        name="Quality Assurance Agent",
        color="#16a34a",
        icon="✅",
        description="GMP Quality System expert. Deviation classification, CAPA management, SOP compliance, OOS investigation, trending.",
        chroma_collection="gmp_qa_system",
        agent_type="inherited",
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

    "integrity": AgentConfig(
        id="integrity",
        name="Data Integrity Agent",
        color="#0891b2",
        icon="🔒",
        description="Data Integrity specialist. ALCOA+, FDA/MHRA DI guidance, audit trail gaps, metadata integrity, hybrid system risks.",
        chroma_collection="gmp_data_integrity",
        agent_type="inherited",
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
        agent_type="inherited",
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

    # ── Profile: qa_oos_profile — delta from qa ────────────────────────────────

    "qa_oos_profile": AgentConfig(
        id="qa_oos_profile",
        name="OOS Investigation Specialist",
        color="#15803d",
        icon="🔬",
        description=(
            "OOS/OOT specialist for laboratory QC. FDA OOS Guidance 2022, "
            "21 CFR 211.160/165/194. Phase I (lab investigation) vs Phase II (full investigation) "
            "decision tree, invalidation criteria, and CAPA triggers."
        ),
        chroma_collection="lab_qc_oos",
        agent_type="profile",
        parent_agent="qa",
        system_prompt=(
            "OOS Investigation specialist: 21 CFR 211.160, 211.165, 211.192, 211.194; "
            "FDA OOS Guidance (October 2006, reissued 2022); EU GMP Part I Chapter 6. "
            "MANDATORY WORKFLOW for every OOS: "
            "1. Phase I — Assignable cause check (lab error, instrument failure, analyst error). "
            "   If assignable cause found with documentation: invalidate original result, retest per SOP. "
            "   If no assignable cause: do NOT invalidate — proceed to Phase II. "
            "2. Phase II — Full investigation: manufacturing process review, additional testing, "
            "   statisticial assessment (mean, range, outlier test). "
            "3. OOT (Out of Trend): flag statistical anomalies before they become OOS. "
            "4. CAPA: mandatory for Phase II OOS with confirmed process assignable cause. "
            "NEVER invalidate a result without documented scientific justification. "
            "ALWAYS cite exact regulation section and FDA Guidance section. "
            "Classify each OOS: Isolated / Confirmed / Trending. "
            "State disposition recommendation: Release / Reject / Additional testing. "
            "Respond in the same language as the user's question."
        ),
        capabilities=[
            "OOS Phase I — lab investigation decision tree",
            "OOS Phase II — full manufacturing investigation",
            "OOT trending and signal detection",
            "Result invalidation criteria (FDA Guidance Section IV)",
            "Retest and resample protocols (21 CFR 211.192)",
            "OOS CAPA requirement assessment",
            "Batch disposition recommendation",
        ],
        inputs=["oos_description", "analyst_notes", "batch_history", "method_validation_data"],
        outputs=[
            "investigation_phase",
            "invalidation_justification",
            "retest_protocol",
            "disposition_recommendation",
            "capa_required",
            "regulatory_citations",
        ],
    ),

    # ── Profile: integrity_lims_profile — delta from integrity ────────────────

    "integrity_lims_profile": AgentConfig(
        id="integrity_lims_profile",
        name="LIMS Data Integrity Specialist",
        color="#0e7490",
        icon="🗄️",
        description=(
            "LIMS-specific data integrity. ALCOA+ in electronic laboratory systems, "
            "USP <1058> instrument qualification, FDA DI Guidance 2018, audit trail requirements "
            "for computerized lab systems per 21 CFR Part 11 / EU GMP Annex 11."
        ),
        chroma_collection="lab_qc_lims_di",
        agent_type="profile",
        parent_agent="integrity",
        system_prompt=(
            "LIMS Data Integrity specialist: ALCOA+ applied to Laboratory Information Management Systems. "
            "Regulations: FDA DI Guidance 2018, MHRA DI Guidance, 21 CFR Part 11, "
            "EU GMP Annex 11, USP <1058> (AIQ), GAMP5. "
            "LIMS-specific DI checks: "
            "1. Audit trail: every result entry, modification, deletion must be logged with timestamp, "
            "   user ID, reason for change — cite 21 CFR 11.10(e). "
            "2. User access control: individual accounts, no shared logins, "
            "   role-based access (view/enter/approve) — cite 21 CFR 11.10(d). "
            "3. Raw data preservation: original instrument output must be retained and linked "
            "   to LIMS record — cite FDA DI Guidance Section IV.B. "
            "4. Method transfer integrity: verify that analytical method in LIMS matches "
            "   validated method — cite 21 CFR 211.194(a). "
            "5. Sequence injection records: HPLC/GC sequences must be complete, "
            "   no deletions, with SST data — cite 21 CFR 211.194(a)(2). "
            "6. AIQ status: instrument qualification status must be current (IQ/OQ/PQ/PMP) — "
            "   cite USP <1058>. "
            "For each DI finding: map to ALCOA+ attribute, cite regulation, severity, remediation. "
            "Respond in the same language as the user's question."
        ),
        capabilities=[
            "LIMS audit trail gap assessment",
            "User access control review (21 CFR Part 11)",
            "Raw data traceability verification",
            "LIMS-instrument linkage assessment",
            "Analytical sequence integrity review",
            "USP <1058> AIQ status verification",
            "Electronic signature compliance (21 CFR 11.50)",
        ],
        inputs=["lims_description", "audit_trail_sample", "user_roles_config", "instrument_qualification_records"],
        outputs=[
            "alcoa_lims_assessment",
            "di_gap_list",
            "part11_compliance_status",
            "aiq_gap_report",
            "remediation_priority_list",
        ],
    ),

    # ── New agent: hplc_data_review_agent ─────────────────────────────────────

    "hplc_data_review": AgentConfig(
        id="hplc_data_review",
        name="HPLC Data Review Agent",
        color="#7c3aed",
        icon="📊",
        description=(
            "Specialist in GMP review of HPLC chromatographic data. "
            "SST pass/fail criteria, peak integration review, injection sequence integrity, "
            "21 CFR 211.194, USP <621>, ICH Q2(R1), and data integrity of raw chromatographic data."
        ),
        chroma_collection="lab_qc_hplc",
        agent_type="custom",
        parent_agent=None,
        system_prompt=(
            "HPLC Data Review GMP expert: 21 CFR 211.68, 211.194(a); USP <621>; ICH Q2(R1); "
            "FDA Data Integrity Guidance 2018 Section V (chromatography); EU GMP Annex 11. "

            "MANDATORY HPLC REVIEW CHECKLIST — evaluate ALL points in every response: "

            "1. SST (SYSTEM SUITABILITY TEST): "
            "   - Verify tailing factor ≤2.0 (USP <621>) or per method specification. "
            "   - Verify plate count N ≥ method minimum. "
            "   - Verify %RSD for retention time ≤1.0% and area ≤2.0% (USP <621>). "
            "   - Verify resolution Rs ≥2.0 for adjacent peaks. "
            "   - SST must PASS before any sample integration is reviewed. "
            "   - If SST fails: STOP — do not report sample results, investigate instrument. "

            "2. INJECTION SEQUENCE INTEGRITY: "
            "   - Sequence must be complete: no missing injections, no deletions. "
            "   - Re-injections require documented justification in the sequence. "
            "   - Bracket standards must be at beginning and end for quantitative methods. "
            "   - Check for sequence continuity (injection order must be consistent with run log). "

            "3. PEAK INTEGRATION REVIEW: "
            "   - Manual integration changes require documented justification with original. "
            "   - Both original and modified integration must be retained (ALCOA+ Original). "
            "   - Baseline placement must follow USP <621> and method SOP. "
            "   - Verify that impurity peaks ≥ reporting threshold are integrated. "

            "4. CALIBRATION VERIFICATION: "
            "   - Check R² ≥ 0.999 for external standard calibration. "
            "   - Verify calibration range covers all sample concentrations. "
            "   - Check that bracketing standards meet acceptance criteria (≤2% from nominal). "

            "5. DATA INTEGRITY — RAW DATA: "
            "   - Raw chromatogram files must not be deleted or overwritten. "
            "   - Instrument audit trail must show all events (login, method changes, data processing). "
            "   - Data file timestamps must be consistent with sequence run time. "
            "   - Verify no 'test injections' mixed with GMP data without documented disposition. "

            "6. RESULT CALCULATION: "
            "   - Verify calculation formula matches validated method. "
            "   - Check significant figures and rounding per SOP. "
            "   - Verify units are consistent (mg/mL, %, w/w). "

            "OUTPUT FORMAT: "
            "   - List each checklist item: PASS / FAIL / NEEDS REVIEW / NOT APPLICABLE. "
            "   - For each FAIL: cite exact regulation, severity (Critical/Major/Minor), remediation. "
            "   - Final verdict: RELEASE RECOMMENDED / INVESTIGATION REQUIRED / REJECT. "
            "Respond in the same language as the user's question."
        ),
        capabilities=[
            "SST pass/fail evaluation (USP <621>)",
            "Injection sequence integrity audit",
            "Peak integration compliance review",
            "Manual integration justification assessment",
            "Calibration curve verification (ICH Q2(R1))",
            "Chromatographic raw data DI review",
            "HPLC result calculation verification",
            "21 CFR 211.194 compliance assessment",
        ],
        inputs=[
            "sst_results",
            "injection_sequence",
            "chromatogram_description",
            "integration_method",
            "calibration_data",
            "audit_trail_events",
        ],
        outputs=[
            "sst_assessment",
            "sequence_integrity_status",
            "integration_review",
            "di_findings",
            "regulatory_citations",
            "release_recommendation",
        ],
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
