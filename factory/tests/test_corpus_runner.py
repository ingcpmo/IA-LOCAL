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
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg


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
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_default_extractor", lambda path: ["Texto corto de prueba." * 20])
    monkeypatch.setattr(runner, "compute_d4a", lambda **k: {
        "hard_stop_calls": 999, "hard_stop_wall_time_hours": 999.0,
    })


def _run(units, provider=None, tmp_path=None, **kw):
    ckpt = tmp_path / "ckpt" if tmp_path else None
    manifest = tmp_path / "manifest" if tmp_path else None
    kwargs = {}
    if ckpt is not None:
        kwargs["checkpoint_dir"] = ckpt
        kwargs["manifest_dir"] = manifest
    kwargs.update(kw)
    return runner.run_corpus_batch(units, provider=provider or FakeCorpusProvider(), **kwargs)


def test_sin_unidades_no_hace_nada():
    summary = runner.run_corpus_batch([], provider=FakeCorpusProvider())
    assert summary.stop_reason == "NO_UNITS"
    assert summary.units == []


def test_bloqueado_sin_corpus_authorization(monkeypatch):
    monkeypatch.setattr(resolver, "resolve",
                        lambda *a, **k: _AuthorizedScope(authorized=False, denial_reason="no firmada"))
    with pytest.raises(runner.CorpusRunNotAuthorizedError):
        runner.run_corpus_batch([_unit()], provider=FakeCorpusProvider())


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
            provider=FakeCorpusProvider())


def test_bloqueado_si_modelo_no_qualified(monkeypatch):
    monkeypatch.setattr(mqg, "require_inference_authorized",
                        lambda *a, **k: (_ for _ in ()).throw(
                            mqg.InferenceNotAuthorizedError("no qualified")))
    provider = FakeCorpusProvider()
    with pytest.raises(mqg.InferenceNotAuthorizedError):
        runner.run_corpus_batch([_unit()], provider=provider)
    assert provider.generate_calls == 0, "ninguna llamada real si la autorizacion de inferencia fallo"


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

    first = runner.run_corpus_batch([unit], provider=provider,
                                    checkpoint_dir=ckpt, manifest_dir=tmp_path / "m1")
    assert first.units[0].status == "COMPLETED"
    assert first.units[0].technical_execution_failures == 1
    assert first.units[0].calls_made_this_invocation == 2
    calls_after_first = provider.generate_calls
    assert calls_after_first == 2

    second = runner.run_corpus_batch([unit], provider=provider,
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
