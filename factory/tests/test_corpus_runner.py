"""Runner real de la corrida del corpus (corpus_runner.py).

Lo que estos tests protegen, en orden de importancia:
  1. nunca arranca sin CORPUS_AUTHORIZATION vigente +
     require_inference_authorized(run_context='production');
  2. el hard stop de D4-A nunca se cruza -- una unidad (documento, agente)
     cuyo costo esperado no cabe en el presupuesto restante NUNCA arranca;
  3. resume real (mismo checkpoint_dir): una segunda invocacion no repite
     ninguna llamada ya hecha;
  4. un fallo tecnico real (Ollama caido en preflight) se registra en el
     manifiesto y se relanza -- nunca se traga en silencio.

Nunca llama a Ollama real: FakeCorpusProvider responde un checkpoint
generico valido contra checkpoint_llm_response_v1, independiente del
agente/prompt (mismo patron que el resto de la suite W5 V2)."""
from __future__ import annotations

import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.regulatory import corpus_authorization as ca
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg

# Capturada ANTES de que la fixture autouse mockee ca.verify_fingerprint_matches
# -- TestFingerprintEnforcementIntegration la restaura para probar el
# camino real, sin el mock que aisla al resto de este archivo.
_REAL_VERIFY_FINGERPRINT_MATCHES = ca.verify_fingerprint_matches


class FakeCorpusProvider:
    def __init__(self, digest="digest-corpus"):
        self._digest = digest
        self.generate_calls = 0

    @property
    def model_name(self):
        return "modelo-test-corpus"

    @property
    def context_window(self):
        return 16384

    def generate(self, prompt, *, num_predict=None):
        self.generate_calls += 1
        payload = {"checkpoints": [
            {"req_id": "generic", "estado": "evidencia_insuficiente",
             "evidencia_exacta": "", "brecha": "", "recomendacion": ""}
        ]}
        return {"response": json.dumps(payload), "done": True, "done_reason": "stop"}

    def show_digest(self):
        return self._digest

    def runtime_version(self):
        return "test-0.0.0"


class _OllamaDownProvider(FakeCorpusProvider):
    def show_digest(self):
        raise RuntimeError("ollama no alcanzable (simulado)")


class _AuthorizedScope:
    def __init__(self, authorized=True, covering_instances=("INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


def _unit(document_id="DOC-1", agent_id="fda_part11_agent", expected_calls=1, text="Texto corto de prueba."):
    return runner.CorpusRunUnit(
        document_id=document_id, document_type="FS",
        document_path=runner.PROMPTS_DIR,  # no se lee: _default_extractor esta parcheado
        document_sha256="0" * 64, agent_id=agent_id,
        prompt_path=runner._PROMPT_PATH_BY_AGENT[agent_id], expected_calls=expected_calls,
    )


@pytest.fixture(autouse=True)
def _isolate_and_authorize(monkeypatch, tmp_path):
    """Aisla checkpoint/manifest en tmp, autoriza siempre (salvo que un
    test override explicito lo cambie) y evita cualquier escritura real de
    auditoria/registro de calificacion."""
    monkeypatch.setattr(runner, "DEFAULT_CHECKPOINT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(runner, "DEFAULT_MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _AuthorizedScope())
    monkeypatch.setattr(runner, "resolver", resolver)
    # Cierre del gap tecnico (docs_plan, 2026-08-26): _check_corpus_authorization
    # ahora tambien verifica el fingerprint vivo contra el firmado. Estos
    # tests ejercitan OTRA cosa (hard stops, resume, manifest) sobre un
    # decision_instance_id falso ("INST-1") que no existe en ningun
    # almacen real -- se mockea la verificacion de fingerprint aparte,
    # igual que ya se mockea require_inference_authorized, para no atar
    # esta suite a un concern que no le corresponde. La cobertura real de
    # verify_fingerprint_matches vive en test_corpus_authorization.py y en
    # TestFingerprintEnforcement mas abajo.
    monkeypatch.setattr(ca, "verify_fingerprint_matches", lambda *a, **k: {})
    monkeypatch.setattr(runner, "ca", ca)
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto de prueba." * 20])
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 999, "hard_stop_wall_time_hours": 999.0,
    })


def _run(units, provider=None, tmp_path=None, **kw):
    """Default run_context='validation' (Bloque 2,
    docs_plan/DISENO_UNIFICACION_RUNNER_FORMAL.md): estos tests ejercitan
    la MECANICA del runner (resume, hard stops, manifest) con
    retrieval_mode='full_chunk' -- nunca declaran una corrida formal, asi
    que nunca deben chocar con validate_production_run_config(). El guard
    en si mismo tiene su propia clase de tests mas abajo
    (TestProductionRunConfigGuard)."""
    ckpt = tmp_path / "ckpt" if tmp_path else None
    manifest = tmp_path / "manifest" if tmp_path else None
    kwargs = {"run_context": "validation"}
    if ckpt is not None:
        kwargs["checkpoint_dir"] = ckpt
        kwargs["manifest_dir"] = manifest
    kwargs.update(kw)
    return runner.run_corpus_batch(units, provider=provider or FakeCorpusProvider(), **kwargs)


def test_sin_unidades_no_hace_nada():
    summary = runner.run_corpus_batch([], provider=FakeCorpusProvider(), run_context="validation")
    assert summary.stop_reason == "NO_UNITS"
    assert summary.units == []


def test_sin_unidades_no_hace_nada_ni_siquiera_valida_config_de_produccion():
    """NO_UNITS es un no-op legitimo -- no debe fallar por el guard del
    Bloque 2 aunque venga con run_context='production' por default,
    porque no hay ninguna llamada real que arriesgar."""
    summary = runner.run_corpus_batch([], provider=FakeCorpusProvider())
    assert summary.stop_reason == "NO_UNITS"


def test_bloqueado_sin_corpus_authorization(monkeypatch):
    monkeypatch.setattr(resolver, "resolve",
                        lambda *a, **k: _AuthorizedScope(authorized=False, denial_reason="no firmada"))
    with pytest.raises(runner.CorpusRunNotAuthorizedError):
        runner.run_corpus_batch([_unit()], provider=FakeCorpusProvider(), run_context="validation")


def test_bloqueado_si_cobertura_esta_dividida_entre_dos_decisiones(monkeypatch):
    """document_ids con covering_instances DISTINTAS -- nunca se ejecuta un
    lote con cobertura mixta."""
    calls = {"n": 0}

    def fake_resolve(*a, **k):
        calls["n"] += 1
        inst = "INST-1" if calls["n"] == 1 else "INST-2"
        return _AuthorizedScope(covering_instances=(inst,))

    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    with pytest.raises(runner.CorpusRunNotAuthorizedError):
        runner.run_corpus_batch(
            [_unit(document_id="DOC-1"), _unit(document_id="DOC-2")],
            provider=FakeCorpusProvider(), run_context="validation")


def test_bloqueado_si_modelo_no_qualified(monkeypatch):
    monkeypatch.setattr(mqg, "require_inference_authorized",
                        lambda *a, **k: (_ for _ in ()).throw(
                            mqg.InferenceNotAuthorizedError("no qualified")))
    provider = FakeCorpusProvider()
    with pytest.raises(mqg.InferenceNotAuthorizedError):
        runner.run_corpus_batch([_unit()], provider=provider, run_context="validation")
    assert provider.generate_calls == 0, "ninguna llamada real si la autorizacion de inferencia fallo"


class TestFingerprintEnforcementIntegration:
    """Cierre del gap tecnico (docs_plan, 2026-08-26): confirma que
    run_corpus_batch() de verdad invoca la verificacion de fingerprint --
    NO mockeada aqui (a diferencia del resto del archivo, donde
    ca.verify_fingerprint_matches esta mockeada en la fixture autouse para
    aislar otros concerns) -- contra un almacen de decisiones TEMPORAL
    real, con una CORPUS_AUTHORIZATION real firmada via el ciclo
    propose->confirm de gobernanza."""

    @staticmethod
    def _grant_d4_coverage(tmp_decisions, document_ids):
        from factory.services import governance_service as gov
        prop = gov.propose(
            "D4", target_ids=list(document_ids), decision_type="ORIGINAL",
            selection_mode="EXPLICIT_LIST", proposed_by_id="test",
            reason="presupuesto de prueba", payload={"max_calls": 10},
            store_file=tmp_decisions)
        conf = gov.confirm(
            prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
            reason="presupuesto de prueba", family_state_hash=prop["family_state_hash"],
            store_file=tmp_decisions)
        return conf["decision_instance_id"]

    def _authorize_real(self, tmp_decisions, document_ids, provider):
        """Firma una CORPUS_AUTHORIZATION real, de punta a punta, sobre
        `document_ids` con el fingerprint LIMPIO de `provider`. Devuelve el
        decision_instance_id real (nunca "INST-1" -- ese es el fake del
        resto del archivo)."""
        self._grant_d4_coverage(tmp_decisions, document_ids)
        prop = ca.propose_corpus_authorization(
            document_ids, proposed_by_id="test", decision_store_file=tmp_decisions,
            provider=provider)
        from factory.services import governance_service as gov
        conf = gov.confirm(
            prop["proposal_id"], approved_by_id="cesar", approved_by_display_name="Cesar",
            reason="autorizado", family_state_hash=prop["family_state_hash"],
            store_file=tmp_decisions)
        return conf["decision_instance_id"]

    def _unmock_and_authorize(self, monkeypatch, tmp_decisions, instance_id):
        """Restaura el verify_fingerprint_matches REAL (la fixture autouse
        del archivo lo mockea) y apunta resolver.resolve al instance_id
        real recien firmado."""
        monkeypatch.setattr(ca, "verify_fingerprint_matches", _REAL_VERIFY_FINGERPRINT_MATCHES)
        monkeypatch.setattr(resolver, "resolve",
                            lambda *a, **k: _AuthorizedScope(covering_instances=(instance_id,)))

    def test_fingerprint_valido_permite_la_corrida(self, monkeypatch, tmp_path):
        tmp_decisions = tmp_path / "decisions_v2.jsonl"
        tmp_decisions.write_text("", encoding="utf-8")
        provider = FakeCorpusProvider()
        instance_id = self._authorize_real(tmp_decisions, ("DOC-1",), provider)
        self._unmock_and_authorize(monkeypatch, tmp_decisions, instance_id)
        summary = runner.run_corpus_batch(
            [_unit()], provider=provider, decision_store_file=tmp_decisions,
            run_context="validation")
        assert summary.corpus_authorization_id == instance_id
        assert summary.stop_reason != "NOT_AUTHORIZED"

    def test_catalogo_cambiado_bloquea_la_corrida(self, monkeypatch, tmp_path):
        tmp_decisions = tmp_path / "decisions_v2.jsonl"
        tmp_decisions.write_text("", encoding="utf-8")
        provider = FakeCorpusProvider()
        instance_id = self._authorize_real(tmp_decisions, ("DOC-1",), provider)
        self._unmock_and_authorize(monkeypatch, tmp_decisions, instance_id)

        original = mqg.build_qualification_fingerprint

        def _drifted(provider=None):
            fp = dict(original(provider))
            fp["catalog_sha256"] = "0" * 64
            return fp

        monkeypatch.setattr(mqg, "build_qualification_fingerprint", _drifted)
        with pytest.raises(runner.CorpusRunNotAuthorizedError, match="ya no coincide"):
            runner.run_corpus_batch(
                [_unit()], provider=provider, decision_store_file=tmp_decisions,
                run_context="validation")

    def test_prompt_cambiado_bloquea_la_corrida(self, monkeypatch, tmp_path):
        tmp_decisions = tmp_path / "decisions_v2.jsonl"
        tmp_decisions.write_text("", encoding="utf-8")
        provider = FakeCorpusProvider()
        instance_id = self._authorize_real(tmp_decisions, ("DOC-1",), provider)
        self._unmock_and_authorize(monkeypatch, tmp_decisions, instance_id)

        original = mqg.build_qualification_fingerprint

        def _drifted(provider=None):
            fp = dict(original(provider))
            fp["prompt_versions"] = dict(fp["prompt_versions"])
            key = next(iter(fp["prompt_versions"]))
            fp["prompt_versions"][key] = "9.9.9-drift"
            return fp

        monkeypatch.setattr(mqg, "build_qualification_fingerprint", _drifted)
        with pytest.raises(runner.CorpusRunNotAuthorizedError, match="ya no coincide"):
            runner.run_corpus_batch(
                [_unit()], provider=provider, decision_store_file=tmp_decisions,
                run_context="validation")

    def test_autorizacion_inexistente_bloquea_la_corrida(self, monkeypatch, tmp_path):
        """decision_instance_id resuelto por el resolver pero ausente del
        almacen real -- caso degenerado, fail-closed igual."""
        tmp_decisions = tmp_path / "decisions_v2.jsonl"
        tmp_decisions.write_text("", encoding="utf-8")
        monkeypatch.setattr(ca, "verify_fingerprint_matches", _REAL_VERIFY_FINGERPRINT_MATCHES)
        monkeypatch.setattr(resolver, "resolve",
                            lambda *a, **k: _AuthorizedScope(covering_instances=("CORPUS_AUTHORIZATION-2026-999",)))
        with pytest.raises(runner.CorpusRunNotAuthorizedError, match="no se encuentra en el almacén"):
            runner.run_corpus_batch(
                [_unit()], provider=FakeCorpusProvider(), decision_store_file=tmp_decisions,
                run_context="validation")

    def test_documento_fuera_de_scope_bloquea_la_corrida(self, monkeypatch):
        """Ya cubierto por test_bloqueado_sin_corpus_authorization arriba
        (mismo mecanismo: el resolver niega authorized=False) -- se deja
        aqui como referencia explicita del quinto caso pedido, sin
        duplicar aserciones."""
        monkeypatch.setattr(resolver, "resolve",
                            lambda *a, **k: _AuthorizedScope(authorized=False, denial_reason="fuera de scope"))
        with pytest.raises(runner.CorpusRunNotAuthorizedError, match="fuera de scope"):
            runner.run_corpus_batch([_unit()], provider=FakeCorpusProvider(), run_context="validation")


class TestProductionRunConfigGuard:
    """Bloque 2: reproduce EXACTAMENTE la desviacion real de
    fase5_produccion_real_fixture7p2n_20260820 (run_context de produccion +
    retrieval_mode='full_chunk') y confirma que ahora se bloquea ANTES de
    cualquier llamada real -- y que la configuracion correcta (H2H4 vimplicito
    via top_k_fusion) no se bloquea."""

    def test_produccion_con_full_chunk_se_bloquea_como_en_fase5(self):
        """Mismo caso real que broke silenciosamente el 2026-08-20: sin
        pasar run_context (default='production') ni retrieval_mode (default
        ='full_chunk'), exactamente como fase5_produccion_real_fixture7p2n.py
        invoco run_corpus_batch()."""
        provider = FakeCorpusProvider()
        with pytest.raises(runner.ProductionRunConfigError) as exc:
            runner.run_corpus_batch([_unit()], provider=provider)
        assert provider.generate_calls == 0, "cero llamadas reales -- el guard corre primero"
        message = str(exc.value)
        assert "full_chunk" in message and "top_k_fusion" in message

    def test_produccion_con_full_chunk_explicito_tambien_se_bloquea(self):
        provider = FakeCorpusProvider()
        with pytest.raises(runner.ProductionRunConfigError):
            runner.run_corpus_batch([_unit()], provider=provider,
                                    run_context="production", retrieval_mode="full_chunk")
        assert provider.generate_calls == 0

    def test_validation_con_full_chunk_no_se_bloquea(self):
        """run_context='validation' sigue libre de elegir su config, como
        hasta ahora -- el guard es especifico de 'production'."""
        summary = runner.run_corpus_batch([_unit()], provider=FakeCorpusProvider(),
                                          run_context="validation", retrieval_mode="full_chunk")
        assert summary.stop_reason == "CORPUS_COMPLETE"

    def test_pilot_run_context_nunca_pasa_por_este_guard(self):
        """run_pilot_sample_batch no llama a validate_production_run_config
        -- es una familia de gobernanza distinta (PILOT_EXECUTION, no
        CORPUS_AUTHORIZATION/D4-A). Confirmado por inspeccion: el guard vive
        solo en run_corpus_batch."""
        import inspect
        source = inspect.getsource(runner.run_pilot_sample_batch)
        assert "validate_production_run_config" not in source

    def test_validate_production_run_config_es_funcion_publica_reutilizable(self):
        """Expuesta a nivel de modulo (no _prefijada) para que un futuro
        llamador -- o un test dedicado -- pueda invocarla directamente sin
        pasar por toda la mecanica de run_corpus_batch."""
        runner.validate_production_run_config(run_context="validation", retrieval_mode="full_chunk")
        runner.validate_production_run_config(run_context="production", retrieval_mode="top_k_fusion")
        with pytest.raises(runner.ProductionRunConfigError):
            runner.validate_production_run_config(run_context="production", retrieval_mode="full_chunk")


def test_hard_stop_detiene_antes_de_una_unidad_que_no_cabe(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 1, "hard_stop_wall_time_hours": 999.0,
    })
    units = [_unit(document_id="DOC-1", expected_calls=1),
             _unit(document_id="DOC-2", expected_calls=1)]
    summary = _run(units, tmp_path=tmp_path)
    assert summary.stop_reason == "HARD_STOP_CALLS"
    assert summary.units[0].status == "COMPLETED"
    assert summary.units[1].status == "NOT_STARTED_HARD_STOP"
    assert summary.units[1].document_id == "DOC-2"


def test_lote_completo_sin_hard_stop_ejecuta_todas_las_unidades(tmp_path):
    units = [_unit(document_id="DOC-1"), _unit(document_id="DOC-2")]
    summary = _run(units, tmp_path=tmp_path)
    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert [u.status for u in summary.units] == ["COMPLETED", "COMPLETED"]
    assert summary.total_calls_made == 2


def test_manifest_persistido_con_resumen_real(tmp_path):
    summary = _run([_unit()], tmp_path=tmp_path)
    assert summary.manifest_path is not None
    payload = json.loads(open(summary.manifest_path, encoding="utf-8").read())
    assert payload["stop_reason"] == "CORPUS_COMPLETE"
    assert payload["units"][0]["status"] == "COMPLETED"


class _FlakyProvider(FakeCorpusProvider):
    """Falla tecnicamente en su primera llamada (simula una caida
    transitoria de Ollama en 1 chunk), correcta en las siguientes --
    incluida la del reintento dirigido de la segunda invocacion."""

    def __init__(self, fail_on_call=1):
        super().__init__()
        self._fail_on_call = fail_on_call

    def generate(self, prompt, *, num_predict=None):
        self.generate_calls += 1
        if self.generate_calls == self._fail_on_call:
            raise RuntimeError("fallo tecnico simulado (transitorio)")
        payload = {"checkpoints": [
            {"req_id": "generic", "estado": "evidencia_insuficiente",
             "evidencia_exacta": "", "brecha": "", "recomendacion": ""}
        ]}
        return {"response": json.dumps(payload), "done": True, "done_reason": "stop"}


def test_resume_reintenta_solo_el_chunk_que_fallo_tecnicamente(monkeypatch, tmp_path):
    """2 chunks reales; el provider falla SOLO en la primera llamada (chunk
    0). La corrida completa igual (1 fallo tecnico, no se aborta). La
    segunda invocacion (mismo checkpoint_dir, retry_technical_failures=True
    ya activo en el runner) debe reintentar UNICAMENTE el chunk fallido --
    nunca repetir el que ya tuvo exito."""
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["A" * 7000, "B" * 7000])
    provider = _FlakyProvider(fail_on_call=1)
    ckpt = tmp_path / "ckpt"
    unit = _unit(expected_calls=2)

    first = runner.run_corpus_batch([unit], provider=provider, run_context="validation",
                                    checkpoint_dir=ckpt, manifest_dir=tmp_path / "m1")
    assert first.units[0].status == "COMPLETED"
    assert first.units[0].technical_execution_failures == 1
    assert first.units[0].calls_made_this_invocation == 2
    calls_after_first = provider.generate_calls
    assert calls_after_first == 2

    second = runner.run_corpus_batch([unit], provider=provider, run_context="validation",
                                     checkpoint_dir=ckpt, manifest_dir=tmp_path / "m2")
    assert second.units[0].status == "COMPLETED"
    assert second.units[0].calls_made_this_invocation == 1, "solo se reintenta el chunk fallido"
    assert second.units[0].resumed_chunk_count == 1, "el chunk exitoso se reusa, nunca se repite"
    assert second.units[0].technical_execution_failures == 0, "el reintento tuvo exito"
    assert provider.generate_calls == calls_after_first + 1


def test_fallo_tecnico_en_preflight_se_registra_y_se_relanza(tmp_path):
    provider = _OllamaDownProvider()
    with pytest.raises(RuntimeError, match="ollama no alcanzable"):
        _run([_unit()], provider=provider, tmp_path=tmp_path)


def test_plan_corpus_units_real_reproduce_d4a_232_llamadas():
    """Integracion real (sin Ollama, sin monkeypatch): plan_corpus_units()
    contra el allowlist real y los 5 PDF reales de Rockwell debe reproducir
    EXACTAMENTE max_calls=232 de D4-2026-003 -- si un archivo se mueve, un
    hash cambia, o R(d,a) se desalinea con corpus_budget_formula, este test
    lo detecta antes que una corrida real de 71 horas."""
    units = runner.plan_corpus_units()
    assert len(units) == 20  # 5 documentos x 4 agentes, todos con R(d,a) != vacio
    assert sum(u.expected_calls for u in units) == 232
    assert {u.document_id for u in units} == {"RW-0005", "RW-0006", "RW-0011", "RW-0012", "RW-0014"}
    for u in units:
        assert u.document_path.is_file()
        assert len(u.document_sha256) == 64
