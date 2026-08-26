"""Verificacion 0-LLM (Cesar, 2026-08-22, antes de firmar JUDGMENT_EXECUTION-
2026-003=600): valida contra el motor REAL (ce.evaluate_chunked, no
mockeado) que el conteo que corpus_runner reporta y el hard-stop que aplica
corresponden a llamadas FISICAS reales a provider.generate() -- incluyendo
el reintento INLINE de truncamiento (chunked_engine.py:~1493) y el reintento
TECNICO externo (Bloque 1, _run_unit_top_k_fusion) -- y que retomar desde
checkpoint preserva el consumo ya hecho (no lo recuenta, no lo pierde).

Solo `ce.evaluate_chunked` es real aqui -- todo lo que normalmente gastaria
red (indexer, embeddings, JUDGMENT_EXECUTION/EMBED_EXECUTION resolver) sigue
mockeado, igual que el resto de este modulo. `_ScriptedProviderWithWindow`
nunca llama a Ollama: responde segun un guion fijo por numero de llamada."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.regulatory import corpus_authorization as ca
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg

# Capturada ANTES de que ningun test la mockee -- los tests de
# TestJudgmentHardStopBoundaryIsPerUnitNotPerCall monkeypatchean
# runner._run_unit_top_k_fusion con un fake que a su vez necesita invocar
# la funcion REAL (motor de verdad) para producir el conteo fisico
# -- sin esta referencia capturada, ese fake se llamaria a si mismo
# (recursion infinita).
_REAL_RUN_UNIT_TOP_K_FUSION = runner._run_unit_top_k_fusion

# Mismas dos paginas que factory/tests/test_retry_technical_failures.py --
# superan CHUNK_MAX_CHARS para garantizar DOS chunks reales separados
# (build_page_chunks las trata como una unidad cada una, nunca fusionadas).
_PAGE_A = ("El sistema documenta controles de acceso y auditoria. " * 130)[:6500]
_PAGE_B = ("La seccion describe registros y trazabilidad del proceso. " * 130)[:6500]

_TRUNCATED = {"response": '{"checkpoints": [{"req_id": "A", "estado": "cumple", '
                          '"evidencia_exacta": "x", "brecha": "", "recomendacion": ""}, {',
              "done_reason": "length"}
_MALFORMED_JSON = {"response": "esto no es json valido {{{", "done_reason": "stop"}


def _good_payload_for(agent_id: str) -> dict:
    meta = ce.load_prompt_meta(runner._PROMPT_PATH_BY_AGENT[agent_id])
    return {"checkpoints": [
        {"req_id": cp["req_id"], "estado": "evidencia_insuficiente",
         "evidencia_exacta": "", "brecha": "", "recomendacion": ""}
        for cp in meta["checkpoints"]
    ]}


def _good(agent_id: str) -> dict:
    return {"response": json.dumps(_good_payload_for(agent_id)), "done_reason": "stop"}


class _AuthorizedScope:
    def __init__(self, authorized=True, covering_instances=("INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


class _ScriptedProviderWithWindow:
    """Cuenta llamadas FISICAS reales (self.calls) -- la misma metrica que
    debe coincidir con outcome.calls_made_this_invocation / provider.calls
    contra summary.total_calls_made. Declara context_window para que el
    reintento INLINE de truncamiento pueda dispararse (igual que
    test_retry_technical_failures.py::_ScriptedProviderWithWindow)."""

    def __init__(self, script: list[dict]):
        self.script = script
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-model-physical-accounting"

    @property
    def context_window(self) -> int:
        return 16384

    def generate(self, prompt: str, *, num_predict: int | None = None) -> dict:
        response = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return response

    def show_digest(self) -> str:
        return "sha256:fake-digest-physical"

    def runtime_version(self) -> str:
        return "0.0.0-fake"


def _unit(document_id="DOC-PHYS", agent_id="fda_part11_agent"):
    return runner.CorpusRunUnit(
        document_id=document_id, document_type="FS",
        document_path=runner.PROMPTS_DIR, document_sha256="p" * 64, agent_id=agent_id,
        prompt_path=runner._PROMPT_PATH_BY_AGENT[agent_id], expected_calls=1,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(runner, "DEFAULT_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _AuthorizedScope())
    monkeypatch.setattr(runner, "resolver", resolver)
    # Cierre del gap tecnico (docs_plan, 2026-08-26): ver misma nota en
    # test_corpus_runner.py -- este archivo mockea su propio
    # resolver.resolve con un decision_instance_id falso.
    monkeypatch.setattr(ca, "verify_fingerprint_matches", lambda *a, **k: {})
    monkeypatch.setattr(runner, "ca", ca)
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 999999, "hard_stop_wall_time_hours": 999.0,
    })
    # Un solo requisito admitido -- aisla el conteo al pool de 2 chunks que
    # cada test arma explicitamente, sin depender de cuantos requisitos
    # reales tenga fda_part11_agent.
    monkeypatch.setattr(runner, "_admitted_requirement_ids", lambda prompt_path: ["21_CFR_11.10(a)"])

    from factory.regulatory.retrieval import indexer as _indexer, embed_runner as _embed_runner
    monkeypatch.setattr(_indexer, "build_index", lambda path, **k: {"document_sha256": "sha-phys"})

    class _EmbedSummary:
        total_calls_made = 0
        stop_reason = "BATCH_COMPLETE"

    monkeypatch.setattr(_embed_runner, "run_embed_batch", lambda *a, **k: _EmbedSummary())
    monkeypatch.setattr(runner, "_preflight_embed_budget", lambda *a, **k: {
        "needed": 0, "max_calls": 999, "remaining": 999, "fits": True,
        "selected_embed_instance_id": "EMBED_EXECUTION-test-phys",
        "per_document_pending_chunks": {}, "unique_query_pairs": 0,
    })

    pool = [
        {"chunk_index": 0, "page_start": 1, "page_end": 1, "text": _PAGE_A},
        {"chunk_index": 1, "page_start": 2, "page_end": 2, "text": _PAGE_B},
    ]
    from factory.regulatory.retrieval import judgment_candidate_pool as _jcp
    monkeypatch.setattr(_jcp, "build_fusion_candidate_pool",
                        lambda doc_id, sha, req_id, **k: pool)


def _run_unit_real_engine(provider, checkpoint_dir: Path, unit=None):
    """_run_unit_top_k_fusion() con ce.evaluate_chunked() REAL (sin mockear)
    -- solo la capa de recuperacion (candidate pool/indexer/embeddings) esta
    aislada via _isolate. Cualquier llamada a provider.generate() que ocurra
    aqui, incluyendo reintentos inline/tecnicos, pasa por el `provider`
    scripteado y se cuenta en `provider.calls`."""
    checkpoint_store = ce.CheckpointStore(checkpoint_dir)
    return _REAL_RUN_UNIT_TOP_K_FUSION(
        unit or _unit(), checkpoint_store=checkpoint_store, provider=provider,
        calls_already_used_for_embed=0, decision_store_file=None, run_context="validation",
    )


class TestPhysicalCallAccounting:
    """El conteo que corpus_runner reporta (calls_made_this_invocation /
    summary.total_calls_made) debe ser EXACTAMENTE el numero de llamadas
    fisicas reales a provider.generate() -- ni menos (subestimarlo volveria
    al hueco que dejo pasar Paso A sin control), ni mas (sobreestimarlo
    bloquearia corridas legitimas)."""

    def test_inline_truncation_retry_and_technical_retry_are_both_counted_exactly(self, tmp_path):
        """chunk0: trunca en el primer intento, se autorepara con el
        reintento INLINE (2 llamadas fisicas). chunk1: falla con JSON
        invalido (fallo tecnico NO-truncamiento) en el primer intento (1
        llamada), dispara el reintento TECNICO externo de Bloque 1 (una
        invocacion mas de evaluate_chunked, que reintenta solo chunk1: 1
        llamada mas). Total fisico esperado: 2 + 1 + 1 = 4."""
        provider = _ScriptedProviderWithWindow([
            _TRUNCATED, _good("fda_part11_agent"),   # chunk0: trunca, reintento inline OK
            _MALFORMED_JSON,                          # chunk1: falla tecnico (no-truncamiento)
            _good("fda_part11_agent"),                # chunk1, reintento tecnico (Bloque 1): OK
        ])

        outcome, _ = _run_unit_real_engine(provider, tmp_path / "ckpt")

        assert provider.calls == 4, (
            "conteo de llamadas fisicas reales debe ser 2 (chunk0: base+inline) "
            "+ 1 (chunk1 base) + 1 (chunk1 retry tecnico Bloque 1) = 4"
        )
        assert outcome.calls_made_this_invocation == provider.calls == 4, (
            "el conteo que corpus_runner reporta debe coincidir EXACTAMENTE "
            "con las llamadas fisicas reales -- ninguna llamada del reintento "
            "inline ni del reintento tecnico debe quedar sin contar"
        )
        assert outcome.status == "COMPLETED"
        assert outcome.technical_execution_failures == 0, "ambos chunks terminan resueltos"

    def test_all_chunks_truncate_twice_hits_the_4x_physical_ceiling_per_chunk(self, tmp_path):
        """Escenario declarado en JUDGMENT_EXECUTION-2026-003 como PEOR CASO
        determinista: chunk0 trunca en la 1a invocacion Y en su reintento
        inline (2 llamadas, technical_execution_failure=True), lo que
        dispara el reintento tecnico externo -- que a su vez tambien
        trunca en su intento base Y en su propio reintento inline (2
        llamadas mas). Total fisico para UN chunk: 4 -- confirma
        deterministicamente el multiplicador 4x usado para derivar
        MAX_PHYSICAL_PROVIDER_CALLS=600 (150 base x 4)."""
        provider = _ScriptedProviderWithWindow([
            _TRUNCATED, _TRUNCATED,   # chunk0, 1a invocacion: base trunca, inline retry TAMBIEN trunca
            _TRUNCATED, _TRUNCATED,   # chunk0, retry tecnico (Bloque1): base trunca, inline retry TAMBIEN trunca
        ])
        pool_one_chunk = [{"chunk_index": 0, "page_start": 1, "page_end": 1, "text": _PAGE_A}]
        import factory.regulatory.retrieval.judgment_candidate_pool as jcp
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(jcp, "build_fusion_candidate_pool",
                      lambda doc_id, sha, req_id, **k: pool_one_chunk)
            outcome, _ = _run_unit_real_engine(provider, tmp_path / "ckpt")

        assert provider.calls == 4, "1 chunk, peor caso -> 4 llamadas fisicas (multiplicador 4x confirmado)"
        assert outcome.calls_made_this_invocation == 4
        assert outcome.technical_execution_failures == 1, (
            "tras agotar AMBOS reintentos (inline + tecnico), el chunk sigue sin "
            "resolverse -- contenido honestamente, nunca fabricado"
        )


class TestJudgmentHardStopBoundaryIsPerUnitNotPerCall:
    """El hard-stop de JUDGMENT_EXECUTION se evalua ANTES de cada UNIDAD
    (contra el total REAL acumulado hasta ese punto + la estimacion BASE de
    la siguiente unidad) -- no hay circuit-breaker por llamada fisica
    individual dentro de una unidad ya admitida. Esto significa que una
    unidad ya en curso puede, por reintentos reales, consumir MAS llamadas
    fisicas que su estimacion base -- el hard-stop no aborta esa unidad a
    mitad de camino. Lo que SI garantiza: la unidad SIGUIENTE se admite
    contra el total REAL (inflado), nunca contra la estimacion base
    obsoleta -- por eso MAX_PHYSICAL_PROVIDER_CALLS=600 (derivado como
    4x del total BASE de las 6 unidades) sigue siendo la cota real del
    LOTE completo, aunque no exista un corte a mitad de una unidad."""

    def test_a_unit_can_physically_exceed_its_own_base_estimate_mid_execution(self, monkeypatch, tmp_path):
        """judgment_hard_stop_calls=2 (exactamente la estimacion BASE de la
        unidad A, pool de 2 chunks). La unidad se ADMITE (2 <= 2) pero su
        ejecucion real, con el reintento tecnico de Bloque 1, gasta 4
        llamadas fisicas -- 2 MAS que el techo autorizado. El runner no
        aborta la unidad a mitad de camino."""
        monkeypatch.setattr(runner, "_select_judgment_execution_instance", lambda *a, **k: {
            "selected_instance_id": "JUDGMENT_EXECUTION-test-tight", "payload": {"max_calls": 2},
        })
        monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 2)

        provider = _ScriptedProviderWithWindow([
            _TRUNCATED, _good("fda_part11_agent"),    # chunk0: trunca, inline retry OK (2 llamadas)
            _MALFORMED_JSON,                           # chunk1: falla tecnico (1 llamada)
            _good("fda_part11_agent"),                 # chunk1, retry tecnico Bloque1: OK (1 llamada)
        ])

        def _fake_run_unit_top_k_fusion(unit, *, checkpoint_store, **kw):
            return _run_unit_real_engine(provider, tmp_path / "ckpt", unit=unit)

        monkeypatch.setattr(runner, "_run_unit_top_k_fusion", _fake_run_unit_top_k_fusion)

        summary = runner.run_corpus_batch(
            [_unit(document_id="DOC-A")], provider=provider,
            checkpoint_dir=tmp_path / "ckpt-outer", manifest_dir=tmp_path / "manifest",
            retrieval_mode="top_k_fusion",
        )

        assert summary.units[0].status == "COMPLETED", "la unidad admitida corre hasta el final, no se aborta a mitad"
        assert summary.total_calls_made == 4, "el consumo REAL (4) excede el techo autorizado (2) -- confirmado, no oculto"
        assert summary.total_calls_made > summary.judgment_hard_stop_calls, (
            "prueba explicita: no existe circuit-breaker por llamada fisica dentro de una unidad ya admitida"
        )

    def test_next_unit_is_refused_against_the_real_inflated_total_not_the_stale_base_estimate(self, monkeypatch, tmp_path):
        """Continuacion del escenario anterior: tras la unidad A gastar 4
        reales (excediendo el techo de 2), la unidad B NUNCA debe arrancar
        -- el chequeo debe usar el total REAL acumulado (4), no la
        estimacion base obsoleta con la que se admitio A."""
        monkeypatch.setattr(runner, "_select_judgment_execution_instance", lambda *a, **k: {
            "selected_instance_id": "JUDGMENT_EXECUTION-test-tight", "payload": {"max_calls": 2},
        })
        monkeypatch.setattr(runner, "_expected_calls_top_k_fusion", lambda unit, **k: 2)

        provider = _ScriptedProviderWithWindow([
            _TRUNCATED, _good("fda_part11_agent"),
            _MALFORMED_JSON,
            _good("fda_part11_agent"),
        ])

        started_units = []

        def _fake_run_unit_top_k_fusion(unit, *, checkpoint_store, **kw):
            started_units.append(unit.document_id)
            return _run_unit_real_engine(provider, tmp_path / "ckpt", unit=unit)

        monkeypatch.setattr(runner, "_run_unit_top_k_fusion", _fake_run_unit_top_k_fusion)

        summary = runner.run_corpus_batch(
            [_unit(document_id="DOC-A"), _unit(document_id="DOC-B")], provider=provider,
            checkpoint_dir=tmp_path / "ckpt-outer", manifest_dir=tmp_path / "manifest",
            retrieval_mode="top_k_fusion",
        )

        assert started_units == ["DOC-A"], "DOC-B nunca debe arrancar -- A ya gasto (real) mas que el techo"
        assert summary.stop_reason == "HARD_STOP_JUDGMENT_CALLS"
        assert summary.units[-1].status == "NOT_STARTED_HARD_STOP"
        assert summary.units[-1].document_id == "DOC-B"


class TestResumePreservesPriorPhysicalConsumption:
    """Dos comportamientos REALES distintos, ambos verificados contra el
    motor real (0 llamadas a Ollama, provider scripteado):

    1. Un run COMPLETADO SIN fallos tecnicos nunca se reabre (`find_
       resumable`, chunked_engine.py:991: "Un run completado SIN fallos
       tecnicos nunca se reabre: solo se permite volver sobre lo que
       fallo tecnicamente"). Esto significa -- confirmado aqui, no
       asumido -- que invocar la MISMA unidad ya completada limpia por
       SEGUNDA vez NO es gratis: se re-ejecuta entera, a costo fisico
       completo otra vez. Relevante en directo para esta sesion: es la
       razon tecnica por la que reautorizar el corpus completo (12
       unidades) en JUDGMENT_EXECUTION-2026-001 hubiera arriesgado
       gasto real duplicado sobre las 6 que Paso A ya completo -- no
       habria resume gratuito que lo evitara.

    2. Lo que SI se preserva es el reintento TECNICO (Bloque 1): si una
       invocacion tiene un chunk con fallo tecnico, el reintento
       selectivo cobra SOLO ese chunk, nunca los que ya resolvieron --
       validado a fondo con motor real en
       test_retry_technical_failures.py::TestRetryTechnicalFailures
       (ya PASS en la suite). Aqui se prueba la integracion con el
       conteo fisico de corpus_runner en la MISMA invocacion (Bloque 1
       de _run_unit_top_k_fusion ya lo ejercita)."""

    def test_a_clean_completed_run_is_never_free_on_a_second_invocation(self, tmp_path):
        ckpt_dir = tmp_path / "ckpt-resume-clean"

        first_provider = _ScriptedProviderWithWindow([_good("fda_part11_agent")])
        outcome1, _ = _run_unit_real_engine(first_provider, ckpt_dir)
        assert first_provider.calls == 2, "pool de 2 chunks, ambos OK a la primera"
        assert outcome1.status == "COMPLETED"
        assert outcome1.technical_execution_failures == 0

        second_provider = _ScriptedProviderWithWindow([_good("fda_part11_agent")])
        outcome2, _ = _run_unit_real_engine(second_provider, ckpt_dir)

        assert second_provider.calls == 2, (
            "un run limpio ya completado NO se reabre (find_resumable) -- "
            "una segunda invocacion de la MISMA unidad la re-ejecuta entera, "
            "a costo fisico completo otra vez. Nunca asumir que repetir el "
            "scope ya hecho por Paso A hubiera sido gratis."
        )
        assert outcome2.calls_made_this_invocation == 2
        assert outcome2.run_ids != outcome1.run_ids, "run_id nuevo -- no es el mismo run reconocido, es uno distinto"

    def test_technical_retry_within_one_invocation_bills_only_the_failed_chunk(self, tmp_path):
        """Bloque 1 de _run_unit_top_k_fusion, en UNA sola invocacion de la
        unidad: chunk0 OK a la primera, chunk1 falla tecnico y se recobra
        con el retry tecnico -- el retry cobra SOLO chunk1 (1 llamada mas),
        nunca vuelve a cobrar chunk0."""
        provider = _ScriptedProviderWithWindow([
            _good("fda_part11_agent"),   # chunk0 OK
            _MALFORMED_JSON,             # chunk1 falla tecnico
            _good("fda_part11_agent"),   # chunk1, retry tecnico Bloque1: OK
        ])
        outcome, _ = _run_unit_real_engine(provider, tmp_path / "ckpt-resume-partial")

        assert provider.calls == 3, "chunk0(1) + chunk1 base(1) + chunk1 retry tecnico(1) -- nunca 4"
        assert outcome.calls_made_this_invocation == provider.calls == 3
        assert outcome.status == "COMPLETED"
        assert outcome.technical_execution_failures == 0, "el retry tecnico resolvio el unico fallo"
