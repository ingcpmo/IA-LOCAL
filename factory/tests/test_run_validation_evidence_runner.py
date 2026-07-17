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
from factory.regulatory.tools.run_validation_evidence import (
    EvidenceRunConfig, run_validation_evidence,
)

FAKE_PAGES = ["El sistema no menciona autenticacion en esta pagina."] * 2


def _fake_extractor(path):
    return FAKE_PAGES


def _fake_manifest():
    return {
        "model": "m", "model_digest": "d", "prompt_sha256": "p",
        "schema_name": "finding_llm_v1", "schema_sha256": "s",
        "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
        "manifest_incomplete": False,
    }


def test_runner_only_ever_calls_generate_controlled_with_validation(monkeypatch):
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
        document_path="dummy.pdf", document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2,
        run_by="test-suite", extractor=_fake_extractor,
    )
    result = run_validation_evidence(config)

    assert calls, "generate_controlled no fue invocado"
    assert set(calls) == {"validation"}
    assert result.records_total == len(calls)


def test_runner_avoids_ollama_calls_for_out_of_document_scope(monkeypatch):
    def _fail_if_called(*a, **k):
        raise AssertionError("no debia llamarse a Ollama para un requisito out_of_document_scope")

    monkeypatch.setattr(ollama_client, "generate_controlled", _fail_if_called)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    config = EvidenceRunConfig(
        document_path="dummy.pdf", document_type="IQ",  # 21_CFR_11.10(d).IQ = out_of_document_scope
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=2,
        run_by="test-suite", extractor=_fake_extractor,
    )
    result = run_validation_evidence(config)

    assert result.ollama_calls_avoided >= 1
    assert result.records_total == 0


def test_runner_requires_extractor():
    config = EvidenceRunConfig(
        document_path="dummy.pdf", document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], extractor=None,
    )
    with pytest.raises(ValueError, match="extractor es obligatorio"):
        run_validation_evidence(config)


def test_runner_raw_output_is_json_serializable(monkeypatch):
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
        document_path="dummy.pdf", document_type="FS",
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
def test_runner_real_ollama_smoke():
    """Integracion real, NO forma parte de Gate 0 por defecto (requiere
    Ollama real). Prueba minima: 1 requisito, 1 chunk sintetico corto."""
    import os as _os
    _os.environ.setdefault("FACTORY_OLLAMA_BASE_URL", "http://host.docker.internal:11434")

    def _one_page_extractor(path):
        return ["Este documento no contiene informacion de control de acceso."]

    config = EvidenceRunConfig(
        document_path="synthetic.pdf", document_type="FS",
        document_type_source="human_assigned",
        requirement_ids=["21_CFR_11.10(d)"], max_chunks=1,
        run_by="integration-test", extractor=_one_page_extractor,
    )
    result = run_validation_evidence(config)
    assert result.records_total >= 1
