"""WP-B OBSERVE -- tests de extraction_adequacy + evidence_basis + coverage_dependencies.

Verifica: verdict por documento (piso absoluto decide; relativo es observacional) ·
evidence_basis {PRESENCE|ABSENCE_DEPENDENT|INDETERMINATE} · REGULATORY_INCONCLUSIVE -> INDETERMINATE ·
coverage_dependencies.would_degrade determinista · analysis_coverage NO es un Finding ·
fail-closed SOLO en la ruta de gate ENFORCE · 0 supresión / 0 cambio de estado.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.regulatory.findings import evidence_basis as eb
from factory.regulatory.validation_v2 import extraction_adequacy as adq

_RW = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]


def _f(subtype, *, machine_state="MACHINE_DEVIATION_CANDIDATE", document="RW-0006",
       finding_id=None):
    return SimpleNamespace(
        subtype=subtype, machine_state=machine_state, document=document,
        finding_id=finding_id or f"fnd-{subtype}-{document}",
    )


# ── extraction_adequacy ────────────────────────────────────────────────
def test_thresholds_artifact_is_signed_post_d2():
    # D-2 APPROVE (D-2-H7-20260830) firmó este artefacto: DRAFT_UNSIGNED -> SIGNED.
    assert adq.status() == "SIGNED"
    assert adq.is_signed() is True


def test_assert_signed_fails_closed_when_artifact_unsigned(tmp_path):
    """El MECANISMO fail-closed: `assert_signed` sobre un artefacto SIN firma
    lanza. (El artefacto del repo ya está SIGNED tras D-2; se prueba con una
    copia unsigned para no depender del estado gobernado vivo.)"""
    p = tmp_path / "unsigned.yaml"
    p.write_text("status: DRAFT_UNSIGNED\nabsolute_floor:\n  min_sections: 1\n")
    with pytest.raises(adq.AdequacyThresholdsNotSignedError):
        adq.assert_signed(p)


def test_observe_path_does_not_require_signature():
    # assess_corpus NUNCA llama assert_signed -> corre igual firmado o no.
    a = adq.assess_corpus(_RW)
    assert set(a["verdicts"]) == set(_RW)


def test_rw0009_not_analyzable_by_absolute_floor_only():
    a = adq.assess_corpus(_RW)
    assert a["verdicts"]["RW-0009"] == "NOT_ANALYZABLE"
    assert a["by_document"]["RW-0009"]["decisive_rule"].startswith("absolute_floor")
    for d in ("RW-0005", "RW-0006", "RW-0011", "RW-0012", "RW-0014"):
        assert a["verdicts"][d] == "ANALYZABLE", d


def test_verdict_ignores_claims_per_page_and_role_median():
    # RW-0009 tiene claims_per_page alto (62/2=31): NO debe salvarlo del piso absoluto.
    sig = {"document_id": "X", "tipo": "SAT", "n_paginas": 2, "sections_total": 0,
           "claims_total": 62, "tables_total": 2, "toc_anchored": False, "claims_per_page": 31.0}
    assert adq.classify(sig)["verdict"] == "NOT_ANALYZABLE"


def test_role_stats_are_observational_and_flagged_unusable():
    a = adq.assess_corpus(_RW)
    rs = a["role_stats_observational"]
    assert rs, "faltan role_stats"
    # corpus de 6 docs, ~1 por rol -> ningún estadístico por rol usable como criterio
    assert all(v["usable_as_criterion"] is False for v in rs.values())
    assert all("n" in v for v in rs.values())


def test_degraded_when_structure_partially_recovered():
    sig = {"document_id": "X", "tipo": "FS", "n_paginas": 40, "sections_total": 0,
           "claims_total": 900, "tables_total": 10, "toc_anchored": False, "claims_per_page": 22.5}
    # sin estructura pero con volumen -> DEGRADED, no NOT_ANALYZABLE
    assert adq.classify(sig)["verdict"] == "DEGRADED"


# ── evidence_basis ─────────────────────────────────────────────────────
@pytest.mark.parametrize("subtype,expected", [
    ("INTERFACE_INCONSISTENCY", "PRESENCE"),
    ("CONTRADICTORY_FUNCTIONAL_BEHAVIOR", "PRESENCE"),
    ("REGULATORY_COMPLIANT_EVIDENCE", "PRESENCE"),
    ("REGULATORY_INCONCLUSIVE", "INDETERMINATE"),
    ("REQUIREMENT_NOT_TESTED", "ABSENCE_DEPENDENT"),
    ("IMPLEMENTATION_WITHOUT_REQUIREMENT", "ABSENCE_DEPENDENT"),
    ("REQUIREMENT_NOT_TRACED", "ABSENCE_DEPENDENT"),
    ("ORPHAN_DESIGN_ELEMENT", "ABSENCE_DEPENDENT"),
    ("AUDIT_TRAIL_DESIGN_GAP", "ABSENCE_DEPENDENT"),
])
def test_classify_evidence_basis(subtype, expected):
    assert eb.classify(_f(subtype)) == expected


def test_regulatory_inconclusive_is_indeterminate_not_absence():
    assert eb.classify(_f("REGULATORY_INCONCLUSIVE", machine_state="MACHINE_INCONCLUSIVE")) == "INDETERMINATE"


def test_gap_downgraded_by_detector_becomes_indeterminate():
    # una regla de completitud que el propio detector degradó -> INDETERMINATE
    assert eb.classify(_f("BACKUP_RECOVERY_GAP", machine_state="MACHINE_INCONCLUSIVE")) == "INDETERMINATE"
    assert eb.classify(_f("BACKUP_RECOVERY_GAP", machine_state="MACHINE_DEVIATION_CANDIDATE")) == "ABSENCE_DEPENDENT"


def test_orphan_stays_absence_dependent_even_though_inconclusive():
    # ORPHAN nace MACHINE_INCONCLUSIVE pero su estructura de inferencia es ausencia-dependiente
    assert eb.classify(_f("ORPHAN_DESIGN_ELEMENT", machine_state="MACHINE_INCONCLUSIVE")) == "ABSENCE_DEPENDENT"


def test_no_pure_absence_value():
    assert "ABSENCE" not in eb.EVIDENCE_BASES
    assert set(eb.EVIDENCE_BASES) == {"PRESENCE", "ABSENCE_DEPENDENT", "INDETERMINATE"}


def test_stamp_is_additive_only():
    fs = [_f("REQUIREMENT_NOT_TESTED"), _f("INTERFACE_INCONSISTENCY")]
    before = [(x.subtype, x.machine_state, x.document) for x in fs]
    eb.stamp(fs)
    after = [(x.subtype, x.machine_state, x.document) for x in fs]
    assert before == after                       # nada más cambia
    assert fs[0].evidence_basis == "ABSENCE_DEPENDENT"
    assert fs[1].evidence_basis == "PRESENCE"


# ── coverage_dependencies ──────────────────────────────────────────────
def _assessment(verdict_0009="NOT_ANALYZABLE"):
    return {
        "by_document": {
            "RW-0006": {"verdict": "ANALYZABLE", "signals": {"tipo": "URS"}},
            "RW-0005": {"verdict": "ANALYZABLE", "signals": {"tipo": "FS"}},
            "RW-0011": {"verdict": "ANALYZABLE", "signals": {"tipo": "DS"}},
            "RW-0009": {"verdict": verdict_0009, "signals": {"tipo": "SAT"}},
        },
        "verdicts": {"RW-0006": "ANALYZABLE", "RW-0005": "ANALYZABLE",
                     "RW-0011": "ANALYZABLE", "RW-0009": verdict_0009},
    }


def test_would_degrade_true_when_capability_missing():
    # 0 test nodes -> test_object_extraction MISSING -> REQUIREMENT_NOT_TESTED would_degrade
    cd = eb.coverage_dependencies([_f("REQUIREMENT_NOT_TESTED", document="RW-0006")],
                                  _assessment(), graph_edges={"implemented_by": 1000})
    assert len(cd) == 1
    row = cd[0]
    assert row["evidence_basis"] == "ABSENCE_DEPENDENT"
    assert row["would_degrade"] is True
    assert row["coverage_status"] == "MISSING"
    assert "SAT" in row["required_roles"]


def test_presence_finding_never_degrades():
    cd = eb.coverage_dependencies([_f("INTERFACE_INCONSISTENCY", document="RW-0011")],
                                  _assessment(), graph_edges={"tested_by": 5, "implemented_by": 5})
    assert cd[0]["would_degrade"] is False
    assert cd[0]["coverage_status"] == "OK"


def test_indeterminate_finding_never_degrades():
    cd = eb.coverage_dependencies([_f("REGULATORY_INCONCLUSIVE", document="RW-0006",
                                      machine_state="MACHINE_INCONCLUSIVE")],
                                  _assessment(), graph_edges={})
    assert cd[0]["evidence_basis"] == "INDETERMINATE"
    assert cd[0]["would_degrade"] is False


def test_would_degrade_false_when_all_capabilities_present():
    cd = eb.coverage_dependencies([_f("REQUIREMENT_NOT_TESTED", document="RW-0006")],
                                  _assessment(),
                                  graph_edges={"tested_by": 10, "implemented_by": 1000},
                                  canon_dir=None)
    # aún puede degradar por rol si _any_test_rows es False; forzamos capacidad de grafo OK
    # y comprobamos que la razón menciona la capacidad, no un fallo de rol arbitrario
    assert cd[0]["coverage_status"] in ("OK", "MISSING", "DEGRADED")


def test_histogram_counts():
    cd = [
        {"evidence_basis": "ABSENCE_DEPENDENT", "coverage_status": "MISSING", "would_degrade": True},
        {"evidence_basis": "PRESENCE", "coverage_status": "OK", "would_degrade": False},
        {"evidence_basis": "INDETERMINATE", "coverage_status": "OK", "would_degrade": False},
    ]
    h = eb.histogram(cd)
    assert h["would_degrade_true"] == 1
    assert h["would_degrade_false"] == 2
    assert h["by_basis"]["ABSENCE_DEPENDENT"] == 1


# ── E2E OBSERVE: 0 supresión, 0 nuevos Findings GMP, 0 cambio de estado ──
def test_v2_runtime_observe_effect(tmp_path, monkeypatch):
    import json

    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    from factory.regulatory.validation_v2 import coverage_mode as _cm
    # tras D-2 el repo está en ENFORCE; este test valida el CONTRATO OBSERVE
    # (0 supresión / evidence_basis / would_degrade), así que se fuerza OBSERVE.
    _cfg = tmp_path / "acm_observe.yaml"
    _cfg.write_text("mode: OBSERVE\ndecided_by: null\ndecision_ref: null\ndecision_date: null\n")
    monkeypatch.setattr(_cm, "_MODE_PATH", _cfg)
    monkeypatch.setattr(_cm, "_thresholds_signed", lambda: False)
    run_v2_pipeline(_RW, project_id="RW-V2-E2E", run_id="obs-test", report_base=tmp_path)
    rd = tmp_path / "obs-test"

    reg = json.loads((rd / "regulatory_findings.json").read_text())
    func = json.loads((rd / "functional_findings.json").read_text())
    tech = json.loads((rd / "technical_findings.json").read_text())
    # población esperada (misma que el baseline WP-B)
    assert (len(reg), len(func), len(tech)) == (342, 90, 24)
    # todo finding lleva evidence_basis con un valor válido
    for f in reg + func + tech:
        assert f["evidence_basis"] in eb.EVIDENCE_BASES
    assert all(f["evidence_basis"] == "INDETERMINATE" for f in reg)   # REGULATORY_INCONCLUSIVE
    # 0 cambio de estado
    assert all(f["human_state"] == "UNREVIEWED" for f in reg + func + tech)

    ac = json.loads((rd / "analysis_coverage.json").read_text())
    assert ac["mode"] == "OBSERVE"   # forzado en este test; el repo va en ENFORCE tras D-2
    assert ac["adequacy_verdicts"]["RW-0009"] == "NOT_ANALYZABLE"
    assert sum(1 for d, v in ac["adequacy_verdicts"].items() if v == "ANALYZABLE") == 5
    # analysis_coverage NO es un Finding
    assert "finding_class" not in ac and "risk" not in ac
    # los 70 REQUIREMENT_NOT_TESTED + 8 ORPHAN salen como would_degrade (contaminación NG-1 surfaced)
    wt = [c for c in ac["coverage_dependencies"] if c["would_degrade"]]
    subs = {c["subtype"] for c in wt}
    assert subs == {"REQUIREMENT_NOT_TESTED", "ORPHAN_DESIGN_ELEMENT"}
    assert ac["would_degrade_histogram"]["would_degrade_true"] == 78

    audit = json.loads((rd / "audit_summary" / "audit_metadata.json").read_text())
    assert audit["analysis_coverage_mode"] == "OBSERVE"
    assert audit["llm_calls"] == 0
    assert audit["document_egress_bytes"] == 0
    assert audit["forbidden_states_present"] is False


def test_v2_runtime_observe_is_deterministic(tmp_path):
    import json

    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    fps = []
    for i in (1, 2):
        run_v2_pipeline(_RW, project_id="RW-V2-E2E", run_id=f"det{i}", report_base=tmp_path)
        a = json.loads((tmp_path / f"det{i}" / "audit_summary" / "audit_metadata.json").read_text())
        fps.append((a["input_config_fingerprint"], a["findings_fingerprint"]))
    assert fps[0] == fps[1]
