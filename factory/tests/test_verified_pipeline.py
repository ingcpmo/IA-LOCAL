"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.3 — orquestacion verificada
(evaluate_requirement_over_chunks). Usa un generate_fn falso inyectado --
no depende de Ollama real (ver limitacion de conectividad documentada en
W5v2_FASE0_INVENTARIO.md)."""
from __future__ import annotations

import json

import pytest

from factory.regulatory.verified_pipeline import (
    DECISION_COVERAGE_FLAG,
    evaluate_requirement_over_chunks,
)
from factory.services import decision_store_v2 as store

KNOWN_REQS = {"ANNEX11_9"}

# ANNEX11_9 es un requisito REAL del catalogo; su fuente es eu_gmp_annex11.
REQ = "ANNEX11_9"
SRC = "eu_gmp_annex11"


@pytest.fixture()
def authorized(tmp_path):
    """G1.9: sin cobertura de decision, `generate_fn` no se llama ni una vez.
    Firmar D2 sobre el requisito y D1 sobre su fuente es el contrato, no
    andamiaje del test."""
    path = tmp_path / "decisions_v2.jsonl"
    recs = [
        store.build_record(
            decision_family="D2", decision_type="ORIGINAL",
            selection_mode="EXPLICIT_LIST", resolved_target_ids=[REQ],
            decision="APPROVE", decision_origin="human_confirmed",
            approved_by_id="Cesar", approved_by_display_name="Cesar",
            decision_instance_id="D2-2026-001"),
        store.build_record(
            decision_family="D1", decision_type="ORIGINAL",
            selection_mode="EXPLICIT_LIST", resolved_target_ids=[SRC],
            decision="APPROVE", decision_origin="human_confirmed",
            approved_by_id="Cesar", approved_by_display_name="Cesar",
            decision_instance_id="D1-2026-001"),
    ]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs),
                    encoding="utf-8")
    return path


def _manifest():
    return {
        "model": "m", "model_digest": "d", "prompt_sha256": "p",
        "schema_name": "finding_llm_v1", "schema_sha256": "s",
        "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
        "manifest_incomplete": False,
    }


def _fake_generate_all_not_observed(prompt, chunk):
    return {
        "llm_output": {
            "requirement_id": "ANNEX11_9", "chunk_observation": "not_observed_in_chunk",
            "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
            "rationale": "sin mencion", "flags": [],
        },
        "execution_manifest": _manifest(), "ok": True, "errors": [],
        "status": "verified", "rejection_reason": None,
    }


def _fake_generate_one_observed(prompt, chunk):
    if chunk.get("page_start") == 2:
        return {
            "llm_output": {
                "requirement_id": "ANNEX11_9", "chunk_observation": "observed",
                "evidence_quote": chunk["text"], "evidence_page": 2, "confidence": 0.9,
                "rationale": "cita anclada", "flags": [],
            },
            "execution_manifest": _manifest(), "ok": True, "errors": [],
            "status": "verified", "rejection_reason": None,
        }
    return _fake_generate_all_not_observed(prompt, chunk)


def _fake_generate_schema_rejected(prompt, chunk):
    return {
        "llm_output": None, "execution_manifest": _manifest(),
        "ok": False, "errors": ["respuesta del modelo no es JSON valido"],
        "status": "rejected_by_verifier", "rejection_reason": "schema_validation_failed",
    }


CHUNKS = [
    {"text": "no menciona el tema", "page_start": 1, "page_end": 1},
    {"text": "El audit trail registra cada evento con timestamp.", "page_start": 2, "page_end": 2},
]


def test_all_not_observed_yields_documentation_gap(authorized):
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_all_not_observed, "prompt",
        decision_store_file=authorized,
    )
    assert summary.conclusion.conclusion == "DOCUMENTATION_GAP"
    assert summary.verified_count == 2
    assert summary.rejected_count == 0


def test_one_observed_chunk_yields_documented_and_supported(authorized):
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_one_observed, "prompt",
        decision_store_file=authorized,
    )
    assert summary.conclusion.conclusion == "DOCUMENTED_AND_SUPPORTED"


def test_schema_rejected_records_are_preserved_for_traceability(authorized):
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_schema_rejected, "prompt",
        decision_store_file=authorized,
    )
    assert summary.rejected_count == len(CHUNKS)
    assert len(summary.records) == len(CHUNKS)  # nada se descarta
    assert summary.conclusion.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in summary.conclusion.review_flags


# ===========================================================================
# G1.9 -- cobertura de decisión antes de gastar inferencia (consumidor C-3)
# ===========================================================================

def _never_called(prompt, chunk):
    raise AssertionError(
        "se gastó una llamada de inferencia en un requisito SIN cobertura humana")


@pytest.fixture()
def no_decisions(tmp_path):
    path = tmp_path / "sin_decisiones.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def test_uncovered_requirement_spends_zero_inference(no_decisions):
    """El equivalente de L-05 para el planner: sin cobertura, `generate_fn`
    no se llama ni una vez."""
    summary = evaluate_requirement_over_chunks(
        REQ, "FS", "expected", CHUNKS, KNOWN_REQS,
        _never_called, "prompt", decision_store_file=no_decisions,
    )
    assert summary.records == []
    assert summary.verified_count == 0


def test_uncovered_requirement_is_never_reported_as_non_compliant(no_decisions):
    """La garantía más importante de todo el gate: no estar autorizado a
    mirar un requisito NO es evidencia de que el documento lo incumpla."""
    summary = evaluate_requirement_over_chunks(
        REQ, "FS", "expected", CHUNKS, KNOWN_REQS,
        _never_called, "prompt", decision_store_file=no_decisions,
    )
    assert summary.conclusion.conclusion == "EVALUATION_INCOMPLETE"
    assert summary.conclusion.conclusion != "DOCUMENTATION_GAP"
    assert DECISION_COVERAGE_FLAG in summary.conclusion.review_flags


def test_the_reason_is_coverage_not_absence_of_records(no_decisions):
    """`NO_VALID_RECORDS` diría que no hubo evidencia válida. Lo que pasa es
    que nadie autorizó mirarla, y el informe debe distinguirlo."""
    summary = evaluate_requirement_over_chunks(
        REQ, "FS", "expected", CHUNKS, KNOWN_REQS,
        _never_called, "prompt", decision_store_file=no_decisions,
    )
    assert "NO_VALID_RECORDS" not in summary.conclusion.review_flags
    assert any("D2/" in f or "D1/" in f for f in summary.conclusion.review_flags)


def test_evaluate_document_declares_the_exclusion_never_omits_it(no_decisions):
    from factory.regulatory.verified_pipeline import evaluate_document

    result = evaluate_document(
        document_type="FS", document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={REQ: CHUNKS},
        generate_fn=_never_called,
        prompt_by_requirement={REQ: "prompt"},
        requirement_ids={REQ},
        decision_store_file=no_decisions,
    )
    assert result.excluded_by_decision == [REQ]
    assert result.requirement_summaries == []
    terminal = result.terminal_results[0]
    assert terminal["requirement_id"] == REQ
    assert terminal["reason"] == DECISION_COVERAGE_FLAG
    assert terminal["source"] == "decision_scope_resolver"
    assert terminal["denial_reasons"]


def test_excluded_requirements_do_not_inflate_the_inference_budget(no_decisions, authorized):
    """Un requisito excluido no cuesta nada y no puede inflar `max_calls`
    de D4-A."""
    from factory.regulatory.verified_pipeline import evaluate_document

    kwargs = dict(
        document_type="FS", document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={REQ: CHUNKS},
        prompt_by_requirement={REQ: "prompt"},
        requirement_ids={REQ},
    )
    blocked = evaluate_document(generate_fn=_never_called,
                                decision_store_file=no_decisions, **kwargs)
    assert blocked.inference_eligible_requirement_ids == []

    allowed = evaluate_document(generate_fn=_fake_generate_all_not_observed,
                                decision_store_file=authorized, **kwargs)
    assert allowed.inference_eligible_requirement_ids == [REQ]


def test_exclusion_by_decision_is_not_mixed_with_review_queue(no_decisions):
    """'pendiente de juicio humano sobre la evidencia' y 'nadie firmó que se
    pueda mirar' son cosas distintas y no comparten lista."""
    from factory.regulatory.verified_pipeline import evaluate_document

    result = evaluate_document(
        document_type="FS", document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={REQ: CHUNKS},
        generate_fn=_never_called,
        prompt_by_requirement={REQ: "prompt"},
        requirement_ids={REQ},
        decision_store_file=no_decisions,
    )
    assert result.excluded_by_decision == [REQ]
    assert REQ not in result.review_queue


def test_coverage_is_checked_before_applicability(no_decisions):
    """La cobertura humana se evalúa ANTES que la fila de la matriz -- matriz
    cuya propia aprobación está en cuestión (hallazgo A-7)."""
    from factory.regulatory.verified_pipeline import evaluate_document

    result = evaluate_document(
        document_type="CS",   # tipo que dispararía APPLICABILITY_REVIEW_REQUIRED
        document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={},
        generate_fn=_never_called,
        prompt_by_requirement={},
        requirement_ids={"21_CFR_11.10(a)"},
        decision_store_file=no_decisions,
    )
    assert result.excluded_by_decision == ["21_CFR_11.10(a)"]
    assert result.terminal_results[0]["source"] == "decision_scope_resolver"


def test_unknown_requirement_still_reaches_the_applicability_filter(no_decisions):
    """Un id fuera del catálogo no es una denegación de gobernanza: se deja
    al filtro de aplicabilidad, como antes."""
    from factory.regulatory.verified_pipeline import evaluate_document

    result = evaluate_document(
        document_type="FS", document_type_source="human_assigned",
        document_type_confidence=None,
        relevant_chunks_by_requirement={},
        generate_fn=_never_called,
        prompt_by_requirement={},
        requirement_ids={"REQUISITO_INEXISTENTE"},
        decision_store_file=no_decisions,
    )
    assert result.excluded_by_decision == []
    assert result.review_queue == ["REQUISITO_INEXISTENTE"]
