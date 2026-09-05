"""SHADOW · CF-6 v2.0 · R4 (ampliación) — muestra REAL_ADJUDICATED estratificada
y aleatoria, congelada ANTES de cualquier adjudicación.

Instrucción de Capa 9 (2026-09-05): construir 30-50 candidatos del pool de
294 (`CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json`), excluyendo los 15 de
`DIAGNOSTIC_NEAR_THRESHOLD_SAMPLE` y los 27 ya adjudicados, estratificada por
`requirement_id`, semilla declarada, y **congelada** (hash) antes de mostrarla
para adjudicación -- el orden importa: congelar primero, adjudicar después,
para que no se pueda ajustar la muestra tras ver el resultado.

CERO LLM. Reutiliza el pool ya construido (sin recalcular verdicts).
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

SEED = 20260905
PER_GROUP_BEFORE_TRIM = 4
N_TARGET = 40


def build_stratified_sample(pool_path: str | Path, excluded_finding_record_ids: set,
                            seed: int = SEED, n_target: int = N_TARGET,
                            per_group: int = PER_GROUP_BEFORE_TRIM) -> list[dict]:
    pool = json.loads(Path(pool_path).read_text(encoding="utf-8"))
    pending = [c for c in pool["all_candidates"]
              if not c["already_adjudicated_in_r2"]
              and c["finding_record_id"] not in excluded_finding_record_ids]

    by_req: dict[str, list[dict]] = {}
    for c in pending:
        by_req.setdefault(c["requirement_id"], []).append(c)

    rnd = random.Random(seed)
    sample: list[dict] = []
    for rid in sorted(by_req):
        group = by_req[rid][:]
        rnd.shuffle(group)
        sample.extend(group[:per_group])

    rnd.shuffle(sample)
    return sample[:n_target]


def freeze(pool_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json",
          diagnostic_15_ids: tuple = (
              "rec-cb15e1c9d46388bd", "rec-41020224b0ac1d19", "rec-f7eff6b9be225492",
              "rec-bff2bcf00c3551c6", "rec-284aedafa8dddd56", "rec-3369a8711e5f16a3",
              "rec-814e1e0e05380e78", "rec-850828e07185d641", "rec-2bd352f6e733c687",
              "rec-5f59722c74597726", "rec-87279db34937bf9f", "rec-9b9b6b70c63a1f85",
              "rec-e44befac41382590", "rec-39b4c3e7f96aa8b3", "rec-870a752d32280cc4"),
          out_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_v2_R4_RANDOM_STRATIFIED_40.json",
          unblinded_out_path: str | Path = "/tmp/_r4_stratified40_unblinded.json",
          ) -> dict:
    pool = json.loads(Path(pool_path).read_text(encoding="utf-8"))
    sample = build_stratified_sample(pool_path, set(diagnostic_15_ids))

    req_ids = sorted({c["requirement_id"] for c in sample})
    docs = sorted({c["document"] for c in sample})

    blind = [{
        "finding_record_id": c["finding_record_id"], "document": c["document"],
        "requirement_id": c["requirement_id"], "matched_subcriterion_id": c["matched_subcriterion_id"],
        "candidate_quote": c["candidate_quote"], "human_label": None,
        "source_context_sufficient": None,
    } for c in sample]

    frozen = {
        "schema": "SHADOW_CF6_V2_R4_RANDOM_STRATIFIED_40/v1",
        "seed": SEED,
        "n": len(sample),
        "requirement_ids_covered": req_ids,
        "n_requirement_ids_covered": len(req_ids),
        "n_requirement_ids_total_in_decomposition_yaml": 20,
        "documents_covered": docs,
        "n_documents_covered": len(docs),
        "n_documents_total_in_corpus": 5,
        "exclusion": {
            "DIAGNOSTIC_NEAR_THRESHOLD_15": list(diagnostic_15_ids),
            "PREVIOUSLY_ADJUDICATED_27": pool["n_already_adjudicated_preserved_from_r2"],
        },
        "selection_rule": ("estratificado por requirement_id, hasta 4 candidatos aleatorios por "
                          "requirement_id (semilla declarada), recortado a 40 con una segunda "
                          "mezcla aleatoria (misma semilla) preservando cobertura de los 12 "
                          "requirement_id disponibles en el pool pendiente"),
        "status": "FROZEN_BEFORE_ADJUDICATION",
        "blind_candidates": blind,
    }
    blob = json.dumps(frozen, sort_keys=True, ensure_ascii=False)
    frozen["sample_hash"] = hashlib.sha256(blob.encode()).hexdigest()

    Path(out_path).write_text(json.dumps(frozen, indent=1, ensure_ascii=False), encoding="utf-8")
    # referencia NO ciega (predicciones del modelo) -- se guarda aparte, NUNCA se
    # muestra antes de la adjudicación; se usa solo para revelar/calcular después.
    Path(unblinded_out_path).write_text(
        json.dumps({"sample_hash": frozen["sample_hash"], "unblinded_reference": sample},
                  indent=1, ensure_ascii=False), encoding="utf-8")
    return frozen


if __name__ == "__main__":  # pragma: no cover
    f = freeze()
    print(json.dumps({k: f[k] for k in (
        "seed", "n", "requirement_ids_covered", "n_requirement_ids_covered",
        "documents_covered", "n_documents_covered", "sample_hash")}, indent=1, ensure_ascii=False))
