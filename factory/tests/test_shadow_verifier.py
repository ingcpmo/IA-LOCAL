"""Tests -- factory/regulatory/shadow/verifier.py (SHADOW · G2.1 / G2.2).

G2.1  verificador fail-closed: fixtures adversariales obligatorios
      (cita/hash inexistente, MUST_NOT_CHANGE alterado, evidencia vacía)
      -> 100% SHADOW_REJECTED; ninguna salida inválida pasa al reporte.
G2.2  verificador de cobertura: 457/457 -> covered; omitir 1 -> falla.

CERO LLM, CERO red, determinista.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import contracts as C
from factory.regulatory.shadow import verifier as V

_REPO = Path(__file__).parent.parent.parent
_BASELINE = _REPO / "docs_plan" / "shadow_llm" / "FINAL_GMP_CORPUS_FINDINGS.json"


def _findings():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]


def _tech_finding():
    return next(f for f in _findings() if (f.get("technical_basis") or "").strip())


def _anchored_envelope(f, expert="TECHNICAL", assessment="INDETERMINATE"):
    quote = ((f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or "x")[:60]
    return {
        "schema": "SHADOW_OUTPUT_ENVELOPE/v1", "expert": expert,
        "finding_record_id": f["finding_record_id"], "shadow_layer": "L3",
        "assessment": assessment, "rationale": f"obs {C.SHADOW_MARK}",
        "anchored_citations": [{"finding_record_id": f["finding_record_id"], "quote": quote,
                                "page": f.get("page"), "source": C.CLIENT_EVIDENCE,
                                "source_hash": f.get("source_hash")}],
        "external_reg_references": [],
        "MUST_NOT_CHANGE": dict(C.must_not_change_block(f)),
        "confidence": "LOW",
        "model": {"provider": "LOCAL", "model_name": "m", "digest": "d",
                  "prompt_id": "p", "prompt_version": "1"},
        "produced_at": "2026-09-02T00:00:00Z",
    }


# ─────────────────────────── G2.1 ──────────────────────────────────────

def test_g21_positive_control_is_accepted():
    f = _tech_finding()
    r = V.verify_expert_envelope(_anchored_envelope(f), l2_finding=f)
    assert r.status == V.SHADOW_ACCEPTED
    assert r.reasons == []


def test_g21_citation_nonexistent_is_rejected():
    f = _tech_finding()
    env = _anchored_envelope(f)
    env["anchored_citations"] = [{"quote": "TEXTO INEXISTENTE EN L1/L2 XYZZY", "source": C.CLIENT_EVIDENCE}]
    r = V.verify_expert_envelope(env, l2_finding=f)
    assert r.status == V.SHADOW_REJECTED
    assert any("NO ancla" in x for x in r.anchoring_violations)


def test_g21_source_hash_mismatch_is_rejected():
    f = _tech_finding()
    env = _anchored_envelope(f)
    env["anchored_citations"][0]["source_hash"] = "0" * 64
    r = V.verify_expert_envelope(env, l2_finding=f)
    assert r.status == V.SHADOW_REJECTED
    assert any("source_hash" in x for x in r.anchoring_violations)


def test_g21_must_not_change_altered_is_rejected():
    f = _tech_finding()
    env = _anchored_envelope(f)
    env["MUST_NOT_CHANGE"] = dict(env["MUST_NOT_CHANGE"])
    env["MUST_NOT_CHANGE"]["subtype"] = "TAMPERED"
    r = V.verify_expert_envelope(env, l2_finding=f)
    assert r.status == V.SHADOW_REJECTED
    assert any("MUST_NOT_CHANGE.subtype" in x for x in r.structural_violations)


def test_g21_empty_evidence_is_rejected():
    f = _tech_finding()
    for cites in ([], [{"quote": "", "source": C.CLIENT_EVIDENCE}]):
        env = _anchored_envelope(f)
        env["anchored_citations"] = cites
        r = V.verify_expert_envelope(env, l2_finding=f)
        assert r.status == V.SHADOW_REJECTED


def test_g21_all_mandatory_adversarial_fixtures_100pct_rejected():
    demo = V.adversarial_demo(_findings())["G2_1_fail_closed_verifier"]
    assert demo["positive_control"]["status"] == V.SHADOW_ACCEPTED
    assert set(demo["adversarial"]) == {
        "citation_or_hash_nonexistent", "must_not_change_altered", "empty_evidence",
        "related_finding_ids_altered"}  # shadow-G2-r1
    assert all(v["status"] == V.SHADOW_REJECTED for v in demo["adversarial"].values())
    assert demo["all_adversarial_rejected"] is True
    assert demo["PASS"] is True


def test_g21_related_finding_ids_altered_is_rejected():
    f = _tech_finding()
    env = _anchored_envelope(f)
    env["MUST_NOT_CHANGE"] = dict(env["MUST_NOT_CHANGE"])
    env["MUST_NOT_CHANGE"]["related_finding_ids"] = ["injected-cross-domain-link"]
    r = V.verify_expert_envelope(env, l2_finding=f)
    assert r.status == V.SHADOW_REJECTED
    assert any("MUST_NOT_CHANGE.related_finding_ids" in x for x in r.structural_violations)


def test_g21_filter_accepted_drops_rejected_before_report():
    f = _tech_finding()
    good = _anchored_envelope(f)
    bad = _anchored_envelope(f)
    bad["anchored_citations"] = []
    accepted, rejected = V.filter_accepted([(good, f), (bad, f)])
    assert accepted == [good]
    assert len(rejected) == 1 and rejected[0].status == V.SHADOW_REJECTED


def test_g21_verifier_does_not_mutate_inputs():
    f = _tech_finding()
    env = _anchored_envelope(f)
    before = (json.dumps(f, sort_keys=True), json.dumps(env, sort_keys=True))
    V.verify_expert_envelope(env, l2_finding=f)
    assert (json.dumps(f, sort_keys=True), json.dumps(env, sort_keys=True)) == before


# ─────────────────────────── G2.2 ──────────────────────────────────────

def test_g22_full_457_coverage():
    findings = _findings()
    ids = [f["finding_record_id"] for f in findings]
    r = V.verify_report_coverage(findings, ids)
    assert r.covered is True
    assert r.total_l2 == 457 and r.referenced_valid == 457
    assert r.missing == [] and r.unsupported == []
    assert V.assert_full_coverage(findings, ids).covered is True


def test_g22_omitting_one_finding_is_detected_and_fails():
    findings = _findings()
    ids = [f["finding_record_id"] for f in findings]
    omitted = ids[123]
    partial = [i for i in ids if i != omitted]
    r = V.verify_report_coverage(findings, partial)
    assert r.covered is False
    assert r.missing == [omitted]
    with pytest.raises(V.CoverageError):
        V.assert_full_coverage(findings, partial)


def test_g22_unsupported_reference_is_detected():
    findings = _findings()
    ids = [f["finding_record_id"] for f in findings] + ["rec-does-not-exist"]
    r = V.verify_report_coverage(findings, ids)
    assert r.covered is False
    assert r.unsupported == ["rec-does-not-exist"]


def test_g22_demo_pass():
    demo = V.adversarial_demo(_findings())["G2_2_coverage_verifier"]
    assert demo["full_457"]["covered"] is True and demo["full_457"]["total_l2"] == 457
    assert demo["omit_one"]["covered"] is False
    assert demo["omit_one"]["assert_full_coverage_raised"] is True
    assert demo["PASS"] is True
