"""Panel ARQ 2026-08-04 (§3.2/RC-5): "local == servido == cargado" como
prueba automatizada, no como diagnóstico manual repetido cada vez.

RC-5 (causa raíz real del bloqueo de firma original): `uvicorn` corre SIN
`--reload`, así que un `docker restart factory-api` es la ÚNICA forma de
que el proceso vivo recoja código nuevo -- el volumen bind-mount ya tiene
el archivo nuevo en disco, pero el proceso sigue sirviendo lo que cargó al
arrancar. Nada en Python detecta esto solo (un `python -c` nuevo siempre
lee el disco actual, que es justo el falso positivo que produjo el
diagnóstico equivocado original -- ver
`test_governance_signature_flow_live_playwright.py`).

Esta prueba SOLO LEE (nunca un POST): compara el sha256 de
`governance.js` en disco contra el que devuelve un GET real al proceso
vivo. Se salta limpio si no hay servidor+clave (prueba de integración
contra un despliegue, no una unitaria)."""
import hashlib
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASE = os.environ.get("FACTORY_UI_BASE", "http://localhost:9000")
GOVERNANCE_JS = REPO / "factory" / "ui" / "js" / "mission_control" / "governance.js"


def _api_key() -> str | None:
    if os.environ.get("FACTORY_API_KEY"):
        return os.environ["FACTORY_API_KEY"]
    env = REPO / "factory" / ".env"
    if not env.is_file():
        return None
    for linea in env.read_text(encoding="utf-8").splitlines():
        if linea.startswith("FACTORY_API_KEY="):
            return linea.split("=", 1)[1].strip()
    return None


def _servidor_vivo() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# R3-T1.8 bloque 3.3: ademas del skipif ya existente (mas fino, se
# autoevalua), se etiqueta con el marcador uniforme para que Gate 0 pueda
# filtrar TODOS los tests que exigen un servicio vivo con un solo flag
# (-m "not requires_live_ui"), ver factory/tests/conftest.py:pytest_configure.
pytestmark = [
    pytest.mark.requires_live_ui,
    pytest.mark.skipif(
        not _servidor_vivo() or not _api_key(),
        reason="prueba de integracion de solo lectura contra un despliegue vivo -- "
              "requiere servidor+clave alcanzables"),
]


def _get(path: str, *, headers: dict | None = None):
    import urllib.request
    req = urllib.request.Request(f"{BASE}{path}", headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.read(), dict(r.headers)


def test_governance_js_served_matches_disk_byte_for_byte():
    """RC-5: si esto falla, el proceso vivo NO tiene el código commiteado --
    `docker restart factory-api` (nunca asumir hot-reload)."""
    disk = GOVERNANCE_JS.read_bytes()
    status, served, _ = _get("/ui/js/mission_control/governance.js")
    assert status == 200
    assert hashlib.sha256(served).hexdigest() == hashlib.sha256(disk).hexdigest(), (
        "governance.js servido difiere del disco -- el proceso factory-api "
        "esta corriendo codigo viejo, reiniciar el contenedor")


def test_static_ui_assets_are_served_with_no_cache_header():
    """RC-4: sin esta cabecera, un navegador puede quedarse sirviendo JS
    viejo desde su cache local incluso despues de que el servidor ya tenga
    el nuevo -- exactamente el sintoma que reporto Cesar."""
    _, _, headers = _get("/ui/js/mission_control/governance.js")
    cache_control = headers.get("cache-control", "")
    assert "no-cache" in cache_control.lower(), (
        f"Cache-Control={cache_control!r} -- falta 'no-cache', un navegador "
        "podria servir una copia vieja sin revalidar")


def test_governance_state_endpoint_reachable_with_real_key():
    key = _api_key()
    status, body, _ = _get("/api/v1/layer9/governance/state", headers={"x-api-key": key})
    assert status == 200
    import json
    data = json.loads(body)
    assert "artifacts" in data and "proposals" in data


def test_artifact_version_proposals_endpoint_matches_catalog_state():
    """El endpoint canonico (§3.1) devuelve, para el catalogo, exactamente
    la propuesta real vigente hoy -- ARTIFACT_VERSION-2026-005, PROPOSED,
    payload_complete. Prueba de integracion honesta: si algun dia -005 ya
    fue firmada/aplicada, este test debe fallar y ser actualizado, no
    quedar verde sobre un supuesto viejo."""
    key = _api_key()
    catalog_path = "factory/regulatory/requirement_catalog/requirements.yaml"
    status, body, _ = _get(
        f"/api/v1/layer9/governance/artifact-version/proposals?artifact_path={catalog_path}",
        headers={"x-api-key": key})
    assert status == 200
    import json
    data = json.loads(body)
    ids = {p["proposal_id"] for p in data["proposals"]}
    assert "ARTIFACT_VERSION-2026-004" not in ids, "propuesta de otro artefacto filtrada mal"
    firmables = [p for p in data["proposals"]
                if p["status"] == "PROPOSED" and p["payload_complete"]]
    assert len(firmables) <= 1, f"mas de una propuesta firmable simultanea: {firmables}"


def _expected_routes_from_source() -> set[tuple[str, str]]:
    """R3-T1.8 bloque 3.1: extrae (metodo, path) de TODOS los decoradores
    `@router.<metodo>("...")` en factory/api/routes/*.py, combinados con el
    `prefix=` real de `APIRouter(...)` de cada archivo (p.ej. layer9.py ->
    "/api/v1/layer9") -- estatico, sin importar la app (evita side effects
    de import en un test de solo lectura). Fuente unica de "que deberia
    estar corriendo", comparable directo contra /openapi.json (que reporta
    paths completos, con prefijo)."""
    import re as _re
    routes: set[tuple[str, str]] = set()
    routes_dir = REPO / "factory" / "api" / "routes"
    prefix_re = _re.compile(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']*)["\']')
    route_re = _re.compile(r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']')
    for path in routes_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        prefix_match = prefix_re.search(text)
        prefix = prefix_match.group(1).rstrip("/") if prefix_match else ""
        for method, route_path in route_re.findall(text):
            # FastAPI/Starlette normaliza convertidores de tipo en el path
            # ("{x:path}", "{x:int}") a solo "{x}" al generar /openapi.json --
            # sin esto, una ruta real con convertidor se reportaria como
            # "ausente" por un artefacto de formato, nunca por desfase real.
            route_path = _re.sub(r"\{([^:}]+):[a-z]+\}", r"{\1}", route_path)
            full_path = prefix + route_path if route_path != "/" else (prefix or "/")
            routes.add((method.upper(), full_path))
    return routes


def test_deploy_freshness_all_source_routes_are_live():
    """R3-T1.8 bloque 3.1 -- lección directa del incidente de R3-T1.7
    (docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md bloque 4.4):
    `/api/v1/layer9/review/findings/{rc_id}/decide` estuvo un día entero
    commiteado (713f8a5) pero AUSENTE del proceso vivo -- "commiteado" no
    es "corriendo" (bind mount + sin --reload, mismo RC-5 que este archivo
    ya documentaba para el JS estático, nunca extendido al backend). Este
    test compara las rutas que el CÓDIGO FUENTE declara contra las que el
    servidor VIVO reporta en /openapi.json -- si falta alguna, es
    exactamente la señal que hubiera evitado el incidente:
    `docker compose -f factory/docker-compose.factory.yml restart factory-api`."""
    key = _api_key()
    status, body, _ = _get("/openapi.json", headers={"x-api-key": key})
    assert status == 200
    import json
    live_paths = json.loads(body).get("paths", {})
    live_routes = {
        (method.upper(), path)
        for path, methods in live_paths.items()
        for method in methods
    }
    expected = _expected_routes_from_source()
    missing = expected - live_routes
    assert not missing, (
        f"{len(missing)} ruta(s) del codigo fuente ausentes del servidor vivo: "
        f"{sorted(missing)} -- el contenedor factory-api esta sirviendo codigo "
        f"desactualizado. Reiniciar: docker compose -f "
        f"factory/docker-compose.factory.yml restart factory-api")
