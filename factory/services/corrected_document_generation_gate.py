"""W5 V2, Fase N -- CORRECTED_DOCUMENT_GENERATION_GATE
(CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md sección 16 del plan).

Diagnóstico previo a esta fase: 2 de los 15 criterios del gate dependían de
componentes que NO EXISTÍAN (`revalidación fue ejecutada` -> Fase O /
AGT-RVL; `reporte de calidad existe` -> AGT-QLT). Ambos ya se construyeron
(`independent_candidate_revalidation.revalidate_document`,
`document_quality_gate.evaluate_document_quality`) y este gate los
consume vía sendos parámetros opcionales `revalidation_result`/
`quality_report`: si no se proveen, preserva el comportamiento honesto
anterior (`FAIL`, el caller no ejecutó/generó el artefacto para este
documento); si se proveen, el criterio pasa únicamente si el resultado
real lo confirma -- nunca se asume revalidación/calidad sin el artefacto
real.

Reutiliza sin reimplementar: `GovernedCandidateResult` (Fase L),
`build_traceability_matrix`/`build_full_change_review`/`build_package_manifest`
(Fase M), `document_quality_gate.evaluate_document_quality` (AGT-QLT),
`independent_candidate_revalidation.revalidate_document` (AGT-RVL,
Fase O)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from docx import Document

from factory.services.independent_candidate_revalidation import DocumentRevalidationResult

REVALIDATION_NOT_PROVIDED_REASON = (
    "no se proveyo un revalidation_result para este documento -- invocar "
    "independent_candidate_revalidation.revalidate_document() y pasarlo aqui."
)
QUALITY_REPORT_NOT_PROVIDED_REASON = (
    "no se proveyo un quality_report para este documento -- invocar "
    "document_quality_gate.evaluate_document_quality() y pasarlo aqui."
)


@dataclass(frozen=True)
class GateCheckResult:
    criterion: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class CorrectedDocumentGenerationGateResult:
    checks: list[GateCheckResult]
    final_state: str

    @property
    def gate_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_criteria(self) -> list[str]:
        return [c.criterion for c in self.checks if not c.passed]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _document_paragraph_texts(doc: Document) -> list[str]:
    return [p.text for p in doc.paragraphs]


def _is_heading_for(parrafo: str, titulo: str) -> bool:
    """True si `parrafo` es el ENCABEZADO de la seccion `titulo` en el
    candidato generado, que lo renderiza como "<numero> <titulo>".

    Defecto real corregido el 2026-07-28, encontrado la primera vez que la
    cadena L->M->QLT->O->N se ejecuto entera sobre un documento real
    (FS_v1.2, paquete PKG-FS-V1-2-REAL-CONTROLLED):

      present_titles = {t for t in candidate_texts if any(t.endswith(...))}
      len(present_titles) == len(real_section_titles)

    comparaba un conteo de PARRAFOS del candidato contra un conteo de
    SECCIONES. Sobre el documento real dio 14 vs 8 y el criterio fallo con
    las 8 secciones intactas. Las 6 coincidencias de mas eran parrafos de
    cuerpo que terminaban por casualidad en un titulo corto ("F09.00:
    Physical Security" termina en "Security"; una linea que acaba en "Data"
    tambien colaba).

    El mismo `endswith` suelto podia producir el error contrario y mas
    grave: dar por presente una seccion AUSENTE porque algun parrafo de
    cuerpo terminaba con su titulo. De ahi que aqui se exija igualdad exacta
    o el prefijo de numeracion, y que la cobertura se mida sobre el conjunto
    de secciones, no sobre el de parrafos."""
    limpio = parrafo.strip()
    if limpio == titulo:
        return True
    return bool(re.match(rf"^\d+(\.\d+)*\s+{re.escape(titulo)}$", limpio))


def evaluate_corrected_document_generation_gate(
    *,
    candidate_document: Document,
    redline_document: Document,
    structure: dict,
    original_document_sha256: str,
    candidate_document_bytes: bytes,
    included_change_ids: list[str],
    traceability_matrix_change_ids: list[str],
    insertion_manifest: list[dict],
    manifest: dict,
    required_manifest_artifacts: list[str],
    change_review: list[dict],
    quality_report: dict | None = None,
    revalidation_result: DocumentRevalidationResult | None = None,
) -> CorrectedDocumentGenerationGateResult:
    """Evalúa TODOS los criterios del plan (sección 16), sin detenerse en
    el primer fallo -- el caller necesita ver la lista completa de lo que
    falta, no solo el primer motivo."""
    checks: list[GateCheckResult] = []

    candidate_texts = _document_paragraph_texts(candidate_document)
    checks.append(GateCheckResult(
        "candidato_existe", candidate_document is not None, "objeto Document presente",
    ))
    checks.append(GateCheckResult(
        "candidato_puede_abrirse", True,
        "objeto Document ya cargado en memoria (verificacion real de reapertura desde disco "
        "vive en candidate_document_generator.verify_document_conformance, Fase J)",
    ))
    checks.append(GateCheckResult(
        "candidato_no_vacio", len(candidate_texts) > 1,
        f"{len(candidate_texts)} parrafos (incluye titulo/warning)",
    ))

    real_section_titles = {s["titulo"] for s in structure["secciones"]}
    covered_titles = {t for t in real_section_titles
                      if any(_is_heading_for(parrafo, t) for parrafo in candidate_texts)}
    missing_titles = sorted(real_section_titles - covered_titles)
    checks.append(GateCheckResult(
        "conserva_estructura_requerida",
        bool(real_section_titles) and not missing_titles,
        f"{len(covered_titles)}/{len(real_section_titles)} secciones originales presentes"
        + (f"; faltan: {', '.join(missing_titles)}" if missing_titles else ""),
    ))
    checks.append(GateCheckResult(
        "no_truncado",
        all(any(parrafo in candidate_texts for parrafo in s["parrafos"]) for s in structure["secciones"]),
        "cada parrafo original de cada seccion sigue presente en el candidato",
    ))

    candidate_sha256 = _sha256_bytes(candidate_document_bytes)
    checks.append(GateCheckResult(
        "sha256_nuevo", candidate_sha256 != original_document_sha256,
        f"candidato={candidate_sha256[:12]}... vs original={original_document_sha256[:12]}...",
    ))
    checks.append(GateCheckResult(
        "tiene_version_nueva", True,
        "el candidato es un documento nuevo generado, distinto por construccion del original inmutable",
    ))
    checks.append(GateCheckResult(
        "original_intacto", True,
        "este gate nunca escribe sobre el original -- solo lee bytes ya extraidos previamente (Fase A/4)",
    ))

    checks.append(GateCheckResult(
        "todos_los_change_id_en_matriz",
        set(included_change_ids).issubset(set(traceability_matrix_change_ids)),
        f"{len(included_change_ids)} change_id incluidos, {len(traceability_matrix_change_ids)} en la matriz",
    ))

    manifest_change_ids = {m["change_id"] for m in insertion_manifest}
    checks.append(GateCheckResult(
        "redline_coincide_con_candidato",
        manifest_change_ids == set(included_change_ids),
        f"insertion_manifest cubre {sorted(manifest_change_ids)}, candidato incluye {sorted(included_change_ids)}",
    ))

    manifest_artifacts_present = set(manifest.get("artifact_hashes", {}).keys())
    missing_artifacts = set(required_manifest_artifacts) - manifest_artifacts_present
    checks.append(GateCheckResult(
        "manifest_incluye_todos_los_artefactos",
        not missing_artifacts,
        f"faltantes: {sorted(missing_artifacts)}" if missing_artifacts else "todos los artefactos requeridos presentes",
    ))

    review_change_ids = {r["change_id"] for r in change_review}
    checks.append(GateCheckResult(
        "resena_completa",
        set(insertion_manifest and manifest_change_ids or included_change_ids).issubset(review_change_ids),
        f"resena cubre {sorted(review_change_ids)}",
    ))

    if revalidation_result is None:
        checks.append(GateCheckResult(
            "revalidacion_ejecutada", False, REVALIDATION_NOT_PROVIDED_REASON,
        ))
    else:
        revalidation_passed = bool(revalidation_result.revalidation_passed)
        if revalidation_passed:
            detail = (
                "AGT-RVL (independent_candidate_revalidation.revalidate_document) -- "
                f"{len(revalidation_result.gap_results)} gap(s) revisados, todos CLOSED, "
                "sin gaps nuevos, artefactos consistentes, hashes validos, documento abre"
            )
        else:
            open_or_partial = [
                f"{r.change_id}:{r.gap_status}" for r in revalidation_result.gap_results
                if r.gap_status != "CLOSED"
            ]
            reasons = []
            if open_or_partial:
                reasons.append(f"gaps no CLOSED: {open_or_partial}")
            if revalidation_result.new_gaps_introduced:
                reasons.append(f"gaps nuevos introducidos: {revalidation_result.new_gaps_introduced}")
            if not revalidation_result.artifacts_consistent:
                reasons.append("artefactos (redline/matriz/manifest) inconsistentes")
            if not revalidation_result.all_hashes_valid:
                reasons.append("algun hash del manifest no tiene formato sha256 valido")
            if not revalidation_result.document_opens_correctly:
                reasons.append("el documento candidato no abre correctamente")
            detail = "AGT-RVL FAIL -- " + "; ".join(reasons)
        checks.append(GateCheckResult("revalidacion_ejecutada", revalidation_passed, detail))

    if quality_report is None:
        checks.append(GateCheckResult(
            "reporte_de_calidad_existe", False, QUALITY_REPORT_NOT_PROVIDED_REASON,
        ))
    else:
        quality_passed = bool(quality_report.get("applied"))
        if quality_passed:
            detail = "AGT-QLT (document_quality_gate.evaluate_document_quality) -- todos los controles evaluables en PASS"
        else:
            detail = (
                f"AGT-QLT FAIL -- controles de documento fallidos: {quality_report.get('failed_document_wide_controls', [])}, "
                f"cambios fallidos: {quality_report.get('failed_change_ids', [])}"
            )
        checks.append(GateCheckResult("reporte_de_calidad_existe", quality_passed, detail))

    all_pass = all(c.passed for c in checks)
    non_revalidation_quality_checks = [
        c for c in checks if c.criterion not in ("revalidacion_ejecutada", "reporte_de_calidad_existe")
    ]
    core_pass = all(c.passed for c in non_revalidation_quality_checks)

    if all_pass:
        final_state = "CORRECTED_DOCUMENT_GENERATED"
    elif core_pass:
        final_state = "DOCUMENT_GENERATION_PARTIAL"
    else:
        final_state = "DOCUMENT_PACKAGE_INCOMPLETE"

    return CorrectedDocumentGenerationGateResult(checks=checks, final_state=final_state)
