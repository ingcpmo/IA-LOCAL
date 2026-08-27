"""Tests -- factory/regulatory/findings/{from_verdicts,report_v2}.py (V2, B5).

Puente B4 -> B5 (SubcriterionVerdict -> RegulatoryFinding) + render del
informe V2 por clase. Determinista, sin LLM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.retrieval.evidence_bundle import EvidenceBundle
from factory.regulatory.findings import from_verdicts as fv
from factory.regulatory.findings import report_v2
from factory.regulatory.findings.taxonomy import build_finding, FindingProvenance
from factory.regulatory.v2_judgment import adjudicator as adj
from factory.regulatory.v2_judgment.judgment_v2 import CandidateOutcome, SubcriterionVerdict


def _bundle(sc_id="sc1", req="21_CFR_11.10(e)"):
    return EvidenceBundle(
        document_id="RW-0005", requirement_id=req, subcriterion_id=sc_id,
        subcriterion_ref=f"{req}::{sc_id}", subcriterion_text="audit trail con timestamp",
        candidate_claims=[{
            "claim_id": "clm-1",
            "source_text": "The system generates a time-stamped audit trail record for every operator entry.",
            "normalized_statement": "audit trail", "pagina": 45, "section_id": None,
            "tipo": "control", "provenance": {"document_id": "RW-0005", "page": 45},
        }],
    )


def _verdict(state, sc_id="sc1", req="21_CFR_11.10(e)", quote=None, page=None):
    v = SubcriterionVerdict(subcriterion_ref=f"{req}::{sc_id}", requirement_id=req, state=state)
    v.candidate_outcomes = [CandidateOutcome("clm-1", "desc", "SATISFIES", quote or "",
                                             "verified", "AGREE", state, ["x"])]
    v.best_quote = quote
    v.best_page = page
    return v


def test_confirmed_verdict_becomes_compliant_evidence_finding():
    b = _bundle()
    v = _verdict(adj.MACHINE_CONFIRMED, quote=b.candidate_claims[0]["source_text"], page=45)
    fs = fv.regulatory_findings_from_verdicts(
        [(v, b)], document_id="RW-0005", extraction_version="canonical-v1-2026-08",
        run_id="run-1", agent_id="fda_part11_agent")
    assert len(fs) == 1
    f = fs[0]
    assert f.finding_class == "RegulatoryFinding"
    assert f.subtype == "REGULATORY_COMPLIANT_EVIDENCE"
    assert f.machine_state == "MACHINE_CONFIRMED_FINDING"
    assert f.confidence == "HIGH"
    assert f.human_state == "UNREVIEWED"
    assert f.requirement_id == "21_CFR_11.10(e)"
    assert f.risk["band"] in ("LOW", "MEDIUM")
    assert f.provenance.subcriterion_ref == "21_CFR_11.10(e)::sc1"
    assert f.provenance.adjudicator_state == adj.MACHINE_CONFIRMED


def test_evidence_not_found_becomes_inconclusive_not_gap():
    b = _bundle()
    v = _verdict(adj.EVIDENCE_NOT_FOUND)
    f = fv.regulatory_findings_from_verdicts(
        [(v, b)], document_id="RW-0005", extraction_version="v1")[0]
    assert f.subtype == "REGULATORY_INCONCLUSIVE"
    assert f.machine_state == "MACHINE_INCONCLUSIVE"
    assert "GAP" not in f.machine_state


def test_no_anchor_no_finding():
    b = _bundle()
    b.candidate_claims = []
    v = _verdict(adj.INCONCLUSIVE)
    assert fv.regulatory_findings_from_verdicts(
        [(v, b)], document_id="RW-0005", extraction_version="v1") == []


def test_report_groups_by_class_and_has_gxp_header():
    prov = FindingProvenance(document_id="RW-0005", extraction_version="v1")
    findings = [
        build_finding("RegulatoryFinding", "REGULATORY_GAP", severity="CRITICAL",
                      document="RW-0005", page=45, source_text="no audit trail present",
                      rationale="r1", confidence="MEDIUM",
                      machine_state="MACHINE_DEVIATION_CANDIDATE", provenance=prov,
                      requirement_id="21_CFR_11.10(e)", risk={"band": "CRITICAL", "score": 54}),
        build_finding("TestCoverageFinding", "REQUIREMENT_NOT_TESTED", severity="MAJOR",
                      document="RW-0005", page=12, source_text="UR3.3.1 has no SAT step",
                      rationale="r2", confidence="LOW",
                      machine_state="MACHINE_DEVIATION_CANDIDATE", provenance=prov,
                      risk={"band": "MEDIUM", "score": 12}),
    ]
    rep = report_v2.build_report(findings, document_id="RW-0005", run_id="run-1")
    assert rep["summary"]["total_findings"] == 2
    assert rep["summary"]["by_class"] == {"RegulatoryFinding": 1, "TestCoverageFinding": 1}
    assert rep["summary"]["human_review_required"] == 2
    md = report_v2.render_markdown(rep)
    assert "NO es una declaración de cumplimiento" in md
    assert "Hallazgos regulatorios (1)" in md
    assert "Hallazgos de cobertura de pruebas (1)" in md
    # el crítico va antes (orden por banda de riesgo)
    assert md.index("REGULATORY_GAP") < md.index("REQUIREMENT_NOT_TESTED")
    assert report_v2.to_json(rep)
