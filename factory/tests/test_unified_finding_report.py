"""Tests -- factory/services/unified_finding_report.py (Paquete 1, parte b,
cierra hallazgo G).

Usa el fixture REAL de gap_assessment_finding_mapper
(findings_completos_FS_v1_2_v4.json) para los findings narrativos -- mismo
patron que test_gap_assessment_finding_mapper.py, para que un cambio en el
archivo real se note como regresion aqui tambien. Los RequirementOutcome de
Tier1Report son sinteticos (no requieren una corrida LLM real) siguiendo el
patron de test_tier1_report.py::test_render_markdown_never_declares_compliance.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import tier1_report as t1
from factory.services import unified_finding_report as ufr

FINDINGS_PATH = (
    Path(__file__).parent.parent / "docs" / "gmpai_reanalysis" / "fs_v1_2" / "findings_completos_FS_v1_2_v4.json"
)
DOCUMENT_NAME = "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
DOCUMENT_SHA256 = "56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb"

_SUPPORTED_VERDICT = {
    "d_sufficiency": "MET",
    "substantive_evidence_accepted": True,
    "substantive_support": "SUPPORTED",
}


@pytest.fixture(scope="module")
def narrative_findings():
    doc = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    # FSV12-07 y FSV12-19 son 'cumple_parcialmente' -- exigen el veredicto
    # sustantivo declarado (Deuda I-1) para no rechazarse antes de llegar
    # a la regla que cada test quiere ejercitar.
    return [
        {**f, **_SUPPORTED_VERDICT} if f["finding_id"] in ("FSV12-07", "FSV12-19") else f
        for f in doc["findings"]
    ]


def _tier1_report(requirements):
    return t1.Tier1Report(
        document_id="RW-TEST", agent_id="fda_part11_agent", run_id="run-x",
        generated_at="2026-08-19T00:00:00+00:00", requirements=requirements,
    )


class TestMappedRow:

    def test_matching_narrative_finding_populates_risk_and_recommendation(self, narrative_findings):
        """ANNEX11_7.1 (FSV12-07) mapea limpio -- HIGH_RISK, ver
        test_gap_assessment_finding_mapper.py::test_fsv12_07_risk_and_confidence."""
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="ANNEX11_7.1", bucket=t1.CONFIRMED,
                                   conclusion="PARTIALLY_DOCUMENTED",
                                   evidence_quote="cita real anclada", page_or_section="p.3"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        row = report.rows[0]
        assert row.risk_recommendation_status == ufr.MAPPED
        assert row.change_risk == "HIGH_RISK"
        assert row.proposed_content
        assert row.change_reason
        assert row.rules  # trazabilidad completa, reutilizada tal cual
        # Los campos de tier1 (evidencia/pagina) nunca se pisan con los del
        # narrativo -- siguen siendo los del RequirementOutcome real.
        assert row.evidence_quote == "cita real anclada"
        assert row.page_or_section == "p.3"

    def test_never_invents_a_field_gap_assessment_did_not_produce(self, narrative_findings):
        """El renglon MAPPED solo trae los campos reales que
        map_finding_to_remediation_change() produjo -- nada mas."""
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="ANNEX11_7.1", bucket=t1.CONFIRMED,
                                   conclusion="PARTIALLY_DOCUMENTED"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        row = report.rows[0]
        assert set(row.rules.keys()) == {
            "regulatory_catalog_entry_id", "change_type", "requirement_criticality",
            "gxp_impact", "evidence_status", "functional_impact", "page_anchor",
            "relevance_status", "schema_validation_status", "coverage_status",
            "substantive_verdict", "citation_anchor_status", "evidence_type", "chunk_sha256",
        }


class TestNoGapAssessmentData:

    def test_requirement_without_narrative_finding_declares_it_explicitly(self, narrative_findings):
        """El caso normal de una corrida Tier-1 en vivo: la mayoria de los
        requisitos no tienen un finding narrativo asociado -- nunca se
        inventa riesgo/recomendacion, se declara la ausencia."""
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="NOT_IN_FIXTURE_SET", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="PROVISIONAL_GAP", review_queue_rc_id="finding-run-x-NOT_IN_FIXTURE_SET"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        row = report.rows[0]
        assert row.risk_recommendation_status == ufr.NO_GAP_ASSESSMENT_DATA
        assert row.change_risk is None
        assert row.proposed_content is None
        assert row.rules is None
        # Los campos de tier1 siguen presentes -- la ausencia de gap-assessment
        # no borra lo que si existe.
        assert row.review_queue_rc_id == "finding-run-x-NOT_IN_FIXTURE_SET"

    def test_no_narrative_findings_provided_at_all(self):
        """Sin narrative_findings (default None): todo renglon queda
        NO_GAP_ASSESSMENT_DATA -- comportamiento honesto por defecto, no
        un error."""
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(a)", bucket=t1.CONFIRMED,
                                   conclusion="DOCUMENTED_AND_SUPPORTED"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256)
        assert report.rows[0].risk_recommendation_status == ufr.NO_GAP_ASSESSMENT_DATA


class TestNotMappable:

    def test_narrative_finding_that_fails_mapping_is_declared_not_mappable(self, narrative_findings):
        """FSV12-19 (ALCOA_AVAILABLE) se rechaza por ambiguedad real de
        anclaje de pagina -- ver test_gap_assessment_finding_mapper.py::
        test_fsv12_19_is_not_mappable. El renglon unificado debe declarar
        el motivo real, nunca fabricar un riesgo/recomendacion de todos
        modos ni quedarse en silencio."""
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="ALCOA_AVAILABLE", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="EVALUATION_INCOMPLETE"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        row = report.rows[0]
        assert row.risk_recommendation_status == ufr.NOT_MAPPABLE
        assert "citation_locator/page_start/page_end" in row.not_mappable_reason
        assert row.change_risk is None


class TestRenderMarkdown:

    def test_render_never_declares_compliance(self, narrative_findings):
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="ANNEX11_7.1", bucket=t1.CONFIRMED,
                                   conclusion="PARTIALLY_DOCUMENTED",
                                   evidence_quote="cita real anclada", page_or_section="p.3"),
            t1.RequirementOutcome(requirement_id="NOT_IN_FIXTURE_SET", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="PROVISIONAL_GAP", review_queue_rc_id="finding-run-x-a"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        md = ufr.render_unified_finding_markdown(report)
        assert "cita real anclada" in md
        assert "HIGH_RISK" in md
        assert "Sin gap-assessment narrativo asociado" in md
        for banned in ("cumple con", "aprobado", "libera el lote", "cierra CAPA"):
            assert banned not in md.lower()
        assert "borrador asistido" in md.lower()

    def test_render_reports_not_mappable_reason(self, narrative_findings):
        tier1 = _tier1_report([
            t1.RequirementOutcome(requirement_id="ALCOA_AVAILABLE", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="EVALUATION_INCOMPLETE"),
        ])
        report = ufr.build_unified_finding_report(
            tier1, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            narrative_findings=narrative_findings)
        md = ufr.render_unified_finding_markdown(report)
        assert "NOT_MAPPABLE" in md
