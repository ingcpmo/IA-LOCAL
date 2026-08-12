"""R3-T1.2/F0.3 (2026-08-12): `human_review_queue.supersede_finding()` --
marca una entrada como SUPERSEDED por un defecto tecnico confirmado (nunca
un juicio humano), sin pasar por `mark_reviewed()`/`identity_policy` y sin
borrar el registro original. review_queue.jsonl SIEMPRE aislado
(conftest.py::isolated_review_queue, autouse)."""
from __future__ import annotations

import pytest

from factory.layer9 import human_review_queue as hrq


def _enqueue_sample(req_id="21_CFR_11.10(d)", run_id="chunked-test"):
    return hrq.enqueue_finding_for_review(
        run_id=run_id, requirement_id=req_id, document_id="RW-TEST",
        page=12, evidence_quote="cita real", conclusion="PROVISIONAL_GAP",
        review_flags=["ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE"], agent_id="fda_part11_agent",
    )


def test_supersede_finding_marks_status_without_deleting(isolated_review_queue):
    entry = _enqueue_sample()
    rc_id = entry["rc_id"]

    result = hrq.supersede_finding(rc_id, "SUPERSEDED_BY_PROFILE_CORRECTION -- default equivocado")

    assert result["status"] == "superseded"
    entries = hrq._read_all()
    stored = next(e for e in entries if e["rc_id"] == rc_id)
    assert stored["status"] == "superseded"
    assert stored["superseded_reason"] == "SUPERSEDED_BY_PROFILE_CORRECTION -- default equivocado"
    assert "superseded_at" in stored
    # el registro original nunca se borra -- summary/evidencia intactos
    assert stored["summary"]["evidence_quote"] == "cita real"


def test_supersede_finding_records_superseded_by(isolated_review_queue):
    entry = _enqueue_sample()
    hrq.supersede_finding(entry["rc_id"], "reason", superseded_by="chunked-nuevo-run")
    stored = next(e for e in hrq._read_all() if e["rc_id"] == entry["rc_id"])
    assert stored["superseded_by"] == "chunked-nuevo-run"


def test_supersede_finding_never_requires_reviewer_identity(isolated_review_queue):
    """A diferencia de mark_reviewed(), esto es una correccion de proceso,
    no un juicio humano -- nunca debe exigir/validar una identidad."""
    entry = _enqueue_sample()
    # Ninguna identidad reservada bloquea esto -- ni siquiera se pide una.
    result = hrq.supersede_finding(entry["rc_id"], "reason")
    assert "reviewer" not in result


def test_supersede_finding_unknown_rc_id_raises(isolated_review_queue):
    with pytest.raises(FileNotFoundError):
        hrq.supersede_finding("rc-no-existe", "reason")


def test_queue_summary_counts_superseded(isolated_review_queue):
    entry = _enqueue_sample()
    hrq.supersede_finding(entry["rc_id"], "reason")
    summary = hrq.get_queue_summary()
    assert summary["superseded"] == 1
    assert summary["pending"] == 0
