"""WP-E -- independencia de medición: metric_envelope + held_out_corpus + real_corpus_adjudication.

Verifica: el sobre de métrica es fail-closed (5 campos) · el held-out no es gate mientras
DRAFT_UNSIGNED o autor == autor de las reglas · match ESTRUCTURAL (sin frase literal) ·
procedencia REG/DOM/ADV validada · builder separado del runner de Suite C · la muestra
de adjudicación es determinista, estratificada y prioriza would_degrade · sin etiquetas
-> REPORTABLE_RANGE = UNKNOWN.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from factory.regulatory.validation_v2 import held_out_corpus as ho
from factory.regulatory.validation_v2 import metric_envelope as me
from factory.regulatory.validation_v2 import real_corpus_adjudication as adj


# ── metric_envelope ────────────────────────────────────────────────────
def test_envelope_fail_closed_on_missing_fields():
    with pytest.raises(me.MetricEnvelopeError):
        me.require_envelope({"metric": "X", "value": 0.9})


def test_envelope_wrap_requires_all_five():
    env = me.wrap("TECHNICAL_RECALL", 0.9, suite_version="suite_c@1.0-benchmark (SIGNED)",
                  size={"positives": 10}, definition="TP = ...",
                  reportable_range=[0.7, 0.98],
                  contamination_statement="held-out author-independent; structural match")
    for f in me.REQUIRED_FIELDS:
        assert f in env
    me.require_envelope(env)  # round-trips


def test_envelope_value_none_only_with_sentinel_range():
    me.wrap("R", None, suite_version="v", size=1, definition="d",
            reportable_range="UNKNOWN", contamination_statement="pending")
    with pytest.raises(me.MetricEnvelopeError):
        me.wrap("R", None, suite_version="v", size=1, definition="d",
                reportable_range=[0.1, 0.9], contamination_statement="x")


def test_wilson_interval_bounds():
    lo, hi = me.wilson_interval(9, 10)
    assert 0.0 <= lo < hi <= 1.0
    assert me.wilson_interval(0, 0) == [0.0, 1.0]


# ── held_out_corpus ────────────────────────────────────────────────────
def test_held_out_is_draft_and_not_a_gate():
    assert ho.status() == "DRAFT_UNSIGNED"
    assert ho.is_usable_as_gate() is False
    with pytest.raises(ho.HeldOutNotUsableAsGateError):
        ho.assert_usable_as_gate()


def test_held_out_author_must_differ_from_rules_author(tmp_path):
    import yaml
    d = ho.load()
    rules_author = ho._rules_author()
    assert rules_author == "Capa 9 (Cesar)"
    # simular firmado por el MISMO autor que las reglas -> sigue sin ser gate
    bad = dict(d, status="SIGNED", author=rules_author)
    p = tmp_path / "ho_bad.yaml"
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    ho._load.cache_clear()
    assert ho.is_usable_as_gate(p) is False
    # firmado por autor independiente -> sí sería gate
    good = dict(d, status="SIGNED", author="QA Validation Lead")
    p2 = tmp_path / "ho_good.yaml"
    p2.write_text(yaml.safe_dump(good), encoding="utf-8")
    ho._load.cache_clear()
    assert ho.is_usable_as_gate(p2) is True
    ho._load.cache_clear()


def test_held_out_ground_truth_has_no_literal_phrase():
    """El match es ESTRUCTURAL: cada caso trae (finding_class, subtype, document, page_band),
    NUNCA una cadena de texto que el detector deba contener."""
    for c in ho.load()["cases"]:
        assert set(c["match"]) <= {"document", "page_band"}
        assert "anchor" not in c and "phrase" not in c and "text" not in c
        assert "source_text" not in str(c.get("expected", {}))


def test_held_out_provenance_tags_validated():
    for c in ho.load()["cases"]:
        assert c["provenance_tag"] in ho.PROVENANCE_TAGS
        if c["provenance_tag"] == "REG":
            assert (c.get("source_clause") or "").strip()
        if c["provenance_tag"] == "ADV":
            assert c.get("human_approved") is True


def test_held_out_dry_runs_structurally_and_is_indicative_only():
    r = ho.run_held_out_dry()
    assert r["usable_as_gate"] is False
    assert r["metric_envelope"]["reportable_range"] == "NOT_A_GATE"
    assert r["document_egress_bytes"] == 0
    assert set(r["by_provenance_tag"]) <= set(ho.PROVENANCE_TAGS)
    # determinista
    r2 = ho.run_held_out_dry()
    assert r["TP"] == r2["TP"] and r["FN"] == r2["FN"]


def test_held_out_builder_is_separate_module_from_suite_c_runner():
    import factory.regulatory.validation_v2.held_out_corpus as hoc
    import factory.regulatory.validation_v2.technical_suite_c as tsc
    assert hasattr(hoc, "build_seed_corpus")
    # el runner de Suite C NO importa el builder del held-out ni viceversa de forma circular
    assert "build_seed_corpus" not in dir(tsc)


# ── real_corpus_adjudication ───────────────────────────────────────────
@pytest.fixture(scope="module")
def _run_dir():
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    docs = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]
    base = Path(tempfile.mkdtemp(prefix="wpe-adj-"))
    run_v2_pipeline(docs, project_id="RW-V2-E2E", run_id="adj", report_base=base)
    return base / "adj"


def test_sample_is_deterministic_and_stratified(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=40, seed=7)
    b = adj.sample_for_adjudication(_run_dir, n=40, seed=7)
    assert [c["case_id"] for c in a["cases"]] == [c["case_id"] for c in b["cases"]]
    # distinto seed -> (posiblemente) distinto orden, mismo tamaño
    c = adj.sample_for_adjudication(_run_dir, n=40, seed=99)
    assert c["sample_size"] == a["sample_size"] == 40
    # estratificado: varias (class, subtype) presentes
    combos = {(x["finding_class"], x["subtype"]) for x in a["cases"]}
    assert len(combos) >= 6


def test_sample_prioritizes_would_degrade(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=40, seed=7)
    # el corpus real marca 78 findings would_degrade; la muestra debe traer varios
    assert sum(1 for c in a["cases"] if c["would_degrade"]) >= 10
    assert all(c["label"] == "PENDING" for c in a["cases"])


def test_unlabeled_sheet_has_unknown_reportable_range(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=1)
    sc = adj.score_sheet(a)
    assert sc["labeled"] is False
    assert sc["reportable_range"] == "UNKNOWN"
    assert sc["metric_envelope"]["value"] is None
    me.require_envelope(sc["metric_envelope"])  # el sobre es válido aun sin medición


def test_labeled_sheet_produces_range_and_excludes_coverage_limited(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=2)
    for i, c in enumerate(a["cases"]):
        c["label"] = "COVERAGE_LIMITED" if c["would_degrade"] else ("TP" if i % 2 else "FP")
    a["adjudicator"] = "QA reviewer (sim)"
    sc = adj.score_sheet(a)
    assert sc["labeled"] is True
    assert isinstance(sc["reportable_range"], list) and len(sc["reportable_range"]) == 2
    # COVERAGE_LIMITED fuera del cálculo
    cl = sc["counts"]["COVERAGE_LIMITED"]
    assert sc["metric_envelope"]["size"]["coverage_limited"] == cl
    me.require_envelope(sc["metric_envelope"])
