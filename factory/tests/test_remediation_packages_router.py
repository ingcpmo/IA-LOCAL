"""Tests HTTP -- factory/api/routes/remediation_packages.py.

Brecha real detectada en la auditoria de Fases J-P (2026-07-27): el
contrato HTTP de Fase P ("doble-aprobacion -> 409, idempotencia") solo
estaba probado en la capa de SERVICIO (que
PackageDecisionAlreadyRecordedError se lanza y que es subclase de
InvalidTransitionError). Nada probaba el mapeo del router, asi que
cambiar `HTTPException(409, ...)` por `400` pasaba los 122 tests
relevantes sin una sola falla -- verificado por mutacion controlada.

El 409 es justamente lo que distingue "ya decidido" (idempotencia) de
"estado invalido" (400) para un consumidor externo, y
PackageDecisionAlreadyRecordedError es subclase de InvalidTransitionError:
si el `except` especifico se moviera DESPUES del generico, el 409 se
degradaria a 400 en silencio. Estos tests fijan el contrato observable.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factory.api.routes import remediation_packages
from factory.core import audit_writer
from factory.services import paths
from factory.services import remediation_package_service as svc

PROJECT_ID = "gmpai_document_validation_test"
BASE = "/api/v1/remediation-packages"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Mismo aislamiento que test_remediation_package_service.py: estado en
    tmp_path y auditoria fuera del jsonl real de la fabrica."""
    monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", tmp_path / "audit" / "test_factory_audit.jsonl")
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    # Resolutor de directivas sintetico (mismo patron/razon que
    # test_remediation_package_service.py): estos tests prueban el
    # contrato HTTP de excepciones/lotes/decision/release, no el flujo de
    # RemediationDirective -- ese cierre real (P0) se prueba end-to-end,
    # SIN este monkeypatch, en test_create_package_rejects_change_without_
    # real_submitted_directive de abajo.
    monkeypatch.setattr(svc, "_resolve_directive", lambda directive_id: {"status": "SUBMITTED"})
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(remediation_packages.router)
    return TestClient(app)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _citation(change_id):
    literal_text = f"texto literal sintetico para {change_id}"
    return {
        "citation_id": f"CIT-{change_id}", "regulatory_catalog_entry_id": "ALCOA_CONTEMPORANEOUS",
        "regulatory_source": "ALCOA+", "regulatory_source_sha256": _sha256(f"source-{change_id}"),
        "requirement_catalog_sha256": _sha256(f"catalog-{change_id}"),
        "run_id": "RUN-TEST-0001", "record_id": f"REC-{change_id}",
        "document_role": "CANDIDATE_DOCUMENT", "document_sha256": _sha256(f"doc-{change_id}"),
        "chunk_sha256": _sha256(f"chunk-{change_id}"), "citation_locator": f"chunk_20#p12-14-{change_id}",
        "page_start": 12, "page_end": 14, "literal_text": literal_text,
        "citation_text_sha256": _sha256(literal_text), "evidence_type": "LITERAL_QUOTE",
        "evidence_location": f"seccion 4.2, {change_id}",
    }


def _change(change_id):
    return {
        "change_id": change_id, "finding_id": f"F-{change_id}", "requirement_id": f"REQ-{change_id}",
        "document_location": "seccion 4.2", "original_content": None,
        "proposed_content": f"contenido propuesto para {change_id}",
        "change_reason": "gap documental real", "change_type": "CONTENT_ADDITION",
        "citations": [_citation(change_id)], "change_risk": "LOW_RISK",
        "change_risk_basis": ["change_type"], "evaluation_confidence": "HIGH_CONFIDENCE",
        "evaluation_confidence_basis": ["coverage_status"], "schema_validation_status": "PASSED",
        "citation_anchor_status": "VERIFIED", "relevance_status": "CONFIRMED",
        "candidate_application_status": "APPLIED_TO_DRAFT", "limitations": "",
        "directive_id": f"DIR-{change_id}",
    }


def _artifact(kind: str) -> dict:
    return {
        "artifact_id": f"ART-{kind}", "storage_location": f"/synthetic/{kind}.bin",
        "mime_type": "application/octet-stream", "sha256": _sha256(f"synthetic-{kind}"),
        "size_bytes": 1024,
        "classification": {
            "source_document": "SOURCE_IMMUTABLE", "candidate_document": "CANDIDATE_DRAFT",
            "remediation_report": "REPORT", "redline_document": "REDLINE",
            "package_manifest": "MANIFEST",
        }[kind],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _artifacts() -> dict:
    return {kind: _artifact(kind) for kind in
            ("source_document", "candidate_document", "remediation_report",
             "redline_document", "package_manifest")}


def _create(client, package_id, *, version=1):
    r = client.post(f"{BASE}/{PROJECT_ID}/{package_id}/{version}", json={
        "changes": [_change("C1")],
        "artifacts": _artifacts(),
        "automatic_evaluation_basis": {
            "requirement_ids": ["REQ-C1"], "regulatory_catalog_version": "v1",
            "applicability_matrix_version": "v1", "evaluation_run_id": "RUN-TEST-0001",
        },
        "generation_commit_sha": "deadbeef",
    })
    assert r.status_code == 201, r.text
    return r


def _decide(client, package_id, headers, *, version=1, justification="ok"):
    return client.post(f"{BASE}/{PROJECT_ID}/{package_id}/{version}/decision", json={
        "decision": "APPROVE_CLEAN", "justification": justification,
    }, headers=headers)


# ── Fase P: el contrato HTTP real ────────────────────────────────────────

def test_first_decision_returns_201_with_human_confirmed_origin(client, identity_headers):
    _create(client, "PKG-HTTP-1")
    r = _decide(client, "PKG-HTTP-1", identity_headers, justification="primera decision")
    assert r.status_code == 201, r.text
    assert r.json()["decision_origin"] == "human_confirmed"


def test_double_decision_returns_409_not_400(client, identity_headers):
    """La regresion concreta que ningun test cubria: si el except especifico
    de PackageDecisionAlreadyRecordedError se moviera despues del generico
    (es subclase de InvalidTransitionError), esto devolveria 400."""
    _create(client, "PKG-HTTP-2")
    assert _decide(client, "PKG-HTTP-2", identity_headers, justification="primera").status_code == 201
    r = _decide(client, "PKG-HTTP-2", identity_headers, justification="segunda")
    assert r.status_code == 409, f"esperado 409 (idempotencia), obtenido {r.status_code}: {r.text}"


def test_premature_state_is_400_so_409_keeps_meaning_something(client, identity_headers):
    """Contrapeso: el 409 solo significa algo si otros errores de
    transicion NO son 409. Una decision sobre un paquete inexistente da
    404, y un cuerpo invalido da 400 -- nunca 409."""
    r = _decide(client, "PKG-NO-EXISTE", identity_headers)
    assert r.status_code == 404, r.text


def test_missing_identity_key_is_rejected_over_http(client):
    """Paquete 2 (hallazgo M): decided_by ya no viaja en el body -- sin
    X-Identity-Key el rechazo debe ser un error de cliente, nunca un 201."""
    _create(client, "PKG-HTTP-3")
    r = _decide(client, "PKG-HTTP-3", headers=None)
    assert r.status_code == 401, r.text
    assert r.status_code != 201


def test_unknown_identity_key_is_rejected_over_http(client):
    _create(client, "PKG-HTTP-3B")
    r = _decide(client, "PKG-HTTP-3B", headers={"X-Identity-Key": "key-no-registrada"})
    assert r.status_code == 401, r.text


# ── Decision 2 (2026-08-26): endpoint de liberacion ─────────────────────────
# `identity_headers` resuelve a "Cesar" (conftest.py) -- coincide a
# proposito con la UNICA identidad de factory/config/release_authorized_
# identities.yaml real (no mockeado en estos tests: son de contrato HTTP
# end-to-end). `identity_headers_other` resuelve a "OtroRevisor" -- real,
# autenticado, pero NUNCA en esa lista, para probar autorizacion negativa
# sin depender de una identidad inventada que require_identity rechazaria
# antes de llegar al concern que se quiere probar.

def _release(client, package_id, headers, *, version=1):
    return client.post(f"{BASE}/{PROJECT_ID}/{package_id}/{version}/release",
                       json={"released_by": "inyectado-por-el-cliente"}, headers=headers)


def test_release_with_authorized_and_distinct_identity_returns_201(client, identity_headers,
                                                                    identity_headers_other):
    """decide OtroRevisor, libera Cesar (autorizado, distinto) -> 201."""
    _create(client, "PKG-REL-1")
    assert _decide(client, "PKG-REL-1", identity_headers_other, justification="ok").status_code == 201
    r = _release(client, "PKG-REL-1", identity_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["released_by"] == "Cesar", "released_by debe ser la identidad SERVER-SIDE, nunca el body"
    assert body["release_id"].startswith("REL-PKG-REL-1")


def test_release_body_cannot_inject_released_by(client, identity_headers, identity_headers_other):
    """El body manda released_by='inyectado-por-el-cliente' en TODOS estos
    tests (via el helper _release) -- si algun dia el endpoint empezara a
    leerlo, este valor apareceria en el ReleaseRecord. Se ignora siempre:
    no hay ningun parametro Body declarado en la firma del endpoint."""
    _create(client, "PKG-REL-2")
    _decide(client, "PKG-REL-2", identity_headers_other, justification="ok")
    r = _release(client, "PKG-REL-2", identity_headers)
    assert r.status_code == 201, r.text
    assert r.json()["released_by"] != "inyectado-por-el-cliente"
    assert r.json()["released_by"] == "Cesar"


def test_release_same_identity_that_decided_fails_closed(client, identity_headers):
    """Cuatro ojos: Cesar decide Y Cesar intenta liberar -> FAIL CLOSED."""
    _create(client, "PKG-REL-3")
    assert _decide(client, "PKG-REL-3", identity_headers, justification="ok").status_code == 201
    r = _release(client, "PKG-REL-3", identity_headers)
    assert r.status_code == 403, r.text
    assert "misma identidad" in r.text or "no puede" in r.text


def test_release_unauthorized_identity_fails_closed(client, identity_headers, identity_headers_other):
    """OtroRevisor esta autenticado y es distinto de quien decidio, pero NO
    esta en release_authorized_identities.yaml -> FAIL CLOSED (403), nunca
    201 solo por tener una X-Identity-Key valida."""
    _create(client, "PKG-REL-4")
    assert _decide(client, "PKG-REL-4", identity_headers, justification="ok").status_code == 201
    r = _release(client, "PKG-REL-4", identity_headers_other)
    assert r.status_code == 403, r.text
    assert "autorizado" in r.text


def test_release_package_not_ready_fails_closed(client, identity_headers):
    """Paquete creado pero sin PackageDecisionRecord -- nunca llega a
    PACKAGE_READY_FOR_RELEASE."""
    _create(client, "PKG-REL-5")
    r = _release(client, "PKG-REL-5", identity_headers)
    assert r.status_code == 400, r.text


def test_release_nonexistent_package_returns_404(client, identity_headers):
    r = _release(client, "PKG-REL-NO-EXISTE", identity_headers)
    assert r.status_code == 404, r.text


def test_release_duplicate_returns_409(client, identity_headers, identity_headers_other):
    _create(client, "PKG-REL-6")
    _decide(client, "PKG-REL-6", identity_headers_other, justification="ok")
    assert _release(client, "PKG-REL-6", identity_headers).status_code == 201
    r = _release(client, "PKG-REL-6", identity_headers)
    assert r.status_code == 409, r.text


def test_release_missing_identity_key_is_rejected_over_http(client, identity_headers_other):
    _create(client, "PKG-REL-7")
    _decide(client, "PKG-REL-7", identity_headers_other, justification="ok")
    r = _release(client, "PKG-REL-7", headers=None)
    assert r.status_code == 401, r.text


def test_release_emits_document_released_audit_event(client, identity_headers, identity_headers_other,
                                                       tmp_path, monkeypatch):
    from factory.core import audit_writer as aw
    audit_file = tmp_path / "audit" / "release_audit_test.jsonl"
    monkeypatch.setattr(aw, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(aw, "_last_entry_hash", None)

    _create(client, "PKG-REL-8")
    _decide(client, "PKG-REL-8", identity_headers_other, justification="ok")
    r = _release(client, "PKG-REL-8", identity_headers)
    assert r.status_code == 201, r.text

    events = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    released_events = [e for e in events if e.get("event_type") == "document_released"]
    assert len(released_events) == 1, events
    assert released_events[0]["data"]["released_by"] == "Cesar"
    assert released_events[0]["data"]["package_id"] == "PKG-REL-8"


# ── GET .../release (gap cerrado 2026-08-26): sin esto, la UI no podia
# distinguir "nunca se libero" de "ya se libero" tras un refresh de pagina --
# solo lo sabia mientras durara la memoria en JS de la propia sesion que
# disparo el POST.

def _get_release(client, package_id, *, version=1):
    return client.get(f"{BASE}/{PROJECT_ID}/{package_id}/{version}/release")


def test_get_release_before_release_returns_null(client, identity_headers):
    _create(client, "PKG-REL-GET-1")
    r = _get_release(client, "PKG-REL-GET-1")
    assert r.status_code == 200, r.text
    assert r.json() == {"release": None}


def test_get_release_after_release_returns_record(client, identity_headers, identity_headers_other):
    _create(client, "PKG-REL-GET-2")
    _decide(client, "PKG-REL-GET-2", identity_headers_other, justification="ok")
    posted = _release(client, "PKG-REL-GET-2", identity_headers).json()
    r = _get_release(client, "PKG-REL-GET-2")
    assert r.status_code == 200, r.text
    assert r.json() == {"release": posted}


def test_get_release_nonexistent_package_returns_404(client):
    r = _get_release(client, "PKG-REL-GET-NO-EXISTE")
    assert r.status_code == 404, r.text


# ── Cierre P0 (2026-08-18, VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md,
# hallazgo I): el endpoint de creacion de paquetes debia aceptar `changes`
# arbitrarios sin exigir una RemediationDirective real y SUBMITTED detras.
# Estos tests NO usan el _resolve_directive sintetico del fixture autouse
# -- lo reemplazan por el real (remediation_directive.get_directive) y
# apuntan remediation_directive.DIRECTIVES_FILE a un archivo temporal, para
# ejercitar el cierre end-to-end exactamente por la ruta HTTP real que
# tenia el bypass.

def _real_directive(directive_id: str, *, status: str = "SUBMITTED") -> dict:
    """RemediationDirective minima con forma real (ver
    remediation_directive._DIRECTIVE_REQUIRED_FIELDS) -- get_directive() no
    revalida forma, solo busca por directive_id, asi que basta con que sea
    completa y legible por json.loads, igual que un registro real
    persistido por propose_remediation_directive()."""
    return {
        "directive_id": directive_id, "finding_rc_id": f"RC-{directive_id}",
        "document_id": "RW-0001", "document_sha256": _sha256("doc"),
        "requirement_id": "ALCOA_CONTEMPORANEOUS", "change_type": "ADD",
        "proposed_text": "texto propuesto por un humano real", "target_location":
            {"page_start": 1, "page_end": 1, "section": None}, "original_text": None,
        "regulatory_citation": ["ALCOA_CONTEMPORANEOUS"], "rationale": "brecha confirmada por Acto 1",
        "authored_by_id": "cesar", "authored_by_display_name": "Cesar",
        "authored_at": datetime.now(timezone.utc).isoformat(), "status": status,
    }


def _use_real_directive_resolver(monkeypatch, tmp_path):
    from factory.services import remediation_directive
    monkeypatch.setattr(svc, "_resolve_directive", remediation_directive.get_directive)
    monkeypatch.setattr(remediation_directive, "DIRECTIVES_FILE", tmp_path / "remediation_directives.jsonl")
    return remediation_directive


def test_create_package_rejects_change_without_directive_id(client, monkeypatch, tmp_path):
    _use_real_directive_resolver(monkeypatch, tmp_path)
    change = _change("C1")
    del change["directive_id"]
    r = client.post(f"{BASE}/{PROJECT_ID}/PKG-P0-1/1", json={
        "changes": [change], "artifacts": _artifacts(),
        "automatic_evaluation_basis": {
            "requirement_ids": ["REQ-C1"], "regulatory_catalog_version": "v1",
            "applicability_matrix_version": "v1", "evaluation_run_id": "RUN-TEST-0001",
        },
        "generation_commit_sha": "deadbeef",
    })
    assert r.status_code == 400, r.text
    assert "directive_id" in r.text


def test_create_package_rejects_unknown_directive_id(client, monkeypatch, tmp_path):
    _use_real_directive_resolver(monkeypatch, tmp_path)  # remediation_directives.jsonl nunca se escribe
    r = client.post(f"{BASE}/{PROJECT_ID}/PKG-P0-2/1", json={
        "changes": [_change("C1")], "artifacts": _artifacts(),
        "automatic_evaluation_basis": {
            "requirement_ids": ["REQ-C1"], "regulatory_catalog_version": "v1",
            "applicability_matrix_version": "v1", "evaluation_run_id": "RUN-TEST-0001",
        },
        "generation_commit_sha": "deadbeef",
    })
    assert r.status_code == 400, r.text
    assert "no existe" in r.text


def test_create_package_rejects_directive_not_submitted(client, monkeypatch, tmp_path):
    remediation_directive = _use_real_directive_resolver(monkeypatch, tmp_path)
    remediation_directive.DIRECTIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    remediation_directive.DIRECTIVES_FILE.write_text(
        json.dumps(_real_directive("DIR-C1", status="SUPERSEDED")) + "\n", encoding="utf-8")
    r = client.post(f"{BASE}/{PROJECT_ID}/PKG-P0-3/1", json={
        "changes": [_change("C1")], "artifacts": _artifacts(),
        "automatic_evaluation_basis": {
            "requirement_ids": ["REQ-C1"], "regulatory_catalog_version": "v1",
            "applicability_matrix_version": "v1", "evaluation_run_id": "RUN-TEST-0001",
        },
        "generation_commit_sha": "deadbeef",
    })
    assert r.status_code == 400, r.text
    assert "SUBMITTED" in r.text


def test_create_package_succeeds_with_real_submitted_directive(client, monkeypatch, tmp_path):
    """El camino que SI debe funcionar: una RemediationDirective real,
    SUBMITTED, con directive_id resoluble -- exactamente lo que el bypass
    (hallazgo I) permitia saltarse."""
    remediation_directive = _use_real_directive_resolver(monkeypatch, tmp_path)
    remediation_directive.DIRECTIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    remediation_directive.DIRECTIVES_FILE.write_text(
        json.dumps(_real_directive("DIR-C1", status="SUBMITTED")) + "\n", encoding="utf-8")
    r = client.post(f"{BASE}/{PROJECT_ID}/PKG-P0-4/1", json={
        "changes": [_change("C1")], "artifacts": _artifacts(),
        "automatic_evaluation_basis": {
            "requirement_ids": ["REQ-C1"], "regulatory_catalog_version": "v1",
            "applicability_matrix_version": "v1", "evaluation_run_id": "RUN-TEST-0001",
        },
        "generation_commit_sha": "deadbeef",
    })
    assert r.status_code == 201, r.text


# ── Paquete 4/K2: GET /{project_id} -- listado de paquetes ────────────────

def test_list_packages_empty_project_returns_empty_list(client):
    r = client.get(f"{BASE}/{PROJECT_ID}")
    assert r.status_code == 200
    assert r.json() == {"packages": []}


def test_list_packages_returns_one_summary_per_package_id(client):
    _create(client, "PKG-LIST-1")
    _create(client, "PKG-LIST-2")
    r = client.get(f"{BASE}/{PROJECT_ID}")
    assert r.status_code == 200
    by_id = {p["package_id"]: p for p in r.json()["packages"]}
    assert set(by_id) == {"PKG-LIST-1", "PKG-LIST-2"}
    entry = by_id["PKG-LIST-1"]
    assert entry["project_id"] == PROJECT_ID
    assert entry["version"] == 1
    assert entry["other_versions"] == []
    assert entry["status"] == "AWAITING_PACKAGE_DECISION"
    assert entry["risk_counts"] == {"low_risk": 1, "medium_risk": 0, "high_risk": 0}
    assert entry["package_decision"] is None


def test_list_packages_reflects_the_latest_version_only(client):
    _create(client, "PKG-LIST-V", version=1)
    _create(client, "PKG-LIST-V", version=2)
    r = client.get(f"{BASE}/{PROJECT_ID}")
    entries = [p for p in r.json()["packages"] if p["package_id"] == "PKG-LIST-V"]
    assert len(entries) == 1
    assert entries[0]["version"] == 2
    assert entries[0]["other_versions"] == [1]


def test_list_packages_reflects_a_real_decision(client, identity_headers):
    _create(client, "PKG-LIST-D")
    decide = _decide(client, "PKG-LIST-D", identity_headers, justification="cerrado limpio")
    assert decide.status_code == 201, decide.text
    r = client.get(f"{BASE}/{PROJECT_ID}")
    entry = next(p for p in r.json()["packages"] if p["package_id"] == "PKG-LIST-D")
    assert entry["status"] == "PACKAGE_READY_FOR_RELEASE"
    assert entry["package_decision"]["decision"] == "APPROVE_CLEAN"
    assert entry["package_decision"]["decided_by"] == "Cesar"


def test_list_packages_never_requires_identity(client):
    """Listar es solo lectura -- a diferencia de /decision, no exige
    X-Identity-Key."""
    _create(client, "PKG-LIST-RO")
    r = client.get(f"{BASE}/{PROJECT_ID}")
    assert r.status_code == 200
