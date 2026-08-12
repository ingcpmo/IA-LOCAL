"""R3-T1.7 (docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md) -- superficie
UNICA de validez/anclaje de un candidato de chunk para un requisito.

Antes de este modulo, "¿este candidato aporta evidencia valida?" se
decidia de forma FRAGMENTADA en al menos 2 rutas independientes dentro de
`chunked_engine.evaluate_chunked()` -- Ruta A (`by_req`/`Finding`, el
registro tecnico) y Ruta B (`verified_records_by_req`, la que realmente
alimenta `absence_consolidator.consolidate()` y decide el bucket Tier-1
real) -- cada una con su propia logica de anclaje, calculada en puntos
distintos del mismo bucle. B3 (agregacion D, commit `e823015`), B4
(rescate de headline vacio en la Ruta A, commit `f629959`) y el hallazgo
"B5" (el mismo rescate nunca llegaba a la Ruta B) fueron el MISMO defecto
reapareciendo en sitios distintos -- ver el mapa de 4 rutas en
`R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md` bloque 1 (incluye ademas Ruta C,
distinta preocupacion de catalogo, y Ruta D, latente/sin llamador de
produccion hoy).

Mismo patron ya aplicado en el proyecto para evitar superficies paralelas:
`factory/core/path_policy.py` (rutas), `factory/core/
decision_scope_resolver.py` (lectura de decisiones de gobernanza). Esta
es la tercera superficie que se unifica.

TODA ruta que necesite decidir si un candidato ancla, y que texto
representa su evidencia, llama a `resolve_candidate_evidence()`. Ninguna
reimplementa su propia version."""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADLINE_SOURCE_MODEL = "model_headline"
_HEADLINE_SOURCE_DERIVED = "derived_from_criterion_quotes"
_HEADLINE_SOURCE_NONE = "none"

_UNANCHORED_PLACEHOLDER = "(no anclado en el chunk, descartado)"
_REFERENCE_LIST_PLACEHOLDER = "(no anclado en el chunk, descartado -- lista de referencias)"
_DERIVED_PREFIX = "[headline derivado de citas por criterio verificadas] "


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def is_derived_headline(evidencia_exacta: str) -> bool:
    """R3-T1.8 bloque 2: expone publicamente la deteccion del prefijo de
    headline derivado -- CUALQUIER consumidor downstream de
    `Finding.evidencia_exacta` (Ruta A) que necesite re-verificar esa cita
    contra un texto fuente (p.ej. `gap_assessment_finding_mapper.py`,
    Ruta D, hoy sin llamador de produccion) DEBE usar esta funcion en vez
    de reimplementar/hardcodear el marcador -- exactamente el patron que
    causo el defecto B3/B4/B5 (una misma senal, verificada de formas
    distintas en sitios distintos)."""
    return evidencia_exacta.startswith(_DERIVED_PREFIX)


def split_derived_quotes(evidencia_exacta: str) -> list[str]:
    """Inverso de la union `_DERIVED_PREFIX + ' | '.join(derived_quotes)` --
    devuelve las citas individuales, cada una literal y re-verificable por
    separado. `evidencia_exacta` debe cumplir `is_derived_headline()`;
    si no, devuelve `[]` (nunca inventa una cita)."""
    if not is_derived_headline(evidencia_exacta):
        return []
    return evidencia_exacta[len(_DERIVED_PREFIX):].split(" | ")


def is_literally_anchored(quote: str, source_text: str) -> bool:
    """Verificacion de anclaje simple (normalize + substring, sin fuzzy) --
    identica a la que `chunked_engine._is_anchored()` usaba antes de
    R3-T1.7 (movida aqui como la UNICA definicion; ese modulo la
    reexporta para no romper imports existentes). Deliberadamente mas
    estricta que `semantic_evidence_verification.verify_anchor()`
    (que si acepta `fuzzy`) -- ese es un chequeo DISTINTO (validacion A
    formal, ABCD), no se reemplaza aqui, solo se documenta la diferencia
    para que quede explicita, no accidental."""
    if not quote or not quote.strip():
        return False
    return _normalize(quote) in _normalize(source_text)


@dataclass
class CandidateEvidence:
    anchored: bool
    evidencia_exacta: str
    has_evidence: bool
    headline_source: str  # model_headline | derived_from_criterion_quotes | none
    # R3-T1.7 (hallazgo durante el bloque 3 -- re-ejecucion de F2-DRY):
    # `evidencia_exacta` cuando headline_source='derived_from_criterion_quotes'
    # lleva un PREFIJO humano ("[headline derivado...]") y puede unir VARIAS
    # citas con " | " -- ese texto compuesto NUNCA existe literalmente en el
    # chunk como una sola cadena, asi que un consumidor que vuelva a verificar
    # el anclaje de forma independiente (evidence_verifier.verify_llm_output,
    # Ruta B -- un CUARTO punto de anclaje encontrado al validar este fix,
    # fuera del mapa original del bloque 1) lo rechaza (`citation_not_found`)
    # aunque cada cita individual SI ancle. `verifiable_quote` es SIEMPRE
    # una unica cita literal, re-verificable tal cual contra `chunk_text`
    # (la primera cita derivada si hay varias; identica a `evidencia_exacta`
    # cuando el headline es directo, sin cambios). Los consumidores que
    # vuelven a verificar anclaje (Ruta B) DEBEN usar este campo, nunca
    # `evidencia_exacta` -- ese es para presentacion humana (Ruta A/Finding).
    verifiable_quote: str


def resolve_candidate_evidence(
    *, evidencia: str, requires_anchor: bool, chunk_text: str,
    criterion_assessments: "list | None", d_detail: "dict | None",
) -> CandidateEvidence:
    """LA decision unica: ¿este candidato (un chunk, para un requisito)
    aporta evidencia valida, y que texto la representa?

    `requires_anchor`: False para estados que no exigen cita (no_cumple,
    no_aplica, etc.) -- ese candidato cuenta como valido trivialmente
    (comportamiento historico, sin cambios).

    Regla, en orden (nunca afloja, solo puede RECHAZAR mas de lo que
    `is_literally_anchored()` solo ya rechazaba):

    1. Headline directo (`evidencia` no vacio): ancla si
       `is_literally_anchored()` PASA Y no vive dentro de una lista de
       referencias numeradas (`detect_reference_list_context` -- MISMO
       chequeo que ya protegia unicamente a la Ruta B verificada antes de
       R3-T1.7; ahora aplica por igual a cualquier ruta que consuma esta
       funcion, cerrando el gap donde un headline directo podia colarse
       por una ruta que nunca corria ese chequeo).
    2. Fix B4/B5 (R3-T1.6/R3-T1.7): si el headline viene VACIO pero
       `d_detail['met']` (ya calculado por `verify_sufficiency()`, Nivel B
       ya aplica `verify_anchor` por criterio -- nunca puede contener una
       cita fabricada o no anclada) trae al menos un criterio, se DERIVA
       el headline de esas citas ya verificadas -- nunca se inventa texto.
       Cada cita derivada se revisa individualmente contra
       `detect_reference_list_context` (el texto unido con " | " nunca
       existe literalmente en el chunk, revisarlo unido dejaria el
       chequeo mudo para 2+ citas) -- una sola cita sospechosa invalida
       el rescate completo.
    3. Si ninguna de las dos aplica: sin evidencia -- ausencia honesta
       preservada, nunca se rescata con datos inventados.

    Retorna `CandidateEvidence` con el veredicto final; el llamador NUNCA
    vuelve a evaluar anclaje por su cuenta."""
    from factory.regulatory import semantic_evidence_verification as sev

    original = evidencia or ""

    if not requires_anchor:
        return CandidateEvidence(
            anchored=True, evidencia_exacta=original, has_evidence=bool(original.strip()),
            headline_source=_HEADLINE_SOURCE_MODEL if original.strip() else _HEADLINE_SOURCE_NONE,
            verifiable_quote=original,
        )

    if original.strip():
        anchored = is_literally_anchored(original, chunk_text) and not sev.detect_reference_list_context(
            original, chunk_text)
        if anchored:
            return CandidateEvidence(
                anchored=True, evidencia_exacta=original, has_evidence=True,
                headline_source=_HEADLINE_SOURCE_MODEL, verifiable_quote=original,
            )
        return CandidateEvidence(
            anchored=False,
            evidencia_exacta=(
                _REFERENCE_LIST_PLACEHOLDER
                if sev.detect_reference_list_context(original, chunk_text)
                else _UNANCHORED_PLACEHOLDER
            ),
            has_evidence=bool(original.strip()), headline_source=_HEADLINE_SOURCE_MODEL,
            verifiable_quote="",
        )

    # Headline vacio -- unico caso donde el rescate B4/B5 puede aplicar.
    met_criteria = set((d_detail or {}).get("met") or [])
    derived_quotes = [
        str(ca.get("evidence_quote") or "").strip()
        for ca in (criterion_assessments or [])
        if ca.get("status") == "MET" and ca.get("criterion_text") in met_criteria
        and str(ca.get("evidence_quote") or "").strip()
    ] if met_criteria else []
    derived_quotes = list(dict.fromkeys(derived_quotes))  # dedupe, orden estable
    any_reference_list = any(sev.detect_reference_list_context(q, chunk_text) for q in derived_quotes)

    if derived_quotes and not any_reference_list:
        return CandidateEvidence(
            anchored=True, evidencia_exacta=_DERIVED_PREFIX + " | ".join(derived_quotes),
            has_evidence=True, headline_source=_HEADLINE_SOURCE_DERIVED,
            # UNA sola cita, literal, re-verificable -- nunca el texto
            # compuesto (prefijo + join) que verify_llm_output/match_citation
            # jamas encontraria como substring del chunk.
            verifiable_quote=derived_quotes[0],
        )
    return CandidateEvidence(
        anchored=False, evidencia_exacta=_UNANCHORED_PLACEHOLDER if not derived_quotes else _REFERENCE_LIST_PLACEHOLDER,
        has_evidence=False, headline_source=_HEADLINE_SOURCE_NONE, verifiable_quote="",
    )
