"""
Fase 6 (`factory/docs/document_remediation_evolution/LANGUAGE_AND_TECHNICAL_QUALITY_GATES.md`)
— los 6 controles de calidad exigidos para un `RemediationChange` antes de
aplicarse al candidato (`candidate_document_generator.py`, Fase 5).

Reglas deterministas, no un juicio del LLM sobre su propia salida (mismo
principio que `evidence_verifier.py`) -- ver §3 del diseño: "un juicio de
'calidad' hecho por el LLM reintroduciría exactamente el patrón que
evidence_verifier.py fue construido para evitar".

Salida: dos estados únicos por control, sin intermedios (§6) -- PASS o
FAIL (que implica siempre CHANGE_NOT_APPLIED + HUMAN_INPUT_REQUIRED, las
dos caras de la misma falla, nunca "aplicado con advertencia"). Un
tercer estado real, NOT_EVALUATED, existe solo para controles cuya base
de evaluación real no existe todavía en el sistema (tabla de equivalencia
terminológica real, herramienta de ortografía/gramática) -- se declara
explícitamente en vez de fingir un PASS sin haber verificado nada.

Controles 1 (validez regulatoria) y 5 (trazabilidad) YA EXISTEN --
`remediation_package_schemas.validate_remediation_change` ya los cubre
(cada campo de trazabilidad es obligatorio en el schema, y la cita
regulatoria se valida contra el catálogo real). Se reutilizan, no se
reinventan.
"""
from __future__ import annotations

import re

from factory.services.remediation_package_schemas import (
    SchemaValidationError,
    validate_remediation_change,
)

_CAPABILITY_CLAIM_PATTERNS = [
    "el sistema garantiza", "el sistema asegura",
    "el sistema valida automaticamente", "el sistema verifica automaticamente",
    "el sistema controla automaticamente", "el sistema previene automaticamente",
]

_UNVERIFIED_IMPLEMENTATION_PATTERNS = [
    "el sistema ahora garantiza", "se ha verificado que", "ya fue verificado",
    "ha sido implementado", "ya ha sido implementado", "queda demostrado que",
    "se ha comprobado que", "el sistema ya cumple", "ya se encuentra implementado",
]

_RECOMMENDATION_VERBS = {"agregar", "incluir", "añadir", "anadir", "reemplazar", "corregir", "sustituir"}

_NEGATION_PHRASES = ["no aplica", "no se requiere", "no es necesario", "no existe", "not applicable"]

_STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "del", "al", "en", "para",
    "con", "por", "que", "se", "su", "sus", "este", "esta", "estos", "estas", "sin",
    "no", "ya", "como", "sobre", "cada", "mas", "más", "the", "and", "for", "of", "to",
}

_MIN_WORDS = 3
_MAX_WORDS = 2000


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 3}


def _flatten_document_paragraphs(structure: dict) -> list[str]:
    paragraphs = list(structure.get("texto_previo_a_primera_seccion", []))
    for seccion in structure["secciones"]:
        paragraphs.extend(seccion["parrafos"])
    return paragraphs


def check_regulatory_validity_and_traceability(change: dict) -> dict:
    """Controles 1 (validez regulatoria) y 5 (trazabilidad) -- YA EXISTEN,
    reutiliza `validate_remediation_change` sin reimplementar nada."""
    try:
        validate_remediation_change(change)
    except SchemaValidationError as e:
        return {"status": "FAIL", "reason": str(e)}
    return {"status": "PASS", "reason": "validate_remediation_change() sin errores"}


def check_no_invented_capability(change: dict, structure: dict) -> dict:
    """§2 -- detector de capacidad inventada: si `proposed_content` afirma
    una capacidad del sistema ya operando, esa afirmación debe aparecer
    descrita en algún párrafo del propio documento fuente evaluado."""
    proposed = _normalize(change["proposed_content"])
    document_text = _normalize(" ".join(_flatten_document_paragraphs(structure)))
    for pattern in _CAPABILITY_CLAIM_PATTERNS:
        if pattern in proposed and pattern not in document_text:
            return {
                "status": "FAIL",
                "reason": f"proposed_content afirma una capacidad ('{pattern}') que no aparece "
                          "descrita en ningún párrafo del documento fuente evaluado",
            }
    return {"status": "PASS", "reason": "no afirma una capacidad ausente del documento fuente"}


def check_writing_length(change: dict) -> dict:
    """§3 -- longitud mínima/máxima razonable."""
    n_words = len(change["proposed_content"].split())
    if n_words < _MIN_WORDS:
        return {"status": "FAIL", "reason": f"proposed_content de {n_words} palabra(s), por debajo del mínimo ({_MIN_WORDS})"}
    if n_words > _MAX_WORDS:
        return {"status": "FAIL", "reason": f"proposed_content de {n_words} palabras, por encima del máximo ({_MAX_WORDS})"}
    return {"status": "PASS", "reason": f"{n_words} palabras, dentro de [{_MIN_WORDS}, {_MAX_WORDS}]"}


def check_writing_controlled_verb(change: dict) -> dict:
    """§3 -- verbo inicial de proposed_content pertenece al vocabulario
    controlado real de `gap_assessment_finding_mapper._derive_change_type`
    (7 verbos: agregar/incluir/añadir/anadir/reemplazar/corregir/sustituir)
    -- no se amplía esa lista aquí sin evidencia real que lo motive."""
    proposed = change["proposed_content"].strip()
    if not proposed:
        return {"status": "FAIL", "reason": "proposed_content vacío"}
    verbo = proposed.split()[0].lower().strip(",.;:")
    if verbo not in _RECOMMENDATION_VERBS:
        return {
            "status": "FAIL",
            "reason": f"verbo inicial '{verbo}' no pertenece al vocabulario controlado {sorted(_RECOMMENDATION_VERBS)}",
        }
    return {"status": "PASS", "reason": f"verbo inicial '{verbo}' es de acción documental reconocida"}


def check_writing_terminology_consistency() -> dict:
    """§3 -- terminología consistente. NOT_EVALUATED explícito: no existe
    hoy una tabla real de pares término-equivalente (ej. "backup"/
    "respaldo") construida a partir de evidencia real del documento --
    inventarla sin datos reales sería fabricar una regla, no aplicarla."""
    return {
        "status": "NOT_EVALUATED",
        "reason": "sin tabla real de equivalencias terminológicas construida con evidencia -- no se inventa",
    }


def check_writing_orthography() -> dict:
    """§3 -- ortografía/gramática. NOT_EVALUATED explícito: requiere una
    herramienta determinista externa (LanguageTool/aspell local, sin
    llamar a Ollama) que no está instalada en este entorno -- no se
    finge una verificación sin ella."""
    return {
        "status": "NOT_EVALUATED",
        "reason": "herramienta determinista de ortografía/gramática no disponible en este entorno",
    }


def check_document_coherence(change: dict, structure: dict) -> dict:
    """§4 -- coherencia con el resto del documento: si alguna línea del
    documento fuente contiene una negación explícita ("no aplica", "no se
    requiere"...) junto con un término de contenido que también aparece en
    proposed_content, se marca como posible contradicción sin reconciliar
    -- comparación léxica determinista, no un juicio del LLM."""
    content_words = _content_words(change["proposed_content"])
    if not content_words:
        return {"status": "PASS", "reason": "proposed_content sin términos de contenido para comparar"}

    for linea in _flatten_document_paragraphs(structure):
        low = linea.lower()
        for neg in _NEGATION_PHRASES:
            if neg in low and any(w in low for w in content_words):
                return {
                    "status": "FAIL",
                    "reason": f"el documento fuente contiene '{neg}' en una línea que menciona "
                              f"término(s) de proposed_content sin reconciliar: {linea.strip()[:160]!r}",
                }
    return {"status": "PASS", "reason": "sin negación contradictoria detectada en el documento fuente"}


def check_no_unverified_implementation_claim(change: dict) -> dict:
    """§5 -- ausencia de afirmaciones de implementación no demostradas:
    proposed_content nunca puede usar un tiempo verbal que implique que
    el cambio ya fue verificado/implementado -- es siempre una PROPUESTA."""
    proposed = _normalize(change["proposed_content"])
    for pattern in _UNVERIFIED_IMPLEMENTATION_PATTERNS:
        if pattern in proposed:
            return {
                "status": "FAIL",
                "reason": f"usa un tiempo verbal de implementación ya verificada ('{pattern}') -- "
                          "un cambio documental es siempre una propuesta, nunca una declaración de estado verificado",
            }
    return {"status": "PASS", "reason": "no afirma implementación/verificación ya realizada"}


def evaluate_quality_gates(change: dict, structure: dict) -> dict:
    """Corre los 6 controles (§1) sobre un RemediationChange. `structure`
    es la representación intermedia de Fase 4 (`document_structure_extractor`)
    del documento fuente evaluado por el propio `change`.

    `applied`: False si CUALQUIER control evaluable (PASS/FAIL, no
    NOT_EVALUATED) falló -- coherente con §6: sin estado intermedio
    "aplicado con advertencia"."""
    controls = {
        "validez_regulatoria_y_trazabilidad": check_regulatory_validity_and_traceability(change),
        "validez_tecnica_capacidad_inventada": check_no_invented_capability(change, structure),
        "redaccion_longitud": check_writing_length(change),
        "redaccion_verbo_controlado": check_writing_controlled_verb(change),
        "redaccion_terminologia": check_writing_terminology_consistency(),
        "redaccion_ortografia": check_writing_orthography(),
        "coherencia_documental": check_document_coherence(change, structure),
        "ausencia_afirmacion_no_demostrada": check_no_unverified_implementation_claim(change),
    }

    failed = [name for name, result in controls.items() if result["status"] == "FAIL"]
    applied = not failed

    return {
        "change_id": change["change_id"],
        "controls": controls,
        "applied": applied,
        "human_input_required": not applied,
        "failed_controls": failed,
    }
