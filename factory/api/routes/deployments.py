import json
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.core.quality_gate_runner import run_deployment_gates

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])

DEPLOYMENTS_DIR = Path(__file__).parent.parent.parent / "deployments"
REGISTRY_FILE = Path(__file__).parent.parent.parent / "registry" / "ports.yaml"


class IngestPayload(BaseModel):
    collection: str = "gmp_fda_regulations"
    text: str
    source_name: str = "factory_upload"


class GatesPayload(BaseModel):
    fast: bool = True


def _get_deployment_port(project_id: str) -> int | None:
    if not REGISTRY_FILE.exists():
        return None
    data = yaml.safe_load(REGISTRY_FILE.read_text(encoding="utf-8")) or {}
    return data.get("allocations", {}).get(project_id, {}).get("ports", {}).get("api")


def _get_deployment_api_key(project_id: str) -> str | None:
    env_file = DEPLOYMENTS_DIR / project_id / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("GMP_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


@router.get("")
def get_deployments():
    if not DEPLOYMENTS_DIR.exists():
        return []
    result = []
    for d in DEPLOYMENTS_DIR.iterdir():
        if d.is_dir():
            meta = d / "deployment_meta.json"
            result.append(json.loads(meta.read_text()) if meta.exists() else {"project_id": d.name})
    return result


@router.get("/{project_id}")
def get_deployment(project_id: str):
    meta = DEPLOYMENTS_DIR / project_id / "deployment_meta.json"
    if not meta.exists():
        raise HTTPException(404, f"Deployment '{project_id}' no encontrado")
    return json.loads(meta.read_text())


@router.post("/{project_id}/ingest")
def ingest_to_deployment(project_id: str, body: IngestPayload):
    """
    Proxy de ingesta de corpus hacia un deployment custom activo.
    Lee la API key del deployment server-side y la usa para autenticar la petición.
    """
    port = _get_deployment_port(project_id)
    if not port:
        raise HTTPException(404, f"Puerto no encontrado para deployment '{project_id}'")

    api_key = _get_deployment_api_key(project_id)
    if not api_key:
        raise HTTPException(500, "No se pudo leer la API key del deployment")

    url = f"http://host.docker.internal:{port}/api/v1/ingest"
    try:
        r = httpx.post(
            url,
            json={"collection": body.collection, "text": body.text, "source_name": body.source_name},
            headers={"x-api-key": api_key},
            timeout=30.0,
        )
    except httpx.TimeoutException:
        raise HTTPException(504, "El deployment no respondió en 30s")
    except Exception as exc:
        raise HTTPException(502, f"Error contactando deployment: {str(exc)[:80]}")

    if r.status_code not in (200, 201):
        raise HTTPException(r.status_code, r.text[:200])

    write_event(
        "knowledge_ingested",
        project_id,
        {"collection": body.collection, "source_name": body.source_name, "chars": len(body.text)},
    )
    return {"ok": True, "deployment": project_id, "result": r.json()}


@router.post("/{project_id}/quality-gates")
def run_deployment_quality_gates(project_id: str, body: GatesPayload):
    """
    Ejecuta los quality gates funcionales contra el deployment activo.
    fast=True (default): sólo gates sin LLM (<15s).
    fast=False: incluye test de respuesta Ollama (~90-120s adicionales).
    """
    port = _get_deployment_port(project_id)
    if not port:
        raise HTTPException(404, f"Puerto no encontrado para deployment '{project_id}'")

    api_key = _get_deployment_api_key(project_id)
    if not api_key:
        raise HTTPException(500, "No se pudo leer la API key del deployment")

    dep_dir = DEPLOYMENTS_DIR / project_id
    if not dep_dir.exists():
        raise HTTPException(404, f"Directorio del deployment '{project_id}' no encontrado")

    # Leer manifest del deployment (no del workspace)
    manifest_path = dep_dir / "manifest.yaml"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    report_path = dep_dir / "quality_gates_report.json"

    report = run_deployment_gates(
        project_id=project_id,
        api_port=port,
        api_key=api_key,
        manifest=manifest,
        report_path=report_path,
        fast=body.fast,
    )

    # Registrar resultado en audit
    write_event(
        "deployment_gates_validated",
        project_id,
        {
            "api_port": port,
            "fast": body.fast,
            "summary": report["summary"],
            "report_hash": report.get("report_hash", ""),
        },
    )

    return {
        "project_id": project_id,
        "api_port": port,
        "fast": body.fast,
        "summary": report["summary"],
        "gates": report["gates"],
        "report_hash": report.get("report_hash"),
    }
