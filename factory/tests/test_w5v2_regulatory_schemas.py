"""W5 Ciclo 1 (v2), Fase 1 -- schemas en dos capas + ejecucion controlada.

Cubre: fail-closed de schema_loader, additionalProperties:false y enum
restringido de finding_llm_v1 (P2/P3), resolucion de $ref en
finding_record_v1, y el contrato de generate_controlled() (schema-gate,
un solo reintento, manifest_incomplete nunca oculto -- P1/P4)."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from factory.regulatory.schema_loader import load_schema, schema_sha256, validate_against
from factory.engines.gmpai_integrity import ollama_client

VALID_LLM_OUTPUT = {
    "requirement_id": "21_CFR_11.10(d)",
    "chunk_observation": "observed",
    "evidence_quote": "Autenticacion de dos factores requerida.",
    "evidence_page": 5,
    "confidence": 0.9,
    "rationale": "Cita explicita de autenticacion.",
    "flags": [],
}


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return {"response": json.dumps(self._body)}


def test_load_schema_finding_llm_v1():
    schema = load_schema("finding_llm_v1")
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["chunk_observation"]["enum"]) == {
        "observed", "partially_observed", "not_observed_in_chunk",
    }


def test_finding_llm_v1_rejects_compliance_conclusions():
    """P3: el modelo NUNCA puede emitir cumple/no_cumple/no_aplica -- esos
    valores pertenecen al catalogo de estado del consolidador
    (chunked_engine._VALID_ESTADOS), no al contrato del LLM."""
    for forbidden in ("cumple", "no_cumple", "cumple_parcialmente", "no_aplica"):
        payload = dict(VALID_LLM_OUTPUT, chunk_observation=forbidden)
        ok, errors = validate_against(payload, "finding_llm_v1")
        assert ok is False, f"{forbidden} no deberia ser un chunk_observation valido"


def test_finding_llm_v1_rejects_additional_properties():
    payload = dict(VALID_LLM_OUTPUT, estado="cumple")
    ok, errors = validate_against(payload, "finding_llm_v1")
    assert ok is False
    assert any("estado" in e for e in errors)


def test_finding_llm_v1_accepts_valid_observation():
    ok, errors = validate_against(VALID_LLM_OUTPUT, "finding_llm_v1")
    assert ok is True
    assert errors == []


def test_finding_record_v1_resolves_ref_to_finding_llm_v1():
    record = {
        "record_id": "r1",
        "llm_output": VALID_LLM_OUTPUT,
        "execution_manifest": {
            "model": "qwen2.5:7b-instruct-q4_K_M",
            "model_digest": "abc123",
            "prompt_sha256": "x" * 64,
            "schema_name": "finding_llm_v1",
            "schema_sha256": schema_sha256("finding_llm_v1"),
            "chunk_sha256": "y" * 64,
            "options": {"temperature": 0},
            "timestamp_utc": "2026-07-17T00:00:00Z",
        },
        "verification": {},
        "status": "verified",
    }
    ok, errors = validate_against(record, "finding_record_v1")
    assert ok is True, errors


def test_finding_record_v1_ref_catches_invalid_llm_output():
    record = {
        "record_id": "r1",
        "llm_output": dict(VALID_LLM_OUTPUT, chunk_observation="no_cumple"),
        "execution_manifest": {
            "model": "m", "model_digest": "d", "prompt_sha256": "p",
            "schema_name": "finding_llm_v1", "schema_sha256": "s",
            "chunk_sha256": "c", "options": {}, "timestamp_utc": "t",
        },
        "verification": {},
        "status": "verified",
    }
    ok, errors = validate_against(record, "finding_record_v1")
    assert ok is False


def test_generate_controlled_accepts_valid_first_try():
    with mock.patch("httpx.post", return_value=_FakeResp(VALID_LLM_OUTPUT)), \
         mock.patch.object(ollama_client, "_get_digest_cached", return_value="digest-1"):
        out = ollama_client.generate_controlled("prompt", {"text": "chunk"})
    assert out["ok"] is True
    assert out["status"] == "verified"
    assert out["execution_manifest"]["manifest_incomplete"] is False
    assert out["execution_manifest"]["schema_name"] == "finding_llm_v1"


def test_generate_controlled_rejects_after_single_retry():
    bad = {"requirement_id": "X", "estado": "cumple"}
    with mock.patch("httpx.post", return_value=_FakeResp(bad)), \
         mock.patch.object(ollama_client, "_get_digest_cached", return_value=None):
        out = ollama_client.generate_controlled("prompt", {"text": "chunk"})
    assert out["ok"] is False
    assert out["status"] == "rejected_by_verifier"
    assert out["rejection_reason"] == "schema_validation_failed"
    # P1: manifiesto incompleto NUNCA se oculta, aunque el hallazgo se rechace.
    assert out["execution_manifest"]["manifest_incomplete"] is True


def test_generate_controlled_recovers_on_retry():
    bad = {"requirement_id": "X", "estado": "cumple"}
    responses = [_FakeResp(bad), _FakeResp(VALID_LLM_OUTPUT)]
    with mock.patch("httpx.post", side_effect=responses), \
         mock.patch.object(ollama_client, "_get_digest_cached", return_value="digest-1"):
        out = ollama_client.generate_controlled("prompt", {"text": "chunk"})
    assert out["ok"] is True


def test_generate_controlled_does_not_loop_beyond_single_retry():
    bad = {"requirement_id": "X", "estado": "cumple"}
    with mock.patch("httpx.post", return_value=_FakeResp(bad)) as post, \
         mock.patch.object(ollama_client, "_get_digest_cached", return_value="digest-1"):
        ollama_client.generate_controlled("prompt", {"text": "chunk"})
    assert post.call_count == 2  # 1 intento + 1 reintento, nunca mas (P6)


def test_schema_loader_is_fail_closed_on_missing_schema():
    with pytest.raises(FileNotFoundError):
        load_schema("schema_que_no_existe_v99")
