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
layer9_decision_store_migrated, layer9_decision_store_migration_reverted,
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
import pwd
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path(__file__).parent.parent / "audit" / "factory_audit.jsonl"
FORK_BASELINE_FILE = Path(__file__).parent.parent / "audit" / "fork_baseline.json"

# --- W5 V2 G7 — medidas preventivas §4.2 del AUDIT_FORK_REMEDIATION_SPEC -----
#
# Un evento perdido es peor que una excepción: si `write_event` no logra
# escribir, el fallo tiene que dejar rastro FUERA de la cadena que no pudo
# tocar. De ahí este fichero, que no está encadenado a propósito — encadenar el
# registro de "no pude encadenar" es circular.
AUDIT_WRITE_FAILURES_FILE = Path(__file__).parent.parent / "logs" / "audit_write_failures.log"

# Nunca escribir sin lock. Agotados los reintentos se falla ruidosamente.
LOCK_TIMEOUT_SECONDS = 5.0
LOCK_RETRIES = 3
_LOCK_POLL_SECONDS = 0.05

# Guardia de escritor único: identifica a QUIÉN escribió cada entrada. Van en
# el cuerpo HASHEADO, no en `data`: una identidad de escritor que se pueda
# editar sin invalidar el hash no prueba nada.
WRITER_IDENTITY_FIELDS = ("writer_pid", "writer_host", "writer_identity")

_last_entry_hash: str | None = None


class AuditLockError(RuntimeError):
    """No se pudo tomar el lock exclusivo. No se escribió nada."""

# --- W5 V2 G1.14 — reporte por dimensión ------------------------------------
#
# `verify_chain()` colapsaba tres cosas distintas en un booleano y producía
# esto sobre la cadena real:
#
#     {"verified": false, ..., "part11_compliant": true}
#
# El sistema se declaraba conforme a Part 11 sobre una cadena que él mismo
# reportaba como no verificada.
#
# La regla anterior —"fork concurrente ⇒ contenido auténtico ⇒ Part-11
# cumplido"— era CORRECTA en su análisis técnico y EQUIVOCADA en su
# conclusión. Que el contenido sea auténtico es *una* de las condiciones de
# Part 11 (§11.10(e)); la continuidad verificable de la secuencia es otra, y
# está rota. Un sistema no puede firmar su propio certificado de cumplimiento,
# y menos sobre la dimensión que él mismo reporta como fallida.
#
# `part11_compliant` pasa de `bool` a uno de los tres valores de abajo.
# Cambiar el TIPO es deliberado: obliga a que cada lector actual se revise, en
# vez de seguir tratando el valor como un `bool` que ahora mentiría al revés
# (`"NOT_DETERMINED"` es truthy). Los dos lectores que ramificaban por
# veracidad —`api/routes/status.py` y `ui/js/mission_control/dash.js`— se
# corrigieron en esta misma fase.

CONTENT_HASH_INTEGRITY_VERIFIED = "VERIFIED"
CONTENT_HASH_INTEGRITY_COMPROMISED = "COMPROMISED"

CHAIN_CONTINUITY_VERIFIED = "VERIFIED"
CHAIN_CONTINUITY_BROKEN_HISTORICAL = "BROKEN_HISTORICAL"
CHAIN_CONTINUITY_BROKEN_NEW = "BROKEN_NEW"
CHAIN_CONTINUITY_ACCEPTED = "ACCEPTED_WITH_DOCUMENTED_EXCEPTION"

PART11_NOT_DETERMINED = "NOT_DETERMINED"
PART11_ACCEPTED_WITH_EXCEPTION = "ACCEPTED_WITH_DOCUMENTED_EXCEPTION"
PART11_COMPLIANT = "COMPLIANT"

PART11_VALUES = (PART11_NOT_DETERMINED, PART11_ACCEPTED_WITH_EXCEPTION,
                 PART11_COMPLIANT)

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
    # W5 V2 G1 -- migracion de los dos almacenes historicos al modelo unico.
    # La reversion tiene su propio evento: revertir es un hecho tan real como
    # migrar, y el evento de migracion NUNCA se borra de la cadena.
    "layer9_decision_store_migrated", "layer9_decision_store_migration_reverted",
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
    # G3 (W5V2_REGULATORY_REDESIGN) — hermano de broken_link_report para
    # "URL viva pero tipo de artefacto equivocado" (comparable=False)
    "regulatory_artifact_type_mismatch_report_generated",
    "regulatory_source_url_updated",
    # SOURCE_CURRENCY (2026-08-05) — apply_source_currency_confirmation()
    # escribe regulatory_currency_status; único evento agregado por decisión.
    "regulatory_source_currency_confirmed",
    # W5 V2 — alta gobernada de una fuente regulatoria NUEVA
    # (human_source_registration). Distinto de _url_updated: aquel modifica una
    # fuente existente, este ingiere la copia canónica y crea la entrada.
    "regulatory_source_registered",
    # G3 (2026-08-03) — re-gobernanza del ARTEFACTO CANONICO de una fuente ya
    # existente (human_source_regovernance). Distinto de _url_updated (solo
    # URL/hash-original, canonical_path nunca cambia) y de _registered (fuente
    # nueva): este cambia el tipo de artefacto de una fuente que ya existe.
    "regulatory_source_regoverned",
    # W5V2-ARQ (2026-08-07) — apply_source_origin_verification() promueve
    # official_origin_status FIRST_INGESTION -> VERIFIED_AGAINST_PRIOR_KNOWN_HASH
    # sobre una segunda reingesta real (source_currency_log.jsonl) que coincide
    # con el mismo origen ya gobernado. Distinto de _source_currency_confirmed
    # (ese declara vigencia normativa; este declara procedencia del archivo).
    "regulatory_source_origin_verified",
    # W5V2-ARQ (2026-08-07) -- apply_corpus_authorization() registra el
    # go/no-go de corrida atado al run_fingerprint exacto (plan Bloque 6).
    "corpus_authorization_applied",
    # W5V2-ARQ (2026-08-07) -- corpus_runner.run_corpus_batch(): resumen de
    # UN lote de la corrida real del corpus (documento x agente), incluida
    # la razon de parada (corpus completo / hard stop / fallo tecnico).
    # Cada llamada individual a Ollama YA queda en su propio evento via
    # evaluate_chunked()'s _write_audit_event() -- este es el resumen de
    # nivel de lote, no una duplicacion de esa cadena.
    "corpus_run_batch_completed",
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
    # W5 V2 G4c — único punto de escritura del bump de version_record de un
    # artefacto gobernado (factory/core/artifact_version_apply.py). Distinto
    # de layer9_decision_recorded: aquel registra la DECISION (propose/
    # confirm, sin efecto), este es el efecto real que la decisión autorizó.
    "artifact_version_applied",
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


def writer_identity() -> dict:
    """Quién está escribiendo: proceso, host e identidad de SO.

    Las tres juntas, y no una sola, porque los escritores reales de esta cadena
    tienen identidades de SO DISTINTAS: el host escribe como `ing_cpmo` y el
    contenedor `factory-api` como `root`, sobre el mismo inodo a través del
    bind-mount. Con solo el pid no se distinguen dos procesos de contenedores
    diferentes; con solo el usuario, no se distingue un script ad-hoc del
    servidor.
    """
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
    except Exception:  # noqa: BLE001 -- uid sin entrada en passwd (contenedores)
        user = f"uid:{os.getuid()}"
    return {
        "writer_pid": os.getpid(),
        "writer_host": socket.gethostname(),
        "writer_identity": f"{user}@uid:{os.getuid()}",
    }


def _report_write_failure(reason: str, detail: str) -> None:
    """Deja rastro de un fallo de escritura en stderr Y en fichero.

    §4.2: `write_event` nunca debe fallar en silencio. Antes devolvía
    `{"error": ...}` y muchos llamadores no miran el retorno, así que un evento
    perdido no dejaba ni una línea en ninguna parte.

    Este reporte es best-effort por construcción y NO propaga: se lo llama
    desde la ruta de error, y una excepción aquí taparía justo el fallo que se
    intenta hacer visible. stderr va primero para que quede algo aunque el
    fichero sea inescribible — que es uno de los modos de fallo posibles.
    """
    stamp = datetime.now(timezone.utc).isoformat()
    line = json.dumps({"timestamp": stamp, "reason": reason, "detail": detail,
                       **writer_identity()},
                      separators=(",", ":"), ensure_ascii=False)
    try:
        print(f"AUDIT WRITE FAILURE {line}", file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001
        pass
    try:
        AUDIT_WRITE_FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_WRITE_FAILURES_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def _acquire_lock(lock_fh, *, timeout: float = LOCK_TIMEOUT_SECONDS,
                  retries: int = LOCK_RETRIES) -> None:
    """Lock exclusivo con timeout y reintentos. Nunca escribir sin lock.

    `LOCK_EX` bloqueante esperaba PARA SIEMPRE: un lock huérfano —y hubo uno,
    creado por root con modo 644 mientras el host escribía como 1001— colgaba
    al escritor sin decir nada. Un cuelgue silencioso y un evento perdido en
    silencio son el mismo defecto con dos caras.

    Agotados los reintentos se lanza `AuditLockError` y NO se escribe. Escribir
    sin lock reintroduciría exactamente la condición que produjo el fork.
    """
    last_error: OSError | None = None
    for _ in range(max(1, retries)):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError as e:  # EACCES / EAGAIN -- lo tiene otro
                last_error = e
                time.sleep(_LOCK_POLL_SECONDS)
    raise AuditLockError(
        f"lock no adquirido tras {retries} intentos de {timeout}s "
        f"({last_error}) — no se escribió el evento"
    )


def write_event(event_type: str, project_id: str, data: dict | None = None) -> dict:
    """
    Registra un evento en factory_audit.jsonl.
    Retorna la entrada escrita. Nunca lanza excepción (mismo patrón que app/audit.py).

    "Nunca lanza" se conserva —hay llamadores en rutas de API que dependen de
    ello— pero desde G7 ya NO significa "en silencio": todo fallo se reporta a
    stderr y a `audit_write_failures.log` antes de devolver `{"error": ...}`.
    """
    global _last_entry_hash
    if event_type not in VALID_EVENTS:
        raise ValueError(f"Evento desconocido: {event_type}. Válidos: {VALID_EVENTS}")
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive lock para serializar escrituras concurrentes (local + container)
        lock_path = AUDIT_FILE.with_suffix(".lock")
        with open(lock_path, "a") as lock_fh:
            _acquire_lock(lock_fh)
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
                    **writer_identity(),
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
        _report_write_failure(type(e).__name__, f"{event_type}/{project_id}: {e}")
        return {"error": str(e)}


def verify_chain(*, decision_store_file: Path | None = None) -> dict:
    """
    Verifica la integridad de factory_audit.jsonl.

    `decision_store_file` solo dice CONTRA QUE ALMACEN se resuelven las
    excepciones firmadas; la cadena leida es siempre la real. Sin el,
    `get_state(store_file=X)` mezclaba dos almacenes —cobertura del indicado y
    excepciones del real— y en un almacen de prueba con la excepcion firmada G7
    seguia sin cerrar. En produccion nunca se pasa y no cambia nada; el defecto
    solo asomaba donde se mide, que es justo donde peor sienta.

    `assessment` conserva su semántica operativa (OK/WARN/FAIL) por
    retrocompatibilidad, pero **no es la conclusión regulatoria**: esa vive en
    las cinco dimensiones que añade `_dimensions()`, y `part11_compliant` es
    ahora un enum, nunca un booleano.

    Regla SUPERSEDED: *"fork concurrente ⇒ WARN con part11_compliant=true;
    contenido auténtico, Part-11 cumplido"*. Lo que esa regla debió producir
    es "contenido auténtico, continuidad rota, conformidad no determinada".
    """
    if not AUDIT_FILE.exists():
        return {
            "verified": True, "is_fork": False, "assessment": "OK",
            "detail": "Archivo de auditoría no existe aún.",
            "log_count": 0, "verified_count": 0,
            "hash_errors": 0, "chain_errors": 0, "failed_count": 0,
            "hash_algo": "sha256",
            **_dimensions(0, 0, 0,
                          decision_store_file=decision_store_file),
            "audit_file": str(AUDIT_FILE),
        }

    walk = _walk_chain(AUDIT_FILE)
    total = walk["total"]
    verified_count = walk["verified_count"]
    hash_errors = walk["hash_errors"]
    chain_errors = walk["chain_errors"]

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
        **_dimensions(hash_errors, chain_errors, total,
                      break_ids=walk["break_ids"],
                      decision_store_file=decision_store_file),
        "audit_file": str(AUDIT_FILE),
    }


# ---------------------------------------------------------------------------
# Recorrido único de la cadena
# ---------------------------------------------------------------------------

def _walk_chain(path: Path) -> dict:
    """Recorre la cadena UNA vez y devuelve todo lo que se puede saber de ella.

    Existe porque `verify_chain()` y `chain_break_entry_ids()` respondían la
    misma pregunta —"¿dónde se rompe el enlace?"— con dos bucles distintos.
    Dos implementaciones de la misma regla en el mismo módulo acaban
    divergiendo, y aquí divergir significa que las dimensiones dirían una cosa
    y el conteo otra. De paso, recorrer 21 000 entradas una vez en lugar de
    dos.

    Distingue las dos patologías, que NO son la misma:
      - hash de contenido incorrecto  => corrupción. No cuenta como fork y no
        es exceptuable por diseño.
      - enlace `prev_entry_hash` roto => fork. Es lo que un humano puede
        aceptar con una excepción documentada.
    """
    if not path.exists():
        return {"total": 0, "verified_count": 0, "hash_errors": 0,
                "chain_errors": 0, "break_ids": ()}

    verified_count = hash_errors = chain_errors = 0
    breaks: list[str] = []
    prev_hash = "GENESIS"
    total = 0

    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        total += 1
        try:
            entry = json.loads(raw)
        except Exception:  # noqa: BLE001 -- ilegible: corrupción, no fork
            hash_errors += 1
            continue

        stored_hash = entry.get("entry_hash", "")
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        if stored_hash != f"sha256:{_compute_entry_hash(body)}":
            hash_errors += 1
            prev_hash = stored_hash
            continue

        if entry.get("prev_entry_hash") != prev_hash:
            chain_errors += 1
            # Sin `entry_id` no hay nada que un humano pueda firmar. Se declara
            # con un id sintético en vez de omitirse: una ruptura invisible
            # para el gate es exactamente lo que este módulo evita.
            breaks.append(entry.get("entry_id") or f"<sin entry_id:{stored_hash}>")
        else:
            verified_count += 1

        prev_hash = stored_hash

    return {"total": total, "verified_count": verified_count,
            "hash_errors": hash_errors, "chain_errors": chain_errors,
            "break_ids": tuple(breaks)}


# ---------------------------------------------------------------------------
# Baseline de forks conocidos y detección de forks NUEVOS
# ---------------------------------------------------------------------------

def load_fork_baseline(baseline_file: Path | None = None) -> dict:
    """Lee `fork_baseline.json`. Fail-closed: ilegible == baseline vacío.

    Un baseline vacío no silencia nada -- al contrario, hace que TODO fork
    detectado cuente como nuevo. Degradar hacia "no conozco ninguno" es el
    lado seguro; degradar hacia "los conozco todos" sería una alfombra.
    """
    path = baseline_file or FORK_BASELINE_FILE
    if not path.is_file():
        return {"known_forks": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"known_forks": []}
    if not isinstance(data, dict) or not isinstance(data.get("known_forks"), list):
        return {"known_forks": []}
    return data


def known_fork_entry_ids(baseline_file: Path | None = None) -> tuple[str, ...]:
    baseline = load_fork_baseline(baseline_file)
    return tuple(f.get("entry_id") for f in baseline["known_forks"] if f.get("entry_id"))


def new_forks_since_baseline(audit_file: Path | None = None,
                             baseline_file: Path | None = None) -> tuple[str, ...]:
    """Forks detectados que NO están en el baseline, por `entry_id`. Read-only.

    Se identifican por `entry_id` y no por número de línea: si el fichero se
    rota, la línea cambia y el evento no.
    """
    known = set(known_fork_entry_ids(baseline_file))
    return tuple(eid for eid in chain_break_entry_ids(audit_file) if eid not in known)


def unbacked_known_forks(baseline_file: Path | None = None, *,
                         decision_store_file: Path | None = None) -> tuple[str, ...]:
    """`known_forks` del baseline SIN una decisión AUDIT_EXCEPTION que los cubra.

    Es lo que impide que el baseline se convierta en una alfombra: no se puede
    silenciar un fork editando el JSON. El fichero se valida contra las
    excepciones REGISTRADAS, y un `known_fork` sin decisión que lo respalde es
    una señal de FAIL para Gate 0, no una aceptación.

    Import local a propósito, y por DOS razones. La primera es el ciclo:
    `audit_writer` es dependencia de casi todo y el resolver importa
    `decision_store_v2`. La segunda la destapó Gate 0: `schema_loader` exige
    `jsonschema` de forma fail-closed al importarse, y `verify_chain()` se
    llama desde `factory_selfcheck.sh` y `factory_status.sh` con el `python3`
    del SISTEMA, que no lo tiene. Con el import a nivel de módulo, preguntar
    por la integridad de la cadena empezaba a reventar en los dos scripts que
    más falta hace que funcionen.

    De ahí que se capture también el fallo de import: verificar la cadena es
    una lectura fundacional y no puede depender de que una dependencia de
    gobernanza esté instalada. Los cuatro campos que esos scripts leen
    (`verified`, `log_count`, `hash_errors`, `chain_errors`) no tocan el
    resolver en absoluto.
    """
    known = known_fork_entry_ids(baseline_file)
    try:
        from factory.core import decision_scope_resolver as _resolver
        return tuple(
            eid for eid in known
            if not _resolver.is_authorized("AUDIT_EXCEPTION", eid,
                                           store_file=decision_store_file)
        )
    except Exception:  # noqa: BLE001 -- import roto, familias inválidas, etc.
        # No se puede DEMOSTRAR ninguna excepción, así que ninguna cuenta. Se
        # degrada hacia "todos sin respaldo": el lado seguro, porque nunca
        # puede sobre-reportar conformidad. Lo contrario -- asumir que están
        # aceptados -- convertiría una dependencia ausente en una absolución.
        return known


def _dimensions(hash_errors: int, chain_errors: int, total: int, *,
                break_ids: tuple[str, ...] | None = None,
                audit_file: Path | None = None,
                baseline_file: Path | None = None,
                decision_store_file: Path | None = None) -> dict:
    """Las cinco dimensiones de §1.2. NINGUNA se deriva de otra.

    `CONTENT_HASH_INTEGRITY = VERIFIED` es una buena noticia real y debe poder
    decirse sin que arrastre una conclusión de conformidad.

    `break_ids` lo pasa `verify_chain()` desde su propio recorrido para no
    recorrer la cadena dos veces. Si no se pasa, se calcula.
    """
    content = (CONTENT_HASH_INTEGRITY_VERIFIED if hash_errors == 0
               else CONTENT_HASH_INTEGRITY_COMPROMISED)

    if break_ids is None:
        break_ids = chain_break_entry_ids(audit_file)
    known = set(known_fork_entry_ids(baseline_file))
    new_forks = tuple(eid for eid in break_ids if eid not in known)
    unbacked = unbacked_known_forks(baseline_file,
                                    decision_store_file=decision_store_file)
    historical_present = bool(known_fork_entry_ids(baseline_file)) and chain_errors > 0

    if chain_errors == 0:
        continuity = CHAIN_CONTINUITY_VERIFIED
    elif new_forks:
        continuity = CHAIN_CONTINUITY_BROKEN_NEW
    elif unbacked:
        continuity = CHAIN_CONTINUITY_BROKEN_HISTORICAL
    else:
        continuity = CHAIN_CONTINUITY_ACCEPTED

    # PART11_COMPLIANCE. `hash_errors > 0` NO es exceptuable por diseño: es
    # corrupción de contenido, no de enlace, y ninguna firma humana la
    # convierte en otra cosa.
    if hash_errors > 0 or total == 0:
        part11 = PART11_NOT_DETERMINED
    elif chain_errors == 0:
        part11 = PART11_COMPLIANT
    elif continuity == CHAIN_CONTINUITY_ACCEPTED:
        part11 = PART11_ACCEPTED_WITH_EXCEPTION
    else:
        part11 = PART11_NOT_DETERMINED

    return {
        "content_hash_integrity": content,
        "chain_continuity": continuity,
        "historical_fork_present": historical_present,
        "new_forks_since_baseline": len(new_forks),
        "new_fork_entry_ids": list(new_forks),
        "unbacked_known_fork_entry_ids": list(unbacked),
        # Conserva el NOMBRE por retrocompatibilidad de acceso y cambia el
        # TIPO para que ningún lector lo siga tratando como bool sin enterarse.
        "part11_compliant": part11,
    }


def chain_break_entry_ids(audit_file: Path | None = None) -> tuple[str, ...]:
    """`entry_id` de cada entrada cuyo `prev_entry_hash` no enlaza. Read-only.

    `verify_chain()` cuenta las rupturas pero no dice CUALES son, y contar no
    basta para gobernarlas: una excepcion humana se firma sobre un evento
    concreto (familia AUDIT_EXCEPTION, target_kind=audit_event_id), no sobre
    un numero. Esto es lo que consume el gate G15 (W5 V2 G1.11).

    Solo reporta rupturas de ENLACE. Una entrada con hash de contenido malo no
    es un fork: es corrupcion, no se gobierna con una excepcion, y por eso no
    aparece en esta lista.
    """
    return _walk_chain(audit_file or AUDIT_FILE)["break_ids"]


# ---------------------------------------------------------------------------
# Guardia de escritor único (§4.2, medida 2)
# ---------------------------------------------------------------------------

def writer_identity_audit(audit_file: Path | None = None) -> dict:
    """¿Hay alguna entrada escrita FUERA de `write_event()`? Read-only.

    El riesgo residual que cierra esta medida no es el fork —ese ya lo cierra el
    lock— sino un escritor que no pase por `write_event()` en absoluto: un
    script ad-hoc, un `echo >>`, una edición manual. Ese escritor no toma el
    lock, así que ninguna cantidad de locking lo detecta. Lo que sí lo delata es
    que no sabe poner los tres campos de identidad, y no puede falsificarlos sin
    invalidar el `entry_hash`.

    **El ancla se DERIVA, no se declara.** Es la primera entrada del fichero que
    trae los tres campos. Un ancla en un JSON editable a mano permitiría
    esconder entradas moviéndola hacia delante; una derivada, no: si aparece una
    entrada sin identidad DESPUÉS de la primera que la trae, sale reportada, y
    la única forma de mover el ancla es borrar entradas — que rompe la cadena y
    lo detecta `_walk_chain`.

    Las entradas anteriores al ancla son las 21 000 escritas antes de que
    existiera la medida. No son violaciones y no se cuentan como tales:
    reportarlas dejaría el indicador en rojo permanente por historia, y un
    indicador que nunca puede estar verde deja de leerse.
    """
    path = audit_file or AUDIT_FILE
    if not path.exists():
        return {"guard_live": False, "anchor_entry_id": None,
                "anchor_timestamp": None, "entries_after_anchor": 0,
                "missing_writer_identity_ids": []}

    anchor_id = anchor_ts = None
    after = 0
    missing: list[str] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except Exception:  # noqa: BLE001 -- ilegible: lo reporta _walk_chain
            continue

        complete = all(entry.get(f) not in (None, "") for f in WRITER_IDENTITY_FIELDS)
        if anchor_id is None:
            if complete:
                anchor_id = entry.get("entry_id")
                anchor_ts = entry.get("timestamp")
                after = 1
            continue

        after += 1
        if not complete:
            missing.append(entry.get("entry_id") or f"<sin entry_id:{entry.get('entry_hash','')}>")

    return {"guard_live": anchor_id is not None,
            "anchor_entry_id": anchor_id,
            "anchor_timestamp": anchor_ts,
            "entries_after_anchor": after,
            "missing_writer_identity_ids": missing}


# ---------------------------------------------------------------------------
# Estado de las medidas preventivas (§7 del paquete de excepción)
# ---------------------------------------------------------------------------
#
# Se DERIVA. La versión anterior de esta lista vivía como un array de literales
# `ok:false` en `governance.js`, para que un humano los fuera flipando a mano
# según creyera. Ese es el mismo defecto que ya apareció en el guard de riesgos
# (`ecc7fa6`): fotografiar el mundo en vez de medir la regla. Aquí el precio
# sería peor — el botón "Aceptar" del panel G7 depende de esta lista, así que un
# `true` escrito a mano habilita una firma regulatoria sobre una prevención que
# podría no existir.
#
# Dos clases de evidencia, etiquetadas y NO equivalentes:
#   DERIVED_FROM_CHAIN  — medido sobre la cadena real. Es prueba.
#   SOURCE_INSPECTION   — el código/gate contiene la regla. Prueba que está
#                         escrita, no que se ejecute; de eso responden los tests
#                         F-10, F-11 y F-13, que sí la ejecutan.

EVIDENCE_DERIVED = "DERIVED_FROM_CHAIN"
EVIDENCE_SOURCE = "SOURCE_INSPECTION"

_SELFCHECK_FILE = Path(__file__).parent.parent / "scripts" / "ops" / "factory_selfcheck.sh"


def _cache_invalidation_is_inside_the_lock() -> bool:
    """La línea que cierra la causa raíz, en su sitio y en ese orden.

    No es el `flock` lo que arregla §3.2 —el segundo escritor habría tomado el
    lock sin problema tres minutos después— sino releer la cabeza DENTRO de él.
    Fuera del lock, la invalidación no vale nada.
    """
    try:
        src = Path(__file__).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    body = src.split("def write_event(", 1)[-1].split("\ndef ", 1)[0]
    try:
        i_lock = body.index("_acquire_lock(")
        i_inval = body.index("_last_entry_hash = None")
        i_read = body.index("_get_prev_hash()")
    except ValueError:
        return False
    return i_lock < i_inval < i_read


def _write_event_stamps_identity() -> bool:
    """`write_event` sella los tres campos en el cuerpo hasheado.

    Esta comprobación existe para no crear un abrazo mortal. La versión anterior
    exigía que la cadena ya CONTUVIERA una entrada con identidad, y eso se muerde
    la cola: las entradas nuevas las produce la actividad gobernada, y la
    actividad que faltaba era justo la firma que esta medida bloquea. Prevención
    implementada y prevención ya ejercitada no son lo mismo; lo que hay que
    exigir antes de firmar es la primera.

    La violación —una entrada SIN identidad después del ancla— sigue midiéndose
    sobre la cadena real, que es donde se puede medir.
    """
    try:
        src = Path(__file__).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    body = src.split("def write_event(", 1)[-1].split("\ndef ", 1)[0]
    return "**writer_identity()" in body


def _write_failures_are_reported() -> bool:
    """La ruta de error reporta antes de devolver, y el lock falla en vez de seguir."""
    try:
        src = Path(__file__).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    body = src.split("def write_event(", 1)[-1].split("\ndef ", 1)[0]
    reports = "_report_write_failure(" in body and "return {\"error\"" in body
    raises = "raise AuditLockError(" in src
    return reports and raises


def _gate0_fails_on_new_forks() -> bool:
    """Gate 0 trata un fork NUEVO como FAIL, no como WARN."""
    try:
        src = _SELFCHECK_FILE.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    block = src.split("_verdict_audit_chain()", 1)[-1].split("\n}", 1)[0]
    return "fork(s) NUEVO(s)" in block and "ko " in block


def _baseline_is_validated_against_decisions() -> bool:
    """El baseline se contrasta contra las excepciones REGISTRADAS.

    Que `unbacked_known_forks()` exista no basta: degrada a "todos sin respaldo"
    si el resolver no se puede importar, y en ese modo el fichero no está siendo
    validado contra nada — solo se está negando todo. Se exige que el resolver
    responda de verdad.
    """
    if not load_fork_baseline().get("known_forks"):
        return False
    try:
        from factory.core import decision_scope_resolver as _resolver
        _resolver.is_authorized("AUDIT_EXCEPTION", "<probe:no-such-entry-id>")
        return True
    except Exception:  # noqa: BLE001
        return False


def preventive_measures(audit_file: Path | None = None) -> list[dict]:
    """Las 5 medidas de §7 del paquete de excepción, con su estado real.

    Es lo que gobierna el botón "Aceptar" del panel G7: aceptar una excepción
    cuya prevención no está implementada es aceptar que vuelva a pasar.
    """
    wi = writer_identity_audit(audit_file)
    return [
        {
            "id": "flock_and_cache_invalidation",
            "measure": "flock exclusivo + invalidación de caché dentro del lock",
            "implemented": _cache_invalidation_is_inside_the_lock(),
            "evidence_kind": EVIDENCE_SOURCE,
            "evidence": "commit 8c033fa, 27 min después del fork; F-10 y F-11 lo ejecutan",
        },
        {
            "id": "writer_identity_guard",
            "measure": "writer_pid / writer_host / writer_identity por entrada",
            # Sellado (el escritor lo hace) Y sin violaciones (nadie escribió
            # fuera del canal). NO se exige que la cadena ya traiga una entrada
            # sellada: eso se muerde la cola, porque las entradas nuevas las
            # produce la actividad que esta medida bloquea.
            "implemented": (_write_event_stamps_identity()
                            and not wi["missing_writer_identity_ids"]),
            "evidence_kind": EVIDENCE_DERIVED,
            "evidence": (
                f"write_event sella los 3 campos; ancla {wi['anchor_entry_id']} "
                f"({wi['anchor_timestamp']}), {wi['entries_after_anchor']} entradas "
                f"desde el ancla, {len(wi['missing_writer_identity_ids'])} sin identidad"
                if wi["guard_live"] else
                "write_event sella los 3 campos; la cadena aún no tiene ninguna "
                "entrada sellada, así que no hay violaciones que medir"
            ),
        },
        {
            "id": "baseline_validated",
            "measure": "fork_baseline.json validado contra las excepciones registradas",
            "implemented": _baseline_is_validated_against_decisions(),
            "evidence_kind": EVIDENCE_DERIVED,
            "evidence": "unbacked_known_forks() consulta al resolver, que responde",
        },
        {
            "id": "new_forks_fail_gate0",
            "measure": "NEW_FORKS_SINCE_BASELINE > 0 ⇒ FAIL en Gate 0",
            "implemented": _gate0_fails_on_new_forks(),
            "evidence_kind": EVIDENCE_SOURCE,
            "evidence": "_verdict_audit_chain trata el fork nuevo con ko, no con warn",
        },
        {
            "id": "no_silent_write_failure",
            "measure": "write_event nunca falla en silencio",
            "implemented": _write_failures_are_reported(),
            "evidence_kind": EVIDENCE_SOURCE,
            "evidence": (
                "todo fallo va a stderr y a logs/audit_write_failures.log; "
                "el lock agotado lanza AuditLockError y no escribe (F-13)"
            ),
        },
    ]


def preventive_measures_complete(audit_file: Path | None = None) -> bool:
    return all(m["implemented"] for m in preventive_measures(audit_file))
