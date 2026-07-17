"""W5 Ciclo 1 (v2) — cierre técnico: verificación explícita de los 5
controles de gobernanza exigidos antes del commit final (ver
factory/docs/W5v2_CICLO1_CIERRE.md, PRODUCTION_ENABLEMENT=BLOCKED):

1. run_context ausente nunca habilita production (default = production
   a nivel de auditoría de evaluate_chunked(), pero eso NO autoriza nada
   por sí solo -- ver 2 y 3).
2. La matriz sin regulatory_approval (approval.status != human_confirmed)
   bloquea run_context='production'.
3. generate_controlled() permanece habilitado SOLO para
   run_context='validation' -- 'production' (u otro valor cualquiera,
   incluida la ausencia del parámetro combinada con un intento de
   invocación en producción) se rechaza antes de llamar a Ollama.
4. Los eventos con data.run_context='validation' quedan excluidos de
   GET .../audit?context=production.
5. Los GET no escriben en la cadena de auditoría (ni el servicio ni la
   ruta HTTP)."""
from __future__ import annotations

import json

import pytest

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.engines.gmpai_integrity.ollama_client import ProductionNotEnabledError
from factory.regulatory.applicability import MatrixNotApprovedError, require_matrix_approved_for_production
from factory.services import mission_evidence_service as mes


# ── 1. run_context ausente nunca habilita production ───────────────────────

def test_run_context_absent_raises_type_error_never_assumes_production(monkeypatch, tmp_path):
    """Fase 5.0 (W5.3), corrección: run_context ya NO tiene default. Omitirlo
    debe fallar en la firma (TypeError), no asumir 'production' en
    silencio -- ni siquiera para etiquetar auditoría."""
    from factory.core import audit_writer
    audit_file = tmp_path / "factory_audit.jsonl"
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: {"response": json.dumps(
        {"checkpoints": [{"req_id": "21_CFR_11.10(a)", "estado": "evidencia_insuficiente",
                           "evidencia_exacta": "", "pagina": 1}]}
    )})
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    from pathlib import Path
    prompt_path = Path(ce.__file__).parent / "prompts" / "part11_prompts.yaml"
    with pytest.raises(TypeError):
        ce.evaluate_chunked(prompt_path, "fda_part11_agent", "1.0.0", ["texto " * 500],
                             "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-default-ctx")


# ── 2. Matriz sin regulatory_approval bloquea production ────────────────────

def test_matrix_without_regulatory_approval_blocks_production(monkeypatch):
    import factory.regulatory.applicability as mod

    def _pending():
        return {"requirements": {}, "approval": {"status": "pending_human_confirmation"}}

    monkeypatch.setattr(mod, "load_matrix", _pending)
    with pytest.raises(MatrixNotApprovedError):
        mod.require_matrix_approved_for_production(run_context="production")


def test_matrix_without_regulatory_approval_still_allows_validation(monkeypatch):
    import factory.regulatory.applicability as mod

    def _pending():
        return {"requirements": {}, "approval": {"status": "pending_human_confirmation"}}

    monkeypatch.setattr(mod, "load_matrix", _pending)
    mod.require_matrix_approved_for_production(run_context="validation")  # no debe lanzar


def test_real_matrix_is_currently_approved_but_that_is_matrix_governance_only():
    """La matriz REAL esta aprobada (Checkpoint B, MC-0001) -- pero esa
    aprobacion es de GOBERNANZA DE LA MATRIZ, no de habilitacion de
    produccion del pipeline completo (ver PRODUCTION_ENABLEMENT=BLOCKED:
    generate_controlled() sigue bloqueado para 'production'
    independientemente del estado de la matriz, ver bloque 3 mas abajo)."""
    require_matrix_approved_for_production(run_context="production")  # no debe lanzar (matriz SI aprobada)


# ── 3. generate_controlled() habilitado solo para validation ───────────────

def test_generate_controlled_run_context_has_no_default_at_all():
    """Fase 5.0 (W5.3), corrección: ya no basta con que el default sea
    seguro ('validation') -- run_context debe ser keyword-only SIN default,
    para forzar que cada caller lo piense explícitamente en cada llamada."""
    import inspect
    sig = inspect.signature(ollama_client.generate_controlled)
    param = sig.parameters["run_context"]
    assert param.default is inspect.Parameter.empty
    assert param.kind == inspect.Parameter.KEYWORD_ONLY


def test_generate_controlled_omitting_run_context_raises_type_error(monkeypatch):
    monkeypatch.setattr("httpx.post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debia llamarse")))
    with pytest.raises(TypeError):
        ollama_client.generate_controlled("prompt", {"text": "chunk"})


def test_generate_controlled_blocks_production_before_any_ollama_call(monkeypatch):
    import httpx

    def _fail_if_called(*a, **k):
        raise AssertionError("No debia llamarse a Ollama -- el bloqueo de produccion debe cortar ANTES")

    monkeypatch.setattr(httpx, "post", _fail_if_called)
    with pytest.raises(ProductionNotEnabledError):
        ollama_client.generate_controlled("prompt", {"text": "chunk"}, run_context="production")


def test_generate_controlled_blocks_any_context_other_than_validation(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debia llamarse")))
    for bad_context in ("production", "staging", "", "PRODUCTION", "prod"):
        with pytest.raises(ProductionNotEnabledError):
            ollama_client.generate_controlled("prompt", {"text": "chunk"}, run_context=bad_context)


def test_generate_controlled_allows_validation_explicitly(monkeypatch):
    valid_output = {
        "requirement_id": "21_CFR_11.10(d)", "chunk_observation": "not_observed_in_chunk",
        "evidence_quote": "", "evidence_page": None, "confidence": 0.5,
        "rationale": "n/a", "flags": [],
    }

    class _FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": json.dumps(valid_output)}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _FakeResp())
    monkeypatch.setattr(ollama_client, "_get_digest_cached", lambda: "digest-1")
    out = ollama_client.generate_controlled("prompt", {"text": "chunk"}, run_context="validation")
    assert out["ok"] is True


# ── 4. Eventos validation excluidos de reportes production ─────────────────

def test_validation_events_never_appear_in_production_context_report(monkeypatch, tmp_path):
    from factory.services import paths
    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "w5v2_validation_evidence_run",
                     "timestamp": "t1", "entry_hash": "h1",
                     "data": {"run_id": "v1", "run_context": "validation"}}) + "\n" +
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "gmpai_chunked_analysis_run",
                     "timestamp": "t2", "entry_hash": "h2",
                     "data": {"run_id": "p1", "run_context": "production"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)

    production_report = mes.read_audit("gmpai_document_validation", context="production")
    run_ids_in_production_report = {e["data"]["run_id"] for e in production_report["events"]}
    assert "v1" not in run_ids_in_production_report
    assert "p1" in run_ids_in_production_report


# ── 5. Los GET no escriben auditoría ────────────────────────────────────────

def test_read_audit_service_never_writes(monkeypatch, tmp_path):
    from factory.services import paths
    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "p", "event_type": "e", "timestamp": "t",
                     "entry_hash": "h", "data": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)
    before = audit_file.read_bytes()

    mes.read_audit("p", context="production")
    mes.read_audit("p", context="validation")
    mes.read_audit("p")

    assert audit_file.read_bytes() == before


def test_get_mission_audit_route_is_read_only(monkeypatch, tmp_path):
    """Extremo a extremo por la ruta HTTP (no solo el servicio): GET
    /missions/{project_id}/audit no debe escribir en la cadena real."""
    from factory.core import audit_writer as real_audit_writer
    from factory.services import paths

    audit_file = tmp_path / "factory_audit.jsonl"
    audit_file.write_text(
        json.dumps({"project_id": "gmpai_document_validation", "event_type": "gmpai_chunked_analysis_run",
                     "timestamp": "t1", "entry_hash": "h1", "data": {"run_context": "production"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(real_audit_writer, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(real_audit_writer, "_last_entry_hash", None)
    before = audit_file.read_bytes()

    from factory.api.routes.layer9 import get_mission_audit
    result = get_mission_audit("gmpai_document_validation", limit=50, context="production")

    assert result["count"] == 1
    assert audit_file.read_bytes() == before
