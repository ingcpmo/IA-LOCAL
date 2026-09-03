"""Tests — factory/regulatory/shadow/composer_gate.py (SHADOW · CF-6 v1.2, sin LLM).

Cubre:
  - clasificación determinista section_type / regulatory_state de las 66 secciones
  - Q-STATE-1..6 fail-closed (rechaza fabricación de estado / conclusión / CAPA / cita no anclada)
  - render 100% determinista y byte-reproducible (PUNTO DE NO-RETORNO: 0 LLM)
  - blacklist Q1..Q5 sobre el render
  - modo determinista seguro como fallback
  - línea base v1: la narrativa v1 tiene violaciones de estado y hits de blacklist > 0
CERO LLM, CERO red.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import composer as CMP
from factory.regulatory.shadow import composer_gate as CG

_REPO = Path(__file__).parent.parent.parent
_SL = _REPO / "docs_plan" / "shadow_llm"
_BASELINE = _SL / "FINAL_GMP_CORPUS_FINDINGS.json"


def _findings():
    return json.loads(_BASELINE.read_text(encoding="utf-8"))["findings"]


def _skeleton():
    return CMP.build_composer_skeleton(_findings(), source_ref=str(_BASELINE))


def _l2_by_rid():
    return {f["finding_record_id"]: f for f in _findings()}


# ───────────────────────── section_type / regulatory_state ────────────

def test_section_type_counts_are_deterministic_and_total_66():
    sk = _skeleton()
    counts = {}
    for s in sk["sections"]:
        st, has_reg = CG.infer_section_type(s)
        assert st in CG.SECTION_TYPES
        assert isinstance(has_reg, bool)
        counts[st] = counts.get(st, 0) + 1
    assert sum(counts.values()) == 66
    assert counts == {"REGULATORY": 50, "CROSS_DOMAIN": 11,
                      "FUNCTIONAL_TRACEABILITY": 3, "TECHNICAL": 2}


def test_expected_regulatory_state_partition():
    sk = _skeleton()
    counts = {}
    for s in sk["sections"]:
        st = CG.expected_regulatory_state(s)
        assert st in CG.REGULATORY_STATES
        counts[st] = counts.get(st, 0) + 1
    assert counts == {"INCONCLUSIVE": 60, "NOT_APPLICABLE": 5, "NOT_ANALYZABLE": 1}


def test_rw0009_is_not_analyzable():
    sk = _skeleton()
    rw9 = [s for s in sk["sections"] if s["document"] == "RW-0009"]
    assert len(rw9) == 1
    assert CG.expected_regulatory_state(rw9[0]) == "NOT_ANALYZABLE"


def test_functional_and_technical_are_not_applicable():
    sk = _skeleton()
    for s in sk["sections"]:
        st, has_reg = CG.infer_section_type(s)
        if st in ("FUNCTIONAL_TRACEABILITY", "TECHNICAL") and not has_reg:
            assert CG.expected_regulatory_state(s) == "NOT_APPLICABLE"


# ───────────────────────────── Q-STATE ───────────────────────────────

def _good_structured(section, l2_by_rid):
    """Estructura mínima que DEBE pasar Q-STATE para una sección dada."""
    st_type, _ = CG.infer_section_type(section)
    state = CG.expected_regulatory_state(section)
    rid = (section.get("finding_record_ids") or
           [e["finding_record_id"] for e in section["entries"]])[0]
    f = l2_by_rid[rid]
    quote = (f.get("evidence") or {}).get("anchored_quote") or f.get("source_text") or ""
    return {
        "section_type": st_type,
        "regulatory_state": state,
        "evidence_observed": [{"finding_record_id": rid, "quote": quote, "page": f.get("page")}],
        "evidence_limitation": [],
        "technical_findings": [],
        "reviewer_action": "verificar el sub-criterio contra el documento fuente",
        "prohibited_conclusion": "NONE",
    }


def test_qstate_passes_on_wellformed_structure():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"]
              if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    res = CG.verify_qstate(_good_structured(reg, l2), reg, l2)
    assert res.passed, res.violations


def test_qstate1_rejects_compliance_state_on_regulatory_section():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"]
              if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    bad = _good_structured(reg, l2)
    bad["regulatory_state"] = "NOT_APPLICABLE"
    res = CG.verify_qstate(bad, reg, l2)
    assert not res.passed
    assert any("Q-STATE-1" in v for v in res.violations)


def test_qstate2_rejects_inconclusive_on_pure_technical_section():
    sk, l2 = _skeleton(), _l2_by_rid()
    tech = next(s for s in sk["sections"] if CG.infer_section_type(s) == ("TECHNICAL", False))
    bad = _good_structured(tech, l2)
    bad["regulatory_state"] = "INCONCLUSIVE"
    res = CG.verify_qstate(bad, tech, l2)
    assert not res.passed
    assert any("Q-STATE-2" in v for v in res.violations)


def test_qstate3_forces_not_analyzable_on_rw0009():
    sk, l2 = _skeleton(), _l2_by_rid()
    rw9 = next(s for s in sk["sections"] if s["document"] == "RW-0009")
    bad = _good_structured(rw9, l2)
    bad["regulatory_state"] = "INCONCLUSIVE"
    res = CG.verify_qstate(bad, rw9, l2)
    assert not res.passed
    assert any("Q-STATE-3" in v for v in res.violations)


def test_qstate4_rejects_human_conclusion_language():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"] if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    bad = _good_structured(reg, l2)
    bad["evidence_limitation"] = ["el documento no cumple con el requisito de firma"]
    res = CG.verify_qstate(bad, reg, l2)
    assert not res.passed
    assert any("Q-STATE-4" in v for v in res.violations)


def test_qstate5_rejects_capa_in_reviewer_action():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"] if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    bad = _good_structured(reg, l2)
    bad["reviewer_action"] = "abrir una acción correctiva (CAPA) para cerrar el hallazgo"
    res = CG.verify_qstate(bad, reg, l2)
    assert not res.passed
    assert any("Q-STATE-5" in v for v in res.violations)


def test_qstate6_rejects_unanchored_or_foreign_citation():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"] if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    bad = _good_structured(reg, l2)
    bad["evidence_observed"] = [{"finding_record_id": bad["evidence_observed"][0]["finding_record_id"],
                                 "quote": "TEXTO QUE NO EXISTE EN NINGUN FINDING L2 DE ESTA SECCION"}]
    res = CG.verify_qstate(bad, reg, l2)
    assert not res.passed
    assert any("Q-STATE-6" in v for v in res.violations)

    bad2 = _good_structured(reg, l2)
    bad2["evidence_observed"][0]["finding_record_id"] = "rec-000000000000dead"
    res2 = CG.verify_qstate(bad2, reg, l2)
    assert not res2.passed
    assert any("Q-STATE-6" in v for v in res2.violations)


# ───────────────────────────── render ────────────────────────────────

def test_render_is_byte_deterministic_and_llm_free():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"] if CG.infer_section_type(s)[0] == "REGULATORY"
              and CG.expected_regulatory_state(s) == "INCONCLUSIVE")
    st = _good_structured(reg, l2)
    a = CG.render_section(st, reg)
    b = CG.render_section(copy.deepcopy(st), reg)
    assert a == b
    assert "permanece INCONCLUSIVE" in a
    assert "ACCIÓN PARA EL REVISOR:" in a


def test_render_of_every_section_passes_blacklist():
    sk, l2 = _skeleton(), _l2_by_rid()
    for s in sk["sections"]:
        st = _good_structured(s, l2)
        out = CG.compose_section(st, s, l2)
        # una estructura bien formada por sección -> RENDERED y blacklist limpio
        assert out["mode"] == "RENDERED", (s["section_id"], out.get("qstate"))
        assert out["blacklist_hits"] == []
        assert out["post_qstate_llm_calls"] == 0


def test_blacklist_catches_known_v1_tokens():
    txt = ("El documento no cumple con 21 CFR 11.10(g); se recomienda una acción correctiva. "
           "candidate ranking para rec-7d6cb2d2d0fe0d19. MACHINE_INCONCLUSIVE. [[SHADOW / NO GOBERNADO]]")
    rules = {h["rule"] for h in CG.blacklist_scan(txt)}
    assert {"Q1_compliance_conclusion", "Q2_corrective_action", "Q3_internal_vocab",
            "Q4_record_id_leak", "Q5_machine_token_leak"} <= rules


# ───────────────────────── modo seguro / fallback ────────────────────

def test_safe_mode_on_qstate_reject_and_on_none():
    sk, l2 = _skeleton(), _l2_by_rid()
    reg = next(s for s in sk["sections"] if CG.infer_section_type(s)[0] == "REGULATORY")
    out_none = CG.compose_section(None, reg, l2)
    assert out_none["mode"] == "SAFE_MODE"
    assert "[NARRATIVA LLM NO DISPONIBLE" in out_none["text"]
    assert CG.blacklist_scan(out_none["text"]) == []

    bad = _good_structured(reg, l2)
    bad["regulatory_state"] = "NOT_APPLICABLE"  # viola Q-STATE-1
    out_bad = CG.compose_section(bad, reg, l2)
    assert out_bad["mode"] == "SAFE_MODE"
    assert out_bad["reason"] == "qstate_reject"


def test_safe_mode_render_of_every_section_is_blacklist_clean():
    sk, l2 = _skeleton(), _l2_by_rid()
    for s in sk["sections"]:
        assert CG.blacklist_scan(CG.safe_mode_section(s, l2)) == []


# ───────────────────────── G4d normalización ─────────────────────────

def test_normalize_g4d_is_neutral_and_deterministic():
    for a in ("CANDIDATE_RANKING_PROVIDED", "BEHAVIOR_NOT_FOUND_IN_SCOPE", "NO_USEFUL_CANDIDATE"):
        n = CG.normalize_g4d(a)
        assert CG.blacklist_scan(n) == []
        assert n == CG.normalize_g4d(a)
    assert "revisión humana" in CG.normalize_g4d("CANDIDATE_RANKING_PROVIDED")


# ───────────────────────── línea base v1 ────────────────────────────

def test_v1_baseline_reports_state_violations_and_blacklist_hits():
    base = CG.measure_v1_baseline(_SL)
    assert base["v1_sections_total"] == 66
    assert base["SECTION_TYPE_COUNTS"] == {"REGULATORY": 50, "CROSS_DOMAIN": 11,
                                           "FUNCTIONAL_TRACEABILITY": 3, "TECHNICAL": 2}
    # el fallo de v1 debe quedar cuantificado (> 0) — es la razón de existir de CF-6
    assert base["v1_sections_with_state_violation"] > 0
    assert base["v1_blacklist_hits_by_rule"].get("Q1_compliance_conclusion", 0) > 0
    assert base["v1_blacklist_hits_by_rule"].get("Q2_corrective_action", 0) > 0
    assert base["post_qstate_llm_calls"] == 0


def test_measure_v1_baseline_does_not_mutate_inputs():
    before = _BASELINE.read_bytes()
    CG.measure_v1_baseline(_SL)
    assert _BASELINE.read_bytes() == before


def test_contract_spec_declares_no_retorno():
    spec = CG.contract_spec()
    assert spec["post_qstate_llm_calls"] == 0
    assert spec["g4d_reexecuted"] is False
    assert spec["qstate_checks"] == [f"Q-STATE-{i}" for i in range(1, 7)]
