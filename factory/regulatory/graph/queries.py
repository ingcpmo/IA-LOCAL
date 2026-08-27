"""Consultas sobre el grafo (V2, B2) — determinista, sin LLM.

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B2:
`trace(requirement_id)`, `orphans(...)`, `contradictions(node_id)`.

Estas consultas son lo que habilita las clases FUNCTIONAL/TECHNICAL de
findings (FASE 7):
  - requirement sin `implemented_by`  -> REQUIREMENT_NOT_IMPLEMENTED
  - claim de FS sin requirement aguas arriba -> IMPLEMENTATION_WITHOUT_REQUIREMENT
  - requirement sin `test` transitivo -> REQUIREMENT_NOT_TESTED
  - test sin `verifies` -> TEST_WITHOUT_REQUIREMENT
  - arista `contradicts` -> CONTRADICTORY_FUNCTIONAL_BEHAVIOR
"""
from __future__ import annotations

from collections import deque

from factory.regulatory.graph.store import GraphStore, Node

# Aristas que forman la cadena de trazabilidad "hacia abajo".
_DOWNSTREAM = ("implemented_by", "designed_by", "tested_by")


def trace(g: GraphStore, requirement_id: str, *, max_depth: int = 8) -> dict:
    """Camino(s) desde un requirement: hacia arriba a su `regulation`, y
    hacia abajo por implemented_by -> designed_by -> tested_by hasta los
    `test`. Devuelve nodos alcanzados por tipo + si llega a un test.
    """
    root = g.get_node(requirement_id)
    if root is None or root.kind != "requirement":
        return {"requirement_id": requirement_id, "found": False}

    regulation = [n.node_id for n in g.neighbors(requirement_id, rel="regulated_by", direction="out")]

    reached: dict[str, list[str]] = {"claim": [], "section": [], "test": []}
    seen: set[str] = {requirement_id}
    dq: deque[tuple[str, int]] = deque([(requirement_id, 0)])
    while dq:
        nid, depth = dq.popleft()
        if depth >= max_depth:
            continue
        for rel in _DOWNSTREAM:
            for nb in g.neighbors(nid, rel=rel, direction="out"):
                if nb.node_id in seen:
                    continue
                seen.add(nb.node_id)
                if nb.kind in reached:
                    reached[nb.kind].append(nb.node_id)
                dq.append((nb.node_id, depth + 1))

    return {
        "requirement_id": requirement_id,
        "found": True,
        "label": root.label,
        "regulation": regulation,
        "reached": reached,
        "has_implementation": bool(reached["claim"] or reached["section"]),
        "has_test": bool(reached["test"]),
        "complete": bool(regulation) and bool(reached["claim"] or reached["section"]) and bool(reached["test"]),
    }


def requirements_not_implemented(g: GraphStore) -> list[Node]:
    """Requirements sin ninguna arista `implemented_by` saliente."""
    out = []
    for r in g.nodes(kind="requirement"):
        if not g.edges(src_id=r.node_id, rel="implemented_by"):
            out.append(r)
    return out


def requirements_not_tested(g: GraphStore) -> list[Node]:
    """Requirements que no alcanzan ningún `test` por la cadena
    downstream (implemented_by/designed_by/tested_by) ni por `verifies`
    entrante."""
    out = []
    for r in g.nodes(kind="requirement"):
        if g.edges(dst_id=r.node_id, rel="verifies"):
            continue
        if trace(g, r.node_id)["has_test"]:
            continue
        out.append(r)
    return out


def implementation_without_requirement(g: GraphStore, *, impl_document_ids: list[str] | None = None) -> list[Node]:
    """Claims (de documentos de implementación) sin ningún requirement
    aguas arriba: ni `implemented_by` entrante desde un requirement, ni
    cadena inversa hacia uno."""
    out = []
    for c in g.nodes(kind="claim"):
        if impl_document_ids and c.document_id not in impl_document_ids:
            continue
        if c.attrs.get("tipo") not in ("control", "function", "parameter"):
            continue
        if _has_upstream_requirement(g, c.node_id):
            continue
        out.append(c)
    return out


def _has_upstream_requirement(g: GraphStore, node_id: str, *, max_depth: int = 8) -> bool:
    seen = {node_id}
    dq = deque([(node_id, 0)])
    inbound = ("implemented_by", "designed_by")
    while dq:
        nid, depth = dq.popleft()
        if depth >= max_depth:
            continue
        for rel in inbound:
            for e in g.edges(dst_id=nid, rel=rel):
                src = g.get_node(e.src_id)
                if src is None:
                    continue
                if src.kind == "requirement":
                    return True
                if src.node_id not in seen:
                    seen.add(src.node_id)
                    dq.append((src.node_id, depth + 1))
    return False


def tests_without_requirement(g: GraphStore) -> list[Node]:
    """Tests sin ninguna arista `verifies` ni `tested_by` entrante."""
    out = []
    for t in g.nodes(kind="test"):
        if g.edges(src_id=t.node_id, rel="verifies"):
            continue
        if g.edges(dst_id=t.node_id, rel="tested_by"):
            continue
        out.append(t)
    return out


def contradictions(g: GraphStore, node_id: str | None = None) -> list[tuple[Node, Node, dict]]:
    """Aristas `contradicts` (todas, o las que tocan `node_id`)."""
    edges = g.edges(rel="contradicts")
    out = []
    for e in edges:
        if node_id and node_id not in (e.src_id, e.dst_id):
            continue
        a, b = g.get_node(e.src_id), g.get_node(e.dst_id)
        if a and b:
            out.append((a, b, e.attrs))
    return out


def coverage_summary(g: GraphStore) -> dict:
    reqs = g.nodes(kind="requirement")
    not_impl = requirements_not_implemented(g)
    not_tested = requirements_not_tested(g)
    return {
        "requirements_total": len(reqs),
        "not_implemented": [r.node_id for r in not_impl],
        "not_tested": [r.node_id for r in not_tested],
        "tests_without_requirement": [t.node_id for t in tests_without_requirement(g)],
        "contradictions": len(contradictions(g)),
    }
