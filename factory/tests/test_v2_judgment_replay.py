"""Tests -- factory/regulatory/v2_judgment/{critic,judgment_v2}.py (V2, B4a).

Replay OFFLINE: el ModelProvider está MOCKEADO -> CERO llamadas reales,
cero gobernanza. Verifica el flujo paso A -> paso B -> verifier -> critic
-> adjudicator y los guardarraíles de docs_plan/PROPUESTA_PROMPTS_JUICIO_V2_B4.md.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.retrieval.evidence_bundle import EvidenceBundle
from factory.regulatory.v2_judgment import adjudicator as adj
from factory.regulatory.v2_judgment import critic as v2critic
from factory.regulatory.v2_judgment import judgment_v2, prompts


# ── Mock provider ────────────────────────────────────────────────────────

class ScriptedProvider:
    """Devuelve respuestas según qué prompt reciba (paso A / paso B /
    critic), sin ninguna llamada real."""
    model_name = "scripted-mock"

    def __init__(self, *, step_a="El sistema registra la acción del operador con fecha y hora.",
                 step_b=None, critic="AGREE"):
        self._a = step_a
        self._b = step_b or {"verdict": "SATISFIES", "rationale": "ok",
                             "evidence_claim_id": None, "evidence_quote": None}
        self._critic = critic
        self.calls = []

    def generate(self, prompt, *, num_predict=None):
        self.calls.append(prompt)
        if "Descripción operativa neutra:" in prompt and "SUB-CRITERIO" not in prompt:
            return {"response": self._a, "done": True}
        if "VEREDICTO PREVIO:" in prompt:
            return {"response": f'{{"assessment": "{self._critic}", "reason": "r"}}', "done": True}
        # paso B
        import json
        return {"response": json.dumps(self._b), "done": True}


CLAIM_TEXT = ("The system shall generate a time-stamped audit trail record for every operator "
              "entry that creates, modifies or deletes an electronic record, preserving the "
              "previous value.")


def _bundle(claim_text=CLAIM_TEXT):
    return EvidenceBundle(
        document_id="RW-0005", requirement_id="21_CFR_11.10(e)",
        subcriterion_id="sc1", subcriterion_ref="21_CFR_11.10(e)::sc1",
        subcriterion_text="existe un audit trail generado automáticamente por el sistema",
        candidate_claims=[{
            "claim_id": "clm-1", "source_text": claim_text,
            "normalized_statement": claim_text, "pagina": 45, "section_id": None,
            "tipo": "control", "bm25_score": 1.0, "rerank_score": 1.0,
            "provenance": {"document_id": "RW-0005", "page": 45},
        }],
    )


# ── Critic ───────────────────────────────────────────────────────────────

def test_critic_parses_valid():
    p = ScriptedProvider(critic="DISAGREE")
    r = v2critic.review("sub", "claim text", "SATISFIES", provider=p)
    assert r.assessment == "DISAGREE"
    assert r.parse_ok


def test_critic_unparseable_falls_to_cannot_confirm():
    class Bad:
        model_name = "bad"
        def generate(self, prompt, *, num_predict=None):
            return {"response": "no json here at all"}
    r = v2critic.review("sub", "claim", "SATISFIES", provider=Bad())
    assert r.assessment == "CANNOT_CONFIRM"
    assert not r.parse_ok


def test_critic_invalid_assessment_falls_to_cannot_confirm():
    class Weird:
        model_name = "w"
        def generate(self, prompt, *, num_predict=None):
            return {"response": '{"assessment": "PROBABLY", "reason": "x"}'}
    r = v2critic.review("sub", "claim", "SATISFIES", provider=Weird())
    assert r.assessment == "CANNOT_CONFIRM"


# ── judgment_v2 end-to-end (mocked) ─────────────────────────────────────

def test_happy_path_confirmed():
    quote = "generate a time-stamped audit trail record for every operator entry"
    p = ScriptedProvider(step_b={"verdict": "SATISFIES", "rationale": "ok",
                                 "evidence_claim_id": "clm-1", "evidence_quote": quote},
                         critic="AGREE")
    v = judgment_v2.evaluate_bundle(_bundle(), provider=p)
    assert v.state == adj.MACHINE_CONFIRMED
    assert v.best_claim_id == "clm-1"
    assert v.best_quote == quote
    assert v.calls_made == 3          # A + B + Critic


def test_fabricated_quote_is_rejected_by_verifier():
    """El paso B devuelve una cita que NO aparece literal en el claim ->
    evidence_verifier la rechaza -> MACHINE_REJECTED. El paso B no puede
    'colar' evidencia."""
    p = ScriptedProvider(step_b={"verdict": "SATISFIES", "rationale": "ok",
                                 "evidence_claim_id": "clm-1",
                                 "evidence_quote": "the system fully complies with 21 CFR Part 11"},
                         critic="AGREE")
    v = judgment_v2.evaluate_bundle(_bundle(), provider=p)
    assert v.state == adj.MACHINE_REJECTED


def test_satisfies_but_critic_disagree_is_inconclusive():
    quote = "generate a time-stamped audit trail record"
    p = ScriptedProvider(step_b={"verdict": "SATISFIES", "rationale": "ok",
                                 "evidence_claim_id": "clm-1", "evidence_quote": quote},
                         critic="DISAGREE")
    v = judgment_v2.evaluate_bundle(_bundle(), provider=p)
    assert v.state == adj.INCONCLUSIVE


def test_hunter_no_is_evidence_not_found_not_gap():
    p = ScriptedProvider(step_b={"verdict": "NO", "rationale": "not present",
                                 "evidence_claim_id": None, "evidence_quote": ""})
    v = judgment_v2.evaluate_bundle(_bundle(), provider=p)
    assert v.state == adj.EVIDENCE_NOT_FOUND
    assert v.calls_made == 2          # A + B, sin Critic (no fue positivo)


def test_positive_without_quote_is_inconclusive():
    p = ScriptedProvider(step_b={"verdict": "SATISFIES", "rationale": "ok",
                                 "evidence_claim_id": "clm-1", "evidence_quote": ""},
                         critic="AGREE")
    v = judgment_v2.evaluate_bundle(_bundle(), provider=p)
    assert v.state == adj.INCONCLUSIVE


def test_step_b_unparseable_is_inconclusive():
    class BadB:
        model_name = "b"
        def generate(self, prompt, *, num_predict=None):
            if "Descripción operativa neutra:" in prompt and "SUB-CRITERIO" not in prompt:
                return {"response": "desc"}
            return {"response": "not json"}
    v = judgment_v2.evaluate_bundle(_bundle(), provider=BadB())
    assert v.state == adj.INCONCLUSIVE


def test_empty_bundle_is_inconclusive():
    b = _bundle()
    b.candidate_claims = []
    v = judgment_v2.evaluate_bundle(b, provider=ScriptedProvider())
    assert v.state == adj.INCONCLUSIVE
    assert v.calls_made == 0


def test_guardrail_step_a_prompt_has_no_norm_vocabulary():
    """El prompt del paso A no debe pedir evaluación de cumplimiento."""
    txt = prompts.render(prompts.STEP_A, claims_source_text="x")
    low = txt.lower()
    assert "no menciones ninguna norma" in low
    assert "no evalúes si algo" in low


def test_prompts_are_draft_unsigned():
    """B4a: los 3 prompts están sin firmar; assert_all_signed() falla."""
    assert not prompts.is_signed(prompts.STEP_A)
    with pytest.raises(prompts.PromptNotSignedError):
        prompts.assert_all_signed()
