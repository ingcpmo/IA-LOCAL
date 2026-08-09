"""R2 (docs_plan/R2_DESIGN_DETALLADO.md, 2026-08-09) -- Okapi BM25 puro,
sin dependencias nuevas (`re`/`collections.Counter`/`math`, todo stdlib).
Decisión de Cesar: TF-IDF/BM25 en vez de ChromaDB, y "sin dependencia
nueva" tomado literalmente -- ni siquiera `rank_bm25`/`scikit-learn`.

k1/b son los valores de referencia de la literatura (Robertson/Sparck
Jones), NO calibrados a mano contra el fixture -- anotado explícitamente
para que una sesión futura no los confunda con un ajuste fino ya hecho."""
from __future__ import annotations

import math
import re
from collections import Counter

K1_DEFAULT = 1.5
B_DEFAULT = 0.75

_TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+")


def tokenize(text: str) -> list[str]:
    """Mismo patrón de extracción de palabras que
    chunked_engine._is_topically_relevant (re.findall + lower) -- se
    reutiliza el patrón, no se inventa una regex nueva. Sin filtro de
    longitud mínima ni stopwords aquí (a diferencia de _LABEL_STOPWORDS,
    que es especifico de esa heuristica): BM25 ya down-weightea términos
    comunes vía IDF, no hace falta un stopword list adicional."""
    return [w.lower() for w in _TOKEN_RE.findall(text)]


def term_counts(text: str) -> dict[str, int]:
    return dict(Counter(tokenize(text)))


def idf(term: str, chunks: list[dict]) -> float:
    """IDF Okapi estándar. chunks: lista de {"term_counts": {...}, ...}."""
    n_docs = len(chunks)
    if n_docs == 0:
        return 0.0
    n_containing = sum(1 for c in chunks if term in c["term_counts"])
    return math.log((n_docs - n_containing + 0.5) / (n_containing + 0.5) + 1)


def build_idf_table(query_terms: list[str], chunks: list[dict]) -> dict[str, float]:
    """Solo calcula IDF para los términos de la query -- no hace falta
    indexar el vocabulario completo del documento para responder una
    query puntual."""
    return {term: idf(term, chunks) for term in set(query_terms)}


def bm25_score(query_terms: list[str], chunk: dict, corpus_idf: dict[str, float],
               avg_chunk_len: float, k1: float = K1_DEFAULT, b: float = B_DEFAULT) -> float:
    """chunk: {"term_counts": {...}, "token_count": int}. Determinista --
    mismo input siempre produce el mismo score, sin llamada a LLM ni a
    ningún servicio externo."""
    if avg_chunk_len <= 0:
        return 0.0
    score = 0.0
    dl = chunk["token_count"]
    for term in query_terms:
        f = chunk["term_counts"].get(term, 0)
        if f == 0:
            continue
        term_idf = corpus_idf.get(term, 0.0)
        score += term_idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_chunk_len))
    return score
