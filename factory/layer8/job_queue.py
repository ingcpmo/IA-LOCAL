"""
Capa 8 Tier-1 — Job Queue.

Cola de jobs basada en archivos JSON en factory/jobs/{pending,running,completed,failed}/.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

JOBS_BASE = Path(__file__).parent.parent / "jobs"
VALID_QUEUES = ("pending", "running", "completed", "failed")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _queue_path(queue: str) -> Path:
    if queue not in VALID_QUEUES:
        raise ValueError(f"Cola inválida: {queue}. Válidas: {VALID_QUEUES}")
    path = JOBS_BASE / queue
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_file(queue: str, job_id: str) -> Path:
    return _queue_path(queue) / f"{job_id}.json"


def _find_job(job_id: str) -> tuple[str, Path] | tuple[None, None]:
    """Busca un job en todas las colas. Retorna (queue, path) o (None, None)."""
    for q in VALID_QUEUES:
        p = _job_file(q, job_id)
        if p.exists():
            return q, p
    return None, None


def create_job(project_id: str, job_type: str, payload: dict | None = None) -> dict[str, Any]:
    """Crea un job nuevo en la cola pending."""
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "project_id": project_id,
        "job_type": job_type,
        "status": "pending",
        "payload": payload or {},
        "created_at": _ts(),
        "updated_at": _ts(),
        "result": None,
        "error": None,
    }
    p = _job_file("pending", job_id)
    p.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    """Retorna el job independientemente de la cola donde esté."""
    queue, path = _find_job(job_id)
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs(queue: str | None = None, project_id: str | None = None) -> list[dict[str, Any]]:
    """Lista jobs, opcionalmente filtrados por cola y/o project_id."""
    queues = [queue] if queue else list(VALID_QUEUES)
    result = []
    for q in queues:
        q_path = _queue_path(q)
        for f in sorted(q_path.glob("*.json")):
            if f.name == ".gitkeep":
                continue
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
                if project_id is None or job.get("project_id") == project_id:
                    result.append(job)
            except Exception:
                continue
    return result


def move_job(job_id: str, target_queue: str) -> dict[str, Any]:
    """Mueve un job de su cola actual a target_queue."""
    if target_queue not in VALID_QUEUES:
        raise ValueError(f"Cola destino inválida: {target_queue}")

    queue, src_path = _find_job(job_id)
    if src_path is None:
        raise FileNotFoundError(f"Job '{job_id}' no encontrado en ninguna cola.")

    job = json.loads(src_path.read_text(encoding="utf-8"))
    job["status"] = target_queue
    job["updated_at"] = _ts()

    dst_path = _job_file(target_queue, job_id)
    dst_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    src_path.unlink()
    return job


def fail_job(job_id: str, error: str) -> dict[str, Any]:
    """Marca un job como fallido con mensaje de error."""
    queue, src_path = _find_job(job_id)
    if src_path is None:
        raise FileNotFoundError(f"Job '{job_id}' no encontrado.")

    job = json.loads(src_path.read_text(encoding="utf-8"))
    job["status"] = "failed"
    job["error"] = error
    job["updated_at"] = _ts()

    dst_path = _job_file("failed", job_id)
    dst_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    src_path.unlink()
    return job


def complete_job(job_id: str, result: dict | None = None) -> dict[str, Any]:
    """Marca un job como completado con resultado opcional."""
    queue, src_path = _find_job(job_id)
    if src_path is None:
        raise FileNotFoundError(f"Job '{job_id}' no encontrado.")

    job = json.loads(src_path.read_text(encoding="utf-8"))
    job["status"] = "completed"
    job["result"] = result or {}
    job["updated_at"] = _ts()

    dst_path = _job_file("completed", job_id)
    dst_path.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    src_path.unlink()
    return job
