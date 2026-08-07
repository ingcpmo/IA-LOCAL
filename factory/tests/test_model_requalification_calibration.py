"""Corrida real de calibracion de rendimiento (model_requalification_calibration.py).

Lo que estos tests protegen, en orden de importancia:
  1. que la corrida real NUNCA se ejecute sin pasar por
     require_inference_authorized() con run_context='model_requalification';
  2. que las 4 metricas medidas SOLO se incorporen a
     evaluate_model_qualification() cuando el fingerprint coincide EXACTO
     (una calibracion contra otra configuracion no es evidencia valida);
  3. que 0 llamadas reales nunca produzca una metrica inventada.

Nunca llama a Ollama real: FakeProvider (mismo patron que
test_model_qualification_gate.py) simula respuestas deterministas con
eval_count/prompt_eval_count reales del contrato de la API de Ollama.
"""
from __future__ import annotations

import json

import pytest

from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory import model_requalification_calibration as calib


class FakeCalibrationProvider:
    """Simula OllamaProvider: cada generate() devuelve un checkpoint valido
    para el req_id del prompt, con eval_count/prompt_eval_count/done_reason
    reales del contrato de /api/generate (nunca stream=false parcial)."""

    def __init__(self, digest="digest-A", name="modelo-test", eval_count=42):
        self._digest, self._name, self._eval_count = digest, name, eval_count

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def context_window(self) -> int:
        return 16384

    def generate(self, prompt, *, num_predict=None) -> dict:
        payload = {"checkpoints": [
            {"req_id": "21_CFR_11.10(a)", "estado": "evidencia_insuficiente",
             "evidencia_exacta": "", "brecha": "n/a", "recomendacion": "n/a"}
        ]}
        return {
            "response": json.dumps(payload),
            "done": True, "done_reason": "stop",
            "prompt_eval_count": 900, "eval_count": self._eval_count,
        }

    def show_digest(self) -> str:
        return self._digest

    def runtime_version(self) -> str:
        return "test-0.0.0"


class _TransportFailingProvider(FakeCalibrationProvider):
    """Primera llamada devuelve JSON invalido (falla tecnica real);
    verifica que retry_rate > 0 se calcula sobre chunk_executions reales,
    no se inventa."""

    def generate(self, prompt, *, num_predict=None) -> dict:
        return {"response": "esto no es json", "done": True,
                "done_reason": "stop", "prompt_eval_count": 900, "eval_count": 5}


@pytest.fixture(autouse=True)
def _isolate_records(monkeypatch, tmp_path):
    """Ningun test escribe en los registros reales de calificacion/calibracion."""
    qdir = tmp_path / "mq"
    monkeypatch.setattr(mqg, "QUALIFICATION_DIR", qdir)
    monkeypatch.setattr(mqg, "RECORD_PATH", qdir / "qualification_record.json")
    monkeypatch.setattr(calib, "CALIBRATION_DIR", qdir)
    monkeypatch.setattr(calib, "CALIBRATION_RECORD_PATH", qdir / "runtime_calibration_record.json")


def test_calibracion_exige_autorizacion_antes_de_la_primera_llamada(monkeypatch):
    """Si require_inference_authorized() bloquea, no debe ejecutarse ninguna
    llamada real al provider -- la autorizacion es una guardia previa, no
    un chequeo posterior."""
    calls = []
    monkeypatch.setattr(mqg, "require_inference_authorized",
                        lambda *a, **k: (_ for _ in ()).throw(
                            mqg.InferenceNotAuthorizedError("bloqueado")))

    class SpyProvider(FakeCalibrationProvider):
        def generate(self, prompt, *, num_predict=None):
            calls.append(1)
            return super().generate(prompt, num_predict=num_predict)

    with pytest.raises(mqg.InferenceNotAuthorizedError):
        calib.run_runtime_calibration(SpyProvider())
    assert calls == [], "ninguna llamada real debe ocurrir si la autorizacion fallo"


def test_corrida_real_produce_2_llamadas_y_las_4_metricas():
    record = calib.run_runtime_calibration(FakeCalibrationProvider())
    assert record["n_calls"] == 2
    for name in mqg.RUNTIME_ONLY_METRICS:
        assert record["metrics"][name] is not None
    assert record["metrics"]["tokens_per_task"] == 42


def test_retry_rate_refleja_fallos_tecnicos_reales():
    record = calib.run_runtime_calibration(_TransportFailingProvider())
    assert record["metrics"]["retry_rate"] == 1.0


def test_calibracion_con_fingerprint_distinto_no_se_incorpora(tmp_path):
    """Persistir una calibracion y luego calificar con OTRO provider (otro
    digest -> otro fingerprint) no debe heredar las metricas: es la misma
    doctrina de QUALIFICATION_INVALIDATED aplicada a la calibracion."""
    calib.run_runtime_calibration(FakeCalibrationProvider(digest="digest-A"), persist=True)
    r = mqg.evaluate_model_qualification(FakeCalibrationProvider(digest="digest-B"))
    assert r.status == mqg.STATUS_VALIDATION_ONLY
    assert set(r.unmeasured_metrics) == set(mqg.RUNTIME_ONLY_METRICS)


def test_calibracion_con_fingerprint_coincidente_habilita_qualified():
    """Persistir una calibracion real y luego calificar con el MISMO
    provider (mismo fingerprint) debe incorporar las 4 metricas medidas y
    llegar a QUALIFIED pleno -- el Golden Dataset ya da 0 fallidas."""
    provider = FakeCalibrationProvider()
    calib.run_runtime_calibration(provider, persist=True)
    r = mqg.evaluate_model_qualification(provider)
    assert r.status == mqg.STATUS_QUALIFIED
    assert r.unmeasured_metrics == []
    for name in mqg.RUNTIME_ONLY_METRICS:
        m = next(x for x in r.metrics if x.name == name)
        assert m.measured is True
        assert m.passed is True


def test_cero_llamadas_nunca_produce_metricas_inventadas(monkeypatch):
    """Si evaluate_chunked() no ejecuta ningun chunk (texto vacio), la
    corrida debe fallar explicito, nunca reportar 0.0 como si fuera una
    medicion real."""
    monkeypatch.setattr(calib, "CALIBRATION_PAGES", ["", ""])
    with pytest.raises(calib.CalibrationProducedNoCallsError):
        calib.run_runtime_calibration(FakeCalibrationProvider())
