"""
Tests -- factory/services/golden_dataset_criteria.py (Fase 7,
document_remediation_evolution).

Este modulo NO cierra el gate completo de Fase 7 (12/12 sobre el Golden
Dataset completo -- faltan 8/14 categorias reales por recolectar, ver
REGULATORY_VALIDATION_PLAN.md SS2). Mecaniza los 12 criterios y los corre
de verdad contra los 2 casos reales ya disponibles, reportando PASS/FAIL/
NOT_EVALUATED con evidencia real -- nunca fuerza un resultado.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.regulatory import document_structure_extractor as extractor
from factory.services import golden_dataset_criteria as gdc

STRUCTURE = {
    "total_paginas": 5,
    "secciones": [
        {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1, "parrafos": ["texto original"]},
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


def _change(**overrides):
    change = {
        "change_id": "COR-TEST", "finding_id": "F-1", "requirement_id": "ALCOA_ATTRIBUTABLE",
        "document_location": "doc.pdf pag 1", "original_content": None,
        "proposed_content": "Incluir un detalle real suficientemente largo aqui.",
        "change_reason": "motivo real", "change_type": "CONTENT_ADDITION",
        "citations": [dict(VALID_CITATION)],
        "change_risk": "MEDIUM_RISK", "change_risk_basis": ["change_type"],
        "evaluation_confidence": "HIGH_CONFIDENCE",
        "evaluation_confidence_basis": ["citation_anchor_status"],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT",
        "limitations": "",
    }
    change.update(overrides)
    return change


def test_check_schema_valid_passes_for_valid_change():
    result = gdc.check_schema_valid([_change()])
    assert result["status"] == "PASS"


def test_check_schema_valid_fails_for_broken_change():
    change = _change()
    del change["finding_id"]
    result = gdc.check_schema_valid([change])
    assert result["status"] == "FAIL"


def test_check_applicability_traceable_passes_for_expected_requirement():
    result = gdc.check_applicability_traceable([_change()], "FS")
    assert result["status"] == "PASS"


def test_check_applicability_traceable_fails_for_unmapped_document_type():
    result = gdc.check_applicability_traceable([_change()], "SOP_UNMAPPED_TYPE")
    assert result["status"] == "FAIL"


def test_check_official_source_citations_fails_for_unknown_entry_id():
    change = _change()
    change["citations"][0]["regulatory_catalog_entry_id"] = "NO_EXISTE"
    result = gdc.check_official_source_citations([change])
    assert result["status"] == "FAIL"


def test_check_no_invented_citations_fails_on_hash_mismatch():
    change = _change()
    change["citations"][0]["citation_text_sha256"] = "0" * 64
    result = gdc.check_no_invented_citations([change])
    assert result["status"] == "FAIL"


def test_check_no_invented_citations_passes_on_matching_hash():
    result = gdc.check_no_invented_citations([_change()])
    assert result["status"] == "PASS"


def test_check_no_partial_coverage_gap_is_not_evaluated_honestly():
    """Gap real declarado, no un PASS fingido -- verified_conclusions no
    existe en ningun RemediationChange real todavia (Fase 3 sin cablear
    por defecto)."""
    result = gdc.check_no_partial_coverage_gap()
    assert result["status"] == "NOT_EVALUATED"


def test_check_no_artifact_divergence_is_not_evaluated_honestly():
    result = gdc.check_no_artifact_divergence()
    assert result["status"] == "NOT_EVALUATED"


def test_check_no_pending_high_risk_passes_with_reviewed_exception():
    package_state = {
        "package": {"changes": {"high_risk": ["COR-1"], "medium_risk": [], "low_risk": []}},
        "exceptions": {
            "EXC-COR-1": {"change_id": "COR-1", "status": "REVIEWED", "human_review_decision": "ACCEPTED_WITH_JUSTIFICATION"}
        },
    }
    result = gdc.check_no_pending_high_risk_without_exception(package_state)
    assert result["status"] == "PASS"


def test_check_no_pending_high_risk_fails_without_exception():
    package_state = {
        "package": {"changes": {"high_risk": ["COR-1"], "medium_risk": [], "low_risk": []}},
        "exceptions": {},
    }
    result = gdc.check_no_pending_high_risk_without_exception(package_state)
    assert result["status"] == "FAIL"


def test_check_no_automatic_release_passes_structurally():
    """Verificacion estructural real: el router de remediation_packages no
    registra ninguna ruta de release ni importa create_release_record."""
    result = gdc.check_no_automatic_release()
    assert result["status"] == "PASS"


REAL_PDF = Path(
    "/home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
)
REAL_PACKAGES_DIR = Path("/home/ing_cpmo/factory/remediation_packages/gmpai_document_validation")


def test_fase7_criteria_run_against_2_real_packages_no_fail():
    """No es el gate completo de Fase 7 (faltan 8/14 categorias reales del
    Golden Dataset) -- pero de los criterios mecanizables hoy, ninguno
    falla contra los 2 casos reales ya disponibles; los que quedan
    NOT_EVALUATED lo hacen con motivo real declarado, nunca forzado."""
    if not REAL_PDF.exists() or not REAL_PACKAGES_DIR.exists():
        pytest.skip("PDF real o paquetes reales no disponibles en este entorno")

    structure = extractor.extract_structure_from_pdf(REAL_PDF)

    for pkg_id in ["PKG-FS-V1-2-MEDIUM-RISK-REAL", "PKG-FS-V1-2-REAL-CONTROLLED"]:
        state = json.loads((REAL_PACKAGES_DIR / pkg_id / "v1" / "state.json").read_text(encoding="utf-8"))
        changes = list(state["changes"].values())
        result = gdc.evaluate_golden_dataset_criteria(state, changes, structure, "FS")

        assert result["failed"] == [], (pkg_id, result["failed"], result["criteria"])
        assert set(result["not_evaluated"]) <= {
            "4_enlaces_verificados", "6_sin_cobertura_parcial_en_gap", "10_sin_divergencia_artefactos",
        }
        assert result["gate_12_of_12"] is False
