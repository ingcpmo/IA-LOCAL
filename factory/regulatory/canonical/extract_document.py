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


#: H-10 / D-4 -- umbral de "PDF imagen": si pdfplumber recupera < este nº de
#: caracteres promedio por página, el documento es escaneado y necesita OCR.
_IMAGE_PDF_CHARS_PER_PAGE = 8


def _per_page_text_pdfplumber(pdf_path: Path) -> list[str]:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def _looks_image_only(per_page: list[str]) -> bool:
    if not per_page:
        return False
    total = sum(len((t or "").strip()) for t in per_page)
    return (total / max(1, len(per_page))) < _IMAGE_PDF_CHARS_PER_PAGE


#: H-10 -- tamaño de lote para el OCR docling: acota el RSS pico (~3 GB/lote de
#: 24 pág vs ~9.3 GB para 204 pág de una vez, medido en H-9). El resultado
#: semántico es idéntico: cada página se procesa de forma independiente.
_DOCLING_BATCH_PAGES = 24


def _docling_converter():
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    # bug docling 2.123 + pydantic 2.10: hash de opciones con referencia circular
    try:  # pragma: no cover - defensivo
        import docling.utils.pipeline_cache as _pc
        import docling.document_converter as _dc
        _pc.create_pipeline_options_hash = lambda *a, **k: "h10-fixed"  # type: ignore
        _dc.create_pipeline_options_hash = lambda *a, **k: "h10-fixed"  # type: ignore
    except Exception:
        pass
    _assets = (Path(__file__).resolve().parents[2]
               / "regulatory/validation_v2/_h9_assets/docling")
    opts = PdfPipelineOptions()
    opts.do_ocr = True
    opts.do_table_structure = True
    opts.enable_remote_services = False
    if _assets.exists():
        opts.artifacts_path = str(_assets)
    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def _pdf_page_count(pdf_path: Path) -> int:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        return len(pdf.pages)


def _docling_content(pdf_path: Path) -> tuple[list[str], list[dict]]:
    """H-10 / D-4: backend OCR (docling, offline, `enable_remote_services=False`).
    Procesa el PDF **por lotes de páginas** (control de memoria) y libera cada
    lote antes del siguiente. Devuelve (texto_por_página, tablas_estructuradas).
    Cada tabla: {page, headers, rows}. Determinista (cada página independiente)."""
    import gc
    conv = _docling_converter()
    n_pages = _pdf_page_count(pdf_path)
    pages: dict[int, list[str]] = {}
    tables: list[dict] = []
    start = 1
    while start <= n_pages:
        end = min(start + _DOCLING_BATCH_PAGES - 1, n_pages)
        res = conv.convert(str(pdf_path), page_range=(start, end))
        doc = res.document
        for item, _level in doc.iterate_items():
            pno = None
            for pr in (getattr(item, "prov", None) or []):
                pno = getattr(pr, "page_no", None)
                if pno is not None:
                    break
            pno = int(pno or start)
            if type(item).__name__ == "TableItem":
                try:
                    df = item.export_to_dataframe(doc)
                    headers = [str(c) for c in df.columns]
                    rows = [[("" if v is None else str(v)) for v in r]
                            for r in df.itertuples(index=False, name=None)]
                    tables.append({"page": pno, "headers": headers, "rows": rows})
                except Exception:  # noqa: BLE001 - tabla no exportable se salta
                    pass
                continue
            txt = getattr(item, "text", None)
            if txt:
                pages.setdefault(pno, []).append(txt)
        del res, doc
        gc.collect()
        start = end + 1
    n = max([*pages.keys(), *[t["page"] for t in tables], 0])
    per_page = ["\n".join(pages.get(i, [])) for i in range(1, n + 1)]
    return per_page, tables


def _per_page_text(pdf_path: Path, *, ocr: bool | None = None) -> list[str]:
    """pdfplumber por defecto (el anclaje por TOC depende de su layout de
    dot-leaders). Si `ocr=True` y pdfplumber no recupera texto (PDF imagen),
    cae al backend OCR gobernado por D-4 (docling). Solo lectura."""
    per_page = _per_page_text_pdfplumber(pdf_path)
    if ocr and _looks_image_only(per_page):
        return _docling_content(pdf_path)[0]
    return per_page


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
                     extract_tests: bool | None = None,
                     ocr: bool | None = None) -> ExtractionResult:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # H-10: si `ocr=True` y el PDF es imagen, docling da texto Y tablas
    # estructuradas (por lotes, control de memoria). Si no, ruta pdfplumber.
    _ocr_tables: list[dict] = []
    _pp_pdfplumber = _per_page_text_pdfplumber(pdf_path)
    if ocr and _looks_image_only(_pp_pdfplumber):
        per_page, _ocr_tables = _docling_content(pdf_path)
    else:
        per_page = _pp_pdfplumber
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

        # H-10: tablas estructuradas recuperadas por docling (PDF imagen) -> se
        # persisten como `Table` canónicas con provenance por página + roles
        # semánticos de columna deterministas (mismo mapeo que pdfplumber).
        if _ocr_tables:
            from factory.regulatory.canonical.model import build_table as _bt
            from factory.regulatory.table_structure_extractor import map_column_roles as _mcr
            for _t in _ocr_tables:
                try:
                    _h = list(_t.get("headers") or [])
                    _r = [list(x) for x in (_t.get("rows") or [])]
                    _roles, _unmapped = _mcr(_h, _r)
                    store.put(_bt(document_id=document_id, pagina=int(_t["page"]),
                                  headers=_h, rows=_r,
                                  column_roles=_roles, columns_unmapped=_unmapped))
                except Exception:  # noqa: BLE001
                    pass

        # WP-D: extracción de `Test` (solo si el flag está ON y el rol es de protocolo).
        if tests_on:
            tests = extract_tests_for_document(document_id, per_page, doc_type)
            # H-10: además, casos de prueba desde las TABLAS de ejecución del SAT
            # (docling). No sustituye la ruta de texto; la complementa.
            if _ocr_tables:
                from factory.regulatory.canonical.extract_tests import (
                    extract_tests_from_tables,
                )
                _seen_ids = {t.identificador for t in tests}
                for _tt in extract_tests_from_tables(document_id, _ocr_tables, doc_type):
                    if _tt.identificador not in _seen_ids:
                        tests.append(_tt)
                        _seen_ids.add(_tt.identificador)
            if tests:
                store.put_many(tests)
            store.set_meta("test_extraction", "tests-v1")

            # H-10: extracción de `SystemComponent` / `Actor` desde los claims YA
            # persistidos (mención literal + diccionario cerrado + provenance).
            # Mismo flag -> mismo salto gobernado de EXTRACTION_VERSION.
            from factory.regulatory.canonical.extract_entities import (
                extract_entities_for_document,
            )
            _claims_now = store.all("claim")
            _comps, _actors = extract_entities_for_document(document_id, _claims_now)
            if _comps:
                store.put_many(_comps)
            if _actors:
                store.put_many(_actors)
            store.set_meta("entity_extraction", "tests-v1")

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
