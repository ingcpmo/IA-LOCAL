"""W5 V2, Fase J -- decisión determinista de estrategia de generación de
documento corregido por formato (CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md,
sección 14 del plan de instrucciones).

Diagnóstico previo a esta fase: `factory/services/candidate_document_generator.py`
YA implementa el caso DOCX (candidato limpio + redline + verificación
DOCUMENT_CONFORMANCE), con 3 cambios reales en producción (COR-1/COR-2/
COR-5). Este módulo NO reimplementa eso -- solo agrega la capa de DECISIÓN
que falta: dado un archivo real del allowlist de Fase A
(source_baseline_allowlist.yaml), qué estrategia de generación aplica,
consumiendo `extraction_capability`/`processing_state`/`extension` reales
en vez de asumir que todo documento es generable.

Regla dura (igual que `_validate_change_type` en candidate_document_generator.py
para CONTENT_REPLACEMENT): una estrategia sin caso real que la ejercite
declara NOT_IMPLEMENTED explícito, nunca un generador fabricado sin
validación. Hoy (2026-07-23) XLSX y DOCM no tienen ningún finding/cambio
real que los ejercite -- se declaran NOT_IMPLEMENTED, no se construye un
generador especulativo."""
from __future__ import annotations

from dataclasses import dataclass

# Estados de processing_state (Fase A) que indican un documento NO elegible
# para generación todavía -- requieren resolución humana o no son la copia
# canónica, independientemente de su formato/extraction_capability.
_NOT_YET_ELIGIBLE_STATES = {
    "DUPLICATE", "HUMAN_REVIEW_REQUIRED", "ORIGINAL_SOURCE_UNCONFIRMED",
    "PROCESSING_BLOCKED", "DERIVED_DOCUMENT_EXCLUDED",
}

_IMPLEMENTED_STRATEGIES = {
    "PDF_RECONSTRUCTED_DOCX_AND_PDF",
    "DOCX_CANDIDATE_AND_PDF",  # mismo candidate_document_generator.py que la anterior (fix: faltaba, hallazgo real de esta sesion)
    "XLSX_CANDIDATE_CELL_LEVEL",  # xlsx_candidate_generator.py, generador real construido y probado
    "DOCM_CANDIDATE_SAFE_EXTRACTION",  # docm_candidate_generator.py, generador real construido y probado
}


@dataclass(frozen=True)
class GenerationStrategyDecision:
    file_id: str
    strategy: str
    generation_ready: bool
    reason: str


def decide_generation_strategy(entry: dict) -> GenerationStrategyDecision:
    """entry: una entrada real del allowlist de Fase A (dict con file_id,
    extension, extraction_capability, processing_state). Nunca lanza --
    toda combinación produce una decisión explícita, incluso las
    bloqueadas/no implementadas (fail-visible, no fail-silent)."""
    file_id = entry["file_id"]
    ext = entry["extension"].lower()
    capability = entry["extraction_capability"]
    state = entry["processing_state"]

    if state in _NOT_YET_ELIGIBLE_STATES:
        return GenerationStrategyDecision(
            file_id, "NOT_ELIGIBLE_YET", generation_ready=False,
            reason=f"processing_state={state!r} -- no es la copia canonica elegible o requiere resolucion humana previa",
        )

    if capability in ("OCR_REQUIRED", "NOT_EXTRACTABLE"):
        return GenerationStrategyDecision(
            file_id, "GENERATION_BLOCKED_INSUFFICIENT_FIDELITY", generation_ready=False,
            reason=(
                f"extraction_capability={capability!r} -- el contenido no puede reconstruirse "
                "con confiabilidad suficiente (regla del plan: bloquear en vez de generar un "
                "candidato con perdida de fidelidad no controlada)"
            ),
        )

    if ext == ".xlsx":
        return GenerationStrategyDecision(
            file_id, "XLSX_CANDIDATE_CELL_LEVEL", generation_ready=False,
            reason=(
                "generador real implementado y probado (xlsx_candidate_generator.py: "
                "candidato + redline celda a celda + DOCUMENT_CONFORMANCE, hojas/formulas "
                "preservadas), pero SIN caso real/finding del corpus Rockwell que lo haya "
                "ejercitado todavia -- generation_ready sigue False hasta esa validacion real, "
                "mismo criterio que el resto del pipeline (nunca declarar listo sin un caso real)"
            ),
        )

    if ext == ".docm":
        return GenerationStrategyDecision(
            file_id, "DOCM_CANDIDATE_SAFE_EXTRACTION", generation_ready=False,
            reason=(
                "generador real implementado y probado (docm_candidate_generator.py: "
                "candidato + redline + verify_vba_project_untouched, copia byte a byte de "
                "vbaProject.bin, nunca lo abre ni ejecuta), pero SIN caso real/finding del "
                "corpus Rockwell que lo haya ejercitado todavia -- generation_ready sigue "
                "False hasta esa validacion real"
            ),
        )

    if ext == ".pdf" and capability == "TEXT_NATIVE":
        return GenerationStrategyDecision(
            file_id, "PDF_RECONSTRUCTED_DOCX_AND_PDF", generation_ready=True,
            reason=(
                "PDF sin fuente editable declarada, con texto extraible confiable -- "
                "reconstruir version editable via document_structure_extractor.py "
                "(Fase 4, document_remediation_evolution) + candidate_document_generator.py "
                "(YA IMPLEMENTADO Y EN PRODUCCION para DOCX; PDF de revision pendiente de "
                "Fase K/L)"
            ),
        )

    if ext == ".docx":
        return GenerationStrategyDecision(
            file_id, "DOCX_CANDIDATE_AND_PDF", generation_ready=True,
            reason="DOCX con candidate_document_generator.py ya implementado y en produccion",
        )

    return GenerationStrategyDecision(
        file_id, "DOCUMENT_GENERATION_BLOCKED", generation_ready=False,
        reason=f"extension {ext!r} / extraction_capability {capability!r} sin estrategia definida en el plan",
    )


def is_strategy_implemented(strategy: str) -> bool:
    """Distingue 'estrategia definida en el plan' de 'generador realmente
    construido y probado' -- una decision con generation_ready=True para
    una estrategia NO implementada aqui seria una contradiccion; este
    helper existe para que los tests puedan verificar esa invariante."""
    return strategy in _IMPLEMENTED_STRATEGIES
