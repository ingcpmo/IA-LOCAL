"""Tests — CF-6 v1.2 · CF6-2 (corrección) · shadow-cf6-composer-struct-v3 (SHADOW, sin LLM).

Validación determinista PREVIA a un nuevo CF6-2.5:
  - technical_findings ⊆ allowed_technical_findings ; nunca section_type/regulatory_state/
    REGULATORY_INCONCLUSIVE ; [] cuando no hay subtypes técnicos reales
  - reviewer_action rechaza "cumple" / "cumplimiento"/"incumplimiento" / "acción correctiva"/"CAPA"
    / páginas
  - evidence_observed deduplicado por quote textual
+ regresiones explícitas para las 7 secciones del piloto fallido de CF6-2.5.
CERO LLM. NO toca el prompt v2 firmado, Q-STATE, renderer, G4d, L2.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.shadow import composer as CMP
from factory.regulatory.shadow import composer_gate as CG
from factory.regulatory.shadow import composer_prompt as V2
from factory.regulatory.shadow import composer_prompt_v3 as V3

_REPO = Path(__file__).parent.parent.parent
_SL = _REPO / "docs_plan" / "shadow_llm"
_B = _SL / "CF6" / "CF6_2_5_B_OUTPUTS.jsonl"


def _l2():
    return {f["finding_record_id"]: f
            for f in json.loads((_SL / "FINAL_GMP_CORPUS_FINDINGS.json").read_text(encoding="utf-8"))["findings"]}


def _sections():
    findings = list(_l2().values())
    return {s["section_id"]: s for s in CMP.build_composer_skeleton(findings)["sections"]}


def _v2_outputs():
    return {json.loads(l)["section_id"]: json.loads(l)
            for l in _B.read_text(encoding="utf-8").splitlines() if l.strip()}


def _ok_base(section_type="REGULATORY", regulatory_state="INCONCLUSIVE"):
    return {
        "section_type": section_type,
        "regulatory_state": regulatory_state,
        "evidence_observed": [{"finding_record_id": "rec-a", "quote": "texto uno"},
                              {"finding_record_id": "rec-b", "quote": "texto dos"}],
        "evidence_limitation": ["no se ancló eco léxico en el alcance revisado"],
        "technical_findings": [],
        "reviewer_action": "Verificar en el documento fuente si los pasajes recuperados cubren el sub-criterio",
        "prohibited_conclusion": "NONE",
    }


# ───────────────────── gobernanza / no-solape con v2 ──────────────────

def test_v3_is_draft_unsigned_and_supersedes_v2():
    p = V3.load()
    assert p["status"] == "DRAFT_UNSIGNED"
    assert V3.is_signed() is False
    with pytest.raises(V3.PromptNotSignedError):
        V3.assert_signed()
    assert p["supersedes"] == "shadow-cf6-composer-struct-v2" == V3.SUPERSEDES
    assert V3.PROMPT_VERSION == "shadow-cf6-composer-struct-v3"
    assert len(V3.few_shot()) == 3


def test_v2_signed_prompt_is_untouched():
    assert V2.is_signed() is True
    assert V2.load()["status"] == "SIGNED"
    assert V2.PROMPT_VERSION == "shadow-cf6-composer-struct-v2"


# ───────────────────── allowed_technical_findings determinista ────────

def test_allowed_technical_findings_per_section():
    sk, l2 = _sections(), _l2()
    got = {sid: V3.allowed_technical_findings(sk[sid], l2)
           for sid in ("sec-0004", "sec-0005", "sec-0016", "sec-0018", "sec-0026", "sec-0042", "sec-0062")}
    assert got == {
        "sec-0004": ["ACCESS_CONTROL_GAP", "AUTHORITY_CHECK_GAP"],
        "sec-0005": [],
        "sec-0016": [],
        "sec-0018": ["ACCESS_CONTROL_GAP", "AUTHORITY_CHECK_GAP"],
        "sec-0026": ["BACKUP_RECOVERY_GAP"],
        "sec-0042": ["IMPLEMENTATION_WITHOUT_REQUIREMENT", "ORPHAN_DESIGN_ELEMENT"],
        "sec-0062": [],
    }
    # nunca incluye REGULATORY_INCONCLUSIVE
    for v in got.values():
        assert "REGULATORY_INCONCLUSIVE" not in v


# ───────────────────── las 8 comprobaciones deterministas ────────────

@pytest.mark.parametrize("bad_tf", ["REGULATORY", "CROSS_DOMAIN", "TECHNICAL",
                                    "INCONCLUSIVE", "NOT_APPLICABLE", "REGULATORY_INCONCLUSIVE"])
def test_technical_findings_rejects_section_type_state_and_regulatory_subtype(bad_tf):
    o = _ok_base(); o["technical_findings"] = [bad_tf]
    v = V3.validate_structure_contract(o, allowed_technical_findings=["ACCESS_CONTROL_GAP"])
    assert any("valor prohibido" in x or "∉ allowed" in x for x in v), v


def test_technical_findings_must_be_subset_of_allowed():
    o = _ok_base(); o["technical_findings"] = ["NOT_IN_ALLOWED_GAP"]
    v = V3.validate_structure_contract(o, allowed_technical_findings=["ACCESS_CONTROL_GAP"])
    assert any("∉ allowed_technical_findings" in x for x in v), v
    o["technical_findings"] = ["ACCESS_CONTROL_GAP"]
    assert V3.validate_structure_contract(o, allowed_technical_findings=["ACCESS_CONTROL_GAP"]) == []


def test_technical_findings_must_be_empty_when_no_real_tech_findings():
    o = _ok_base(); o["technical_findings"] = ["ANYTHING"]
    v = V3.validate_structure_contract(o, allowed_technical_findings=[])
    assert any("debe ser [] (allowed_technical_findings vacío)" in x for x in v), v
    o["technical_findings"] = []
    assert V3.validate_structure_contract(o, allowed_technical_findings=[]) == []


@pytest.mark.parametrize("ra", [
    "Revisar si el sistema documentado y cumple con los requisitos",
    "Verificar el cumplimiento del sub-criterio",
    "Confirmar el incumplimiento de la regla",
    "Revisar la no conformidad detectada",
])
def test_reviewer_action_rejects_compliance_language(ra):
    o = _ok_base(); o["reviewer_action"] = ra
    v = V3.validate_structure_contract(o, allowed_technical_findings=[])
    assert any("cumplimiento/conformidad" in x for x in v), (ra, v)


@pytest.mark.parametrize("ra", [
    "Abrir una acción correctiva para cerrar el hallazgo",
    "Evaluar la necesidad de CAPA",
    "Revisar si requieren acciones correctivas",
    "Documentar la desviación y su remediación",
])
def test_reviewer_action_rejects_capa_and_corrective_action(ra):
    o = _ok_base(); o["reviewer_action"] = ra
    v = V3.validate_structure_contract(o, allowed_technical_findings=[])
    assert any("CAPA/acción correctiva/desviación" in x for x in v), (ra, v)


@pytest.mark.parametrize("ra", [
    "Revisar en RW-0005 (pág. 2) si los pasajes cubren el requisito",
    "Verificar en RW-0006 (pág. 1-8) el control de acceso",
    "Revisar la página 4 del documento",
    "Consultar p. 5 para el detalle",
])
def test_reviewer_action_rejects_page_references_not_in_input(ra):
    o = _ok_base(); o["reviewer_action"] = ra
    v = V3.validate_structure_contract(o, allowed_technical_findings=[])
    assert any("página no presente en el input" in x for x in v), (ra, v)


def test_reviewer_action_without_pages_or_compliance_passes():
    o = _ok_base()
    o["reviewer_action"] = ("Revisar en RW-0005 si los pasajes recuperados cubren el sub-criterio "
                            "y contrastarlos con los findings de la sección")
    assert V3.validate_structure_contract(o, allowed_technical_findings=[]) == []


def test_evidence_observed_flags_and_removes_textual_duplicates():
    o = _ok_base()
    o["evidence_observed"] = [
        {"finding_record_id": "rec-a", "quote": "misma cita"},
        {"finding_record_id": "rec-b", "quote": "misma cita"},
        {"finding_record_id": "rec-c", "quote": "misma cita"},
        {"finding_record_id": "rec-d", "quote": "otra"},
    ]
    v = V3.validate_structure_contract(o, allowed_technical_findings=[])
    assert any("citas textualmente duplicadas" in x for x in v), v
    dedup = V3.normalize_evidence_observed(o)
    quotes = [it["quote"] for it in dedup["evidence_observed"]]
    assert quotes == ["misma cita", "otra"]
    assert V3.validate_structure_contract(dedup, allowed_technical_findings=[]) == []


def test_evidence_limitation_rejects_gap_confirmed_and_real_absence_and_compliance():
    for bad in ["se confirma un gap confirmado en la sección",
                "esto constituye una ausencia real del control",
                "el documento no cumple con el requisito"]:
        o = _ok_base(); o["evidence_limitation"] = [bad]
        assert V3.validate_structure_contract(o, allowed_technical_findings=[]), bad
    # negación válida (no debe marcarse)
    o = _ok_base()
    o["evidence_limitation"] = ["el comportamiento no se localizó en el alcance; no implica ausencia real"]
    assert V3.validate_structure_contract(o, allowed_technical_findings=[]) == []


# ───────────────────── regresiones explícitas — 7 secciones ──────────

_EXPECTED_V3_CATCH = {
    "sec-0004": ["valor prohibido", "página no presente"],            # tf=CROSS_DOMAIN + pág. 2
    "sec-0005": ["valor prohibido", "citas textualmente duplicadas"],  # tf=REGULATORY + dup ×3
    "sec-0016": ["valor prohibido", "citas textualmente duplicadas", "página no presente"],  # tf=REG_INCONCLUSIVE + dups + pág 1-8
    "sec-0018": ["valor prohibido"],                                   # tf=CROSS_DOMAIN
    "sec-0026": ["cumplimiento/conformidad"],                          # reviewer_action "cumple"
    "sec-0042": ["CAPA/acción correctiva/desviación"],                 # "acciones correctivas"
    "sec-0062": ["cumplimiento/conformidad"],                          # reviewer_action "cumplen"
}


@pytest.mark.parametrize("sid", ["sec-0004", "sec-0005", "sec-0016", "sec-0018",
                                 "sec-0026", "sec-0042", "sec-0062"])
def test_regression_v2_failed_output_is_now_caught_by_v3(sid):
    sk, l2 = _sections(), _l2()
    raw = _v2_outputs()[sid]["structured_llm"]
    assert raw is not None, f"{sid}: no hay structured_llm en el piloto v2"
    atf = V3.allowed_technical_findings(sk[sid], l2)
    v = V3.validate_structure_contract(raw, allowed_technical_findings=atf)
    assert v, f"{sid}: v3 no detectó ninguna violación en la salida v2"
    for frag in _EXPECTED_V3_CATCH[sid]:
        assert any(frag in x for x in v), f"{sid}: v3 no detectó {frag!r} ; violaciones={v}"


def test_regression_sec0026_technical_findings_was_actually_valid():
    # sec-0026 emitió technical_findings=["BACKUP_RECOVERY_GAP"] que SÍ ∈ allowed;
    # su único defecto real es reviewer_action ("cumple"). v3 no debe inventar
    # una violación de technical_findings donde no la hay.
    sk, l2 = _sections(), _l2()
    raw = _v2_outputs()["sec-0026"]["structured_llm"]
    atf = V3.allowed_technical_findings(sk["sec-0026"], l2)
    v = V3.validate_structure_contract(raw, allowed_technical_findings=atf)
    assert not any("technical_findings" in x for x in v), v


# ───────────────────── few-shots v3 ─────────────────────────────────

def test_v3_few_shots_pass_structure_and_qstate_on_real_sections():
    sk, l2 = _sections(), _l2()
    real = {
        "21_CFR_11.10(e) — sección real sec-0031 (RW-0011)": "sec-0031",
        "ANNEX11_7 — sección real sec-0012 (RW-0005), TECHNICAL": "sec-0012",
        "trazabilidad sin regulación directa — sección real sec-0001 (RW-0005), FUNCTIONAL_TRACEABILITY": "sec-0001",
    }
    for fs in V3.few_shot():
        eo = fs["expected_output"]
        atf = fs["input_context"]["allowed_technical_findings"]
        assert V3.validate_structure_contract(eo, allowed_technical_findings=atf) == [], fs["based_on"]
        q = CG.verify_qstate(eo, sk[real[fs["based_on"]]], l2)
        assert q.passed, (fs["based_on"], q.violations)


def test_v3_technical_and_functional_few_shots_have_real_nonempty_technical_findings():
    fs = {x["based_on"].split(" —")[0]: x for x in V3.few_shot()}
    tech = fs["ANNEX11_7"]["expected_output"]["technical_findings"]
    trace = fs["trazabilidad sin regulación directa"]["expected_output"]["technical_findings"]
    assert tech == ["BACKUP_RECOVERY_GAP"]
    assert trace == ["IMPLEMENTATION_WITHOUT_REQUIREMENT", "ORPHAN_DESIGN_ELEMENT"]
    # el few-shot regulatorio conserva technical_findings = []
    reg = [x for x in V3.few_shot() if x["based_on"].startswith("21_CFR")][0]
    assert reg["expected_output"]["technical_findings"] == []


def test_propose_record_shape():
    r = V3.propose_record()
    assert r["NEW_PROMPT_VERSION"] == "shadow-cf6-composer-struct-v3"
    assert r["OLD_PROMPT_VERSION"] == "shadow-cf6-composer-struct-v2"
    assert r["status_at_propose"] == "DRAFT_UNSIGNED"
    assert r["written_to_ledger"] is False
    assert r["awaiting"]["action"] == "human_confirmed"
    assert "composer_structured_v2.yaml (firmado)" in r["does_not_touch"]
    assert r["invariants"]["FINDINGS_FINGERPRINT"].startswith("235f724a738ce783")
