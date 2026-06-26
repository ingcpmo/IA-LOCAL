"""
Capa 8 — Host Worker.

Ejecuta jobs headless en el HOST (no en el contenedor factory-api).
El CLI de claude está en /home/ing_cpmo/.local/bin/claude, no en el contenedor.

Flujo: pending/ → running/ → completed/ | failed/
Reset automático de headless_enabled tras cada job.
NUNCA usa --dangerously-skip-permissions.
NUNCA guarda credenciales.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.job_queue import create_job, fail_job, complete_job, list_jobs, move_job
from factory.layer8.claude_runtime import validate_workspace, validate_task_safety

RUNTIME_CONFIG = Path(__file__).parent.parent / "runtime" / "runtime_config.yaml"
WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"


def is_headless_enabled() -> bool:
    if not RUNTIME_CONFIG.exists():
        return False
    try:
        cfg = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {}
        return bool(cfg.get("headless_enabled", False))
    except Exception:
        return False


def reset_headless_after_job(project_id: str) -> None:
    try:
        cfg = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
        cfg["headless_enabled"] = False
        RUNTIME_CONFIG.write_text(yaml.dump(cfg, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        write_event("layer8_stop_condition_triggered", project_id, {
            "reason": "headless_reset_after_job",
            "source": "host_worker",
        })
    except Exception:
        pass


def _pick_oldest_pending() -> dict | None:
    jobs = list_jobs(queue="pending")
    headless_jobs = [j for j in jobs if j.get("job_type") == "headless_run"]
    if not headless_jobs:
        return None
    return min(headless_jobs, key=lambda j: j.get("created_at", ""))


def poll_and_execute(once: bool = True) -> dict:
    """
    Busca el job headless_run más antiguo en pending/ y lo ejecuta.
    Si once=True corre una sola vez; si False, hace polling continuo.
    """
    if not is_headless_enabled():
        return {"status": "disabled", "reason": "headless_enabled=false en runtime_config.yaml"}

    job = _pick_oldest_pending()
    if job is None:
        return {"status": "no_jobs"}

    job_id = job["job_id"]
    project_id = job["project_id"]

    ws_validation = validate_workspace(project_id)
    if not ws_validation["valid"]:
        fail_job(job_id, f"workspace_invalid: {ws_validation.get('missing', [])}")
        reset_headless_after_job(project_id)
        return {"status": "error", "job_id": job_id, "reason": "workspace_invalid",
                "missing": ws_validation.get("missing", [])}

    safety = validate_task_safety(project_id)
    if not safety["safe"]:
        fail_job(job_id, f"task_safety_violated: {safety['violations']}")
        reset_headless_after_job(project_id)
        return {"status": "error", "job_id": job_id, "reason": "task_safety_violated",
                "violations": safety["violations"]}

    claude_path = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    if not Path(claude_path).exists():
        fail_job(job_id, "claude_cli_not_found")
        reset_headless_after_job(project_id)
        return {"status": "error", "job_id": job_id, "reason": "claude CLI no encontrado"}

    move_job(job_id, "running")

    ws_path = WORKSPACES_BASE / project_id
    task_content = (ws_path / "task.md").read_text(encoding="utf-8")
    log_dir = ws_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"headless_{int(time.time())}.log"

    cfg_pre = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
    write_event("layer8_claude_execution_started", project_id, {
        "mode": "headless_host_worker",
        "job_id": job_id,
        "claude_path": claude_path,
        "log_file": str(log_file),
        "claude_model": cfg_pre.get("claude_model", "claude-sonnet-4-6"),
    })

    try:
        cfg = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8")) or {} if RUNTIME_CONFIG.exists() else {}
        timeout = cfg.get("headless_timeout_seconds", 1800)
        model = cfg.get("claude_model", "claude-sonnet-4-6")

        proc = subprocess.run(
            [claude_path, "-p", task_content,
             "--model", model,
             "--output-format", "json",
             "--no-session-persistence",
             "--permission-mode", "auto"],
            cwd=str(ws_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        log_content = proc.stdout
        if proc.stderr:
            log_content += f"\n\n=== STDERR ===\n{proc.stderr}"
        log_file.write_text(log_content, encoding="utf-8")

        write_event("layer8_claude_execution_completed", project_id, {
            "job_id": job_id,
            "returncode": proc.returncode,
            "log_file": str(log_file),
        })

        complete_job(job_id, {
            "returncode": proc.returncode,
            "log_file": str(log_file),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        reset_headless_after_job(project_id)
        return {
            "status": "completed",
            "job_id": job_id,
            "returncode": proc.returncode,
            "log_file": str(log_file),
        }

    except subprocess.TimeoutExpired:
        write_event("layer8_claude_execution_failed", project_id, {
            "job_id": job_id, "reason": "timeout"})
        fail_job(job_id, "timeout")
        reset_headless_after_job(project_id)
        return {"status": "timeout", "job_id": job_id}

    except Exception as exc:
        write_event("layer8_claude_execution_failed", project_id, {
            "job_id": job_id, "reason": str(exc)})
        fail_job(job_id, str(exc))
        reset_headless_after_job(project_id)
        return {"status": "error", "job_id": job_id, "reason": str(exc)}
