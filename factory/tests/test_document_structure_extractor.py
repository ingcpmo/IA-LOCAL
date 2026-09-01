"""
Tests -- factory/regulatory/document_structure_extractor.py (Fase 4,
document_remediation_evolution).

Cubre el bug real encontrado al correr el gate contra el PDF real de
Rockwell (FS_v1.2): sin anclaje por Tabla de Contenido, una tabla interna
del documento con numeracion de fila secuencial ("1 Overview", "2
Monitoring"...) se confundia con secciones de nivel 1 reales, produciendo
19 "secciones" en vez de las 8 reales. El fix ancla contra la Tabla de
Contenido real del documento; sin TOC parseable, degrada a la heuristica
original y lo marca explicitamente (`toc_anchored=False`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory import document_structure_extractor as extractor

TOC_PAGE = (
    "Contents\n"
    "1 Introduction ..................................................... 7\n"
    "Purpose ........................................................... 7\n"
    "2 Project Overview ................................................. 9\n"
    "Scope ............................................................ 11\n"
    "3 Functions and Processes ......................................... 13\n"
)


def test_toc_anchored_extraction_ignores_table_false_positive():
    """Reproduce el bug real: una tabla con filas numeradas 1, 2 (que
    tambien son Title Case) aparece DESPUES de la seccion 3 real -- sin
    anclaje por TOC se confundirian con secciones 4 y 5."""
    per_page_text = [
        TOC_PAGE,
        "1 Introduction\nTexto de introduccion real.",
        "2 Project Overview\nTexto de overview real.",
        "3 Functions and Processes\n"
        "Number Screen Name\n"
        "1 Overview\n"
        "2 Monitoring\n"
        "Texto real de la seccion 3.",
    ]
    result = extractor.extract_structure(per_page_text)
    assert result["toc_anchored"] is True
    numeros = [s["numero"] for s in result["secciones"]]
    assert numeros == ["1", "2", "3"]
    assert "1 Overview" in result["secciones"][2]["parrafos"]
    assert "2 Monitoring" in result["secciones"][2]["parrafos"]


def test_heading_with_period_after_number_is_recognized():
    """Causa A (CALIFICACION_FINAL_CURRENT_ENGINE.md, continuacion 2026-08-20):
    plantillas tipo MAVERICK "Control Block Narrative" (RW-0011/RW-0012)
    numeran "1. OBJECTIVE" (punto entre el numero y el titulo), tanto en la
    Tabla de Contenido como en el cuerpo -- a diferencia de "1 Introduction"
    (sin punto) de los FS de Rockwell (RW-0005). Ambas formas deben
    reconocerse como el mismo tipo de encabezado de nivel 1, con titulos en
    MAYUSCULAS incluidos (ya soportado por _is_title_case, que solo exige
    mayuscula inicial por palabra)."""
    toc_page_con_punto = (
        "TABLE OF CONTENTS\n"
        "1. OBJECTIVE ................................................. 3\n"
        "2. TERMINOLOGY ............................................... 3\n"
        "3. INPUT CONSIDERATIONS ...................................... 3\n"
    )
    per_page_text = [
        toc_page_con_punto,
        "1. OBJECTIVE\nTexto real del objetivo.",
        "2. TERMINOLOGY\nTexto real de terminologia.",
        "3. INPUT CONSIDERATIONS\nTexto real de consideraciones de entrada.",
    ]
    result = extractor.extract_structure(per_page_text)
    assert result["toc_anchored"] is True
    numeros = [s["numero"] for s in result["secciones"]]
    titulos = [s["titulo"] for s in result["secciones"]]
    assert numeros == ["1", "2", "3"]
    assert titulos == ["OBJECTIVE", "TERMINOLOGY", "INPUT CONSIDERATIONS"]


def test_heading_with_period_does_not_match_subsection_numbers():
    """El punto opcional no debe ampliar el match a sub-secciones tipo
    "4.1 Titulo" -- el caracter inmediatamente despues del punto opcional
    debe seguir siendo espacio, y en "4.1" es un digito, nunca deberia
    tratarse como una repeticion de la seccion 4."""
    per_page_text = [
        "1. Objective\ntexto",
        "2. Description\n4.1 Process Description And Strategy Design\nmas texto de la subseccion",
    ]
    result = extractor.extract_structure(per_page_text)
    numeros = [s["numero"] for s in result["secciones"]]
    assert numeros == ["1", "2"]
    assert "4.1 Process Description And Strategy Design" in result["secciones"][1]["parrafos"]


def test_toc_anchored_rejects_title_mismatch():
    """Una linea con el numero secuencial correcto pero titulo distinto al
    de la TOC nunca se acepta como encabezado (aunque sea Title Case)."""
    per_page_text = [
        TOC_PAGE,
        "1 Introduction\ntexto",
        "2 Something Else Entirely\ntexto que no coincide con la TOC",
    ]
    result = extractor.extract_structure(per_page_text)
    numeros = [s["numero"] for s in result["secciones"]]
    assert numeros == ["1"]


def test_without_toc_degrades_to_heuristic_and_flags_it():
    """Sin una Tabla de Contenido parseable, usa la heuristica original
    (secuencia + Title Case) y lo declara explicitamente via
    toc_anchored=False -- nunca finge tener anclaje que no tiene."""
    per_page_text = ["1 Introduction\ntexto\n2 Project Overview\nmas texto"]
    result = extractor.extract_structure(per_page_text)
    assert result["toc_anchored"] is False
    numeros = [s["numero"] for s in result["secciones"]]
    assert numeros == ["1", "2"]


def test_toc_entries_never_become_headings_themselves():
    """Las propias lineas de la Tabla de Contenido (con lider de puntos)
    nunca se confunden con encabezados del cuerpo."""
    per_page_text = [TOC_PAGE]
    result = extractor.extract_structure(per_page_text)
    assert result["secciones"] == []
    assert result["toc_anchored"] is True


def test_texto_previo_a_primera_seccion_captura_portada():
    per_page_text = ["Functional Specification (FS)\nCustomer: Acme", "1 Introduction\ntexto"]
    result = extractor.extract_structure(per_page_text)
    assert "Functional Specification (FS)" in result["texto_previo_a_primera_seccion"]
    assert "Customer: Acme" in result["texto_previo_a_primera_seccion"]


def test_pagina_inicio_es_1_indexada_por_pagina_real():
    per_page_text = ["texto de portada", "1 Introduction\ntexto"]
    result = extractor.extract_structure(per_page_text)
    assert result["secciones"][0]["pagina_inicio"] == 2


def test_total_paginas_refleja_longitud_de_entrada():
    per_page_text = ["a", "b", "c"]
    result = extractor.extract_structure(per_page_text)
    assert result["total_paginas"] == 3


def test_extract_structure_from_pdf_never_writes_to_source():
    """El original nunca se modifica -- solo lectura via pdfplumber.open,
    nunca escritura de ningun tipo en este modulo."""
    src = Path(__file__).parent.parent / "regulatory" / "document_structure_extractor.py"
    text = src.read_text(encoding="utf-8")
    assert ".write_text(" not in text
    assert '"w")' not in text and "'w')" not in text


def test_real_fs_v1_2_pdf_reproduces_toc_section_numbering():
    """Gate de Fase 4 (`IMPLEMENTATION_ROADMAP.md`): la extraccion del
    FS_v1.2.pdf real reproduce la numeracion de secciones real declarada
    en su propia Tabla de Contenido -- 8 secciones de nivel 1, mismos
    titulos y mismas paginas de inicio verificados a ojo contra el PDF."""
    pdf_path = Path(
        "/home/ing_cpmo/GMPAI/source/Rockwell/"
        "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
    )
    if not pdf_path.exists():
        import pytest
        pytest.skip("PDF real no disponible en este entorno")

    result = extractor.extract_structure_from_pdf(pdf_path)
    assert result["toc_anchored"] is True
    assert result["total_paginas"] == 58

    expected = [
        ("1", "Introduction", 7),
        ("2", "Project Overview", 9),
        ("3", "Functions and Processes", 13),
        ("4", "Security", 40),
        ("5", "Data", 45),
        ("6", "External Interfaces", 49),
        ("7", "Non-Functional Attributes", 51),
        ("8", "Appendix", 54),
    ]
    actual = [
        (s["numero"], s["titulo"], s["pagina_inicio"]) for s in result["secciones"]
    ]
    assert actual == expected


# ── F1 (plan de reconciliación v1.1): regression guard de los 3 DS MAVERICK
#    "Control Block Narrative" (RW-0011/0012/0014), que numeran "1. OBJECTIVE"
#    con punto. Ground truth congelado en docs_plan/reconc/F1_ground_truth_headings.json
#    (GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39).
#    Con el extractor de HEAD (sin `\.?`) estos 3 documentos dan 0 secciones
#    (toc_anchored=False). Con el fix dan las 8 reales. ──────────────────────────
_DS_GROUND_TRUTH = {
    "MCCPDC EMS Control Block Narrative revB.pdf": [
        "OBJECTIVE", "TERMINOLOGY", "INPUT CONSIDERATIONS", "EMS CONTROL DESCRIPTION",
        "SOFTWARE PERMISSIVES", "INTER-NETWORK RELATIONSHIPS", "HARDWARE INTERLOCKS", "REFERENCES",
    ],
    "MCCPDC PCS Signal Interface Control Block Narrative.pdf": [
        "OBJECTIVE", "TERMINOLOGY", "INPUT CONSIDERATIONS",
        "PCS SIGNAL INTERFACE CONTROL DESCRIPTION",
        "SOFTWARE PERMISSIVES", "INTER-NETWORK RELATIONSHIPS", "HARDWARE INTERLOCKS", "REFERENCES",
    ],
    "MCCPDC WFI Control Block Narrative revB.pdf": [
        "OBJECTIVE", "TERMINOLOGY", "INPUT CONSIDERATIONS", "WFI CONTROL DESCRIPTION",
        "SOFTWARE PERMISSIVES", "INTER-NETWORK RELATIONSHIPS", "HARDWARE INTERLOCKS", "REFERENCES",
    ],
}


def _find_rockwell_pdf(fname: str):
    for base in (
        Path("GMPAI/source/Rockwell"),
        Path(__file__).parent.parent.parent / "GMPAI" / "source" / "Rockwell",
        Path("/home/ing_cpmo/GMPAI/source/Rockwell"),
    ):
        p = base / fname
        if p.exists():
            return p
    return None


def test_maverick_control_block_narratives_reproduce_8_level1_sections():
    import pytest
    checked = 0
    for fname, expected_titles in _DS_GROUND_TRUTH.items():
        pdf_path = _find_rockwell_pdf(fname)
        if pdf_path is None:
            continue
        checked += 1
        result = extractor.extract_structure_from_pdf(pdf_path)
        assert result["toc_anchored"] is True, f"{fname}: TOC no anclado (regresión del fix `\\.?`)"
        titulos = [s["titulo"] for s in result["secciones"]]
        numeros = [s["numero"] for s in result["secciones"]]
        assert numeros == [str(i) for i in range(1, 9)], f"{fname}: {numeros}"
        assert titulos == expected_titles, f"{fname}: {titulos}"
    if checked == 0:
        pytest.skip("PDFs DS de Rockwell no disponibles en este entorno")
