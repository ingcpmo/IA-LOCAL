"""Tier-1 asistido (D2, docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md §5,
.claude/plans/wise-bubbling-toucan.md) -- `factory/regulatory/
tier1_report.py`. Ollama SIEMPRE mockeado (`ollama_client.generate`,
mismo patrón que `test_gmpai_chunked_engine.py`), gobernanza PILOT_
EXECUTION mockeada (mismo patrón que `test_r2_judgment.py`) -- cero
llamadas reales."""
from __future__ import annotations

import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.engines.gmpai_integrity import ollama_client
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory import tier1_report as t1
from factory.tests.test_gmpai_chunked_engine import (
    PROMPT_PATH,
    _ANCHORED_QUOTE,
    _D_CRITERIA_11_10_D,
    _all_insufficient,
    _d_assessments,
    _ollama_response,
)


class _Scope:
    def __init__(self, authorized=True, covering_instances=("PILOT-INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(t1, "_resolve_document_path", lambda doc_id: (PROMPT_PATH, "0" * 64))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")


def _authorize(monkeypatch, *, max_calls=60, authorized=True, denial_reason=None):
    def fake_resolve(family, target_id, *, store_file=None):
        assert family == "PILOT_EXECUTION"
        return _Scope(authorized=authorized, denial_reason=denial_reason)
    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1",
         "payload": {"max_calls": max_calls, "authorizes_corpus": False, "authorizes_baseline": False}},
    ])


def _positive_pages():
    return [f"Introduccion general. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D)
            + " Resto del documento sin relacion. " * 40]


def test_hard_stop_without_pilot_execution_budget(monkeypatch, tmp_path):
    """Mismo guardián que run_pilot_sample_batch/judgment.py -- sin
    presupuesto utilizable, ninguna llamada arranca. La excepción viene
    de _select_pilot_execution_instance (corpus_runner), reutilizada tal
    cual, nunca reimplementada."""
    _authorize(monkeypatch, max_calls=0)
    monkeypatch.setattr(t1, "_default_extractor", lambda path: _positive_pages())
    with pytest.raises(runner.CorpusRunNotAuthorizedError):
        t1.generate_tier1_report("RW-TEST", "fda_part11_agent", document_type="FS",
                                  checkpoint_dir=tmp_path / "ckpt")


def test_hard_stop_when_document_exceeds_budget(monkeypatch, tmp_path):
    """Tier1ReportError propio: presupuesto vigente > 0 pero insuficiente
    para el documento completo -- nunca arranca una corrida a medias."""
    _authorize(monkeypatch, max_calls=1)
    monkeypatch.setattr(t1, "_default_extractor", lambda path: ["A" * 7000, "B" * 7000, "C" * 7000])
    with pytest.raises(t1.Tier1ReportError):
        t1.generate_tier1_report("RW-TEST", "fda_part11_agent", document_type="FS",
                                  checkpoint_dir=tmp_path / "ckpt")


def test_confirmed_requirement_includes_anchored_quote_and_source_caveat(monkeypatch, tmp_path):
    _authorize(monkeypatch, max_calls=60)
    monkeypatch.setattr(t1, "_default_extractor", lambda path: _positive_pages())
    entry = {"req_id": "21_CFR_11.10(d)", "estado": "cumple",
             "evidencia_exacta": _ANCHORED_QUOTE, "brecha": "n/a", "recomendacion": "n/a",
             "criterion_assessments": _d_assessments(["MET"] * 5)}
    payload = _all_insufficient({"21_CFR_11.10(d)": entry})
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))

    report = t1.generate_tier1_report("RW-TEST", "fda_part11_agent", document_type="FS",
                                       checkpoint_dir=tmp_path / "ckpt")

    outcome = next(r for r in report.requirements if r.requirement_id == "21_CFR_11.10(d)")
    assert outcome.bucket == t1.CONFIRMED
    assert outcome.conclusion == "PROVISIONALLY_DOCUMENTED"
    assert outcome.evidence_quote == _ANCHORED_QUOTE
    assert "SOURCE_PENDING_REVERIFICATION" in outcome.review_flags


def test_gap_requirement_is_needs_human_review_and_links_queue_entry(monkeypatch, tmp_path, isolated_review_queue):
    _authorize(monkeypatch, max_calls=60)
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(t1, "_default_extractor", lambda path: pages)
    payload = _all_insufficient()
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))

    report = t1.generate_tier1_report("RW-TEST", "fda_part11_agent", document_type="FS",
                                       checkpoint_dir=tmp_path / "ckpt")

    outcome = next(r for r in report.requirements if r.requirement_id == "21_CFR_11.10(e)")
    assert outcome.bucket == t1.NEEDS_HUMAN_REVIEW
    assert outcome.conclusion in ("DOCUMENTATION_GAP", "PROVISIONAL_GAP")
    assert outcome.review_queue_rc_id is not None
    assert outcome.review_queue_rc_id == f"finding-{report.run_id}-21_CFR_11.10(e)"


def test_unknown_conclusion_fails_closed_to_needs_review():
    assert t1._bucket_for_conclusion("SOME_FUTURE_CONCLUSION_NOT_YET_MAPPED") == t1.NEEDS_HUMAN_REVIEW


def test_render_markdown_never_declares_compliance_and_lists_confirmed_and_pending():
    report = t1.Tier1Report(
        document_id="RW-TEST", agent_id="fda_part11_agent", run_id="run-x",
        generated_at="2026-08-11T00:00:00+00:00",
        requirements=[
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(d)", bucket=t1.CONFIRMED,
                                   conclusion="PROVISIONALLY_DOCUMENTED",
                                   review_flags=["SOURCE_PENDING_REVERIFICATION"],
                                   evidence_quote="cita real anclada", page_or_section="p.3"),
            t1.RequirementOutcome(requirement_id="21_CFR_11.10(e)", bucket=t1.NEEDS_HUMAN_REVIEW,
                                   conclusion="PROVISIONAL_GAP", review_queue_rc_id="finding-run-x-21_CFR_11.10(e)"),
        ],
    )
    md = t1.render_tier1_markdown(report)
    assert "cita real anclada" in md
    assert "finding-run-x-21_CFR_11.10(e)" in md
    assert "fuente pendiente de reverificación" in md
    for banned in ("cumple con", "aprobado", "libera el lote", "cierra CAPA"):
        assert banned not in md.lower()
    assert "borrador asistido" in md.lower()
