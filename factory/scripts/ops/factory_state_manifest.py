#!/usr/bin/env python3
"""H-6F (2026-08-29) -- inventario + clasificación del estado persistente de
GMP AI Factory y construcción del MANIFEST del backup.

NO usa PostgreSQL pg_dump (eso es H-6B). NO respalda material secreto en claro
(ver SECRET_SPECS). Solo lectura sobre el árbol real.

Uso:
  factory_state_manifest.py classify              -> imprime la tabla de clasificación (JSON)
  factory_state_manifest.py filelist  <root>      -> lista de rutas a incluir (una por línea)
  factory_state_manifest.py manifest  <root> <staged_dir> <out_manifest.json>
  factory_state_manifest.py secrets   <root> <out_secrets.json>
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Clasificación -- 28 stores del rediseño (docs_plan/REDISENO_H5_H6_POST_R1B_20260829.md §4)
# categoria: GOVERNED_CORE | GOVERNED_CATALOG | RUN_ARTIFACT | REGENERABLE
# ---------------------------------------------------------------------------
#: (rel_path, purpose, mutable, required_for_recovery, category, is_glob)
STORE_SPECS = [
    # --- núcleo gobernado -------------------------------------------------
    ("factory/audit",                                  "cadena 21 CFR Part 11 + logs de auditoría + fork_baseline", True,  True,  "GOVERNED_CORE", False),
    ("factory/layer9/decisions",                       "stores de decisiones de gobernanza (v2 + legacy A/B)",       True,  True,  "GOVERNED_CORE", False),
    ("factory/layer9/review_queue.jsonl",              "cola de revisión humana",                                    True,  True,  "GOVERNED_CORE", False),
    ("factory/layer9/risks/risks.jsonl",               "log de aceptación de riesgo",                                True,  True,  "GOVERNED_CORE", False),
    ("factory/layer9/remediation_directives.jsonl",    "directivas de remediación de Capa 9",                        True,  True,  "GOVERNED_CORE", False),
    ("factory/layer9/missions",                        "definiciones de misión de Capa 9",                           True,  True,  "GOVERNED_CORE", False),
    ("factory/registry/artifact_versions.jsonl",       "guard de versiones de artefactos gobernados",                True,  True,  "GOVERNED_CORE", False),
    ("factory/registry/agents_catalog.yaml",           "catálogo de agentes",                                        True,  True,  "GOVERNED_CORE", False),
    ("factory/registry/ports.yaml",                    "registro de puertos de deployments",                         True,  True,  "GOVERNED_CORE", False),
    ("factory/config/release_authorized_identities.yaml", "identidades autorizadas para release",                    True,  True,  "GOVERNED_CORE", False),
    ("factory/config/identity_keys.yaml.example",      "plantilla NO secreta del registro de identidades",           False, True,  "GOVERNED_CORE", False),
    # --- config gobernada / catálogos ----------------------------------
    ("factory/regulatory/requirement_catalog",         "catálogo de requisitos Tier-1 + versiones",                  True,  True,  "GOVERNED_CATALOG", False),
    ("factory/regulatory/schemas",                     "schemas de validación",                                      True,  True,  "GOVERNED_CATALOG", False),
    ("factory/regulatory/golden_dataset",              "dataset dorado (regulatorio)",                               True,  True,  "GOVERNED_CATALOG", False),
    ("factory/eval",                                   "fixtures de evaluación",                                     True,  True,  "GOVERNED_CATALOG", False),
    ("factory/regulatory/model_qualification",         "registros de calificación del modelo",                       True,  True,  "GOVERNED_CATALOG", False),
    ("factory/regulatory/sources",                     "corpus fuente inmutable gobernado (originales + registro)",  False, True,  "GOVERNED_CATALOG", False),
    ("factory/engines/gmpai_integrity/prompts",        "contratos de prompt gobernados",                             True,  True,  "GOVERNED_CATALOG", False),
    ("factory/policies",                               "políticas de aprobación",                                    True,  True,  "GOVERNED_CATALOG", False),
    ("factory/profiles",                               "perfiles de agente derivados",                               True,  True,  "GOVERNED_CATALOG", False),
    ("factory/agent_prompts",                          "prompts de dossier",                                         True,  True,  "GOVERNED_CATALOG", False),
    # --- artefactos de corrida ---------------------------------------
    ("factory/release_candidates",                     "paquetes RC",                                                False, True,  "RUN_ARTIFACT", False),
    ("factory/releases",                               "paquetes liberados",                                         False, True,  "RUN_ARTIFACT", False),
    ("factory/qa_packages",                            "paquetes QA",                                                False, True,  "RUN_ARTIFACT", False),
    ("factory/remediation_packages",                   "contenido versionado de paquetes de remediación",           True,  True,  "RUN_ARTIFACT", False),
    ("factory/validation",                             "artefactos de validación",                                   True,  True,  "RUN_ARTIFACT", False),
    ("factory/regulatory/v2_judgment",                 "artefactos de juicio v2",                                    True,  True,  "RUN_ARTIFACT", False),
    ("factory/regulatory/findings",                    "artefactos de findings",                                     True,  True,  "RUN_ARTIFACT", False),
    ("factory/regulatory/validation_evidence",         "checkpoints de juicio LLM VERSIONADOS (replay baseline)",    True,  "GIT_ONLY", "RUN_ARTIFACT", False),
    ("GMPAI/reports/gmpai_document_validation",        "paquetes completos de corrida del Analizador V2 (+ graph snapshots)", False, True, "RUN_ARTIFACT", False),
    # --- regenerable -- NO va al backup como fuente primaria -----------
    ("factory/regulatory/canonical_store",             "modelo canónico por doc (regenerable desde PDF)",            False, False, "REGENERABLE", False),
    ("factory/regulatory/graph_store",                 "grafo de evidencia por proyecto (regenerable)",              False, False, "REGENERABLE", False),
    ("factory/regulatory/retrieval_index",             "índice BM25 (regenerable)",                                  False, False, "REGENERABLE", False),
    ("factory/regulatory/embedding_index",             "índice de embeddings (regenerable)",                         False, False, "REGENERABLE", False),
    ("factory/regulatory/corpus_run",                  "salidas de corridas piloto (regenerable, caro)",            True,  False, "REGENERABLE", False),
    ("factory/regulatory/case_memory",                 "memoria de casos (regenerable)",                             True,  False, "REGENERABLE", False),
    ("factory/logs",                                   "logs de acceso API (operativo)",                             True,  False, "REGENERABLE", False),
    ("factory/workspaces",                             "proyectos custom generados (ciclo propio)",                  True,  False, "REGENERABLE", False),
]

#: material sensible / secreto -- NUNCA en el tar en claro. Se registra solo
#: naturaleza + sha256 + tamaño en SECRETS_MANIFEST.json.
SECRET_SPECS = [
    ("factory/config/identity_keys.yaml",              "registro de identidades -- {name, key_sha256}. Hashes de credenciales vivas + mapeo nombre->credencial."),
    ("factory/.env",                                   "variables de entorno de Factory (FACTORY_API_KEY, etc.)."),
    ("factory/deployments/oos_hplc_investigator/.env", "env de deployment."),
    ("factory/deployments/lab_qc_project/.env",        "env de deployment."),
]
#: además, cualquier fichero que empiece por este prefijo:
SECRET_GLOB_PREFIXES = ["factory/config/identity_keys.yaml.backup"]

BACKUP_SCHEMA_VERSION = "factory-state-backup/1"

_EXCLUDE_DIR_NAMES = {".venv", "__pycache__", ".pytest_cache", "node_modules", ".git"}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".lock"}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path, rel: str):
    base = root / rel
    if base.is_file():
        yield base
        return
    if not base.is_dir():
        return
    for p in sorted(base.rglob("*")):
        if p.is_dir():
            continue
        if any(part in _EXCLUDE_DIR_NAMES for part in p.relative_to(root).parts):
            continue
        if p.suffix in _EXCLUDE_SUFFIXES:
            continue
        yield p


def _secret_paths(root: Path) -> list[Path]:
    out: list[Path] = []
    for rel, _desc in SECRET_SPECS:
        p = root / rel
        if p.is_file():
            out.append(p)
    for pref in SECRET_GLOB_PREFIXES:
        parent = (root / pref).parent
        stem = (root / pref).name
        if parent.is_dir():
            out += sorted(q for q in parent.iterdir() if q.name.startswith(stem))
    return out


def classify() -> list[dict]:
    rows = []
    for rel, purpose, mutable, req, cat, _g in STORE_SPECS:
        rows.append({
            "path": rel, "purpose": purpose, "mutable": mutable,
            "required_for_recovery": req, "category": cat,
            "in_backup": bool(req) and cat != "REGENERABLE" and req != "GIT_ONLY"
                         or req == "GIT_ONLY",  # los 9 versionados de validation_evidence sí
        })
    for rel, desc in SECRET_SPECS:
        rows.append({"path": rel, "purpose": desc, "mutable": True,
                     "required_for_recovery": True, "category": "SENSITIVE",
                     "in_backup": False, "note": "PLAINTEXT_BACKUP_FORBIDDEN -- solo en SECRETS_MANIFEST"})
    return rows


def _git_tracked_under(root: Path, rel: str) -> set[str]:
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", rel],
                           capture_output=True, text=True, check=True)
        return {x for x in r.stdout.split("\0") if x}
    except Exception:  # noqa: BLE001
        return set()


def filelist(root: Path) -> list[str]:
    secret_set = {p.resolve() for p in _secret_paths(root)}
    seen: set[Path] = set()
    out: list[str] = []
    for rel, _purpose, _mut, req, cat, _g in STORE_SPECS:
        if cat == "REGENERABLE" or req is False:
            continue
        if req == "GIT_ONLY":
            # p.ej. validation_evidence: 2.6 GB de diagnóstico regenerable, de los
            # que SOLO los ficheros versionados (replay baseline) son REQUIRED.
            for tracked_rel in sorted(_git_tracked_under(root, rel)):
                p = (root / tracked_rel)
                if p.is_file() and p.resolve() not in secret_set and p.resolve() not in seen:
                    seen.add(p.resolve()); out.append(tracked_rel)
            continue
        for p in _iter_files(root, rel):
            rp = p.resolve()
            if rp in secret_set or rp in seen:
                continue
            seen.add(rp)
            out.append(str(p.relative_to(root)))
    return out


def _git_head(root: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def _audit_chain_summary(root: Path) -> dict:
    try:
        sys.path.insert(0, str(root))
        from factory.core import audit_writer as aw
        af = root / "factory" / "audit" / "factory_audit.jsonl"
        fb = root / "factory" / "audit" / "fork_baseline.json"
        rep = aw.verify_chain(decision_store_file=None) if af.exists() else {}
        known = list(aw.known_fork_entry_ids(fb))
        new_forks = list(aw.new_forks_since_baseline(af, fb))
        base = json.loads(fb.read_text()) if fb.exists() else {"known_forks": []}
        fork_ids = [f.get("fork_id") for f in base.get("known_forks", [])]
        return {
            "verify_chain": {k: rep.get(k) for k in ("verified", "log_count", "hash_errors", "chain_errors")},
            "historical_fork_count": len(known),
            "historical_fork_ids": fork_ids,
            "historical_fork_entry_ids": known,
            "new_forks_since_baseline": new_forks,
            "line_count": sum(1 for _ in af.open()) if af.exists() else 0,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


_LINE_COUNT_STORES = [
    "factory/audit/factory_audit.jsonl",
    "factory/layer9/decisions/decisions_v2.jsonl",
    "factory/layer9/decisions/decisions.jsonl",
    "factory/layer9/decisions/w5_human_decisions.jsonl",
    "factory/layer9/review_queue.jsonl",
    "factory/layer9/remediation_directives.jsonl",
    "factory/layer9/risks/risks.jsonl",
    "factory/registry/artifact_versions.jsonl",
]


def manifest(root: Path, staged: Path, out: Path) -> dict:
    files = sorted(p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file())
    sha_index = {rel: _sha256(staged / rel) for rel in files}
    line_counts = {}
    for rel in _LINE_COUNT_STORES:
        p = staged / rel
        if p.is_file():
            line_counts[rel] = sum(1 for _ in p.open("rb"))
    man = {
        "backup_schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source_root": str(root),
        "git_head": _git_head(root),
        "file_count": len(files),
        "total_bytes": sum((staged / f).stat().st_size for f in files),
        "jsonl_line_counts": line_counts,
        "audit_chain": _audit_chain_summary(root),
        "sha256": sha_index,
        "excludes": {"dir_names": sorted(_EXCLUDE_DIR_NAMES), "suffixes": sorted(_EXCLUDE_SUFFIXES),
                     "secret_specs": [r for r, _ in SECRET_SPECS], "secret_glob_prefixes": SECRET_GLOB_PREFIXES},
    }
    out.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    (out.parent / "SHA256SUMS").write_text(
        "".join(f"{sha}  {rel}\n" for rel, sha in sorted(sha_index.items())), encoding="utf-8")
    return man


def secrets_manifest(root: Path, out: Path) -> dict:
    items = []
    for p in _secret_paths(root):
        items.append({
            "path": str(p.relative_to(root)),
            "sha256": _sha256(p),
            "size_bytes": p.stat().st_size,
            "included_in_backup": False,
            "reason": "PLAINTEXT_BACKUP_FORBIDDEN",
        })
    man = {
        "backup_schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "PLAINTEXT_BACKUP_FORBIDDEN": True,
        "SECRET_BACKUP_MECHANISM_MISSING": True,
        "SECRET_BACKUP_STATUS": "BLOCKED_PENDING_HUMAN_DECISION",
        "note": ("No existe un mecanismo de backup cifrado APROBADO para Factory "
                 "(age/sops/ansible-vault/git-crypt no instalados; gpg/openssl/"
                 "systemd-creds presentes pero sin patrón establecido ni clave "
                 "gestionada). NO se inventa cifrado ad-hoc. Estos artefactos "
                 "quedan FUERA del backup en claro; su respaldo seguro es una "
                 "decisión pendiente de Capa 9. identity_keys.yaml almacena "
                 "key_sha256 (hashes), no claves en claro, pero se trata como "
                 "sensible por precaución."),
        "items": items,
    }
    out.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    return man


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "classify":
        print(json.dumps(classify(), indent=1, ensure_ascii=False))
    elif cmd == "filelist":
        for rel in filelist(Path(argv[2])):
            print(rel)
    elif cmd == "manifest":
        m = manifest(Path(argv[2]), Path(argv[3]), Path(argv[4]))
        print(json.dumps({"file_count": m["file_count"], "git_head": m["git_head"],
                          "audit_chain": m["audit_chain"]}, indent=1, ensure_ascii=False))
    elif cmd == "secrets":
        m = secrets_manifest(Path(argv[2]), Path(argv[3]))
        print(json.dumps({"SECRET_BACKUP_MECHANISM_MISSING": m["SECRET_BACKUP_MECHANISM_MISSING"],
                          "items": [i["path"] for i in m["items"]]}, indent=1, ensure_ascii=False))
    else:
        print(f"comando desconocido: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
