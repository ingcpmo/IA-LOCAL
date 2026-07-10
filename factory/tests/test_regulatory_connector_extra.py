"""
W9 Bloque 3 — Tests del segundo/tercer conector online controlado (openFDA
Device Enforcement y Food Enforcement).

CERO RED: _http_get se mockea siempre. Garantías fijadas:
  - mismo modelo de memoria ligera que W6.3, con case_type/source_id/
    authority correctos por fuente (device_recall/food_recall)
  - fuente desconocida (no device/food) → 404, jamás sale a red
  - cupo COMPARTIDO con el conector base (W6.3): una llamada del módulo
    base consume el mismo intervalo/cupo que ve este módulo, y viceversa
  - selective fetch decide el endpoint por el source_id guardado en el
    case, no por un endpoint fijo; caso de fuente ajena (drug) → 404
  - auditoría: exactamente 1 evento por query y 1 por fetch, con el
    source_id correcto
  - annotate_sources anota SOLO las 2 fuentes de Bloque 3, sin pisar W6.3
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import paths as svc_paths
from factory.services import regulatory_connector_service as base_svc
from factory.services import regulatory_connector_extra_service as svc

DEVICE_RECORD = {
    "recall_number": "Z-1001-2026",
    "classification": "Class II",
    "status": "Ongoing",
    "product_description": "Infusion Pump Model X",
    "reason_for_recall": "Software malfunction may cause incorrect dosing",
    "recalling_firm": "Acme Devices LLC",
    "recall_initiation_date": "20260601",
    "report_date": "20260615",
    "voluntary_mandated": "Voluntary: Firm initiated",
    "event_id": "88001",
    "address_1": "123 Main St",
    "postal_code": "00000",
    "openfda": {"device_name": ["Infusion Pump"]},
    "distribution_pattern": "Nationwide",
    "code_info": "Lot A1",
}

FOOD_RECORD = {
    "recall_number": "F-2001-2026",
    "classification": "Class I",
    "status": "Ongoing",
    "product_description": "Frozen Vegetable Blend 16oz",
    "reason_for_recall": "Undeclared milk allergen; possible Listeria contamination",
    "recalling_firm": "Acme Foods LLC",
    "recall_initiation_date": "20260601",
    "report_date": "20260615",
    "voluntary_mandated": "Voluntary: Firm initiated",
    "event_id": "77001",
    "address_1": "456 Oak Ave",
    "postal_code": "11111",
    "openfda": {"brand_name": ["Acme"]},
    "distribution_pattern": "Nationwide",
    "code_info": "Lot B2",
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
    monkeypatch.setattr(base_svc, "MIN_INTERVAL_S", 0)   # no aplica por defecto
    calls = []

    def fake_get(endpoint, params):
        calls.append((endpoint, params))
        payload = DEVICE_RECORD if "device" in endpoint else FOOD_RECORD
        return FakeResp(200, {"results": [payload]})
    monkeypatch.setattr(svc, "_http_get", fake_get)
    return {"tmp": tmp_path, "calls": calls, "audit": isolated_audit}


def _audit_events(audit_file):
    if not audit_file.exists():
        return []
    return [json.loads(l) for l in audit_file.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Consulta controlada ───────────────────────────────────────────────────────

def test_unknown_source_404(conn_env):
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("openfda_enforcement", "sterility", 5, "Cesar")  # es del módulo base, no de este
    assert e.value.status_code == 404
    assert conn_env["calls"] == []


def test_device_query_saves_light_memory(conn_env):
    out = svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    assert out["saved"] == 1
    case = json.loads(svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines()[0])
    assert case["case_id"] == "openfda_device_enforcement:Z-1001-2026"
    assert case["source_id"] == "openfda_device_enforcement" and case["authority"] == "FDA"
    assert case["case_type"] == "device_recall"
    assert "device_malfunction" in case["tags"] and "software_defect" in case["tags"]
    raw = json.dumps(case)
    assert "address_1" not in raw and "123 Main St" not in raw
    assert "postal_code" not in raw and "distribution_pattern" not in raw


def test_food_query_saves_light_memory(conn_env):
    out = svc.query_recalls("openfda_food_enforcement", "allergen", 5, "Cesar")
    assert out["saved"] == 1
    case = json.loads(svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8").splitlines()[0])
    assert case["case_id"] == "openfda_food_enforcement:F-2001-2026"
    assert case["source_id"] == "openfda_food_enforcement"
    assert case["case_type"] == "food_recall" and case["classification"] == "Class I"
    assert "allergen_undeclared" in case["tags"] and "microbial" in case["tags"]


def test_query_uses_correct_endpoint_per_source(conn_env):
    svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    assert conn_env["calls"][0][0] == "https://api.fda.gov/device/enforcement.json"


def test_query_requires_real_name(conn_env):
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "system")
    assert e.value.status_code == 422
    assert conn_env["calls"] == []


def test_query_dedupes_by_case_id(conn_env):
    svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    out2 = svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    assert out2["saved"] == 0 and out2["skipped_existing"] == 1


def test_query_handles_no_matches_404(conn_env, monkeypatch):
    monkeypatch.setattr(svc, "_http_get", lambda e, p: FakeResp(404, {}))
    out = svc.query_recalls("openfda_device_enforcement", "nomatch", 5, "Cesar")
    assert out["results_returned"] == 0 and out["saved"] == 0


def test_query_audits_with_correct_source_id(conn_env):
    svc.query_recalls("openfda_food_enforcement", "allergen", 3, "Cesar")
    events = [e for e in _audit_events(conn_env["audit"])
              if e["event_type"] == "regulatory_query_executed"]
    assert len(events) == 1
    assert events[0]["data"]["source_id"] == "openfda_food_enforcement"


# ── Cupo compartido con el conector base (W6.3) ───────────────────────────────

def test_rate_limit_shared_with_base_connector(conn_env, monkeypatch):
    monkeypatch.setattr(base_svc, "MIN_INTERVAL_S", 60)
    monkeypatch.setattr(base_svc, "_http_get", lambda p: FakeResp(200, {"results": []}))
    base_svc.query_recalls("sterility", 5, "Cesar")            # consume el cupo base
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    assert e.value.status_code == 429
    assert conn_env["calls"] == []                             # el conector extra no salió a red


def test_daily_quota_shared_with_base_connector(conn_env):
    from datetime import datetime, timezone
    svc_paths.CONNECTOR_STATE_FILE.write_text(json.dumps({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "calls_today": base_svc.MAX_CALLS_PER_DAY, "last_call_at": None}), encoding="utf-8")
    with pytest.raises(HTTPException) as e:
        svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    assert e.value.status_code == 429


# ── Selective fetch ───────────────────────────────────────────────────────────

def test_fetch_requires_known_case(conn_env):
    with pytest.raises(HTTPException) as e:
        svc.fetch_case_detail("openfda_device_enforcement:INEXISTENTE", "Cesar")
    assert e.value.status_code == 404
    assert conn_env["calls"] == []


def test_fetch_rejects_case_of_foreign_source(conn_env):
    # un caso guardado por el conector BASE (drug) no es fetcheable por este módulo
    base_svc._append_cases([{
        "case_id": "openfda_enforcement:D-9999-2026", "source_id": "openfda_enforcement",
        "retrieval_path": {"params": {}}, "content_hash": "sha256:x",
    }])
    with pytest.raises(HTTPException) as e:
        svc.fetch_case_detail("openfda_enforcement:D-9999-2026", "Cesar")
    assert e.value.status_code == 404
    assert conn_env["calls"] == []


def test_fetch_returns_detail_without_persisting(conn_env):
    svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    before = svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8")
    out = svc.fetch_case_detail("openfda_device_enforcement:Z-1001-2026", "Cesar")
    assert out["persisted"] is False
    assert out["content_changed"] is False
    assert "address_1" not in out["detail"] and "openfda" not in out["detail"]
    assert svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8") == before
    assert conn_env["calls"][-1][0] == "https://api.fda.gov/device/enforcement.json"


def test_fetch_detects_content_change(conn_env, monkeypatch):
    svc.query_recalls("openfda_device_enforcement", "malfunction", 5, "Cesar")
    changed = dict(DEVICE_RECORD, status="Terminated")
    monkeypatch.setattr(svc, "_http_get", lambda e, p: FakeResp(200, {"results": [changed]}))
    out = svc.fetch_case_detail("openfda_device_enforcement:Z-1001-2026", "Cesar")
    assert out["content_changed"] is True


# ── annotate_sources ───────────────────────────────────────────────────────────

def test_annotate_sources_marks_only_bloque3_sources(conn_env):
    reg = {"sources": [
        {"source_id": "openfda_enforcement", "status": "connected"},
        {"source_id": "openfda_device_enforcement", "status": "connected"},
        {"source_id": "openfda_food_enforcement", "status": "connected"},
        {"source_id": "ema_gmp_public", "status": "not_connected"},
    ]}
    connected = svc.annotate_sources(reg)
    assert sorted(connected) == ["openfda_device_enforcement", "openfda_food_enforcement"]
    assert reg["sources"][1].get("connector_live") is True
    assert reg["sources"][2].get("connector_live") is True
    assert "connector_live" not in reg["sources"][0]     # W6.3 lo anota su propio módulo
    assert "connector_live" not in reg["sources"][3]
