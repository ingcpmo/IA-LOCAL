"""R2.3 §4 (docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md, 2026-08-11) --
enriquecimiento de la cola R1.8: el modo JUICIO adjunta sus top-k
candidatos de fusión (recuperación, NUNCA evidencia validada) para que el
revisor humano reciba "revisa estos N pasajes en estas páginas", no
"busca en todo el documento". Ollama SIEMPRE mockeado, cero llamadas
reales."""
from __future__ import annotations

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.layer9 import human_review_queue as hrq

PART11_PROMPT_PATH = __import__("pathlib").Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"


def _all_insufficient():
    return {"checkpoints": [
        {"req_id": "21_CFR_11.10(e)", "estado": "evidencia_insuficiente",
         "evidencia_exacta": "", "brecha": "n/a", "recomendacion": "n/a"},
    ]}


def _ollama_response(payload):
    import json
    return {"response": json.dumps(payload), "done": True, "done_reason": "stop"}


def _run_judgment_mode(monkeypatch, candidate_metadata=None):
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    return ce.evaluate_chunked(
        PART11_PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
        run_context="production", use_verified_pipeline=True, document_type="FS",
        full_document_coverage=False, candidate_metadata=candidate_metadata,
    )


def test_entry_with_candidates_complete(monkeypatch, isolated_review_queue):
    candidate_metadata = [
        {"chunk_index": 5, "page_start": 10, "page_end": 10,
         "bm25_rank": 2, "embedding_rank": 1, "fusion_rank": 1},
        {"chunk_index": 9, "page_start": 22, "page_end": 23,
         "bm25_rank": None, "embedding_rank": 3, "fusion_rank": 2},
    ]
    _run_judgment_mode(monkeypatch, candidate_metadata=candidate_metadata)
    pending = hrq.list_pending()
    entry = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"][0]

    assert entry["schema_version"] == "finding_review_v2"
    cands = entry["summary"]["candidates"]
    assert len(cands) == 2
    assert cands[0]["chunk_index"] == 5
    assert cands[0]["page_start"] == 10 and cands[0]["page_end"] == 10
    assert cands[0]["bm25_rank"] == 2
    assert cands[0]["embedding_rank"] == 1
    assert cands[0]["fusion_rank"] == 1
    assert "excerpt" in cands[0] and cands[0]["excerpt"]
    assert cands[1]["bm25_rank"] is None  # candidato solo-embedding, honesto
    assert "candidates_honesty_note" in entry["summary"]
    assert "RECUPERACION" in entry["summary"]["candidates_honesty_note"]


def test_entry_without_candidates_still_valid():
    """Un despacho sin candidate_metadata (llamador que no lo provee, o
    pool vacío) sigue produciendo una entrada válida -- candidates=[]
    nunca None, sin nota de honestidad (no hay nada que advertir sobre una
    lista vacía)."""
    entry = hrq.enqueue_finding_for_review(
        run_id="run-x", requirement_id="21_CFR_11.10(e)", document_id="doc.pdf",
        page=None, evidence_quote="", conclusion="EVIDENCE_NOT_LOCATED_IN_CANDIDATES",
        review_flags=["ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE"], agent_id="fda_part11_agent",
    )
    assert entry["summary"]["candidates"] == []
    assert "candidates_honesty_note" not in entry["summary"]


def test_excerpt_sanitization_collapses_whitespace_and_truncates(monkeypatch, isolated_review_queue):
    noisy_text = ("Texto   con\n\nmuchos    espacios\ny saltos de linea. " * 20)
    candidate_metadata = [{"chunk_index": 1, "page_start": 1, "page_end": 1,
                            "bm25_rank": 1, "embedding_rank": None, "fusion_rank": 1}]
    pages = [noisy_text]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    ce.evaluate_chunked(
        PART11_PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
        run_context="production", use_verified_pipeline=True, document_type="FS",
        full_document_coverage=False, candidate_metadata=candidate_metadata,
    )
    pending = hrq.list_pending()
    entry = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"][0]
    excerpt = entry["summary"]["candidates"][0]["excerpt"]
    assert "\n" not in excerpt
    assert "  " not in excerpt
    assert len(excerpt) <= 400 + len("... [truncado]")
    assert excerpt.endswith("... [truncado]")


def test_human_decision_on_enriched_entry_emits_exactly_one_event(monkeypatch, isolated_review_queue):
    import factory.core.audit_writer as aw

    events = []
    original_write_event = aw.write_event

    def _spy(event_type, *a, **k):
        events.append(event_type)
        return original_write_event(event_type, *a, **k)

    monkeypatch.setattr(hrq, "write_event", _spy)

    candidate_metadata = [{"chunk_index": 3, "page_start": 12, "page_end": 12,
                            "bm25_rank": 1, "embedding_rank": 1, "fusion_rank": 1}]
    _run_judgment_mode(monkeypatch, candidate_metadata=candidate_metadata)
    pending = hrq.list_pending()
    entry = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"][0]

    events.clear()
    result = hrq.mark_reviewed(
        entry["rc_id"], "approved", "Cesar",
        confirmed_page=12, confirmed_quote="evidencia que el humano señaló",
    )
    assert events == ["rc_reviewed"]
    assert result["reviewer"] == "Cesar"

    updated = [e for e in hrq._read_all() if e["rc_id"] == entry["rc_id"]][0]
    assert updated["human_confirmed_evidence"]["page"] == 12
    assert updated["human_confirmed_evidence"]["quote"] == "evidencia que el humano señaló"
    assert updated["human_confirmed_evidence"]["confirmed_by"] == "Cesar"


def test_mark_reviewed_rejects_reserved_reviewer_identity(isolated_review_queue):
    hrq.enqueue("rc-test", "proj", {"x": 1})
    for reserved in ("human", "AGENT", " Capa8 "):
        with pytest.raises(ValueError):
            hrq.mark_reviewed("rc-test", "approved", reserved)
