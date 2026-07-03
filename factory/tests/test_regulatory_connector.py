"""
W6.3 — Tests del conector online controlado (openFDA Drug Enforcement).

CERO RED: _http_get se mockea siempre. Garantías fijadas:
  - limit se acota a 1..10 (anti descarga masiva)
  - término sanitizado (sin sintaxis de búsqueda inyectable) y 422 si vacío
  - run_by: nombres reservados → 422
  - rate limit: segunda llamada antes de MIN_INTERVAL_S → 429;
    cupo diario agotado → 429
  - memoria ligera: NUNCA se guardan address/postal_code/openfda ni el
    documento completo; sí pointer + metadata + summary + tags + hash +
    freshness + retrieval_path
  - dedupe por case_id (segunda consulta no duplica)
  - openFDA 404 (sin coincidencias) → 0 resultados, sin excepción, auditado
  - auditoría: exactamente 1 evento por query y 1 por fetch
  - selective fetch: parte de un caso conocido (404 si no), devuelve detalle
    SIN persistirlo, detecta cambio de contenido por hash
  - la búsqueda local existente encuentra los casos guardados y no audita
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import design_mode_service as design
from factory.services import paths as svc_paths
from factory.services import regulatory_connector_service as svc

RECORD = {
    "recall_number": "D-0001-2026",
    "classification": "Class II",
    "status": "Ongoing",
    "product_description": "Sterile Injectable 10mg/mL",
    "reason_for_recall": "Lack of assurance of sterility; CGMP deviations",
    "recalling_firm": "Acme Pharma LLC",
    "recall_initiation_date": "20260601",
    "report_date": "20260615",
    "voluntary_mandated": "Voluntary: Firm initiated",
    "product_type": "Drugs",
    "event_id": "99001",
    "address_1": "123 Main St",       # NO debe llegar a la memoria
    "postal_code": "00000",           # NO debe llegar a la memoria
    "openfda": {"spl_id": ["x"]},     # NO debe llegar a la memoria
    "distribution_pattern": "Nationwide",
    "code_info": "Lot A1",
}


class FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture()
def conn_env(tmp_path, monkeypatch, isolated_audit):
    monkeypatch.setattr(svc_paths, "CASE_MEMORY_FILE", tmp_path / "cases.jsonl")
    monkeypatch.setattr(svc_paths, "CONNECTOR_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(svc_paths, "AUDIT_FILE", isolated_audit)
    # el intervalo mínimo no aplica por defecto en tests (se prueba aparte)
    monkeypatch.setattr(svc, "MIN_INTERVAL_S", 0)
    calls = []

    def fake_get(params):
        calls.append(params)
        return FakeResp(200, {"results": [RECORD]})
    monkeypatch.setattr(svc, "_http_get", fake_get)
    return {"tmp": tmp_path, "calls": calls, "audit": isolated_audit}


def _audit_events(audit_file):
    if not audit_file.exists():
        return []
    return [json.loads(l) for l in audit_file.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Consulta controlada ───────────────────────────────────────────────────────

def test_query_saves_light_memory_only(conn_env):
    out = svc.query_recalls("sterility", 5, "Cesar")
    assert out["saved"] == 1 and out["results_returned"] == 1
    case = json.loads(svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines()[0])
    # modelo obligatorio completo
    assert case["case_id"] == "openfda_enforcement:D-0001-2026"
    assert case["source_id"] == "openfda_enforcement" and case["authority"] == "FDA"
    assert case["case_type"] == "drug_recall" and case["classification"] == "Class II"
    assert case["consulted_at"] and case["content_hash"].startswith("sha256:")
    assert case["retrieval_path"]["params"]["search"] == 'recall_number:"D-0001-2026"'
    assert case["freshness"]["stale_after_days"] == 30
    assert "sterility" in case["tags"] and "cgmp" in case["tags"]
    assert case["summary"] and len(case["summary"]) <= 1200
    # lo que NUNCA se guarda
    raw = json.dumps(case)
    assert "address_1" not in raw and "123 Main St" not in raw
    assert "postal_code" not in raw and "distribution_pattern" not in raw
    assert "spl_id" not in raw and "code_info" not in raw


def test_query_limit_clamped_and_term_sanitized(conn_env):
    svc.query_recalls('ster:"ility[]', 999, "Cesar")
    params = conn_env["calls"][0]
    assert params["limit"] == 10                       # clamp duro
    assert params["search"] == 'reason_for_recall:"sterility"'  # sin sintaxis inyectada
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("x", 5, "Cesar")             # término inútil tras sanitizar
    assert e.value.status_code == 422


def test_query_requires_real_name(conn_env):
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("sterility", 5, "system")
    assert e.value.status_code == 422
    assert conn_env["calls"] == []                     # jamás salió a internet


def test_query_dedupes_by_case_id(conn_env):
    svc.query_recalls("sterility", 5, "Cesar")
    out2 = svc.query_recalls("sterility", 5, "Cesar")
    assert out2["saved"] == 0 and out2["skipped_existing"] == 1
    lines = svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1                             # append-only sin duplicados


def test_query_handles_no_matches_404(conn_env, monkeypatch):
    monkeypatch.setattr(svc, "_http_get", lambda p: FakeResp(404, {"error": {"code": "NOT_FOUND"}}))
    out = svc.query_recalls("nomatchterm", 5, "Cesar")
    assert out["results_returned"] == 0 and out["saved"] == 0
    events = [e for e in _audit_events(conn_env["audit"])
              if e["event_type"] == "regulatory_query_executed"]
    assert len(events) == 1                            # consulta vacía también se audita


def test_query_audits_exactly_one_event(conn_env):
    svc.query_recalls("sterility", 3, "Cesar")
    events = [e for e in _audit_events(conn_env["audit"])
              if e["event_type"] == "regulatory_query_executed"]
    assert len(events) == 1
    d = events[0]["data"]
    assert d["run_by"] == "Cesar" and d["source_id"] == "openfda_enforcement"
    assert d["search_term"] == "sterility" and d["saved"] == 1


# ── Rate limit (anti-saturación) ──────────────────────────────────────────────

def test_min_interval_enforced(conn_env, monkeypatch):
    monkeypatch.setattr(svc, "MIN_INTERVAL_S", 60)
    svc.query_recalls("sterility", 5, "Cesar")
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("cgmp", 5, "Cesar")
    assert e.value.status_code == 429
    assert len(conn_env["calls"]) == 1                 # la segunda no salió


def test_daily_quota_enforced(conn_env):
    from datetime import datetime, timezone
    svc_paths.CONNECTOR_STATE_FILE.write_text(json.dumps({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "calls_today": svc.MAX_CALLS_PER_DAY, "last_call_at": None}), encoding="utf-8")
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("sterility", 5, "Cesar")
    assert e.value.status_code == 429
    assert conn_env["calls"] == []


# ── Selective fetch ───────────────────────────────────────────────────────────

def test_fetch_requires_known_case(conn_env):
    with pytest.raises(HTTPException) as e:
        svc.fetch_case_detail("openfda_enforcement:INEXISTENTE", "Cesar")
    assert e.value.status_code == 404
    assert conn_env["calls"] == []                     # sin caso conocido no hay red


def test_fetch_returns_detail_without_persisting(conn_env):
    svc.query_recalls("sterility", 5, "Cesar")
    before = svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8")
    out = svc.fetch_case_detail("openfda_enforcement:D-0001-2026", "Cesar")
    assert out["persisted"] is False
    assert out["content_changed"] is False             # mismo registro → mismo hash
    assert out["detail"]["reason_for_recall"].startswith("Lack of assurance")
    assert "address_1" not in out["detail"] and "openfda" not in out["detail"]
    assert svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8") == before
    fetches = [e for e in _audit_events(conn_env["audit"])
               if e["event_type"] == "case_detail_fetched"]
    assert len(fetches) == 1 and fetches[0]["data"]["case_id"] == "openfda_enforcement:D-0001-2026"


def test_fetch_detects_content_change(conn_env, monkeypatch):
    svc.query_recalls("sterility", 5, "Cesar")
    changed = dict(RECORD, status="Terminated")
    monkeypatch.setattr(svc, "_http_get", lambda p: FakeResp(200, {"results": [changed]}))
    out = svc.fetch_case_detail("openfda_enforcement:D-0001-2026", "Cesar")
    assert out["content_changed"] is True


# ── Integración con la memoria local existente (W6) ──────────────────────────

def test_local_search_finds_saved_cases_without_auditing(conn_env):
    svc.query_recalls("sterility", 5, "Cesar")
    before = len(_audit_events(conn_env["audit"]))
    found = design.search_case_memory("sterility")
    assert found["count"] == 1
    assert found["results"][0]["case_id"] == "openfda_enforcement:D-0001-2026"
    assert len(_audit_events(conn_env["audit"])) == before   # leer nunca audita


def test_annotate_sources_marks_connector(conn_env):
    reg = {"sources": [{"source_id": "openfda_enforcement", "status": "connected"},
                       {"source_id": "ema_gmp_public", "status": "not_connected"}]}
    out = svc.annotate_sources(reg)
    assert out["connected_sources"] == ["openfda_enforcement"]
    assert out["sources"][0].get("connector_live") is True
    assert "connector_live" not in out["sources"][1]
