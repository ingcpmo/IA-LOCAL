"""Paquete 4/K2 (2026-08-19) -- verificación end-to-end contra la UI viva
real de: (a) el listado de paquetes de remediación (nuevo endpoint
GET /api/v1/remediation-packages/{project_id} + panel nuevo en
mission_control.html/remediation.js), y (b) el panel de candidatos
governance_candidate (NCR/CAPA sugeridos, Paquete 1a) en review.js.

Mismo patrón que test_review_queue_finding_ui_playwright.py: TODAS las
llamadas de red se interceptan con page.route -- cero POST/GET reales
llegan a producción, solo /health y los estáticos."""
from __future__ import annotations

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


pytestmark = [
    pytest.mark.requires_live_ui,
    pytest.mark.skipif(
        not _servidor_vivo(), reason="requiere factory-api vivo (prueba de integracion de UI)"),
]


def _api_key_del_env() -> str:
    env = REPO / "factory" / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("FACTORY_API_KEY="):
                return linea.split("=", 1)[1].strip()
    return "mock"


_VALID_IDENTITY_KEY = "test-identity-key-k2-playwright"

_CANDIDATE_ENTRY = {
    "schema_version": "governance_candidate_v1",
    "rc_id": "candidate-chunked-test-21_CFR_11.10(e)",
    "entry_type": "governance_candidate",
    "project_id": "RW-TEST",
    "enqueued_at": "2026-08-19T00:00:00+00:00",
    "status": "pending",
    "summary": {
        "run_id": "chunked-test", "requirement_id": "21_CFR_11.10(e)",
        "document_id": "RW-TEST", "conclusion": "DOCUMENTATION_GAP",
        "suggested_type": "NCR", "rationale": "primera aparición, fixture de test",
        "prior_occurrences": 0, "agent_id": "fda_part11_agent",
    },
}

_PACKAGES_LIST = {
    "packages": [
        {"project_id": "RW-TEST", "package_id": "PKG-TEST-1", "version": 2,
         "other_versions": [1], "status": "AWAITING_PACKAGE_DECISION",
         "risk_counts": {"low_risk": 1, "medium_risk": 0, "high_risk": 0},
         "automatic_evaluation_complete": True, "human_exception_review_complete": True,
         "package_decision": None},
    ],
}


@pytest.fixture(scope="module")
def _browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield navegador
        navegador.close()


@pytest.fixture()
def pagina(_browser):
    contexto = _browser.new_context()
    page = contexto.new_page()
    try:
        llamadas = {"decide_calls": []}

        def _route(route):
            url = route.request.url
            method = route.request.method
            if url.endswith("/api/v1/layer9/review-queue") and method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "pending": [_CANDIDATE_ENTRY],
                    "summary": {"pending": 1, "approved": 0, "rejected": 0, "returned": 0, "superseded": 0},
                }))
            elif "/review/candidates/" in url and url.endswith("/decide") and method == "POST":
                body = json.loads(route.request.post_data or "{}")
                identity_key = route.request.headers.get("x-identity-key", "")
                llamadas["decide_calls"].append({"body": body, "identity_key": identity_key})
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "rc_id": _CANDIDATE_ENTRY["rc_id"], "decision": body.get("decision"),
                    "reviewer": "Cesar", "human_classification": body.get("human_classification"),
                }))
            elif url.endswith("/api/v1/remediation-packages/RW-TEST") and method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(_PACKAGES_LIST))
            elif url.endswith("/api/v1/remediation-packages/RW-TEST/PKG-TEST-1/2") and method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "package": {"package_id": "PKG-TEST-1", "package_version": 2,
                                "status": "AWAITING_PACKAGE_DECISION", "project_id": "RW-TEST",
                                "artifacts": {}, "changes": {"low_risk": [], "medium_risk": [], "high_risk": []},
                                "automatic_evaluation_complete": True,
                                "human_exception_review_complete": True},
                    "changes": {}, "exceptions": {}, "medium_risk_batch_decisions": {},
                    "package_decision": None,
                }))
            else:
                route.continue_()

        page.route("**/api/v1/layer9/review**", _route)
        page.route("**/api/v1/remediation-packages/**", _route)

        page.goto(f"{BASE}/ui/mission_control.html", wait_until="domcontentloaded")
        page.wait_for_selector("#apikey", timeout=20000)
        page.fill("#apikey", os.environ.get("FACTORY_API_KEY") or _api_key_del_env())
        page.fill("#identitykey", _VALID_IDENTITY_KEY)
        page.click("text=Conectar")
        page.wait_for_function(
            "document.getElementById('conn') "
            "&& document.getElementById('conn').textContent.includes('conectado')",
            timeout=15000)
        yield page, llamadas
    finally:
        contexto.close()


def test_governance_candidate_card_renders_and_confirms(pagina):
    page, calls = pagina
    page.click('button[data-v="review"]')
    page.wait_for_selector("#review-list .rc", timeout=15000)
    assert page.locator("#review-list :text('21_CFR_11.10(e)')").count() > 0
    assert "primera aparición" in page.locator("#review-list").inner_text()

    page.select_option("select[id^='candidate-type-']", "NCR")
    page.click("button:has-text('Confirmar clasificación')")
    page.wait_for_function(
        "document.getElementById('_toast') && document.getElementById('_toast').textContent.length > 0",
        timeout=8000)
    assert len(calls["decide_calls"]) == 1
    assert calls["decide_calls"][0]["body"]["decision"] == "confirmed"
    assert calls["decide_calls"][0]["body"]["human_classification"] == "NCR"
    assert calls["decide_calls"][0]["identity_key"] == _VALID_IDENTITY_KEY


def test_package_list_panel_renders_and_opens_detail(pagina):
    page, _ = pagina
    page.click('button[data-v="remediacion"]')
    page.fill("#rpl-project", "RW-TEST")
    page.click("text=Listar paquetes")
    page.wait_for_selector("#remediation-packages-list .card", timeout=10000)
    text = page.locator("#remediation-packages-list").inner_text()
    assert "PKG-TEST-1" in text
    assert "AWAITING_PACKAGE_DECISION" in text

    page.click("text=Ver / adjudicar")
    page.wait_for_function(
        "document.getElementById('rp-project') && document.getElementById('rp-project').value === 'RW-TEST'",
        timeout=5000)
    assert page.locator("#rp-package").input_value() == "PKG-TEST-1"
    assert page.locator("#rp-version").input_value() == "2"
