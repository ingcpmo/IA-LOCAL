"""FASE M3 (`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`) -- `corpus_runner.
run_corpus_batch(retrieval_mode=...)`. Cero llamadas reales a Ollama ni a
embeddings en este archivo: `evaluate_chunked`/`build_fusion_candidate_
pool`/`run_embed_batch` están mockeados -- lo que se prueba es el
CABLEADO (qué se llama, con qué argumentos, en qué orden, qué detiene el
lote antes de gastar), no el recall en sí. El recall real de
`build_fusion_candidate_pool` (la misma función que aquí se mockea) ya
está medido end-to-end en `docs_plan/V1_RECALL_SECTION_AWARE_CHUNKING_
RESULTADO.md` (7/7, camino real, sin mocks) -- este archivo prueba que
`run_corpus_batch` reproduce EXACTAMENTE esa llamada, no vuelve a medir
recall gastando presupuesto de nuevo."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.regulatory import corpus_runner as runner

# Capturada ANTES de que cualquier fixture la mockee (ver _isolate mas abajo)
# -- unica forma de restaurar la resolucion REAL de JUDGMENT_EXECUTION en el
# test que necesita ejercitarla de verdad, sin duplicar su logica aqui.
_REAL_SELECT_JUDGMENT_EXECUTION_INSTANCE = runner._select_judgment_execution_instance
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.retrieval import embed_index, embed_runner, indexer, judgment_candidate_pool as jcp


class FakeCorpusProvider:
    @property
    def model_name(self):
        return "modelo-test-m3"

    @property
    def context_window(self):
        return 16384

    def show_digest(self):
        return "digest-m3"

    def runtime_version(self):
        return "test-0.0.0"


class _AuthorizedScope:
    def __init__(self, authorized=True, covering_instances=("INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


def _unit(document_id="DOC-1", agent_id="fda_part11_agent"):
    return runner.CorpusRunUnit(
        document_id=document_id, document_type="FS",
        document_path=runner.PROMPTS_DIR, document_sha256="0" * 64, agent_id=agent_id,
        prompt_path=runner._PROMPT_PATH_BY_AGENT[agent_id], expected_calls=1,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(runner, "DEFAULT_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _AuthorizedScope())
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 999, "hard_stop_wall_time_hours": 999.0,
    })
    # Bloque 2 (docs_plan/PASOA_RESOLUCION_K_Y_HARDSTOP.md): default
    # generoso para no interferir con los tests que no ejercitan el techo
    # de JUDGMENT_EXECUTION en si -- los que SI lo hacen sobreescriben esto
    # localmente con su propio monkeypatch.
    monkeypatch.setattr(runner, "_select_judgment_execution_instance", lambda *a, **k: {
        "selected_instance_id": "JUDGMENT_EXECUTION-test-default", "payload": {"max_calls": 999},
    })


def _run(units, tmp_path, **kw):
    return runner.run_corpus_batch(
        units, provider=FakeCorpusProvider(),
        checkpoint_dir=tmp_path / "ckpt", manifest_dir=tmp_path / "manifest", **kw)


# ---------------------------------------------------------------------------
# full_chunk (default): cero cambio de comportamiento
# ---------------------------------------------------------------------------

def test_retrieval_mode_default_is_full_chunk_and_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto." * 20])
    captured = {}

    def _fake_evaluate_chunked(*a, **kw):
        captured.update(kw)
        return {
            "run_id": "run-1", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
            "technical_execution_failures": [],
        }

    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    summary = _run([_unit()], tmp_path, run_context="validation")
    assert summary.retrieval_mode == "full_chunk"
    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert "retrieval_mode" not in captured  # el llamador de siempre no lo pasa


def test_top_k_fusion_never_activates_implicitly():
    import inspect
    sig = inspect.signature(runner.run_corpus_batch)
    assert sig.parameters["retrieval_mode"].default == "full_chunk"


# ---------------------------------------------------------------------------
# preflight de EMBED_EXECUTION -- nunca gasta una llamada de juicio si no
# hay presupuesto de embedding suficiente para el lote completo
# ---------------------------------------------------------------------------

def test_top_k_fusion_hard_stops_before_any_judgment_call_if_embed_budget_insufficient(
        monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 100, "max_calls": 60, "remaining": 10, "fits": False,
        "selected_embed_instance_id": "EMBED_EXECUTION-2026-002",
        "per_document_pending_chunks": {}, "unique_query_pairs": 0,
    })
    judgment_calls = {"n": 0}
    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", lambda *a, **kw: judgment_calls.__setitem__(
        "n", judgment_calls["n"] + 1))

    summary = _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")

    assert summary.stop_reason == "HARD_STOP_EMBED_CALLS"
    assert summary.units[0].status == "NOT_STARTED_HARD_STOP"
    assert judgment_calls["n"] == 0, "ninguna llamada de juicio si el preflight de embedding no cabe"


def test_preflight_embed_budget_fits_when_needed_within_remaining(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})
    monkeypatch.setattr(embed_index, "chunks_pending_embedding", lambda sha, **k: [1, 2, 3])
    monkeypatch.setattr(embed_runner, "_select_embed_execution_instance", lambda doc_ids, **k: {
        "selected_instance_id": "EMBED_EXECUTION-2026-002", "payload": {"max_calls": 60},
    })
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(e)", "label": "x"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    result = runner._preflight_embed_budget([_unit()], calls_already_used_for_embed=10)
    assert result["needed"] == 4  # 3 chunks pendientes + 1 consulta unica
    assert result["remaining"] == 50
    assert result["fits"] is True


def test_preflight_embed_budget_does_not_fit_when_needed_exceeds_remaining(monkeypatch):
    monkeypatch.setattr(indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})
    monkeypatch.setattr(embed_index, "chunks_pending_embedding", lambda sha, **k: list(range(55)))
    monkeypatch.setattr(embed_runner, "_select_embed_execution_instance", lambda doc_ids, **k: {
        "selected_instance_id": "EMBED_EXECUTION-2026-002", "payload": {"max_calls": 60},
    })
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(e)", "label": "x"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    result = runner._preflight_embed_budget([_unit()], calls_already_used_for_embed=10)
    assert result["fits"] is False


# ---------------------------------------------------------------------------
# cableado real de una unidad en modo top_k_fusion
# ---------------------------------------------------------------------------

def test_top_k_fusion_calls_evaluate_chunked_once_per_admitted_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-2026-002",
        "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(a)", "label": "a"}, {"req_id": "21_CFR_11.10(d)", "label": "d"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    pool_by_req = {
        "21_CFR_11.10(a)": [{"chunk_index": 0, "page_start": 46, "page_end": 46, "text": "evidencia a"}],
        "21_CFR_11.10(d)": [{"chunk_index": 1, "page_start": 40, "page_end": 40, "text": "evidencia d"}],
    }
    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool",
                        lambda doc_id, sha, req_id, **k: pool_by_req[req_id])

    captured_calls = []

    def _fake_evaluate_chunked(*a, **kw):
        captured_calls.append(kw)
        return {
            "run_id": f"run-{len(captured_calls)}", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
            "technical_execution_failures": [],
        }

    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    summary = _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")

    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert len(captured_calls) == 2  # 1 por requirement_id admitido
    assert summary.units[0].status == "COMPLETED"
    assert summary.units[0].run_ids == ["run-1", "run-2"]

    for kw, req_id in zip(captured_calls, ["21_CFR_11.10(a)", "21_CFR_11.10(d)"]):
        assert kw["full_document_coverage"] is False
        assert kw["evaluation_profile"] == "H2H4"
        assert kw["target_requirement_ids"] == [req_id]
        assert kw["retrieval_mode"] == "top_k_fusion"
        assert kw["per_unit_text"] == [c["text"] for c in pool_by_req[req_id]]
        assert kw["candidate_metadata"] == pool_by_req[req_id]
        assert kw["page_numbers"] == [c["page_start"] for c in pool_by_req[req_id]]


# ---------------------------------------------------------------------------
# Bloque 1 (docs_plan/CIERRE_PENDIENTES_PASO_B_Y_GATE_PRODUCCION.md): retry
# de fallos tecnicos NO-truncamiento dentro de top_k_fusion -- replay del
# caso real (RW-0005/alcoa_plus_agent/ALCOA_ATTRIBUTABLE,
# chunked-ef211e17236b, failure_reason=schema_validation_failed) que
# quedo contenido pero nunca reintentado en Paso A.
# ---------------------------------------------------------------------------

_REAL_SCHEMA_FAILURE_CHECKPOINT = Path(
    "factory/regulatory/corpus_run/checkpoints/chunked-ef211e17236b.checkpoint.json")


def _load_real_schema_failure_raw() -> str | None:
    """Lee el raw real persistido del intento tecnico fallido -- runtime
    local, nunca en Git (mismo regimen que W5.3 Fase 5.4.4); si no existe
    en este entorno, el test que lo usa se salta explicitamente."""
    if not _REAL_SCHEMA_FAILURE_CHECKPOINT.is_file():
        return None
    ckpt = json.loads(_REAL_SCHEMA_FAILURE_CHECKPOINT.read_text())
    ce0 = ckpt["chunk_executions"][0]
    assert ce0["failure_reason"] == "schema_validation_failed"
    rel_path = ce0["raw_response_full_path"]
    full_path = _REAL_SCHEMA_FAILURE_CHECKPOINT.parent / rel_path
    if not full_path.is_file():
        return None
    import gzip
    with gzip.open(full_path, "rt", encoding="utf-8") as f:
        return f.read()


def test_technical_failure_retried_immediately_within_the_same_requirement(monkeypatch, tmp_path):
    """Replay del fallo tecnico real: la respuesta cruda real (schema
    invalido) en el primer intento, una respuesta valida en el reintento
    -- confirma que _run_unit_top_k_fusion() ahora SI dispara ese segundo
    intento (antes: quedaba contenido en rejected_by_verifier para
    siempre, nunca reintentado) y que el costo de AMBOS intentos se suma,
    nunca se pierde."""
    real_raw = _load_real_schema_failure_raw()
    if real_raw is None:
        pytest.skip("evidencia real de Paso A no presente en este entorno -- runtime local, no en Git")

    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-test",
        "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "ALCOA_ATTRIBUTABLE", "label": "a"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool", lambda doc_id, sha, req_id, **k: [
        {"chunk_index": 0, "page_start": 12, "page_end": 12, "text": "evidencia real"}])

    # Primer intento: la respuesta cruda REAL que fallo validacion de
    # schema. Reintento: una respuesta valida sintetica (el reintento en
    # si nunca corrio en produccion -- el fix es posterior a Paso A).
    calls = {"n": 0}

    def _fake_evaluate_chunked(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "run_id": "run-real-failure", "chunk_executions": [{"chunk_index": 0}],
                "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
                "technical_execution_failures": [
                    {"chunk_index": 0, "task_id": "task-23358ad39227", "error": real_raw[:80]}],
            }
        return {
            "run_id": "run-real-failure", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {"resumed_chunk_count": 1, "retried_chunk_indices": [0]},
            "technical_execution_failures": [],
        }

    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    outcome, _ = runner._run_unit_top_k_fusion(
        _unit(document_id="RW-0005", agent_id="alcoa_plus_agent"),
        checkpoint_store=None, provider=None, calls_already_used_for_embed=0,
        decision_store_file=None, run_context="production",
    )

    assert calls["n"] == 2, "debe reintentar exactamente una vez tras el fallo tecnico"
    assert outcome.status == "COMPLETED"
    assert outcome.technical_execution_failures == 0, (
        "tras el reintento exitoso, 0 fallos pendientes -- antes de este fix quedaba en 1 para siempre"
    )
    assert outcome.run_ids == ["run-real-failure"], "el reintento resuelve el MISMO run_id, no crea uno nuevo"
    assert outcome.calls_made_this_invocation == 2, (
        "el costo del primer intento (1 llamada real, aunque fallara) y del reintento "
        "(1 llamada real) se suman -- nunca se pierde el primero"
    )


def test_technical_failure_stays_rejected_if_the_retry_also_fails(monkeypatch, tmp_path):
    """Si el reintento TAMBIEN falla, sigue contenido (rejected_by_
    verifier), nunca fabricado -- mismo criterio que antes del fix, solo
    que ahora se le dio una oportunidad real de resolverse primero."""
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-test",
        "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "ALCOA_ATTRIBUTABLE", "label": "a"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool", lambda doc_id, sha, req_id, **k: [
        {"chunk_index": 0, "page_start": 12, "page_end": 12, "text": "evidencia real"}])

    calls = {"n": 0}

    def _fake_evaluate_chunked(*a, **kw):
        calls["n"] += 1
        return {
            "run_id": "run-still-failing", "chunk_executions": [{"chunk_index": 0}],
            "preflight_metadata": {
                "resumed_chunk_count": 0 if calls["n"] == 1 else 1,
                "retried_chunk_indices": [] if calls["n"] == 1 else [0],
            },
            "technical_execution_failures": [{"chunk_index": 0, "task_id": "t", "error": "sigue fallando"}],
        }

    monkeypatch.setattr(runner.ce, "evaluate_chunked", _fake_evaluate_chunked)

    outcome, _ = runner._run_unit_top_k_fusion(
        _unit(document_id="RW-0005", agent_id="alcoa_plus_agent"),
        checkpoint_store=None, provider=None, calls_already_used_for_embed=0,
        decision_store_file=None, run_context="production",
    )

    assert calls["n"] == 2, "se intenta el reintento exactamente una vez, nunca en bucle"
    assert outcome.status == "COMPLETED", "la unidad no aborta -- el fallo queda contenido, no fabricado"
    assert outcome.technical_execution_failures == 1, "sigue sin resolverse tras el unico reintento -- honesto"


def test_top_k_fusion_hard_stops_if_chunk_embedding_batch_did_not_complete(monkeypatch, tmp_path):
    """Defensa en profundidad: aunque el preflight del LOTE haya dicho que
    cabe, si `run_embed_batch` de una unidad concreta reporta
    HARD_STOP_CALLS (p.ej. por una reconciliación manual desactualizada),
    la unidad falla explícito -- nunca sigue con un candidate pool
    construido sobre chunks sin embeddings completos."""
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "x", "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 5
        stop_reason = "HARD_STOP_CALLS"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())

    with pytest.raises(runner.EmbedBudgetInsufficientError):
        _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")


# ---------------------------------------------------------------------------
# Bloque 2 (docs_plan/PASOA_RESOLUCION_K_Y_HARDSTOP.md): techo REAL de
# llamadas de JUICIO bajo top_k_fusion, resuelto contra JUDGMENT_EXECUTION
# -- D4-A (hard_stop_calls) mide otra formula de costo y no debe ser el
# unico control (ese fue exactamente el hueco que dejo pasar las 149
# llamadas reales de Paso A).
# ---------------------------------------------------------------------------

def test_judgment_execution_gates_top_k_fusion_before_any_real_call(monkeypatch, tmp_path):
    """Sin JUDGMENT_EXECUTION vigente que cubra el lote, top_k_fusion falla
    cerrado ANTES de cualquier llamada real -- mismo principio que
    EMBED_EXECUTION/CORPUS_AUTHORIZATION."""
    monkeypatch.setattr(runner, "_select_judgment_execution_instance",
                        _REAL_SELECT_JUDGMENT_EXECUTION_INSTANCE)  # restaura la resolucion real
    monkeypatch.setattr(resolver, "resolve", lambda family, doc_id, **k: (
        _AuthorizedScope() if family != "JUDGMENT_EXECUTION"
        else _AuthorizedScope(authorized=False, denial_reason="sin JUDGMENT_EXECUTION firmada")
    ))
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "x", "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    calls = {"n": 0}
    monkeypatch.setattr(runner, "_run_unit_top_k_fusion",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))

    with pytest.raises(runner.JudgmentExecutionNotAuthorizedError):
        _run([_unit()], tmp_path, retrieval_mode="top_k_fusion")
    assert calls["n"] == 0, "cero llamadas reales -- el guard corre antes que cualquier unidad"


def test_judgment_hard_stop_calls_stops_before_the_call_that_would_exceed_it(monkeypatch, tmp_path):
    """Escenario sintetico donde el conteo real superaria el techo
    aprobado: 2 unidades, la primera cabe exacto (5/5), la segunda (1 mas)
    ya no -- el runner debe detenerse ANTES de arrancar la segunda unidad,
    nunca a mitad ni despues."""
    monkeypatch.setattr(runner, "_select_judgment_execution_instance", lambda *a, **k: {
        "selected_instance_id": "JUDGMENT_EXECUTION-test-tight", "payload": {"max_calls": 5},
    })
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 0, "max_calls": 60, "remaining": 60, "fits": True,
        "selected_embed_instance_id": "x", "per_document_pending_chunks": {}, "unique_query_pairs": 0,
    })
    expected_by_doc = {"DOC-1": 5, "DOC-2": 1}
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion",
                        lambda unit, **k: expected_by_doc[unit.document_id])

    started_units = []

    def _fake_run_unit(unit, **kw):
        started_units.append(unit.document_id)
        outcome = runner.UnitOutcome(
            document_id=unit.document_id, agent_id=unit.agent_id, status="COMPLETED",
            calls_made_this_invocation=expected_by_doc[unit.document_id], run_ids=["run-x"])
        return outcome, kw["calls_already_used_for_embed"]

    monkeypatch.setattr(runner, "_run_unit_top_k_fusion", _fake_run_unit)

    units = [_unit(document_id="DOC-1"), _unit(document_id="DOC-2")]
    summary = _run(units, tmp_path, retrieval_mode="top_k_fusion")

    assert started_units == ["DOC-1"], "DOC-2 nunca debe arrancar -- excederia el techo aprobado"
    assert summary.stop_reason == "HARD_STOP_JUDGMENT_CALLS"
    assert summary.total_calls_made == 5
    assert summary.judgment_execution_id == "JUDGMENT_EXECUTION-test-tight"
    assert summary.judgment_hard_stop_calls == 5
    assert summary.units[-1].status == "NOT_STARTED_HARD_STOP"
    assert summary.units[-1].document_id == "DOC-2"


def test_d4a_never_stops_a_top_k_fusion_run_under_its_own_judgment_ceiling(monkeypatch, tmp_path):
    """Bloque 2 (docs_plan/CIERRE_PENDIENTES_PASO_B_Y_GATE_PRODUCCION.md):
    reproduce EXACTAMENTE el escenario real detectado -- 300 llamadas de
    juicio necesarias bajo top_k_fusion, JUDGMENT_EXECUTION autorizada
    para 300, D4-A (otra formula de costo) calculando solo 205 para el
    mismo lote. El runner NO debe detenerse en 205 -- D4-A no gobierna
    top_k_fusion."""
    monkeypatch.setattr(runner, "_select_judgment_execution_instance", lambda *a, **k: {
        "selected_instance_id": "JUDGMENT_EXECUTION-test-300", "payload": {"max_calls": 300},
    })
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 0, "max_calls": 60, "remaining": 60, "fits": True,
        "selected_embed_instance_id": "x", "per_document_pending_chunks": {}, "unique_query_pairs": 0,
    })
    # Mismo D4-A real que el escenario detectado: 205 para este lote,
    # bajo la formula de full_chunk -- deliberadamente MENOR que las 300
    # llamadas reales que top_k_fusion necesita.
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 205, "hard_stop_wall_time_hours": 999.0,
    })
    expected_by_doc = {"DOC-1": 150, "DOC-2": 150}  # suma 300 > 205 (D4-A) pero <= 300 (judgment)
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion",
                        lambda unit, **k: expected_by_doc[unit.document_id])

    started_units = []

    def _fake_run_unit(unit, **kw):
        started_units.append(unit.document_id)
        outcome = runner.UnitOutcome(
            document_id=unit.document_id, agent_id=unit.agent_id, status="COMPLETED",
            calls_made_this_invocation=expected_by_doc[unit.document_id], run_ids=["run-x"])
        return outcome, kw["calls_already_used_for_embed"]

    monkeypatch.setattr(runner, "_run_unit_top_k_fusion", _fake_run_unit)

    units = [_unit(document_id="DOC-1"), _unit(document_id="DOC-2")]
    summary = _run(units, tmp_path, retrieval_mode="top_k_fusion")

    assert started_units == ["DOC-1", "DOC-2"], "ambas unidades deben arrancar -- D4-A no debe cortar aqui"
    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert summary.total_calls_made == 300
    assert summary.total_calls_made > 205, "confirma que SI se supero el techo (equivocado) de D4-A sin detenerse"


def test_d4a_still_governs_full_chunk_runs_unchanged(monkeypatch, tmp_path):
    """2.4: D4-A no se retira, solo se acota -- una corrida full_chunk
    sigue deteniendose en su techo real, sin cambio de comportamiento."""
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 0, "hard_stop_wall_time_hours": 999.0,
    })
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto." * 20])
    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())
    calls = {"n": 0}
    monkeypatch.setattr(runner.ce, "evaluate_chunked", lambda *a, **kw: calls.__setitem__("n", calls["n"] + 1))

    summary = _run([_unit(document_id="DOC-1"), _unit(document_id="DOC-2")], tmp_path,
                   run_context="validation")  # retrieval_mode default = full_chunk

    assert summary.stop_reason == "HARD_STOP_CALLS", "full_chunk sigue gobernado por D4-A, sin cambios"
    assert calls["n"] == 0, "hard_stop_calls=0 debe bloquear incluso la primera unidad (expected_calls=1 > 0)"


# ---------------------------------------------------------------------------
# fingerprint: un checkpoint top_k_fusion nunca se confunde con full_chunk
# ---------------------------------------------------------------------------

def test_fingerprint_differs_between_retrieval_modes():
    meta = {"prompt_version": "1.0.0", "schema_version": "checkpoint_llm_response_v1"}
    common = dict(model_digest="d", document_sha256="s" * 64, agent_version="v1", use_verified_pipeline=True)
    fp_full = ce.build_run_fingerprint(meta, **common, retrieval_mode="full_chunk")
    fp_topk = ce.build_run_fingerprint(meta, **common, retrieval_mode="top_k_fusion")
    assert fp_full != fp_topk
    assert fp_full["retrieval_mode"] == "full_chunk"
    assert fp_topk["retrieval_mode"] == "top_k_fusion"


def test_fingerprint_default_retrieval_mode_is_full_chunk_backward_compatible():
    meta = {"prompt_version": "1.0.0", "schema_version": "checkpoint_llm_response_v1"}
    fp = ce.build_run_fingerprint(
        meta, model_digest="d", document_sha256="s" * 64, agent_version="v1",
        use_verified_pipeline=True)
    assert fp["retrieval_mode"] == "full_chunk"


# ---------------------------------------------------------------------------
# Bloque 3 (docs_plan/DISENO_UNIFICACION_RUNNER_FORMAL.md): configuracion
# efectiva registrada en CorpusRunSummary/manifest ANTES de la primera
# llamada real -- lo que fase5_produccion_real_fixture7p2n_20260820 no dejo
# verificable.
# ---------------------------------------------------------------------------

def test_manifest_registra_configuracion_efectiva_bloque3(monkeypatch, tmp_path):
    """Cubre las dos ramas reales de evaluation_profile (BASELINE via
    full_chunk, H2H4 via top_k_fusion) y confirma que summary Y el
    manifest.json persistido coinciden campo a campo -- nunca solo uno de
    los dos."""
    monkeypatch.setattr(mqg, "evaluate_model_qualification",
                        lambda *a, **k: type("R", (), {"status": mqg.STATUS_QUALIFIED})())

    # --- rama full_chunk (BASELINE) ---
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto." * 20])
    monkeypatch.setattr(runner.ce, "evaluate_chunked", lambda *a, **kw: {
        "run_id": "run-full", "chunk_executions": [{"chunk_index": 0}],
        "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
        "technical_execution_failures": [],
    })

    summary_full = _run([_unit()], tmp_path, run_context="validation")

    assert summary_full.evaluation_profile == "BASELINE"
    assert summary_full.retrieval_mode == "full_chunk"
    assert summary_full.run_context == "validation"
    assert summary_full.corpus_authorization_id == "INST-1"  # _AuthorizedScope de este archivo
    assert summary_full.model_qualification_status == mqg.STATUS_QUALIFIED
    assert summary_full.requirement_scope == {
        "DOC-1::fda_part11_agent": runner._admitted_requirement_ids(
            runner._PROMPT_PATH_BY_AGENT["fda_part11_agent"])
    }
    assert summary_full.truncation_retry_multiplier == ce.TRUNCATION_RETRY_MULTIPLIER

    manifest_full = json.loads(Path(summary_full.manifest_path).read_text())
    assert manifest_full["engine"] == "CURRENT"
    assert manifest_full["evaluation_profile"] == "BASELINE"
    assert manifest_full["retrieval_mode"] == "full_chunk"
    assert manifest_full["run_context"] == "validation"
    assert manifest_full["corpus_authorization_id"] == "INST-1"
    assert manifest_full["model_qualification_status"] == mqg.STATUS_QUALIFIED
    assert manifest_full["requirement_scope"] == summary_full.requirement_scope
    assert manifest_full["truncation_retry_multiplier"] == ce.TRUNCATION_RETRY_MULTIPLIER

    # --- rama top_k_fusion (H2H4) -- run_context='production' a proposito:
    # es la UNICA combinacion que el guard del Bloque 2 admite en produccion,
    # y es la que realmente importa demostrar (evaluation_profile='H2H4'
    # persistido para la corrida formal real, no solo para diagnostico).
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 1, "max_calls": 60, "remaining": 50, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-2026-002",
        "per_document_pending_chunks": {}, "unique_query_pairs": 1,
    })
    monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 1)

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-x"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner.ce, "load_prompt_meta", lambda p: {"checkpoints": [
        {"req_id": "21_CFR_11.10(a)", "label": "a"}]})
    monkeypatch.setattr(runner.ce, "evidence_pack_gate", lambda meta: (meta["checkpoints"], []))

    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool", lambda doc_id, sha, req_id, **k: [
        {"chunk_index": 0, "page_start": 46, "page_end": 46, "text": "evidencia a"}])

    monkeypatch.setattr(runner.ce, "evaluate_chunked", lambda *a, **kw: {
        "run_id": "run-topk", "chunk_executions": [{"chunk_index": 0}],
        "preflight_metadata": {"resumed_chunk_count": 0, "retried_chunk_indices": []},
        "technical_execution_failures": [],
    })

    summary_topk = _run([_unit(document_id="DOC-2")], tmp_path,
                        run_context="production", retrieval_mode="top_k_fusion")

    assert summary_topk.evaluation_profile == "H2H4"
    assert summary_topk.retrieval_mode == "top_k_fusion"
    assert summary_topk.run_context == "production"
    assert summary_topk.corpus_authorization_id == "INST-1"
    assert summary_topk.model_qualification_status == mqg.STATUS_QUALIFIED
    assert summary_topk.requirement_scope == {"DOC-2::fda_part11_agent": ["21_CFR_11.10(a)"]}
    assert summary_topk.truncation_retry_multiplier == ce.TRUNCATION_RETRY_MULTIPLIER

    manifest_topk = json.loads(Path(summary_topk.manifest_path).read_text())
    assert manifest_topk["engine"] == "CURRENT"
    assert manifest_topk["evaluation_profile"] == "H2H4"
    assert manifest_topk["retrieval_mode"] == "top_k_fusion"
    assert manifest_topk["run_context"] == "production"
    assert manifest_topk["corpus_authorization_id"] == "INST-1"
    assert manifest_topk["model_qualification_status"] == mqg.STATUS_QUALIFIED
    assert manifest_topk["requirement_scope"] == summary_topk.requirement_scope
    assert manifest_topk["truncation_retry_multiplier"] == ce.TRUNCATION_RETRY_MULTIPLIER
