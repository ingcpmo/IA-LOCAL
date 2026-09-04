"""SHADOW · CF-6 v2.0 · R1 — Requirement <-> Evidence Relevance Model (diseño §4).

Determinista, fail-closed, trazable. Se aplica POR CADA ítem de evidencia
candidata de una sección del Composer (`factory/regulatory/shadow/composer.py`),
ANTES de que esa evidencia pueda llegar a cualquier llamada LLM.

Fuente de verdad: `decomposition.yaml` (GOBERNADO, firmado por Capa 9,
`requirement_decomposition_loader.py`) — este módulo NUNCA lo modifica, solo
lo lee.

Por qué existe (diagnóstico real, `CF6_v2_REDISENO_AUDITORIA_PROFESIONAL.md`
§0/§4): `sec-0016` (RW-0006, 21_CFR_11.10(d)) incluyó en su narrativa un
finding cuya cita anclada ("The system shall measure the critical process
parameters...") no tiene relación con el sub-criterio real que la generó
(`sc3`, "proceso de cambio de privilegios de cuentas") — llegó al LLM
porque el recall léxico previo la propuso como candidata, no porque fuera
pertinente. Este módulo separa "evidencia recuperada" de "evidencia
pertinente" ANTES de que el LLM la vea.

Nota honesta de alcance: a este nivel (entradas de sección del Composer,
derivadas de findings L2 ya resueltos) no hay `bm25_score` adjunto por
entrada -- ese campo vive un nivel más abajo, en los candidatos crudos de
`factory/regulatory/retrieval/evidence_bundle.py` (BM25 sobre `Claim`).
Cuando ese `bm25_score` SÍ está disponible en el objeto de evidencia (p.ej.
si en el futuro este modelo se invoca directamente sobre un
`EvidenceBundle`), se usa como señal adicional; si no está, la clasificación
se apoya solo en solapamiento léxico ponderado (nunca se inventa un bm25).
Esto es explícito y auditable — no una degradación silenciosa.

Ponderación (`_local_idf`): en vez de una lista de stopwords "de dominio"
hecha a mano, el peso de cada término se calcula como 1 / (número de
sub-criterios del MISMO requisito cuyo texto contiene ese término). Términos
que aparecen en casi todos los sub-criterios de un requisito (p.ej.
"process"/"account" en 21_CFR_11.10(d)) pesan poco por construcción; términos
distintivos de un sub-criterio concreto pesan 1.0. Esto se deriva del propio
`decomposition.yaml` firmado -- no es un umbral arbitrario por caso.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria,
)

RELEVANT = "RELEVANT"
PARTIALLY_RELEVANT = "PARTIALLY_RELEVANT"
IRRELEVANT = "IRRELEVANT"
INCONCLUSIVE = "INCONCLUSIVE"

# Umbrales deterministas, calibrados contra el caso confirmado de sec-0016
# (RW-0006 / 21_CFR_11.10(d)::sc3, ver test_relevance_model.py) y contra un
# caso positivo confirmado de la misma sección (sc1). Conservador por diseño:
# ambiguo -> INCONCLUSIVE, NUNCA se sube a RELEVANT por defecto.
_RELEVANT_MIN_MATCHED = 2
_RELEVANT_MIN_RATIO = 0.30
_PARTIAL_MIN_MATCHED = 1
_PARTIAL_MIN_RATIO = 0.12

# Ref. a "<requirement_id>::<sc_id>" tal como la escribe el pipeline previo
# en `rationale_l2` (ver `factory/regulatory/shadow/composer.py` y las
# rationales de MODO TIER-1 / Palanca C). Solo lectura -- nunca se genera.
_SC_REF_RE = re.compile(r"::(sc\d+)\b")

_BASIC_STOPWORDS = frozenset({
    # ES
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "y", "o", "en", "con", "por", "para", "que", "su", "sus", "se", "es",
    "son", "hay", "existe", "si", "las", "lo", "como", "sin", "más",
    # EN
    "the", "a", "an", "is", "are", "of", "for", "with", "to", "and", "or",
    "this", "that", "shall", "system", "there", "if", "any", "be", "by",
    "on", "as", "its",
})


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-záéíóúñü]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in _BASIC_STOPWORDS]


@lru_cache(maxsize=64)
def _local_idf(requirement_id: str) -> dict:
    """peso[term] = 1 / (n sub-criterios del requisito que contienen `term`).
    Calculado únicamente a partir de `decomposition.yaml` (ya firmado) para
    este `requirement_id` -- 0 escrituras, 0 llamadas externas."""
    subs = get_subcriteria(requirement_id)
    doc_terms = [set(_tokenize(sc.get("text", "")) + _tokenize(sc.get("text_en", ""))) for sc in subs]
    df: dict[str, int] = {}
    for terms in doc_terms:
        for t in terms:
            df[t] = df.get(t, 0) + 1
    n = max(len(subs), 1)
    return {t: 1.0 / c for t, c in df.items()} | {"__n_subcriteria__": n}


def extract_subcriterion_ref(rationale_l2: str) -> str | None:
    """`sc_id` explícito si `rationale_l2` lo menciona (p.ej. '...::sc3...'),
    None si no hay referencia -- en ese caso se evalúa contra TODOS los
    sub-criterios del requisito (agregado, se toma el mejor match, conservador
    en la clasificación, nunca en el filtrado: el mejor match manda)."""
    m = _SC_REF_RE.search(rationale_l2 or "")
    return m.group(1) if m else None


@dataclass(frozen=True)
class RelevanceVerdict:
    relevance_state: str
    matched_subcriterion_id: str | None
    matched_terms: tuple
    weighted_ratio: float
    n_matched: int
    requirement_id: str
    bm25_score: float | None = None
    reason: str = ""


def _score_against_subcriterion(quote_terms: set, sc: dict, idf: dict) -> tuple:
    sc_terms = set(_tokenize(sc.get("text", "")) + _tokenize(sc.get("text_en", "")))
    if not sc_terms:
        return (0.0, 0, frozenset())
    matched = quote_terms & sc_terms
    weighted_matched = sum(idf.get(t, 1.0) for t in matched)
    weighted_total = sum(idf.get(t, 1.0) for t in sc_terms) or 1.0
    ratio = weighted_matched / weighted_total
    return (ratio, len(matched), frozenset(matched))


def classify(*, quote_text: str, requirement_id: str, rationale_l2: str = "",
             subcriterion_id: str | None = None, bm25_score: float | None = None) -> RelevanceVerdict:
    """Clasifica UNA evidencia candidata contra el requisito `requirement_id`.

    `subcriterion_id`, si se pasa explícitamente, fija contra qué sub-criterio
    se evalúa. Si no, se intenta extraer de `rationale_l2`; si tampoco hay,
    se evalúa contra TODOS los sub-criterios del requisito y se toma el de
    mayor solapamiento ponderado (el candidato tiene el beneficio de la duda
    sobre A CUÁL sub-criterio corresponde, nunca sobre SI es pertinente)."""
    quote_terms = set(_tokenize(quote_text))
    idf = _local_idf(requirement_id)
    subs = get_subcriteria(requirement_id)

    target_id = subcriterion_id or extract_subcriterion_ref(rationale_l2)
    if target_id:
        subs = [sc for sc in subs if sc["id"] == target_id] or subs

    best = (0.0, 0, frozenset(), None)
    for sc in subs:
        ratio, n_matched, matched = _score_against_subcriterion(quote_terms, sc, idf)
        if (ratio, n_matched) > (best[0], best[1]):
            best = (ratio, n_matched, matched, sc["id"])
    ratio, n_matched, matched, sc_id = best

    if n_matched == 0:
        if bm25_score is not None and bm25_score >= 0.5:
            # solapamiento léxico nulo pero bm25 alto -- posible paráfrasis
            # real, no se descarta a ciegas: conservador -> INCONCLUSIVE.
            state, reason = INCONCLUSIVE, "overlap nulo, bm25 alto: ambiguo, no se descarta a ciegas"
        else:
            state, reason = IRRELEVANT, "overlap léxico nulo con el sub-criterio (bm25 no disponible o bajo)"
    elif n_matched >= _RELEVANT_MIN_MATCHED and ratio >= _RELEVANT_MIN_RATIO:
        state, reason = RELEVANT, f"overlap alto ({n_matched} términos, ratio={ratio:.3f})"
    elif n_matched >= _PARTIAL_MIN_MATCHED and ratio >= _PARTIAL_MIN_RATIO:
        state, reason = PARTIALLY_RELEVANT, f"overlap parcial ({n_matched} términos, ratio={ratio:.3f})"
    else:
        state, reason = INCONCLUSIVE, f"overlap bajo/ambiguo ({n_matched} términos, ratio={ratio:.3f})"

    return RelevanceVerdict(
        relevance_state=state, matched_subcriterion_id=sc_id,
        matched_terms=tuple(sorted(matched)), weighted_ratio=round(ratio, 4),
        n_matched=n_matched, requirement_id=requirement_id, bm25_score=bm25_score, reason=reason,
    )


def classify_entry(entry: dict, *, bm25_score: float | None = None) -> RelevanceVerdict:
    """Conveniencia sobre una `entry` de `composer.build_composer_skeleton`
    (tiene `requirement_id`, `anchored_quote_l2`, `rationale_l2`)."""
    return classify(
        quote_text=entry.get("anchored_quote_l2") or "",
        requirement_id=entry.get("requirement_id"),
        rationale_l2=entry.get("rationale_l2") or "",
        bm25_score=bm25_score,
    )


def partition_entries(entries: list[dict]) -> dict:
    """Partición determinista de `entries[]` de una sección del Composer en
    `relevant_evidence[]` (RELEVANT|PARTIALLY_RELEVANT) y `excluded_evidence[]`
    (IRRELEVANT|INCONCLUSIVE) -- excluded_evidence se conserva para auditoría,
    NUNCA se descarta del artefacto, solo se excluye del prompt del LLM."""
    relevant, excluded = [], []
    for e in entries:
        rid = e.get("requirement_id")
        if not rid:
            # sin requirement_id no hay contra qué evaluar pertinencia --
            # fail-closed: se trata como INCONCLUSIVE (excluida), nunca se
            # asume relevante por defecto.
            verdict = RelevanceVerdict(
                relevance_state=INCONCLUSIVE, matched_subcriterion_id=None,
                matched_terms=(), weighted_ratio=0.0, n_matched=0,
                requirement_id="", reason="sin requirement_id -- no evaluable")
        else:
            verdict = classify_entry(e)
        item = {"finding_record_id": e.get("finding_record_id"), "verdict": verdict}
        (relevant if verdict.relevance_state in (RELEVANT, PARTIALLY_RELEVANT) else excluded).append(item)
    return {"relevant_evidence": relevant, "excluded_evidence": excluded}
