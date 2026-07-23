"""W5 V2, Fase L -- generación del documento candidato completo
(CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md).

Diagnóstico previo a esta fase: `candidate_document_generator.py` (Fase J)
ya genera DOCX candidato+redline reales, y
`remediation_change_application_resolver.select_changes_for_clean_candidate()`
(Fase K) ya filtra los cambios seguros para incluir -- pero NADA los
conectaba entre sí. `generate_candidate_document()`/`generate_redline_document()`
aceptan cualquier lista de `changes` sin filtrar; un llamador descuidado
podía (y puede, hoy, sin este módulo) pasarles cambios `PROPOSED_NOT_APPLIED`/
`EXCEPTION_REQUIRED`/`REJECTED_BY_VALIDATOR` y estos se insertarían
igual -- exactamente la violación que el plan prohíbe ("jamás se
incorporan silenciosamente").

Este módulo es el único punto de entrada gobernado: siempre filtra por
`select_changes_for_clean_candidate()` antes de generar, y siempre exige
la estructura real del documento (Fase 4, `document_structure_extractor.py`)
en vez de aceptar cualquier `structure` sin procedencia."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document

from factory.regulatory.document_structure_extractor import extract_structure_from_pdf
from factory.services.candidate_document_generator import (
    generate_candidate_document, generate_redline_document,
)
from factory.services.remediation_change_application_resolver import (
    resolve_package_changes, select_changes_for_clean_candidate,
)


@dataclass(frozen=True)
class GovernedCandidateResult:
    candidate_document: Document
    redline_document: Document
    insertion_manifest: list[dict]
    included_change_ids: list[str]
    excluded_change_ids: list[str]
    exclusion_reasons: dict[str, str]


def generate_governed_candidate(structure: dict, package_state: dict) -> GovernedCandidateResult:
    """Punto de entrada único: resuelve el estado de aplicación real de
    CADA cambio del paquete (Fase K), genera candidato+redline SOLO con
    los cambios AUTO_APPLIED_TO_DRAFT (Fase J), y reporta explícitamente
    qué quedó excluido y por qué -- nunca una lista muda de cambios
    aplicados sin contexto de los que no lo fueron."""
    all_changes = list(package_state["changes"].values())
    resolutions = resolve_package_changes(package_state)
    resolutions_by_id = {r.change_id: r for r in resolutions}

    included_changes = select_changes_for_clean_candidate(all_changes, package_state)
    included_ids = [c["change_id"] for c in included_changes]
    excluded_ids = [cid for cid in resolutions_by_id if cid not in included_ids]
    exclusion_reasons = {
        cid: f"{resolutions_by_id[cid].final_status}: {resolutions_by_id[cid].reason}"
        for cid in excluded_ids
    }

    candidate_doc = generate_candidate_document(structure, included_changes)
    redline_doc, insertion_manifest = generate_redline_document(structure, included_changes)

    return GovernedCandidateResult(
        candidate_document=candidate_doc,
        redline_document=redline_doc,
        insertion_manifest=insertion_manifest,
        included_change_ids=included_ids,
        excluded_change_ids=excluded_ids,
        exclusion_reasons=exclusion_reasons,
    )


def generate_governed_candidate_from_pdf(pdf_path: Path, package_state: dict) -> GovernedCandidateResult:
    """Conveniencia real end-to-end: extrae la estructura directamente de
    un PDF real (Fase 4, solo lectura, el original nunca se toca) y genera
    el candidato gobernado. Reutiliza decide_generation_strategy (Fase J)
    implícitamente al exigir que el llamador ya haya confirmado
    generation_ready=True para este archivo antes de invocar esto -- este
    módulo no vuelve a verificar extraction_capability/processing_state,
    esa es responsabilidad de la capa que lo invoca (mismo principio de
    responsabilidad única que separa AGT-INV de AGT-DOC)."""
    structure = extract_structure_from_pdf(pdf_path)
    return generate_governed_candidate(structure, package_state)
