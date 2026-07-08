"""
W6.5.1 (Pieza B) — Verificador v2: criterios de aceptación del gate.

Los fixtures v01–v06 son las propuestas REALES del experimento de Fase D
(data_integrity_assessment de oos_hplc_investigator, mistral v1–v3 y qwen
v4–v6), archivadas en tests/fixtures/ porque factory/validation/ no está bajo
git y lo escribe el contenedor. Cada criterio marcado [GATE] es un checkbox
literal de factory/docs/W6_5_1_GATE_REVISION_DIRIGIDA.md.

Las grants de citas se derivan de las declaraciones REALES vigentes
(factory/profiles/integrity_profiles.yaml + regulatory_scope de la misión
oos_hplc_investigator): si una futura fase de corpus cambia esas
declaraciones, estos tests lo hacen visible para revisión consciente.
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import claim_verifier as cv
from factory.services import dossier_agent_review_service as svc
from factory.services import paths

FIXTURES = Path(__file__).parent / "fixtures" / "agent_proposals" / "data_integrity_assessment"


def _record(v: int) -> dict:
    return json.loads((FIXTURES / f"v{v:02d}.json").read_text(encoding="utf-8"))


def _grants_integrity() -> dict:
    corpus = svc.corpus_sufficiency("oos_hplc_investigator", "integrity_lims_profile")
    mission = yaml.safe_load(
        (paths.MISSIONS_DIR / "oos_hplc_investigator.yaml").read_text(encoding="utf-8"))
    return cv.parse_reference_grants(
        list(corpus["available"]) + list(corpus["pending"])
        + list(mission.get("regulatory_scope") or []))


def _verify(v: int) -> dict:
    rec = _record(v)
    items = cv.items_from_prompt(rec["governance"]["prompt_full"])
    return cv.verify_v2(rec["response"], rec["claims"]["detail"], items,
                        _grants_integrity())


# ── [GATE] criterios de aceptación con fixtures reales ────────────────────────

def test_gate_v05_flags_unverified_references():
    """[GATE] v5 → unverified_reference en §11.30(a)/(c) y en 'FDA Data
    Integrity Guidance 2018, §3.4' — y en NADA más (precisión)."""
    out = _verify(5)
    assert "unverified_reference" in out["flags"]
    refs = [f["reference"] for f in out["findings"]
            if f["type"] == "unverified_reference"]
    assert any("11.30(c)" in r for r in refs)
    assert any("11.30(a)" in r for r in refs)
    assert any("§3.4" in r for r in refs)
    assert len(refs) == 3


def test_gate_v06_flags_negation_contradicted():
    """[GATE] v6 → negation_contradicted en el [SE] 'no hay evidencia de
    aprobaciones humanas' (la auditoría contiene validation_doc_approved).
    Las demás negaciones de v6 (SOP de revisión periódica, firmas
    electrónicas) NO se señalan: los registros operacionales no las
    contradicen — que la misión PIDA firmas no es evidencia de firmas."""
    out = _verify(6)
    negs = [f for f in out["findings"] if f["type"] == "negation_contradicted"]
    assert len(negs) == 1
    assert "aprobaciones humanas" in negs[0]["claim"]
    assert negs[0]["matched_tokens"] == {"aprobaciones": "approv"}
    assert "audit" in negs[0]["evidence_ids"]


def test_gate_v06_no_false_positives_on_correct_references():
    """[GATE] v6 → SIN flag en §11.10(e), Subparte C y guía 2018 sin numeral."""
    out = _verify(6)
    assert [f for f in out["findings"] if f["type"] == "unverified_reference"] == []


def test_gate_v04_flags_multi_claim_line():
    """[GATE] v4 → multi_claim_line: agrupó ~8 claims en 3 viñetas y el parser
    solo contaba la primera de cada línea."""
    out = _verify(4)
    multi = [f for f in out["findings"] if f["type"] == "multi_claim_line"]
    assert "multi_claim_line" in out["flags"]
    assert len(multi) == 3
    assert all(len(f["tags"]) >= 2 for f in multi)


def test_gate_confidence_penalized_by_v2_flags():
    """[GATE] confianza computada penalizada por los flags nuevos, misma
    filosofía anti-optimismo: texto potencialmente falso → baja; verificación
    incompleta → nunca alta."""
    clean = {"supported": 3, "partially_supported": 0,
             "unsupported": 0, "unverifiable": 0}
    assert svc._confidence("sufficient", clean) == "alta"
    assert svc._confidence("sufficient", clean, ["negation_contradicted"]) == "baja"
    assert svc._confidence("sufficient", clean, ["unverified_reference"]) == "baja"
    assert svc._confidence("sufficient", clean, ["multi_claim_line"]) == "media"
    # los flags previos al gate conservan su regla (no cambian de semántica)
    assert svc._confidence("sufficient", clean, ["decision_language"]) == "alta"


def test_all_archived_versions_are_verifiable():
    """El verificador corre sobre las 6 propuestas archivadas sin excepción
    (incluye v1–v3 format_invalid de mistral)."""
    for v in range(1, 7):
        out = _verify(v)
        assert out["version"] == cv.VERIFIER_VERSION
        assert isinstance(out["findings"], list)


# ── Derivación de grants desde declaraciones (whitelist sin archivo nuevo) ────

def test_grants_derivation_rules():
    g = cv.parse_reference_grants([
        "21 CFR Part 11 §11.10 (todos los controles) — texto CFR público",
        "21 CFR 211.160, 211.165, 211.192, 211.194 — texto CFR público",
        "FDA Data Integrity Guidance 2018 (completo) — PDF",
        "21_CFR_PART_11", "21_CFR_211_192", "ALCOA_PLUS",
    ])
    assert {"11.10", "211.160", "211.165", "211.192", "211.194"} <= g["cfr_sections"]
    assert "11.30" not in g["cfr_sections"]      # jamás se deriva lo no enumerado
    assert {11, 211} <= g["cfr_parts"]
    assert any({"alcoa", "plus"} == d for d in g["documents"])


def test_reference_granularity_rules():
    g = cv.parse_reference_grants([
        "21 CFR Part 11 §11.10 (todos los controles) — texto CFR público",
        "FDA Data Integrity Guidance 2018 (completo) — PDF"])
    # sección enumerada, parte y subparte de parte declarada: citables
    assert cv.check_reference("21 CFR 11.10(e)", g) is None
    assert cv.check_reference("21 CFR Part 11", g) is None
    assert cv.check_reference("21 CFR Part 11 Subpart C", g) is None
    # sección NO enumerada: la parte declarada no autoriza secciones específicas
    assert cv.check_reference("21 CFR 11.30(c)", g)["reason"] == "cfr_section_not_declared"
    assert cv.check_reference("21 CFR 820.198", g)["reason"] == "cfr_section_not_declared"
    # documento declarado: citable a nivel documento, nunca con numeral
    assert cv.check_reference("FDA Data Integrity Guidance 2018", g) is None
    assert cv.check_reference("FDA Data Integrity Guidance 2018, §3.4",
                              g)["reason"] == "document_section_not_verifiable"
    # fuera de toda declaración
    assert cv.check_reference("EU Annex 11", g)["reason"] == "document_not_declared"
    assert cv.check_reference("", g)["reason"] == "empty_reference"


def test_pending_corpus_grants_title_citability():
    """corpus_pending otorga citabilidad de TÍTULO: el documento está
    declarado; la disponibilidad del contenido ya la captura
    corpus_sufficiency y la confianza computada."""
    g = _grants_integrity()      # DI Guidance 2018 está en corpus_pending real
    assert cv.check_reference("FDA Data Integrity Guidance 2018", g) is None


# ── Negaciones: solo la evidencia operacional contradice ──────────────────────

_ITEMS = [
    {"id": "audit", "trust": "internal",
     "content": "eventos de la misión: 5 · validation_doc_approved · por Cesar"},
    {"id": "runs", "trust": "internal",
     "content": "- alcoa_all_present: PASS · por cesar"},
    {"id": "mission", "trust": "internal",
     "content": "debe generar firma electrónica del analista y del supervisor"},
]


def test_negation_matched_against_operational_records():
    claims = [{"tag": "SE", "pointer": None,
               "text": "No hay evidencia de aprobaciones humanas en el sistema, "
                       "lo que impide verificar el cumplimiento."}]
    f = cv.check_negations(claims, _ITEMS)
    assert len(f) == 1
    assert f[0]["matched_tokens"] == {"aprobaciones": "approv"}


def test_negation_not_contradicted_by_intent_evidence():
    """La misión PIDE firma electrónica (intención) — eso NO contradice
    'no hay evidencia de firmas electrónicas' (hecho). mission/agents/catalog
    quedan fuera del contraste a propósito."""
    claims = [{"tag": "SE", "pointer": None,
               "text": "Falta evidencia de firmas electrónicas conforme a la "
                       "Subparte C; sin ellas no hay autenticidad."}]
    assert cv.check_negations(claims, _ITEMS) == []


def test_negation_all_rule_requires_every_subject_token():
    claims = [{"tag": "SE", "pointer": None,
               "text": "No hay evidencia de un SOP de revisión periódica del "
                       "audit trail; sin él no puede evaluarse."}]
    assert cv.check_negations(claims, _ITEMS) == []


def test_negation_without_operational_evidence_never_flags():
    claims = [{"tag": "SE", "pointer": None,
               "text": "No hay evidencia de aprobaciones humanas."}]
    only_intent = [it for it in _ITEMS if it["id"] == "mission"]
    assert cv.check_negations(claims, only_intent) == []


# ── intra_proposal_contradiction (v2.1, W7) ───────────────────────────────────

def test_w7_v08_flags_intra_proposal_contradiction():
    """[W7 Fase A/B] v08 REAL → intra_proposal_contradiction: la viñeta [SE]
    'No hay evidencia de un perfil de agente dedicado a la gestión OOS'
    contradice la [E: agents] 'qa_oos_profile es el perfil específico para la
    gestión OOS' de la misma respuesta. El v2.0 no lo veía (solo contrastaba
    contra evidencia operacional); lo detectó Cesar a mano — limitación 1 del
    preflight de Fase 0, cerrada con este fixture."""
    out = _verify(8)
    intra = [f for f in out["findings"]
             if f["type"] == "intra_proposal_contradiction"]
    assert "intra_proposal_contradiction" in out["flags"]
    assert len(intra) == 1
    assert "perfil de agente dedicado" in intra[0]["claim"]
    assert intra[0]["contradicted_by_pointer"] == "agents"
    assert "qa_oos_profile" in intra[0]["contradicted_by"]


def test_w7_archived_v01_v07_no_intra_regressions():
    """Precisión: la regla nueva NO dispara en ninguna versión archivada
    previa (v01–v07) y sus flags existentes no cambian."""
    expected = {1: [], 2: [], 3: [], 4: ["multi_claim_line"],
                5: ["unverified_reference"], 6: ["negation_contradicted"],
                7: []}
    for v, flags in expected.items():
        out = _verify(v)
        assert out["flags"] == flags, f"v{v:02d}"


def test_intra_contradiction_requires_two_subject_tokens():
    """Un solo sustantivo negado ('reglas') es señal demasiado débil: v08 real
    contiene '[SE] no hay evidencia de reglas que garanticen...' junto a
    '[E: catalog] el catálogo incluye reglas...' y NO es contradicción."""
    claims = [
        {"tag": "E", "pointer": "catalog", "support": "supported",
         "text": "El catálogo incluye reglas para la validación ALCOA+."},
        {"tag": "SE", "pointer": None, "support": "unverifiable",
         "text": "No hay evidencia de reglas que garanticen la consistencia."},
    ]
    assert cv.check_intra_contradictions(claims) == []


def test_intra_contradiction_ignores_negated_segments_in_e_claims():
    """Dos negaciones coincidentes son ACUERDO, no contradicción: el segmento
    negado dentro de la [E:] se excluye del contraste."""
    claims = [
        {"tag": "E", "pointer": "runs", "support": "partially_supported",
         "text": "Las ejecuciones tienen PASS, pero no hay evidencia de "
                 "firmas electrónicas conformes."},
        {"tag": "SE", "pointer": None, "support": "unverifiable",
         "text": "No hay evidencia de firmas electrónicas en los registros."},
    ]
    assert cv.check_intra_contradictions(claims) == []


def test_intra_contradiction_only_against_verified_e_claims():
    """Una [E:] unsupported no sirve de base para señalar contradicción: su
    propio contenido ya está en duda (flag unsupported_claims)."""
    claims = [
        {"tag": "E", "pointer": "agents", "support": "unsupported",
         "text": "El perfil qa_oos_profile cubre la gestión OOS del flujo."},
        {"tag": "SE", "pointer": None, "support": "unverifiable",
         "text": "No hay evidencia de un perfil para la gestión OOS del flujo."},
    ]
    assert cv.check_intra_contradictions(claims) == []


def test_qualifier_lexicon_extension_dedicado():
    """v2.1 añadió 'dedicado/a(s)' a los tokens genéricos (misma categoría que
    'específico'): el calificador no identifica al sujeto negado. Test que
    fija la extensión del léxico, como exige el módulo."""
    assert "dedicado" in cv._GENERIC_SUBJECT_TOKENS
    claims = [
        {"tag": "E", "pointer": "agents", "support": "supported",
         "text": "qa_oos_profile es el perfil de agente para la gestión OOS."},
        {"tag": "SE", "pointer": None, "support": "unverifiable",
         "text": "No hay evidencia de un perfil de agente dedicado a la "
                 "gestión OOS; sin él no se garantiza el flujo."},
    ]
    f = cv.check_intra_contradictions(claims)
    assert len(f) == 1 and f[0]["contradicted_by_pointer"] == "agents"


def test_w7_confidence_penalized_by_intra_contradiction():
    """Contradicción interna = texto potencialmente falso → confianza baja
    (misma filosofía anti-optimismo que negation/reference)."""
    clean = {"supported": 3, "partially_supported": 0,
             "unsupported": 0, "unverifiable": 0}
    assert svc._confidence("sufficient", clean,
                           ["intra_proposal_contradiction"]) == "baja"


# ── multi_claim_line ──────────────────────────────────────────────────────────

def test_multi_claim_line_detection():
    resp = ("- [E: runs] a ok. [SE] falta x. [REF: 21 CFR 11.10] norma.\n"
            "- [E: mission] una sola claim por línea no señala.\n"
            "## Limitaciones\n- ok\n")
    f = cv.check_multi_claim_lines(resp)
    assert len(f) == 1
    assert f[0]["line_number"] == 1 and len(f[0]["tags"]) == 3


# ── Estructural: módulo puro ──────────────────────────────────────────────────

def test_verifier_module_is_pure():
    """Advisory y determinista: sin HTTP, sin auditoría, sin escritura."""
    src = Path(cv.__file__).read_text(encoding="utf-8")
    assert "import httpx" not in src
    assert "audit_writer" not in src and "write_event" not in src
    assert "write_text" not in src and "open(" not in src
