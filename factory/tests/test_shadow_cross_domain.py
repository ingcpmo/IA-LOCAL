"""Tests -- factory/regulatory/shadow/cross_domain.py (SHADOW · G3).

Post-pass determinista de relaciones cross-domain -> shadow/cross_domain_links.json.
Corr. 2: NUNCA se escribe en Finding.related_finding_ids (L2). Solo lectura de L2.
CERO LLM, CERO red.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import cross_domain as X

_REPO = Path(__file__).parent.parent.parent
_BASELINE = _REPO / "docs_plan" / "shadow_llm" / "FINAL_GMP_CORPUS_FINDINGS.json"
_DIAG = _REPO / "docs_plan" / "shadow_llm" / "G0_inputs" / "CURRENT_FINDING_AGENT_ROUTING.json"


def _findings():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]


def _art():
    return X.build_cross_domain_links(_findings(), source_ref=str(_BASELINE))


# ── detección de las 15 relaciones ────────────────────────────────────

def test_exactly_15_links_and_acceptance_pass():
    a = _art()
    assert a["summary"]["total_links"] == 15
    assert len(a["links"]) == 15
    assert a["acceptance"]["PASS"] is True
    for k, v in a["acceptance"].items():
        assert v is True, k


def test_link_ids_stable_and_unique():
    a = _art()
    ids = [lk["link_id"] for lk in a["links"]]
    assert ids == [f"cdl-{i:04d}" for i in range(1, 16)]
    # determinismo: segunda construcción idéntica
    assert json.dumps(a, sort_keys=True) == json.dumps(_art(), sort_keys=True)


def test_every_link_is_technical_with_regulatory_counterpart_same_doc():
    findings = _findings()
    by_rid = {f["finding_record_id"]: f for f in findings}
    for lk in X.build_cross_domain_links(findings)["links"]:
        assert lk["technical"]["primary_bucket"] == "TECHNICAL"
        assert lk["relation"] == X.RELATION
        assert lk["shared_regulations"]
        assert lk["regulatory_counterparts"]
        for cp in lk["regulatory_counterparts"]:
            rf = by_rid[cp["finding_record_id"]]
            assert (rf.get("provenance") or {}).get("agent_id") == "regulatory_tier1"
            assert rf["subtype"] == "REGULATORY_INCONCLUSIVE"
            assert rf["document"] == lk["document"]


def test_link_technical_ids_match_g0_diagnostic():
    art_ids = {lk["technical"]["finding_record_id"] for lk in _art()["links"]}
    diag = json.loads(_DIAG.read_text(encoding="utf-8"))
    diag_ids = {x["finding_record_id"]
                for x in diag["summary"]["cross_domain_same_requirement_family_detail"]}
    assert art_ids == diag_ids


# ── corr. 2: nada se escribe en L2 ───────────────────────────────────

def test_post_pass_does_not_mutate_l2_findings():
    findings = _findings()
    before = json.dumps(findings, sort_keys=True)
    X.build_cross_domain_links(findings)
    after = json.dumps(findings, sort_keys=True)
    assert before == after
    X.assert_no_l2_mutation(json.loads(before), json.loads(after))  # no raise


def test_relation_not_present_in_any_related_finding_ids():
    findings = _findings()
    by_rid = {f["finding_record_id"]: f for f in findings}
    for lk in X.build_cross_domain_links(findings)["links"]:
        tech = by_rid[lk["technical"]["finding_record_id"]]
        rel = set(tech.get("related_finding_ids") or [])
        for cp in lk["regulatory_counterparts"]:
            rf = by_rid[cp["finding_record_id"]]
            assert cp["finding_record_id"] not in rel
            assert rf.get("finding_id") not in rel


def test_assert_no_l2_mutation_raises_on_change():
    a = _findings()
    b = copy.deepcopy(a)
    b[0]["related_finding_ids"] = ["injected"]
    with pytest.raises(X.L2MutationError):
        X.assert_no_l2_mutation(a, b)


# ── hook G4b: DISAGREEMENT_PERSISTS -> HUMAN_REVIEW_REQUIRED ──────────

def test_apply_review_outcome_flags_human_review_on_disagreement():
    art = _art()
    first = art["links"][0]["link_id"]
    out = X.apply_review_outcome(art, {first: "DISAGREEMENT_PERSISTS",
                                       art["links"][1]["link_id"]: "RECONCILED_CONSISTENT"})
    lk0 = next(l for l in out["links"] if l["link_id"] == first)
    lk1 = out["links"][1]
    assert lk0["status"] == X.STATUS_HUMAN_REVIEW and lk0["human_review_required"] is True
    assert lk1["status"] == X.STATUS_PENDING and lk1["human_review_required"] is False
    assert out["summary"]["human_review_required_count"] == 1
    # no muta el artefacto de entrada
    assert art["links"][0]["status"] == X.STATUS_PENDING


def test_apply_review_outcome_rejects_invalid_assessment():
    art = _art()
    with pytest.raises(ValueError):
        X.apply_review_outcome(art, {art["links"][0]["link_id"]: "COMPLIANT"})


def test_missing_link_id_in_outcomes_keeps_pending():
    art = _art()
    out = X.apply_review_outcome(art, {})
    assert all(lk["status"] == X.STATUS_PENDING for lk in out["links"])
