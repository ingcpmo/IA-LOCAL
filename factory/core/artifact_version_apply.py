"""Aplicación gobernada del versionado de artefactos — W5 V2 G4c.

`artifact_version_guard.py` solo MIDE la invariante (hash⟺version⟺decisión);
declara explícitamente que no escribe nada. Este módulo es el tercer paso,
igual que `human_source_registration.apply_source_registration` o
`bootstrap_artifact_versions.py`: el ÚNICO punto que toca disco, y solo
después de que el resolver confirme que existe una decisión `ARTIFACT_VERSION`
`ACTIVE` y `human_confirmed` que cubra el `artifact_id`.

ALCANCE DE `apply_catalog_version_bump`: solo la clase `catalog` (el único
caso real de BUMP de contenido hoy, `ARTIFACT_VERSIONING_SPEC.md` §3).
Generalizar el bump a matrix/pack/prompt/golden sin un caso real que lo
exija repetiría el error que este roadmap lleva corregido varias veces
(Fase J de `project_w5_v2_regulatory_redesign`: "no se fabrica código sin un
caso real que lo valide").

`apply_artifact_first_approval` (G6, `MODEL_REQUALIFICATION_AND_D4A_SPEC.md`
§3) SÍ es genérica desde el principio: el caso real que la justifica es
`golden_dataset`, bootstrapeado por G4 con `approved_by_decision=null` desde
entonces (`NO_APPROVING_DECISION` en `guard_report()`). A diferencia de un
bump, aquí no hay versión ni contenido nuevos que escribir -- la decisión
aprueba EXACTAMENTE lo que ya está en disco desde el bootstrap. Generalizarla
no repite el error de Fase J porque no hay una segunda clase hipotética
detrás: es la misma operación (adjuntar `approved_by_decision` a un
version_record sin bump) que cualquier otra clase bootstrapeada necesitaría
el día que tenga su propio caso real.

ORDEN DELIBERADO (mismo patrón que `apply_source_registration`): se valida
TODO -- decisión, versión, formato del archivo -- antes de escribir un solo
byte. Un fallo a mitad de camino no debe dejar el catálogo bumpeado sin su
`version_record`, ni viceversa.

COPIA HISTÓRICA (§3.4): se congela desde `git show HEAD:<ruta>`, nunca desde
el archivo vivo -- un archivo vivo puede tener cambios sin commitear que no
son los que de verdad se aprobaron. Si HEAD no coincide byte a byte con el
archivo vivo (hay cambios sin commitear), se declara honestamente
`UNAVAILABLE_NOT_COMMITTED` en vez de fabricar una copia de algo que nunca
se commiteó.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from factory.core import artifact_version_guard as guard
from factory.core import decision_scope_resolver as resolver
from factory.core.audit_writer import write_event
from factory.services import decision_store_v2 as store

CATALOG_VERSION_LINE = re.compile(r"^catalog_version:\s*'([^']*)'\s*$", re.MULTILINE)

#: Hallazgo real de 2026-08-04 (panel ARQ, verificado contra el almacén):
#: ARTIFACT_VERSION-2026-001/002/003 tenían `payload={}` -- la familia
#: guardaba QUÉ ARTEFACTO se versiona, nunca QUÉ TRANSICIÓN se autoriza. El
#: resolver certifica cobertura por `artifact_id`, no por transición, así
#: que una decisión `human_confirmed` para 1.0→2.0 (`ARTIFACT_VERSION-2026-002`)
#: técnicamente podía citarse para aplicar CUALQUIER bump futuro del mismo
#: artefacto (2.0→2.1, 2.1→3.7, lo que fuera) sin que el código lo impidiera
#: -- nunca se explotó, pero nada en `apply_catalog_version_bump` lo hacía
#: imposible. Estos 6 campos, ahora obligatorios en el `payload` de toda
#: propuesta `ARTIFACT_VERSION`, atan la decisión a la transición EXACTA que
#: un humano vio al confirmarla.
REQUIRED_PROPOSAL_PAYLOAD_FIELDS = (
    "artifact_path", "artifact_hash_before", "from_version", "to_version",
    "expected_hash_after", "change_reason",
)


class ArtifactVersionApplyError(Exception):
    pass


class ArtifactVersionProposalError(Exception):
    pass


def _catalog_artifact_id(base: Path) -> str:
    return (base / "factory" / "regulatory" / "requirement_catalog"
            / "requirements.yaml").relative_to(base).as_posix()


def _freeze_historical_copy(base: Path, artifact_id: str, *,
                            previous_version: str | None,
                            previous_sha256: str) -> dict:
    """Congela la copia histórica desde HEAD. Nunca desde el archivo vivo."""
    live_path = base / artifact_id
    live_text = live_path.read_text(encoding="utf-8")

    try:
        head_blob = subprocess.run(
            ["git", "-C", str(base), "show", f"HEAD:{artifact_id}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        return {"status": "UNAVAILABLE_NOT_COMMITTED",
                "reason": f"HEAD no tiene {artifact_id!r}: {exc.stderr.strip()}"}

    if head_blob != live_text:
        return {"status": "UNAVAILABLE_NOT_COMMITTED",
                "reason": "el archivo vivo difiere de HEAD: hay cambios sin "
                          "commitear, y la copia histórica se genera SOLO desde "
                          "un commit real, nunca del archivo vivo"}

    versions_dir = live_path.parent / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    short_hash = previous_sha256[:8]
    dest = versions_dir / f"requirements-{previous_version or 'unversioned'}-{short_hash}.yaml"

    if dest.exists():
        if dest.read_text(encoding="utf-8") != head_blob:
            raise ArtifactVersionApplyError(
                f"{dest} ya existe con contenido distinto al de HEAD -- "
                "posible colisión, nada escrito")
    else:
        dest.write_text(head_blob, encoding="utf-8")

    return {"status": "FROZEN", "path": dest.relative_to(base).as_posix()}


def propose_artifact_version_change(*, artifact_path: str, to_version: str,
                                    change_reason: str, proposed_by_id: str,
                                    repo: Path | None = None,
                                    decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`, no escribe nada aplicable) un bump
    `ARTIFACT_VERSION` con el payload estructurado completo -- cierra el
    hallazgo de 2026-08-04 (ver `REQUIRED_PROPOSAL_PAYLOAD_FIELDS`).

    Todos los valores del payload se DERIVAN del estado vivo en el momento
    de proponer, nunca se aceptan como parámetro de quien propone (evita que
    una propuesta declare un `artifact_hash_before` distinto del real):

      artifact_hash_before -- `enumerate_artifacts()` real, ahora.
      from_version         -- idem.
      expected_hash_after  -- se SIMULA la sustitución de `catalog_version`
                              sobre el texto vivo (sin escribir nada) y se
                              hashea igual que `canonical_hash_yaml`. Hoy
                              `catalog_version` está EXCLUIDO del hash
                              canónico (ver `_EXCLUDED` en
                              `artifact_version_guard.py`), así que
                              `expected_hash_after == artifact_hash_before`
                              -- pero se CALCULA, no se copia, para que si
                              ese campo alguna vez deja de excluirse, este
                              valor lo refleje solo.

    Solo soporta la clase `catalog` hoy (mismo alcance deliberado que
    `apply_catalog_version_bump` -- `ARTIFACT_VERSIONING_SPEC.md` §3)."""
    base = repo or guard.REPO

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_path), None)
    if current is None:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.artifact != "catalog":
        raise ArtifactVersionProposalError(
            f"propose_artifact_version_change solo soporta la clase 'catalog' hoy "
            f"(clase real de {artifact_path!r}: {current.artifact!r})")
    if current.version == to_version:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} ya está en version {to_version!r} -- nada que proponer")

    live_text = (base / artifact_path).read_text(encoding="utf-8")
    new_text, n = CATALOG_VERSION_LINE.subn(
        f"catalog_version: '{to_version}'", live_text, count=1)
    if n != 1:
        raise ArtifactVersionProposalError(
            "no se encontró la línea \"catalog_version: '...'\" -- no se puede "
            "simular el bump para calcular expected_hash_after")
    expected_hash_after = guard.canonical_hash_yaml_text(new_text, current.artifact)

    payload = {
        "artifact_path": artifact_path,
        "artifact_hash_before": current.sha256,
        "from_version": current.version,
        "to_version": to_version,
        "expected_hash_after": expected_hash_after,
        "change_reason": change_reason,
    }

    from factory.services import governance_service as gov
    return gov.propose(
        "ARTIFACT_VERSION", target_ids=[artifact_path], decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=change_reason, payload=payload, store_file=decision_store_file)


def propose_catalog_source_verification_sync(*, to_version: str, change_reason: str,
                                             proposed_by_id: str,
                                             registry_path: Path | None = None,
                                             repo: Path | None = None,
                                             decision_store_file: Path | None = None) -> dict:
    """R3-T1.2/F0.6 (2026-08-12) -- variante de `propose_artifact_version_change`
    para EXACTAMENTE un caso real: sincronizar `source_verification_status`
    (mecánico, `source_lifecycle.sync_catalog_source_verification_status()`)
    contra el estado real de `evaluate_registry()`, en el mismo movimiento
    que el bump de versión que lo declara.

    Deliberadamente NO se generalizó `propose_artifact_version_change` para
    aceptar "cualquier cambio de contenido" (mismo criterio que el docstring
    de este módulo cita de Fase J: "no se fabrica código sin un caso real
    que lo valide" -- un parámetro `content_transform` genérico sería
    exactamente el tipo de escotilla que la gobernanza ARTIFACT_VERSION
    existe para impedir). Esta función es angosta a propósito: solo hace
    ESTA sincronización, nunca acepta contenido arbitrario de quien la
    llama.

    `registry_sha256_before` (extra, fuera de `REQUIRED_PROPOSAL_PAYLOAD_FIELDS`
    pero exigido igual por `apply_catalog_source_verification_sync`): congela
    qué estado del registry vio esta propuesta -- si el registry cambia
    entre proponer y aplicar (otra reingesta, una revocación), aplicar debe
    fallar y exigir una propuesta nueva, nunca aplicar una sincronización
    calculada sobre un registry que ya no es el vivo."""
    from factory.regulatory import source_lifecycle as sl
    import yaml as _yaml

    base = repo or guard.REPO
    artifact_path = _catalog_artifact_id(base)

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_path), None)
    if current is None:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.version == to_version:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} ya está en version {to_version!r} -- nada que proponer")

    live_text = (base / artifact_path).read_text(encoding="utf-8")
    reg_path = registry_path or sl.REGISTRY_PATH
    registry_sha256_before = hashlib.sha256(reg_path.read_bytes()).hexdigest()

    data = _yaml.safe_load(live_text)
    order = [(rid, entry["source_id"]) for rid, entry in data["requirements"].items()]
    synced_text, changes = sl.sync_catalog_source_verification_status(
        live_text, order, registry_path=registry_path, repo=base,
        decision_store_file=decision_store_file)

    versioned_text, n = CATALOG_VERSION_LINE.subn(
        f"catalog_version: '{to_version}'", synced_text, count=1)
    if n != 1:
        raise ArtifactVersionProposalError(
            "no se encontró la línea \"catalog_version: '...'\" -- no se puede "
            "simular el bump para calcular expected_hash_after")
    expected_hash_after = guard.canonical_hash_yaml_text(versioned_text, current.artifact)

    payload = {
        "artifact_path": artifact_path,
        "artifact_hash_before": current.sha256,
        "from_version": current.version,
        "to_version": to_version,
        "expected_hash_after": expected_hash_after,
        "change_reason": change_reason,
        "sync_type": "source_verification_status",
        "registry_sha256_before": registry_sha256_before,
        "source_verification_changes": changes,
    }

    from factory.services import governance_service as gov
    return gov.propose(
        "ARTIFACT_VERSION", target_ids=[artifact_path], decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=change_reason, payload=payload, store_file=decision_store_file)


def apply_catalog_version_bump(new_version: str, *, decision_instance_id: str,
                               repo: Path | None = None,
                               decision_store_file: Path | None = None,
                               versions_store_file: Path | None = None) -> dict:
    """Único punto de escritura de G4c. Fail-closed en cada paso.

    Devuelve el `version_record` escrito. No hace nada si:
      - la familia ARTIFACT_VERSION no cubre `artifact_id` (resolver real,
        no el campo `approved_by_decision` de un registro -- ese puede
        nombrar una decisión revocada o superada),
      - `decision_instance_id` no es una de las instancias que SÍ otorgan
        esa cobertura (evita aplicar con una decisión ajena, aunque ambas
        sean ACTIVE),
      - el `payload` de la decisión no trae los 6 campos de
        `REQUIRED_PROPOSAL_PAYLOAD_FIELDS` (cierre del hallazgo de
        2026-08-04: decisiones antiguas con `payload={}` -- p.ej.
        `ARTIFACT_VERSION-2026-002`, que confirmó la transición 1.0→2.0 --
        YA NO SE PUEDEN reutilizar para aplicar un bump distinto),
      - el `artifact_path` declarado en el payload no es este `artifact_id`
        (decisión de otro artefacto),
      - el `to_version` declarado en el payload no es este `new_version`
        (el decision_id corresponde a OTRA transición del mismo artefacto),
      - la versión viva no coincide con el `from_version` declarado
        (el estado cambió desde que se propuso),
      - el hash vivo no coincide con `artifact_hash_before` declarado
        (el contenido cambió desde que se propuso),
      - la versión declarada ya es `new_version` (nada que aplicar),
      - el archivo no tiene la línea `catalog_version: '...'` esperada,
      - tras escribir, el hash resultante no coincide con
        `expected_hash_after` declarado (bump revertido, nunca se deja a
        medias).
    """
    base = repo or guard.REPO
    artifact_id = _catalog_artifact_id(base)

    scope = resolver.resolve(guard.DECISION_FAMILY, artifact_id,
                             store_file=decision_store_file)
    if not scope.authorized:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no está autorizado para versionar: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan "
            f"cobertura ({scope.covering_instances!r}) -- no se aplica un bump "
            "con una decisión que no es la que lo autoriza")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no se encuentra en el almacén de decisiones")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PROPOSAL_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no declara la transición exacta que autoriza "
            f"(faltan en payload: {missing}) -- decisiones sin transición declarada "
            "ya no se pueden aplicar, usar propose_artifact_version_change() para "
            "generar una propuesta nueva sobre el estado actual")
    if payload["artifact_path"] != artifact_id:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} autoriza artifact_path="
            f"{payload['artifact_path']!r}, no {artifact_id!r} -- decisión de otro "
            "artefacto")
    if payload["to_version"] != new_version:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} autoriza la transición a "
            f"{payload['to_version']!r}, no a {new_version!r} -- el decision_id "
            "corresponde a otra transición")

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_id), None)
    if current is None:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.version == new_version:
        raise ArtifactVersionApplyError(
            f"catalog_version ya es {new_version!r} -- nada que aplicar")
    if current.version != payload["from_version"]:
        raise ArtifactVersionApplyError(
            f"la versión viva ({current.version!r}) no coincide con from_version "
            f"declarado en la decisión ({payload['from_version']!r}) -- el estado "
            "cambió desde que se propuso, re-proponer sobre el estado actual")
    if current.sha256 != payload["artifact_hash_before"]:
        raise ArtifactVersionApplyError(
            f"el hash vivo ({current.sha256}) no coincide con artifact_hash_before "
            f"declarado en la decisión ({payload['artifact_hash_before']}) -- el "
            "contenido cambió desde que se propuso, re-proponer sobre el estado actual")

    previous_version, previous_sha256 = current.version, current.sha256
    catalog_path = base / artifact_id
    original_text = catalog_path.read_text(encoding="utf-8")

    historical_copy = _freeze_historical_copy(
        base, artifact_id, previous_version=previous_version,
        previous_sha256=previous_sha256)

    new_text, n = CATALOG_VERSION_LINE.subn(
        f"catalog_version: '{new_version}'", original_text, count=1)
    if n != 1:
        raise ArtifactVersionApplyError(
            "no se encontró la línea \"catalog_version: '...'\" -- bump "
            "abortado, nada escrito en el archivo ni en el almacén")

    catalog_path.write_text(new_text, encoding="utf-8")
    try:
        new_state = next((s for s in guard.enumerate_artifacts(repo=base)
                          if s.artifact_id == artifact_id), None)
        if new_state is None or new_state.version != new_version:
            raise ArtifactVersionApplyError(
                "el bump no produjo la versión esperada tras escribirlo")
        if new_state.sha256 != payload["expected_hash_after"]:
            raise ArtifactVersionApplyError(
                f"el hash resultante ({new_state.sha256}) no coincide con "
                f"expected_hash_after declarado en la decisión "
                f"({payload['expected_hash_after']}) -- bump revertido")
    except Exception:
        catalog_path.write_text(original_text, encoding="utf-8")
        raise

    record = guard.build_version_record(
        new_state, previous_version=previous_version,
        previous_sha256=previous_sha256,
        approved_by_decision=decision_instance_id)
    record["historical_copy"] = historical_copy

    path = versions_store_file or guard.STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_event("artifact_version_applied", "factory", {
        "artifact_id": artifact_id,
        "from_version": previous_version,
        "to_version": new_version,
        "approved_by_decision": decision_instance_id,
        "historical_copy": historical_copy,
    })

    return record


def apply_catalog_source_verification_sync(new_version: str, *, decision_instance_id: str,
                                           registry_path: Path | None = None,
                                           repo: Path | None = None,
                                           decision_store_file: Path | None = None,
                                           versions_store_file: Path | None = None) -> dict:
    """Aplica una propuesta de `propose_catalog_source_verification_sync()`.
    Mismas validaciones que `apply_catalog_version_bump` (decisión cubre el
    artefacto, transición exacta, versión/hash vivos coinciden con lo
    propuesto) MÁS una adicional propia de este caso: el registry no puede
    haber cambiado desde que se propuso (`registry_sha256_before`) -- una
    reingesta o revocación nueva entre proponer y aplicar invalidaría el
    cálculo, y aplicar de todas formas escribiría una sincronización que ya
    no refleja el estado real. Regenera el texto nuevo llamando a
    `sync_catalog_source_verification_status()` de nuevo (nunca guarda el
    texto propuesto como blob) -- determinista, así que si nada cambió
    produce byte-a-byte lo mismo que se propuso."""
    from factory.regulatory import source_lifecycle as sl
    import yaml as _yaml

    base = repo or guard.REPO
    artifact_id = _catalog_artifact_id(base)

    scope = resolver.resolve(guard.DECISION_FAMILY, artifact_id,
                             store_file=decision_store_file)
    if not scope.authorized:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no está autorizado para versionar: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan "
            f"cobertura ({scope.covering_instances!r}) -- no se aplica un bump "
            "con una decisión que no es la que lo autoriza")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no se encuentra en el almacén de decisiones")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PROPOSAL_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no declara la transición exacta que autoriza "
            f"(faltan en payload: {missing})")
    if payload.get("sync_type") != "source_verification_status":
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no es una propuesta de sincronización de "
            "source_verification_status -- usar apply_catalog_version_bump para "
            "un bump simple de versión")
    if payload["artifact_path"] != artifact_id:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} autoriza artifact_path="
            f"{payload['artifact_path']!r}, no {artifact_id!r}")
    if payload["to_version"] != new_version:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} autoriza la transición a "
            f"{payload['to_version']!r}, no a {new_version!r}")

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_id), None)
    if current is None:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.version == new_version:
        raise ArtifactVersionApplyError(
            f"catalog_version ya es {new_version!r} -- nada que aplicar")
    if current.version != payload["from_version"]:
        raise ArtifactVersionApplyError(
            f"la versión viva ({current.version!r}) no coincide con from_version "
            f"declarado en la decisión ({payload['from_version']!r}) -- el estado "
            "cambió desde que se propuso, re-proponer sobre el estado actual")
    if current.sha256 != payload["artifact_hash_before"]:
        raise ArtifactVersionApplyError(
            f"el hash vivo ({current.sha256}) no coincide con artifact_hash_before "
            f"declarado en la decisión ({payload['artifact_hash_before']}) -- el "
            "contenido cambió desde que se propuso, re-proponer sobre el estado actual")

    reg_path = registry_path or sl.REGISTRY_PATH
    registry_sha256_now = hashlib.sha256(reg_path.read_bytes()).hexdigest()
    if registry_sha256_now != payload.get("registry_sha256_before"):
        raise ArtifactVersionApplyError(
            f"registry.json cambió desde que se propuso esta sincronización "
            f"(antes {payload.get('registry_sha256_before')}, ahora "
            f"{registry_sha256_now}) -- re-proponer sobre el estado actual, "
            "nunca aplicar una sincronización calculada sobre un registry viejo")

    previous_version, previous_sha256 = current.version, current.sha256
    catalog_path = base / artifact_id
    original_text = catalog_path.read_text(encoding="utf-8")

    historical_copy = _freeze_historical_copy(
        base, artifact_id, previous_version=previous_version,
        previous_sha256=previous_sha256)

    data = _yaml.safe_load(original_text)
    order = [(rid, entry["source_id"]) for rid, entry in data["requirements"].items()]
    synced_text, _changes = sl.sync_catalog_source_verification_status(
        original_text, order, registry_path=registry_path, repo=base,
        decision_store_file=decision_store_file)
    new_text, n = CATALOG_VERSION_LINE.subn(
        f"catalog_version: '{new_version}'", synced_text, count=1)
    if n != 1:
        raise ArtifactVersionApplyError(
            "no se encontró la línea \"catalog_version: '...'\" -- bump "
            "abortado, nada escrito en el archivo ni en el almacén")

    catalog_path.write_text(new_text, encoding="utf-8")
    try:
        new_state = next((s for s in guard.enumerate_artifacts(repo=base)
                          if s.artifact_id == artifact_id), None)
        if new_state is None or new_state.version != new_version:
            raise ArtifactVersionApplyError(
                "el bump no produjo la versión esperada tras escribirlo")
        if new_state.sha256 != payload["expected_hash_after"]:
            raise ArtifactVersionApplyError(
                f"el hash resultante ({new_state.sha256}) no coincide con "
                f"expected_hash_after declarado en la decisión "
                f"({payload['expected_hash_after']}) -- bump revertido")
    except Exception:
        catalog_path.write_text(original_text, encoding="utf-8")
        raise

    record = guard.build_version_record(
        new_state, previous_version=previous_version,
        previous_sha256=previous_sha256,
        approved_by_decision=decision_instance_id)
    record["historical_copy"] = historical_copy
    record["source_verification_changes"] = payload.get("source_verification_changes")

    path = versions_store_file or guard.STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_event("artifact_version_applied", "factory", {
        "artifact_id": artifact_id,
        "from_version": previous_version,
        "to_version": new_version,
        "approved_by_decision": decision_instance_id,
        "historical_copy": historical_copy,
    })

    return record


def apply_artifact_first_approval(artifact_id: str, *, decision_instance_id: str,
                                  repo: Path | None = None,
                                  decision_store_file: Path | None = None,
                                  versions_store_file: Path | None = None) -> dict:
    """Adjunta `approved_by_decision` al `version_record` YA BOOTSTRAPPED de
    un artefacto, sin cambiar version ni contenido -- caso real: G6,
    `golden_dataset`. Distinto de `apply_catalog_version_bump`: no hay
    version nueva que escribir, así que no acepta `new_version`. Fail-closed
    en cada paso, mismo orden que el bump: nada se escribe hasta validar
    decisión, estado del artefacto y ausencia de drift desde el bootstrap."""
    base = repo or guard.REPO

    scope = resolver.resolve(guard.DECISION_FAMILY, artifact_id,
                             store_file=decision_store_file)
    if not scope.authorized:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no está autorizado para versionar: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan "
            f"cobertura ({scope.covering_instances!r}) -- no se aplica con una "
            "decisión que no es la que lo autoriza")

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_id), None)
    if current is None:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")

    records = guard.read_version_records(versions_store_file)
    existing = guard.latest_record_for(artifact_id, records)
    if existing is None:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no tiene version_record -- requiere bootstrap primero, "
            "esta función solo aprueba un estado ya fotografiado")
    if existing.get("sha256") != current.sha256:
        raise ArtifactVersionApplyError(
            f"el contenido de {artifact_id!r} cambió desde el bootstrap "
            f"({existing.get('sha256')} -> {current.sha256}) -- esto ya no es una "
            "primera aprobación simple, es un cambio de contenido real")
    if existing.get("approved_by_decision"):
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} ya tiene approved_by_decision="
            f"{existing['approved_by_decision']!r} -- nada que aplicar")

    record = guard.build_version_record(
        current, previous_version=current.version, previous_sha256=current.sha256,
        approved_by_decision=decision_instance_id)

    path = versions_store_file or guard.STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_event("artifact_version_applied", "factory", {
        "artifact_id": artifact_id,
        "from_version": current.version,
        "to_version": current.version,
        "approved_by_decision": decision_instance_id,
        "first_approval": True,
    })

    return record


# ---------------------------------------------------------------------------
# Regularización — el cambio ya está en disco/commiteado, la decisión llega
# después (plan W5V2_ARQ_RETOMAR_Y_FINALIZAR.md, Bloque 2.2)
# ---------------------------------------------------------------------------
#
# Distinta de `propose_artifact_version_change`/`apply_catalog_version_bump`
# (que simulan un cambio FUTURO antes de escribirlo) y de
# `apply_artifact_first_approval` (que exige que el hash NO haya cambiado
# desde el bootstrap). Caso real: `applicability_matrix.yaml` pasó de 2.1 a
# 2.2 (commit `84a7a58`, V6 -- vocabulario de document_types) sin pasar por
# ningún flujo gobernado porque en ese momento no existía uno para esta
# clase. El "antes" no se reconstruye de la nada: viene del último
# `version_record` YA registrado (aquí, el bootstrap de 2.1), nunca de git
# ni de un valor aceptado como parámetro humano.

def propose_regularization_for_applied_change(*, artifact_path: str,
                                               change_reason: str,
                                               proposed_by_id: str,
                                               repo: Path | None = None,
                                               decision_store_file: Path | None = None,
                                               versions_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) una decisión `ARTIFACT_VERSION` que cubra
    una transición que YA ocurrió en disco. `from_version`/`artifact_hash_before`
    se toman del último `version_record` registrado (nunca reconstruidos);
    `to_version`/`expected_hash_after` del estado VIVO medido ahora. Mismos
    6 campos obligatorios que `propose_artifact_version_change` -- la
    decisión resultante se aplica con `apply_regularization_for_applied_change`,
    no con `apply_catalog_version_bump` (que reescribiría un archivo que ya
    está correcto)."""
    base = repo or guard.REPO

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_path), None)
    if current is None:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")

    records = guard.read_version_records(versions_store_file)
    existing = guard.latest_record_for(artifact_path, records)
    if existing is None:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} no tiene ningún version_record previo -- una "
            "regularización necesita un 'antes' ya registrado (p.ej. un "
            "bootstrap), nunca se reconstruye de la nada")
    if existing.get("sha256") == current.sha256 and existing.get("version") == current.version:
        raise ArtifactVersionProposalError(
            f"{artifact_path!r} no cambió desde el último version_record -- "
            "nada que regularizar")

    payload = {
        "artifact_path": artifact_path,
        "artifact_hash_before": existing.get("sha256"),
        "from_version": existing.get("version"),
        "to_version": current.version,
        "expected_hash_after": current.sha256,
        "change_reason": change_reason,
    }

    from factory.services import governance_service as gov
    return gov.propose(
        "ARTIFACT_VERSION", target_ids=[artifact_path], decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=change_reason, payload=payload, store_file=decision_store_file)


def apply_regularization_for_applied_change(artifact_path: str, *,
                                             decision_instance_id: str,
                                             repo: Path | None = None,
                                             decision_store_file: Path | None = None,
                                             versions_store_file: Path | None = None) -> dict:
    """Registra el `version_record` de una regularización ya propuesta y
    confirmada. NUNCA toca el archivo del artefacto -- ya está en el estado
    aprobado, escribirlo de nuevo sería una operación sin sentido y con
    riesgo real de corromper contenido correcto. Mismos checks fail-closed
    que `apply_catalog_version_bump`, sin el paso de escritura del YAML."""
    base = repo or guard.REPO

    scope = resolver.resolve(guard.DECISION_FAMILY, artifact_path,
                             store_file=decision_store_file)
    if not scope.authorized:
        raise ArtifactVersionApplyError(
            f"{artifact_path!r} no está autorizado para versionar: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan "
            f"cobertura ({scope.covering_instances!r}) -- no se aplica con una "
            "decisión que no es la que lo autoriza")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no se encuentra en el almacén de decisiones")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PROPOSAL_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} no declara la transición exacta que autoriza "
            f"(faltan en payload: {missing})")
    if payload["artifact_path"] != artifact_path:
        raise ArtifactVersionApplyError(
            f"{decision_instance_id!r} autoriza artifact_path="
            f"{payload['artifact_path']!r}, no {artifact_path!r} -- decisión de otro "
            "artefacto")

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_path), None)
    if current is None:
        raise ArtifactVersionApplyError(
            f"{artifact_path!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.version != payload["to_version"] or current.sha256 != payload["expected_hash_after"]:
        raise ArtifactVersionApplyError(
            f"el estado vivo (version={current.version!r}, sha256={current.sha256}) "
            "ya no coincide con lo que la decisión declaró -- el archivo cambió desde "
            "que se propuso, re-proponer sobre el estado actual")

    records = guard.read_version_records(versions_store_file)
    existing = guard.latest_record_for(artifact_path, records)
    if existing is not None and existing.get("approved_by_decision"):
        raise ArtifactVersionApplyError(
            f"{artifact_path!r} ya tiene approved_by_decision="
            f"{existing['approved_by_decision']!r} -- nada que aplicar")

    record = guard.build_version_record(
        current, previous_version=payload["from_version"],
        previous_sha256=payload["artifact_hash_before"],
        approved_by_decision=decision_instance_id)

    path = versions_store_file or guard.STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_event("artifact_version_applied", "factory", {
        "artifact_id": artifact_path,
        "from_version": payload["from_version"],
        "to_version": payload["to_version"],
        "approved_by_decision": decision_instance_id,
        "regularization": True,
    })

    return record
