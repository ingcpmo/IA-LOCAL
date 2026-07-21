"""
Tests — validacion formal de RegulatoryCitationReference/RemediationChange/
ArtifactReference (factory/services/remediation_package_schemas.py).
"""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.services import remediation_package_schemas as schemas


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _valid_citation(**overrides) -> dict:
    literal_text = "El sistema registra fecha y hora del evento en el momento de su ocurrencia."
    citation = {
        "citation_id": "CIT-1", "regulatory_catalog_entry_id": "ALCOA_CONTEMPORANEOUS",
        "regulatory_source": "ALCOA+", "regulatory_source_sha256": _sha256("source"),
        "requirement_catalog_sha256": _sha256("catalog"), "run_id": "RUN-1", "record_id": "REC-1",
        "document_role": "CANDIDATE_DOCUMENT", "document_sha256": _sha256("doc"),
        "chunk_sha256": _sha256("chunk"), "citation_locator": "chunk_20#p12-14",
        "page_start": 12, "page_end": 14, "literal_text": literal_text,
        "citation_text_sha256": _sha256(literal_text), "evidence_type": "LITERAL_QUOTE",
        "evidence_location": "seccion 4.2",
    }
    citation.update(overrides)
    return citation


def _valid_artifact(**overrides) -> dict:
    artifact = {
        "artifact_id": "ART-1", "storage_location": "/synthetic/candidate.docx",
        "mime_type": "application/octet-stream", "sha256": _sha256("payload"), "size_bytes": 2048,
        "classification": "CANDIDATE_DRAFT", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    artifact.update(overrides)
    return artifact


def _valid_change(**overrides) -> dict:
    change = {
        "change_id": "C1", "finding_id": "F1", "requirement_id": "REQ-1",
        "document_location": "seccion_4.2", "original_content": None, "proposed_content": "texto propuesto",
        "change_reason": "brecha detectada", "change_type": "CONTENT_ADDITION",
        "citations": [_valid_citation()], "change_risk": "MEDIUM_RISK", "change_risk_basis": ["change_type"],
        "evaluation_confidence": "HIGH_CONFIDENCE", "evaluation_confidence_basis": ["coverage_status"],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT",
        "limitations": "",
    }
    change.update(overrides)
    return change


# ── RegulatoryCitationReference ──────────────────────────────────────────────

def test_valid_citation_passes():
    schemas.validate_regulatory_citation_reference(_valid_citation())


def test_citation_unknown_catalog_entry_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="no existe en el catalogo"):
        schemas.validate_regulatory_citation_reference(_valid_citation(regulatory_catalog_entry_id="NO_EXISTE_XYZ"))


def test_citation_alcoa_contemporaneous_is_a_real_catalog_entry():
    schemas.validate_regulatory_citation_reference(_valid_citation(regulatory_catalog_entry_id="ALCOA_CONTEMPORANEOUS"))


def test_citation_text_sha256_mismatch_rejected():
    bad = _valid_citation()
    bad["citation_text_sha256"] = "0" * 64
    with pytest.raises(schemas.SchemaValidationError, match="no coincide con el"):
        schemas.validate_regulatory_citation_reference(bad)


def test_citation_invalid_sha256_format_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="sha256 hexadecimal"):
        schemas.validate_regulatory_citation_reference(_valid_citation(document_sha256="not-a-hash"))


def test_citation_page_range_invalid_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="page_start/page_end"):
        schemas.validate_regulatory_citation_reference(_valid_citation(page_start=14, page_end=12))


def test_citation_missing_field_rejected():
    bad = _valid_citation()
    del bad["run_id"]
    with pytest.raises(schemas.SchemaValidationError, match="falta el campo obligatorio"):
        schemas.validate_regulatory_citation_reference(bad)


def test_citation_unexpected_property_rejected():
    bad = _valid_citation()
    bad["campo_no_declarado"] = "x"
    with pytest.raises(schemas.SchemaValidationError, match="propiedades inesperadas"):
        schemas.validate_regulatory_citation_reference(bad)


def test_citation_invalid_document_role_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="valor invalido"):
        schemas.validate_regulatory_citation_reference(_valid_citation(document_role="SOMETHING_ELSE"))


# ── ArtifactReference ────────────────────────────────────────────────────────

def test_valid_artifact_passes():
    schemas.validate_artifact_reference(_valid_artifact())


def test_artifact_negative_size_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="size_bytes"):
        schemas.validate_artifact_reference(_valid_artifact(size_bytes=-1))


def test_artifact_invalid_classification_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="valor invalido"):
        schemas.validate_artifact_reference(_valid_artifact(classification="UNKNOWN"))


def test_artifact_invalid_created_at_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="iso8601"):
        schemas.validate_artifact_reference(_valid_artifact(created_at="not-a-date"))


def test_artifact_unexpected_property_rejected():
    bad = _valid_artifact()
    bad["extra"] = "x"
    with pytest.raises(schemas.SchemaValidationError, match="propiedades inesperadas"):
        schemas.validate_artifact_reference(bad)


# ── RemediationChange ────────────────────────────────────────────────────────

def test_valid_change_passes():
    schemas.validate_remediation_change(_valid_change())


def test_change_empty_citations_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="citations"):
        schemas.validate_remediation_change(_valid_change(citations=[]))


def test_change_applied_to_draft_without_valid_citation_rejected():
    """Ajuste #4: un cambio sin cita regulatoria valida no puede quedar
    APPLIED_TO_DRAFT como cambio soportado."""
    with pytest.raises(schemas.SchemaValidationError):
        schemas.validate_remediation_change(_valid_change(
            citations=[], candidate_application_status="APPLIED_TO_DRAFT"))


def test_change_invalid_citation_inside_change_rejected():
    bad_citation = _valid_citation()
    bad_citation["regulatory_catalog_entry_id"] = "NO_EXISTE"
    with pytest.raises(schemas.SchemaValidationError, match="no existe en el catalogo"):
        schemas.validate_remediation_change(_valid_change(citations=[bad_citation]))


def test_change_invalid_enum_rejected():
    with pytest.raises(schemas.SchemaValidationError, match="valor invalido"):
        schemas.validate_remediation_change(_valid_change(change_risk="EXTREME_RISK"))


def test_change_unexpected_property_rejected():
    bad = _valid_change()
    bad["campo_no_declarado"] = "x"
    with pytest.raises(schemas.SchemaValidationError, match="propiedades inesperadas"):
        schemas.validate_remediation_change(bad)


def test_change_missing_original_content_key_rejected():
    bad = _valid_change()
    del bad["original_content"]
    with pytest.raises(schemas.SchemaValidationError, match="original_content"):
        schemas.validate_remediation_change(bad)
