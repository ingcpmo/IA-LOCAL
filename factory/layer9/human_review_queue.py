"""
Capa 9 — Human Review Queue.

Cola de RCs pendientes de revisión humana.
Persiste en factory/layer9/review_queue.jsonl (append-only).
"""

from __future__ import annotations

import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

REVIEW_QUEUE_FILE = Path(__file__).parent / "review_queue.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_all() -> list[dict]:
    if not REVIEW_QUEUE_FILE.exists():
        return []
    entries = []
    for line in REVIEW_QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _rewrite(entries: list[dict]) -> None:
    REVIEW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_FILE.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def enqueue(rc_id: str, project_id: str, summary: dict) -> dict:
    """Añade un RC a la cola de revisión humana."""
    entry = {
        "rc_id": rc_id,
        "project_id": project_id,
        "enqueued_at": _ts(),
        "status": "pending",
        "summary": summary,
    }
    REVIEW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = REVIEW_QUEUE_FILE.with_suffix(".lock")
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(REVIEW_QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    write_event("rc_enqueued", project_id, {
        "rc_id": rc_id,
        "summary": summary,
    })
    return entry


def list_pending() -> list[dict]:
    """Retorna los RCs con status='pending'."""
    return [e for e in _read_all() if e.get("status") == "pending"]


def get_queue_summary() -> dict:
    """Conteo por estado."""
    entries = _read_all()
    summary: dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0, "returned": 0}
    for e in entries:
        st = e.get("status", "pending")
        if st in summary:
            summary[st] += 1
    return summary


def mark_reviewed(rc_id: str, decision: str, reviewer: str) -> dict:
    """Actualiza el estado de un RC en la cola."""
    entries = _read_all()
    updated = False
    for e in entries:
        if e.get("rc_id") == rc_id:
            e["status"] = decision
            e["reviewer"] = reviewer
            e["reviewed_at"] = _ts()
            updated = True
            project_id = e.get("project_id", "unknown")
            break

    if not updated:
        raise FileNotFoundError(f"RC '{rc_id}' no encontrado en la cola")

    _rewrite(entries)

    write_event("rc_reviewed", project_id, {
        "rc_id": rc_id,
        "decision": decision,
        "reviewer": reviewer,
    })
    return {"rc_id": rc_id, "decision": decision, "reviewer": reviewer}
