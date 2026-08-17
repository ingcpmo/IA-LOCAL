"""FASE M2 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`, "Contrato unico +
chunking por seccion") -- `build_page_chunks(structure=...)` respeta los
limites de seccion de nivel 1 declarados por
`document_structure_extractor` cuando `toc_anchored=True`, con fallback
identico al chunking por tamano de siempre cuando no hay Tabla de
Contenido parseable. Cero llamadas a LLM: todos los asserts son
mecanicos (substrings, longitudes, igualdad de listas).
"""
from pathlib import Path

import pytest

from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks
from factory.regulatory.document_structure_extractor import extract_structure

_RW0005 = (
    Path(__file__).resolve().parents[2]
    / "GMPAI" / "source" / "Rockwell" / "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
)


def _make_pages(*sections: list[str]) -> list[str]:
    """sections: cada arg es una lista de textos de pagina para una
    seccion sintetica; la primera linea de la primera pagina de cada
    seccion debe ser el encabezado real (ej. '1 Introduccion')."""
    pages: list[str] = []
    for sec in sections:
        pages.extend(sec)
    return pages


def test_structure_none_is_byte_identical_to_size_only_chunking():
    pages = [f"pagina {i} " + ("x" * 3000) for i in range(1, 6)]
    assert build_page_chunks(pages) == build_page_chunks(pages, structure=None)


def test_toc_anchored_false_falls_back_to_size_only_chunking():
    pages = [f"pagina {i} " + ("x" * 3000) for i in range(1, 6)]
    structure = {"toc_anchored": False, "secciones": [{"numero": "1", "titulo": "X", "pagina_inicio": 1}]}
    old = build_page_chunks(pages)
    new = build_page_chunks(pages, structure=structure)
    # mismas paginas por chunk que el chunking por tamano; solo se agregan
    # las claves aditivas section_numero/section_titulo=None
    assert [(c["page_start"], c["page_end"], c["text"]) for c in old] == \
           [(c["page_start"], c["page_end"], c["text"]) for c in new]
    assert all(c["section_numero"] is None for c in new)


def test_never_merges_two_level1_sections_into_one_chunk_even_if_they_fit():
    # 2 secciones cortas que juntas caben muy por debajo de max_chars
    pages = [
        "1 Introduction\ncontenido breve de introduccion",
        "2 Overview\ncontenido breve de overview",
    ]
    # Estructura construida a mano (equivalente a lo que produciria un
    # documento con Tabla de Contenido real) para aislar la propiedad de
    # chunking sin depender de fixtures externos -- la extraccion real de
    # toc_anchored ya esta cubierta en test_document_structure_extractor.py
    # y en el caso real RW-0005 mas abajo.
    structure = {
        "toc_anchored": True,
        "secciones": [
            {"numero": "1", "titulo": "Introduction", "pagina_inicio": 1},
            {"numero": "2", "titulo": "Overview", "pagina_inicio": 2},
        ],
    }
    chunks = build_page_chunks(pages, max_chars=6000, structure=structure)
    assert len(chunks) == 2
    assert chunks[0]["section_numero"] == "1"
    assert chunks[1]["section_numero"] == "2"
    assert "Overview" not in chunks[0]["text"] or "introduccion" not in chunks[1]["text"]
    assert "introduccion" in chunks[0]["text"]
    assert "overview" in chunks[1]["text"]


@pytest.mark.skipif(not _RW0005.exists(), reason="fixture RW-0005 no disponible en este entorno")
def test_p3_chunk_no_longer_mixes_unrelated_security_section():
    """Caso real del fixture 7P+2N: P3 (RW-0005, ANNEX11_17, UR3.3.6 Data
    retention, pagina 44 0-based) vivia en el mismo chunk que contenido de
    la seccion 'Security' (UR5.2.5, tabla 'Graphic Filename Security
    Code') bajo el chunking por tamano anterior -- verificado mecanicamente
    aqui contra el PDF real, no supuesto."""
    import pdfplumber

    with pdfplumber.open(_RW0005) as pdf:
        per_page_text = [(page.extract_text() or "") for page in pdf.pages]

    structure = extract_structure(per_page_text)
    assert structure["toc_anchored"] is True

    old_chunks = build_page_chunks(per_page_text)
    new_chunks = build_page_chunks(per_page_text, structure=structure)

    old_p3_chunk = next(c for c in old_chunks if c["page_start"] <= 45 <= c["page_end"])
    assert "UR3.3.6" in old_p3_chunk["text"]
    # regresion documentada: el chunking anterior SI mezclaba contenido de
    # Security (seccion 4) con el pasaje de retencion de Data (seccion 5)
    assert "UR5.2.5" in old_p3_chunk["text"]
    assert "Graphic Filename Security Code" in old_p3_chunk["text"]

    new_p3_chunk = next(c for c in new_chunks if c["page_start"] <= 45 <= c["page_end"])
    assert "UR3.3.6" in new_p3_chunk["text"]
    assert new_p3_chunk["section_numero"] == "5"
    assert new_p3_chunk["section_titulo"] == "Data"
    # la mezcla con la seccion no relacionada desaparece
    assert "UR5.2.5" not in new_p3_chunk["text"]
    assert "Graphic Filename Security Code" not in new_p3_chunk["text"]
    # el pasaje relacionado (misma seccion 'Data', Historian/Audit Trail,
    # P1/P5 del mismo fixture) sigue presente -- la fase no exige separar
    # contenido de la MISMA seccion, solo dejar de mezclar secciones no
    # relacionadas
    assert "Historian" in new_p3_chunk["text"]
