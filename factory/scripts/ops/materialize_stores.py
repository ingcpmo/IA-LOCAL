"""F2 (plan de reconciliación v1.1) — materialización LIMPIA, determinista y AISLADA
de canonical_store + graph_store del corpus RW-6, con doble hash
(BYTE + LOGICAL) según docs_plan/reconc/F2_HASH_DEFINITION.md.

F2-r1 (correcciones de la auditoría externa):
  1. Funciona desde un CLON LIMPIO SIN canonical_store previo: el mapeo doc_id→PDF
     y el sha256 esperado están DECLARADOS aquí (constante `_PDF_MAP`), verificados
     contra el corpus; NUNCA se leen de stores existentes.
  2. Por defecto materializa en un DIRECTORIO TEMPORAL AISLADO; nunca toca los
     stores del origen (salvo `--apply`, paso controlado y separado).
  3. `--runs N` demuestra determinismo (N corridas → LOGICAL_CONTENT_HASH idéntico).
  4. `--baseline-manifest PATH` compara los LOGICAL hashes contra un manifest previo
     (no contra stores del origen).

USO:
  # validación aislada + 3 corridas de determinismo (clon limpio):
  PYTHONPATH=. .venv/bin/python factory/scripts/ops/materialize_stores.py --runs 3
  # comparar contra el manifest congelado:
  PYTHONPATH=. .venv/bin/python factory/scripts/ops/materialize_stores.py \
      --baseline-manifest docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json
  # actualización CONTROLADA del baseline del origen (paso separado, con backup):
  PYTHONPATH=. .venv/bin/python factory/scripts/ops/materialize_stores.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from factory.regulatory.canonical.extract_document import extract_document       # noqa: E402
from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DISK     # noqa: E402
from factory.regulatory.graph import build as gb                                # noqa: E402
from factory.regulatory.graph.store import STORE_DIR as GRAPH_DISK              # noqa: E402
from factory.regulatory.validation_v2.local_only import network_locked          # noqa: E402

PROJECT_ID = "RW-TECH-REAL"

# --- mapeo doc_id -> (pdf, sha256 esperado, tipo) DECLARADO (F2-r1 §1).
#     Fuente: benchmark de extracción / F1 (los 3 DS) + registry del corpus.
#     El sha256 se VERIFICA contra el PDF real; si no coincide -> abort.
#     RW-0012 apunta al PDF CORRECTO (PCS Signal Interface), NO al de b4b_runner
#     (que apunta a WFI = documento de RW-0014 -> causa de la contaminación).
_PDF_MAP = {
    "RW-0005": ("215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf",
                "56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb", "FS"),
    "RW-0006": ("215115305 SCADA-PCS Misc PLC System URS v2.1.pdf",
                "d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8", "URS"),
    "RW-0009": ("215115305-T-041 SAT3 Completed.pdf",
                "2edb00a3eae471926f41f6d6b707874e52c78c29ebc583ad6da6c4cf961009eb", "SAT"),
    "RW-0011": ("MCCPDC EMS Control Block Narrative revB.pdf",
                "13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53", "DS"),
    "RW-0012": ("MCCPDC PCS Signal Interface Control Block Narrative.pdf",
                "de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71", "DS"),
    "RW-0014": ("MCCPDC WFI Control Block Narrative revB.pdf",
                "8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb", "DS"),
}
RW_DOCS = [(d, _PDF_MAP[d][2]) for d in _PDF_MAP]

_ROCKWELL_BASES = [
    REPO / "GMPAI" / "source" / "Rockwell",
    Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell"),
    Path("/home/ing_cpmo/GMPAI/source/Rockwell"),
]

# ---- LOGICAL_CONTENT_HASH (F2_HASH_DEFINITION §2.1) ----
_VOLATILE_KEYS = {"run_id", "run_context", "agent_id"}
def _is_volatile_key(k: str) -> bool:
    return (k in _VOLATILE_KEYS or k.endswith("_at") or k.endswith("_timestamp")
            or k in ("generated_at", "recorded_at"))


def _norm_env_path(v: str) -> str:
    for marker in ("GMPAI/source/", "/GMPAI/source/"):
        i = v.find(marker)
        if i != -1:
            return v[i:].lstrip("/")
    if v.startswith("/") and ("/ivr-ia/" in v or "/ing_cpmo/" in v):
        for anchor in ("/ivr-ia/", "/ing_cpmo/"):
            j = v.find(anchor)
            if j != -1:
                return "<ENV>/" + v[j + len(anchor):]
    return v


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: ("<VOLATILE>" if _is_volatile_key(k) else _scrub(x)) for k, x in obj.items()}
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, str):
        return _norm_env_path(obj)
    return obj


def _canon_json(v):
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "{[":
            try:
                return json.dumps(_scrub(json.loads(s)), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            except Exception:  # noqa: BLE001
                return _norm_env_path(v)
        return _norm_env_path(v)
    return v


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


def _rockwell_base() -> Path:
    b = next((x for x in _ROCKWELL_BASES if x.is_dir()), None)
    if b is None:
        raise RuntimeError("corpus Rockwell no disponible (GMPAI/source/Rockwell)")
    return b


def materialize_once(canon_dir: Path, graph_dir: Path) -> dict:
    """Una materialización limpia y determinista. Devuelve counts + hashes por store."""
    base = _rockwell_base()
    canon_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    per_doc = {}
    with network_locked():
        for did, tipo in RW_DOCS:
            fname, expect_sha, _ = _PDF_MAP[did]
            pdf = base / fname
            if not pdf.exists():
                per_doc[did] = {"status": "PDF_MISSING", "expected": str(pdf)}
                continue
            got_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
            if got_sha != expect_sha:
                raise RuntimeError(f"{did}: sha256 del PDF no coincide con _PDF_MAP "
                                   f"(got {got_sha[:16]} != {expect_sha[:16]})")
            extract_document(pdf, did, tipo=tipo, store_dir=canon_dir)
            lh, c = logical_hash_sqlite(canon_dir / f"{did}.sqlite3")
            per_doc[did] = {"status": "OK", "pdf_name": fname, "pdf_sha256": got_sha,
                            "byte_hash": byte_hash_file(canon_dir / f"{did}.sqlite3"),
                            "logical_hash": lh, "counts": c}
        counts = gb.build_project_graph(PROJECT_ID, RW_DOCS, canon_dir=canon_dir, graph_dir=graph_dir)
    graph = {"build_counts": counts, "per_db": {}, "tree_byte_hash": tree_byte_hash(graph_dir)}
    for f in sorted(graph_dir.rglob("*.sqlite3")):
        lh, c = logical_hash_sqlite(f)
        graph["per_db"][f.name] = {"logical_hash": lh, "byte_hash": byte_hash_file(f), "counts": c}
    return {"canonical": per_doc, "graph": graph}


def _code_hashes() -> dict:
    return {p: byte_hash_file(REPO / f"factory/regulatory/{p}") for p in (
        "document_structure_extractor.py", "canonical/extract_document.py",
        "canonical/normalize_claims.py", "graph/build.py")}


def _git(*args) -> str:
    import subprocess
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


def run(*, out_root: Path, runs: int, apply: bool, baseline_manifest: Path | None) -> dict:
    rep = {
        "artifact": "F2_materialization_report", "phase": "F2-r1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "hash_definition": {"ref": "docs_plan/reconc/F2_HASH_DEFINITION.md", "commit": "9ab7c2b"},
        "pdf_map_source": "DECLARADO en materialize_stores.py::_PDF_MAP (verificado por sha256); NO se leen stores del origen",
        "rockwell_base": str(_rockwell_base()),
        "code_hashes": _code_hashes(),
        "runs": [],
    }

    # N corridas AISLADAS (cada una en su propio tmp) -> prueba de determinismo
    for i in range(runs):
        d = Path(tempfile.mkdtemp(prefix=f"reconc_f2_run{i}_"))
        r = materialize_once(d / "canonical_store", d / "graph_store")
        rep["runs"].append({
            "i": i, "tmp": str(d),
            "canonical_logical": {k: v.get("logical_hash") for k, v in r["canonical"].items()},
            "canonical_counts": {k: v.get("counts") for k, v in r["canonical"].items()},
            "graph_logical": {k: v["logical_hash"] for k, v in r["graph"]["per_db"].items()},
            "graph_counts": r["graph"]["build_counts"],
            "detail": r,
        })
        shutil.rmtree(d, ignore_errors=True)

    # determinismo: todos los runs iguales?
    if runs >= 2:
        c0 = rep["runs"][0]["canonical_logical"]; g0 = rep["runs"][0]["graph_logical"]
        rep["deterministic_canonical"] = all(x["canonical_logical"] == c0 for x in rep["runs"])
        rep["deterministic_graph"] = all(x["graph_logical"] == g0 for x in rep["runs"])
    rep["logical_canonical"] = rep["runs"][-1]["canonical_logical"]
    rep["logical_graph"] = rep["runs"][-1]["graph_logical"]
    rep["counts_canonical"] = rep["runs"][-1]["canonical_counts"]
    rep["counts_graph"] = rep["runs"][-1]["graph_counts"]

    # comparación contra manifest previo (no contra el origen)
    if baseline_manifest and baseline_manifest.exists():
        m = json.loads(baseline_manifest.read_text())
        want_c = ((m.get("canonical_store_manifest") or {}).get("per_doc") or {})
        want_g = ((m.get("graph_store_manifest") or {}).get("per_db") or {})
        rep["vs_manifest"] = {
            "canonical": {k: (rep["logical_canonical"].get(k) == (want_c.get(k) or {}).get("logical_hash_clean"))
                          for k in rep["logical_canonical"]},
            "graph": {k: (rep["logical_graph"].get(k) == (want_g.get(k) or {}).get("logical_hash_clean"))
                      for k in rep["logical_graph"]},
        }

    # actualización CONTROLADA del baseline del origen (paso separado, con backup)
    if apply:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = REPO / f"factory/regulatory/_reconc_backup_{ts}"
        backup.mkdir(parents=True)
        for name, disk in (("canonical_store", CANON_DISK), ("graph_store", GRAPH_DISK)):
            if disk.is_dir():
                shutil.copytree(disk, backup / name)
                shutil.rmtree(disk)
            disk.mkdir(parents=True)
        materialize_once(CANON_DISK, GRAPH_DISK)
        rep["apply"] = {"backup_dir": str(backup),
                        "note": "baseline del origen actualizado a la materialización limpia (F2-r1 §4)"}

    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="factory/regulatory/_reconc_materialized")
    ap.add_argument("--report", default="docs_plan/reconc/F2_materialization_report.json")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--apply", action="store_true",
                    help="paso controlado y separado: actualiza el baseline del origen (con backup)")
    ap.add_argument("--baseline-manifest", default=None)
    args = ap.parse_args()
    rep = run(out_root=REPO / args.out, runs=args.runs, apply=args.apply,
              baseline_manifest=Path(args.baseline_manifest) if args.baseline_manifest else None)
    Path(REPO / args.report).write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(f"HEAD={rep['git_commit'][:12]}  runs={len(rep['runs'])}  base={rep['rockwell_base']}")
    if "deterministic_canonical" in rep:
        print(f"  DETERMINISTA canonical: {rep['deterministic_canonical']}  graph: {rep['deterministic_graph']}")
    for k, v in rep["logical_canonical"].items():
        print(f"  {k}: LOGICAL={v[:16]}  sections={rep['counts_canonical'][k].get('section')}  claims={rep['counts_canonical'][k].get('claim')}")
    for k, v in rep["logical_graph"].items():
        print(f"  graph {k}: LOGICAL={v[:16]}  counts={rep['counts_graph']}")
    if "vs_manifest" in rep:
        print(f"  vs_manifest: canonical={rep['vs_manifest']['canonical']}  graph={rep['vs_manifest']['graph']}")
    if "apply" in rep:
        print(f"  APPLY -> origen actualizado. backup {rep['apply']['backup_dir']}")
    print(f"report -> {args.report}")


if __name__ == "__main__":
    main()
