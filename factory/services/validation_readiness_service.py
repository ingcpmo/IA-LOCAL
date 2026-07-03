"""
W6.1 — Servicio read-only de: biblioteca de reportes por misión (V6),
paquete de validación CSV/GAMP 5 (V10) y readiness piloto/go-live (V9).

Reglas duras:
  - SOLO lectura local. NUNCA audita, NUNCA escribe, NUNCA genera documentos.
  - Toda función valida primero que la misión exista (404 si no) — el
    project_id jamás se usa para construir rutas sin ese gate.
  - Readiness: cada dimensión cita su evidencia o dice "sin evidencia".
    NUNCA un estado optimista sin soporte (riesgo R7 del diseño W6).

Los tests redirigen rutas con monkeypatch sobre factory.services.paths y
la agregación con monkeypatch sobre _evidence.build_mission_summary.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml as _yaml
from fastapi import HTTPException

from factory.services import design_mode_service as _design
from factory.services import mission_evidence_service as _evidence
from factory.services import paths


def require_mission(project_id: str) -> dict:
    """Gate común: la misión debe existir. Devuelve el YAML parseado."""
    mission_file = paths.MISSIONS_DIR / f"{project_id}.yaml"
    if not mission_file.exists():
        raise HTTPException(404, f"Misión '{project_id}' no encontrada")
    try:
        return _yaml.safe_load(mission_file.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise HTTPException(500, f"Error leyendo misión: {e}")


# ── V6: biblioteca de reportes ────────────────────────────────────────────────

_REPORT_NAMES = {"test_report.json", "diff.txt", "rc_manifest.json"}


def _file_entry(f: Path, base: Path, kind: str) -> dict:
    stat = f.stat()
    return {
        "kind": kind,
        "path": str(f.relative_to(base)),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256_12": hashlib.sha256(f.read_bytes()).hexdigest()[:12],
    }


def list_reports(project_id: str) -> dict:
    """
    Artefactos de reporte YA presentes en disco (no genera nada):
    reportes de RC (test_report, diff, manifest, logs headless), resultados
    de pruebas funcionales W4, y los reportes generables bajo demanda
    (gmp-report / gmp-report.pdf) como referencias de endpoint.
    """
    require_mission(project_id)
    stored = []

    rc_dir = paths.RC_BASE / project_id
    if rc_dir.exists():
        for f in sorted(rc_dir.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(rc_dir))
            if any(bl in rel for bl in paths.FILTER_PARTS):
                continue
            if f.name in _REPORT_NAMES or (f.name.startswith("headless_") and f.suffix == ".log"):
                stored.append(_file_entry(f, rc_dir, "release_candidate"))

    results_file = paths.TEST_RESULTS_DIR / f"{project_id}.jsonl"
    if results_file.exists():
        stored.append(_file_entry(results_file, paths.TEST_RESULTS_DIR, "functional_test_results"))

    return {
        "project_id": project_id,
        "stored_reports": stored,
        "on_demand": [
            {"name": "Dashboard GMP (JSON)",
             "endpoint": f"/api/v1/layer9/missions/{project_id}/gmp-report"},
            {"name": "Informe GMP robusto (PDF, 18 secciones)",
             "endpoint": f"/api/v1/layer9/missions/{project_id}/gmp-report.pdf"},
        ],
        "note": None if stored else "sin reportes almacenados para esta misión",
    }


# ── V10: paquete de validación CSV / GAMP 5 ──────────────────────────────────

# Los 22 documentos del paquete documental (diseño W5 FASE 3 / W6 §V10).
VALIDATION_DOCS = [
    ("intended_use", "Intended Use"),
    ("gxp_impact_assessment", "GxP Impact Assessment"),
    ("system_risk_assessment", "System Risk Assessment"),
    ("supplier_ai_model_assessment", "Supplier / AI Model Assessment"),
    ("urs", "URS — User Requirements Specification"),
    ("frs", "FRS — Functional Requirements Specification"),
    ("design_spec", "Design Specification"),
    ("configuration_spec", "Configuration Specification"),
    ("data_integrity_assessment", "Data Integrity Assessment"),
    ("part11_assessment", "21 CFR Part 11 Assessment"),
    ("alcoa_plus_assessment", "ALCOA+ Assessment"),
    ("traceability_matrix", "Traceability Matrix"),
    ("test_strategy", "Test Strategy"),
    ("iq", "IQ — Installation Qualification"),
    ("oq", "OQ — Operational Qualification"),
    ("pq", "PQ — Performance Qualification"),
    ("validation_summary_report", "Validation Summary Report"),
    ("sop_suggested", "SOP sugeridos"),
    ("change_control", "Change Control"),
    ("periodic_review", "Periodic Review"),
    ("incident_deviation_handling", "Incident / Deviation Handling"),
    ("retirement_plan", "Retirement Plan"),
]

# W6.2 — estados del ciclo de vida documental (generated se acepta como
# alias legado y se normaliza a draft)
_DOC_STATUSES = {"not_started", "draft", "missing_evidence", "needs_human_review", "approved"}
_LEGACY_STATUS = {"generated": "draft"}


def read_validation_package(project_id: str) -> dict:
    """
    Estado del dossier CSV por misión. Lee validation/<pid>/dossier.yaml si
    existe; si no, TODOS los documentos en not_started (la brecha se muestra
    tal cual, nunca se simula avance).
    """
    require_mission(project_id)
    dossier_file = paths.VALIDATION_BASE / project_id / "dossier.yaml"
    recorded: dict = {}
    if dossier_file.exists():
        try:
            data = _yaml.safe_load(dossier_file.read_text(encoding="utf-8")) or {}
            recorded = data.get("documents", {}) or {}
        except Exception:
            recorded = {}

    documents = []
    counts = {s: 0 for s in _DOC_STATUSES}
    for doc_id, title in VALIDATION_DOCS:
        entry = recorded.get(doc_id) or {}
        status = entry.get("status", "not_started")
        status = _LEGACY_STATUS.get(status, status)
        if status not in _DOC_STATUSES:
            status = "not_started"
        counts[status] += 1
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "status": status,
            "approved_by": entry.get("approved_by"),
            "generated_at": entry.get("generated_at"),
            "missing": entry.get("missing") or [],
        })

    return {
        "project_id": project_id,
        "dossier_exists": dossier_file.exists(),
        "documents": documents,
        "counts": counts,
        "total": len(VALIDATION_DOCS),
        "note": None if dossier_file.exists() else
        "sin dossier: aún no se han generado borradores para esta misión (W6.2)",
    }


# ── V9: readiness piloto / go-live ────────────────────────────────────────────

def _dim(dim_id: str, label: str, status: str, evidence: str) -> dict:
    """status: ready | partial | not_ready | sin_evidencia."""
    return {"id": dim_id, "label": label, "status": status, "evidence": evidence}


def build_readiness(project_id: str) -> dict:
    """
    Checklist go/no-go derivado EXCLUSIVAMENTE de evidencia existente.
    Dimensión sin fuente de datos en el sistema → "sin evidencia" (not ready).
    """
    summary = _evidence.build_mission_summary(project_id)
    dims = []

    m = summary.get("mission", {})
    approved = m.get("status") == "approved"
    dims.append(_dim("mission_approved", "Misión aprobada por humano",
                     "ready" if approved else "not_ready",
                     f"misión {m.get('status')} · approved_by={m.get('approved_by') or '—'}"))

    agents = (summary.get("design") or {}).get("agents_summary") or {}
    agent_ids = agents.get("agent_ids", []) or []
    dims.append(_dim("agents_defined", "Agentes de dominio definidos",
                     "ready" if agent_ids else "not_ready",
                     f"{len(agent_ids)} agentes en el diseño: {', '.join(agent_ids) or '—'}"))

    t = summary.get("tests")
    if t and (t.get("passed", 0) + t.get("failed", 0)) > 0:
        ok = t.get("failed", 0) == 0
        dims.append(_dim("build_tests", "Tests de construcción (workspace)",
                         "ready" if ok else "partial",
                         f"{t.get('passed', 0)} passed · {t.get('failed', 0)} failed"))
    else:
        dims.append(_dim("build_tests", "Tests de construcción (workspace)",
                         "sin_evidencia", "sin test_report.json en el workspace"))

    runs = 0
    results_file = paths.TEST_RESULTS_DIR / f"{project_id}.jsonl"
    if results_file.exists():
        runs = sum(1 for line in results_file.read_text(encoding="utf-8").splitlines()
                   if line.strip())
    dims.append(_dim("functional_tests", "Pruebas funcionales W4 ejecutadas",
                     "ready" if runs else "sin_evidencia",
                     f"{runs} ejecuciones registradas" if runs else "sin ejecuciones registradas"))

    rcs = summary.get("rcs", {})
    dims.append(_dim("canonical_rc", "Release candidate canónico",
                     "ready" if rcs.get("canonical") else "not_ready",
                     f"canonical={rcs.get('canonical') or '—'} · {rcs.get('count', 0)} RCs"))

    dep = summary.get("deployment", {})
    dep_status = "ready" if dep.get("health_ok") else ("partial" if dep.get("exists") else "not_ready")
    dims.append(_dim("deployment", "Deployment operativo",
                     dep_status,
                     f"exists={dep.get('exists')} · puerto={dep.get('api_port') or '—'} · health_ok={dep.get('health_ok')}"))

    audit = summary.get("audit", {})
    dims.append(_dim("audit_trail", "Trazabilidad en cadena de auditoría",
                     "ready" if audit.get("event_count_filtered") else "not_ready",
                     f"{audit.get('event_count_filtered', 0)} eventos de la misión en la cadena"))

    vp = read_validation_package(project_id)
    c = vp["counts"]
    in_progress = c["draft"] + c["needs_human_review"] + c["missing_evidence"]
    csv_status = ("ready" if c["approved"] == vp["total"] else
                  "partial" if (c["approved"] + in_progress) > 0 else "not_ready")
    dims.append(_dim("csv_package", "Paquete CSV / GAMP 5",
                     csv_status,
                     f"{c['approved']} aprobados · {c['draft']} draft · "
                     f"{c['needs_human_review']} por revisar · {c['missing_evidence']} sin evidencia · "
                     f"{c['not_started']} sin iniciar (de {vp['total']})"))

    reg = _design.read_source_registry()
    connected = [s for s in reg.get("sources", []) if s.get("status") == "connected"]
    dims.append(_dim("regulatory_corpus", "Corpus regulatorio conectado",
                     "ready" if connected else "not_ready",
                     f"{len(connected)} de {len(reg.get('sources', []))} fuentes conectadas"))

    # Dimensiones sin fuente de datos en el sistema actual: se dicen tal cual.
    for dim_id, label in [
        ("roles_signatures", "Roles y firma electrónica Part 11"),
        ("lims_cds", "Integración LIMS / CDS"),
        ("representative_data", "Datos representativos reales"),
    ]:
        dims.append(_dim(dim_id, label, "sin_evidencia",
                         "sin evidencia — capacidad no implementada en el sistema"))

    ready = sum(1 for d in dims if d["status"] == "ready")
    return {
        "project_id": project_id,
        "dimensions": dims,
        "ready": ready,
        "total": len(dims),
        "verdict": "no_go" if ready < len(dims) else "go",
        "note": "veredicto derivado solo de evidencia: cualquier dimensión no-ready implica no_go",
    }
