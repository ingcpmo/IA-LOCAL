"""Corpus de INYECCIÓN DE DEFECTOS para medir FUNCTIONAL_RECALL (B8b, opción A).

docs_plan/DECISION_B8B_SUITE_B.md. El corpus real Rockwell tiene
trazabilidad completa -> no hay findings funcionales verdaderos que
detectar. Aquí se construye un proyecto sintético con defectos CONOCIDOS
y anclados, para medir cuántos detecta el analizador determinista (B6a).

Determinista, sin LLM, sin PDF, sin gobernanza. Construye `CanonicalStore`
directamente y devuelve la verdad-terreno (`GROUND_TRUTH`).
"""
from __future__ import annotations

from dataclasses import dataclass

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.graph import build as gb

PROJECT_ID = "DEFECT-B8B"
URS, FS, DS, SAT = "DB-URS", "DB-FS", "DB-DS", "DB-SAT"
_EXT_VER = "canonical-v1-2026-08"


@dataclass(frozen=True)
class ExpectedFinding:
    case_id: str
    subtype: str
    finding_class: str
    document_id: str
    anchor_substring: str        # debe aparecer en el source_text del finding


# Verdad-terreno: qué debería detectar el analizador y qué NO.
GROUND_TRUTH: list[ExpectedFinding] = [
    # 4 requisitos de la URS SIN implementación en el FS -> REQUIREMENT_NOT_TRACED
    ExpectedFinding("NI1", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-011"),
    ExpectedFinding("NI2", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-012"),
    ExpectedFinding("NI3", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-013"),
    ExpectedFinding("NI4", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-014"),
    # 4 requisitos implementados pero SIN prueba en el SAT -> REQUIREMENT_NOT_TESTED
    ExpectedFinding("NT1", "REQUIREMENT_NOT_TESTED", "TestCoverageFinding", URS, "UR-DB-005"),
    ExpectedFinding("NT2", "REQUIREMENT_NOT_TESTED", "TestCoverageFinding", URS, "UR-DB-006"),
    ExpectedFinding("NT3", "REQUIREMENT_NOT_TESTED", "TestCoverageFinding", URS, "UR-DB-007"),
    ExpectedFinding("NT4", "REQUIREMENT_NOT_TESTED", "TestCoverageFinding", URS, "UR-DB-008"),
    # 2 claims del FS sin requisito aguas arriba -> IMPLEMENTATION_WITHOUT_REQUIREMENT
    ExpectedFinding("IW1", "IMPLEMENTATION_WITHOUT_REQUIREMENT", "FunctionalFinding", FS, "FX-DB-101"),
    ExpectedFinding("IW2", "IMPLEMENTATION_WITHOUT_REQUIREMENT", "FunctionalFinding", FS, "FX-DB-102"),
    # 3 contradicciones cross-doc modal-opuesto sobre el mismo predicado
    ExpectedFinding("CT1", "CONTRADICTORY_FUNCTIONAL_BEHAVIOR", "FunctionalFinding", URS, "UR-DB-021"),
    ExpectedFinding("CT2", "CONTRADICTORY_FUNCTIONAL_BEHAVIOR", "FunctionalFinding", URS, "UR-DB-022"),
    ExpectedFinding("CT3", "CONTRADICTORY_FUNCTIONAL_BEHAVIOR", "FunctionalFinding", URS, "UR-DB-023"),
    # los 3 requisitos contradichos TAMPOCO tienen implementación -> además NOT_TRACED
    ExpectedFinding("CT1b", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-021"),
    ExpectedFinding("CT2b", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-022"),
    ExpectedFinding("CT3b", "REQUIREMENT_NOT_TRACED", "TraceabilityFinding", URS, "UR-DB-023"),
]
# 3 requisitos completamente trazados (URS->FS->SAT): el analizador NO debe
# emitir ningún finding para ellos.
NEGATIVE_REFS = ["UR-DB-001", "UR-DB-002", "UR-DB-003"]


def _c(store, did, page, text, tipo="control", local_id=None):
    store.put(m.build_claim(did, page, text, tipo,
                            m.sha256_text(text) and text[:180], local_id=local_id))


def build_defect_corpus(canon_dir, graph_dir):
    """Puebla los 4 CanonicalStore + el grafo. Devuelve los conteos del grafo."""
    with CanonicalStore(URS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=URS, sha256="u" * 64, tipo="URS", titulo="URS defect", n_paginas=30))
        # 3 fully-traced
        for i, ref in enumerate(NEGATIVE_REFS, start=1):
            _c(s, URS, i, f"{ref} The system shall record operation {i} with a timestamp and operator id.",
               local_id=ref)
        # 4 implementados pero no probados (005-008)
        for i in range(5, 9):
            _c(s, URS, i, f"UR-DB-{i:03d} The system shall enforce access control on subsystem {i}.",
               local_id=f"UR-DB-{i:03d}")
        # 4 sin implementación (011-014)
        for i in range(11, 15):
            _c(s, URS, i, f"UR-DB-{i:03d} The system shall provide an audit report export for module {i}.",
               local_id=f"UR-DB-{i:03d}")
        # 3 lados 'positivos' de contradicción (021-023)
        _c(s, URS, 21, "UR-DB-021 The operator shall have access to the alarm reset function from the OIT.",
           local_id="UR-DB-021")
        _c(s, URS, 22, "UR-DB-022 The system shall allow manual override of the interlock during maintenance.",
           local_id="UR-DB-022")
        _c(s, URS, 23, "UR-DB-023 Historical data shall be editable by the calibration engineer.",
           local_id="UR-DB-023")

    with CanonicalStore(FS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=FS, sha256="f" * 64, tipo="FS", titulo="FS defect", n_paginas=40))
        # implementa los 3 fully-traced + los 4 not-tested (005-008)
        for ref in NEGATIVE_REFS:
            _c(s, FS, 40, f"This function implements {ref}: records the operation with timestamp.",
               tipo="function")
        for i in range(5, 9):
            _c(s, FS, 41, f"This function implements UR-DB-{i:03d}: enforces access control on subsystem {i}.",
               tipo="function")
        # 2 claims sin requisito aguas arriba
        _c(s, FS, 50, "FX-DB-101 The HMI shall display a decorative company logo on the splash screen.",
           tipo="function", local_id="FX-DB-101")
        _c(s, FS, 51, "FX-DB-102 The system shall play a startup chime through the panel speaker.",
           tipo="function", local_id="FX-DB-102")

    with CanonicalStore(DS, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=DS, sha256="d" * 64, tipo="DS", titulo="DS defect", n_paginas=30))
        # 3 lados 'negativos' de contradicción (modal opuesto, mismo predicado)
        _c(s, DS, 12, "Regarding UR-DB-021, the operator shall not have access to the alarm reset "
                      "function from the OIT without a supervisor key.")
        _c(s, DS, 13, "For UR-DB-022, the system shall not allow manual override of the interlock "
                      "during maintenance under any circumstance.")
        _c(s, DS, 14, "Per UR-DB-023, historical data shall not be editable by the calibration "
                      "engineer once committed.")

    with CanonicalStore(SAT, store_dir=canon_dir) as s:
        s.put(m.Document(document_id=SAT, sha256="s" * 64, tipo="SAT", titulo="SAT defect", n_paginas=20))
        # prueba SOLO los 3 fully-traced (005-008 quedan sin test)
        for i, ref in enumerate(NEGATIVE_REFS, start=1):
            s.put(m.build_test(SAT, 5, f"SAT-DB-{i:03d}",
                               f"Test case SAT-DB-{i:03d}: verify {ref} records operation {i} with timestamp."))

    return gb.build_project_graph(
        PROJECT_ID,
        [(URS, "URS"), (FS, "FS"), (DS, "DS"), (SAT, "SAT")],
        canon_dir=canon_dir, graph_dir=graph_dir,
    )


def run_suite_b(canon_dir, graph_dir) -> dict:
    """Corre B6a sobre el corpus de defectos y mide FUNCTIONAL_RECALL /
    FUNCTIONAL_FALSE_POSITIVE contra GROUND_TRUTH. Determinista, sin LLM."""
    from factory.regulatory.findings.functional_findings import graph_functional_findings
    from factory.regulatory.validation_v2 import gates

    counts = build_defect_corpus(canon_dir, graph_dir)
    stats: dict = {}
    findings = graph_functional_findings(
        PROJECT_ID, [URS, FS, DS, SAT], extraction_version=_EXT_VER, run_id="suite-b",
        canon_dir=canon_dir, graph_dir=graph_dir, stats=stats)

    # match: un ExpectedFinding se considera detectado si hay un finding
    # con el mismo subtype y cuyo source_text contiene el anchor_substring.
    detected: dict[str, bool] = {}
    matched_finding_ids: set[str] = set()
    for exp in GROUND_TRUTH:
        hit = next((f for f in findings
                    if f.subtype == exp.subtype
                    and exp.anchor_substring in f.source_text
                    and f.finding_id not in matched_finding_ids), None)
        detected[exp.case_id] = hit is not None
        if hit:
            matched_finding_ids.add(hit.finding_id)

    # falsos positivos: findings emitidos que no casan con ningún expected
    # NI referencian un requisito completamente trazado (negativo).
    false_positives = []
    for f in findings:
        if f.finding_id in matched_finding_ids:
            continue
        # ¿toca un ref negativo (completamente trazado)? entonces es FP claro.
        false_positives.append({
            "subtype": f.subtype, "document": f.document, "page": f.page,
            "source_text": f.source_text[:140],
        })

    case_results = [{"case_id": e.case_id, "expected_finding": True,
                     "emitted_finding": detected[e.case_id], "subtype_match": detected[e.case_id]}
                    for e in GROUND_TRUTH]
    # casos negativos (fully-traced) -> nunca deben producir finding
    for ref in NEGATIVE_REFS:
        touched = any(ref in f.source_text for f in findings if f.finding_id in
                      {x.finding_id for x in findings} and ref in f.source_text)
        case_results.append({"case_id": f"NEG-{ref}", "expected_finding": False,
                             "emitted_finding": touched})
    # CADA finding no casado con un expected es un falso positivo contable
    for fp in false_positives:
        case_results.append({"case_id": f"FP-{fp['subtype']}-{fp['page']}",
                             "expected_finding": False, "emitted_finding": True})

    report = gates.evaluate_functional(case_results)
    n_expected = len(GROUND_TRUTH)
    n_detected = sum(detected.values())
    return {
        "graph_edges": counts["edges_by_rel"],
        "n_expected": n_expected,
        "n_detected": n_detected,
        "recall": round(n_detected / n_expected, 3),
        "by_case": detected,
        "false_positives": false_positives,
        "n_false_positives": len(false_positives),
        "gate_report": report.as_dict(),
        "stats": stats,
        "n_findings_total": len(findings),
    }
