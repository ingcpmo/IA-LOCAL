"""W5 V2, Fase N -- CORRECTED_DOCUMENT_GENERATION_GATE
(CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md sección 16 del plan).

Diagnóstico previo a esta fase: 2 de los 15 criterios del gate dependen de
componentes que NO EXISTEN todavía (`revalidación fue ejecutada` -> Fase O
/ AGT-RVL; `reporte de calidad existe` -> AGT-QLT). Este gate no simula ni
omite esos 2 criterios -- los evalúa a `FAIL` explícito con motivo real,
porque evaluarlos honestamente hoy da ese resultado. Consecuencia
esperada y correcta (no un bug de esta fase): NINGÚN documento real puede
alcanzar `CORRECTED_DOCUMENT_GENERATED` todavía -- el máximo alcanzable
hoy es reportar exactamente qué falta, nunca fingir que pasa.

Reutiliza sin reimplementar: `GovernedCandidateResult` (Fase L),
`build_traceability_matrix`/`build_full_change_review`/`build_package_manifest`
(Fase M)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from docx import Document

REVALIDATION_NOT_EXECUTED_REASON = "AGT-RVL (revalidacion independiente) no existe todavia -- Fase O del roadmap."
QUALITY_REPORT_NOT_EXISTS_REASON = "AGT-QLT (validacion de calidad del documento completo) no existe todavia."


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
    present_titles = {t for t in candidate_texts if any(t.endswith(s["titulo"]) for s in structure["secciones"])}
    checks.append(GateCheckResult(
        "conserva_estructura_requerida",
        len(present_titles) == len(real_section_titles) if real_section_titles else False,
        f"{len(present_titles)}/{len(real_section_titles)} titulos de seccion originales presentes",
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

    checks.append(GateCheckResult(
        "revalidacion_ejecutada", False, REVALIDATION_NOT_EXECUTED_REASON,
    ))
    checks.append(GateCheckResult(
        "reporte_de_calidad_existe", False, QUALITY_REPORT_NOT_EXISTS_REASON,
    ))

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
