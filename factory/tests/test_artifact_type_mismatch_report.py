"""
Tests -- factory/regulatory/artifact_type_mismatch_report.py (G3,
W5V2_REGULATORY_REDESIGN).

Garantías fijadas:
  - menos de N verificaciones registradas -> INSUFFICIENT_HISTORY (nunca se
    afirma nada sobre una fuente sin historial suficiente)
  - las últimas N verificaciones todas comparable=False -> ARTIFACT_TYPE_MISMATCH
  - una sola verificación comparable=True (o sin la clave -- entradas
    anteriores a G3) dentro de las últimas N -> OK (no basta un caso aislado)
  - reachable nunca decide el status (solo comparable) -- ese es el
    hermano de broken_link_report.py, no una extensión suya
  - build_report(): 1 entrada en el log append-only por fuente, exactamente
    1 evento de auditoría agregado
  - run_by reservado -> HTTPException 422 (mismo validador que los demás)
  - este módulo NUNCA escribe en registry.json ni en source_currency_log.jsonl
"""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from factory.regulatory import artifact_type_mismatch_report as report
from factory.services import paths as svc_paths


def _entry(source_id, checked_at, comparable, reachable=True):
    return {
        "source_id": source_id,
        "checked_at": checked_at,
        "reachable": reachable,
        "comparable": comparable,
    }


@pytest.fixture()
def report_env(tmp_path, monkeypatch, isolated_audit):
    monkeypatch.setattr(svc_paths, "ARTIFACT_TYPE_MISMATCH_REPORT_FILE", tmp_path / "artifact_type_mismatch_report.jsonl")
    monkeypatch.setattr(svc_paths, "SOURCE_CURRENCY_LOG_FILE", tmp_path / "source_currency_log.jsonl")
    yield tmp_path


def test_insufficient_history_below_threshold():
    history = [_entry("s1", "2026-07-01T00:00:00Z", False)]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
    assert result["status"] == report.STATUS_INSUFFICIENT_HISTORY


def test_all_mismatches_flags_artifact_type_mismatch():
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", False),
        _entry("s1", "2026-07-02T00:00:00Z", False),
        _entry("s1", "2026-07-03T00:00:00Z", False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
    assert result["status"] == report.STATUS_ARTIFACT_TYPE_MISMATCH
    assert result["checks_considered"] == 3
    assert result["last_checked_at"] == "2026-07-03T00:00:00Z"


def test_single_match_within_window_is_ok():
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", False),
        _entry("s1", "2026-07-02T00:00:00Z", True),
        _entry("s1", "2026-07-03T00:00:00Z", False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
    assert result["status"] == report.STATUS_OK


def test_pre_g3_entries_without_comparable_key_never_flag_mismatch():
    """Entradas de antes de G3 no tienen la clave `comparable` -- .get()
    las trata como None, nunca como mismatch."""
    history = [
        {"source_id": "s1", "checked_at": "2026-07-01T00:00:00Z", "reachable": True},
        {"source_id": "s1", "checked_at": "2026-07-02T00:00:00Z", "reachable": True},
        _entry("s1", "2026-07-03T00:00:00Z", False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
    assert result["status"] == report.STATUS_OK


def test_reachable_never_decides_status():
    """reachable=False (enlace roto) no es competencia de este módulo."""
    history = [
        _entry("s1", "2026-07-01T00:00:00Z", True, reachable=False),
        _entry("s1", "2026-07-02T00:00:00Z", True, reachable=False),
        _entry("s1", "2026-07-03T00:00:00Z", True, reachable=False),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
    assert result["status"] == report.STATUS_OK


def test_only_last_n_considered_older_mismatches_ignored():
    history = [
        _entry("s1", "2026-06-01T00:00:00Z", False),
        _entry("s1", "2026-06-02T00:00:00Z", False),
        _entry("s1", "2026-07-01T00:00:00Z", True),
        _entry("s1", "2026-07-02T00:00:00Z", True),
        _entry("s1", "2026-07-03T00:00:00Z", True),
    ]
    result = report.evaluate_source("s1", history, min_consecutive_mismatches=3)
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
    results = report.build_report("QA Real", ["s1", "s2"], min_consecutive_mismatches=3)
    assert len(results) == 2
    by_id = {r["source_id"]: r for r in results}
    assert by_id["s1"]["status"] == report.STATUS_ARTIFACT_TYPE_MISMATCH
    assert by_id["s2"]["status"] == report.STATUS_OK

    report_lines = svc_paths.ARTIFACT_TYPE_MISMATCH_REPORT_FILE.read_text(encoding="utf-8").splitlines()
    assert len(report_lines) == 2
    logged = [json.loads(l) for l in report_lines]
    assert all(e["run_by"] == "QA Real" for e in logged)

    from factory.core import audit_writer as aw
    aw_lines = aw.AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    events = [json.loads(l) for l in aw_lines]
    report_events = [e for e in events if e.get("event_type") == "regulatory_artifact_type_mismatch_report_generated"]
    assert len(report_events) == 1
    assert report_events[0]["data"]["sources_evaluated"] == 2
    assert report_events[0]["data"]["flagged_mismatch"] == 1


def test_never_writes_registry_json_or_currency_log():
    src = Path("/home/ing_cpmo/factory/regulatory/artifact_type_mismatch_report.py").read_text(encoding="utf-8")
    assert ".write_text(" not in src
    assert 'open(paths.ARTIFACT_TYPE_MISMATCH_REPORT_FILE, "a"' in src
