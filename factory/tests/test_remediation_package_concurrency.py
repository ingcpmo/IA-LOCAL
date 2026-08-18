"""
Tests — escritura segura bajo concurrencia real (factory/services/
remediation_package_service.py): cero corrupcion, cero decisiones
duplicadas, cero releases duplicados, versiones monotonicas, recuperacion
ante fallo intermedio.

Los tests de release/decision usan multiprocessing.Pool (procesos reales,
como multiples workers de gunicorn) porque fcntl.flock es lo que hay que
demostrar bajo procesos separados, no solo hilos del mismo interprete.
"""

import hashlib
import json
import multiprocessing
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from factory.core import audit_writer
from factory.services import paths
from factory.services import remediation_package_service as svc

PROJECT_ID = "gmpai_document_validation_concurrency_test"


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


def _basis() -> dict:
    return {
        "requirements_applicable": 1, "coverage_complete_by_requirement": {"REQ-C1": True},
        "expected_chunks": 5, "evaluated_chunks": 5, "execution_errors": 0, "rejected_records": 0,
    }


LOW_RISK_FACTORS = {
    "change_type": "COSMETIC", "requirement_criticality": "MINOR", "gxp_impact": "NONE",
    "evidence_status": "LITERAL_EVIDENCE_CONFIRMED", "functional_impact": "DOCUMENTATION_ONLY",
}


@pytest.fixture(autouse=True)
def _isolated_remediation_packages_base(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "REMEDIATION_PACKAGES_BASE", tmp_path / "remediation_packages")
    # Aislamiento de auditoria (ver misma nota en test_remediation_package_service.py).
    # El patch ocurre ANTES de crear cualquier Pool: los procesos hijo (fork)
    # heredan la memoria ya parcheada del proceso padre en el momento del fork.
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", tmp_path / "audit" / "test_factory_audit.jsonl")
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    # Resolutor de directivas sintetico (mismo patron/razon que
    # test_remediation_package_service.py): estos tests prueban concurrencia
    # de escritura, no el flujo de RemediationDirective. Debe patchearse
    # ANTES de crear cualquier Pool: los procesos hijo (fork) heredan la
    # memoria ya parcheada del proceso padre en el momento del fork.
    monkeypatch.setattr(svc, "_resolve_directive", lambda directive_id: {"status": "SUBMITTED"})
    yield tmp_path / "remediation_packages"


# ── Multiprocessing worker functions (deben ser top-level para picklear) ────

def _mp_worker_create_release(args):
    """Cada proceso hijo reconfigura su propia base de persistencia (import
    fresco del modulo) y compite por liberar la MISMA (package_id, version)."""
    base_dir, project_id, package_id = args
    import importlib
    from factory.services import paths as _paths
    from factory.services import remediation_package_service as _svc
    importlib.reload(_paths)
    _paths.REMEDIATION_PACKAGES_BASE = Path(base_dir)
    try:
        record = _svc.create_release_record(
            project_id=project_id, package_id=package_id, package_version=1, released_by="worker")
        return ("ok", record["release_id"])
    except _svc.DuplicateReleaseError as e:
        return ("duplicate", str(e))
    except Exception as e:  # cualquier otro error cuenta como fallo real
        return ("error", f"{type(e).__name__}: {e}")


def _mp_worker_package_decision(args):
    base_dir, project_id, package_id = args
    import importlib
    from factory.services import paths as _paths
    from factory.services import remediation_package_service as _svc
    importlib.reload(_paths)
    _paths.REMEDIATION_PACKAGES_BASE = Path(base_dir)
    try:
        record = _svc.record_package_decision(
            project_id=project_id, package_id=package_id, package_version=1,
            decision="APPROVE_CLEAN", decided_by="worker", justification="concurrencia sintetica")
        return ("ok", record["decision_id"])
    except _svc.InvalidTransitionError as e:
        return ("blocked", str(e))
    except Exception as e:
        return ("error", f"{type(e).__name__}: {e}")


def _approved_ready_package(base_dir: Path, package_id: str) -> None:
    """Crea y aprueba un paquete LOW_RISK limpio, dejandolo en
    PACKAGE_READY_FOR_RELEASE, listo para que los procesos compitan por
    liberarlo."""
    import importlib
    from factory.services import paths as _paths
    importlib.reload(_paths)
    _paths.REMEDIATION_PACKAGES_BASE = base_dir
    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                        changes=[_change("C1", LOW_RISK_FACTORS)], artifacts=_artifacts(),
                        automatic_evaluation_basis=_basis(), generation_commit_sha="deadbeef")


# ── Cero releases duplicados (multiproceso) ─────────────────────────────────

def test_concurrent_processes_never_create_duplicate_release(_isolated_remediation_packages_base):
    base_dir = _isolated_remediation_packages_base
    package_id = "PKG-MP-RELEASE"
    _approved_ready_package(base_dir, package_id)
    svc.record_package_decision(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                                 decision="APPROVE_CLEAN", decided_by="setup", justification="preparacion")

    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=8) as pool:
        results = pool.map(_mp_worker_create_release, [(str(base_dir), PROJECT_ID, package_id)] * 8)

    ok_results = [r for r in results if r[0] == "ok"]
    duplicate_results = [r for r in results if r[0] == "duplicate"]
    error_results = [r for r in results if r[0] == "error"]

    assert error_results == [], f"ningun proceso debe fallar por error inesperado: {error_results}"
    assert len(ok_results) == 1, f"exactamente UN proceso debe lograr crear el release: {results}"
    assert len(duplicate_results) == 7

    releases = svc._read_jsonl(svc._releases_path(PROJECT_ID, package_id))
    assert len(releases) == 1, "cero releases duplicados en disco"
    # cero corrupcion: el unico release en disco es JSON valido y coincide con el ganador
    assert releases[0]["release_id"] == ok_results[0][1]


# ── Cero decisiones duplicadas (multiproceso) ───────────────────────────────

def test_concurrent_processes_never_record_duplicate_package_decision(_isolated_remediation_packages_base):
    base_dir = _isolated_remediation_packages_base
    package_id = "PKG-MP-DECISION"
    _approved_ready_package(base_dir, package_id)

    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=8) as pool:
        results = pool.map(_mp_worker_package_decision, [(str(base_dir), PROJECT_ID, package_id)] * 8)

    ok_results = [r for r in results if r[0] == "ok"]
    blocked_results = [r for r in results if r[0] == "blocked"]
    error_results = [r for r in results if r[0] == "error"]

    assert error_results == [], f"ningun proceso debe fallar por error inesperado: {error_results}"
    assert len(ok_results) == 1, f"exactamente UNA decision de paquete debe registrarse: {results}"
    assert len(blocked_results) == 7

    state = svc._read_state(PROJECT_ID, package_id, 1)
    assert state["package_decision"]["decision_id"] == ok_results[0][1]
    assert state["package"]["status"] == "PACKAGE_READY_FOR_RELEASE"


# ── Cero corrupción bajo hilos concurrentes escribiendo excepciones ─────────

def test_concurrent_threads_never_corrupt_state_json(_isolated_remediation_packages_base):
    base_dir = _isolated_remediation_packages_base
    package_id = "PKG-THREADS"
    high_risk_factors = {
        "change_type": "CONTENT_REPLACEMENT", "requirement_criticality": "CRITICAL",
        "gxp_impact": "DIRECT_GXP_IMPACT", "evidence_status": "ABSENCE_CONFIRMED",
        "functional_impact": "SYSTEM_BEHAVIOR_CHANGE",
    }
    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                        changes=[_change("C-HIGH", high_risk_factors)], artifacts=_artifacts(),
                        automatic_evaluation_basis={
                            "requirements_applicable": 1,
                            "coverage_complete_by_requirement": {"REQ-C-HIGH": True},
                            "expected_chunks": 5, "evaluated_chunks": 5,
                            "execution_errors": 0, "rejected_records": 0,
                        }, generation_commit_sha="deadbeef")

    results = []

    def _attempt():
        try:
            svc.record_exception_review(
                project_id=PROJECT_ID, package_id=package_id, package_version=1, change_id="C-HIGH",
                human_review_decision="accept_risk", responsible="qa_lead", justification="riesgo aceptado")
            results.append("ok")
        except Exception as e:  # el mismo change_id revisado 2 veces solo debe sobreescribir su propio registro
            results.append(f"error:{type(e).__name__}")

    threads = [threading.Thread(target=_attempt) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # cero corrupcion: state.json final SIEMPRE es JSON valido y consistente
    state_path = svc._state_path(PROJECT_ID, package_id, 1)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["package"]["status"] == "AWAITING_PACKAGE_DECISION"
    assert state["package"]["human_exception_review_complete"] is True
    assert len(state["exceptions"]) == 1  # un solo change_id -- un solo exception_id posible
    assert all(r == "ok" for r in results)


# ── Versiones monotónicas ────────────────────────────────────────────────────

def test_versions_are_strictly_monotonic():
    package_id = "PKG-MONOTONIC"
    change = _change("C1", LOW_RISK_FACTORS)
    with pytest.raises(svc.DuplicateVersionError, match="primera version debe ser v1"):
        svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=2,
                            changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                            generation_commit_sha="deadbeef")

    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                        changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                        generation_commit_sha="deadbeef")

    # reusar el mismo numero de version -> duplicado exacto
    with pytest.raises(svc.DuplicateVersionError, match="ya existe"):
        svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                            changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                            generation_commit_sha="deadbeef")

    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=5,
                        changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                        generation_commit_sha="deadbeef2")

    # version intermedia nunca usada (3) pero por debajo de la maxima existente (5) -> retroceso rechazado
    with pytest.raises(svc.DuplicateVersionError, match="estrictamente monotonicas"):
        svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=3,
                            changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                            generation_commit_sha="deadbeef3")


# ── Recuperación ante fallo intermedio ───────────────────────────────────────

def test_recovers_safely_from_stray_temp_file_left_by_a_crash():
    """Simula un proceso que murio DESPUES de escribir el temporal pero
    ANTES de os.replace(): un *.tmp.* huerfano en el directorio de la
    version nunca debe interferir con lecturas/escrituras posteriores."""
    package_id = "PKG-CRASH-RECOVERY"
    change = _change("C1", LOW_RISK_FACTORS)
    svc.create_package(project_id=PROJECT_ID, package_id=package_id, package_version=1,
                        changes=[change], artifacts=_artifacts(), automatic_evaluation_basis=_basis(),
                        generation_commit_sha="deadbeef")

    version_dir = svc._version_dir(PROJECT_ID, package_id, 1)
    stray_tmp = version_dir / "state.json.tmp.deadbeefdeadbeefdeadbeefdeadbeef"
    stray_tmp.write_text('{"corrupted": true, "incomplete"', encoding="utf-8")  # JSON invalido a proposito

    # el estado real sigue siendo el ultimo escrito correctamente -- el huerfano se ignora
    state_before = svc._read_state(PROJECT_ID, package_id, 1)
    assert state_before["package"]["status"] == "AWAITING_PACKAGE_DECISION"

    # una escritura legitima posterior funciona con normalidad pese al huerfano presente
    decision = svc.record_package_decision(
        project_id=PROJECT_ID, package_id=package_id, package_version=1,
        decision="APPROVE_CLEAN", decided_by="cesar", justification="recuperacion verificada")
    assert decision["decision"] == "APPROVE_CLEAN"

    state_after = svc._read_state(PROJECT_ID, package_id, 1)
    assert state_after["package"]["status"] == "PACKAGE_READY_FOR_RELEASE"
    assert stray_tmp.exists()  # el huerfano no se borra solo, pero tampoco corrompe nada
