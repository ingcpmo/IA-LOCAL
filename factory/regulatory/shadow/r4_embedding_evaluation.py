"""SHADOW · CF-6 v2.0 · R4 (evaluación de embeddings, autorizada 2026-09-05)
-- ¿la similitud coseno de embeddings distingue mejor que el solapamiento
léxico del Relevance Model, específicamente en los casos donde éste falla
por `n_matched=0`?

Autorización de Capa 9: "autoriza evaluar la integración de embeddings en el
Relevance Model" -- respuesta al hallazgo de que 2 falsos negativos reales
(`rec-8dd53df9991ab844`, `rec-b9f11dd9d3963b94`) tienen ratio=0.0/n_matched=0:
cero información compartida en superficie, ningún umbral sobre el mecanismo
léxico actual puede rescatarlos.

Gobernanza: `EMBED_EXECUTION-2026-012/-013` (propose/confirm vía
`governance_service`, familia SEPARADA de `PILOT_EXECUTION`, nunca la
autoriza). Modelo `nomic-embed-text:latest` (Ollama local, 100% local, sin
egress). NO usa `canonical_store` (vacío en este entorno) ni
`embed_runner.py`/`embed_index.py` (diseñados para indexar TODO el corpus
por chunks) -- llamadas ad hoc y acotadas vía `embed.embed_text()` sobre
texto YA existente: las citas ancladas L2 de los 82 pares REAL_ADJUDICATED
(`ORIGINAL_27` + `DIAGNOSTIC_NEAR_THRESHOLD_15` + `RANDOM_STRATIFIED_40`,
ya adjudicados por Capa 9) y el texto de los sub-criterios de
`decomposition.yaml` que targetean.

Esto es SOLO medición: NO modifica `relevance_model.py`, NO cambia ningún
threshold, NO altera el Composer. El resultado es un dato adicional para
que Capa 9 decida si autoriza integrar esta señal -- no una implementación
de esa integración.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria,
)
from factory.regulatory.retrieval.embed import cosine_similarity, embed_text

EMBED_EXECUTION_INSTANCE = "EMBED_EXECUTION-2026-013"
MAX_CALLS = 250
POS = {"RELEVANT", "PARTIALLY_RELEVANT"}


def _subcriterion_text(requirement_id: str, subcriterion_id: str | None) -> str:
    subs = get_subcriteria(requirement_id)
    if subcriterion_id:
        sc = next((s for s in subs if s["id"] == subcriterion_id), None)
        if sc:
            return f"{sc['text']} {sc.get('text_en', '')}".strip()
    # sin sub-criterio explícito: concatena todos (mismo criterio agregado
    # que requirement_centric.requirement_text_and_intent, sin LLM)
    return " ".join(f"{sc['text']} {sc.get('text_en', '')}" for sc in subs).strip()


def _load_all_82_pairs() -> list[dict]:
    """Reconstruye los 82 pares ya adjudicados (3 particiones), con su
    human_label preservado exacto -- nunca re-etiqueta."""
    pairs = []

    pool27 = json.loads(Path(
        "docs_plan/shadow_llm/CF6/MESA_DISENO_CF6_v2_R1_R3_20260904/"
        "03_ARTEFACTOS_R2_EJECUCION/CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json"
    ).read_text(encoding="utf-8"))
    for c in pool27["candidates"]:
        pairs.append({
            "partition": "ORIGINAL_27", "finding_record_id": c["finding_record_id"],
            "requirement_id": c["requirement_id"], "subcriterion_id": c["matched_subcriterion_id"],
            "quote": c["candidate_quote"], "human_label": c["human_label"],
            "lexical_ratio": c["weighted_ratio"], "lexical_n_matched": c["n_matched"],
            "lexical_state": c["model_relevance_state"],
        })

    pool294 = json.loads(Path(
        "docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json"
    ).read_text(encoding="utf-8"))
    by_id294 = {c["finding_record_id"]: c for c in pool294["all_candidates"]}

    diag = json.loads(Path(
        "docs_plan/shadow_llm/CF6/CF6_v2_R4_DIAGNOSTIC_15_ADJUDICATED.json"
    ).read_text(encoding="utf-8"))
    for r in diag["rows"]:
        c = by_id294[r["finding_record_id"]]
        pairs.append({
            "partition": "DIAGNOSTIC_NEAR_THRESHOLD_15", "finding_record_id": r["finding_record_id"],
            "requirement_id": c["requirement_id"], "subcriterion_id": c["matched_subcriterion_id"],
            "quote": c["candidate_quote"], "human_label": r["human"],
            "lexical_ratio": c["weighted_ratio"], "lexical_n_matched": c["n_matched"],
            "lexical_state": r["model"],
        })

    res40 = json.loads(Path(
        "docs_plan/shadow_llm/CF6/CF6_v2_R4_RANDOM_STRATIFIED_40_RESULT.json"
    ).read_text(encoding="utf-8"))
    for r in res40["rows"]:
        c = by_id294[r["finding_record_id"]]
        pairs.append({
            "partition": "RANDOM_STRATIFIED_40", "finding_record_id": r["finding_record_id"],
            "requirement_id": c["requirement_id"], "subcriterion_id": c["matched_subcriterion_id"],
            "quote": c["candidate_quote"], "human_label": r["human_label"],
            "lexical_ratio": c["weighted_ratio"], "lexical_n_matched": c["n_matched"],
            "lexical_state": r["model_relevance_state"],
        })

    return pairs


def run_embedding_evaluation(*, dry_run: bool = False) -> dict:
    pairs = _load_all_82_pairs()
    assert len(pairs) == 82, f"esperaba 82 pares, obtuve {len(pairs)}"

    # cachés para no re-embeber texto repetido (varias citas comparten
    # sub-criterio; algunas citas se repiten exactas entre pares)
    quote_cache: dict[str, list[float]] = {}
    subcrit_cache: dict[str, list[float]] = {}
    calls_made = 0

    def _embed_cached(text: str, cache: dict) -> list[float]:
        nonlocal calls_made
        if text in cache:
            return cache[text]
        if dry_run:
            vec = [0.0]
        else:
            calls_made_local = calls_made
            vec = embed_text(text)
            calls_made += 1
            if calls_made > MAX_CALLS:
                raise RuntimeError(f"excedido MAX_CALLS={MAX_CALLS} de {EMBED_EXECUTION_INSTANCE}")
        cache[text] = vec
        return vec

    rows = []
    for p in pairs:
        sc_key = f"{p['requirement_id']}::{p['subcriterion_id']}"
        sc_text = _subcriterion_text(p["requirement_id"], p["subcriterion_id"])
        q_vec = _embed_cached(p["quote"], quote_cache)
        sc_vec = _embed_cached(sc_text, subcrit_cache)
        sim = 0.0 if dry_run else cosine_similarity(q_vec, sc_vec)
        rows.append({**p, "sc_key": sc_key, "cosine_similarity": round(sim, 4)})

    return {
        "schema": "SHADOW_CF6_V2_R4_EMBEDDING_EVALUATION/v1",
        "embed_execution_instance": EMBED_EXECUTION_INSTANCE,
        "embedding_model": "nomic-embed-text:latest",
        "dry_run": dry_run,
        "n_pairs": len(rows),
        "n_unique_quotes_embedded": len(quote_cache),
        "n_unique_subcriteria_embedded": len(subcrit_cache),
        "embedding_calls_made": calls_made,
        "rows": rows,
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    out = run_embedding_evaluation(dry_run=("--dry-run" in sys.argv))
    Path("docs_plan/shadow_llm/CF6/CF6_v2_R4_EMBEDDING_EVALUATION.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "n_pairs", "n_unique_quotes_embedded", "n_unique_subcriteria_embedded",
        "embedding_calls_made")}, indent=1, ensure_ascii=False))
