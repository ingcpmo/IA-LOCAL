from __future__ import annotations

import math

# [INTERNAL_SUMMARY: internal_summary_usp_621_chromatography.txt (lab_qc_project/data/regulations/hplc_di/)
#  Valores validados contra resumen interno. Ingesta oficial de USP <621> pendiente para release productivo.]
_SST_CRITERIA = {
    "theoretical_plates_min": 2000,   # rango típico 1500-10000; el método/SOP define el mínimo exacto
    "tailing_factor_min": 0.8,
    "tailing_factor_max": 2.0,        # USP <621>: T ≤ 2.0 para todos los picos de interés
    "resolution_min": 2.0,            # USP <621>: Rs ≥ 2.0 para separación de baseline
    "rsd_retention_max": 1.0,         # USP <621>: %RSD tiempo de retención ≤ 1.0% todos los métodos
}


def validate_sst(sst_data: dict) -> dict:
    failures: list[str] = []
    evaluated: dict = {}

    tp = sst_data.get("theoretical_plates")
    if tp is not None:
        evaluated["theoretical_plates"] = tp
        if tp < _SST_CRITERIA["theoretical_plates_min"]:
            failures.append(
                f"theoretical_plates={tp} < {_SST_CRITERIA['theoretical_plates_min']} (minimum)"
            )

    tf = sst_data.get("tailing_factor")
    if tf is not None:
        evaluated["tailing_factor"] = tf
        if not (_SST_CRITERIA["tailing_factor_min"] <= tf <= _SST_CRITERIA["tailing_factor_max"]):
            failures.append(
                f"tailing_factor={tf} outside "
                f"[{_SST_CRITERIA['tailing_factor_min']}, {_SST_CRITERIA['tailing_factor_max']}]"
            )

    res = sst_data.get("resolution")
    if res is not None:
        evaluated["resolution"] = res
        if res < _SST_CRITERIA["resolution_min"]:
            failures.append(
                f"resolution={res} < {_SST_CRITERIA['resolution_min']} (minimum)"
            )

    rsd = sst_data.get("rsd_retention")
    if rsd is not None:
        evaluated["rsd_retention"] = rsd
        if rsd > _SST_CRITERIA["rsd_retention_max"]:
            failures.append(
                f"rsd_retention={rsd}% > {_SST_CRITERIA['rsd_retention_max']}% (maximum)"
            )

    return {"pass": len(failures) == 0, "failures": failures, "evaluated": evaluated}


def detect_peak_anomalies(peaks: list[dict]) -> list[str]:
    anomalies: list[str] = []
    for peak in peaks:
        name = peak.get("name", "<unnamed>")
        area = peak.get("area")
        rt = peak.get("retention_time")
        sym = peak.get("symmetry")

        if area is not None and area < 0:
            anomalies.append(f"Peak '{name}': negative area ({area})")

        if rt is not None and rt <= 0:
            anomalies.append(f"Peak '{name}': retention_time <= 0 ({rt})")

        if sym is not None and not (0.5 <= sym <= 2.5):
            anomalies.append(f"Peak '{name}': symmetry={sym} outside [0.5, 2.5]")

    return anomalies


def calculate_rsd(values: list[float]) -> float:
    if len(values) < 2:
        raise ValueError("calculate_rsd requires at least 2 values")
    n = len(values)
    mean = sum(values) / n
    if mean == 0:
        raise ValueError("calculate_rsd: mean is zero, RSD undefined")
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return (math.sqrt(variance) / mean) * 100


def validate_injection_sequence(sequence: list[dict]) -> dict:
    issues: list[str] = []

    if not sequence:
        return {"valid": False, "issues": ["Empty injection sequence"]}

    types = [inj.get("type", "") for inj in sequence]

    if "blank" in types and types[0] != "blank":
        issues.append("'blank' injection must appear first in the sequence")

    if "sst" in types and "sample" in types:
        sst_idx = types.index("sst")
        sample_idx = types.index("sample")
        if sst_idx > sample_idx:
            issues.append("'sst' injection must appear before the first 'sample'")

    return {"valid": len(issues) == 0, "issues": issues}
