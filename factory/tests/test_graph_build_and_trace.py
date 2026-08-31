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


def test_h10_refers_to_by_literal_entity_mention(tmp_path):
    """H-10: `claim --refers_to--> system_component|actor` cuando el nombre/rol
    literal de la entidad aparece en el texto citable del claim. Guardas
    anti-falso-positivo: nombre genérico ('System') NO crea arista; sin
    entidad no pasa nada."""
    from factory.regulatory.canonical import model as m
    from factory.regulatory.canonical.persistence import CanonicalStore
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    with CanonicalStore("RW-DS", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-DS", sha256="d" * 64, tipo="DS",
                         titulo="DS", n_paginas=10))
        s.put(m.build_claim("RW-DS", 3,
                            "The Historian Server FR-HS-01 shall archive alarms hourly.",
                            "function", "historian archives alarms"))
        s.put(m.build_claim("RW-DS", 4,
                            "The Maintenance Technician acknowledges the alarm at the panel.",
                            "actor_action", "technician acks alarm"))
        s.put(m.build_claim("RW-DS", 5,
                            "The system shall be available 99.9% of the time.",
                            "statement", "availability target"))
        s.put(m.SystemComponent(component_id="cmp-hist", document_id="RW-DS",
                                nombre="Historian Server FR-HS-01", tipo="Historian"))
        s.put(m.SystemComponent(component_id="cmp-generic", document_id="RW-DS",
                                nombre="System", tipo="other"))
        s.put(m.Actor(actor_id="act-tech", document_id="RW-DS",
                      nombre_rol="Maintenance Technician", tipo="role"))
    gb.build_project_graph("PRJ-H10R", [("RW-DS", "DS")],
                           canon_dir=canon_dir, graph_dir=graph_dir)
    g = GraphStore("PRJ-H10R", store_dir=graph_dir)
    refs = g.edges(rel="refers_to")
    dsts = {e.dst_id for e in refs}
    assert "cmp-hist" in dsts          # nombre compuesto y distintivo -> arista
    assert "act-tech" in dsts          # rol literal -> arista
    assert "cmp-generic" not in dsts   # 'System' es genérico -> SIN arista
    # todas las aristas parten de un claim real
    srcs = {e.src_id for e in refs}
    assert srcs and all(s.startswith("clm-") for s in srcs)
    g.close()


def test_h10_refers_to_specificity_resolution(tmp_path):
    """H-10 fix (2026-08-31, tras revisión humana E1 = 30/77 WRONG_NODE):
    cuando el diccionario tiene un término que es subcadena de otro
    ('FactoryTalk' ⊂ 'FactoryTalk Historian'; 'CP01' ⊂ 'PCS-CP01') y el claim
    menciona la forma LARGA, sólo se enlaza la entidad más específica -- la
    genérica dominada NO recibe arista. Una mención genérica AUTÓNOMA (sin
    forma larga que la contenga) sí se enlaza."""
    from factory.regulatory.canonical import model as m
    from factory.regulatory.canonical.persistence import CanonicalStore
    canon_dir = tmp_path / "canon"
    graph_dir = tmp_path / "graph"
    with CanonicalStore("RW-SP", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-SP", sha256="e" * 64, tipo="DS",
                         titulo="DS", n_paginas=10))
        # claim con la forma LARGA -> sólo la específica
        s.put(m.build_claim("RW-SP", 3,
                            "Alarms are archived by the FactoryTalk Historian SE server on PCS-CP01.",
                            "function", "historian archives on cp"))
        # claim con la forma GENÉRICA autónoma -> sí enlaza la genérica
        s.put(m.build_claim("RW-SP", 4,
                            "The FactoryTalk platform provides the licensing framework.",
                            "statement", "factorytalk licensing"))
        s.put(m.SystemComponent(component_id="cmp-ft", document_id="RW-SP",
                                nombre="FactoryTalk", tipo="SCADA"))
        s.put(m.SystemComponent(component_id="cmp-fth", document_id="RW-SP",
                                nombre="FactoryTalk Historian", tipo="Historian"))
        s.put(m.SystemComponent(component_id="cmp-cp01", document_id="RW-SP",
                                nombre="CP01", tipo="PLC"))
        s.put(m.SystemComponent(component_id="cmp-pcscp01", document_id="RW-SP",
                                nombre="PCS-CP01", tipo="PLC"))
    gb.build_project_graph("PRJ-SP", [("RW-SP", "DS")],
                           canon_dir=canon_dir, graph_dir=graph_dir)
    g = GraphStore("PRJ-SP", store_dir=graph_dir)
    pairs = {(e.src_id, e.dst_id) for e in g.edges(rel="refers_to")}
    dsts_by_src = {}
    for s_, d_ in pairs:
        dsts_by_src.setdefault(s_, set()).add(d_)
    # el claim de la forma larga: enlaza Historian y PCS-CP01, NO 'FactoryTalk' ni 'CP01'
    largo = [s_ for s_ in dsts_by_src if "cmp-fth" in dsts_by_src[s_]]
    assert largo, "no se creó la arista a la entidad específica"
    d = dsts_by_src[largo[0]]
    assert "cmp-fth" in d and "cmp-pcscp01" in d
    assert "cmp-ft" not in d, "'FactoryTalk' genérico dominado NO debe enlazarse"
    assert "cmp-cp01" not in d, "'CP01' genérico dominado NO debe enlazarse"
    # la mención genérica autónoma SÍ enlaza 'FactoryTalk'
    assert any("cmp-ft" in dd for s_, dd in dsts_by_src.items() if s_ != largo[0])
    g.close()


def test_h10_rc3_tested_by_requires_semantic_anchoring():
    """H-10 fix RC-3 (tras revisión humana E1-2: 10/17 tested_by eran ruido).
    Una coincidencia de token de referencia corta ('3.2.3') NO basta:
      - un claim que lidera con OTRO id y sólo cita '[MCCPDC 3.2.3]' -> NO enlaza
      - un claim que ES el requisito 3.2.3, o comparte tema con el Test -> SÍ enlaza
    Preserva los enlaces válidos de UR3.2.3."""
    from factory.regulatory.graph.build import _tested_by_anchored
    test_desc = ("UR3.2.3 The Equipment shall have critical alarms and warnings as "
                 "listed in Table 1 - List of Critical-to-Quality Alarms.")
    # cross-reference -> DROP
    assert not _tested_by_anchored(
        "UR4.1.1 [MCCPDC 3.2.3] - The physical servers shall be two redundant appliances.",
        test_desc, "3.2.3")
    assert not _tested_by_anchored("specification (See 3.1.9, F05.05:", test_desc, "F05.05")
    assert not _tested_by_anchored(
        "UR4.1.1 requirement includes in its text the customer reference number MCCPDC 3.2.3.",
        test_desc, "3.2.3")
    # sin anclaje semántico -> DROP
    assert not _tested_by_anchored("included in the Functional Specification document.",
                                   test_desc, "3.2.3")
    # el claim ES el requisito -> KEEP
    assert _tested_by_anchored("3.2.3 The Equipment shall have critical alarms and warnings.",
                               test_desc, "3.2.3")
    assert _tested_by_anchored("UR3.2.3 The Equipment shall have critical alarms.",
                               test_desc, "3.2.3")
    # comparte tema con el Test -> KEEP
    assert _tested_by_anchored("The list of critical alarms in the table is complete.",
                               test_desc, "3.2.3")
    # tag de ref al final -> KEEP
    assert _tested_by_anchored("screen, accessible by Admin and Maintenance personnel.-F05.05, 24",
                               "F05.05: Input State and Simulation Review Screen", "F05.05")
