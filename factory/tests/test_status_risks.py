"""
Guard U8/U12: riesgos de observabilidad — lógica de endpoint y estado post-U12.

U8  — verificó que /status/risks exponía R6+R7 para r6_change_control.
U12 — r6_change_control cancelada y archivada; ambos riesgos resueltos.

Tests actuales verifican:
  - Endpoint con forma correcta siempre
  - Estado limpio post-U12: sin RISK_REMEDIATION_R6 ni RISK_PORT_UNDEPLOYED_R6
  - lab_qc_project activo sigue sin generar zombie
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _get_api_key():
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible")
    return key


def _get_risks():
    import httpx
    key = _get_api_key()
    r = httpx.get("http://localhost:9000/api/v1/status/risks",
                  headers={"x-api-key": key}, timeout=10)
    assert r.status_code == 200
    return r.json()


def test_risks_endpoint_returns_valid_shape():
    data = _get_risks()
    assert "risks" in data
    assert "count" in data
    assert data["count"] == len(data["risks"])


def test_no_r6_remediation_risk_after_u12():
    """U12: r6_change_control cancelada — RISK_REMEDIATION_R6 debe estar ausente."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_REMEDIATION_R6_CHANGE_CONTROL" not in ids, (
        f"r6_change_control fue resuelta en U12 pero el riesgo persiste: {ids}"
    )


def test_no_zombie_port_r6_after_u12():
    """U12: puerto 8102 liberado del registry — RISK_PORT_UNDEPLOYED_R6 debe estar ausente."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_R6_CHANGE_CONTROL" not in ids, (
        f"Puerto 8102 liberado en U12 pero el riesgo zombie persiste: {ids}"
    )


def test_clean_state_post_u12():
    """U12: sistema sin riesgos activos tras cierre operativo."""
    data = _get_risks()
    assert data["count"] == 0, (
        f"Se esperaba count=0 tras U12, encontrado: {data['risks']}"
    )


def test_no_spurious_risk_for_lab_qc_deployed():
    """lab_qc_project tiene deployment activo — NO debe tener RISK_PORT_UNDEPLOYED."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_LAB_QC_PROJECT" not in ids, (
        "lab_qc_project tiene deployment activo y no debe ser zombie"
    )
