#!/usr/bin/env python3
"""H-10 -- validación final AISLADA: RW-6 + RW-0003 (SAT real OCR ya ingerido).

CONTROL   : RW-6, V2_TEST_EXTRACTION OFF, canonical-v1-2026-08     (baseline)
H10_RUN_1 : RW-6 + RW-0003, flag ON, canonical-v1-2026-08+tests-v1
H10_RUN_2 : idéntico a RUN_1 -> determinismo

RW-6 se re-extrae fresco (rápido, sin OCR). RW-0003 se copia del store ya
ingerido (`canonical_store_v2/RW-0003.sqlite3`, docling por lotes, egress 0).
Todo el grafo/paquete va a tmp. `canonical_store`/`graph_store` de producción
NO se tocan.

Reporta: TEST_OBJECTS, TESTED_BY, VERIFIES, REFERS_TO, implemented_by/designed_by
before/after, los 3 fingerprints RUN1==RUN2, y una muestra determinista de las
aristas nuevas con provenance.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from factory.regulatory.canonical.extract_document import extract_document  # noqa: E402
from factory.regulatory.canonical.persistence import CanonicalStore  # noqa: E402
from factory.regulatory.graph.store import GraphStore  # noqa: E402
from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline  # noqa: E402

_ROCKWELL = _REPO / "GMPAI/source/Rockwell"
_RW0003_SRC = _REPO / "factory/regulatory/canonical_store_v2/RW-0003.sqlite3"
RW6 = [
    ("RW-0005", "FS",  "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"),
    ("RW-0006", "URS", "215115305 SCADA-PCS Misc PLC System URS v2.1.pdf"),
    ("RW-0009", "SAT", "215115305-T-041 SAT3 Completed.pdf"),
    ("RW-0011", "DS",  "MCCPDC EMS Control Block Narrative revB.pdf"),
    ("RW-0012", "DS",  "MCCPDC PCS Signal Interface Control Block Narrative.pdf"),
    ("RW-0014", "DS",  "MCCPDC WFI Control Block Narrative revB.pdf"),
]


def _populate(canon: Path, *, with_rw0003: bool, extract_tests: bool):
    for did, tipo, fname in RW6:
        extract_document(_ROCKWELL / fname, did, tipo=tipo, store_dir=canon,
                         extract_tests=extract_tests)
    if with_rw0003:
        shutil.copy2(_RW0003_SRC, canon / "RW-0003.sqlite3")


def _counts(gdir: Path, pid: str) -> dict:
    g = GraphStore(pid, store_dir=gdir)
    c = g.counts()
    g.close()
    return c


def _fps(run_dir: Path) -> dict:
    a = json.loads((run_dir / "audit_summary" / "audit_metadata.json").read_text())
    return {k: a.get(k) for k in
            ("input_config_fingerprint", "graph_snapshot_fingerprint", "findings_fingerprint")}


def _edge_sample(gdir: Path, pid: str, canon: Path, docs: list[str], limit=50) -> list[dict]:
    prov = {}
    for did in docs:
        try:
            with CanonicalStore(did, store_dir=canon) as s:
                for t in s.all("test"):
                    p = t.get("provenance") or {}
                    prov[t["test_id"]] = {"doc": did, "page": p.get("page"),
                                          "anchor": (p.get("source_text") or "")[:220],
                                          "hash": p.get("source_hash"),
                                          "name": t.get("identificador"),
                                          "refs": t.get("verifies_requirement_ids")}
                for c in s.all("system_component"):
                    p = c.get("provenance") or {}
                    prov[c["component_id"]] = {"doc": did, "page": p.get("page"),
                                               "anchor": (p.get("source_text") or "")[:220],
                                               "hash": p.get("source_hash"),
                                               "name": c.get("nombre")}
                for a in s.all("actor"):
                    p = a.get("provenance") or {}
                    prov[a["actor_id"]] = {"doc": did, "page": p.get("page"),
                                           "anchor": (p.get("source_text") or "")[:220],
                                           "hash": p.get("source_hash"),
                                           "name": a.get("nombre_rol")}
        except Exception:  # noqa: BLE001
            pass
    g = GraphStore(pid, store_dir=gdir)
    node = {n.node_id: n for n in g.nodes()}
    cap = {}
    out = []
    for e in sorted(g.edges(), key=lambda x: x.edge_id):
        if e.rel not in ("tested_by", "verifies", "refers_to"):
            continue
        if cap.get(e.rel, 0) >= limit:
            continue
        cap[e.rel] = cap.get(e.rel, 0) + 1
        s, d = node.get(e.src_id), node.get(e.dst_id)
        endp = prov.get(e.dst_id) or prov.get(e.src_id) or {}
        out.append({
            "relation": e.rel,
            "source_document": endp.get("doc"),
            "page": endp.get("page"),
            "table_or_anchor": endp.get("anchor"),
            "source_node": e.src_id, "source_kind": getattr(s, "kind", None),
            "source_label": (getattr(s, "label", "") or "")[:120],
            "dest_node": e.dst_id, "dest_kind": getattr(d, "kind", None),
            "dest_label": (getattr(d, "label", "") or "")[:120],
            "requirement_or_ref": (e.attrs or {}).get("via_ref") or (e.attrs or {}).get("match")
            or (endp.get("refs") or None),
            "provenance_hash": endp.get("hash"),
            "HUMAN_VERIFIED": None, "HUMAN_VERDICT": "",
        })
    g.close()
    return out


def _derive(tag: str, *, with_rw0003: bool, extract_tests: bool, pid: str) -> dict:
    root = Path(tempfile.mkdtemp(prefix=f"h10fv-{tag}-"))
    canon, graph, reports = root / "c", root / "g", root / "r"
    for p in (canon, graph, reports):
        p.mkdir(parents=True)
    try:
        _populate(canon, with_rw0003=with_rw0003, extract_tests=extract_tests)
        docs = [d for d, _, _ in RW6] + (["RW-0003"] if with_rw0003 else [])
        res = run_v2_pipeline(docs, project_id=pid, run_id=f"h10fv-{tag}",
                              canon_dir=canon, graph_dir=graph, report_base=reports)
        rd = Path(res["run_dir"])
        c = _counts(graph, pid)
        per_doc = {}
        for did in docs:
            with CanonicalStore(did, store_dir=canon) as s:
                tt = s.all("test")
                per_doc[did] = {
                    "tests": len(tt),
                    "tests_with_ref": sum(1 for t in tt if t.get("verifies_requirement_ids")),
                    "system_component": len(s.all("system_component")),
                    "actor": len(s.all("actor")),
                    "tables": len(s.all("table_obj")),
                    "tables_with_roles": sum(1 for t in s.all("table_obj") if t.get("column_roles")),
                    "claims": len(s.all("claim")),
                }
        return {"tag": tag, "docs": docs, "edges_by_rel": c["edges_by_rel"],
                "nodes_by_kind": c["nodes_by_kind"], "fingerprints": _fps(rd),
                "per_doc": per_doc,
                "human_gate_intact": res.get("human_gate_intact"),
                "document_egress_bytes": res.get("document_egress_bytes"),
                "edge_sample": _edge_sample(graph, pid, canon, docs),
                "findings_total": _findings_total(rd)}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _findings_total(rd: Path) -> int:
    n = 0
    for fn in ("regulatory_findings.json", "functional_findings.json", "technical_findings.json"):
        p = rd / fn
        if p.exists():
            n += len(json.loads(p.read_text()))
    return n


def main() -> int:
    control = _derive("control", with_rw0003=False, extract_tests=False, pid="H10FV-CTRL")
    run1 = _derive("run1", with_rw0003=True, extract_tests=True, pid="H10FV-V2")
    run2 = _derive("run2", with_rw0003=True, extract_tests=True, pid="H10FV-V2B")

    ce, r1 = control["edges_by_rel"], run1["edges_by_rel"]
    f1, f2 = run1["fingerprints"], run2["fingerprints"]
    n1 = run1["nodes_by_kind"]
    gate = {
        "TEST_OBJECTS_RW0003": run1["per_doc"].get("RW-0003", {}).get("tests", 0),
        "TESTS_WITH_REQUIREMENT_REF": run1["per_doc"].get("RW-0003", {}).get("tests_with_ref", 0),
        "TESTS_WITHOUT_REQUIREMENT_REF": (run1["per_doc"].get("RW-0003", {}).get("tests", 0)
                                          - run1["per_doc"].get("RW-0003", {}).get("tests_with_ref", 0)),
        "TEST_NODES_TOTAL": n1.get("test", 0),
        "TESTED_BY": r1.get("tested_by", 0),
        "VERIFIES": r1.get("verifies", 0),
        "REFERS_TO": r1.get("refers_to", 0),
        "SYSTEM_COMPONENT": n1.get("system_component", 0),
        "ACTOR": n1.get("actor", 0),
        "IMPLEMENTED_BY_BEFORE": ce.get("implemented_by", 0),
        "IMPLEMENTED_BY_AFTER": r1.get("implemented_by", 0),
        "IMPLEMENTED_BY_NO_REGRESSION": r1.get("implemented_by", 0) >= ce.get("implemented_by", 0),
        "DESIGNED_BY_BEFORE": ce.get("designed_by", 0),
        "DESIGNED_BY_AFTER": r1.get("designed_by", 0),
        "DESIGNED_BY_NO_REGRESSION": r1.get("designed_by", 0) >= ce.get("designed_by", 0),
        "CONTRADICTS_BEFORE": ce.get("contradicts", 0),
        "CONTRADICTS_AFTER": r1.get("contradicts", 0),
        "INPUT_CONFIG_FP_RUN1": f1["input_config_fingerprint"],
        "INPUT_CONFIG_FP_RUN2": f2["input_config_fingerprint"],
        "GRAPH_SNAPSHOT_FP_RUN1": f1["graph_snapshot_fingerprint"],
        "GRAPH_SNAPSHOT_FP_RUN2": f2["graph_snapshot_fingerprint"],
        "FINDINGS_FP_RUN1": f1["findings_fingerprint"],
        "FINDINGS_FP_RUN2": f2["findings_fingerprint"],
        "DETERMINISM_RUN1_EQ_RUN2": {
            "input_config": f1["input_config_fingerprint"] == f2["input_config_fingerprint"],
            "graph_snapshot": f1["graph_snapshot_fingerprint"] == f2["graph_snapshot_fingerprint"],
            "findings": f1["findings_fingerprint"] == f2["findings_fingerprint"],
        },
        "COUNTS_RUN1_EQ_RUN2": {
            k: run1["edges_by_rel"].get(k) == run2["edges_by_rel"].get(k)
            for k in ("tested_by", "verifies", "refers_to", "implemented_by", "designed_by")
        },
        "FINDINGS_TOTAL_CONTROL": control["findings_total"],
        "FINDINGS_TOTAL_RUN1": run1["findings_total"],
        "DOCUMENT_EGRESS_BYTES": run1["document_egress_bytes"],
        "HUMAN_GATE_INTACT": run1["human_gate_intact"],
        "FABRICATED_EDGES_CHECK": {
            "tested_by_from_upstream": all(
                x["source_kind"] in ("claim", "section", "requirement")
                for x in run1["edge_sample"] if x["relation"] == "tested_by"),
            "tested_by_to_test": all(
                x["dest_kind"] == "test"
                for x in run1["edge_sample"] if x["relation"] == "tested_by"),
            "verifies_to_requirement": all(
                x["dest_kind"] == "requirement"
                for x in run1["edge_sample"] if x["relation"] == "verifies"),
            "refers_to_to_entity": all(
                x["dest_kind"] in ("system_component", "actor")
                for x in run1["edge_sample"] if x["relation"] == "refers_to"),
            "all_sample_edges_have_provenance": all(
                x.get("provenance_hash") or x.get("requirement_or_ref")
                for x in run1["edge_sample"]),
        },
    }
    result = {"control": control, "run1": run1, "run2_fingerprints": f2, "gate": gate}
    (_REPO / "docs_plan/_h9_full/H10_FINAL_VALIDATION.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(gate, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
