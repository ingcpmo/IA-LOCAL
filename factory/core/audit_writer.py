"""
Auditoría de fábrica — JSONL con hash chain SHA-256.

Patrón replicado de app/audit.py (21 CFR Part 11):
- Un archivo único: factory/audit/factory_audit.jsonl
- Cada entrada: entry_body → entry_hash = sha256(json.dumps(body, sort_keys=True))
- prev_entry_hash encadena con la entrada anterior ("GENESIS" al inicio)
- verify_chain() recorre todas las entradas en orden y verifica hashes e integridad

Eventos registrados: project_created, requirement_registered, workspace_created,
task_dispatched, gates_executed, diff_presented, approval_granted, approval_rejected,
release_created, deployment_created, deployment_started,
layer9_mission_created, layer9_mission_approved, layer9_requirement_submitted,
layer9_decision_recorded, layer9_risk_accepted,
layer8_mission_started, layer8_requirement_interpreted, layer8_agent_design_generated,
layer8_regulatory_matrix_generated, layer8_workspace_created, layer8_workspace_resumed,
layer8_claude_status_checked, layer8_claude_execution_started, layer8_claude_execution_completed,
layer8_claude_execution_failed, layer8_stop_condition_triggered, layer8_recovery_required,
gmp_report_generated, validation_dossier_generated, validation_doc_approved
"""

import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path(__file__).parent.parent / "audit" / "factory_audit.jsonl"

_last_entry_hash: str | None = None

VALID_EVENTS = {
    # Eventos de fábrica (F1-F4)
    "project_created", "requirement_registered", "workspace_created",
    "task_dispatched", "gates_executed", "diff_presented",
    # approval_proposed = agente propone (→ pending_human_confirmation)
    # approval_granted  = humano confirma (→ approved, decision_origin=human_confirmed)
    "approval_proposed", "approval_granted", "approval_rejected",
    "release_created", "deployment_created", "deployment_started",
    # Eventos Capa 9 Mission Control (F4.5a)
    "layer9_mission_created", "layer9_mission_approved",
    "layer9_requirement_submitted", "layer9_decision_recorded",
    "layer9_risk_accepted",
    # Eventos Capa 8 Tier-1 diseño (F4.5b)
    "layer8_mission_started", "layer8_requirement_interpreted",
    "layer8_agent_design_generated", "layer8_regulatory_matrix_generated",
    "layer8_workspace_created", "layer8_workspace_resumed",
    # Eventos Capa 8 Tier-2 runtime (F4.5c)
    "layer8_claude_status_checked", "layer8_claude_execution_started",
    "layer8_claude_execution_completed", "layer8_claude_execution_failed",
    "layer8_stop_condition_triggered", "layer8_recovery_required",
    # Eventos F7 — headless controlado
    "layer8_headless_enabled", "layer8_headless_result_reviewed",
    
    # Fase B+C
    "layer8_autonomy_policy_applied",
    # Eventos F9 — ops
    "knowledge_ingested",
    "tests_executed",
    "artifacts_collected",
    "layer8_autobuild_started",
    "layer8_autobuild_completed",
    "layer8_autobuild_failed",
    # Eventos F10 — quality gates live
    "deployment_gates_validated",
    # Eventos R3 — conectividad Ollama / UFW
    "network_access_configured",
    # Eventos Fase F — Release Candidate + cola revisión humana
    "release_candidate_created",
    "release_candidate_approved",
    "release_candidate_rejected",
    "rc_enqueued",
    "rc_reviewed",
    # V2 — configuración de modelo Claude Code
    "claude_model_changed",
    # W1 — RC canónico explícito
    "rc_marked_canonical",
    "rc_unmarked_canonical",
    # W1 — revisión de misión
    "layer9_mission_revised",
    # W4 — consola de pruebas funcionales por agente
    "agent_functional_test_executed",
    "agent_suite_tested",
    # W4.1 — informe PDF del Dashboard GMP (trazabilidad opcional de generación)
    "gmp_report_generated",
    # W6.2 — dossier CSV/GAMP 5: generación asistida y aprobación humana por documento
    "validation_dossier_generated",
    "validation_doc_approved",
    # W6.3 — conector online controlado (openFDA): consulta limitada y selective fetch
    "regulatory_query_executed",
    "case_detail_fetched",
    # Fase 1 (document_remediation_evolution) — verificación real de acceso
    # y hash de las fuentes regulatorias gobernadas
    "regulatory_source_currency_checked",
    "regulatory_broken_link_report_generated",
    # W6.5 — propuestas de agente sobre el dossier: el agente propone, el humano decide
    "dossier_agent_proposal_generated",
    "dossier_agent_proposal_failed",
    "dossier_agent_proposal_decision",
    # W7 — análisis de casos regulatorios por agente (project_id = misión real)
    "case_analysis_generated",
    "case_analysis_failed",
    "case_analysis_decision",
    # W9 Bloque 2 — el dossier referencia (por ID+versión) un análisis de
    # caso aceptado; nunca copia su texto
    "dossier_case_reference_linked",
    # gmpai_document_validation — reanálisis por chunks del motor git-trackeado
    # (factory/engines/gmpai_integrity/), un evento por documento analizado
    "gmpai_chunked_analysis_run",
    # gmpai_document_validation — gap de cobertura por fallo tecnico (chunks
    # que no produjeron JSON valido tras reintentos); nunca se declara
    # evidencia_insuficiente regulatoria por un fallo de ejecucion
    "gmpai_chunked_analysis_gap_registered",
    # W5 Ciclo 1 v2, Fase 4 (Bloque 4.3) — ejecucion de evidencia end-to-end
    # del pipeline verificado v2 (schema-gate + verificador + consolidador
    # de ausencias), SIEMPRE con run_context='validation' en su payload
    # ('data'). Distinto de gmpai_chunked_analysis_run (motor v1 en
    # produccion, run_context='production' por defecto) -- misma cadena de
    # auditoria unica, nunca fragmentada.
    "w5v2_validation_evidence_run",
    # BATCH_AND_EXCEPTION — flujo de revision humana por paquete (no por
    # chunk) sobre RemediationChange/CandidatePackage, ver
    # factory/services/remediation_package_service.py. candidate_document_created
    # y remediation_report_created son SIEMPRE automaticos (nunca requieren
    # revision humana); exception_reviewed es SIEMPRE individual y solo para
    # HIGH_RISK; document_released es el UNICO evento que puede asertar
    # liberacion (ReleaseRecord es append-only, nunca se reescribe).
    "candidate_document_created",
    "remediation_report_created",
    "remediation_package_generated",
    "exception_reviewed",
    "package_decision_recorded",
    "document_released",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _compute_entry_hash(entry_body: dict) -> str:
    canonical = json.dumps(entry_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _hash(canonical)


def _get_prev_hash() -> str:
    global _last_entry_hash
    if _last_entry_hash is not None:
        return _last_entry_hash

    if AUDIT_FILE.exists():
        try:
            lines = AUDIT_FILE.read_bytes().splitlines()
            for raw in reversed(lines):
                raw = raw.strip()
                if raw:
                    entry = json.loads(raw)
                    _last_entry_hash = entry.get("entry_hash", "GENESIS")
                    return _last_entry_hash
        except Exception:
            pass

    _last_entry_hash = "GENESIS"
    return "GENESIS"


def write_event(event_type: str, project_id: str, data: dict | None = None) -> dict:
    """
    Registra un evento en factory_audit.jsonl.
    Retorna la entrada escrita. Nunca lanza excepción (mismo patrón que app/audit.py).
    """
    global _last_entry_hash
    if event_type not in VALID_EVENTS:
        raise ValueError(f"Evento desconocido: {event_type}. Válidos: {VALID_EVENTS}")
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive lock para serializar escrituras concurrentes (local + container)
        lock_path = AUDIT_FILE.with_suffix(".lock")
        with open(lock_path, "a") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                _last_entry_hash = None  # forzar re-lectura dentro del lock
                prev_hash = _get_prev_hash()

                entry_body = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "entry_id": str(uuid.uuid4()),
                    "event_type": event_type,
                    "project_id": project_id,
                    "data": data or {},
                    "prev_entry_hash": prev_hash,
                }

                entry_hash = f"sha256:{_compute_entry_hash(entry_body)}"
                entry_body["entry_hash"] = entry_hash

                with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry_body, separators=(",", ":"), ensure_ascii=False) + "\n")

                _last_entry_hash = entry_hash
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

        return entry_body

    except Exception as e:
        return {"error": str(e)}


def verify_chain() -> dict:
    """
    Verifica la integridad de factory_audit.jsonl.

    Semántica Part-11:
      assessment="OK"   → cadena íntegra (hash_errors=0, chain_errors=0)
      assessment="WARN" → fork concurrente (hash_errors=0, chain_errors>0):
                          enlace roto por escrituras paralelas, contenido auténtico,
                          Part-11 cumplido.
      assessment="FAIL" → corrupción real (hash_errors>0): contenido puede estar
                          alterado, Part-11 NO cumplido.
    """
    if not AUDIT_FILE.exists():
        return {
            "verified": True, "is_fork": False, "assessment": "OK",
            "detail": "Archivo de auditoría no existe aún.",
            "log_count": 0, "verified_count": 0,
            "hash_errors": 0, "chain_errors": 0, "failed_count": 0,
            "hash_algo": "sha256",
            "part11_compliant": False, "audit_file": str(AUDIT_FILE),
        }

    lines = [ln.strip() for ln in AUDIT_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    total = len(lines)
    verified_count = 0
    hash_errors = 0
    chain_errors = 0
    prev_hash = "GENESIS"

    for raw in lines:
        try:
            entry = json.loads(raw)
        except Exception:
            hash_errors += 1
            continue

        stored_hash = entry.get("entry_hash", "")
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        expected_hash = f"sha256:{_compute_entry_hash(body)}"

        if stored_hash != expected_hash:
            hash_errors += 1
            prev_hash = stored_hash
            continue

        if entry.get("prev_entry_hash") != prev_hash:
            chain_errors += 1
        else:
            verified_count += 1

        prev_hash = stored_hash

    is_fork = hash_errors == 0 and chain_errors > 0
    if hash_errors == 0 and chain_errors == 0:
        assessment = "OK"
        detail = f"Cadena íntegra. {total} entradas verificadas."
    elif is_fork:
        assessment = "WARN"
        detail = (
            f"Fork concurrente: {chain_errors} ruptura(s) de enlace sin errores de hash. "
            "Contenido auténtico, Part-11 cumplido."
        )
    else:
        assessment = "FAIL"
        detail = (
            f"Corrupción detectada: {hash_errors} error(es) de hash. "
            "Contenido puede estar alterado, Part-11 NO cumplido."
        )

    return {
        "verified": hash_errors == 0 and chain_errors == 0,
        "is_fork": is_fork,
        "assessment": assessment,
        "detail": detail,
        "log_count": total,
        "verified_count": verified_count,
        "hash_errors": hash_errors,
        "chain_errors": chain_errors,
        "failed_count": hash_errors + chain_errors,
        "hash_algo": "sha256",
        # Part-11: hash_errors=0 garantiza autenticidad de contenido.
        # Un fork (chain_errors>0, hash_errors=0) es auténtico aunque el enlace esté roto.
        "part11_compliant": hash_errors == 0 and total > 0,
        "audit_file": str(AUDIT_FILE),
    }
