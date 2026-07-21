"""
Tests -- factory/services/document_quality_gates.py (Fase 6,
document_remediation_evolution).

Gate del roadmap: los 3 proposed_content reales existentes (COR-1, COR-2,
COR-5) pasan los controles evaluables sin ningun CHANGE_NOT_APPLIED --
si alguno fallara seria senal real de gate mal calibrado o de un
problema real no detectado hasta ahora (ninguno se fuerza).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import document_structure_extractor as extractor
from factory.services import document_quality_gates as gates
from factory.services.remediation_package_schemas import SchemaValidationError

STRUCTURE = {
    "total_paginas": 5,
    "secciones": [
        {
            "numero": "1", "titulo": "Introduction", "pagina_inicio": 1,
            "parrafos": ["El sistema garantiza la trazabilidad de todos los eventos."],
        },
        {
            "numero": "2", "titulo": "Retention", "pagina_inicio": 3,
            "parrafos": ["No aplica retencion de datos historicos en este sistema."],
        },
    ],
    "texto_previo_a_primera_seccion": [],
    "toc_anchored": True,
}

VALID_CITATION = {
    "citation_id": "CIT-X", "regulatory_catalog_entry_id": "ALCOA_ATTRIBUTABLE",
    "regulatory_source": "mhra_gxp_di_guidance_2018",
    "regulatory_source_sha256": "a" * 64, "requirement_catalog_sha256": "b" * 64,
    "run_id": "RUN-X", "record_id": "REC-X", "document_role": "SOURCE_DOCUMENT",
    "document_sha256": "c" * 64, "chunk_sha256": "d" * 64,
    "citation_locator": "chunk_1#p1-1", "page_start": 1, "page_end": 1,
    "literal_text": "texto literal", "evidence_type": "LITERAL_QUOTE",
    "evidence_location": "doc.pdf pag 1",
}
VALID_CITATION["citation_text_sha256"] = __import__("hashlib").sha256(
    VALID_CITATION["literal_text"].encode("utf-8")
).hexdigest()


def _change(proposed_content, **overrides):
    change = {
        "change_id": "COR-TEST", "finding_id": "F-1", "requirement_id": "ALCOA_ATTRIBUTABLE",
        "document_location": "doc.pdf pag 1", "original_content": None,
        "proposed_content": proposed_content, "change_reason": "motivo real",
        "change_type": "CONTENT_ADDITION", "citations": [VALID_CITATION],
        "change_risk": "MEDIUM_RISK", "change_risk_basis": ["change_type"],
        "evaluation_confidence": "HIGH_CONFIDENCE",
        "evaluation_confidence_basis": ["citation_anchor_status"],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT",
        "limitations": "",
    }
    change.update(overrides)
    return change


def test_valid_change_passes_all_evaluable_controls():
    change = _change("Incluir una nota de sincronizacion de eventos operativos.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert result["applied"] is True
    assert result["failed_controls"] == []
    assert result["controls"]["redaccion_terminologia"]["status"] == "NOT_EVALUATED"
    assert result["controls"]["redaccion_ortografia"]["status"] == "NOT_EVALUATED"


def test_invented_capability_not_in_source_fails():
    change = _change("Incluir que el sistema valida automaticamente cada firma electronica.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert "validez_tecnica_capacidad_inventada" in result["failed_controls"]
    assert result["applied"] is False


def test_capability_claim_present_in_source_passes():
    change = _change("Incluir que el sistema garantiza la trazabilidad de todos los eventos.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert result["controls"]["validez_tecnica_capacidad_inventada"]["status"] == "PASS"


def test_too_short_proposed_content_fails_length():
    change = _change("Incluir esto.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    # "Incluir esto." son 2 palabras -- por debajo de MIN_WORDS=3
    assert "redaccion_longitud" in result["failed_controls"]


def test_verb_outside_controlled_vocabulary_fails():
    change = _change("Detallar la politica de retencion de datos completa.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert "redaccion_verbo_controlado" in result["failed_controls"]


def test_verb_in_controlled_vocabulary_passes():
    for verbo, texto in [
        ("agregar", "Agregar una seccion de politica de backup completa."),
        ("incluir", "Incluir el detalle del proceso de restauracion aqui."),
        ("reemplazar", "Reemplazar el parrafo obsoleto por el texto correcto."),
    ]:
        change = _change(texto)
        result = gates.evaluate_quality_gates(change, STRUCTURE)
        assert result["controls"]["redaccion_verbo_controlado"]["status"] == "PASS", verbo


def test_coherence_contradiction_with_negation_fails():
    change = _change("Agregar una politica de retencion de datos historicos completa.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert "coherencia_documental" in result["failed_controls"]


def test_coherence_without_overlapping_terms_passes():
    change = _change("Incluir el nombre del responsable de calibracion del equipo.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert result["controls"]["coherencia_documental"]["status"] == "PASS"


def test_unverified_implementation_claim_fails():
    change = _change("Incluir que se ha verificado que el control opera correctamente.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert "ausencia_afirmacion_no_demostrada" in result["failed_controls"]


def test_recommendation_verb_never_triggers_unverified_claim():
    change = _change("Incluir la identificacion del responsable en cada registro.")
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert result["controls"]["ausencia_afirmacion_no_demostrada"]["status"] == "PASS"


def test_invalid_regulatory_catalog_entry_id_fails_via_reused_schema():
    change = _change("Incluir un cambio con catalogo invalido de prueba.")
    change["citations"] = [{**VALID_CITATION, "regulatory_catalog_entry_id": "NO_EXISTE_EN_CATALOGO"}]
    result = gates.evaluate_quality_gates(change, STRUCTURE)
    assert "validez_regulatoria_y_trazabilidad" in result["failed_controls"]


def test_check_regulatory_validity_reuses_validate_remediation_change_directly():
    """No reinventa la validacion -- delega en el schema ya probado."""
    change = _change("Incluir texto de prueba suficientemente largo.")
    del change["finding_id"]  # rompe trazabilidad (campo obligatorio del schema real)
    with pytest.raises(SchemaValidationError):
        from factory.services.remediation_package_schemas import validate_remediation_change
        validate_remediation_change(change)
    result = gates.check_regulatory_validity_and_traceability(change)
    assert result["status"] == "FAIL"


REAL_PDF = Path(
    "/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
)
REAL_PACKAGES_DIR = Path("/home/ing_cpmo/factory/remediation_packages/gmpai_document_validation")


def _load_real_changes() -> list[dict]:
    changes = []
    for pkg, ids in [
        ("PKG-FS-V1-2-MEDIUM-RISK-REAL", ["COR-1"]),
        ("PKG-FS-V1-2-REAL-CONTROLLED", ["COR-2", "COR-5"]),
    ]:
        state = json.loads((REAL_PACKAGES_DIR / pkg / "v1" / "state.json").read_text(encoding="utf-8"))
        for change_id in ids:
            changes.append(state["changes"][change_id])
    return changes


def test_fase6_gate_3_real_changes_pass_all_evaluable_controls():
    """Gate de Fase 6 (`IMPLEMENTATION_ROADMAP.md`): los 3 proposed_content
    reales ya aprobados por Cesar (COR-1, COR-2, COR-5) pasan los
    controles evaluables sin ningun CHANGE_NOT_APPLIED."""
    if not REAL_PDF.exists() or not REAL_PACKAGES_DIR.exists():
        pytest.skip("PDF real o paquetes reales no disponibles en este entorno")

    structure = extractor.extract_structure_from_pdf(REAL_PDF)
    changes = _load_real_changes()
    assert {c["change_id"] for c in changes} == {"COR-1", "COR-2", "COR-5"}

    for change in changes:
        result = gates.evaluate_quality_gates(change, structure)
        assert result["applied"] is True, (change["change_id"], result["failed_controls"], result["controls"])
        assert result["failed_controls"] == []
