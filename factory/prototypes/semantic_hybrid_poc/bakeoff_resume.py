"""Reanuda el bake-off tras la caida transitoria de Ollama (Connection refused).
Reutiliza los dos JSON por-modelo ya escritos (14 recs c/u) y ejecuta SOLO lo
que falta: reproducibility_rate (N>=3) sobre una sub-muestra + verificacion de
cache RW-0012/RW-0014 + resumen consolidado. FASE 2, aislado. No commitea nada.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc.bakeoff import (
    RUN_DIR, OUT_DIR, MODELS, _load_findings, _normalize, _metrics,
)
from factory.prototypes.semantic_hybrid_poc.runner import assess, _cache_key

REPRO_N = 3
# sub-muestra: 3 findings de menor latencia observada en la corrida qwen
REPRO_FINDING_KEYS = [
    ("RW-0006", 11, "BACKUP_RECOVERY_GAP"),
    ("RW-0006", 6, "AUDIT_TRAIL_INTEGRITY_GAP"),
    ("RW-0006", 16, "ACCESS_CONTROL_GAP"),
]


def _find(findings, doc, page, subt):
    for f in findings:
        if f["document"] == doc and f.get("page") == page and f["subtype"] == subt:
            return _normalize(f)
    return None


def run():
    findings = _load_findings()
    results = {m: json.loads((OUT_DIR / f"bakeoff_{m.replace(':','_').replace('/','_')}.json").read_text())
               for m in MODELS}
    meta = json.loads((OUT_DIR / "bakeoff_meta.json").read_text())

    sub = [_find(findings, d, p, s) for d, p, s in REPRO_FINDING_KEYS]
    assert all(sub), "sub-muestra de reproducibilidad no resuelta"

    repro = {}
    for model in MODELS:
        per_finding = []
        for f in sub:
            hashes, statuses, covs = [], [], []
            for k in range(REPRO_N):
                r = assess(f, model)
                hashes.append(r["output_hash"])
                statuses.append(r["assessment_status"])
                covs.append(r["semantic_coverage"])
                print(f"  [repro] {model[:12]} {f['subtype']:24s} rep{k+1} "
                      f"-> {r['assessment_status']:13s} {r['wall_time_s']}s hash={r['output_hash'][:12]}")
            per_finding.append({
                "finding_id": f.get("finding_id"), "subtype": f["subtype"],
                "document": f["document"], "page": f.get("page"),
                "output_hashes": hashes, "statuses": statuses, "coverages": covs,
                "identical_output": len(set(hashes)) == 1,
                "identical_status": len(set(statuses)) == 1,
            })
        rate = round(sum(1 for x in per_finding if x["identical_output"]) / len(per_finding), 4)
        srate = round(sum(1 for x in per_finding if x["identical_status"]) / len(per_finding), 4)
        repro[model] = {"reproducibility_rate_output": rate,
                        "reproducibility_rate_status": srate,
                        "N": REPRO_N, "per_finding": per_finding}
        print(f"[repro] {model}: output={rate} status={srate}")
    (OUT_DIR / "bakeoff_reproducibility.json").write_text(json.dumps(repro, indent=2, ensure_ascii=False))

    # ---- cache: RW-0012 p.5 y RW-0014 p.5 (AUTHORITY_CHECK_GAP) comparten source_hash ----
    a = _find(findings, "RW-0012", 5, "AUTHORITY_CHECK_GAP")
    b = _find(findings, "RW-0014", 5, "AUTHORITY_CHECK_GAP")
    dg = meta["models"][MODELS[0]]
    cache = {
        "found_a": bool(a), "found_b": bool(b),
        "source_hash_a": a["source_hash"], "source_hash_b": b["source_hash"],
        "same_source_hash": a["source_hash"] == b["source_hash"],
        "cache_key_a": _cache_key(a, dg), "cache_key_b": _cache_key(b, dg),
        "same_cache_key": _cache_key(a, dg) == _cache_key(b, dg),
        "inferences_needed_for_pair": 1 if _cache_key(a, dg) == _cache_key(b, dg) else 2,
    }
    (OUT_DIR / "bakeoff_cache_check.json").write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"[cache] {json.dumps(cache)}")

    summary = {
        "meta": meta, "cache_check": cache,
        "reproducibility": {m: {"output": repro[m]["reproducibility_rate_output"],
                                "status": repro[m]["reproducibility_rate_status"],
                                "N": REPRO_N} for m in MODELS},
        "per_model": {m: _metrics(results[m]) for m in MODELS},
        "note": "reanudado tras caida transitoria de Ollama; los 14+14 assessments "
                "por-modelo son de la corrida original, intactos.",
    }
    (OUT_DIR / "bakeoff_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\n=== RESUMEN ===")
    print(json.dumps(summary["per_model"], indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    run()
