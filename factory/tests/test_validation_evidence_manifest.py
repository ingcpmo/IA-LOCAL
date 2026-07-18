"""W5.3 Fase 5.4.4 (gobernanza) -- manifiesto sanitizado versionable.

Diseño allowlist: se prueba que NINGÚN campo prohibido sobrevive incluso si
está anidado en lugares no obvios (dentro de execution_manifest, dentro de
llm_output, etc.), y que los campos legítimos (hashes/métricas/estados) sí
se conservan."""
from __future__ import annotations

import json
import stat

from factory.regulatory import validation_evidence_manifest as manifest_mod

_FORBIDDEN_SUBSTRINGS = ("raw_response", "source_text", "_by_req_candidates",
                          "DOCUMENTO SECRETO", "evidence_quote", "rationale")


def _record_with_sensitive_content():
    return {
        "record_id": "rec-1",
        "llm_output": {
            "requirement_id": "ALCOA_ACCURATE",
            "evidence_quote": "DOCUMENTO SECRETO cita literal del PDF",
            "rationale": "DOCUMENTO SECRETO razonamiento con texto del documento",
        },
        "execution_manifest": {
            "model": "m", "model_digest": "d", "prompt_sha256": "p",
            "schema_name": "finding_llm_v1", "schema_sha256": "ss",
            "chunk_sha256": "c", "options": {"temperature": 0.0},
            "timestamp_utc": "2026-07-18T00:00:00Z", "manifest_incomplete": False,
        },
        "status": "verified",
        "rejection_reason": None,
        "review_flags": [],
        "raw_response": '{"evidence_quote": "DOCUMENTO SECRETO raw completo"}',
        "errors": [],
        "source_text": "DOCUMENTO SECRETO texto de chunk antes de inferencia",
        "_by_req_candidates": ["DOCUMENTO SECRETO candidato heredado"],
    }


def _raw_agg():
    return {
        "run_id": "w5v3-validation-abcdef012345",
        "run_context": "validation",
        "run_by": "test-suite",
        "timestamp_utc": "2026-07-18T00:00:00Z",
        "document_sha256": "sha-doc-test",
        "document_type": "FS",
        "document_type_source": "human_assigned",
        "total_chunks_real": 1,
        "chunks_used": 1,
        "coverage": "full",
        "model": "m",
        "model_digest": "d",
        "ollama_version": "v",
        "records_by_status": {"verified": 1},
        "validation_evidence_status": "VALIDATION_EVIDENCE_COMPLETE",
        "golden_dataset_eligible": True,
        "per_requirement_conclusions": {
            "ALCOA_ACCURATE": {
                "conclusion": "DOCUMENTED_AND_SUPPORTED",
                "chunks_evaluated": 1, "chunks_observed": 1, "review_flags": [],
            },
        },
    }


def test_sanitize_strips_all_forbidden_content():
    manifest = manifest_mod.sanitize_run_raw_for_manifest(
        _raw_agg(), all_records=[_record_with_sensitive_content()],
    )
    serialized = json.dumps(manifest, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized, f"'{forbidden}' filtro al manifiesto sanitizado"


def test_sanitize_keeps_hashes_metrics_states():
    manifest = manifest_mod.sanitize_run_raw_for_manifest(
        _raw_agg(), all_records=[_record_with_sensitive_content()],
    )
    assert manifest["run_id"] == "w5v3-validation-abcdef012345"
    assert manifest["document_sha256"] == "sha-doc-test"
    assert manifest["golden_dataset_eligible"] is True
    assert manifest["records_total"] == 1
    rec = manifest["records"][0]
    assert rec["status"] == "verified"
    assert rec["execution_manifest"]["chunk_sha256"] == "c"
    assert rec["execution_manifest"]["model_digest"] == "d"
    assert "manifest_sha256" in manifest and len(manifest["manifest_sha256"]) == 64


def test_sanitize_records_field_never_includes_llm_output_key():
    manifest = manifest_mod.sanitize_run_raw_for_manifest(
        _raw_agg(), all_records=[_record_with_sensitive_content()],
    )
    rec = manifest["records"][0]
    assert "llm_output" not in rec
    assert "raw_response" not in rec
    assert "source_text" not in rec
    assert "_by_req_candidates" not in rec


def test_sanitize_without_records_still_produces_top_level_manifest():
    manifest = manifest_mod.sanitize_run_raw_for_manifest(_raw_agg(), all_records=None)
    assert "records" not in manifest
    assert manifest["run_id"] == "w5v3-validation-abcdef012345"


def test_write_sanitized_manifest_permissions_and_location(tmp_path):
    path = manifest_mod.write_sanitized_manifest(
        "w5v3-validation-abcdef012345", _raw_agg(),
        all_records=[_record_with_sensitive_content()], evidence_base=tmp_path,
    )
    assert path.parent.name == "manifests"
    assert path.name == "w5v3-validation-abcdef012345.manifest.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o750
    content = path.read_text(encoding="utf-8")
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in content


def test_write_sanitized_manifest_no_partial_tmp_left_behind(tmp_path):
    manifest_mod.write_sanitized_manifest(
        "w5v3-validation-abcdef012345", _raw_agg(), evidence_base=tmp_path,
    )
    leftovers = list((tmp_path / "manifests").glob("*.tmp"))
    assert leftovers == []
