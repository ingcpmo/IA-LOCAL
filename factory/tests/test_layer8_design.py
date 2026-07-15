"""
Tests de Capa 8 — Diseño: requirement_interpreter, agent_design_engine,
regulatory_compliance_engine.

Cubre:
- requirement_interpreter detecta dominios de lab_qc
- agent_design_engine propone: heredar capa (CAPA) + qa_oos/integrity_lims
  profiles + hplc_data_review_agent nuevo
- regulatory engine NUNCA emite texto normativo y marca PENDING_DOCUMENT
- gate anti-texto-normativo aborta ante párrafo tipo CFR/USP/ICH
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.layer8.requirement_interpreter import (
    RequirementSpec,
    extract_domains,
    extract_regulatory_scope,
    generate_requirement_spec,
)
from factory.layer8.agent_design_engine import (
    decide_inherited_profiles_custom,
    generate_agent_design_proposal,
)
from factory.layer8.regulatory_compliance_engine import (
    generate_regulatory_matrix,
    validate_no_unsupported_regulatory_claims,
)

# ── Misión lab_qc representativa ──────────────────────────────────────────────

_LAB_QC_MISSION = {
    "project_id": "test_lab_qc_design",
    "client_type": "pharma_manufacturer",
    "objective": (
        "Laboratorio QC farmacéutico con LIMS para gestión de muestras y audit trail, "
        "análisis HPLC con integración de picos y SST, investigación OOS Fase I y Fase II "
        "según FDA OOS Guidance 2022, integridad de datos ALCOA+ / 21 CFR Part 11, "
        "y sistema CAPA con 5-Why y Fishbone"
    ),
    "regulatory_scope": ["21 CFR Part 211", "21 CFR Part 11"],
    "documents": {
        "FDA_OOS_Guidance_2022": "pending",
        "FDA_DI_Guidance_2018": "pending",
        "USP_621": "pending",
        "USP_1058": "pending",
    },
    "constraints": ["Solo Ollama local", "Sin acceso internet"],
}

def _make_spec(isolated_audit) -> RequirementSpec:
    return generate_requirement_spec("test_lab_qc_design", _LAB_QC_MISSION)


# ── Requirement Interpreter ───────────────────────────────────────────────────

class TestRequirementInterpreter:
    def test_detects_lims_domain(self):
        domains = extract_domains("LIMS con audit trail y control de acceso a muestras")
        assert "LIMS" in domains

    def test_detects_hplc_domain(self):
        domains = extract_domains("análisis HPLC con integración de picos y SST cromatográfico")
        assert "HPLC" in domains

    def test_detects_oos_domain(self):
        domains = extract_domains("investigación OOS Fase I y OOS Fase II out-of-specification")
        assert "OOS" in domains

    def test_detects_data_integrity_domain(self):
        domains = extract_domains("data integrity ALCOA+ registros electrónicos 21 cfr part 11")
        assert "DATA_INTEGRITY" in domains

    def test_detects_capa_domain(self):
        domains = extract_domains("CAPA con 5-why y fishbone análisis de causa raíz")
        assert "CAPA" in domains

    def test_lab_qc_mission_detects_all_domains(self):
        domains = extract_domains(_LAB_QC_MISSION["objective"])
        for expected in ("LIMS", "HPLC", "OOS", "DATA_INTEGRITY", "CAPA"):
            assert expected in domains, f"Dominio esperado '{expected}' no detectado en lab_qc"

    def test_regulatory_scope_detects_part11(self):
        scope = extract_regulatory_scope(_LAB_QC_MISSION)
        assert scope["part11_required"] is True

    def test_regulatory_scope_detects_alcoa_plus(self):
        mission = {**_LAB_QC_MISSION, "objective": _LAB_QC_MISSION["objective"] + " ALCOA+"}
        scope = extract_regulatory_scope(mission)
        assert scope["alcoa_plus_required"] is True

    def test_regulatory_scope_detects_eu_annex11(self):
        mission = {**_LAB_QC_MISSION, "objective": _LAB_QC_MISSION["objective"] + " EU GMP Annex 11"}
        scope = extract_regulatory_scope(mission)
        assert scope["annex11_required"] is True

    def test_regulatory_scope_annex11_false_by_default(self):
        scope = extract_regulatory_scope(_LAB_QC_MISSION)
        assert scope["annex11_required"] is False

    def test_detects_doc_inventory_version_domain(self):
        domains = extract_domains("inventariar 32 archivos y verificar contra SHA256SUMS, seleccionar versiones vigentes")
        assert "DOC_INVENTORY_VERSION" in domains

    def test_detects_traceability_domain(self):
        domains = extract_domains("trazabilidad URS-FS-DS-IQ-OQ-PQ de la documentacion")
        assert "TRACEABILITY" in domains

    def test_generate_requirement_spec_returns_all_domains(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        for domain in ("LIMS", "HPLC", "OOS", "DATA_INTEGRITY"):
            assert domain in spec.domains, f"Dominio '{domain}' ausente en RequirementSpec"

    def test_generate_requirement_spec_sets_part11(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        assert spec.part11_required is True

    def test_generate_requirement_spec_detects_pending_docs(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        assert len(spec.pending_documents) > 0


# ── Agent Design Engine ───────────────────────────────────────────────────────

class TestAgentDesignEngine:
    def _spec_with_domains(self, domains: list[str], part11_required: bool = False,
                            alcoa_plus_required: bool = False, annex11_required: bool = False) -> RequirementSpec:
        return RequirementSpec(
            project_id="test_design",
            domains=domains,
            regulatory_scope=[],
            dual_use=False,
            part11_required=part11_required,
            alcoa_plus_required=alcoa_plus_required,
            annex11_required=annex11_required,
            client_needs=[],
            constraints=[],
            pending_documents=[],
            raw_objective=" ".join(domains),
        )

    def test_capa_domain_proposes_inherit(self):
        spec = self._spec_with_domains(["CAPA"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "capa_inherited" and d.decision == "inherit"
                   for d in decisions), "CAPA debe heredarse de la capa base"

    def test_oos_domain_proposes_profile(self):
        spec = self._spec_with_domains(["OOS"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "qa_oos_profile" and d.decision == "profile"
                   for d in decisions), "OOS debe generar perfil qa_oos_profile"

    def test_lims_domain_proposes_profile(self):
        spec = self._spec_with_domains(["LIMS"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "integrity_lims_profile" and d.decision == "profile"
                   for d in decisions), "LIMS debe generar perfil integrity_lims_profile"

    def test_data_integrity_domain_alone_proposes_nothing_without_lims_or_scope_flags(self):
        """DATA_INTEGRITY es solo una señal léxica débil (p.ej. 'audit trail' suelto);
        sin LIMS ni regulatory_scope declarado no debe generar ningún agente — evita
        proponer integrity_lims_profile (perfil de LIMS de laboratorio) para misiones
        que no tienen nada que ver con LIMS (p.ej. documentación OT/SCADA)."""
        spec = self._spec_with_domains(["DATA_INTEGRITY"])
        decisions = decide_inherited_profiles_custom(spec)
        assert decisions == []

    def test_lims_domain_still_proposes_lims_profile_even_with_data_integrity(self):
        spec = self._spec_with_domains(["LIMS", "DATA_INTEGRITY"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "integrity_lims_profile" for d in decisions)

    def test_part11_and_alcoa_flags_without_lims_propose_separate_ot_agents(self):
        """Para misiones de integridad de datos sin LIMS (p.ej. documentación OT
        Rockwell/SCADA), Part 11 y ALCOA+ deben separarse del perfil de LIMS."""
        spec = self._spec_with_domains([], part11_required=True, alcoa_plus_required=True)
        decisions = decide_inherited_profiles_custom(spec)
        agent_ids = {d.agent_id for d in decisions}
        assert "fda_part11_agent" in agent_ids
        assert "alcoa_plus_agent" in agent_ids
        assert "integrity_lims_profile" not in agent_ids
        part11 = next(d for d in decisions if d.agent_id == "fda_part11_agent")
        assert part11.decision == "profile" and part11.base_agent == "integrity"
        alcoa = next(d for d in decisions if d.agent_id == "alcoa_plus_agent")
        assert alcoa.decision == "inherit" and alcoa.base_agent == "integrity"

    def test_annex11_flag_proposes_profile(self):
        spec = self._spec_with_domains([], annex11_required=True)
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "eu_annex11_agent" and d.decision == "profile"
                   and d.base_agent == "integrity" for d in decisions)

    def test_doc_inventory_and_classification_domains_propose_new_agents(self):
        spec = self._spec_with_domains(["DOC_INVENTORY_VERSION", "DOC_CLASSIFICATION"])
        decisions = decide_inherited_profiles_custom(spec)
        agent_ids = {d.agent_id: d.decision for d in decisions}
        assert agent_ids.get("doc_inventory_version_agent") == "new_agent"
        assert agent_ids.get("doc_classification_agent") == "new_agent"

    def test_traceability_domain_proposes_csv_profile(self):
        spec = self._spec_with_domains(["TRACEABILITY"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "requirements_traceability_agent" and d.decision == "profile"
                   and d.base_agent == "csv" for d in decisions)

    def test_compliance_risk_and_final_review_domains_propose_new_agents(self):
        spec = self._spec_with_domains(["COMPLIANCE_RISK", "FINAL_REVIEW_GATE"])
        decisions = decide_inherited_profiles_custom(spec)
        agent_ids = {d.agent_id: d.decision for d in decisions}
        assert agent_ids.get("compliance_risk_agent") == "new_agent"
        assert agent_ids.get("final_review_agent") == "new_agent"

    def test_hplc_domain_proposes_new_agent(self):
        spec = self._spec_with_domains(["HPLC"])
        decisions = decide_inherited_profiles_custom(spec)
        assert any(d.agent_id == "hplc_data_review_agent" and d.decision == "new_agent"
                   for d in decisions), "HPLC debe crear agente nuevo hplc_data_review_agent"

    def test_lab_qc_full_proposal_has_all_agents(self, isolated_audit):
        """Lab QC completo debe proponer los 4 agentes del diseño arquitectónico."""
        spec = _make_spec(isolated_audit)
        decisions = decide_inherited_profiles_custom(spec)
        agent_ids = {d.agent_id for d in decisions}
        expected = {"qa_oos_profile", "integrity_lims_profile", "hplc_data_review_agent"}
        missing = expected - agent_ids
        assert not missing, f"Agentes esperados no propuestos: {missing}"

    def test_all_decisions_have_rationale(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        decisions = decide_inherited_profiles_custom(spec)
        for d in decisions:
            assert d.rationale, f"Agente {d.agent_id} sin rationale"

    def test_proposal_generates_routing_notes(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        proposal = generate_agent_design_proposal("test_lab_qc_design", spec)
        assert proposal.routing_notes, "La propuesta debe incluir routing_notes"
        d = proposal.to_dict()
        assert "agents" in d and len(d["agents"]) > 0


# ── Regulatory Compliance Engine ──────────────────────────────────────────────

class TestRegulatoryEngine:
    def test_matrix_marks_fda_guidance_as_pending(self, isolated_audit):
        """El motor regulatorio NUNCA emite texto de guías FDA — las marca PENDING_DOCUMENT."""
        spec = _make_spec(isolated_audit)
        matrix = generate_regulatory_matrix(spec)
        statuses = [r.get("source_status") for r in matrix.get("requirements", [])]
        assert "PENDING_DOCUMENT" in statuses, (
            "La matriz debe marcar FDA OOS Guidance / USP como PENDING_DOCUMENT"
        )

    def test_matrix_never_emits_long_normative_text(self, isolated_audit):
        """Ningún campo de la matriz debe contener un párrafo normativo largo."""
        spec = _make_spec(isolated_audit)
        matrix = generate_regulatory_matrix(spec)
        for req in matrix.get("requirements", []):
            for key, val in req.items():
                if isinstance(val, str) and len(val) > 200:
                    result = validate_no_unsupported_regulatory_claims(val, source_id=key)
                    assert not result["blocked"], (
                        f"Campo '{key}' contiene texto normativo largo no permitido: {val[:80]}"
                    )

    def test_matrix_has_requirements_for_each_lab_qc_domain(self, isolated_audit):
        spec = _make_spec(isolated_audit)
        matrix = generate_regulatory_matrix(spec)
        domains_in_matrix = {r["domain"] for r in matrix.get("requirements", [])}
        for domain in spec.domains:
            assert domain in domains_in_matrix, (
                f"Dominio '{domain}' no tiene entries en la matriz regulatoria"
            )

    # ── Gate anti-texto-normativo ─────────────────────────────────────────────

    def test_anti_text_gate_blocks_cfr_paragraph(self):
        """Un párrafo con referencia 21 CFR X.Y supera el umbral y es bloqueado."""
        cfr_paragraph = (
            "The requirements of 21 CFR 211.68 state that automated, mechanical, and electronic "
            "equipment, including computers, or related systems that will perform a function "
            "covered by this part, shall be calibrated, inspected, or checked according to "
            "a written program designed to assure proper performance of the system."
        )
        result = validate_no_unsupported_regulatory_claims(cfr_paragraph, source_id="test")
        assert result["blocked"] is True
        assert result["pending_marker"] == "PENDING_DOCUMENT"

    def test_anti_text_gate_blocks_usp_paragraph(self):
        """Párrafo con USP <NNN> debe ser bloqueado."""
        usp_paragraph = (
            "According to USP <621> Chromatography, the system suitability test requirements "
            "must be met before any sample analysis can be considered valid under current GMP. "
            "The requirements include tailing factor and plate count within specified limits."
        )
        result = validate_no_unsupported_regulatory_claims(usp_paragraph)
        assert result["blocked"] is True
        assert result["pending_marker"] == "PENDING_DOCUMENT"

    def test_anti_text_gate_blocks_ich_paragraph(self):
        """Párrafo con ICH Q2 debe ser bloqueado."""
        ich_paragraph = (
            "ICH Q2 R2 guidelines specify the validation parameters for analytical procedures "
            "including accuracy, precision, specificity, detection limit, quantitation limit, "
            "linearity and range. All parameters must be evaluated for the analytical method "
            "to be considered validated under the ICH Q2 framework in pharmaceutical analysis."
        )
        result = validate_no_unsupported_regulatory_claims(ich_paragraph)
        assert result["blocked"] is True

    def test_anti_text_gate_allows_short_reference(self):
        """Referencias cortas (< umbral de longitud) no son bloqueadas."""
        short_ref = "Verificar cumplimiento 21 CFR Part 11."
        result = validate_no_unsupported_regulatory_claims(short_ref)
        assert result["blocked"] is False

    def test_anti_text_gate_allows_plain_text_no_patterns(self):
        """Texto largo sin patrones regulatorios pasa sin restricción."""
        plain = (
            "El sistema debe gestionar el ciclo de vida completo de las muestras de laboratorio, "
            "desde la recepción hasta el descarte, incluyendo registro de resultados, vinculación "
            "con lotes de producción y generación de reportes de conformidad con buenas prácticas."
        )
        result = validate_no_unsupported_regulatory_claims(plain)
        assert result["blocked"] is False
