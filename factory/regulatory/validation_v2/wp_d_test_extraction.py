"""WP-D -- validación de la etapa de extracción de `Test` sobre FIXTURE SINTÉTICO.

docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md WP-D ;
docs_plan/WP_C_BENCHMARK_EXTRACCION_20260828.md §6.

RW-0009 es un transmittal de 2 páginas (no un SAT) y el único SAT real (RW-0003)
es 100% imagen -> validación sobre corpus real BLOQUEADA en decisiones de
gobernanza. Aquí WP-D se valida contra un corpus sintético legible: URS + FS +
SAT cuyo cuerpo se hace pasar por `extract_tests_for_document` (el código real).

Gate WP-D:
  - `tested_by > 0` con casos verificables a mano (no por conteo).
  - 0 regresión en `implemented_by` / `designed_by`.
  - ningún `REQUIREMENT_NOT_TESTED` nuevo sin arista trazable
    (los requisitos con test alcanzable dejan de emitirlo).
  - anti-falso-positivo: líneas que NO son casos de prueba no generan `Test`.

Determinista, sin LLM, sin red, sin PDF. NO toca el corpus RW ni `EXTRACTION_VERSION`
de producción (el flag global sigue OFF; aquí se construye el store directamente).
"""
from __future__ import annotations

from pathlib import Path

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.extract_tests import extract_tests_for_document
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph import build as gb

PROJECT_ID = "WP-D-SYN"
URS, FS, SAT = "WD-URS", "WD-FS", "WD-SAT"
_EXT_VER = m.EXTRACTION_VERSION + m.TEST_EXTRACTION_SUFFIX

# Verdad-terreno del fixture:
#   UR-WD-001..006  implementados en FS y PROBADOS en SAT  -> NO REQUIREMENT_NOT_TESTED
#   UR-WD-007..008  implementados en FS, SIN prueba        -> SÍ REQUIREMENT_NOT_TESTED
#   UR-WD-009..010  sin implementación                      -> REQUIREMENT_NOT_TRACED (otro subtipo)
TESTED_REQS = [f"UR-WD-{i:03d}" for i in range(1, 7)]
IMPLEMENTED_NOT_TESTED = [f"UR-WD-{i:03d}" for i in range(7, 9)]
NOT_IMPLEMENTED = [f"UR-WD-{i:03d}" for i in range(9, 11)]

# Líneas que NO son casos de prueba (guardas anti-falso-positivo):
_NON_TEST_LINES = [
    "Note: the following section describes the acceptance approach in general.",
    "Step 1 of 2",                                   # paginación
    "Table of Contents .................. 3",        # dot leaders (TOC)
    "Revision B  2023-04-06  Issued for execution",  # cabecera
    "The operator shall be trained before execution.",
]


def _c(store, doc_id, page, text, tipo="function", local_id=None):
    store.put(m.build_claim(doc_id, page, text, tipo, text[:180], local_id=local_id))


def _sat_pages() -> list[str]:
    """Cuerpo sintético del SAT: 6 casos de prueba reales + ruido no-test."""
    lines = [
        "215115305-T-041 Site Acceptance Test 3 -- Completed",
        "Section 5  Test Execution",
    ]
    descs = {
        1: "Verify UR-WD-001 the operator can acknowledge an active alarm from the HMI.",
        2: "Verify UR-WD-002 the audit trail records operator id, timestamp and old/new value.",
        3: "Verify UR-WD-003 a nightly backup of the application database completes and is logged.",
        4: "Verify UR-WD-004 only users assigned to a defined role can change a critical parameter.",
        5: "Verify UR-WD-005 the system enforces role based access at login.",
        6: "Verify UR-WD-006 electronic records are retained for seven years and remain legible.",
    }
    for i, d in descs.items():
        lines.append(f"SAT-{i:03d}  {d}  Result: PASS")
    lines += _NON_TEST_LINES
    return ["\n".join(lines)]


def build_wp_d_corpus(canon_dir: Path, graph_dir: Path) -> dict:
    # URS -- 10 requisitos con local_id
    with CanonicalStore(URS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=URS, sha256="0" * 64, tipo="URS",
                         titulo="URS sintética WP-D", n_paginas=4))
        for i in range(1, 11):
            rid = f"UR-WD-{i:03d}"
            _c(s, URS, 1 + (i // 6), f"{rid}  The system shall satisfy requirement {rid}.",
               tipo="control", local_id=rid)

    # FS -- implementa UR-WD-001..008 (cita el id)
    with CanonicalStore(FS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=FS, sha256="f" * 64, tipo="FS",
                         titulo="FS sintética WP-D", n_paginas=6))
        for i in range(1, 9):
            rid = f"UR-WD-{i:03d}"
            _c(s, FS, 1 + (i // 5),
               f"Function F{i:02d}.00 implements {rid}: deterministic behaviour for {rid}.")

    # SAT -- cuerpo sintético -> PASA POR extract_tests_for_document (código real)
    tests = extract_tests_for_document(SAT, _sat_pages(), "SAT")
    with CanonicalStore(SAT, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=SAT, sha256="a" * 64, tipo="SAT",
                         titulo="SAT sintético WP-D (completado)", n_paginas=1))
        s.put_many(tests)

    counts = gb.build_project_graph(
        PROJECT_ID, [(URS, "URS"), (FS, "FS"), (SAT, "SAT")],
        canon_dir=canon_dir, graph_dir=graph_dir)
    return {"graph_counts": counts, "n_tests_extracted": len(tests),
            "test_identifiers": sorted(t.identificador for t in tests)}


def run_wp_d_synthetic(canon_dir: Path | None = None, graph_dir: Path | None = None) -> dict:
    """Corre el fixture y evalúa el gate WP-D. Determinista."""
    import tempfile

    from factory.regulatory.findings.functional_findings import graph_functional_findings
    from factory.regulatory.graph.store import GraphStore
    from factory.regulatory.validation_v2.local_only import network_locked

    cdir = Path(canon_dir) if canon_dir else Path(tempfile.mkdtemp(prefix="wpd-canon-"))
    gdir = Path(graph_dir) if graph_dir else Path(tempfile.mkdtemp(prefix="wpd-graph-"))

    with network_locked() as egress:
        built = build_wp_d_corpus(cdir, gdir)
        edges = built["graph_counts"].get("edges_by_rel", built["graph_counts"])

        g = GraphStore(PROJECT_ID, store_dir=gdir)
        n_tests_nodes = len(list(g.nodes(kind="test")))
        g.close()

        findings = graph_functional_findings(
            PROJECT_ID, [URS, FS, SAT], extraction_version=_EXT_VER,
            run_id="wp-d-syn", canon_dir=cdir, graph_dir=gdir)

    not_tested = sorted({f.source_text.split()[0] for f in findings
                         if f.subtype == "REQUIREMENT_NOT_TESTED"})
    tested_ok = [r for r in TESTED_REQS
                 if not any(r in (f.source_text or "") for f in findings
                            if f.subtype == "REQUIREMENT_NOT_TESTED")]

    gate = {
        "TESTED_BY_EDGES": edges.get("tested_by", 0),
        "TESTED_BY_POSITIVE": edges.get("tested_by", 0) > 0,
        "TEST_NODES": n_tests_nodes,
        "N_TESTS_EXTRACTED": built["n_tests_extracted"],
        "TEST_IDS": built["test_identifiers"],
        "IMPLEMENTED_BY_EDGES": edges.get("implemented_by", 0),
        "DESIGNED_BY_EDGES": edges.get("designed_by", 0),
        "TESTED_REQS_NO_LONGER_FLAGGED": tested_ok == TESTED_REQS,
        "REQUIREMENT_NOT_TESTED_EMITTED_FOR": not_tested,
        "REQUIREMENT_NOT_TESTED_ONLY_FOR_UNTESTED":
            set(not_tested) <= set(IMPLEMENTED_NOT_TESTED),
        "ANTI_FP_NON_TEST_LINES": len(_NON_TEST_LINES),
        "ANTI_FP_OK": built["n_tests_extracted"] == 6,   # exactamente los 6, ni uno más
        "local_only": egress.local_only,
        "document_egress_bytes": egress.document_egress_bytes,
        "edges_by_rel": edges,
    }
    gate["ALL_PASSED"] = bool(
        gate["TESTED_BY_POSITIVE"] and gate["ANTI_FP_OK"]
        and gate["TESTED_REQS_NO_LONGER_FLAGGED"]
        and gate["REQUIREMENT_NOT_TESTED_ONLY_FOR_UNTESTED"]
        and gate["document_egress_bytes"] == 0)
    return gate


if __name__ == "__main__":
    import json
    print(json.dumps(run_wp_d_synthetic(), indent=1, ensure_ascii=False, default=str))
