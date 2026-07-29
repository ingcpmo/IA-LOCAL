"""Alta gobernada de una fuente regulatoria NUEVA en `sources/registry.json`.

Brecha que cierra (detectada en el assessment de cobertura del 2026-07-29,
`factory/docs/design/regulatory_redesign_v2/W5V2_D1A_D2A_ADDENDUM_DRAFT.md`
§A.0): `human_source_update.py` solo edita `official_source_url` /
`sha256_original` / `official_source_description` de una fuente **ya
existente**. Dar de alta una fuente nueva no tenia camino gobernado, y el
schema `source_registry_entry_v1` exige `canonical_path` + hashes
coincidentes, asi que tampoco se podia declarar una fuente "sin copia".

Mismo patron de 3 pasos separados y auditables que `human_source_update`:

  propose_source_registration()  -- agent_proposed, NUNCA escribe nada
  confirm_source_registration()  -- human_confirmed, NUNCA escribe nada
  apply_source_registration()    -- UNICA funcion que escribe: ingiere la
                                    copia canonica al almacen inmutable y
                                    anade la entrada al registry

NO-OBJETIVO EXPLICITO: **esta herramienta nunca descarga nada.** El operador
obtiene el documento oficial por una via autorizada y pasa una ruta local. La
decision de descargar es humana y queda fuera de este modulo por diseno: el
codigo no puede juzgar si una URL es la fuente oficial correcta.

Invariantes fail-closed (cada una probada en
`factory/tests/test_human_source_registration.py`):

  1. Un `source_id` ya existente NUNCA se sobrescribe -- el alta es alta, no
     actualizacion; para eso esta `human_source_update`.
  2. El SHA-256 se **calcula sobre el fichero real** y debe coincidir con el
     `sha256_original` declarado por el humano. `hashes_match` se demuestra,
     no se declara (el schema lo fija a `const: true`).
  3. Los campos derivados (`canonical_path`, `sha256_copy`, `hashes_match`,
     `size_bytes`, `copied_at`, `regulatory_currency_status`,
     `derived_artifacts`) NUNCA se aceptan del proponente: los deriva `apply_`.
  4. `regulatory_currency_status` siempre `pending_reverification` -- unico
     valor del enum. Registrar una fuente NO la declara vigente.
  5. `official_origin_status` no puede afirmar verificacion contra un hash
     previo conocido cuando la fuente es nueva y no hay hash previo con el
     que comparar. Es la guarda anti-fabricacion de procedencia.
  6. `version` y `effective_date` deben ser literales del propio documento o
     un `NO_DISPONIBLE (motivo)` con motivo real -- nunca vacios ni asumidos
     (regla del schema, aqui se hace ejecutable).
  7. `supersedes` y `reverification_due` nunca se infieren: `null` es el valor
     honesto mientras no exista decision humana que los fije.
  8. La entrada se valida contra el schema **antes** de tocar el disco. Si no
     valida, no se copia el fichero ni se escribe el registry.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from factory.core.audit_writer import write_event
from factory.layer9 import decision_log
from factory.regulatory.schema_loader import validate_against

ACTION = "regulatory_source_registration"
SCHEMA_NAME = "source_registry_entry_v1"
PROJECT_ID = "gmpai_document_validation"

SOURCES_REGISTRY_FILE = Path(__file__).parent / "sources" / "registry.json"
SOURCES_STORE_DIR = Path(__file__).parent / "sources" / "sha256"

CURRENCY_STATUS = "pending_reverification"

#: Valor honesto de `official_origin_status` para una primera ingesta: no hay
#: hash previo gobernado contra el que comparar, y decir otra cosa seria
#: fabricar procedencia.
FIRST_INGESTION_ORIGIN_STATUS = "FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE"

_PRIOR_HASH_CLAIM = "VERIFIED_AGAINST_PRIOR_KNOWN_HASH"

#: Campos que declara el humano. Todos obligatorios: el schema los exige y
#: ninguno tiene un default honesto que el codigo pueda inventar.
DECLARED_REQUIRED_FIELDS = frozenset({
    "official_source_url",
    "official_source_description",
    "sha256_original",
    "normative_type",
    "jurisdiction",
    "official_origin_status",
    "version",
    "effective_date",
})

#: Opcionales, pero nunca inferidos: si no se pasan, quedan en `None`.
DECLARED_OPTIONAL_FIELDS = frozenset({"supersedes", "reverification_due"})

#: Derivados por `apply_`. Que el proponente los pase es un error, no un
#: valor a respetar -- sobre todo `regulatory_currency_status`, que es la via
#: por la que alguien podria intentar declarar una fuente vigente.
DERIVED_FIELDS = frozenset({
    "canonical_path", "sha256_copy", "hashes_match", "size_bytes",
    "copied_at", "regulatory_currency_status", "derived_artifacts",
    "original_path", "source_id",
})

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_NO_DISPONIBLE_RE = re.compile(r"^NO_DISPONIBLE\s*\(.+\)$", re.DOTALL)
_ISO_DATE_RE = re.compile(r"^\d{4}(-\d{2}){0,2}$")


class HumanSourceRegistrationError(Exception):
    pass


# --------------------------------------------------------------------------
# 1. PROPONER -- no escribe nada, ni siquiera lee el fichero canonico
# --------------------------------------------------------------------------

def propose_source_registration(
    source_id: str,
    canonical_file: str | Path,
    declared: dict,
    rationale: str,
    proposed_by: str = "layer8_agent",
) -> dict:
    """Registra una PROPUESTA (`agent_proposed`) en `decisions.jsonl`.

    No copia el fichero, no calcula hashes y no escribe `registry.json`. Su
    unico trabajo es dejar constancia de QUE se propone dar de alta y con que
    metadatos declarados, para que la confirmacion humana tenga algo concreto
    y estable que aprobar.
    """
    if not source_id or len(source_id) < 3:
        raise HumanSourceRegistrationError(
            f"source_id invalido: {source_id!r} (minimo 3 caracteres, lo exige el schema)"
        )

    unknown = set(declared) - DECLARED_REQUIRED_FIELDS - DECLARED_OPTIONAL_FIELDS
    if unknown:
        derived = sorted(unknown & DERIVED_FIELDS)
        if derived:
            raise HumanSourceRegistrationError(
                f"campos derivados no se declaran, los calcula apply_: {derived}"
            )
        raise HumanSourceRegistrationError(f"campos desconocidos en declared: {sorted(unknown)}")

    missing = sorted(DECLARED_REQUIRED_FIELDS - set(declared))
    if missing:
        raise HumanSourceRegistrationError(f"faltan campos obligatorios en declared: {missing}")

    _validate_declared_values(source_id, declared)

    if _find_source(source_id) is not None:
        raise HumanSourceRegistrationError(
            f"source_id={source_id!r} ya existe en el registry -- el alta no sobrescribe; "
            "para modificar una fuente existente usar human_source_update"
        )

    return decision_log.write_decision(
        project_id=PROJECT_ID, action=ACTION, decision="approve",
        rationale=rationale, decided_by=proposed_by, decision_origin="agent_proposed",
        recorded_by=proposed_by,
        metadata={
            "source_id": source_id,
            "canonical_file": str(Path(canonical_file)),
            "declared": dict(declared),
        },
    )


# --------------------------------------------------------------------------
# 2. CONFIRMAR -- tampoco escribe nada
# --------------------------------------------------------------------------

def confirm_source_registration(decision_id: str, confirmed_by: str) -> dict:
    """Confirma una propuesta ya registrada. Sigue sin escribir el registry:
    la aplicacion es un tercer paso deliberado, igual que en
    `human_source_update`."""
    proposal = _find_decision(decision_id)
    if proposal is None:
        raise HumanSourceRegistrationError(
            f"decision_id {decision_id!r} no encontrada en decisions.jsonl"
        )
    if proposal["action"] != ACTION or proposal["decision_origin"] != "agent_proposed":
        raise HumanSourceRegistrationError(
            f"decision_id {decision_id!r} no es una propuesta agent_proposed de {ACTION!r}"
        )
    if not confirmed_by or not confirmed_by.strip():
        raise HumanSourceRegistrationError("confirmed_by vacio -- se exige identidad humana real")

    return decision_log.write_decision(
        project_id=proposal["project_id"], action=ACTION, decision="approve",
        rationale=f"Confirma propuesta {decision_id}", decided_by=confirmed_by,
        decision_origin="human_confirmed", recorded_by=confirmed_by,
        metadata={**proposal["metadata"], "confirms_decision_id": decision_id},
    )


# --------------------------------------------------------------------------
# 3. APLICAR -- unico punto de escritura
# --------------------------------------------------------------------------

def apply_source_registration(decision_id: str) -> dict:
    """Ingiere la copia canonica al almacen inmutable y anade la entrada al
    registry. Unica funcion del modulo que escribe en disco.

    Orden deliberado: se valida TODO (decision, unicidad, hash real, schema)
    antes de tocar el disco. Asi un fallo de validacion no deja ni un fichero
    copiado ni un registry a medias.
    """
    decision = _find_decision(decision_id)
    if decision is None:
        raise HumanSourceRegistrationError(
            f"decision_id {decision_id!r} no encontrada en decisions.jsonl"
        )
    if (decision["action"] != ACTION
            or decision["decision_origin"] != "human_confirmed"
            or decision["decision"] != "approve"):
        raise HumanSourceRegistrationError(
            f"decision_id {decision_id!r} no es human_confirmed+approve de {ACTION!r}"
        )

    source_id = decision["metadata"]["source_id"]
    declared = dict(decision["metadata"]["declared"])
    canonical_file = Path(decision["metadata"]["canonical_file"])

    # (1) el alta nunca sobrescribe. Se revalida aqui y no solo en propose_:
    # entre la propuesta y la aplicacion el registry pudo cambiar.
    registry = _read_registry()
    if any(s["source_id"] == source_id for s in registry["sources"]):
        raise HumanSourceRegistrationError(
            f"source_id={source_id!r} ya existe en el registry -- apply_ nunca sobrescribe una fuente"
        )

    # (2) la copia canonica tiene que existir de verdad.
    if not canonical_file.is_file():
        raise HumanSourceRegistrationError(
            f"copia canonica no encontrada: {canonical_file} -- esta herramienta NUNCA descarga; "
            "el fichero debe obtenerse por una via autorizada antes de aplicar"
        )

    # (3) hashes_match se DEMUESTRA calculando, no se declara.
    real_sha256 = _sha256_file(canonical_file)
    if real_sha256 != declared["sha256_original"]:
        raise HumanSourceRegistrationError(
            f"el SHA-256 real del fichero ({real_sha256}) no coincide con el declarado "
            f"({declared['sha256_original']}) -- integridad no demostrada, alta abortada"
        )

    # (4) guarda anti-fabricacion de procedencia.
    if _PRIOR_HASH_CLAIM in declared["official_origin_status"]:
        raise HumanSourceRegistrationError(
            f"official_origin_status afirma {_PRIOR_HASH_CLAIM!r} pero {source_id!r} es una fuente "
            f"NUEVA: no existe hash previo gobernado con el que comparar. Valor honesto para una "
            f"primera ingesta: {FIRST_INGESTION_ORIGIN_STATUS!r}"
        )

    # (5) supersedes nunca se infiere, y si se declara debe resolver.
    supersedes = declared.get("supersedes")
    if supersedes is not None and not any(s["source_id"] == supersedes for s in registry["sources"]):
        raise HumanSourceRegistrationError(
            f"supersedes={supersedes!r} no resuelve a ninguna fuente del registry"
        )

    size_bytes = canonical_file.stat().st_size
    if size_bytes < 1:
        raise HumanSourceRegistrationError(
            f"copia canonica vacia ({canonical_file}) -- el schema exige size_bytes >= 1"
        )

    store_path = SOURCES_STORE_DIR / real_sha256 / canonical_file.name
    entry = {
        "source_id": source_id,
        "original_path": str(canonical_file),
        "canonical_path": str(store_path),
        "official_source_url": declared["official_source_url"],
        "official_source_description": declared["official_source_description"],
        "sha256_original": declared["sha256_original"],
        "sha256_copy": real_sha256,
        "hashes_match": True,
        "size_bytes": size_bytes,
        "normative_type": declared["normative_type"],
        "jurisdiction": declared["jurisdiction"],
        "local_integrity_status": "PASS",
        "official_origin_status": declared["official_origin_status"],
        "regulatory_currency_status": CURRENCY_STATUS,
        "copied_at": datetime.now(timezone.utc).isoformat(),
        "derived_artifacts": [],
        "version": declared["version"],
        "effective_date": declared["effective_date"],
        "supersedes": supersedes,
        "reverification_due": declared.get("reverification_due"),
    }

    # (6) el schema decide antes de que exista un solo byte nuevo en disco.
    ok, errors = validate_against(entry, SCHEMA_NAME)
    if not ok:
        raise HumanSourceRegistrationError(
            f"la entrada no valida contra {SCHEMA_NAME}: {errors} -- nada escrito"
        )

    # (7) ingesta al almacen inmutable. Si el directorio del hash ya existe,
    # el contenido tiene que ser identico byte a byte: mismo hash con distinto
    # contenido seria una colision o una corrupcion, nunca algo que sobrescribir.
    created_store_file = False
    if store_path.exists():
        if _sha256_file(store_path) != real_sha256:
            raise HumanSourceRegistrationError(
                f"{store_path} ya existe con contenido distinto al del hash {real_sha256} -- "
                "almacen inmutable inconsistente, alta abortada"
            )
    else:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canonical_file, store_path)
        created_store_file = True

    # (8) escritura atomica del registry: tmp + replace, para que un fallo a
    # medias no deje un registry ilegible.
    try:
        registry["sources"].append(entry)
        _write_registry_atomic(registry)
    except Exception:
        if created_store_file:
            store_path.unlink(missing_ok=True)
        raise

    write_event("regulatory_source_registered", PROJECT_ID, {
        "source_id": source_id,
        "decision_id": decision_id,
        "canonical_path": entry["canonical_path"],
        "sha256_copy": real_sha256,
        "regulatory_currency_status": CURRENCY_STATUS,
        "schema_validated": SCHEMA_NAME,
    })

    return {
        "source_id": source_id,
        "decision_id": decision_id,
        "canonical_path": entry["canonical_path"],
        "sha256_copy": real_sha256,
        "regulatory_currency_status": CURRENCY_STATUS,
        "entry": entry,
    }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _validate_declared_values(source_id: str, declared: dict) -> None:
    if not _SHA256_RE.match(str(declared["sha256_original"])):
        raise HumanSourceRegistrationError(
            f"sha256_original no es un SHA-256 hex de 64 caracteres: {declared['sha256_original']!r}"
        )

    valid_types = {"regulation", "official_guidance", "internal_interpretation"}
    if declared["normative_type"] not in valid_types:
        raise HumanSourceRegistrationError(
            f"normative_type invalido: {declared['normative_type']!r}. Validos: {sorted(valid_types)}"
        )

    if len(str(declared["jurisdiction"])) < 2:
        raise HumanSourceRegistrationError("jurisdiction exige al menos 2 caracteres")

    if len(str(declared["official_origin_status"])) < 3:
        raise HumanSourceRegistrationError("official_origin_status exige al menos 3 caracteres")

    for field in ("version", "effective_date"):
        _validate_declared_or_unavailable(field, declared[field])

    reverification_due = declared.get("reverification_due")
    if reverification_due is not None and not _ISO_DATE_RE.match(str(reverification_due)):
        raise HumanSourceRegistrationError(
            f"reverification_due={reverification_due!r} no es una fecha ISO; usar None mientras no "
            "exista una cadencia aprobada por Capa 9 -- nunca se calcula con una cadencia inventada"
        )


def _validate_declared_or_unavailable(field: str, value: object) -> None:
    """`version` y `effective_date` salen del texto gobernado o se declaran
    ausentes CON MOTIVO. Un `NO_DISPONIBLE` pelado esconde exactamente lo que
    el schema pide explicitar."""
    text = str(value).strip()
    if not text:
        raise HumanSourceRegistrationError(f"{field} vacio -- el schema exige minLength 1")
    if text.upper().startswith("NO_DISPONIBLE") and not _NO_DISPONIBLE_RE.match(text):
        raise HumanSourceRegistrationError(
            f"{field}={value!r}: 'NO_DISPONIBLE' exige motivo entre parentesis, "
            "p.ej. 'NO_DISPONIBLE (eCFR es texto consolidado sin edicion discreta)'"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_registry() -> dict:
    return json.loads(SOURCES_REGISTRY_FILE.read_text(encoding="utf-8"))


def _write_registry_atomic(registry: dict) -> None:
    tmp_path = SOURCES_REGISTRY_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    tmp_path.replace(SOURCES_REGISTRY_FILE)


def _find_source(source_id: str) -> dict | None:
    if not SOURCES_REGISTRY_FILE.exists():
        return None
    for source in _read_registry()["sources"]:
        if source["source_id"] == source_id:
            return source
    return None


def _find_decision(decision_id: str) -> dict | None:
    for entry in decision_log.list_decisions():
        if entry["decision_id"] == decision_id:
            return entry
    return None
