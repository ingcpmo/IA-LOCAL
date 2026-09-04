"""Tests — CF-6 v1.2 · CF6-2.G + CF6-2.5 SAMPLE_MANIFEST (SHADOW, sin LLM).

  - cf6_pilot_scope.evaluate() : gate PILOT_SCOPE_MATCH_CF6 contra el ledger real
  - sample_manifest.build()    : selección determinista + criterios §4.1 + hash
CERO LLM.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import cf6_pilot_scope as PS
from factory.regulatory.shadow import sample_manifest as SM
from factory.regulatory.shadow import composer as CMP
from factory.regulatory.shadow import composer_gate as CG

_REPO = Path(__file__).parent.parent.parent
_LEDGER = _REPO / "factory" / "layer9" / "decisions" / "decisions_v2.jsonl"
_SL = _REPO / "docs_plan" / "shadow_llm"


# ───────────────────────── CF6-2.G ─────────────────────────────────

def test_pilot_scope_gate_fails_closed_on_current_ledger():
    res = PS.evaluate(_LEDGER)
    assert res["gate"] == "CF6-2.G"
    assert res["llm_calls"] == 0
    # -035/-036 autorizaron SHADOW_G4A..G4E (interpretación experta), NO el
    # composer_prompt_version nuevo ni CF6-2.5/CF6-3 ni la emisión de estructura JSON.
    assert res["PILOT_SCOPE_MATCH_CF6"] == "NO"
    assert res["scope_checks"] == {
        "a_composer_prompt_version": "NO", "b_cf6_2_5": "NO",
        "c_cf6_3": "NO", "d_execution_type_json_structure": "NO"}
    assert res["GATE_RESULT"] == "FAIL"
    assert "STOP" in res["decision"]


def test_pilot_scope_gate_reports_budget_active_not_superseded():
    res = PS.evaluate(_LEDGER)
    assert res["REMAINING_BUDGET_SUFFICIENT"] == "YES"
    assert res["remaining_calls"] == 519          # 1000 - 481 (G4)
    assert res["ACTIVE"] == "YES"
    assert res["NOT_SUPERSEDED"] == "YES"


def test_latest_pilot_is_a_pilot_execution_record():
    p = PS.latest_pilot(_LEDGER)
    assert p is not None
    blob = str(p)
    assert "PILOT_EXECUTION" in blob and "scope" in blob


# ───────────────────────── CF6-2.5 SAMPLE_MANIFEST ────────────────

def test_manifest_is_draft_and_llm_free():
    m = SM.build(_SL)
    assert m["status"] == "DRAFT_PENDING_CF6_2_G_PASS"
    assert m["llm_calls"] == 0
    assert m["integrity"]["LLM_CALLS"] == 0
    assert m["integrity"]["FINDINGS_FINGERPRINT"].startswith("235f724a738ce783")


def test_manifest_meets_all_mandatory_inclusion_criteria():
    m = SM.build(_SL)
    assert m["mandatory_all_present"] is True
    assert set(SM.MANDATORY_SECTIONS) <= set(m["sections_selected"])
    c = m["inclusion_criteria_counts"]
    assert c["regulatory_with_inconclusive_>=2"] >= 2
    assert c["functional_traceability_>=1"] >= 1
    assert c["technical_>=1"] >= 1
    assert c["cross_domain_>=2"] >= 2
    assert m["inclusion_criteria_pass"] is True
    assert sorted(m["categories_covered"]) == [
        "CROSS_DOMAIN", "FUNCTIONAL_TRACEABILITY", "REGULATORY", "TECHNICAL"]


def test_manifest_hash_is_deterministic():
    assert SM.build(_SL)["sample_manifest_hash"] == SM.build(_SL)["sample_manifest_hash"]


def test_manifest_rows_match_deterministic_section_types():
    findings = __import__("json").loads(
        (_SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    by_id = {s["section_id"]: s for s in CMP.build_composer_skeleton(findings)["sections"]}
    for row in SM.build(_SL)["rows"]:
        s = by_id[row["section_id"]]
        st, _ = CG.infer_section_type(s)
        assert row["section_type"] == st
        assert row["regulatory_state_expected"] == CG.expected_regulatory_state(s)


def test_mandatory_sections_have_expected_types():
    rows = {r["section_id"]: r for r in SM.build(_SL)["rows"]}
    assert rows["sec-0016"]["section_type"] == "REGULATORY"
    assert rows["sec-0062"]["section_type"] == "REGULATORY"
    assert rows["sec-0018"]["section_type"] == "CROSS_DOMAIN"
    for sid in ("sec-0016", "sec-0062", "sec-0018"):
        assert rows[sid]["regulatory_state_expected"] == "INCONCLUSIVE"
        assert rows[sid]["has_inconclusive_finding"] is True
