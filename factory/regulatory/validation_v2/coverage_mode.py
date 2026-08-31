"""H-7 (2026-08-29) -- `analysis_coverage_mode` como PARÁMETRO GOBERNADO.

Antes: literal `"OBSERVE"` en 4 sitios de `v2_runtime.py`. Ahora: un solo
resolutor que lee `requirement_catalog/analysis_coverage_mode.yaml`, cruza con
la firma de `extraction_adequacy_thresholds.yaml`, y devuelve el modo EFECTIVO
+ una atestación de por qué.

Regla dura: `ENFORCE` efectivo SOLO si (1) el YAML pide `ENFORCE` con firma de
Capa 9 (`decided_by` + `decision_ref` + `decision_date`) **y** (2)
`extraction_adequacy_thresholds.yaml` está `SIGNED`. Cualquier otro caso -> el
runtime fuerza `OBSERVE` (fail-safe) y lo registra en `downgrade_reason`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml as _yaml

_MODE_PATH = (Path(__file__).resolve().parent.parent
              / "requirement_catalog" / "analysis_coverage_mode.yaml")

MODES = ("OBSERVE", "ENFORCE")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        d = _yaml.safe_load(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _thresholds_signed() -> bool:
    try:
        from factory.regulatory.validation_v2 import extraction_adequacy as _adq
        return bool(_adq.is_signed())
    except Exception:  # noqa: BLE001
        return False


def resolve(path: Path | None = None) -> dict:
    """Devuelve la atestación del modo. `effective_mode` es lo que el runtime usa."""
    p = Path(path) if path else _MODE_PATH
    cfg = _load(p)
    requested = str(cfg.get("mode", "OBSERVE") or "OBSERVE").strip().upper()
    if requested not in MODES:
        requested = "OBSERVE"

    mode_config_signed = all(cfg.get(k) not in (None, "", "null")
                             for k in ("decided_by", "decision_ref", "decision_date"))
    thresholds_signed = _thresholds_signed()

    downgrade_reason = None
    if requested == "ENFORCE":
        missing = []
        if not mode_config_signed:
            missing.append("analysis_coverage_mode.yaml sin firma de Capa 9 (decided_by/decision_ref/decision_date)")
        if not thresholds_signed:
            missing.append("extraction_adequacy_thresholds.yaml no está SIGNED (D-2)")
        if missing:
            effective = "OBSERVE"
            downgrade_reason = "; ".join(missing)
        else:
            effective = "ENFORCE"
    else:
        effective = "OBSERVE"

    return {
        "requested_mode": requested,
        "effective_mode": effective,
        "thresholds_signed": thresholds_signed,
        "mode_config_signed": mode_config_signed,
        "downgrade_reason": downgrade_reason,
        "config_path": "factory/regulatory/requirement_catalog/analysis_coverage_mode.yaml",
        "config_sha256": _sha256(p),
        "decision_ref": cfg.get("decision_ref"),
        "note": ("ENFORCE efectivo exige firma de Capa 9 en el YAML del modo Y "
                 "extraction_adequacy_thresholds.yaml SIGNED. Fail-safe: OBSERVE."),
    }


def effective_mode(path: Path | None = None) -> str:
    return resolve(path)["effective_mode"]
