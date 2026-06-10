"""Gestión del ciclo de vida de workspaces (factory/workspaces/<project_id>/)."""

import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.core.template_engine import load_manifest, render_templates, render_manifest
from factory.core.port_registry import assign_ports, get_allocated_ports
from factory.claude.claude_bridge import generate_task_package

FACTORY_DIR   = Path(__file__).parent.parent
WORKSPACES_DIR = FACTORY_DIR / "workspaces"
BACKUPS_DIR   = Path(os.getenv("FACTORY_BACKUPS_DIR", str(FACTORY_DIR.parent / "backups" / "factory")))
EXPORT_SCRIPT = FACTORY_DIR / "core" / "template_export.sh"
REPO_DIR      = FACTORY_DIR.parent


def _manifest_defaults(project_id: str, base_tag: str, ports: dict,
                        name: str = "", description: str = "", requirement: str = "") -> dict:
    commit = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-list", "-n", "1", base_tag],
        capture_output=True, text=True
    ).stdout.strip()
    factory_commit = subprocess.run(
        ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    ).stdout.strip()
    return {
        "manifest_version": "1.0",
        "project": {
            "id": project_id,
            "name": name or project_id,
            "description": description or requirement,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "source": {
            "base_product_tag": base_tag,
            "base_product_commit": commit,
            "factory_commit": factory_commit,
            "generated_by": "factory_layer_8_claude_code_agent",
            "generation_mode": "manual_assisted",
        },
        "deployment": {
            "docker_project_name": project_id,
            "api_port": ports["api"],
            "postgres_port": ports["postgres"],
            "redis_port": ports["redis"],
            "use_shared_ollama": True,
            "ollama_url": "http://host.docker.internal:11434",
            "ollama_model": os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M"),
            "resource_limits_applied": True,
        },
        "agents": {"inherited": [], "profiles": {}, "custom": {}},
        "rag_collections": {},
        "security": {
            "api_key_in_env_only": True,
            "api_key_not_in_frontend": True,
            "env_gitignored": True,
        },
        "status": "draft",
    }


def create_workspace(project_id: str, base_tag: str = "base-v1.0.0",
                     name: str = "", description: str = "", requirement: str = "") -> dict:
    ws_path = WORKSPACES_DIR / project_id
    if ws_path.exists():
        raise ValueError(f"Workspace '{project_id}' ya existe")

    ports = assign_ports(project_id)
    ws_path.mkdir(parents=True)

    result = subprocess.run(
        ["bash", str(EXPORT_SCRIPT), base_tag, str(ws_path)],
        capture_output=True, text=True, cwd=str(REPO_DIR)
    )
    if result.returncode != 0:
        ws_path.rmdir()
        raise RuntimeError(f"template_export falló: {result.stderr}")

    manifest = _manifest_defaults(project_id, base_tag, ports, name, description, requirement)
    render_templates(manifest, ws_path)
    render_manifest(manifest, ws_path)
    generate_task_package(project_id, manifest, ws_path, requirement)

    write_event("workspace_created", project_id, {
        "workspace": str(ws_path),
        "base_tag": base_tag,
        "ports": ports,
    })
    return {"project_id": project_id, "path": str(ws_path), "ports": ports, "status": "created"}


def get_workspace_status(project_id: str) -> dict | None:
    ws_path = WORKSPACES_DIR / project_id
    if not ws_path.exists():
        return None
    manifest_path = ws_path / "manifest.yaml"
    manifest = load_manifest(manifest_path) if manifest_path.exists() else {}
    ports = get_allocated_ports(project_id) or {}
    files = list(ws_path.rglob("*"))
    return {
        "project_id": project_id,
        "path": str(ws_path),
        "ports": ports,
        "files": len([f for f in files if f.is_file()]),
        "manifest_status": manifest.get("status", "unknown"),
        "has_compose": (ws_path / "docker-compose.yml").exists(),
        "has_task_md": (ws_path / "task.md").exists(),
        "has_gates_report": (ws_path / "quality_gates_report.json").exists(),
        "has_approval": (ws_path / "approval.json").exists(),
    }


def list_workspaces() -> list[dict]:
    if not WORKSPACES_DIR.exists():
        return []
    return [s for pid in WORKSPACES_DIR.iterdir()
            if pid.is_dir() and (s := get_workspace_status(pid.name))]


def close_workspace(project_id: str) -> dict:
    ws_path = WORKSPACES_DIR / project_id
    if not ws_path.exists():
        raise ValueError(f"Workspace '{project_id}' no existe")
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"{project_id}_{ts}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(ws_path, arcname=project_id)
    import shutil
    shutil.rmtree(ws_path)
    return {"project_id": project_id, "backup": str(backup_path), "status": "closed"}
