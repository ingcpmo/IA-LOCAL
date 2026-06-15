"""
Capa 8 — Artifact Collector.

Empaqueta artefactos del workspace en factory/release_candidates/<project_id>/<rc_id>/artifacts/.
Los artefactos obligatorios son: test_report.json y al menos un log headless.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"
RC_BASE = Path(__file__).parent.parent / "release_candidates"

_OPTIONAL_FILES = [
    "manifest.yaml",
    "test_report.json",
    "quality_gates_report.json",
]
_REQUIRED = ["test_report.json"]


def collect(project_id: str, rc_id: str) -> dict:
    """
    Recopila artefactos del workspace para el RC. Retorna {ok, artifacts_path, artifact_list}.
    """
    ws_path = WORKSPACES_BASE / project_id
    artifacts_dir = RC_BASE / project_id / rc_id / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    collected: list[str] = []
    missing_required: list[str] = []

    # Copiar archivos opcionales conocidos
    for fname in _OPTIONAL_FILES:
        src = ws_path / fname
        if src.exists():
            shutil.copy2(src, artifacts_dir / fname)
            collected.append(fname)

    # Log headless más reciente (buscar en workspace/ y workspace/logs/)
    log_dirs = [ws_path, ws_path / "logs"]
    headless_log = None
    for log_dir in log_dirs:
        if log_dir.exists():
            logs = sorted(log_dir.glob("headless_*.log"), reverse=True)
            if logs:
                headless_log = logs[0]
                break

    if headless_log:
        dest_name = f"headless_{headless_log.stem}.log"
        shutil.copy2(headless_log, artifacts_dir / dest_name)
        collected.append(dest_name)

    # Generar diff.txt
    diff_txt = artifacts_dir / "diff.txt"
    try:
        result = subprocess.run(
            ["git", "diff", "--", str(ws_path)],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff_content = result.stdout or "(sin cambios en git diff)"
        diff_txt.write_text(diff_content, encoding="utf-8")
        collected.append("diff.txt")
    except Exception as exc:
        diff_txt.write_text(f"(error generando diff: {exc})", encoding="utf-8")
        collected.append("diff.txt")

    # Verificar obligatorios
    for req in _REQUIRED:
        if req not in collected:
            missing_required.append(req)
    if headless_log is None:
        missing_required.append("headless_*.log (ningún log encontrado)")

    if missing_required:
        write_event("artifacts_collected", project_id, {
            "rc_id": rc_id,
            "ok": False,
            "missing": missing_required,
        })
        return {
            "ok": False,
            "missing": missing_required,
            "artifacts_path": str(artifacts_dir),
            "artifact_list": collected,
        }

    write_event("artifacts_collected", project_id, {
        "rc_id": rc_id,
        "ok": True,
        "artifacts_path": str(artifacts_dir),
        "artifact_list": collected,
    })

    return {
        "ok": True,
        "artifacts_path": str(artifacts_dir),
        "artifact_list": collected,
    }
