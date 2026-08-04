"""Panel ARQ 2026-08-04 §4 -- flujo de firma del panel `catalog-version`,
AISLADO: navegador real contra los archivos estáticos reales (GET,
inofensivo), pero TODA llamada a `/api/v1/layer9/governance/**` se
intercepta y se sirve desde fixtures controladas. Cero POSTs reales llegan
al servidor -- se prueba interceptando la ruta del POST de firma
(`/governance/artifact-version/sign`) y confirmando que NUNCA se dispara
salvo cuando el test la espera explícitamente (y en ese caso también se
intercepta, nunca llega de verdad).

Mismo patrón que `test_governance_ui_stale_state_playwright.py` (reutiliza
su fixture de navegador si Playwright está disponible). Se salta si no hay
servidor vivo (sirve los estáticos) -- prueba de integración de UI, no
unitaria.

FRAGILIDAD YA DOCUMENTADA (mismo hallazgo que
`test_governance_ui_stale_state_playwright.py`): lanzar varios contextos de
Chromium seguidos en el mismo proceso Python es poco fiable bajo carga --
verificado el 2026-08-04: los 5 tests de este archivo pasan limpio en
aislamiento (uno a la vez), pero corriendo el archivo COMPLETO de una vez
pueden fallar por timeout en `#apikey`/`wait_for_function` sin que el
código probado esté involucrado. Es contención de recursos del entorno,
no un defecto de la UI ni del backend."""
import hashlib
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BASE = os.environ.get("FACTORY_UI_BASE", "http://localhost:9000")
CATALOG = "factory/regulatory/requirement_catalog/requirements.yaml"
GOLDEN = "factory/regulatory/golden_dataset/semantic_verification_golden_dataset.py"
HASH_LIVE = "7ae4aaf28534b769271d7b9e50837191922cbf4db46067f2a768733c3fbcaf16"
HASH_OLD = "dc017efbdf5a4f80ab0c360f138ebce2a97581cf2f754421555e19a587362a5e"


def _servidor_vivo() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _servidor_vivo(), reason="requiere factory-api vivo (prueba de integracion de UI)")


def _api_key_del_env() -> str:
    if os.environ.get("FACTORY_API_KEY"):
        return os.environ["FACTORY_API_KEY"]
    env = REPO / "factory" / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("FACTORY_API_KEY="):
                return linea.split("=", 1)[1].strip()
    return "mock"


def _estado_base(*, with_valid_proposal: bool):
    """`with_valid_proposal=False` reproduce el estado ANTES de -005 (solo
    -001/-002/-003 huerfanas) -- boton debe quedar deshabilitado."""
    proposals = [
        {"decision_instance_id": "ARTIFACT_VERSION-2026-003",
         "resolved_target_ids": [CATALOG], "payload": {}, "proposal_state": "PROPOSED"},
        {"decision_instance_id": "ARTIFACT_VERSION-2026-004",
         "resolved_target_ids": [GOLDEN], "payload": {"artifact_path": GOLDEN},
         "proposal_state": "PROPOSED"},
    ]
    if with_valid_proposal:
        proposals.append({
            "decision_instance_id": "ARTIFACT_VERSION-2026-005",
            "resolved_target_ids": [CATALOG],
            "payload": {"artifact_path": CATALOG, "artifact_hash_before": HASH_LIVE,
                       "from_version": "2.0", "to_version": "2.1",
                       "expected_hash_after": HASH_LIVE, "change_reason": "test playwright"},
            "proposal_state": "PROPOSED",
        })
    return {
        "state_hash": "a" * 64,
        "families": {"D1": {}, "D2": {}, "D3": {}, "D4": {}, "D5": {},
                     "ARTIFACT_VERSION": {"label": "Aprobacion de version"}},
        "coverage": {
            "D1": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
            "D2": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
            "D3": {"unavailable_reason": "x"},
            "D4": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
            "D5": {"registry_ids": [], "covered_ids": [], "uncovered_ids": [],
                   "reconstructed_only_ids": [], "revoked_ids": [], "active_instances": []},
            "ARTIFACT_VERSION": {"registry_ids": [CATALOG], "covered_ids": [CATALOG],
                   "uncovered_ids": [], "reconstructed_only_ids": [], "revoked_ids": [],
                   "active_instances": [p["decision_instance_id"] for p in proposals] + ["ARTIFACT_VERSION-2026-002"],
                   "confirmed_active_instances": ["ARTIFACT_VERSION-2026-002"]},
        },
        "artifacts": {"status": "FAIL", "fail_count": 1, "warn_count": 26,
                      "artifacts_seen": 28, "records_in_store": 31,
                      "catalog_state": {
                          "artifact_id": CATALOG, "found": True,
                          "live_version": "2.0", "live_sha256": HASH_LIVE,
                          "last_approved_version": "2.0", "last_approved_sha256": HASH_OLD,
                          "approved_by_decision": "ARTIFACT_VERSION-2026-002"}},
        "proposals": {"ARTIFACT_VERSION": proposals},
        "audit": {"content_hash_integrity": "VERIFIED", "hash_errors": 0, "log_count": 1,
                   "chain_continuity": "VERIFIED", "chain_errors": 0,
                   "historical_fork_present": False, "new_forks_since_baseline": 0,
                   "part11_compliant": "NOT_DETERMINED",
                   "unbacked_known_fork_entry_ids": [], "new_fork_entry_ids": []},
        "critical_path": [{"gate": "G4", "status": "LISTO", "blocked_by": []}],
        "preventive_measures": [],
        "family_state_hashes": {"D1": "d1"+"0"*62, "D2": "d2"+"0"*62, "D3": "d3"+"0"*62,
                                  "D4": "d4"+"0"*62, "D5": "d5"+"0"*62,
                                  "ARTIFACT_VERSION": "av"+"0"*62},
        "active_instances": {"D1": None, "D2": None, "D3": None, "D4": None, "D5": None,
                             "ARTIFACT_VERSION": "ARTIFACT_VERSION-2026-002"},
        "read_at": "2026-08-04T00:00:00Z",
    }


@pytest.fixture(scope="module")
def _browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield navegador
        navegador.close()


def _abrir_panel(browser, estado, *, sign_handler=None):
    contexto = browser.new_context()
    pg = contexto.new_page()
    llamadas = {"sign": 0, "sign_bodies": []}

    def _route(route):
        url, method = route.request.url, route.request.method
        if url.endswith("/governance/state") and method == "GET":
            route.fulfill(status=200, content_type="application/json", body=json.dumps(estado))
        elif "/governance/artifact-version/sign" in url and method == "POST":
            llamadas["sign"] += 1
            llamadas["sign_bodies"].append(json.loads(route.request.post_data or "{}"))
            if sign_handler:
                sign_handler(route)
            else:
                route.fulfill(status=201, content_type="application/json",
                              body=json.dumps({"decision_instance_id": "ARTIFACT_VERSION-2026-006"}))
        else:
            route.continue_()

    pg.route("**/api/v1/layer9/governance/**", _route)
    pg.goto(f"{BASE}/ui/mission_control.html", wait_until="domcontentloaded")
    pg.wait_for_selector("#apikey", timeout=20000)
    pg.fill("#apikey", _api_key_del_env())
    pg.click("text=Conectar")
    pg.wait_for_function(
        "document.getElementById('conn') && "
        "document.getElementById('conn').textContent.includes('conectado')", timeout=15000)
    pg.click('button[data-v="gobierno"]')
    pg.wait_for_function(
        "document.getElementById('gov-state-hash') && "
        "document.getElementById('gov-state-hash').textContent.length > 0", timeout=15000)
    pg.evaluate("window.govOpen && window.govOpen('catalog-version')")
    pg.wait_for_selector("#catv-status", timeout=10000)
    return contexto, pg, llamadas


def test_render_shows_005_and_never_004_or_1_0_to_2_0(_browser):
    contexto, pg, _ = _abrir_panel(_browser, _estado_base(with_valid_proposal=True))
    try:
        html = pg.evaluate("document.getElementById('gov-body').innerHTML")
        assert "ARTIFACT_VERSION-2026-005" in html
        assert "1.0 → 2.0" not in html
        assert HASH_LIVE in html
        # -004 (golden_dataset) no debe listarse como propuesta de este panel
        seccion = html.split("PROPUESTAS ARTIFACT_VERSION PARA ESTE ARTEFACTO")[1]
        seccion = seccion.split("MOTIVO")[0]
        assert "ARTIFACT_VERSION-2026-004" not in seccion
    finally:
        contexto.close()


def test_button_disabled_without_a_valid_proposal(_browser):
    contexto, pg, _ = _abrir_panel(_browser, _estado_base(with_valid_proposal=False))
    try:
        disabled = pg.eval_on_selector("#catv-submit-btn", "e=>e.disabled")
        assert disabled is True
        html = pg.evaluate("document.getElementById('gov-body').innerHTML")
        assert "No hay ninguna propuesta con la transición vigente" in html
    finally:
        contexto.close()


def test_button_enabled_and_signs_with_full_echo_back_when_valid(_browser):
    contexto, pg, llamadas = _abrir_panel(_browser, _estado_base(with_valid_proposal=True))
    try:
        disabled = pg.eval_on_selector("#catv-submit-btn", "e=>e.disabled")
        assert disabled is False

        pg.fill("#catv-reason", "prueba playwright aislada")
        pg.fill("#catv-id", "cesar")
        pg.fill("#catv-name", "Cesar May")
        pg.click("text=Confirmar ARTIFACT_VERSION-2026-005")
        pg.wait_for_function(
            "(document.getElementById('catv-status')?.textContent||'').length > 0", timeout=10000)

        assert llamadas["sign"] == 1, "debe llamar EXACTAMENTE una vez al endpoint de firma"
        body = llamadas["sign_bodies"][0]
        assert body["proposal_id"] == "ARTIFACT_VERSION-2026-005"
        assert body["artifact_path"] == CATALOG
        assert body["from_version"] == "2.0" and body["to_version"] == "2.1"
        assert body["artifact_hash_before"] == HASH_LIVE
        assert body["expected_hash_after"] == HASH_LIVE
        assert body["approved_by_id"] == "cesar"
        assert body["approved_by_display_name"] == "Cesar May"
    finally:
        contexto.close()


def test_409_proposal_mismatch_is_rendered_persistently(_browser):
    def _mismatch(route):
        route.fulfill(status=409, content_type="application/json",
                      body=json.dumps({"detail": {"detail": "no coincide",
                                                   "reason": "proposal_mismatch"}}))
    contexto, pg, llamadas = _abrir_panel(
        _browser, _estado_base(with_valid_proposal=True), sign_handler=_mismatch)
    try:
        pg.fill("#catv-reason", "prueba 409")
        pg.fill("#catv-id", "cesar")
        pg.click("text=Confirmar ARTIFACT_VERSION-2026-005")
        pg.wait_for_function(
            "(document.getElementById('catv-status')?.textContent||'').length > 0", timeout=10000)
        status = pg.evaluate("document.getElementById('catv-status')?.textContent || ''")
        assert "409" in status
        assert "recarga" in status.lower() or "distinta" in status.lower()
        assert llamadas["sign"] == 1
    finally:
        contexto.close()


def test_409_stale_state_is_rendered_persistently(_browser):
    def _stale(route):
        route.fulfill(status=409, content_type="application/json",
                      body=json.dumps({"detail": {"detail": "state_hash obsoleto",
                                                   "reason": "stale_state"}}))
    contexto, pg, llamadas = _abrir_panel(
        _browser, _estado_base(with_valid_proposal=True), sign_handler=_stale)
    try:
        pg.fill("#catv-reason", "prueba stale")
        pg.fill("#catv-id", "cesar")
        pg.click("text=Confirmar ARTIFACT_VERSION-2026-005")
        pg.wait_for_function(
            "(document.getElementById('catv-status')?.textContent||'').length > 0", timeout=10000)
        status = pg.evaluate("document.getElementById('catv-status')?.textContent || ''")
        assert "409" in status
        assert llamadas["sign"] == 1
    finally:
        contexto.close()
