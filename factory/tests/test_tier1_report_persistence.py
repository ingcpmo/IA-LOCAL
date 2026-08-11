"""R2.3/D2 -- tests de persistencia del informe Tier-1 asistido:
path_policy (confinamiento de run_id), tier1_report_writer (escritura
atómica, tamaño, permisos) y tier1_report_service (lectura de solo-lectura).
Mismo patrón que test_validation_evidence_persistence.py/
test_gmpai_artifacts.py -- cero llamadas reales, todo sobre tmp_path."""
from __future__ import annotations

import json
import stat

import pytest

from factory.core import path_policy
from factory.regulatory import tier1_report as t1
from factory.regulatory import tier1_report_writer as writer
from factory.services import tier1_report_service as svc

VALID_RUN_ID = "chunked-abcdef012345"


def _sample_report(run_id: str = VALID_RUN_ID) -> t1.Tier1Report:
    return t1.Tier1Report(
        document_id="RW-0005", agent_id="fda_part11_agent", run_id=run_id,
        generated_at="2026-08-11T00:00:00+00:00",
        requirements=[
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(d)", bucket=t1.CONFIRMED,
                                   conclusion="PROVISIONALLY_DOCUMENTED",
                                   review_flags=["SOURCE_PENDING_REVERIFICATION"],
                                   evidence_quote="cita real anclada", page_or_section="p.3"),
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(e)", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="PROVISIONAL_GAP",
                                   review_queue_rc_id=f"finding-{run_id}-21_CFR_11.10(e)"),
        ],
    )


# ── path_policy.resolve_tier1_report ─────────────────────────────────────

def test_resolve_tier1_report_accepts_valid_run_id(tmp_path):
    target = path_policy.resolve_tier1_report(VALID_RUN_ID, ".json", tmp_path)
    assert target == (tmp_path / f"{VALID_RUN_ID}.json").resolve()


@pytest.mark.parametrize("bad_run_id", [
    "../../../etc/passwd",
    "chunked-",
    "chunked-ZZZZZZZZZZZZ",
    "w5v3-validation-abcdef012345",  # prefijo de otro árbol, no válido aquí
    "chunked-abcdef0123456789",  # demasiado largo
    "",
])
def test_resolve_tier1_report_rejects_invalid_run_id(tmp_path, bad_run_id):
    with pytest.raises(ValueError):
        path_policy.resolve_tier1_report(bad_run_id, ".json", tmp_path)


def test_resolve_tier1_report_rejects_disallowed_extension(tmp_path):
    with pytest.raises(PermissionError):
        path_policy.resolve_tier1_report(VALID_RUN_ID, ".pdf", tmp_path)


def test_resolve_tier1_report_confines_under_base(tmp_path):
    target = path_policy.resolve_tier1_report(VALID_RUN_ID, ".md", tmp_path)
    assert target.is_relative_to(tmp_path.resolve())


# ── tier1_report_writer.persist_tier1_report ─────────────────────────────

def test_persist_writes_markdown_and_json_with_matching_hashes(tmp_path):
    report = _sample_report()
    manifest = writer.persist_tier1_report(report, reports_base=tmp_path)

    md_path = tmp_path / f"{VALID_RUN_ID}.md"
    json_path = tmp_path / f"{VALID_RUN_ID}.json"
    assert md_path.exists() and json_path.exists()
    assert manifest["markdown_path"] == str(md_path)
    assert manifest["json_path"] == str(json_path)
    assert manifest["run_id"] == VALID_RUN_ID
    assert manifest["counts_by_bucket"] == report.counts_by_bucket()

    import hashlib
    assert hashlib.sha256(md_path.read_bytes()).hexdigest() == manifest["markdown_sha256"]
    assert hashlib.sha256(json_path.read_bytes()).hexdigest() == manifest["json_sha256"]

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["document_id"] == "RW-0005"
    assert len(data["requirements"]) == 2
    assert "cita real anclada" in md_path.read_text(encoding="utf-8")


def test_persist_sets_file_permissions_0640(tmp_path):
    import os

    report = _sample_report()
    manifest = writer.persist_tier1_report(report, reports_base=tmp_path)
    for key in ("markdown_path", "json_path"):
        mode = stat.S_IMODE(os.stat(manifest[key]).st_mode)
        assert mode == 0o640


def test_persist_never_leaves_partial_tmp_files(tmp_path):
    report = _sample_report()
    writer.persist_tier1_report(report, reports_base=tmp_path)
    assert list(tmp_path.glob("*.tmp")) == []


def test_persist_rejects_oversized_content(tmp_path, monkeypatch):
    huge_report = _sample_report()
    huge_report.requirements[0].review_flags = ["x" * (writer.TIER1_REPORT_MAX_BYTES + 1)]
    with pytest.raises(writer.Tier1ReportTooLargeError):
        writer.persist_tier1_report(huge_report, reports_base=tmp_path)
    # Fail-closed: no debe quedar ningún archivo (ni parcial ni completo).
    assert list(tmp_path.glob(f"{VALID_RUN_ID}*")) == []


# ── tier1_report_service (solo-lectura) ──────────────────────────────────

def test_service_list_reports_empty_base_returns_empty_list(tmp_path):
    assert svc.list_reports(reports_base=tmp_path) == []


def test_service_list_and_get_round_trip(tmp_path):
    report = _sample_report()
    writer.persist_tier1_report(report, reports_base=tmp_path)

    reports = svc.list_reports(reports_base=tmp_path)
    assert len(reports) == 1
    assert reports[0]["run_id"] == VALID_RUN_ID
    assert reports[0]["document_id"] == "RW-0005"
    assert reports[0]["counts_by_bucket"] == report.counts_by_bucket()

    full = svc.get_report_json(VALID_RUN_ID, reports_base=tmp_path)
    assert len(full["requirements"]) == 2

    md = svc.get_report_markdown(VALID_RUN_ID, reports_base=tmp_path)
    assert "cita real anclada" in md
    assert "borrador asistido" in md.lower()


def test_service_get_report_json_raises_not_found_for_missing_run_id(tmp_path):
    with pytest.raises(svc.Tier1ReportNotFound):
        svc.get_report_json("chunked-000000000000", reports_base=tmp_path)


def test_service_get_report_markdown_raises_not_found_for_missing_run_id(tmp_path):
    with pytest.raises(svc.Tier1ReportNotFound):
        svc.get_report_markdown("chunked-000000000000", reports_base=tmp_path)
