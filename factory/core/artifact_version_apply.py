"""Aplicación gobernada del versionado de artefactos — W5 V2 G4c.

`artifact_version_guard.py` solo MIDE la invariante (hash⟺version⟺decisión);
declara explícitamente que no escribe nada. Este módulo es el tercer paso,
igual que `human_source_registration.apply_source_registration` o
`bootstrap_artifact_versions.py`: el ÚNICO punto que toca disco, y solo
después de que el resolver confirme que existe una decisión `ARTIFACT_VERSION`
`ACTIVE` y `human_confirmed` que cubra el `artifact_id`.

ALCANCE DELIBERADAMENTE ACOTADO: solo la clase `catalog` (el único caso real
hoy, `ARTIFACT_VERSIONING_SPEC.md` §3). Generalizar a matrix/pack/prompt/
golden sin un caso real que lo exija repetiría el error que este roadmap
lleva corregido varias veces (Fase J de `project_w5_v2_regulatory_redesign`:
"no se fabrica código sin un caso real que lo valide").

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

import json
import re
import subprocess
from pathlib import Path

from factory.core import artifact_version_guard as guard
from factory.core import decision_scope_resolver as resolver
from factory.core.audit_writer import write_event

CATALOG_VERSION_LINE = re.compile(r"^catalog_version:\s*'([^']*)'\s*$", re.MULTILINE)


class ArtifactVersionApplyError(Exception):
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
      - la versión declarada ya es `new_version` (nada que aplicar),
      - el archivo no tiene la línea `catalog_version: '...'` esperada.
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

    current = next((s for s in guard.enumerate_artifacts(repo=base)
                    if s.artifact_id == artifact_id), None)
    if current is None:
        raise ArtifactVersionApplyError(
            f"{artifact_id!r} no aparece en enumerate_artifacts() -- ¿archivo ausente?")
    if current.version == new_version:
        raise ArtifactVersionApplyError(
            f"catalog_version ya es {new_version!r} -- nada que aplicar")

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
