"""V1 (GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md, Fase M2+V1) -- medicion
real de retrieval_recall_at_5 con chunking por seccion (M2), reusando el
mismo instrumento ya productizado en R2.2/R2.3 (indexer/embed_runner/
judgment_candidate_pool/fusion), gobernado por EMBED_EXECUTION-2026-002
(vigente, human_confirmed, max_calls=60, 10 ya consumidas por el ledger
de factory_audit.jsonl -- ver reporte de auditoria antes de correr esto
de nuevo, calls_already_used debe reflejar el consumo REAL acumulado).

Ejecutar una sola vez con proposito de medicion (no es un test
permanente -- llama a Ollama real). Salida: JSON con rank real de cada
positivo/negativo del fixture 7P+2N bajo chunking por seccion (RW-0005)
+ chunking legacy sin cambios (RW-0011/RW-0012, toc_anchored=False,
fallback identico -- confirmado mecanicamente en M2, cero costo
adicional: reusa los embeddings ya persistidos bajo la clave legacy)."""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.retrieval import embed_index, indexer
from factory.regulatory.retrieval.embed_runner import run_embed_batch
from factory.regulatory.retrieval.judgment_candidate_pool import build_fusion_candidate_pool

_SOURCE_DIR = Path("/home/ing_cpmo/GMPAI/source/Rockwell")
_DOCS = {
    "RW-0005": _SOURCE_DIR / "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf",
    "RW-0011": _SOURCE_DIR / "MCCPDC EMS Control Block Narrative revB.pdf",
    "RW-0012": _SOURCE_DIR / "MCCPDC PCS Signal Interface Control Block Narrative.pdf",
}

# document_id -> structure_aware (solo RW-0005 tiene toc_anchored=True;
# RW-0011/RW-0012 caen al fallback identico al chunking legacy -- reusar
# la clave legacy ahi es correcto, no una aproximacion)
_STRUCTURE_AWARE = {"RW-0005": True, "RW-0011": False, "RW-0012": False}

# (document_id, req_id) -> lista de (label_del_fixture, pagina_objetivo_1indexada)
_CASES: dict[tuple[str, str], list[tuple[str, int]]] = {
    ("RW-0005", "21_CFR_11.10(e)"): [("P1", 46), ("N2", 4)],
    ("RW-0005", "21_CFR_11.10(g)"): [("P2", 40)],
    ("RW-0005", "ANNEX11_17"): [("P3", 45)],
    ("RW-0011", "ALCOA_ATTRIBUTABLE"): [("P4", 13)],
    ("RW-0005", "ALCOA_CONTEMPORANEOUS"): [("P5", 46)],
    ("RW-0011", "21_CFR_211.68(b)"): [("P6", 13)],
    ("RW-0012", "21_CFR_211.68(b)"): [("P7", 14)],
    ("RW-0005", "ANNEX11_4"): [("N1", 2)],
}

CALLS_ALREADY_USED_AT_START = 10  # ledger real, factory_audit.jsonl, 3 eventos previos (7+2+1)


def main() -> dict:
    calls_used = CALLS_ALREADY_USED_AT_START
    doc_sha = {}
    build_log = []

    for doc_id, path in _DOCS.items():
        idx = indexer.build_index(path, structure_aware=_STRUCTURE_AWARE[doc_id])
        doc_sha[doc_id] = idx["document_sha256"]
        build_log.append({
            "document_id": doc_id, "structure_aware": _STRUCTURE_AWARE[doc_id],
            "n_chunks": len(idx["chunks"]),
        })

    # embed cualquier chunk pendiente ANTES de pedir candidate pools (evita
    # gastar la llamada de query si el batch de chunks se corta por
    # HARD_STOP_CALLS a mitad de camino)
    for doc_id in _DOCS:
        summary = run_embed_batch(
            [doc_id], calls_already_used=calls_used, structure_aware=_STRUCTURE_AWARE[doc_id])
        calls_used += summary.total_calls_made
        build_log.append({
            "document_id": doc_id, "phase": "chunk_embedding",
            "calls_made": summary.total_calls_made, "stop_reason": summary.stop_reason,
            "cumulative_calls_used": calls_used,
        })
        if summary.stop_reason != "BATCH_COMPLETE":
            raise RuntimeError(f"HARD_STOP_CALLS embebiendo chunks de {doc_id} -- detener, "
                                f"reportar presupuesto agotado, no seguir")

    results = []
    for (doc_id, req_id), targets in _CASES.items():
        pool = build_fusion_candidate_pool(
            doc_id, doc_sha[doc_id], req_id, k=5, calls_already_used=calls_used,
            structure_aware=_STRUCTURE_AWARE[doc_id])
        calls_used += 1  # 1 llamada de query por par (document_id, req_id) unico
        top5_pages = [(c["page_start"], c["page_end"]) for c in pool[:5]]
        for label, target_page in targets:
            rank = next(
                (i for i, c in enumerate(pool, start=1)
                 if c["page_start"] <= target_page <= c["page_end"]),
                None,
            )
            results.append({
                "label": label, "document_id": doc_id, "req_id": req_id,
                "target_page_1indexed": target_page, "rank_in_fused_pool": rank,
                "in_top5": rank is not None and rank <= 5,
                "top5_pages": top5_pages,
            })

    positives = [r for r in results if r["label"].startswith("P")]
    negatives = [r for r in results if r["label"].startswith("N")]
    recall_at_5 = sum(1 for r in positives if r["in_top5"])
    negatives_rejected = sum(1 for r in negatives if not r["in_top5"])

    report = {
        "build_log": build_log,
        "cases": results,
        "retrieval_recall_at_5": f"{recall_at_5}/{len(positives)}",
        "negatives_rejected_at_5": f"{negatives_rejected}/{len(negatives)}",
        "total_calls_used_this_run": calls_used - CALLS_ALREADY_USED_AT_START,
        "cumulative_calls_used_against_authorization": calls_used,
        "authorization": "EMBED_EXECUTION-2026-002",
    }
    return report


if __name__ == "__main__":
    report = main()
    print(json.dumps(report, indent=2, ensure_ascii=False))
