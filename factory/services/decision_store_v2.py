"""Almacen UNICO de decisiones de gobernanza — W5 V2, G1.3.

Reemplaza a los dos almacenes previos, que tenian propiedades opuestas y no se
leian entre si (GOVERNANCE_STATE_AUDIT.md §0):

  Sistema A  factory/layer9/decision_log.py + decisions.jsonl
             ids abiertos, ciclo propose/confirm/apply, enforcement REAL en el
             acto de alta, sin superficie humana, identidad solo "no vacia".
  Sistema B  factory/services/w5_human_decisions.py + w5_human_decisions.jsonl
             tupla cerrada de 5, UI en Mission Control, identidad estricta,
             y CERO lectores en todo el arbol.

Part 211 entro por el A y entro bien (Cesar confirmo `caa2421d`); lo que le
falta es cobertura de D1, que vive en el B. Ese es el hueco que este modelo
cierra: un solo almacen, un solo vocabulario, una sola lectura (el resolver).

Reglas duras:
  - Append-only. `status` NUNCA se edita in situ: la proyeccion de vigencia se
    deriva recorriendo el JSONL (`project_status`), y es regenerable desde cero.
  - `resolved_target_ids` SIEMPRE materializada. "ALL" no se almacena jamas.
  - Escribir un registro emite EXACTAMENTE UN evento de auditoria.
  - Identidad generica => 422, con la MISMA funcion para todas las superficies.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from factory.core.audit_writer import write_event
from factory.core import identity_policy as _identity
from factory.regulatory.schema_loader import validate_against
from factory.services import paths

STORE_FILE = paths.FACTORY_ROOT / "layer9" / "decisions" / "decisions_v2.jsonl"
FAMILIES_FILE = paths.FACTORY_ROOT / "registry" / "decision_families.yaml"

SCHEMA_NAME = "decision_record_v1"

# G1.15: la lista vive en factory/core/identity_policy.py, que es el UNICO
# sitio donde se define. G1.1 la habia escrito aqui diciendo "se centraliza
# AQUI" y no se centralizo -- las otras siete superficies siguieron con su
# copia. Se reexporta el nombre para no romper importadores existentes.
RESERVED_IDENTITIES = _identity.RESERVED_IDENTITIES

INSTANCE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*-[0-9]{4}-[0-9]{3}$")

AMENDING_TYPES = frozenset({"CORRECTION", "SUPERSESSION", "REVOCATION"})
COVERING_TYPES = frozenset({"ORIGINAL", "CORRECTION", "ADDENDUM", "SUPERSESSION"})

# Veredictos que OTORGAN cobertura. `decision_type` dice que FORMA tiene el
# registro (original, adendo, correccion); `decision` dice que se resolvio.
# Hacian falta las dos y solo se miraba la primera: hasta G1.15, un registro
# con decision="REJECT" y decision_type="ORIGINAL" pasaba las doce invariantes
# y AUTORIZABA. Un rechazo firmado concedia exactamente lo que rechazaba.
#
# PARTIAL otorga sobre sus `resolved_target_ids` y solo sobre ellos, que es
# justo lo que significa: se aprobo una parte, y la parte esta materializada.
GRANTING_DECISIONS = frozenset({"APPROVE", "PARTIAL"})

W5_PROJECT_ID = "gmpai_document_validation"


class DecisionValidationError(ValueError):
    """422 -- el registro no es valido tal como viene."""


class DecisionConflictError(RuntimeError):
    """409 -- decision_instance_id duplicado."""


class FamiliesRegistryError(RuntimeError):
    """Fallo de despliegue, no de datos: el registro de familias no carga.

    Se lanza a proposito (a diferencia del resolver, que NUNCA lanza): un
    decision_families.yaml ausente o invalido debe impedir el arranque, no
    degradar a "no autorizado" silencioso.
    """


# ---------------------------------------------------------------------------
# Registro de familias
# ---------------------------------------------------------------------------

def load_families() -> dict:
    """Familias declaradas. Fail-closed: cualquier inconsistencia lanza."""
    if not FAMILIES_FILE.is_file():
        raise FamiliesRegistryError(f"registro de familias no encontrado: {FAMILIES_FILE}")
    try:
        data = yaml.safe_load(FAMILIES_FILE.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- se re-lanza tipada
        raise FamiliesRegistryError(f"decision_families.yaml no parsea: {exc}") from exc

    families = (data or {}).get("families")
    if not isinstance(families, dict) or not families:
        raise FamiliesRegistryError("decision_families.yaml no declara `families`")

    known = set((data or {}).get("known_consumers") or [])
    for name, spec in families.items():
        modes = set(spec.get("selection_modes") or [])
        if not modes or not modes <= {"EXPLICIT_LIST", "ALL_SNAPSHOT"}:
            raise FamiliesRegistryError(f"familia {name}: selection_modes invalido: {sorted(modes)}")
        unknown = set(spec.get("consumers") or []) - known
        if unknown:
            raise FamiliesRegistryError(
                f"familia {name}: consumidores no declarados en known_consumers: {sorted(unknown)}"
            )
    return families


def families_registry_hash() -> str:
    return hashlib.sha256(FAMILIES_FILE.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_target_set_hash(target_ids) -> str:
    """sha256 de los ids ordenados y unidos por \\n.

    Deliberadamente simple y reproducible a mano: quien audite debe poder
    recalcularlo con `printf '%s\\n' ... | sha256sum` sin leer este codigo.
    """
    return hashlib.sha256("\n".join(sorted(target_ids)).encode("utf-8")).hexdigest()


def validate_identity(name: str | None) -> str:
    """Delega en la politica unica y traduce a la excepcion de este modulo.

    La traduccion existe porque los llamadores de este almacen ya capturan
    `DecisionValidationError`; cambiarles el tipo de excepcion seria romperlos
    para ganar nada. La REGLA es una sola; solo el envoltorio cambia.
    """
    try:
        return _identity.validate_identity(name, field="approved_by_id")
    except _identity.IdentityValidationError as exc:
        raise DecisionValidationError(str(exc)) from exc


def read_all(store_file: Path | None = None) -> list[dict]:
    """Todos los registros, en orden de escritura. Solo lectura."""
    path = store_file or STORE_FILE
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def next_instance_id(family: str, *, year: int | None = None,
                     store_file: Path | None = None) -> str:
    """Siguiente id derivado de la familia. No es un uuid4 libre (cierra A-10)."""
    yr = year or datetime.now(timezone.utc).year
    prefix = f"{family}-{yr}-"
    used = [
        int(r["decision_instance_id"][len(prefix):])
        for r in read_all(store_file)
        if r.get("decision_instance_id", "").startswith(prefix)
    ]
    return f"{prefix}{(max(used) + 1) if used else 1:03d}"


# ---------------------------------------------------------------------------
# Invariantes I-1..I-12
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecordValidation:
    valid: bool
    violations: tuple[str, ...]


def validate_record(record: dict, *, families: dict | None = None,
                    store_file: Path | None = None,
                    known_instances: set[str] | None = None) -> RecordValidation:
    """Comprueba las invariantes. NO lanza: devuelve el detalle.

    El resolver la usa para marcar registros INVALID sin descartarlos en
    silencio; el escritor la usa para rechazar con 422.

    `known_instances` existe para validar un LOTE cuyos predecesores todavia
    no estan en disco -- el caso de la migracion, donde una CORRECTION y la
    decision que supersede se proyectan en la misma pasada. Sin esto, I-6
    marcaria como rota una cadena que en realidad esta completa.
    """
    v: list[str] = []
    fams = families if families is not None else load_families()

    ok, errors = validate_against(record, SCHEMA_NAME)
    if not ok:
        v.extend(f"I-0 schema: {e}" for e in errors)
        # Sin schema valido el resto de comprobaciones leerian campos ausentes.
        return RecordValidation(False, tuple(v))

    family = record["decision_family"]
    spec = fams.get(family)
    if spec is None:
        v.append(f"I-1: decision_family {family!r} no declarada en decision_families.yaml")
        return RecordValidation(False, tuple(v))

    if record["selection_mode"] not in (spec.get("selection_modes") or []):
        v.append(
            f"I-2: selection_mode={record['selection_mode']} no permitido para {family} "
            f"(permitidos: {spec.get('selection_modes')})"
        )

    # Una familia `never_authorizes` (LEGACY_UNMAPPED) queda exenta de las
    # invariantes que protegen la AUTORIZACION -- I-3 (alcance declarado) e
    # I-8 (identidad real). No es una puerta trasera: el resolver deniega esa
    # familia antes de mirar ningun registro. Su unico proposito es que las 4
    # decisiones historicas que no son de gobernanza del corpus (2 de deploy,
    # agent_design, resolucion de contradicciones) sigan siendo LEGIBLES.
    # Exigirles un alcance que nadie firmo obligaria a inventarselo.
    never_authorizes = bool(spec.get("never_authorizes"))

    targets = record["resolved_target_ids"]
    status = record["status"]
    if not targets and status != "INVALID_PENDING_RESIGNATURE" and not never_authorizes:
        v.append("I-3: resolved_target_ids vacia — una decision ACTIVE debe declarar su alcance")

    if record["target_set_hash"] != compute_target_set_hash(targets):
        v.append("I-4: target_set_hash no recomputa sobre resolved_target_ids")

    dtype = record["decision_type"]
    seq = record["amendment_sequence"]
    if dtype == "ORIGINAL":
        if seq != 0:
            v.append(f"I-5: ORIGINAL exige amendment_sequence=0, trae {seq}")
        if record.get("supersedes_instance_id") or record.get("supersedes_event_id"):
            v.append("I-5: ORIGINAL no puede superseder a nada")

    if dtype in AMENDING_TYPES:
        sup_id = record.get("supersedes_instance_id")
        if not sup_id:
            v.append(f"I-6: {dtype} exige supersedes_instance_id")
        elif known_instances is not None:
            if sup_id not in known_instances:
                v.append(f"I-6: supersedes_instance_id={sup_id!r} no resuelve en el lote")
        elif store_file is not None or STORE_FILE.is_file():
            prev = {r["decision_instance_id"]: r for r in read_all(store_file)}
            target = prev.get(sup_id)
            if target is None:
                v.append(f"I-6: supersedes_instance_id={sup_id!r} no resuelve")
            elif target["decision_family"] != family:
                v.append("I-6: no se puede superseder una decision de OTRA familia")
        if not (record.get("reason") or "").strip():
            v.append(f"I-6: {dtype} exige `reason`")

    if dtype == "ADDENDUM":
        if record.get("supersedes_instance_id") or record.get("supersedes_event_id"):
            v.append("I-7: ADDENDUM amplia, no supersede — no puede referenciar supersedes_*")
        if seq < 1:
            v.append(f"I-7: ADDENDUM exige amendment_sequence>=1, trae {seq}")

    origin = record["decision_origin"]
    if origin == "human_confirmed" and not never_authorizes:
        try:
            validate_identity(record.get("approved_by_id"))
        except DecisionValidationError as exc:
            v.append(f"I-8: {exc}")
    elif origin == "agent_proposed":
        if record.get("approved_by_id"):
            v.append("I-9: agent_proposed no puede traer approved_by_id — una propuesta no firma")

    if record.get("provenance") == "RECONSTRUCTED_SNAPSHOT" and not record.get("reconstruction_evidence"):
        v.append("I-10: RECONSTRUCTED_SNAPSHOT exige reconstruction_evidence")

    if not INSTANCE_ID_RE.match(record["decision_instance_id"]):
        v.append(f"I-11: decision_instance_id {record['decision_instance_id']!r} no tiene la forma <FAMILIA>-<anio>-<nnn>")
    if not record["decision_instance_id"].startswith(family + "-"):
        v.append("I-11: decision_instance_id no empieza por su propia familia")

    return RecordValidation(not v, tuple(v))


# ---------------------------------------------------------------------------
# Proyeccion de vigencia (derivada, nunca almacenada)
# ---------------------------------------------------------------------------

def project_status(records: list[dict]) -> dict[str, str]:
    """decision_instance_id -> status vigente.

    Derivada recorriendo el JSONL. El campo `status` del registro es su estado
    AL ESCRIBIRSE; esta funcion aplica las supersesiones posteriores. Se
    regenera identica desde cero: nada puede depender de una proyeccion
    persistida que no se pueda rederivar.
    """
    status = {r["decision_instance_id"]: r["status"] for r in records}
    for r in records:
        sup = r.get("supersedes_instance_id")
        if not sup or sup not in status:
            continue
        if r["decision_origin"] != "human_confirmed":
            # DEFECTO REAL cerrado en G2: una PROPUESTA superseia.
            #
            # Un registro `agent_proposed` con `supersedes_instance_id` marcaba
            # SUPERSEDED a la decision firmada, asi que proponer una correccion
            # RETIRABA la autorizacion vigente sin que ningun humano confirmara
            # nada. Un agente podia anular una decision de Cesar solo pidiendolo
            # -- la inversion exacta que este sistema existe para impedir.
            #
            # Proponer no cambia la vigencia de nada. Solo una firma humana
            # supersede.
            continue
        if r["decision_type"] in ("CORRECTION", "SUPERSESSION"):
            status[sup] = "SUPERSEDED"
        elif r["decision_type"] == "REVOCATION":
            # La REVOCATION no supersede a la previa: retira ids concretos.
            # La previa sigue ACTIVE; la resta la hace `effective_coverage`.
            pass
    for r in records:
        # Misma regla que arriba, y aqui el agujero era mayor: una SUPERSESSION
        # solo PROPUESTA barria de golpe TODA la familia anterior.
        if (r["decision_type"] == "SUPERSESSION"
                and r["decision_origin"] == "human_confirmed"):
            for other in records:
                if (other["decision_family"] == r["decision_family"]
                        and other["decision_instance_id"] != r["decision_instance_id"]
                        and other["recorded_at"] < r["recorded_at"]):
                    status[other["decision_instance_id"]] = "SUPERSEDED"
    return status


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

@contextmanager
def _exclusive(path: Path):
    """Serializa comprobar-y-escribir sobre el almacen.

    G2.1: sin esto, comprobar el duplicado y escribirlo eran dos pasos con una
    ventana en medio, y el id se habia asignado ANTES leyendo el mismo fichero
    (`build_record` -> `next_instance_id`). Dos peticiones casi simultaneas
    calculaban el MISMO id, las dos veian que aun no existia y las dos
    escribian: I-11 violado en el propio registro de registros, no en teoria.
    Paso en produccion -- D1-2026-017, -018 y -021 estan duplicados, cada par
    con el mismo segundo, hijos de un doble clic.

    El candado va en un fichero aparte y no en el almacen porque el almacen se
    abre en modo append y se lee en otros sitios sin candado; bloquear el
    sidecar no cambia como se lee. Con esto el segundo escritor ve la linea del
    primero y sale con DecisionConflictError, que es un error honesto, en vez
    de duplicar en silencio.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    with lock.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def append_record(record: dict, *, store_file: Path | None = None,
                  emit_audit: bool = True) -> dict:
    """Anade UN registro validado y emite UN evento. Nunca edita lo anterior."""
    path = store_file or STORE_FILE
    families = load_families()

    result = validate_record(record, families=families, store_file=store_file)
    if not result.valid:
        raise DecisionValidationError(
            "registro invalido:\n  - " + "\n  - ".join(result.violations)
        )

    with _exclusive(path):
        # La relectura ocurre DENTRO del candado a proposito: leer fuera es
        # exactamente lo que dejo pasar los duplicados.
        existing = {r["decision_instance_id"] for r in read_all(store_file)}
        if record["decision_instance_id"] in existing:
            raise DecisionConflictError(
                f"decision_instance_id {record['decision_instance_id']!r} ya existe (I-11)"
            )

        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if emit_audit:
        event = write_event("layer9_decision_recorded", W5_PROJECT_ID, {
            "scope": "governance_decision_v2",
            "decision_family": record["decision_family"],
            "decision_instance_id": record["decision_instance_id"],
            "decision_type": record["decision_type"],
            "decision": record["decision"],
            "decision_origin": record["decision_origin"],
            "approved_by_id": record.get("approved_by_id"),
            "target_set_hash": record["target_set_hash"],
            # Se declara explicitamente que registrar no ejecuta.
            "side_effects_applied": False,
        })
        record = {**record, "audit_event_id": event.get("entry_id")}

    return record


def build_record(
    *,
    decision_family: str,
    decision_type: str,
    selection_mode: str,
    resolved_target_ids,
    decision: str,
    decision_origin: str,
    approved_by_id: str | None = None,
    approved_by_display_name: str | None = None,
    proposed_by_id: str | None = None,
    confirms_instance_id: str | None = None,
    supersedes_instance_id: str | None = None,
    supersedes_event_id: str | None = None,
    amendment_sequence: int = 0,
    reason: str = "",
    payload: dict | None = None,
    provenance: str = "NATIVE",
    reconstruction_evidence: dict | None = None,
    status: str = "ACTIVE",
    decision_date: str | None = None,
    recorded_by: str | None = None,
    registry_hash_at_decision: str | None = None,
    decision_instance_id: str | None = None,
    store_file: Path | None = None,
) -> dict:
    """Construye un registro completo y coherente. No escribe."""
    targets = sorted(set(resolved_target_ids))
    now = _now()
    return {
        "schema_version": SCHEMA_NAME,
        "decision_family": decision_family,
        "decision_instance_id": decision_instance_id
            or next_instance_id(decision_family, store_file=store_file),
        "decision_type": decision_type,
        "amendment_sequence": amendment_sequence,
        "supersedes_event_id": supersedes_event_id,
        "supersedes_instance_id": supersedes_instance_id,
        "selection_mode": selection_mode,
        "resolved_target_ids": targets,
        "target_set_hash": compute_target_set_hash(targets),
        "registry_hash_at_decision": registry_hash_at_decision,
        "families_registry_hash": families_registry_hash(),
        "decision": decision,
        "decision_origin": decision_origin,
        "proposed_by_id": proposed_by_id,
        "confirms_instance_id": confirms_instance_id,
        "approved_by_id": approved_by_id,
        "approved_by_display_name": approved_by_display_name,
        "recorded_by": recorded_by,
        "decision_date": decision_date or now,
        "recorded_at": now,
        "reason": reason,
        "status": status,
        "payload": payload or {},
        "provenance": provenance,
        "reconstruction_evidence": reconstruction_evidence,
        "audit_event_id": None,
        "invalid_reason": None,
    }


def resolve_all_snapshot(family: str, *, families: dict | None = None) -> tuple[list[str], str]:
    """Materializa ALL_SNAPSHOT contra el registry vigente. (ids, registry_hash).

    Se llama EN LA FIRMA, nunca en la lectura. Esa es toda la diferencia entre
    este modelo y el anterior: la D1 del 29-jul almaceno la cadena "ALL" y por
    eso nadie pudo decir, dos horas despues, si Part 211 estaba dentro.
    """
    fams = families if families is not None else load_families()
    spec = fams[family]
    rel = spec.get("target_registry")
    if not rel:
        raise DecisionValidationError(
            f"familia {family} no declara target_registry: ALL_SNAPSHOT no es resoluble"
        )
    path = paths.FACTORY_ROOT.parent / rel
    if not path.is_file():
        raise DecisionValidationError(f"target_registry no encontrado: {path}")

    raw = path.read_bytes()
    registry_hash = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)

    id_path = spec.get("target_registry_id_path") or ""
    if id_path.endswith("[].source_id"):
        ids = [s["source_id"] for s in data.get("sources", [])]
    elif id_path == "[].file_id":
        # El allowlist de documentos es una lista plana en la raiz.
        ids = [e["file_id"] for e in (data or [])]
    elif id_path == "requirements{}":
        ids = list((data.get("requirements") or {}).keys())
    else:
        raise DecisionValidationError(
            f"target_registry_id_path no soportado para ALL_SNAPSHOT: {id_path!r}"
        )
    return sorted(ids), registry_hash
