"""
Capa 8 Tier-2 — Claude Account Status.

Verifica la disponibilidad del CLI de Claude sin guardar credenciales, tokens ni contraseñas.
Campos guardados: cli_found, cli_path, version, linux_user, auth_status, mode, checked_at.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

RUNTIME_DIR = Path(__file__).parent.parent / "runtime"
STATUS_FILE = RUNTIME_DIR / "claude_status.json"

SAFE_FIELDS = {"cli_found", "cli_path", "version", "linux_user", "auth_status", "mode", "checked_at"}


def check_claude_cli() -> dict:
    """
    Verifica si el CLI de Claude está disponible.
    No guarda credenciales, tokens ni contraseñas.
    Retorna solo campos seguros.
    """
    cli_path = shutil.which("claude")
    cli_found = cli_path is not None
    version = "unknown"

    if cli_found:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            v_raw = (result.stdout or result.stderr or "").strip()
            version = v_raw.split("\n")[0][:80] if v_raw else "unknown"
        except Exception:
            version = "unknown"

    return {
        "cli_found": cli_found,
        "cli_path": cli_path or "",
        "version": version,
        "linux_user": os.environ.get("USER", os.environ.get("LOGNAME", "unknown")),
        "auth_status": "unknown",
        "mode": "manual_assisted",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def write_status(project_id: str = "factory") -> dict:
    """
    Escribe factory/runtime/claude_status.json con solo campos seguros.
    Nunca persiste credenciales, tokens ni contraseñas.
    """
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    status = check_claude_cli()

    safe_status = {k: v for k, v in status.items() if k in SAFE_FIELDS}
    STATUS_FILE.write_text(json.dumps(safe_status, indent=2, ensure_ascii=False), encoding="utf-8")

    write_event("layer8_claude_status_checked", project_id, {
        "cli_found": safe_status["cli_found"],
        "mode": safe_status["mode"],
        "status_file": str(STATUS_FILE),
    })

    return safe_status
