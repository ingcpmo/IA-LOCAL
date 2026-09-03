"""Tests — factory/regulatory/shadow/composer_prompt.py (SHADOW · CF-6 v1.2 · CF6-2, sin LLM).

El nuevo composer_prompt_version emite SOLO estructura JSON. CF6-2 lo entrega
DRAFT_UNSIGNED: la firma de Capa 9 y el tag cf6-G2 son un paso gobernado posterior.
CERO LLM.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import composer_prompt as CP


def test_prompt_is_delivered_unsigned():
    assert CP.load()["status"] == "DRAFT_UNSIGNED"
    assert CP.is_signed() is False
    with pytest.raises(CP.PromptNotSignedError):
        CP.assert_signed()


def test_prompt_metadata_matches_cf6_v12():
    p = CP.load()
    assert p["prompt_version"] == CP.PROMPT_VERSION == "shadow-cf6-composer-struct-v2"
    assert p["schema_version"] == "SHADOW_CF6_COMPOSER_CONTRACT/v1.2"
    assert p["output"] == "json_only"
    assert float(p["temperature"]) == 0.0
    assert "shadow-g4-interp-v1" in p["supersedes"]


def test_render_fills_all_placeholders_and_emits_no_prose_request():
    txt = CP.render(
        document="RW-0006", regulation="21_CFR_11.10(d)",
        section_type="REGULATORY", regulatory_state="INCONCLUSIVE",
        entries="- rec-abc | firma | HIGH | (opinión normalizada)",
        anchored_quotes="rec-abc: \"texto anclado\"",
        normalized_opinions="rec-abc: se recuperaron pasajes que requieren revisión humana",
    )
    assert "{" in txt and "}" in txt          # el ejemplo JSON quedó renderizado
    assert "narrative" not in txt.lower()
    assert "prohibited_conclusion" in txt
    for tok in ("candidate ranking", "acción correctiva", "CAPA "):
        assert tok.lower() not in txt.lower() or "nunca" in txt.lower()


def test_structure_contract_accepts_wellformed_output():
    ok = {
        "section_type": "REGULATORY",
        "regulatory_state": "INCONCLUSIVE",
        "evidence_observed": [{"finding_record_id": "rec-abc", "quote": "texto anclado"}],
        "evidence_limitation": ["no se localizó el registro de revisión en el alcance"],
        "technical_findings": [],
        "reviewer_action": "verificar el sub-criterio contra el documento fuente",
        "prohibited_conclusion": "NONE",
    }
    assert CP.validate_structure_contract(ok) == []


@pytest.mark.parametrize("mut,expect", [
    (lambda o: o.pop("reviewer_action"), "faltan claves"),
    (lambda o: o.update(section_type="COMPLIANT"), "section_type"),
    (lambda o: o.update(regulatory_state="OBSERVED"), "regulatory_state"),
    (lambda o: o.update(prohibited_conclusion="minor deviation"), "prohibited_conclusion"),
    (lambda o: o.update(narrative="prosa libre del modelo"), "prohibidas"),
    (lambda o: o.update(evidence_observed=[{"quote": "x"}]), "finding_record_id"),
    (lambda o: o.update(technical_findings="no-es-lista"), "technical_findings"),
])
def test_structure_contract_rejects_violations(mut, expect):
    o = {
        "section_type": "REGULATORY", "regulatory_state": "INCONCLUSIVE",
        "evidence_observed": [{"finding_record_id": "rec-abc", "quote": "t"}],
        "evidence_limitation": [], "technical_findings": [],
        "reviewer_action": "verificar", "prohibited_conclusion": "NONE",
    }
    mut(o)
    violations = CP.validate_structure_contract(o)
    assert any(expect in v for v in violations), violations


def test_spec_declares_zero_llm_and_unsigned():
    s = CP.spec()
    assert s["llm_calls"] == 0
    assert s["is_signed"] is False
    assert s["status"] == "DRAFT_UNSIGNED"
    assert s["required_keys"] == list(CP._REQUIRED_KEYS)
