"""Versionado de artefactos gobernados — W5 V2 G1.13.

Implementa ARTIFACT_VERSIONING_SPEC.md. Cierra A-7 (grano de aprobación) y
A-9 (alcance decidido pero invisible).

LA INVARIANTE, Y SUS TRES DIRECCIONES
-------------------------------------
    sha256 cambia  ⟺  version cambia  ⟺  existe una decisión ACTIVE que la aprueba

Las tres importan y cada una tiene un caso real detrás:

    hash cambia ⇒ versión cambia    `requirements.yaml` declara `1.0` con un
                                    hash distinto del congelado en la
                                    calificación: contenido cambiado en silencio.
    versión cambia ⇒ hash cambia    "versionar" sin tocar nada para simular
                                    que hubo revisión.
    versión cambia ⇒ hay decisión   `matrix_version: "2.1"` mientras `MC-0001`
                                    solo cubre la `2.0`.

EL PATRÓN QUE SE GENERALIZA
---------------------------
`model_qualification_gate` enumera los prompts por GLOB dinámico, y por eso
fue la primera pieza del sistema que detectó un cambio material sin que nadie
se lo recordara: cuando apareció `cgmp211_prompts.yaml` el fingerprint dejó de
coincidir solo. Si la lista fuera estática, el artefacto nuevo habría pasado
inadvertido.

`enumerate_artifacts()` generaliza ese patrón a las cinco clases: ENUMERA EL
MUNDO, no una lista congelada. `test_vz09_*` lo protege contra la
"optimización" futura que lo convertiría en una tupla.

CANONICALIZACION
----------------
El hash se calcula sobre el CONTENIDO SEMANTICO, no sobre los bytes: reordenar
claves de un YAML o cambiar un comentario no debe disparar una versión nueva,
y añadir un criterio sí. El propio campo de versión se EXCLUYE siempre -- si
no, cambiar la versión cambiaría el hash y la invariante sería trivialmente
cierta, y por tanto inútil.

LO QUE ESTE MODULO NO HACE
--------------------------
No cambia ninguna versión, no escribe ningún `version_record` y no corrige
ninguna inconsistencia. Solo las MIDE y las reporta. El bootstrap del almacén
vive en `scripts/ops/bootstrap_artifact_versions.py` (dry-run por defecto), y
la corrección del catálogo a 2.0 es G4c, deliberadamente DESPUES de G4a: hoy
el pack 211 está vacío, así que aprobar sus criterios volvería a cambiar el
hash y obligaría a versionar dos veces en 48 h. Versionar dos veces no añade
trazabilidad, añade ruido.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from factory.core import decision_scope_resolver as _resolver

DECISION_FAMILY = "ARTIFACT_VERSION"

REPO = Path(__file__).resolve().parents[2]
FACTORY = REPO / "factory"

STORE_FILE = FACTORY / "registry" / "artifact_versions.jsonl"

CATALOG_PATH = FACTORY / "regulatory" / "requirement_catalog" / "requirements.yaml"
MATRIX_PATH = FACTORY / "regulatory" / "applicability_matrix.yaml"
PROMPTS_DIR = FACTORY / "engines" / "gmpai_integrity" / "prompts"
GOLDEN_PATH = (FACTORY / "regulatory" / "golden_dataset"
               / "semantic_verification_golden_dataset.py")

ARTIFACT_CLASSES = ("catalog", "applicability_matrix", "evidence_pack",
                    "prompt", "golden_dataset")

# Campos excluidos del hash canónico, por clase. El campo de versión SIEMPRE
# se excluye (ver docstring). `generated_at` y `run_context` tampoco son
# contenido: son metadatos de la corrida que lo produjo.
_EXCLUDED = {
    "catalog": ("catalog_version", "generated_at", "run_context"),
    "applicability_matrix": ("matrix_version", "approval"),
    "prompt": ("prompt_version",),
}

# Los SEIS campos de juicio regulatorio humano de un evidence pack
# (EVIDENCE_PACK_GOVERNANCE_AND_D2A_SPEC §2.1). El resto de los ~30 campos es
# derivado o determinista: no se edita, se calcula, y meterlo en el hash haría
# que un recálculo automático pareciera una revisión humana.
PACK_GOVERNED_FIELDS = (
    "evidence_min_criteria",
    "exclusion_criteria",
    "weak_keywords",
    "typical_insufficient_evidence",
    "governed_interpretation",
    "expected_doc_types",
)


@dataclass(frozen=True)
class ArtifactState:
    """Lo que un artefacto DICE ser hoy, medido en disco."""
    artifact: str
    artifact_id: str
    version: str | None
    sha256: str


@dataclass(frozen=True)
class Finding:
    artifact: str
    artifact_id: str
    severity: str          # FAIL | WARN
    code: str
    detail: str


# ---------------------------------------------------------------------------
# Canonicalización
# ---------------------------------------------------------------------------

def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def _sha256_of(obj) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def canonical_hash_yaml(path: Path, artifact_class: str) -> str:
    """Hash del contenido semántico de un YAML.

    `yaml.safe_load` ya descarta comentarios y orden de claves; el
    `sort_keys=True` del volcado descarta el orden que quedara. Lo que
    sobrevive es lo que significa algo.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for field in _EXCLUDED.get(artifact_class, ()):
        data.pop(field, None)
    return _sha256_of(data)


def canonical_hash_pack(pack: dict) -> str:
    """Hash de los seis campos gobernados de un evidence pack.

    Un campo ausente se hashea como ausente, no como vacío: `None` y `[]` son
    estados distintos -- "nadie lo ha escrito" y "se decidió que no hay
    ninguno" -- y colapsarlos borraría justo la diferencia que el pack 211
    hace visible hoy (0 criterios, pendiente de interpretación humana).
    """
    return _sha256_of({f: pack[f] for f in PACK_GOVERNED_FIELDS if f in pack})


def canonical_hash_golden(path: Path) -> str:
    """Hash del AST del módulo del Golden Dataset.

    El Golden Dataset no es un fichero de datos sino código: los casos son
    funciones. Se hashea el AST y no el texto porque comentarios, saltos de
    línea y formato no son contenido; añadir, quitar o reescribir un caso sí
    cambia el AST.

    LIMITACION DECLARADA: `ast.dump` no distingue un cambio de nombre de
    variable local de un cambio de comportamiento. Es más estricto de lo
    necesario (renombrar dispara versión) y nunca más laxo, que es el lado
    seguro para un artefacto de verificación.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    return hashlib.sha256(ast.dump(tree).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Enumeración — el mundo, no una lista congelada
# ---------------------------------------------------------------------------

def enumerate_artifacts(*, repo: Path | None = None) -> list[ArtifactState]:
    """Estado ACTUAL de los artefactos de las cinco clases.

    Todo lo enumerable se enumera por glob o por recorrido del contenido:
    los prompts con `glob("*_prompts.yaml")`, los packs recorriendo los
    requisitos del catálogo. Ninguna lista está escrita a mano, y ese es el
    punto -- una lista a mano no detecta lo que se añadió sin avisar.
    """
    base = repo or REPO
    factory = base / "factory"
    catalog_path = factory / "regulatory" / "requirement_catalog" / "requirements.yaml"
    matrix_path = factory / "regulatory" / "applicability_matrix.yaml"
    prompts_dir = factory / "engines" / "gmpai_integrity" / "prompts"
    golden_path = (factory / "regulatory" / "golden_dataset"
                   / "semantic_verification_golden_dataset.py")

    out: list[ArtifactState] = []

    if catalog_path.is_file():
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        out.append(ArtifactState(
            artifact="catalog",
            artifact_id=catalog_path.relative_to(base).as_posix(),
            version=_as_str(catalog.get("catalog_version")),
            sha256=canonical_hash_yaml(catalog_path, "catalog"),
        ))
        # Los packs viven DENTRO del catálogo pero se versionan por separado:
        # A-7 es exactamente eso -- aprobación de grano de fichero sobre
        # contenido de grano de fila.
        for req_id, pack in sorted((catalog.get("requirements") or {}).items()):
            out.append(ArtifactState(
                artifact="evidence_pack",
                artifact_id=req_id,
                version=_as_str(pack.get("pack_version")),
                sha256=canonical_hash_pack(pack),
            ))

    if matrix_path.is_file():
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
        out.append(ArtifactState(
            artifact="applicability_matrix",
            artifact_id=matrix_path.relative_to(base).as_posix(),
            version=_as_str(matrix.get("matrix_version")),
            sha256=canonical_hash_yaml(matrix_path, "applicability_matrix"),
        ))

    if prompts_dir.is_dir():
        for path in sorted(prompts_dir.glob("*_prompts.yaml")):
            meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            out.append(ArtifactState(
                artifact="prompt",
                artifact_id=path.relative_to(base).as_posix(),
                version=_as_str(meta.get("prompt_version")),
                sha256=canonical_hash_yaml(path, "prompt"),
            ))

    if golden_path.is_file():
        out.append(ArtifactState(
            artifact="golden_dataset",
            artifact_id=golden_path.relative_to(base).as_posix(),
            # Sin campo de versión declarado. `None` es el valor honesto: el
            # artefacto existe y no está versionado. Inventarle un "1.0" sería
            # fabricar una trazabilidad que nadie firmó.
            version=None,
            sha256=canonical_hash_golden(golden_path),
        ))

    return out


def _as_str(value) -> str | None:
    """YAML lee `1.0` como float. Se normaliza a texto sin reformatear: la
    versión es una etiqueta, no un número con el que se opere."""
    if value is None:
        return None
    return str(value)


# ---------------------------------------------------------------------------
# Almacén de version_records
# ---------------------------------------------------------------------------

def build_version_record(state: ArtifactState, *,
                         previous_version: str | None = None,
                         previous_sha256: str | None = None,
                         approved_by_decision: str | None = None,
                         bootstrap: bool = False,
                         bootstrap_note: str = "") -> dict:
    record = {
        "artifact": state.artifact,
        "artifact_id": state.artifact_id,
        "version": state.version,
        "sha256": state.sha256,
        "previous_version": previous_version,
        "previous_sha256": previous_sha256,
        "approved_by_decision": approved_by_decision,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if bootstrap:
        record["bootstrap"] = True
        record["bootstrap_note"] = bootstrap_note
    return record


def read_version_records(store_file: Path | None = None) -> list[dict]:
    """Lee el almacén append-only. Fail-closed: ilegible == vacío, nunca una
    excepción que un `try` del llamador convierta en "siga adelante"."""
    path = store_file or STORE_FILE
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def latest_record_for(artifact_id: str, records: list[dict]) -> dict | None:
    """El último registro de ese artefacto. Append-only: el último gana."""
    matching = [r for r in records if r.get("artifact_id") == artifact_id]
    return matching[-1] if matching else None


# ---------------------------------------------------------------------------
# La guardia
# ---------------------------------------------------------------------------

CONTENT_CHANGED_VERSION_SAME = "CONTENT_CHANGED_VERSION_SAME"
VERSION_CHANGED_CONTENT_SAME = "VERSION_CHANGED_CONTENT_SAME"
VERSION_CHANGED_WITHOUT_DECISION = "VERSION_CHANGED_WITHOUT_DECISION"
NO_VERSION_RECORD = "NO_VERSION_RECORD"


def check_artifact(state: ArtifactState, record: dict | None, *,
                   decision_store_file: Path | None = None) -> list[Finding]:
    """Las cuatro reglas de §2.3 sobre UN artefacto.

    Las tres primeras son FAIL desde el día uno: son corrupción de
    trazabilidad. La cuarta es WARN, porque hoy NINGUN artefacto tiene
    `version_record` -- el almacén no existe todavía y convertirlo en FAIL
    dejaría la fábrica en rojo por no haber hecho aún el bootstrap, que es
    una tarea pendiente, no una corrupción.
    """
    if record is None:
        return [Finding(state.artifact, state.artifact_id, "WARN",
                        NO_VERSION_RECORD,
                        "sin version_record: estado inicial, pendiente de bootstrap")]

    hash_changed = state.sha256 != record.get("sha256")
    version_changed = state.version != record.get("version")
    findings: list[Finding] = []

    if hash_changed and not version_changed:
        findings.append(Finding(
            state.artifact, state.artifact_id, "FAIL", CONTENT_CHANGED_VERSION_SAME,
            f"contenido cambiado con versión igual ({state.version}): "
            f"{record.get('sha256')} -> {state.sha256}"))

    if version_changed and not hash_changed:
        findings.append(Finding(
            state.artifact, state.artifact_id, "FAIL", VERSION_CHANGED_CONTENT_SAME,
            f"versión cambiada sin cambio de contenido: "
            f"{record.get('version')} -> {state.version}"))

    if version_changed:
        # Se pregunta al resolver, no al campo `approved_by_decision` del
        # registro. Un registro puede NOMBRAR una decisión revocada, superada
        # o nunca confirmada; solo el resolver sabe si sigue autorizando.
        scope = _resolver.resolve(DECISION_FAMILY, state.artifact_id,
                                  store_file=decision_store_file)
        if not scope.authorized:
            findings.append(Finding(
                state.artifact, state.artifact_id, "FAIL",
                VERSION_CHANGED_WITHOUT_DECISION,
                f"versión {record.get('version')} -> {state.version} sin decisión "
                f"ACTIVE que la apruebe ({scope.coverage_basis}: {scope.denial_reason})"))

    return findings


def guard_report(*, store_file: Path | None = None,
                 decision_store_file: Path | None = None,
                 repo: Path | None = None) -> dict:
    """Reporte completo. Lo consume el paso 7/7 de Gate 0 (cableado en G1.17).

    Read-only: no escribe el almacén, no corrige versiones, no aprueba nada.
    """
    states = enumerate_artifacts(repo=repo)
    records = read_version_records(store_file)

    findings: list[Finding] = []
    for state in states:
        findings.extend(check_artifact(
            state, latest_record_for(state.artifact_id, records),
            decision_store_file=decision_store_file))

    fails = [f for f in findings if f.severity == "FAIL"]
    warns = [f for f in findings if f.severity == "WARN"]
    return {
        "artifacts_seen": len(states),
        "by_class": {c: sum(1 for s in states if s.artifact == c)
                     for c in ARTIFACT_CLASSES},
        "records_in_store": len(records),
        "status": "FAIL" if fails else ("WARN" if warns else "PASS"),
        "fail_count": len(fails),
        "warn_count": len(warns),
        "findings": [f.__dict__ for f in findings],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
