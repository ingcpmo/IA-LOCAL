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
from factory.services.test_console_service import RESERVED_RUN_BY

PROJECT_ID = "gmpai_document_validation_test"
BASE = "/api/v1/remediation-packages"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Mismo aislamiento que test_remediation_package_service.py: estado en
    tmp_path y auditoria fuera del jsonl real de la fabrica."""
    monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", tmp_path / "audit" / "test_factory_audit.jsonl")
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
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


def _decide(client, package_id, *, version=1, decided_by="cesar", justification="ok"):
    return client.post(f"{BASE}/{PROJECT_ID}/{package_id}/{version}/decision", json={
        "decision": "APPROVE_CLEAN", "decided_by": decided_by, "justification": justification,
    })


# ── Fase P: el contrato HTTP real ────────────────────────────────────────

def test_first_decision_returns_201_with_human_confirmed_origin(client):
    _create(client, "PKG-HTTP-1")
    r = _decide(client, "PKG-HTTP-1", justification="primera decision")
    assert r.status_code == 201, r.text
    assert r.json()["decision_origin"] == "human_confirmed"


def test_double_decision_returns_409_not_400(client):
    """La regresion concreta que ningun test cubria: si el except especifico
    de PackageDecisionAlreadyRecordedError se moviera despues del generico
    (es subclase de InvalidTransitionError), esto devolveria 400."""
    _create(client, "PKG-HTTP-2")
    assert _decide(client, "PKG-HTTP-2", justification="primera").status_code == 201
    r = _decide(client, "PKG-HTTP-2", justification="segunda")
    assert r.status_code == 409, f"esperado 409 (idempotencia), obtenido {r.status_code}: {r.text}"


def test_premature_state_is_400_so_409_keeps_meaning_something(client):
    """Contrapeso: el 409 solo significa algo si otros errores de
    transicion NO son 409. Una decision sobre un paquete inexistente da
    404, y un cuerpo invalido da 400 -- nunca 409."""
    r = _decide(client, "PKG-NO-EXISTE")
    assert r.status_code == 404, r.text


def test_empty_decided_by_is_rejected_over_http(client):
    """Fase P: identidad real del aprobador validada con validate_run_by.
    Sobre HTTP el rechazo debe ser un error de cliente, nunca un 201."""
    _create(client, "PKG-HTTP-3")
    r = _decide(client, "PKG-HTTP-3", decided_by="   ")
    assert r.status_code in (400, 422), r.text
    assert r.status_code != 201


@pytest.mark.parametrize("reserved", sorted(RESERVED_RUN_BY))
def test_generic_reserved_identity_is_rejected_over_http(client, reserved):
    """Los 6 nombres genericos reservados reales de validate_run_by, no una
    lista adivinada: una aprobacion regulatoria firmada por 'system' o
    'admin' no identifica a nadie."""
    _create(client, f"PKG-HTTP-R-{reserved}")
    r = _decide(client, f"PKG-HTTP-R-{reserved}", decided_by=reserved)
    assert r.status_code in (400, 422), r.text
