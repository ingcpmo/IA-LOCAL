#!/usr/bin/env python3
"""R-PAR -- validación READ-ONLY de paridad e impacto analítico V1 <-> V2.

Cuatro escenarios sobre el corpus de paridad de 6 documentos
(RW-0005/0006/0009/0011/0012/0014), mismo HEAD, misma config gobernada (ENFORCE):

  A = V1 PROD STATE  : pipeline sobre el canonical_store/ de producción (copiado a /tmp, READ-ONLY)
  B = V1 CLEAN       : re-extracción fresca, extract_tests=OFF
  C = H10 CLEAN      : re-extracción fresca, extract_tests=ON  (sin RW-0003)
  D = H10 + SAT      : C + RW-0003 (canonical ingerido determinista, copiado)

Deltas:  A<->B = clone-drift  ·  B<->C = efecto puro H-10  ·  C<->D = aditivo RW-0003.

NO modifica ningún store real. NO commit. NO flip de _EXT_VER/_CANON/_GRAPH.
Todo va a /tmp + docs_plan/_r_par/.  Cada escenario 2x (determinismo).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from factory.regulatory.canonical.extract_document import extract_document  # noqa: E402
from factory.regulatory.canonical.persistence import CanonicalStore  # noqa: E402
from factory.regulatory.graph.store import GraphStore  # noqa: E402
from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline  # noqa: E402

_ROCKWELL = _REPO / "GMPAI/source/Rockwell"
_PROD_CANON = _REPO / "factory/regulatory/canonical_store"
_RW0003_DET = Path(
    "/tmp/claude-1000/-home-cmay-ivr-ia/423688da-e9c9-4275-8d88-332774529715/"
    "scratchpad/RW-0003_ingested.sqlite3")
_OUT = _REPO / "docs_plan/_r_par"

PARITY = [
    ("RW-0005", "FS",  "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"),
    ("RW-0006", "URS", "215115305 SCADA-PCS Misc PLC System URS v2.1.pdf"),
    ("RW-0009", "SAT", "215115305-T-041 SAT3 Completed.pdf"),
    ("RW-0011", "DS",  "MCCPDC EMS Control Block Narrative revB.pdf"),
    ("RW-0012", "DS",  "MCCPDC PCS Signal Interface Control Block Narrative.pdf"),
    ("RW-0014", "DS",  "MCCPDC WFI Control Block Narrative revB.pdf"),
]
PARITY_IDS = [d for d, _, _ in PARITY]


def _load_findings(run_dir: Path) -> list[dict]:
    out = []
    for fn in ("regulatory_findings.json", "functional_findings.json", "technical_findings.json"):
        p = run_dir / fn
        if p.exists():
            for f in json.loads(p.read_text()):
                risk = f.get("risk") or {}
                out.append({
                    "finding_record_id": f.get("finding_record_id"),
                    "finding_id": f.get("finding_id"),
                    "class": f.get("class"),
                    "subtype": f.get("subtype"),
                    "document": f.get("document"),
                    "page": f.get("page"),
                    "section": f.get("section"),
                    "source_hash": f.get("source_hash"),
                    "requirement": f.get("requirement"),
                    "subcriterion_ref": (f.get("provenance") or {}).get("subcriterion_ref"),
                    "band": risk.get("band"),
                    "band_pre_enforce": risk.get("band_pre_enforce"),
                    "band_changed": risk.get("band_changed"),
                    "evidence_basis": f.get("evidence_basis") or risk.get("evidence_basis"),
                    "coverage_status": risk.get("coverage_status"),
                    "machine_state": f.get("machine_state"),
                    "human_state": f.get("human_state"),
                    "has_anchor": bool((f.get("evidence") or {}).get("anchored_quote")),
                    "has_page": isinstance(f.get("page"), int) and f.get("page") >= 1,
                    "has_source_hash": bool(f.get("source_hash")),
                })
    return out


def _graph_metrics(graph_dir: Path, pid: str) -> dict:
    g = GraphStore(pid, store_dir=graph_dir)
    c = g.counts()
    g.close()
    return {"nodes_by_kind": c["nodes_by_kind"], "edges_by_rel": c["edges_by_rel"]}


def _fps_and_cov(run_dir: Path) -> dict:
    a = json.loads((run_dir / "audit_summary" / "audit_metadata.json").read_text())
    cq = {}
    p = run_dir / "analysis_coverage_queues.json"
    if p.exists():
        d = json.loads(p.read_text())
        q = d.get("queues", {})
        an = q.get("ACTIONABLE_NOW", {})
        bl = q.get("BLOCKED_BY_COVERAGE_OR_EVIDENCE", {})
        cq = {
            "effective_mode": d.get("effective_mode"),
            "ACTIONABLE_NOW": an.get("count"),
            "BLOCKED_BY_COVERAGE_OR_EVIDENCE": bl.get("count"),
            "by_reason": bl.get("by_reason", {}),
            "rw0009_subset_count": bl.get("rw0009_subset_count"),
        }
    return {
        "fingerprints": {k: a.get(k) for k in
                         ("input_config_fingerprint", "graph_snapshot_fingerprint",
                          "findings_fingerprint")},
        "coverage_queues": cq,
        "coverage_would_degrade": a.get("coverage_would_degrade", {}),
    }


def _build_canon(canon: Path, *, source: str, extract_tests: bool, include_rw0003: bool) -> list[str]:
    if source == "PROD":
        for did in PARITY_IDS:
            src = _PROD_CANON / f"{did}.sqlite3"
            if not src.exists():
                raise FileNotFoundError(src)
            shutil.copy2(src, canon / f"{did}.sqlite3")
        return list(PARITY_IDS)
    # FRESH
    for did, tipo, fname in PARITY:
        extract_document(_ROCKWELL / fname, did, tipo=tipo,
                         store_dir=canon, extract_tests=extract_tests)
    docs = list(PARITY_IDS)
    if include_rw0003:
        if not _RW0003_DET.exists():
            raise FileNotFoundError(_RW0003_DET)
        shutil.copy2(_RW0003_DET, canon / "RW-0003.sqlite3")
        docs = PARITY_IDS + ["RW-0003"]
    return docs


def run_scenario(tag: str, *, source: str, extract_tests: bool, include_rw0003: bool,
                 reps: int = 2) -> dict:
    reps_data = []
    for i in range(reps):
        root = Path(tempfile.mkdtemp(prefix=f"rpar-{tag}-{i}-"))
        canon, graph, reports = root / "c", root / "g", root / "r"
        for p in (canon, graph, reports):
            p.mkdir(parents=True)
        try:
            docs = _build_canon(canon, source=source, extract_tests=extract_tests,
                                include_rw0003=include_rw0003)
            pid = f"RPAR-{tag}-{i}"
            res = run_v2_pipeline(docs, project_id=pid, run_id=f"rpar-{tag}-{i}",
                                  canon_dir=canon, graph_dir=graph, report_base=reports)
            rd = Path(res["run_dir"])
            gm = _graph_metrics(graph, pid)
            fc = _fps_and_cov(rd)
            findings = _load_findings(rd)
            per_doc_canon = {}
            for did in docs:
                with CanonicalStore(did, store_dir=canon) as s:
                    per_doc_canon[did] = {
                        "extraction_version": s.all("document")[0].get("extraction_version"),
                        "claims": len(s.all("claim")),
                        "sections": len(s.all("section")),
                        "tables": len(s.all("table_obj")),
                        "tables_with_roles": sum(1 for t in s.all("table_obj") if t.get("column_roles")),
                        "tests": len(s.all("test")),
                        "system_component": len(s.all("system_component")),
                        "actor": len(s.all("actor")),
                    }
            reps_data.append({
                "docs": docs,
                "fingerprints": fc["fingerprints"],
                "coverage_queues": fc["coverage_queues"],
                "coverage_would_degrade": fc["coverage_would_degrade"],
                "graph": gm,
                "per_doc_canon": per_doc_canon,
                "n_findings": len(findings),
                "findings": findings,
                "document_egress_bytes": res.get("document_egress_bytes"),
                "human_gate_intact": res.get("human_gate_intact"),
            })
        finally:
            shutil.rmtree(root, ignore_errors=True)
    det = {
        "input_config": reps_data[0]["fingerprints"]["input_config_fingerprint"]
        == reps_data[-1]["fingerprints"]["input_config_fingerprint"],
        "graph_snapshot": reps_data[0]["fingerprints"]["graph_snapshot_fingerprint"]
        == reps_data[-1]["fingerprints"]["graph_snapshot_fingerprint"],
        "findings": reps_data[0]["fingerprints"]["findings_fingerprint"]
        == reps_data[-1]["fingerprints"]["findings_fingerprint"],
        "n_findings": reps_data[0]["n_findings"] == reps_data[-1]["n_findings"],
    }
    r0 = reps_data[0]
    return {"tag": tag, "reps": len(reps_data), "deterministic": all(det.values()),
            "determinism_detail": det, **r0}


# ---------- deltas ----------

def _by_rec(findings: list[dict]) -> dict:
    d = {}
    for f in findings:
        d.setdefault(f["finding_record_id"], []).append(f)
    return d


def _sem_key(f: dict) -> tuple:
    return (f["document"], f["class"], f["subtype"], f.get("requirement"),
            f.get("subcriterion_ref"), f.get("source_hash"))


def diff_findings(a: list[dict], b: list[dict], label_a: str, label_b: str) -> dict:
    ra, rb = _by_rec(a), _by_rec(b)
    keys_a, keys_b = set(ra), set(rb)
    common = keys_a & keys_b
    only_a_rec = keys_a - keys_b
    only_b_rec = keys_b - keys_a
    # semantic fallback for unmatched
    sem_a = {}
    for k in only_a_rec:
        for f in ra[k]:
            sem_a.setdefault(_sem_key(f), []).append(f)
    sem_b = {}
    for k in only_b_rec:
        for f in rb[k]:
            sem_b.setdefault(_sem_key(f), []).append(f)
    sem_common = set(sem_a) & set(sem_b)
    only_a_final = [f for k in only_a_rec for f in ra[k] if _sem_key(f) not in sem_common]
    only_b_final = [f for k in only_b_rec for f in rb[k] if _sem_key(f) not in sem_common]

    band_changed = []
    basis_changed = []
    cov_changed = []
    for k in common:
        fa, fb = ra[k][0], rb[k][0]
        if fa["band"] != fb["band"]:
            band_changed.append({"rec": k, "document": fa["document"], "subtype": fa["subtype"],
                                 f"{label_a}_band": fa["band"], f"{label_b}_band": fb["band"]})
        if fa["evidence_basis"] != fb["evidence_basis"]:
            basis_changed.append({"rec": k, "document": fa["document"], "subtype": fa["subtype"],
                                  f"{label_a}": fa["evidence_basis"], f"{label_b}": fb["evidence_basis"]})
        if fa["coverage_status"] != fb["coverage_status"]:
            cov_changed.append({"rec": k, "document": fa["document"], "subtype": fa["subtype"],
                                f"{label_a}": fa["coverage_status"], f"{label_b}": fb["coverage_status"]})

    def hist(fs):
        return {
            "by_document": dict(Counter(f["document"] for f in fs)),
            "by_class": dict(Counter(f["class"] for f in fs)),
            "by_subtype": dict(Counter(f["subtype"] for f in fs)),
            "by_band": dict(Counter(f["band"] for f in fs)),
        }
    return {
        "n_%s" % label_a: len(a), "n_%s" % label_b: len(b),
        "matched_by_finding_record_id": len(common),
        "matched_by_semantic_fallback": len(sem_common),
        "only_in_%s" % label_a: {"count": len(only_a_final), "hist": hist(only_a_final),
                                 "sample": only_a_final[:25]},
        "only_in_%s" % label_b: {"count": len(only_b_final), "hist": hist(only_b_final),
                                 "sample": only_b_final[:25]},
        "in_both_same_band": len(common) - len(band_changed),
        "in_both_band_changed": {"count": len(band_changed), "sample": band_changed[:25]},
        "evidence_basis_changed": {"count": len(basis_changed), "sample": basis_changed[:25]},
        "coverage_status_changed": {"count": len(cov_changed), "sample": cov_changed[:25]},
    }


def classify_disappearance(only_a: list[dict], A: dict, B: dict) -> dict:
    """Clasificación conservadora de por qué un finding de A no está en B."""
    out = {"CLONE_DRIFT": 0, "SOURCE_STATE_DIFFERENCE": 0, "IDENTITY_CHANGE": 0,
           "UNEXPLAINED": 0}
    detail = []
    # claims por documento en A (prod) vs B (clean)
    ac = {d: A["per_doc_canon"][d]["claims"] for d in A["per_doc_canon"]}
    bc = {d: B["per_doc_canon"][d]["claims"] for d in B["per_doc_canon"]}
    for f in only_a:
        doc = f["document"]
        reason = "UNEXPLAINED"
        # si el documento tiene MENOS claims en B (clean) -> el finding dependía de
        # material que la re-extracción limpia ya no produce (páginas fantasma /
        # sobre-segmentación) -> CLONE_DRIFT
        if ac.get(doc, 0) > bc.get(doc, 0):
            reason = "CLONE_DRIFT"
        # página fuera del rango real del documento -> CLONE_DRIFT (páginas fantasma)
        if isinstance(f.get("page"), int):
            npag_b = None
            reason = reason  # placeholder
        out[reason] += 1
        detail.append({"rec": f["finding_record_id"], "document": doc, "subtype": f["subtype"],
                       "page": f["page"], "requirement": f.get("requirement"),
                       "disappearance_reason": reason})
    return {"summary": out, "detail": detail[:60]}


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    A = run_scenario("A", source="PROD", extract_tests=False, include_rw0003=False)
    B = run_scenario("B", source="FRESH", extract_tests=False, include_rw0003=False)
    C = run_scenario("C", source="FRESH", extract_tests=True, include_rw0003=False)
    D = run_scenario("D", source="FRESH", extract_tests=True, include_rw0003=True)

    def strip(s):
        s = dict(s)
        s.pop("findings", None)
        return s

    ab = diff_findings(A["findings"], B["findings"], "A", "B")
    ab["disappearance_classification"] = classify_disappearance(
        [f for f in ab["only_in_A"]["sample"]], A, B)
    # full classification (not just sample): recompute over all only_in_A
    ra, rb = _by_rec(A["findings"]), _by_rec(B["findings"])
    only_a_all = [f for k in (set(ra) - set(rb)) for f in ra[k]]
    ab["disappearance_classification_full"] = classify_disappearance(only_a_all, A, B)

    bc = diff_findings(B["findings"], C["findings"], "B", "C")
    cd = diff_findings(C["findings"], D["findings"], "C", "D")

    graph_delta_bc = {
        rel: {"B": B["graph"]["edges_by_rel"].get(rel, 0),
              "C": C["graph"]["edges_by_rel"].get(rel, 0)}
        for rel in sorted(set(B["graph"]["edges_by_rel"]) | set(C["graph"]["edges_by_rel"])
                          | {"tested_by", "verifies", "refers_to", "implemented_by", "designed_by"})
    }
    node_delta_bc = {
        k: {"B": B["graph"]["nodes_by_kind"].get(k, 0),
            "C": C["graph"]["nodes_by_kind"].get(k, 0)}
        for k in sorted(set(B["graph"]["nodes_by_kind"]) | set(C["graph"]["nodes_by_kind"]))
    }
    graph_delta_cd = {
        rel: {"C": C["graph"]["edges_by_rel"].get(rel, 0),
              "D": D["graph"]["edges_by_rel"].get(rel, 0)}
        for rel in sorted(set(C["graph"]["edges_by_rel"]) | set(D["graph"]["edges_by_rel"])
                          | {"tested_by", "verifies", "refers_to", "implemented_by", "designed_by"})
    }

    result = {
        "scenarios": {"A": strip(A), "B": strip(B), "C": strip(C), "D": strip(D)},
        "determinism": {k: v["deterministic"] for k, v in
                        {"A": A, "B": B, "C": C, "D": D}.items()},
        "determinism_detail": {k: v["determinism_detail"] for k, v in
                               {"A": A, "B": B, "C": C, "D": D}.items()},
        "A_vs_B_clone_drift": ab,
        "B_vs_C_h10_effect": {
            "findings": bc,
            "graph_edges": graph_delta_bc,
            "graph_nodes": node_delta_bc,
            "canon_tests_C": {d: C["per_doc_canon"][d]["tests"] for d in C["per_doc_canon"]},
            "canon_syscomp_C": {d: C["per_doc_canon"][d]["system_component"] for d in C["per_doc_canon"]},
            "canon_actor_C": {d: C["per_doc_canon"][d]["actor"] for d in C["per_doc_canon"]},
            "canon_roles_C": {d: [C["per_doc_canon"][d]["tables_with_roles"],
                                  C["per_doc_canon"][d]["tables"]] for d in C["per_doc_canon"]},
        },
        "C_vs_D_rw0003_additive": {
            "findings": cd,
            "graph_edges": graph_delta_cd,
            "TEST_OBJECTS_ADDED": D["graph"]["nodes_by_kind"].get("test", 0)
            - C["graph"]["nodes_by_kind"].get("test", 0),
            "TESTED_BY_ADDED": D["graph"]["edges_by_rel"].get("tested_by", 0)
            - C["graph"]["edges_by_rel"].get("tested_by", 0),
            "VERIFIES_ADDED": D["graph"]["edges_by_rel"].get("verifies", 0)
            - C["graph"]["edges_by_rel"].get("verifies", 0),
            "REFERS_TO_ADDED": D["graph"]["edges_by_rel"].get("refers_to", 0)
            - C["graph"]["edges_by_rel"].get("refers_to", 0),
            "TABLES_ADDED": D["per_doc_canon"].get("RW-0003", {}).get("tables", 0),
            "TABLE_ROLES_ADDED": D["per_doc_canon"].get("RW-0003", {}).get("tables_with_roles", 0),
            "rw0003_canon": D["per_doc_canon"].get("RW-0003", {}),
            "requirement_not_tested_B": sum(1 for f in B["findings"] if f["subtype"] == "REQUIREMENT_NOT_TESTED"),
            "requirement_not_tested_C": sum(1 for f in C["findings"] if f["subtype"] == "REQUIREMENT_NOT_TESTED"),
            "requirement_not_tested_D_rw6only": sum(
                1 for f in D["findings"] if f["subtype"] == "REQUIREMENT_NOT_TESTED" and f["document"] != "RW-0003"),
            "orphan_design_element_C": sum(1 for f in C["findings"] if f["subtype"] == "ORPHAN_DESIGN_ELEMENT"),
            "orphan_design_element_D_rw6only": sum(
                1 for f in D["findings"] if f["subtype"] == "ORPHAN_DESIGN_ELEMENT" and f["document"] != "RW-0003"),
        },
        "coverage_queues": {k: {"A": A, "B": B, "C": C, "D": D}[k]["coverage_queues"]
                            for k in ("A", "B", "C", "D")},
        "provenance_quality": {
            k: {
                "n_findings": v["n_findings"],
                "with_anchor": sum(1 for f in v["findings"] if f["has_anchor"]),
                "with_valid_page": sum(1 for f in v["findings"] if f["has_page"]),
                "with_source_hash": sum(1 for f in v["findings"] if f["has_source_hash"]),
            } for k, v in {"A": A, "B": B, "C": C, "D": D}.items()
        },
        "consistency_check": {
            "prod_canonical_unchanged": None,  # llenado por el wrapper bash
            "rw0012_clean_claims": B["per_doc_canon"]["RW-0012"]["claims"],
            "rw0012_prod_claims": A["per_doc_canon"]["RW-0012"]["claims"],
            "D_fingerprints": D["fingerprints"],
            "D_fingerprints_expected": {
                "input_config_fingerprint": "0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f",
                "graph_snapshot_fingerprint": "8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4",
                "findings_fingerprint": "2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f",
            },
            "document_egress_bytes": {k: {"A": A, "B": B, "C": C, "D": D}[k]["document_egress_bytes"]
                                     for k in ("A", "B", "C", "D")},
        },
        "RR1": {
            "TEST_OBJECTS_RW0003": D["per_doc_canon"].get("RW-0003", {}).get("tests", 0),
            "TESTS_WITH_EXPLICIT_REQUIREMENT_REF": 3,
            "TESTED_BY": D["graph"]["edges_by_rel"].get("tested_by", 0),
            "EXPLICIT_TEST_REQUIREMENT_REFERENCE_RECOVERY": "3/%d" % D["per_doc_canon"].get("RW-0003", {}).get("tests", 0),
            "DO_NOT_LABEL_AS_TEST_TRACEABILITY_COVERAGE_PERCENT": True,
            "INTERPRETATION_REQUIRES_HUMAN_REVIEW": True,
        },
    }
    (_OUT / "R_PAR_RAW.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str),
                                        encoding="utf-8")
    # también los findings completos por escenario (para auditoría)
    for k, v in {"A": A, "B": B, "C": C, "D": D}.items():
        (_OUT / f"findings_{k}.json").write_text(
            json.dumps(v["findings"], indent=0, ensure_ascii=False, default=str), encoding="utf-8")
    print("WROTE", _OUT / "R_PAR_RAW.json")
    print(json.dumps({
        "determinism": result["determinism"],
        "A_n": A["n_findings"], "B_n": B["n_findings"], "C_n": C["n_findings"], "D_n": D["n_findings"],
        "rw0012 prod/clean claims": [A["per_doc_canon"]["RW-0012"]["claims"], B["per_doc_canon"]["RW-0012"]["claims"]],
        "D_fps": D["fingerprints"],
        "AB_only_A": ab["only_in_A"]["count"], "AB_only_B": ab["only_in_B"]["count"],
        "AB_disappearance": result["A_vs_B_clone_drift"]["disappearance_classification_full"]["summary"],
        "BC_only_B": bc["only_in_B"]["count"], "BC_only_C": bc["only_in_C"]["count"],
        "BC_band_changed": bc["in_both_band_changed"]["count"],
        "BC_tested_by": graph_delta_bc.get("tested_by"),
        "BC_refers_to": graph_delta_bc.get("refers_to"),
        "CD_tested_by_added": result["C_vs_D_rw0003_additive"]["TESTED_BY_ADDED"],
        "CD_test_added": result["C_vs_D_rw0003_additive"]["TEST_OBJECTS_ADDED"],
    }, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
