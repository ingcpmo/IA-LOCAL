"""
Capa 8 Tier-1 — Diff Manager.

Recolecta, formatea y archiva diffs de cambios en workspaces.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def collect_diff(project_id: str) -> str:
    """
    Retorna el diff completo del workspace (git diff).
    Si el workspace no es un repo git, lista archivos modificados.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return f"Workspace '{project_id}' no encontrado."

    result = subprocess.run(
        ["git", "diff"],
        cwd=str(ws_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return result.stdout or "(sin cambios no staged)"

    # Fallback: listar archivos modificados
    result2 = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(ws_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result2.stdout or "(workspace no es repo git o sin cambios)"


def collect_diff_stat(project_id: str) -> str:
    """Retorna el diff --stat del workspace."""
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return f"Workspace '{project_id}' no encontrado."

    result = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=str(ws_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout or "(sin cambios)"


def archive_diff(project_id: str) -> dict[str, Any]:
    """
    Archiva el diff actual en el workspace bajo logs/diffs/.
    Retorna metadata del archivo creado.
    """
    ws_path = WORKSPACES_BASE / project_id
    if not ws_path.exists():
        return {"error": f"Workspace '{project_id}' no encontrado."}

    diff_content = collect_diff(project_id)
    diff_dir = ws_path / "logs" / "diffs"
    diff_dir.mkdir(parents=True, exist_ok=True)

    ts = _ts()
    diff_file = diff_dir / f"diff_{ts}.txt"
    diff_file.write_text(diff_content, encoding="utf-8")

    return {
        "project_id": project_id,
        "diff_file": str(diff_file),
        "size_bytes": diff_file.stat().st_size,
        "timestamp": ts,
    }
