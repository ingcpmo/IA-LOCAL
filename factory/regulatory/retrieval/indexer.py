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


def _index_path(document_sha256: str) -> Path:
    return INDEX_DIR / f"{document_sha256}.json"


def build_index(pdf_path: Path, *, force: bool = False) -> dict:
    """Indexa pdf_path si no existe ya un índice con el mismo
    document_sha256 (idempotente, determinista). force=True reindexa de
    todos modos (para tests o si el chunking cambió)."""
    document_sha256 = sha256_file(pdf_path)
    index_path = _index_path(document_sha256)
    if index_path.exists() and not force:
        return json.loads(index_path.read_text(encoding="utf-8"))

    per_page_text = extract_per_page_text(pdf_path)
    page_chunks = build_page_chunks(per_page_text)

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


def load_index(document_sha256: str) -> dict | None:
    index_path = _index_path(document_sha256)
    if not index_path.exists():
        return None
    return json.loads(index_path.read_text(encoding="utf-8"))
