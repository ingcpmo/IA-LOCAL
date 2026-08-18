"""R4-T1.0v2 bloque 2 (docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md) --
adaptador que traduce una `RemediationDirective` YA VALIDADA (Acto 2,
`remediation_directive.py`) al formato narrativo que
`gap_assessment_finding_mapper.map_finding_to_remediation_change()`
(Ruta D) exige. Ruta D fue diseñada para `findings_completos_*.json`
(pipeline BATCH_AND_EXCEPTION anterior a Fase F) -- este módulo es el
ÚNICO punto que la alimenta con datos del flujo de directivas; una
directiva es la ÚNICA entrada a Ruta D en este flujo (nunca se llama
map_finding_to_remediation_change() directo con una entrada de la cola
de revisión sin pasar por aquí).

Limitación declarada (decisión de Cesar, 2026-08-13): `change_type=DELETE`
se rechaza explícitamente -- Ruta D no tiene regla de mapeo de
`change_type` para eliminación de contenido (`_CHANGE_TYPE_BY_VERB` solo
cubre adición/reemplazo). Deuda para una iteración futura si hace falta,
nunca fabricada aquí."""
from __future__ import annotations

from factory.regulatory.corpus_runner import _resolve_document_path
from factory.regulatory.regulatory_catalog import RegulatoryCatalogError, get_catalog_entry
from factory.services.gap_assessment_finding_mapper import (
    MappedChange, NotMappableToCurrentSchema, map_finding_to_remediation_change,
)
from factory.services.remediation_directive import _extract_target_text, TargetLocation

# Ambas conclusiones de brecha (hallazgo 2 corregido) describen la MISMA
# situación de fondo -- difieren solo en si la fuente regulatoria está
# PENDING_REVERIFICATION (eje separado, ya gobernado por B1/
# positive_conclusion_eligibility en otra parte del pipeline, no por este
# mapeo) -- así que ninguna distingue clasificacion_brecha por sí sola.
# Lo que SÍ distingue clasificacion_brecha es change_type: ADD significa
# "nada se encontró" (ABSENCE_CONFIRMED); REPLACE significa "se encontró
# algo, pero insuficiente/incorrecto, hay que reemplazarlo"
# (NOT_DEMONSTRATED_IN_DOSSIER -> PARTIAL_EVIDENCE) -- confundir ambas
# hacía que 'evidencia' (una cita real a reemplazar) fuera evaluada con
# la regla de ausencia (exige la frase "todas las secciones evaluadas"),
# rechazando todo REPLACE real.
_TRIGGER_CONCLUSIONS_OK = frozenset({"DOCUMENTATION_GAP", "PROVISIONAL_GAP"})
_CLASIFICACION_BRECHA_BY_CHANGE_TYPE = {
    "ADD": "DOCUMENTATION_GAP",
    "REPLACE": "NOT_DEMONSTRATED_IN_DOSSIER",
}

_RECOMENDACION_VERB_BY_CHANGE_TYPE = {
    "ADD": "Agregar",
    "REPLACE": "Reemplazar",
    # DELETE: sin verbo mapeado a propósito -- ver docstring del módulo.
}

_SEVERIDAD_BY_BINDING_STATUS = {
    "binding_regulation": "mayor",
    "binding_requirement": "mayor",
    "non_binding_guidance": "menor",
}


class DirectiveNotDispatchable(Exception):
    """Fail-closed: la directiva no puede traducirse a un
    RemediationChange -- el llamador decide qué hacer (encolar para
    revisión humana, nunca fabricar un valor)."""


def _translate_directive_to_narrative_finding(
    directive: dict, *, trigger_conclusion: str,
) -> dict:
    if directive["change_type"] == "DELETE":
        raise DirectiveNotDispatchable(
            "change_type=DELETE no tiene regla de mapeo en Ruta D (gap_assessment_finding_mapper."
            "_CHANGE_TYPE_BY_VERB no cubre eliminación) -- deuda declarada, no soportado en esta iteración")

    if trigger_conclusion not in _TRIGGER_CONCLUSIONS_OK:
        raise DirectiveNotDispatchable(
            f"trigger_conclusion={trigger_conclusion!r} no es un disparador válido -- "
            "solo DOCUMENTATION_GAP/PROVISIONAL_GAP deberían llegar aquí (ver remediation_directive."
            "VALID_TRIGGER_CONCLUSIONS)")
    clasificacion_brecha = _CLASIFICACION_BRECHA_BY_CHANGE_TYPE[directive["change_type"]]

    requirement_id = directive["requirement_id"]
    try:
        catalog_entry = get_catalog_entry(requirement_id)
    except RegulatoryCatalogError as e:
        raise DirectiveNotDispatchable(f"requirement_id={requirement_id!r} no existe en el catálogo real: {e}") from e

    verbo = _RECOMENDACION_VERB_BY_CHANGE_TYPE[directive["change_type"]]
    recomendacion = f"{verbo} el siguiente contenido: {directive['proposed_text']}"

    binding_status = catalog_entry.get("binding_status")
    severidad = _SEVERIDAD_BY_BINDING_STATUS.get(binding_status)
    if severidad is None:
        raise DirectiveNotDispatchable(
            f"requirement_id={requirement_id!r}: binding_status={binding_status!r} del catálogo no mapea "
            "a ninguna severidad conocida")

    loc = directive["target_location"]
    # Decisión de Cesar (2026-08-13): page_start como proxy de chunk_id --
    # mismo principio ya documentado y aceptado en Ruta D para
    # chunk_sha256 ("proxy determinista, NO el hash real del motor W7").
    paginas = f"pag {loc['page_start']}-{loc['page_end']} (chunk {loc['page_start']})"

    if directive["change_type"] == "ADD":
        # ABSENCE_CONFIRMATION: no hay cita real que anclar -- 'evidencia'
        # describe la ausencia, nunca un fragmento inventado del documento.
        # La frase exacta es la que _derive_coverage_status() exige (texto
        # heurístico, sin verified_conclusion) para FULL_COVERAGE.
        evidencia = (
            "No se encontró evidencia documental en todas las secciones evaluadas para este "
            "requisito -- brecha confirmada por revisión humana (Acto 1, human_review_queue)."
        )
    else:  # REPLACE, ya validado con original_text anclado en propose_remediation_directive()
        evidencia = directive["original_text"]

    return {
        "finding_id": directive["directive_id"],
        "requisito": f"{requirement_id} — {catalog_entry['label']}",
        "evidencia": evidencia,
        "paginas": paginas,
        "aplicabilidad": "Aplicable — confirmado en el flujo de revisión humana (Acto 1)",
        "clasificacion_brecha": clasificacion_brecha,
        "clasificacion_brecha_rationale": directive["rationale"],
        "recomendacion": recomendacion,
        "severidad": severidad,
        "confianza": "alta",
        "cambio_documental_propuesto": directive["directive_id"],
        # finding_substantive_adapter.py (deuda I-1): un estado no-positivo
        # (evidencia_insuficiente, real -- la brecha confirmada por el
        # Acto 1) no es sujeto de sustento sustantivo -> NOT_APPLICABLE,
        # dentro de PERMITS_COVERAGE_EVALUATION. Nunca 'cumple'/
        # 'cumple_parcialmente' -- este finding SIEMPRE describe una
        # ausencia real, jamas una afirmacion positiva del modelo.
        "estado_agente_original": "evidencia_insuficiente",
    }


def dispatch_directive_to_remediation(directive: dict, *, run_id: str) -> MappedChange:
    """Única función de entrada a Ruta D desde el flujo de directivas.
    `directive` debe venir de `remediation_directive.list_directives()`/
    `propose_remediation_directive()` -- ya pasó todos los guardianes de
    Acto 2 (hallazgo confirmado, conclusión de brecha válida, cita
    regulatoria real, anclaje real para REPLACE). Este módulo NO
    revalida esas condiciones -- solo traduce y llama a Ruta D.

    Lanza NotMappableToCurrentSchema (de Ruta D) o DirectiveNotDispatchable
    (de este adaptador) -- el llamador decide qué hacer con el rechazo
    (encolar para revisión humana, nunca bloquear el resto del lote)."""
    from factory.layer9.human_review_queue import get_entry

    entry = get_entry(directive["finding_rc_id"])
    if entry is None:
        raise DirectiveNotDispatchable(
            f"finding_rc_id={directive['finding_rc_id']!r}: el hallazgo de origen ya no existe en la cola")
    trigger_conclusion = (entry.get("summary") or {}).get("conclusion")

    finding = _translate_directive_to_narrative_finding(directive, trigger_conclusion=trigger_conclusion)

    document_id = directive["document_id"]
    path, document_sha256 = _resolve_document_path(document_id)
    if document_sha256 != directive["document_sha256"]:
        raise DirectiveNotDispatchable(
            f"document_id={document_id!r}: SHA-256 real ({document_sha256}) no coincide con el registrado "
            f"en la directiva ({directive['document_sha256']}) -- el documento cambió desde que se redactó")

    source_text = None
    if directive["change_type"] == "REPLACE":
        loc = directive["target_location"]
        location = TargetLocation(page_start=loc["page_start"], page_end=loc["page_end"], section=loc.get("section"))
        source_text = _extract_target_text(path, location)

    try:
        mapped = map_finding_to_remediation_change(
            finding, document_name=document_id, document_sha256=document_sha256,
            run_id=run_id, source_text=source_text,
        )
    except NotMappableToCurrentSchema:
        raise

    # Cierre P0 (2026-08-18, VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md,
    # hallazgo I/J): remediation_package_service.create_package() exige
    # directive_id real -- Ruta D (map_finding_to_remediation_change) es
    # generica y no lo conoce, asi que este unico adaptador del flujo de
    # directivas lo agrega explicitamente. change_id ya coincide con
    # directive_id en este camino (via finding["cambio_documental_propuesto"]
    # arriba), pero el campo debe existir por su propio nombre -- un
    # consumidor de traceability no deberia tener que asumir esa igualdad.
    mapped.change["directive_id"] = directive["directive_id"]
    return mapped
