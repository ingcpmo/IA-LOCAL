"""Tests -- factory/regulatory/findings/functional_findings.py (V2, B6a).

DETERMINISTA, sin LLM: findings funcionales / de trazabilidad / de
cobertura desde el evidence graph (B2). Anclados al source_text literal
del claim/test (B1).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.findings import functional_findings as ff
from factory.regulatory.graph import build as gb


def _seed_doc(canon_dir, did, tipo, claims, tests=None):
    with CanonicalStore(did, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=did, sha256="x" * 64, tipo=tipo, titulo=tipo, n_paginas=20))
        for pg, tp, tx in claims:
            s.put(m.build_claim(did, pg, tx, tp, tx))
        for ident, desc in (tests or []):
            s.put(m.build_test(did, 5, ident, desc))


def test_contradiction_and_orphan_test_and_untraced(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"

    _seed_doc(canon_dir, "RW-URS", "URS", [
        (7, "control", "For F09.00 the operator shall have access to the alarm reset function."),
        (8, "control", "UR9.9.9 The system shall retain historical trends for one year."),
    ])
    _seed_doc(canon_dir, "RW-DS", "DS", [
        (12, "control", "Regarding F09.00, the operator shall not have access to the alarm "
                        "reset function without supervisor override."),
    ])
    _seed_doc(canon_dir, "RW-SAT", "SAT", [], tests=[
        ("SAT-999", "Verify that the coffee machine brews espresso in under 30 seconds."),
    ])

    docs = [("RW-URS", "URS"), ("RW-DS", "DS"), ("RW-SAT", "SAT")]
    gb.build_project_graph("PRJ-F", docs, canon_dir=canon_dir, graph_dir=graph_dir)

    findings = ff.graph_functional_findings(
        "PRJ-F", [d for d, _ in docs], extraction_version="canonical-v1-2026-08",
        run_id="run-1", canon_dir=canon_dir, graph_dir=graph_dir)

    by_subtype = {}
    for f in findings:
        by_subtype.setdefault(f.subtype, []).append(f)

    # contradicción F09.00
    assert "CONTRADICTORY_FUNCTIONAL_BEHAVIOR" in by_subtype
    c = by_subtype["CONTRADICTORY_FUNCTIONAL_BEHAVIOR"][0]
    assert c.finding_class == "FunctionalFinding"
    assert "F09.00" in c.source_text
    assert c.human_state == "UNREVIEWED"
    assert c.provenance.graph_path[1] == "contradicts"
    assert c.risk["band"] in ("MEDIUM", "HIGH", "CRITICAL")

    # test sin requisito
    assert "TEST_WITHOUT_REQUIREMENT" in by_subtype
    t = by_subtype["TEST_WITHOUT_REQUIREMENT"][0]
    assert t.finding_class == "TestCoverageFinding"
    assert "espresso" in t.source_text

    # claim URS sin trazabilidad hacia abajo (UR9.9.9)
    assert "REQUIREMENT_NOT_TRACED" in by_subtype
    tr = [x for x in by_subtype["REQUIREMENT_NOT_TRACED"] if "UR9.9.9" in x.source_text]
    assert tr
    assert tr[0].finding_class == "TraceabilityFinding"
    assert tr[0].machine_state == "MACHINE_INCONCLUSIVE"


def test_no_findings_when_everything_traces(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    _seed_doc(canon_dir, "RW-URS", "URS", [
        (7, "control", "UR3.3.1 audit trail record shall be generated on threshold change."),
    ])
    _seed_doc(canon_dir, "RW-FS", "FS", [
        (41, "function", "This function implements UR3.3.1 audit trail record generation."),
    ])
    docs = [("RW-URS", "URS"), ("RW-FS", "FS")]
    gb.build_project_graph("PRJ-OK", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = ff.graph_functional_findings(
        "PRJ-OK", [d for d, _ in docs], extraction_version="v1",
        canon_dir=canon_dir, graph_dir=graph_dir)
    # URS claim SÍ tiene implemented_by -> sin REQUIREMENT_NOT_TRACED; sin contradicciones; sin tests
    assert all(f.subtype != "REQUIREMENT_NOT_TRACED" for f in findings)
    assert all(f.subtype != "CONTRADICTORY_FUNCTIONAL_BEHAVIOR" for f in findings)


def test_findings_feed_report_v2(tmp_path):
    from factory.regulatory.findings import report_v2
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    _seed_doc(canon_dir, "RW-URS", "URS", [
        (7, "control", "For F01.00 the pump shall start."),
    ])
    _seed_doc(canon_dir, "RW-DS", "DS", [
        (9, "control", "For F01.00 the pump shall not start unless interlocks are clear."),
    ])
    docs = [("RW-URS", "URS"), ("RW-DS", "DS")]
    gb.build_project_graph("PRJ-R", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    findings = ff.graph_functional_findings("PRJ-R", [d for d, _ in docs],
                                            extraction_version="v1", canon_dir=canon_dir,
                                            graph_dir=graph_dir)
    rep = report_v2.build_report(findings, document_id="PRJ-R")
    md = report_v2.render_markdown(rep)
    assert rep["summary"]["human_review_required"] == len(findings)
    assert "NO es una declaración de cumplimiento" in md
