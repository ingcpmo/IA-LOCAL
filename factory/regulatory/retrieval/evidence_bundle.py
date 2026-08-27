"""EvidenceBundle — candidate pool acotado POR SUB-CRITERIO (V2, B3).

docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 4.3:
el LLM de juicio NUNCA busca dentro de texto grande. Recibe un
`EvidenceBundle` -- ≤5 `Claim` candidatos + tablas relevantes, con
provenance completo -- y juzga sub-criterio por sub-criterio.

B3 es 100% DETERMINISTA: BM25 sobre los `Claim` del canonical_store (B1)
+ reranker léxico (rerank.py) contra el texto del sub-criterio firmado
(decomposition.yaml). Sin LLM, sin embeddings, sin descargas, sin
gobernanza nueva. El modo `fusion` (BM25 + embeddings) queda como
extensión posterior gobernada por EMBED_EXECUTION -- este módulo no lo
invoca.

La cita citable sigue siendo `Claim.source_text` literal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DIR, CanonicalStore
from factory.regulatory.requirement_catalog.requirement_catalog_loader import get_requirement
from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria, subcriterion_ref,
)
from factory.regulatory.retrieval.bm25 import (
    bm25_score, build_idf_table, term_counts, tokenize,
)
from factory.regulatory.retrieval.rerank import Reranker, lexical_score, rerank
from factory.regulatory.table_structure_extractor import Table, table_row_events

MAX_CANDIDATES = 5
_BM25_PREFILTER = 20          # cuántos candidatos BM25 pasan al reranker


@dataclass
class EvidenceBundle:
    document_id: str
    requirement_id: str
    subcriterion_id: str
    subcriterion_ref: str
    subcriterion_text: str
    candidate_claims: list[dict] = field(default_factory=list)   # {claim_id, source_text, normalized_statement, pagina, section_id, bm25_score, rerank_score, provenance}
    candidate_tables: list[dict] = field(default_factory=list)   # {table_id, pagina, matched_rows:[...], rerank_score, provenance}
    retrieval_mode: str = "bm25"

    def is_empty(self) -> bool:
        return not self.candidate_claims and not self.candidate_tables


def _claim_query(requirement_id: str, subcriterion_text: str) -> str:
    """Query determinista: texto del sub-criterio + términos de la cita
    normativa del requisito (contexto), nunca texto libre externo."""
    try:
        citation = (get_requirement(requirement_id).get("citation") or {}).get("citation_text", "")
    except Exception:  # noqa: BLE001 -- el catálogo tiene sus propios tests
        citation = ""
    return f"{subcriterion_text} {citation}".strip()


def _bm25_over_claims(claims: list[dict], query: str, k: int) -> list[dict]:
    if not claims:
        return []
    query_terms = tokenize(query)
    if not query_terms:
        return []
    indexed = []
    total_tokens = 0
    for c in claims:
        toks = tokenize(c.get("source_text", ""))
        indexed.append({**c, "term_counts": term_counts(c.get("source_text", "")),
                        "token_count": len(toks)})
        total_tokens += len(toks)
    avg_len = (total_tokens / len(indexed)) if indexed else 0.0
    corpus_idf = build_idf_table(query_terms, indexed)
    scored = [
        {**c, "bm25_score": bm25_score(query_terms, c, corpus_idf, avg_len)}
        for c in indexed
    ]
    scored.sort(key=lambda r: r["bm25_score"], reverse=True)
    return scored[:k]


def _tables_for_subcriterion(tables: list[dict], subcriterion_text: str, *,
                             min_score: float = 0.08, top_k: int = 2) -> list[dict]:
    """Tablas cuyo texto de filas solapa léxicamente con el sub-criterio.
    Reconstruye objetos Table livianos solo para `table_row_events`."""
    out = []
    for t in tables:
        try:
            tbl = Table(
                table_id=t["table_id"], document_id=t["document_id"], pagina=t["pagina"],
                headers=t.get("headers", []), rows=t.get("rows", []),
                merged_cells=t.get("merged_cells", []), caption=t.get("caption"),
                section_id=t.get("section_id"), column_roles=t.get("column_roles", {}),
                columns_unmapped=t.get("columns_unmapped", []),
                provenance=_prov_from_dict(t.get("provenance")),
            )
        except Exception:  # noqa: BLE001 -- provenance corrupta en una tabla no aborta el bundle
            continue
        events = table_row_events(tbl)
        row_texts = [e["provenance"]["source_text"] for e in events]
        blob = "\n".join(row_texts) + "\n" + " ".join(str(h) for h in tbl.headers)
        s = lexical_score(subcriterion_text, blob)
        if s >= min_score:
            matched = sorted(
                events, key=lambda e: lexical_score(subcriterion_text, e["provenance"]["source_text"]),
                reverse=True,
            )[:3]
            out.append({
                "table_id": tbl.table_id, "pagina": tbl.pagina,
                "matched_rows": matched, "rerank_score": round(s, 5),
                "provenance": t.get("provenance"),
            })
    out.sort(key=lambda r: r["rerank_score"], reverse=True)
    return out[:top_k]


def _prov_from_dict(d):
    from factory.regulatory.canonical.model import Provenance
    if not d:
        return None
    return Provenance(
        document_id=d["document_id"], page=d["page"], source_text=d["source_text"],
        source_hash=d["source_hash"], extraction_version=d["extraction_version"],
        section_numero=d.get("section_numero"), section_titulo=d.get("section_titulo"),
    )


def build_bundles_for_requirement(document_id: str, requirement_id: str, *,
                                  canon_dir=CANON_DIR,
                                  reranker: Reranker | None = None,
                                  max_candidates: int = MAX_CANDIDATES) -> list[EvidenceBundle]:
    """Un `EvidenceBundle` por sub-criterio del requisito (decomposition.yaml).
    Requiere que `document_id` tenga canonical_store poblado (B1)."""
    with CanonicalStore(document_id, store_dir=canon_dir) as store:
        claims = store.all("claim")
        tables = store.all("table_obj")

    bundles: list[EvidenceBundle] = []
    for sc in get_subcriteria(requirement_id):
        sc_text = sc["text"]
        query = _claim_query(requirement_id, sc_text)
        prefiltered = _bm25_over_claims(claims, query, _BM25_PREFILTER)
        # El reranker se corre contra el texto del sub-criterio MÁS el
        # contexto de la cita normativa (query): el sub-criterio solo
        # aporta términos propios (lo que diferencia los N sub-criterios
        # de un requisito), y la cita aporta el vocabulario normativo
        # -- importante cuando el documento fuente está en otro idioma que
        # el sub-criterio (limitación conocida del reranker léxico, ver
        # docs_plan). El anclaje final sigue siendo Claim.source_text.
        rerank_text = f"{sc_text} {query}"
        reranked = rerank(rerank_text, prefiltered, top_k=max_candidates,
                          text_key="source_text", reranker=reranker)
        cand_claims = [{
            "claim_id": c["claim_id"],
            "source_text": c["source_text"],
            "normalized_statement": c.get("normalized_statement", ""),
            "pagina": c.get("pagina"),
            "section_id": c.get("section_id"),
            "tipo": c.get("tipo"),
            "bm25_score": round(c.get("bm25_score", 0.0), 5),
            "rerank_score": c.get("rerank_score"),
            "rerank_method": c.get("rerank_method"),
            "provenance": c.get("provenance"),
        } for c in reranked]
        cand_tables = _tables_for_subcriterion(tables, f"{sc_text} {query}")
        bundles.append(EvidenceBundle(
            document_id=document_id, requirement_id=requirement_id,
            subcriterion_id=sc["id"], subcriterion_ref=subcriterion_ref(requirement_id, sc["id"]),
            subcriterion_text=sc_text, candidate_claims=cand_claims,
            candidate_tables=cand_tables, retrieval_mode="bm25",
        ))
    return bundles
