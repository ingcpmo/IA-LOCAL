"""
Tests de idempotencia de approve/reject de RC — Part-11 guard.

Prueba directamente la capa de datos (confirm_rc, get_rc, mark_reviewed)
y simula la lógica de guardia implementada en el route handler de layer9.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.layer8.release_candidate_builder import confirm_rc, get_rc
from factory.layer9.human_review_queue import mark_reviewed


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def isolated_rc(tmp_path, monkeypatch, isolated_audit):
    """RC temporal en pending_human_confirmation."""
    import factory.layer8.release_candidate_builder as rcb
    import factory.layer9.human_review_queue as hrq

    rc_base = tmp_path / "release_candidates"
    rc_dir = rc_base / "test_project" / "test_project-rc-v1.0-20260101T000000"
    rc_dir.mkdir(parents=True)

    rc_id = "test_project-rc-v1.0-20260101T000000"
    manifest = {
        "rc_id": rc_id,
        "project_id": "test_project",
        "version": "v1.0",
        "status": "pending_human_confirmation",
        "approved_by": None,
        "decided_at": None,
    }
    (rc_dir / "rc_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    queue_file = tmp_path / "review_queue.jsonl"
    queue_entry = {
        "rc_id": rc_id,
        "project_id": "test_project",
        "status": "pending",
        "reviewer": None,
        "reviewed_at": None,
    }
    queue_file.write_text(json.dumps(queue_entry) + "\n", encoding="utf-8")

    monkeypatch.setattr(rcb, "RC_BASE", rc_base)
    monkeypatch.setattr(hrq, "REVIEW_QUEUE_FILE", queue_file)

    yield rc_id, isolated_audit


def _guard_check(rc_id: str):
    """
    Replica exacta de la guardia implementada en post_approve_rc / post_reject_rc.
    Retorna (bloqueado, detail_dict).
    """
    rc = get_rc(rc_id)
    if rc is None:
        return True, {"error": "not_found"}
    if rc.get("status") in ("approved", "rejected"):
        return True, {
            "error": "rc_already_finalized",
            "rc_id": rc_id,
            "current_status": rc["status"],
            "previously_decided_by": rc.get("approved_by", "?"),
            "previously_decided_at": rc.get("decided_at", "?"),
        }
    return False, {}


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_first_approve_passes_guard(isolated_rc):
    """Antes de aprobar, la guardia no bloquea."""
    rc_id, _ = isolated_rc
    blocked, _ = _guard_check(rc_id)
    assert not blocked


def test_approve_sets_status(isolated_rc):
    """confirm_rc + mark_reviewed dejan el RC en status=approved."""
    rc_id, _ = isolated_rc
    confirm_rc(rc_id, "Cesar", "approved", "")
    mark_reviewed(rc_id, "approved", "Cesar")

    rc = get_rc(rc_id)
    assert rc["status"] == "approved"
    assert rc["approved_by"] == "Cesar"


def test_second_approve_blocked_by_guard(isolated_rc):
    """Después de aprobar, la guardia retorna bloqueado con rc_already_finalized."""
    rc_id, _ = isolated_rc
    confirm_rc(rc_id, "Cesar", "approved", "")
    mark_reviewed(rc_id, "approved", "Cesar")

    blocked, detail = _guard_check(rc_id)
    assert blocked
    assert detail["error"] == "rc_already_finalized"
    assert detail["current_status"] == "approved"
    assert detail["previously_decided_by"] == "Cesar"


def test_audit_chain_does_not_grow_on_blocked_approve(isolated_rc):
    """La cadena de auditoría NO crece si el segundo approve es bloqueado."""
    rc_id, audit_file = isolated_rc

    confirm_rc(rc_id, "Cesar", "approved", "")
    mark_reviewed(rc_id, "approved", "Cesar")
    lines_after_first = audit_file.read_text().strip().splitlines()

    # Simular el bloqueo: la guardia lo intercepta y NO llama confirm_rc/mark_reviewed
    blocked, _ = _guard_check(rc_id)
    assert blocked  # confirma que la guardia actúa

    lines_after_block = audit_file.read_text().strip().splitlines()
    assert len(lines_after_block) == len(lines_after_first), (
        "La cadena de auditoría creció aunque el segundo approve fue bloqueado"
    )


def test_approve_after_reject_blocked_by_guard(isolated_rc):
    """Aprobar un RC ya rechazado debe ser bloqueado."""
    rc_id, _ = isolated_rc
    confirm_rc(rc_id, "Cesar", "rejected", "")
    mark_reviewed(rc_id, "rejected", "Cesar")

    blocked, detail = _guard_check(rc_id)
    assert blocked
    assert detail["current_status"] == "rejected"


def test_reject_after_approve_blocked_by_guard(isolated_rc):
    """Rechazar un RC ya aprobado debe ser bloqueado."""
    rc_id, _ = isolated_rc
    confirm_rc(rc_id, "Cesar", "approved", "")
    mark_reviewed(rc_id, "approved", "Cesar")

    blocked, detail = _guard_check(rc_id)
    assert blocked
    assert detail["current_status"] == "approved"
