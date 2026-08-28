"""WP-A -- Fingerprint de corrida: identidad de ejecucion != resultado + attestation de la
base de fuentes runtime (conjunto estatico y reproducible, NO "codigo ejecutado").

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-A ; docs_plan/ADR_HARDENING_V2.md.

Tres digests SEPARADOS, deterministas, sin red, SIN rutas absolutas:

  INPUT_CONFIG_FINGERPRINT
      Identidad de "que se pidio + como se configuro + con que base de fuentes runtime
      (conjunto estatico y reproducible)".
      sha256( canonical_json({
          inputs                 : [{document_id, sha256}] ordenado por document_id
          extraction_version
          canonical_schema_digest : sha256 de las FUENTES que definen el modelo canonico
          graph_schema_digest     : sha256 de la FUENTE que define el esquema del grafo
          consumed_artifacts      : { nombre: {version, sha256} }  -- SOLO los que ese entrypoint consume
          applied_thresholds      : { ... }                        -- SOLO los que ese entrypoint usa
          source_attestation_digest : ata la base de fuentes runtime alcanzable
                                      (cierre estatico de imports factory.* por AST) + py X.Y
                                      -- NO es prueba de que ese codigo se haya ejecutado
      }) )

  FINDINGS_FINGERPRINT
      Identidad de "que FINDINGS salieron" -- NO es un fingerprint del paquete de corrida.
      Hashea la lista de findings reducida a sus campos semanticos estables + la evidencia
      anclada (source_hash + anchored_quote) + provenance determinista minima.
      EXCLUYE: finding_id, provenance.run_id, timestamps, y el ORDEN de la lista
      (los findings se ordenan por su serializacion canonica antes de hashear).

  RUN_ATTESTATION  (metadata / advisory -- NO identidad logica)
      timestamp_utc, wall_clock_seconds, host, pid, active_engine, routing_source,
      source_attestation (manifest completo de modulos: ruta relativa al repo + sha256),
      git {commit, dirty, describe}  -- ADVISORY, no entra en ningun digest de identidad.

Determinismo -- decisiones clave (precision de Capa 9, 2026-08-28):
  * SOURCE_ATTESTATION usa el CIERRE ESTATICO de imports `factory.*` a partir de un
    entrypoint declarado (AST sobre las fuentes en disco), NO el conjunto variable de
    `sys.modules` observado tras ejecutar.
  * Si no hay una version de esquema autoritativa, se usa un `schema_digest` sobre las
    FUENTES que definen ese esquema; su alcance esta documentado en `_SCHEMA_SOURCES`.
  * Ninguna ruta absoluta entra a ningun digest ni a la metadata: todo es relativo a la
    raiz del repo; un archivo fuera del repo aporta solo su basename.
  * git / host / timestamp / pid / tiempos son metadata; nunca identidad.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ATTESTATION_SCHEMA = "wp-a/run-attestation/1"
INPUT_CONFIG_SCHEMA = "wp-a/input-config/1"
FINDINGS_SCHEMA = "wp-a/findings/1"

_REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Entrypoints declarados y los artefactos de configuracion que CADA UNO consume.
# (El codigo ejecutado se deriva por cierre estatico de imports; esto es solo la
#  config gobernada -- YAML -- que ese entrypoint puede cargar.)
# ---------------------------------------------------------------------------
ENTRYPOINTS = {
    "v2_runtime": "factory.regulatory.validation_v2.v2_runtime",
    "suite_c_formal": "factory.regulatory.validation_v2.technical_suite_c",
    "real_corpus_technical": "factory.regulatory.validation_v2.real_corpus_technical",
}

_ARTIFACT_REGISTRY = {
    "technical_completeness_rules.yaml": "factory/regulatory/requirement_catalog/technical_completeness_rules.yaml",
    "risk_matrix.yaml": "factory/regulatory/findings/risk_matrix.yaml",
    "requirements.yaml": "factory/regulatory/requirement_catalog/requirements.yaml",
    "decomposition.yaml": "factory/regulatory/requirement_catalog/decomposition.yaml",
    "requirement_terms.yaml": "factory/regulatory/requirement_terms.yaml",
    "technical_suite_c.yaml": "factory/regulatory/validation_v2/fixtures_draft/technical_suite_c.yaml",
}

_CONSUMED_BY_ENTRYPOINT = {
    "v2_runtime": (
        "technical_completeness_rules.yaml", "risk_matrix.yaml", "requirements.yaml",
        "decomposition.yaml", "requirement_terms.yaml",
    ),
    "suite_c_formal": (
        "technical_suite_c.yaml", "technical_completeness_rules.yaml", "risk_matrix.yaml",
        "requirements.yaml",
    ),
    "real_corpus_technical": (
        "technical_completeness_rules.yaml", "risk_matrix.yaml", "requirements.yaml",
    ),
}

# Fuentes que DEFINEN cada esquema. Alcance explicito -- si algun dia hay una constante
# de version autoritativa, esta se sustituye por ella.
_SCHEMA_SOURCES = {
    # dataclasses del modelo canonico + DDL/orden de campos de la persistencia SQLite
    "canonical_schema_digest": (
        "factory/regulatory/canonical/model.py",
        "factory/regulatory/canonical/persistence.py",
    ),
    # tipos de nodo, relaciones tipadas y DDL del grafo
    "graph_schema_digest": (
        "factory/regulatory/graph/store.py",
    ),
}

_VERSION_KEYS = ("version", "decomposition_version", "risk_matrix_version", "schema_version")


# ---------------------------------------------------------------------------
# helpers deterministas
# ---------------------------------------------------------------------------
def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _canonical_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_canon(obj) -> str:
    return _sha256_bytes(_canonical_json(obj))


def _rel(p: Path | str) -> str:
    """Ruta relativa al repo, posix. Un archivo fuera del repo aporta solo su basename
    (nunca una ruta absoluta del servidor)."""
    p = Path(p).resolve()
    try:
        return p.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return p.name


# ---------------------------------------------------------------------------
# cierre estatico de imports factory.*  -- base de fuentes runtime alcanzable
# desde el entrypoint (conjunto estatico y reproducible; NO "codigo ejecutado",
# NO cobertura de ramas, NO sys.modules)
# ---------------------------------------------------------------------------
def _module_to_path(mod: str) -> Path | None:
    rel = Path(*mod.split("."))
    for cand in (_REPO_ROOT / rel.with_suffix(".py"), _REPO_ROOT / rel / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _iter_factory_imports(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("factory."):
                    out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith("factory."):
                out.add(node.module)
                for a in node.names:
                    out.add(f"{node.module}.{a.name}")  # `from x.y import z` -> quiza x.y.z es submodulo
    return out


def static_import_closure(entry_module: str) -> list[tuple[str, str]]:
    """Cierre transitivo de imports `factory.*` alcanzables (AST) desde `entry_module`,
    sobre las fuentes EN DISCO. Determinista, independiente de `sys.modules`.
    Devuelve [(ruta_relativa_repo, sha256_contenido)] ordenado por ruta."""
    seen: set[str] = set()
    files: dict[str, str] = {}
    queue = [entry_module]
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        p = _module_to_path(mod)
        if p is None:
            continue
        files[_rel(p)] = _sha256_file(p)
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for imp in _iter_factory_imports(tree):
            if imp not in seen:
                queue.append(imp)
    return sorted(files.items())


def _schema_digest(rel_paths: tuple[str, ...]) -> str:
    parts = []
    for rp in sorted(rel_paths):
        fp = _REPO_ROOT / rp
        parts.append([rp, _sha256_file(fp) if fp.is_file() else "ABSENT"])
    return _sha256_canon(parts)


def schema_digests() -> dict:
    return {name: _schema_digest(src) for name, src in _SCHEMA_SOURCES.items()}


# ---------------------------------------------------------------------------
# artefactos de configuracion consumidos
# ---------------------------------------------------------------------------
def _artifact_version(path: Path) -> str | None:
    try:
        import yaml as _yaml
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for k in _VERSION_KEYS:
        if k in data and data[k] is not None:
            return str(data[k])
    return None


def artifact_entry(rel_path: str) -> dict:
    fp = _REPO_ROOT / rel_path
    if not fp.is_file():
        return {"version": None, "sha256": "ABSENT"}
    return {"version": _artifact_version(fp), "sha256": _sha256_file(fp)}


def consumed_artifacts_for(entrypoint: str, *, tier1_requirements: list | None = None) -> dict:
    if entrypoint not in _CONSUMED_BY_ENTRYPOINT:
        raise KeyError(f"entrypoint desconocido: {entrypoint!r} (permitidos: {sorted(ENTRYPOINTS)})")
    out: dict = {}
    for name in _CONSUMED_BY_ENTRYPOINT[entrypoint]:
        out[name] = artifact_entry(_ARTIFACT_REGISTRY[name])
    if tier1_requirements is not None:
        out["_TIER1_REQUIREMENTS"] = {
            "version": None,
            "sha256": _sha256_canon(sorted(str(x) for x in tier1_requirements)),
        }
    return out


# ---------------------------------------------------------------------------
# inputs  (document_id + sha256 del PDF, tomado del canonical_store)
# ---------------------------------------------------------------------------
def inputs_from_canon(document_ids: list[str], canon_dir) -> list[dict]:
    from factory.regulatory.canonical.persistence import CanonicalStore
    out = []
    for did in document_ids:
        sha = None
        try:
            with CanonicalStore(did, store_dir=Path(canon_dir)) as cs:
                docs = cs.all("document")
                if docs:
                    sha = docs[0].get("sha256")
        except Exception:
            sha = None
        out.append({"document_id": str(did), "sha256": sha})
    return sorted(out, key=lambda d: d["document_id"])


# ---------------------------------------------------------------------------
# findings  (identidad del resultado -- SOLO findings, no el paquete)
# ---------------------------------------------------------------------------
_FINDING_SEMANTIC_FIELDS = (
    "finding_class", "subtype", "severity", "document", "page", "section",
    "source_hash", "requirement_id", "regulatory_basis", "technical_basis",
    "risk", "confidence", "machine_state", "human_state", "rationale",
)


def _normalized_finding(f) -> dict:
    g = lambda name: getattr(f, name, None)  # noqa: E731
    p = getattr(f, "provenance", None)
    row = {k: g(k) for k in _FINDING_SEMANTIC_FIELDS}
    row["anchored_quote"] = g("source_text")  # evidencia anclada
    row["evidence_ids"] = sorted(str(x) for x in (g("evidence_ids") or []))
    row["related_finding_ids"] = sorted(str(x) for x in (g("related_finding_ids") or []))
    row["provenance"] = {
        "agent_id": getattr(p, "agent_id", None),
        "extraction_version": getattr(p, "extraction_version", None),
        "subcriterion_ref": getattr(p, "subcriterion_ref", None),
        "adjudicator_state": getattr(p, "adjudicator_state", None),
        "graph_path": getattr(p, "graph_path", None),
        # EXCLUIDO deliberadamente: run_id (volatil), document_id (== document)
    }
    return row


def findings_fingerprint(findings) -> str:
    rows = [_normalized_finding(f) for f in findings]
    rows_sorted = sorted(rows, key=_canonical_json)  # inmune al orden de la lista
    return _sha256_canon({"schema": FINDINGS_SCHEMA, "count": len(rows_sorted), "findings": rows_sorted})


# ---------------------------------------------------------------------------
# attestation (advisory)
# ---------------------------------------------------------------------------
def _git_advisory() -> dict:
    def _run(args):
        try:
            r = subprocess.run(["git", "-C", str(_REPO_ROOT), *args],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None
    commit = _run(["rev-parse", "HEAD"])
    if not commit:
        return {"commit": "UNKNOWN", "dirty": None, "describe": None}
    status = _run(["status", "--porcelain"])
    return {
        "commit": commit,
        "dirty": (status != "" and status is not None) if status is not None else None,
        "describe": _run(["describe", "--always", "--dirty"]),
    }


_KEY_DEPS = ("pdfplumber", "pypdf", "PyYAML", "python-docx", "python-dateutil")


def _dep_versions() -> dict:
    out: dict = {}
    try:
        from importlib.metadata import PackageNotFoundError, version
        for name in _KEY_DEPS:
            try:
                out[name] = version(name)
            except PackageNotFoundError:
                out[name] = None
    except Exception:
        pass
    return out


def _routing_source() -> str:
    if os.environ.get("V2_ANALYZER_ROUTING") is not None:
        return "env"
    if (Path(__file__).resolve().parent / "routing.txt").exists():
        return "file"
    return "default"


def _active_engine() -> str:
    try:
        from factory.regulatory.validation_v2.analyzer_router import active_engine
        return str(active_engine())
    except Exception:
        return "UNKNOWN"


def source_attestation(entry_module: str) -> dict:
    manifest = [{"path": rp, "sha256": sha} for rp, sha in static_import_closure(entry_module)]
    manifest_sha256 = _sha256_canon([[m["path"], m["sha256"]] for m in manifest])
    py_mm = f"{sys.version_info.major}.{sys.version_info.minor}"
    return {
        "entrypoint": entry_module,
        "module_manifest": manifest,
        "module_manifest_sha256": manifest_sha256,
        "python_version_mm": py_mm,                 # entra en el digest de identidad
        "python_version": platform.python_version(),  # advisory
        "key_deps": _dep_versions(),                # advisory
        "git": _git_advisory(),                     # advisory
    }


def source_attestation_digest(att: dict) -> str:
    """Identidad de la BASE DE FUENTES RUNTIME (cierre estatico de imports factory.*
    alcanzable desde el entrypoint) + python major.minor. NO es prueba de que ese
    codigo se haya ejecutado. git / deps / python patch NO entran."""
    return _sha256_canon({
        "entrypoint": att["entrypoint"],
        "module_manifest_sha256": att["module_manifest_sha256"],
        "python_version_mm": att["python_version_mm"],
    })


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def compute_fingerprints(*, entrypoint: str, inputs: list[dict], extraction_version: str,
                         consumed_artifacts: dict, applied_thresholds: dict, findings,
                         wall_clock_seconds: float | None = None) -> dict:
    """Devuelve los tres digests + sus piezas. `entrypoint` in ENTRYPOINTS."""
    if entrypoint not in ENTRYPOINTS:
        raise KeyError(f"entrypoint desconocido: {entrypoint!r} (permitidos: {sorted(ENTRYPOINTS)})")
    entry_module = ENTRYPOINTS[entrypoint]

    att = source_attestation(entry_module)
    sa_digest = source_attestation_digest(att)
    sch = schema_digests()

    input_config = {
        "schema": INPUT_CONFIG_SCHEMA,
        "entrypoint": entrypoint,
        "inputs": sorted(
            [{"document_id": str(i.get("document_id")), "sha256": i.get("sha256")} for i in inputs],
            key=lambda d: d["document_id"],
        ),
        "extraction_version": extraction_version,
        "canonical_schema_digest": sch["canonical_schema_digest"],
        "graph_schema_digest": sch["graph_schema_digest"],
        "consumed_artifacts": consumed_artifacts,
        "applied_thresholds": applied_thresholds,
        "source_attestation_digest": sa_digest,
    }
    input_config_fp = _sha256_canon(input_config)
    findings_fp = findings_fingerprint(findings)

    run_attestation = {
        "schema": ATTESTATION_SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wall_clock_seconds": wall_clock_seconds,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "active_engine": _active_engine(),
        "routing_source": _routing_source(),
        "source_attestation": att,
        "note": ("git/host/timestamp/pid/tiempos son advisory, NO identidad logica. "
                 "module_manifest_sha256 (cierre estatico de imports factory.* por AST) + "
                 "python_version_mm identifican la BASE DE FUENTES RUNTIME alcanzable desde el "
                 "entrypoint; NO son prueba de que ese codigo se haya ejecutado."),
    }

    return {
        "input_config_fingerprint": input_config_fp,
        "findings_fingerprint": findings_fp,
        "run_attestation": run_attestation,
        "schema_digests": sch,
        "input_config": input_config,  # dict transparente (para tests / auditoria)
    }
