"""G3 — re-gobernanza del ARTEFACTO CANÓNICO de una fuente YA EXISTENTE en
`sources/registry.json` (cambio de tipo de artefacto, no solo de URL).

Por qué existe: `human_source_update.py` cubre el caso de MHRA (URL rota o
apuntando al tipo equivocado, pero el ARCHIVO gobernado sigue siendo
correcto) -- solo permite tocar `official_source_url`/`sha256_original`/
`official_source_description`, nunca `canonical_path`. El caso real de
`ecfr_21cfr_part11` es distinto: la única URL oficial que sirve un tipo de
artefacto comparable (XML, vía el mismo `versioner API` ya gobernado para
`ecfr_21cfr_part211`) exige cambiar TAMBIÉN qué archivo es la copia
canónica -- no es un cambio de URL, es re-ingerir la fuente como un
artefacto distinto. `human_source_update.py` rechaza ese campo a propósito
(fail-closed); este módulo es su hermano para ese caso específico, no una
ampliación silenciosa de aquel.

Reutiliza la primitiva de ingesta de `human_source_registration.py` (hash
real, copia al almacén inmutable por SHA-256, escritura atómica) en vez de
reimplementarla -- la única diferencia estructural es la precondición: el
alta exige que el `source_id` NO exista, la re-gobernanza exige que SÍ
exista.

Mismo patrón de 3 pasos separados y auditables:

  propose_source_regovernance()  -- agent_proposed, NUNCA escribe nada
  confirm_source_regovernance()  -- human_confirmed, NUNCA escribe nada
  apply_source_regovernance()    -- ÚNICA función que escribe: ingiere la
                                     nueva copia canónica y reemplaza los
                                     campos derivados de la fuente existente

Guard de `apply_`, igual que `human_source_update.apply_source_url_update`:
exige que la fuente esté `REGULATORY_SOURCE_UNVERIFIED`
(`broken_link_report`) o `ARTIFACT_TYPE_MISMATCH`
(`artifact_type_mismatch_report`) -- nunca re-gobierna una fuente sana, ni
con decisión humana válida. Un cambio de TIPO DE ARTEFACTO es una acción
más profunda que un cambio de URL: el mismo guard fail-closed aplica con
más razón, no con menos.

Campos que preserva de la entrada existente (no se re-declaran, no
cambian con el formato del archivo): `jurisdiction`, `normative_type`,
`supersedes`, `reverification_due`, `regulatory_currency_status` (sigue
`pending_reverification`, invariante del schema). `derived_artifacts` se
reinicia a `[]`: los artefactos derivados del archivo VIEJO (p.ej. una
extracción pdfplumber) ya no describen el archivo nuevo -- mantenerlos
sería una procedencia falsa.
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
from factory.regulatory import artifact_type_mismatch_report
from factory.regulatory import broken_link_report
from factory.regulatory.human_source_registration import repo_relative
from factory.regulatory.schema_loader import validate_against
from factory.services import paths as svc_paths

ACTION = "regulatory_source_regovernance"
SCHEMA_NAME = "source_registry_entry_v1"
PROJECT_ID = "gmpai_document_validation"

SOURCES_REGISTRY_FILE = Path(__file__).parent / "sources" / "registry.json"
SOURCES_STORE_DIR = Path(__file__).parent / "sources" / "sha256"

#: Campos que declara el humano al re-gobernar. `version`/`effective_date`
#: se vuelven a exigir porque un artefacto distinto puede citar su propia
#: fecha/versión de forma distinta al anterior (p.ej. el snapshot fijado de
#: una API versionada). `official_origin_status` también se vuelve a exigir
#: (no se preserva del registro viejo): ese campo describe la procedencia
#: DEL ARCHIVO CONCRETO, y preservarlo tras cambiar de hash/formato sería
#: afirmar una verificación que nunca ocurrió sobre el archivo nuevo. El
#: resto de metadatos regulatorios (`jurisdiction`, `normative_type`,
#: `supersedes`, `reverification_due`) no cambia con el formato del archivo
#: y se preserva de la entrada existente.
DECLARED_REQUIRED_FIELDS = frozenset({
    "official_source_url",
    "official_source_description",
    "sha256_original",
    "official_origin_status",
    "version",
    "effective_date",
})

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_NO_DISPONIBLE_RE = re.compile(r"^NO_DISPONIBLE\s*\(.+\)$", re.DOTALL)


class HumanSourceRegovernanceError(Exception):
    pass


def _validate_declared_or_unavailable(field: str, value: object) -> None:
    """`version` y `effective_date` salen del texto gobernado o se declaran
    ausentes CON MOTIVO -- mismo criterio que `human_source_registration.py`
    (duplicado a propósito, no importado: es un helper privado de un módulo
    hermano, no una API compartida)."""
    text = str(value).strip()
    if not text:
        raise HumanSourceRegovernanceError(f"{field} vacio -- el schema exige minLength 1")
    if text.upper().startswith("NO_DISPONIBLE") and not _NO_DISPONIBLE_RE.match(text):
        raise HumanSourceRegovernanceError(
            f"{field}={value!r}: 'NO_DISPONIBLE' exige motivo entre parentesis, "
            "p.ej. 'NO_DISPONIBLE (eCFR es texto consolidado sin edicion discreta)'"
        )


# --------------------------------------------------------------------------
# 1. PROPONER -- no escribe nada, ni siquiera lee el fichero canonico
# --------------------------------------------------------------------------

def propose_source_regovernance(
    source_id: str,
    canonical_file: str | Path,
    declared: dict,
    rationale: str,
    proposed_by: str = "layer8_agent",
) -> dict:
    """Registra una PROPUESTA (`agent_proposed`) en `decisions.jsonl`. No
    copia el fichero, no calcula hashes, no toca `registry.json`."""
    unknown = set(declared) - DECLARED_REQUIRED_FIELDS
    if unknown:
        raise HumanSourceRegovernanceError(f"campos desconocidos en declared: {sorted(unknown)}")

    missing = sorted(DECLARED_REQUIRED_FIELDS - set(declared))
    if missing:
        raise HumanSourceRegovernanceError(f"faltan campos obligatorios en declared: {missing}")

    if not _SHA256_RE.match(str(declared["sha256_original"])):
        raise HumanSourceRegovernanceError(
            f"sha256_original no es un SHA-256 hex de 64 caracteres: {declared['sha256_original']!r}"
        )
    if len(str(declared["official_origin_status"])) < 3:
        raise HumanSourceRegovernanceError("official_origin_status exige al menos 3 caracteres")
    for field in ("version", "effective_date"):
        _validate_declared_or_unavailable(field, declared[field])

    existing = _find_source(source_id)
    if existing is None:
        raise HumanSourceRegovernanceError(
            f"source_id={source_id!r} no existe en el registry -- la re-gobernanza actualiza una "
            "fuente EXISTENTE; para dar de alta una fuente nueva usar human_source_registration"
        )
    if existing["sha256_original"] == declared["sha256_original"]:
        raise HumanSourceRegovernanceError(
            "sha256_original declarado es idéntico al ya gobernado -- no hay artefacto distinto que "
            "re-ingerir; para solo cambiar la URL usar human_source_update"
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

def confirm_source_regovernance(decision_id: str, confirmed_by: str) -> dict:
    proposal = _find_decision(decision_id)
    if proposal is None:
        raise HumanSourceRegovernanceError(f"decision_id {decision_id!r} no encontrada en decisions.jsonl")
    if proposal["action"] != ACTION or proposal["decision_origin"] != "agent_proposed":
        raise HumanSourceRegovernanceError(
            f"decision_id {decision_id!r} no es una propuesta agent_proposed de {ACTION!r}"
        )
    if not confirmed_by or not confirmed_by.strip():
        raise HumanSourceRegovernanceError("confirmed_by vacio -- se exige identidad humana real")

    return decision_log.write_decision(
        project_id=proposal["project_id"], action=ACTION, decision="approve",
        rationale=f"Confirma propuesta {decision_id}", decided_by=confirmed_by,
        decision_origin="human_confirmed", recorded_by=confirmed_by,
        metadata={**proposal["metadata"], "confirms_decision_id": decision_id},
    )


# --------------------------------------------------------------------------
# 3. APLICAR -- unico punto de escritura
# --------------------------------------------------------------------------

def apply_source_regovernance(decision_id: str) -> dict:
    """Ingiere la nueva copia canónica y reemplaza los campos derivados de
    la fuente ya existente. Fail-closed en el mismo guard de
    `human_source_update.apply_source_url_update`: exige
    REGULATORY_SOURCE_UNVERIFIED o ARTIFACT_TYPE_MISMATCH real."""
    decision = _find_decision(decision_id)
    if decision is None:
        raise HumanSourceRegovernanceError(f"decision_id {decision_id!r} no encontrada en decisions.jsonl")
    if (decision["action"] != ACTION or decision["decision_origin"] != "human_confirmed"
            or decision["decision"] != "approve"):
        raise HumanSourceRegovernanceError(
            f"decision_id {decision_id!r} no es human_confirmed+approve de {ACTION!r}"
        )

    source_id = decision["metadata"]["source_id"]
    declared = dict(decision["metadata"]["declared"])
    canonical_file = Path(decision["metadata"]["canonical_file"])

    log_entries = _read_currency_log()
    broken_status = broken_link_report.evaluate_source(source_id, log_entries)["status"]
    mismatch_status = artifact_type_mismatch_report.evaluate_source(source_id, log_entries)["status"]
    if (broken_status != broken_link_report.STATUS_UNVERIFIED
            and mismatch_status != artifact_type_mismatch_report.STATUS_ARTIFACT_TYPE_MISMATCH):
        raise HumanSourceRegovernanceError(
            f"source_id={source_id!r} no está REGULATORY_SOURCE_UNVERIFIED ni ARTIFACT_TYPE_MISMATCH "
            f"(broken_link_report={broken_status!r}, artifact_type_mismatch_report={mismatch_status!r}) "
            "-- human_source_regovernance nunca re-gobierna una fuente sana"
        )

    registry = _read_registry()
    existing = next((s for s in registry["sources"] if s["source_id"] == source_id), None)
    if existing is None:
        raise HumanSourceRegovernanceError(f"source_id={source_id!r} ya no existe en el registry")

    if not canonical_file.is_file():
        raise HumanSourceRegovernanceError(
            f"copia canonica no encontrada: {canonical_file} -- este modulo NUNCA descarga; "
            "el fichero debe obtenerse por una via autorizada antes de aplicar"
        )

    real_sha256 = _sha256_file(canonical_file)
    if real_sha256 != declared["sha256_original"]:
        raise HumanSourceRegovernanceError(
            f"el SHA-256 real del fichero ({real_sha256}) no coincide con el declarado "
            f"({declared['sha256_original']}) -- integridad no demostrada, re-gobernanza abortada"
        )

    size_bytes = canonical_file.stat().st_size
    if size_bytes < 1:
        raise HumanSourceRegovernanceError(
            f"copia canonica vacia ({canonical_file}) -- el schema exige size_bytes >= 1"
        )

    before = {k: existing.get(k) for k in (
        "canonical_path", "official_source_url", "official_source_description",
        "sha256_original", "sha256_copy", "size_bytes", "version", "effective_date",
        "official_origin_status", "derived_artifacts",
    )}

    store_path = SOURCES_STORE_DIR / real_sha256 / canonical_file.name
    updated = dict(existing)
    updated.update({
        "original_path": repo_relative(canonical_file),
        "canonical_path": repo_relative(store_path),
        "official_source_url": declared["official_source_url"],
        "official_source_description": declared["official_source_description"],
        "sha256_original": declared["sha256_original"],
        "official_origin_status": declared["official_origin_status"],
        "sha256_copy": real_sha256,
        "hashes_match": True,
        "size_bytes": size_bytes,
        "local_integrity_status": "PASS",
        "copied_at": datetime.now(timezone.utc).isoformat(),
        "derived_artifacts": [],
        "version": declared["version"],
        "effective_date": declared["effective_date"],
    })
    if updated["regulatory_currency_status"] != "pending_reverification":
        raise HumanSourceRegovernanceError(
            "regulatory_currency_status cambió de 'pending_reverification' -- invariante del schema violada, abortando escritura"
        )

    ok, errors = validate_against(updated, SCHEMA_NAME)
    if not ok:
        raise HumanSourceRegovernanceError(
            f"la entrada no valida contra {SCHEMA_NAME}: {errors} -- nada escrito"
        )

    created_store_file = False
    if store_path.exists():
        if _sha256_file(store_path) != real_sha256:
            raise HumanSourceRegovernanceError(
                f"{store_path} ya existe con contenido distinto al del hash {real_sha256} -- "
                "almacen inmutable inconsistente, re-gobernanza abortada"
            )
    else:
        store_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canonical_file, store_path)
        created_store_file = True

    try:
        registry["sources"] = [
            updated if s["source_id"] == source_id else s for s in registry["sources"]
        ]
        _write_registry_atomic(registry)
    except Exception:
        if created_store_file:
            store_path.unlink(missing_ok=True)
        raise

    write_event("regulatory_source_regoverned", PROJECT_ID, {
        "source_id": source_id, "decision_id": decision_id,
        "before": before,
        "after": {k: updated.get(k) for k in before},
    })

    return {"source_id": source_id, "decision_id": decision_id, "before": before,
            "after": {k: updated.get(k) for k in before}, "entry": updated}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

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


def _read_currency_log() -> list[dict]:
    if not svc_paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in svc_paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries
