"""
Reintento dirigido de chunks con technical_execution_failure al reanudar, y
propagacion del flag provisional a la rama `no_cumple` (defecto D-5).

Ambos salen del post-mortem de la corrida fsv12_reeval_20260727
(factory/docs/W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md):

  - Sin reintento dirigido, un fallo tecnico es PERMANENTE: el chunk ya
    figura en chunk_executions y start_index lo salta. Un error de
    configuracion obligaba a descartar la corrida entera.
  - La rama `no_cumple` emitia un incumplimiento MAYOR sin marcarlo
    provisional aunque hubiera chunks fallidos, a diferencia de la rama
    contigua. Latente en esa corrida, real igual.

Providers falsos deterministas -- nunca llama a Ollama real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPT_PATH = Path(ce.__file__).parent / "prompts" / "part11_prompts.yaml"

# Dos paginas que superan CHUNK_MAX_CHARS para garantizar DOS chunks reales
# separados (misma leccion que la Fase G: paginas cortas se fusionan en un
# unico chunk y el escenario deja de existir en silencio).
_PAGE_A = ("El sistema documenta controles de acceso y auditoria. " * 130)[:6500]
_PAGE_B = ("La seccion describe registros y trazabilidad del proceso. " * 130)[:6500]


def _ok_payload(estado: str = "evidencia_insuficiente", evidencia: str = "") -> dict:
    meta = ce.load_prompt_meta(PROMPT_PATH)
    return {"checkpoints": [
        {"req_id": cp["req_id"], "estado": estado, "evidencia_exacta": evidencia,
         "brecha": "", "recomendacion": ""}
        for cp in meta["checkpoints"]
    ]}


class _ScriptedProvider:
    """Responde segun un guion por numero de llamada."""

    def __init__(self, script: list[dict]):
        self.script = script
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-model"

    # Sin context_window declarado, a proposito (Bloque 4,
    # docs_plan/BLOQUE4_FIX_AUDIT_TRAIL_Y_CIERRE.md): este archivo prueba el
    # mecanismo de reintento POR RESUME (retry_technical_failures), un
    # mecanismo distinto al reintento INLINE de truncamiento (ver
    # TestTruncationRetry en test_output_token_budget.py, que si declara
    # context_window para poder probarlo). Sin context_window, la guardia de
    # chunked_engine que dispara el reintento inline nunca se activa (no
    # puede verificar que el reintento no trunque el prompt sin conocer la
    # ventana) -- un _TRUNCATED en este archivo sigue siendo, como antes de
    # Bloque 4, un fallo tecnico permanente hasta que se pida el resume.

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        response = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return response

    def show_digest(self) -> str:
        return "sha256:fake-digest"

    def runtime_version(self) -> str:
        return "0.0.0-fake"


class _ScriptedProviderWithWindow(_ScriptedProvider):
    """Misma respuesta guionada que _ScriptedProvider, pero SI declara
    context_window -- usada unicamente por los tests de Bloque 4 que
    necesitan ejercer el reintento INLINE de truncamiento a la vez que el
    reintento por resume, para probar que ambos mecanismos coexisten sin
    pisarse (nunca en el resto de este archivo, que prueba resume aislado)."""

    @property
    def context_window(self) -> int:
        return 16384


_TRUNCATED = {"response": '{"checkpoints": [{"req_id": "A", "estado": "cumple", '
                          '"evidencia_exacta": "x", "brecha": "", "recomendacion": ""}, {',
              "done_reason": "length"}


def _good(estado: str = "evidencia_insuficiente", evidencia: str = "") -> dict:
    return {"response": json.dumps(_ok_payload(estado, evidencia)), "done_reason": "stop"}


def _run(provider, sha: str, store=None, **kwargs) -> dict:
    return ce.evaluate_chunked(
        PROMPT_PATH, "fda_part11_agent", "v-test", [_PAGE_A, _PAGE_B], "sys",
        "doc", "v1", "doc.pdf", sha, run_context="validation",
        provider=provider, checkpoint_store=store, **kwargs,
    )


class TestRetryTechnicalFailures:

    def test_completed_run_with_failures_is_not_reopened_without_the_flag(self, tmp_path):
        """Comportamiento HISTORICO preservado (default sin cambios): un run
        COMPLETADO con fallos tecnicos no se reabre. La unica salida era
        rehacer el documento entero -- que es exactamente el costo que se
        pago al descartar la corrida fsv12_reeval_20260727."""
        store = ce.CheckpointStore(tmp_path)
        first = _ScriptedProvider([_TRUNCATED, _good()])
        _run(first, "a" * 64, store)
        assert first.calls == 2

        second = _ScriptedProvider([_good()])
        result = _run(second, "a" * 64, store)
        assert result["preflight_metadata"]["resumed_from_checkpoint"] is False
        assert result["preflight_metadata"]["retried_chunk_indices"] == []
        assert second.calls == 2, "sin el flag se reejecuta TODO, no solo lo que fallo"

    def test_completed_run_without_failures_is_never_reopened(self, tmp_path):
        """Reabrir solo es legitimo para lo que fallo tecnicamente. Un run
        limpio no se re-analiza nunca, ni siquiera pidiendo el reintento."""
        store = ce.CheckpointStore(tmp_path)
        _run(_ScriptedProvider([_good()]), "z" * 64, store)
        result = _run(_ScriptedProvider([_good()]), "z" * 64, store,
                      retry_technical_failures=True)
        assert result["preflight_metadata"]["resumed_from_checkpoint"] is False
        assert result["preflight_metadata"]["retried_chunk_indices"] == []

    def test_retry_reexecutes_only_the_failed_chunk(self, tmp_path):
        store = ce.CheckpointStore(tmp_path)
        first = _ScriptedProvider([_TRUNCATED, _good()])
        _run(first, "b" * 64, store)

        second = _ScriptedProvider([_good()])
        result = _run(second, "b" * 64, store, retry_technical_failures=True)

        assert second.calls == 1, "exactamente un chunk reintentado, no los dos"
        assert result["preflight_metadata"]["retried_chunk_indices"] == [0]
        assert result["chunk_executions"][0]["technical_execution_failure"] is False
        assert result["chunk_executions"][0]["ok"] is True
        assert len(result["chunk_executions"]) == 2, "reemplaza, nunca anade"

    def test_previous_attempt_is_preserved_never_erased(self, tmp_path):
        """Un run regulatorio debe poder demostrar que hubo un fallo y que se
        resolvio -- no aparentar que nunca ocurrio."""
        store = ce.CheckpointStore(tmp_path)
        _run(_ScriptedProvider([_TRUNCATED, _good()]), "c" * 64, store)
        result = _run(_ScriptedProvider([_good()]), "c" * 64, store,
                      retry_technical_failures=True)

        history = result["chunk_executions"][0]["superseded_attempts"]
        assert len(history) == 1
        assert history[0]["technical_execution_failure"] is True
        assert history[0]["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED

    def test_retry_does_not_duplicate_verified_records(self, tmp_path):
        """Sin purgar los registros del intento viejo, el chunk reintentado
        aportaria DOS registros por requisito y coverage_complete contaria
        una cobertura que no existe."""
        store = ce.CheckpointStore(tmp_path)
        common = dict(use_verified_pipeline=True, document_type="FS")
        _run(_ScriptedProvider([_TRUNCATED, _good()]), "d" * 64, store, **common)
        _run(_ScriptedProvider([_good()]), "d" * 64, store,
             retry_technical_failures=True, **common)

        state = json.loads(next(Path(tmp_path).glob("*.checkpoint.json")).read_text())
        for req_id, records in state["verified_records_by_req"].items():
            assert len(records) == 2, f"{req_id}: un registro por chunk, no mas"
            ids = [r["record_id"] for r in records]
            assert len(set(ids)) == len(ids)

    def test_retry_is_declared_in_preflight(self, tmp_path):
        store = ce.CheckpointStore(tmp_path)
        _run(_ScriptedProvider([_TRUNCATED, _good()]), "e" * 64, store)
        result = _run(_ScriptedProvider([_good()]), "e" * 64, store,
                      retry_technical_failures=True)
        preflight = result["preflight_metadata"]
        assert preflight["retry_technical_failures_requested"] is True
        assert preflight["retried_chunk_indices"] == [0]


class TestProvisionalFlagOnNoCumpleBranch:
    """Defecto D-5: la rama `no_cumple` no propagaba
    technical_execution_failure_pending."""

    def _no_cumple_with_a_failed_chunk(self, sha: str) -> dict:
        # Chunk 0 falla tecnicamente; chunk 1 devuelve no_cumple SIN cita
        # (has_evidence=False -> not_observed), que es justo la rama afectada.
        provider = _ScriptedProvider([_TRUNCATED, _good(estado="no_cumple")])
        return _run(provider, sha)

    def test_no_cumple_is_marked_provisional_when_a_chunk_failed(self):
        result = self._no_cumple_with_a_failed_chunk("f" * 64)
        no_cumple = [f for f in result["findings"] if f["estado"] == "no_cumple"]
        assert no_cumple, "el escenario debe producir al menos un no_cumple"
        for finding in no_cumple:
            assert finding["technical_execution_failure_pending"] is True
            assert finding["brecha"].startswith("PROVISIONAL")
            assert "severidad" in finding and finding["severidad"] == "mayor"

    def test_no_cumple_without_failures_stays_definitive(self):
        """El flag no debe encenderse solo: sin fallos tecnicos, el
        incumplimiento se sigue presentando como definitivo."""
        provider = _ScriptedProvider([_good(estado="no_cumple")])
        result = _run(provider, "g" * 64)
        no_cumple = [f for f in result["findings"] if f["estado"] == "no_cumple"]
        assert no_cumple
        for finding in no_cumple:
            assert finding["technical_execution_failure_pending"] is False
            assert not finding["brecha"].startswith("PROVISIONAL")


class TestBloque4AttemptLineage:
    """docs_plan/BLOQUE4_FIX_AUDIT_TRAIL_Y_CIERRE.md Bloque B: el reintento
    INLINE de truncamiento (chunked_engine, ~1473) y el reintento POR RESUME
    (este archivo) son dos mecanismos de preservacion de evidencia
    independientes que deben coexistir sin pisarse. Unica clase de este
    archivo que usa _ScriptedProviderWithWindow -- necesita que el inline
    retry SI se active para poder probar la interaccion entre ambos."""

    def test_max_inline_retry_is_one(self):
        assert ce.MAX_INLINE_RETRY == 1

    def test_resume_after_inline_retry_success_is_idempotent(self, tmp_path):
        """B.2: un chunk resuelto por el reintento INLINE (dentro de la
        misma corrida) no debe reejecutarse ni ver alterado su
        superseded_attempts cuando una corrida POSTERIOR reanuda para
        resolver OTRO chunk que si sigue fallando -- el resume debe
        reconocer que ese chunk ya esta ok=True y saltarlo."""
        store = ce.CheckpointStore(tmp_path)
        # chunk0 (PAGE_A): trunca y se autorepara via reintento inline.
        # chunk1 (PAGE_B): trunca DOS veces (inicial + reintento inline) y
        # queda con technical_execution_failure=True, exigiendo resume.
        first = _ScriptedProviderWithWindow([_TRUNCATED, _good(), _TRUNCATED, _TRUNCATED])
        first_result = _run(first, "h" * 64, store)
        assert first.calls == 4
        chunk0_history_before = first_result["chunk_executions"][0]["superseded_attempts"]
        assert len(chunk0_history_before) == 1
        assert first_result["chunk_executions"][0]["ok"] is True
        assert first_result["chunk_executions"][1]["technical_execution_failure"] is True

        second = _ScriptedProviderWithWindow([_good()])
        result = _run(second, "h" * 64, store, retry_technical_failures=True)

        assert second.calls == 1, "solo el chunk que seguia fallando debe reejecutarse"
        assert result["preflight_metadata"]["retried_chunk_indices"] == [1]
        assert result["chunk_executions"][0]["superseded_attempts"] == chunk0_history_before, (
            "el chunk ya resuelto por el reintento inline no debe alterarse al reanudar"
        )
        assert result["chunk_executions"][1]["ok"] is True

    def test_bridge_scenario_inline_retry_then_resume_recovers(self, tmp_path):
        """B.3: truncamiento -> reintento inline -> vuelve a fallar ->
        persistencia con superseded_attempts completo -> resume con
        retry_technical_failures=True -> recuperacion final. Confirma que
        ambos mecanismos, encadenados en el mismo chunk, producen un
        linaje de intentos completo y correctamente numerado."""
        store = ce.CheckpointStore(tmp_path)
        first = _ScriptedProviderWithWindow([_TRUNCATED, _TRUNCATED, _good()])
        first_result = _run(first, "i" * 64, store)
        failed = first_result["chunk_executions"][0]
        assert failed["technical_execution_failure"] is True
        assert failed["attempt_type"] == ce.ATTEMPT_TYPE_INLINE_TRUNCATION_RETRY
        assert len(failed["superseded_attempts"]) == 1
        assert failed["superseded_attempts"][0]["attempt_type"] == ce.ATTEMPT_TYPE_INITIAL

        second = _ScriptedProviderWithWindow([_good()])
        result = _run(second, "i" * 64, store, retry_technical_failures=True)

        recovered = result["chunk_executions"][0]
        assert recovered["ok"] is True
        assert recovered["technical_execution_failure"] is False
        assert recovered["attempt_type"] == ce.ATTEMPT_TYPE_CHECKPOINT_RESUME_RETRY
        history = recovered["superseded_attempts"]
        assert len(history) == 2, "el intento inicial Y el intento truncado-tras-inline se preservan ambos"
        assert [a["attempt_type"] for a in history] == [
            ce.ATTEMPT_TYPE_INITIAL, ce.ATTEMPT_TYPE_INLINE_TRUNCATION_RETRY,
        ]
        assert [a["attempt_number"] for a in history] == [1, 2]
        assert [a["superseded_by_attempt"] for a in history] == [2, 3]
        assert recovered["attempt_number"] == 3
        for attempt in history:
            assert attempt["technical_execution_failure"] is True
            assert attempt["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
