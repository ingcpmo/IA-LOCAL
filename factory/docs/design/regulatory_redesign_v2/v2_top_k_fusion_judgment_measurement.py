"""FASE V2 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`, "Medicion decisiva
de juicio requisito-centrico") -- mide AD-1 (1 llamada de JUICIO por
requisito, alimentada con el candidate pool top-k fusionado de M3) contra
las 8 triples unicas (documento, agente, requirement_id) del fixture
7P+2N. Autorizacion real: PILOT_EXECUTION-2026-022 (human_confirmed,
Cesar, 2026-08-17T16:34:49Z, confirma PILOT_EXECUTION-2026-021,
max_calls=25) + EMBED_EXECUTION-2026-002 (vigente, 44/60 consumidas antes
de esta corrida, 16 de margen -- se necesitan 8 consultas nuevas, cabe).

Reusa `judgment.run_judgment_batch` (R2, ya construido/probado, gated por
PILOT_EXECUTION) -- no `corpus_runner.run_corpus_batch(retrieval_mode=
'top_k_fusion')` (M3, gated por CORPUS_AUTHORIZATION -- esa es la corrida
FORMAL futura, no esta medicion diagnostica). Ambas rutas construyen el
mismo candidate pool via `judgment_candidate_pool.build_fusion_candidate_
pool()`, sin cambios."""
from __future__ import annotations

import json
from pathlib import Path

from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER
from factory.regulatory.corpus_runner import _resolve_document_path
from factory.regulatory.retrieval import judgment_candidate_pool as jcp
from factory.regulatory.retrieval.judgment import JudgmentUnit, expected_calls_for_unit, run_judgment_batch

_RUN_DIR = Path("/home/ing_cpmo/factory/regulatory/pilot_run/v2_top_k_fusion_20260817")
_CHECKPOINT_DIR = _RUN_DIR / "checkpoints"
_PROGRESS_FILE = _RUN_DIR / "progress.jsonl"
_RESULT_FILE = _RUN_DIR / "v2_result.json"

CALLS_ALREADY_USED_FOR_EMBED_AT_START = 0  # EMBED_EXECUTION-2026-004 (human_confirmed,
# Cesar, 2026-08-17T18:12:18Z, confirma EMBED_EXECUTION-2026-003, max_calls=10)
# -- instancia NUEVA, 0 consumidas. EMBED_EXECUTION-2026-002 (60/60, agotada
# por V1 + 2 intentos abortados de V2) queda sin tocar; el resolver de
# embed_runner selecciona automaticamente la instancia vigente mas reciente
# con presupuesto>0, que ahora es -004.

_K = 3  # ADR-V2-2 (2026-08-17, decision arquitectonica de Cesar): k=3 para
# la CAPA DE JUICIO, justificado por evidencia real de V1 (rank maximo
# medido entre los 7 positivos = 3, P7; ambos negativos ya fuera del top-5,
# luego tambien fuera del top-3) -- no reduce cobertura conocida. V1 (k=5,
# metrica de recuperacion pura, retrieval_recall_at_5=7/7) NO se re-mide ni
# se invalida: k=3 es una decision de costo de la capa de JUICIO,
# independiente de la metrica de recuperacion ya cerrada. 8 triples * k=3 =
# 24, cabe en el tope firmado de PILOT_EXECUTION-2026-022 (25).
#
# NOTA IMPORTANTE (correccion factual, 2026-08-17): la decision
# arquitectonica que autorizo este k=3 tambien afirmaba "EMBED_EXECUTION_
# NEW_REQUIRED=false (reuso del pool persistido de V1)". Verificado contra
# el codigo y el disco: NINGUN candidate pool fusionado (ranking real por
# requisito) quedo persistido en ninguna corrida anterior -- solo los
# EMBEDDINGS DE CHUNK (embedding_index/*.json, reutilizables sin costo) y
# el INDICE BM25 (retrieval_index/*.json) se persisten; el ranking
# fusionado se recalcula en cada llamada a build_fusion_candidate_pool(),
# y esa funcion SIEMPRE gasta 1 embedding de consulta nuevo (nunca
# cacheado, confirmado en V1 y en los dos intentos abortados de esta
# sesion). Con EMBED_EXECUTION-2026-002 en 60/60 (0 remanente), este
# script NO PUEDE construir ningun candidate pool -- ver
# docs_plan/V2_DISCREPANCY_REPORT_20260817_ADENDA.md para el detalle
# completo. Este archivo documenta el diseno correcto (k=3, agregacion ya
# existente via verify_sufficiency_aggregated -- chunked_engine.py:1860,
# sin cambios de codigo necesarios ahi) pero NO se ejecuta hasta que haya
# presupuesto de EMBED_EXECUTION real.

# document_id -> structure_aware para build_fusion_candidate_pool: RW-0005
# tiene toc_anchored=True (M2); RW-0011/RW-0012 caen al fallback identico
# al legacy (sin Tabla de Contenido) -- mismo criterio ya usado en V1.
_STRUCTURE_AWARE = {"RW-0005": True, "RW-0011": False, "RW-0012": False}
_DOCUMENT_TYPE = {"RW-0005": "FS", "RW-0011": "DS", "RW-0012": "DS"}

# (document_id, agent_id, requirement_id) -> etiqueta(s) del fixture que cubre
_TRIPLES: list[tuple[str, str, str, str]] = [
    ("RW-0005", "fda_part11_agent", "21_CFR_11.10(e)", "P1+N2"),
    ("RW-0005", "fda_part11_agent", "21_CFR_11.10(g)", "P2"),
    ("RW-0005", "eu_annex11_agent", "ANNEX11_17", "P3"),
    ("RW-0011", "alcoa_plus_agent", "ALCOA_ATTRIBUTABLE", "P4"),
    ("RW-0005", "alcoa_plus_agent", "ALCOA_CONTEMPORANEOUS", "P5"),
    ("RW-0011", "fda_cgmp_211_agent", "21_CFR_211.68(b)", "P6"),
    ("RW-0012", "fda_cgmp_211_agent", "21_CFR_211.68(b)", "P7"),
    ("RW-0005", "eu_annex11_agent", "ANNEX11_4", "N1"),
]


def main() -> dict:
    _RUN_DIR.mkdir(parents=True, exist_ok=True)
    calls_used_embed = CALLS_ALREADY_USED_FOR_EMBED_AT_START

    units: list[JudgmentUnit] = []
    build_log = []
    for document_id, agent_id, req_id, labels in _TRIPLES:
        _, document_sha256 = _resolve_document_path(document_id)
        pool = jcp.build_fusion_candidate_pool(
            document_id, document_sha256, req_id, k=_K,
            calls_already_used=calls_used_embed, structure_aware=_STRUCTURE_AWARE[document_id])
        calls_used_embed += 1
        units.append(JudgmentUnit(
            document_id=document_id, document_type=_DOCUMENT_TYPE[document_id],
            agent_id=agent_id, requirement_id=req_id, candidate_chunks=pool,
            selection_reason=f"V2 top_k_fusion -- fixture {labels}",
        ))
        build_log.append({
            "document_id": document_id, "agent_id": agent_id, "requirement_id": req_id,
            "labels": labels, "pool_size": len(pool),
            "expected_calls": expected_calls_for_unit(units[-1]),
        })

    total_expected = sum(b["expected_calls"] for b in build_log)
    if total_expected > 25:
        raise RuntimeError(
            f"expected_calls total ({total_expected}) excede max_calls=25 de "
            "PILOT_EXECUTION-2026-022 -- detener antes de gastar nada")

    summary = run_judgment_batch(
        units, provider=DEFAULT_PROVIDER, checkpoint_dir=_CHECKPOINT_DIR,
        progress_file=_PROGRESS_FILE)

    label_by_key = {(d, a, r): l for d, a, r, l in _TRIPLES}
    results = []
    for u, outcome in zip(units, summary.units):
        results.append({
            "labels": label_by_key[(u.document_id, u.agent_id, u.requirement_id)],
            "document_id": u.document_id, "requirement_id": u.requirement_id,
            "status": outcome.status, "run_id": outcome.run_id,
            "chunk_observation": outcome.chunk_observation, "conclusion": outcome.conclusion,
            "calls_made": outcome.calls_made_this_invocation, "error": outcome.error,
        })

    report = {
        "authorization": "PILOT_EXECUTION-2026-022 + EMBED_EXECUTION-2026-004",
        "build_log": build_log,
        "results": results,
        "stop_reason": summary.stop_reason,
        "total_calls_made": summary.total_calls_made,
        "total_wall_seconds": summary.total_wall_seconds,
        "selected_pilot_instance_id": summary.selected_pilot_instance_id,
        "total_embed_calls_used_this_run": calls_used_embed - CALLS_ALREADY_USED_FOR_EMBED_AT_START,
    }
    _RESULT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = main()
    print(json.dumps(report, indent=2, ensure_ascii=False))
