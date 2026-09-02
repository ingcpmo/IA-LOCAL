"""Tests -- factory/regulatory/shadow/contracts.py (SHADOW · G2).

Contratos declarativos + validación ESTRUCTURAL (no de anclaje).
CERO LLM, CERO red. G2 no ejecuta nada; solo define y valida forma.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import contracts as C

_REPO = Path(__file__).parent.parent.parent
_BASELINE = _REPO / "docs_plan" / "shadow_llm" / "FINAL_GMP_CORPUS_FINDINGS.json"


def _a_technical_finding():
    findings = json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]
    return next(f for f in findings if (f.get("technical_basis") or "").strip())


def _well_formed_envelope(finding, expert="TECHNICAL", assessment="INDETERMINATE"):
    return {
        "schema": "SHADOW_OUTPUT_ENVELOPE/v1",
        "expert": expert,
        "finding_record_id": finding["finding_record_id"],
        "shadow_layer": "L3",
        "assessment": assessment,
        "rationale": f"Observación del experto. {C.SHADOW_MARK}",
        "anchored_citations": [{"finding_record_id": finding["finding_record_id"],
                                "quote": (finding.get("source_text") or "x")[:40],
                                "page": finding.get("page"), "source": C.CLIENT_EVIDENCE}],
        "external_reg_references": [],
        "MUST_NOT_CHANGE": dict(C.must_not_change_block(finding)),
        "confidence": "LOW",
        "model": {"provider": "LOCAL", "model_name": "m", "digest": "d",
                  "prompt_id": "p", "prompt_version": "1"},
        "produced_at": "2026-09-02T00:00:00Z",
    }


# ── contrato bien formado ──────────────────────────────────────────────

def test_must_not_change_covers_l2_immutable_set():
    for k in ("finding_record_id", "finding_class", "subtype", "severity",
              "risk_band", "requirement_id", "machine_state", "human_state",
              "document", "page", "source_hash"):
        assert k in C.MUST_NOT_CHANGE_FIELDS


def test_no_expert_assessment_is_a_compliance_verdict():
    for expert, values in C.ASSESSMENT_VALUES.items():
        for a in values:
            assert not any(tok in a.upper() for tok in C.FORBIDDEN_ASSESSMENT_TOKENS), (expert, a)


def test_every_expert_has_context_spec_and_assessment_enum():
    for e in C.EXPERTS:
        assert e in C.INPUT_CONTEXT_SPEC and C.INPUT_CONTEXT_SPEC[e]
        assert e in C.ASSESSMENT_VALUES and C.ASSESSMENT_VALUES[e]


def test_cross_domain_disagreement_triggers_human_review():
    assert C.CROSS_DOMAIN_HUMAN_REVIEW_TRIGGER in C.ASSESSMENT_VALUES["CROSS_DOMAIN"]
    assert C.CROSS_DOMAIN_HUMAN_REVIEW_TRIGGER == "DISAGREEMENT_PERSISTS"


# ── build_input_package ───────────────────────────────────────────────

def test_input_package_copies_only_whitelisted_l2_and_requires_context():
    f = _a_technical_finding()
    ctx = {k: [] for k in C.INPUT_CONTEXT_SPEC["TECHNICAL"]}
    pkg = C.build_input_package(f, "TECHNICAL", ctx, provenance={"run_id": "r"})
    assert pkg["finding_record_id"] == f["finding_record_id"]
    assert set(pkg["MUST_NOT_CHANGE"]) == set(C.MUST_NOT_CHANGE_FIELDS)
    assert set(pkg["context"]) == set(C.INPUT_CONTEXT_SPEC["TECHNICAL"])
    assert pkg["network"] == "LOCAL_ONLY"
    # no hay claves de documento crudo en la envoltura
    blob = json.dumps(pkg)
    for bad in C.FORBIDDEN_PACKAGE_KEYS:
        assert f'"{bad}"' not in blob


def test_input_package_rejects_missing_context_and_forbidden_keys():
    f = _a_technical_finding()
    import pytest
    with pytest.raises(C.ContractError):
        C.build_input_package(f, "TECHNICAL", {})
    ctx = {k: [] for k in C.INPUT_CONTEXT_SPEC["TECHNICAL"]}
    ctx["pdf_bytes"] = b"x"
    with pytest.raises(C.ContractError):
        C.build_input_package(f, "TECHNICAL", ctx)


# ── validate_output_envelope (estructural) ────────────────────────────

def test_well_formed_envelope_passes():
    f = _a_technical_finding()
    assert C.validate_output_envelope(_well_formed_envelope(f), l2_finding=f) == []


def test_mutated_must_not_change_is_rejected():
    f = _a_technical_finding()
    env = _well_formed_envelope(f)
    env["MUST_NOT_CHANGE"]["risk_band"] = "LOW__tampered"
    viol = C.validate_output_envelope(env, l2_finding=f)
    assert any("MUST_NOT_CHANGE.risk_band" in x for x in viol)


def test_missing_shadow_mark_is_rejected():
    f = _a_technical_finding()
    env = _well_formed_envelope(f)
    env["rationale"] = "sin marca"
    assert any("marca" in x for x in C.validate_output_envelope(env, l2_finding=f))


def test_assessment_out_of_enum_is_rejected():
    f = _a_technical_finding()
    env = _well_formed_envelope(f, assessment="COMPLIANT")
    viol = C.validate_output_envelope(env, l2_finding=f)
    assert any("assessment" in x for x in viol)


def test_external_reference_cannot_be_client_evidence():
    f = _a_technical_finding()
    env = _well_formed_envelope(f)
    env["external_reg_references"] = [{"regulation": "21 CFR 11.10(e)",
                                      "retrieved_at": "t", "source": C.CLIENT_EVIDENCE}]
    assert any("CLIENT_EVIDENCE" in x for x in C.validate_output_envelope(env, l2_finding=f))


def test_non_local_provider_is_rejected():
    f = _a_technical_finding()
    env = _well_formed_envelope(f)
    env["model"]["provider"] = "REMOTE"
    assert any("provider" in x for x in C.validate_output_envelope(env, l2_finding=f))


def test_validator_does_not_mutate_inputs():
    f = _a_technical_finding()
    env = _well_formed_envelope(f)
    before = (json.dumps(f, sort_keys=True), json.dumps(env, sort_keys=True))
    C.validate_output_envelope(env, l2_finding=f)
    assert (json.dumps(f, sort_keys=True), json.dumps(env, sort_keys=True)) == before


# ── evaluación de reutilización ───────────────────────────────────────

def test_reuse_evaluation_well_formed():
    verdicts = {"REUSE", "REUSE_WITH_ADAPTATION", "DISCARD"}
    seen = 0
    for k, v in C.REUSE_EVALUATION.items():
        if v is None:
            continue
        seen += 1
        assert v["verdict"] in verdicts, (k, v)
        assert v["why"].strip()
    assert seen >= 10
    s = C.reuse_summary()
    assert s["REUSE"] >= 3 and s["DISCARD"] >= 3 and s["REUSE_WITH_ADAPTATION"] >= 1
    assert sum(s.values()) == seen


def test_adjudicator_and_evaluate_bundle_are_discarded():
    ev = {k: v for k, v in C.REUSE_EVALUATION.items() if v}
    assert any("adjudicator.adjudicate" in k and v["verdict"] == "DISCARD" for k, v in ev.items())
    assert any("evaluate_bundle" in k and v["verdict"] == "DISCARD" for k, v in ev.items())
    assert any("evidence_verifier" in k and v["verdict"] == "REUSE" for k, v in ev.items())


def test_contract_spec_serialises():
    spec = C.contract_spec()
    json.dumps(spec)  # no raise
    assert spec["experts"] == list(C.EXPERTS)
    assert spec["reuse_summary"] == C.reuse_summary()
