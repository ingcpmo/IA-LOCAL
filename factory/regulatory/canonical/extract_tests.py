"""WP-D -- Extracción determinista de objetos `Test` del cuerpo de un protocolo
(SAT / OQ / IQ / PQ).  docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-D.

Cierra D-1 (sub-fallo estructural): `extract_document.py` no tenía etapa de
extracción de `Test`; `build_test()` no tenía llamadores de producción; el
linker del grafo (`_link_to_tests`, `verifies`) estaba correcto pero inanido.

ADITIVA y GOBERNADA POR FLAG: no corre salvo que el llamador lo pida
explícitamente (o `V2_TEST_EXTRACTION=1`). Con el flag OFF (default), la salida
del pipeline es idéntica a hoy -> NO cambia `EXTRACTION_VERSION` ni re-deriva los
stores. Activarlo es decisión de versión de Capa 9.

Sin LLM, sin red. Determinista. Heurística de líneas con guardas anti-falso-positivo.
"""
from __future__ import annotations

import re

from factory.regulatory.canonical.model import build_test

# Tipos de documento cuyo cuerpo contiene casos de prueba.
TEST_DOC_TYPES = frozenset({"SAT", "OQ", "IQ", "PQ"})

# Identificador de caso de prueba al INICIO de línea (o tras tab / '|').
_TESTID_RE = re.compile(
    r"""^\s*(?:[|\t]\s*)?
        (?P<id>
            (?:SAT|OQ|IQ|PQ)[\s\-]?\d{1,4}[A-Za-z]?      # SAT-042, OQ 7
          | TC[\s\-]?\d{1,4}[A-Za-z]?                      # TC-12
          | Test\s+Case\s+\d{1,4}[A-Za-z]?                 # Test Case 5
          | (?:Test\s+)?Step\s+\d{1,3}(?:\.\d{1,3}){0,3}  # Step 5.2.3
        )
        \s*[:.\)\-–]?\s+(?P<rest>\S.*)$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Referencias a requisitos que un test puede citar (feed de `verifies`).
_REQREF_RE = re.compile(
    r"\bUR[S]?[\s\-]?\d+(?:\.\d+){0,3}[a-z]?\b"
    r"|\bF\d{1,2}\.\d{2}\b"
    r"|\b(?:URS[\s\-])?[A-Z]{2,6}[\s\-][A-Z]{2,5}[\s\-]\d{2,5}[a-z]?\b"
    r"|\b\d{1,2}\s*CFR\s*\d{2,3}\.\d{1,3}\([a-z]\)",
    re.IGNORECASE,
)

# Token de resultado -- señal fuerte de "esto es un caso de prueba ejecutado".
_RESULT_RE = re.compile(
    r"\b(?:PASS(?:ED)?|FAIL(?:ED)?|P/F|N/?A|ACCEPT(?:ED)?|COMPLETE[D]?|"
    r"SATISFACTORY|CONFORME|APROBADO|RECHAZADO)\b",
    re.IGNORECASE,
)

# Guardas anti-falso-positivo: NO es un caso de prueba si la línea es...
_TOC_LEADER_RE = re.compile(r"\.{4,}\s*\d{1,4}\s*$")          # entrada de TOC (dot leaders)
_PAGINATION_RE = re.compile(r"^\s*(?:Test\s+)?Step\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE)
_HEADER_NOISE_RE = re.compile(
    r"^\s*(?:page\s+\d+|revision|document\s+no|confidential|uncontrolled)\b", re.IGNORECASE)

_MIN_DESC = 18            # descripción mínima si no hay resultado ni req-ref
_MAX_TESTS_PER_DOC = 4000  # tope defensivo


def _norm_id(raw: str) -> str:
    return re.sub(r"\s+", "-", raw.strip()).upper().replace("--", "-")


def looks_like_test_line(line: str) -> tuple[str, str] | None:
    """Devuelve (identificador, descripcion) si la línea es un caso de prueba
    plausible; None en caso contrario. Determinista."""
    if not line or _TOC_LEADER_RE.search(line) or _PAGINATION_RE.match(line):
        return None
    if _HEADER_NOISE_RE.match(line):
        return None
    m = _TESTID_RE.match(line)
    if not m:
        return None
    ident = _norm_id(m.group("id"))
    rest = m.group("rest").strip()
    has_result = bool(_RESULT_RE.search(line))
    has_reqref = bool(_REQREF_RE.search(rest))
    # exige AL MENOS una señal de sustancia: resultado, o cita de requisito,
    # o una descripción no trivial. Un "Step 3" pelado NO es un test.
    if not (has_result or has_reqref or len(rest) >= _MIN_DESC):
        return None
    return ident, rest


def extract_tests_for_document(document_id: str, per_page_text: list[str],
                               doc_type: str) -> list:
    """Una lista de `Test` (modelo canónico) para un documento de protocolo.
    Vacía si `doc_type` no es de prueba. Dedup por identificador (primera
    aparición gana). Provenance por página."""
    if (doc_type or "").upper() not in TEST_DOC_TYPES:
        return []
    out: list = []
    seen: set[str] = set()
    for pidx, ptext in enumerate(per_page_text or [], start=1):
        for raw in (ptext or "").splitlines():
            parsed = looks_like_test_line(raw)
            if not parsed:
                continue
            ident, desc = parsed
            if ident in seen:
                continue
            seen.add(ident)
            result = None
            rm = _RESULT_RE.search(raw)
            if rm:
                result = rm.group(0).upper()
            req_ids = sorted({m.group(0).strip() for m in _REQREF_RE.finditer(desc)})
            out.append(build_test(
                document_id=document_id, pagina=pidx, identificador=ident,
                descripcion=desc[:400], resultado=result,
                verifies_requirement_ids=req_ids, source_text=raw.strip()[:400],
            ))
            if len(out) >= _MAX_TESTS_PER_DOC:
                return out
    return out
