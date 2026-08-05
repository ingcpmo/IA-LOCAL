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


def test_las_metricas_del_spec_estan_todas_presentes_y_en_orden():
    """El invariante es que el resultado trae EXACTAMENTE las metricas
    requeridas, en su orden. El `len(REQUIRED_METRICS) == 13` que habia
    debajo solo repetia el tamano de la constante de al lado: no podia
    fallar sin que fallara antes la linea anterior, y obligaba a editar dos
    sitios para anadir una metrica."""
    r = mqg.evaluate_model_qualification(FakeProvider())
    assert [m.name for m in r.metrics] == list(mqg.REQUIRED_METRICS)
    assert len(set(mqg.REQUIRED_METRICS)) == len(mqg.REQUIRED_METRICS), "sin duplicados"


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


def test_fingerprint_incluye_el_hash_del_golden_dataset():
    """Q-09 (G6, MODEL_REQUALIFICATION_AND_D4A_SPEC.md hallazgo D-1): sin el
    hash del Golden Dataset en el fingerprint, dos calificaciones con el
    mismo resto de campos podrian haberse medido contra datasets DISTINTOS
    -- el patron de referencia mutable invalidaria la medicion sin que nada
    lo notara. Reutiliza el mismo hash de AST que artifact_version_guard."""
    from factory.core.artifact_version_guard import GOLDEN_PATH, canonical_hash_golden

    fp = mqg.build_qualification_fingerprint(FakeProvider())
    assert "golden_dataset_sha256" in fp
    assert fp["golden_dataset_sha256"] == canonical_hash_golden(GOLDEN_PATH)


def test_guardia_de_produccion_siempre_falla_hoy():
    """PRODUCTION_ENABLEMENT sigue BLOCKED y el gate lo hace explicito."""
    with pytest.raises(mqg.ModelNotQualifiedError) as exc:
        mqg.require_qualified_for_production(FakeProvider())
    assert mqg.STATUS_VALIDATION_ONLY in str(exc.value)


def test_registro_persistido_es_json_valido_y_completo():
    mqg.evaluate_model_qualification(FakeProvider(), persist=True)
    d = json.loads(mqg.RECORD_PATH.read_text(encoding="utf-8"))
    assert d["status"] == mqg.STATUS_VALIDATION_ONLY
    assert len(d["metrics"]) == len(mqg.REQUIRED_METRICS)
    assert d["fingerprint"]["model_digest"] == "digest-A"


# ---------------------------------------------------------------------------
# G6 §4.1 -- guardia de inferencia (Q-05/Q-06/Q-07 de
# MODEL_REQUALIFICATION_AND_D4A_SPEC.md §7)
# ---------------------------------------------------------------------------

def test_q05_metadata_query_allowed_even_when_invalidated():
    mqg.require_inference_authorized(
        mqg.STATUS_NOT_QUALIFIED, call_type=mqg.CALL_TYPE_METADATA,
        run_context="production")  # no debe lanzar


def test_q06_inference_blocked_unless_qualified_or_requalifying():
    with pytest.raises(mqg.InferenceNotAuthorizedError, match="inferencia bloqueada"):
        mqg.require_inference_authorized(
            mqg.STATUS_VALIDATION_ONLY, call_type=mqg.CALL_TYPE_INFERENCE,
            run_context="production")


def test_q06_inference_allowed_when_qualified():
    mqg.require_inference_authorized(
        mqg.STATUS_QUALIFIED, call_type=mqg.CALL_TYPE_INFERENCE,
        run_context="production")  # no debe lanzar


def test_q07_requalification_run_context_only_valid_against_golden_dataset():
    # contra el Golden Dataset: autorizado pese a no estar QUALIFIED.
    mqg.require_inference_authorized(
        mqg.STATUS_NOT_QUALIFIED, call_type=mqg.CALL_TYPE_INFERENCE,
        run_context=mqg.RUN_CONTEXT_MODEL_REQUALIFICATION,
        target=mqg.GOLDEN_DATASET_TARGET)  # no debe lanzar

    # contra un documento real: NUNCA, ni con run_context=model_requalification.
    with pytest.raises(mqg.InferenceNotAuthorizedError, match="GOLDEN DATASET"):
        mqg.require_inference_authorized(
            mqg.STATUS_NOT_QUALIFIED, call_type=mqg.CALL_TYPE_INFERENCE,
            run_context=mqg.RUN_CONTEXT_MODEL_REQUALIFICATION,
            target="factory/workspaces/gmpai_document_validation/data/RW-0005.pdf")


# ---------------------------------------------------------------------------
# G6 §2 -- las 5 precondiciones de recalificacion (Q-08 de la tabla del spec)
# ---------------------------------------------------------------------------

def test_q08_two_real_preconditions_remain_open_today():
    """Estado real de hoy, segunda actualizacion (2026-08-05): G4c
    (ARTIFACT_VERSION-2026-007, bump del catalogo) y G6 (ARTIFACT_VERSION-
    2026-009, primera aprobacion del golden dataset) siguen cerrados con
    firmas reales de Cesar. G4b (matriz) REABRIO: la matriz cambio de
    version otra vez (2.1->2.2, panel D2-A/G5, +4 document_types) y esa
    nueva version todavia no tiene su propia decision humana
    (APPLICABILITY_MATRIX-2026-005 sigue PROPOSED) -- mismo patron exacto
    que ya paso una vez con el catalogo antes de G4c. Si alguna precondicion
    pasa sin que Cesar haya firmado nada, este test lo detecta."""
    r = mqg.requalification_preconditions()
    assert r.ready is False
    assert r.sources_verified is False
    assert r.pack_211_complete is False
    assert r.matrix_approved is False
    assert r.catalog_versioned is True
    assert r.golden_dataset_approved is True
    assert len(r.reasons) == 3
    assert all(isinstance(x, str) and x for x in r.reasons)


def test_q08_ready_only_when_the_five_are_true(monkeypatch):
    """Camino positivo: si las 5 fuentes de verdad reales dicen que TODO esta
    en orden, `ready` es True -- el agregador no esta encadenado a devolver
    False siempre por construccion."""
    import factory.regulatory.model_qualification_gate as mqg_mod
    from factory.core import decision_scope_resolver as resolver
    from factory.regulatory import applicability as applicability_mod
    from factory.regulatory import source_lifecycle
    from factory.regulatory import evidence_pack_governance as epg

    class _AllVerified:
        lifecycle_state = source_lifecycle.LOCAL_CANONICAL_COPY_VERIFIED
        source_id = "x"

    class _Authorized:
        authorized = True
        coverage_basis = "HUMAN_CONFIRMED_EXPLICIT"

    class _PackPassed:
        passed = True
        failures = ()
        def failure_codes(self): return ()

    monkeypatch.setattr(source_lifecycle, "evaluate_registry",
                        lambda: [_AllVerified(), _AllVerified(), _AllVerified(), _AllVerified()])
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _Authorized())
    monkeypatch.setattr(applicability_mod, "load_matrix", lambda: {"matrix_version": "2.1"})
    monkeypatch.setattr(epg, "validate_pack", lambda *a, **k: _PackPassed())

    from factory.core import artifact_version_guard as guard
    monkeypatch.setattr(guard, "guard_report", lambda **k: {"findings": []})

    r = mqg_mod.requalification_preconditions()
    assert r.ready is True
    assert r.reasons == []


def test_q08_a_single_open_precondition_blocks_readiness(monkeypatch):
    """Las otras 4 en verde, solo G6 (golden dataset) abierto -- ready sigue
    False y el motivo senala exactamente esa precondicion."""
    import factory.regulatory.model_qualification_gate as mqg_mod
    from factory.core import decision_scope_resolver as resolver
    from factory.regulatory import applicability as applicability_mod
    from factory.regulatory import source_lifecycle
    from factory.regulatory import evidence_pack_governance as epg

    class _AllVerified:
        lifecycle_state = source_lifecycle.LOCAL_CANONICAL_COPY_VERIFIED
        source_id = "x"

    class _Authorized:
        authorized = True
        coverage_basis = "HUMAN_CONFIRMED_EXPLICIT"

    class _PackPassed:
        passed = True
        failures = ()
        def failure_codes(self): return ()

    monkeypatch.setattr(source_lifecycle, "evaluate_registry",
                        lambda: [_AllVerified(), _AllVerified(), _AllVerified(), _AllVerified()])
    monkeypatch.setattr(resolver, "resolve", lambda *a, **k: _Authorized())
    monkeypatch.setattr(applicability_mod, "load_matrix", lambda: {"matrix_version": "2.1"})
    monkeypatch.setattr(epg, "validate_pack", lambda *a, **k: _PackPassed())

    from factory.core import artifact_version_guard as guard
    monkeypatch.setattr(guard, "guard_report", lambda **k: {"findings": [
        {"artifact": "golden_dataset", "artifact_id": mqg_mod.__dict__.get("GOLDEN_DATASET_TARGET", "x"),
         "severity": "WARN", "code": "NO_APPROVING_DECISION", "detail": "sin decision"},
    ]})

    r = mqg_mod.requalification_preconditions()
    assert r.ready is False
    assert r.sources_verified is True
    assert r.pack_211_complete is True
    assert r.matrix_approved is True
    assert r.catalog_versioned is True
    assert r.golden_dataset_approved is False
    assert len(r.reasons) == 1
    assert "G6" in r.reasons[0]
