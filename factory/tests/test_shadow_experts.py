"""Tests -- factory/regulatory/shadow/experts.py (SHADOW · G4).

Con un ModelProvider MOCKEADO: CERO llamadas reales a Ollama. Verifican que
cada sub-agente construye una envoltura de OPINIÓN conforme al contrato G2,
la pasa por el verificador fail-closed, no muta L2 y no emite tokens de
cumplimiento. La corrida real (LLM_CALLS>0) está atestada en
docs_plan/shadow_llm/G4/G4_SUMMARY.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import contracts as C
from factory.regulatory.shadow import experts as X
from factory.regulatory.shadow import verifier as V

_REPO = Path(__file__).parent.parent.parent
_BASE = json.loads((_REPO / "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json").read_text())["findings"]
_BY = {f["finding_record_id"]: f for f in _BASE}
_ROUTING = {r["finding_record_id"]: r["primary_bucket"]
            for r in json.loads((_REPO / "docs_plan/shadow_llm/G1_routing.json").read_text())["routing"]}


class MockProvider:
    """ModelProvider mock -- devuelve un JSON fijo, 0 red."""
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    @property
    def model_name(self):
        return "mock-model"

    def generate(self, prompt, *, num_predict=None):
        self.calls += 1
        return {"response": json.dumps(self._payload)}

    def show_digest(self):
        return "mock-digest"

    def runtime_version(self):
        return "mock"


def _tech():
    return next(f for f in _BASE if _ROUTING.get(f["finding_record_id"]) == "TECHNICAL")


def _func():
    return next(f for f in _BASE if _ROUTING.get(f["finding_record_id"]) == "FUNCTIONAL_TRACEABILITY")


def _reg():
    return next(f for f in _BASE if _ROUTING.get(f["finding_record_id"]) == "REGULATORY")


def test_technical_envelope_valid_and_accepted():
    f = _tech()
    q = (f.get("evidence") or {}).get("anchored_quote") or f["source_text"]
    prov = MockProvider({"assessment": "BEHAVIOR_NOT_FOUND_IN_SCOPE",
                         "rationale": "no aparece el comportamiento requerido",
                         "cited_quote": q[:50], "confidence": "MEDIUM"})
    clog = X.CallLog()
    res = X.run_technical(f, prov, clog)
    env = res["envelope"]
    assert prov.calls == 1 and clog.n == 1
    assert env["expert"] == "TECHNICAL"
    assert env["assessment"] in C.ASSESSMENT_VALUES["TECHNICAL"]
    assert C.SHADOW_MARK in env["rationale"]
    assert env["model"]["provider"] == "LOCAL" or env["model"]["provider"] == "LOCAL"
    assert res["verifier"]["status"] == V.SHADOW_ACCEPTED, res["verifier"]


def test_functional_envelope_valid():
    f = _func()
    q = (f.get("evidence") or {}).get("anchored_quote") or f["source_text"]
    prov = MockProvider({"assessment": "LIKELY_EXTRACTION_LIMIT", "rationale": "el id existe aguas abajo",
                         "cited_quote": q[:40], "confidence": "LOW"})
    res = X.run_functional(f, prov, X.CallLog())
    assert res["envelope"]["assessment"] == "LIKELY_EXTRACTION_LIMIT"
    assert res["verifier"]["status"] == V.SHADOW_ACCEPTED


def test_regulatory_triage_never_observed_and_le5():
    f = _reg()
    cands = [{"claim_id": f"clm-{i}", "source_text": f"texto candidato {i} sobre el sub-criterio"}
             for i in range(5)]
    prov = MockProvider({"assessment": "CANDIDATE_RANKING_PROVIDED",
                         "ranked_candidate_claim_ids": ["clm-2", "clm-0", "clm-4"],
                         "rationale": "orden por pertinencia para el revisor",
                         "cited_quote": "texto candidato 2 sobre el sub-criterio", "confidence": "LOW"})
    res = X.run_regulatory_triage(f, cands, prov, X.CallLog())
    env = res["envelope"]
    assert env["assessment"] in C.ASSESSMENT_VALUES["REGULATORY"]
    assert "OBSERVED" not in env["assessment"].upper() and "COMPLIANT" not in env["assessment"].upper()
    assert len(env["ranked_candidate_claim_ids"]) <= 5
    assert set(env["ranked_candidate_claim_ids"]) <= {c["claim_id"] for c in cands}
    # el finding L2 no cambia
    assert env["MUST_NOT_CHANGE"]["subtype"] == f["subtype"] == "REGULATORY_INCONCLUSIVE"
    assert env["MUST_NOT_CHANGE"]["human_state"] == "UNREVIEWED"


def test_regulatory_forbidden_assessment_is_downgraded_not_emitted():
    f = _reg()
    prov = MockProvider({"assessment": "OBSERVED", "rationale": "x", "cited_quote": "", "confidence": "LOW"})
    res = X.run_regulatory_triage(f, [], prov, X.CallLog())
    assert res["envelope"]["assessment"] in C.ASSESSMENT_VALUES["REGULATORY"]
    assert res["envelope"]["assessment"] == "NEEDS_HUMAN_SEARCH"  # fallback


def test_bad_citation_is_rejected_by_verifier():
    f = _tech()
    prov = MockProvider({"assessment": "INDETERMINATE", "rationale": "x",
                         "cited_quote": "CITA QUE NO EXISTE EN NINGUN PASAJE ZZZ", "confidence": "LOW"})
    res = X.run_technical(f, prov, X.CallLog())
    assert res["verifier"]["status"] == V.SHADOW_REJECTED
    assert res["verifier"]["anchoring_violations"]


def test_run_does_not_mutate_l2_finding():
    f = _tech()
    before = json.dumps(f, sort_keys=True)
    X.run_technical(f, MockProvider({"assessment": "INDETERMINATE", "rationale": "x",
                                     "cited_quote": "", "confidence": "LOW"}), X.CallLog())
    assert json.dumps(f, sort_keys=True) == before


def test_composer_marks_shadow_and_only_cites_section_rids():
    f = _tech()
    section = {"section_id": "sec-0001", "document": f["document"], "regulation": "21_CFR_11.10(e)",
               "entries": [{"finding_record_id": f["finding_record_id"], "subtype": f["subtype"],
                            "risk_band": (f.get("risk") or {}).get("band")}]}
    prov = MockProvider({"narrative": f"El hallazgo {f['finding_record_id']} indica un gap.",
                         "assessment": "NARRATIVE_DRAFTED",
                         "cited_finding_record_ids": [f["finding_record_id"], "rec-inventado"],
                         "confidence": "LOW"})
    out = X.run_composer(section, {}, prov, X.CallLog())
    assert C.SHADOW_MARK in out["narrative"]
    assert out["cited_finding_record_ids"] == [f["finding_record_id"]]  # 'rec-inventado' filtrado
    assert out["assessment"] in C.ASSESSMENT_VALUES["COMPOSER"]


def test_make_provider_only_local():
    import pytest
    with pytest.raises(ValueError):
        X.make_provider("REMOTE")
