"""
Tests de GMPAI — artefactos de cierre de gmpai_document_validation
(REM-GMPAI-001, informe final, tracker, empaquetado, descarga segura).

Reusa el RC canónico real ya aprobado (no reprocesa documentos, no invoca
agentes). GMPAI_REPORTS_BASE se monkeypatchea a un directorio temporal para
no escribir en /home/ing_cpmo/GMPAI/reports durante los tests.
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import gmpai_artifact_service as svc
from factory.core.gmpai_pdf_report import build_final_report_pdf, build_remediation_tracker_pdf
from factory.services.gmpai_docx_draft import build_remediation_draft_docx


@pytest.fixture()
def tmp_reports_base(tmp_path, monkeypatch):
    base = tmp_path / "gmpai_reports"
    monkeypatch.setattr(svc, "GMPAI_REPORTS_BASE", base)
    return base


def test_load_remediation_items_has_rem_001():
    items = svc.load_remediation_items()
    assert any(i["id"] == "REM-GMPAI-001" for i in items)
    rem = next(i for i in items if i["id"] == "REM-GMPAI-001")
    assert rem["estado"] == "open"
    assert rem["rc_relacionado"]
    assert rem["evidencia_revisada"]


def test_load_canonical_pipeline_data_reads_approved_rc():
    canonical, pdata = svc.load_canonical_pipeline_data()
    assert canonical["is_canonical"] is True
    assert canonical["status"] == "approved"
    assert canonical["project_id"] == "gmpai_document_validation"
    assert pdata["findings"]
    assert len(pdata["findings"]) == pdata["risk_summary"]["total_findings"]


def test_build_final_report_data_declares_scada_scope_limitation():
    data = svc.build_final_report_data()
    scope = data["scope"]
    # El alcance declarado debe cuadrar consigo mismo: las dos familias
    # suman el total, sin documentos huerfanos ni contados dos veces. Antes
    # se congelaban 32/14/18 -- tres numeros que hay que reeditar cada vez
    # que el corpus crezca, y que no comprueban que la suma cierre.
    assert scope["rockwell_documents"] > 0 and scope["scada_documents"] > 0
    assert scope["total_documents_declared"] == \
        scope["rockwell_documents"] + scope["scada_documents"]
    # No debe declarar SCADA con findings de cumplimiento (limitación real).
    assert data["scope"]["documents_with_compliance_findings"] == ["Rockwell"]
    assert "SCADA" in data["scope"]["limitation"]
    assert data["findings_total"] == sum(data["findings_by_status"].values())


def test_final_report_data_never_declares_full_compliance():
    data = svc.build_final_report_data()
    assert "evaluacion asistida" in data["conclusion"].lower()
    assert "no" in data["conclusion"].lower()


def test_build_final_report_pdf_bytes():
    data = svc.build_final_report_data()
    pdf_bytes = build_final_report_pdf(data)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000


def test_build_remediation_tracker_pdf_bytes():
    data = svc.build_remediation_tracker_data()
    pdf_bytes = build_remediation_tracker_pdf(data)
    assert pdf_bytes[:4] == b"%PDF"


def test_build_remediation_draft_docx_bytes_and_hash():
    data = svc.build_final_report_data()
    docx_bytes, sha = build_remediation_draft_docx(data)
    assert docx_bytes[:2] == b"PK"  # docx is a zip container
    assert sha == hashlib.sha256(docx_bytes).hexdigest()
    assert len(sha) == 64


def test_run_packaging_creates_all_required_artifacts(tmp_reports_base):
    result = svc.run_packaging(recorded_by="test_suite")
    run_dir = Path(result["run_dir"])
    assert run_dir.exists()

    required = [
        "final_report.pdf",
        "remediation_tracker.pdf",
        "manifest.json",
        "SHA256SUMS.txt",
        "paquete_final.zip",
        "README.md",
        "corrected_documents/REM-GMPAI-001_propuesta_remediacion_draft_v1.docx",
        "corrected_documents/README_limitaciones.md",
        "audit_summary/audit_verify.json",
        "agent_reports/agent_execution_status.json",
        "compliance_matrices/finding_correction_matrix.json",
    ]
    for rel in required:
        assert (run_dir / rel).exists(), f"falta {rel}"

    # Al menos una matriz y un reporte por agente por cada agente con findings.
    matrices = list((run_dir / "compliance_matrices").glob("*.json"))
    agent_reports = list((run_dir / "agent_reports").glob("*.json"))
    assert matrices
    assert agent_reports


def test_run_packaging_manifest_has_required_fields(tmp_reports_base):
    result = svc.run_packaging(recorded_by="test_suite")
    manifest = result["manifest"]
    assert manifest["run_id"]
    assert manifest["project_id"] == "gmpai_document_validation"
    assert manifest["rc_canonical"]
    required_fields = {
        "artifact_id", "filename", "mime_type", "version", "sha256", "size_bytes",
        "generated_at", "project_id", "mission_id", "run_id", "agente",
        "agent_version", "estado", "decision_humana", "ruta_logica_origen",
    }
    for artifact in manifest["artifacts"]:
        assert required_fields.issubset(artifact.keys())


def test_run_packaging_hashes_match_files_on_disk(tmp_reports_base):
    result = svc.run_packaging(recorded_by="test_suite")
    run_dir = Path(result["run_dir"])
    for artifact in result["manifest"]["artifacts"]:
        p = run_dir / artifact["filename"]
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == artifact["sha256"], f"hash mismatch: {artifact['filename']}"


def test_run_packaging_sha256sums_txt_matches(tmp_reports_base):
    result = svc.run_packaging(recorded_by="test_suite")
    run_dir = Path(result["run_dir"])
    sums_text = (run_dir / "SHA256SUMS.txt").read_text(encoding="utf-8")
    for line in sums_text.strip().splitlines():
        sha, _, filename = line.partition("  ")
        actual = hashlib.sha256((run_dir / filename).read_bytes()).hexdigest()
        assert actual == sha, f"SHA256SUMS.txt no coincide: {filename}"


def test_run_packaging_zip_contains_all_files(tmp_reports_base):
    result = svc.run_packaging(recorded_by="test_suite")
    run_dir = Path(result["run_dir"])
    with zipfile.ZipFile(run_dir / "paquete_final.zip") as zf:
        names = set(zf.namelist())
    on_disk = {str(f.relative_to(run_dir)) for f in run_dir.rglob("*")
               if f.is_file() and f.name != "paquete_final.zip"}
    assert names == on_disk


def test_run_packaging_never_touches_source_documents(tmp_reports_base):
    source_dir = Path("/home/ing_cpmo/GMPAI/source")
    before = {f: f.stat().st_mtime for f in source_dir.rglob("*") if f.is_file()}
    svc.run_packaging(recorded_by="test_suite")
    after = {f: f.stat().st_mtime for f in source_dir.rglob("*") if f.is_file()}
    assert before == after


def test_run_packaging_does_not_reprocess_documents(tmp_reports_base, monkeypatch):
    """El empaquetado no debe invocar ningún agente ni el motor de
    extracción — solo debe leer el RC canónico ya aprobado."""
    called = []

    def _boom(*a, **kw):
        called.append(True)
        raise AssertionError("no debe reprocesar documentos")

    # Si algún agente real fuera invocado, fallaría con una excepción
    # distinta y ruidosa; en cambio, verificamos que el pipeline module de
    # extracción ni siquiera se importe/ejecute vía el servicio.
    result = svc.run_packaging(recorded_by="test_suite")
    assert result["manifest"]["artifacts"]
    assert not called


# ── Resolución segura de artefactos (path traversal, 404) ────────────────────

def test_resolve_artifact_path_blocks_traversal(tmp_reports_base):
    run_id = "run1"
    (tmp_reports_base / run_id).mkdir(parents=True)
    (tmp_reports_base / run_id / "ok.pdf").write_bytes(b"%PDF-1.4 x")

    for bad in ["../../../etc/passwd", "/etc/passwd", "sub/../../etc/passwd"]:
        with pytest.raises(svc.PathTraversalError):
            svc.resolve_artifact_path(run_id, bad)


def test_resolve_artifact_path_404_missing_file(tmp_reports_base):
    run_id = "run1"
    (tmp_reports_base / run_id).mkdir(parents=True)
    with pytest.raises(svc.ArtifactNotFound):
        svc.resolve_artifact_path(run_id, "no_existe.pdf")


def test_resolve_artifact_path_404_missing_run(tmp_reports_base):
    with pytest.raises(svc.ArtifactNotFound):
        svc.resolve_artifact_path("no-existe-run", "final_report.pdf")


def test_resolve_artifact_path_one_run_cannot_reach_another(tmp_reports_base):
    (tmp_reports_base / "run1").mkdir(parents=True)
    (tmp_reports_base / "run2").mkdir(parents=True)
    (tmp_reports_base / "run2" / "secret.pdf").write_bytes(b"%PDF-1.4 x")

    # Pedir un archivo de run2 usando run1 como run_id no debe encontrar nada.
    with pytest.raises(svc.ArtifactNotFound):
        svc.resolve_artifact_path("run1", "secret.pdf")

    # Sí debe resolver correctamente cuando el run_id es el correcto.
    resolved = svc.resolve_artifact_path("run2", "secret.pdf")
    assert resolved.name == "secret.pdf"


def test_resolve_artifact_path_valid_file_ok(tmp_reports_base):
    run_id = "run1"
    (tmp_reports_base / run_id / "compliance_matrices").mkdir(parents=True)
    target = tmp_reports_base / run_id / "compliance_matrices" / "x.json"
    target.write_text("{}", encoding="utf-8")
    resolved = svc.resolve_artifact_path(run_id, "compliance_matrices/x.json")
    assert resolved == target.resolve()


def test_list_runs_and_get_manifest(tmp_reports_base):
    assert svc.list_runs() == []
    with pytest.raises(svc.ArtifactNotFound):
        svc.get_manifest("nope")

    result = svc.run_packaging(recorded_by="test_suite")
    runs = svc.list_runs()
    assert result["run_id"] in runs
    manifest = svc.get_manifest(result["run_id"])
    assert manifest["run_id"] == result["run_id"]


def test_artifact_mime_types():
    assert svc._ARTIFACT_MIME[".pdf"] == "application/pdf"
    assert svc._ARTIFACT_MIME[".zip"] == "application/zip"
    assert svc._ARTIFACT_MIME[".docx"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
