"""H-3 — `finding_record_id` (modelo M2+M3, diseño
`DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829` §H-3).

M2: `finding_id` intacto; nuevo campo aditivo `finding_record_id` determinista y
    único por registro emitido.
M3: `finding_record_id` = clave de direccionamiento inequívoca (el caso QA40
    duplicado se resuelve).

Verifica:
  - finding_id UNCHANGED  (misma fórmula `_det_id`)
  - finding_record_id UNIQUE  (por corrida)
  - discriminante SEMÁNTICO estable (subcriterion_ref / requirement_id), SIN ordinal
  - findings_fingerprint UNCHANGED  (el campo no entra en la whitelist)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.findings import taxonomy as tx
from factory.regulatory.findings.taxonomy import (
    Finding, FindingProvenance, build_finding, as_dict, _det_id, _det_record_id,
)
from factory.regulatory.validation_v2 import run_fingerprint as rf


def _prov(subcriterion_ref=None):
    return FindingProvenance(document_id="RW-0005", extraction_version="canonical-v1-2026-08",
                             run_id="t", agent_id="regulatory_tier1",
                             subcriterion_ref=subcriterion_ref)


def _reg_finding(sc):
    """Dos sub-criterios del mismo requisito, mismo source_text -> mismo finding_id."""
    return build_finding(
        "RegulatoryFinding", "REGULATORY_INCONCLUSIVE", severity="MAJOR",
        document="RW-0005", page=40, source_text="runtime security restricts GUI access.",
        rationale="r", confidence="LOW", machine_state="MACHINE_INCONCLUSIVE",
        provenance=_prov(f"21_CFR_11.10(g)::{sc}"),
        requirement_id="21_CFR_11.10(g)",
    )


def test_finding_id_formula_is_unchanged():
    f = _reg_finding("sc1")
    assert f.finding_id == _det_id("RW-0005", "RegulatoryFinding",
                                   "REGULATORY_INCONCLUSIVE", 40,
                                   "runtime security restricts GUI access.")


def test_colliding_finding_ids_get_distinct_record_ids():
    a, b = _reg_finding("sc1"), _reg_finding("sc3")
    # el defecto G-1: mismo finding_id
    assert a.finding_id == b.finding_id
    # H-3: finding_record_id los distingue
    assert a.finding_record_id != b.finding_record_id
    assert a.finding_record_id.startswith("rec-")
    assert len(a.finding_record_id) == len("rec-") + 16


def test_record_id_is_deterministic_and_semantic_not_ordinal():
    # mismo (finding_id, subcriterion_ref, requirement_id) -> mismo record_id,
    # independientemente del orden de construcción
    first = _reg_finding("sc1").finding_record_id
    _noise = [_reg_finding("sc9") for _ in range(5)]   # emitidos "antes"
    again = _reg_finding("sc1").finding_record_id
    assert first == again
    assert first == _det_record_id(_reg_finding("sc1").finding_id,
                                   "21_CFR_11.10(g)::sc1", "21_CFR_11.10(g)")


def test_non_regulatory_findings_also_get_a_record_id():
    f = build_finding(
        "TestCoverageFinding", "REQUIREMENT_NOT_TESTED", severity="MAJOR",
        document="RW-0006", page=16, source_text="5.1.2 URS-PCS-SR-002 ...",
        rationale="r", confidence="MEDIUM", machine_state="MACHINE_DEVIATION_CANDIDATE",
        provenance=_prov(None),
    )
    assert f.finding_record_id.startswith("rec-")


def test_record_id_is_serialized_by_as_dict():
    d = as_dict(_reg_finding("sc1"))
    assert "finding_record_id" in d and d["finding_record_id"].startswith("rec-")
    assert "finding_id" in d


def test_findings_fingerprint_is_not_perturbed_by_record_id():
    """El fingerprint del pipeline NO puede moverse por añadir finding_record_id."""
    findings = [_reg_finding("sc1"), _reg_finding("sc3"),
                build_finding("TestCoverageFinding", "REQUIREMENT_NOT_TESTED",
                              severity="MAJOR", document="RW-0006", page=16,
                              source_text="x", rationale="r", confidence="MEDIUM",
                              machine_state="MACHINE_DEVIATION_CANDIDATE",
                              provenance=_prov(None))]
    fp_before = rf.findings_fingerprint(findings)

    # muta finding_record_id a mano en cada finding: el fingerprint no debe cambiar
    for i, f in enumerate(findings):
        f.finding_record_id = f"rec-manipulado-{i}"
    fp_after = rf.findings_fingerprint(findings)
    assert fp_before == fp_after

    # y finding_record_id NO está en la whitelist semántica
    assert "finding_record_id" not in rf._FINDING_SEMANTIC_FIELDS
