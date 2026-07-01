"""
Guard U5: todos los endpoints que el refresh() y el status-check llaman
deben ser READ-ONLY — no deben incrementar la cadena de auditoría.

Si este test falla, algún endpoint de observación tiene efecto secundario
que escribe en factory_audit.jsonl (violación del invariante Part-11).
"""

import json
import sys
from pathlib import Path

import pytest
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import AUDIT_FILE

FACTORY_URL = "http://localhost:9000"

# Obtener la API key del contenedor en tiempo de ejecución
def _get_api_key() -> str:
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "factory-api", "printenv", "FACTORY_API_KEY"],
        capture_output=True, text=True, timeout=5,
    )
    key = r.stdout.strip()
    if not key:
        pytest.skip("factory-api no disponible o FACTORY_API_KEY no definida")
    return key


def _count_audit_lines() -> int:
    if not AUDIT_FILE.exists():
        return 0
    return sum(1 for l in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if l.strip())


# Endpoints GET del refresh() de mission_control.html (todos los views)
REFRESH_ENDPOINTS = [
    "/api/v1/status/full",
    "/api/v1/layer9/missions",
    "/api/v1/layer8/jobs",
    "/api/v1/layer9/review-queue",
    "/api/v1/layer8/status",
    "/api/v1/deployments/lab_qc_project",
    "/api/v1/status/risks",
    "/api/v1/audit/verify",
    "/api/v1/audit/entries?limit=20",
    "/api/v1/status/resources",
    # U5: nuevo endpoint de lectura de reporte cacheado
    "/api/v1/deployments/lab_qc_project/gates-report",
    # pipeline refresh endpoints
    "/api/v1/layer8/workspaces/r6_change_control/tree",
    "/api/v1/layer8/missions/r6_change_control/artifacts",
    # W4: consola de pruebas funcionales — catálogo e historial son READER puro
    "/api/v1/layer9/missions/oos_hplc_investigator/test-catalog",
    "/api/v1/layer9/missions/oos_hplc_investigator/test-results?limit=50",
]


def test_refresh_endpoints_are_readonly():
    """
    Llama cada endpoint de observación N veces y verifica que el
    contador de líneas en factory_audit.jsonl no crece.
    """
    api_key = _get_api_key()
    headers = {"x-api-key": api_key}

    N = 3
    baseline = _count_audit_lines()

    with httpx.Client(base_url=FACTORY_URL, timeout=15.0) as client:
        for _ in range(N):
            for path in REFRESH_ENDPOINTS:
                try:
                    client.get(path, headers=headers)
                except Exception:
                    pass  # 404 es OK — lo que importa es que no escribe

    after = _count_audit_lines()
    delta = after - baseline

    assert delta == 0, (
        f"INVARIANTE ROTA: {delta} entrada(s) nueva(s) en la cadena de auditoría "
        f"después de {N} rondas de refresh. "
        f"Algún endpoint GET tiene efecto secundario de escritura."
    )


def test_gates_report_is_readonly():
    """
    GET /gates-report específicamente: no debe escribir auditoría
    y debe devolver el reporte cacheado (200) o 404 limpio.
    """
    api_key = _get_api_key()
    headers = {"x-api-key": api_key}

    baseline = _count_audit_lines()

    with httpx.Client(base_url=FACTORY_URL, timeout=10.0) as client:
        r = client.get("/api/v1/deployments/lab_qc_project/gates-report", headers=headers)
        assert r.status_code in (200, 404), (
            f"GET /gates-report devolvió {r.status_code} inesperado"
        )
        if r.status_code == 200:
            data = r.json()
            assert "summary" in data, "Reporte cacheado no tiene campo 'summary'"
            assert "gates" in data, "Reporte cacheado no tiene campo 'gates'"

    after = _count_audit_lines()
    assert after == baseline, (
        f"GET /gates-report escribió {after - baseline} entrada(s) en la cadena de auditoría"
    )
