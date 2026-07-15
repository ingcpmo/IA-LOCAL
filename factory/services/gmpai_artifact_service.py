"""
GMPAI — Servicio de agregación y empaquetado de artefactos de cierre para
gmpai_document_validation (REM-GMPAI-001 + informe final + descargas).

Capa de PRESENTACIÓN/EMPAQUETADO sobre datos YA existentes y aprobados:
RC canónico (rc_manifest.json + pipeline_pilot_llm.json), mission.yaml,
tracker de remediación. NUNCA reprocesa documentos ni invoca agentes —
solo lee, agrega y empaqueta lo que ya fue decidido por Cesar.

Persistencia de artefactos: /home/ing_cpmo/GMPAI/reports/gmpai_document_validation/<run_id>/
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml as _yaml

from factory.core.audit_writer import write_event
from factory.layer8.release_candidate_builder import get_rc
from factory.layer9.mission_control import get_mission
from factory.services import paths

PROJECT_ID = "gmpai_document_validation"
GMPAI_REPORTS_BASE = Path("/home/ing_cpmo/GMPAI/reports") / PROJECT_ID
REMEDIATION_JSON = Path(__file__).parent.parent / "docs" / "gmpai_remediation_tracker.json"

_ARTIFACT_MIME = {
    ".pdf": "application/pdf",
    ".json": "application/json",
    ".txt": "text/plain",
    ".zip": "application/zip",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
}


class ArtifactNotFound(Exception):
    pass


class PathTraversalError(Exception):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_remediation_items() -> list[dict]:
    """Fuente estructurada de REM-GMPAI-001+ — el .md en factory/docs/ es la
    versión legible por humanos, este JSON es la fuente que consumen los PDF
    y la API. Mismo contenido, sin parsear markdown."""
    if not REMEDIATION_JSON.exists():
        return []
    return json.loads(REMEDIATION_JSON.read_text(encoding="utf-8"))["items"]


def load_canonical_pipeline_data() -> tuple[dict, dict]:
    """Retorna (rc_manifest, pipeline_data) del RC canónico. No reprocesa nada:
    lee el pipeline_pilot_llm.json que ya está en el RC aprobado."""
    rc_base = paths.RC_BASE / PROJECT_ID
    canonical = None
    for manifest_file in rc_base.rglob("rc_manifest.json"):
        d = json.loads(manifest_file.read_text(encoding="utf-8"))
        if d.get("is_canonical") is True:
            canonical = d
            break
    if canonical is None:
        raise ArtifactNotFound(f"Sin RC canónico marcado para '{PROJECT_ID}'")

    artifacts_dir = Path(canonical["artifacts_path"].replace("/app/factory", str(paths.FACTORY_ROOT)))
    pipeline_path = artifacts_dir / "pipeline_pilot_llm.json"
    if not pipeline_path.exists():
        raise ArtifactNotFound(f"pipeline_pilot_llm.json no encontrado en {artifacts_dir}")
    pipeline_data = json.loads(pipeline_path.read_text(encoding="utf-8"))
    return canonical, pipeline_data


def _rc_history() -> list[dict]:
    """Historial completo de decisiones humanas sobre RCs de esta misión."""
    rc_base = paths.RC_BASE / PROJECT_ID
    out = []
    for manifest_file in sorted(rc_base.rglob("rc_manifest.json")):
        d = json.loads(manifest_file.read_text(encoding="utf-8"))
        out.append({
            "rc_id": d.get("rc_id"),
            "version": d.get("version"),
            "status": d.get("status"),
            "approved_by": d.get("approved_by"),
            "decided_at": d.get("decided_at"),
            "is_canonical": d.get("is_canonical", False),
        })
    return out


def build_final_report_data() -> dict:
    """Agrega TODO lo necesario para el informe final, desde datos ya
    aprobados. No dispara ningún agente ni relee los 32 documentos fuente."""
    canonical, pdata = load_canonical_pipeline_data()
    mission = get_mission(PROJECT_ID) or {}
    mission_yaml_path = paths.MISSIONS_DIR / f"{PROJECT_ID}.yaml"
    mission_full = _yaml.safe_load(mission_yaml_path.read_text(encoding="utf-8")) if mission_yaml_path.exists() else {}

    findings = pdata.get("findings", [])
    records = pdata.get("records", [])
    totals = pdata.get("totals_inventory", {})
    documents_declared = mission_full.get("documents", {})
    all_docs = sorted(documents_declared.keys())
    rockwell_docs = [d for d in all_docs if d.startswith("Rockwell/")]
    scada_docs = [d for d in all_docs if d.startswith("SCADA/")]

    by_status: dict[str, int] = {}
    for f in findings:
        by_status[f["estado"]] = by_status.get(f["estado"], 0) + 1
    for st in ("cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica"):
        by_status.setdefault(st, 0)

    agent_versions = {}
    for f in findings:
        aid = f["agente_responsable"]
        agent_versions.setdefault(aid, {
            "agent_version": f.get("agent_version"),
            "prompt_version": f.get("prompt_version"),
            "model": f.get("model"),
            "verifier_version": f.get("verifier_version"),
            "findings_count": 0,
        })
        agent_versions[aid]["findings_count"] += 1

    matrices = {}
    for f in findings:
        aid = f["agente_responsable"]
        matrices.setdefault(aid, []).append({
            "documento": f["documento"],
            "requisito_regulatorio": f["requisito_regulatorio"],
            "estado": f["estado"],
            "severidad": f["severidad"],
            "brecha": f["brecha"],
            "confianza": f["confianza"],
        })

    top_risks = sorted(
        [f for f in findings if f["estado"] in ("no_cumple", "cumple_parcialmente")],
        key=lambda f: {"critica": 0, "mayor": 1, "menor": 2, "": 3, "no_determinada": 3}.get(f.get("severidad", ""), 3),
    )[:10]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "project_id": PROJECT_ID,
            "client_type": mission_full.get("client_type"),
            "objective": mission_full.get("objective"),
            "regulatory_scope": mission_full.get("regulatory_scope", []),
            "status": mission_full.get("status"),
            "approved_at": mission_full.get("approved_at"),
        },
        "rc_canonical": {
            "rc_id": canonical.get("rc_id"),
            "version": canonical.get("version"),
            "approved_by": canonical.get("approved_by"),
            "decided_at": canonical.get("decided_at"),
            "marked_canonical_by": canonical.get("is_canonical_marked_by"),
            "marked_canonical_at": canonical.get("is_canonical_marked_at"),
            "sha256sums": canonical.get("sha256sums", {}),
        },
        "rc_history": _rc_history(),
        "scope": {
            "total_documents_declared": len(all_docs),
            "rockwell_documents": len(rockwell_docs),
            "scada_documents": len(scada_docs),
            "documents_with_compliance_findings": sorted({f["sistema"].split("::")[0] for f in findings}),
            "note": pdata.get("final_review", {}).get("totals", {}).get("note", ""),
            "limitation": (
                f"El inventario/hash-verificacion/deteccion de version cubre los "
                f"{len(all_docs)} documentos declarados en la mision (Rockwell "
                f"{len(rockwell_docs)} + SCADA {len(scada_docs)}). Las matrices de "
                f"cumplimiento (Part 11 / Annex 11 / ALCOA+ / trazabilidad) del RC "
                f"canonico solo cubren Rockwell ({len(records)} documentos con "
                f"extraccion+clasificacion detallada). SCADA (18 documentos) esta "
                f"inventariado y verificado por hash pero SIN hallazgos de "
                f"cumplimiento en este RC — no se reprocesa automaticamente."
            ),
        },
        "inventory": {
            "totals": totals,
            "all_declared_documents": all_docs,
            "records_detail": records,
            "duplicates_by_hash": pdata.get("duplicates_by_hash", {}),
        },
        "version_decisions": pdata.get("version_decisions", []),
        "version_conflicts": [v for v in pdata.get("version_decisions", []) if v.get("version_conflict")],
        "agents": agent_versions,
        "matrices": matrices,
        "findings_by_status": by_status,
        "findings_total": len(findings),
        "top_risks": top_risks,
        "remediation_items": load_remediation_items(),
        "risk_summary": pdata.get("risk_summary", {}),
        "final_review": pdata.get("final_review", {}),
        "governance_statement": pdata.get("final_review", {}).get("governance_statement", ""),
        "limitations": [
            "SCADA (18/32 documentos) inventariado y verificado por hash, pero sin "
            "hallazgos de cumplimiento en el RC canonico (scope=pilot, ver seccion Alcance).",
            "requirements_traceability_agent no registra agent_version/prompt_version/"
            "model/verifier_version en sus findings (limitacion del modulo LLM de "
            "trazabilidad, findings de los otros 3 agentes si los registran).",
            "El motor de integridad usado es LLM real (Ollama, qwen2.5:7b-instruct-q4_K_M) "
            "vía httpx directo a la API REST — no via paquete Python ollama.",
        ],
        "conclusion": (
            "Este resultado es una evaluacion asistida por agentes de IA, NO una "
            "aprobacion GMP automatica. Los hallazgos son insumo para revision y "
            "decision humana (accept/reject/request_changes) registrada con nombre "
            "real via el mecanismo oficial de Capa 9. La liberacion de lote y la "
            "disposicion final permanecen bajo responsabilidad del personal QA/QC "
            "calificado."
        ),
    }


def build_remediation_tracker_data() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_id": PROJECT_ID,
        "items": load_remediation_items(),
    }


# ── Empaquetado ──────────────────────────────────────────────────────────────

def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_packaging(run_id: str | None = None, recorded_by: str | None = None) -> dict:
    """Genera final_report.pdf, remediation_tracker.pdf, matrices, borrador
    DOCX controlado, manifest.json, SHA256SUMS.txt y paquete_final.zip bajo
    GMPAI_REPORTS_BASE/<run_id>/. No reprocesa los 32 documentos: solo lee el
    RC canónico ya aprobado y empaqueta."""
    from factory.core.gmpai_pdf_report import build_final_report_pdf, build_remediation_tracker_pdf
    from factory.services.gmpai_docx_draft import build_remediation_draft_docx

    run_id = run_id or _new_run_id()
    run_dir = GMPAI_REPORTS_BASE / run_id
    matrices_dir = run_dir / "compliance_matrices"
    agent_reports_dir = run_dir / "agent_reports"
    corrected_dir = run_dir / "corrected_documents"
    audit_dir = run_dir / "audit_summary"
    for d in (run_dir, matrices_dir, agent_reports_dir, corrected_dir, audit_dir):
        d.mkdir(parents=True, exist_ok=True)

    report_data = build_final_report_data()
    tracker_data = build_remediation_tracker_data()

    artifacts: list[dict] = []

    def _write(rel_path: str, content: bytes, agente: str | None = None, estado: str = "final") -> Path:
        p = run_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        artifacts.append({
            "artifact_id": _sha256_bytes(content)[:16],
            "filename": rel_path,
            "mime_type": _ARTIFACT_MIME.get(p.suffix, "application/octet-stream"),
            "version": report_data["rc_canonical"]["version"],
            "sha256": _sha256_bytes(content),
            "size_bytes": len(content),
            "generated_at": report_data["generated_at"],
            "project_id": PROJECT_ID,
            "mission_id": PROJECT_ID,
            "run_id": run_id,
            "agente": agente,
            "agent_version": (report_data["agents"].get(agente) or {}).get("agent_version") if agente else None,
            "estado": estado,
            "decision_humana": "no_aplica" if estado == "final" else "pendiente_revision_humana",
            "ruta_logica_origen": f"RC canonico {report_data['rc_canonical']['rc_id']}",
        })
        return p

    # 1. PDFs principales
    final_pdf = build_final_report_pdf(report_data)
    _write("final_report.pdf", final_pdf)

    tracker_pdf = build_remediation_tracker_pdf(tracker_data)
    _write("remediation_tracker.pdf", tracker_pdf)

    # 2. Matrices de cumplimiento (JSON, ya calculadas, no reprocesadas)
    for agente, rows in report_data["matrices"].items():
        content = json.dumps(rows, indent=2, ensure_ascii=False).encode("utf-8")
        _write(f"compliance_matrices/{agente}.json", content, agente=agente)

    # 3. Reportes por agente (resumen + findings)
    for agente, meta in report_data["agents"].items():
        payload = {"agente": agente, **meta, "findings": report_data["matrices"].get(agente, [])}
        content = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        _write(f"agent_reports/{agente}.json", content, agente=agente)

    # 4. Documento corregido controlado (DOCX) — solo REM-GMPAI-001, el único
    # finding con suficiente especificidad (familia + brecha + recomendacion
    # concreta) para una propuesta controlada. Los otros 266 findings son
    # gaps de evidencia (Part11/Annex11/ALCOA+), no ediciones de texto sobre
    # un documento original — NO se fabrica una correccion sin soporte.
    docx_bytes, docx_sha256 = build_remediation_draft_docx(report_data)
    _write("corrected_documents/REM-GMPAI-001_propuesta_remediacion_draft_v1.docx", docx_bytes,
           agente="requirements_traceability_agent", estado="draft")
    limitation_note = (
        "LIMITACION DECLARADA: solo se genero un borrador controlado para "
        "REM-GMPAI-001 (gap de protocolo IQ/OQ/PQ, finding a nivel de familia "
        "documental con recomendacion concreta). Los 266 findings restantes "
        "(fda_part11_agent, eu_annex11_agent, alcoa_plus_agent) son hallazgos "
        "de evidencia insuficiente o no-cumplimiento sobre AUSENCIA de "
        "informacion en los documentos originales, no errores de texto "
        "puntuales corregibles — generar una 'correccion' ahi implicaria "
        "fabricar contenido regulatorio no verificado. No se modifico ni "
        "sobrescribio ningun documento original en GMPAI/source/."
    )
    _write("corrected_documents/README_limitaciones.md", limitation_note.encode("utf-8"))

    # 5. Resumen de auditoría
    from factory.core.audit_writer import verify_chain
    audit_snapshot = verify_chain()
    _write("audit_summary/audit_verify.json",
           json.dumps(audit_snapshot, indent=2, ensure_ascii=False).encode("utf-8"))

    # 6. README del paquete
    readme = (
        f"# GMPAI Document Validation — paquete de artefactos\n\n"
        f"Proyecto: {PROJECT_ID}\n"
        f"RC canonico: {report_data['rc_canonical']['rc_id']}\n"
        f"Generado: {report_data['generated_at']}\n"
        f"Run ID: {run_id}\n\n"
        f"## Alcance\n\n{report_data['scope']['limitation']}\n\n"
        f"## Limitaciones\n\n" + "\n".join(f"- {l}" for l in report_data["limitations"]) + "\n\n"
        f"## Conclusion\n\n{report_data['conclusion']}\n"
    )
    _write("README.md", readme.encode("utf-8"))

    # 7. manifest.json (antes del zip, para que el zip lo incluya)
    manifest = {
        "run_id": run_id,
        "project_id": PROJECT_ID,
        "mission_id": PROJECT_ID,
        "generated_at": report_data["generated_at"],
        "rc_canonical": report_data["rc_canonical"]["rc_id"],
        "artifacts": artifacts,
    }
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_bytes(manifest_bytes)

    # 8. SHA256SUMS.txt (incluye manifest.json también)
    sums_lines = []
    for a in artifacts:
        sums_lines.append(f"{a['sha256']}  {a['filename']}")
    sums_lines.append(f"{_sha256_bytes(manifest_bytes)}  manifest.json")
    sums_path = run_dir / "SHA256SUMS.txt"
    sums_path.write_text("\n".join(sums_lines) + "\n", encoding="utf-8")

    # 9. paquete_final.zip — todo lo anterior
    zip_path = run_dir / "paquete_final.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in run_dir.rglob("*"):
            if f.is_file() and f.name != "paquete_final.zip":
                zf.write(f, arcname=f.relative_to(run_dir))

    write_event("gmp_report_generated", PROJECT_ID, {
        "record_by": recorded_by or "system_packaging",
        "canonical_rc": report_data["rc_canonical"]["rc_id"],
        "artifact_kind": "gmpai_artifact_package",
        "run_id": run_id,
        "artifact_count": len(artifacts) + 3,  # + manifest + sha256sums + zip
    })

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "manifest": manifest,
        "zip_path": str(zip_path),
        "zip_sha256": _sha256_file(zip_path),
    }


def list_runs() -> list[str]:
    if not GMPAI_REPORTS_BASE.exists():
        return []
    return sorted([d.name for d in GMPAI_REPORTS_BASE.iterdir() if d.is_dir()], reverse=True)


def get_manifest(run_id: str) -> dict:
    manifest_path = GMPAI_REPORTS_BASE / run_id / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactNotFound(f"run '{run_id}' no encontrado")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_artifact_path(run_id: str, rel_path: str) -> Path:
    """Resuelve un artefacto dentro de un run de forma segura — bloquea
    path traversal (.., rutas absolutas, symlinks fuera del run_dir)."""
    if ".." in Path(rel_path).parts or Path(rel_path).is_absolute():
        raise PathTraversalError(f"ruta inválida: {rel_path}")
    run_dir = (GMPAI_REPORTS_BASE / run_id).resolve()
    if not run_dir.exists() or not str(run_dir).startswith(str(GMPAI_REPORTS_BASE.resolve())):
        raise ArtifactNotFound(f"run '{run_id}' no encontrado")
    target = (run_dir / rel_path).resolve()
    if not str(target).startswith(str(run_dir) + "/") and target != run_dir:
        raise PathTraversalError(f"ruta fuera del run: {rel_path}")
    if not target.exists() or not target.is_file():
        raise ArtifactNotFound(f"artefacto '{rel_path}' no encontrado en run '{run_id}'")
    return target
