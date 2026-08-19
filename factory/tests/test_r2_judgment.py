"""
R2 -- fase de JUICIO (`factory/regulatory/retrieval/judgment.py`,
`.claude/plans/sharded-riding-turing.md`, 2026-08-09). Ollama SIEMPRE
mockeado (`FakeCorpusProvider`, mismo patrón que `test_corpus_runner.py`/
`test_pilot_isolation.py`) -- ninguna llamada real en esta suite.

Reutiliza la MISMA gobernanza de `run_pilot_sample_batch`
(`_select_pilot_execution_instance`/`model_qualification_gate`), así que
los tests de gobernanza (familia PILOT_EXECUTION, hard-stop por
max_calls) siguen el mismo patrón de aislamiento que
`test_pilot_isolation.py` -- no se duplica la lógica, se prueba que
`judgment.py` la INVOCA correctamente."""
from __future__ import annotations

import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.retrieval import judgment
from factory.tests.test_corpus_runner import FakeCorpusProvider


class _Scope:
    def __init__(self, authorized=True, covering_instances=("PILOT-INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


def _candidate(text: str, chunk_index=0, page_start=1, page_end=1) -> dict:
    return {"chunk_index": chunk_index, "page_start": page_start, "page_end": page_end,
            "text": text, "bm25_score": 1.0}


def _unit(requirement_id="21_CFR_11.10(e)", document_id="RW-0011", agent_id="fda_part11_agent",
          n_candidates=1, chars_per_candidate=200):
    candidates = [_candidate(("Texto real de prueba. " * (chars_per_candidate // 22))[:chars_per_candidate],
                              chunk_index=i, page_start=i + 1, page_end=i + 1)
                  for i in range(n_candidates)]
    return judgment.JudgmentUnit(document_id=document_id, document_type="DS", agent_id=agent_id,
                                  requirement_id=requirement_id, candidate_chunks=candidates,
                                  selection_reason="fixture de test, no un caso real")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(judgment, "_write_judgment_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(judgment, "_resolve_document_path",
                        lambda doc_id: (runner.PROMPTS_DIR, "0" * 64))


def _authorize(monkeypatch, *, max_calls=60, authorized=True, denial_reason=None):
    def fake_resolve(family, target_id, *, store_file=None):
        assert family == "PILOT_EXECUTION", (
            f"run_judgment_batch consultó la familia {family!r}, no PILOT_EXECUTION")
        return _Scope(authorized=authorized, denial_reason=denial_reason)
    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1",
         "payload": {"max_calls": max_calls, "authorizes_corpus": False,
                     "authorizes_baseline": False}},
    ])


def _run(units, tmp_path, provider=None, **kw):
    kwargs = {"checkpoint_dir": tmp_path / "ckpt"}
    kwargs.update(kw)
    return judgment.run_judgment_batch(units, provider=provider or FakeCorpusProvider(), **kwargs)


# ===========================================================================
# 1. expected_calls_for_unit -- dry-run determinista, sin LLM
# ===========================================================================

def test_expected_calls_for_unit_counts_real_chunking_not_len_candidates():
    """El costo real depende de build_page_chunks() del texto YA
    recuperado -- no siempre es 1:1 con len(candidate_chunks) (motivo
    documentado en el plan: los chunks recuperados casi no consolidan al
    volver a chunkear, pero esto lo confirma el propio cálculo, no una
    suposición)."""
    unit_small = _unit(n_candidates=1, chars_per_candidate=100)
    assert judgment.expected_calls_for_unit(unit_small) == 1

    unit_empty = _unit(n_candidates=0)
    assert judgment.expected_calls_for_unit(unit_empty) == 0


# ===========================================================================
# 2. Gobernanza: familia PILOT_EXECUTION, nunca CORPUS_AUTHORIZATION/D4
# ===========================================================================

def test_judgment_batch_consulta_solo_pilot_execution(monkeypatch, tmp_path):
    _authorize(monkeypatch)
    summary = _run([_unit()], tmp_path)
    assert summary.stop_reason == "BATCH_COMPLETE"
    assert summary.units[0].status == "COMPLETED"
    assert summary.selected_pilot_instance_id == "PILOT-INST-1"


def test_judgment_batch_bloqueado_sin_pilot_execution_firmada(monkeypatch):
    _authorize(monkeypatch, authorized=False, denial_reason="PILOT_EXECUTION no firmada")
    with pytest.raises(runner.CorpusRunNotAuthorizedError, match="PILOT_EXECUTION"):
        judgment.run_judgment_batch([_unit()], provider=FakeCorpusProvider())


def test_judgment_batch_sin_max_calls_valido_bloquea(monkeypatch):
    _authorize(monkeypatch)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1", "payload": {"authorizes_corpus": False}},
    ])
    with pytest.raises(runner.CorpusRunNotAuthorizedError, match="max_calls"):
        judgment.run_judgment_batch([_unit()], provider=FakeCorpusProvider())


# ===========================================================================
# 3. Hard-stop por presupuesto -- calculado ANTES de gastar la llamada
# ===========================================================================

def test_hard_stop_antes_de_exceder_max_calls(monkeypatch, tmp_path):
    _authorize(monkeypatch, max_calls=1)
    units = [_unit(document_id="RW-0011", n_candidates=1),
             _unit(document_id="RW-0012", n_candidates=1)]
    summary = _run(units, tmp_path)
    assert summary.stop_reason == "HARD_STOP_CALLS"
    assert summary.units[0].status == "COMPLETED"
    assert summary.units[1].status == "NOT_STARTED_HARD_STOP"
    assert summary.total_calls_made == 1


def test_unidad_sin_candidatos_falla_sin_gastar_presupuesto(monkeypatch, tmp_path):
    _authorize(monkeypatch, max_calls=60)
    summary = _run([_unit(n_candidates=0)], tmp_path)
    assert summary.units[0].status == "FAILED"
    assert "vacío" in summary.units[0].error
    assert summary.total_calls_made == 0


# ===========================================================================
# 4. Resultado: chunk_observation/conclusion reales, no inventados
# ===========================================================================

def test_completed_unit_reports_chunk_observation_from_verified_conclusions(monkeypatch, tmp_path):
    """Ollama mockeado responde 'evidencia_insuficiente' para un req_id
    ('generic') que no coincide con el target real -- chunk_observation
    debe reflejar 'no observado', no asumir 'observed' porque la llamada
    terminó bien."""
    _authorize(monkeypatch, max_calls=60)
    summary = _run([_unit(requirement_id="21_CFR_11.10(e)")], tmp_path)
    outcome = summary.units[0]
    assert outcome.status == "COMPLETED"
    assert outcome.chunk_observation == "not_observed_in_chunk"
    assert outcome.run_id is not None


# ===========================================================================
# 4.1 Hallazgo A (VERIFICACION_ACOTADA_20260818/PAQUETE_1): page_numbers
# reales del pool de candidatos, no el fallback 1..N por posicion.
# ===========================================================================

def test_page_numbers_passed_are_the_real_candidate_page_starts(monkeypatch, tmp_path):
    """Antes del fix, evaluate_chunked() no recibia page_numbers -- para
    un candidate pool (no el documento completo), build_page_chunks()
    caia al fallback 1..N por posicion dentro del pool, no la pagina real
    del documento. Con 3 candidatos de paginas [5, 5, 12] (no
    contiguas/no 1..N), page_numbers debe reflejar exactamente eso."""
    _authorize(monkeypatch, max_calls=60)
    captured = {}
    real_evaluate_chunked = ce.evaluate_chunked

    def _spy(*args, **kwargs):
        captured["page_numbers"] = kwargs.get("page_numbers")
        return real_evaluate_chunked(*args, **kwargs)

    monkeypatch.setattr(ce, "evaluate_chunked", _spy)
    unit = judgment.JudgmentUnit(
        document_id="RW-0011", document_type="DS", agent_id="fda_part11_agent",
        requirement_id="21_CFR_11.10(e)",
        candidate_chunks=[
            _candidate("texto candidato uno " * 10, chunk_index=0, page_start=5, page_end=5),
            _candidate("texto candidato dos " * 10, chunk_index=7, page_start=5, page_end=5),
            _candidate("texto candidato tres " * 10, chunk_index=20, page_start=12, page_end=12),
        ],
        selection_reason="fixture de test, no un caso real")
    _run([unit], tmp_path)
    assert captured["page_numbers"] == [5, 5, 12]


# ===========================================================================
# 5. progress_file -- estado incremental por unidad, sin esperar el batch completo
# ===========================================================================

def test_progress_file_gets_one_line_per_unit_as_it_completes(monkeypatch, tmp_path):
    _authorize(monkeypatch, max_calls=60)
    progress_file = tmp_path / "progress.jsonl"
    units = [_unit(document_id="RW-0011"), _unit(document_id="RW-0012")]
    summary = _run(units, tmp_path, progress_file=progress_file)

    lines = progress_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["document_id"] == "RW-0011"
    assert first["status"] == "COMPLETED"
    second = json.loads(lines[1])
    assert second["document_id"] == "RW-0012"


def test_progress_file_records_hard_stop_unit_too(monkeypatch, tmp_path):
    _authorize(monkeypatch, max_calls=1)
    progress_file = tmp_path / "progress.jsonl"
    units = [_unit(document_id="RW-0011"), _unit(document_id="RW-0012")]
    _run(units, tmp_path, progress_file=progress_file)

    lines = [json.loads(l) for l in progress_file.read_text(encoding="utf-8").strip().splitlines()]
    assert lines[1]["status"] == "NOT_STARTED_HARD_STOP"
