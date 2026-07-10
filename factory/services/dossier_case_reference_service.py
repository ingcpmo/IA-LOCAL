"""
W9 Bloque 2 (Opción A) — el dossier CITA análisis de casos aceptados por
ID + versión; JAMÁS copia ni adapta su texto dentro del documento. Cero
duplicación de contenido gobernado: `regulatory/case_analyses/` sigue
siendo la única fuente de verdad del análisis, este módulo solo añade un
puntero verificable en `dossier.yaml`. Aprobado por Cesar
(W8_GROUNDING_PLAN.md §Bloque 2, 2026-07-10): "el dossier debe referenciar
análisis de casos por ID y versión, no copiar ni adaptar el texto dentro
del dossier."

Reglas duras de este módulo:
  - Solo se referencian análisis en status == "accepted" (decisión humana
    ya emitida) — nunca drafts, rechazados ni pendientes de decisión.
  - El análisis debe existir para el MISMO project_id del dossier
    (case_analysis_service.read_analysis ya lo namespacea por mission_id —
    no hay citación entre misiones distintas en este bloque).
  - JAMÁS toca content_sha256, status, approved_by/approved_at del
    documento: `case_references` es metadata de citación aparte del modelo
    de aprobación del dossier (decisión de diseño de Bloque 2 — no fusiona
    approve de dossier con accept de caso, ni sus auditorías).
  - Idempotente por (case_id, analysis_version): referenciar el mismo par
    dos veces en el mismo doc_id es 409, no duplica la entrada.
  - 1 evento de auditoría propio (dossier_case_reference_linked) que NUNCA
    reescribe ni copia el evento case_analysis_decision original — la
    referencia guarda su entry_hash para verificación cruzada.
"""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException

from factory.services import case_analysis_service as _case_analysis
from factory.services import dossier_generator_service as _dossier
from factory.services import paths
from factory.services import test_console_service as _console
from factory.services import validation_readiness_service as _valready

ACCEPTED_STATUS = "accepted"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_accept_audit_event(project_id: str, case_id: str, version: int) -> dict | None:
    """Localiza el evento case_analysis_decision (decision=accept) exacto de
    este (case_id, version) — solo lectura, nunca escribe."""
    if not paths.AUDIT_FILE.exists():
        return None
    found = None
    for raw in paths.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except Exception:
            continue
        if entry.get("event_type") != "case_analysis_decision":
            continue
        data = entry.get("data") or {}
        if (data.get("case_id") == case_id and data.get("analysis_version") == version
                and data.get("decision") == "accept"):
            found = entry   # última aparición gana (no debería haber más de una)
    return found


def link_case_reference(project_id: str, doc_id: str, case_id: str,
                        analysis_version: int, linked_by: str) -> dict:
    """Añade a documents[doc_id].case_references un puntero verificable al
    análisis aceptado — nunca copia su texto. Acto humano/agente auditado con
    nombre real (mismo patrón run_by de W4)."""
    name = _console.validate_run_by(linked_by)
    _valready.require_mission(project_id)

    if doc_id not in _dossier._TITLES:
        raise HTTPException(404, f"Documento '{doc_id}' no existe en el paquete de validación")
    dossier = _dossier._load_dossier(project_id)
    entry = dossier["documents"].get(doc_id)
    if not entry:
        raise HTTPException(409, f"'{doc_id}' no ha sido generado — nada que referenciar")

    record = _case_analysis.read_analysis(project_id, case_id, analysis_version)
    if record.get("status") != ACCEPTED_STATUS:
        raise HTTPException(422, f"El análisis v{analysis_version} del caso '{case_id}' está en "
                                 f"'{record.get('status')}' — solo se pueden referenciar análisis "
                                 f"en estado '{ACCEPTED_STATUS}'")

    refs = entry.setdefault("case_references", [])
    if any(r.get("case_id") == case_id and r.get("analysis_version") == analysis_version
           for r in refs):
        raise HTTPException(409, f"El análisis v{analysis_version} del caso '{case_id}' ya está "
                                 f"referenciado en '{doc_id}'")

    audit_event = _find_accept_audit_event(project_id, case_id, analysis_version)
    if audit_event is None:
        raise HTTPException(500, "No se encontró el evento de auditoría de la decisión 'accept' "
                                 "para este análisis — no se crea una referencia no verificable")

    analysis_file = _case_analysis._analysis_path(project_id, case_id, analysis_version)
    decision = record.get("decision") or {}
    pointer = (f"regulatory/case_analyses/{project_id}/"
              f"{_case_analysis._case_dir(case_id)}/v{analysis_version:02d}.json")

    reference = {
        "case_id": case_id,
        "analysis_version": analysis_version,
        "mission_id": project_id,
        "status": ACCEPTED_STATUS,
        "analysis_pointer": pointer,
        "analysis_sha256": _file_sha256(analysis_file),
        "decided_at": decision.get("decided_at"),
        "decided_by": decision.get("decided_by"),
        "decision": decision.get("decision"),
        "audit_event_hash": audit_event.get("entry_hash"),
        "audit_event_timestamp": audit_event.get("timestamp"),
        "linked_at": _now(),
        "linked_by": name,
    }
    refs.append(reference)
    _dossier._save_dossier(project_id, dossier)

    from factory.core.audit_writer import write_event
    write_event("dossier_case_reference_linked", project_id, {
        "doc_id": doc_id, "case_id": case_id, "analysis_version": analysis_version,
        "linked_by": name, "audit_event_hash": audit_event.get("entry_hash"),
    })
    return {"project_id": project_id, "doc_id": doc_id, "case_id": case_id,
            "analysis_version": analysis_version, "linked_by": name,
            "case_references": refs}
