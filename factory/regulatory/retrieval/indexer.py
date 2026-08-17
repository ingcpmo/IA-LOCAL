"""R2 (docs_plan/R2_DESIGN_DETALLADO.md) -- indexación BM25 de un
documento objetivo. Reutiliza chunked_engine.build_page_chunks()
(page-aware, ya probado) -- nunca el chunking de knowledge/retriever.py
(pierde el número de página). Un índice por documento (document_sha256
como clave), nunca mezcla documentos distintos en un mismo índice.

Persistencia: JSON en disco, sin servidor/cliente adicional (a
diferencia de ChromaDB) -- factory/regulatory/retrieval_index/
(artefacto de runtime, regenerable desde el PDF real, gitignored --
mismo criterio que engines/gmpai_integrity/.checkpoints_*/)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks
from factory.regulatory.document_structure_extractor import extract_structure
from factory.regulatory.retrieval.bm25 import term_counts, tokenize

INDEX_DIR = Path(__file__).parent.parent / "retrieval_index"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def extract_per_page_text(pdf_path: Path) -> list[str]:
    """Mismo extractor ya usado en corpus_runner._default_extractor
    (pypdf, ya dependencia del proyecto, sin agregar nada nuevo) --
    solo lectura, el PDF original nunca se toca."""
    import pypdf

    reader = pypdf.PdfReader(str(pdf_path))
    return [(p.extract_text() or "") for p in reader.pages]


def _index_path(document_sha256: str, *, structure_aware: bool = False) -> Path:
    suffix = "__section_aware" if structure_aware else ""
    return INDEX_DIR / f"{document_sha256}{suffix}.json"


def build_index(pdf_path: Path, *, force: bool = False, structure_aware: bool = False) -> dict:
    """Indexa pdf_path si no existe ya un índice con el mismo
    document_sha256 (idempotente, determinista). force=True reindexa de
    todos modos (para tests o si el chunking cambió).

    structure_aware (Fase M2+V1, 2026-08-17, default False -- CERO cambio
    de comportamiento para todo llamador existente, incluido
    test_r2_retrieval.py que fija ranks exactos contra el chunking por
    tamaño de siempre): cuando True, calcula
    `document_structure_extractor.extract_structure()` sobre el MISMO
    `per_page_text` ya extraído aquí (pypdf, no pdfplumber -- el
    extractor de estructura es agnóstico al extractor de texto) y lo pasa
    a `build_page_chunks(structure=...)`. Se persiste bajo una clave de
    índice DISTINTA (`{sha256}__section_aware.json`) -- nunca pisa el
    índice legacy, para que ambos convivan mientras V1 (medición) no ha
    decidido si M3 (producción) adopta este modo."""
    document_sha256 = sha256_file(pdf_path)
    index_path = _index_path(document_sha256, structure_aware=structure_aware)
    if index_path.exists() and not force:
        return json.loads(index_path.read_text(encoding="utf-8"))

    per_page_text = extract_per_page_text(pdf_path)
    structure = extract_structure(per_page_text) if structure_aware else None
    page_chunks = build_page_chunks(per_page_text, structure=structure)

    indexed_chunks = []
    total_tokens = 0
    for pc in page_chunks:
        tokens = tokenize(pc["text"])
        indexed_chunks.append({
            "chunk_index": pc["chunk_index"],
            "page_start": pc["page_start"],
            "page_end": pc["page_end"],
            "has_overlap_prefix": pc["has_overlap_prefix"],
            "text": pc["text"],
            "term_counts": term_counts(pc["text"]),
            "token_count": len(tokens),
        })
        total_tokens += len(tokens)

    avg_chunk_len = (total_tokens / len(indexed_chunks)) if indexed_chunks else 0.0
    index = {
        "document_sha256": document_sha256,
        "document_path": str(pdf_path),
        "avg_chunk_len": avg_chunk_len,
        "chunks": indexed_chunks,
    }
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def load_index(document_sha256: str, *, structure_aware: bool = False) -> dict | None:
    index_path = _index_path(document_sha256, structure_aware=structure_aware)
    if not index_path.exists():
        return None
    return json.loads(index_path.read_text(encoding="utf-8"))
