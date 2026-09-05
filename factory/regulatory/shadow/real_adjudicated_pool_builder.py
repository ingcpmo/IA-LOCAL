"""SHADOW · CF-6 v2.0 · R4 (ampliación autorizada 2026-09-05) — construcción
del pool expandido de `REAL_ADJUDICATED`.

Autorización de Capa 9: "autoriza ampliar REAL_ADJUDICATED antes de
recalibrar" (respuesta al hallazgo R4: el umbral óptimo hallado contra el
fixture SINTÉTICO, incluso su versión v2 más agresiva, queda por encima de
los `weighted_ratio` de los 2 únicos candidatos reales confirmados
`RELEVANT` en la muestra de 27 pares de R2 -- muestra insuficiente para
decidir nada).

Este módulo NO etiqueta nada -- solo construye el POOL de candidatos reales
(no sintéticos, no fabricados) para que Capa 9/QA lo etiquete. Fuente:
las 300 entradas reales de las 60 secciones DENTRO DE ALCANCE (con
`decomposition.yaml`) de las 66 del corpus L2 completo (`FINAL_GMP_CORPUS_
FINDINGS.json`, 457 findings) -- no solo las 7 secciones de la muestra
congelada de R2. CERO LLM: reutiliza `relevance_model.classify_entry()`
(sin modificarlo) sobre citas YA ANCLADAS en L2 (nunca texto inventado).

Los 27 pares ya adjudicados por Capa 9 en R2 preservan su `human_label`
exacto (nunca se re-etiquetan ni se reinterpretan); los ~273 restantes
quedan `human_label: null`, listos para adjudicación.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    has_decomposition,
)
from factory.regulatory.shadow import composer as _skel
from factory.regulatory.shadow import relevance_model as rm

_NO_REGULATION = _skel._NO_REGULATION
_NOT_ANALYZABLE = _skel._NOT_ANALYZABLE

_EXISTING_POOL_PATH = (
    "docs_plan/shadow_llm/CF6/MESA_DISENO_CF6_v2_R1_R3_20260904/"
    "03_ARTEFACTOS_R2_EJECUCION/CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json"
)


def _in_scope(section: dict) -> bool:
    reg = section.get("regulation") or ""
    if reg in (_NO_REGULATION, _NOT_ANALYZABLE):
        return False
    return has_decomposition(reg)


def build_expanded_pool(findings_path: str = "docs_plan/shadow_llm/FINAL_GMP_CORPUS_FINDINGS.json",
                        existing_pool_path: str = _EXISTING_POOL_PATH) -> dict:
    findings = json.loads(Path(findings_path).read_text(encoding="utf-8"))["findings"]
    skeleton = _skel.build_composer_skeleton(findings)

    existing_labels: dict[str, str] = {}
    if Path(existing_pool_path).is_file():
        existing = json.loads(Path(existing_pool_path).read_text(encoding="utf-8"))
        for c in existing["candidates"]:
            if c.get("human_label"):
                existing_labels[c["finding_record_id"]] = c["human_label"]

    pool = []
    n_in_scope_sections = 0
    for section in skeleton["sections"]:
        if not _in_scope(section):
            continue
        n_in_scope_sections += 1
        for entry in section["entries"]:
            rid = entry["finding_record_id"]
            entry_req = entry.get("requirement_id")
            # una entrada dentro de una sección en-alcance puede traer su
            # PROPIO requirement_id (hallazgo cross-domain / compuesto) sin
            # descomposición -- se filtra a nivel de entrada, no solo de
            # sección (fail-closed: nunca se le asume descomposición).
            if not entry_req or not has_decomposition(entry_req):
                continue
            v = rm.classify_entry(entry)
            pool.append({
                "section_id": section["section_id"], "document": section["document"],
                "requirement_id": entry_req, "finding_record_id": rid,
                "candidate_quote": entry.get("anchored_quote_l2"),
                "matched_subcriterion_id": v.matched_subcriterion_id,
                "n_matched": v.n_matched, "weighted_ratio": round(v.weighted_ratio, 4),
                "matched_terms": list(v.matched_terms),
                "model_relevance_state": v.relevance_state,
                "human_label": existing_labels.get(rid),
                "already_adjudicated_in_r2": rid in existing_labels,
            })

    n_preserved = sum(1 for p in pool if p["already_adjudicated_in_r2"])
    n_pending = len(pool) - n_preserved

    # subconjunto prioritario para etiquetado práctico: candidatos NO
    # adjudicados todavía, ordenados por cercanía al umbral actual (0.12) --
    # el mismo criterio de valor informativo usado en R2, ahora aplicado a
    # los ~273 nuevos, con diversidad de documento/requisito (máx. 3 por
    # combinación document×requirement_id para no concentrar la muestra).
    pending = [p for p in pool if not p["already_adjudicated_in_r2"]]
    pending.sort(key=lambda p: abs(p["weighted_ratio"] - 0.12))
    priority: list[dict] = []
    seen_combo: dict[str, int] = {}
    for p in pending:
        combo = f"{p['document']}::{p['requirement_id']}"
        if seen_combo.get(combo, 0) >= 3:
            continue
        seen_combo[combo] = seen_combo.get(combo, 0) + 1
        priority.append(p)
        if len(priority) >= 100:
            break

    return {
        "schema": "SHADOW_CF6_V2_R4_REAL_ADJUDICATED_EXPANDED_POOL/v1",
        "purpose": ("Ampliación de REAL_ADJUDICATED autorizada por Capa 9 (2026-09-05) -- "
                   "candidatos REALES (no sintéticos) de las 60 secciones en alcance del "
                   "corpus L2 completo (457 findings), no solo las 7 de la muestra de R2. "
                   "0 LLM: relevance_model.classify_entry() sobre citas ya ancladas."),
        "n_in_scope_sections": n_in_scope_sections,
        "n_candidates_total": len(pool),
        "n_already_adjudicated_preserved_from_r2": n_preserved,
        "n_pending_adjudication": n_pending,
        "priority_subset_for_labeling": {
            "n": len(priority),
            "selection_rule": ("no adjudicados todavía + ordenados por cercanía al umbral "
                              "actual (0.12) + máx. 3 por combinación documento×requisito "
                              "(diversidad, evita concentrar la muestra) -- sugerencia, "
                              "no una selección definitiva; Capa 9/QA decide el tamaño y "
                              "composición final"),
            "candidates": priority,
        },
        "all_candidates": pool,
    }


if __name__ == "__main__":  # pragma: no cover
    out = build_expanded_pool()
    Path("docs_plan/shadow_llm/CF6/CF6_v2_R4_REAL_ADJUDICATED_EXPANDED_POOL.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "n_in_scope_sections", "n_candidates_total", "n_already_adjudicated_preserved_from_r2",
        "n_pending_adjudication")}, indent=1, ensure_ascii=False))
    print("priority_subset n =", out["priority_subset_for_labeling"]["n"])
