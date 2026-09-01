"""
Fase 4 (`factory/docs/document_remediation_evolution/DOCUMENT_REMEDIATION_SPEC.md`
§2, `IMPLEMENTATION_ROADMAP.md`) — representación intermedia con estructura
preservada: `{secciones: [{numero, titulo, pagina_inicio, parrafos: [...]}],
...}`. NO existe hoy en el pipeline de `chunked_engine.py`, que aplana
deliberadamente todo a texto plano por chunk (correcto para el LLM,
insuficiente para regenerar un documento candidato completo).

Extrae SOLO secciones de nivel 1 (numeración secuencial entera 1, 2, 3...
-- las que aparecen en la tabla de Contenido del documento real, ej.
"1 Introduction", "2 Project Overview"). Las subsecciones sin numeración
propia en el texto extraído (ej. "Purpose", "Scope" bajo "1 Introduction")
quedan como parte de los párrafos de su sección de nivel 1 -- distinguirlas
exigiría metadata de estilo/fuente que `pdfplumber.extract_text()` no
preserva; declarado como límite conocido, no resuelto aquí (deuda para una
iteración futura si se necesita jerarquía más profunda).

**Anclaje por Tabla de Contenido (corrige un falso positivo real
encontrado al correr el gate contra el FS_v1.2.pdf real de Rockwell)**:
la primera heurística (solo `^(N)\\s+(Titulo)$` con N secuencial y Title
Case) producía 19 "secciones" en vez de las 8 reales -- después de la
sección 3 real ("Functions and Processes"), tablas internas del documento
(ej. "HMI Screen List": filas "1 Overview", "2 Monitoring"...) reinician
una numeración secuencial de tabla que por coincidencia también empieza
en el entero esperado por el extractor y también es Title Case, así que
la heurística de una sola señal las confundía con secciones reales.
Corrección: se extrae primero la Tabla de Contenido real del documento
(página con encabezado "Contents", entradas con líder de puntos
`título .... página`) y se usa como lista blanca -- una línea del cuerpo
solo se acepta como encabezado de sección N si su título coincide
(normalizado, case-insensitive) con el título que la propia Tabla de
Contenido declara para la sección N. Si el documento no tiene una Tabla
de Contenido parseable, se degrada a la heurística original de una sola
señal (Title Case + secuencia), y el resultado se marca
`toc_anchored: false` para que quede explícito que la extracción es menos
confiable en ese caso -- fail-visible, no fail-silent.

Reutiliza `pdfplumber`, el mismo extractor ya usado y verificado para las
3 fuentes regulatorias de `sources/registry.json` -- no se reinventa un
extractor nuevo.
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADING_RE = re.compile(r"^(\d{1,2})\.?\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90})$")
_TOC_ENTRY_RE = re.compile(
    r"^(\d{1,2})\.?\s+([A-Za-z][A-Za-z0-9 ,;:/\-\(\)'\.]{1,90}?)\s*\.{3,}\s*[\d ]+$"
)
_DOT_LEADER = "...."
_CONNECTOR_WORDS = {"and", "of", "for", "the", "to", "in", "on", "a", "an", "or", "with"}


def _is_title_case(titulo: str) -> bool:
    words = titulo.split()
    if not words:
        return False
    for w in words:
        core = w.strip(",;:()'.")
        if not core:
            continue
        if core.lower() in _CONNECTOR_WORDS:
            continue
        if not core[0].isupper():
            return False
    return True


def _normalize_titulo(titulo: str) -> str:
    return " ".join(titulo.split()).strip(" .").lower()


def _extract_toc_level1(per_page_text: list[str]) -> dict[int, str]:
    """Escanea todas las páginas buscando entradas de Tabla de Contenido
    de nivel 1 (con líder de puntos), en secuencia estricta 1, 2, 3...
    Devuelve {} si no encuentra una secuencia parseable -- nunca inventa
    una Tabla de Contenido que no está."""
    toc: dict[int, str] = {}
    expected = 1
    for text in per_page_text:
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = _TOC_ENTRY_RE.match(line)
            if not m:
                continue
            numero = int(m.group(1))
            if numero != expected:
                continue
            titulo = m.group(2).strip()
            if not _is_title_case(titulo):
                continue
            toc[numero] = titulo
            expected += 1
    return toc


def _match_heading(
    line: str, expected_next: int, toc: dict[int, str]
) -> tuple[str, str] | None:
    line = line.strip()
    if not line or _DOT_LEADER in line:
        return None
    m = _HEADING_RE.match(line)
    if not m:
        return None
    if int(m.group(1)) != expected_next:
        return None
    titulo = m.group(2).strip()
    if not _is_title_case(titulo):
        return None
    if toc:
        toc_titulo = toc.get(expected_next)
        if toc_titulo is None or _normalize_titulo(titulo) != _normalize_titulo(toc_titulo):
            return None
    return m.group(1), titulo


def extract_structure(per_page_text: list[str]) -> dict:
    """per_page_text: texto plano por página (ej. de
    pdfplumber.PdfReader / la misma extracción usada en
    tools/run_validation_evidence.py). 1-indexado internamente para
    'pagina_inicio' (primera página real = 1)."""
    toc = _extract_toc_level1(per_page_text)
    secciones: list[dict] = []
    texto_previo_a_primera_seccion: list[str] = []
    current: dict | None = None
    expected_next = 1

    for page_num, text in enumerate(per_page_text, start=1):
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            matched = _match_heading(line, expected_next, toc)
            if matched:
                numero, titulo = matched
                current = {
                    "numero": numero, "titulo": titulo,
                    "pagina_inicio": page_num, "parrafos": [],
                }
                secciones.append(current)
                expected_next += 1
                continue
            if current is not None:
                current["parrafos"].append(line)
            else:
                texto_previo_a_primera_seccion.append(line)

    return {
        "total_paginas": len(per_page_text),
        "secciones": secciones,
        "texto_previo_a_primera_seccion": texto_previo_a_primera_seccion,
        "toc_anchored": bool(toc),
    }


def extract_structure_from_pdf(pdf_path: Path) -> dict:
    """Extrae directamente de un PDF real via pdfplumber (mismo extractor
    ya usado para sources/registry.json). El original NUNCA se modifica --
    solo lectura."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        per_page_text = [(page.extract_text() or "") for page in pdf.pages]
    result = extract_structure(per_page_text)
    result["document_path"] = str(pdf_path)
    return result
