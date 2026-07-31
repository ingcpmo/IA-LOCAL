"""W5V2_FIX_FIRMA_SILENCIOSA -- feedback visible en TODAS las ramas de la
firma, y deteccion proactiva de estado obsoleto (H1).

REGLA ABSOLUTA de docs_plan/W5V2_FIX_FIRMA_SILENCIOSA.md: ninguna prueba de
firma toca el backend de produccion con una identidad inventada, ni siquiera
de prueba. Este fichero no lo hace: interceptA (`page.route`) TODAS las
llamadas a /api/v1/layer9/governance/* y las sirve con fixtures controladas.
El unico trafico real hacia factory-api es el GET de los archivos estaticos
(HTML/JS), que no escribe nada. Cero POSTs reales llegan al servidor.

Se SALTA si no hay servidor vivo -- misma politica que
test_governance_signature_flow_live_playwright.py.
"""
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASE = os.environ.get("FACTORY_UI_BASE", "http://localhost:9000")


def _servidor_vivo() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _servidor_vivo(), reason="requiere factory-api vivo (prueba de integracion de UI)")


def _estado_base(state_hash="a" * 64, d2_hash="d2" + "0" * 62):
    return {
        "state_hash": state_hash,
        "families": {"D1": {"label": "Fuentes"}, "D2": {"label": "Packs"},
                      "D3": {}, "D4": {}, "D5": {}},
        "coverage": {
            "D1": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": [],
                   "confirmed_active_instances": []},
            "D2": {"registry_ids": ["21_CFR_211.68(b)"], "covered_ids": [],
                   "uncovered_ids": ["21_CFR_211.68(b)"], "reconstructed_only_ids": [],
                   "revoked_ids": [], "active_instances": [], "confirmed_active_instances": []},
            "D3": {"unavailable_reason": "x"},
            "D4": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
            "D5": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
        },
        "audit": {"content_hash_integrity": "VERIFIED", "hash_errors": 0, "log_count": 1,
                   "chain_continuity": "VERIFIED", "chain_errors": 0,
                   "historical_fork_present": False, "new_forks_since_baseline": 0,
                   "part11_compliant": "NOT_DETERMINED",
                   "unbacked_known_fork_entry_ids": [], "new_fork_entry_ids": []},
        "critical_path": [{"gate": "G4", "status": "LISTO", "blocked_by": []}],
        "preventive_measures": [],
        "family_state_hashes": {"D1": "d1" + "0" * 62, "D2": d2_hash, "D3": "d3" + "0" * 62,
                                  "D4": "d4" + "0" * 62, "D5": "d5" + "0" * 62},
        "active_instances": {"D1": None, "D2": None, "D3": None, "D4": None, "D5": None},
        "read_at": "2026-07-31T00:00:00Z",
    }


@pytest.fixture(scope="module")
def _browser():
    """Un solo proceso de Chromium para todo el modulo. Lanzar un
    `sync_playwright()` completo por test resulto poco fiable a partir del
    tercero en el mismo proceso Python (timeouts en el primer selector,
    antes de tocar nada del codigo probado) -- reutilizar el navegador y
    abrir un contexto nuevo por test es el patron estandar de Playwright y
    evita ese degradado."""
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield navegador
        navegador.close()


@pytest.fixture()
def pagina_con_mock(_browser):
    """Pagina real, pero CERO trafico de escritura llega al servidor: toda
    llamada a /governance/ se responde desde aqui."""
    contexto = _browser.new_context()
    pg = contexto.new_page()
    try:
        estado = {"actual": _estado_base()}
        llamadas = {"propose": 0, "confirm": 0, "state_get": 0}

        def _route(route):
            url = route.request.url
            method = route.request.method
            if url.endswith("/governance/state") and method == "GET":
                llamadas["state_get"] += 1
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(estado["actual"]))
            elif "/governance/decisions/D2/propose" in url and method == "POST":
                llamadas["propose"] += 1
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"detail": "mock: no deberia llegar aqui en el test de stale"}))
            elif "/confirm" in url and method == "POST":
                llamadas["confirm"] += 1
                route.fulfill(status=200, content_type="application/json", body="{}")
            else:
                route.continue_()

        pg.route("**/api/v1/layer9/governance/**", _route)
        # "networkidle" se observo poco fiable al lanzar varios navegadores
        # seguidos en el mismo proceso (colas de conexion previas) -- se
        # espera el DOM y despues el propio selector, condicion real.
        pg.goto(f"{BASE}/ui/mission_control.html", wait_until="domcontentloaded")
        pg.wait_for_selector("#apikey", timeout=20000)
        # flujo real de la app: Conectar (GET /health, real e inofensivo) y
        # abrir la pestaña de gobierno -- dispara refresh('gobierno') ->
        # GET /governance/state, que SI cae en el mock de arriba.
        # Se espera la CONDICION real (conectado, luego GOV cargado), no un
        # timeout fijo: bajo carga (muchos chromium seguidos) un numero fijo
        # de ms es la fuente mas comun de flakiness, no el codigo probado.
        pg.fill("#apikey", os.environ.get("FACTORY_API_KEY") or _api_key_del_env())
        pg.click("text=Conectar")
        pg.wait_for_function(
            "document.getElementById('conn') "
            "&& document.getElementById('conn').textContent.includes('conectado')",
            timeout=15000)
        pg.click('button[data-v="gobierno"]')
        pg.wait_for_function(
            "document.getElementById('gov-state-hash') "
            "&& document.getElementById('gov-state-hash').textContent.length > 0",
            timeout=15000)
        yield pg, estado, llamadas
    finally:
        contexto.close()


def _api_key_del_env() -> str:
    env = REPO / "factory" / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("FACTORY_API_KEY="):
                return linea.split("=", 1)[1].strip()
    return "mock"


def test_stale_state_detection_blocks_and_recovers(pagina_con_mock):
    """H1: el escenario que produce el sintoma real. La pagina carga con un
    state_hash; algo (otra pestaña, otra firma) lo cambia; al recuperar foco
    la pestaña, el nuevo checkStaleness() lo detecta SIN esperar a que el
    POST falle -- antes del fix, el primer indicio era un 409 silencioso.
    Combina las dos mitades (bloqueo + recuperacion) en un solo test para
    no multiplicar contextos de navegador en el mismo proceso."""
    pg, estado, llamadas = pagina_con_mock
    pg.evaluate("window.govOpen && window.govOpen('pack-211')")
    pg.wait_for_selector("#pk211-status", timeout=10000)

    assert "El estado cambió" not in pg.evaluate("document.getElementById('gov-body').innerHTML")

    # el estado en el "servidor" (mock) cambia -- state_hash global distinto,
    # como pasaria tras cualquier escritura de otra pestaña o firma
    estado["actual"] = _estado_base(state_hash="b" * 64)
    pg.evaluate("window.dispatchEvent(new Event('focus'))")
    pg.wait_for_function(
        "document.getElementById('gov-body').innerHTML.includes('El estado cambió')",
        timeout=10000)

    body = pg.evaluate("document.getElementById('gov-body').innerHTML")
    assert "El estado cambió" in body, "el banner de estado obsoleto no aparecio"
    assert "Recargar estado" in body

    # intentar firmar de todos modos: bloqueado ANTES de cualquier POST real
    pg.fill("#pk211-reason", "prueba stale")
    pg.fill("#pk211-id", "identidad_de_prueba_no_reservada")
    pg.click("text=Registrar aprobación")
    pg.wait_for_timeout(500)
    assert llamadas["propose"] == 0, "no debe salir ningun POST con el estado marcado obsoleto"
    status = pg.evaluate("document.getElementById('pk211-status')?.textContent || ''")
    assert "estado cambió" in status.lower() or "recarga" in status.lower()

    # "Recargar estado" limpia el aviso (el mock ya sirve el hash nuevo)
    pg.click("text=Recargar estado")
    pg.wait_for_function(
        "!document.getElementById('gov-body').innerHTML.includes('El estado cambió')",
        timeout=10000)
    assert "El estado cambió" not in pg.evaluate("document.getElementById('gov-body').innerHTML")


def test_every_response_branch_renders_a_persistent_message(pagina_con_mock):
    """Antes del fix, toast() era la UNICA senal (se desvanece en 2.2s). Cada
    rama de respuesta ahora escribe ademas en una linea persistente
    (`#pk211-status`) que un humano puede leer sin haber mirado la esquina
    en el instante exacto. Cubre 409 y excepcion de red en un solo test."""
    pg, estado, llamadas = pagina_con_mock

    def _route_409(route):
        if "/governance/decisions/D2/propose" in route.request.url and route.request.method == "POST":
            route.fulfill(status=409, content_type="application/json",
                          body=json.dumps({"detail": "state_hash obsoleto: recarga y revisa"}))
        elif route.request.url.endswith("/governance/state"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(estado["actual"]))
        else:
            route.continue_()

    pg.unroute("**/api/v1/layer9/governance/**")
    pg.route("**/api/v1/layer9/governance/**", _route_409)
    pg.evaluate("window.govOpen && window.govOpen('pack-211')")
    pg.wait_for_selector("#pk211-status", timeout=10000)

    pg.fill("#pk211-reason", "prueba 409")
    pg.fill("#pk211-id", "identidad_de_prueba_no_reservada")
    pg.click("text=Registrar aprobación")
    pg.wait_for_function(
        "(document.getElementById('pk211-status')?.textContent||'').length > 0", timeout=10000)
    status = pg.evaluate("document.getElementById('pk211-status')?.textContent || ''")
    assert "409" in status or "conflicto" in status.lower(), (
        f"la rama 409 debe quedar escrita en la linea persistente, no solo en un toast: {status!r}")

    # segunda mitad: excepcion de red -- misma pagina, se reemplaza la ruta
    def _route_abort(route):
        if "/governance/decisions/D2/propose" in route.request.url and route.request.method == "POST":
            route.abort("failed")
        elif route.request.url.endswith("/governance/state"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps(estado["actual"]))
        else:
            route.continue_()

    pg.unroute("**/api/v1/layer9/governance/**")
    pg.route("**/api/v1/layer9/governance/**", _route_abort)
    pg.fill("#pk211-reason", "prueba red caida")
    pg.fill("#pk211-id", "identidad_de_prueba_no_reservada")
    pg.click("text=Registrar aprobación")
    pg.wait_for_function(
        "(document.getElementById('pk211-status')?.textContent||'').toLowerCase().includes('error')",
        timeout=10000)
    status2 = pg.evaluate("document.getElementById('pk211-status')?.textContent || ''")
    assert "error" in status2.lower()

    # el boton se restaura (no queda deshabilitado colgado tras la excepcion)
    disabled = pg.eval_on_selector("#pk211-submit-btn", "e=>e.disabled")
    assert disabled is False
