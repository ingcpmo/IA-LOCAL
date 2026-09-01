"""
Capa 8 — Test Execution Manager.

Ejecuta la suite de tests de un workspace y produce un reporte estructurado.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"


def run_tests(
    project_id: str,
    cmd: str = "python3 -m pytest tests/ -q --tb=short",
    timeout: int = 120,
) -> dict:
    """
    Ejecuta tests en el workspace y retorna reporte estructurado.
    Guarda workspace/test_report.json.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return {
            "project_id": project_id,
            "all_passed": False,
            "error": f"workspace '{project_id}' no encontrado",
        }

    start = time.monotonic()
    # Portabilidad: un `python`/`python3` literal apunta al python del sistema, que en un
    # host con venv NO tiene pytest ni las deps. Se normaliza al intérprete que corre este
    # manager (bajo el venv del proyecto sí tiene todo).
    parts = cmd.split()
    if parts and parts[0] in ("python", "python3"):
        parts[0] = sys.executable
    try:
        proc = subprocess.run(
            parts,
            cwd=str(ws_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        return {
            "project_id": project_id,
            "all_passed": False,
            "error": f"timeout after {timeout}s",
            "cmd": cmd,
        }
    except Exception as exc:
        return {
            "project_id": project_id,
            "all_passed": False,
            "error": str(exc),
            "cmd": cmd,
        }

    duration = round(time.monotonic() - start, 2)

    passed = _parse_int(r"(\d+) passed", output)
    failed = _parse_int(r"(\d+) failed", output)
    skipped = _parse_int(r"(\d+) skipped", output)
    errors = _parse_int(r"(\d+) error", output)

    all_passed = returncode == 0 and failed == 0 and errors == 0

    report = {
        "project_id": project_id,
        "all_passed": all_passed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "returncode": returncode,
        "output_preview": output[:600],
        "cmd": cmd,
        "duration_seconds": duration,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    report_path = ws_path / "test_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    write_event("tests_executed", project_id, {
        "all_passed": all_passed,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "duration_seconds": duration,
        "cmd": cmd,
    })

    return report


def _parse_int(pattern: str, text: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0
