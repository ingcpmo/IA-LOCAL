"""
Presupuesto de tokens de salida gobernado en evaluate_chunked()
(2026-07-28). Ver factory/docs/W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md
y factory/designs/num_predict_budget/DESIGN.md.

Defecto que motiva estos tests: `NUM_PREDICT = 1024` quedo atras cuando la
ampliacion D de la Fase F agrego `criterion_assessments` al contrato de
salida. Ollama truncaba la respuesta (`done_reason="length"`) en todo chunk
que analizara contenido real, y el motor lo reportaba como "el modelo no
devolvio JSON valido" -- conflacionando un error de CONFIGURACION con un
fallo del modelo, y descartando la respuesta cruda que lo demostraba.

Todo con providers falsos deterministas -- nunca llama a Ollama real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.engines.gmpai_integrity import chunked_engine as ce

PROMPTS = Path(ce.__file__).parent / "prompts"
PART11 = PROMPTS / "part11_prompts.yaml"
ANNEX11 = PROMPTS / "annex11_prompts.yaml"
ALCOA = PROMPTS / "alcoa_prompts.yaml"


def _payload(prompt_path: Path, estado: str = "evidencia_insuficiente",
             evidencia: str = "") -> dict:
    meta = ce.load_prompt_meta(prompt_path)
    return {"checkpoints": [
        {"req_id": cp["req_id"], "estado": estado, "evidencia_exacta": evidencia,
         "brecha": "", "recomendacion": ""}
        for cp in meta["checkpoints"]
    ]}


class _BaseProvider:
    """Provider falso que ACEPTA num_predict (contrato actual)."""

    def __init__(self, responses: list[dict]):
        self._responses = responses
        self.calls: list[dict] = []

    @property
    def model_name(self) -> str:
        return "fake-model"

    @property
    def context_window(self) -> int:
        return 16384

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        self.calls.append({"num_predict": num_predict, "prompt_chars": len(prompt)})
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]

    def show_digest(self) -> str:
        return "sha256:fake-digest"

    def runtime_version(self) -> str:
        return "0.0.0-fake"


class _LegacyProvider(_BaseProvider):
    """Provider del contrato ANTERIOR: generate() sin num_predict. Debe
    seguir funcionando (retrocompatibilidad real, no declarada)."""

    def generate(self, prompt: str) -> dict:  # type: ignore[override]
        self.calls.append({"num_predict": None, "prompt_chars": len(prompt)})
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


class _UndeclaredWindowProvider:
    """No declara context_window -- caso de la mayoria de los providers de
    test y de cualquier backend que no exponga ese dato."""

    def __init__(self, responses: list[dict]):
        self._responses = responses
        self.calls: list[dict] = []

    @property
    def model_name(self) -> str:
        return "fake-model"

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        self.calls.append({"num_predict": num_predict, "prompt_chars": len(prompt)})
        return self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]

    def show_digest(self) -> str:
        return "sha256:fake-digest"

    def runtime_version(self) -> str:
        return "0.0.0-fake"


class _NarrowProvider(_BaseProvider):
    """Ventana de contexto deliberadamente pequena."""

    @property
    def context_window(self) -> int:
        return 2048


def _run(prompt_path: Path, provider, doc: list[str], sha: str, **kwargs) -> dict:
    return ce.evaluate_chunked(
        prompt_path, "fda_part11_agent", "v-test", doc, "sys", "doc", "v1",
        "doc.pdf", sha, run_context="validation", provider=provider, **kwargs,
    )


class TestOutputTokenBudget:
    """El presupuesto se DERIVA del contrato; no es una constante."""

    def test_real_agent_contracts_produce_expected_budgets(self):
        assert ce.output_token_budget(5, 20) == 3072   # eu_annex11_agent
        assert ce.output_token_budget(9, 25) == 4096   # alcoa_plus_agent

    def test_budget_grows_with_the_contract(self):
        """La invariante que importa: si el catalogo gana criterios, el
        presupuesto sube SOLO. Es lo que evita que vuelva a quedarse atras."""
        previous = 0
        for n_criteria in range(0, 60, 5):
            current = ce.output_token_budget(5, n_criteria)
            assert current >= previous
            previous = current
        assert ce.output_token_budget(5, 40) > ce.output_token_budget(5, 20)

    def test_always_a_positive_multiple_of_512(self):
        for n_cp, n_crit in ((0, 0), (1, 1), (5, 20), (9, 25), (30, 200)):
            budget = ce.output_token_budget(n_cp, n_crit)
            assert budget >= 512 and budget % 512 == 0

    def test_negative_contract_is_rejected(self):
        with pytest.raises(ValueError):
            ce.output_token_budget(-1, 10)
        with pytest.raises(ValueError):
            ce.output_token_budget(5, -1)

    def test_budget_matches_the_real_catalog_for_annex11(self):
        """Contra el catalogo REAL. El cuerpo anterior contradecia su propio
        docstring: afirmaba 5 checkpoints y 20 criterios, dos numeros
        escritos a mano que se rompen en cuanto el catalogo gane un criterio
        -- justo el cambio que el presupuesto derivado existe para absorber.

        Lo que se comprueba ahora es el enlace real: el presupuesto que se
        usaria para este prompt sale del contrato que se le va a enviar."""
        meta = ce.load_prompt_meta(ANNEX11)
        admitidos, _bloqueados = ce.evidence_pack_gate(meta)
        criterios = ce._count_contract_criteria(meta)
        assert admitidos and criterios > 0, "el prompt real debe tener contrato que dimensionar"

        provider = _BaseProvider([{"response": json.dumps(_payload(ANNEX11)),
                                   "done_reason": "stop"}])
        result = ce.evaluate_chunked(
            ANNEX11, "eu_annex11_agent", "v-test", ["texto de prueba " * 50], "sys",
            "doc", "v1", "doc.pdf", "b" * 64, run_context="validation", provider=provider,
        )
        usado = result["preflight_metadata"]["token_budget"]["num_predict"]
        assert usado == ce.output_token_budget(len(admitidos), criterios), (
            "el motor debe usar el presupuesto derivado del contrato real que envia"
        )
        assert all(c["num_predict"] == usado for c in provider.calls)


class TestPreflightContextGuard:
    """Un prompt que no cabe NO falla en Ollama: se trunca en silencio. La
    guardia tiene que impedirlo ANTES de gastar llamadas."""

    def test_budget_that_does_not_fit_raises_before_any_call(self):
        provider = _NarrowProvider([{"response": json.dumps(_payload(PART11)),
                                     "done_reason": "stop"}])
        with pytest.raises(ce.TokenBudgetError) as exc:
            _run(PART11, provider, ["texto " * 500], "a" * 64)
        assert provider.calls == [], "no debe gastarse NINGUNA llamada al modelo"
        message = str(exc.value)
        assert "num_ctx" in message and "num_predict" in message

    def test_guard_uses_the_worst_chunk_not_the_average(self):
        """Un documento con un chunk grande entre muchos pequenos debe
        bloquear igual -- el promedio ocultaria el caso real."""
        meta = ce.load_prompt_meta(PART11)
        chunks = ce.build_page_chunks(["corto"] * 5 + ["x" * 6000])
        budget = ce.output_token_budget(len(meta["checkpoints"]),
                                        ce._count_contract_criteria(meta))
        with pytest.raises(ce.TokenBudgetError):
            ce._assert_token_budget_fits(chunks, meta, budget, 2048)

    def test_alcoa_does_not_fit_in_the_old_8192_window(self):
        """Comprobacion real del hallazgo del diseno: con el presupuesto
        correcto, alcoa_plus_agent NO cabe en la ventana anterior."""
        meta = ce.load_prompt_meta(ALCOA)
        chunks = ce.build_page_chunks(["x" * 6000] * 3)
        budget = ce.output_token_budget(len(meta["checkpoints"]),
                                        ce._count_contract_criteria(meta))
        with pytest.raises(ce.TokenBudgetError):
            ce._assert_token_budget_fits(chunks, meta, budget, 8192)
        fits = ce._assert_token_budget_fits(chunks, meta, budget, 16384)
        assert fits["headroom_tokens"] > 0

    def test_provider_without_declared_window_is_not_blocked_by_a_guessed_one(self):
        """Un provider que no declara context_window NO se somete a la
        guardia: no se puede verificar un limite que no se conoce, y suponer
        uno bloquearia corridas legitimas por un numero inventado. Debe
        quedar declarado, no asumido."""
        provider = _UndeclaredWindowProvider([{"response": json.dumps(_payload(PART11)),
                                               "done_reason": "stop"}])
        assert not hasattr(provider, "context_window")
        result = _run(PART11, provider, ["x" * 6000] * 3, "h" * 64)
        budget = result["preflight_metadata"]["token_budget"]
        assert budget["context_window_declared"] is False
        assert budget["num_ctx"] is None
        assert budget["headroom_tokens"] is None

    def test_real_ollama_provider_does_declare_its_window(self):
        """La guardia solo sirve si esta activa donde importa."""
        from factory.engines.gmpai_integrity.model_provider import OllamaProvider
        assert isinstance(OllamaProvider().context_window, int)

    def test_budget_detail_reaches_preflight_metadata(self):
        provider = _BaseProvider([{"response": json.dumps(_payload(PART11)),
                                   "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido de prueba"], "b" * 64)
        budget = result["preflight_metadata"]["token_budget"]
        assert budget["num_predict"] == provider.calls[0]["num_predict"]
        assert budget["provider_honors_token_budget"] is True
        assert budget["headroom_tokens"] > 0


class TestReadTimeoutScalesWithBudget:
    """El timeout de lectura es la MISMA clase de constante que NUM_PREDICT:
    tiene que escalar con el presupuesto o mata la llamada que el presupuesto
    hizo posible. La primera validacion real con num_predict=3072 murio por
    ReadTimeout a los 1200 s fijos."""

    def test_timeout_covers_the_real_budget(self):
        from factory.engines.gmpai_integrity import ollama_client as oc
        # 3072 tokens a 2 tok/s = 1536 s, mas margen de prompt eval.
        assert oc.read_timeout_for(3072) > oc.TIMEOUT_READ_S
        assert oc.read_timeout_for(3072) >= 3072 / oc.MIN_TOKENS_PER_SECOND

    def test_timeout_never_drops_below_the_configured_floor(self):
        from factory.engines.gmpai_integrity import ollama_client as oc
        assert oc.read_timeout_for(None) == oc.TIMEOUT_READ_S
        assert oc.read_timeout_for(0) == oc.TIMEOUT_READ_S
        assert oc.read_timeout_for(16) == oc.TIMEOUT_READ_S

    def test_timeout_grows_with_the_budget(self):
        from factory.engines.gmpai_integrity import ollama_client as oc
        assert oc.read_timeout_for(8192) > oc.read_timeout_for(4096) > oc.read_timeout_for(3072)

    def test_assumed_rate_is_below_the_measured_one(self):
        """Si la velocidad asumida fuera >= la medida (3,33 tok/s), un host
        cargado produciria timeouts espureos."""
        from factory.engines.gmpai_integrity import ollama_client as oc
        assert oc.MIN_TOKENS_PER_SECOND < 3.33


class TestProviderBudgetPropagation:

    def test_budget_is_passed_to_the_provider(self):
        provider = _BaseProvider([{"response": json.dumps(_payload(PART11)),
                                   "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido"], "c" * 64)
        meta = ce.load_prompt_meta(PART11)
        expected = ce.output_token_budget(len(meta["checkpoints"]),
                                          ce._count_contract_criteria(meta))
        assert provider.calls[0]["num_predict"] == expected
        assert result["chunk_executions"][0]["num_predict"] == expected

    def test_legacy_provider_still_works_and_is_declared_honestly(self):
        """Un provider viejo no rompe la corrida, pero el motor NO finge que
        el presupuesto se respeto."""
        provider = _LegacyProvider([{"response": json.dumps(_payload(PART11)),
                                     "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido"], "d" * 64)
        assert result["preflight_metadata"]["token_budget"]["provider_honors_token_budget"] is False
        assert result["chunk_executions"][0]["num_predict"] is None
        assert result["chunk_executions"][0]["ok"] is True


class TestFailureCauseClassification:
    """Las cuatro causas eran un solo mensaje. Un truncamiento por
    presupuesto es error del OPERADOR; los otros tres, del modelo."""

    def test_truncated_output_is_named_as_such(self):
        provider = _BaseProvider([{"response": '{"checkpoints": [{"req_id": "x"',
                                   "done_reason": "length"}])
        result = _run(PART11, provider, ["contenido"], "e" * 64)
        execution = result["chunk_executions"][0]
        assert execution["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert execution["technical_execution_failure"] is True
        assert "num_predict" in execution["error"]

    def test_truncation_wins_over_the_parse_error_it_causes(self):
        """Una respuesta truncada casi siempre falla tambien el parseo.
        Reportar 'json_parse_failed' esconderia la causa real -- que fue
        exactamente lo que paso en la corrida fsv12_reeval_20260727."""
        # Forma REAL del corte observado en chunk3_raw.txt: los checkpoints
        # ya emitidos cierran sus llaves, y el corte cae al abrir el
        # siguiente. Por eso hay `{...}` y el fallo es de parseo, no de
        # ausencia de objeto JSON.
        truncated = (
            '{"checkpoints": [{"req_id": "A", "estado": "cumple", '
            '"evidencia_exacta": "x", "brecha": "", "recomendacion": ""}, '
            '{"req_id": "B",'
        )
        parsed, reason, _ = ce.classify_model_response(
            {"response": truncated, "done_reason": "length"})
        assert parsed is None and reason == ce.FAILURE_OUTPUT_TRUNCATED
        _, reason_without_flag, _ = ce.classify_model_response(
            {"response": truncated, "done_reason": "stop"})
        assert reason_without_flag == ce.FAILURE_JSON_PARSE

    def test_no_json_object_at_all(self):
        parsed, reason, _ = ce.classify_model_response(
            {"response": "lo siento, no puedo ayudar", "done_reason": "stop"})
        assert parsed is None and reason == ce.FAILURE_NO_JSON_OBJECT

    def test_truncation_before_any_closing_brace_is_not_called_a_parse_error(self):
        """Si el corte llega antes de cerrar una sola llave no hay objeto
        JSON que parsear: la causa honesta es no_json_object, no
        json_parse_failed. Comprobado para que la distincion entre las cuatro
        causas sea real y no una etiqueta puesta por defecto."""
        _, reason, _ = ce.classify_model_response(
            {"response": '{"checkpoints": [{"req_id": "A"', "done_reason": "stop"})
        assert reason == ce.FAILURE_NO_JSON_OBJECT

    def test_valid_json_violating_the_schema(self):
        parsed, reason, _ = ce.classify_model_response(
            {"response": '{"checkpoints": [{"sin_req_id": 1}]}', "done_reason": "stop"})
        assert parsed is None and reason == ce.FAILURE_SCHEMA_VALIDATION

    def test_valid_response_has_no_failure_reason(self):
        parsed, reason, raw = ce.classify_model_response(
            {"response": json.dumps(_payload(PART11)), "done_reason": "stop"})
        assert reason is None and parsed is not None and raw

    def test_raw_response_is_persisted_for_diagnosis(self):
        """Sin el raw hizo falta un script dedicado y ~20 min de CPU para
        diagnosticar algo que el motor tuvo en la mano y tiro."""
        provider = _BaseProvider([{"response": "respuesta imposible de parsear",
                                   "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido"], "f" * 64)
        assert result["chunk_executions"][0]["raw_response"] == "respuesta imposible de parsear"

    def test_persisted_raw_is_capped(self):
        provider = _BaseProvider([{"response": "x" * 40000, "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido"], "g" * 64)
        execution = result["chunk_executions"][0]
        assert len(execution["raw_response"]) == ce._RAW_PERSIST_MAX_CHARS
        assert execution["raw_response_truncated_in_log"] is True

    def test_full_raw_response_recoverable_beyond_the_checkpoint_cap(self, tmp_path):
        """W5V2_REMEDIACION_RECALL_MODELO.md 1.2: el cap de 8192 caracteres
        en el checkpoint impidio auditar el razonamiento real de una llamada
        del Piloto 1 (2026-08-08). Con checkpoint_store, la respuesta
        COMPLETA debe poder recuperarse mas alla del extracto truncado."""
        full_text = "y" * 40000
        provider = _BaseProvider([{"response": full_text, "done_reason": "stop"}])
        store = ce.CheckpointStore(tmp_path)
        result = _run(PART11, provider, ["contenido"], "h" * 64, checkpoint_store=store)
        execution = result["chunk_executions"][0]

        assert execution["raw_response_truncated_in_log"] is True
        assert execution["raw_response_full_path"] is not None
        assert execution["raw_response_full_sha256"] == (
            __import__("hashlib").sha256(full_text.encode("utf-8")).hexdigest()
        )

        recovered = store.load_raw_response(execution["raw_response_full_path"])
        assert recovered == full_text

    def test_no_full_raw_persisted_without_a_checkpoint_store(self):
        """Sin checkpoint_store no hay donde persistir el archivo aparte --
        se degrada al extracto de siempre, nunca a un error."""
        provider = _BaseProvider([{"response": "x" * 40000, "done_reason": "stop"}])
        result = _run(PART11, provider, ["contenido"], "i" * 64)
        execution = result["chunk_executions"][0]
        assert execution["raw_response_full_path"] is None
        assert execution["raw_response_full_sha256"] is None


class _FitsBaseNotEscalatedProvider(_BaseProvider):
    """Ventana que alcanza para el presupuesto BASE (pasa el preflight) pero
    no para el escalado 2x del reintento -- para PART11 (base=4096,
    escalado=8192, prompt~2662 tok): 8192 >= 2662+4096=6758 (cabe base),
    8192 < 2662+8192=10854 (NO cabe escalado)."""

    @property
    def context_window(self) -> int:
        return 8192


_TRUNCATED = {"response": '{"checkpoints": [{"req_id": "x"', "done_reason": "length"}


def _valid_part11_response() -> dict:
    return {"response": json.dumps(_payload(PART11)), "done_reason": "stop"}


class TestTruncationRetry:
    """Reintento puntual de UN chunk truncado por presupuesto, con
    TRUNCATION_RETRY_MULTIPLIER (2026-08-21, motivado por el chunk 17 real
    de RW-0005/FIXTURE_7P2N). Nunca toca el presupuesto BASE de las demas
    ~800 llamadas de una corrida completa -- solo el chunk que YA se
    trunco, una sola vez, y solo si el reintento cabe en context_window."""

    def test_multiplier_constant_is_two(self):
        assert ce.TRUNCATION_RETRY_MULTIPLIER == 2.0

    def test_retries_only_on_output_truncated(self):
        """Un fallo que NO es truncamiento (aqui: no_json_object) no debe
        disparar ningun reintento -- solo output_truncated es un error de
        CONFIGURACION recuperable subiendo el presupuesto; los otros tres
        son del modelo/contrato y reintentar con mas tokens no los arregla."""
        provider = _BaseProvider([
            {"response": "lo siento, no puedo ayudar", "done_reason": "stop"},
            _valid_part11_response(),
        ])
        result = _run(PART11, provider, ["contenido"], "j" * 64)
        execution = result["chunk_executions"][0]
        assert len(provider.calls) == 1, "no debe gastarse una segunda llamada"
        assert execution["failure_reason"] == ce.FAILURE_NO_JSON_OBJECT
        assert execution["truncation_retry_used"] is False

    def test_truncated_output_retries_once_with_escalated_budget_and_recovers(self):
        provider = _BaseProvider([_TRUNCATED, _valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "k" * 64)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 2, "exactamente un reintento, no mas"
        base = provider.calls[0]["num_predict"]
        escalated = provider.calls[1]["num_predict"]
        assert base == ce.output_token_budget(5, 26)
        assert escalated == -(-int(base * ce.TRUNCATION_RETRY_MULTIPLIER) // 512) * 512
        assert escalated == base * 2, "para este contrato el redondeo a 512 coincide con 2x exacto"

        assert execution["truncation_retry_used"] is True
        assert execution["num_predict"] == escalated, (
            "num_predict persistido debe ser el REALMENTE usado (el del reintento), no el base"
        )
        assert execution["failure_reason"] is None
        assert execution["technical_execution_failure"] is False
        assert execution["ok"] is True

        # Bloque 4 (docs_plan/BLOQUE4_FIX_AUDIT_TRAIL_Y_CIERRE.md): el
        # primer intento truncado debe preservarse, no perderse al
        # sobrescribirse con el resultado del reintento.
        assert execution["attempt_type"] == ce.ATTEMPT_TYPE_INLINE_TRUNCATION_RETRY
        assert execution["attempt_number"] == 2
        history = execution["superseded_attempts"]
        assert len(history) == 1
        assert history[0]["attempt_type"] == ce.ATTEMPT_TYPE_INITIAL
        assert history[0]["attempt_number"] == 1
        assert history[0]["superseded_by_attempt"] == 2
        assert history[0]["technical_execution_failure"] is True
        assert history[0]["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert history[0]["num_predict"] == base

    def test_at_most_one_retry_even_if_the_retry_also_truncates(self):
        """Si el reintento TAMBIEN se trunca, no hay un tercer intento --
        el reintento esta acotado a UNA sola vez, siempre."""
        provider = _BaseProvider([_TRUNCATED, _TRUNCATED, _valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "l" * 64)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 2, "el tercer response nunca debe consultarse"
        assert execution["truncation_retry_used"] is True, "el reintento SI se intento"
        assert execution["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED, (
            "sigue fallando -- el reintento no garantiza exito, solo se intenta una vez"
        )
        assert execution["technical_execution_failure"] is True
        assert execution["num_predict"] == provider.calls[1]["num_predict"], (
            "aunque el reintento fallo tambien, el num_predict persistido es el del intento real"
        )

        # Bloque 4: el reintento SI se intento, asi que el primer intento
        # sigue debiendo preservarse aunque el resultado final tambien haya
        # fallado -- la evidencia no depende de que el reintento tenga exito.
        history = execution["superseded_attempts"]
        assert len(history) == 1
        assert history[0]["attempt_type"] == ce.ATTEMPT_TYPE_INITIAL
        assert history[0]["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED

    def test_no_retry_when_the_escalated_budget_does_not_fit_context_window(self):
        """Misma garantia que la guardia de preflight (_assert_token_budget_
        fits): si prompt + num_predict escalado > context_window, el
        reintento arriesgaria truncar el PROMPT en silencio (perdiendo
        common_contract/req_id) -- estrictamente peor que quedarse en
        technical_execution_failure. Debe NO reintentar y fallar-cerrado."""
        provider = _FitsBaseNotEscalatedProvider([_TRUNCATED, _valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "m" * 64)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 1, "el reintento no debe intentarse si no cabe"
        assert execution["truncation_retry_used"] is False
        assert execution["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert execution["technical_execution_failure"] is True
        assert execution["num_predict"] == provider.calls[0]["num_predict"]
        assert "superseded_attempts" not in execution, (
            "sin reintento inline no hay nada que preservar"
        )

    def test_no_retry_when_provider_does_not_honor_num_predict(self):
        """Un provider del contrato ANTERIOR (sin num_predict) no tiene nada
        que escalar -- comportamiento identico al de antes de este cambio:
        se declara honestamente (provider_honors_token_budget=False,
        num_predict persistido=None) y no se reintenta."""
        provider = _LegacyProvider([_TRUNCATED, _valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "n" * 64)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 1
        assert execution["truncation_retry_used"] is False
        assert execution["num_predict"] is None
        assert execution["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert execution["technical_execution_failure"] is True
        assert "superseded_attempts" not in execution

    def test_no_retry_when_context_window_is_undeclared(self):
        """Sin context_window conocido no se puede verificar que el
        reintento no trunque el prompt -- mismo principio que la guardia de
        preflight: no se supone un limite que no se conoce."""
        provider = _UndeclaredWindowProvider([_TRUNCATED, _valid_part11_response()])
        assert not hasattr(provider, "context_window")
        result = _run(PART11, provider, ["contenido"], "o" * 64)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 1
        assert execution["truncation_retry_used"] is False
        assert execution["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert "superseded_attempts" not in execution

    def test_normal_success_is_not_marked_as_a_retry(self):
        """No-regresion: un chunk que responde bien a la primera no debe
        traer ningun rastro de reintento."""
        provider = _BaseProvider([_valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "p" * 64)
        execution = result["chunk_executions"][0]
        assert "superseded_attempts" not in execution
        assert execution["attempt_type"] == ce.ATTEMPT_TYPE_INITIAL
        assert execution["attempt_number"] == 1

        assert len(provider.calls) == 1
        assert execution["truncation_retry_used"] is False
        assert execution["num_predict"] == provider.calls[0]["num_predict"]
        assert execution["ok"] is True

    def test_retry_preserves_the_final_raw_response_used(self):
        """El raw_response persistido debe corresponder a la respuesta que
        REALMENTE se uso (la del reintento cuando hubo uno), no al primer
        intento descartado -- para que un dossier audite lo que paso de
        verdad."""
        provider = _BaseProvider([_TRUNCATED, _valid_part11_response()])
        result = _run(PART11, provider, ["contenido"], "q" * 64)
        execution = result["chunk_executions"][0]
        assert execution["raw_response"] == json.dumps(_payload(PART11))


class _RealFailureReplayProvider(_BaseProvider):
    """Repite EXACTAMENTE la respuesta cruda real capturada por Fase 5 en el
    primer intento (mismo done_reason='length' que Ollama devolvio de
    verdad), y una respuesta valida sintetica en el reintento -- el reintento
    en si nunca corrio en produccion (el fix es posterior a la corrida), asi
    que no hay un "raw_response real del reintento" que reproducir; lo que
    se valida aqui es que el DISPARADOR (el fallo real) escala el
    presupuesto exactamente como predice el contrato real del agente."""

    def __init__(self, real_raw_response: str, agent_prompt_path: Path):
        payload = json.dumps(_payload(agent_prompt_path))
        super().__init__([
            {"response": real_raw_response, "done_reason": "length"},
            {"response": payload, "done_reason": "stop"},
        ])


class TestTruncationRetryAgainstRealFase5Failures:
    """Bloque 4.1 de docs_plan/DISENO_UNIFICACION_RUNNER_FORMAL.md: el fix
    de TestTruncationRetry (arriba) se probo solo contra un truncamiento
    SINTETICO. Esta clase repite, en el primer intento de cada caso, la
    respuesta cruda REAL persistida por la propia corrida de produccion
    fase5_produccion_real_fixture7p2n_20260820 (2026-08-20/21) que motivo el
    fix -- leida en vivo desde su ubicacion real bajo
    factory/regulatory/corpus_run/, nunca copiada a este archivo.

    Por que no esta embebida como literal en este test (W5.3 Fase 5.4.4,
    mismo regimen de confidencialidad que factory/regulatory/
    validation_evidence/.gitignore: ningun texto citado del documento
    regulado real entra a Git): el archivo se lee de su ruta original en
    disco -- si no existe (clon limpio, CI sin esta evidencia de runtime),
    el test se salta explicitamente en vez de fallar o inventar un
    sustituto, y el sha256 se verifica ANTES de usarlo para que un archivo
    corrupto/distinto nunca pase como si fuera la evidencia real."""

    _CHECKPOINT_DIR = Path("factory/regulatory/corpus_run/checkpoints")

    _CASES = [
        # (nombre, checkpoint run_id, task_id, agente, prompt, sha256 real
        # registrado en el chunk_execution correspondiente, num_predict BASE
        # real que se uso en la corrida -- ver fase5_result.json/checkpoint).
        (
            "eu_annex11_RW-0005_chunk17",
            "chunked-d56217c2d498", "task-9f3b53406432", "eu_annex11_agent", ANNEX11,
            "54f7caf560748f9051fe951c94ad3978556d64a16dff077912ddc9602d2f09a3",
            3072,
        ),
        (
            "alcoa_plus_RW-0005_chunk17",
            "chunked-6a24f7ec77e5", "task-e548f07c600a", "alcoa_plus_agent", ALCOA,
            "175a3c5517cc2f6851cf2f7836d22a3c3c4cdf6e282dc812e928a536b2d56043",
            4096,
        ),
    ]

    def _load_real_raw_response(self, run_id: str, task_id: str, expected_sha256: str) -> str:
        import gzip
        import hashlib

        path = self._CHECKPOINT_DIR / "raw_responses" / run_id / f"{task_id}.txt.gz"
        if not path.is_file():
            pytest.skip(
                f"evidencia real de Fase 5 no presente en este entorno ({path}) -- "
                "runtime local, nunca en Git (W5.3 Fase 5.4.4)"
            )
        with gzip.open(path, "rt", encoding="utf-8") as f:
            text = f.read()
        actual_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert actual_sha256 == expected_sha256, (
            f"{path}: el contenido en disco no coincide con el sha256 registrado por la "
            "corrida real -- no se puede confiar en que sea la misma evidencia"
        )
        return text

    @pytest.mark.parametrize("name,run_id,task_id,agent_id,prompt_path,sha256,base_predict", _CASES)
    def test_real_truncated_response_triggers_correctly_scaled_retry(
        self, name, run_id, task_id, agent_id, prompt_path, sha256, base_predict, tmp_path
    ):
        real_raw = self._load_real_raw_response(run_id, task_id, sha256)
        provider = _RealFailureReplayProvider(real_raw, prompt_path)
        # Bloque 4 (docs_plan/BLOQUE4_FIX_AUDIT_TRAIL_Y_CIERRE.md) B.1: con
        # checkpoint_store, el intento truncado real debe quedar anclado en
        # superseded_attempts con el MISMO sha256 que el archivo .txt.gz
        # original -- cero llamadas nuevas, es el mismo raw ya capturado.
        store = ce.CheckpointStore(tmp_path)

        result = _run(prompt_path, provider, ["contenido"], "r" * 64, checkpoint_store=store)
        execution = result["chunk_executions"][0]

        assert len(provider.calls) == 2, (
            f"{name}: el fallo real debio disparar exactamente un reintento"
        )
        assert provider.calls[0]["num_predict"] == base_predict, (
            f"{name}: el presupuesto BASE calculado debe coincidir con el que la corrida "
            "real de produccion efectivamente uso (mismo contrato, mismo agente)"
        )
        escalated = provider.calls[1]["num_predict"]
        assert escalated == base_predict * ce.TRUNCATION_RETRY_MULTIPLIER
        assert execution["truncation_retry_used"] is True
        assert execution["num_predict"] == escalated
        assert execution["failure_reason"] is None, (
            f"{name}: con el fix activo, el caso real que antes quedaba "
            "rejected_by_verifier debe resolverse en el reintento"
        )
        assert execution["ok"] is True

        history = execution["superseded_attempts"]
        assert len(history) == 1, f"{name}: el intento truncado real debe preservarse, no perderse"
        preserved = history[0]
        assert preserved["attempt_type"] == ce.ATTEMPT_TYPE_INITIAL
        assert preserved["technical_execution_failure"] is True
        assert preserved["failure_reason"] == ce.FAILURE_OUTPUT_TRUNCATED
        assert preserved["num_predict"] == base_predict
        assert preserved["raw_response_full_sha256"] == sha256, (
            f"{name}: el sha256 anclado del intento preservado debe coincidir EXACTO con el "
            "archivo .txt.gz real -- si no coincide, no se puede confiar en que sea la misma evidencia"
        )
        assert store.load_raw_response(preserved["raw_response_full_path"]) == real_raw

    def test_both_real_fase5_failures_are_covered(self):
        """No-regresion de cobertura: si algun dia se agrega un tercer
        truncamiento real a la evidencia de Fase 5, este test avisa que la
        lista de _CASES quedo corta -- 2 es el conteo real confirmado
        (technical_execution_failures=1+1 en fase5_result.json)."""
        assert len(self._CASES) == 2
