"""
BATCH_AND_EXCEPTION — revision humana por paquete, no por chunk.

Objetivo (aprobado en diseno, no re-litigar aqui): el sistema genera
automaticamente el documento candidato + informe sin que ningun chunk
individual requiera aprobacion humana; el juicio humano se concentra en las
excepciones HIGH_RISK y en la decision de paquete; la liberacion final es el
unico punto bloqueado. Este modulo implementa las invariantes de servicio (lo
que JSON Schema no puede expresar: cobertura cruzada, resolucion de
referencias, no-circularidad de hashes, unicidad de release) MAS la
formalizacion completa de RegulatoryCitationReference/RemediationChange/
ArtifactReference (ver remediation_package_schemas.py) y escritura segura
(locking por package_id + escritura atomica temp+fsync+rename).

Persistencia (ver factory/services/paths.py):
  remediation_packages/<project_id>/<package_id>/.package.lock            (fcntl.flock, todas las mutaciones)
  remediation_packages/<project_id>/<package_id>/v<version>/state.json
    { package, changes, exceptions, medium_risk_batch_decisions, package_decision }
  remediation_packages/<project_id>/<package_id>/releases.jsonl            (append-only)
  remediation_packages/<project_id>/<package_id>/release_supersessions.jsonl (append-only)

NUNCA reprocesa documentos ni invoca agentes: opera sobre RemediationChange
ya construidos por el motor de chunks/finding-correction existente.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from factory.core.audit_writer import write_event
from factory.services import paths
from factory.services import remediation_directive
from factory.services.remediation_package_schemas import (
    SchemaValidationError,
    validate_artifact_reference,
    validate_remediation_change,
)

# Rebindable a nivel de modulo (no un parametro de create_package): permite
# a los tests inyectar un resolutor sintetico sin acoplar cada RemediationChange
# de prueba a una RemediationDirective real respaldada por un PDF + entrada de
# human_review_queue -- mismo patron ya usado en este archivo para
# paths.REMEDIATION_PACKAGES_BASE/audit_writer.AUDIT_FILE via monkeypatch. En
# produccion (el llamador real es unicamente el endpoint HTTP, ver
# factory/api/routes/remediation_packages.py) resuelve siempre contra
# remediation_directives.jsonl real.
_resolve_directive = remediation_directive.get_directive

# ── Errores ──────────────────────────────────────────────────────────────

class RemediationPackageError(Exception):
    pass


class RemediationPackageNotFound(RemediationPackageError):
    pass


class DuplicateVersionError(RemediationPackageError):
    pass


class InvalidApplicationStatusError(RemediationPackageError):
    pass


class InvalidTransitionError(RemediationPackageError):
    pass


class PackageDecisionAlreadyRecordedError(InvalidTransitionError):
    """W5 V2, Fase P -- distinto de un InvalidTransitionError generico
    (paquete todavia no listo para decision): esta subclase se reserva
    para la doble-aprobacion real (ya existe un package_decision para esta
    version) -- se mapea a HTTP 409 en el router, nunca al 400 generico."""


class MissingJustificationError(RemediationPackageError):
    pass


class UnknownChangeError(RemediationPackageError):
    pass


class InvalidExceptionError(RemediationPackageError):
    pass


class InvalidBatchError(RemediationPackageError):
    pass


class IncompleteExceptionCoverageError(RemediationPackageError):
    pass


class DuplicateReleaseError(RemediationPackageError):
    pass


class MissingDirectiveError(RemediationPackageError):
    """P0 cerrado (verificacion 2026-08-18, hallazgo I de
    VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md): un RemediationChange sin
    directive_id no puede persistirse en un paquete -- ningun
    proposed_content entra al documento candidato sin una
    RemediationDirective real detras (Acto 2, autoria humana)."""


class DirectiveNotFoundError(RemediationPackageError):
    """El directive_id declarado no resuelve a ninguna RemediationDirective
    real en remediation_directives.jsonl."""


class DirectiveNotSubmittedError(RemediationPackageError):
    """La RemediationDirective existe pero su status no es SUBMITTED --
    solo una directiva con proposed_text de autoria humana ya confirmado
    puede respaldar un RemediationChange en un paquete."""


class ReleaseInvariantViolationError(RemediationPackageError):
    pass


class ReleaseNotAuthorizedError(RemediationPackageError):
    """Decisión 2 (2026-08-26): `released_by` no está en la lista de
    identidades autorizadas a liberar (`release_authorization.
    is_authorized_to_release()`). Distinta de un fallo de autenticación
    (eso ya lo resuelve `require_identity` con 401 antes de llegar aquí)
    -- esta es una identidad real y autenticada, pero sin autorización
    específica para este acto."""


class ReleaseFourEyesViolationError(RemediationPackageError):
    """Decisión 2 (2026-08-26): `released_by` coincide con
    `package_decision.decided_by` -- la misma identidad que aprobó el
    paquete no puede además liberarlo. Segregación de funciones exigida
    por Cesar (Capa 9), comparada contra la identidad CANÓNICA resuelta
    por el sistema en ambos actos, nunca contra un nombre visible o un
    string del cliente."""


# ── Cálculo de riesgo/confianza (deterministas, "el peor factor gana") ──────
# CHANGE_RISK: solo factores de contenido/impacto regulatorio. Nunca incluye
# coverage_status/anchor/relevance/schema -- esos alimentan EVALUATION_
# CONFIDENCE, para que una cobertura parcial no convierta todos los cambios
# en HIGH_RISK ni recree revision individual masiva (ver ajuste aprobado).

_CHANGE_RISK_FACTOR_LEVELS = {
    "change_type": {"COSMETIC": 0, "CLARIFICATION": 0, "CONTENT_ADDITION": 1, "CONTENT_REPLACEMENT": 2},
    "requirement_criticality": {"MINOR": 0, "MAJOR": 1, "CRITICAL": 2},
    "gxp_impact": {"NONE": 0, "INDIRECT": 1, "DIRECT_GXP_IMPACT": 2},
    "evidence_status": {"LITERAL_EVIDENCE_CONFIRMED": 0, "PARTIAL_EVIDENCE": 1,
                         "ABSENCE_CONFIRMED": 2, "NO_LITERAL_EVIDENCE": 2},
    "functional_impact": {"DOCUMENTATION_ONLY": 0, "CONFIGURATION_CHANGE": 1, "SYSTEM_BEHAVIOR_CHANGE": 2},
}
_RISK_LEVEL_NAMES = {0: "LOW_RISK", 1: "MEDIUM_RISK", 2: "HIGH_RISK"}

_EVALUATION_CONFIDENCE_FACTOR_LEVELS = {
    "coverage_status": {"FULL_COVERAGE": 0, "PARTIAL_COVERAGE": 1, "GAP_IN_COVERAGE": 2},
    "citation_anchor_status": {"VERIFIED": 0, "UNDER_REVIEW": 1, "NOT_VERIFIED": 2},
    "relevance_status": {"CONFIRMED": 0, "UNDER_REVIEW": 1, "NOT_RELEVANT": 2},
    "schema_validation_status": {"PASSED": 0, "FAILED": 2},
}
_CONFIDENCE_LEVEL_NAMES = {0: "HIGH_CONFIDENCE", 1: "MEDIUM_CONFIDENCE", 2: "LOW_CONFIDENCE"}


def compute_change_risk(factors: dict) -> tuple[str, list[str]]:
    """factors: dict con las 5 claves de _CHANGE_RISK_FACTOR_LEVELS.
    Retorna (change_risk, risk_basis) -- risk_basis lista los factores que
    alcanzaron el nivel maximo, nunca un score ponderado opaco."""
    levels = {}
    for factor, table in _CHANGE_RISK_FACTOR_LEVELS.items():
        value = factors.get(factor)
        if value not in table:
            raise ValueError(f"valor invalido para change_risk factor '{factor}': {value!r}")
        levels[factor] = table[value]
    max_level = max(levels.values())
    basis = sorted(f for f, lvl in levels.items() if lvl == max_level)
    return _RISK_LEVEL_NAMES[max_level], basis


def compute_evaluation_confidence(factors: dict) -> tuple[str, list[str]]:
    """factors: dict con las 4 claves de _EVALUATION_CONFIDENCE_FACTOR_LEVELS.
    Separado de compute_change_risk a proposito: nunca debe usarse para
    escalar change_risk."""
    levels = {}
    for factor, table in _EVALUATION_CONFIDENCE_FACTOR_LEVELS.items():
        value = factors.get(factor)
        if value not in table:
            raise ValueError(f"valor invalido para evaluation_confidence factor '{factor}': {value!r}")
        levels[factor] = table[value]
    max_level = max(levels.values())
    basis = sorted(f for f, lvl in levels.items() if lvl == max_level)
    return _CONFIDENCE_LEVEL_NAMES[max_level], basis


def validate_change_application_status(change: dict) -> None:
    """Invariante: schema FAILED o citation NOT_VERIFIED nunca puede quedar
    APPLIED_TO_DRAFT -- debe quedar NOT_APPLIED/APPLICATION_FAILED (propuesta
    no soportada o excepcion, nunca aplicada silenciosamente al candidato).
    La exigencia de al menos una cita valida para APPLIED_TO_DRAFT vive en
    remediation_package_schemas.validate_remediation_change (ahi se valida
    tambien el CONTENIDO de cada cita, no solo su presencia)."""
    if change.get("candidate_application_status") == "APPLIED_TO_DRAFT":
        if change.get("schema_validation_status") == "FAILED":
            raise InvalidApplicationStatusError(
                f"change '{change.get('change_id')}': schema_validation_status=FAILED "
                "no puede quedar APPLIED_TO_DRAFT")
        if change.get("citation_anchor_status") == "NOT_VERIFIED":
            raise InvalidApplicationStatusError(
                f"change '{change.get('change_id')}': citation_anchor_status=NOT_VERIFIED "
                "no puede quedar APPLIED_TO_DRAFT")


def compute_automatic_evaluation_complete(basis: dict) -> bool:
    """Nunca depende de accion humana -- solo de cobertura/errores de
    ejecucion, mismo principio que coverage_complete del motor de chunks."""
    coverage_by_req = basis.get("coverage_complete_by_requirement", {})
    applicable = basis.get("requirements_applicable", 0)
    full_coverage = len(coverage_by_req) >= applicable and all(coverage_by_req.values())
    return (
        full_coverage
        and basis.get("execution_errors", 0) == 0
        and basis.get("rejected_records", 0) == 0
    )


# ── Persistencia ─────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_dir(project_id: str, package_id: str) -> Path:
    return paths.REMEDIATION_PACKAGES_BASE / project_id / package_id


def _version_dir(project_id: str, package_id: str, package_version: int) -> Path:
    return _package_dir(project_id, package_id) / f"v{package_version}"


def _state_path(project_id: str, package_id: str, package_version: int) -> Path:
    return _version_dir(project_id, package_id, package_version) / "state.json"


def _releases_path(project_id: str, package_id: str) -> Path:
    return _package_dir(project_id, package_id) / "releases.jsonl"


def _supersessions_path(project_id: str, package_id: str) -> Path:
    return _package_dir(project_id, package_id) / "release_supersessions.jsonl"


# ── Locking: un unico lock por package_id serializa TODAS las mutaciones
# (creacion de version, excepciones, decisiones de lote, decision de
# paquete, release y supersesion). Simplifica la correccion (una version N+1
# nunca puede crearse mientras se decide sobre la version N del mismo
# package_id) a costa de concurrencia -- aceptable: esto es un flujo de
# revision humana, no un endpoint de alto throughput. fcntl.flock funciona
# entre procesos (multiples workers) y entre hilos del mismo proceso.

def _lock_file_path(project_id: str, package_id: str) -> Path:
    d = _package_dir(project_id, package_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / ".package.lock"


@contextlib.contextmanager
def _package_lock(project_id: str, package_id: str):
    lock_path = _lock_file_path(project_id, package_id)
    with open(lock_path, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _existing_versions(project_id: str, package_id: str) -> list[int]:
    d = _package_dir(project_id, package_id)
    if not d.exists():
        return []
    out = []
    for p in d.iterdir():
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit():
            out.append(int(p.name[1:]))
    return sorted(out)


def list_packages(project_id: str) -> list[dict]:
    """Paquete 4/K2 (docs_plan/PAQUETE_4_UI_Y_VOCABULARIO_DISENO.md):
    resumen de todos los paquetes de un proyecto -- la ÚLTIMA versión real
    de cada package_id, leída de su state.json real (nunca inventa un
    campo que el estado no tenga). Antes de esto, `remediation.js` solo
    podía "buscar a mano" un (project_id, package_id, version) exacto --
    no existía ninguna forma de saber qué paquetes había.

    Devuelve [] (nunca lanza) si el proyecto no tiene ningún paquete
    todavía -- estado real, no un error."""
    project_dir = paths.REMEDIATION_PACKAGES_BASE / project_id
    if not project_dir.exists():
        return []
    out = []
    for pkg_dir in sorted(p for p in project_dir.iterdir() if p.is_dir()):
        package_id = pkg_dir.name
        versions = _existing_versions(project_id, package_id)
        if not versions:
            continue
        latest = max(versions)
        try:
            state = _read_state(project_id, package_id, latest)
        except RemediationPackageNotFound:
            continue
        p = state["package"]
        changes = p.get("changes") or {}
        pd = state.get("package_decision")
        out.append({
            "project_id": project_id,
            "package_id": package_id,
            "version": latest,
            "other_versions": [v for v in versions if v != latest],
            "status": p.get("status"),
            "risk_counts": {
                "low_risk": len(changes.get("low_risk") or []),
                "medium_risk": len(changes.get("medium_risk") or []),
                "high_risk": len(changes.get("high_risk") or []),
            },
            "automatic_evaluation_complete": p.get("automatic_evaluation_complete"),
            "human_exception_review_complete": p.get("human_exception_review_complete"),
            "package_decision": (
                {"decision": pd.get("decision"), "decided_by": pd.get("decided_by"),
                 "decided_at": pd.get("decided_at")}
                if pd else None
            ),
        })
    return out


def _read_state(project_id: str, package_id: str, package_version: int) -> dict:
    """Lee SIEMPRE state.json (nunca un *.tmp.*) -- un archivo temporal
    huerfano de una escritura interrumpida jamas se confunde con el estado
    real, porque solo os.replace() lo convierte en state.json y esa llamada
    es atomica a nivel de sistema de archivos."""
    p = _state_path(project_id, package_id, package_version)
    if not p.exists():
        raise RemediationPackageNotFound(
            f"package '{package_id}' v{package_version} no encontrado en proyecto '{project_id}'")
    return json.loads(p.read_text(encoding="utf-8"))


def _write_state(project_id: str, package_id: str, package_version: int, state: dict) -> None:
    """Escritura atomica: archivo temporal unico -> flush -> fsync ->
    os.replace (atomico en el mismo filesystem) -> fsync del directorio para
    durabilidad del rename. Recuperacion ante fallo: si el proceso muere
    entre la escritura del temporal y el os.replace, state.json final NUNca
    se toca (sigue siendo la ultima version consistente escrita) y solo
    queda un *.tmp.<uuid> huerfano, que ninguna funcion de lectura considera
    -- se sobreescribe/ignora en el siguiente intento sin intervencion."""
    final_path = _state_path(project_id, package_id, package_version)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.parent / f"state.json.tmp.{uuid.uuid4().hex}"
    payload = json.dumps(state, indent=2, ensure_ascii=False)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, final_path)
    dir_fd = os.open(str(final_path.parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, record: dict) -> None:
    """Escritura completa de una sola linea + fsync. Se invoca SIEMPRE bajo
    _package_lock, asi que no hay interleaving posible entre escritores
    concurrentes (el lock serializa; esta funcion solo garantiza que la
    linea llega a disco antes de soltar el lock)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _artifacts_integrity_ok(artifacts: dict) -> bool:
    return bool(artifacts) and all(a.get("sha256") for a in artifacts.values())


# Estados en los que una version todavia admite escritura humana (excepciones,
# lote MEDIUM_RISK). Fuera de este set la version quedo cerrada -- terminal
# (CLOSED_REJECTED/RETURNED_SUPERSEDED) o ya lista para liberar
# (PACKAGE_READY_FOR_RELEASE) -- y es inmutable: ninguna funcion de este
# modulo debe volver a escribir su exceptions/medium_risk_batch_decisions.
_OPEN_FOR_HUMAN_REVIEW_STATUSES = {"AWAITING_HUMAN_EXCEPTION_REVIEW", "AWAITING_PACKAGE_DECISION"}


def _require_open_for_review(pkg: dict, package_id: str, package_version: int) -> None:
    if pkg["status"] not in _OPEN_FOR_HUMAN_REVIEW_STATUSES:
        raise InvalidTransitionError(
            f"package '{package_id}' v{package_version} en estado '{pkg['status']}' es inmutable "
            "-- no admite nuevas excepciones ni decisiones de lote")


# ── Generación automática (sin revisión por chunk) ──────────────────────

def create_package(
    *,
    project_id: str,
    package_id: str,
    package_version: int,
    changes: list[dict],
    artifacts: dict,
    automatic_evaluation_basis: dict,
    generation_commit_sha: str,
    superseded_from: str | None = None,
) -> dict:
    """Crea GENERATED -> AWAITING_HUMAN_EXCEPTION_REVIEW/AWAITING_PACKAGE_DECISION.
    Enteramente automatico: ningun chunk/change individual requiere
    aprobacion aqui. Valida formalmente cada RemediationChange (con sus
    RegulatoryCitationReference) y cada ArtifactReference antes de persistir
    -- fail-closed, nada con forma invalida llega a disco. Bajo
    _package_lock: rechaza reusar un package_version existente Y exige
    versiones estrictamente monotonicas (nunca v2 antes de que exista v1)."""
    for change in changes:
        validate_remediation_change(change)
        validate_change_application_status(change)
        directive_id = change.get("directive_id")
        if not directive_id:
            raise MissingDirectiveError(
                f"change '{change.get('change_id')}': falta directive_id -- todo RemediationChange "
                "debe originarse en una RemediationDirective real (Acto 2, autoria humana) antes de "
                "poder incluirse en un paquete de remediacion")
        directive = _resolve_directive(directive_id)
        if directive is None:
            raise DirectiveNotFoundError(
                f"change '{change.get('change_id')}': directive_id '{directive_id}' no existe en "
                "remediation_directives.jsonl")
        if directive.get("status") != "SUBMITTED":
            raise DirectiveNotSubmittedError(
                f"change '{change.get('change_id')}': directive_id '{directive_id}' tiene "
                f"status={directive.get('status')!r} -- solo una directiva SUBMITTED (autoria humana "
                "ya confirmada) puede respaldar un RemediationChange en un paquete")
    for artifact in artifacts.values():
        validate_artifact_reference(artifact)

    with _package_lock(project_id, package_id):
        existing_versions = _existing_versions(project_id, package_id)
        if package_version in existing_versions:
            raise DuplicateVersionError(
                f"package '{package_id}' v{package_version} ya existe -- el servicio nunca reescribe una version")
        if existing_versions and package_version <= max(existing_versions):
            raise DuplicateVersionError(
                f"package '{package_id}': v{package_version} no es mayor que la version maxima "
                f"existente (v{max(existing_versions)}) -- las versiones son estrictamente monotonicas")
        if not existing_versions and package_version != 1:
            raise DuplicateVersionError(
                f"package '{package_id}': la primera version debe ser v1, se solicito v{package_version}")

        changes_by_id = {c["change_id"]: c for c in changes}
        high_risk = sorted(c["change_id"] for c in changes if c["change_risk"] == "HIGH_RISK")
        medium_risk = sorted(c["change_id"] for c in changes if c["change_risk"] == "MEDIUM_RISK")
        low_risk = sorted(c["change_id"] for c in changes if c["change_risk"] == "LOW_RISK")

        confidence_summary = {"high": 0, "medium": 0, "low": 0}
        _conf_key = {"HIGH_CONFIDENCE": "high", "MEDIUM_CONFIDENCE": "medium", "LOW_CONFIDENCE": "low"}
        for c in changes:
            confidence_summary[_conf_key[c["evaluation_confidence"]]] += 1

        automatic_evaluation_complete = compute_automatic_evaluation_complete(automatic_evaluation_basis)

        package = {
            "package_id": package_id,
            "package_version": package_version,
            "superseded_from": superseded_from,
            "status": "AWAITING_HUMAN_EXCEPTION_REVIEW" if high_risk else "AWAITING_PACKAGE_DECISION",
            "project_id": project_id,
            "artifacts": artifacts,
            "generation_commit_sha": generation_commit_sha,
            "changes": {"low_risk": low_risk, "medium_risk": medium_risk, "high_risk": high_risk},
            "automatic_evaluation_complete": automatic_evaluation_complete,
            "automatic_evaluation_basis": automatic_evaluation_basis,
            "package_evaluation_confidence_summary": confidence_summary,
            # human_exception_review_complete es trivialmente true si no hay
            # high_risk -- no significa que hubo revision humana, significa
            # que no habia nada que revisar individualmente.
            "human_exception_review_complete": not high_risk,
        }

        state = {
            "package": package,
            "changes": changes_by_id,
            "exceptions": {},
            "medium_risk_batch_decisions": {},
            "package_decision": None,
        }
        _write_state(project_id, package_id, package_version, state)

        write_event("candidate_document_created", project_id, {
            "package_id": package_id, "package_version": package_version,
            "sha256": artifacts.get("candidate_document", {}).get("sha256"),
        })
        write_event("remediation_report_created", project_id, {
            "package_id": package_id, "package_version": package_version,
            "sha256": artifacts.get("remediation_report", {}).get("sha256"),
        })
        write_event("remediation_package_generated", project_id, {
            "package_id": package_id, "package_version": package_version,
            "low_risk_count": len(low_risk), "medium_risk_count": len(medium_risk),
            "high_risk_count": len(high_risk),
            "automatic_evaluation_complete": automatic_evaluation_complete,
        })
        return package


# ── Revisión humana al final: excepciones HIGH_RISK + lote MEDIUM_RISK ──────

def record_exception_review(
    *, project_id: str, package_id: str, package_version: int, change_id: str,
    human_review_decision: str, responsible: str, justification: str,
) -> dict:
    """Un registro por HIGH_RISK, individual, justificacion siempre obligatoria."""
    if not justification or not justification.strip():
        raise MissingJustificationError("justification es obligatoria en toda decision humana")

    with _package_lock(project_id, package_id):
        state = _read_state(project_id, package_id, package_version)
        _require_open_for_review(state["package"], package_id, package_version)
        change = state["changes"].get(change_id)
        if change is None:
            raise UnknownChangeError(f"change_id '{change_id}' no existe en v{package_version}")
        if change["change_risk"] != "HIGH_RISK":
            raise InvalidExceptionError(
                f"change '{change_id}' es {change['change_risk']}, solo HIGH_RISK requiere excepcion individual")

        exception_id = f"EXC-{change_id}"
        record = {
            "exception_id": exception_id, "package_id": package_id, "package_version": package_version,
            "change_id": change_id, "change_risk": "HIGH_RISK",
            "human_review_decision": human_review_decision, "responsible": responsible,
            "justification": justification, "status": "REVIEWED", "decided_at": _now_iso(),
        }
        state["exceptions"][exception_id] = record

        high_risk_ids = state["package"]["changes"]["high_risk"]
        reviewed_change_ids = {e["change_id"] for e in state["exceptions"].values() if e["status"] == "REVIEWED"}
        state["package"]["human_exception_review_complete"] = all(cid in reviewed_change_ids for cid in high_risk_ids)
        if state["package"]["human_exception_review_complete"] and state["package"]["status"] == "AWAITING_HUMAN_EXCEPTION_REVIEW":
            state["package"]["status"] = "AWAITING_PACKAGE_DECISION"

        _write_state(project_id, package_id, package_version, state)
        write_event("exception_reviewed", project_id, {
            "package_id": package_id, "package_version": package_version,
            "exception_id": exception_id, "change_id": change_id,
            "human_review_decision": human_review_decision, "responsible": responsible,
        })
        return record


def record_medium_risk_batch_decision(
    *, project_id: str, package_id: str, package_version: int,
    covered_change_ids: list[str], responsible: str, justification: str,
) -> dict:
    """Una sola decision cubre el lote MEDIUM_RISK completo (o un subconjunto
    explicito) -- nunca requiere registro individual por change."""
    if not justification or not justification.strip():
        raise MissingJustificationError("justification es obligatoria en toda decision humana")

    with _package_lock(project_id, package_id):
        state = _read_state(project_id, package_id, package_version)
        _require_open_for_review(state["package"], package_id, package_version)
        medium_set = set(state["package"]["changes"]["medium_risk"])
        invalid = set(covered_change_ids) - medium_set
        if invalid:
            raise InvalidBatchError(f"change_id fuera de medium_risk de esta version: {sorted(invalid)}")

        covered_sha256 = hashlib.sha256(
            json.dumps(sorted(covered_change_ids), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        batch_decision_id = f"BATCH-{covered_sha256[:16]}"
        record = {
            "batch_decision_id": batch_decision_id, "package_id": package_id, "package_version": package_version,
            "covered_change_ids": sorted(covered_change_ids), "covered_set_sha256": covered_sha256,
            "responsible": responsible, "justification": justification, "decided_at": _now_iso(),
        }
        state["medium_risk_batch_decisions"][batch_decision_id] = record
        _write_state(project_id, package_id, package_version, state)
        return record


def _resolve_high_risk_exception_change_ids(state: dict, exception_ids: list[str]) -> set[str]:
    """Invariante corregida: resuelve exception_id -> change_id ANTES de
    comparar contra changes.high_risk (comparar exception_id directamente
    nunca coincide -- son identificadores de distinto espacio)."""
    resolved = set()
    for exc_id in exception_ids:
        exc = state["exceptions"].get(exc_id)
        if exc is None or exc["status"] != "REVIEWED":
            raise IncompleteExceptionCoverageError(f"excepcion '{exc_id}' no existe o no esta REVIEWED")
        resolved.add(exc["change_id"])
    return resolved


def record_package_decision(
    *, project_id: str, package_id: str, package_version: int, decision: str, decided_by: str,
    justification: str, medium_risk_batch_decision_id: str | None = None,
    high_risk_exception_ids: list[str] | None = None,
) -> dict:
    """decision in {APPROVE_CLEAN, APPROVE_WITH_EXCEPTIONS, RETURN_TO_ADJUSTMENTS, REJECT}
    -- RETURN_TO_ADJUSTMENTS cumple la semantica de REQUEST_CHANGES del plan
    W5 V2 (QA_FINAL_PACKAGE_AND_DECISION_SPEC.md), nombre historico
    preservado para no romper datos/tests ya reales.

    W5 V2 Fase P: decided_by se valida con la misma identidad real
    exigida en el resto de la fabrica (test_console_service.validate_run_by
    -- 422 si esta vacio o es un nombre generico reservado). Bajo
    _package_lock: dos llamadas concurrentes sobre el mismo (package_id,
    package_version) nunca producen dos decisiones -- la segunda que
    encuentra un package_decision ya registrado lanza
    PackageDecisionAlreadyRecordedError (409 en el router), distinto de
    un InvalidTransitionError generico por estado prematuro (400)."""
    from factory.services.test_console_service import validate_run_by
    decided_by = validate_run_by(decided_by)

    if not justification or not justification.strip():
        raise MissingJustificationError("justification es obligatoria en toda decision humana")

    with _package_lock(project_id, package_id):
        state = _read_state(project_id, package_id, package_version)
        pkg = state["package"]
        if state.get("package_decision") is not None:
            raise PackageDecisionAlreadyRecordedError(
                f"paquete '{package_id}' v{package_version} ya tiene una decision registrada "
                f"({state['package_decision']['decision_id']}) -- no se admite una segunda decision"
            )
        if pkg["status"] != "AWAITING_PACKAGE_DECISION":
            raise InvalidTransitionError(f"paquete en estado '{pkg['status']}' no admite decision de paquete")

        high_risk_ids = set(pkg["changes"]["high_risk"])
        if decision == "APPROVE_WITH_EXCEPTIONS":
            resolved = _resolve_high_risk_exception_change_ids(state, high_risk_exception_ids or [])
            if resolved != high_risk_ids:
                missing = high_risk_ids - resolved
                extra = resolved - high_risk_ids
                raise IncompleteExceptionCoverageError(
                    f"high_risk_exception_ids no cubre exactamente changes.high_risk "
                    f"(faltantes={sorted(missing)}, sobrantes={sorted(extra)})")

        decision_id = f"DEC-{package_id}-v{package_version}-{uuid.uuid4().hex[:8]}"
        record = {
            "decision_id": decision_id, "package_id": package_id, "package_version": package_version,
            "decision": decision, "decided_by": decided_by, "decided_at": _now_iso(),
            "justification": justification,
            "medium_risk_batch_decision_id": medium_risk_batch_decision_id,
            "high_risk_exception_ids": high_risk_exception_ids or [],
            "decision_origin": "human_confirmed",
        }
        state["package_decision"] = record

        if decision == "REJECT":
            pkg["status"] = "CLOSED_REJECTED"
        elif decision == "RETURN_TO_ADJUSTMENTS":
            pkg["status"] = "RETURNED_SUPERSEDED"
        elif decision in ("APPROVE_CLEAN", "APPROVE_WITH_EXCEPTIONS"):
            ready = (
                pkg["automatic_evaluation_complete"]
                and pkg["human_exception_review_complete"]
                and _artifacts_integrity_ok(pkg["artifacts"])
            )
            if not ready:
                raise InvalidTransitionError(
                    "condiciones de package_ready_for_release no se cumplen "
                    "(evaluacion automatica/revision de excepciones/integridad de artefactos)")
            pkg["status"] = "PACKAGE_READY_FOR_RELEASE"
        else:
            raise InvalidTransitionError(f"decision desconocida: '{decision}'")

        _write_state(project_id, package_id, package_version, state)
        write_event("package_decision_recorded", project_id, {
            "package_id": package_id, "package_version": package_version,
            "decision_id": decision_id, "decision": decision, "decided_by": decided_by,
        })
        return record


# ── Liberación (único punto bloqueado; ReleaseRecord append-only) ──────────

def _effective_release(releases: list[dict], supersessions: list[dict]) -> dict | None:
    superseded_ids = {s["previous_release_id"] for s in supersessions}
    candidates = [r for r in releases if r["release_id"] not in superseded_ids]
    if len(candidates) > 1:
        raise ReleaseInvariantViolationError(
            f"mas de un release vigente detectado: {[c['release_id'] for c in candidates]}")
    return candidates[0] if candidates else None


def get_effective_release(project_id: str, package_id: str) -> dict | None:
    with _package_lock(project_id, package_id):
        releases = _read_jsonl(_releases_path(project_id, package_id))
        supersessions = _read_jsonl(_supersessions_path(project_id, package_id))
        return _effective_release(releases, supersessions)


def create_release_record(
    *, project_id: str, package_id: str, package_version: int, released_by: str,
) -> dict:
    """Unica fuente de RELEASED. Append-only: nunca modifica un ReleaseRecord
    existente. Como mucho uno por (package_id, package_version); como mucho
    un vigente por package_id (el anterior, si existe, se supersede via
    ReleaseSupersessionRecord, nunca se reescribe). Bajo _package_lock: la
    comprobacion de duplicado y el append ocurren en la misma seccion
    critica, asi que dos llamadas concurrentes nunca producen dos releases
    para la misma version.

    Decisión 2 (2026-08-26), dos controles nuevos, en este orden:
    1. `released_by` debe estar en `release_authorization.
       is_authorized_to_release()` -- se verifica ANTES de leer el estado
       del paquete, no requiere ningún dato de él.
    2. Cuatro ojos: `released_by` debe ser DISTINTO de
       `package_decision.decided_by` -- la identidad que aprobó el
       paquete no puede además liberarlo (segregación de funciones
       exigida por Cesar). Ambas identidades ya son las CANÓNICAS
       resueltas por el sistema (`require_identity` en ambos actos),
       nunca un nombre visible ni un string del cliente."""
    from factory.core.release_authorization import is_authorized_to_release
    if not is_authorized_to_release(released_by):
        raise ReleaseNotAuthorizedError(
            f"{released_by!r} no está autorizado a liberar documentos "
            "(release_authorized_identities.yaml)")

    with _package_lock(project_id, package_id):
        state = _read_state(project_id, package_id, package_version)
        pkg = state["package"]
        if pkg["status"] != "PACKAGE_READY_FOR_RELEASE":
            raise InvalidTransitionError(
                f"paquete v{package_version} en estado '{pkg['status']}', no esta PACKAGE_READY_FOR_RELEASE")

        decided_by = state["package_decision"]["decided_by"]
        if released_by == decided_by:
            raise ReleaseFourEyesViolationError(
                f"{released_by!r} ya firmó el PackageDecisionRecord de este paquete -- "
                "la misma identidad no puede además liberarlo, se exige una identidad distinta")

        releases_path = _releases_path(project_id, package_id)
        supersessions_path = _supersessions_path(project_id, package_id)
        releases = _read_jsonl(releases_path)
        supersessions = _read_jsonl(supersessions_path)

        if any(r["package_version"] == package_version for r in releases):
            raise DuplicateReleaseError(f"ya existe un ReleaseRecord para '{package_id}' v{package_version}")

        prior_effective = _effective_release(releases, supersessions)

        release_id = f"REL-{package_id}-v{package_version}-{uuid.uuid4().hex[:8]}"
        record = {
            "release_id": release_id, "package_id": package_id, "package_version": package_version,
            "decision_id": state["package_decision"]["decision_id"],
            "released_by": released_by, "released_at": _now_iso(),
            "release_manifest_sha256": pkg["artifacts"]["package_manifest"]["sha256"],
        }
        _append_jsonl(releases_path, record)

        if prior_effective is not None:
            supersession = {
                "supersession_id": f"SUP-{uuid.uuid4().hex[:8]}", "package_id": package_id,
                "previous_release_id": prior_effective["release_id"], "new_release_id": release_id,
                "recorded_at": _now_iso(), "reason": "change_control_cycle_post_release",
            }
            _append_jsonl(supersessions_path, supersession)

        write_event("document_released", project_id, {
            "package_id": package_id, "package_version": package_version,
            "release_id": release_id, "released_by": released_by,
            "supersedes_release_id": prior_effective["release_id"] if prior_effective else None,
        })
        return record
