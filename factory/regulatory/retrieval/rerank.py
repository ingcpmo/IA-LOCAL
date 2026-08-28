"""Reranker local del candidate pool contra un SUB-CRITERIO concreto
(V2, B3) — docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 4.2.

El pool de fusión/BM25 se rankeó contra la query del REQUISITO completo.
Tras la descomposición (decomposition.yaml, firmado), la pregunta al modelo
es por sub-criterio -> conviene re-rankear los candidatos contra el texto
del sub-criterio específico, que es más estrecho.

B3 usa un reranker LÉXICO DETERMINISTA (solapamiento de tokens ponderado +
proximidad de bigramas), sin modelo, sin descargas, sin LLM. Es
suficiente para acercar el candidato correcto al top-k cuando el
sub-criterio comparte vocabulario con el pasaje (que es justo el caso
LEXICAL_ECHO que sí funciona).

Hook opcional (NO implementado, requiere autorización de Capa 9 para el
pull): un cross-encoder local (p. ej. ms-marco-MiniLM-L-6-v2, ~80 MB, CPU)
vía `CrossEncoderReranker`. Si el modelo no está disponible, se usa el
léxico -- nunca falla por su ausencia.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúñÑ0-9]+")

# Palabras funcionales que no deben dominar el solapamiento (ES + EN).
_STOP = frozenset("""
el la los las un una unos unas de del a al y o u en con por para que se su sus lo
es son ser este esta estos estas como o si no ni mas más menos the a an of to in
on for and or is are be as that this these those with by from at
""".split())


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _TOKEN_RE.findall(text or "")]


def _content_tokens(text: str) -> list[str]:
    return [t for t in _tokens(text) if t not in _STOP and len(t) > 2]


def _bigrams(toks: list[str]) -> set[tuple[str, str]]:
    return set(zip(toks, toks[1:]))


def lexical_score(subcriterion_text: str, candidate_text: str) -> float:
    """Score determinista en [0, ~1+]: solapamiento de tokens de contenido
    (con idf-lite por rareza dentro del par) + bonus por bigramas
    compartidos. Mismo input -> mismo score."""
    q = _content_tokens(subcriterion_text)
    d = _content_tokens(candidate_text)
    if not q or not d:
        return 0.0
    qset, dcount = set(q), Counter(d)
    # solapamiento ponderado: un token del sub-criterio presente en el
    # candidato aporta 1; se normaliza por el tamaño del sub-criterio.
    overlap = sum(1.0 for t in qset if t in dcount)
    base = overlap / len(qset)
    # bonus por bigramas compartidos (captura "audit trail", "valor previo")
    shared_bg = len(_bigrams(q) & _bigrams(d))
    bonus = 0.15 * shared_bg
    # leve penalización si el candidato es enorme (dilución)
    length_pen = 1.0 / (1.0 + math.log1p(max(0, len(d) - 120) / 120))
    return (base + bonus) * length_pen


def rerank(subcriterion_text: str, candidates: list[dict], *, top_k: int = 5,
           text_key: str = "text", reranker: "Reranker | None" = None) -> list[dict]:
    """Reordena `candidates` por relevancia al `subcriterion_text` y
    devuelve los `top_k`. Cada candidato gana `rerank_score` y
    `rerank_method`. Estable: empates conservan el orden de entrada
    (que ya viene de fusión/BM25)."""
    scorer = reranker or _LEXICAL_SINGLETON
    scored = []
    for i, c in enumerate(candidates):
        s = scorer.score(subcriterion_text, c.get(text_key) or "")
        scored.append((i, s, c))
    scored.sort(key=lambda t: (-t[1], t[0]))
    out = []
    for _, s, c in scored[:top_k]:
        c2 = dict(c)
        c2["rerank_score"] = round(float(s), 5)
        c2["rerank_method"] = scorer.name
        out.append(c2)
    return out


class Reranker:
    name = "base"

    def score(self, query: str, doc: str) -> float:  # pragma: no cover - interfaz
        raise NotImplementedError


class LexicalReranker(Reranker):
    name = "lexical_v1"

    def score(self, query: str, doc: str) -> float:
        return lexical_score(query, doc)


_LEXICAL_SINGLETON = LexicalReranker()


class CrossEncoderReranker(Reranker):
    """Hook OPCIONAL. Requiere `sentence-transformers` + un modelo
    cross-encoder local (pull sujeto a autorización de Capa 9). Si algo
    falta, __init__ lanza y el llamador cae al LexicalReranker.
    NO se instancia por defecto en ningún sitio de B3."""
    name = "cross_encoder"

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "CrossEncoderReranker no disponible: falta sentence-transformers o el "
                "modelo local (pull no autorizado). Usar LexicalReranker."
            ) from e
        self._model = CrossEncoder(model_name)

    def score(self, query: str, doc: str) -> float:
        return float(self._model.predict([(query, doc)])[0])
