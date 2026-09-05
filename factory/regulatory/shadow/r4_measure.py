"""SHADOW · CF-6 v2.0 · R4/E3-E4 — instrumentación de score + medición.

E3: el `score` (ratio ponderado, nº de términos, sub-criterio emparejado)
YA está expuesto por `relevance_model.classify()` desde R1
(`RelevanceVerdict.weighted_ratio/n_matched/matched_terms/
matched_subcriterion_id`) -- no requiere ningún cambio. Este módulo SOLO
LEE esos campos; en ningún punto reasigna `_RELEVANT_MIN_RATIO`,
`_PARTIAL_MIN_RATIO`, `_RELEVANT_MIN_MATCHED` ni `_PARTIAL_MIN_MATCHED` de
`relevance_model.py` -- el barrido de umbral de E4 es una sustitución
LOCAL, aplicada solo a las etiquetas calculadas aquí, nunca al módulo real.

E4: mide `relevance_model.classify()` (CONGELADO, `CONFIG_R4`) contra el
fixture congelado (E2) y contra `REAL_ADJUDICATED` (los 27 pares de R2, ya
adjudicados por Capa 9). Produce matrices de confusión por categoría/perfil,
y el `ACHIEVABLE_OPTIMUM`: el mejor (precisión, recall) alcanzable barriendo
el `ratio` YA EXISTENTE, sin tocar la fórmula. CERO LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.regulatory.shadow import relevance_model as rm

_POSITIVE_LABELS = {"RELEVANT", "PARTIALLY_RELEVANT"}
_RELEVANT_CATEGORIES = {"POSITIVE_CLEAR", "TECHNICAL_PARAPHRASE"}
_HARD_NEGATIVE_CATEGORY = "IRRELEVANT_SIMILAR_DOMAIN"

T_RECALL = 0.90
T_PRECISION = 0.80


def measure_fixture(fixture: dict) -> list[dict]:
    """Corre `relevance_model.classify()` (sin modificar) sobre cada par del
    fixture congelado. `subcriterion_id` se fija explícitamente al
    sub-criterio objetivo declarado por construcción (no se infiere)."""
    rows = []
    for p in fixture["pairs"]:
        v = rm.classify(quote_text=p["evidence_text"], requirement_id=p["target_requirement_id"],
                        subcriterion_id=p["target_subcriterion_id"])
        rows.append({
            "pair_id": p["pair_id"], "category": p["category"], "label": p["label"],
            "partition": p["partition"], "profile": p["requirement_shape_profile"],
            "requirement_id": p["target_requirement_id"],
            "model_state_frozen": v.relevance_state,
            "weighted_ratio": v.weighted_ratio, "n_matched": v.n_matched,
            "matched_terms": list(v.matched_terms),
        })
    return rows


def _is_positive_frozen(row: dict) -> bool:
    return row["model_state_frozen"] in _POSITIVE_LABELS


def _is_positive_at_threshold(row: dict, threshold: float, min_matched: int = 1) -> bool:
    """Sustitución LOCAL del umbral de ratio -- NUNCA se escribe de vuelta a
    relevance_model.py. `min_matched` se mantiene fijo (estructural, no es
    el parámetro que se barre)."""
    return row["n_matched"] >= min_matched and row["weighted_ratio"] >= threshold


def confusion_by(rows: list[dict], predicate) -> dict:
    tp = fp = fn = tn = 0
    for r in rows:
        ground_truth_positive = r["label"] in _POSITIVE_LABELS
        model_positive = predicate(r)
        if model_positive and ground_truth_positive:
            tp += 1
        elif model_positive and not ground_truth_positive:
            fp += 1
        elif not model_positive and ground_truth_positive:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "precision": precision, "recall": recall, "n": len(rows)}


def recall_on_relevant_categories(rows: list[dict], predicate) -> float | None:
    subset = [r for r in rows if r["category"] in _RELEVANT_CATEGORIES]
    tp = sum(1 for r in subset if predicate(r))
    return (tp / len(subset)) if subset else None


def correct_rejection_on_hard_negative(rows: list[dict], predicate) -> float | None:
    """'Precisión sobre irrelevante-pero-semánticamente-similar' (§5.2):
    fracción de esta categoría (ground truth 100% IRRELEVANT por
    construcción) que el modelo rechaza correctamente (no la deja entrar a
    relevant_evidence)."""
    subset = [r for r in rows if r["category"] == _HARD_NEGATIVE_CATEGORY]
    correct = sum(1 for r in subset if not predicate(r))
    return (correct / len(subset)) if subset else None


def sweep_achievable_optimum(rows: list[dict], partition: str) -> dict:
    """Barre el `weighted_ratio` YA EXISTENTE sobre CALIBRATION -- sin tocar
    la fórmula. Devuelve el mejor punto (recall, precisión-hard-negativo)
    y si algún umbral alcanza T_RECALL y T_PRECISION simultáneamente."""
    subset = [r for r in rows if r["partition"] == partition]
    candidate_thresholds = sorted({r["weighted_ratio"] for r in subset} | {0.0, 1.0})
    curve = []
    best_meets_both = None
    best_min = (-1.0, None)
    for t in candidate_thresholds:
        pred = lambda r, t=t: _is_positive_at_threshold(r, t)
        recall = recall_on_relevant_categories(subset, pred)
        precision = correct_rejection_on_hard_negative(subset, pred)
        point = {"threshold": t, "recall_on_relevant": recall, "precision_on_hard_negative": precision}
        curve.append(point)
        if recall is not None and precision is not None:
            if recall >= T_RECALL and precision >= T_PRECISION:
                if best_meets_both is None or t > best_meets_both["threshold"]:
                    best_meets_both = point
            m = min(recall, precision)
            if m > best_min[0]:
                best_min = (m, point)
    return {
        "partition": partition,
        "curve_n_points": len(curve),
        "curve": curve,
        "achieves_both_targets": best_meets_both is not None,
        "best_meeting_both_targets": best_meets_both,
        "best_balanced_point": best_min[1],
        "T_RECALL": T_RECALL, "T_PRECISION": T_PRECISION,
    }


def measure_real_adjudicated(pool_path: str | Path) -> dict:
    """Métricas sobre los 27 pares REAL_ADJUDICATED (R2, Capa 9) -- reportadas
    SIEMPRE por separado, nunca mezcladas con el fixture construido."""
    data = json.loads(Path(pool_path).read_text(encoding="utf-8"))
    rows = [{
        "label": c["human_label"], "model_state_frozen": c["model_relevance_state"],
        "weighted_ratio": c["weighted_ratio"], "n_matched": c["n_matched"],
        "category": "REAL_ADJUDICATED",
    } for c in data["candidates"]]
    conf = confusion_by(rows, _is_positive_frozen)
    return {"n_pairs": len(rows), "confusion_frozen_threshold": conf}


def run_r4_measurement(fixture_path: str | Path = "docs_plan/shadow_llm/CF6/CF6_v2_R4_FIXTURE.json",
                       pool_path: str | Path = (
                           "docs_plan/shadow_llm/CF6/MESA_DISENO_CF6_v2_R1_R3_20260904/"
                           "03_ARTEFACTOS_R2_EJECUCION/CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json")
                       ) -> dict:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    rows = measure_fixture(fixture)

    by_category = {}
    for cat in fixture["category_labels_by_construction"]:
        subset = [r for r in rows if r["category"] == cat]
        by_category[cat] = confusion_by(subset, _is_positive_frozen)

    by_profile = {}
    for profile in ("MANY_SHORT", "FEW_LONG"):
        subset = [r for r in rows if r["profile"] == profile]
        by_profile[profile] = confusion_by(subset, _is_positive_frozen)

    global_conf = confusion_by(rows, _is_positive_frozen)
    calibration_conf = confusion_by([r for r in rows if r["partition"] == "CALIBRATION"], _is_positive_frozen)
    heldout_conf = confusion_by([r for r in rows if r["partition"] == "HELDOUT"], _is_positive_frozen)

    optimum_calibration = sweep_achievable_optimum(rows, "CALIBRATION")
    # verificación en HELDOUT con el umbral que mejor equilibrio dio en CALIBRATION
    best_point = optimum_calibration["best_meeting_both_targets"] or optimum_calibration["best_balanced_point"]
    heldout_rows = [r for r in rows if r["partition"] == "HELDOUT"]
    heldout_at_best_threshold = None
    if best_point is not None:
        pred = lambda r, t=best_point["threshold"]: _is_positive_at_threshold(r, t)
        heldout_at_best_threshold = {
            "threshold_from_calibration": best_point["threshold"],
            "recall_on_relevant_heldout": recall_on_relevant_categories(heldout_rows, pred),
            "precision_on_hard_negative_heldout": correct_rejection_on_hard_negative(heldout_rows, pred),
        }

    real_adjudicated = measure_real_adjudicated(pool_path)

    return {
        "schema": "SHADOW_CF6_V2_R4_MEASUREMENT/v1",
        "fixture_hash": fixture["fixture_hash"],
        "n_pairs_measured": len(rows),
        "GLOBAL_CONFUSION_FROZEN_THRESHOLD": global_conf,
        "CALIBRATION_CONFUSION_FROZEN_THRESHOLD": calibration_conf,
        "HELDOUT_CONFUSION_FROZEN_THRESHOLD": heldout_conf,
        "BY_CATEGORY_FROZEN_THRESHOLD": by_category,
        "BY_PROFILE_FROZEN_THRESHOLD": by_profile,
        "ACHIEVABLE_OPTIMUM_CALIBRATION": optimum_calibration,
        "HELDOUT_VERIFICATION_AT_BEST_CALIBRATION_THRESHOLD": heldout_at_best_threshold,
        "REAL_ADJUDICATED": real_adjudicated,
        "rows": rows,
    }


if __name__ == "__main__":  # pragma: no cover
    out = run_r4_measurement()
    Path("docs_plan/shadow_llm/CF6/CF6_v2_R4_MEASUREMENT.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summary = {k: out[k] for k in (
        "fixture_hash", "n_pairs_measured", "GLOBAL_CONFUSION_FROZEN_THRESHOLD",
        "CALIBRATION_CONFUSION_FROZEN_THRESHOLD", "HELDOUT_CONFUSION_FROZEN_THRESHOLD",
        "BY_PROFILE_FROZEN_THRESHOLD", "HELDOUT_VERIFICATION_AT_BEST_CALIBRATION_THRESHOLD",
        "REAL_ADJUDICATED")}
    summary["achieves_both_targets_in_calibration"] = out["ACHIEVABLE_OPTIMUM_CALIBRATION"]["achieves_both_targets"]
    summary["best_meeting_both_targets"] = out["ACHIEVABLE_OPTIMUM_CALIBRATION"]["best_meeting_both_targets"]
    print(json.dumps(summary, indent=1, ensure_ascii=False))
