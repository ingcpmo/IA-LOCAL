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
#: H-4 (2026-08-29): el grafo es un artefacto DERIVADO, no una ENTRADA.
#: `INPUT_CONFIG_FINGERPRINT` NO lo incorpora. Se calcula un digest SEPARADO
#: (`GRAPH_SNAPSHOT_FINGERPRINT`) y `RUN_ATTESTATION` liga los tres.
GRAPH_SNAPSHOT_SCHEMA = "wp-a/graph-snapshot/1"

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
    # WP-B: heurísticas de adecuación de extracción (DRAFT_UNSIGNED) -- consumidas por
    # v2_runtime y real_corpus_technical al construir analysis_coverage.json.
    "extraction_adequacy_thresholds.yaml":
        "factory/regulatory/requirement_catalog/extraction_adequacy_thresholds.yaml",
    # H-7: parámetro gobernado del modo de cobertura + criticidad GxP estructurada.
    "analysis_coverage_mode.yaml":
        "factory/regulatory/requirement_catalog/analysis_coverage_mode.yaml",
    "gxp_criticality.yaml":
        "factory/regulatory/requirement_catalog/gxp_criticality.yaml",
}

_CONSUMED_BY_ENTRYPOINT = {
    "v2_runtime": (
        "technical_completeness_rules.yaml", "risk_matrix.yaml", "requirements.yaml",
        "decomposition.yaml", "requirement_terms.yaml", "extraction_adequacy_thresholds.yaml",
        "analysis_coverage_mode.yaml", "gxp_criticality.yaml",
    ),
    "suite_c_formal": (
        "technical_suite_c.yaml", "technical_completeness_rules.yaml", "risk_matrix.yaml",
        "requirements.yaml",
    ),
    "real_corpus_technical": (
        "technical_completeness_rules.yaml", "risk_matrix.yaml", "requirements.yaml",
        "extraction_adequacy_thresholds.yaml",
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
    "evidence_basis",   # WP-B: metadata epistémica aditiva (PRESENCE|ABSENCE_DEPENDENT|INDETERMINATE|None)
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
        # H-4 (2026-08-29): la CLAVE se conserva (compat. con la linea base
        # historica b5196a71…) pero su VALOR se fija a None: `graph_path` es un
        # PUNTERO a un artefacto DERIVADO (el snapshot de grafo), no contenido
        # semantico del RESULTADO. Su identidad vive en GRAPH_SNAPSHOT_FINGERPRINT.
        # Poblar provenance.graph_path (v2_runtime._stamp_graph_path) NO mueve
        # findings_fingerprint.
        "graph_path": None,
        # EXCLUIDO: run_id (volatil), document_id (== document)
    }
    return row


def findings_fingerprint(findings) -> str:
    rows = [_normalized_finding(f) for f in findings]
    rows_sorted = sorted(rows, key=_canonical_json)  # inmune al orden de la lista
    return _sha256_canon({"schema": FINDINGS_SCHEMA, "count": len(rows_sorted), "findings": rows_sorted})


# ---------------------------------------------------------------------------
# graph snapshot  (H-4 -- artefacto DERIVADO, digest SEPARADO de INPUT_CONFIG)
# ---------------------------------------------------------------------------
def normalize_graph_snapshot(nodes: list, edges: list) -> dict:
    """Representacion canonica y determinista del grafo construido para una
    corrida. `nodes`/`edges` son iterables de dicts o de objetos con esos
    campos. El orden de entrada NO importa (se ordena). Nada volatil entra."""
    def _n(x):
        g = (lambda k: x.get(k)) if isinstance(x, dict) else (lambda k: getattr(x, k, None))
        return {
            "node_id": str(g("node_id")),
            "kind": g("kind"),
            "document_id": g("document_id"),
            "label": g("label"),
            "attrs": g("attrs") or {},
        }

    def _e(x):
        g = (lambda k: x.get(k)) if isinstance(x, dict) else (lambda k: getattr(x, k, None))
        return {
            "src_id": str(g("src_id")),
            "dst_id": str(g("dst_id")),
            "rel": g("rel"),
            "attrs": g("attrs") or {},
        }

    ns = sorted((_n(x) for x in nodes), key=_canonical_json)
    es = sorted((_e(x) for x in edges), key=_canonical_json)
    return {
        "schema": GRAPH_SNAPSHOT_SCHEMA,
        "node_count": len(ns),
        "edge_count": len(es),
        "edges_by_rel": _edges_by_rel(es),
        "nodes": ns,
        "edges": es,
    }


def _edges_by_rel(edges: list) -> dict:
    out: dict[str, int] = {}
    for e in edges:
        out[e["rel"]] = out.get(e["rel"], 0) + 1
    return dict(sorted(out.items()))


#: H-4 (2026-08-29): el fingerprint del grafo captura la TOPOLOGIA -- nodos por
#: identidad (node_id + kind + document_id + label) y aristas por extremos +
#: relacion (src_id + dst_id + rel). Los `attrs` se CONSERVAN en el snapshot
#: (auditoria humana) pero NO entran al digest: `edge.attrs["via_ref"]` lo
#: escribe `build._safe_edge` con "ultimo ref que caso gana" y el orden de
#: iteracion sobre un `set`/`dict` de refs varia con PYTHONHASHSEED entre
#: procesos -- misma topologia, distinto `via_ref` (medido: 71/1344 aristas).
#: Incluir `attrs` rompia "mismos inputs -> mismo graph fingerprint" entre
#: procesos. La identidad de la arista (`_edge_id`) NO depende de attrs, asi que
#: la topologia es estable; el digest se ancla a ella.
def _structural_node(n: dict) -> dict:
    return {"node_id": n.get("node_id"), "kind": n.get("kind"),
            "document_id": n.get("document_id"), "label": n.get("label")}


def _structural_edge(e: dict) -> dict:
    return {"src_id": e.get("src_id"), "dst_id": e.get("dst_id"), "rel": e.get("rel")}


def graph_snapshot_fingerprint(snapshot: dict) -> str:
    """Digest determinista de la TOPOLOGIA del grafo DERIVADO. Cambia si cambia
    cualquier nodo (id/kind/document_id/label) o arista (src/dst/rel); estable
    entre procesos para los mismos inputs. `attrs` NO entra (ver nota arriba)."""
    ns = sorted((_structural_node(n) for n in snapshot.get("nodes", [])), key=_canonical_json)
    es = sorted((_structural_edge(e) for e in snapshot.get("edges", [])), key=_canonical_json)
    return _sha256_canon({
        "schema": GRAPH_SNAPSHOT_SCHEMA,
        "node_count": snapshot.get("node_count"),
        "edge_count": snapshot.get("edge_count"),
        "nodes": ns,
        "edges": es,
    })


def graph_snapshot_from_store(project_id: str, graph_dir) -> dict:
    """Lee el GraphStore recien construido y devuelve el snapshot normalizado.
    Solo lectura -- no modifica el store."""
    from factory.regulatory.graph.store import GraphStore
    g = GraphStore(project_id, store_dir=Path(graph_dir))
    try:
        nodes = list(g.nodes())
        edges = list(g.edges())
    finally:
        g.close()
    return normalize_graph_snapshot(nodes, edges)


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
                         graph_snapshot: dict | None = None,
                         wall_clock_seconds: float | None = None) -> dict:
    """Devuelve los digests + sus piezas. `entrypoint` in ENTRYPOINTS.

    H-4: si se pasa `graph_snapshot` (dict de `normalize_graph_snapshot`), se
    calcula un `GRAPH_SNAPSHOT_FINGERPRINT` SEPARADO y `run_attestation.fingerprints`
    liga los tres (input_config, graph_snapshot, findings). El grafo NO entra a
    `INPUT_CONFIG_FINGERPRINT`."""
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
    graph_snapshot_fp = graph_snapshot_fingerprint(graph_snapshot) if graph_snapshot is not None else None

    run_attestation = {
        "schema": ATTESTATION_SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "wall_clock_seconds": wall_clock_seconds,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "active_engine": _active_engine(),
        "routing_source": _routing_source(),
        "source_attestation": att,
        # H-4: los tres digests, ligados. input_config = ENTRADAS; graph_snapshot
        # = artefacto DERIVADO; findings = RESULTADO. Ninguno contiene al otro.
        "fingerprints": {
            "input_config_fingerprint": input_config_fp,
            "graph_snapshot_fingerprint": graph_snapshot_fp,
            "findings_fingerprint": findings_fp,
        },
        "note": ("git/host/timestamp/pid/tiempos son advisory, NO identidad logica. "
                 "module_manifest_sha256 (cierre estatico de imports factory.* por AST) + "
                 "python_version_mm identifican la BASE DE FUENTES RUNTIME alcanzable desde el "
                 "entrypoint; NO son prueba de que ese codigo se haya ejecutado. "
                 "El grafo es un artefacto DERIVADO: su identidad esta en "
                 "graph_snapshot_fingerprint, NO en input_config_fingerprint."),
    }

    return {
        "input_config_fingerprint": input_config_fp,
        "graph_snapshot_fingerprint": graph_snapshot_fp,
        "findings_fingerprint": findings_fp,
        "run_attestation": run_attestation,
        "schema_digests": sch,
        "input_config": input_config,  # dict transparente (para tests / auditoria)
    }
