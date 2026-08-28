"""Cálculo de riesgo DETERMINISTA (V2, B5) -- FASE 7.4.

`compute_risk(subtype, severity, gxp_impact)` -> RiskResult con
`score` (1..81) y `band` (LOW|MEDIUM|HIGH|CRITICAL), usando la tabla
gobernada `risk_matrix.yaml`. NUNCA un número del LLM. Mismo input ->
mismo resultado.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml as _yaml

_MATRIX_PATH = Path(__file__).parent / "risk_matrix.yaml"


class RiskMatrixError(Exception):
    pass


@lru_cache(maxsize=1)
def load_matrix() -> dict:
    if not _MATRIX_PATH.exists():
        raise RiskMatrixError(f"risk_matrix.yaml no encontrado: {_MATRIX_PATH}")
    m = _yaml.safe_load(_MATRIX_PATH.read_text(encoding="utf-8"))
    for k in ("severity_weights", "gxp_impact_weights", "bands", "default", "subtypes"):
        if k not in m:
            raise RiskMatrixError(f"risk_matrix.yaml sin '{k}'")
    return m


@dataclass
class RiskResult:
    subtype: str
    severity: str
    gxp_impact: str
    severity_w: int
    gxp_impact_w: int
    probability_w: int
    detectability_w: int
    score: int
    band: str
    matrix_version: str

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _weight(table: dict, key: str, *, what: str) -> int:
    k = str(key).strip().upper()
    if k not in table:
        raise RiskMatrixError(f"{what} desconocido para la matriz de riesgo: {key!r}")
    return int(table[k])


def compute_risk(subtype: str, severity: str, gxp_impact: str = "MEDIUM") -> RiskResult:
    m = load_matrix()
    sev_w = _weight(m["severity_weights"], severity, what="severity")
    gxp_w = _weight(m["gxp_impact_weights"], gxp_impact, what="gxp_impact")
    sub = m["subtypes"].get(subtype, m["default"])
    prob_w = int(sub.get("probability", m["default"]["probability"]))
    det_w = int(sub.get("detectability", m["default"]["detectability"]))
    score = sev_w * gxp_w * prob_w * det_w
    band = _band(score, m["bands"])
    return RiskResult(
        subtype=subtype, severity=str(severity).upper(), gxp_impact=str(gxp_impact).upper(),
        severity_w=sev_w, gxp_impact_w=gxp_w, probability_w=prob_w, detectability_w=det_w,
        score=score, band=band, matrix_version=str(m.get("risk_matrix_version", "unknown")),
    )


def _band(score: int, bands: list) -> str:
    for entry in bands:
        if score <= int(entry["max"]):
            return str(entry["band"])
    return str(bands[-1]["band"])
