"""Orquestador de extracción del modelo canónico (V2, B1) —
docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B1.

Encadena, todo DETERMINISTA y de SOLO LECTURA sobre el PDF original:
  1. texto por página        -- pypdf (mismo extractor que retrieval/indexer.py)
  2. estructura de secciones -- document_structure_extractor.extract_structure (nivel-1, TOC anchor)
  3. tablas estructuradas    -- table_structure_extractor.extract_tables_from_pdf (pdfplumber)
  4. claims por sección      -- normalize_claims.extract_claims_for_section (heurística léxica)
  5. persistencia            -- CanonicalStore (SQLite local)

Sin llamadas LLM. Sin red. Sin gobernanza nueva. El PDF nunca se modifica.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from factory.regulatory import document_structure_extractor as dse
from factory.regulatory.canonical.model import (
    EXTRACTION_VERSION, Document, build_section, effective_extraction_version,
    test_extraction_enabled,
)
from factory.regulatory.canonical.extract_tests import extract_tests_for_document
from factory.regulatory.canonical.normalize_claims import extract_claims_for_section
from factory.regulatory.canonical.persistence import STORE_DIR, CanonicalStore
from factory.regulatory.table_structure_extractor import extract_tables_from_pdf

# Marcadores fuertes en el NOMBRE de archivo (deciden primero: un FS que
# cita user requirements no debe clasificarse como URS por el cuerpo).
_FILENAME_HINTS = [
    ("URS", ("urs", " urs_", "urs v", "user requirement spec", "user requirements spec")),
    ("FS", ("fs_v", " fs ", "func spec", "functional spec", "fds")),
    ("DS", ("design spec", " ds ", "sys_arch", "sys arch", "system architecture", "detailed design")),
    ("SAT", ("sat3", "sat ", " sat_", "site acceptance", "sat completed", "-sat")),
    ("OQ", (" oq ", "oq_", "oq protocol", "operational qualification")),
    ("IQ", (" iq ", "iq_", "iq protocol", "installation qualification")),
    ("PQ", (" pq ", "pq_", "performance qualification")),
    ("SOP", ("sop-", " sop ", "sop_", "standard operating procedure")),
]
# Marcadores en el CUERPO (respaldo, solo si el nombre no resolvió).
_BODY_HINTS = [
    ("URS", ("this user requirement specification", "urs document")),
    ("FS", ("functional specification for the", "this functional specification")),
    ("DS", ("design specification for the", "this design specification")),
    ("SAT", ("site acceptance test", "sat protocol", "test result", "expected result")),
    ("OQ", ("operational qualification protocol",)),
    ("IQ", ("installation qualification protocol",)),
]


def infer_document_type(filename: str, first_pages_text: str = "") -> str:
    fn = f" {filename.lower()} "
    for tipo, hints in _FILENAME_HINTS:
        if any(h in fn for h in hints):
            return tipo
    body = f" {first_pages_text[:4000].lower()} "
    for tipo, hints in _BODY_HINTS:
        if any(h in body for h in hints):
            return tipo
    return "OTHER"


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _per_page_text(pdf_path: Path) -> list[str]:
    """pdfplumber -- el MISMO extractor que espera
    `document_structure_extractor.extract_structure_from_pdf` (el anclaje
    por Tabla de Contenido depende del layout de dot-leaders que produce
    pdfplumber, distinto al de pypdf). Solo lectura."""
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


@dataclass
class ExtractionResult:
    document_id: str
    store_path: Path
    counts: dict
    toc_anchored: bool
    doc_type: str


def extract_document(pdf_path: str | Path, document_id: str, *,
                     tipo: str | None = None, cliente: str | None = None,
                     store_dir: Path = STORE_DIR,
                     extract_tests: bool | None = None) -> ExtractionResult:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    per_page = _per_page_text(pdf_path)
    n_paginas = len(per_page)
    first_text = "\n".join(per_page[:3])
    doc_type = tipo or infer_document_type(pdf_path.name, first_text)

    structure = dse.extract_structure(per_page)
    tables = extract_tables_from_pdf(pdf_path, document_id)

    # WP-D: etapa de extracción de `Test`. GOBERNADA POR FLAG -- OFF por default
    # => salida idéntica a hoy y `EXTRACTION_VERSION` sin cambio.
    tests_on = test_extraction_enabled(extract_tests)
    ext_ver = effective_extraction_version(extract_tests)

    doc = Document(
        document_id=document_id, sha256=_sha256_file(pdf_path), tipo=doc_type,
        titulo=_guess_title(pdf_path.name, first_text), n_paginas=n_paginas,
        extraction_version=ext_ver, cliente=cliente,
        archivo=str(pdf_path),
    )

    with CanonicalStore(document_id, store_dir=store_dir) as store:
        store.put(doc)
        store.set_meta("toc_anchored", structure.get("toc_anchored", False))
        store.set_meta("extraction_version", ext_ver)

        # Secciones + claims
        secciones = structure.get("secciones", [])
        section_ids: list[str] = []
        for i, sec in enumerate(secciones):
            pag_inicio = sec["pagina_inicio"]
            pag_fin = (secciones[i + 1]["pagina_inicio"] if i + 1 < len(secciones)
                       else n_paginas)
            section_text = "\n".join(sec.get("parrafos", []))
            s = build_section(
                document_id=document_id, numero=sec.get("numero"),
                titulo=sec.get("titulo"), pagina_inicio=pag_inicio,
                pagina_fin=max(pag_inicio, pag_fin),
                source_text=section_text[:400] or (sec.get("titulo") or ""),
            )
            store.put(s)
            section_ids.append(s.section_id)
            claims = extract_claims_for_section(
                document_id=document_id, pagina=pag_inicio,
                section_text=section_text, section_id=s.section_id,
                section_numero=sec.get("numero"), section_titulo=sec.get("titulo"),
            )
            store.put_many(claims)

        # Texto anterior a la primera sección: claims sin sección
        pre = structure.get("texto_previo_a_primera_seccion", [])
        if pre:
            pre_claims = extract_claims_for_section(
                document_id=document_id, pagina=1,
                section_text="\n".join(pre), section_id=None,
            )
            store.put_many(pre_claims)

        # Si el documento NO tiene secciones parseables, extraer claims
        # página por página para no perder todo el contenido (fail-visible).
        if not secciones:
            for pidx, ptext in enumerate(per_page, start=1):
                store.put_many(extract_claims_for_section(
                    document_id=document_id, pagina=pidx,
                    section_text=ptext, section_id=None,
                ))

        store.put_many(tables)

        # WP-D: extracción de `Test` (solo si el flag está ON y el rol es de protocolo).
        if tests_on:
            tests = extract_tests_for_document(document_id, per_page, doc_type)
            if tests:
                store.put_many(tests)
            store.set_meta("test_extraction", "tests-v1")

        counts = store.counts()

    return ExtractionResult(
        document_id=document_id, store_path=(store_dir / f"{document_id}.sqlite3"),
        counts=counts, toc_anchored=structure.get("toc_anchored", False),
        doc_type=doc_type,
    )


def _guess_title(filename: str, first_text: str) -> str:
    stem = Path(filename).stem
    for line in (first_text or "").splitlines():
        line = line.strip()
        if 8 <= len(line) <= 120 and re.search(r"[A-Za-z]", line) and not line.isupper():
            return line
    return stem
