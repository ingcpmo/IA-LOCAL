"""Tests -- factory/regulatory/graph/build.py + queries.py (V2, B2).

docs_plan/PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md B2: poblado
determinista por coincidencia de referencias literales; trace() devuelve
el camino URS->FS->SAT; los huérfanos se detectan.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph import build as gb
from factory.regulatory.graph import queries as gq
from factory.regulatory.graph.store import GraphStore


def _seed_doc(canon_dir: Path, document_id: str, tipo: str, claims: list[tuple[int, str, str]],
              tests: list[tuple[str, str]] | None = None) -> None:
    with CanonicalStore(document_id, store_dir=canon_dir) as store:
        store.put(m.Document(document_id=document_id, sha256="x" * 64, tipo=tipo,
                             titulo=f"{tipo} doc", n_paginas=20))
        for pagina, tipo_claim, text in claims:
            store.put(m.build_claim(document_id, pagina, text, tipo_claim, text))
        for ident, desc in (tests or []):
            store.put(m.build_test(document_id, 5, ident, desc))


def test_ref_extraction():
    refs = gb.extract_refs("This implements UR3.3.1 and F12.00 per 21 CFR 11.10(e).")
    assert "UR3.3.1" in refs
    assert "F12.00" in refs
    assert "21CFR11.10(E)" in refs


def test_build_links_urs_fs_sat_by_shared_ref(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"

    _seed_doc(canon_dir, "RW-URS", "URS", [
        (7, "control", "UR3.3.1 The system shall generate an audit trail record for every "
                       "change to a critical alarm threshold, per 21 CFR 11.10(e)."),
        (8, "control", "UR9.9.9 An unrelated user requirement with no downstream link."),
    ])
    _seed_doc(canon_dir, "RW-FS", "FS", [
        (41, "function", "This function implements UR3.3.1: the audit trail record includes "
                         "operator identity, date, time, previous value and new value."),
    ])
    _seed_doc(canon_dir, "RW-SAT", "SAT", [], tests=[
        ("SAT-039", "Test case SAT-039: verify UR3.3.1 - audit trail record is written on "
                    "alarm threshold change with operator identity and timestamp."),
    ])

    counts = gb.build_project_graph(
        "PRJ-T", [("RW-URS", "URS"), ("RW-FS", "FS"), ("RW-SAT", "SAT")],
        canon_dir=canon_dir, graph_dir=graph_dir,
    )
    assert counts["nodes_by_kind"].get("requirement", 0) >= 1
    assert counts["edges_by_rel"].get("implemented_by", 0) >= 1

    g = GraphStore("PRJ-T", store_dir=graph_dir)
    tr = gq.trace(g, "21_CFR_11.10(e)")
    assert tr["found"] is True
    assert tr["regulation"] == ["ecfr_21cfr_part11"]
    assert tr["has_implementation"] is True
    assert tr["has_test"] is True
    assert tr["complete"] is True
    g.close()


def test_orphan_requirement_detected(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    # FS que solo implementa 11.10(e); el resto del catálogo queda huérfano.
    _seed_doc(canon_dir, "RW-URS", "URS", [
        (7, "control", "UR3.3.1 audit trail per 21 CFR 11.10(e)."),
    ])
    _seed_doc(canon_dir, "RW-FS", "FS", [
        (41, "function", "Implements UR3.3.1 audit trail record with timestamp."),
    ])
    gb.build_project_graph("PRJ-O", [("RW-URS", "URS"), ("RW-FS", "FS")],
                           canon_dir=canon_dir, graph_dir=graph_dir)
    g = GraphStore("PRJ-O", store_dir=graph_dir)
    not_impl = {r.node_id for r in gq.requirements_not_implemented(g)}
    # 20 requisitos en el catálogo; solo 11.10(e) linkeado.
    assert "21_CFR_11.10(e)" not in not_impl
    assert "21_CFR_11.10(a)" in not_impl
    summ = gq.coverage_summary(g)
    assert summ["requirements_total"] == 20
    assert "21_CFR_11.10(a)" in summ["not_tested"]
    g.close()


def test_contradiction_heuristic_modal_opposite(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    _seed_doc(canon_dir, "RW-FS", "FS", [
        (10, "control", "For F09.00 the operator shall have access to the alarm reset function."),
    ])
    _seed_doc(canon_dir, "RW-DS", "DS", [
        (12, "control", "Regarding F09.00, the operator shall not have access to the alarm "
                        "reset function without supervisor override."),
    ])
    gb.build_project_graph("PRJ-C", [("RW-FS", "FS"), ("RW-DS", "DS")],
                           canon_dir=canon_dir, graph_dir=graph_dir)
    g = GraphStore("PRJ-C", store_dir=graph_dir)
    contras = gq.contradictions(g)
    assert len(contras) == 1
    assert contras[0][2]["via_ref"] == "F09.00"
    g.close()


def test_build_is_idempotent(tmp_path):
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    _seed_doc(canon_dir, "RW-URS", "URS", [(7, "control", "UR3.3.1 audit trail 21 CFR 11.10(e).")])
    _seed_doc(canon_dir, "RW-FS", "FS", [(41, "function", "Implements UR3.3.1 audit trail.")])
    c1 = gb.build_project_graph("PRJ-I", [("RW-URS", "URS"), ("RW-FS", "FS")],
                                canon_dir=canon_dir, graph_dir=graph_dir)
    c2 = gb.build_project_graph("PRJ-I", [("RW-URS", "URS"), ("RW-FS", "FS")],
                                canon_dir=canon_dir, graph_dir=graph_dir)
    assert c1 == c2


def test_real_rockwell_corpus_if_available(tmp_path):
    """Pipeline B1->B2 completo sobre el corpus real, si está disponible.
    Skippea limpio si no (mismo patrón que test_r2_retrieval)."""
    from factory.regulatory.canonical.extract_document import extract_document
    bases = [Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell"),
             Path("/home/ing_cpmo/GMPAI/source/Rockwell")]
    base = next((b for b in bases if b.exists()), None)
    if base is None:
        pytest.skip("corpus real Rockwell no disponible")
    jobs = [
        ("RW-URS", "URS", "215115305 SCADA-PCS Misc PLC System URS v2.1.pdf"),
        ("RW-0005", "FS", "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"),
        ("RW-SAT", "SAT", "215115305-T-041 SAT3 Completed.pdf"),
    ]
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    docs = []
    for did, tipo, fn in jobs:
        p = base / fn
        if not p.exists():
            continue
        extract_document(p, did, tipo=tipo, store_dir=canon_dir)
        docs.append((did, tipo))
    if len(docs) < 2:
        pytest.skip("faltan PDFs del corpus para la prueba de grafo")

    counts = gb.build_project_graph("PRJ-RW", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    assert counts["nodes_by_kind"].get("requirement", 0) == 20
    assert counts["nodes_by_kind"].get("claim", 0) > 0
    # No exigimos un número mínimo de links cross-doc (la extracción B1 es
    # heurística), pero el grafo debe construirse sin error y ser consultable.
    g = GraphStore("PRJ-RW", store_dir=graph_dir)
    summ = gq.coverage_summary(g)
    assert summ["requirements_total"] == 20
    assert isinstance(summ["not_implemented"], list)
    g.close()


def test_b12_links_urs_continuation_line_by_local_id(tmp_path):
    """B1.2: un claim de la URS SIN número en su texto (continuación de
    línea) se linkea al FS por el local_id heredado."""
    from factory.regulatory.canonical.persistence import CanonicalStore
    from factory.regulatory.canonical import model as m
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    with CanonicalStore("RW-URS", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-URS", sha256="x" * 64, tipo="URS", titulo="URS", n_paginas=20))
        # dos claims: el 2º sin número propio, hereda "5.2.22"
        s.put(m.build_claim("RW-URS", 8, "5.2.22 URS-PCS-SR-028 Alarms shall be stored one year.",
                            "control", "alarms stored", local_id="5.2.22"))
        s.put(m.build_claim("RW-URS", 8, "A historical archive shall retain the records.",
                            "control", "historical archive", local_id="5.2.22"))
    with CanonicalStore("RW-FS", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-FS", sha256="y" * 64, tipo="FS", titulo="FS", n_paginas=40))
        # el FS cita el número jerárquico (patrón real: FS usa UR5.2.22 / 5.2.22)
        s.put(m.build_claim("RW-FS", 30, "This function implements UR5.2.22: alarm storage and archiving.",
                            "function", "implements alarm storage"))
    docs = [("RW-URS", "URS"), ("RW-FS", "FS")]
    gb.build_project_graph("PRJ-B12L", docs, canon_dir=canon_dir, graph_dir=graph_dir)
    g = GraphStore("PRJ-B12L", store_dir=graph_dir)
    impl = g.edges(rel="implemented_by")
    # el FS claim debe quedar aguas abajo de AMBOS claims URS: el que trae
    # "5.2.22" en el texto Y la continuación de línea, que lo hereda por local_id.
    assert len(impl) >= 2
    g.close()
