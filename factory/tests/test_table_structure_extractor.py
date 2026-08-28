"""Tests -- factory/regulatory/table_structure_extractor.py (V2, B1).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 9:
representación estructurada (headers/rows/roles) en vez de texto plano
concatenado. Regla dura: si un rol de columna es ambiguo se marca en
`columns_unmapped` -- NUNCA se inventa un rol.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory import table_structure_extractor as tse


def test_maps_known_headers_to_roles():
    headers = ["Parameter", "User", "Time", "Old Value", "New Value"]
    rows = [["Alarm HI", "OP01", "10:35", "100", "120"],
            ["Alarm LO", "OP02", "10:37", "20", "25"]]
    roles, unmapped = tse.map_column_roles(headers, rows)
    assert roles == {0: "parameter", 1: "actor", 2: "timestamp",
                     3: "old_value", 4: "new_value"}
    assert unmapped == []


def test_unknown_header_goes_to_unmapped_not_guessed():
    headers = ["Widget", "Frobnicator", "User"]
    rows = [["a", "b", "OP01"], ["c", "d", "OP02"]]
    roles, unmapped = tse.map_column_roles(headers, rows)
    assert roles == {2: "actor"}
    assert unmapped == [0, 1]          # no se les inventa rol


def test_data_fallback_only_for_timestamp_and_numeric():
    headers = ["", "", ""]
    rows = [["x", "10:35", "100"], ["y", "10:36", "200"], ["z", "10:37", "300"]]
    roles, unmapped = tse.map_column_roles(headers, rows)
    assert roles.get(1) == "timestamp"
    assert roles.get(2) == "numeric_value"
    assert 0 in unmapped               # texto ambiguo, sin rol


def test_extract_tables_from_pages_builds_table_objects():
    per_page_tables = [
        [],  # p.1 sin tablas
        [[["Parameter", "User", "Time"],
          ["Alarm HI", "OP01", "10:35"],
          ["Alarm LO", "OP02", "10:37"]]],  # p.2 una tabla
    ]
    tables = tse.extract_tables_from_pages(per_page_tables, "RW-0011")
    assert len(tables) == 1
    t = tables[0]
    assert t.pagina == 2
    assert t.headers == ["Parameter", "User", "Time"]
    assert len(t.rows) == 2
    assert t.column_roles == {0: "parameter", 1: "actor", 2: "timestamp"}
    assert t.provenance is not None
    assert t.provenance.document_id == "RW-0011"


def test_table_row_events_structure_and_provenance():
    per_page_tables = [
        [[["Parameter", "User", "Time", "Old Value", "New Value"],
          ["Alarm HI", "OP01", "10:35", "100", "120"]]],
    ]
    t = tse.extract_tables_from_pages(per_page_tables, "RW-0011")[0]
    events = tse.table_row_events(t)
    assert len(events) == 1
    ev = events[0]
    assert ev["parameter"] == "Alarm HI"
    assert ev["actor"] == "OP01"
    assert ev["timestamp"] == "10:35"
    assert ev["old_value"] == "100"
    assert ev["new_value"] == "120"
    assert ev["provenance"]["document_id"] == "RW-0011"
    assert ev["provenance"]["page"] == 1          # única entrada -> página 1 (page_offset=1)
    assert "Alarm HI | OP01" in ev["provenance"]["source_text"]


def test_unmapped_columns_preserved_in_extra_never_dropped():
    per_page_tables = [
        [[["Widget", "User"],
          ["gizmo-7", "OP01"]]],
    ]
    t = tse.extract_tables_from_pages(per_page_tables, "RW-0011")[0]
    ev = tse.table_row_events(t)[0]
    assert ev["actor"] == "OP01"
    assert ev["extra"]["Widget"] == "gizmo-7"   # no se pierde, no se le da rol


def test_single_row_grid_is_not_a_table():
    per_page_tables = [[[["just", "one", "row"]]]]
    assert tse.extract_tables_from_pages(per_page_tables, "RW-0011") == []


def test_real_rockwell_sat_pdf_if_available():
    """Si el corpus real está disponible en este entorno, extrae tablas de
    un SAT real y verifica que produce objetos Table con provenance. Se
    skippea limpio si el PDF no está (mismo patrón que test_r2_retrieval)."""
    import pytest
    candidates = [
        Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell/215115305-T-041 SAT3 Completed.pdf"),
        Path("/home/ing_cpmo/GMPAI/source/Rockwell/215115305-T-041 SAT3 Completed.pdf"),
    ]
    pdf = next((p for p in candidates if p.exists()), None)
    if pdf is None:
        pytest.skip("corpus real Rockwell no disponible en este entorno")
    tables = tse.extract_tables_from_pdf(pdf, "RW-SAT-041")
    # Un SAT completado tiene tablas de pasos/resultados: esperamos > 0.
    assert isinstance(tables, list)
    for t in tables:
        assert t.provenance is not None
        assert t.provenance.source_hash
        assert t.pagina >= 1
