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


def _map(findings_by_id, finding_id):
    return mapper.map_finding_to_remediation_change(
        findings_by_id[finding_id],
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
    findings = [findings_by_id[fid] for fid in ("FSV12-07", "FSV12-13", "FSV12-11", "FSV12-12", "FSV12-19")]
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
