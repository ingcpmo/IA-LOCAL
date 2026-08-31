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


# ── H-10: extracción de `Test` desde TABLAS estructuradas (docling / OCR) ──
#
# El SAT real (RW-0003) es 100 % imagen: sus casos de prueba viven en tablas de
# ejecución con firma de columnas del tipo
#   Item | Test Description | Expected Result | Actual Result | Deviation ID | Result (Pass/Fail) | Performed By
# `extract_tests_for_document` (texto lineal) no las recupera. Esta ruta consume
# las tablas que `docling` reconstruye y crea UN `Test` por escenario, SÓLO si la
# fila tiene evidencia suficiente para ser trazable. NUNCA inventa identificadores
# de requisito ni aristas. Determinista.

_TEST_TABLE_DESC_COL = re.compile(r"test\s*description|test\s*step|procedure|descripci[oó]n", re.I)
_TEST_TABLE_RESULT_COL = re.compile(
    r"expected\s*result|actual\s*result|result\s*\(?\s*pass|pass\s*/?\s*fail|resultado", re.I)
_MIN_SCENARIO_DESC = 15

#: Referencias de trazabilidad ESTRICTAS para tests de tabla OCR: sólo formas
#: inequívocas. NO se usa el patrón laxo de id formal (`[A-Z]{2,6} [A-Z]{2,5} \d+`)
#: porque casa ruido OCR de las columnas Result/Performed-By ("NA PASS 03").
_TABLE_REQREF_RE = re.compile(
    r"\bF\d{1,2}\.\d{2}\b"                                  # F05.05  (id de función)
    r"|\b\d{1,2}\s*CFR\s*\d{2,3}\.\d{1,3}\([a-z]\)"          # 21 CFR 11.10(e)
    r"|\bANNEX\s*11[_\s\-]?\d{1,2}\b"                        # ANNEX 11 17
    r"|\b[A-Z]{2,4}-[HS]R-\d{2,4}\b"                         # PCS-HR-001 (id de requisito)
    r"|\bUR[S]?[\s\-]?\d+(?:\.\d+){2,3}[a-z]?\b",            # UR3.3.1 (3+ niveles)
    re.IGNORECASE)


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _is_test_execution_table(headers: list[str]) -> bool:
    joined = " | ".join(_norm_header(h) for h in (headers or []))
    return bool(_TEST_TABLE_DESC_COL.search(joined) and _TEST_TABLE_RESULT_COL.search(joined))


def _col_index(headers: list[str], pat: re.Pattern) -> int | None:
    for i, h in enumerate(headers or []):
        if pat.search(_norm_header(h)):
            return i
    return None


def extract_tests_from_tables(document_id: str, tables: list[dict], doc_type: str) -> list:
    """`tables`: lista de dicts {page:int, headers:list[str], rows:list[list[str]]}
    (estructura de `docling`). Devuelve `Test` del modelo canónico, uno por
    escenario de prueba trazable. Provenance por página de la tabla.

    DO_NOT_CREATE_TEST cuando la tabla/escenario NO tiene:
      - una descripción de escenario sustantiva (>= 15 chars), Y
      - al menos una referencia de trazabilidad REAL (`_REQREF_RE`: F-id, sección,
        id de requisito, CFR/Annex) O un token de resultado (PASS/FAIL/...).
    """
    if (doc_type or "").upper() not in TEST_DOC_TYPES:
        return []
    out: list = []
    seen: set[str] = set()
    per_page_seq: dict[int, int] = {}
    for tbl in tables or []:
        headers = tbl.get("headers") or []
        rows = tbl.get("rows") or []
        page = int(tbl.get("page") or 1)
        if not _is_test_execution_table(headers) or not rows:
            continue
        desc_i = _col_index(headers, _TEST_TABLE_DESC_COL)
        res_i = _col_index(headers, _TEST_TABLE_RESULT_COL)
        # texto completo de la tabla -> refs reales (patrón ESTRICTO) + resultado
        cells = [str(c) for r in rows for c in r] + [str(h) for h in headers]
        blob = " ".join(cells)
        refs = sorted({re.sub(r"\s+", " ", m.group(0).strip())
                       for m in _TABLE_REQREF_RE.finditer(blob)})
        rmatch = _RESULT_RE.search(blob)
        result = rmatch.group(0).upper() if rmatch else None
        # descripción del escenario: primera celda sustantiva de la col de descripción
        scenario = ""
        for r in rows:
            if desc_i is not None and desc_i < len(r):
                cand = re.sub(r"\s+", " ", str(r[desc_i])).strip()
                if len(cand) >= _MIN_SCENARIO_DESC and not cand.lower().startswith(("performed by", "reviewed by")):
                    scenario = cand
                    break
        if len(scenario) < _MIN_SCENARIO_DESC:
            continue                                   # DO_NOT_CREATE_TEST
        if not refs and result is None:
            continue                                   # DO_NOT_CREATE_TEST (no trazable)
        seq = per_page_seq.get(page, 0) + 1
        per_page_seq[page] = seq
        ident = _norm_id(f"{(doc_type or 'SAT').upper()}-P{page:03d}-T{seq}")
        if ident in seen:
            continue
        seen.add(ident)
        # ancla: encabezado de la tabla + escenario + hasta 2 filas de paso
        anchor_rows = [" | ".join(str(c) for c in r) for r in rows[:3]]
        src = (" | ".join(str(h) for h in headers) + "\n" + scenario + "\n"
               + "\n".join(anchor_rows))[:400]
        out.append(build_test(
            document_id=document_id, pagina=page, identificador=ident,
            descripcion=scenario[:400], resultado=result,
            verifies_requirement_ids=refs, source_text=src,
        ))
        if len(out) >= _MAX_TESTS_PER_DOC:
            break
    return out
