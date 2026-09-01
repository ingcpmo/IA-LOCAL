"""Bake-off de modelos para la capa semantica (FASE 2, aislado).

Corre `runner.assess` sobre una muestra ESTRATIFICADA de findings REALES de la
corrida postmejoras_v4 (r1) para los 8 subtipos, con dos modelos locales:
  - qwen2.5:7b-instruct-q4_K_M
  - mistral:7b-instruct-q4_K_M

Mide (seccion 4 del prompt de la Mesa de Diseno):
  quote_verification_pass_rate, unsupported_claims, fabricated_evidence (=0 por
  construccion tras el gate), contradictions_detected, INDETERMINATE/FAILED rate,
  schema_compliance, latency p50/p95, reproducibility_rate (N>=3 sub-muestra).
Verifica el caso de cache: RW-0012 p.5 y RW-0014 p.5 -> una sola inferencia.

NO commitea nada. Escribe resultados a bakeoff_results/ (gitignored).
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc.runner import assess, _cache_key
from factory.prototypes.semantic_hybrid_poc.context_composer import REQUIRED_ELEMENTS

RUN_DIR = Path("factory/regulatory/pilot_run/postmejoras_v4_20260831/postmejoras_v4_20260831_r1")
OUT_DIR = Path("factory/prototypes/semantic_hybrid_poc/bakeoff_results")
MODELS = ["qwen2.5:7b-instruct-q4_K_M", "mistral:7b-instruct-q4_K_M"]

TARGET_SUBTYPES = [
    "AUTHORITY_CHECK_GAP", "ACCESS_CONTROL_GAP", "BACKUP_RECOVERY_GAP",
    "AUDIT_TRAIL_DESIGN_GAP", "AUDIT_TRAIL_INTEGRITY_GAP", "ALCOA_ATTRIBUTABLE_GAP",
    "REGULATORY_INCONCLUSIVE", "REQUIREMENT_NOT_TESTED",
]
PER_SUBTYPE = 2                 # tamano de estrato
REPRO_N = 3                     # repeticiones para reproducibility_rate
REPRO_SUBSAMPLE = 3            # cuantos findings se repiten


def _normalize(f: dict) -> dict:
    g = dict(f)
    g.setdefault("finding_class", f.get("class") or f.get("finding_class") or "Finding")
    return g


def _load_findings() -> list[dict]:
    out = []
    for name in ("technical_findings.json", "regulatory_findings.json"):
        p = RUN_DIR / name
        if p.exists():
            out.extend(json.loads(p.read_text()))
    return out


def _stratify(findings: list[dict]) -> tuple[list[dict], dict]:
    by_sub: dict[str, list[dict]] = {}
    for f in findings:
        by_sub.setdefault(f.get("subtype"), []).append(f)
    sample, coverage = [], {}
    for sub in TARGET_SUBTYPES:
        pool = sorted(by_sub.get(sub, []), key=lambda x: x.get("finding_id") or "")
        take = pool[:PER_SUBTYPE]
        coverage[sub] = {"available": len(pool), "sampled": len(take)}
        sample.extend(_normalize(x) for x in take)
    return sample, coverage


def _metrics(records: list[dict]) -> dict:
    n = len(records)
    completed = [r for r in records if r["assessment_status"] == "COMPLETED"]
    failed = [r for r in records if r["assessment_status"] == "FAILED"]
    indet = [r for r in records if r["assessment_status"] == "INDETERMINATE"]
    confirms_absence = [r for r in records if r["assessment_status"] == "CONFIRMS_ABSENCE"]
    lat = sorted(r["wall_time_s"] for r in records if r.get("wall_time_s") is not None)
    def _pct(xs, q):
        if not xs:
            return None
        k = min(len(xs) - 1, int(round(q * (len(xs) - 1))))
        return xs[k]
    qv_rates = [r["quote_verification_rate"] for r in completed
                if r["quote_verification_rate"] is not None]
    fabricated_surviving = sum(len(r.get("fabricated_quotes") or []) for r in records
                              if r["assessment_status"] == "COMPLETED"
                              and any(fq.get("for_element") in
                                      {e["element_id"] for st in REQUIRED_ELEMENTS.values() for e in st}
                                      for fq in (r.get("fabricated_quotes") or [])))
    return {
        "n": n,
        "schema_compliance": round(1 - len(failed) / n, 4) if n else None,
        "completed_rate": round(len(completed) / n, 4) if n else None,
        "confirms_absence_rate": round(len(confirms_absence) / n, 4) if n else None,
        "indeterminate_rate": round(len(indet) / n, 4) if n else None,
        "failed_rate": round(len(failed) / n, 4) if n else None,
        "quote_verification_pass_rate_mean": round(statistics.mean(qv_rates), 4) if qv_rates else None,
        "quote_verification_pass_rate_min": round(min(qv_rates), 4) if qv_rates else None,
        "unsupported_claims_total": sum(len(r.get("fabricated_quotes") or []) for r in records),
        "fabricated_evidence_surviving_gate": fabricated_surviving,  # DEBE ser 0
        "near_matches_total": sum(r.get("near_matches") or 0 for r in records),          # H-2
        "elements_forced_unclear_total": sum(r.get("elements_forced_unclear") or 0 for r in records),  # H-3
        "contradictions_detected_total": sum(len(r.get("contradictory_evidence") or []) for r in records),
        "grounded_quotes_total": sum(len(r.get("grounded_quotes") or []) for r in records),
        "latency_p50_s": _pct(lat, 0.50),
        "latency_p95_s": _pct(lat, 0.95),
        "latency_max_s": lat[-1] if lat else None,
    }


def run():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    findings = _load_findings()
    sample, coverage = _stratify(findings)
    print(f"[bakeoff] findings totales={len(findings)}  muestra estratificada={len(sample)}")
    for sub, c in coverage.items():
        print(f"  {sub:26s} disp={c['available']:4d} muestreados={c['sampled']}")

    meta = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_dir": str(RUN_DIR),
        "ollama_version": pc.ollama_version(),
        "pinned_options": pc.PINNED_OPTIONS,
        "prompt_version": pc.PROMPT_VERSION,
        "models": {m: pc.model_digest(m) for m in MODELS},
        "stratification": coverage,
        "sample_finding_ids": [f.get("finding_id") for f in sample],
    }
    (OUT_DIR / "bakeoff_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    results: dict[str, list[dict]] = {}
    for model in MODELS:
        print(f"\n=== modelo: {model} ({meta['models'][model][:16]}) ===")
        recs = []
        for i, f in enumerate(sample, 1):
            t0 = time.time()
            r = assess(f, model)
            recs.append(r)
            print(f"  [{i:2d}/{len(sample)}] {f['subtype']:24s} {f['document']} p.{f.get('page')}"
                  f"  -> {r['assessment_status']:13s} qv={r['quote_verification_rate']}"
                  f"  {time.time()-t0:5.1f}s")
        results[model] = recs
        (OUT_DIR / f"bakeoff_{model.replace(':','_').replace('/','_')}.json").write_text(
            json.dumps(recs, indent=2, ensure_ascii=False))

    # ---- reproducibility: N>=3 sobre sub-muestra, mismo input -> mismo output_hash ----
    repro = {}
    sub = sample[:REPRO_SUBSAMPLE]
    for model in MODELS:
        per_finding = []
        for f in sub:
            hashes, statuses = [], []
            for _ in range(REPRO_N):
                r = assess(f, model)
                hashes.append(r["output_hash"])
                statuses.append(r["assessment_status"])
            per_finding.append({
                "finding_id": f.get("finding_id"), "subtype": f["subtype"],
                "output_hashes": hashes, "statuses": statuses,
                "identical_output": len(set(hashes)) == 1,
                "identical_status": len(set(statuses)) == 1,
            })
        rate = round(sum(1 for x in per_finding if x["identical_output"]) / len(per_finding), 4)
        repro[model] = {"reproducibility_rate": rate, "per_finding": per_finding}
        print(f"[repro] {model}: reproducibility_rate={rate}")
    (OUT_DIR / "bakeoff_reproducibility.json").write_text(json.dumps(repro, indent=2, ensure_ascii=False))

    # ---- cache: RW-0012 p.5 y RW-0014 p.5 (AUTHORITY_CHECK_GAP) comparten source_hash ----
    def _find(doc, page, subt):
        for f in findings:
            if f["document"] == doc and f.get("page") == page and f["subtype"] == subt:
                return _normalize(f)
        return None
    a = _find("RW-0012", 5, "AUTHORITY_CHECK_GAP")
    b = _find("RW-0014", 5, "AUTHORITY_CHECK_GAP")
    cache = {"found_a": bool(a), "found_b": bool(b)}
    if a and b:
        dg = meta["models"][MODELS[0]]
        cache.update({
            "source_hash_a": a["source_hash"], "source_hash_b": b["source_hash"],
            "same_source_hash": a["source_hash"] == b["source_hash"],
            "cache_key_a": _cache_key(a, dg), "cache_key_b": _cache_key(b, dg),
            "same_cache_key": _cache_key(a, dg) == _cache_key(b, dg),
            "inferences_needed": 1 if _cache_key(a, dg) == _cache_key(b, dg) else 2,
        })
    (OUT_DIR / "bakeoff_cache_check.json").write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"[cache] {json.dumps(cache)}")

    # ---- resumen ----
    summary = {"meta": meta, "cache_check": cache,
               "reproducibility": {m: repro[m]["reproducibility_rate"] for m in MODELS},
               "per_model": {m: _metrics(results[m]) for m in MODELS}}
    (OUT_DIR / "bakeoff_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== RESUMEN ===")
    print(json.dumps(summary["per_model"], indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
