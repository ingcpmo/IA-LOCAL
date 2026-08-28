"""Extracción ESTRUCTURADA de tablas (V2, B1) —
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 9.

Hoy `pdfplumber.extract_text()` aplana las tablas a texto concatenado y
`build_page_chunks` las re-concatena: una fila
`"Alarm HI | OP01 | 10:35 | 100 | 120"` llega al LLM como texto corrido
sin roles de columna. Esto NO es la causa raíz del recall (R4 probó que
aislar la tabla a mano no cambia el juicio del 7B) pero sí es pérdida de
información estructural que los agentes FUNCTIONAL/TECHNICAL necesitan
(listas de I/O, tablas de alarmas, matrices de trazabilidad, parámetros
de SAT).

B1 es 100% determinista: `pdfplumber.extract_tables()` (ya dependencia
del proyecto) + heurística de mapeo columna→rol por nombre de header y
tipo de dato. Si el rol es ambiguo, la columna se marca en
`columns_unmapped` — NUNCA se inventa un rol. La variante opcional con 1
llamada LLM local corta de clasificación de headers se documenta pero
NO se implementa aquí.

El PDF original es de solo lectura, nunca se modifica.
"""
from __future__ import annotations

import re
from pathlib import Path

from factory.regulatory.canonical.model import Table, build_table

#: Sinónimos de header -> rol semántico. Comparación normalizada
#: (lower, sin signos). Orden: el primero que casa gana.
_HEADER_ROLE_SYNONYMS: list[tuple[str, tuple[str, ...]]] = [
    ("actor", ("user", "usuario", "operator", "operador", "performed by", "realizado por",
               "signed by", "firmado por", "responsible", "responsable", "who", "quien")),
    ("timestamp", ("timestamp", "time", "hora", "fecha", "date", "date/time", "datetime",
                   "date and time", "fecha y hora", "when", "cuando")),
    ("old_value", ("old value", "valor previo", "previous value", "valor anterior",
                   "from", "de", "before", "antes", "original value")),
    ("new_value", ("new value", "valor nuevo", "nuevo valor", "to", "a", "after", "despues",
                   "changed to", "modified value")),
    ("action", ("action", "accion", "event", "evento", "activity", "actividad",
                "change", "cambio", "operation", "operacion", "description", "descripcion")),
    ("parameter", ("parameter", "parametro", "tag", "point", "punto", "signal", "senal",
                   "attribute", "atributo", "field", "campo", "item", "name", "nombre")),
    ("requirement_ref", ("requirement", "requisito", "req id", "req", "ur", "urs ref",
                         "user requirement", "spec ref", "trace")),
    ("test_ref", ("test", "prueba", "test id", "test case", "caso de prueba", "step", "paso")),
    ("result", ("result", "resultado", "pass/fail", "status", "estado", "outcome", "verdict")),
    ("comment", ("comment", "comentario", "note", "nota", "remarks", "observaciones")),
]

_NUM_RE = re.compile(r"^-?\d+([.,]\d+)?$")
_TIME_RE = re.compile(
    r"^\s*(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}([ T]\d{1,2}:\d{2}(:\d{2})?)?|\d{1,2}:\d{2}(:\d{2})?)\s*$"
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 /]", "", (s or "").strip().lower())


def _role_from_header(header: str) -> str | None:
    h = _norm(header)
    if not h:
        return None
    for role, syns in _HEADER_ROLE_SYNONYMS:
        for syn in syns:
            if syn == h or re.search(rf"\b{re.escape(syn)}\b", h):
                return role
    return None


def _column_values(rows: list[list[str]], col: int) -> list[str]:
    out = []
    for r in rows:
        if col < len(r) and (r[col] or "").strip():
            out.append(r[col].strip())
    return out


def _role_from_data(values: list[str]) -> str | None:
    """Solo se usa como respaldo cuando el header no resolvió, y solo
    para tipos inequívocos (timestamp / valor numérico). Nunca decide
    roles semánticos ambiguos como actor/parameter por los datos."""
    if not values:
        return None
    if all(_TIME_RE.match(v) for v in values):
        return "timestamp"
    if len(values) >= 3 and all(_NUM_RE.match(v) for v in values):
        return "numeric_value"
    return None


def map_column_roles(headers: list[str], rows: list[list[str]]) -> tuple[dict, list[int]]:
    """-> ({col_index: rol}, [col_index sin resolver]).

    Determinista. Header primero; dato como respaldo solo para
    timestamp/numeric. Un rol semántico (actor/old_value/new_value/...)
    solo se asigna si el HEADER lo dice — nunca se adivina de los datos.
    """
    roles: dict = {}
    unmapped: list[int] = []
    for i, h in enumerate(headers):
        role = _role_from_header(h)
        if role is None:
            role = _role_from_data(_column_values(rows, i))
        if role is None:
            unmapped.append(i)
        else:
            roles[i] = role
    return roles, unmapped


def _clean_cell(v) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def _looks_like_header(row: list[str]) -> bool:
    cells = [c for c in row if c]
    if len(cells) < 2:
        return False
    # Un header típico: pocas celdas numéricas, celdas cortas.
    numeric = sum(1 for c in cells if _NUM_RE.match(c))
    return numeric <= len(cells) // 3 and all(len(c) <= 60 for c in cells)


def extract_tables_from_pages(per_page_tables: list[list[list[list]]], document_id: str,
                              *, page_offset: int = 1) -> list[Table]:
    """`per_page_tables[i]` = lista de tablas de la página i (0-based);
    cada tabla = lista de filas; cada fila = lista de celdas crudas (tal
    como las devuelve `pdfplumber.Page.extract_tables()`).

    `page_offset` (default 1): número de página real de la primera
    entrada (1-indexado, consistente con `Provenance.page` y con
    `document_structure_extractor`).
    """
    out: list[Table] = []
    for page_idx, tables in enumerate(per_page_tables):
        pagina = page_idx + page_offset
        for raw in tables or []:
            grid = [[_clean_cell(c) for c in row] for row in raw if any(_clean_cell(c) for c in row)]
            if len(grid) < 2:
                continue  # una fila sola no es una tabla útil
            header_row = grid[0]
            body = grid[1:]
            if not _looks_like_header(header_row):
                # Sin header reconocible: se conserva la tabla con headers
                # sintéticos col_0..col_n (fail-visible, no se descarta).
                header_row = [f"col_{i}" for i in range(max(len(r) for r in grid))]
                body = grid
            roles, unmapped = map_column_roles(header_row, body)
            out.append(build_table(
                document_id=document_id, pagina=pagina,
                headers=header_row, rows=body,
                column_roles=roles, columns_unmapped=unmapped,
            ))
    return out


def extract_tables_from_pdf(pdf_path: Path, document_id: str) -> list[Table]:
    """Extrae directamente de un PDF real vía pdfplumber (mismo extractor
    ya usado y verificado para `sources/registry.json` y
    `document_structure_extractor`). El original NUNCA se modifica."""
    import pdfplumber

    per_page: list[list] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            try:
                per_page.append(page.extract_tables() or [])
            except Exception:  # noqa: BLE001 -- una página ilegible no aborta el documento
                per_page.append([])
    return extract_tables_from_pages(per_page, document_id)


def table_row_events(table: Table) -> list[dict]:
    """Convierte cada fila en un evento estructurado usando los roles ya
    mapeados. Solo emite las claves cuyo rol se resolvió; las columnas en
    `columns_unmapped` van a `extra` con su header literal — nunca se
    pierden, nunca se les asigna un rol inventado.

    Ejemplo:
      headers = ["Parameter","User","Time","Old","New"]  (roles resueltos)
      fila    = ["Alarm HI","OP01","10:35","100","120"]
      -> {"parameter":"Alarm HI","actor":"OP01","timestamp":"10:35",
          "old_value":"100","new_value":"120",
          "provenance":{document_id,page,table_id,source_text,source_hash}}
    """
    events: list[dict] = []
    inv = table.column_roles
    for r in table.rows:
        ev: dict = {}
        extra: dict = {}
        for i, cell in enumerate(r):
            if not cell:
                continue
            role = inv.get(i)
            if role:
                ev[role] = cell
            else:
                header = table.headers[i] if i < len(table.headers) else f"col_{i}"
                extra[header] = cell
        if not ev and not extra:
            continue
        if extra:
            ev["extra"] = extra
        row_text = " | ".join(str(c) for c in r)
        ev["provenance"] = {
            "document_id": table.document_id,
            "page": table.pagina,
            "table_id": table.table_id,
            "source_text": row_text,
        }
        events.append(ev)
    return events
