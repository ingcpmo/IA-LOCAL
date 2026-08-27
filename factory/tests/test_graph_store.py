"""Tests -- factory/regulatory/graph/store.py (V2, B2).

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B2: aristas
tipadas, SIN aristas colgantes (fail-closed), ids deterministas.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.graph.store import (
    DanglingEdgeError, GraphStore, UnknownRelationError, _edge_id,
)


def _g(tmp_path):
    return GraphStore("PRJ-TEST", store_dir=tmp_path)


def test_node_crud(tmp_path):
    g = _g(tmp_path)
    g.add_node("req-1", "requirement", "Audit trail", attrs={"source_id": "ecfr"})
    assert g.has_node("req-1")
    n = g.get_node("req-1")
    assert n.kind == "requirement"
    assert n.attrs["source_id"] == "ecfr"
    assert [x.node_id for x in g.nodes(kind="requirement")] == ["req-1"]
    g.close()


def test_add_edge_requires_both_nodes(tmp_path):
    g = _g(tmp_path)
    g.add_node("req-1", "requirement", "R")
    with pytest.raises(DanglingEdgeError):
        g.add_edge("req-1", "clm-missing", "implemented_by")
    with pytest.raises(DanglingEdgeError):
        g.add_edge("clm-missing", "req-1", "verifies")
    g.close()


def test_unknown_relation_rejected(tmp_path):
    g = _g(tmp_path)
    g.add_node("a", "claim", "A")
    g.add_node("b", "claim", "B")
    with pytest.raises(UnknownRelationError):
        g.add_edge("a", "b", "frobnicates")
    g.close()


def test_relation_kind_constraints_enforced(tmp_path):
    g = _g(tmp_path)
    g.add_node("req-1", "requirement", "R")
    g.add_node("reg-1", "regulation", "eCFR")
    g.add_node("tst-1", "test", "T")
    # regulated_by: requirement -> regulation  (ok)
    g.add_edge("req-1", "reg-1", "regulated_by")
    # regulated_by con origen 'test' -> inválido
    with pytest.raises(UnknownRelationError):
        g.add_edge("tst-1", "reg-1", "regulated_by")
    g.close()


def test_edge_id_deterministic_and_idempotent(tmp_path):
    g = _g(tmp_path)
    g.add_node("req-1", "requirement", "R")
    g.add_node("clm-1", "claim", "C")
    e1 = g.add_edge("req-1", "clm-1", "implemented_by", attrs={"via_ref": "UR3.3.1"})
    e2 = g.add_edge("req-1", "clm-1", "implemented_by", attrs={"via_ref": "OTRO"})
    assert e1 == e2 == _edge_id("req-1", "clm-1", "implemented_by")
    assert len(g.edges(rel="implemented_by")) == 1        # idempotente
    assert g.edges(rel="implemented_by")[0].attrs["via_ref"] == "OTRO"  # attrs actualizados
    g.close()


def test_neighbors_direction(tmp_path):
    g = _g(tmp_path)
    for nid, kind in [("req-1", "requirement"), ("clm-1", "claim"), ("tst-1", "test")]:
        g.add_node(nid, kind, nid)
    g.add_edge("req-1", "clm-1", "implemented_by")
    g.add_edge("tst-1", "req-1", "verifies")
    assert [n.node_id for n in g.neighbors("req-1", direction="out")] == ["clm-1"]
    assert [n.node_id for n in g.neighbors("req-1", direction="in")] == ["tst-1"]
    assert {n.node_id for n in g.neighbors("req-1", direction="both")} == {"clm-1", "tst-1"}
    assert g.neighbors("req-1", rel="verifies", direction="out") == []
    g.close()


def test_counts(tmp_path):
    g = _g(tmp_path)
    g.add_node("req-1", "requirement", "R")
    g.add_node("reg-1", "regulation", "eCFR")
    g.add_edge("req-1", "reg-1", "regulated_by")
    c = g.counts()
    assert c["nodes"] == 2 and c["edges"] == 1
    assert c["nodes_by_kind"]["requirement"] == 1
    assert c["edges_by_rel"]["regulated_by"] == 1
    g.close()
