#!/usr/bin/env python3
"""H-10 (2026-08-30) -- re-derivación GOBERNADA y AISLADA con V2_TEST_EXTRACTION.

Mide el efecto real de habilitar la extracción de objetos `Test`
(`extract_tests.py`, capacidad ya construida y probada por WP-D) sobre el
corpus REAL RW-6, por el FLUJO REAL (`run_v2_pipeline`), SIN tocar producción.

Reglas duras:
  * NO escribe en factory/regulatory/canonical_store ni graph_store ni en
    GMPAI/reports/... de producción. Todo va a tmp -> stores v1 intactos.
  * `network_locked()` -> DOCUMENT_EGRESS = 0.
  * CONTROL (flag OFF, canonical-v1-2026-08) vs TEST_ON (flag ON,
    canonical-v1-2026-08+tests-v1). TEST_ON se corre 2x (determinismo).
  * NO flipa `_EXT_VER` de producción: la activación real es decisión de Capa 9
    tras verificación HUMANA del muestreo `tested_by`.

Uso:  h10_test_extraction_rederivation.py --out results.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
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
PROJECT_ID = "H10-REDERIVE"


def _populate_canon(canon_dir: Path, *, extract_tests: bool) -> dict:
    per_doc = {}
    for did, tipo, fname in RW6:
        pdf = _ROCKWELL / fname
        if not pdf.exists():
            raise FileNotFoundError(pdf)
        extract_document(pdf, did, tipo=tipo, store_dir=canon_dir, extract_tests=extract_tests)
        with CanonicalStore(did, store_dir=canon_dir) as s:
            per_doc[did] = {
                "extraction_version": s.all("document")[0].get("extraction_version"),
                "claims": len(s.all("claim")),
                "sections": len(s.all("section")),
                "tables": len(s.all("table_obj")),
                "tables_with_roles": sum(1 for t in s.all("table_obj") if t.get("column_roles")),
                "tests": len(s.all("test")),
                "system_component": len(s.all("system_component")),
                "actor": len(s.all("actor")),
            }
    return per_doc


def _read_attestation(run_dir: Path) -> dict:
    p = run_dir / "audit_summary" / "audit_metadata.json"
    if p.exists():
        a = json.loads(p.read_text())
        return {"fingerprints": {
            "input_config_fingerprint": a.get("input_config_fingerprint"),
            "graph_snapshot_fingerprint": a.get("graph_snapshot_fingerprint"),
            "findings_fingerprint": a.get("findings_fingerprint"),
        }, "raw": a}
    return {}


_SAMPLE_RELS = ("tested_by", "verifies", "refers_to")


def _relations_sample(graph_dir: Path, project_id: str, canon_dir: Path,
                      limit_per_rel: int = 40) -> list[dict]:
    """Muestra reproducible de las relaciones NUEVAS de H-10, con provenance de
    extracción para verificación HUMANA (no marcada como verificada)."""
    g = GraphStore(project_id, store_dir=graph_dir)
    node = {n.node_id: n for n in g.nodes()}
    # índice de provenance de los nodos test/system_component/actor desde el canonical
    prov_idx: dict[str, dict] = {}
    for did in RW_IDS:
        try:
            with CanonicalStore(did, store_dir=canon_dir) as s:
                for t in s.all("test"):
                    prov_idx[t["test_id"]] = {"page": (t.get("provenance") or {}).get("page"),
                                              "anchor": (t.get("provenance") or {}).get("source_text", "")[:200],
                                              "doc": did}
                for c in s.all("system_component"):
                    prov_idx[c["component_id"]] = {"page": (c.get("provenance") or {}).get("page"),
                                                   "anchor": (c.get("provenance") or {}).get("source_text", "")[:200],
                                                   "doc": did}
                for a in s.all("actor"):
                    prov_idx[a["actor_id"]] = {"page": (a.get("provenance") or {}).get("page"),
                                               "anchor": (a.get("provenance") or {}).get("source_text", "")[:200],
                                               "doc": did}
        except Exception:  # noqa: BLE001
            pass
    per_rel: dict[str, int] = {r: 0 for r in _SAMPLE_RELS}
    out = []
    for e in g.edges():
        if e.rel not in _SAMPLE_RELS or per_rel[e.rel] >= limit_per_rel:
            continue
        s, d = node.get(e.src_id), node.get(e.dst_id)
        endprov = prov_idx.get(e.dst_id) or prov_idx.get(e.src_id) or {}
        out.append({
            "relation": e.rel,
            "source_node": e.src_id, "source_kind": getattr(s, "kind", None),
            "source_doc": getattr(s, "document_id", None),
            "source_label": (getattr(s, "label", "") or "")[:140],
            "dest_node": e.dst_id, "dest_kind": getattr(d, "kind", None),
            "dest_doc": getattr(d, "document_id", None),
            "dest_label": (getattr(d, "label", "") or "")[:140],
            "via_ref": (e.attrs or {}).get("via_ref") or (e.attrs or {}).get("match"),
            "extraction_provenance": {
                "source_document": endprov.get("doc"),
                "page": endprov.get("page"),
                "exact_source_anchor": endprov.get("anchor"),
            },
            "HUMAN_VERIFIED": False,
        })
        per_rel[e.rel] += 1
    g.close()
    return out


def _edge_counts(graph_dir: Path, project_id: str) -> dict:
    g = GraphStore(project_id, store_dir=graph_dir)
    c = g.counts()
    g.close()
    return {"edges_by_rel": c["edges_by_rel"], "nodes_by_kind": c["nodes_by_kind"]}


def _findings_summary(run_dir: Path) -> dict:
    allf = []
    for fn in ("regulatory_findings.json", "functional_findings.json", "technical_findings.json"):
        p = run_dir / fn
        if p.exists():
            allf += json.loads(p.read_text())
    from collections import Counter
    return {"total": len(allf),
            "by_subtype": dict(Counter(f.get("subtype") for f in allf)),
            "keys": sorted({(f.get("finding_class"), f.get("subtype"), f.get("document"),
                             f.get("page"), f.get("source_hash")) for f in allf}.__iter__(),
                           key=lambda x: tuple(str(v) for v in x))}


def _variant(tag: str, *, extract_tests: bool) -> dict:
    root = Path(tempfile.mkdtemp(prefix=f"h10-{tag}-"))
    canon, graph, reports = root / "canon", root / "graph", root / "reports"
    for p in (canon, graph, reports):
        p.mkdir(parents=True)
    try:
        t0 = time.time()
        per_doc = _populate_canon(canon, extract_tests=extract_tests)
        run_id = f"h10-{tag}"
        res = run_v2_pipeline(RW_IDS, project_id=PROJECT_ID, run_id=run_id,
                              canon_dir=canon, graph_dir=graph, report_base=reports)
        run_dir = Path(res["run_dir"])
        att = _read_attestation(run_dir)
        fps = att.get("fingerprints") or {}
        ec = _edge_counts(graph, PROJECT_ID)
        fs = _findings_summary(run_dir)
        return {
            "tag": tag, "extract_tests": extract_tests,
            "wall_s": round(time.time() - t0, 1),
            "per_doc": per_doc,
            "edges_by_rel": ec["edges_by_rel"],
            "nodes_by_kind": ec["nodes_by_kind"],
            "findings_total": fs["total"],
            "findings_by_subtype": fs["by_subtype"],
            "_findings_keys": fs["keys"],
            "fingerprints": {
                "input_config_fingerprint": fps.get("input_config_fingerprint"),
                "graph_snapshot_fingerprint": fps.get("graph_snapshot_fingerprint"),
                "findings_fingerprint": fps.get("findings_fingerprint"),
            },
            "pipeline_summary": {k: res.get(k) for k in
                                 ("total_findings", "findings_degraded",
                                  "findings_suppressed", "human_gate_intact",
                                  "analysis_coverage_mode") if k in res},
            "relations_sample": _relations_sample(graph, PROJECT_ID, canon),
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    control = _variant("control", extract_tests=False)
    test1 = _variant("teston1", extract_tests=True)
    test2 = _variant("teston2", extract_tests=True)

    ce, te = control["edges_by_rel"], test1["edges_by_rel"]
    f1, f2 = test1["fingerprints"], test2["fingerprints"]
    ck = {tuple(x) for x in control["_findings_keys"]}
    tk = {tuple(x) for x in test1["_findings_keys"]}
    findings_delta = {
        "control_total": control["findings_total"],
        "test_on_total": test1["findings_total"],
        "only_in_control": [list(x) for x in sorted(ck - tk)][:50],
        "only_in_test_on": [list(x) for x in sorted(tk - ck)][:50],
        "subtype_control": control["findings_by_subtype"],
        "subtype_test_on": test1["findings_by_subtype"],
    }
    for v in (control, test1, test2):
        v.pop("_findings_keys", None)
    tn = test1["nodes_by_kind"]
    gate = {
        "TEST_OBJECTS_TEST_ON": tn.get("test", 0),
        "SYSTEM_COMPONENT_TEST_ON": tn.get("system_component", 0),
        "ACTOR_TEST_ON": tn.get("actor", 0),
        "TESTED_BY_CONTROL": ce.get("tested_by", 0),
        "TESTED_BY_TEST_ON": te.get("tested_by", 0),
        "TESTED_BY_POSITIVE": te.get("tested_by", 0) > 0,
        "VERIFIES_CONTROL": ce.get("verifies", 0),
        "VERIFIES_TEST_ON": te.get("verifies", 0),
        "IMPLEMENTED_BY_CONTROL": ce.get("implemented_by", 0),
        "IMPLEMENTED_BY_TEST_ON": te.get("implemented_by", 0),
        "IMPLEMENTED_BY_NO_REGRESSION": te.get("implemented_by", 0) >= ce.get("implemented_by", 0),
        "DESIGNED_BY_CONTROL": ce.get("designed_by", 0),
        "DESIGNED_BY_TEST_ON": te.get("designed_by", 0),
        "DESIGNED_BY_NO_REGRESSION": te.get("designed_by", 0) >= ce.get("designed_by", 0),
        "REFERS_TO_TEST_ON": te.get("refers_to", 0),
        "CONTRADICTS_CONTROL": ce.get("contradicts", 0),
        "CONTRADICTS_TEST_ON": te.get("contradicts", 0),
        "GSFP_CONTROL": control["fingerprints"]["graph_snapshot_fingerprint"],
        "GSFP_TEST_ON": f1["graph_snapshot_fingerprint"],
        "GSFP_CHANGED": control["fingerprints"]["graph_snapshot_fingerprint"] != f1["graph_snapshot_fingerprint"],
        "ICFP_CONTROL": control["fingerprints"]["input_config_fingerprint"],
        "ICFP_TEST_ON": f1["input_config_fingerprint"],
        "FINDINGS_FP_CONTROL": control["fingerprints"]["findings_fingerprint"],
        "FINDINGS_FP_TEST_ON": f1["findings_fingerprint"],
        "DETERMINISM_TEST_ON_2X": {
            "input_config": f1["input_config_fingerprint"] == f2["input_config_fingerprint"],
            "graph_snapshot": f1["graph_snapshot_fingerprint"] == f2["graph_snapshot_fingerprint"],
            "findings": f1["findings_fingerprint"] == f2["findings_fingerprint"],
        },
    }
    gate["FINDINGS_DELTA"] = findings_delta
    _new = findings_delta["only_in_test_on"]     # cada key = [class, subtype, doc, page, source_hash]
    gate["FABRICATED_EVIDENCE_CHECK"] = {
        "n_new_findings": len(_new),
        "all_new_findings_have_source_hash": all(bool(k[4]) for k in _new),
    }
    # aristas fabricadas: refers_to sólo válido si su destino es un nodo entidad REAL
    rs = test1["relations_sample"]
    gate["FABRICATED_EDGES_CHECK"] = {
        "refers_to_all_to_entity_nodes": all(
            r["dest_kind"] in ("system_component", "actor")
            for r in rs if r["relation"] == "refers_to"),
        "refers_to_all_have_anchor": all(
            bool((r.get("extraction_provenance") or {}).get("exact_source_anchor"))
            for r in rs if r["relation"] == "refers_to"),
        "tested_by_all_from_upstream": all(
            r["source_kind"] in ("claim", "section", "requirement")
            for r in rs if r["relation"] == "tested_by"),
    }
    result = {"control": control, "test_on": test1,
              "test_on_run2_fingerprints": f2, "gate": gate}
    txt = json.dumps(result, indent=1, ensure_ascii=False, default=str)
    if args.out:
        Path(args.out).write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
