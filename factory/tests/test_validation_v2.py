"""Tests -- factory/regulatory/validation_v2/ (V2, B8a).

FASE 10: evaluadores de gate deterministas, chequeo LOCAL_ONLY, carga de
fixtures B/C (borrador, fail-closed). Sin LLM.
"""
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.validation_v2 import fixtures, gates, runner
from factory.regulatory.validation_v2.local_only import (
    EgressBlocked, network_locked, run_local_only,
)


# ── gates: Suite A ─────────────────────────────────────────────────────

def _reg_cases(pos_ok, neg_ok, fabricated=0):
    cases = []
    for i in range(7):
        cases.append({"case_id": f"P{i}", "kind": "positive",
                      "anchored": i < pos_ok, "fabricated_citation": i < fabricated,
                      "schema_valid": True, "latency_s": 12.0})
    for i in range(2):
        cases.append({"case_id": f"N{i}", "kind": "negative",
                      "anchored": i >= neg_ok, "fabricated_citation": False,
                      "schema_valid": True, "latency_s": 8.0})
    return cases


def test_regulatory_pass_when_6of7_and_negatives_ok():
    rep = gates.evaluate_regulatory(_reg_cases(6, 2))
    assert rep.all_passed
    assert gates.interpret_regulatory(rep).startswith("V2_RESUELVE_RECALL")


def test_regulatory_fail_when_below_6():
    rep = gates.evaluate_regulatory(_reg_cases(2, 2))
    assert not rep.all_passed
    assert "TECHO_NO_CRUZADO" in gates.interpret_regulatory(rep)


def test_regulatory_hard_fail_on_fabricated_citation():
    rep = gates.evaluate_regulatory(_reg_cases(7, 2, fabricated=1))
    assert not rep.all_passed
    assert "FALLO_DURO" in gates.interpret_regulatory(rep)


def test_regulatory_hard_fail_when_negative_not_rejected():
    rep = gates.evaluate_regulatory(_reg_cases(7, 1))   # solo 1/2 negativos rechazados
    assert "FALLO_DURO" in gates.interpret_regulatory(rep)


def test_intermediate_range_asks_capa9():
    rep = gates.evaluate_regulatory(_reg_cases(4, 2))
    assert "MEJORA_INSUFICIENTE" in gates.interpret_regulatory(rep)


# ── gates: Suites B/C ─────────────────────────────────────────────────

def test_functional_recall_and_fp():
    cases = ([{"case_id": f"e{i}", "expected_finding": True, "emitted_finding": True,
               "subtype_match": True} for i in range(9)]
             + [{"case_id": "e9", "expected_finding": True, "emitted_finding": False}]
             + [{"case_id": "n0", "expected_finding": False, "emitted_finding": False}])
    rep = gates.evaluate_functional(cases)
    recall = next(g for g in rep.gates if g.name == "FUNCTIONAL_RECALL")
    assert recall.value == 0.9 and recall.passed
    assert rep.all_passed


def test_functional_fails_on_false_positives():
    cases = ([{"case_id": f"e{i}", "expected_finding": True, "emitted_finding": True} for i in range(10)]
             + [{"case_id": f"n{i}", "expected_finding": False, "emitted_finding": True} for i in range(3)])
    rep = gates.evaluate_functional(cases)
    fp = next(g for g in rep.gates if g.name == "FUNCTIONAL_FALSE_POSITIVE")
    assert not fp.passed


# ── transversal + runner ─────────────────────────────────────────────

def test_transversal_gate_local_only():
    ok = gates.evaluate_transversal(local_only=True, document_egress_bytes=0,
                                    human_gate_intact=True, audit_chain_status="VERIFIED",
                                    gate0_factory_pass=True, traceability_complete=True)
    assert ok.all_passed
    bad = gates.evaluate_transversal(local_only=False, document_egress_bytes=1234,
                                     human_gate_intact=True, audit_chain_status="VERIFIED",
                                     gate0_factory_pass=True, traceability_complete=True)
    assert not bad.all_passed


def test_full_report_markdown():
    rep = runner.build_full_report(
        regulatory_cases=_reg_cases(6, 2),
        functional_cases=[{"case_id": "e0", "expected_finding": True, "emitted_finding": True}],
        technical_cases=[{"case_id": "e0", "expected_finding": True, "emitted_finding": True}],
        transversal=dict(local_only=True, document_egress_bytes=0, human_gate_intact=True,
                         audit_chain_status="ACCEPTED_WITH_DOCUMENTED_EXCEPTION",
                         gate0_factory_pass=True, traceability_complete=True),
    )
    assert rep["all_gates_passed"]
    md = runner.render_markdown(rep)
    assert "Interpretación Suite A" in md
    assert "PROHIBIDO aflojar validadores" in md


# ── LOCAL_ONLY ────────────────────────────────────────────────────────

def test_local_connection_allowed():
    with network_locked() as report:
        s = socket.socket()
        try:
            s.connect_ex(("127.0.0.1", 9))   # loopback: permitido (fallará por puerto, no por bloqueo)
        finally:
            s.close()
    assert report.local_only and report.document_egress_bytes == 0


def test_outbound_connection_blocked():
    def _try_egress():
        s = socket.socket()
        s.connect(("8.8.8.8", 443))
    with pytest.raises(EgressBlocked):
        run_local_only(_try_egress)


def test_run_local_only_clean_callable():
    result, report = run_local_only(lambda: 2 + 2)
    assert result == 4
    assert report.local_only and report.document_egress_bytes == 0


# ── fixtures B/C (borrador) ──────────────────────────────────────────

def test_suite_b_shape_and_distribution():
    assert fixtures.case_count(fixtures.SUITE_B) == 20
    dist = fixtures.distribution(fixtures.SUITE_B)
    assert dist.get("NO_FINDING") == 5
    assert dist.get("REQUIREMENT_NOT_IMPLEMENTED") == 5
    assert dist.get("REQUIREMENT_NOT_TESTED") == 5
    assert dist.get("CONTRADICTORY_FUNCTIONAL_BEHAVIOR") == 5


def test_suite_c_shape():
    assert fixtures.case_count(fixtures.SUITE_C) == 20
    dist = fixtures.distribution(fixtures.SUITE_C)
    assert dist.get("NO_FINDING") == 7
    assert sum(v for k, v in dist.items() if k != "NO_FINDING") == 13


def test_fixtures_are_draft_unsigned_fail_closed():
    assert not fixtures.is_signed(fixtures.SUITE_B)
    with pytest.raises(fixtures.FixtureNotSignedError):
        fixtures.assert_signed(fixtures.SUITE_B)
    with pytest.raises(fixtures.FixtureNotSignedError):
        fixtures.assert_signed(fixtures.SUITE_C)
