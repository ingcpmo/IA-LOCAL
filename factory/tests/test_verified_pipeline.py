"""W5 Ciclo 1 (v2), Fase 2, Bloque 2.3 — orquestacion verificada
(evaluate_requirement_over_chunks). Usa un generate_fn falso inyectado --
no depende de Ollama real (ver limitacion de conectividad documentada en
W5v2_FASE0_INVENTARIO.md)."""
from __future__ import annotations

from factory.regulatory.verified_pipeline import evaluate_requirement_over_chunks

KNOWN_REQS = {"ANNEX11_9"}


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


def test_all_not_observed_yields_documentation_gap():
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_all_not_observed, "prompt",
    )
    assert summary.conclusion.conclusion == "DOCUMENTATION_GAP"
    assert summary.verified_count == 2
    assert summary.rejected_count == 0


def test_one_observed_chunk_yields_documented_and_supported():
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_one_observed, "prompt",
    )
    assert summary.conclusion.conclusion == "DOCUMENTED_AND_SUPPORTED"


def test_schema_rejected_records_are_preserved_for_traceability():
    summary = evaluate_requirement_over_chunks(
        "ANNEX11_9", "FS", "expected", CHUNKS, KNOWN_REQS,
        _fake_generate_schema_rejected, "prompt",
    )
    assert summary.rejected_count == len(CHUNKS)
    assert len(summary.records) == len(CHUNKS)  # nada se descarta
    assert summary.conclusion.conclusion == "EVALUATION_INCOMPLETE"
    assert "NO_VALID_RECORDS" in summary.conclusion.review_flags
