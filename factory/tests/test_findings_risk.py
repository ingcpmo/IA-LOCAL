"""Tests -- factory/regulatory/findings/risk.py (V2, B5).

FASE 7.4: Risk DETERMINISTA desde risk_matrix.yaml (gobernado), nunca un
número del LLM. score = severity_w * gxp_impact_w * probability_w *
detectability_w; band por umbrales.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.findings import risk as rk


def test_deterministic():
    a = rk.compute_risk("REGULATORY_GAP", "CRITICAL", "HIGH")
    b = rk.compute_risk("REGULATORY_GAP", "CRITICAL", "HIGH")
    assert a == b


def test_score_is_product_of_weights():
    r = rk.compute_risk("REGULATORY_GAP", "CRITICAL", "HIGH")
    assert r.score == r.severity_w * r.gxp_impact_w * r.probability_w * r.detectability_w
    # CRITICAL=3, HIGH=3, REGULATORY_GAP prob=3 det=2  -> 54 -> CRITICAL
    assert r.score == 54
    assert r.band == "CRITICAL"


def test_low_end_band():
    r = rk.compute_risk("REGULATORY_COMPLIANT_EVIDENCE", "LOW", "LOW")
    assert r.score == 1
    assert r.band == "LOW"


def test_spanish_severity_aliases_accepted():
    assert rk.compute_risk("REGULATORY_GAP", "critica", "HIGH").severity_w == 3
    assert rk.compute_risk("REGULATORY_GAP", "mayor", "MEDIUM").severity_w == 2


def test_unknown_subtype_uses_default_not_error():
    r = rk.compute_risk("SOMETHING_NEW", "MAJOR", "MEDIUM")
    m = rk.load_matrix()
    assert r.probability_w == m["default"]["probability"]
    assert r.detectability_w == m["default"]["detectability"]


def test_unknown_severity_or_gxp_raises():
    with pytest.raises(rk.RiskMatrixError):
        rk.compute_risk("REGULATORY_GAP", "APOCALYPTIC", "HIGH")
    with pytest.raises(rk.RiskMatrixError):
        rk.compute_risk("REGULATORY_GAP", "MAJOR", "STRATOSPHERIC")


def test_matrix_version_reported():
    assert rk.compute_risk("REGULATORY_GAP", "MAJOR").matrix_version == "1.0"


def test_all_taxonomy_subtypes_present_in_matrix():
    from factory.regulatory.findings.taxonomy import SUBTYPES
    m = rk.load_matrix()["subtypes"]
    missing = []
    for subs in SUBTYPES.values():
        for s in subs:
            if s not in m:
                missing.append(s)
    assert not missing, f"subtipos sin fila en risk_matrix.yaml: {missing}"
