"""W5 Ciclo 1 (v2), Fase 4, Bloque 4.1 — run_context en el evento auditado
+ filtro de lectura ?context= (sin fragmentar la cadena Part 11, sin
escrituras en GET)."""
from __future__ import annotations

import json

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.services import mission_evidence_service as mes


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload)}


def _all_insufficient():
    return {"checkpoints": [
        {"req_id": r, "estado": "evidencia_insuficiente", "evidencia_exacta": "", "pagina": 1}
        for r in ("21_CFR_11.10(a)",)
    ]}


def _run(monkeypatch, tmp_path, run_context=None):
    from factory.core import audit_writer
    audit_file = tmp_path / "factory_audit.jsonl"
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    import factory.engines.gmpai_integrity.chunked_engine as ce_mod
    prompt_path = list((ce_mod.__file__.rsplit("/", 1)[0] + "/prompts",))[0]
    from pathlib import Path
    prompt_path = Path(prompt_path) / "part11_prompts.yaml"

    kwargs = {}
    if run_context is not None:
        kwargs["run_context"] = run_context
    pages = ["texto " * 500]
    result = ce.evaluate_chunked(prompt_path, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf",
                                  "sha-run-context", **kwargs)
    return result, audit_file


def test_omitting_run_context_raises_type_error(monkeypatch, tmp_path):
    """Fase 5.0 (W5.3): run_context ya NO tiene default -- omitirlo es un
    TypeError de Python (parametro keyword-only sin valor), no un
    ValueError en runtime. Nunca se asume 'production' silenciosamente."""
    with pytest.raises(TypeError):
        _run(monkeypatch, tmp_path)  # run_context=None -> kwargs vacio -> falta el requerido


def test_explicit_production_run_context_is_recorded(monkeypatch, tmp_path):
    result, audit_file = _run(monkeypatch, tmp_path, run_context="production")
    assert result["run_context"] == "production"
    entry = json.loads(audit_file.read_text(encoding="utf-8").strip())
    assert entry["data"]["run_context"] == "production"


def test_validation_run_context_is_recorded_in_the_same_audit_chain(monkeypatch, tmp_path):
    """Bloque 4.1: una sola cadena de auditoria (Part 11), nunca
    fragmentada -- el run de validacion escribe al MISMO archivo, solo con
    run_context distinto."""
    result, audit_file = _run(monkeypatch, tmp_path, run_context="validation")
    assert result["run_context"] == "validation"
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # exactamente 1 evento nuevo, mismo archivo
    entry = json.loads(lines[0])
    assert entry["data"]["run_context"] == "validation"


def test_invalid_run_context_is_rejected_fail_closed(monkeypatch, tmp_path):
    from factory.core import audit_writer
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", tmp_path / "factory_audit.jsonl")
    with pytest.raises(ValueError, match="run_context invalido"):
        _run(monkeypatch, tmp_path, run_context="staging")


def test_read_audit_context_filter_excludes_other_context(monkeypatch, tmp_path):
    from factory.services import paths
    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "gmpai_chunked_analysis_run",
                     "timestamp": "t1", "entry_hash": "h1",
                     "data": {"run_id": "r1", "run_context": "production"}}) + "\n" +
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "gmpai_chunked_analysis_run",
                     "timestamp": "t2", "entry_hash": "h2",
                     "data": {"run_id": "r2", "run_context": "validation"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)

    prod_only = mes.read_audit("gmpai_document_validation", context="production")
    assert prod_only["count"] == 1
    assert prod_only["events"][0]["data"]["run_id"] == "r1"

    validation_only = mes.read_audit("gmpai_document_validation", context="validation")
    assert validation_only["count"] == 1
    assert validation_only["events"][0]["data"]["run_id"] == "r2"

    unfiltered = mes.read_audit("gmpai_document_validation")
    assert unfiltered["count"] == 2


def test_read_audit_context_filter_treats_missing_run_context_as_production(monkeypatch, tmp_path):
    """Eventos escritos ANTES de Fase 4 (sin campo run_context) no deben
    desaparecer de un filtro context='production' -- serian, de hecho,
    ejecuciones productivas historicas."""
    from factory.services import paths
    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "gmp_report_generated",
                     "timestamp": "t0", "entry_hash": "h0", "data": {"run_id": "legacy"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)

    prod = mes.read_audit("gmpai_document_validation", context="production")
    assert prod["count"] == 1

    validation = mes.read_audit("gmpai_document_validation", context="validation")
    assert validation["count"] == 0


def test_read_audit_is_read_only_no_file_writes(monkeypatch, tmp_path):
    """GET no debe escribir nada -- confirma que read_audit no toca
    AUDIT_FILE (solo lo lee)."""
    from factory.services import paths
    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "p", "event_type": "e", "timestamp": "t",
                     "entry_hash": "h", "data": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)
    before_mtime = audit_file.stat().st_mtime_ns
    before_content = audit_file.read_bytes()

    mes.read_audit("p", context="production")

    assert audit_file.stat().st_mtime_ns == before_mtime
    assert audit_file.read_bytes() == before_content
