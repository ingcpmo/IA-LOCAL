"""R2.3 §3 (docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md, 2026-08-11) -- cierra
el pendiente declarado en R2_2_CIERRE_Y_CAPA_SEMANTICA.md §6
(JUDGMENT_MODE_GAP_BLOCKED): los tests del blindaje de R2.2 §2
(test_gmpai_chunked_engine.py) usaban un escenario NEGATIVO SINTÉTICO
equivalente, no el replay literal de P2/P5. El caso real que motivó la
regla es el mejor guardián de la regla.

Replay EXACTO y offline de PILOT_EXECUTION-2026-012 (human_confirmed por
Cesar, 2026-08-10T22:23:05Z): las 5 respuestas RAW reales del modelo
qwen2.5 para cada unidad (persistidas en
factory/regulatory/pilot_run/checkpoints/raw_responses/{run_id}/, aquí
copiadas a fixtures/r2_3_judgment_replay/ para que el test no dependa de
artefactos de runtime gitignorados) + los mismos 5 chunks reales del
documento (mismo chunk_index que la corrida real, recuperados del índice
BM25 real -- GMPAI/source/Rockwell/, se skippea si el corpus no está
disponible en este entorno, mismo patrón que test_r2_retrieval.py).

Cero llamadas nuevas a Ollama: ollama_client.generate mockeado para
devolver, en orden, las 5 respuestas reales ya persistidas."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.layer9 import human_review_queue as hrq
from factory.regulatory.retrieval import indexer

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "r2_3_judgment_replay"
_SOURCE_DIR = Path("/home/ing_cpmo/GMPAI/source/Rockwell")
_RW_0005 = _SOURCE_DIR / "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"

pytestmark = pytest.mark.skipif(
    not _RW_0005.exists(), reason="corpus real GMPAI/source/Rockwell/ no disponible en este entorno"
)

PART11_PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"
ALCOA_PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "alcoa_prompts.yaml"

# Mismo orden de chunk_index (fusión RRF top-5) que run_judgment_batch()
# construyó realmente en PILOT_EXECUTION-2026-012 -- ver
# docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md §5.2.
_P2_CHUNK_ORDER = [18, 17, 19, 26, 10]
_P5_CHUNK_ORDER = [27, 20, 24, 25, 11]


def _sequential_generate_mock(raw_payloads: list[dict]):
    calls = {"n": 0}

    def _mock(*args, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        return {"response": json.dumps(raw_payloads[i]), "done": True, "done_reason": "stop"}
    return _mock


def _candidate_pool_texts(chunk_order: list[int]) -> list[str]:
    idx = indexer.build_index(_RW_0005)
    by_ci = {c["chunk_index"]: c for c in idx["chunks"]}
    return [by_ci[ci]["text"] for ci in chunk_order]


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "INDEX_DIR", tmp_path / "retrieval_index")


def test_p2_real_replay_judgment_mode_never_emits_gap(monkeypatch, isolated_review_queue):
    """P2 (21_CFR_11.10(g)) real: PILOT_EXECUTION-2026-010 midió esta
    misma evidencia como not_observed con un pool BM25 k=10 (rank 6,
    fuera de top-5). PILOT_EXECUTION-2026-012 la re-midió con el pool de
    fusión top-5 real (chunk_index 18,17,19,26,10) -- SIGUE not_observed,
    pero ahora bajo el blindaje de R2.2 §2: EVALUATION_INCOMPLETE +
    EVIDENCE_NOT_LOCATED_IN_CANDIDATES, nunca PROVISIONAL_GAP/
    DOCUMENTATION_GAP."""
    raw_payloads = json.loads(
        (_FIXTURES_DIR / "p2_21_cfr_11_10g_raw_payloads.json").read_text(encoding="utf-8"))
    per_unit_text = _candidate_pool_texts(_P2_CHUNK_ORDER)

    monkeypatch.setattr(ollama_client, "generate", _sequential_generate_mock(raw_payloads))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    result = ce.evaluate_chunked(
        PART11_PROMPT_PATH, "fda_part11_agent", "1.0.0", per_unit_text,
        "Rockwell", "RW-0005", "1.2", str(_RW_0005), "sha-test",
        run_context="production", use_verified_pipeline=True, document_type="FS",
        retry_technical_failures=True, evaluation_profile="H2H4",
        target_requirement_ids=["21_CFR_11.10(g)"], full_document_coverage=False,
    )

    c = result["verified_conclusions"]["21_CFR_11.10(g)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert c["conclusion"] not in ("PROVISIONAL_GAP", "DOCUMENTATION_GAP")
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c["review_flags"]

    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(g)"]
    assert len(matches) == 1
    entry = matches[0]["summary"]
    assert entry["conclusion"] == "EVIDENCE_NOT_LOCATED_IN_CANDIDATES"
    assert entry["evidence_quote"] == ""
    assert entry["page"] is None
    assert any(f.startswith("PARTIAL_COVERAGE_CANDIDATES_SEEN=") for f in entry["review_flags"])
    assert result["governed_exceptions"] == []


def test_p5_real_replay_judgment_mode_never_emits_gap(monkeypatch, isolated_review_queue):
    """P5 (ALCOA_CONTEMPORANEOUS) real: mismo pasaje de audit trail que P1
    (rescatado), mismo chunk limpio (rank 1 BM25/2 fusión) -- pero el 7B
    sigue sin reconocerlo NI con el pool perfecto (PILOT_EXECUTION-2026-012).
    Confirma que el blindaje de §2 protege exactamente el caso que lo
    motivó: cobertura parcial nunca cierra un gap."""
    raw_payloads = json.loads(
        (_FIXTURES_DIR / "p5_alcoa_contemporaneous_raw_payloads.json").read_text(encoding="utf-8"))
    per_unit_text = _candidate_pool_texts(_P5_CHUNK_ORDER)

    monkeypatch.setattr(ollama_client, "generate", _sequential_generate_mock(raw_payloads))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", per_unit_text,
        "Rockwell", "RW-0005", "1.2", str(_RW_0005), "sha-test",
        run_context="production", use_verified_pipeline=True, document_type="FS",
        retry_technical_failures=True, evaluation_profile="H2H4",
        target_requirement_ids=["ALCOA_CONTEMPORANEOUS"], full_document_coverage=False,
    )

    c = result["verified_conclusions"]["ALCOA_CONTEMPORANEOUS"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert c["conclusion"] not in ("PROVISIONAL_GAP", "DOCUMENTATION_GAP")
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c["review_flags"]

    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "ALCOA_CONTEMPORANEOUS"]
    assert len(matches) == 1
    entry = matches[0]["summary"]
    assert entry["conclusion"] == "EVIDENCE_NOT_LOCATED_IN_CANDIDATES"
    assert entry["evidence_quote"] == ""
    assert result["governed_exceptions"] == []
