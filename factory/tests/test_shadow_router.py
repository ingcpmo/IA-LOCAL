"""Tests -- factory/regulatory/shadow/router.py (SHADOW · G1).

Router DETERMINISTA, sin LLM, sin red, solo lectura de L2.
Criterio de aceptación de G1 (diseño v1.1):
  routing primario EXCLUSIVO suma 457  (285 REGULATORY + 98 FUNCTIONAL + 17 TECHNICAL + 57 HUMAN_ONLY)
  + 15 cross_domain_flag SECUNDARIOS  (no un 5º bucket, no se suman a 457)
sobre el corpus baseline congelado en G0 (FINAL_GMP_CORPUS_FINDINGS.json, FINDINGS_FINGERPRINT 235f724a…).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import router as R

_REPO = Path(__file__).parent.parent.parent
_BASELINE = _REPO / "docs_plan" / "shadow_llm" / "FINAL_GMP_CORPUS_FINDINGS.json"
_DIAG_ROUTING = (_REPO / "docs_plan" / "shadow_llm" / "G0_inputs"
                 / "CURRENT_FINDING_AGENT_ROUTING.json")


def _findings():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]


def _routing():
    return R.build_routing(_findings(), source_ref=str(_BASELINE))


# ── forma de las reglas (unitario, sin depender del corpus) ──────────────

def test_human_only_wins_over_everything():
    f = {"finding_record_id": "x", "document": "RW-0009",
         "provenance": {"agent_id": "regulatory_tier1"},
         "technical_basis": "21_CFR_11.10(e)", "evidence_basis": "ABSENCE_DEPENDENT"}
    assert R.route_primary(f) == "HUMAN_ONLY"


def test_regulatory_before_technical_and_functional():
    f = {"finding_record_id": "x", "document": "RW-0006",
         "provenance": {"agent_id": "regulatory_tier1"}}
    assert R.route_primary(f) == "REGULATORY"


def test_technical_requires_non_empty_technical_basis():
    f = {"finding_record_id": "x", "document": "RW-0006",
         "provenance": {"agent_id": "data_integrity_agent"},
         "technical_basis": "ALCOA_ATTRIBUTABLE ; 21_CFR_11.10(d)"}
    assert R.route_primary(f) == "TECHNICAL"
    f["technical_basis"] = ""
    assert R.route_primary(f) != "TECHNICAL"


def test_functional_requires_absence_dependent_and_known_agent():
    f = {"finding_record_id": "x", "document": "RW-0006",
         "provenance": {"agent_id": "test_coverage_agent"},
         "evidence_basis": "ABSENCE_DEPENDENT"}
    assert R.route_primary(f) == "FUNCTIONAL_TRACEABILITY"
    f["evidence_basis"] = "INDETERMINATE"
    assert R.route_primary(f) == "UNROUTED"


def test_cross_domain_flag_only_on_technical():
    reg_fams = {"RW-0005": {"21_CFR_11.10(e)"}}
    tech = {"finding_record_id": "x", "document": "RW-0005",
            "provenance": {"agent_id": "technical_design_agent"},
            "technical_basis": "21_CFR_11.10(e)"}
    assert R.cross_domain_matches(tech, reg_fams) == ["21_CFR_11.10(e)"]
    reg = {"finding_record_id": "y", "document": "RW-0005",
           "provenance": {"agent_id": "regulatory_tier1"}, "requirement": "21_CFR_11.10(e)::sc1"}
    assert R.cross_domain_matches(reg, reg_fams) == []


# ── criterio de aceptación de G1 sobre el corpus baseline ────────────────

def test_acceptance_primary_routing_sums_457():
    s = _routing()["summary"]
    assert s["total_records"] == 457
    assert s["by_primary_bucket"] == {
        "REGULATORY": 285, "FUNCTIONAL_TRACEABILITY": 98, "TECHNICAL": 17, "HUMAN_ONLY": 57}
    assert sum(s["by_primary_bucket"].values()) == 457


def test_acceptance_no_unrouted_and_unique_records():
    a = _routing()["acceptance"]
    assert a["all_records_routed_exclusively"] is True
    assert a["unrouted_finding_record_ids"] == []
    assert a["unique_finding_record_id"] == 457
    assert a["PASS"] is True
    assert a["matches_expected_baseline"] is True


def test_acceptance_15_cross_domain_flags_secondary_only():
    r = _routing()
    assert r["summary"]["cross_domain_flags"] == 15
    flagged = [row for row in r["routing"] if row["cross_domain_flag"]]
    assert len(flagged) == 15
    # todos son TECHNICAL (flag secundario, nunca cambia el bucket primario)
    assert all(row["primary_bucket"] == "TECHNICAL" for row in flagged)
    # cada flag nombra >=1 regulación y >=1 contraparte regulatory_tier1 del mismo doc
    assert all(row["cross_domain_regulations"] for row in flagged)
    assert all(row["cross_domain_regulatory_counterparts"] for row in flagged)


def test_cross_domain_ids_match_g0_diagnostic():
    flagged = {row["finding_record_id"] for row in _routing()["routing"] if row["cross_domain_flag"]}
    diag = json.loads(_DIAG_ROUTING.read_text(encoding="utf-8"))
    diag_ids = {x["finding_record_id"]
                for x in diag["summary"]["cross_domain_same_requirement_family_detail"]}
    assert flagged == diag_ids


def test_router_does_not_mutate_input_findings():
    src = _findings()
    before = json.dumps(src, sort_keys=True)
    R.build_routing(src)
    assert json.dumps(src, sort_keys=True) == before  # L2 intacto


def test_human_only_are_all_rw0009_and_never_routed_to_llm():
    rows = _routing()["routing"]
    human = [r for r in rows if r["primary_bucket"] == "HUMAN_ONLY"]
    assert len(human) == 57
    assert all(r["document"] == "RW-0009" for r in human)
    # ningún RW-0009 cae en un bucket de experto LLM
    assert all(r["primary_bucket"] == "HUMAN_ONLY"
               for r in rows if r["document"] == "RW-0009")
