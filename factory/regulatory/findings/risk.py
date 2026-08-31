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


_BAND_LADDER = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _downgrade_band(band: str) -> str:
    """H-7 ENFORCE: baja la banda un escalón, con suelo en LOW."""
    try:
        i = _BAND_LADDER.index(str(band).upper())
    except ValueError:
        return band
    return _BAND_LADDER[max(0, i - 1)]


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
    # --- H-7: campos aditivos; SOLO se serializan en modo ENFORCE ----------
    evidence_basis: str | None = None
    coverage_status: str | None = None
    mode: str = "OBSERVE"
    enforced_degraded: bool = False
    band_changed: bool = False
    band_pre_enforce: str | None = None

    def as_dict(self) -> dict:
        d = {
            "subtype": self.subtype, "severity": self.severity, "gxp_impact": self.gxp_impact,
            "severity_w": self.severity_w, "gxp_impact_w": self.gxp_impact_w,
            "probability_w": self.probability_w, "detectability_w": self.detectability_w,
            "score": self.score, "band": self.band, "matrix_version": self.matrix_version,
        }
        # En OBSERVE el dict es BYTE-IDÉNTICO al histórico (findings_fingerprint
        # intacto). Los campos H-7 solo aparecen cuando ENFORCE está EFECTIVO.
        if str(self.mode).upper() == "ENFORCE":
            d.update({
                "evidence_basis": self.evidence_basis,
                "coverage_status": self.coverage_status,
                "mode": "ENFORCE",
                "enforced_degraded": self.enforced_degraded,
                "band_changed": self.band_changed,
                "band_pre_enforce": self.band_pre_enforce,
            })
        return d


def _weight(table: dict, key: str, *, what: str) -> int:
    k = str(key).strip().upper()
    if k not in table:
        raise RiskMatrixError(f"{what} desconocido para la matriz de riesgo: {key!r}")
    return int(table[k])


def compute_risk(subtype: str, severity: str, gxp_impact: str = "MEDIUM", *,
                 evidence_basis: str | None = None, coverage_status: str | None = None,
                 mode: str = "OBSERVE") -> RiskResult:
    """`mode="OBSERVE"` (default) -> comportamiento y `as_dict()` IDÉNTICOS al
    histórico; `evidence_basis`/`coverage_status` se ignoran (metadata aditiva).

    `mode="ENFORCE"` (GATE D-2) -> si el finding es `ABSENCE_DEPENDENT` y su
    cobertura es MISSING/DEGRADED, la banda baja un escalón (`enforced_degraded`).
    """
    m = load_matrix()
    sev_w = _weight(m["severity_weights"], severity, what="severity")
    gxp_w = _weight(m["gxp_impact_weights"], gxp_impact, what="gxp_impact")
    sub = m["subtypes"].get(subtype, m["default"])
    prob_w = int(sub.get("probability", m["default"]["probability"]))
    det_w = int(sub.get("detectability", m["default"]["detectability"]))
    score = sev_w * gxp_w * prob_w * det_w
    band = _band(score, m["bands"])

    enforced_degraded = False   # la REGLA de degradación aplica a este finding
    band_changed = False        # y además la banda se movió numéricamente
    band_pre = band
    if str(mode).upper() == "ENFORCE":
        if (str(evidence_basis).upper() == "ABSENCE_DEPENDENT"
                and str(coverage_status).upper() in ("MISSING", "DEGRADED")):
            enforced_degraded = True
            band = _downgrade_band(band)
            band_changed = band != band_pre

    return RiskResult(
        subtype=subtype, severity=str(severity).upper(), gxp_impact=str(gxp_impact).upper(),
        severity_w=sev_w, gxp_impact_w=gxp_w, probability_w=prob_w, detectability_w=det_w,
        score=score, band=band, matrix_version=str(m.get("risk_matrix_version", "unknown")),
        evidence_basis=evidence_basis, coverage_status=coverage_status, mode=str(mode).upper(),
        enforced_degraded=enforced_degraded, band_changed=band_changed, band_pre_enforce=band_pre,
    )


def _band(score: int, bands: list) -> str:
    for entry in bands:
        if score <= int(entry["max"]):
            return str(entry["band"])
    return str(bands[-1]["band"])
