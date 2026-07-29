"""W5 V2 — decisiones humanas D1–D5 en Mission Control.

Diagnóstico que originó esto: las decisiones D1–D5 no existían en ninguna
capa (0 apariciones en el repo, ausentes de las 111 rutas de OpenAPI, sin
vista). Gobierno → Revisión humana administra RELEASE CANDIDATES, y ni esa
vista ni Aprobación de misión ni Validación GAMP 5 pueden sustituirlas.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import layer9 as layer9_routes
from factory.services import w5_human_decisions as w5

UI_DIR = "factory/ui"


@pytest.fixture
def client():
    """App mínima con solo el router (mismo patrón que
    test_remediation_packages_router.py): factory.api.main monta un log de
    acceso propiedad de root que no es escribible desde la suite."""
    app = FastAPI()
    app.include_router(layer9_routes.router)  # el router ya trae su prefijo
    return TestClient(app)


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Aísla el almacén y la auditoría: ningún test escribe en los reales."""
    monkeypatch.setattr(w5, "DECISIONS_FILE", tmp_path / "w5_human_decisions.jsonl")
    events = []
    monkeypatch.setattr(w5, "write_event",
                        lambda et, pid, data=None: events.append((et, pid, data)))
    return events


class TestReadIsSideEffectFree:

    def test_get_writes_no_audit_event(self, isolated_store):
        """Requisito 1 y 10: ningún GET genera eventos de auditoría."""
        for _ in range(3):
            w5.get_decisions_state()
        assert isolated_store == []

    def test_get_does_not_create_the_store_file(self, isolated_store):
        w5.get_decisions_state()
        assert not w5.DECISIONS_FILE.exists()

    def test_get_reports_all_five_decisions_as_pending(self, isolated_store):
        state = w5.get_decisions_state()
        ids = [d["decision_id"] for d in state["decisions"]]
        assert ids == list(w5.DECISION_IDS)
        assert state["pending_count"] == 5
        assert all(d["status"] == "PENDING" for d in state["decisions"])
        assert state["read_only"] is True

    def test_governance_constants_are_blocked(self, isolated_store):
        g = w5.get_decisions_state()["governance"]
        assert g["FORMAL_RELEASE_GATE"] == "BLOCKED"
        assert g["REGULATORY_COMPLIANCE"] == "NOT_DETERMINED"
        assert g["PRODUCTION_ENABLEMENT"] == "BLOCKED"


class TestD1IsIndependentOfTheReleaseCandidateQueue:

    def test_d1_is_present_even_when_the_rc_queue_is_empty(self, client, isolated_store):
        """Requisito 2: D1 se muestra aunque la cola de RC esté vacía. Son
        superficies distintas; una vacía no puede ocultar la otra."""
        rc = client.get("/api/v1/layer9/review-queue")
        if rc.status_code == 200:
            assert rc.json()["summary"]["pending"] == 0, "precondición: cola vacía"

        state = w5.get_decisions_state()
        d1 = next(d for d in state["decisions"] if d["decision_id"] == "D1_regulatory_sources")
        assert d1["status"] == "PENDING"
        assert len(d1["context"]["sources"]) == 3

    def test_d1_context_carries_the_fields_the_card_must_show(self, isolated_store):
        d1 = next(d for d in w5.get_decisions_state()["decisions"]
                  if d["decision_id"] == "D1_regulatory_sources")
        for s in d1["context"]["sources"]:
            for field in ("source_id", "regulation", "official_source_url",
                          "version", "sha256", "current_state"):
                assert s[field] != "" and s[field] is not None, f"{field} vacío en {s['source_id']}"
            assert len(s["sha256"]) == 64


class TestIdentityAndIdempotency:

    @pytest.mark.parametrize("identity", ["", "  ", "human", "HUMAN", "system", "agent", "qa"])
    def test_generic_identity_is_rejected(self, identity, isolated_store):
        """Requisito 3: identidad genérica ⇒ 422 (aquí, su excepción)."""
        with pytest.raises(w5.DecisionValidationError):
            w5.record_decision("D3_T039", decision="APPROVE", approved_by=identity)
        assert isolated_store == [], "una decisión rechazada no puede auditar"

    def test_generic_identity_returns_422_over_http(self, client, isolated_store):
        r = client.post("/api/v1/layer9/w5-decisions/D3_T039",
                        json={"decision": "APPROVE", "approved_by": "human"})
        assert r.status_code == 422

    def test_second_decision_returns_409(self, client, isolated_store):
        """Requisito 4: la segunda decisión sobre el mismo id ⇒ 409."""
        body = {"decision": "APPROVE", "approved_by": "Cesar (ing_cpmo)"}
        first = client.post("/api/v1/layer9/w5-decisions/D3_T039", json=body)
        assert first.status_code == 200
        second = client.post("/api/v1/layer9/w5-decisions/D3_T039", json=body)
        assert second.status_code == 409
        assert len(isolated_store) == 1, "el 409 no puede escribir un segundo evento"

    def test_recording_writes_exactly_one_audit_event(self, isolated_store):
        w5.record_decision("D3_T039", decision="APPROVE", approved_by="Cesar (ing_cpmo)")
        assert len(isolated_store) == 1
        event_type, project_id, data = isolated_store[0]
        assert event_type == "layer9_decision_recorded"
        assert data["decision_origin"] == "human_confirmed"
        assert data["side_effects_applied"] is False

    def test_d1_requires_cadence_authority_and_scope(self, isolated_store):
        with pytest.raises(w5.DecisionValidationError, match="approved_source_ids"):
            w5.record_decision("D1_regulatory_sources", decision="APPROVE",
                               approved_by="Cesar (ing_cpmo)")
        with pytest.raises(w5.DecisionValidationError, match="cadence"):
            w5.record_decision("D1_regulatory_sources", decision="APPROVE",
                               approved_by="Cesar (ing_cpmo)", approved_source_ids="ALL")
        with pytest.raises(w5.DecisionValidationError, match="authority"):
            w5.record_decision("D1_regulatory_sources", decision="APPROVE",
                               approved_by="Cesar (ing_cpmo)", approved_source_ids="ALL",
                               reverification_cadence_months=12)
        assert isolated_store == []


class TestRecordingDoesNotExecuteConsequences:

    def _record_d1(self):
        return w5.record_decision(
            "D1_regulatory_sources", decision="APPROVE", approved_by="Cesar (ing_cpmo)",
            approved_source_ids="ALL", reverification_cadence_months=12,
            reverification_authority="Cesar (Capa 9)")

    def test_d1_does_not_approve_any_mission(self, isolated_store):
        """Requisito 5: una decisión D1 no aprueba una misión."""
        from factory.layer9 import mission_control
        before = json.dumps(mission_control.list_missions(), sort_keys=True, default=str)
        self._record_d1()
        after = json.dumps(mission_control.list_missions(), sort_keys=True, default=str)
        assert before == after

    def test_d1_does_not_change_any_source_to_verified(self, isolated_store):
        """Requisito 6: D1 por sí sola no promueve ninguna fuente a
        LOCAL_CANONICAL_COPY_VERIFIED."""
        from factory.services import paths
        registry = paths.FACTORY_ROOT / "regulatory" / "sources" / "registry.json"
        before = registry.read_bytes()
        self._record_d1()
        assert registry.read_bytes() == before

        data = json.loads(registry.read_text(encoding="utf-8"))
        assert all(s["regulatory_currency_status"] == "pending_reverification"
                   for s in data["sources"])

        state = w5.get_decisions_state()
        d1 = next(d for d in state["decisions"] if d["decision_id"] == "D1_regulatory_sources")
        assert all(s["current_state"] == "pending_reverification"
                   for s in d1["context"]["sources"])

    def test_d1_does_not_touch_the_requirement_catalog(self, isolated_store):
        from factory.services import paths
        catalog = paths.FACTORY_ROOT / "regulatory" / "requirement_catalog" / "requirements.yaml"
        before = catalog.read_bytes()
        self._record_d1()
        assert catalog.read_bytes() == before


class TestHttpSurface:

    def test_get_endpoint_returns_the_five_decisions(self, client, isolated_store):
        r = client.get("/api/v1/layer9/w5-decisions")
        assert r.status_code == 200
        assert [d["decision_id"] for d in r.json()["decisions"]] == list(w5.DECISION_IDS)

    def test_unknown_decision_id_is_422_not_500(self, client, isolated_store):
        r = client.post("/api/v1/layer9/w5-decisions/D9_inventada",
                        json={"decision": "APPROVE", "approved_by": "Cesar (ing_cpmo)"})
        assert r.status_code == 422

    def test_invalid_decision_value_is_422(self, client, isolated_store):
        r = client.post("/api/v1/layer9/w5-decisions/D3_T039",
                        json={"decision": "MAYBE", "approved_by": "Cesar (ing_cpmo)"})
        assert r.status_code == 422


class TestFrontendContract:
    """Requisitos 7, 8 y 9 verificados sobre los ficheros que se sirven tal
    cual (StaticFiles sobre el árbol de trabajo: no hay bundle ni build)."""

    def _read(self, name):
        return open(f"{UI_DIR}/{name}", encoding="utf-8").read()

    def test_frontend_renders_the_five_decisions_with_the_real_contract(self, isolated_store):
        """Requisito 9: el frontend consume los campos que el backend emite."""
        js = self._read("js/mission_control/w5_decisions.js")
        assert "/api/v1/layer9/w5-decisions" in js
        for field in ("decisions", "decision_id", "pending_count", "recorded_count",
                      "governance", "context"):
            assert field in js, f"el frontend no lee '{field}'"
        for field in ("source_id", "official_source_url", "version", "sha256", "current_state"):
            assert field in js, f"la tarjeta D1 no muestra '{field}'"
        for action in ("APPROVE", "PARTIAL", "REJECT"):
            assert action in js
        for field in ("reverification_cadence_months", "reverification_authority",
                      "approved_source_ids"):
            assert field in js, f"D1 no envía '{field}'"

    def test_view_is_separate_from_the_release_candidate_queue(self, isolated_store):
        html = self._read("mission_control.html")
        assert 'id="v-w5"' in html
        assert 'data-v="w5"' in html
        assert 'id="w5-list"' in html
        review_block = html.split('id="v-review"')[1].split("</section>")[0]
        assert "w5-list" not in review_block, "D1–D5 no puede vivir dentro de la cola de RC"

    def test_header_and_page_share_one_connection_state(self, isolated_store):
        """Requisito 7: misma fuente de estado. `_checkAuthFailure` actualiza
        `state.connected` y el header `#conn`, y la vista w5 lo invoca."""
        refresh = self._read("js/mission_control/refresh.js")
        w5_block = refresh.split("if(v==='w5')")[1].split("if(v===")[0]
        assert "_checkAuthFailure(r)" in w5_block
        assert "state.connected=false" in refresh
        assert "document.getElementById('conn')" in refresh

    def test_errors_are_shown_as_errors_not_as_conectar(self, isolated_store):
        """Requisito 8: 401/403/404/500 se muestran explícitamente."""
        js = self._read("js/mission_control/w5_decisions.js")
        assert "renderW5Error" in js
        for label in ("Sesión no autorizada", "Endpoint no encontrado", "Error del backend"):
            assert label in js
        assert "conectar para ver" not in js

        refresh = self._read("js/mission_control/refresh.js")
        review_block = refresh.split("v==='dash'||v==='review'")[1].split("if(v==='w5')")[0]
        assert "else if(v==='review')" in review_block, (
            "la cola de RC debe distinguir error de 'no conectado'")


class TestGovernedCorrection:
    """Una cadencia firmada por error es un hecho histórico. Se corrige
    SUPERPONIENDO un registro firmado, nunca reescribiendo el anterior: el
    almacén es append-only y la cadena es Part 11."""

    def _record_d1(self, months=1):
        return w5.record_decision(
            "D1_regulatory_sources", decision="APPROVE", approved_by="cesar",
            approved_source_ids="ALL", reverification_cadence_months=months,
            reverification_authority="cesar")

    def test_correction_appends_and_never_edits_the_original(self, isolated_store):
        original = self._record_d1(months=1)
        raw_before = w5.DECISIONS_FILE.read_text(encoding="utf-8")

        w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                             reason="la cadencia de 1 mes fue un valor de prueba",
                             reverification_cadence_months=12)

        raw_after = w5.DECISIONS_FILE.read_text(encoding="utf-8")
        assert raw_after.startswith(raw_before), "el registro original fue alterado"
        history = w5.decision_history("D1_regulatory_sources")
        assert len(history) == 2
        assert history[0]["reverification_cadence_months"] == 1, "el original debe conservarse"
        assert history[0] == original

    def test_current_record_is_the_correction(self, isolated_store):
        self._record_d1(months=1)
        w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                             reason="valor de prueba", reverification_cadence_months=12)
        current = w5.recorded_decisions()["D1_regulatory_sources"]
        assert current["reverification_cadence_months"] == 12
        assert current["record_type"] == "correction"
        assert current["corrected_fields"]["reverification_cadence_months"] == {"from": 1, "to": 12}
        assert current["approved_by"] == "cesar", "el firmante original se conserva"

    def test_correction_writes_exactly_one_audit_event(self, isolated_store):
        self._record_d1()
        isolated_store.clear()
        w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                             reason="valor de prueba", reverification_cadence_months=12)
        assert len(isolated_store) == 1
        _, _, data = isolated_store[0]
        assert data["scope"] == "w5_human_decision_correction"
        assert data["side_effects_applied"] is False
        assert data["corrected_fields"]["reverification_cadence_months"]["to"] == 12

    def test_history_travels_in_the_read_state(self, isolated_store):
        self._record_d1()
        w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                             reason="valor de prueba", reverification_cadence_months=12)
        d1 = next(d for d in w5.get_decisions_state()["decisions"]
                  if d["decision_id"] == "D1_regulatory_sources")
        assert d1["corrections"] == 1
        assert len(d1["history"]) == 2
        assert d1["recorded"]["reverification_cadence_months"] == 12

    def test_correction_requires_a_reason_and_a_real_identity(self, isolated_store):
        self._record_d1()
        with pytest.raises(w5.DecisionValidationError, match="reason"):
            w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                                 reason="  ", reverification_cadence_months=12)
        with pytest.raises(w5.DecisionValidationError):
            w5.record_correction("D1_regulatory_sources", corrected_by="human",
                                 reason="x", reverification_cadence_months=12)

    def test_correction_without_any_change_is_rejected(self, isolated_store):
        self._record_d1(months=1)
        with pytest.raises(w5.DecisionValidationError, match="no cambia ningún campo"):
            w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                                 reason="sin cambios", reverification_cadence_months=1)

    def test_correcting_a_decision_that_was_never_recorded_is_404(self, client, isolated_store):
        r = client.post("/api/v1/layer9/w5-decisions/D2_evidence_packs/correct",
                        json={"corrected_by": "cesar", "reason": "x",
                              "reverification_cadence_months": 12})
        assert r.status_code == 404

    def test_correction_changes_no_governed_state(self, isolated_store):
        from factory.services import paths
        registry = paths.FACTORY_ROOT / "regulatory" / "sources" / "registry.json"
        self._record_d1()
        before = registry.read_bytes()
        w5.record_correction("D1_regulatory_sources", corrected_by="cesar",
                             reason="valor de prueba", reverification_cadence_months=12)
        assert registry.read_bytes() == before
