"""F2 (plan de reconciliación v1.1) — materialización LIMPIA y determinista de
canonical_store + graph_store del corpus RW-6, con doble hash (BYTE + LOGICAL)
según docs_plan/reconc/F2_HASH_DEFINITION.md.

- NO usa el mapeo doc->pdf de b4b_runner (tiene RW-0012 -> WFI, que es RW-0014):
  el mapeo correcto se toma de `canonical_store/*.sqlite3::document.payload.archivo`
  y se resuelve contra las bases Rockwell conocidas.
- Sin LLM. Sin red. Determinista (pdfplumber + regex + heurística + grafo idempotente).
- Escribe en un directorio NUEVO (por defecto factory/regulatory/_reconc_materialized/);
  NO sobrescribe los stores en disco.

USO:
    PYTHONPATH=. .venv/bin/python factory/scripts/ops/materialize_stores.py [--out DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from factory.regulatory.canonical.extract_document import extract_document       # noqa: E402
from factory.regulatory.canonical.persistence import CanonicalStore, STORE_DIR as CANON_DISK  # noqa: E402
from factory.regulatory.graph import build as gb                                # noqa: E402
from factory.regulatory.graph.store import STORE_DIR as GRAPH_DISK              # noqa: E402
from factory.regulatory.validation_v2.local_only import network_locked          # noqa: E402

PROJECT_ID = "RW-TECH-REAL"
RW_DOCS = [("RW-0005", "FS"), ("RW-0006", "URS"), ("RW-0009", "SAT"),
           ("RW-0011", "DS"), ("RW-0012", "DS"), ("RW-0014", "DS")]

_ROCKWELL_BASES = [
    REPO / "GMPAI" / "source" / "Rockwell",
    Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell"),
    Path("/home/ing_cpmo/GMPAI/source/Rockwell"),
]

# --- campos volátiles excluidos del LOGICAL_CONTENT_HASH (F2_HASH_DEFINITION §2.1) ---
_VOLATILE_KEYS = {"run_id", "run_context", "agent_id"}
def _is_volatile_key(k: str) -> bool:
    return k in _VOLATILE_KEYS or k.endswith("_at") or k.endswith("_timestamp") or k in ("generated_at", "recorded_at")


def _norm_env_path(v: str) -> str:
    """F2_HASH_DEFINITION §2.2: rutas absolutas del entorno -> forma canónica relativa.
    Un `archivo` de documento puede persistirse como ruta absoluta o relativa según
    el entorno de la extracción; ambas apuntan al mismo PDF."""
    for marker in ("GMPAI/source/", "/GMPAI/source/"):
        i = v.find(marker)
        if i != -1:
            return v[i:].lstrip("/")
    if v.startswith("/") and ("/ivr-ia/" in v or "/ing_cpmo/" in v):
        # ruta absoluta del repo -> <ENV>/<cola>
        for anchor in ("/ivr-ia/", "/ing_cpmo/"):
            j = v.find(anchor)
            if j != -1:
                return "<ENV>/" + v[j + len(anchor):]
    return v


def _canon_json(v):
    """Serialización determinista; si un string es JSON, se re-serializa con claves ordenadas
    y campos volátiles neutralizados."""
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "{[":
            try:
                return json.dumps(_scrub(json.loads(s)), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            except Exception:  # noqa: BLE001
                return _norm_env_path(v)
        return _norm_env_path(v)
    return v


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: ("<VOLATILE>" if _is_volatile_key(k) else _scrub(x)) for k, x in obj.items()}
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, str):
        return _norm_env_path(obj)
    return obj


def byte_hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_byte_hash(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file():
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def logical_hash_sqlite(db: Path) -> tuple[str, dict]:
    con = sqlite3.connect(db)
    cur = con.cursor()
    tabs = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    h = hashlib.sha256()
    counts = {}
    for t in tabs:
        cols = [d[1] for d in cur.execute(f"PRAGMA table_info({t})")]
        order = ", ".join(f'"{c}"' for c in cols) or "1"
        rows = cur.execute(f'SELECT * FROM "{t}" ORDER BY {order}').fetchall()
        counts[t] = len(rows)
        h.update(t.encode())
        for row in rows:
            rec = {c: _canon_json(("<VOLATILE>" if _is_volatile_key(c) else val))
                   for c, val in zip(cols, row)}
            h.update(json.dumps(rec, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True, default=str).encode())
    con.close()
    return h.hexdigest(), counts


def materialize(out_dir: Path, *, apply: bool = False) -> dict:
    """Materializa los stores del corpus RW-6 de forma limpia y determinista.

    apply=False  -> escribe en out_dir/{canonical_store,graph_store} (no toca los reales).
    apply=True   -> respalda los reales en _reconc_backup_<ts>/ y los REGENERA in situ
                    (para que los targeted lean stores materializados por el procedimiento).
    """
    out_dir = out_dir.resolve()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # 1. Pre-captura del estado en disco (mapeo doc->pdf, sha del PDF, y hashes lógicos
    #    PREVIOS) ANTES de tocar nada.
    pdf_by_doc, disk_sha, pre_canon, pre_graph = {}, {}, {}, {}
    for did, _ in RW_DOCS:
        with CanonicalStore(did, store_dir=CANON_DISK) as s:
            doc = s.all("document")[0]
        pdf_by_doc[did] = Path(doc["archivo"]).name
        disk_sha[did] = doc["sha256"]
        db = CANON_DISK / f"{did}.sqlite3"
        if db.exists():
            lh, c = logical_hash_sqlite(db)
            pre_canon[did] = {"logical_hash": lh, "counts": c, "byte_hash": byte_hash_file(db)}
    if GRAPH_DISK.is_dir():
        for f in sorted(GRAPH_DISK.rglob("*.sqlite3")):
            lh, c = logical_hash_sqlite(f)
            pre_graph[f.name] = {"logical_hash": lh, "counts": c}
        pre_graph_tree = tree_byte_hash(GRAPH_DISK)
    else:
        pre_graph_tree = None

    backup = None
    if apply:
        canon_new, graph_new = CANON_DISK, GRAPH_DISK
        backup = REPO / f"factory/regulatory/_reconc_backup_{ts}"
        backup.mkdir(parents=True)
        if CANON_DISK.is_dir():
            shutil.copytree(CANON_DISK, backup / "canonical_store")
        if GRAPH_DISK.is_dir():
            shutil.copytree(GRAPH_DISK, backup / "graph_store")
        for d in (CANON_DISK, GRAPH_DISK):
            if d.is_dir():
                shutil.rmtree(d)
            d.mkdir(parents=True)
    else:
        canon_new = out_dir / "canonical_store"
        graph_new = out_dir / "graph_store"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        canon_new.mkdir(parents=True)
        graph_new.mkdir(parents=True)

    base = next((b for b in _ROCKWELL_BASES if b.is_dir()), None)
    if base is None:
        raise RuntimeError("corpus Rockwell no disponible (GMPAI/source/Rockwell)")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": _git_head(), "branch": _git_branch(),
        "hash_definition_ref": "docs_plan/reconc/F2_HASH_DEFINITION.md",
        "hash_definition_commit": "9ab7c2b",
        "rockwell_base": str(base),
        "mode": "apply (regenera in situ)" if apply else "out_dir (no toca los reales)",
        "backup_dir": str(backup) if backup else None,
        "pdf_map_source": "canonical_store/*.sqlite3::document.payload.archivo (NO b4b_runner._PDF_BY_DOC)",
        "b4b_runner_bug": "b4b_runner.py:_PDF_BY_DOC['RW-0012'] apunta a 'MCCPDC WFI Control Block Narrative revB.pdf' (documento de RW-0014). Causa del canonical_store/RW-0012 contaminado (13 secciones). b4b_runner.py fuera del alcance editable de F2.",
        "pre_state_canonical": pre_canon,
        "pre_state_graph": {"per_db": pre_graph, "tree_byte_hash": pre_graph_tree},
        "docs": {},
    }

    code_hashes = {
        "document_structure_extractor.py": byte_hash_file(REPO / "factory/regulatory/document_structure_extractor.py"),
        "canonical/extract_document.py": byte_hash_file(REPO / "factory/regulatory/canonical/extract_document.py"),
        "canonical/normalize_claims.py": byte_hash_file(REPO / "factory/regulatory/canonical/normalize_claims.py"),
        "graph/build.py": byte_hash_file(REPO / "factory/regulatory/graph/build.py"),
    }
    report["code_hashes"] = code_hashes

    with network_locked() as egress:
        for did, tipo in RW_DOCS:
            pdf = base / pdf_by_doc[did]
            if not pdf.exists():
                report["docs"][did] = {"status": "PDF_MISSING", "expected": str(pdf)}
                continue
            pdf_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
            extract_document(pdf, did, tipo=tipo, store_dir=canon_new)
            new_db = canon_new / f"{did}.sqlite3"
            lh_new, counts_new = logical_hash_sqlite(new_db)
            pre = pre_canon.get(did, {})
            report["docs"][did] = {
                "status": "OK",
                "pdf_name": pdf_by_doc[did], "pdf_sha256": pdf_sha,
                "pdf_sha256_matches_canonical_meta": pdf_sha == disk_sha[did],
                "byte_hash_new": byte_hash_file(new_db),
                "byte_hash_pre": pre.get("byte_hash"),
                "logical_hash_new": lh_new,
                "logical_hash_pre": pre.get("logical_hash", "<no-pre>"),
                "logical_match_new_vs_pre": lh_new == pre.get("logical_hash"),
                "counts_new": counts_new, "counts_pre": pre.get("counts", {}),
            }

        counts = gb.build_project_graph(PROJECT_ID, RW_DOCS, canon_dir=canon_new, graph_dir=graph_new)

    # hash del graph_store regenerado vs PRE-estado capturado
    g_dbs = sorted(graph_new.rglob("*.sqlite3"))
    report["graph_store"] = {
        "build_counts": counts,
        "files": [f.name for f in g_dbs],
        "tree_byte_hash_new": tree_byte_hash(graph_new),
        "tree_byte_hash_pre": pre_graph_tree,
        "per_db": {},
    }
    for f in g_dbs:
        lh_new, c_new = logical_hash_sqlite(f)
        pre = pre_graph.get(f.name, {})
        report["graph_store"]["per_db"][f.name] = {
            "logical_hash_new": lh_new, "logical_hash_pre": pre.get("logical_hash", "<no-pre>"),
            "logical_match_new_vs_pre": lh_new == pre.get("logical_hash"),
            "counts_new": c_new, "counts_pre": pre.get("counts", {}),
        }

    report["materialized_dir"] = str(out_dir)
    report["egress_bytes"] = getattr(egress, "bytes", getattr(egress, "total", 0)) if egress else 0
    return report


def _git_head() -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def _git_branch() -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="factory/regulatory/_reconc_materialized")
    ap.add_argument("--report", default="docs_plan/reconc/F2_materialization_report.json")
    ap.add_argument("--apply", action="store_true",
                    help="regenera canonical_store + graph_store IN SITU (con backup)")
    args = ap.parse_args()
    rep = materialize(REPO / args.out, apply=args.apply)
    Path(REPO / args.report).write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(f"HEAD={rep['repo_head'][:12]}  base={rep['rockwell_base']}  mode={rep['mode']}")
    if rep.get("backup_dir"):
        print(f"  backup -> {rep['backup_dir']}")
    for did, d in rep["docs"].items():
        if d.get("status") != "OK":
            print(f"  {did}: {d['status']}"); continue
        print(f"  {did} ({d['pdf_name']}): pdf_sha_ok={d['pdf_sha256_matches_canonical_meta']}  "
              f"LOGICAL new==pre: {d['logical_match_new_vs_pre']}  "
              f"sections new={d['counts_new'].get('section')} pre={d['counts_pre'].get('section')}  "
              f"claims new={d['counts_new'].get('claim')} pre={d['counts_pre'].get('claim')}")
    gs = rep["graph_store"]
    print(f"  graph_store: build_counts={gs['build_counts']}")
    for name, x in gs["per_db"].items():
        print(f"    {name}: LOGICAL new==pre: {x['logical_match_new_vs_pre']}  "
              f"counts_new={x['counts_new']}  counts_pre={x['counts_pre']}")
    print(f"report -> {args.report}")


if __name__ == "__main__":
    main()
