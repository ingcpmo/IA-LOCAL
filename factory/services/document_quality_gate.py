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


def _original_full_text(structure: dict) -> str:
    """Texto del documento ORIGINAL tal como lo modela el extractor:
    frontmatter (portada, TOC, cabeceras previas a la seccion 1) + los
    parrafos de cada seccion. Omitir el frontmatter subcuenta las
    repeticiones estructurales y reintroduce el falso positivo."""
    lines = list(structure.get("texto_previo_a_primera_seccion") or [])
    for seccion in structure["secciones"]:
        lines.extend(seccion.get("parrafos") or [])
    return "\n".join(lines)


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


def _reference_depth(numero: str) -> int:
    return numero.count(".") + 1


def check_cross_references_resolve(structure: dict, candidate_full_text: str) -> dict:
    """Referencias cruzadas: una mención tipo 'sección N'/'section N' que no
    corresponde a ninguna sección real es un error de consistencia.

    Se adjudica SOLO a la granularidad que la estructura realmente modela.
    `document_structure_extractor` extrae por diseño **solo secciones de
    nivel 1** (su propio docstring lo declara: la heurística de subsecciones
    producía 19 "secciones" donde hay 8). Comparar una referencia a `2.1.1`
    contra ese universo garantiza un falso positivo: la subsección puede
    existir perfectamente y el extractor no la modela.

    Defecto real medido el 2026-07-28 sobre FS_v1.2: la regla reportaba
    2.1.1, 3.1.12, 3.1.3 y 7.1.1 como inexistentes. Las cuatro se citan en
    el documento junto a su título ("Section 2.1.1 Software", "Section
    3.1.12 Overview Screen", "Section 3.1.3 F01.03: Engineering
    Workstation") y esos títulos SÍ están en el texto extraído: son
    subsecciones reales cuya numeración se perdió en la extracción, no
    referencias rotas.

    Por tanto: una referencia de nivel 1 sigue siendo refutable y se reporta
    FAIL si no existe. Una referencia a subsección solo se adjudica si la
    estructura modela subsecciones; si no las modela, queda NOT_EVALUATED
    con la razón explícita -- afirmar que no existe sería afirmar algo que
    esta estructura no puede saber."""
    real_section_numbers = {s["numero"] for s in structure["secciones"]}
    structure_models_subsections = any(_reference_depth(n) > 1 for n in real_section_numbers)
    referenced = set(_CROSS_REFERENCE_RE.findall(candidate_full_text))

    adjudicable = {
        r for r in referenced
        if _reference_depth(r) == 1 or structure_models_subsections
    }
    not_adjudicable = sorted(referenced - adjudicable)
    dangling = sorted(adjudicable - real_section_numbers)

    if dangling:
        return {
            "status": "FAIL",
            "reason": f"referencias cruzadas a secciones inexistentes en el documento: {dangling}",
        }
    if not_adjudicable:
        return {
            "status": "NOT_EVALUATED",
            "reason": f"{len(adjudicable)} referencia(s) de nivel 1 resuelven correctamente; "
                      f"{len(not_adjudicable)} referencia(s) a subseccion ({not_adjudicable}) no son "
                      "evaluables: document_structure_extractor modela solo secciones de nivel 1, "
                      "asi que su existencia no puede confirmarse ni refutarse desde esta estructura",
        }
    return {
        "status": "PASS",
        "reason": f"{len(referenced)} referencia(s) cruzada(s) encontradas, todas resuelven a secciones reales",
    }


def _substantive_paragraph_counts(text: str) -> Counter:
    return Counter(
        p.strip() for p in text.split("\n")
        if len(p.strip()) >= _MIN_PARAGRAPH_LEN_FOR_DUPLICATE_CHECK
    )


def check_no_duplicate_paragraphs(candidate_full_text: str, original_full_text: str) -> dict:
    """Duplicaciones INTRODUCIDAS por la generación: un párrafo sustantivo
    (>= 20 caracteres) cuya multiplicidad en el candidato SUPERA la que ya
    tenía en el documento original.

    Por qué no basta "aparece más de una vez" (defecto real medido el
    2026-07-28 sobre FS_v1.2): el texto de un PDF paginado repite
    necesariamente sus encabezados y pies de página una vez por página --
    el FS tiene 58 páginas y su cabecera aparece 58 veces-- y una
    especificación funcional repite legítimamente frases de plantilla
    ("This function implements the following user requirement(s)", 51
    veces). La regla anterior reportaba 76 párrafos duplicados; los 76 ya
    estaban en el original con multiplicidad igual o mayor. Cero eran
    inserciones nuestras.

    La comparación contra el original NO oculta nada: una duplicación
    realmente introducida por la remediación aumenta la multiplicidad, y
    eso es exactamente lo que se sigue reportando. Lo que deja de afirmarse
    es que la estructura propia del documento fuente sea un defecto del
    candidato."""
    candidate_counts = _substantive_paragraph_counts(candidate_full_text)
    original_counts = _substantive_paragraph_counts(original_full_text)

    introduced = {
        p: (c, original_counts.get(p, 0))
        for p, c in candidate_counts.items()
        if c > 1 and c > original_counts.get(p, 0)
    }
    if introduced:
        worst = max(introduced.items(), key=lambda kv: kv[1][0] - kv[1][1])
        p, (in_candidate, in_original) = worst
        return {
            "status": "FAIL",
            "reason": f"{len(introduced)} parrafo(s) con multiplicidad AUMENTADA respecto al "
                      f"original (ejemplo: {in_original} -> {in_candidate} veces, {p[:80]!r})",
        }
    preexisting = sum(1 for p, c in candidate_counts.items() if c > 1)
    return {
        "status": "PASS",
        "reason": f"{sum(candidate_counts.values())} parrafos evaluados, 0 duplicaciones introducidas "
                  f"({preexisting} repeticion(es) ya presentes en el original: encabezados de pagina "
                  f"y texto de plantilla, no inserciones)",
    }


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

    # Texto ORIGINAL completo reconstruido desde la misma `structure` que ya
    # recibe esta funcion -- incluye el frontmatter previo a la seccion 1
    # (portada, TOC, cabeceras), sin el cual la comparacion de multiplicidad
    # subcontaria las repeticiones legitimas y volveria a dar falsos
    # positivos. No hace falta ningun parametro nuevo.
    original_full_text = _original_full_text(structure)

    document_wide_controls = {
        "numeracion_secuencial": check_section_numbering_sequential(structure),
        "referencias_cruzadas": check_cross_references_resolve(structure, candidate_full_text),
        "sin_duplicaciones": check_no_duplicate_paragraphs(candidate_full_text, original_full_text),
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
