"""W5 V2, Fase O -- AGT-RVL, revalidación independiente
(CANDIDATE_REVALIDATION_SPEC.md).

Brecha completa confirmada antes de esta fase: no existía ningún código
que comparara `BASELINE_ORIGINAL` vs. `DOCUMENTO_CANDIDATO_COMPLETO` de
forma independiente. Este módulo es la primera implementación real de
AGT-RVL.

Regla dura de independencia (sección 5 del plan): AGT-RVL "nunca comparte
lógica de decisión con AGT-REM ni consume sus conclusiones intermedias;
solo compara artefactos finales contra baseline". Este módulo NUNCA llama
a `resolve_package_changes()`/`ChangeApplicationResolution` (Fase K, la
lógica de decisión de AGT-REM) -- reabre el documento candidato YA
GENERADO (bytes reales, no el objeto en memoria) y verifica desde cero,
con las mismas primitivas de bajo nivel que cualquier agente puede usar
(`semantic_evidence_verification`, Fase F -- una utilidad compartida, no
la lógica de decisión de un agente específico).

Clasificación por gap (sección 17 del plan):
  CLOSED                          -- el cambio está incorporado en el
                                      candidato Y ancla literalmente.
  PARTIALLY_CLOSED                -- el cambio esta parcialmente presente
                                      (ancla con desviacion, fuzzy).
  OPEN                            -- el cambio no fue incorporado (excluido
                                      por Fase K, o nunca se propuso).
  NEW_GAP_INTRODUCED               -- contenido original requerido
                                      desaparecio del candidato.
  IMPLEMENTATION_VERIFICATION_REQUIRED -- NUNCA se asigna automaticamente
                                      aqui: requiere verificar el sistema
                                      fisico, fuera del alcance de
                                      cualquier automatizacion documental
                                      (declarado explicitamente, no
                                      omitido)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from docx import Document

from factory.regulatory.semantic_evidence_verification import verify_anchor

IMPLEMENTATION_VERIFICATION_NOTE = (
    "IMPLEMENTATION_VERIFICATION_REQUIRED nunca se asigna automaticamente -- "
    "requiere verificar el sistema fisico, decision siempre humana."
)


@dataclass(frozen=True)
class GapRevalidationResult:
    change_id: str
    requirement_id: str
    gap_status: str
    detail: str


@dataclass(frozen=True)
class DocumentRevalidationResult:
    gap_results: list[GapRevalidationResult]
    new_gaps_introduced: list[str]
    all_hashes_valid: bool
    document_opens_correctly: bool
    artifacts_consistent: bool

    @property
    def revalidation_passed(self) -> bool:
        return (
            self.all_hashes_valid
            and self.document_opens_correctly
            and self.artifacts_consistent
            and not self.new_gaps_introduced
            and all(r.gap_status == "CLOSED" for r in self.gap_results)
        )


def _candidate_full_text(candidate_document_bytes: bytes) -> str:
    """Reabre el candidato DESDE BYTES (nunca el objeto Document en
    memoria que AGT-REM/Fase J ya produjeron) -- misma disciplina que
    verify_document_conformance de Fase J, pero reimplementada aqui de
    forma independiente, sin llamarla."""
    doc = Document(io.BytesIO(candidate_document_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def revalidate_change(change: dict, candidate_full_text: str, was_included: bool) -> GapRevalidationResult:
    """Verifica UN cambio de forma independiente: no consulta
    candidate_application_status ni ninguna conclusion de Fase K -- solo
    mira si el proposed_content real esta o no en el texto real del
    candidato ya generado."""
    change_id = change["change_id"]
    requirement_id = change["requirement_id"]

    if not was_included:
        return GapRevalidationResult(
            change_id, requirement_id, "OPEN",
            "El cambio no fue incorporado al candidato (excluido por gobernanza de riesgo o nunca aplicado)",
        )

    status, match_type = verify_anchor(change["proposed_content"], candidate_full_text)
    if status == "PASS" and match_type in ("exact", "normalized", "despaced"):
        return GapRevalidationResult(
            change_id, requirement_id, "CLOSED",
            f"proposed_content anclado en el candidato real (match_type={match_type})",
        )
    if status == "PASS" and match_type == "fuzzy":
        return GapRevalidationResult(
            change_id, requirement_id, "PARTIALLY_CLOSED",
            "proposed_content presente con desviacion (CITATION_DEVIATION) -- revision humana recomendada",
        )
    return GapRevalidationResult(
        change_id, requirement_id, "OPEN",
        "El insertion_manifest declara el cambio incluido, pero el texto NO se encuentra en el "
        "candidato reabierto -- posible fallo de serializacion o candidato desincronizado",
    )


def _detect_new_gaps(structure: dict, candidate_full_text: str) -> list[str]:
    """Sin eliminacion de contenido requerido (seccion 17 del plan): cada
    parrafo ORIGINAL de cada seccion debe seguir presente literalmente en
    el candidato reabierto. Retorna la lista de fragmentos originales que
    desaparecieron -- lista vacia si nada se perdio."""
    missing: list[str] = []
    for seccion in structure["secciones"]:
        for parrafo in seccion["parrafos"]:
            status, _match_type = verify_anchor(parrafo, candidate_full_text)
            if status != "PASS":
                missing.append(f"{seccion['numero']} {seccion['titulo']}: {parrafo[:60]!r}")
    return missing


def revalidate_document(
    *,
    structure: dict,
    changes: list[dict],
    included_change_ids: list[str],
    candidate_document_bytes: bytes,
    redline_change_ids: list[str],
    matrix_change_ids: list[str],
    manifest_artifact_hashes: dict[str, str],
    required_manifest_artifacts: list[str],
) -> DocumentRevalidationResult:
    """Revalidación completa e independiente del documento candidato
    contra el original (no se limita a fragmentos modificados: recorre
    TODAS las secciones de la estructura original, no solo las tocadas
    por un cambio)."""
    document_opens_correctly = True
    try:
        candidate_full_text = _candidate_full_text(candidate_document_bytes)
    except Exception:
        document_opens_correctly = False
        candidate_full_text = ""

    included_set = set(included_change_ids)
    gap_results = [
        revalidate_change(change, candidate_full_text, change["change_id"] in included_set)
        for change in changes
    ]

    new_gaps = _detect_new_gaps(structure, candidate_full_text) if document_opens_correctly else ["documento no abre"]

    artifacts_consistent = (
        set(redline_change_ids) == included_set
        and included_set.issubset(set(matrix_change_ids))
        and not (set(required_manifest_artifacts) - set(manifest_artifact_hashes.keys()))
    )

    all_hashes_valid = all(
        isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)
        for h in manifest_artifact_hashes.values()
    )

    return DocumentRevalidationResult(
        gap_results=gap_results,
        new_gaps_introduced=new_gaps,
        all_hashes_valid=all_hashes_valid,
        document_opens_correctly=document_opens_correctly,
        artifacts_consistent=artifacts_consistent,
    )
