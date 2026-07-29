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
