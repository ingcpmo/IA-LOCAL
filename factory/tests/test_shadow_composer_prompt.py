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


def test_prompt_is_signed_by_layer9():
    p = CP.load()
    assert p["status"] == "SIGNED"
    assert CP.is_signed() is True
    CP.assert_signed()  # no raise
    sig = CP.signature()
    assert sig["signed_by"] == "Capa 9 (Cesar)"
    assert sig["signed_at"] == "2026-09-03"
    assert "sesión" in sig["signed_on"]


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


def test_spec_declares_zero_llm_and_signed():
    s = CP.spec()
    assert s["llm_calls"] == 0
    assert s["is_signed"] is True
    assert s["status"] == "SIGNED"
    assert s["required_keys"] == list(CP._REQUIRED_KEYS)
    assert s["has_few_shot"] is True


# ───────────────────────── CF6-2 · few-shot 21 CFR 11.10(e) ─────────

def test_few_shot_present_and_based_on_11_10_e():
    assert CP.has_few_shot() is True
    fs = CP.few_shot()
    assert "11.10(e)" in fs["based_on"]
    assert fs["input_context"]["regulation"] == "21_CFR_11.10(e)"
    assert fs["input_context"]["section_type"] == "REGULATORY"
    assert fs["input_context"]["regulatory_state"] == "INCONCLUSIVE"


def test_few_shot_block_is_rendered_into_the_prompt():
    txt = CP.render(
        document="RW-0011", regulation="21_CFR_11.10(e)",
        section_type="REGULATORY", regulatory_state="INCONCLUSIVE",
        entries="- rec-x | REGULATORY_INCONCLUSIVE | HIGH | ...",
        anchored_quotes='rec-x: "q"', normalized_opinions="rec-x: pasajes recuperados",
    )
    assert "EJEMPLO DE REFERENCIA" in txt
    assert "setpoint, and any time-delay associated with the alarm." in txt


def test_few_shot_expected_output_passes_structure_contract():
    eo = CP.few_shot()["expected_output"]
    assert CP.validate_structure_contract(eo) == []


def test_few_shot_expected_output_passes_qstate_on_real_section():
    """El ejemplo del few-shot debe pasar Q-STATE-1..6 contra la sección REAL
    sec-0031 (RW-0011, 21_CFR_11.10(e)) — no eleva INCONCLUSIVE, cita anclada."""
    import json
    from factory.regulatory.shadow import composer as CMP
    from factory.regulatory.shadow import composer_gate as CG

    findings = json.loads(
        (Path(__file__).parent.parent.parent / "docs_plan" / "shadow_llm"
         / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]
    sec = next(s for s in CMP.build_composer_skeleton(findings)["sections"]
               if s["section_id"] == "sec-0031")
    l2 = {f["finding_record_id"]: f for f in findings}
    res = CG.verify_qstate(CP.few_shot()["expected_output"], sec, l2)
    assert res.passed, res.violations


# ───────────────────────── CF6-2 · evidencia propose → human_confirmed ──

_CF6 = Path(__file__).parent.parent.parent / "docs_plan" / "shadow_llm" / "CF6"


def test_frozen_propose_record_is_wellformed_and_unsigned():
    import json
    rec = json.loads((_CF6 / "CF6_2_PROPOSE_shadow-cf6-composer-struct-v2.json")
                     .read_text(encoding="utf-8"))
    assert rec["action"] == "propose"
    assert rec["prompt_version"] == "shadow-cf6-composer-struct-v2"
    assert rec["status_at_propose"] == "DRAFT_UNSIGNED"   # el propose se hizo sobre el prompt sin firmar
    assert rec["few_shot_present"] is True
    assert rec["prompt_sha256"] == "694000793697ecf87a33ac6c00a33b17e735aeda82332392eaaa317b4ccf6c79"
    assert rec["awaiting"]["action"] == "human_confirmed"


def test_human_confirmed_record_requires_signed_prompt_and_references_propose():
    rec = CP.human_confirmed_record()
    assert rec["action"] == "human_confirmed"
    assert rec["signed_by"] == "Capa 9 (Cesar)"
    assert rec["signed_at"] == "2026-09-03"
    assert rec["frozen_in_tag"] == "cf6-G2"
    assert rec["confirms_propose"]["proposed_prompt_sha256"] == (
        "694000793697ecf87a33ac6c00a33b17e735aeda82332392eaaa317b4ccf6c79")
    assert rec["signed_prompt_sha256"] != rec["confirms_propose"]["proposed_prompt_sha256"]
    assert rec["invariants"]["FINDINGS_FINGERPRINT"].startswith("235f724a738ce783")


def test_governed_evidence_bundle_is_consistent():
    ev = CP.governed_evidence()
    assert ev["propose_to_human_confirmed_consistent"] is True
    assert ev["propose"]["action"] == "propose"
    assert ev["human_confirmed"]["action"] == "human_confirmed"
    assert ev["signature"]["status"] == "SIGNED"
    assert ev["tag"] == "cf6-G2"
    assert ev["prior_tag_kept_intact"] == "cf6-G2-draft"


def test_frozen_governed_evidence_file_matches_builder():
    import json
    on_disk = json.loads((_CF6 / "CF6_2_GOVERNED_EVIDENCE_shadow-cf6-composer-struct-v2.json")
                         .read_text(encoding="utf-8"))
    assert on_disk["propose_to_human_confirmed_consistent"] is True
    assert on_disk["human_confirmed"]["signed_prompt_sha256"] == CP.prompt_sha256()


def test_prompt_sha256_is_deterministic():
    assert CP.prompt_sha256() == CP.prompt_sha256()
