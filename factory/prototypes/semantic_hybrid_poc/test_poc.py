"""Suite PROPIA del POC (no toca la suite del proyecto). FASE 2, aislado.

Test obligatorio: cita fabricada -> el gate R5 la rechaza y degrada a INDETERMINATE.
Tests H-1/H-2/H-3: hallazgos del bake-off 2026-09-01 incorporados al gate.
"""
from __future__ import annotations

import json

from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc.citation_gate import (
    verify_quote, apply_gate, MATCH_THRESHOLD,
)
from factory.prototypes.semantic_hybrid_poc.validator import validate
from factory.prototypes.semantic_hybrid_poc.runner import assess, _cache_key
from factory.prototypes.semantic_hybrid_poc import stability as stab

_REAL_TEXT = ("The system enforces role based access for the operator interface. "
              "Three named roles are available: Operator, Supervisor and Engineer.")


# --------------------------------------------------------------------------- R5

def test_r5_rejects_fabricated_quote():
    scope = {"sec-x": _REAL_TEXT}
    real = verify_quote("role based access for the operator interface", scope)
    fab = verify_quote("the system re-authenticates the user before every critical operation", scope)
    assert real["verified"] is True and real["method"] == "literal"
    assert fab["verified"] is False


def test_r5_gate_degrades_to_indeterminate_on_all_fabricated():
    payload = {
        "required_elements": [
            {"element_id": "ac1", "verdict": "PRESENT",
             "supporting_quote": "the system re-authenticates before every operation"},
            {"element_id": "ac2", "verdict": "PRESENT",
             "supporting_quote": "authority is checked at the point of use for each transaction"},
        ],
        "semantic_coverage": "SUPPORTED",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "todos los elementos presentes",
        "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["quotes_verified"] == 0
    assert len(gated["fabricated_quotes"]) == 2
    assert gated["assessment_status"] == "INDETERMINATE"
    assert gated["semantic_coverage"] == "INDETERMINATE"
    for el in gated["elements_gated"]:
        assert el["supporting_quote"] is None
        assert el["verdict"] == "UNCLEAR"


# ----------------------------------------------------------------------- H-2

def test_h2_fuzzy_match_is_never_marked_verified():
    """R5 = substring literal. Un match difuso (>=0.93) NO es 'verified'."""
    scope = {"sec-x": _REAL_TEXT}
    # dos typos: no es substring literal, pero SequenceMatcher da ratio alto
    res = verify_quote("role based access for the operater interfase", scope)
    assert res["verified"] is False
    assert res["method"] != "literal"
    if res["method"] == "fuzzy":
        assert res["near_match"] is (res["score"] >= MATCH_THRESHOLD)


def test_h2_fuzzy_quote_does_not_count_toward_verification_rate():
    payload = {
        "required_elements": [
            {"element_id": "ac1", "verdict": "PRESENT",
             "supporting_quote": "role based access for the operater interfase"},  # casi-literal
        ],
        "semantic_coverage": "SUPPORTED",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["quotes_verified"] == 0
    assert gated["elements_gated"][0]["verdict"] == "UNCLEAR"      # H-3 tambien
    assert gated["assessment_status"] == "INDETERMINATE"


# ----------------------------------------------------------------------- H-3

def test_h3_present_without_quote_is_forced_unclear():
    payload = {
        "required_elements": [
            {"element_id": "cc1", "verdict": "PRESENT", "supporting_quote": None},
            {"element_id": "cc2", "verdict": "ABSENT", "supporting_quote": None},
        ],
        "semantic_coverage": "PARTIAL",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    el = {e["element_id"]: e for e in gated["elements_gated"]}
    assert el["cc1"]["verdict"] == "UNCLEAR"
    assert el["cc1"]["verdict_original"] == "PRESENT"
    assert el["cc2"]["verdict"] == "ABSENT"
    assert gated["elements_forced_unclear"] == 1
    # cc1 (PRESENT sin cita) -> no puede quedar CONFIRMS_ABSENCE
    assert gated["assessment_status"] == "INDETERMINATE"


def test_h3_contradictory_without_quote_is_forced_unclear():
    payload = {
        "required_elements": [
            {"element_id": "ai1", "verdict": "CONTRADICTORY", "supporting_quote": None},
        ],
        "semantic_coverage": "PARTIAL",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["elements_gated"][0]["verdict"] == "UNCLEAR"
    assert gated["elements_forced_unclear"] == 1


# ----------------------------------------------------------------------- H-1

def test_h1_all_absent_no_quotes_is_confirms_absence():
    payload = {
        "required_elements": [
            {"element_id": "br1", "verdict": "ABSENT", "supporting_quote": None},
            {"element_id": "br2", "verdict": "ABSENT", "supporting_quote": None},
            {"element_id": "br3", "verdict": "ABSENT", "supporting_quote": None},
        ],
        "semantic_coverage": "UNSUPPORTED",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "el contexto no describe backups", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["assessment_status"] == "CONFIRMS_ABSENCE"
    assert gated["semantic_coverage"] == "UNSUPPORTED"
    assert gated["quotes_emitted"] == 0
    assert gated["fabricated_quotes"] == []


def test_h1_mixed_absent_and_unclear_is_indeterminate_not_confirms_absence():
    payload = {
        "required_elements": [
            {"element_id": "br1", "verdict": "ABSENT", "supporting_quote": None},
            {"element_id": "br2", "verdict": "UNCLEAR", "supporting_quote": None},
        ],
        "semantic_coverage": "INDETERMINATE",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["assessment_status"] == "INDETERMINATE"


def test_h1_confirms_absence_requires_at_least_one_element():
    payload = {
        "required_elements": [],
        "semantic_coverage": "INDETERMINATE",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["assessment_status"] == "INDETERMINATE"


def test_h1_grounded_absence_stays_completed():
    """ABSENT con una cita literal que respalda la ausencia -> el modelo SI
    aporto evidencia verificable -> COMPLETED, no CONFIRMS_ABSENCE."""
    payload = {
        "required_elements": [
            {"element_id": "cc1", "verdict": "ABSENT",
             "supporting_quote": "Three named roles are available"},
        ],
        "semantic_coverage": "PARTIAL",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "x", "limitations": [],
    }
    gated = apply_gate(payload, {"sec-x": _REAL_TEXT})
    assert gated["quotes_verified"] == 1
    assert gated["assessment_status"] == "COMPLETED"


# ----------------------------------------------------------------- validador

def test_validator_fails_closed_on_truncated():
    gen = {"transport_error": None, "done_reason": "length", "raw_response": '{"required_eleme'}
    payload, status, errs = validate(gen)
    assert status == "FAILED" and payload is None and "truncated" in errs[0]


def test_validator_fails_closed_on_invalid_json():
    gen = {"transport_error": None, "done_reason": "stop", "raw_response": "not json at all"}
    payload, status, errs = validate(gen)
    assert status == "FAILED" and "json_invalid" in errs[0]


def test_validator_fails_closed_on_schema_violation():
    gen = {"transport_error": None, "done_reason": "stop",
           "raw_response": json.dumps({"required_elements": "wrong type"})}
    payload, status, errs = validate(gen)
    assert status == "FAILED" and any("schema" in e for e in errs)


# --------------------------------------------------------------------- cache

def test_cache_key_is_content_addressed_and_shared_on_same_source_hash():
    f1 = {"source_hash": "abc", "subtype": "AUTHORITY_CHECK_GAP", "finding_id": "f1"}
    f2 = {"source_hash": "abc", "subtype": "AUTHORITY_CHECK_GAP", "finding_id": "f2"}
    f3 = {"source_hash": "def", "subtype": "AUTHORITY_CHECK_GAP", "finding_id": "f3"}
    assert _cache_key(f1, "D") == _cache_key(f2, "D")
    assert _cache_key(f1, "D") != _cache_key(f3, "D")


# ----------------------------------------------------------------------- H-4

def _rec(status, verdicts, ohash):
    return {"assessment_status": status, "semantic_coverage": status,
            "output_hash": ohash, "wall_time_s": 1.0,
            "required_elements": [{"element_id": k, "verdict": v} for k, v in verdicts.items()]}


def test_h4_stable_when_status_and_verdicts_agree(monkeypatch):
    seq = iter([_rec("COMPLETED", {"e1": "PRESENT"}, "h1"),
                _rec("COMPLETED", {"e1": "PRESENT"}, "h2")])  # distinto hash, mismo status/verdict
    monkeypatch.setattr(stab, "assess", lambda f, m, **kw: next(seq))
    out = stab.assess_stable({"finding_id": "x"}, "qwen2.5:7b-instruct-q4_K_M", n=2)
    assert out["stability"]["stable"] is True
    assert out["stability_flag"] is False
    assert out["assessment_status"] == "COMPLETED"
    assert out["stability"]["output_bit_identical"] is False  # se reporta, no degrada


def test_h4_degrades_to_indeterminate_when_status_flips(monkeypatch):
    seq = iter([_rec("COMPLETED", {"e1": "PRESENT"}, "h1"),
                _rec("INDETERMINATE", {"e1": "UNCLEAR"}, "h2")])
    monkeypatch.setattr(stab, "assess", lambda f, m, **kw: next(seq))
    out = stab.assess_stable({"finding_id": "x"}, "qwen2.5:7b-instruct-q4_K_M", n=2)
    assert out["stability"]["stable"] is False
    assert out["stability_flag"] is True
    assert out["assessment_status"] == "INDETERMINATE"
    assert out["semantic_coverage"] == "INDETERMINATE"
    assert out["assessment_status_raw"] == "COMPLETED"      # se conserva el crudo


def test_h4_degrades_when_a_single_verdict_differs(monkeypatch):
    seq = iter([_rec("COMPLETED", {"e1": "PRESENT", "e2": "ABSENT"}, "h1"),
                _rec("COMPLETED", {"e1": "PRESENT", "e2": "UNCLEAR"}, "h2")])
    monkeypatch.setattr(stab, "assess", lambda f, m, **kw: next(seq))
    out = stab.assess_stable({"finding_id": "x"}, "qwen2.5:7b-instruct-q4_K_M", n=2)
    assert out["stability_flag"] is True
    assert out["assessment_status"] == "INDETERMINATE"


# ------------------------------------------------- test obligatorio (inyeccion)

def test_injected_fabricated_response_via_assess_degrades():
    finding = {"finding_id": "poc-inj", "document": "RW-0006", "page": 16,
               "subtype": "AUTHORITY_CHECK_GAP", "finding_class": "SecurityFinding",
               "source_text": "Engineer security level privileges.",
               "source_hash": "x" * 64, "section": "sec-caa61dcd3e461fab",
               "technical_basis": "21_CFR_11.10(g)"}
    injected = {
        "required_elements": [
            {"element_id": "ac1", "verdict": "PRESENT",
             "supporting_quote": "the system cryptographically verifies authority via SHA-256 tokens"},
            {"element_id": "ac2", "verdict": "PRESENT",
             "supporting_quote": "re-authentication is enforced before every parameter change"},
            {"element_id": "ac3", "verdict": "PRESENT",
             "supporting_quote": "this applies to all 512 system operations"},
        ],
        "semantic_coverage": "SUPPORTED",
        "contradictory_evidence": [], "supporting_evidence": [],
        "auditor_explanation": "fabricado", "limitations": [],
    }
    r = assess(finding, "qwen2.5:7b-instruct-q4_K_M", inject_response=injected)
    assert r["assessment_status"] == "INDETERMINATE"
    assert r["semantic_coverage"] == "INDETERMINATE"
    assert len(r["fabricated_quotes"]) == 3
    assert r["quotes_verified"] == 0
    assert r["elements_forced_unclear"] == 3
