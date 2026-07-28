"""
Guard U8/U12: riesgos de observabilidad — lógica de endpoint y estado post-U12.

U8  — verificó que /status/risks exponía R6+R7 para r6_change_control.
U12 — r6_change_control cancelada y archivada; ambos riesgos resueltos.

Corrección 2026-07-28. Dos de estos tests afirmaban una FOTOGRAFÍA del mundo
("hoy r6 no tiene riesgo") en vez del invariante que U12 estableció ("una
misión resuelta no deja un riesgo zombie"). Cuando Cesar devolvió
r6_change_control a ajustes desde Mission Control —una transición gobernada,
legítima y auditada— el riesgo apareció CORRECTAMENTE y los dos tests
fallaron, tumbando Gate 0.

Eso creaba una presión perversa: cerrar una misión real para que pasara la
suite. La expectativa se corrige para medir la regla, no el estado del día:
el riesgo debe estar presente si y solo si la misión está devuelta. Así se
sigue detectando el zombie (riesgo sin misión devuelta) sin exigir que
ninguna misión vuelva a devolverse jamás.
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


def _mission_status(project_id):
    import httpx
    r = httpx.get("http://localhost:9000/api/v1/layer9/missions",
                  headers={"x-api-key": _get_api_key()}, timeout=10)
    assert r.status_code == 200
    for m in r.json():
        if m["project_id"] == project_id:
            return m["status"]
    return None


def test_r6_remediation_risk_tracks_the_real_mission_state():
    """El riesgo de remediación existe si y solo si la misión está en
    returned_to_adjustments. Detecta el zombie de U12 (riesgo persistente sin
    misión devuelta) sin romperse cuando alguien devuelve una misión de
    verdad."""
    ids = [r["id"] for r in _get_risks()["risks"]]
    present = "RISK_REMEDIATION_R6_CHANGE_CONTROL" in ids
    returned = _mission_status("r6_change_control") == "returned_to_adjustments"
    assert present == returned, (
        "el riesgo de remediación no corresponde al estado real de la misión: "
        f"riesgo_presente={present}, misión_devuelta={returned}"
    )


def test_no_zombie_port_r6_after_u12():
    """U12: puerto 8102 liberado del registry — RISK_PORT_UNDEPLOYED_R6 debe estar ausente."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_R6_CHANGE_CONTROL" not in ids, (
        f"Puerto 8102 liberado en U12 pero el riesgo zombie persiste: {ids}"
    )


def test_every_blocking_risk_is_justified_by_a_real_state():
    """U12+V1, reformulado: no se exige "cero riesgos bloqueantes" —eso haría
    fallar la suite cada vez que la gobernanza detecta algo de verdad— sino
    que todo riesgo bloqueante corresponda a un estado real y comprobable.
    Un riesgo sin causa verificable sigue siendo un fallo."""
    blocking = [r for r in _get_risks()["risks"] if r.get("severity") not in ("info",)]
    unjustified = []
    for risk in blocking:
        if risk["id"].startswith("RISK_REMEDIATION_"):
            pid = risk["id"].removeprefix("RISK_REMEDIATION_").lower()
            if _mission_status(pid) != "returned_to_adjustments":
                unjustified.append(risk)
        else:
            unjustified.append(risk)
    assert unjustified == [], f"riesgos bloqueantes sin estado real que los sustente: {unjustified}"


def test_returned_mission_yields_no_go_never_a_false_approval():
    """Requisito explícito: una misión devuelta (o rechazada) debe producir
    NO-GO. El riesgo visible no puede convivir con un readiness que la dé por
    aprobada."""
    import httpx
    status = _mission_status("r6_change_control")
    if status not in ("returned_to_adjustments", "rejected"):
        pytest.skip(f"r6_change_control está en '{status}': este test aplica a devuelta/rechazada")

    r = httpx.get("http://localhost:9000/api/v1/layer9/missions/r6_change_control/readiness",
                  headers={"x-api-key": _get_api_key()}, timeout=10)
    assert r.status_code == 200
    readiness = r.json()
    assert readiness["verdict"] == "no_go", f"verdict={readiness['verdict']} para misión {status}"

    approved = next(d for d in readiness["dimensions"] if d["id"] == "mission_approved")
    assert approved["status"] != "ready", (
        f"una misión '{status}' no puede contar como aprobada: {approved}")
    assert status in approved["evidence"], (
        "la evidencia debe nombrar el estado real, no una aprobación histórica")


def test_no_spurious_risk_for_lab_qc_deployed():
    """lab_qc_project tiene deployment activo — NO debe tener RISK_PORT_UNDEPLOYED."""
    data = _get_risks()
    ids = [r["id"] for r in data["risks"]]
    assert "RISK_PORT_UNDEPLOYED_LAB_QC_PROJECT" not in ids, (
        "lab_qc_project tiene deployment activo y no debe ser zombie"
    )
