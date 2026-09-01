"""H-4 — gate de estabilidad para la deriva run-to-run (FASE 2, aislado).

El bake-off midio reproducibilidad de salida baja con pinning completo
(qwen 0.33 bit-identico; un status cambio entre repeticiones). llama.cpp CPU
no es bit-determinista; la 1a inferencia tras cargar el modelo difiere y luego
se estabiliza (rep1 != rep2 == rep3).

Mitigacion, sin tocar `runner.assess` (que sigue siendo UNA inferencia):
  - `warmup(model)`: una inferencia trivial descartada, para sacar al modelo
    del arranque en frio antes del lote.
  - `assess_stable(finding, model, n=2)`: corre `assess` n veces; si el
    `assessment_status` o algun `verdict` por elemento discrepa entre corridas
    -> se degrada a INDETERMINATE con `stability_flag`, NUNCA se "elige" una.
    Direccion fail-safe: la inestabilidad va hacia "necesita humano".
"""
from __future__ import annotations

import time

from factory.prototypes.semantic_hybrid_poc import pinned_client as pc
from factory.prototypes.semantic_hybrid_poc.runner import assess
from factory.prototypes.semantic_hybrid_poc.schema import SCTA_V1

_WARMUP_PROMPT = ('Responde SOLO con este JSON exacto, sin nada mas: '
                  '{"required_elements":[],"semantic_coverage":"INDETERMINATE",'
                  '"contradictory_evidence":[],"supporting_evidence":[],'
                  '"auditor_explanation":"warmup","limitations":[]}')


def warmup(model: str) -> dict:
    """Saca al modelo del arranque en frio. Resultado descartado."""
    t0 = time.time()
    gen = pc.generate(model, _WARMUP_PROMPT, SCTA_V1)
    return {"model": model, "wall_time_s": round(time.time() - t0, 2),
            "transport_error": gen.get("transport_error"),
            "done_reason": gen.get("done_reason")}


def _verdict_map(rec: dict) -> dict:
    return {e.get("element_id"): e.get("verdict")
            for e in (rec.get("required_elements") or [])}


def assess_stable(finding: dict, model: str, *, n: int = 2,
                  context_override: dict | None = None) -> dict:
    """Corre `assess` n veces (n>=2). Devuelve el registro de la 1a corrida
    enriquecido con un bloque `stability`. Si status o verdicts discrepan ->
    assessment_status/semantic_coverage = INDETERMINATE y stability_flag=True."""
    assert n >= 2, "n>=2"
    runs = [assess(finding, model, context_override=context_override) for _ in range(n)]
    first = dict(runs[0])

    statuses = [r["assessment_status"] for r in runs]
    vmaps = [_verdict_map(r) for r in runs]
    status_stable = len(set(statuses)) == 1
    all_keys = set().union(*[set(v) for v in vmaps]) if vmaps else set()
    verdict_stable = all(len({vm.get(k) for vm in vmaps}) == 1 for k in all_keys)
    stable = status_stable and verdict_stable

    first["stability"] = {
        "n": n,
        "stable": stable,
        "status_seen": statuses,
        "status_stable": status_stable,
        "verdict_stable": verdict_stable,
        "output_hashes": [r.get("output_hash") for r in runs],
        "output_bit_identical": len({r.get("output_hash") for r in runs}) == 1,
        "wall_time_s_total": round(sum(r.get("wall_time_s") or 0 for r in runs), 2),
    }
    if not stable:
        first["assessment_status_raw"] = first["assessment_status"]
        first["semantic_coverage_raw"] = first["semantic_coverage"]
        first["assessment_status"] = "INDETERMINATE"
        first["semantic_coverage"] = "INDETERMINATE"
        first["stability_flag"] = True
        first["stability_reason"] = "modelo inestable en este input (status/verdict discrepan entre corridas)"
    else:
        first["stability_flag"] = False
    return first
