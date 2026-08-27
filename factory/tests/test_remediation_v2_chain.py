"""Tests -- factory/regulatory/findings/remediation_v2.py (V2, B7).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 8: cadena
causal exigida finding -> RemediationDirective -> candidate -> redline ->
manifest; manifest NO se emite sin la cadena completa; marca obligatoria
MACHINE GENERATED; PROHIBIDO QA_APPROVED / RELEASED / CAPA_CLOSED /
FINAL_GMP_APPROVAL. Determinista, sin LLM.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.findings import remediation_v2 as rem
from factory.regulatory.findings.taxonomy import FindingProvenance, build_finding


def _finding(machine_state="MACHINE_DEVIATION_CANDIDATE"):
    return build_finding(
        "RegulatoryFinding", "REGULATORY_GAP", severity="MAJOR", document="RW-0005",
        page=45, source_text="The system logs alarm changes.",
        rationale="audit trail incompleto: falta timestamp y valor previo",
        confidence="MEDIUM", machine_state=machine_state,
        provenance=FindingProvenance(document_id="RW-0005", extraction_version="v1",
                                     run_id="run-1", subcriterion_ref="21_CFR_11.10(e)::sc2"),
        requirement_id="21_CFR_11.10(e)", evidence_ids=["evd-1"],
    )


PROPOSED = ("The system shall log every alarm threshold change with a secure, computer-generated "
            "timestamp, the operator identity, and the previous and new values.")


def test_build_proposal_carries_traceability_and_mark():
    p = rem.build_proposal(_finding(), proposed_text=PROPOSED)
    assert p.finding_id.startswith("fnd-")
    assert p.mark == rem.MACHINE_GENERATED_MARK
    assert p.original_excerpt == "The system logs alarm changes."
    assert p.traceability["requirement_id"] == "21_CFR_11.10(e)"
    assert p.traceability["evidence_ids"] == ["evd-1"]
    assert p.traceability["subcriterion_ref"] == "21_CFR_11.10(e)::sc2"


def test_non_remediable_state_rejected():
    with pytest.raises(rem.RemediationChainError):
        rem.build_proposal(_finding("MACHINE_INCONCLUSIVE"), proposed_text=PROPOSED)


def test_redline_is_deterministic_and_does_not_touch_document():
    p = rem.build_proposal(_finding(), proposed_text=PROPOSED)
    r1 = rem.apply_and_redline(p)
    r2 = rem.apply_and_redline(p)
    assert r1.diff_unified == r2.diff_unified
    assert "The system logs alarm changes." in r1.diff_unified          # línea original (-)
    assert "previous and new values" in r1.candidate_excerpt
    assert r1.candidate_excerpt_hash == r2.candidate_excerpt_hash


def test_manifest_requires_complete_chain():
    f = _finding()
    p = rem.build_proposal(f, proposed_text=PROPOSED)
    r = rem.apply_and_redline(p)
    chain = rem.RemediationChain(finding=f, proposal=p, redline=r)
    m = chain.build_manifest()
    assert m["chain_complete"] is True
    assert m["qa_status"] == "NOT_QA_APPROVED"
    assert m["mark"] == rem.MACHINE_GENERATED_MARK
    assert [c["link"] for c in m["chain"]] == ["finding", "remediation_directive", "candidate", "redline"]
    assert m["human_state"] == "UNREVIEWED"
    assert m["docx_backed"] is False


def test_manifest_broken_link_refused():
    f = _finding()
    p = rem.build_proposal(f, proposed_text=PROPOSED)
    r = rem.apply_and_redline(p)
    # redline de OTRA propuesta -> eslabón roto
    other = rem.build_proposal(_finding(), proposed_text=PROPOSED + " extra")
    r_other = rem.apply_and_redline(other)
    with pytest.raises(rem.RemediationChainError):
        rem.RemediationChain(finding=f, proposal=p, redline=r_other).build_manifest()


def test_require_docx_needs_real_hashes():
    f = _finding()
    p = rem.build_proposal(f, proposed_text=PROPOSED)
    r = rem.apply_and_redline(p)
    chain = rem.RemediationChain(finding=f, proposal=p, redline=r)
    with pytest.raises(rem.RemediationChainError):
        chain.build_manifest(require_docx=True)
    m = chain.build_manifest(require_docx=True, candidate_doc_sha256="a" * 64,
                             redline_doc_sha256="b" * 64, insertion_manifest={"sections": []})
    assert m["docx_backed"] is True


def test_forbidden_state_anywhere_is_rejected():
    f = _finding()
    p = rem.build_proposal(f, proposed_text=PROPOSED)
    r = rem.apply_and_redline(p)
    # inyectar un estado prohibido en el finding y construir la cadena
    object.__setattr__(f, "human_state", "QA_APPROVED")
    with pytest.raises(rem.RemediationChainError):
        rem.RemediationChain(finding=f, proposal=p, redline=r).build_manifest()


def test_current_pipeline_change_adapter_shape():
    p = rem.build_proposal(_finding(), proposed_text=PROPOSED, change_type="insert_after")
    ch = rem.to_current_pipeline_change(p)
    assert ch["page_start"] == 45
    assert ch["change_type"] == "insert_after"
    assert ch["new_text"] == PROPOSED
    assert ch["mark"] == rem.MACHINE_GENERATED_MARK
    assert ch["finding_id"] == p.finding_id
