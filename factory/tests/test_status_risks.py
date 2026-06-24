"""
Guard U8: riesgos de observabilidad — remediación r6 y zombie de puerto.

Verifica que /api/v1/status/risks exponga:
  R6 — RISK_REMEDIATION_*  para misiones en returned_to_adjustments
  R7 — RISK_PORT_UNDEPLOYED_* para puertos asignados sin deployment activo
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


def test_remediation_risk_present_for_returned_mission():
    """R6: misiones en returned_to_adjustments generan RISK_REMEDIATION_*."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    remediation = [i for i in ids if i.startswith("RISK_REMEDIATION_")]
    assert len(remediation) >= 1, (
        f"Esperado al menos un RISK_REMEDIATION_*, risks actuales: {ids}"
    )


def test_remediation_risk_r6_specifically():
    """El riesgo de r6_change_control debe estar presente."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_REMEDIATION_R6_CHANGE_CONTROL" in ids, (
        f"RISK_REMEDIATION_R6_CHANGE_CONTROL no encontrado. Risks: {ids}"
    )


def test_remediation_risk_has_return_reason():
    data = _get_risks()
    for r in data["risks"]:
        if r["id"] == "RISK_REMEDIATION_R6_CHANGE_CONTROL":
            assert "motivo" in r["description"].lower() or "reason" in r["description"].lower()
            assert r["severity"] == "medio"
            return
    pytest.fail("RISK_REMEDIATION_R6_CHANGE_CONTROL no encontrado")


def test_zombie_port_risk_present():
    """R7: puerto 8102 asignado sin deployment genera RISK_PORT_UNDEPLOYED_*."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    zombie = [i for i in ids if i.startswith("RISK_PORT_UNDEPLOYED_")]
    assert len(zombie) >= 1, (
        f"Esperado al menos un RISK_PORT_UNDEPLOYED_*, risks actuales: {ids}"
    )


def test_zombie_port_r6_specifically():
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_R6_CHANGE_CONTROL" in ids


def test_zombie_port_risk_mentions_port_number():
    data = _get_risks()
    for r in data["risks"]:
        if r["id"] == "RISK_PORT_UNDEPLOYED_R6_CHANGE_CONTROL":
            assert "8102" in r["description"]
            assert r["severity"] == "info"
            return
    pytest.fail("RISK_PORT_UNDEPLOYED_R6_CHANGE_CONTROL no encontrado")


def test_no_spurious_risk_for_lab_qc_deployed():
    """lab_qc_project tiene deployment activo — NO debe tener RISK_PORT_UNDEPLOYED."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_LAB_QC_PROJECT" not in ids, (
        "lab_qc_project tiene deployment activo y no debe ser zombie"
    )
