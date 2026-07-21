"""
Tests -- factory/regulatory/broken_link_report.py (Fase 1,
document_remediation_evolution).

Garantías fijadas:
  - menos de N verificaciones registradas -> INSUFFICIENT_HISTORY (nunca se
    afirma nada sobre una fuente sin historial suficiente)
  - las últimas N verificaciones todas reachable=False -> REGULATORY_SOURCE_UNVERIFIED
  - una sola verificación reachable=True dentro de las últimas N -> OK
    (no basta un fallo aislado)
  - content_matches_governed_copy nunca decide el status (solo reachable)
  - build_report(): 1 entrada en el log append-only por fuente, exactamente
    1 evento de auditoría agregado
  - run_by reservado -> HTTPException 422 (mismo validador que los demás)
  - este módulo NUNCA escribe en registry.json ni en source_currency_log.jsonl
"""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from factory.regulatory import broken_link_report as report
from factory.services import paths as svc_paths


def _entry(source_id, checked_at, reachable, content_matches=None):
    return {
        "source_id": source_id,
        "checked_at": checked_at,
        "reachable": reachable,
        "content_matches_governed_copy": content_matches,
    }


@pytest.fixture()
def report_env(tmp_path, monkeypatch, isolated_audit):
    monkeypatch.setattr(svc_paths, "BROKEN_LINK_REPORT_FILE", tmp_path / "broken_link_report.jsonl")
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", tmp_path / "source_currency_log.jsonl")
    yield tmp_path


def test_insufficient_history_below_threshold():
    history = [_entry("s1", "2026-07-01T00:00:00Z", False)]
    result = report.evaluate_source("s1", history, min_consecutive_failures=3)
    assert result["status"] == report.STATUS_INSUFFICIENT_HISTORY


def test_all_failures_flags_unverified():
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", False),
        _entry("s1", "2026-07-02T00:00:00Z", False),
        _entry("s1", "2026-07-03T00:00:00Z", False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_failures=3)
    assert result["status"] == report.STATUS_UNVERIFIED
    assert result["checks_considered"] == 3
    assert result["last_checked_at"] == "2026-07-03T00:00:00Z"


def test_single_success_within_window_is_ok():
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", False),
        _entry("s1", "2026-07-02T00:00:00Z", True, content_matches=False),
        _entry("s1", "2026-07-03T00:00:00Z", False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_failures=3)
    assert result["status"] == report.STATUS_OK


def test_content_mismatch_never_flags_unverified():
    """reachable=True con hash no coincidente no es un enlace roto."""
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", True, content_matches=False),
        _entry("s1", "2026-07-02T00:00:00Z", True, content_matches=False),
        _entry("s1", "2026-07-03T00:00:00Z", True, content_matches=False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_failures=3)
    assert result["status"] == report.STATUS_OK


def test_only_last_n_considered_older_failures_ignored():
    history = [
        _entry("s1", "2026-06-01T00:00:00Z", False),
        _entry("s1", "2026-06-02T00:00:00Z", False),
        _entry("s1", "2026-07-01T00:00:00Z", True),
        _entry("s1", "2026-07-02T00:00:00Z", True),
        _entry("s1", "2026-07-03T00:00:00Z", True),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_failures=3)
    assert result["status"] == report.STATUS_OK
    assert result["checks_considered"] == 3


def test_run_by_reserved_name_rejected(report_env):
    with pytest.raises(HTTPException) as exc:
        report.build_report("system", ["s1"])
    assert exc.value.status_code == 422


def test_build_report_logs_and_audits_once(report_env):
    svc_paths.SOURCE_CURRENCY_LOG_FILE.write_text(
        "\n".join(json.dumps(_entry("s1", f"2026-07-0{i}T00:00:00Z", False)) for i in range(1, 4))
        + "\n"
        + "\n".join(json.dumps(_entry("s2", f"2026-07-0{i}T00:00:00Z", True)) for i in range(1, 4))
        + "\n",
        encoding="utf-8",
    )
    results = report.build_report("QA Real", ["s1", "s2"], min_consecutive_failures=3)
    assert len(results) == 2
    by_id = {r["source_id"]: r for r in results}
    assert by_id["s1"]["status"] == report.STATUS_UNVERIFIED
    assert by_id["s2"]["status"] == report.STATUS_OK

    report_lines = svc_paths.BROKEN_LINK_REPORT_FILE.read_text(encoding="utf-8").splitlines()
    assert len(report_lines) == 2
    logged = [json.loads(l) for l in report_lines]
    assert all(e["run_by"] == "QA Real" for e in logged)

    from factory.core import audit_writer as aw
    aw_lines = aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in aw_lines]
    report_events = [e for e in events if e.get("event_type") == "regulatory_broken_link_report_generated"]
    assert len(report_events) == 1
    assert report_events[0]["data"]["sources_evaluated"] == 2
    assert report_events[0]["data"]["flagged_unverified"] == 1


def test_never_writes_registry_json_or_currency_log():
    src = Path("/home/ing_cpmo/factory/regulatory/broken_link_report.py").read_text(encoding="utf-8")
    assert ".write_text(" not in src
    assert 'open(paths.BROKEN_LINK_REPORT_FILE, "a"' in src
