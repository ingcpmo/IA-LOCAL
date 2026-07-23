"""W5 V2, Fase F -- validación A/B/C/D (SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md).

Diagnóstico previo a esta fase: A ya existía, probada y con historial real
de fixes (W5.5/W5.6) en `evidence_verifier.match_citation`/
`verify_llm_output`. Existía una versión parcial de C (heurística de
solapamiento léxico, `relevance_score`/`RELEVANCE_REVIEW_REQUIRED`). B no
existía como chequeo explícito a nivel de hallazgo. D no puede
implementarse con juicio regulatorio real porque `evidence_min_criteria`
sigue `PENDING_HUMAN_INTERPRETATION` (decisión de Fase C) -- este módulo
declara D como `NOT_ASSESSABLE` en vez de inventar un criterio.

Este módulo compone las 4 validaciones sin reemplazar la lógica existente:
  A -- delega en evidence_verifier.match_citation (anclaje en el documento).
  B -- NUEVO: el requirement_id resuelve en el catálogo gobernado (Fase C)
       Y la fuente regulatoria tiene hashes_match=True (integridad real,
       no solo presencia).
  C -- reusa evidence_verifier.relevance_score (heurística léxica existente)
       MÁS una regla determinista GENÉRICA nueva (no requiere
       weak_keywords por requisito): detecta si la cita vive dentro de una
       LISTA DE REFERENCIAS NUMERADAS del documento bajo revisión (patrón
       real confirmado: '[6] ... [7] ... [8] Good Automated Manufacturing
       Practice... GAMP5' en el propio corpus Rockwell -- exactamente el
       caso real ANNEX11_4 de la corrida URS v2.1). Esta regla es
       estructural (formato del documento), no interpretación regulatoria
       por requisito.
  D -- NOT_ASSESSABLE explícito, con motivo declarado -- nunca MET/NOT_MET
       inventado.

Evidencia sustantiva aceptada ⇔ A ∧ B ∧ C (D queda fuera de la conjunción
mientras sea NOT_ASSESSABLE en todos los casos -- exigir D=MET haría que
NINGÚN hallazgo pudiera aceptarse jamás, lo cual sería fail-closed hasta el
extremo de bloquear el pipeline completo; se declara la limitación en el
resultado en vez de eso)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory.regulatory.evidence_verifier import match_citation, relevance_score

# Patrón de referencia numerada entre corchetes ('[6]', '[12]', ...) --
# convención tipográfica generica de listas de referencias tecnicas,
# independiente del dominio o del requisito evaluado.
_BRACKETED_REF_RE = re.compile(r"\[\d{1,3}\]")
_REFERENCE_LIST_MIN_MARKERS = 2
_REFERENCE_LIST_WINDOW_CHARS = 250


@dataclass
class ABCDResult:
    a_anchor: str               # PASS | FAIL
    a_match_type: str           # exact | normalized | despaced | fuzzy | not_found
    b_source: str               # PASS | FAIL | NOT_VERIFIABLE
    c_semantic: str             # PASS | FAIL | NOT_VERIFIABLE
    c_flags: list = field(default_factory=list)
    d_sufficiency: str = "NOT_ASSESSABLE"
    d_reason: str = "evidence_min_criteria pendiente de interpretacion humana (Fase C)"

    @property
    def accepted(self) -> bool:
        """A ∧ B ∧ C -- D excluido a proposito (ver docstring del modulo)."""
        return self.a_anchor == "PASS" and self.b_source == "PASS" and self.c_semantic == "PASS"


def verify_anchor(quote: str, source_text: str) -> tuple[str, str]:
    """Validación A. Reusa evidence_verifier.match_citation sin
    reimplementar la lógica de anclaje ya probada."""
    match_type, _score = match_citation(quote, source_text)
    return ("PASS" if match_type in ("exact", "normalized", "despaced", "fuzzy") else "FAIL", match_type)


def verify_regulatory_source(requirement_id: str) -> str:
    """Validación B (nueva). El requisito resuelve en el catálogo gobernado
    Y la fuente regulatoria tiene integridad verificada (hashes_match).
    Import local para no crear un ciclo con requirement_catalog_loader en
    tiempo de import de este módulo (mismo patrón que otros módulos de
    factory/regulatory/ que importan el catálogo bajo demanda)."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        CatalogValidationError, get_requirement, get_source,
    )
    try:
        entry = get_requirement(requirement_id)
        source = get_source(entry["source_id"])
    except CatalogValidationError:
        return "FAIL"
    return "PASS" if source.get("hashes_match") is True else "FAIL"


def detect_reference_list_context(quote: str, source_text: str) -> bool:
    """Regla determinista genérica (no requiere weak_keywords por
    requisito): True si la cita vive dentro de una lista de referencias
    numeradas entre corchetes ('[N]') -- patrón real confirmado en el
    corpus Rockwell (caso ANNEX11_4 de la corrida URS v2.1: 'GAMP5' citado
    dentro de '[8] Good Automated Manufacturing Practice... GAMP5', junto a
    '[6]'/'[7]'/'[9]'/'[10]' en la misma lista). Busca la posición de la
    cita (misma normalización que match_citation) y cuenta marcadores
    '[N]' en una ventana alrededor -- ≥2 marcadores en la ventana indica
    una lista de referencias, no prosa regulatoria real."""
    if not quote or not quote.strip() or not source_text:
        return False
    idx = source_text.find(quote)
    if idx == -1:
        # Intenta con normalizacion basica de espacios (mismo criterio
        # relajado que 'normalized' en match_citation, sin duplicar su
        # lógica completa aquí -- solo para ubicar una posición aproximada).
        collapsed_source = re.sub(r"\s+", " ", source_text)
        collapsed_quote = re.sub(r"\s+", " ", quote).strip()
        idx = collapsed_source.find(collapsed_quote)
        if idx == -1:
            return False
        source_text = collapsed_source
    start = max(0, idx - _REFERENCE_LIST_WINDOW_CHARS)
    end = min(len(source_text), idx + len(quote) + _REFERENCE_LIST_WINDOW_CHARS)
    window = source_text[start:end]
    return len(_BRACKETED_REF_RE.findall(window)) >= _REFERENCE_LIST_MIN_MARKERS


def verify_semantic_relevance(
    quote: str, source_text: str, requirement_terms: list
) -> tuple[str, list[str]]:
    """Validación C: heurística léxica existente (relevance_score) MÁS la
    regla estructural nueva de lista de referencias. Cualquiera de las dos
    señales negativas degrada a NOT_VERIFIABLE (nunca PASS silencioso) --
    consistente con el principio ya establecido en evidence_verifier.py de
    nunca auto-rechazar por heurística, solo marcar para revisión."""
    flags: list[str] = []
    if detect_reference_list_context(quote, source_text):
        flags.append("REFERENCE_LIST_CONTEXT_SUSPECTED")

    rscore = relevance_score(quote, requirement_terms)
    if rscore == -1.0:
        flags.append("RELEVANCE_NOT_EVALUABLE")
    elif rscore < 0.15:  # mismo umbral que evidence_verifier.RELEVANCE_THRESHOLD
        flags.append("RELEVANCE_REVIEW_REQUIRED")

    if flags:
        return ("NOT_VERIFIABLE", flags)
    return ("PASS", flags)


def verify_evidence_abcd(
    quote: str, source_text: str, requirement_id: str, requirement_terms: list
) -> ABCDResult:
    """Composición completa A/B/C/D para un hallazgo puntual (una cita de
    un chunk del documento bajo revisión, para un requirement_id dado)."""
    a_status, a_match_type = verify_anchor(quote, source_text)
    b_status = verify_regulatory_source(requirement_id)
    c_status, c_flags = verify_semantic_relevance(quote, source_text, requirement_terms)
    return ABCDResult(
        a_anchor=a_status, a_match_type=a_match_type,
        b_source=b_status,
        c_semantic=c_status, c_flags=c_flags,
    )
