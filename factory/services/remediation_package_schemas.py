"""
BATCH_AND_EXCEPTION — validacion formal e independiente de los 3 schemas que
en la primera implementacion quedaron sin validar (o parcialmente validados):
RegulatoryCitationReference, RemediationChange, ArtifactReference.

Validacion manual (sin Pydantic/JSON Schema, mismo estilo que el resto del
modulo) pero completa: campos obligatorios, tipos, enums, formato de hash,
tamanos, y ausencia de propiedades inesperadas (equivalente a
additionalProperties:false). Fail-closed: cualquier desviacion lanza, nunca
se corrige ni se completa un campo faltante en silencio.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from factory.regulatory.regulatory_catalog import RegulatoryCatalogError, known_entry_ids

_SHA256_HEX_LEN = 64


class SchemaValidationError(Exception):
    """Fail-closed: un schema (RegulatoryCitationReference/RemediationChange/
    ArtifactReference) no valida contra su contrato formal."""


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and len(value) == _SHA256_HEX_LEN and all(c in "0123456789abcdef" for c in value)


def _require_no_unexpected_keys(obj: dict, allowed: set[str], schema_name: str) -> None:
    extra = set(obj.keys()) - allowed
    if extra:
        raise SchemaValidationError(f"{schema_name}: propiedades inesperadas no permitidas: {sorted(extra)}")


def _require_field(obj: dict, field: str, expected_type: type, schema_name: str) -> object:
    if field not in obj:
        raise SchemaValidationError(f"{schema_name}: falta el campo obligatorio '{field}'")
    value = obj[field]
    if not isinstance(value, expected_type) or (expected_type is str and value.strip() == ""):
        raise SchemaValidationError(
            f"{schema_name}.{field}: se esperaba {expected_type.__name__} no vacio, se recibio {value!r}")
    return value


def _require_enum(obj: dict, field: str, allowed_values: set[str], schema_name: str) -> str:
    value = _require_field(obj, field, str, schema_name)
    if value not in allowed_values:
        raise SchemaValidationError(f"{schema_name}.{field}: valor invalido {value!r}, esperado uno de {sorted(allowed_values)}")
    return value


def _require_sha256(obj: dict, field: str, schema_name: str) -> str:
    value = _require_field(obj, field, str, schema_name)
    if not _is_sha256_hex(value):
        raise SchemaValidationError(f"{schema_name}.{field}: no es un sha256 hexadecimal valido de {_SHA256_HEX_LEN} caracteres: {value!r}")
    return value


def _require_iso8601(obj: dict, field: str, schema_name: str) -> str:
    value = _require_field(obj, field, str, schema_name)
    try:
        datetime.fromisoformat(value)
    except ValueError as e:
        raise SchemaValidationError(f"{schema_name}.{field}: no es iso8601 valido: {value!r}") from e
    return value


# ── RegulatoryCitationReference ─────────────────────────────────────────────

_DOCUMENT_ROLES = {"SOURCE_DOCUMENT", "CANDIDATE_DOCUMENT"}
_EVIDENCE_TYPES = {"LITERAL_QUOTE", "ABSENCE_CONFIRMATION", "CROSS_REFERENCE"}

_CITATION_REQUIRED_FIELDS = {
    "citation_id", "regulatory_catalog_entry_id", "regulatory_source", "regulatory_source_sha256",
    "requirement_catalog_sha256", "run_id", "record_id", "document_role", "document_sha256",
    "chunk_sha256", "citation_locator", "page_start", "page_end", "literal_text",
    "citation_text_sha256", "evidence_type", "evidence_location",
}


def validate_regulatory_citation_reference(citation: dict) -> None:
    """Valida los 16 campos de RegulatoryCitationReference. Fail-closed:
    regulatory_catalog_entry_id DEBE existir en el catalogo real (ver
    factory/regulatory/regulatory_catalog.py); citation_text_sha256 se
    recalcula desde literal_text (mismo patron que
    requirement_catalog_loader.py -- una discrepancia significa que la cita
    se edito sin recalcular el hash, y se rechaza)."""
    name = "RegulatoryCitationReference"
    _require_no_unexpected_keys(citation, _CITATION_REQUIRED_FIELDS, name)

    entry_id = _require_field(citation, "regulatory_catalog_entry_id", str, name)
    try:
        known = known_entry_ids()
    except RegulatoryCatalogError as e:
        raise SchemaValidationError(f"{name}: catalogo regulatorio no disponible: {e}") from e
    if entry_id not in known:
        raise SchemaValidationError(f"{name}.regulatory_catalog_entry_id: '{entry_id}' no existe en el catalogo real")

    _require_field(citation, "regulatory_source", str, name)
    _require_sha256(citation, "regulatory_source_sha256", name)
    _require_sha256(citation, "requirement_catalog_sha256", name)
    _require_field(citation, "run_id", str, name)
    _require_field(citation, "record_id", str, name)
    _require_enum(citation, "document_role", _DOCUMENT_ROLES, name)
    _require_sha256(citation, "document_sha256", name)
    _require_sha256(citation, "chunk_sha256", name)
    _require_field(citation, "citation_locator", str, name)

    page_start = _require_field(citation, "page_start", int, name)
    page_end = _require_field(citation, "page_end", int, name)
    if page_start < 1 or page_end < page_start:
        raise SchemaValidationError(
            f"{name}: page_start/page_end invalidos (page_start={page_start}, page_end={page_end})")

    literal_text = _require_field(citation, "literal_text", str, name)
    citation_text_sha256 = _require_sha256(citation, "citation_text_sha256", name)
    recomputed = hashlib.sha256(literal_text.encode("utf-8")).hexdigest()
    if recomputed != citation_text_sha256:
        raise SchemaValidationError(
            f"{name}: citation_text_sha256 declarado ({citation_text_sha256}) no coincide con el "
            f"recalculado desde literal_text ({recomputed}) -- la cita pudo editarse sin recalcular el hash")

    _require_enum(citation, "evidence_type", _EVIDENCE_TYPES, name)
    _require_field(citation, "evidence_location", str, name)


# ── ArtifactReference ────────────────────────────────────────────────────────

_ARTIFACT_CLASSIFICATIONS = {"SOURCE_IMMUTABLE", "CANDIDATE_DRAFT", "REPORT", "REDLINE", "MANIFEST"}
_ARTIFACT_REQUIRED_FIELDS = {
    "artifact_id", "storage_location", "mime_type", "sha256", "size_bytes", "classification", "created_at",
}


def validate_artifact_reference(artifact: dict) -> None:
    name = "ArtifactReference"
    _require_no_unexpected_keys(artifact, _ARTIFACT_REQUIRED_FIELDS, name)
    _require_field(artifact, "artifact_id", str, name)
    _require_field(artifact, "storage_location", str, name)
    _require_field(artifact, "mime_type", str, name)
    _require_sha256(artifact, "sha256", name)
    size_bytes = _require_field(artifact, "size_bytes", int, name)
    if size_bytes < 0:
        raise SchemaValidationError(f"{name}.size_bytes: no puede ser negativo ({size_bytes})")
    _require_enum(artifact, "classification", _ARTIFACT_CLASSIFICATIONS, name)
    _require_iso8601(artifact, "created_at", name)


# ── RemediationChange ────────────────────────────────────────────────────────

_CHANGE_TYPES = {"COSMETIC", "CLARIFICATION", "CONTENT_ADDITION", "CONTENT_REPLACEMENT"}
_CHANGE_RISKS = {"LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"}
_EVALUATION_CONFIDENCES = {"HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"}
_SCHEMA_VALIDATION_STATUSES = {"PASSED", "FAILED"}
_CITATION_ANCHOR_STATUSES = {"VERIFIED", "NOT_VERIFIED", "UNDER_REVIEW"}
_RELEVANCE_STATUSES = {"CONFIRMED", "NOT_RELEVANT", "UNDER_REVIEW"}
_APPLICATION_STATUSES = {"APPLIED_TO_DRAFT", "NOT_APPLIED", "APPLICATION_FAILED"}

_CHANGE_REQUIRED_FIELDS = {
    "change_id", "finding_id", "requirement_id", "document_location", "original_content",
    "proposed_content", "change_reason", "change_type", "citations", "change_risk", "change_risk_basis",
    "evaluation_confidence", "evaluation_confidence_basis", "schema_validation_status",
    "citation_anchor_status", "relevance_status", "candidate_application_status", "limitations",
}
# directive_id es OPCIONAL a nivel de forma (muchos consumidores de
# validate_remediation_change -- document_quality_gates.py,
# golden_dataset_criteria.py -- validan RemediationChange sin estar
# atados al flujo de paquetes). remediation_package_service.create_package()
# es quien lo EXIGE como precondicion real (verificacion 2026-08-18,
# hallazgo I de VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md): el punto
# correcto para cerrar el bypass es el unico llamador de produccion que
# persiste un paquete, no este validador de forma generico.
_CHANGE_OPTIONAL_FIELDS = {"directive_id"}
_CHANGE_ALLOWED_FIELDS = _CHANGE_REQUIRED_FIELDS | _CHANGE_OPTIONAL_FIELDS


def validate_remediation_change(change: dict) -> None:
    """Valida forma completa de RemediationChange, incluidas TODAS sus
    RegulatoryCitationReference. Un APPLIED_TO_DRAFT sin al menos una cita
    valida se rechaza aqui (ajuste #4 de esta ronda) -- ver tambien
    validate_change_application_status() en remediation_package_service.py
    para la invariante de schema/anchor."""
    name = "RemediationChange"
    _require_no_unexpected_keys(change, _CHANGE_ALLOWED_FIELDS, name)

    if "directive_id" in change and not (isinstance(change["directive_id"], str) and change["directive_id"].strip()):
        raise SchemaValidationError(f"{name}.directive_id: si se provee, debe ser str no vacio")

    _require_field(change, "change_id", str, name)
    _require_field(change, "finding_id", str, name)
    _require_field(change, "requirement_id", str, name)
    _require_field(change, "document_location", str, name)
    if "original_content" not in change:
        raise SchemaValidationError(f"{name}: falta el campo obligatorio 'original_content' (str o None)")
    if change["original_content"] is not None and not isinstance(change["original_content"], str):
        raise SchemaValidationError(f"{name}.original_content: debe ser str o None")
    _require_field(change, "proposed_content", str, name)
    _require_field(change, "change_reason", str, name)
    _require_enum(change, "change_type", _CHANGE_TYPES, name)

    citations = change.get("citations")
    if not isinstance(citations, list) or not citations:
        raise SchemaValidationError(f"{name}.citations: debe ser una lista no vacia de RegulatoryCitationReference")
    for citation in citations:
        if not isinstance(citation, dict):
            raise SchemaValidationError(f"{name}.citations: cada elemento debe ser un dict")
        validate_regulatory_citation_reference(citation)

    _require_enum(change, "change_risk", _CHANGE_RISKS, name)
    risk_basis = change.get("change_risk_basis")
    if not isinstance(risk_basis, list) or not risk_basis:
        raise SchemaValidationError(f"{name}.change_risk_basis: debe ser una lista no vacia")

    _require_enum(change, "evaluation_confidence", _EVALUATION_CONFIDENCES, name)
    conf_basis = change.get("evaluation_confidence_basis")
    if not isinstance(conf_basis, list) or not conf_basis:
        raise SchemaValidationError(f"{name}.evaluation_confidence_basis: debe ser una lista no vacia")

    _require_enum(change, "schema_validation_status", _SCHEMA_VALIDATION_STATUSES, name)
    _require_enum(change, "citation_anchor_status", _CITATION_ANCHOR_STATUSES, name)
    _require_enum(change, "relevance_status", _RELEVANCE_STATUSES, name)
    _require_enum(change, "candidate_application_status", _APPLICATION_STATUSES, name)

    if "limitations" not in change or not isinstance(change["limitations"], str):
        raise SchemaValidationError(f"{name}.limitations: debe ser str (puede ser cadena vacia)")

    # Ajuste #4: un cambio sin cita regulatoria valida no puede quedar
    # APPLIED_TO_DRAFT como cambio soportado. Las citas ya se validaron
    # arriba (fail-closed): si llegamos aqui todas son validas, asi que solo
    # falta exigir que exista al menos una -- ya lo hace el chequeo de
    # 'citations no vacia' de arriba, pero lo dejamos explicito para que la
    # regla sea legible sin tener que rastrear el chequeo generico.
    if change["candidate_application_status"] == "APPLIED_TO_DRAFT" and not citations:
        raise SchemaValidationError(
            f"{name}: candidate_application_status=APPLIED_TO_DRAFT requiere al menos "
            "una RegulatoryCitationReference valida")
