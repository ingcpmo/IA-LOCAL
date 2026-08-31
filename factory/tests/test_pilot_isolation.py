"""Aislamiento del piloto de diagnóstico pre-corpus (`corpus_runner.
run_pilot_sample_batch`, `pilot_execution.py`) -- plan
`W5V2_PILOTO_DIAGNOSTICO_PRECORPUS.md` §2.

Lo que estos tests protegen, en orden de importancia:
  1. un run `run_context='pilot'` NUNCA arranca con `CORPUS_AUTHORIZATION`/
     `D4` -- solo con la familia SEPARADA `PILOT_EXECUTION`, y viceversa:
     firmar `PILOT_EXECUTION` nunca satisface `CORPUS_AUTHORIZATION`;
  2. el tope duro de llamadas del piloto viene de `PILOT_EXECUTION.
     payload['max_calls']`, nunca de `compute_d4a()` (presupuesto formal);
  3. checkpoint_dir/manifest_dir del piloto son rutas físicamente distintas
     de las de producción -- un resume/manifest formal no puede leer nada
     escrito por un piloto, ni al revés;
  4. `run_pilot_sample_batch` nunca escribe en `CORPUS_PLAN_DOCUMENTS` ni
     afecta ningún estado que `plan_corpus_units()`/`run_corpus_batch()`
     (formales) consulten.

Nunca llama a Ollama real: mismo `FakeCorpusProvider` que
`test_corpus_runner.py`."""
from __future__ import annotations

import json

import pytest

from factory.core import decision_scope_resolver as resolver
from factory.regulatory import corpus_runner as runner
from factory.regulatory import model_qualification_gate as mqg
from factory.tests.test_corpus_runner import FakeCorpusProvider

#: Capturada ANTES de que el fixture autouse la reemplace por un no-op en
#: cada test -- es la única forma de recuperar la implementación real dentro
#: de un test que sí quiere observarla.
_REAL_WRITE_BATCH_EVENT = runner._write_batch_event


class _Scope:
    def __init__(self, authorized=True, covering_instances=("PILOT-INST-1",), denial_reason=None):
        self.authorized = authorized
        self.covering_instances = set(covering_instances)
        self.denial_reason = denial_reason


def _sample_unit(document_id="RW-0011", agent_id="fda_part11_agent",
                 requirement_id="PART11_1", page_indices=(0,)):
    return runner.PilotSampleUnit(
        document_id=document_id, document_type="DS", agent_id=agent_id,
        requirement_id=requirement_id, page_indices=page_indices,
        selection_reason="fixture de test, no un caso real seleccionado")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "PILOT_CHECKPOINT_DIR", tmp_path / "pilot_checkpoints")
    monkeypatch.setattr(runner, "PILOT_MANIFEST_DIR", tmp_path / "pilot_manifests")
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)
    monkeypatch.setattr(runner, "_write_batch_event", lambda *a, **k: None)
    monkeypatch.setattr(runner, "_resolve_document_path",
                        lambda doc_id: (runner.PROMPTS_DIR, "0" * 64))
    monkeypatch.setattr(runner, "_extract_pilot_excerpt",
                        lambda path, page_indices: ["Texto corto real de prueba." * 10
                                                     for _ in page_indices])


def _run_pilot(units, tmp_path, provider=None, **kw):
    """Mismo patron que test_corpus_runner.py::_run -- checkpoint_dir/
    manifest_dir SIEMPRE explicitos en tmp_path. El default de
    run_pilot_sample_batch se resuelve en tiempo de DEFINICION de la
    funcion (no de llamada), asi que parchear el modulo PILOT_CHECKPOINT_DIR/
    PILOT_MANIFEST_DIR no alcanza para aislar un test que no pase la ruta
    explicita -- sin esto, un test real escribe en
    factory/regulatory/pilot_run/ (visto y corregido en esta sesion)."""
    kwargs = {"checkpoint_dir": tmp_path / "ckpt", "manifest_dir": tmp_path / "manifest"}
    kwargs.update(kw)
    return runner.run_pilot_sample_batch(units, provider=provider or FakeCorpusProvider(), **kwargs)


def _authorize_pilot(monkeypatch, *, max_calls=12, authorized=True, denial_reason=None):
    def fake_resolve(family, target_id, *, store_file=None):
        assert family == "PILOT_EXECUTION", (
            f"run_pilot_sample_batch consultó la familia {family!r}, no PILOT_EXECUTION")
        return _Scope(authorized=authorized, denial_reason=denial_reason)
    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1",
         "payload": {"max_calls": max_calls, "authorizes_corpus": False,
                     "authorizes_baseline": False}},
    ])


# ===========================================================================
# 1. Familia separada -- nunca CORPUS_AUTHORIZATION/D4
# ===========================================================================

def test_pilot_sample_batch_consulta_solo_pilot_execution(monkeypatch, tmp_path):
    """Si el runner consultara CORPUS_AUTHORIZATION/D4 por error, el assert
    dentro de fake_resolve lo revienta antes de llegar a ejecutar nada."""
    _authorize_pilot(monkeypatch)
    summary = _run_pilot([_sample_unit()], tmp_path)
    assert summary.stop_reason == "CORPUS_COMPLETE"
    assert summary.units[0].status == "COMPLETED"


def test_pilot_sample_batch_bloqueado_sin_pilot_execution_firmada(monkeypatch):
    _authorize_pilot(monkeypatch, authorized=False, denial_reason="PILOT_EXECUTION no firmada")
    with pytest.raises(runner.CorpusRunNotAuthorizedError, match="PILOT_EXECUTION"):
        runner.run_pilot_sample_batch([_sample_unit()], provider=FakeCorpusProvider())


def test_pilot_execution_nunca_declara_autorizar_corpus_ni_baseline():
    """Guardia sobre el propio contrato de payload -- `propose_pilot_execution`
    SIEMPRE fija estos dos campos en False, nunca los deja como parámetro."""
    import inspect

    from factory.regulatory import pilot_execution as pe

    src = inspect.getsource(pe.propose_pilot_execution)
    assert '"authorizes_corpus": False' in src
    assert '"authorizes_baseline": False' in src


def test_corpus_authorization_family_nunca_consulta_pilot_execution():
    """`_check_corpus_authorization` (formal) usa la familia de
    `corpus_authorization.DECISION_FAMILY` -- NUNCA `PILOT_EXECUTION` --
    verificado leyendo la fuente, no solo el comportamiento en runtime."""
    import inspect

    from factory.regulatory import corpus_authorization as ca

    src = inspect.getsource(ca.propose_corpus_authorization) + inspect.getsource(
        runner._check_corpus_authorization)
    assert "PILOT_EXECUTION" not in src
    assert "resolver.resolve(ca.DECISION_FAMILY" in inspect.getsource(runner._check_corpus_authorization)


# ===========================================================================
# 2. Tope duro del piloto viene de PILOT_EXECUTION.max_calls, nunca de D4-A
# ===========================================================================

def test_hard_stop_usa_max_calls_de_pilot_execution_no_compute_d4a(monkeypatch, tmp_path):
    calls = {"n": 0}

    def _boom(**k):
        calls["n"] += 1
        raise AssertionError("run_pilot_sample_batch no debe llamar a compute_d4a()")

    monkeypatch.setattr(runner, "compute_d4a", _boom)
    _authorize_pilot(monkeypatch, max_calls=1)
    units = [_sample_unit(document_id="RW-0011", page_indices=(0,)),
             _sample_unit(document_id="RW-0012", page_indices=(0,))]
    summary = _run_pilot(units, tmp_path)
    assert calls["n"] == 0
    assert summary.stop_reason == "HARD_STOP_CALLS"
    assert summary.units[0].status == "COMPLETED"
    assert summary.units[1].status == "NOT_STARTED_HARD_STOP"


def test_pilot_execution_sin_max_calls_valido_bloquea(monkeypatch):
    _authorize_pilot(monkeypatch)
    monkeypatch.setattr(runner.decision_store, "read_all", lambda store_file=None: [
        {"decision_instance_id": "PILOT-INST-1", "payload": {"authorizes_corpus": False}},
    ])
    with pytest.raises(runner.CorpusRunNotAuthorizedError, match="max_calls"):
        runner.run_pilot_sample_batch([_sample_unit()], provider=FakeCorpusProvider())


# ===========================================================================
# 3. Aislamiento físico de rutas -- nunca las de producción
# ===========================================================================

def test_checkpoint_y_manifest_dirs_del_piloto_nunca_coinciden_con_produccion():
    assert runner.PILOT_CHECKPOINT_DIR != runner.DEFAULT_CHECKPOINT_DIR
    assert runner.PILOT_MANIFEST_DIR != runner.DEFAULT_MANIFEST_DIR
    assert "pilot" in str(runner.PILOT_CHECKPOINT_DIR)
    assert "pilot" in str(runner.PILOT_MANIFEST_DIR)
    assert "pilot" in str(runner.PILOT_OUTPUT_DIR)


def test_manifest_del_piloto_se_escribe_en_su_propio_directorio(monkeypatch, tmp_path):
    _authorize_pilot(monkeypatch)
    ckpt = tmp_path / "ckpt"
    manifest_dir = tmp_path / "manifest"
    summary = runner.run_pilot_sample_batch(
        [_sample_unit()], provider=FakeCorpusProvider(),
        checkpoint_dir=ckpt, manifest_dir=manifest_dir)
    assert summary.manifest_path is not None
    assert str(manifest_dir) in summary.manifest_path
    payload = json.loads(open(summary.manifest_path, encoding="utf-8").read())
    assert payload["units"][0]["status"] == "COMPLETED"


def test_write_batch_event_declara_run_context_pilot(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(runner, "write_event", lambda name, svc, payload: captured.update(payload))
    monkeypatch.setattr(runner, "_write_batch_event", _REAL_WRITE_BATCH_EVENT)
    _authorize_pilot(monkeypatch)
    runner.run_pilot_sample_batch(
        [_sample_unit()], provider=FakeCorpusProvider(),
        checkpoint_dir=tmp_path / "ckpt", manifest_dir=tmp_path / "manifest")
    assert captured["run_context"] == "pilot"


# ===========================================================================
# 4. run_context='pilot' es un valor real aceptado por el motor
# ===========================================================================

def test_chunked_engine_acepta_run_context_pilot():
    from factory.engines.gmpai_integrity import chunked_engine as ce

    with pytest.raises(ValueError, match="pilot"):
        # 'bogus' sigue rechazado -- el mensaje de error ahora menciona
        # 'pilot' como valor valido, prueba de que el whitelist se extendio
        # (y no que se abrio por completo).
        ce.evaluate_chunked(
            runner.PROMPTS_DIR, agent_id="x", agent_version="v1", per_unit_text=[],
            sistema="s", documento="d", version="v", archivo="a", document_sha256="0" * 64,
            run_context="bogus")


def test_chunked_engine_rechaza_valores_no_declarados():
    from factory.engines.gmpai_integrity import chunked_engine as ce

    for bad in ("production ", "PILOT", "corpus", ""):
        with pytest.raises(ValueError):
            ce.evaluate_chunked(
                runner.PROMPTS_DIR, agent_id="x", agent_version="v1", per_unit_text=[],
                sistema="s", documento="d", version="v", archivo="a", document_sha256="0" * 64,
                run_context=bad)


# ===========================================================================
# 5. Guard duro: PILOT_EXECUTION nunca aparece en la cobertura de D4/
#    CORPUS_AUTHORIZATION, ni siquiera con cobertura "accidentalmente
#    completa" (mismo documento firmado en ambas familias)
# ===========================================================================

def test_pilot_execution_firmada_no_autoriza_run_corpus_batch_formal(monkeypatch, tmp_path):
    """Un documento con PILOT_EXECUTION vigente pero SIN CORPUS_AUTHORIZATION
    debe seguir bloqueado para la corrida formal -- las familias nunca se
    mezclan, aunque cubran el mismo document_id."""
    def fake_resolve(family, target_id, *, store_file=None):
        if family == "PILOT_EXECUTION":
            return _Scope(authorized=True)
        return _Scope(authorized=False, denial_reason="solo PILOT_EXECUTION esta firmada")

    monkeypatch.setattr(resolver, "resolve", fake_resolve)
    monkeypatch.setattr(runner, "resolver", resolver)
    monkeypatch.setattr(mqg, "require_inference_authorized", lambda *a, **k: None)
    monkeypatch.setattr(runner, "mqg", mqg)

    unit = runner.CorpusRunUnit(
        document_id="RW-0011", document_type="DS", document_path=runner.PROMPTS_DIR,
        document_sha256="0" * 64, agent_id="fda_part11_agent",
        prompt_path=runner._PROMPT_PATH_BY_AGENT["fda_part11_agent"], expected_calls=1)
    with pytest.raises(runner.CorpusRunNotAuthorizedError):
        runner.run_corpus_batch([unit], provider=FakeCorpusProvider(), run_context="validation",
                                checkpoint_dir=tmp_path / "ckpt", manifest_dir=tmp_path / "manifest")
