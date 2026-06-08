import glob
import os

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
CHROMA_FDA_COLLECTION = os.getenv("CHROMA_FDA_COLLECTION", "gmp_fda_regulations")
CHROMA_IQ_COLLECTION = os.getenv("CHROMA_IQ_COLLECTION", "gmp_iq_oq_pq")

_CHUNK_SIZE = 600
_CHUNK_OVERLAP = 80


def _get_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


def _split_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks on paragraph boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > chunk_size and current:
            chunks.append("\n\n".join(current))
            # overlap: keep last paragraph
            if overlap and current:
                current = [current[-1]]
                current_len = len(current[-1])
            else:
                current = []
                current_len = 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if len(c) >= 40]


def _extract_pdf_text(filepath: str) -> str:
    """Extract text from PDF using pypdf if available."""
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        return ""


def ingest_directory(directory: str, collection_name: str) -> int:
    """
    Ingest all .txt and .pdf files from directory into a ChromaDB collection.
    Returns total document count in collection after ingestion.
    """
    client = _get_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    txt_files = glob.glob(os.path.join(directory, "*.txt"))
    pdf_files = glob.glob(os.path.join(directory, "*.pdf"))
    all_files = sorted(txt_files + pdf_files)

    new_docs: list[str] = []
    new_ids: list[str] = []
    new_metas: list[dict] = []

    for filepath in all_files:
        filename = os.path.basename(filepath)
        if filepath.endswith(".pdf"):
            text = _extract_pdf_text(filepath)
        else:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

        if not text.strip():
            continue

        chunks = _split_text(text)
        for i, chunk in enumerate(chunks):
            doc_id = f"{filename}__chunk{i:04d}"
            new_docs.append(chunk)
            new_ids.append(doc_id)
            new_metas.append({"source": filename, "chunk": i, "directory": directory})

    if not new_docs:
        return collection.count()

    # Upsert in batches of 100 to avoid memory spikes
    batch = 100
    for start in range(0, len(new_docs), batch):
        collection.upsert(
            documents=new_docs[start : start + batch],
            ids=new_ids[start : start + batch],
            metadatas=new_metas[start : start + batch],
        )

    return collection.count()


def get_collection_stats() -> dict:
    try:
        client = _get_client()
        stats = {}
        collections = client.list_collections()
        total = 0
        for col_obj in collections:
            name = col_obj.name if hasattr(col_obj, "name") else str(col_obj)
            try:
                col = client.get_collection(name)
                count = col.count()
            except Exception:
                count = 0
            stats[name] = {"name": name, "count": count}
            total += count
        stats["_total"] = {"collections": len(collections), "total_chunks": total}
        return stats
    except Exception as exc:
        return {
            "fda_collection": {"name": CHROMA_FDA_COLLECTION, "count": 0, "error": str(exc)},
            "iq_collection": {"name": CHROMA_IQ_COLLECTION, "count": 0, "error": str(exc)},
        }


async def retrieve_context(
    question: str,
    n_results: int = 2,
    collection_name: str | None = None,
) -> list[str]:
    """Query one specific collection (if collection_name given) or the two defaults."""
    texts, _ = await retrieve_context_with_sources(question, n_results, collection_name)
    return texts


async def retrieve_context_with_sources(
    question: str,
    n_results: int = 2,
    collection_name: str | None = None,
) -> tuple[list[str], list[dict]]:
    """Same as retrieve_context but also returns source metadata per chunk."""
    try:
        client = _get_client()
        texts: list[str] = []
        sources: list[dict] = []
        if collection_name:
            names = [collection_name]
        else:
            names = [CHROMA_FDA_COLLECTION, CHROMA_IQ_COLLECTION]
        for name in names:
            try:
                col = client.get_collection(name)
                if col.count() == 0:
                    continue
                results = col.query(
                    query_texts=[question],
                    n_results=min(n_results, col.count()),
                    include=["documents", "metadatas"],
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                texts.extend(docs)
                for doc, meta in zip(docs, metas):
                    sources.append({
                        "file": meta.get("source", "unknown"),
                        "chunk": meta.get("chunk", 0),
                        "collection": name,
                        "text_preview": doc[:120],
                    })
            except Exception:
                continue
        return texts, sources
    except Exception:
        return [], []
