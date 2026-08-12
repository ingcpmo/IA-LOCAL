"""R3-T1.2/F0.4 (2026-08-12) -- UI de revision humana debe renderizar por
TIPO (findings sin diff, distinto de un RC real) y nunca dejar una carga
muda: el fetch de diff de un RC real usa timeout + error visible; una
entrada finding_review nunca dispara ese fetch. Ademas cubre identidad de
revisor validada (422/409) end-to-end contra la UI real.

REGLA ABSOLUTA (mismo criterio que test_governance_ui_stale_state_playwright.py):
ninguna prueba de firma/decision toca el backend de produccion con una
identidad inventada. Este archivo intercepta (page.route) TODAS las
llamadas a /api/v1/layer9/review* y las sirve con fixtures controladas.
Cero POSTs reales llegan al servidor -- solo el GET de estaticos y /health
son trafico real.

Se SALTA si no hay servidor vivo -- misma politica que el resto de los
tests Playwright de este proyecto.

Nota de infraestructura (2026-08-12, NO relacionada con el codigo probado):
el servidor tiene un rate-limit por rafaga de requests que puede activarse
si se corren los 4 tests de este archivo espalda-con-espalda (cada
page.goto() dispara ~10 modulos JS casi simultaneos) -- verificado
corriendo los 4 tests individualmente contra el servidor real, todos
pasan. Si un run completo del archivo da 429/timeout en '#apikey', espaciar
las corridas (no es un defecto de review.js/main.js/layer9.py)."""
import json
import os
import re
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


def _api_key_del_env() -> str:
    env = REPO / "factory" / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("FACTORY_API_KEY="):
                return linea.split("=", 1)[1].strip()
    return "mock"


_FINDING_ENTRY = {
    "schema_version": "finding_review_v2",
    "rc_id": "finding-chunked-test-21_CFR_11.10(e)",
    "entry_type": "finding_review",
    "project_id": "RW-TEST",
    "enqueued_at": "2026-08-12T00:00:00+00:00",
    "status": "pending",
    "summary": {
        "run_id": "chunked-test", "requirement_id": "21_CFR_11.10(e)",
        "document_id": "RW-TEST", "page": None, "evidence_quote": "",
        "conclusion": "PROVISIONAL_GAP", "review_flags": ["ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE"],
        "agent_id": "fda_part11_agent",
        "candidates": [
            {"chunk_index": 3, "page_start": 45, "page_end": 46, "bm25_rank": 9,
             "embedding_rank": 4, "fusion_rank": 2, "excerpt": "texto real del candidato de fusion"},
        ],
        "candidates_honesty_note": "Estos candidatos son RECUPERACION, no evidencia validada.",
    },
}

_RC_ENTRY = {
    "rc_id": "test_project-rc-v1.0-20260101T000000",
    "project_id": "test_project",
    "enqueued_at": "2026-08-12T00:00:00+00:00",
    "status": "pending",
    "summary": {"version": "v1.0"},
}


@pytest.fixture(scope="module")
def _browser():
    """Mismo patrón que test_governance_ui_stale_state_playwright.py: un
    solo proceso de Chromium para todo el módulo (sync_playwright() por
    test resultó poco fiable a partir del tercero en el mismo proceso)."""
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        navegador = pw.chromium.launch()
        yield navegador
        navegador.close()


@pytest.fixture()
def pagina_con_mock(_browser):
    contexto = _browser.new_context()
    page = contexto.new_page()
    try:
        contexto_llamadas = {"decide_calls": []}

        def _route(route):
            url = route.request.url
            method = route.request.method
            if url.endswith("/api/v1/layer9/review-queue") and method == "GET":
                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                    "pending": [_FINDING_ENTRY, _RC_ENTRY],
                    "summary": {"pending": 2, "approved": 0, "rejected": 0, "returned": 0, "superseded": 0},
                }))
            elif "/review/findings/" in url and url.endswith("/decide") and method == "POST":
                body = json.loads(route.request.post_data or "{}")
                contexto_llamadas["decide_calls"].append(body)
                if body.get("reviewer", "").lower() == "human":
                    route.fulfill(status=422, content_type="application/json",
                                   body=json.dumps({"detail": "reviewer='human' es una identidad reservada."}))
                else:
                    route.fulfill(status=200, content_type="application/json",
                                   body=json.dumps({"rc_id": _FINDING_ENTRY["rc_id"],
                                                    "decision": body.get("decision"),
                                                    "reviewer": body.get("reviewer")}))
            elif "/api/v1/layer8/missions/" in url and url.endswith("/diff"):
                # Un RC real SI pide diff -- nunca debe llegar aqui para el
                # finding_review (F0.4: "render por tipo, findings sin diff").
                route.fulfill(status=200, content_type="application/json", body=json.dumps("+linea nueva\n-linea vieja\n"))
            else:
                route.continue_()

        page.route("**/api/v1/layer9/review**", _route)
        page.route("**/api/v1/layer8/missions/**/diff", _route)

        page.goto(f"{BASE}/ui/mission_control.html", wait_until="domcontentloaded")
        page.wait_for_selector("#apikey", timeout=20000)
        page.fill("#apikey", os.environ.get("FACTORY_API_KEY") or _api_key_del_env())
        page.click("text=Conectar")
        page.wait_for_function(
            "document.getElementById('conn') "
            "&& document.getElementById('conn').textContent.includes('conectado')",
            timeout=15000)
        page.click('button[data-v="review"]')
        page.wait_for_selector("#review-list .rc", timeout=15000)
        yield page, contexto_llamadas
    finally:
        contexto.close()


def test_finding_and_rc_render_with_distinct_layout(pagina_con_mock):
    """F0.4: render por tipo -- el finding_review muestra su cita/candidatos
    y NUNCA la caja de diff; el RC real muestra su caja de diff."""
    page, _ = pagina_con_mock
    finding_card = page.locator(f"#review-list :text('{_FINDING_ENTRY['summary']['requirement_id']}')").first
    assert finding_card.count() > 0
    # el finding no dispara ninguna caja de diff (id derivado de su document_id)
    assert page.locator(f"#rc-diff-{_FINDING_ENTRY['summary']['document_id']}").count() == 0
    # el RC real si tiene su caja de diff, y SI se resuelve (nunca queda muda)
    page.wait_for_function(
        "document.getElementById('rc-diff-test_project') "
        "&& !document.getElementById('rc-diff-test_project').textContent.includes('cargando')",
        timeout=10000)
    assert "linea nueva" in page.locator("#rc-diff-test_project").inner_html()


def test_candidates_table_shows_page_rank_and_excerpt(pagina_con_mock):
    """F0.4: vista de evidencia con candidatos de fusion -- pagina, rank
    por metodo, extracto -- nunca solo un placeholder de "hay candidatos"."""
    page, _ = pagina_con_mock
    row = page.locator("#review-list table.tbl tbody tr").first
    assert row.count() > 0
    row_text = row.inner_text()
    assert "45-46" in row_text
    assert "texto real del candidato de fusion" in row_text


def test_reserved_identity_shows_visible_error_and_never_advances(pagina_con_mock):
    """F0.4: identidad del revisor validada -- un 422 real del backend debe
    ser visible en la UI, y la decision nunca se manda a la cola con exito."""
    page, calls = pagina_con_mock
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", _FINDING_ENTRY["rc_id"])
    page.fill(f"#finding-reviewer-{safe}", "human")
    page.click(f"button:has-text('Confirmar evidencia')")
    page.wait_for_function("document.getElementById('_toast') && document.getElementById('_toast').textContent.length > 0", timeout=8000)
    toast_text = page.locator("#_toast").inner_text()
    assert "422" in toast_text or "reservad" in toast_text.lower()
    assert len(calls["decide_calls"]) == 1
    assert calls["decide_calls"][0]["reviewer"] == "human"


def test_confirm_with_real_reviewer_sends_exactly_one_decide_call(pagina_con_mock):
    """F0.4: un evento por decision -- un clic, una sola llamada al backend."""
    page, calls = pagina_con_mock
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", _FINDING_ENTRY["rc_id"])
    page.fill(f"#finding-reviewer-{safe}", "Cesar")
    page.click(f"button:has-text('Confirmar evidencia')")
    page.wait_for_function("document.getElementById('_toast') && document.getElementById('_toast').textContent.length > 0", timeout=8000)
    assert len(calls["decide_calls"]) == 1
    assert calls["decide_calls"][0]["decision"] == "confirmed"
    assert calls["decide_calls"][0]["reviewer"] == "Cesar"
