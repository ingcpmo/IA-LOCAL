"""
W7.1 — Flag determinista guidance_unapplied (verificador v2.2).

Criterios A1–A5 y A7 del contrato docs/W7_1_FLAG_GUIDANCE_UNAPPLIED.md a
nivel de función pura, con los fixtures REALES de W7 Fase D: v01–v03 del
análisis del caso openfda_enforcement:D-0554-2026 (misión
oos_hplc_investigator), archivados en tests/fixtures/case_analyses/ porque
factory/regulatory/case_analyses/ no está bajo git y lo escribe el
contenedor. v02 reprodujo v01 byte a byte ignorando la guidance de borrado
y pasó v2.1 sin señal alguna (el fallo vivo que motiva W7.1); v03 aplicó el
reemplazo exacto (1 viñeta eliminada, resto intacto).

A6 (paridad de pipelines) vive en test_dossier_agent_review.py y
test_case_analysis.py — usa sus fixtures de entorno. A8 (pureza del módulo)
lo cubre test_verifier_module_is_pure de test_claim_verifier_v2.py: el
código nuevo vive en el mismo módulo.

Las grants se derivan de las declaraciones REALES vigentes
(factory/profiles/qa_profiles.yaml + regulatory_scope de la misión): si una
fase futura de corpus las cambia, estos tests lo hacen visible.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import claim_verifier as cv
from factory.services import dossier_agent_review_service as review
from factory.services import paths

FIXTURES = Path(__file__).parent / "fixtures" / "case_analyses" / "openfda_enforcement__D-0554-2026"


def _record(v: int) -> dict:
    return json.loads((FIXTURES / f"v{v:02d}.json").read_text(encoding="utf-8"))


def _grants_qa_oos() -> dict:
    corpus = review.corpus_sufficiency("oos_hplc_investigator", "qa_oos_profile")
    mission = yaml.safe_load(
        (paths.MISSIONS_DIR / "oos_hplc_investigator.yaml").read_text(encoding="utf-8"))
    return cv.parse_reference_grants(
        list(corpus["available"]) + list(corpus["pending"])
        + list(mission.get("regulatory_scope") or []))


def _verify(v: int, prev_v: int | None = None) -> dict:
    rec = _record(v)
    items = cv.items_from_prompt(rec["governance"]["prompt_full"])
    prev = _record(prev_v)["response"] if prev_v else None
    return cv.verify_v2(rec["response"], rec["claims"]["detail"], items,
                        _grants_qa_oos(), prev_response=prev)


# ── [A1] el fallo vivo de Fase D queda fijado como regresión ──────────────────

def test_a1_real_v2_identical_to_v1_flags_guidance_unapplied():
    """[A1] v2 real ≡ v1 real → flag; y en NADA más (precisión: v02 pasó
    limpio el resto de reglas en vivo — eso no debe cambiar)."""
    out = _verify(2, prev_v=1)
    assert out["flags"] == ["guidance_unapplied"]
    finding = [f for f in out["findings"] if f["type"] == "guidance_unapplied"]
    assert len(finding) == 1 and "idéntica" in finding[0]["detail"]


def test_a1_confidence_penalized_to_baja():
    """[A1] con el flag, la confianza computada cae a baja (anti-optimismo).
    En vivo, v2 quedó 'media' — con v2.2 habría quedado 'baja'."""
    rec = _record(2)
    counts = {k: rec["claims"][k] for k in
              ("supported", "partially_supported", "unsupported", "unverifiable")}
    assert review._confidence("partial", counts, ["guidance_unapplied"]) == "baja"
    # sin el flag, el mismo registro computa media (control del delta)
    assert review._confidence("partial", counts, []) == "media"


def test_a1_no_retroactive_flag_without_prev_response():
    """[§3.5] re-verificación de archivados (sin prev_response) jamás
    flaggea retroactivamente: v02 re-verificado queda limpio, como en vivo."""
    assert _verify(2)["flags"] == []


# ── [A2] el éxito de Fase D no flaggea ────────────────────────────────────────

def test_a2_real_v3_replacement_does_not_flag():
    """[A2] v3 real (1 viñeta eliminada, resto verbatim) vs v2 → sin flag."""
    assert "guidance_unapplied" not in _verify(3, prev_v=2)["flags"]


# ── [A3] draft nunca flaggea ──────────────────────────────────────────────────

def test_a3_draft_prev_none_never_flags():
    assert cv.check_guidance_unapplied("cualquier texto", None) == []
    assert cv.check_guidance_unapplied("", None) == []


# ── [A4] normalización absorbe whitespace ─────────────────────────────────────

def test_a4_whitespace_only_difference_still_flags():
    prev = _record(1)["response"]
    noisy = "\n\n" + "\n\n".join("  " + l + "  " for l in prev.splitlines()) + "\n\n"
    out = cv.check_guidance_unapplied(noisy, prev)
    assert out and out[0]["type"] == "guidance_unapplied"


# ── [A5] conservador: cualquier cambio real de contenido → sin flag ───────────

def test_a5_single_char_change_does_not_flag():
    prev = _record(1)["response"]
    assert cv.check_guidance_unapplied(prev + " x", prev) == []
    assert cv.check_guidance_unapplied(prev.replace("Class II", "Class I", 1),
                                       prev) == []


# ── [A7] retrocompatibilidad de la firma ──────────────────────────────────────

def test_a7_legacy_call_without_prev_response_unchanged():
    """verify_v2 sin el parámetro nuevo se comporta como antes (default None):
    mismos findings que la llamada explícita con prev_response=None."""
    rec = _record(2)
    items = cv.items_from_prompt(rec["governance"]["prompt_full"])
    grants = _grants_qa_oos()
    legacy = cv.verify_v2(rec["response"], rec["claims"]["detail"], items, grants)
    explicit = cv.verify_v2(rec["response"], rec["claims"]["detail"], items,
                            grants, prev_response=None)
    assert legacy == explicit
    assert "guidance_unapplied" not in legacy["flags"]


def test_verifier_version_bumped_to_2_2():
    # pin consciente: v2.2 = W7.1 añadió guidance_unapplied
    assert cv.VERIFIER_VERSION == "2.2"
    assert _verify(1)["version"] == "2.2"
