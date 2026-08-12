"""
Tests -- factory/services/gap_assessment_finding_mapper.py.

Fijan como codigo el comportamiento ya verificado en vivo contra
factory/docs/gmpai_reanalysis/fs_v1_2/findings_completos_FS_v1_2_v4.json
(paquete real PKG-FS-V1-2-REAL-CONTROLLED, proyecto
gmpai_document_validation): FSV12-07->COR-5, FSV12-13->COR-2 mapeados;
FSV12-19 rechazado por ambiguedad de anclaje de pagina. Usa el fixture
REAL (no datos inventados) para que un cambio futuro en el archivo real
se note aqui como regresion, no como sorpresa en produccion.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory.absence_consolidator import consolidate
from factory.services import gap_assessment_finding_mapper as mapper
from factory.services.remediation_package_schemas import validate_remediation_change

FINDINGS_PATH = (
    Path(__file__).parent.parent / "docs" / "gmpai_reanalysis" / "fs_v1_2" / "findings_completos_FS_v1_2_v4.json"
)
DOCUMENT_NAME = "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
# sha256 real del PDF fuente, calculado independientemente en la sesion
# que corrio la prueba en vivo -- no se recalcula aqui a proposito (el
# PDF fuente no vive en el repo); este test solo fija el comportamiento
# del mapeo, no la integridad del archivo original.
DOCUMENT_SHA256 = "56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb"
RUN_ID = "RUN-FS_V1_2-v4.1-2026-07-16T21:25:40.305486+00:00"


@pytest.fixture(scope="module")
def findings_by_id():
    doc = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    return {f["finding_id"]: f for f in doc["findings"]}


# Deuda I-1 (W5 V2, 2026-07-27): la heuristica de texto ya no mapea un
# finding de estado POSITIVO sin veredicto sustantivo A^B^C^D. El fixture
# real es anterior a Fase F y no lo trae, asi que los tests que fijan la
# MECANICA del mapeo le adjuntan el veredicto explicito que una corrida
# real con D==MET habria producido. La regla nueva se prueba aparte, abajo
# (test_legacy_positive_finding_*), sobre el fixture crudo sin tocar.
_SUPPORTED_VERDICT = {
    "d_sufficiency": "MET",
    "substantive_evidence_accepted": True,
    "substantive_support": "SUPPORTED",
}
_POSITIVE_ESTADOS_FIXTURE = ("cumple", "cumple_parcialmente")


def _with_declared_verdict(finding):
    """Adjunta el veredicto solo a los estados positivos -- un no_cumple
    da NOT_APPLICABLE por si solo y no necesita declaracion."""
    if finding.get("estado_agente_original") in _POSITIVE_ESTADOS_FIXTURE:
        return {**finding, **_SUPPORTED_VERDICT}
    return finding


def _map(findings_by_id, finding_id):
    return mapper.map_finding_to_remediation_change(
        _with_declared_verdict(findings_by_id[finding_id]),
        document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
    )


# ── FSV12-07 -> COR-5: cita literal, HIGH_RISK, anclaje por auto-marcador ───

def test_fsv12_07_maps_to_cor5(findings_by_id):
    result = _map(findings_by_id, "FSV12-07")
    change = result.change
    assert change["change_id"] == "COR-5"
    assert change["requirement_id"] == "ANNEX11_7.1"
    assert change["change_type"] == "CONTENT_ADDITION"
    assert change["candidate_application_status"] == "APPLIED_TO_DRAFT"
    assert change["original_content"] == change["citations"][0]["literal_text"]


def test_fsv12_07_risk_and_confidence(findings_by_id):
    result = _map(findings_by_id, "FSV12-07")
    assert result.risk_factors["gxp_impact"] == "DIRECT_GXP_IMPACT"
    assert result.risk_factors["evidence_status"] == "PARTIAL_EVIDENCE"
    assert result.change["change_risk"] == "HIGH_RISK"
    assert result.change["change_risk_basis"] == ["gxp_impact"]
    assert result.change["evaluation_confidence"] == "HIGH_CONFIDENCE"


def test_fsv12_07_citation_anchor_from_self_reference(findings_by_id):
    result = _map(findings_by_id, "FSV12-07")
    citation = result.change["citations"][0]
    assert citation["page_start"] == 40
    assert citation["page_end"] == 40
    assert citation["citation_locator"] == "p40-40"
    assert citation["evidence_type"] == "LITERAL_QUOTE"
    assert "Page 40 of 58" in citation["literal_text"]


def test_fsv12_07_citation_text_sha256_matches_recomputation(findings_by_id):
    result = _map(findings_by_id, "FSV12-07")
    citation = result.change["citations"][0]
    recomputed = hashlib.sha256(citation["literal_text"].encode("utf-8")).hexdigest()
    assert recomputed == citation["citation_text_sha256"]


# ── FSV12-13 -> COR-2: ausencia confirmada, HIGH_RISK, anclaje por chunk ───

def test_fsv12_13_maps_to_cor2(findings_by_id):
    result = _map(findings_by_id, "FSV12-13")
    change = result.change
    assert change["change_id"] == "COR-2"
    assert change["requirement_id"] == "ALCOA_CONTEMPORANEOUS"
    assert change["original_content"] is None
    assert change["citations"][0]["evidence_type"] == "ABSENCE_CONFIRMATION"


def test_fsv12_13_risk_and_confidence(findings_by_id):
    result = _map(findings_by_id, "FSV12-13")
    assert result.risk_factors["evidence_status"] == "ABSENCE_CONFIRMED"
    # ALCOA_CONTEMPORANEOUS es guia MHRA no vinculante (binding_status=
    # non_binding_guidance) -> gxp_impact=INDIRECT, no DIRECT_GXP_IMPACT.
    # Sigue en HIGH_RISK, pero ahora solo por evidence_status (ausencia
    # confirmada), no por los dos factores empatados como antes.
    assert result.risk_factors["gxp_impact"] == "INDIRECT"
    assert result.change["change_risk"] == "HIGH_RISK"
    assert result.change["change_risk_basis"] == ["evidence_status"]
    assert result.change["evaluation_confidence"] == "HIGH_CONFIDENCE"


def test_fsv12_13_citation_anchor_from_explicit_chunk(findings_by_id):
    result = _map(findings_by_id, "FSV12-13")
    citation = result.change["citations"][0]
    assert citation["page_start"] == 41
    assert citation["page_end"] == 42
    assert citation["citation_locator"] == "chunk_17#p41-42"


# ── FSV12-11 -> COR-1: gxp_impact=INDIRECT (ALCOA+, guia no vinculante) +  ──
# severidad=menor -> primer MEDIUM_RISK real del catalogo, anclaje por
# rango unico con chunk (mismo patron que antes solo se aceptaba para
# evidence_status=ABSENCE_CONFIRMED, ahora generalizado)

def test_fsv12_11_maps_to_cor1_medium_risk(findings_by_id):
    result = _map(findings_by_id, "FSV12-11")
    change = result.change
    assert change["change_id"] == "COR-1"
    assert change["requirement_id"] == "ALCOA_ATTRIBUTABLE"
    assert result.risk_factors["gxp_impact"] == "INDIRECT"
    assert result.risk_factors["requirement_criticality"] == "MINOR"
    assert change["change_risk"] == "MEDIUM_RISK"
    assert change["evaluation_confidence"] == "HIGH_CONFIDENCE"
    citation = change["citations"][0]
    assert citation["citation_locator"] == "chunk_3#p7-9"
    assert citation["evidence_type"] == "LITERAL_QUOTE"


def test_fsv12_11_coverage_status_from_single_range_not_human_resolution(findings_by_id):
    """A diferencia de FSV12-07 (rango multiple, necesita
    resolucion_humana_incorporada), FSV12-11 tiene un unico rango --
    coverage_status debe salir FULL_COVERAGE sin depender de ninguna
    resolucion humana registrada (este finding no tiene ese campo)."""
    finding = findings_by_id["FSV12-11"]
    assert "resolucion_humana_incorporada" not in finding
    result = _map(findings_by_id, "FSV12-11")
    assert result.confidence_factors["coverage_status"] == "FULL_COVERAGE"


# ── FSV12-12: rechazado -- verbo de 'recomendacion' ('Detallar') sin ───────
# mapeo conocido a change_type (independiente del problema de anclaje que
# tambien tiene: 'pag 22-23 (chunk 9) (confirmado ... pag 18-19)' no es un
# rango unico limpio)

def test_fsv12_12_is_not_mappable(findings_by_id):
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="change_type"):
        _map(findings_by_id, "FSV12-12")


# ── FSV12-19: rechazado -- 7 rangos de pagina sin correlacion univoca ──────

def test_fsv12_19_is_not_mappable(findings_by_id):
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="citation_locator/page_start/page_end"):
        _map(findings_by_id, "FSV12-19")


# ── Los 2 changes mapeados deben ser un RemediationChange valido de verdad ──

@pytest.mark.parametrize("finding_id", ["FSV12-07", "FSV12-13", "FSV12-11"])
def test_mapped_change_passes_real_schema_validation(findings_by_id, finding_id):
    """No basta con que el modulo produzca un dict con las claves
    correctas -- debe pasar el validador real (fail-closed) que usa
    remediation_package_service.create_package()."""
    result = _map(findings_by_id, finding_id)
    validate_remediation_change(result.change)  # no debe lanzar


# ── map_findings(): separa incluidos/rechazados sin que uno bloquee al otro ─

def test_map_findings_splits_included_and_rejected(findings_by_id):
    findings = [_with_declared_verdict(findings_by_id[fid])
                for fid in ("FSV12-07", "FSV12-13", "FSV12-11", "FSV12-12", "FSV12-19")]
    included, rejected = mapper.map_findings(
        findings, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
    )
    assert {m.change["change_id"] for m in included} == {"COR-5", "COR-2", "COR-1"}
    assert {r.finding_id for r in rejected} == {"FSV12-12", "FSV12-19"}


# ── gxp_impact diferenciado por binding_status del catalogo (segunda ───────
# iteracion, ver docstring del modulo): fijado como codigo para que
# cualquier regresion futura de esta regla se note de inmediato.

def test_gxp_impact_differentiates_binding_vs_guidance(findings_by_id):
    """21 CFR Part 11 / EU Annex 11 (binding_regulation/binding_requirement)
    -> DIRECT_GXP_IMPACT. ALCOA+ / MHRA GxP DI guidance (non_binding_guidance)
    -> INDIRECT. Antes de esta iteracion, gxp_impact era constante
    DIRECT_GXP_IMPACT para las 19 entradas del catalogo -- este test fija
    que eso ya no es cierto."""
    annex11 = _map(findings_by_id, "FSV12-07")  # ANNEX11_7.1
    assert annex11.risk_factors["gxp_impact"] == "DIRECT_GXP_IMPACT"

    alcoa_absence = _map(findings_by_id, "FSV12-13")  # ALCOA_CONTEMPORANEOUS
    assert alcoa_absence.risk_factors["gxp_impact"] == "INDIRECT"

    alcoa_partial = _map(findings_by_id, "FSV12-11")  # ALCOA_ATTRIBUTABLE
    assert alcoa_partial.risk_factors["gxp_impact"] == "INDIRECT"


def test_gxp_impact_unknown_binding_status_is_not_mappable():
    """Fail-closed: si el catalogo alguna vez declara un binding_status
    fuera de los 3 valores conocidos, el modulo rechaza en vez de
    adivinar un gxp_impact por defecto."""
    fake_entry = {"binding_status": "algo_nuevo_no_contemplado"}
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="gxp_impact"):
        mapper._derive_gxp_impact(fake_entry)


# ── Fase 2 (document_remediation_evolution): coverage_status consume ──────
# absence_consolidator.consolidate() REAL (no mockeado) cuando el llamador lo
# provee -- nunca la heuristica de texto. Gate del roadmap: un finding con
# coverage_complete=False real jamas llega a FULL_COVERAGE via el mapper.

_NOT_OBSERVED_RECORD = {"record_id": "r1", "status": "verified", "llm_output": {"chunk_observation": "not_observed"}}


def test_verified_conclusion_evaluation_incomplete_never_reaches_full_coverage(findings_by_id):
    incomplete = consolidate(
        "ALCOA_CONTEMPORANEOUS", "FS", "expected", [_NOT_OBSERVED_RECORD], coverage_complete=False,
    )
    assert incomplete.conclusion == "EVALUATION_INCOMPLETE"
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="EVALUATION_INCOMPLETE"):
        mapper.map_finding_to_remediation_change(
            findings_by_id["FSV12-13"], document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            run_id=RUN_ID, verified_conclusion=incomplete,
        )


def test_verified_conclusion_rejected_chunk_never_reaches_full_coverage(findings_by_id):
    """Mismo gate, pero via la otra condicion de EVALUATION_INCOMPLETE:
    coverage_complete=True pero algun chunk quedo rejected_by_verifier."""
    incomplete = consolidate(
        "ALCOA_CONTEMPORANEOUS", "FS", "expected",
        [_NOT_OBSERVED_RECORD, {"record_id": "r2", "status": "rejected_by_verifier", "llm_output": None}],
        coverage_complete=True,
    )
    assert incomplete.conclusion == "EVALUATION_INCOMPLETE"
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="EVALUATION_INCOMPLETE"):
        mapper.map_finding_to_remediation_change(
            findings_by_id["FSV12-13"], document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            run_id=RUN_ID, verified_conclusion=incomplete,
        )


def test_verified_conclusion_documentation_gap_maps_to_full_coverage(findings_by_id):
    gap = consolidate(
        "ALCOA_CONTEMPORANEOUS", "FS", "expected", [_NOT_OBSERVED_RECORD], coverage_complete=True,
    )
    assert gap.conclusion == "DOCUMENTATION_GAP"
    result = mapper.map_finding_to_remediation_change(
        findings_by_id["FSV12-13"], document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
        run_id=RUN_ID, verified_conclusion=gap,
    )
    assert result.confidence_factors["coverage_status"] == "FULL_COVERAGE"
    assert "absence_consolidator.consolidate()" in result.rules["coverage_status"]


def test_verified_conclusion_without_mapping_rule_is_not_mappable(findings_by_id):
    """CROSS_REFERENCE_MISSING no tiene regla de mapeo a RemediationChange
    todavia -- fail-closed, nunca se adivina un coverage_status."""
    cross_ref = consolidate(
        "ALCOA_CONTEMPORANEOUS", "FS", "cross_reference_expected", [_NOT_OBSERVED_RECORD], coverage_complete=True,
    )
    assert cross_ref.conclusion == "CROSS_REFERENCE_MISSING"
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="CROSS_REFERENCE_MISSING"):
        mapper.map_finding_to_remediation_change(
            findings_by_id["FSV12-13"], document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256,
            run_id=RUN_ID, verified_conclusion=cross_ref,
        )


def test_heuristic_path_still_used_by_default_and_labeled_incomplete_prone(findings_by_id):
    """Sin verified_conclusion (el caso real de hoy -- chunked_engine.py no
    genera chunk-level records), el mapper sigue usando la heuristica de
    texto de siempre, pero la regla ahora se etiqueta explicitamente como
    EVALUATION_INCOMPLETE-prone (Fase 2, TARGET_REGULATORY_ARCHITECTURE.md §6)."""
    result = _map(findings_by_id, "FSV12-13")
    assert result.confidence_factors["coverage_status"] == "FULL_COVERAGE"
    assert "EVALUATION_INCOMPLETE-prone" in result.rules["coverage_status"]


def test_map_findings_propagates_verified_conclusions_by_finding_id(findings_by_id):
    incomplete = consolidate(
        "ALCOA_CONTEMPORANEOUS", "FS", "expected", [_NOT_OBSERVED_RECORD], coverage_complete=False,
    )
    findings = [_with_declared_verdict(findings_by_id[fid])
                for fid in ("FSV12-07", "FSV12-13", "FSV12-11")]
    included, rejected = mapper.map_findings(
        findings, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        verified_conclusions={"FSV12-13": incomplete},
    )
    # FSV12-13 ahora rechazado por el verified_conclusion real; FSV12-07/11
    # sin entrada en el dict -> siguen su camino heuristico de siempre.
    assert {m.change["change_id"] for m in included} == {"COR-5", "COR-1"}
    assert {r.finding_id for r in rejected} == {"FSV12-13"}


# ── W5 V2 Fase I: citation_anchor_status conectado a la validacion A real ──
# (semantic_evidence_verification.verify_anchor) -- antes de esta fase era
# una constante hardcodeada 'VERIFIED', nunca re-verificada.

def test_citation_anchor_status_defaults_to_verified_without_source_text(findings_by_id):
    """Sin source_text (comportamiento historico, todo llamador existente
    hoy), citation_anchor_status sigue siendo VERIFIED incondicional --
    cero cambio de comportamiento para el resto de la suite."""
    result = _map(findings_by_id, "FSV12-07")
    assert result.change["citation_anchor_status"] == "VERIFIED"
    assert "source_text no provisto" in result.rules["citation_anchor_status"]


def test_citation_anchor_status_verified_when_source_text_contains_real_quote(findings_by_id):
    """FSV12-07 cita literalmente 'Page 40 of 58' (ver
    test_fsv12_07_citation_anchor_from_self_reference) -- si el source_text
    provisto contiene esa cita, debe re-verificarse como VERIFIED via
    verify_anchor real, no solo por la regla anterior."""
    finding = _with_declared_verdict(findings_by_id["FSV12-07"])
    citation_text = finding["evidencia"]
    source_text = f"contenido de relleno ... {citation_text} ... mas contenido"
    result = mapper.map_finding_to_remediation_change(
        finding, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        source_text=source_text,
    )
    assert result.change["citation_anchor_status"] == "VERIFIED"
    assert "verify_anchor real" in result.rules["citation_anchor_status"]


def test_citation_anchor_status_not_verified_when_quote_absent_from_source_text(findings_by_id):
    """Si se provee source_text pero NO contiene la cita real, el anclaje
    debe fallar (NOT_VERIFIED) -- nunca declarar VERIFIED por defecto."""
    finding = _with_declared_verdict(findings_by_id["FSV12-07"])
    source_text = "Este documento no contiene ninguna cita relacionada, es contenido completamente distinto."
    result = mapper.map_finding_to_remediation_change(
        finding, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        source_text=source_text,
    )
    assert result.change["citation_anchor_status"] == "NOT_VERIFIED"


def test_citation_anchor_not_verified_forces_medium_or_high_confidence_not_high(findings_by_id):
    """citation_anchor_status=NOT_VERIFIED es el nivel maximo (2) en
    _EVALUATION_CONFIDENCE_FACTOR_LEVELS -- debe forzar LOW_CONFIDENCE,
    nunca quedar enmascarado por los demas factores."""
    finding = _with_declared_verdict(findings_by_id["FSV12-07"])
    source_text = "contenido irrelevante sin ninguna cita real presente aqui."
    result = mapper.map_finding_to_remediation_change(
        finding, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        source_text=source_text,
    )
    assert result.change["evaluation_confidence"] == "LOW_CONFIDENCE"
    assert "citation_anchor_status" in result.change["evaluation_confidence_basis"]


def test_map_findings_propagates_source_text_to_every_finding(findings_by_id):
    source_text = "contenido sin ninguna de las citas reales de estos findings."
    findings = [_with_declared_verdict(findings_by_id[fid]) for fid in ("FSV12-07", "FSV12-13")]
    included, _rejected = mapper.map_findings(
        findings, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        source_text=source_text,
    )
    assert all(m.change["citation_anchor_status"] == "NOT_VERIFIED" for m in included)


# ── Deuda I-1 (W5 V2, 2026-07-27): la heuristica de texto no puede emitir ──
# FULL_COVERAGE sin veredicto sustantivo A^B^C^D. Se prueba sobre el fixture
# REAL crudo (sin _with_declared_verdict), que es anterior a Fase F.

def test_legacy_positive_finding_without_substantive_verdict_is_rejected(findings_by_id):
    """FSV12-07 (estado_agente_original='cumple_parcialmente') mapeaba a
    COR-5 con coverage_status=FULL_COVERAGE pese a que D nunca se evaluo
    para el. Ese era exactamente el agujero descrito en la deuda I-1, y
    ocurria sobre datos reales del paquete desplegado."""
    raw = findings_by_id["FSV12-07"]
    assert raw["estado_agente_original"] == "cumple_parcialmente"
    assert "substantive_support" not in raw
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="veredicto sustantivo"):
        mapper.map_finding_to_remediation_change(
            raw, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        )


def test_legacy_gap_finding_without_verdict_still_maps(findings_by_id):
    """Contrapeso obligatorio: un gap real (no_cumple -> NOT_APPLICABLE) no
    es sujeto de sustento sustantivo. Si la regla nueva lo rechazara,
    tumbaria justamente los findings que el pipeline de remediacion existe
    para tratar."""
    raw = findings_by_id["FSV12-13"]
    assert raw["estado_agente_original"] == "no_cumple"
    result = mapper.map_finding_to_remediation_change(
        raw, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
    )
    assert result.change["change_id"] == "COR-2"
    assert result.confidence_factors["coverage_status"] == "FULL_COVERAGE"


def test_not_supported_verdict_blocks_full_coverage(findings_by_id):
    """Veredicto transportado explicito y negativo: rechazo, sin importar
    lo que diga el texto de 'evidencia'."""
    finding = {**findings_by_id["FSV12-11"],
               "d_sufficiency": "NOT_MET", "substantive_evidence_accepted": False,
               "substantive_support": "NOT_SUPPORTED"}
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="NOT_SUPPORTED"):
        mapper.map_finding_to_remediation_change(
            finding, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        )


def test_inconsistent_verdict_is_rejected_not_resolved(findings_by_id):
    """SUPPORTED declarado sobre evidencia no aceptada: contradiccion ->
    rechazo. Nunca se elige el lado optimista."""
    finding = {**findings_by_id["FSV12-11"],
               "d_sufficiency": "NOT_ASSESSABLE", "substantive_evidence_accepted": None,
               "substantive_support": "SUPPORTED"}
    with pytest.raises(mapper.NotMappableToCurrentSchema, match="INCONSISTENT"):
        mapper.map_finding_to_remediation_change(
            finding, document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        )


def test_substantive_verdict_is_recorded_in_the_mapping_rules(findings_by_id):
    """Trazabilidad: un auditor debe ver de donde salio el veredicto sin
    deducir que ruta se uso."""
    result = _map(findings_by_id, "FSV12-11")
    assert "substantive_verdict" in result.rules
    assert "SUPPORTED" in result.rules["substantive_verdict"]


def test_verified_conclusion_path_also_records_the_verdict(findings_by_id):
    """La ruta verified_conclusion (donde Fase F ya aplico D) tambien deja
    la traza -- el veredicto no desaparece por tomar el otro camino."""
    observed = {"record_id": "r9", "status": "verified",
                "llm_output": {"chunk_observation": "observed"}}
    conclusion = consolidate(
        "ALCOA_ATTRIBUTABLE", "FS", "expected", [observed], coverage_complete=True,
    )
    result = mapper.map_finding_to_remediation_change(
        _with_declared_verdict(findings_by_id["FSV12-11"]),
        document_name=DOCUMENT_NAME, document_sha256=DOCUMENT_SHA256, run_id=RUN_ID,
        verified_conclusion=conclusion,
    )
    assert "substantive_verdict" in result.rules


# ── R3-T1.8 bloque 2 (docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md):
# Ruta D (este modulo) es LATENTE hoy (sin llamador de produccion) pero se
# activaria en R4-T1 -- estos tests fijan que, si se activa, consume la
# superficie unica (candidate_validity) para headlines derivados en vez de
# reimplementar/romperse con el mismo defecto B4/B5 por un quinto sitio.

_DERIVED_PREFIX = "[headline derivado de citas por criterio verificadas] "


def test_derive_citation_anchor_status_verifies_each_derived_quote_individually():
    """Headline derivado con 2 citas, AMBAS ancladas en source_text ->
    VERIFIED. Antes de este fix, verify_anchor() sobre el texto COMPLETO
    (prefijo + ' | ' + citas) jamas encontraria un match literal -- el
    mismo defecto ya encontrado y corregido para la Ruta B
    (verified_pipeline_adapter), ahora tambien cerrado aqui."""
    quote1 = "Timestamp de fecha y hora del cambio registrado en el sistema."
    quote2 = "Registro de entradas y acciones del operador conservado."
    source_text = f"Introduccion. {quote1} Texto intermedio. {quote2} Cierre."
    evidencia = _DERIVED_PREFIX + f"{quote1} | {quote2}"
    status, rule = mapper._derive_citation_anchor_status(evidencia, "R1", source_text)
    assert status == "VERIFIED", rule
    assert "2 cita(s) derivada(s)" in rule


def test_derive_citation_anchor_status_rejects_when_one_derived_quote_unanchored():
    """Una sola cita del conjunto derivado que NO ancla invalida el
    conjunto entero -- nunca se rescata parcialmente (guardian central
    anti-fabricacion, mismo principio que candidate_validity.py)."""
    quote1 = "Timestamp de fecha y hora del cambio registrado en el sistema."
    quote_fabricada = "Este texto jamas aparece en el documento fuente."
    source_text = f"Introduccion. {quote1} Cierre."
    evidencia = _DERIVED_PREFIX + f"{quote1} | {quote_fabricada}"
    status, rule = mapper._derive_citation_anchor_status(evidencia, "R1", source_text)
    assert status == "NOT_VERIFIED", rule


def test_derive_citation_anchor_status_still_handles_direct_headline():
    """Retrocompatibilidad: un headline DIRECTO (no derivado, el caso
    historico ya cubierto) sigue verificandose exactamente igual que
    antes -- la rama nueva solo se activa para headlines derivados."""
    quote = "Cita directa real del modelo, sin rescate."
    source_text = f"Contexto. {quote} Fin."
    status, rule = mapper._derive_citation_anchor_status(quote, "R1", source_text)
    assert status == "VERIFIED", rule
    assert "headline derivado" not in rule
