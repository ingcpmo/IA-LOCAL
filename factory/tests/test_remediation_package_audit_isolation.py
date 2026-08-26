"""
Tests — aislamiento de auditoria para la suite BATCH_AND_EXCEPTION.

Antes de esta correccion, test_remediation_package_service.py y
test_remediation_package_concurrency.py llamaban a write_event() SIN
aislar factory.core.audit_writer.AUDIT_FILE, escribiendo eventos reales en
factory/audit/factory_audit.jsonl. Se documento el rango exacto ya escrito
(ver docstring de test_documents_synthetic_events_already_written_and_
does_not_delete_them) -- esos eventos NO se borran ni se reescriben (la
cadena de auditoria es append-only por diseno, ver audit_writer.py).

Este archivo demuestra que, con el aislamiento ya aplicado en los otros dos
archivos de test, un ciclo COMPLETO de BATCH_AND_EXCEPTION (que dispara 6
tipos de evento reales) deja el archivo REAL exactamente byte-a-byte
identico.
"""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.core import audit_writer
from factory.core import release_authorization
from factory.services import paths
from factory.services import remediation_package_service as svc

# Misma construccion que audit_writer.AUDIT_FILE en su definicion original
# (factory/core/audit_writer.py linea 30) -- deliberadamente hardcodeado
# aqui, independiente de cualquier monkeypatch, para poder tomar una
# instantanea del archivo REAL antes de que cualquier fixture lo parchee.
REAL_AUDIT_FILE = Path(audit_writer.__file__).parent.parent / "audit" / "factory_audit.jsonl"

PROJECT_ID = "gmpai_document_validation_audit_isolation_test"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _citation(change_id: str) -> dict:
    literal_text = f"texto literal sintetico {change_id}"
    return {
        "citation_id": f"CIT-{change_id}", "regulatory_catalog_entry_id": "ALCOA_CONTEMPORANEOUS",
        "regulatory_source": "ALCOA+", "regulatory_source_sha256": _sha256("source"),
        "requirement_catalog_sha256": _sha256("catalog"), "run_id": "RUN-1", "record_id": f"REC-{change_id}",
        "document_role": "CANDIDATE_DOCUMENT", "document_sha256": _sha256("doc"),
        "chunk_sha256": _sha256(f"chunk-{change_id}"), "citation_locator": "chunk_20#p12-14",
        "page_start": 12, "page_end": 14, "literal_text": literal_text,
        "citation_text_sha256": _sha256(literal_text), "evidence_type": "LITERAL_QUOTE",
        "evidence_location": "seccion 4.2",
    }


def _change(change_id: str, risk_factors: dict) -> dict:
    risk, risk_basis = svc.compute_change_risk(risk_factors)
    return {
        "change_id": change_id, "finding_id": f"F-{change_id}", "requirement_id": f"REQ-{change_id}",
        "document_location": "chunk_1", "original_content": None, "proposed_content": "texto propuesto",
        "change_reason": "gap sintetico", "change_type": risk_factors["change_type"],
        "citations": [_citation(change_id)], "change_risk": risk, "change_risk_basis": risk_basis,
        "evaluation_confidence": "HIGH_CONFIDENCE", "evaluation_confidence_basis": ["coverage_status"],
        "schema_validation_status": "PASSED", "citation_anchor_status": "VERIFIED",
        "relevance_status": "CONFIRMED", "candidate_application_status": "APPLIED_TO_DRAFT", "limitations": "",
        "directive_id": f"DIR-{change_id}",
    }


def _artifact(kind: str, classification: str) -> dict:
    return {
        "artifact_id": f"ART-{kind}", "storage_location": f"/synthetic/{kind}.bin",
        "mime_type": "application/octet-stream", "sha256": _sha256(f"payload-{kind}"), "size_bytes": 1024,
        "classification": classification, "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _artifacts() -> dict:
    return {
        "source_document": _artifact("source_document", "SOURCE_IMMUTABLE"),
        "candidate_document": _artifact("candidate_document", "CANDIDATE_DRAFT"),
        "remediation_report": _artifact("remediation_report", "REPORT"),
        "redline_document": _artifact("redline_document", "REDLINE"),
        "package_manifest": _artifact("package_manifest", "MANIFEST"),
    }


HIGH_RISK_FACTORS = {
    "change_type": "CONTENT_REPLACEMENT", "requirement_criticality": "CRITICAL",
    "gxp_impact": "DIRECT_GXP_IMPACT", "evidence_status": "ABSENCE_CONFIRMED",
    "functional_impact": "SYSTEM_BEHAVIOR_CHANGE",
}


def test_real_audit_log_unchanged_after_full_batch_and_exception_lifecycle(tmp_path, monkeypatch):
    """Ejercita los 6 eventos reales de BATCH_AND_EXCEPTION (candidate_document_
    created, remediation_report_created, remediation_package_generated,
    exception_reviewed, package_decision_recorded, document_released) con el
    aislamiento aplicado, y confirma que factory/audit/factory_audit.jsonl
    (el archivo REAL) es byte-a-byte identico antes y despues."""
    before_bytes = REAL_AUDIT_FILE.read_bytes() if REAL_AUDIT_FILE.exists() else None

    monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
    isolated_audit_file = tmp_path / "audit" / "isolated_test_audit.jsonl"
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", isolated_audit_file)
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    # Resolutor de directivas sintetico (mismo patron/razon que
    # test_remediation_package_service.py): este test prueba aislamiento de
    # auditoria, no el flujo de RemediationDirective.
    monkeypatch.setattr(svc, "_resolve_directive", lambda directive_id: {"status": "SUBMITTED"})
    # Decision 2 (2026-08-26): este test prueba aislamiento de auditoria,
    # no autorizacion de release -- se mockea aparte, mismo criterio que
    # test_remediation_package_service.py.
    monkeypatch.setattr(release_authorization, "is_authorized_to_release", lambda name, **k: True)

    package_id = "PKG-AUDIT-ISOLATION"
    pkg = svc.create_package(
        project_id=PROJECT_ID, package_id=package_id, package_version=1,
        changes=[_change("C-HIGH", HIGH_RISK_FACTORS)], artifacts=_artifacts(),
        automatic_evaluation_basis={
            "requirements_applicable": 1, "coverage_complete_by_requirement": {"REQ-C-HIGH": True},
            "expected_chunks": 5, "evaluated_chunks": 5, "execution_errors": 0, "rejected_records": 0,
        }, generation_commit_sha="deadbeef")
    assert pkg["status"] == "AWAITING_HUMAN_EXCEPTION_REVIEW"

    svc.record_exception_review(
        project_id=PROJECT_ID, package_id=package_id, package_version=1, change_id="C-HIGH",
        human_review_decision="accept_risk", responsible="qa_lead", justification="riesgo aceptado (test)")
    svc.record_package_decision(
        project_id=PROJECT_ID, package_id=package_id, package_version=1,
        decision="APPROVE_WITH_EXCEPTIONS", decided_by="cesar", justification="test aislado",
        high_risk_exception_ids=["EXC-C-HIGH"])
    release = svc.create_release_record(
        project_id=PROJECT_ID, package_id=package_id, package_version=1, released_by="qa_lead")
    assert release["release_id"]

    # el archivo AISLADO si recibio los eventos (confirma que write_event
    # realmente se ejecuto, no que el aislamiento simplemente lo silencio)
    assert isolated_audit_file.exists()
    isolated_events = [
        line for line in isolated_audit_file.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(isolated_events) == 6, "deben registrarse los 6 eventos del ciclo completo"

    after_bytes = REAL_AUDIT_FILE.read_bytes() if REAL_AUDIT_FILE.exists() else None
    assert before_bytes == after_bytes, (
        "factory/audit/factory_audit.jsonl (el archivo REAL) debe permanecer "
        "byte-a-byte identico -- ningun test debe escribir alli")


def test_documents_synthetic_events_already_written_and_does_not_delete_them():
    """No corrige retroactivamente el archivo REAL (append-only, nunca se
    reescribe la cadena historica): documenta -- sin borrar nada -- el rango
    y cantidad de eventos sinteticos que quedaron escritos por corridas
    ANTERIORES a este fix (proyectos de prueba de esta misma tarea, antes de
    que el aislamiento de auditoria se implementara).

    Rango documentado (verificado 2026-07-21, no modificado desde entonces):
      gmpai_document_validation_test               ->   530 eventos
      gmpai_document_validation_concurrency_test   ->   161 eventos
      synthetic_demo_project                       ->     3 eventos
      synthetic_demo_project_v2                    -> 8,411 eventos
      TOTAL                                        -> 9,105 eventos
      timestamp min: 2026-07-21T04:19:27.768831+00:00
      timestamp max: 2026-07-21T05:10:43.563307+00:00

    Este test NO relee esos numeros dinamicamente (evitaria que el numero
    documentado se mueva silenciosamente si alguien vuelve a ejecutar algo
    sin aislar) -- solo confirma que el archivo real sigue existiendo, sigue
    conteniendo al menos esos eventos historicos, y que la cadena de
    auditoria permanece verificable (hash_errors=0) pese a ellos."""
    if not REAL_AUDIT_FILE.exists():
        pytest.skip("factory/audit/factory_audit.jsonl no existe en este entorno")

    documented_synthetic_project_ids = {
        "gmpai_document_validation_test": 530,
        "gmpai_document_validation_concurrency_test": 161,
        "synthetic_demo_project": 3,
        "synthetic_demo_project_v2": 8411,
    }
    lines = [l for l in REAL_AUDIT_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= sum(documented_synthetic_project_ids.values()), (
        "el archivo real nunca debe tener MENOS entradas que las historicas documentadas "
        "-- append-only, nunca se borra ni se reescribe la cadena")

    from factory.core.audit_writer import verify_chain
    result = verify_chain()
    assert result["hash_errors"] == 0, (
        "los eventos sinteticos historicos son contenido autentico (hash_errors=0), "
        "no corrupcion -- solo ruido de proyectos de prueba mezclado con produccion")
