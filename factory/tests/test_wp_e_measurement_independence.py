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


def test_sample_is_emitted_findings_review_not_recall_ground_truth(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=1)
    assert a["sample_type"] == adj.SAMPLE_TYPE_EMITTED
    # FN / TN no son opciones de etiqueta para una muestra de findings emitidos
    assert set(a["label_options"]) == {"TP", "FP", "COVERAGE_LIMITED"}
    assert "FN" not in a["label_options"] and "TN" not in a["label_options"]


def test_unlabeled_emitted_review_is_unknown_for_both_metrics(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=1)
    sc = adj.score_emitted_review(a)
    assert sc["labeled"] is False
    assert sc["PRECISION_REPORTABLE"] == "UNKNOWN"
    assert sc["RECALL_REPORTABLE"] == "UNKNOWN"
    me.require_envelope(sc["metric_envelope_precision"])
    me.require_envelope(sc["metric_envelope_recall"])


def test_score_emitted_review_is_fail_closed_on_fn_or_tn(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=3)
    a["cases"][0]["label"] = "FN"
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_emitted_review(a)
    a["cases"][0]["label"] = "TN"
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_emitted_review(a)


def test_labeled_emitted_review_yields_precision_only_recall_stays_unknown(_run_dir):
    a = adj.sample_for_adjudication(_run_dir, n=20, seed=2)
    for i, c in enumerate(a["cases"]):
        c["label"] = "COVERAGE_LIMITED" if c["would_degrade"] else ("TP" if i % 2 else "FP")
    a["adjudicator"] = "QA reviewer (sim)"
    sc = adj.score_emitted_review(a)
    assert sc["labeled"] is True
    assert isinstance(sc["PRECISION_REPORTABLE"], list) and len(sc["PRECISION_REPORTABLE"]) == 2
    assert sc["RECALL_REPORTABLE"] == "UNKNOWN"                  # nunca se deriva de findings emitidos
    assert sc["metric_envelope_precision"]["size"]["coverage_limited"] == sc["counts"]["COVERAGE_LIMITED"]
    me.require_envelope(sc["metric_envelope_precision"])


def test_score_recall_fail_closed_without_signed_opportunities(_run_dir):
    r = adj.score_recall(_run_dir)                              # opportunities yaml = DRAFT_UNSIGNED
    assert r["opportunities_status"] in ("DRAFT_UNSIGNED", "ABSENT")
    assert r["usable"] is False
    assert r["RECALL_REPORTABLE"] == "UNKNOWN"
    assert r["SPECIFICITY_REPORTABLE"] == "UNKNOWN"
    assert r["TN"] is None                                      # sin negative_units firmadas -> no se inventa TN
    me.require_envelope(r["metric_envelope"])


def test_opportunities_template_is_draft_empty_and_declares_protocol():
    d = adj.load_opportunities()
    assert str(d["status"]).upper() in ("DRAFT_UNSIGNED", "ABSENT")
    assert d["opportunities"] == [] and d["negative_units"] == []
    assert d.get("adjudicator") in (None, "null")
    # política de página EXPLÍCITA, no un ±N implícito
    assert d["page_match_policy"]["tolerance_pages"] == 0
    # los 9 campos obligatorios por oportunidad están declarados
    for k in ("opportunity_id", "expected_class", "expected_subtype", "document", "page_band",
              "expected_topic_or_requirement", "human_evidence_anchor", "basis", "reviewer_note"):
        assert k in adj.OPPORTUNITY_REQUIRED_FIELDS


# --- helpers para construir un yaml de oportunidades sintético SIGNED ---
def _emitted(run_dir):
    import json
    fs = []
    for n in ("regulatory_findings.json", "functional_findings.json", "technical_findings.json"):
        p = run_dir / n
        if p.is_file():
            fs += json.loads(p.read_text())
    return fs


def _write_opps(tmp_path, opps, *, negatives=None, tol=0, name="opps.yaml"):
    import yaml
    d = {"artifact": "real_corpus_opportunities", "version": "test", "status": "SIGNED",
         "adjudicator": "QA sim", "page_match_policy": {"tolerance_pages": tol},
         "opportunities": opps, "negative_units": negatives or []}
    p = tmp_path / name
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    return p


def _opp(cls, sub, doc, band, oid, *, matched=None, by=None, note="n"):
    o = {"opportunity_id": oid, "expected_class": cls, "expected_subtype": sub,
         "document": doc, "page_band": list(band),
         "expected_topic_or_requirement": "t", "human_evidence_anchor": "a",
         "basis": "b", "reviewer_note": "n"}
    if matched is not None:
        o["matched_finding_id"] = matched
        o["match_confirmed_by"] = by or "QA Validation Lead"
        o["match_note"] = note
    return o


def _fids_for(fs, cls, sub, doc):
    return [f["finding_id"] for f in fs if (f["class"], f["subtype"], f["document"]) == (cls, sub, doc)]


def test_score_recall_structural_match_alone_is_not_tp(_run_dir, tmp_path):
    """La coincidencia estructural NO cuenta como TP -- solo propone candidatos."""
    from collections import Counter
    fs = _emitted(_run_dir)
    (cls, sub, doc), _ = max(Counter((f["class"], f["subtype"], f["document"]) for f in fs).items(),
                             key=lambda x: x[1])
    pages = sorted(f["page"] for f in fs if (f["class"], f["subtype"], f["document"]) == (cls, sub, doc))
    band = [min(pages), max(pages)]
    r = adj.score_recall(_run_dir, _write_opps(tmp_path, [_opp(cls, sub, doc, band, "OPP-0")]))
    assert r["human_match_confirmation_required"] is True
    assert r["TP"] == 0 and r["FN"] == 1                       # sin confirmación humana -> FN
    assert r["per_opportunity"][0]["outcome"] == "FN"
    assert r["per_opportunity"][0]["structural_candidate_finding_ids"]     # candidatos propuestos


def test_score_recall_tp_requires_human_confirmation(_run_dir, tmp_path):
    from collections import Counter
    fs = _emitted(_run_dir)
    (cls, sub, doc), _ = max(Counter((f["class"], f["subtype"], f["document"]) for f in fs).items(),
                             key=lambda x: x[1])
    pages = sorted(f["page"] for f in fs if (f["class"], f["subtype"], f["document"]) == (cls, sub, doc))
    band = [min(pages), max(pages)]
    fid = _fids_for(fs, cls, sub, doc)[0]
    opp = _opp(cls, sub, doc, band, "OPP-0", matched=fid, by="QA sim", note="corresponde")
    r = adj.score_recall(_run_dir, _write_opps(tmp_path, [opp]))
    assert r["TP"] == 1 and r["FN"] == 0
    mp = r["matched_pairs"][0]
    assert mp["finding_id"] == fid and mp["match_confirmed_by"] == "QA sim"
    assert mp["within_structural_candidates"] is True
    assert r["RECALL_REPORTABLE"] and r["recall"] == 1.0


def test_score_recall_matching_is_one_to_one(_run_dir, tmp_path):
    """Un mismo finding confirmado no puede acreditar dos oportunidades -> fail-closed."""
    from collections import Counter
    fs = _emitted(_run_dir)
    cc = Counter((f["class"], f["subtype"], f["document"]) for f in fs)
    (cls, sub, doc), k = max(cc.items(), key=lambda x: x[1])
    fids = _fids_for(fs, cls, sub, doc)
    pages = sorted(f["page"] for f in fs if (f["class"], f["subtype"], f["document"]) == (cls, sub, doc))
    band = [min(pages), max(pages)]
    # k oportunidades, cada una confirmada a un finding DISTINTO -> TP=k, uno-a-uno
    ok = [_opp(cls, sub, doc, band, f"OPP-{i}", matched=fids[i], by="QA") for i in range(k)]
    r = adj.score_recall(_run_dir, _write_opps(tmp_path, ok, name="ok.yaml"))
    assert r["TP"] == k and r["one_to_one"] is True
    assert len({m["finding_id"] for m in r["matched_pairs"]}) == k
    # dos oportunidades confirmando el MISMO finding -> AdjudicationMethodError
    dup = [_opp(cls, sub, doc, band, "OPP-A", matched=fids[0], by="QA"),
           _opp(cls, sub, doc, band, "OPP-B", matched=fids[0], by="QA")]
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, dup, name="dup.yaml"))


def test_score_recall_fail_closed_on_confirmed_nonexistent_finding(_run_dir, tmp_path):
    opp = _opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 10], "OPP-1",
               matched="does-not-exist-999", by="QA")
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, [opp]))


def test_score_recall_fail_closed_on_match_without_confirmer(_run_dir, tmp_path):
    opp = _opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 10], "OPP-1")
    opp["matched_finding_id"] = "whatever"        # sin match_confirmed_by
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, [opp]))


def test_score_recall_page_match_policy_governs_candidates_only(_run_dir, tmp_path):
    """page_match_policy gobierna la PROPUESTA de candidatos, no el TP."""
    from collections import Counter
    fs = _emitted(_run_dir)
    (cls, sub, doc), _ = max(Counter((f["class"], f["subtype"], f["document"]) for f in fs).items(),
                             key=lambda x: x[1])
    pages = sorted(f["page"] for f in fs if (f["class"], f["subtype"], f["document"]) == (cls, sub, doc))
    outside = [max(pages) + 5, max(pages) + 6]           # banda fuera de toda página emitida
    opp = [_opp(cls, sub, doc, outside, "OPP-X")]
    r0 = adj.score_recall(_run_dir, _write_opps(tmp_path, opp, tol=0, name="t0.yaml"))
    r6 = adj.score_recall(_run_dir, _write_opps(tmp_path, opp, tol=6, name="t6.yaml"))
    assert r0["per_opportunity"][0]["structural_candidate_finding_ids"] == []      # tol=0 -> sin candidatos
    assert r6["per_opportunity"][0]["structural_candidate_finding_ids"]            # tol=6 -> candidatos
    assert r0["TP"] == 0 and r6["TP"] == 0                # sin confirmación humana, ninguno es TP
    assert r0["page_match_policy"]["tolerance_pages"] == 0
    assert r6["metric_envelope"]["size"]["page_tolerance_pages"] == 6


@pytest.mark.parametrize("band", [
    [5, 3],            # start > end
    [0, 4],            # <= 0
    [-2, 5],           # negativo
    [3],               # longitud != 2
    [1, 2, 3],
    ["1", "9"],        # no enteros
    [1.5, 9.0],        # floats
    "1-9",             # ni siquiera lista
])
def test_page_band_validation_is_strict(_run_dir, tmp_path, band):
    opp = _opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 9], "OPP-1")
    opp["page_band"] = band
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, [opp], name="badband.yaml"))


@pytest.mark.parametrize("scope", [[9, 2], [0, 3], [-1, 4], [2], "1-3", [1.0, 3.0]])
def test_negative_scope_validation_is_strict(_run_dir, tmp_path, scope):
    opp = [_opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 9], "OPP-1")]
    neg = [{"unit_id": "NEG-1", "analysis_unit": "section", "document": "RW-0006",
            "scope": scope, "expected_class": "SecurityFinding",
            "expected_subtype": "ACCESS_CONTROL_GAP", "human_evidence_anchor": "x",
            "basis": "y", "reviewer_note": "z"}]
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, opp, negatives=neg, name="badscope.yaml"))


def test_score_recall_fail_closed_on_missing_opportunity_fields(_run_dir, tmp_path):
    opp = _opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 10], "OPP-1")
    del opp["human_evidence_anchor"]                      # campo que QA debe completar
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, [opp]))


def test_specificity_unknown_without_valid_negative_units(_run_dir, tmp_path):
    opp = [_opp("TechnicalFinding", "BACKUP_RECOVERY_GAP", "RW-0005", [1, 10], "OPP-1")]
    # negative_units incompletas -> fail-closed
    bad_neg = [{"unit_id": "NEG-1", "document": "RW-0006"}]
    with pytest.raises(adj.AdjudicationMethodError):
        adj.score_recall(_run_dir, _write_opps(tmp_path, opp, negatives=bad_neg))
    # sin negative_units -> specificity UNKNOWN, TN None
    r = adj.score_recall(_run_dir, _write_opps(tmp_path, opp, name="noneg.yaml"))
    assert r["SPECIFICITY_REPORTABLE"] == "UNKNOWN" and r["TN"] is None
