"""Orquestador L -> M -> AGT-QLT -> O -> N -> paquete QA.

Por qué existe (auditoría maestra de cierre de W5 V2, 2026-07-28): las Fases
L, M, N y O estaban implementadas, probadas y **sin un solo llamador de
producción**. Búsqueda exhaustiva sobre `factory/`, `scripts/` y los
workspaces gitignorados: `generate_governed_candidate()`,
`evaluate_corrected_document_generation_gate()`, `revalidate_document()` y
`evaluate_document_quality()` solo aparecían en su propio módulo y en sus
tests. Nada las encadenaba, así que los 9 artefactos del
PROFESSIONAL_DOCUMENT_PACKAGE_SPEC nunca se habían generado juntos y
consistentes, y diez de los treinta y un gates de la sección 22 del plan no
eran ni siquiera evaluables.

Este módulo es ese eslabón, y nada más: no reimplementa ninguna fase, las
llama en el orden en que sus dependencias reales lo permiten.

Orden y por qué es ese y no otro:

  1. L  candidato + redline + insertion_manifest
  2. M  matriz de trazabilidad (necesita insertion_manifest para la sección)
  3. M  manifest con hashes reales de los artefactos ya serializados
  4.    AGT-QLT sobre el texto completo del candidato
  5. O  revalidación independiente -- necesita los hashes del manifest y los
        change_id de la matriz, por eso va DESPUÉS de 2 y 3
  6. M  reseña de cambios, ahora sí con el veredicto real de revalidación
        (sin este orden, cada reseña declararía REVALIDATION_NOT_EXECUTED)
  7. M  manifest final, que ya incluye la reseña entre sus artefactos
  8. N  gate de generación, con quality_report y revalidation_result reales
  9.    ensamblado del paquete QA (la DECISIÓN sigue siendo humana, Fase P)

La revalidación es independiente por construcción: recibe artefactos, nunca
las conclusiones de AGT-REM. Este orquestador no le pasa ni una resolución.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from factory.services.corrected_document_generation_gate import (
    evaluate_corrected_document_generation_gate,
)
from factory.services.document_quality_gate import evaluate_document_quality
from factory.services.governed_candidate_document_pipeline import (
    generate_governed_candidate,
    generate_governed_candidate_from_pdf,
)
from factory.services.independent_candidate_revalidation import revalidate_document
from factory.services.remediation_traceability_and_manifest import (
    build_full_change_review,
    build_package_manifest,
    build_traceability_matrix,
)

# Los 9 artefactos del PROFESSIONAL_DOCUMENT_PACKAGE_SPEC. El nombre es el
# que va al manifest, así que es contrato: no se renombra a la ligera.
ARTIFACT_CANDIDATE = "candidate_document.docx"
ARTIFACT_REDLINE = "redline_document.docx"
ARTIFACT_FINDINGS = "findings_report.json"
ARTIFACT_MATRIX = "traceability_matrix.json"
ARTIFACT_REVIEW = "change_review.json"
ARTIFACT_EXCEPTIONS = "exception_package.json"
ARTIFACT_MANIFEST = "manifest.json"
ARTIFACT_REVALIDATION = "revalidation_report.json"
ARTIFACT_QUALITY = "quality_report.json"

REQUIRED_MANIFEST_ARTIFACTS = [
    ARTIFACT_CANDIDATE, ARTIFACT_REDLINE, ARTIFACT_FINDINGS, ARTIFACT_MATRIX,
    ARTIFACT_REVIEW, ARTIFACT_EXCEPTIONS, ARTIFACT_REVALIDATION, ARTIFACT_QUALITY,
]


@dataclass
class DocumentPackageResult:
    run_id: str
    package_id: str
    package_version: int
    generated_at: str
    included_change_ids: list[str]
    excluded_change_ids: list[str]
    exclusion_reasons: dict[str, str]
    traceability_matrix: list[dict]
    change_review: list[dict]
    exception_package: list[dict]
    quality_report: dict
    revalidation_report: dict
    manifest: dict
    gate_result: object
    artifacts: dict = field(default_factory=dict)   # nombre -> bytes
    qa_package_ready: bool = False
    blocking_reasons: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        """Vista sin bytes, apta para log o JSON."""
        return {
            "run_id": self.run_id,
            "package_id": self.package_id,
            "package_version": self.package_version,
            "generated_at": self.generated_at,
            "included_change_ids": self.included_change_ids,
            "excluded_change_ids": self.excluded_change_ids,
            "exclusion_reasons": self.exclusion_reasons,
            "artifacts": sorted(self.artifacts),
            "artifact_count": len(self.artifacts),
            "manifest_fingerprint": self.manifest.get("fingerprint"),
            "manifest_fingerprint_complete": self.manifest.get("fingerprint_complete"),
            "quality_applied": self.quality_report.get("applied"),
            "revalidation_passed": self.revalidation_report.get("revalidation_passed"),
            "gate_status": getattr(self.gate_result, "final_state", None),
            "gate_passed": getattr(self.gate_result, "gate_passed", None),
            "gate_failed_criteria": list(getattr(self.gate_result, "failed_criteria", []) or []),
            "qa_package_ready": self.qa_package_ready,
            "blocking_reasons": self.blocking_reasons,
        }


def _docx_bytes(document: Document) -> bytes:
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _json_bytes(payload) -> bytes:
    import json
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _candidate_full_text(document: Document) -> str:
    return "\n".join(p.text for p in document.paragraphs)


def _as_dict(obj):
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")}


def _exception_package(package_state: dict, exclusion_reasons: dict[str, str]) -> list[dict]:
    """Artefacto 6: TODA excepción del paquete más todo cambio excluido del
    candidato limpio. Gate 21 de la sección 22 exige que ninguna excepción
    quede fuera del paquete QA, así que se construye desde el estado real,
    no desde una lista curada a mano."""
    entradas = []
    # El estado real usa `exceptions` como dict {exception_id: excepcion}
    # (verificado contra PKG-FS-V1-2-REAL-CONTROLLED). Se acepta tambien la
    # forma de lista y el nombre historico `exception_reviews` -- leer solo
    # uno dejaria excepciones reales FUERA del paquete QA, que es justo lo
    # que el gate 21 prohibe.
    for clave in ("exceptions", "exception_reviews"):
        bloque = package_state.get(clave)
        if not bloque:
            continue
        items = bloque.values() if isinstance(bloque, dict) else bloque
        for excepcion in items:
            entradas.append({"tipo": "exception_review", **_as_dict(excepcion)})
    for change_id, motivo in sorted(exclusion_reasons.items()):
        entradas.append({
            "tipo": "change_excluido_del_candidato",
            "change_id": change_id,
            "motivo": motivo,
        })
    return entradas


def build_document_package(
    *,
    structure: dict,
    package_state: dict,
    run_id: str,
    package_id: str,
    package_version: int,
    original_document_sha256: str,
    findings_report: list | dict | None = None,
    run_fingerprint: dict | None = None,
) -> DocumentPackageResult:
    """Genera el paquete completo de 9 artefactos y lo somete al gate.

    NUNCA libera nada: `qa_package_ready` significa "listo para que un humano
    decida", no "aprobado". La decisión sigue viviendo en el endpoint de
    Fase P con `decision_origin=human_confirmed`."""
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes = list(package_state["changes"].values())

    # 1. L -- candidato gobernado
    candidato = generate_governed_candidate(structure, package_state)
    candidate_bytes = _docx_bytes(candidato.candidate_document)
    redline_bytes = _docx_bytes(candidato.redline_document)
    candidate_text = _candidate_full_text(candidato.candidate_document)

    # 2. M -- matriz (sin revalidación todavía: aún no existe)
    matriz = [_as_dict(r) for r in build_traceability_matrix(
        package_state, candidato.insertion_manifest)]

    # 3+4. artefactos base + AGT-QLT
    quality = evaluate_document_quality(
        structure=structure, candidate_full_text=candidate_text, changes=changes)
    excepciones = _exception_package(package_state, candidato.exclusion_reasons)
    findings = findings_report if findings_report is not None else []

    artefactos: dict[str, bytes] = {
        ARTIFACT_CANDIDATE: candidate_bytes,
        ARTIFACT_REDLINE: redline_bytes,
        ARTIFACT_FINDINGS: _json_bytes(findings),
        ARTIFACT_MATRIX: _json_bytes(matriz),
        ARTIFACT_EXCEPTIONS: _json_bytes(excepciones),
        ARTIFACT_QUALITY: _json_bytes(quality),
    }
    manifest_previo = build_package_manifest(
        run_id=run_id, package_id=package_id, package_version=package_version,
        artifacts=artefactos, run_fingerprint=run_fingerprint)

    # 5. O -- revalidación independiente. Recibe artefactos y hashes, jamás
    #    las resoluciones de AGT-REM.
    revalidacion = revalidate_document(
        structure=structure,
        changes=changes,
        included_change_ids=candidato.included_change_ids,
        candidate_document_bytes=candidate_bytes,
        redline_change_ids=[m["change_id"] for m in candidato.insertion_manifest],
        matrix_change_ids=[r["change_id"] for r in matriz],
        manifest_artifact_hashes=manifest_previo["artifact_hashes"],
        required_manifest_artifacts=[a for a in REQUIRED_MANIFEST_ARTIFACTS
                                     if a in manifest_previo["artifact_hashes"]],
    )
    # `revalidation_passed` y `gap_status` son properties: asdict() no las
    # incluye, y el artefacto persistido se quedaria sin el veredicto.
    revalidacion_dict = {
        **_as_dict(revalidacion),
        "revalidation_passed": revalidacion.revalidation_passed,
    }

    # 6. M -- matriz y reseña CON el veredicto real de revalidación
    matriz = [_as_dict(r) for r in build_traceability_matrix(
        package_state, candidato.insertion_manifest, revalidation=revalidacion)]
    resena = build_full_change_review(package_state, revalidation=revalidacion)

    # 7. manifest final sobre los 9 artefactos definitivos
    artefactos[ARTIFACT_MATRIX] = _json_bytes(matriz)
    artefactos[ARTIFACT_REVIEW] = _json_bytes(resena)
    artefactos[ARTIFACT_REVALIDATION] = _json_bytes(revalidacion_dict)
    manifest = build_package_manifest(
        run_id=run_id, package_id=package_id, package_version=package_version,
        artifacts=artefactos, run_fingerprint=run_fingerprint)
    artefactos[ARTIFACT_MANIFEST] = _json_bytes(manifest)

    # 8. N -- gate con quality_report y revalidation_result reales
    gate = evaluate_corrected_document_generation_gate(
        candidate_document=candidato.candidate_document,
        redline_document=candidato.redline_document,
        structure=structure,
        original_document_sha256=original_document_sha256,
        candidate_document_bytes=candidate_bytes,
        included_change_ids=candidato.included_change_ids,
        traceability_matrix_change_ids=[r["change_id"] for r in matriz],
        insertion_manifest=candidato.insertion_manifest,
        manifest=manifest,
        required_manifest_artifacts=REQUIRED_MANIFEST_ARTIFACTS,
        change_review=resena,
        quality_report=quality,
        revalidation_result=revalidacion,
    )

    # 9. ensamblado QA
    bloqueos: list[str] = []
    faltantes = [a for a in REQUIRED_MANIFEST_ARTIFACTS + [ARTIFACT_MANIFEST]
                 if a not in artefactos]
    if faltantes:
        bloqueos.append(f"artefactos faltantes: {', '.join(faltantes)}")
    if getattr(gate, "final_state", None) != "CORRECTED_DOCUMENT_GENERATED":
        bloqueos.append(
            f"gate={getattr(gate, 'final_state', None)}; criterios en rojo: "
            f"{', '.join(getattr(gate, 'failed_criteria', []) or []) or 'ninguno declarado'}")

    return DocumentPackageResult(
        run_id=run_id, package_id=package_id, package_version=package_version,
        generated_at=generated_at,
        included_change_ids=candidato.included_change_ids,
        excluded_change_ids=candidato.excluded_change_ids,
        exclusion_reasons=candidato.exclusion_reasons,
        traceability_matrix=matriz,
        change_review=resena,
        exception_package=excepciones,
        quality_report=quality,
        revalidation_report=revalidacion_dict,
        manifest=manifest,
        gate_result=gate,
        artifacts=artefactos,
        qa_package_ready=not bloqueos,
        blocking_reasons=bloqueos,
    )


def build_document_package_from_pdf(
    *, pdf_path: Path, package_state: dict, run_id: str, package_id: str,
    package_version: int, original_document_sha256: str,
    findings_report: list | dict | None = None,
    run_fingerprint: dict | None = None,
) -> DocumentPackageResult:
    """End-to-end desde un PDF real. El original se abre en SOLO LECTURA;
    nada de esta cadena escribe sobre él."""
    from factory.regulatory.document_structure_extractor import extract_structure_from_pdf

    structure = extract_structure_from_pdf(pdf_path)
    return build_document_package(
        structure=structure, package_state=package_state, run_id=run_id,
        package_id=package_id, package_version=package_version,
        original_document_sha256=original_document_sha256,
        findings_report=findings_report, run_fingerprint=run_fingerprint,
    )


def persist_package(result: DocumentPackageResult, out_dir: Path) -> dict[str, Path]:
    """Escribe los artefactos a disco. Directorio propio del paquete; nunca
    toca el documento original ni artefactos de otra corrida."""
    out_dir.mkdir(parents=True, exist_ok=True)
    escritos = {}
    for nombre, data in result.artifacts.items():
        destino = out_dir / nombre
        destino.write_bytes(data)
        escritos[nombre] = destino
    (out_dir / "package_summary.json").write_bytes(_json_bytes(result.summary()))
    escritos["package_summary.json"] = out_dir / "package_summary.json"
    return escritos
