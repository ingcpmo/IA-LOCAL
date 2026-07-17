"""W5.3 Fase 5.3 -- cableado de persistencia de _by_req_candidates dentro
de evaluate_chunked(), SOLO para run_context='validation'. production
queda byte-a-byte identico al comportamiento previo a esta fase."""
from __future__ import annotations

import json

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.regulatory import validation_evidence_writer as writer

from pathlib import Path

PROMPT_PATH = Path(ce.__file__).parent / "prompts" / "part11_prompts.yaml"


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload)}


def _one_real_finding():
    return {"checkpoints": [
        {"req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente",
         "evidencia_exacta": "El acceso al sistema requiere usuario y contrasena.",
         "pagina": 1},
    ]}


def _setup(monkeypatch, tmp_path):
    from factory.core import audit_writer
    audit_file = tmp_path / "factory_audit.jsonl"
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_one_real_finding()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "digest-1")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    return audit_file


def _run(monkeypatch, tmp_path, run_context, evidence_base=None):
    audit_file = _setup(monkeypatch, tmp_path)
    if evidence_base is not None:
        monkeypatch.setattr(writer, "VALIDATION_EVIDENCE_BASE", evidence_base)
    pages = ["El acceso al sistema requiere usuario y contrasena. " * 20]
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf",
                                  "sha-5-3-test", run_context=run_context)
    return result, audit_file


def test_validation_context_persists_evidence_with_complete_status(monkeypatch, tmp_path):
    evidence_dir = tmp_path / "evidence"
    result, audit_file = _run(monkeypatch, tmp_path, "validation", evidence_base=evidence_dir)

    assert result["analysis_status"] == "ANALYSIS_COMPLETE"
    assert result["validation_evidence_status"] == "VALIDATION_EVIDENCE_COMPLETE"
    assert result["golden_dataset_eligible"] is True

    written_files = list(evidence_dir.glob("*.json"))
    assert len(written_files) == 1
    data = json.loads(written_files[0].read_text(encoding="utf-8"))
    assert data["run_id"] == result["run_id"]
    assert data["document_sha256"] == "sha-5-3-test"
    # _by_req_candidates SI esta presente aqui (a diferencia de
    # result["chunk_executions"], que sigue sin el -- ver test siguiente).
    candidates = data["content"]["chunk_executions_with_candidates"]
    assert any(ce_["_by_req_candidates"] for ce_ in candidates)


def test_production_context_writes_nothing_identical_to_before_fase_5_3(monkeypatch, tmp_path):
    evidence_dir = tmp_path / "evidence"
    result, audit_file = _run(monkeypatch, tmp_path, "production", evidence_base=evidence_dir)

    assert result["analysis_status"] == "ANALYSIS_COMPLETE"
    assert result["validation_evidence_status"] == "NOT_APPLICABLE_PRODUCTION_CONTEXT"
    assert result["golden_dataset_eligible"] is False
    assert not evidence_dir.exists() or list(evidence_dir.glob("*.json")) == []


def test_result_chunk_executions_never_leaks_by_req_candidates_in_either_context(monkeypatch, tmp_path):
    """El contrato de result['chunk_executions'] NO cambia en Fase 5.3 --
    _by_req_candidates solo vive en el archivo de evidencia separado."""
    for run_context in ("validation", "production"):
        result, _ = _run(monkeypatch, tmp_path, run_context, evidence_base=tmp_path / f"ev-{run_context}")
        for ce_ in result["chunk_executions"]:
            assert "_by_req_candidates" not in ce_


def test_audit_event_carries_validation_evidence_status(monkeypatch, tmp_path):
    result, audit_file = _run(monkeypatch, tmp_path, "validation", evidence_base=tmp_path / "ev")
    entry = json.loads(audit_file.read_text(encoding="utf-8").strip())
    assert entry["data"]["analysis_status"] == "ANALYSIS_COMPLETE"
    assert entry["data"]["validation_evidence_status"] == "VALIDATION_EVIDENCE_COMPLETE"
    assert entry["data"]["golden_dataset_eligible"] is True


def test_write_failure_never_hidden_and_never_crashes_analysis(monkeypatch, tmp_path):
    """Fuerza un fallo de escritura (EvidenceTooLargeError) -- el analisis
    debe completarse igual, y el fallo debe quedar declarado, no oculto."""
    def _boom(*a, **k):
        raise writer.EvidenceTooLargeError("simulado para el test")

    monkeypatch.setattr(
        "factory.regulatory.validation_evidence_writer.write_validation_evidence", _boom,
    )
    result, audit_file = _run(monkeypatch, tmp_path, "validation", evidence_base=tmp_path / "ev")

    assert result["analysis_status"] == "ANALYSIS_COMPLETE"  # el analisis NO se tumba
    assert result["validation_evidence_status"] == "VALIDATION_EVIDENCE_INCOMPLETE"
    assert result["golden_dataset_eligible"] is False
    assert "EvidenceTooLargeError" in result["validation_evidence_error"]
    # Tambien visible en auditoria, no solo en el resultado en memoria.
    entry = json.loads(audit_file.read_text(encoding="utf-8").strip())
    assert entry["data"]["validation_evidence_status"] == "VALIDATION_EVIDENCE_INCOMPLETE"
    assert entry["data"]["golden_dataset_eligible"] is False
    # Los findings si se calcularon (el analisis se completo de verdad).
    assert len(result["findings"]) >= 1


def test_real_engine_run_id_format_is_accepted_by_path_policy():
    """Confirma la opcion (a): el run_id real del motor (chunked-<hex>)
    ahora es aceptado por resolve_validation_evidence, sin necesidad de un
    segundo identificador inventado."""
    from factory.core.path_policy import resolve_validation_evidence
    target = resolve_validation_evidence("chunked-abcdef012345", Path("/tmp"))
    assert target.name == "chunked-abcdef012345.json"
