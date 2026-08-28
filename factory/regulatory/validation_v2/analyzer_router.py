"""Dispatcher del analizador documental -- FASE 11 / B9b (cutover controlado).

La "1 línea reversible" que cablea `cutover.routing_mode()` al camino de
análisis. Modos (`cutover.py`):
  current  -> CURRENT decide (motor de juicio LLM; camino histórico).
  shadow   -> CURRENT decide; V2 corre en paralelo SIN efectos.
  v2       -> V2 es el analizador activo. CURRENT se conserva como fallback
              seleccionable volviendo a `current`.

Tras la decisión de Capa 9 (2026-08-28): en modo `v2`, la clase Regulatory
opera en **Tier-1 / Palanca C** (determinista, eco léxico + revisión humana
con cobertura declarada; NUNCA aprobación automática), y V2 aporta además
Functional y Technical. NO se activa juicio LLM.
"""
from __future__ import annotations

from pathlib import Path

from factory.regulatory.validation_v2 import cutover


class CurrentEngineHandoff(RuntimeError):
    """El routing pide CURRENT: este dispatcher no invoca el motor CURRENT
    (vive en corpus_runner / HTTP). Señala al llamador que use el camino
    CURRENT existente -- que sigue intacto."""


def active_engine() -> str:
    """'CURRENT' | 'V2' según el flag de routing."""
    return "V2" if cutover.is_v2_active() else "CURRENT"


def regulatory_modality() -> str:
    """En cutover a V2, la clase Regulatory opera en Tier-1 / Palanca C."""
    return "REGULATORY_TIER1_PALANCA_C" if cutover.is_v2_active() else "CURRENT_LLM_JUDGMENT"


def analyze(document_ids: list[str], *, project_id: str = "V2-ROUTED", **kw) -> dict:
    """Punto único de análisis. Enruta según `cutover.routing_mode()`.

    - `v2`      -> `v2_runtime.run_v2_pipeline` (determinista, 0 LLM, persiste
                   bajo GMPAI/reports/gmpai_document_validation/<run_id>/).
    - `current` -> levanta `CurrentEngineHandoff` (el motor CURRENT se invoca
                   por su camino existente; este dispatcher no lo duplica).
    - `shadow`  -> corre V2 sin efectos y devuelve la comparación (no decide).
    """
    mode = cutover.routing_mode()
    if mode == "current":
        raise CurrentEngineHandoff(
            "routing=current: usar el camino CURRENT (corpus_runner / HTTP). "
            "CURRENT intacto; para activar V2, cutover.set_routing_mode('v2', ...).")
    if mode == "shadow":
        from factory.regulatory.validation_v2.shadow_run_v2 import run_shadow_v2
        return {"mode": "shadow", "decides": "CURRENT", "shadow": run_shadow_v2(document_ids)}

    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    res = run_v2_pipeline(document_ids, project_id=project_id, **kw)
    res["routing_mode"] = "v2"
    res["regulatory_modality"] = regulatory_modality()
    res["current_rollback"] = "cutover.set_routing_mode('current', ...) -> CURRENT vuelve a ser el activo"
    return res


def describe() -> dict:
    d = cutover.describe()
    d["active_engine"] = active_engine()
    d["regulatory_modality"] = regulatory_modality()
    d["routing_history"] = cutover.routing_history()
    return d
