"""Tests -- factory/regulatory/v2_judgment/adjudicator.py (V2, B4a).

docs_plan/PROPUESTA_PROMPTS_JUICIO_V2_B4.md §4. Determinista, sin LLM.
Tabla de verdad Hunter x Critic x Verifier. Regla dura: EVIDENCE_NOT_FOUND
nunca => gap por sí solo (eso es B5).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.v2_judgment import adjudicator as adj


def A(**kw):
    base = dict(hunter_verdict="SATISFIES", critic_assessment="AGREE",
                verifier_status="verified", evidence_quote_present=True)
    base.update(kw)
    return adj.adjudicate(**base).state


def test_confirmed_path():
    assert A() == adj.MACHINE_CONFIRMED


def test_partial_path():
    assert A(hunter_verdict="PARTIAL") == adj.MACHINE_PARTIAL
    assert A(hunter_verdict="PARTIAL", critic_assessment="CANNOT_CONFIRM") == adj.INCONCLUSIVE


def test_verifier_rejected_beats_everything():
    assert A(verifier_status="rejected_by_verifier") == adj.MACHINE_REJECTED
    assert A(hunter_verdict="PARTIAL", verifier_status="rejected_by_verifier") == adj.MACHINE_REJECTED


def test_positive_without_quote_is_inconclusive():
    assert A(evidence_quote_present=False) == adj.INCONCLUSIVE


def test_verifier_review_required_is_inconclusive():
    assert A(verifier_status="review_required") == adj.INCONCLUSIVE


def test_critic_disagree_downgrades_confirmed():
    assert A(critic_assessment="DISAGREE") == adj.INCONCLUSIVE


def test_critic_cannot_confirm_downgrades():
    assert A(critic_assessment="CANNOT_CONFIRM") == adj.INCONCLUSIVE


def test_hunter_no_agree_is_evidence_not_found():
    assert A(hunter_verdict="NO", critic_assessment="AGREE",
             evidence_quote_present=False) == adj.EVIDENCE_NOT_FOUND


def test_hunter_no_but_critic_disagree_is_inconclusive():
    assert A(hunter_verdict="NO", critic_assessment="DISAGREE",
             evidence_quote_present=False) == adj.INCONCLUSIVE


def test_hunter_unclear_is_inconclusive():
    assert A(hunter_verdict="UNCLEAR", evidence_quote_present=False) == adj.INCONCLUSIVE


def test_open_contradiction_short_circuits():
    assert A(has_open_contradiction=True) == adj.CONTRADICTORY_EVIDENCE


def test_evidence_not_found_never_becomes_gap():
    """El adjudicator emite EVIDENCE_NOT_FOUND, jamás DOCUMENTATION_GAP:
    ese estado no existe en esta capa (es consolidación de requisito, B5)."""
    out = adj.adjudicate(hunter_verdict="NO", critic_assessment="AGREE",
                         verifier_status=None, evidence_quote_present=False)
    assert out.state == adj.EVIDENCE_NOT_FOUND
    assert "GAP" not in out.state


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        adj.adjudicate(hunter_verdict="MAYBE", critic_assessment="AGREE",
                       verifier_status="verified", evidence_quote_present=True)
    with pytest.raises(ValueError):
        adj.adjudicate(hunter_verdict="NO", critic_assessment="SURE",
                       verifier_status=None, evidence_quote_present=False)
