"""W5 V2 -- AGT-QLT, validación de calidad del DOCUMENTO COMPLETO
(sección 14 del plan: "AGT-QLT revisa el DOCUMENTO COMPLETO (no solo
fragmentos): coherencia global; consistencia; terminología; numeración;
referencias cruzadas; tablas; abreviaturas; definiciones; duplicaciones;
contradicciones; ortografía; gramática; claridad; precisión; estilo
profesional").

Diagnóstico previo: `document_quality_gates.py` (Fase 6,
document_remediation_evolution) ya implementa 8 controles reales, pero
POR CAMBIO individual (`evaluate_quality_gates(change, structure)`), no
sobre el documento candidato completo. Este módulo NO reimplementa esos 8
controles -- los reutiliza para CADA cambio del paquete, y agrega los
controles que son genuinamente de ALCANCE DOCUMENTO (numeración
secuencial, referencias cruzadas, duplicación de párrafos) que no existían
en ningún lado.

Terminología, ortografía/gramática, tablas y abreviaturas/definiciones
quedan `NOT_EVALUATED` explícito -- mismo criterio de honestidad ya
establecido en Fase 6 del otro roadmap: no existe una tabla real de
equivalencias terminológicas, herramienta de ortografía, estructura de
datos de tablas del documento, ni glosario de abreviaturas construidos con
evidencia real en este entorno. Fingir estos controles sería fabricar una
regla, no aplicarla."""
from __future__ import annotations

import re
from collections import Counter

from factory.services.document_quality_gates import evaluate_quality_gates

_SECTION_NUMBER_RE = re.compile(r"^(\d+)(?:\.\d+)*$")
_CROSS_REFERENCE_RE = re.compile(
    r"\b(?:secci[oó]n|section|cap[ií]tulo|chapter)\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE
)
_MIN_PARAGRAPH_LEN_FOR_DUPLICATE_CHECK = 20  # evita falsos positivos en lineas cortas (titulos, "N/A", etc.)


def check_section_numbering_sequential(structure: dict) -> dict:
    """Numeración: los números de sección de nivel 1 deben ser
    estrictamente secuenciales (1, 2, 3, ...) y sin duplicados -- mismo
    criterio ya usado para anclar la Tabla de Contenido en
    document_structure_extractor.py, aplicado aquí como control de
    calidad explícito sobre el documento completo."""
    numeros = [s["numero"] for s in structure["secciones"]]
    non_top_level = [n for n in numeros if not _SECTION_NUMBER_RE.match(n)]
    if non_top_level:
        return {
            "status": "NOT_EVALUATED",
            "reason": f"numeros de seccion con formato no evaluable por esta regla (subsecciones): {non_top_level}",
        }
    parsed = [int(n) for n in numeros]
    if len(set(parsed)) != len(parsed):
        dupes = [n for n, c in Counter(parsed).items() if c > 1]
        return {"status": "FAIL", "reason": f"numeros de seccion duplicados: {dupes}"}
    expected = list(range(1, len(parsed) + 1))
    if parsed != expected:
        return {"status": "FAIL", "reason": f"secuencia real {parsed} no coincide con la esperada {expected}"}
    return {"status": "PASS", "reason": f"{len(parsed)} secciones, numeración secuencial sin huecos ni duplicados"}


def check_cross_references_resolve(structure: dict, candidate_full_text: str) -> dict:
    """Referencias cruzadas: toda mención tipo 'sección N'/'section N' en
    el texto del candidato debe corresponder a un número de sección
    real del propio documento -- una referencia a una sección inexistente
    es un error de consistencia real, detectable de forma determinista."""
    real_section_numbers = {s["numero"] for s in structure["secciones"]}
    referenced = set(_CROSS_REFERENCE_RE.findall(candidate_full_text))
    dangling = referenced - real_section_numbers
    if dangling:
        return {
            "status": "FAIL",
            "reason": f"referencias cruzadas a secciones inexistentes en el documento: {sorted(dangling)}",
        }
    return {
        "status": "PASS",
        "reason": f"{len(referenced)} referencia(s) cruzada(s) encontradas, todas resuelven a secciones reales",
    }


def check_no_duplicate_paragraphs(candidate_full_text: str) -> dict:
    """Duplicaciones: un párrafo sustantivo (>= 20 caracteres) que aparece
    más de una vez en el documento candidato es una señal real de
    inserción duplicada -- comparación literal determinista, no
    heurística de similitud."""
    paragraphs = [
        p.strip() for p in candidate_full_text.split("\n")
        if len(p.strip()) >= _MIN_PARAGRAPH_LEN_FOR_DUPLICATE_CHECK
    ]
    counts = Counter(paragraphs)
    duplicated = [p for p, c in counts.items() if c > 1]
    if duplicated:
        return {
            "status": "FAIL",
            "reason": f"{len(duplicated)} parrafo(s) duplicado(s) literalmente en el candidato "
                      f"(ejemplo: {duplicated[0][:80]!r})",
        }
    return {"status": "PASS", "reason": f"{len(paragraphs)} parrafos evaluados, ninguno duplicado literalmente"}


def check_terminology_consistency_document_wide() -> dict:
    return {
        "status": "NOT_EVALUATED",
        "reason": "sin tabla real de equivalencias terminológicas construida con evidencia -- no se inventa "
                  "(mismo criterio de document_quality_gates.check_writing_terminology_consistency, Fase 6)",
    }


def check_orthography_grammar_document_wide() -> dict:
    return {
        "status": "NOT_EVALUATED",
        "reason": "herramienta determinista de ortografía/gramática no disponible en este entorno "
                  "(mismo criterio de document_quality_gates.check_writing_orthography, Fase 6)",
    }


def check_tables_preserved() -> dict:
    return {
        "status": "NOT_EVALUATED",
        "reason": "document_structure_extractor.py no modela tablas como estructura de datos propia todavía "
                  "-- no se finge una verificación sin esa representación real",
    }


def check_abbreviations_and_definitions_consistent() -> dict:
    return {
        "status": "NOT_EVALUATED",
        "reason": "sin glosario real de abreviaturas/definiciones del documento construido con evidencia -- "
                  "no se inventa una lista",
    }


def evaluate_document_quality(
    *, structure: dict, candidate_full_text: str, changes: list[dict]
) -> dict:
    """AGT-QLT completo: agrega los 8 controles por-cambio (Fase 6,
    reutilizados sin reimplementar) para CADA cambio del paquete, más los
    controles de alcance documento genuinamente nuevos (numeración,
    referencias cruzadas, duplicación). `applied=False` si cualquier
    control evaluable (PASS/FAIL) de cualquier cambio o del documento
    falló -- mismo principio de estado binario de Fase 6, sin
    intermedios."""
    per_change_results = [evaluate_quality_gates(change, structure) for change in changes]

    document_wide_controls = {
        "numeracion_secuencial": check_section_numbering_sequential(structure),
        "referencias_cruzadas": check_cross_references_resolve(structure, candidate_full_text),
        "sin_duplicaciones": check_no_duplicate_paragraphs(candidate_full_text),
        "terminologia_documento_completo": check_terminology_consistency_document_wide(),
        "ortografia_gramatica_documento_completo": check_orthography_grammar_document_wide(),
        "tablas_preservadas": check_tables_preserved(),
        "abreviaturas_y_definiciones": check_abbreviations_and_definitions_consistent(),
    }

    failed_document_wide = [
        name for name, result in document_wide_controls.items() if result["status"] == "FAIL"
    ]
    failed_changes = [r["change_id"] for r in per_change_results if not r["applied"]]

    applied = not failed_document_wide and not failed_changes

    return {
        "per_change_results": per_change_results,
        "document_wide_controls": document_wide_controls,
        "applied": applied,
        "human_input_required": not applied,
        "failed_document_wide_controls": failed_document_wide,
        "failed_change_ids": failed_changes,
    }
