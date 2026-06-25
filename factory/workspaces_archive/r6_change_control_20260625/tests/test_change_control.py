"""Tests para GMP Change Control Module (r6_change_control)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app, _change_requests
from app.audit import write_audit_entry, verify_audit_integrity


@pytest.fixture(autouse=True)
def clear_state():
    _change_requests.clear()
    yield
    _change_requests.clear()


@pytest.fixture
def client():
    return TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["api"] == "ok"
    assert "pending_documents" in data
    assert len(data["pending_documents"]) == 3


# ── Status ────────────────────────────────────────────────────────────────────

def test_status(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    data = r.json()
    assert "pending_documents" in data
    for doc_status in data["pending_documents"].values():
        assert doc_status == "PENDING_DOCUMENT", "No deben existir claims regulatorios confirmados"


# ── Change Request CRUD ───────────────────────────────────────────────────────

def test_create_change_request(client):
    payload = {
        "title": "Cambio en procedimiento de limpieza CIP-001",
        "description": "Actualización del tiempo de enjuague de 10 a 15 minutos por validación",
        "priority": "HIGH",
        "initiator": "qa_analyst_01",
        "department": "Quality Assurance",
        "affected_systems": ["CIP-001", "LIMS-QA"],
        "justification": "Resultados de validación muestran mejor eficacia con 15 minutos",
    }
    r = client.post("/api/v1/change-request", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["cr_id"].startswith("CR-")
    assert data["status"] == "DRAFT"
    assert data["initiator"] == "qa_analyst_01"
    assert "audit_hash" in data
    assert len(data["audit_hash"]) == 64  # SHA256 hex


def test_get_change_request(client):
    r = client.post("/api/v1/change-request", json={
        "title": "Test CR para consulta",
        "description": "CR de prueba para validar GET endpoint",
        "initiator": "tester",
        "department": "QA",
        "justification": "Prueba de sistema"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.get(f"/api/v1/change-request/{cr_id}")
    assert r2.status_code == 200
    assert r2.json()["cr_id"] == cr_id


def test_get_nonexistent_cr_returns_404(client):
    r = client.get("/api/v1/change-request/CR-NONEXISTENT")
    assert r.status_code == 404


# ── Impact Assessment ─────────────────────────────────────────────────────────

def test_impact_assessment_high_priority(client):
    r = client.post("/api/v1/change-request", json={
        "title": "Cambio crítico en validación de proceso",
        "description": "Modificación de parámetros críticos de proceso de liofilización",
        "priority": "CRITICAL",
        "initiator": "process_engineer",
        "department": "Manufacturing",
        "affected_systems": ["LYOPH-01", "LIMS-MFG", "QC-SYSTEM"],
        "justification": "Optimización de ciclo basada en datos de desarrollo"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.get(f"/api/v1/change-request/{cr_id}/impact")
    assert r2.status_code == 200
    data = r2.json()
    assert data["risk_level"] == "HIGH"
    assert data["validation_required"] is True
    assert data["capa_required"] is True
    assert "PENDING_DOCUMENT" in data["regulatory_note"]


def test_impact_assessment_low_priority(client):
    r = client.post("/api/v1/change-request", json={
        "title": "Actualización menor de etiqueta",
        "description": "Corrección tipográfica en formulario interno de registro",
        "priority": "LOW",
        "initiator": "qa_clerk",
        "department": "QA",
        "justification": "Error tipográfico detectado en revisión rutinaria"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.get(f"/api/v1/change-request/{cr_id}/impact")
    assert r2.status_code == 200
    data = r2.json()
    assert data["risk_level"] == "LOW"
    assert data["capa_required"] is False


# ── Approval Workflow ─────────────────────────────────────────────────────────

def test_approve_cr(client):
    r = client.post("/api/v1/change-request", json={
        "title": "CR para aprobación",
        "description": "Cambio aprobado en procedimiento analítico",
        "initiator": "analyst",
        "department": "QC",
        "justification": "Mejora en precisión del método"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.post(f"/api/v1/change-request/{cr_id}/approve", json={
        "approver": "qa_manager_01",
        "decision": "APPROVED",
        "comments": "Revisado y aprobado tras verificación de datos de validación",
        "capa_required": False
    })
    assert r2.status_code == 200
    data = r2.json()
    assert data["new_status"] == "APPROVED"
    assert data["approver"] == "qa_manager_01"


def test_approve_cr_with_capa(client):
    r = client.post("/api/v1/change-request", json={
        "title": "CR con desviación — requiere CAPA",
        "description": "Cambio originado por desviación de calidad detectada",
        "priority": "HIGH",
        "initiator": "qa_supervisor",
        "department": "QA",
        "justification": "Corrección de desviación documentada en informe QA-2026-042"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.post(f"/api/v1/change-request/{cr_id}/approve", json={
        "approver": "qa_director",
        "decision": "APPROVED",
        "comments": "Aprobado con CAPA obligatorio",
        "capa_required": True
    })
    data = r2.json()
    assert data["capa_generated"] is True
    assert "capa_id" in data
    assert data["capa_id"] == f"CAPA-{cr_id}"


# ── Audit Trail ───────────────────────────────────────────────────────────────

def test_audit_trail_entries_created(client):
    r = client.post("/api/v1/change-request", json={
        "title": "CR para audit trail test",
        "description": "Validar que el audit trail se genera correctamente",
        "initiator": "auditor",
        "department": "QA",
        "justification": "Test de integridad de audit trail ALCOA+"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.get("/api/v1/audit-trail")
    assert r2.status_code == 200
    data = r2.json()
    assert data["count"] > 0
    assert data["alcoa_plus"] is True

    # Verificar que la entrada del CR está en el trail
    entries_for_cr = [e for e in data["entries"] if e.get("cr_id") == cr_id]
    assert len(entries_for_cr) >= 1
    assert entries_for_cr[0]["action"] == "CR_CREATED"


def test_audit_trail_filter_by_cr(client):
    r = client.post("/api/v1/change-request", json={
        "title": "CR específico para filtro",
        "description": "Test de filtrado de audit trail por CR ID",
        "initiator": "tester_filter",
        "department": "QA",
        "justification": "Validación de filtrado"
    })
    cr_id = r.json()["cr_id"]

    r2 = client.get(f"/api/v1/audit-trail?cr_id={cr_id}")
    data = r2.json()
    for entry in data["entries"]:
        assert entry["cr_id"] == cr_id


# ── Knowledge Stats ───────────────────────────────────────────────────────────

def test_knowledge_stats_pending(client):
    r = client.get("/api/v1/knowledge/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["corpus_ready"] is False
    assert data["go_live_blocked"] is True
    for col_name, col_data in data["collections"].items():
        assert col_data["status"] == "PENDING_DOCUMENT", (
            f"Colección '{col_name}' no debe tener datos sin PDFs ingestados"
        )


# ── Audit Integrity (ALCOA+) ──────────────────────────────────────────────────

def test_audit_write_and_verify(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    import app.audit as audit_module
    audit_module.AUDIT_LOG_DIR = tmp_path

    entry = write_audit_entry(
        action="TEST_ACTION",
        actor="test_user",
        details={"key": "value"},
        cr_id="CR-TEST001"
    )
    assert "data_hash" in entry
    assert len(entry["data_hash"]) == 64
    assert entry["alcoa_compliant"] is True

    result = verify_audit_integrity()
    assert result["verified"] is True
    assert result["entry_count"] == 1
    assert result["corrupted_entries"] == []
