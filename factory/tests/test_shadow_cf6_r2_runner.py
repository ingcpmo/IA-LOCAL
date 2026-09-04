"""Tests — CF-6 v2.0 · R2.2 runner (cf6_r2_runner.py). SHADOW, sin LLM
(dry_run=True para las pruebas de forma; el run real con LLM se ejecuta y
audita por separado, ver CF6_v2_R2_RUN.json)."""
from __future__ import annotations

import json

from factory.regulatory.shadow import cf6_r2_runner as R2
from factory.regulatory.shadow import composer as _skel


def _skeleton():
    findings = json.loads(open("docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json",
                               encoding="utf-8").read())["findings"]
    return _skel.build_composer_skeleton(findings), {f["finding_record_id"]: f for f in findings}


class TestInScope:
    def test_regulated_decomposed_section_in_scope(self):
        sk, _ = _skeleton()
        sec = next(s for s in sk["sections"] if s["section_id"] == "sec-0016")
        in_scope, reason = R2._in_scope_r2(sec)
        assert in_scope is True
        assert reason is None

    def test_undecomposed_regulation_out_of_scope(self):
        sk, _ = _skeleton()
        sec = next(s for s in sk["sections"] if s["section_id"] == "sec-0026")
        in_scope, reason = R2._in_scope_r2(sec)
        assert in_scope is False
        assert "ANNEX11_7" in reason

    def test_no_regulation_section_out_of_scope(self):
        sk, _ = _skeleton()
        sec = next(s for s in sk["sections"] if s["section_id"] == "sec-0042")
        in_scope, reason = R2._in_scope_r2(sec)
        assert in_scope is False


class TestAdapter:
    def test_adapt_maps_r1_fields_to_legacy_keys(self):
        sk, _ = _skeleton()
        sec = next(s for s in sk["sections"] if s["section_id"] == "sec-0016")
        structured = {
            "assessment_state": "INCONCLUSIVE",
            "evidence_basis": [{"finding_record_id": "rec-x", "quote": "q"}],
            "evidence_limitation": ["lim"],
            "technical_assessment": "ta", "procedural_responsibility": "pr",
            "assessment_rationale": "ar", "gap_or_open_question": "goq",
            "prohibited_conclusion": "NONE",
        }
        legacy = R2._adapt_r1_to_legacy_view(structured, sec)
        assert legacy["regulatory_state"] == "INCONCLUSIVE"
        assert legacy["evidence_observed"] == [{"finding_record_id": "rec-x", "quote": "q"}]
        assert legacy["reviewer_action"] == "goq"
        assert set(legacy["technical_findings"]) == {"ta", "pr", "ar"}
        assert legacy["section_type"] in ("REGULATORY", "CROSS_DOMAIN", "TECHNICAL", "FUNCTIONAL_TRACEABILITY")
        assert legacy["prohibited_conclusion"] == "NONE"


class TestDryRun:
    def test_dry_run_matches_manifest_shape_no_llm(self):
        s = R2.run_r2(dry_run=True)
        assert s["LLM_CALLS_TOTAL"] == 0
        assert s["POST_QSTATE_LLM_CALLS"] == 0
        assert s["sections_out_of_scope_r2"] == 2
        assert "sec-0026" in s["OUT_OF_SCOPE_SECTIONS"]
        assert "sec-0042" in s["OUT_OF_SCOPE_SECTIONS"]
        assert s["within_budget"] is True

    def test_dry_run_does_not_touch_decomposition_yaml(self):
        import hashlib
        from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
            DECOMPOSITION_PATH,
        )
        before = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        R2.run_r2(dry_run=True)
        after = hashlib.sha256(DECOMPOSITION_PATH.read_bytes()).hexdigest()
        assert before == after
