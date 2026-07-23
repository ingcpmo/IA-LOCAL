"""W5 V2, Fase M -- matriz de trazabilidad, reseña de cambios y manifest
(PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md, artefactos 4/5/7 de 9).

Diagnóstico previo a esta fase: no existía ningún generador de matriz de
trazabilidad, reseña de cambios ni manifest para el pipeline de
remediación (confirmado por búsqueda -- lo único parecido, `dossier_generator_service.py`,
construye el dossier GAMP5 de la propia solución custom de la fábrica, un
objeto completamente distinto). Este módulo construye los 3 artefactos
ÍNTEGRAMENTE desde datos ya reales de fases anteriores, sin inventar
texto: Fase K (`resolve_package_changes`, estado real de aplicación),
Fase L (`insertion_manifest`, ubicación real en el documento generado) y
los campos ya presentes en cada `RemediationChange`/`RegulatoryCitationReference`
(`remediation_package_schemas.py`).

La reseña de cambios (`build_change_narrative`) es ENSAMBLADO
DETERMINISTA de campos ya existentes -- nunca texto generado por LLM. Si
un campo no está disponible (p.ej. revalidación, que es Fase O, todavía no
construida), se declara explícitamente `PENDING_PHASE_O`, nunca se omite
en silencio ni se inventa un valor."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from factory.services.remediation_change_application_resolver import resolve_package_changes

REVALIDATION_STATUS = "PENDING_PHASE_O"
REVALIDATION_REASON = "AGT-RVL (revalidacion independiente) no existe todavia -- Fase O del roadmap."


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_official_url(source_id: str) -> str:
    """Resuelve la URL oficial real desde el catalogo de fuentes
    gobernadas (Fase B). Si el source_id no resuelve, declara
    explicitamente 'NO_RESOLVIBLE' -- nunca inventa una URL."""
    try:
        from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
            CatalogValidationError, get_source,
        )
        source = get_source(source_id)
        return source.get("official_source_url", "NO_DISPONIBLE")
    except (CatalogValidationError, ImportError):
        return "NO_RESOLVIBLE (source_id no encontrado en el catalogo gobernado)"


@dataclass(frozen=True)
class TraceabilityRow:
    requirement_id: str
    change_id: str
    final_status: str
    included_in_clean_candidate: bool
    section_numero: str | None
    citation_ids: list[str]
    revalidation_status: str = REVALIDATION_STATUS


def build_traceability_matrix(
    package_state: dict, insertion_manifest: list[dict] | None = None
) -> list[TraceabilityRow]:
    """requirement_id -> evidencia (citation_ids) -> ... -> change_id ->
    seccion -> revalidacion (PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md
    seccion 2). 'hallazgo'/'gap-desviacion' del diseño original viven en
    el finding pre-mapeo (gap_assessment_finding_mapper.py), no en el
    RemediationChange -- fuera del alcance de esta matriz, que traza
    desde el change_id ya mapeado en adelante."""
    section_by_change_id = {
        m["change_id"]: m["section_numero"] for m in (insertion_manifest or [])
    }
    resolutions = resolve_package_changes(package_state)
    rows = []
    for resolution in resolutions:
        change = package_state["changes"][resolution.change_id]
        rows.append(TraceabilityRow(
            requirement_id=change["requirement_id"],
            change_id=resolution.change_id,
            final_status=resolution.final_status,
            included_in_clean_candidate=resolution.included_in_clean_candidate,
            section_numero=section_by_change_id.get(resolution.change_id),
            citation_ids=[c["citation_id"] for c in change["citations"]],
        ))
    return rows


def build_change_narrative(change: dict, resolution_reason: str) -> dict:
    """Reseña de un cambio real (PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md
    seccion 3): ensamblado determinista de campos ya presentes en el
    RemediationChange, sin generar texto nuevo. Narrativa obligatoria:
    que estaba incompleto -> por que era insuficiente -> que se modifico
    -> como atiende el requisito -> fuente oficial -> que queda
    pendiente."""
    primary_citation = change["citations"][0] if change["citations"] else None
    official_url = _resolve_official_url(primary_citation["regulatory_source"]) if primary_citation else "N/A"
    return {
        "change_id": change["change_id"],
        "requirement_id": change["requirement_id"],
        "document_location": change["document_location"],
        "contenido_anterior": change["original_content"],
        "contenido_nuevo": change["proposed_content"],
        "motivo": change["change_reason"],
        "regulacion_fuente_id": primary_citation["regulatory_source"] if primary_citation else None,
        "numeral": primary_citation.get("citation_locator") if primary_citation else None,
        "cita": primary_citation.get("literal_text") if primary_citation else None,
        "url_oficial": official_url,
        "evidencia": primary_citation.get("evidence_location") if primary_citation else None,
        "estado_aplicacion": resolution_reason,
        "resultado_revalidacion": REVALIDATION_STATUS,
        "implementacion_pendiente": (
            "Este cambio corrige documentacion, no implica que la capacidad descrita ya "
            "este verificada como implementada en el sistema fisico -- esa verificacion "
            "(IMPLEMENTATION_VERIFICATION) permanece siempre fuera de este sistema."
        ),
        "narrativa": (
            f"Incompleto: {change['change_reason']}. "
            f"Se modifico: se {'agrego' if change['change_type'] == 'CONTENT_ADDITION' else 'reemplazo'} "
            f"contenido en {change['document_location']}. "
            f"Fundamento regulatorio: {primary_citation['regulatory_source'] if primary_citation else 'N/A'} "
            f"({primary_citation.get('citation_locator', 'N/A') if primary_citation else 'N/A'}). "
            f"Fuente oficial: {official_url}. "
            f"Pendiente: revalidacion independiente ({REVALIDATION_STATUS})."
        ),
    }


def build_full_change_review(package_state: dict) -> list[dict]:
    resolutions = {r.change_id: r for r in resolve_package_changes(package_state)}
    return [
        build_change_narrative(change, f"{resolutions[change_id].final_status}: {resolutions[change_id].reason}")
        for change_id, change in package_state["changes"].items()
    ]


def build_package_manifest(
    *, run_id: str, package_id: str, package_version: int,
    artifacts: dict[str, bytes],
) -> dict:
    """MANIFEST (artefacto 7 de 9): SHA-256 real de cada artefacto
    provisto + run_id + fingerprint. El fingerprint aqui cubre SOLO los
    componentes disponibles en esta fase (artefactos generados +
    identidad del paquete) -- el fingerprint COMPLETO de corrida
    (modelo+digest, prompt_version, schema_version, catalogo+matriz de
    aplicabilidad con hash, ver PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md
    seccion 5) no esta completamente cableado todavia en ningun runner
    real -- se declara explicitamente que campos faltan, en vez de
    fabricar un fingerprint incompleto disfrazado de completo."""
    artifact_hashes = {name: _sha256_bytes(data) for name, data in artifacts.items()}
    fingerprint_basis = {
        "package_id": package_id, "package_version": package_version,
        "run_id": run_id, "artifact_hashes": artifact_hashes,
    }
    fingerprint = _sha256_bytes(
        json.dumps(fingerprint_basis, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    return {
        "run_id": run_id, "package_id": package_id, "package_version": package_version,
        "artifact_hashes": artifact_hashes,
        "fingerprint": fingerprint,
        "fingerprint_covers": ["package_id", "package_version", "run_id", "artifact_hashes"],
        "fingerprint_missing_components": [
            "model_digest", "prompt_version", "schema_version", "catalog_version_hash",
            "applicability_matrix_version_hash", "agent_versions",
        ],
        "fingerprint_complete": False,
    }
