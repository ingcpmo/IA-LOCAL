"""Tests -- factory/regulatory/shadow/composer.py (SHADOW · G3.1).

Composer esqueleto DETERMINISTA (sin LLM):
  - cubre EXACTAMENTE 457/457 finding_record_id
  - agrupa por documento × regulación; cada finding en una sola sección
  - cada entrada traza al finding L2 (cita + rationale verbatim) y NO re-juzga L2
  - narrativa LLM = PENDIENTE
CERO LLM, CERO red.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import composer as CMP

_REPO = Path(__file__).parent.parent.parent
_BASELINE = _REPO / "docs_plan" / "shadow_llm" / "FINAL_GMP_CORPUS_FINDINGS.json"


def _findings():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]


def _sk():
    return CMP.build_composer_skeleton(_findings(), source_ref=str(_BASELINE))


def test_deterministic_mode_no_llm():
    sk = _sk()
    assert sk["mode"] == "DETERMINISTIC_SKELETON"
    assert sk["llm"] == "NONE"
    assert sk["narrative_status"] == CMP.NARRATIVE_PENDING


def test_covers_exactly_457_of_457():
    sk = _sk()
    rids = [e["finding_record_id"] for s in sk["sections"] for e in s["entries"]]
    assert len(rids) == 457
    assert len(set(rids)) == 457
    assert {f["finding_record_id"] for f in _findings()} == set(rids)
    assert sk["summary"]["coverage"] == {
        "covered": True, "total_l2": 457, "referenced_valid": 457,
        "missing": [], "unsupported": []}
    assert sk["acceptance"]["PASS"] is True


def test_grouping_is_document_x_regulation_and_disjoint():
    sk = _sk()
    seen = set()
    keys = set()
    for s in sk["sections"]:
        assert s["document"] and s["regulation"]
        keys.add((s["document"], s["regulation"]))
        for e in s["entries"]:
            assert e["finding_record_id"] not in seen  # exactamente una sección
            seen.add(e["finding_record_id"])
            assert e["document"] == s["document"]
    assert len(keys) == len(sk["sections"])
    assert len(seen) == 457
    # RW-0009 (NOT_ANALYZABLE) tiene su propia sección de revisión humana
    rw9 = [s for s in sk["sections"] if s["document"] == "RW-0009"]
    assert len(rw9) == 1
    assert "NOT_ANALYZABLE" in rw9[0]["regulation"]
    assert all(e["primary_bucket"] == "HUMAN_ONLY" for e in rw9[0]["entries"])


def test_per_document_counts_match_l2():
    sk = _sk()
    assert sk["summary"]["sections_by_document"] == {
        "RW-0005": 88, "RW-0006": 133, "RW-0009": 57,
        "RW-0011": 58, "RW-0012": 62, "RW-0014": 59}
    assert sk["summary"]["by_primary_bucket"] == {
        "REGULATORY": 285, "FUNCTIONAL_TRACEABILITY": 98,
        "TECHNICAL": 17, "HUMAN_ONLY": 57}


def test_each_entry_is_traceable_and_not_rejudged():
    findings = {f["finding_record_id"]: f for f in _findings()}
    sk = CMP.build_composer_skeleton(list(findings.values()))
    for s in sk["sections"]:
        for e in s["entries"]:
            f = findings[e["finding_record_id"]]
            # facts L2 verbatim (no re-juicio)
            assert e["subtype"] == f["subtype"]
            assert e["risk_band"] == (f.get("risk") or {}).get("band")
            assert e["machine_state"] == f["machine_state"]
            assert e["human_state"] == f["human_state"] == "UNREVIEWED"
            assert e["page"] == f["page"]
            # trazabilidad: cita y rationale L2 verbatim
            q = (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""
            assert e["anchored_quote_l2"] == q
            assert e["rationale_l2"] == (f.get("rationale") or "")
    assert sk["acceptance"]["no_rejudge_l2"] is True


def test_narrative_and_expert_are_pending():
    sk = _sk()
    for s in sk["sections"]:
        for e in s["entries"]:
            assert e["shadow_narrative"] is None
            assert e["shadow_expert_assessment"] is None
            assert e["narrative_status"] == CMP.NARRATIVE_PENDING
    assert sk["acceptance"]["narrative_all_pending"] is True
    assert sk["acceptance"]["expert_all_pending"] is True


def test_cross_domain_link_ids_populated_for_the_15():
    sk = _sk()
    flagged = [e for s in sk["sections"] for e in s["entries"] if e["cross_domain_link_ids"]]
    tech_flagged = [e for e in flagged if e["primary_bucket"] == "TECHNICAL"]
    assert len(tech_flagged) == 15  # los 15 técnicos de cross_domain_links.json
    assert all(lid.startswith("cdl-") for e in flagged for lid in e["cross_domain_link_ids"])


def test_composer_does_not_mutate_l2():
    findings = _findings()
    before = json.dumps(findings, sort_keys=True)
    CMP.build_composer_skeleton(findings)
    assert json.dumps(findings, sort_keys=True) == before


def test_deterministic_output():
    a = json.dumps(_sk(), sort_keys=True)
    b = json.dumps(_sk(), sort_keys=True)
    assert a == b


def test_assert_full_coverage_or_raise_passes_on_baseline():
    CMP.assert_full_coverage_or_raise(_sk())  # no raise


def test_assert_full_coverage_or_raise_fails_when_incomplete():
    import pytest
    findings = _findings()[:-1]  # 456
    sk = CMP.build_composer_skeleton(findings)
    # con 456 el coverage 457/457 falla -> acceptance PASS = False
    assert sk["acceptance"]["PASS"] is False
    with pytest.raises(Exception):
        CMP.assert_full_coverage_or_raise(sk)
