"""W5 Ciclo 1 (v2), Fase 5.0 (W5.3), control #6 -- pruebas del runner
versionado (factory/regulatory/tools/run_validation_evidence.py).

Dos niveles:
  - Wiring (siempre corre en Gate 0): generate_fn/extractor inyectados via
    monkeypatch, sin Ollama real, confirma que el runner tracked ejercita
    correctamente pre_inference_filter -> generate_controlled ->
    verify_llm_output -> consolidate con run_context='validation' fijo.
  - Integración real (opt-in, NO corre en Gate 0 por defecto): requiere
    W5V3_REAL_OLLAMA=1 en el entorno Y conectividad real a Ollama. Mismo
    patrón usado para runs de evidencia reales de Fase 4 (host.docker.internal
    como override de proceso, nunca persistente)."""
from __future__ import annotations

import json
import os

import pytest

from factory.engines.gmpai_integrity import ollama_client
from factory.regulatory import validation_evidence_manifest as manifest_mod
from factory.regulatory import validation_evidence_writer as writer
from factory.regulatory.tools.run_validation_evidence import (
    EvidenceRunConfig, run_validation_evidence,
)

FAKE_PAGES = ["El sistema no menciona autenticacion en esta pagina."] * 2


def _fake_extractor(path):
    return FAKE_PAGES


@pytest.fixture
def dummy_document(tmp_path):
    """Fase 5.4: document_sha256 se calcula del archivo real -- los tests
    ya no pueden usar una ruta inexistente ('dummy.pdf')."""
    p = tmp_path / "dummy.pdf"
    p.write_bytes(b"%PDF-1.4 contenido sintetico para hash de prueba")
    return p


@pytest.fixture(autouse=True)
def _isolate_validation_evidence_base(monkeypatch, tmp_path):
    """Fase 5.4: run_validation_evidence() SIEMPRE persiste de verdad (no
    hay modo 'no persistir') -- autouse para que NINGUN test de este
    archivo pueda escribir por accidente en el directorio real
    (factory/regulatory/validation_evidence/), sin importar si le importa
    o no la persistencia. Los tests que SI quieren inspeccionar el archivo
    escrito pueden seguir usando su propio tmp_path/'evidence' explicito
    (sobrescribe este default igualmente vía monkeypatch).

    Fase 5.4.4: run_validation_evidence() TAMBIEN escribe un manifiesto
    sanitizado (validation_evidence_manifest.write_sanitized_manifest())
    con su PROPIO VALIDATION_EVIDENCE_BASE, independiente del de
    validation_evidence_writer -- aislar solo uno de los dos modulos dejaba
    el otro escribiendo manifiestos sinteticos en el directorio real
    (incidente detectado en esta misma fase, revisando el diff antes del
    commit: 6 manifiestos con document_sha256 de dummy.pdf aparecieron
    tracked en factory/regulatory/validation_evidence/manifests/)."""
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "validation_evidence_autouse")
    monkeypatch.setattr(manifest_mod, "VALIDATION_EVIDENCE_BASE", tmp_path / "validation_evidence_autouse")


def _fake_manifest():
    return {
        "model": "m", "model_digest": "d", "prompt_sha256": "p",
        "schema_name": "finding_llm_v1", "schema_sha256": "s",
        "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
        "manifest_incomplete": False,
    }


def test_runner_only_ever_calls_generate_controlled_with_validation(monkeypatch, dummy_document, tmp_path):
    """Confirma el contrato central del control #6: el runner tracked NUNCA
    pasa run_context distinto de 'validation' a generate_controlled(),
    incluso si alguien intentara manipular EvidenceRunConfig -- el runner
    no expone run_context como parametro configurable en absoluto."""
    calls = []

    def _fake_generate_controlled(prompt, chunk, *, run_context, **kwargs):
        calls.append(run_context)
        return {
            "llm_output": {
                "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
                "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
                "rationale": "n/a", "flags": [],
            },
            "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
            "status": "verified", "rejection_reason": None,
        }

    monkeypatch.setattr(ollama_client, "generate_controlled", _fake_generate_controlled)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2,
        run_by="test-suite", extractor=_fake_extractor,
    )
    result = run_validation_evidence(config)

    assert calls, "generate_controlled no fue invocado"
    assert set(calls) == {"validation"}
    assert result.records_total == len(calls)


def test_runner_avoids_ollama_calls_for_out_of_document_scope(monkeypatch, dummy_document, tmp_path):
    def _fail_if_called(*a, **k):
        raise AssertionError("no debia llamarse a Ollama para un requisito out_of_document_scope")

    monkeypatch.setattr(ollama_client, "generate_controlled", _fail_if_called)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="IQ",  # 21_CFR_11.10(d).IQ = out_of_document_scope
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2,
        run_by="test-suite", extractor=_fake_extractor,
    )
    result = run_validation_evidence(config)

    assert result.ollama_calls_avoided >= 1
    assert result.records_total == 0


def test_runner_requires_extractor(dummy_document):
    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], extractor=None,
    )
    with pytest.raises(ValueError, match="extractor es obligatorio"):
        run_validation_evidence(config)


def test_runner_raw_output_is_json_serializable(monkeypatch, dummy_document, tmp_path):
    monkeypatch.setattr(ollama_client, "generate_controlled", lambda *a, **k: {
        "llm_output": {
            "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
            "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
            "rationale": "n/a", "flags": [],
        },
        "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
        "status": "verified", "rejection_reason": None,
    })
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1,
        run_by="test-suite", extractor=_fake_extractor,
    )
    result = run_validation_evidence(config)
    json.dumps(result.raw)  # no debe lanzar


@pytest.mark.skipif(
    os.environ.get("W5V3_REAL_OLLAMA") != "1",
    reason="Integracion real opt-in -- exportar W5V3_REAL_OLLAMA=1 y tener "
           "Ollama real alcanzable (ver factory/docs/W5v2_FASE0_INVENTARIO.md "
           "sobre conectividad host.docker.internal) para correr esta prueba.",
)
def test_runner_real_ollama_smoke(tmp_path):
    """Integracion real, NO forma parte de Gate 0 por defecto (requiere
    Ollama real). Prueba minima: 1 requisito, 1 chunk sintetico corto."""
    import os as _os
    _os.environ.setdefault("FACTORY_OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    def _one_page_extractor(path):
        return ["Este documento no contiene informacion de control de acceso."]

    synthetic_doc = tmp_path / "synthetic.pdf"
    synthetic_doc.write_bytes(b"%PDF-1.4 sintetico")

    config = EvidenceRunConfig(
        document_path=synthetic_doc, document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1,
        run_by="integration-test", extractor=_one_page_extractor,
    )
    result = run_validation_evidence(config)
    assert result.records_total >= 1


def test_requirement_ids_from_catalog_returns_all_19():
    """Fase 5.3, Bloque 5.3.3: el runner puede derivar requirement_ids
    directamente del catalogo real de Fase 5.2, sin listarlos a mano."""
    from factory.regulatory.tools.run_validation_evidence import requirement_ids_from_catalog
    ids = requirement_ids_from_catalog()
    assert len(ids) == 19
    assert "21_CFR_11.10(d)" in ids
    assert "ALCOA_AVAILABLE" in ids


# ── Fase 5.4, Bloque 5.4.1/5.4.2 -- persistencia de all_records completos ──

def _basic_config(dummy_document, extractor=None):
    return EvidenceRunConfig(
        document_path=dummy_document, document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1,
        run_by="test-suite", extractor=extractor or _fake_extractor,
    )


def test_runner_persists_all_records_with_complete_status(monkeypatch, dummy_document, tmp_path):
    monkeypatch.setattr(ollama_client, "generate_controlled", lambda *a, **k: {
        "llm_output": {
            "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "observed",
            "evidence_quote": "El sistema no menciona autenticacion en esta pagina.",
            "evidence_page": 1, "confidence": 0.9, "rationale": "n/a", "flags": [],
        },
        "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
        "status": "verified", "rejection_reason": None,
    })
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "evidence")

    result = run_validation_evidence(_basic_config(dummy_document))

    assert result.validation_evidence_status == "VALIDATION_EVIDENCE_COMPLETE"
    assert result.golden_dataset_eligible is True
    assert result.raw["document_sha256"]  # real, no vacio

    written = list((tmp_path / "evidence").glob("*.json"))
    assert len(written) == 1
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["document_sha256"] == result.raw["document_sha256"]
    # all_records completos (con llm_output real), no solo el agregado.
    records = data["content"]["all_records"]
    assert len(records) == 1
    assert records[0]["llm_output"]["chunk_observation"] == "observed"


def test_runner_write_failure_never_hidden_analysis_still_completes(monkeypatch, dummy_document, tmp_path):
    monkeypatch.setattr(ollama_client, "generate_controlled", lambda *a, **k: {
        "llm_output": {
            "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
            "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
            "rationale": "n/a", "flags": [],
        },
        "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
        "status": "verified", "rejection_reason": None,
    })
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    def _boom(*a, **k):
        raise writer.EvidenceTooLargeError("simulado para el test")

    monkeypatch.setattr(
        "factory.regulatory.validation_evidence_writer.write_validation_evidence", _boom,
    )

    result = run_validation_evidence(_basic_config(dummy_document))

    # El analisis SI se completo (records calculados) aunque la
    # persistencia haya fallado.
    assert result.records_total == 1
    assert result.validation_evidence_status == "VALIDATION_EVIDENCE_INCOMPLETE"
    assert result.golden_dataset_eligible is False
    assert "EvidenceTooLargeError" in result.validation_evidence_error
    assert result.raw["validation_evidence_status"] == "VALIDATION_EVIDENCE_INCOMPLETE"
    assert result.raw["golden_dataset_eligible"] is False


# ── Fase 3 (gate 551-llamadas) -- checkpoint/resume + corrida por lotes ──

# Cada "pagina" supera CHUNK_MAX_CHARS (6000) por si sola, para forzar que
# build_page_chunks() nunca las fusione -- 1 chunk real por pagina, igual
# que el gate real necesita para ejercitar --max-calls/checkpoint.
FAKE_PAGES_MULTI = [f"Pagina {i}: sin mencion de autenticacion. " + ("x" * 6500) for i in range(4)]


def _fake_extractor_multi(path):
    return FAKE_PAGES_MULTI


def _counting_generate_controlled(calls_log):
    def _gen(prompt, chunk, *, run_context, **kwargs):
        calls_log.append((chunk["chunk_index"],))
        return {
            "llm_output": {
                "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
                "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
                "rationale": "n/a", "flags": [],
            },
            "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
            "status": "verified", "rejection_reason": None,
        }
    return _gen


def test_max_calls_stops_early_and_marks_batch_incomplete(monkeypatch, dummy_document, tmp_path):
    calls_log = []
    monkeypatch.setattr(ollama_client, "generate_controlled", _counting_generate_controlled(calls_log))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=4, run_by="test-suite",
        extractor=_fake_extractor_multi,
        checkpoint_path=tmp_path / "checkpoint.jsonl", max_calls=2,
    )
    result = run_validation_evidence(config)

    assert len(calls_log) == 2  # nunca excede max_calls
    assert result.calls_made_this_invocation == 2
    assert result.batch_complete is False
    assert result.pending_requirement_ids == ["21_CFR_11.10(d)"]
    assert result.validation_evidence_status == "BATCH_INCOMPLETE_NOT_PERSISTED"
    assert result.golden_dataset_eligible is False
    # Un universo incompleto NUNCA se persiste como si fuera evidencia real.
    assert not (tmp_path / "evidence").exists()


def test_second_invocation_resumes_from_checkpoint_without_repeating_calls(monkeypatch, dummy_document, tmp_path):
    calls_log = []
    monkeypatch.setattr(ollama_client, "generate_controlled", _counting_generate_controlled(calls_log))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "evidence")

    checkpoint_path = tmp_path / "checkpoint.jsonl"
    base_config = dict(
        document_path=dummy_document, document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=4, run_by="test-suite",
        extractor=_fake_extractor_multi, checkpoint_path=checkpoint_path,
    )

    # Lote 1: agota el presupuesto a las 2 de 4 llamadas posibles.
    result1 = run_validation_evidence(EvidenceRunConfig(**base_config, max_calls=2))
    assert len(calls_log) == 2
    assert result1.batch_complete is False

    # Lote 2: mismo checkpoint_path, sin limite -- NUNCA repite las 2 ya
    # hechas, solo hace las 2 restantes, y esta vez SI completa/persiste.
    result2 = run_validation_evidence(EvidenceRunConfig(**base_config, max_calls=None))
    assert len(calls_log) == 4  # 2 del lote 1 + 2 nuevas del lote 2, nunca 6
    assert result2.calls_made_this_invocation == 2
    assert result2.batch_complete is True
    assert result2.pending_requirement_ids == []
    assert result2.validation_evidence_status == "VALIDATION_EVIDENCE_COMPLETE"
    assert result2.records_total == 4  # las 4 quedan consolidadas, reusadas + nuevas

    written = list((tmp_path / "evidence").glob("*.json"))
    assert len(written) == 1


def test_checkpoint_entries_scoped_to_document_sha256(monkeypatch, tmp_path):
    """Un checkpoint de OTRO documento (distinto sha256) nunca se reusa --
    evita mezclar evidencia de documentos distintos por compartir ruta de
    checkpoint."""
    calls_log = []
    monkeypatch.setattr(ollama_client, "generate_controlled", _counting_generate_controlled(calls_log))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "evidence")

    checkpoint_path = tmp_path / "checkpoint.jsonl"
    doc_a = tmp_path / "a.pdf"
    doc_a.write_bytes(b"%PDF-1.4 documento A")
    doc_b = tmp_path / "b.pdf"
    doc_b.write_bytes(b"%PDF-1.4 documento B, contenido distinto")

    run_validation_evidence(EvidenceRunConfig(
        document_path=doc_a, document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1, run_by="test-suite",
        extractor=_fake_extractor_multi, checkpoint_path=checkpoint_path,
    ))
    assert len(calls_log) == 1

    run_validation_evidence(EvidenceRunConfig(
        document_path=doc_b, document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1, run_by="test-suite",
        extractor=_fake_extractor_multi, checkpoint_path=checkpoint_path,
    ))
    assert len(calls_log) == 2  # documento B SI llamo, no reuso el checkpoint de A


def test_cached_rejected_record_is_reused_not_retried_and_still_blocks_gap(monkeypatch, tmp_path):
    """Un chunk que quedo rejected_by_verifier en el lote 1 NUNCA se
    reintenta en el lote 2 (el checkpoint lo devuelve tal cual) -- y sigue
    contando como 'rechazado' para el consolidador (ABSENCE_BLOCKED_BY_
    REJECTED_CHUNKS), nunca como si nunca hubiera existido."""
    # Solo 2 paginas/chunks reales -- con max_chunks=2 la cobertura queda
    # completa (2>=2), asi que la unica razon de EVALUATION_INCOMPLETE es
    # el chunk rechazado, no cobertura parcial (evita confundir las 2
    # causas distintas que absence_consolidator.py distingue).
    fake_pages_two = [f"Pagina {i}: sin mencion de autenticacion. " + ("x" * 6500) for i in range(2)]

    def _fake_extractor_two(path):
        return fake_pages_two

    calls_log = []

    def _gen_first_rejected(prompt, chunk, *, run_context, **kwargs):
        calls_log.append(chunk["chunk_index"])
        if chunk["chunk_index"] == 0:
            return {
                "llm_output": None, "execution_manifest": _fake_manifest(),
                "ok": False, "errors": ["bad json"],
                "rejection_reason": "json_parse_failed", "raw_response": "not json",
            }
        return {
            "llm_output": {
                "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
                "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
                "rationale": "n/a", "flags": [],
            },
            "execution_manifest": _fake_manifest(), "ok": True, "errors": [],
            "status": "verified", "rejection_reason": None,
        }

    monkeypatch.setattr(ollama_client, "generate_controlled", _gen_first_rejected)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "evidence")

    checkpoint_path = tmp_path / "checkpoint.jsonl"
    base_config = dict(
        document_path=tmp_path / "doc.pdf", document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2, run_by="test-suite",
        extractor=_fake_extractor_two, checkpoint_path=checkpoint_path,
    )
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 doc")

    # Lote 1: agota el presupuesto a 1 llamada -- chunk 0 queda rejected.
    result1 = run_validation_evidence(EvidenceRunConfig(**base_config, max_calls=1))
    assert len(calls_log) == 1
    assert result1.batch_complete is False

    # Lote 2: mismo checkpoint -- el chunk 0 rechazado se REUSA (no se
    # reintenta), solo se hace 1 llamada nueva para el chunk 1.
    result2 = run_validation_evidence(EvidenceRunConfig(**base_config, max_calls=None))
    assert calls_log == [0, 1]  # nunca [0, 0, 1] -- el chunk 0 no se repite
    assert result2.calls_made_this_invocation == 1
    assert result2.batch_complete is True

    conclusion = result2.per_requirement_conclusions["21_CFR_11.10(d)"]
    # applicability("21_CFR_11.10(d)", "FS") == "expected" -- con un chunk
    # rechazado, la ausencia NUNCA se confirma (P3 reforzado, W5.5).
    assert conclusion["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_REJECTED_CHUNKS" in conclusion["review_flags"]


def test_progress_callback_invoked_per_real_call_only(monkeypatch, dummy_document, tmp_path):
    monkeypatch.setattr(ollama_client, "generate_controlled", _counting_generate_controlled([]))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    events = []
    config = EvidenceRunConfig(
        document_path=dummy_document, document_type="FS", document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2, run_by="test-suite",
        extractor=_fake_extractor_multi, checkpoint_path=tmp_path / "checkpoint.jsonl",
        progress_callback=events.append,
    )
    result = run_validation_evidence(config)

    assert len(events) == 2 == result.calls_made_this_invocation
    assert events[0]["calls_made_this_invocation"] == 1
    assert events[1]["calls_made_this_invocation"] == 2


def test_runner_persists_raw_response_and_errors_for_rejected_records(monkeypatch, dummy_document, tmp_path):
    """Fase 5.4 (fix ETAPA 1): antes de este fix, un registro
    rejected_by_verifier solo guardaba 'rejection_reason' (una constante
    generica) -- el texto crudo del modelo y los errores especificos de
    jsonschema se calculaban en generate_controlled() pero se descartaban
    aqui, dejando cualquier rechazo real irreproducible despues (bug
    detectado al intentar analizar los 21 rechazos reales de Fase 5.4)."""
    monkeypatch.setattr(ollama_client, "generate_controlled", lambda *a, **k: {
        "llm_output": None, "execution_manifest": _fake_manifest(), "ok": False,
        "errors": ["evidence_page: 'cinco' is not of type 'integer', 'null'"],
        "status": "rejected_by_verifier", "rejection_reason": "schema_validation_failed",
        "raw_response": '{"requirement_id": "21_CFR_11.10(d)", "evidence_page": "cinco"}',
    })
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", tmp_path / "evidence")

    result = run_validation_evidence(_basic_config(dummy_document))

    written = list((tmp_path / "evidence").glob("*.json"))
    data = json.loads(written[0].read_text(encoding="utf-8"))
    record = data["content"]["all_records"][0]

    assert record["status"] == "rejected_by_verifier"
    assert record["raw_response"] == '{"requirement_id": "21_CFR_11.10(d)", "evidence_page": "cinco"}'
    assert record["errors"] == ["evidence_page: 'cinco' is not of type 'integer', 'null'"]
