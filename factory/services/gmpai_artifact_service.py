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

    report = {
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

    # Estado de ejecucion real por agente (distinto de findings) y resumen de
    # la matriz finding->correccion — ambos derivados solo de datos ya
    # presentes en `report`, sin reprocesar nada.
    from factory.services import gmpai_agent_execution_status as _aes
    from factory.services import gmpai_finding_correction_service as _fcs
    report["agent_execution_status"] = _aes.build_agent_execution_status(report)
    report["agent_execution_summary"] = _aes.summarize_agent_execution_status(report["agent_execution_status"])
    report["finding_correction_summary"] = _fcs.summarize_correction_matrix(
        _fcs.build_finding_correction_matrix(report))
    return report


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
    from factory.services import gmpai_finding_correction_service as _fcs

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

    agent_execution_status = report_data["agent_execution_status"]
    agent_execution_summary = report_data["agent_execution_summary"]
    correction_matrix = _fcs.build_finding_correction_matrix(report_data)
    correction_matrix_summary = report_data["finding_correction_summary"]

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

    # 4. Documento corregido controlado (DOCX) para REM-GMPAI-001 (gap de
    # protocolo IQ/OQ/PQ, finding a nivel de familia documental).
    docx_bytes, docx_sha256 = build_remediation_draft_docx(report_data)
    _write("corrected_documents/REM-GMPAI-001_propuesta_remediacion_draft_v1.docx", docx_bytes,
           agente="requirements_traceability_agent", estado="draft")

    # 4b. Estado de ejecucion real de los 8 agentes (EXECUTED_VERIFIED /
    # RESULT_RECOVERED / CONFIGURED_ONLY / FAILED / NOT_APPLICABLE) — separa
    # findings de ejecuciones (ver auditoria de runtime, factory/services/
    # gmpai_agent_execution_status.py).
    _write("agent_reports/agent_execution_status.json",
           json.dumps({"agents": agent_execution_status, "summary": agent_execution_summary},
                      indent=2, ensure_ascii=False).encode("utf-8"))

    # 4c. Matriz finding -> correccion sobre los 267 findings reales (no
    # reprocesa nada: clasificacion determinista sobre datos ya aprobados).
    _write("compliance_matrices/finding_correction_matrix.json",
           json.dumps({"matrix": correction_matrix, "summary": correction_matrix_summary},
                      indent=2, ensure_ascii=False).encode("utf-8"))

    # 4d. Borrador consolidado del piloto controlado de verificacion (familia
    # Rockwell::MCCPDC-215115305, 1 documento real, 3 ejecuciones EXECUTED_
    # VERIFIED con run_id/task_id/timestamps — ver
    # factory/workspaces/gmpai_document_validation/run_pilot_verification.py
    # y pilot_verification_result.json). Opcional: solo se incluye si el
    # piloto ya se ejecuto; no se genera aqui ni se reprocesan los 32
    # documentos si no existe.
    pilot_path = paths.WS_BASE / PROJECT_ID / "pilot_verification_result.json"
    if pilot_path.exists():
        from factory.services.gmpai_finding_correction_service import build_document_correction_draft_docx
        pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
        pilot_docx, pilot_sha = build_document_correction_draft_docx(
            pilot["pilot_document"], pilot["findings"], report_data["agents"],
            pilot["pilot_document_sha256"])
        _write(
            f"corrected_documents/PILOTO_{pilot['pilot_document']}_correccion_consolidada_draft_v1.docx",
            pilot_docx, estado="draft",
        )
        _write("agent_reports/pilot_verification_result.json",
               json.dumps(pilot, indent=2, ensure_ascii=False).encode("utf-8"))

    limitation_note = (
        "LIMITACION DECLARADA: el borrador consolidado por documento (DOCX) solo se "
        "genero para REM-GMPAI-001 (nivel de familia documental) y, si el piloto de "
        "verificacion se ejecuto, para el documento del piloto. La matriz finding -> "
        "correccion (compliance_matrices/finding_correction_matrix.json) SI clasifica "
        "los 267 findings reales (83 corregibles / 184 con evidencia insuficiente), pero "
        "generar el DOCX consolidado para los 14 documentos Rockwell restantes es "
        "trabajo pendiente (no se genera aqui para evitar declarar terminada una "
        "capacidad que solo se demostro sobre 1-2 documentos). No se modifico ni "
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


# ── FS_v1.2 — registro explícito de cierre para Mission Control ────────────
# Distinto del RC canónico (que cubre los 32 documentos sin chunking): esto
# registra, para el documento FS_v1.2 puntual, cuál run de gmpai-artifacts es
# el vigente ("is_current") y cuál queda legado ("supersedes_run_id"). No
# reprocesa nada — solo lee fs_v1_2_status.json + manifest del run + la
# decisión Capa 9 ya registrada en factory/layer9/decisions/decisions.jsonl.

FS_V1_2_DIR = Path(__file__).parent.parent / "docs" / "gmpai_reanalysis" / "fs_v1_2"
FS_V1_2_CLOSURE_REGISTRY = GMPAI_REPORTS_BASE / "_fs_v1_2_closure_registry.json"


def _decision_record(decision_id: str) -> dict | None:
    decisions_path = Path(__file__).parent.parent / "layer9" / "decisions" / "decisions.jsonl"
    if not decisions_path.exists():
        return None
    for line in decisions_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("decision_id") == decision_id:
            return d
    return None


def record_fs_v1_2_closure(
    run_id: str,
    supersedes_run_id: str,
    commit: str,
    decision_id: str,
    recorded_by: str | None = None,
    version: str = "v2",
    zip_filename: str = "paquete_final.zip",
    metrics_filename: str | None = None,
    receipt_filename: str | None = None,
) -> dict:
    """Registra explícitamente, en un archivo persistente, cuál run de
    gmpai-artifacts es el vigente para el cierre de FS_v1.2 y la CADENA de
    versiones anteriores (superseded_runs) hasta el paquete histórico legado
    (legacy_runs, RC v1.4 pre-Piloto-B). Idempotente: se puede volver a
    llamar y solo actualiza el registro, nunca reprocesa documentos ni toca
    los runs en disco. No asume el nombre del zip ni la clasificación del
    run superado -- cada versión puede tener su propio zip_filename y su
    propia clasificación (legado vs. simplemente superseded)."""
    status = json.loads((FS_V1_2_DIR / "fs_v1_2_status.json").read_text(encoding="utf-8"))
    decision = _decision_record(decision_id)

    cobertura = {
        agente: f"{d['chunks_ok']}/{d['chunks_total']}"
        for agente, d in status["agentes"].items()
    }

    metrics = None
    if metrics_filename and (FS_V1_2_DIR / metrics_filename).exists():
        metrics = json.loads((FS_V1_2_DIR / metrics_filename).read_text(encoding="utf-8"))

    receipt = None
    receipt_path = GMPAI_REPORTS_BASE / run_id / (receipt_filename or "package_receipt.json")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    record = {
        "mission_id": PROJECT_ID,
        "documento": status["documento"],
        "document_sha256": status["document_sha256"],
        "run_id": run_id,
        "version": version,
        "commit": commit,
        "estado": status["classification"],
        "is_current": True,
        "supersedes_run_id": supersedes_run_id,
        "capa9_decision_id": decision_id,
        "capa9_decision": decision,
        "cobertura_por_agente": cobertura,
        "findings_totales": status["findings_totales"],
        "contradicciones_totales": status["contradicciones_totales"],
        "contradicciones_resueltas": status["contradicciones_resueltas"],
        "matriz_finding_correccion": status["matriz_finding_correccion"],
        "open_items": ["COR-1", "COR-5", "REM-GMPAI-001"],
        "human_review_required": status["revision_humana_requerida"],
        "human_review_status": "AWAITING_HUMAN_REVIEW",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "registered_by": recorded_by or "system",
        "zip_filename": zip_filename,
        "zip_sha256": _sha256_file(GMPAI_REPORTS_BASE / run_id / zip_filename),
        "regulatory_metrics": metrics,
        "package_receipt": receipt,
    }

    prior = {}
    if FS_V1_2_CLOSURE_REGISTRY.exists():
        prior = json.loads(FS_V1_2_CLOSURE_REGISTRY.read_text(encoding="utf-8"))

    registry = {"current": record, "superseded_runs": [], "legacy_runs": prior.get("legacy_runs", [])}

    # La versión anterior (si existía como "current") pasa a superseded_runs,
    # NO a legacy_runs (legacy_runs es solo el RC v1.4 pre-Piloto-B).
    prior_current = prior.get("current")
    superseded_runs = [r for r in prior.get("superseded_runs", []) if r["run_id"] != supersedes_run_id]
    if prior_current and prior_current.get("run_id") == supersedes_run_id:
        superseded_runs.append({
            "run_id": prior_current["run_id"],
            "version": prior_current.get("version", "v?"),
            "classification": ["SUPERSEDED_FOR_OPERATIONAL_USE"],
            "zip_filename": prior_current.get("zip_filename", "paquete_final.zip"),
            "zip_sha256": prior_current.get("zip_sha256"),
            "superseded_by_run_id": run_id,
        })
    elif supersedes_run_id not in {r["run_id"] for r in prior.get("legacy_runs", [])}:
        # supersedes_run_id no es ni el 'current' previo ni un legacy ya
        # conocido -- registrarlo igual como superseded, sin inventar datos
        # que no tenemos (zip_sha256 se recalcula si el archivo existe).
        candidate_zip = GMPAI_REPORTS_BASE / supersedes_run_id / zip_filename
        superseded_runs.append({
            "run_id": supersedes_run_id,
            "version": "v?",
            "classification": ["SUPERSEDED_FOR_OPERATIONAL_USE"],
            "zip_filename": zip_filename,
            "zip_sha256": _sha256_file(candidate_zip) if candidate_zip.exists() else None,
            "superseded_by_run_id": run_id,
        })
    registry["superseded_runs"] = superseded_runs

    legacy_status_path = GMPAI_REPORTS_BASE / "20260715T171646Z" / "LEGACY_STATUS.json"
    if legacy_status_path.exists() and not any(r["run_id"] == "20260715T171646Z" for r in registry["legacy_runs"]):
        registry["legacy_runs"].append({
            "run_id": "20260715T171646Z",
            "classification": ["LEGACY_RC_V1.4_PRE_FS_REANALYSIS", "SUPERSEDED_FOR_OPERATIONAL_USE"],
            "superseded_by_run_id": run_id,
            "legacy_status_detail": json.loads(legacy_status_path.read_text(encoding="utf-8")),
        })

    FS_V1_2_CLOSURE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    FS_V1_2_CLOSURE_REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

    write_event("gmp_report_generated", PROJECT_ID, {
        "record_by": recorded_by or "system",
        "artifact_kind": "gmpai_fs_v1_2_closure_registered",
        "run_id": run_id,
        "supersedes_run_id": supersedes_run_id,
        "commit_reference": commit,
        "decision_id_reference": decision_id,
        "cor1_abierto": True,
        "cor5_abierto": True,
        "rem_gmpai_001_abierto": True,
    })
    return registry


def get_fs_v1_2_closure_status() -> dict:
    if not FS_V1_2_CLOSURE_REGISTRY.exists():
        raise ArtifactNotFound("Registro de cierre FS_v1.2 no generado todavía")
    return json.loads(FS_V1_2_CLOSURE_REGISTRY.read_text(encoding="utf-8"))


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
