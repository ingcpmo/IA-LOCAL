"""
Capa 8 — Gate Execution Manager.

Ejecuta quality gates para misiones con o sin deployment Docker.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.core.quality_gate_runner import (
    g01_compose_syntax,
    g11_key_not_in_frontend,
    g12_git_clean,
    run_deployment_gates,
)

WORKSPACES_BASE = Path(__file__).parent.parent / "workspaces"


def run_gates_for_mission(
    project_id: str,
    api_port: int,
    api_key: str,
    fast: bool = True,
) -> dict:
    """
    Ejecuta el conjunto completo de gates funcionales contra un deployment Docker activo.
    """
    ws_path = WORKSPACES_BASE / project_id
    manifest_path = ws_path / "manifest.yaml"

    manifest: dict = {}
    if manifest_path.exists():
        import yaml
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    report = run_deployment_gates(
        project_id=project_id,
        api_port=api_port,
        api_key=api_key,
        manifest=manifest,
        report_path=ws_path / "quality_gates_report.json",
        fast=fast,
    )

    summary = report.get("summary", {})
    all_pass = summary.get("FAIL", 1) == 0 and summary.get("PASS", 0) > 0

    if not all_pass:
        write_event("layer8_stop_condition_triggered", project_id, {
            "event": "gate_fail",
            "summary": summary,
            "report_hash": report.get("report_hash"),
        })

    return {
        "all_pass": all_pass,
        "summary": summary,
        "gates": report.get("gates", []),
        "report_hash": report.get("report_hash"),
    }


def run_static_gates(project_id: str) -> dict:
    """
    Gates estáticos para misiones sin deployment Docker:
    G01 (compose syntax), G11 (key no en UI), G12 (git clean).
    """
    ws_path = WORKSPACES_BASE / project_id
    compose_path = ws_path / "docker-compose.yml"
    api_key_path = ws_path / ".env"

    api_key = ""
    if api_key_path.exists():
        for line in api_key_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GMP_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"')
                break

    results = []

    if compose_path.exists():
        results.append(g01_compose_syntax(str(compose_path)))
    else:
        results.append({
            "gate": "G01_COMPOSE_SYNTAX",
            "status": "SKIPPED",
            "evidence": "docker-compose.yml no encontrado en workspace",
        })

    results.append(g11_key_not_in_frontend(str(ws_path), api_key))
    results.append(g12_git_clean(str(ws_path)))

    summary = {
        "PASS":    sum(1 for r in results if r["status"] == "PASS"),
        "FAIL":    sum(1 for r in results if r["status"] == "FAIL"),
        "SKIPPED": sum(1 for r in results if r["status"] == "SKIPPED"),
    }
    all_pass = summary["FAIL"] == 0

    ts = datetime.now(timezone.utc).isoformat()
    report = {
        "project_id": project_id,
        "generated_at": ts,
        "gate_set": "static",
        "summary": summary,
        "gates": results,
    }
    report_hash = f"sha256:{hashlib.sha256(json.dumps(report, separators=(',',':')).encode()).hexdigest()}"
    report["report_hash"] = report_hash

    write_event("gates_executed", project_id, {
        "gate_set": "static",
        "summary": summary,
        "report_hash": report_hash,
    })

    return {"all_pass": all_pass, "gates": results, "summary": summary}
