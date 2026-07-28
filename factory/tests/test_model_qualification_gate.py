"""Model Qualification Gate (W5 V2 Fase G, seccion 6 del spec).

Lo que estos tests protegen, en orden de importancia:
  1. que el gate NUNCA diga QUALIFIED sin las 13 metricas medidas;
  2. que un caso del Golden Dataset en rojo tumbe la calificacion;
  3. que un cambio de configuracion INVALIDE una calificacion previa --
     el agujero real del 2026-07-28, cuando num_predict y num_ctx cambiaron
     y se corrio una re-evaluacion regulatoria completa sin recalificar.
"""
from __future__ import annotations

import json

import pytest

from factory.regulatory import model_qualification_gate as mqg


class FakeProvider:
    def __init__(self, digest="digest-A", name="modelo-test"):
        self._digest, self._name = digest, name

    @property
    def model_name(self) -> str:
        return self._name

    def generate(self, prompt, *, num_predict=None) -> dict:
        return {}

    def show_digest(self) -> str:
        return self._digest

    def runtime_version(self) -> str:
        return "test-0.0.0"


@pytest.fixture(autouse=True)
def _isolate_record(monkeypatch, tmp_path):
    """Ningun test puede escribir en el registro real de calificacion."""
    monkeypatch.setattr(mqg, "QUALIFICATION_DIR", tmp_path / "mq")
    monkeypatch.setattr(mqg, "RECORD_PATH", tmp_path / "mq" / "qualification_record.json")


def test_las_13_metricas_del_spec_estan_todas_presentes():
    r = mqg.evaluate_model_qualification(FakeProvider())
    assert [m.name for m in r.metrics] == list(mqg.REQUIRED_METRICS)
    assert len(mqg.REQUIRED_METRICS) == 13


def test_estado_actual_es_validation_only_no_qualified():
    """Las 4 metricas de runtime no se pueden medir sin inferencia real, asi
    que el gate no puede declarar QUALIFIED. Que diga otra cosa seria
    inventar rendimiento."""
    r = mqg.evaluate_model_qualification(FakeProvider())
    assert r.status == mqg.STATUS_VALIDATION_ONLY
    assert set(r.unmeasured_metrics) == set(mqg.RUNTIME_ONLY_METRICS)
    assert r.golden_dataset["failed"] == 0


def test_metricas_no_medidas_nunca_valen_cero():
    """Rellenar una metrica ausente con 0 la haria pasar su umbral: es
    exactamente la clase de mentira que el gate existe para impedir."""
    r = mqg.evaluate_model_qualification(FakeProvider())
    for m in r.metrics:
        if not m.measured:
            assert m.value is None
            assert m.passed is None
            assert "NOT_MEASURED" in m.basis


def test_un_caso_golden_en_rojo_tumba_la_calificacion(monkeypatch):
    """Mutacion controlada: se fuerza el fallo de un caso de categoria A
    (anclaje) y el gate debe pasar a NOT_QUALIFIED por la prioridad 1."""
    real = mqg.run_all

    def _con_un_fallo():
        results = real()
        for r in results:
            if r.category == "A":
                r.passed = False
                break
        return results

    monkeypatch.setattr(mqg, "run_all", _con_un_fallo)
    r = mqg.evaluate_model_qualification(FakeProvider())

    assert r.status == mqg.STATUS_NOT_QUALIFIED
    assert "citation_anchor_precision" in r.failed_metrics
    assert r.priority_verdicts[0]["priority"] == "cero_citas_inventadas"
    assert r.priority_verdicts[0]["verdict"] == "FAIL"


def test_prioridades_en_el_orden_normativo_del_spec():
    r = mqg.evaluate_model_qualification(FakeProvider())
    assert [v["priority"] for v in r.priority_verdicts] == [
        "cero_citas_inventadas",
        "menor_tasa_falsos_positivos",
        "menor_tasa_falsos_negativos_criticos",
        "cumplimiento_de_schema",
        "estabilidad",
        "calidad_de_remediacion",
        "rendimiento",
    ]


def test_cambio_de_configuracion_invalida_la_calificacion_previa(monkeypatch):
    """El caso real del 2026-07-28: se persiste una calificacion, cambia
    num_ctx, y la calificacion anterior NO puede heredarse."""
    primera = mqg.evaluate_model_qualification(FakeProvider(), persist=True)
    assert primera.status == mqg.STATUS_VALIDATION_ONLY
    assert mqg.RECORD_PATH.exists()

    from factory.engines.gmpai_integrity import ollama_client
    monkeypatch.setattr(ollama_client, "NUM_CTX", ollama_client.NUM_CTX * 2)

    segunda = mqg.evaluate_model_qualification(FakeProvider())
    assert segunda.status == mqg.STATUS_INVALIDATED
    assert "num_ctx" in segunda.blocking_reason
    assert segunda.previous_fingerprint is not None


def test_cambio_de_modelo_invalida_la_calificacion_previa():
    mqg.evaluate_model_qualification(FakeProvider(digest="digest-A"), persist=True)
    r = mqg.evaluate_model_qualification(FakeProvider(digest="digest-B"))
    assert r.status == mqg.STATUS_INVALIDATED
    assert "model_digest" in r.blocking_reason


def test_misma_configuracion_no_invalida():
    mqg.evaluate_model_qualification(FakeProvider(), persist=True)
    r = mqg.evaluate_model_qualification(FakeProvider())
    assert r.status == mqg.STATUS_VALIDATION_ONLY


def test_fingerprint_incluye_el_presupuesto_de_salida():
    """La formula de output_token_budget entra en el fingerprint: si alguien
    la cambia, la calificacion se invalida. Sin esto, el defecto de
    NUM_PREDICT habria pasado igual de desapercibido."""
    fp = mqg.build_qualification_fingerprint(FakeProvider())
    assert "output_token_budget_formula" in fp
    assert set(fp["output_token_budget_formula"]) == {
        "tokens_per_criterion", "tokens_per_checkpoint", "json_overhead"}
    assert "num_ctx" in fp and "temperature" in fp


def test_guardia_de_produccion_siempre_falla_hoy():
    """PRODUCTION_ENABLEMENT sigue BLOCKED y el gate lo hace explicito."""
    with pytest.raises(mqg.ModelNotQualifiedError) as exc:
        mqg.require_qualified_for_production(FakeProvider())
    assert mqg.STATUS_VALIDATION_ONLY in str(exc.value)


def test_registro_persistido_es_json_valido_y_completo():
    mqg.evaluate_model_qualification(FakeProvider(), persist=True)
    d = json.loads(mqg.RECORD_PATH.read_text(encoding="utf-8"))
    assert d["status"] == mqg.STATUS_VALIDATION_ONLY
    assert len(d["metrics"]) == 13
    assert d["fingerprint"]["model_digest"] == "digest-A"
