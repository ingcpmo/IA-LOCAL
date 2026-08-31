"""H-7 (2026-08-29) -- loader de `gxp_criticality.yaml`.

Devuelve el nivel de criticidad GxP ESTRUCTURADA de un requisito
(`LOW|MEDIUM|HIGH`). SOLO lo consume el runtime cuando el modo EFECTIVO es
ENFORCE (GATE D-2); en OBSERVE nadie lo llama.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_PATH = Path(__file__).resolve().parent / "gxp_criticality.yaml"

LEVELS = ("LOW", "MEDIUM", "HIGH")


@lru_cache(maxsize=1)
def _load() -> dict:
    if not _PATH.is_file():
        return {"criticality": {}, "default": {"level": "MEDIUM"}, "status": "MISSING"}
    d = _yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    d.setdefault("criticality", {})
    d.setdefault("default", {"level": "MEDIUM"})
    return d


def sha256() -> str:
    return hashlib.sha256(_PATH.read_bytes()).hexdigest() if _PATH.is_file() else ""


def status() -> str:
    return str(_load().get("status", "MISSING")).upper()


def is_signed() -> bool:
    d = _load()
    return status() == "SIGNED" and all(
        d.get(k) not in (None, "", "null") for k in ("decided_by", "decision_ref", "decision_date"))


def level_for(requirement_id: str | None) -> str:
    """Nivel GxP del requisito. Cae al `default` (MEDIUM) si no está mapeado --
    equivalente al literal `gxp_impact="MEDIUM"` actual, para no perturbar nada
    que hoy pase MEDIUM."""
    d = _load()
    entry = d["criticality"].get(str(requirement_id or ""))
    lvl = (entry or {}).get("level") or d["default"].get("level", "MEDIUM")
    lvl = str(lvl).strip().upper()
    return lvl if lvl in LEVELS else "MEDIUM"


def as_gxp_impact(requirement_id: str | None) -> str:
    """Alias semántico: el valor que espera `risk.compute_risk(gxp_impact=...)`."""
    return level_for(requirement_id)
