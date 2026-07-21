"""Verificador deterministico de evidencia. v2 (W5 Ciclo 1, Fase 2, Bloque 2.1).

Checks ternarios: PASS | FAIL | NOT_VERIFIABLE.
  - FAIL en cualquier check demostrable -> rejected_by_verifier.
  - NOT_VERIFIABLE nunca equivale a PASS: agrega flag de revision (P1/P6).
Taxonomia de coincidencia de cita:
  exact | normalized | despaced | fuzzy | not_found
  - exact/normalized/despaced -> cita verificada (misma anchura de criterio:
    coincidencia de caracteres literal, solo se ignora diseño de espacios en
    blanco -- nunca se acepta contenido distinto).
  - fuzzy >= 0.93   -> verified_with_deviation + flag CITATION_DEVIATION.
  - < 0.93          -> not_found -> FAIL.

W5.6 (hallazgo real, chunk 20 de "215115305 SCADA-PCS Misc PLC System
FS_v1.2.pdf", ETAPA 4): una cita literal y correcta quedaba
`rejected_by_verifier/citation_not_found` por dos artefactos DEMOSTRABLES de
extraccion de PDF, ninguno de los dos alteracion del modelo:
  1. Espacio espureo insertado a mitad de palabra por el kerning del PDF
     ("whenever" -> "wheneve r") -- _normalize() ya colapsaba corridas de
     espacios a uno solo, pero no fusionaba un espacio real insertado DENTRO
     de una palabra. Fix: tier adicional "despaced" en match_citation() que
     compara ignorando TODO whitespace (no solo colapsando corridas) --
     sigue siendo comparacion de caracteres literal, no fuzzy/semantica.
  2. Membrete de pagina (furniture) de la plantilla Rockwell -- "Project:
     ... Functional Specification for the ... System ... ID code: ...
     Page N of N ... (c) YYYY Rockwell Automation, Inc. All Rights
     Reserved [/ Author: X] ... This function implements the following
     user requirement(s)" -- insertado literalmente por pypdf entre el
     contenido real de dos paginas consecutivas del mismo chunk (build_page_
     chunks concatena texto de pagina completo, membrete incluido). Fix:
     _strip_page_furniture() elimina este patron generico y acotado (limites
     de longitud en la regex, nunca DOTALL sin cota) ANTES de normalizar --
     no depende del nombre del proyecto/cliente, solo de marcadores
     estructurales genericos de plantilla Rockwell ("ID code:", "Page N of
     N", "Rockwell Automation... All Rights Reserved").
Ninguno de los dos fixes acepta citas semanticamente similares ni relaja el
umbral fuzzy (FUZZY_THRESHOLD sigue en 0.93) -- ambos son, igual que la
normalizacion previa de comillas/guiones, remocion deterministica de ruido
de formato, no de contenido.
Relevancia tematica (heuristica lexica):
  - score bajo -> flag RELEVANCE_REVIEW_REQUIRED (nunca auto-rechazo, P6).

Adaptacion vs el texto original del plan (ver
factory/docs/W5v2_FASE0_INVENTARIO.md §4): el chunk real que produce
build_page_chunks() en chunked_engine.py usa el campo 'text', no
'source_text' -- match_citation/verify_llm_output leen chunk['text']."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import yaml as _yaml

FUZZY_THRESHOLD = 0.93
RELEVANCE_THRESHOLD = 0.15  # calibrable tras Golden Dataset (Fase 4)

PASS, FAIL, NOT_VERIFIABLE = "PASS", "FAIL", "NOT_VERIFIABLE"

REQUIREMENT_TERMS_PATH = Path(__file__).parent / "requirement_terms.yaml"

# W5.6: membrete de pagina de plantilla Rockwell, acotado (sin DOTALL sin
# cota -- cada segmento tiene un limite de longitud explicito para que la
# regex nunca pueda "comerse" contenido real arbitrariamente largo).
# Generico a marcadores estructurales de plantilla (ID code / Page N of N /
# Rockwell Automation... All Rights Reserved), no al nombre de un proyecto o
# cliente especifico.
_PAGE_FURNITURE_RE = re.compile(
    r"project:\s*.{0,120}?"
    r"functional specification for the .{0,120}?"
    r"id code:\s*\S+.{0,60}?page\s+\d+\s+of\s+\d+\s*"
    r"©\s*\d{4}\s*rockwell automation,?\s*inc\.?\s*all rights reserved\S*"
    r"(?:\s*/\s*author:\s*[^\n]*)?\s*"
    r"(?:this function implements the following user requirement\(s\)\s*)?",
    re.IGNORECASE | re.DOTALL,
)


def _strip_page_furniture(text: str) -> str:
    return _PAGE_FURNITURE_RE.sub(" ", text or "")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = _strip_page_furniture(text)
    text = re.sub(r"[\s ]+", " ", text)
    text = re.sub(r"[‐-―]", "-", text)
    text = re.sub(r"[‘’“”]", "'", text)
    return text.strip()


def match_citation(quote: str, source_text: str):
    """-> (match_type, score)  con match_type en
    exact|normalized|despaced|fuzzy|not_found"""
    if not (quote or "").strip():
        return ("not_found", 0.0)
    if quote in (source_text or ""):
        return ("exact", 1.0)
    nq, ns = _normalize(quote), _normalize(source_text)
    if nq and nq in ns:
        return ("normalized", 1.0)
    # W5.6: ignora TODO whitespace (no solo corridas) -- cubre espacios
    # espureos insertados a mitad de palabra por kerning del PDF. Sigue
    # siendo comparacion de caracteres literal (misma exigencia de anclaje
    # que "normalized"), solo indiferente a layout de espacios.
    nq_d, ns_d = nq.replace(" ", ""), ns.replace(" ", "")
    if nq_d and nq_d in ns_d:
        return ("despaced", 1.0)
    wlen = len(nq)
    if wlen == 0 or len(ns) < 10:
        return ("not_found", 0.0)
    step = max(1, wlen // 4)
    best = 0.0
    for i in range(0, max(1, len(ns) - wlen + 1), step):
        s = SequenceMatcher(None, nq, ns[i:i + wlen]).ratio()
        if s > best:
            best = s
            if best >= 0.99:
                break
    if best >= FUZZY_THRESHOLD:
        return ("fuzzy", best)
    return ("not_found", best)


def relevance_score(quote: str, requirement_terms: list) -> float:
    """Solapamiento lexico cita vs terminos del requisito. Heuristico.
    requirement_terms: lista de terminos del dominio de control del
    requisito (proviene de requirement_terms.yaml, catalogo -- no del LLM).
    -1.0 == no evaluable (sin cita o sin terminos definidos)."""
    nq = _normalize(quote)
    if not nq or not requirement_terms:
        return -1.0
    hits = sum(1 for t in requirement_terms if _normalize(t) in nq)
    return hits / len(requirement_terms)


@lru_cache(maxsize=1)
def _load_requirement_terms_file() -> dict:
    if not REQUIREMENT_TERMS_PATH.exists():
        return {}
    return _yaml.safe_load(REQUIREMENT_TERMS_PATH.read_text(encoding="utf-8")) or {}


def load_requirement_terms(requirement_id: str) -> list:
    """Requisito sin fila en requirement_terms.yaml -> lista vacia
    -> relevance_score devuelve -1.0 -> NOT_VERIFIABLE (fail-closed hacia
    revision, nunca hacia PASS silencioso ni hacia rechazo, P1/P6)."""
    return _load_requirement_terms_file().get(requirement_id, [])


@dataclass
class VerificationResult:
    status: str                      # verified | verified_with_deviation |
                                      # rejected_by_verifier | review_required
    checks: dict = field(default_factory=dict)
    review_flags: list = field(default_factory=list)
    rejection_reason: str = ""


def verify_llm_output(llm_output: dict, chunk: dict,
                       known_requirement_ids: set,
                       requirement_terms: list) -> VerificationResult:
    checks, flags, failures = {}, [], []

    # V4 — requisito conocido (demostrable)
    if llm_output.get("requirement_id") in known_requirement_ids:
        checks["requirement_known"] = PASS
    else:
        checks["requirement_known"] = FAIL
        failures.append("requirement_unknown")

    obs = llm_output.get("chunk_observation")
    quote = llm_output.get("evidence_quote", "")
    src = chunk.get("text", "")

    # V1 — cita (demostrable)
    if obs == "not_observed_in_chunk":
        if quote.strip():
            checks["citation"] = FAIL          # incoherencia: no observado pero cita
            failures.append("quote_present_on_not_observed")
        else:
            checks["citation"] = PASS
            checks["citation_match_type"] = "n/a"
    else:
        mtype, score = match_citation(quote, src)
        checks["citation_match_type"] = mtype
        checks["citation_score"] = round(score, 4)
        if mtype in ("exact", "normalized", "despaced"):
            checks["citation"] = PASS
        elif mtype == "fuzzy":
            checks["citation"] = PASS
            flags.append("CITATION_DEVIATION")
        else:
            checks["citation"] = FAIL
            failures.append("citation_not_found")

    # V2 — pagina (ternario)
    page = llm_output.get("evidence_page")
    ps, pe = chunk.get("page_start"), chunk.get("page_end")
    if obs == "not_observed_in_chunk":
        checks["page"] = "n/a"
    elif page is None or ps is None:
        checks["page"] = NOT_VERIFIABLE
        flags.append("PAGE_NOT_VERIFIABLE")
    elif ps <= page <= (pe or ps):
        checks["page"] = PASS
    else:
        checks["page"] = FAIL
        failures.append("page_out_of_range")

    # V5 — relevancia tematica (heuristica: solo flag, P6)
    if obs != "not_observed_in_chunk" and quote.strip():
        rscore = relevance_score(quote, requirement_terms)
        checks["relevance_score"] = round(rscore, 4)
        if rscore == -1.0:
            checks["relevance"] = NOT_VERIFIABLE
            flags.append("RELEVANCE_NOT_EVALUABLE")
        elif rscore < RELEVANCE_THRESHOLD:
            checks["relevance"] = NOT_VERIFIABLE
            flags.append("RELEVANCE_REVIEW_REQUIRED")
        else:
            checks["relevance"] = PASS

    # Resolucion de estado
    if failures:
        return VerificationResult("rejected_by_verifier", checks, flags,
                                   ",".join(failures))
    if "CITATION_DEVIATION" in flags:
        return VerificationResult("verified_with_deviation", checks, flags)
    if any(f in flags for f in ("RELEVANCE_REVIEW_REQUIRED",
                                 "PAGE_NOT_VERIFIABLE",
                                 "RELEVANCE_NOT_EVALUABLE")):
        return VerificationResult("review_required", checks, flags)
    return VerificationResult("verified", checks, flags)
