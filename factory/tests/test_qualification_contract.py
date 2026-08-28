"""WP-F -- contrato de cualificación: reglas duras + checker re-ejecutable.

Verifica: loader fail-closed (literal expected_value prohibido, self-qualify prohibido,
triggers obligatorios) · resolución de valor esperado desde fuente CITADA (const / zero /
assertion) · el checker re-ejecuta las suites y produce found/expected/delta · el
fingerprint (WP-A) se compara · disparadores de requalification por SHA · el sistema
NUNCA se auto-cualifica ni declara cumplimiento.
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest
import yaml

from factory.regulatory.validation_v2 import qualification_contract as qc


def _tmp_contract(mutate) -> pathlib.Path:
    d = qc.load_contract()
    mutate(d)
    p = pathlib.Path(tempfile.mktemp(suffix=".yaml"))
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    return p


# ── reglas duras del loader ────────────────────────────────────────────
def test_contract_loads_and_is_draft():
    d = qc.load_contract()
    assert d["status"] == "DRAFT"
    assert d["qualified_version"] is None
    assert d["system_never_self_qualifies"] is True
    assert d["requalification_triggers"]


def test_literal_expected_value_is_rejected():
    p = _tmp_contract(lambda d: d["qualification_cases"][0].__setitem__("expected_value", 0.9))
    with pytest.raises(qc.QualificationContractError):
        qc.load_contract(p)


def test_missing_self_qualify_flag_is_rejected():
    p = _tmp_contract(lambda d: d.__setitem__("system_never_self_qualifies", False))
    with pytest.raises(qc.QualificationContractError):
        qc.load_contract(p)


def test_missing_requalification_triggers_is_rejected():
    p = _tmp_contract(lambda d: d.__setitem__("requalification_triggers", {}))
    with pytest.raises(qc.QualificationContractError):
        qc.load_contract(p)


def test_every_case_cites_an_authorized_source():
    for c in qc.load_contract()["qualification_cases"]:
        src = c["expected_value_source"]
        assert isinstance(src, dict)
        assert ("const_module" in src and "const" in src) or src.get("zero") is True \
            or "assertion" in src or ("yaml" in src and "key" in src)
        if src.get("zero") is True or "assertion" in src:
            assert src.get("authority")


# ── resolución de la fuente autorizada ─────────────────────────────────
def test_resolve_expected_from_gates_const():
    v, cite = qc.resolve_expected(
        {"const_module": "factory.regulatory.validation_v2.gates", "const": "TECHNICAL_RECALL_MIN"})
    assert v == 0.90 and "gates.TECHNICAL_RECALL_MIN" in cite


def test_resolve_expected_zero_requires_authority():
    with pytest.raises(qc.QualificationContractError):
        qc.resolve_expected({"zero": True})
    v, cite = qc.resolve_expected({"zero": True, "authority": "ADR §K"})
    assert v == 0 and "ADR §K" in cite


def test_resolve_expected_assertion_returns_none_with_citation():
    v, cite = qc.resolve_expected({"assertion": "X", "authority": "doc.md"})
    assert v is None and "doc.md" in cite


def test_resolve_expected_unknown_shape_raises():
    with pytest.raises(qc.QualificationContractError):
        qc.resolve_expected({"foo": "bar"})


# ── checker re-ejecutable ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def _report():
    return qc.run_contract()


def test_checker_runs_all_cases_with_found_expected_delta(_report):
    ids = {c["case_id"] for c in _report["cases"]}
    assert {"QC-TECH-RECALL", "QC-FUNC-RECALL", "QC-DOCUMENT-EGRESS",
            "QC-REPRODUCIBILITY"} <= ids
    for c in _report["cases"]:
        assert "found_value" in c and "expected_value" in c and "delta" in c
        assert c["status"] in ("PASS", "FAIL")
        # el valor esperado viene con su cita, no como literal suelto
        assert c["expected_value_source"]
        qc_me = c["metric_envelope"]
        assert {"suite_version", "definition", "reportable_range",
                "contamination_statement"} <= set(qc_me)


def test_technical_and_functional_gates_pass_against_cited_thresholds(_report):
    st = _report["gates_status"]
    assert st["QC-TECH-RECALL"] == "PASS"
    assert st["QC-FUNC-RECALL"] == "PASS"
    assert st["QC-DOCUMENT-EGRESS"] == "PASS"
    assert st["QC-LLM-CALLS"] == "PASS"
    assert st["QC-REPRODUCIBILITY"] == "PASS"


def test_system_never_self_qualifies(_report):
    assert _report["system_never_self_qualifies"] is True
    assert _report["qualified_version"] is None
    assert _report["overall"] in ("DRAFT_BASELINE", "FAIL_REQUALIFICATION_REQUIRED")
    assert _report["overall"] != "QUALIFIED"
    assert "no se auto-cualifica" in _report["note"].lower() or \
           "no se auto-cualif" in _report["note"].lower()


def test_fingerprint_is_captured_and_compared(_report):
    fp = _report["fingerprint"]
    assert "input_config_fingerprint" in fp["current"]
    assert "findings_fingerprint" in fp["current"]
    # contrato DRAFT -> no hay fingerprint declarado -> match es N/A, no un pase silencioso
    assert fp["declared"] is None
    assert "DRAFT" in str(fp["match"])


def test_requalification_triggers_report_current_shas(_report):
    trg = _report["requalification"]["triggers"]
    names = {t["trigger"] for t in trg}
    assert {"extractor_document", "rules", "gate_thresholds", "graph_build"} <= names
    for t in trg:
        assert "current_sha256" in t
        # DRAFT -> sin SHA congelado -> 'changed' es UNKNOWN, no False silencioso
        assert t["changed"] in (True, False) or "UNKNOWN" in str(t["changed"])


def test_requalification_status_flags_changed_trigger_sha():
    d = qc.load_contract()
    d["qualified_against"]["artifact_sha256"] = {"gate_thresholds": "0" * 64}
    st = qc.requalification_status(d)
    assert st["any_changed_since_qualified"] is True
    row = next(t for t in st["triggers"] if t["trigger"] == "gate_thresholds")
    assert row["changed"] is True and row["current_sha256"] != "0" * 64


def test_decide_overall_is_pure_and_never_qualified():
    ok_cases = [{"status": "PASS"}]
    fail_cases = [{"status": "PASS"}, {"status": "FAIL"}]
    reqal_clean = {"any_changed_since_qualified": False}
    reqal_dirty = {"any_changed_since_qualified": True}
    fp_na = {"match": "N/A (contrato DRAFT)"}
    fp_ok = {"match": True}
    fp_bad = {"match": False}

    assert qc.decide_overall(ok_cases, reqal_clean, fp_na, signed=False) == "DRAFT_BASELINE"
    assert qc.decide_overall(fail_cases, reqal_clean, fp_na, signed=False) == "FAIL_REQUALIFICATION_REQUIRED"
    assert qc.decide_overall(ok_cases, reqal_dirty, fp_na, signed=False) == "FAIL_REQUALIFICATION_REQUIRED"
    assert qc.decide_overall(ok_cases, reqal_clean, fp_bad, signed=True) == "FAIL_REQUALIFICATION_REQUIRED"
    assert qc.decide_overall(ok_cases, reqal_clean, fp_ok, signed=True) == "GATES_MET_AS_QUALIFIED"
    # aunque todo pase y esté firmado, NUNCA "QUALIFIED" a secas
    for args in [(ok_cases, reqal_clean, fp_ok), (ok_cases, reqal_clean, fp_na)]:
        assert qc.decide_overall(*args, signed=True) != "QUALIFIED"


def test_contingencies_are_declared_with_status(_report):
    cids = {c["id"]: c["status"] for c in _report["contingencies"]}
    assert cids["CT-REGULATORY-LLM"] == "FAIL_ACCEPTED_CONTINGENCY"
    assert "CT-EXCEPTIONS-1-5" in cids
    assert "CT-HELD-OUT-PENDING" in cids
