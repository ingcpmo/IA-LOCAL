#!/usr/bin/env python3
"""H-10 -- SALTO GOBERNADO de EXTRACTION_VERSION (autorizado por D-4 / ARTIFACT_VERSION-2026-021).

canonical-v1-2026-08  ->  canonical-v1-2026-08+tests-v1

Materializa el salto sobre el corpus REAL RW-6 por el FLUJO PRODUCTIVO real
(`run_v2_pipeline`), en STORES NUEVOS Y FÍSICAMENTE SEPARADOS:

  factory/regulatory/canonical_store_v2/     (NUEVO)
  factory/regulatory/graph_store_v2/         (NUEVO)
  factory/regulatory/pilot_run/h10_extraction_v2_20260830/   (paquete de corrida)

Los stores v1 (`canonical_store/`, `graph_store/`) NO se tocan -> rollback = seguir
usándolos. `_EXT_VER` / `_CANON` de `v2_runtime.py` NO se modifican: la ACTIVACIÓN
real depende de la verificación HUMANA de la muestra `refers_to`/`tested_by`
(H10_HUMAN_SAMPLE_VERIFICATION=PENDING).

Corre 2× (determinismo). `network_locked()` -> DOCUMENT_EGRESS=0.

Uso:  h10_execute_version_jump.py
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from factory.regulatory.canonical.extract_document import extract_document  # noqa: E402
from factory.regulatory.canonical.persistence import CanonicalStore  # noqa: E402
from factory.regulatory.graph.store import GraphStore  # noqa: E402
from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline  # noqa: E402

_ROCKWELL = _REPO / "GMPAI" / "source" / "Rockwell"
RW6 = [
    ("RW-0005", "FS",  "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"),
    ("RW-0006", "URS", "215115305 SCADA-PCS Misc PLC System URS v2.1.pdf"),
    ("RW-0009", "SAT", "215115305-T-041 SAT3 Completed.pdf"),
    ("RW-0011", "DS",  "MCCPDC EMS Control Block Narrative revB.pdf"),
    ("RW-0012", "DS",  "MCCPDC PCS Signal Interface Control Block Narrative.pdf"),
    ("RW-0014", "DS",  "MCCPDC WFI Control Block Narrative revB.pdf"),
]
RW_IDS = [d for d, _, _ in RW6]
PROJECT_ID = "RW-H10-V2"

_CANON_V1 = _REPO / "factory/regulatory/canonical_store"
_GRAPH_V1 = _REPO / "factory/regulatory/graph_store"
_CANON_V2 = _REPO / "factory/regulatory/canonical_store_v2"
_GRAPH_V2 = _REPO / "factory/regulatory/graph_store_v2"
_PKG = _REPO / "factory/regulatory/pilot_run/h10_extraction_v2_20260830"


def _md5_tree(root: Path) -> dict:
    import hashlib
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.md5(p.read_bytes()).hexdigest()
    return out


def _counts(graph_dir: Path) -> dict:
    g = GraphStore(PROJECT_ID, store_dir=graph_dir)
    c = g.counts()
    g.close()
    return c


def _fps(run_dir: Path) -> dict:
    a = json.loads((run_dir / "audit_summary" / "audit_metadata.json").read_text())
    return {k: a.get(k) for k in
            ("input_config_fingerprint", "graph_snapshot_fingerprint", "findings_fingerprint")}


import os

# RW-0003 (SAT real) ya ingerido con docling por lotes (egress 0). Ruta del
# store ingerido, configurable por env para no depender de canonical_store_v2
# (que este script recrea).
_RW0003_SRC = Path(os.environ.get(
    "H10_RW0003_STORE",
    str(_REPO / "factory/regulatory/canonical_store_v2/RW-0003.sqlite3")))


def _derive(canon_dir: Path, graph_dir: Path, report_base: Path, run_id: str) -> dict:
    for did, tipo, fname in RW6:
        extract_document(_ROCKWELL / fname, did, tipo=tipo,
                         store_dir=canon_dir, extract_tests=True)
    docs = list(RW_IDS)
    if _RW0003_SRC.exists():
        shutil.copy2(_RW0003_SRC, canon_dir / "RW-0003.sqlite3")
        docs = RW_IDS + ["RW-0003"]
    res = run_v2_pipeline(docs, project_id=PROJECT_ID, run_id=run_id,
                          canon_dir=canon_dir, graph_dir=graph_dir, report_base=report_base)
    rd = Path(res["run_dir"])
    _audit = json.loads((rd / "audit_summary" / "audit_metadata.json").read_text())
    per_doc = {}
    for did in docs:
        with CanonicalStore(did, store_dir=canon_dir) as s:
            per_doc[did] = {
                "ext_ver": s.all("document")[0].get("extraction_version"),
                "claims": len(s.all("claim")), "tables": len(s.all("table_obj")),
                "tables_with_roles": sum(1 for t in s.all("table_obj") if t.get("column_roles")),
                "tests": len(s.all("test")),
                "system_component": len(s.all("system_component")),
                "actor": len(s.all("actor")),
            }
    return {"run_dir": str(rd), "counts": _counts(graph_dir),
            "fingerprints": _fps(rd), "per_doc": per_doc,
            "human_gate_intact": res.get("human_gate_intact"),
            "document_egress_bytes": res.get("document_egress_bytes",
                                            _audit.get("document_egress_bytes")),
            "local_only": res.get("local_only", _audit.get("local_only"))}


def main() -> int:
    v1_before = {"canonical_store": _md5_tree(_CANON_V1), "graph_store": _md5_tree(_GRAPH_V1)}

    for d in (_CANON_V2, _GRAPH_V2, _PKG):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    # run_v2_pipeline aplica su propio network_locked() internamente; el probe de
    # egress de H-5F corre ANTES de ese lock -> no envolver aquí.
    run1 = _derive(_CANON_V2, _GRAPH_V2, _PKG / "run1", "h10-v2-run1")
    import tempfile
    tmp_c = Path(tempfile.mkdtemp(prefix="h10v2r2-canon-"))
    tmp_g = Path(tempfile.mkdtemp(prefix="h10v2r2-graph-"))
    try:
        run2 = _derive(tmp_c, tmp_g, _PKG / "run2", "h10-v2-run2")
    finally:
        shutil.rmtree(tmp_c, ignore_errors=True)
        shutil.rmtree(tmp_g, ignore_errors=True)

    v1_after = {"canonical_store": _md5_tree(_CANON_V1), "graph_store": _md5_tree(_GRAPH_V1)}

    det = {k: run1["fingerprints"][k] == run2["fingerprints"][k]
           for k in run1["fingerprints"]}
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jump": "canonical-v1-2026-08 -> canonical-v1-2026-08+tests-v1",
        "authorized_by": "D-4 / ARTIFACT_VERSION-2026-021 (decision_ref D-4-H9-20260830)",
        "stores_written": {"canonical": str(_CANON_V2), "graph": str(_GRAPH_V2),
                           "package": str(_PKG)},
        "v1_stores_preserved": v1_before == v1_after,
        "v1_before_after_equal": {
            "canonical_store": v1_before["canonical_store"] == v1_after["canonical_store"],
            "graph_store": v1_before["graph_store"] == v1_after["graph_store"],
        },
        "run1": run1, "run2_fingerprints": run2["fingerprints"],
        "run2_counts": run2["counts"],
        "determinism_2x": det,
        "determinism_pass": all(det.values()),
        "document_egress_bytes": run1.get("document_egress_bytes"),
        "local_only": run1.get("local_only"),
        "human_gate_intact": run1["human_gate_intact"],
    }
    (_PKG / "H10_VERSION_JUMP_RESULT.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
