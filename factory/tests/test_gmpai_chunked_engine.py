"""
Tests de factory.engines.gmpai_integrity.chunked_engine — Ollama SIEMPRE
mockeado (nunca un modelo real en la suite pytest). Migrado desde
factory/workspaces/gmpai_document_validation/tests/test_chunked_llm_integrity_engine.py
(que sigue existiendo, sin tocar, para no romper el workspace en uso) al
motor ahora git-trackeado en factory/engines/gmpai_integrity/.

Valida: chunking real por paginas con solapamiento, cobertura completa (no
solo el primer chunk), consolidacion por checkpoint, deteccion de
contradicciones, anclaje exigido solo para cumple/cumple_parcialmente, y
checkpoint/reanudacion (capacidad nueva, no presente en la copia original del
workspace).
"""

import json
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import models
from factory.engines.gmpai_integrity import ollama_client

PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload)}


def _all_insufficient(overrides=None):
    overrides = overrides or {}
    reqs = ("21_CFR_11.10(a)", "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)", "21_CFR_11.50_11.70")
    return {"checkpoints": [
        overrides.get(r, {"req_id": r, "estado": "evidencia_insuficiente",
                           "evidencia_exacta": "", "brecha": "n/a", "recomendacion": "n/a"})
        for r in reqs
    ]}


def test_build_page_chunks_covers_all_pages_with_overlap():
    pages = ["a" * 3000, "b" * 3000, "c" * 3000, "d" * 3000, "e" * 3000]
    chunks = ce.build_page_chunks(pages, max_chars=6000, overlap_chars=500)
    assert chunks[0]["page_start"] == 1
    assert chunks[-1]["page_end"] == 5
    covered = set()
    for c in chunks:
        covered.update(range(c["page_start"], c["page_end"] + 1))
    assert covered == set(range(1, 6))
    assert any(c["has_overlap_prefix"] for c in chunks[1:])


def test_evaluate_chunked_covers_start_middle_end(monkeypatch):
    pages = ["Pagina inicio " * 200, "Pagina intermedia " * 200, "Pagina final " * 200]
    calls = []

    def fake_generate(prompt, *a, **k):
        calls.append(prompt)
        return _ollama_response(_all_insufficient())

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    assert len(calls) == len(result["chunk_executions"]) >= 2
    assert result["chunk_executions"][0]["page_start"] == 1
    assert result["chunk_executions"][-1]["page_end"] == 3
    # un finding por checkpoint del prompt real, sean los que sean (antes: == 5)
    assert len(result["findings"]) == len(ce.load_prompt_meta(PROMPT_PATH)["checkpoints"])
    assert all(f["estado"] == "evidencia_insuficiente" for f in result["findings"])
    assert all(e["run_id"] == result["run_id"] for e in result["chunk_executions"])
    assert len({e["task_id"] for e in result["chunk_executions"]}) == len(result["chunk_executions"])
    assert result["model_digest"] == "sha256:fake-digest"


def test_no_cumple_does_not_require_anchoring(monkeypatch):
    pages = ["Contenido de la pagina sin mencion de firma electronica en absoluto." * 5]
    payload = _all_insufficient({
        "21_CFR_11.50_11.70": {"req_id": "21_CFR_11.50_11.70", "estado": "no_cumple",
                                "evidencia_exacta": "esta frase no aparece literalmente en el chunk",
                                "brecha": "No se mencionan controles de firma electronica.",
                                "recomendacion": "Agregar seccion de firma electronica."},
    })
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    firma = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.50_11.70"))
    assert firma["estado"] == "no_cumple"


def test_cumple_parcialmente_still_requires_anchoring(monkeypatch):
    pages = ["Este documento no contiene la frase citada en absoluto." * 5]
    payload = _all_insufficient({
        "21_CFR_11.10(e)": {"req_id": "21_CFR_11.10(e)", "estado": "cumple_parcialmente",
                             "evidencia_exacta": "frase que NO esta en el texto real del chunk",
                             "brecha": "n/a", "recomendacion": "n/a"},
    })
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    audit = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(e)"))
    assert audit["estado"] == "evidencia_insuficiente"


def test_contradiction_between_chunks_is_detected_not_silently_resolved(monkeypatch):
    pages = ["Pagina 1 con acceso restringido documentado claramente aqui. " * 120,
             "Pagina 2 sin ninguna mencion de control de acceso. " * 120]
    call_n = {"i": 0}

    def fake_generate(prompt, *a, **k):
        call_n["i"] += 1
        if call_n["i"] == 1:
            payload = _all_insufficient({
                "21_CFR_11.10(d)": {"req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente",
                                     "evidencia_exacta": "acceso restringido documentado claramente aqui",
                                     "brecha": "n/a", "recomendacion": "n/a"},
            })
        else:
            payload = _all_insufficient({
                "21_CFR_11.10(d)": {"req_id": "21_CFR_11.10(d)", "estado": "no_cumple",
                                     "evidencia_exacta": "sin ninguna mencion de control de acceso",
                                     "brecha": "Ausente en esta seccion.", "recomendacion": "n/a"},
            })
        return _ollama_response(payload)

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    assert len(result["contradictions"]) == 1
    assert result["contradictions"][0]["req_id"] == "21_CFR_11.10(d)"
    finding = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["revision_humana_requerida"] is True
    assert "CONTRADICCION" in finding["brecha"]


def test_topically_irrelevant_citation_is_rejected(monkeypatch):
    """Fix 2026-07-16 (post-mortem C1-FDA-11.10d / C3-ANNEX11-12, ver
    factory/docs/gmpai_reanalysis/fs_v1_2/): una cita que ancla literalmente
    en el chunk pero que NO trata el tema del checkpoint debe descartarse
    para cumple/cumple_parcialmente, no solo verificarse que el texto exista."""
    pages = ["Logins, logouts, and login attempts must be recorded in the Audit Trail " * 20]
    payload = _all_insufficient({
        "21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente",
            "evidencia_exacta": "Logins, logouts, and login attempts must be recorded in the Audit Trail",
            "brecha": "n/a", "recomendacion": "n/a",
        },
    })
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    finding = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["estado"] != "cumple_parcialmente"


def test_no_cumple_without_citation_is_not_observed_not_demonstrated(monkeypatch):
    """Fix 2026-07-16: un no_cumple SIN cita es not_observed_in_chunk, no una
    demostracion de incumplimiento del sistema."""
    pages = ["contenido irrelevante " * 100]
    payload = _all_insufficient({
        "21_CFR_11.10(g)": {"req_id": "21_CFR_11.10(g)", "estado": "no_cumple",
                             "evidencia_exacta": "", "brecha": "", "recomendacion": ""},
    })
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    finding = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(g)"))
    assert finding["estado"] == "no_cumple"
    assert "not_observed_in_chunk" in finding["brecha"] or "ausencia generalizada" in finding["brecha"]
    assert finding["confianza"] == "baja"


def test_unqualified_no_cumple_does_not_create_false_contradiction(monkeypatch):
    """Fix 2026-07-16: un no_cumple SIN cita en un chunk no debe generar una
    contradiccion contra un cumple_parcialmente anclado y tematicamente
    relevante de otro chunk."""
    pages = ["Pagina 1 sin mencion del tema. " * 100,
             "Pagina 2 con acceso restringido documentado claramente aqui. " * 100]
    call_n = {"i": 0}

    def fake_generate(prompt, *a, **k):
        call_n["i"] += 1
        if call_n["i"] == 1:
            payload = _all_insufficient({
                "21_CFR_11.10(d)": {"req_id": "21_CFR_11.10(d)", "estado": "no_cumple",
                                     "evidencia_exacta": "", "brecha": "", "recomendacion": ""},
            })
        else:
            payload = _all_insufficient({
                "21_CFR_11.10(d)": {"req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente",
                                     "evidencia_exacta": "acceso restringido documentado claramente aqui",
                                     "brecha": "n/a", "recomendacion": "n/a"},
            })
        return _ollama_response(payload)

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    assert len(result["contradictions"]) == 0
    finding = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["estado"] == "cumple_parcialmente"
    assert "not_observed_in_chunk" in finding["brecha"]


def test_chunk_execution_metadata_complete(monkeypatch):
    pages = ["texto " * 500]

    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    exe = result["chunk_executions"][0]
    for field in ("run_id", "task_id", "started_at", "finished_at", "wall_clock_ms", "model"):
        assert exe.get(field) not in (None, "")


def test_checkpoint_resume_skips_already_completed_chunks(tmp_path, monkeypatch):
    """Capacidad nueva del motor git-trackeado: si un run se interrumpe a
    mitad de camino, un checkpoint_store permite reanudar sin repetir
    llamadas a Ollama ya hechas para chunks anteriores."""
    pages = ["Pagina A " * 400, "Pagina B " * 400, "Pagina C " * 400]
    store = ce.CheckpointStore(tmp_path)
    calls = {"n": 0}

    def flaky_generate(prompt, *a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("Ollama caido a mitad del run (simulado)")
        return _ollama_response(_all_insufficient())

    monkeypatch.setattr(ollama_client, "generate", flaky_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    result_1 = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                    "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-resume",
                                    checkpoint_store=store, run_context="production")
    # El chunk 2 (indice 1) fallo (ok=False) pero el run completo igual.
    assert any(not ce_["ok"] for ce_ in result_1["chunk_executions"])
    checkpoint = store.load(result_1["run_id"])
    assert checkpoint["completed"] is True

    # Reanudacion explicita: buscar resumible tras marcar el checkpoint como
    # incompleto (simula interrupcion real antes de terminar) y confirmar que
    # NO se re-ejecutan los chunks ya guardados.
    partial_state = {**checkpoint, "chunk_executions": checkpoint["chunk_executions"][:1], "completed": False}
    store.save(result_1["run_id"], partial_state)
    fingerprint = result_1["preflight_metadata"]["run_fingerprint"]
    resumable, mismatch = store.find_resumable("sha-resume", "fda_part11_agent", fingerprint)
    assert mismatch is None
    assert resumable is not None
    assert len(resumable["chunk_executions"]) == 1

    calls["n"] = 0
    result_2 = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                    "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-resume",
                                    checkpoint_store=store, run_context="production")
    # Solo se re-llamo a Ollama para los chunks 2 y 3 (el 1 vino del checkpoint)
    assert calls["n"] == 2
    assert result_2["run_id"] == result_1["run_id"]
    assert len(result_2["chunk_executions"]) == 3


def test_audit_event_written(monkeypatch, tmp_path):
    """El motor escribe un evento resumen por documento en
    factory_audit.jsonl (gmpai_chunked_analysis_run)."""
    from factory.core import audit_writer
    audit_file = tmp_path / "factory_audit.jsonl"
    monkeypatch.setattr(audit_writer, "AUDIT_FILE", audit_file)
    monkeypatch.setattr(audit_writer, "_last_entry_hash", None)

    pages = ["texto " * 500]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-audit", run_context="production")

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event_type"] == "gmpai_chunked_analysis_run"
    assert entry["data"]["run_id"] == result["run_id"]
    assert entry["data"]["document_sha256"] == "sha-audit"


def test_extract_json_repairs_trailing_comma():
    """Fix TE-01: reparacion acotada de comas colgantes antes de reintentar
    json.loads (no inventa contenido, solo corrige sintaxis comun)."""
    raw = ('{"checkpoints": [{"req_id": "21_CFR_11.10(a)", "estado": "no_cumple", '
           '"evidencia_exacta": "", "brecha": "", "recomendacion": "",},]}')
    parsed = ce._extract_json(raw)
    assert parsed is not None
    assert parsed["checkpoints"][0]["req_id"] == "21_CFR_11.10(a)"


def test_extract_json_strips_markdown_fences():
    """Fix TE-01: el modelo a veces envuelve el JSON en cercas ```json pese
    a 'format':'json' -- deben quitarse antes de parsear."""
    raw = ('```json\n{"checkpoints": [{"req_id": "21_CFR_11.10(a)", "estado": "no_cumple", '
           '"evidencia_exacta": "", "brecha": "", "recomendacion": ""}]}\n```')
    parsed = ce._extract_json(raw)
    assert parsed is not None


def test_extract_json_rejects_valid_json_with_wrong_schema():
    """Fix TE-01: JSON sintacticamente valido pero sin la forma esperada
    (checkpoints ausente/vacio, o sin req_id) debe rechazarse -- no basta con
    ser JSON valido."""
    assert ce._extract_json('{"algo_distinto": true}') is None
    assert ce._extract_json('{"checkpoints": []}') is None
    assert ce._extract_json('{"checkpoints": [{"estado": "no_cumple"}]}') is None  # sin req_id


def test_technical_execution_failure_tracked_and_not_silently_evidencia_insuficiente(monkeypatch):
    """Fix TE-01: un chunk con JSON invalido/esquema invalido se marca
    technical_execution_failure=True en su chunk_execution, y el finding
    resultante (si el checkpoint queda sin candidatos) se marca
    technical_execution_failure_pending=True -- no se presenta como una
    conclusion de contenido definitiva."""
    pages = ["contenido irrelevante " * 100]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: {"response": "esto no es json"})
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-te01", run_context="production")

    assert len(result["technical_execution_failures"]) == 1
    assert "technical_execution_failure" in result["chunk_executions"][0]["error"]

    finding = next(f for f in result["findings"]
                   if f["requisito_regulatorio"].startswith("21_CFR_11.10(a)"))
    assert finding["estado"] == "evidencia_insuficiente"
    assert finding["technical_execution_failure_pending"] is True
    assert "PROVISIONAL" in finding["brecha"]


def test_preflight_metadata_captured_before_first_inference(monkeypatch):
    """Requisito de preflight: modelo, model_digest, version de Ollama,
    agent_version, prompt_version, verifier_version, documento, SHA-256 y
    run_id deben capturarse y quedar disponibles en el resultado."""
    pages = ["texto " * 500]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:abc123")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.5.1")

    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-preflight", run_context="production")

    pf = result["preflight_metadata"]
    assert pf["model"] == ollama_client.OLLAMA_MODEL
    assert pf["model_digest"] == "sha256:abc123"
    assert pf["ollama_version"] == "0.5.1"
    assert pf["agent_version"] == "1.0.0"
    assert pf["prompt_version"]
    assert pf["verifier_version"]
    assert pf["documento"] == "doc.pdf"
    assert pf["document_sha256"] == "sha-preflight"
    assert pf["run_id"] == result["run_id"]


def test_ollama_unavailable_fails_fast_before_any_chunk_call(monkeypatch):
    """Fix TE-02: si Ollama no esta disponible, evaluate_chunked debe fallar
    en la captura de metadata (antes de gastar ninguna llamada de chunk),
    no capturar la excepcion en silencio."""
    def _boom():
        raise ollama_client.OllamaUnavailableError("Ollama no alcanzable (simulado)")

    calls = {"n": 0}

    def _generate_should_not_be_called(*a, **k):
        calls["n"] += 1
        return _ollama_response(_all_insufficient())

    monkeypatch.setattr(ollama_client, "show_digest", _boom)
    monkeypatch.setattr(ollama_client, "generate", _generate_should_not_be_called)

    import pytest
    with pytest.raises(ollama_client.OllamaUnavailableError):
        ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", ["texto " * 500],
                            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-unavail", run_context="production")
    assert calls["n"] == 0


# ── Fase 3 (document_remediation_evolution): use_verified_pipeline ─────────
# Wiring puro, sin Ollama real (mismo patron que
# tools/run_validation_evidence.py: "wiring siempre corre en Gate 0").
# La comparacion real contra los 19 findings de FS_v1.2 con Ollama real
# queda pendiente como paso manual posterior (IMPLEMENTATION_ROADMAP.md
# Fase 3, gate de salida).

import pytest


def test_verified_pipeline_off_by_default_no_extra_key(monkeypatch):
    """Cero cambio de comportamiento para todo llamador existente: sin el
    flag, result no trae 'verified_conclusions' en absoluto."""
    pages = ["Texto neutro sin evidencia particular. " * 100]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test", run_context="production")
    assert "verified_conclusions" not in result


def test_verified_pipeline_requires_document_type():
    with pytest.raises(ValueError, match="document_type"):
        ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", ["x"],
                             "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                             run_context="production", use_verified_pipeline=True)


class TestVerifiedPipelineResume:
    """Reanudacion con use_verified_pipeline=True (2026-07-27). Hasta esta
    fecha la combinacion era un ValueError: los checkpoints no persistian
    los registros verificados, asi que reanudar habria consolidado sobre una
    fraccion del documento afirmando coverage_complete=True. Ahora los
    persiste y el resume esta condicionado a que esten completos."""

    PAGES = ["Pagina uno sin relacion. " * 150,
             "Pagina dos sin relacion. " * 150,
             "Pagina tres sin relacion. " * 150]

    def _patch(self, monkeypatch, counter=None):
        def gen(*a, **k):
            if counter is not None:
                counter["n"] += 1
            return _ollama_response(_all_insufficient())
        monkeypatch.setattr(ollama_client, "generate", gen)
        monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
        monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")

    def _run(self, sha, store=None, counter=None, monkeypatch=None):
        self._patch(monkeypatch, counter)
        return ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "1.0.0", self.PAGES,
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", sha,
            run_context="production", use_verified_pipeline=True,
            document_type="FS", checkpoint_store=store)

    def test_resumed_run_matches_uninterrupted_run_exactly(self, tmp_path, monkeypatch):
        """La prueba que importa: reanudar a mitad debe producir las MISMAS
        verified_conclusions que una corrida seguida -- incluido
        chunks_evaluated. Si los registros verificados de los chunks ya
        hechos no se restauraran, la reanudacion consolidaria solo sobre los
        chunks restantes y este assert lo detectaria."""
        baseline = self._run("sha-baseline", monkeypatch=monkeypatch)

        store = ce.CheckpointStore(tmp_path)
        first = self._run("sha-resume", store=store, monkeypatch=monkeypatch)
        assert len(first["chunk_executions"]) == 3

        # Interrupcion real simulada: el checkpoint queda con 1 solo chunk
        # ejecutado y sus registros verificados correspondientes.
        state = store.load(first["run_id"])
        store.save(first["run_id"], {
            **state, "completed": False,
            "chunk_executions": state["chunk_executions"][:1],
            "verified_records_by_req": {r: v[:1] for r, v in state["verified_records_by_req"].items()},
        })

        calls = {"n": 0}
        resumed = self._run("sha-resume", store=store, counter=calls, monkeypatch=monkeypatch)

        assert calls["n"] == 2, "solo deben re-llamarse los 2 chunks pendientes"
        assert resumed["run_id"] == first["run_id"]
        assert resumed["preflight_metadata"]["resumed_from_checkpoint"] is True
        assert resumed["preflight_metadata"]["resumed_chunk_count"] == 1
        assert resumed["verified_conclusions"] == baseline["verified_conclusions"]

    def test_checkpoint_without_verified_records_is_never_resumed(self, tmp_path, monkeypatch):
        """Fail-closed: un checkpoint de formato anterior (sin registros
        verificados) NUNCA se reanuda bajo este flag, ni siquiera con el
        fingerprint correcto. Empieza de cero y lo dice en preflight."""
        self._patch(monkeypatch)
        store = ce.CheckpointStore(tmp_path)
        meta = ce.load_prompt_meta(PROMPT_PATH)
        fingerprint = ce.build_run_fingerprint(
            meta, model_digest=None, document_sha256="sha-legacy", agent_version="1.0.0",
            use_verified_pipeline=True)
        store.save("run-legacy", {
            "run_id": "run-legacy", "document_sha256": "sha-legacy",
            "agent_id": "fda_part11_agent", "documento": "doc.pdf", "archivo": "path/doc.pdf",
            "total_chunks": 3, "chunk_executions": [{"dummy": True}], "completed": False,
            "fingerprint": fingerprint,
        })
        calls = {"n": 0}
        result = self._run("sha-legacy", store=store, counter=calls, monkeypatch=monkeypatch)

        assert result["run_id"] != "run-legacy"
        assert calls["n"] == 3, "los 3 chunks se procesan de cero"
        pf = result["preflight_metadata"]
        assert pf["checkpoint_verified_coverage_discarded"] is True
        assert pf["checkpoint_verified_coverage_detail"]["reason"] == "checkpoint_without_verified_records"
        assert pf["resumed_from_checkpoint"] is False

    def test_checkpoint_with_incomplete_verified_records_is_never_resumed(self, tmp_path, monkeypatch):
        """Fail-closed sobre el hecho, no sobre la intencion: el checkpoint
        dice traer registros verificados, pero no cubren todos los chunks ya
        ejecutados. No se reanuda."""
        self._patch(monkeypatch)
        store = ce.CheckpointStore(tmp_path)
        first = self._run("sha-partial", store=store, monkeypatch=monkeypatch)
        state = store.load(first["run_id"])
        req_ids = list(state["verified_records_by_req"])
        # 3 chunks ejecutados pero un requisito con un solo registro.
        store.save(first["run_id"], {
            **state, "completed": False,
            "verified_records_by_req": {
                **state["verified_records_by_req"],
                req_ids[0]: state["verified_records_by_req"][req_ids[0]][:1],
            },
        })
        calls = {"n": 0}
        result = self._run("sha-partial", store=store, counter=calls, monkeypatch=monkeypatch)

        assert result["run_id"] != first["run_id"]
        assert calls["n"] == 3
        detail = result["preflight_metadata"]["checkpoint_verified_coverage_detail"]
        assert detail["reason"] == "checkpoint_verified_records_incomplete"
        assert detail["detail"]["records_below_coverage"] == {req_ids[0]: 1}

    def test_checkpoint_written_without_the_flag_is_rejected_by_fingerprint(self, tmp_path, monkeypatch):
        """Primera barrera: un checkpoint de un run SIN pipeline verificado
        no es reanudable por uno CON el flag -- el fingerprint los separa."""
        self._patch(monkeypatch)
        store = ce.CheckpointStore(tmp_path)
        plain = ce.evaluate_chunked(
            PROMPT_PATH, "fda_part11_agent", "1.0.0", self.PAGES,
            "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-flagdiff",
            run_context="production", checkpoint_store=store)
        state = store.load(plain["run_id"])
        store.save(plain["run_id"], {**state, "completed": False,
                                     "chunk_executions": state["chunk_executions"][:1]})

        calls = {"n": 0}
        result = self._run("sha-flagdiff", store=store, counter=calls, monkeypatch=monkeypatch)

        assert result["run_id"] != plain["run_id"]
        assert calls["n"] == 3
        pf = result["preflight_metadata"]
        assert pf["checkpoint_fingerprint_mismatch_discarded"] is True
        assert pf["checkpoint_fingerprint_mismatch_detail"]["old_fingerprint"]["use_verified_pipeline"] is False


def test_verified_pipeline_all_insufficient_across_all_chunks_is_provisional_gap(monkeypatch):
    """El fix central de Fase 3: 'evidencia_insuficiente' ya NO se descarta
    en silencio del pipeline verificado -- cada chunk aporta un registro
    not_observed_in_chunk real, coverage_complete=True, sin rejected -> la
    ausencia SI se consolida (nunca EVALUATION_INCOMPLETE por falta de
    registros).

    W5 V2 §10 (2026-07-27): con las 19 fuentes del catalogo todavia en
    PENDING_REVERIFICATION, la ausencia consolidada se emite como
    PROVISIONAL_GAP, no DOCUMENTATION_GAP -- este ultimo esta en
    provisional_evidence_model.PROHIBITED_FINAL_RESULTS_WHILE_PENDING."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    n_chunks = len(result["chunk_executions"])
    assert n_chunks >= 2
    conclusions = result["verified_conclusions"]
    # Solo los requisitos con applicability_value='expected' para document_type
    # 'FS' (ver applicability_matrix.yaml) consolidan ausencia por esta via --
    # 21_CFR_11.10(a) es cross_reference_expected y 11.50_11.70 es optional,
    # cada uno con su propia regla, fuera de alcance de este gate.
    for req_id in ("21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)"):
        c = conclusions[req_id]
        assert c["conclusion"] == "PROVISIONAL_GAP", (req_id, c)
        assert "SOURCE_PENDING_REVERIFICATION" in c["review_flags"], (req_id, c)
        assert c["chunks_evaluated"] == n_chunks


# Debe superar DOS heuristicas distintas y reales: _is_topically_relevant
# de chunked_engine.py (contra el label en espanol del checkpoint) y
# relevance_score de evidence_verifier.py (contra requirement_terms.yaml
# en ingles) -- de ahi la mezcla deliberada de ambos idiomas.
_ANCHORED_QUOTE = ("El acceso de los individuos esta controlado: access is restricted to "
                    "authorized users only, enforced via role-based permission and login authentication.")
# Texto literal de evidence_min_criteria de 21_CFR_11.10(d) en el catalogo
# (requirement_catalog): criterion_text debe coincidir o el contrato de D
# se considera violado (criterios inventados -> NOT_ASSESSABLE).
_D_CRITERIA_11_10_D = [
    "Mecanismo de control de acceso (propio o federado) sobre el sistema, descrito.",
    "Alta, cambio, revision periodica y revocacion de cuentas.",
    "Cuentas humanas individuales (no compartidas).",
    "Cuentas tecnicas no interactivas, si existen, gobernadas con propietario, proposito, privilegio "
    "minimo y prohibicion de firma electronica.",
    "Evidencia de prueba de acceso permitido y denegado.",
]


def _d_assessments(statuses):
    """criterion_assessments reales para 21_CFR_11.10(d). evidence_quote = el
    propio texto del criterio, que las paginas del test contienen literalmente
    -> anclaje real (verify_anchor PASS), nunca simulado."""
    return [
        {"criterion_index": i + 1, "criterion_text": text, "status": status,
          "evidence_quote": text if status == "MET" else "",
          "evidence_location": "pag 1" if status == "MET" else "",
          "justification": "test", "limitations": ""}
        for i, (text, status) in enumerate(zip(_D_CRITERIA_11_10_D, statuses))
    ]


def _run_verified_pipeline_with_positive_citation(monkeypatch, criterion_assessments):
    pages = [f"Introduccion general. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D)
              + " Resto del documento sin relacion. " * 40]
    entry = {"req_id": "21_CFR_11.10(d)", "estado": "cumple",
              "evidencia_exacta": _ANCHORED_QUOTE, "brecha": "n/a", "recomendacion": "n/a"}
    if criterion_assessments is not None:
        entry["criterion_assessments"] = criterion_assessments
    payload = _all_insufficient({"21_CFR_11.10(d)": entry})
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    return ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                run_context="production", use_verified_pipeline=True, document_type="FS")


def test_verified_pipeline_real_anchored_citation_is_provisionally_documented(monkeypatch):
    """Evidencia real, anclada, tematicamente relevante Y con D==MET sobre
    todos los criterios minimos -> 'observed' -> conclusion positiva (nunca
    una ausencia con evidencia positiva real).

    W5 V2 §10: el techo hoy es PROVISIONALLY_DOCUMENTED, no
    DOCUMENTED_AND_SUPPORTED -- la fuente sigue PENDING_REVERIFICATION.
    A∧B∧C∧D==MET es NECESARIO pero no suficiente para un resultado final."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["MET"] * 5))
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["conclusion"] == "PROVISIONALLY_DOCUMENTED"
    assert "SOURCE_PENDING_REVERIFICATION" in c["review_flags"]
    assert c["chunks_observed"] >= 1
    # el Finding SI quedo sustentado: lo provisional es la autoridad de la
    # fuente, no el veredicto sustantivo.
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["substantive_support"] == "SUPPORTED"


# ── R2.1 Opcion C (docs_plan/R2_1_C_DISENO_AGREGACION_D.md, 2026-08-10):
# D agregado entre chunks, end-to-end via evaluate_chunked() real, no solo
# la funcion aislada (ya cubierta en test_semantic_evidence_verification.py).

def _d_assessments_subset(met_indices: set[int]) -> list:
    """criterion_assessments para 21_CFR_11.10(d) donde SOLO los indices en
    met_indices (1-based) quedan MET (anclados con el texto real del
    criterio); el resto NOT_ASSESSABLE -- simula un chunk que solo cubre
    una parte de los criterios reales."""
    return [
        {"criterion_index": i + 1, "criterion_text": text,
         "status": "MET" if (i + 1) in met_indices else "NOT_ASSESSABLE",
         "evidence_quote": text if (i + 1) in met_indices else "",
         "evidence_location": "pag X" if (i + 1) in met_indices else "",
         "justification": "test", "limitations": ""}
        for i, text in enumerate(_D_CRITERIA_11_10_D)
    ]


def test_verified_pipeline_d_aggregates_criteria_scattered_across_chunks(monkeypatch):
    """El caso central que motiva la Opcion C: ningun chunk individual real
    cubre los 5 criterios de 21_CFR_11.10(d), pero entre dos paginas SI --
    D debe agregar y llegar a MET (antes de este fix, habria quedado
    NOT_ASSESSABLE porque solo el 'mejor' chunk individual contaba)."""
    page1_criteria = _D_CRITERIA_11_10_D[:3]
    page2_criteria = _D_CRITERIA_11_10_D[3:]
    page1 = f"Introduccion. {_ANCHORED_QUOTE} " + " ".join(page1_criteria) + " Relleno. " * 500
    page2 = "Seccion siguiente del mismo documento. " + " ".join(page2_criteria) + " Relleno. " * 500
    pages = [page1, page2]

    responses = [
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple",
            "evidencia_exacta": _ANCHORED_QUOTE, "brecha": "n/a", "recomendacion": "n/a",
            "criterion_assessments": _d_assessments_subset({1, 2, 3}),
        }}),
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "evidencia_insuficiente",
            "evidencia_exacta": "", "brecha": "n/a", "recomendacion": "n/a",
            "criterion_assessments": _d_assessments_subset({4, 5}),
        }}),
    ]
    call_count = {"n": 0}

    def _fake_generate(*a, **k):
        idx = call_count["n"]
        call_count["n"] += 1
        return _ollama_response(responses[idx])

    monkeypatch.setattr(ollama_client, "generate", _fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    assert len(result["chunk_executions"]) == 2

    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] == "MET", finding
    assert finding["substantive_support"] == "SUPPORTED"


def test_verified_pipeline_d_contradiction_across_chunks_stays_not_assessable(monkeypatch):
    """Riesgo explicito del diseno: un criterio MET anclado en un chunk y
    NOT_MET en otro es una contradiccion real -- D agregado degrada a
    NOT_ASSESSABLE, nunca se resuelve en silencio a favor de un lado."""
    page1 = f"Introduccion. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    page2 = "Seccion contradictoria del mismo documento. " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    pages = [page1, page2]

    contradicted_index = 2  # 1-based
    assessments_chunk1 = _d_assessments_subset({1, 2, 3, 4, 5})
    assessments_chunk2 = _d_assessments_subset({1, 3, 4, 5})
    assessments_chunk2[contradicted_index - 1]["status"] = "NOT_MET"
    assessments_chunk2[contradicted_index - 1]["evidence_quote"] = ""
    assessments_chunk2[contradicted_index - 1]["evidence_location"] = ""

    responses = [
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple",
            "evidencia_exacta": _ANCHORED_QUOTE, "brecha": "n/a", "recomendacion": "n/a",
            "criterion_assessments": assessments_chunk1,
        }}),
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "no_cumple",
            "evidencia_exacta": "", "brecha": "criterio no cumplido", "recomendacion": "n/a",
            "criterion_assessments": assessments_chunk2,
        }}),
    ]
    call_count = {"n": 0}

    def _fake_generate(*a, **k):
        idx = call_count["n"]
        call_count["n"] += 1
        return _ollama_response(responses[idx])

    monkeypatch.setattr(ollama_client, "generate", _fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")

    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] == "NOT_ASSESSABLE", finding
    assert finding["substantive_support"] != "SUPPORTED"


# ── Fix B4 (R3-T1.6, 2026-08-12, docs_plan/R3_T1_6_FIX_B4_Y_CIERRE.md) ─────
# el candidato "headline" (evidencia_exacta, la cita RESUMEN del requisito)
# puede venir vacio aunque criterion_assessments SI traiga citas MET reales
# y ancladas -- sin rescate, D (ya corregido por B3) se calcula pero nunca
# llega al Finding, porque solo un candidato con anchored=True puede ganar.

def _d_assessments_partial(met_indices: set[int]) -> list:
    """Como _d_assessments_subset, pero los indices fuera de met_indices
    quedan NOT_MET (desacuerdo genuino, no NOT_ASSESSABLE) -- reproduce el
    patron real encontrado en el checkpoint historico (21_CFR_11.10(e),
    chunk 20: 2 MET anclados + 7 NOT_MET genericos, PARTIALLY_MET, nunca
    NOT_ASSESSABLE por incertidumbre)."""
    return [
        {"criterion_index": i + 1, "criterion_text": text,
         "status": "MET" if (i + 1) in met_indices else "NOT_MET",
         "evidence_quote": text if (i + 1) in met_indices else "",
         "evidence_location": "pag X" if (i + 1) in met_indices else "",
         "justification": "test", "limitations": ""}
        for i, text in enumerate(_D_CRITERIA_11_10_D)
    ]


def _run_b4(monkeypatch, estado, criterion_assessments, evidencia_exacta="", pages=None):
    page = pages or [f"Introduccion. " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500]
    entry = {"req_id": "21_CFR_11.10(d)", "estado": estado,
             "evidencia_exacta": evidencia_exacta, "brecha": "n/a", "recomendacion": "n/a"}
    if criterion_assessments is not None:
        entry["criterion_assessments"] = criterion_assessments
    payload = _all_insufficient({"21_CFR_11.10(d)": entry})
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    return ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", page,
                                "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                run_context="production", use_verified_pipeline=True, document_type="FS")


def test_b4_headline_empty_but_criterion_quotes_anchored_rescues_candidate(monkeypatch):
    """CASO REAL: reproduce chunk 20 / 21_CFR_11.10(e) del checkpoint
    historico chunked-943a62bcbb85. evidencia_exacta vacia, pero 2 de 5
    criterios MET con cita real que SI ancla -- el candidato debe ganar
    (headline derivado) y D (PARTIALLY_MET) debe llegar al Finding, en vez
    de perderse en la rama 'sin candidatos'."""
    result = _run_b4(monkeypatch, "cumple_parcialmente", _d_assessments_partial({1, 2}))
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] == "PARTIALLY_MET", finding
    assert finding["evidencia_exacta"].startswith("[headline derivado de citas por criterio verificadas]")
    assert _D_CRITERIA_11_10_D[0] in finding["evidencia_exacta"]


def test_b4_absence_preserved_when_no_criterion_anchors(monkeypatch):
    """AUSENCIA PRESERVADA: headline vacio Y cero criterios MET -- el
    candidato NUNCA gana, la conclusion de ausencia queda intacta (mismo
    comportamiento que antes del fix)."""
    result = _run_b4(monkeypatch, "cumple_parcialmente", _d_assessments_partial(set()))
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] is None, finding
    assert "derivado" not in finding["evidencia_exacta"]


def test_b1_provisional_eligibility_survives_headline_rescue(monkeypatch):
    """R3-T1.8 bloque 0: verificacion de que el bucket CONFIRMED/positivo
    obtenido via el rescate B4/B5 (headline derivado, la ruta NUEVA que
    introdujo la superficie unica, R3-T1.7) sigue pasando por
    apply_conclusion_preconditions §10 -- NUNCA bypasea
    positive_conclusion_eligibility=PROVISIONAL_ONLY (el estado real hoy
    de 21_CFR_11.10(d) en el catalogo).

    HIPOTESIS A confirmada por lectura de codigo (absence_consolidator.py
    lineas 263-293): el prefijo PROVISIONALLY_ ES el mecanismo de respeto,
    no un bypass -- este test lo fija con datos reales que pasan
    especificamente por candidate_validity.resolve_candidate_evidence()
    (headline vacio, rescatado por citas de criterio), no solo por el
    camino de headline directo que test_verified_pipeline_real_anchored_
    citation_is_provisionally_documented ya cubria antes de R3-T1.7."""
    # _ANCHORED_QUOTE (no el texto crudo del criterio del catalogo) como
    # evidence_quote: relevance_score(_ANCHORED_QUOTE, ...) = 0.875, muy
    # por encima del umbral -- evita que verify_llm_output (V5) marque
    # RELEVANCE_REVIEW_REQUIRED (status='review_required' nunca llega a
    # apply_conclusion_preconditions §10 en absoluto -- consolidate() lo
    # resuelve directo a SUPPORTING_EVIDENCE_UNDER_REVIEW, un camino real
    # pero que no ejercita la precondicion B1 que este test quiere probar).
    page = [f"Introduccion. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500]
    assessments = [
        {"criterion_index": i + 1, "criterion_text": text, "status": "MET",
         "evidence_quote": _ANCHORED_QUOTE, "evidence_location": "pag 1",
         "justification": "test", "limitations": ""}
        for i, text in enumerate(_D_CRITERIA_11_10_D)
    ]
    result = _run_b4(monkeypatch, "cumple_parcialmente", assessments, evidencia_exacta="", pages=page)
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    # NUNCA el resultado final "pelado" (bypass de B1) -- solo su
    # equivalente PROVISIONALLY_ (el catalogo real sigue PROVISIONAL_ONLY).
    assert c["conclusion"] not in ("DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED"), c
    assert c["conclusion"] in ("PROVISIONALLY_DOCUMENTED", "PROVISIONALLY_PARTIALLY_DOCUMENTED"), c
    assert "SOURCE_PENDING_REVERIFICATION" in c["review_flags"], c
    assert c["chunks_observed"] >= 1
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["evidencia_exacta"].startswith("[headline derivado de citas por criterio verificadas]"), (
        "este test debe ejercitar la ruta de rescate B4/B5, no el headline directo -- "
        "si esto falla, el test dejo de probar lo que dice probar")


def test_b4_unanchored_criterion_quote_never_rescues(monkeypatch):
    """GUARDIAN CENTRAL anti-fabricacion: headline vacio, y el unico
    criterio 'MET' trae un evidence_quote que NO existe en el chunk (texto
    inventado/de otro chunk) -- Nivel B de verify_sufficiency() ya lo
    descarta de d_detail['met'], asi que el rescate B4 nunca lo ve. El
    candidato sigue sin ganar."""
    assessments = _d_assessments_partial({1})
    assessments[0]["evidence_quote"] = "Este texto jamas aparece en el chunk evaluado, es inventado."
    result = _run_b4(monkeypatch, "cumple_parcialmente", assessments)
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] is None, finding
    assert "derivado" not in finding["evidencia_exacta"]


def test_b4_reference_list_criterion_quote_never_rescues(monkeypatch):
    """Hallazgo adicional durante el diseno (no en el plan original, pero
    necesario): _classify_criteria_for_chunk() solo aplica verify_anchor()
    por criterio, NUNCA detect_reference_list_context() -- a diferencia
    del headline normal. Sin el chequeo explicito que este fix agrega, una
    cita que ancla literalmente pero vive dentro de una lista de
    referencias numeradas ('[N]', el patron real de ANNEX11_4) se colaria
    por la ruta derivada aunque el headline normal la hubiera rechazado."""
    # Indice 3 (no 1): build_page_chunks() re-junta palabras separadas por
    # kerning artificial (ver test_annex11_4_reference_list_still_rejected_
    # after_kerning_fix), y algunos criterios de _D_CRITERIA_11_10_D
    # contienen una "o"/"y" suelta que ese mecanismo fusiona con la palabra
    # vecina ("propio o federado" -> "propioo federado") -- corrompiendo el
    # texto literal antes de llegar a este chequeo. El indice 3 no tiene ese
    # patron y sobrevive intacto; el fenomeno es ortogonal a B4.
    quote = _D_CRITERIA_11_10_D[2]
    page = [f"Referencias: [6] Standard ABC [7] {quote} [8] Standard XYZ [9] Otro documento."]
    assessments = _d_assessments_partial({3})
    result = _run_b4(monkeypatch, "cumple_parcialmente", assessments, pages=page)
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] is None, finding
    assert "derivado" not in finding["evidencia_exacta"]


def test_b4_genuine_contradiction_still_blocks_with_both_headlines_empty(monkeypatch):
    """CONTRADICCION GENUINA sigue bloqueando: dos chunks, AMBOS con
    headline vacio (ambos rescatados por B4 via sus propios criterios
    anclados), en desacuerdo real sobre el criterio 1 (MET en un chunk,
    NOT_MET en el otro) -- D agregado degrada a NOT_ASSESSABLE, exactamente
    igual que si los headlines hubieran venido anclados normalmente. B4
    NUNCA debe destrabar una contradiccion real."""
    page1 = f"Introduccion. " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    page2 = "Seccion contradictoria del mismo documento. " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    pages = [page1, page2]

    assessments_chunk1 = _d_assessments_partial({1, 2, 3, 4, 5})
    assessments_chunk2 = _d_assessments_partial({2, 3, 4, 5})  # criterio 1 queda NOT_MET (contradice)

    # Mismo estado en ambos chunks a proposito: si difieren (p.ej. "cumple"
    # vs "cumple_parcialmente"), dispara el contradiction check de headline
    # (distinct_estados, linea ~1689 -- un mecanismo DISTINTO, anterior a la
    # agregacion D) antes de llegar siquiera a D -- ese Finding nunca puebla
    # d_sufficiency, por diseno, y no es lo que este test quiere ejercitar.
    responses = [
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente", "evidencia_exacta": "",
            "brecha": "n/a", "recomendacion": "n/a", "criterion_assessments": assessments_chunk1,
        }}),
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente", "evidencia_exacta": "",
            "brecha": "n/a", "recomendacion": "n/a", "criterion_assessments": assessments_chunk2,
        }}),
    ]
    call_count = {"n": 0}

    def _fake_generate(*a, **k):
        idx = call_count["n"]
        call_count["n"] += 1
        return _ollama_response(responses[idx])

    monkeypatch.setattr(ollama_client, "generate", _fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")

    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["d_sufficiency"] == "NOT_ASSESSABLE", finding
    assert finding["substantive_support"] != "SUPPORTED"
    # ambos candidatos SI ganaron gracias a B4 (headline derivado) -- la
    # contradiccion se detecta en la agregacion D (verify_sufficiency_
    # aggregated), visible en d_reason, no un candidato descartado en
    # silencio por falta de headline.
    assert finding["evidencia_exacta"].startswith("[headline derivado de citas por criterio verificadas]")


def test_b4_contradiction_blocked_conclusion_reaches_review_queue(monkeypatch, isolated_review_queue):
    """R3-T1.7 (docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md, bloque 3):
    hallazgo real encontrado al validar la superficie unica en la salida
    final -- antes de B4/B5, un candidato con headline vacio nunca llegaba
    a 'observed', asi que una contradiccion genuina jamas llegaba a
    EVALUATION_INCOMPLETE/ABCD_D_NOT_ASSESSABLE con evidencia real
    observada -- quedaba huerfano (NEEDS_HUMAN_REVIEW en el informe, SIN
    entrada en la cola, ninguna de las 3 condiciones de despacho lo
    cubria). Con B4/B5 corregido, este caso SI ocurre -- este test
    confirma que ahora SI se despacha, con la superficie unica activa
    (mismo escenario de dos chunks contradictorios de
    test_b4_genuine_contradiction_still_blocks_with_both_headlines_empty,
    verificado end-to-end contra verified_conclusions y la cola real).

    _ANCHORED_QUOTE (no el texto crudo del criterio del catalogo) como
    evidence_quote: relevance_score(_ANCHORED_QUOTE, ...) = 0.875, muy
    por encima del umbral -- evita que verify_llm_output (V5) marque
    RELEVANCE_REVIEW_REQUIRED y el registro quede status='review_required'
    (lo que haria que consolidate() resolviera SUPPORTING_EVIDENCE_UNDER_
    REVIEW/OBSERVED_ONLY_UNVERIFIED directamente, SIN pasar por D en
    absoluto -- un camino real pero DISTINTO al que este test quiere
    ejercitar: contradiccion genuina sobre evidencia YA verificada)."""
    page1 = f"Introduccion. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    page2 = f"Seccion contradictoria del mismo documento. {_ANCHORED_QUOTE} " + " ".join(_D_CRITERIA_11_10_D) + " Relleno. " * 500
    pages = [page1, page2]

    def _assessments_anchored_quote(met_indices):
        return [
            {"criterion_index": i + 1, "criterion_text": text,
             "status": "MET" if (i + 1) in met_indices else "NOT_MET",
             "evidence_quote": _ANCHORED_QUOTE if (i + 1) in met_indices else "",
             "evidence_location": "pag X" if (i + 1) in met_indices else "",
             "justification": "test", "limitations": ""}
            for i, text in enumerate(_D_CRITERIA_11_10_D)
        ]

    assessments_chunk1 = _assessments_anchored_quote({1, 2, 3, 4, 5})
    assessments_chunk2 = _assessments_anchored_quote({2, 3, 4, 5})  # criterio 1 queda NOT_MET (contradice)

    responses = [
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente", "evidencia_exacta": "",
            "brecha": "n/a", "recomendacion": "n/a", "criterion_assessments": assessments_chunk1,
        }}),
        _all_insufficient({"21_CFR_11.10(d)": {
            "req_id": "21_CFR_11.10(d)", "estado": "cumple_parcialmente", "evidencia_exacta": "",
            "brecha": "n/a", "recomendacion": "n/a", "criterion_assessments": assessments_chunk2,
        }}),
    ]
    call_count = {"n": 0}

    def _fake_generate(*a, **k):
        idx = call_count["n"]
        call_count["n"] += 1
        return _ollama_response(responses[idx])

    monkeypatch.setattr(ollama_client, "generate", _fake_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")

    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE", c
    assert "ABCD_D_NOT_ASSESSABLE" in c["review_flags"], c
    assert c["chunks_observed"] >= 1, "debe haber al menos un registro observed real, no ausencia"

    from factory.layer9.human_review_queue import list_pending
    pending = [e for e in list_pending()
               if e.get("summary", {}).get("run_id") == result["run_id"]
               and e.get("summary", {}).get("requirement_id") == "21_CFR_11.10(d)"]
    assert len(pending) == 1, "el requisito debe tener EXACTAMENTE una entrada en la cola -- antes de este fix no tenia ninguna"
    assert "CONTRADICTION_BLOCKED_POSITIVE_CONCLUSION" in pending[0]["summary"]["review_flags"]


def test_b4_annex11_4_reference_list_still_rejected_end_to_end(monkeypatch):
    """ANNEX11_4 end-to-end tras B4: el caso real conocido (GAMP5 citado
    dentro de una lista de referencias numeradas) sigue rechazado -- ruta
    completa via evaluate_chunked(), no solo la funcion aislada
    (test_annex11_4_reference_list_still_rejected_after_kerning_fix ya
    cubre esa). El chunk NUNCA emite criterion_assessments para ANNEX11_4
    en este escenario (fuera del contrato de fda_part11_agent) -- lo que
    se prueba es que el headline vacio + evidencia solo en la lista de
    referencias no produce una conclusion positiva via el candidato
    headline normal (valid_candidate_verified), que B4 no toca ni afloja."""
    page = ("REFERENCES [6] ISPE Baseline Guide [7] ISA-88 [8] Good Automated "
            "Manufacturing Practice, GAMP5 [9] 21 CFR Part 11 [10] EU Annex 11")
    entry = {"req_id": "21_CFR_11.10(d)", "estado": "cumple",
             "evidencia_exacta": "Good Automated Manufacturing Practice, GAMP5",
             "brecha": "n/a", "recomendacion": "n/a"}
    payload = _all_insufficient({"21_CFR_11.10(d)": entry})
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", [page],
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["conclusion"] != "DOCUMENTED_AND_SUPPORTED"
    assert c["conclusion"] != "PARTIALLY_DOCUMENTED"


def test_b4_anchored_headline_unchanged_behavior(monkeypatch):
    """RETROCOMPATIBILIDAD: un candidato con headline YA anclado (caso
    normal, mayoria de las corridas) se comporta EXACTAMENTE igual que
    antes del fix -- B4 nunca se activa (evidencia.strip() no esta vacio),
    headline_source='model_headline', evidencia_exacta sin el marcador de
    derivado."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["MET"] * 5))
    finding = next(f for f in result["findings"]
                    if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["evidencia_exacta"] == _ANCHORED_QUOTE
    assert "derivado" not in finding["evidencia_exacta"]
    assert finding["d_sufficiency"] == "MET"


# ── W5 V2 Fase F: cierre del hueco de verified_conclusions (2026-07-25) ────
# absence_consolidator decide sobre chunk records y NO conoce D. Sin este
# cableado, una cita positiva anclada concluia DOCUMENTED_AND_SUPPORTED
# (-> FULL_COVERAGE en gap_assessment_finding_mapper) con D sin satisfacer.

def test_verified_conclusion_degrades_when_d_not_assessable(monkeypatch):
    """Misma cita positiva anclada, pero SIN criterion_assessments
    (D=NOT_ASSESSABLE): la evaluacion sustantiva no se hizo -> nunca
    DOCUMENTED_AND_SUPPORTED, sino EVALUATION_INCOMPLETE (el mapper la
    rechaza explicitamente, jamas llega a FULL_COVERAGE)."""
    result = _run_verified_pipeline_with_positive_citation(monkeypatch, None)
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "ABCD_D_NOT_ASSESSABLE" in c["review_flags"]
    assert c["chunks_observed"] >= 1  # la evidencia SI se observo; lo que falta es D


def test_verified_conclusion_ceiling_is_partially_documented_when_d_partially_met(monkeypatch):
    """W5 V2 §12.2: 'Evidencia parcial ⇒ FAIL en D ⇒ maximo
    PARTIALLY_DOCUMENTED'. D=PARTIALLY_MET no puede quedar como
    DOCUMENTED_AND_SUPPORTED, pero tampoco debe hundirse por debajo del
    techo que el plan autoriza."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["MET", "MET", "NOT_MET", "NOT_MET", "NOT_MET"]))
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    # techo §12.2 + provisionalidad §10 aplicados en ese orden
    assert c["conclusion"] == "PROVISIONALLY_PARTIALLY_DOCUMENTED"
    assert "ABCD_D_PARTIALLY_MET" in c["review_flags"]
    assert "SOURCE_PENDING_REVERIFICATION" in c["review_flags"]


def test_verified_conclusion_under_review_when_d_not_met(monkeypatch):
    """D=NOT_MET (ningun criterio minimo confirmado): hay evidencia
    observada pero no sostiene el requisito -> SUPPORTING_EVIDENCE_UNDER_REVIEW,
    nunca una conclusion de soporte ni siquiera parcial."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["NOT_MET"] * 5))
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["conclusion"] == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert "SUBSTANTIVE_EVIDENCE_NOT_ACCEPTED" in c["review_flags"]


def test_verified_conclusion_degradation_is_consistent_with_finding(monkeypatch):
    """La conclusion verificada y el Finding no pueden contradecirse: si el
    Finding quedo NOT_SUPPORTED, la conclusion no puede afirmar soporte --
    ni en su forma final ni en su forma provisional."""
    asserting = ("DOCUMENTED_AND_SUPPORTED", "PARTIALLY_DOCUMENTED",
                 "PROVISIONALLY_DOCUMENTED", "PROVISIONALLY_PARTIALLY_DOCUMENTED")
    for assessments in (None, _d_assessments(["NOT_MET"] * 5)):
        result = _run_verified_pipeline_with_positive_citation(monkeypatch, assessments)
        finding = next(f for f in result["findings"]
                        if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
        c = result["verified_conclusions"]["21_CFR_11.10(d)"]
        assert finding["substantive_support"] == "NOT_SUPPORTED", assessments
        assert c["conclusion"] not in asserting, c


def test_absence_conclusion_is_never_degraded_by_abcd(monkeypatch):
    """Una ausencia consolidada no afirma soporte documental: las reglas
    ABCD no la tocan aunque D nunca se haya evaluado en ese run (solo la
    gobernanza de fuente la marca como provisional)."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    for req_id in ("21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)"):
        c = result["verified_conclusions"][req_id]
        assert c["conclusion"] == "PROVISIONAL_GAP", (req_id, c)
        assert "ABCD_D_NOT_ASSESSABLE" not in c["review_flags"]
        assert "ABCD_NOT_EVALUATED" not in c["review_flags"]


def test_governed_exceptions_key_present_and_empty_on_clean_run(monkeypatch):
    """§13.4: la corrida siempre expone su lista de excepciones gobernadas,
    tambien cuando esta vacia -- nunca 'ausente' (indistinguible de 'no se
    registro')."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["MET"] * 5))
    assert result["governed_exceptions"] == []


def test_consolidation_exception_does_not_abort_the_run(monkeypatch):
    """§13.4.5 + gate '0 fallos recuperables bloqueando toda la corrida':
    si consolidar UN requisito lanza, ese requisito queda
    EVALUATION_INCOMPLETE con excepcion gobernada y los DEMAS se consolidan
    normalmente. Antes de este fix la excepcion se propagaba y tumbaba
    evaluate_chunked() entero."""
    import factory.regulatory.absence_consolidator as ac
    real_consolidate = ac.consolidate

    def exploding(req_id, *a, **k):
        if req_id == "21_CFR_11.10(e)":
            raise RuntimeError("fallo simulado de consolidacion")
        return real_consolidate(req_id, *a, **k)

    monkeypatch.setattr(ac, "consolidate", exploding)
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    failed = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert failed["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "CONSOLIDATION_EXCEPTION" in failed["review_flags"]
    exc = [e for e in result["governed_exceptions"] if e["req_id"] == "21_CFR_11.10(e)"]
    assert len(exc) == 1 and exc[0]["exception"] == "RuntimeError"
    # los demas requisitos NO se vieron afectados: la corrida continuo
    assert result["verified_conclusions"]["21_CFR_11.10(d)"]["conclusion"] == "PROVISIONAL_GAP"
    assert len(result["findings"]) == len(ce.load_prompt_meta(PROMPT_PATH)["checkpoints"])


def test_duplicate_requirement_checkpoint_never_silently_overwrites(monkeypatch):
    """P1 / 'ningun finding puede perderse o sobrescribirse silenciosamente':
    con un req_id repetido en el prompt, el indice req_id->Finding conserva
    solo el ultimo. Los DOS findings siguen en result['findings'] y la
    conclusion se degrada con excepcion gobernada en vez de decidirse sobre
    un indice ambiguo."""
    meta = dict(ce.load_prompt_meta(PROMPT_PATH))
    cps = list(meta["checkpoints"])
    meta["checkpoints"] = cps + [dict(cps[0])]          # req_id duplicado
    monkeypatch.setattr(ce, "load_prompt_meta", lambda _p: meta)
    pages = ["Pagina uno sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    dup_id = cps[0]["req_id"]
    # ningun finding se perdio: hay uno por CADA checkpoint, duplicado incluido
    assert len(result["findings"]) == len(meta["checkpoints"])
    assert sum(1 for f in result["findings"]
                if f["requisito_regulatorio"].startswith(dup_id)) == 2
    c = result["verified_conclusions"][dup_id]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "DUPLICATE_REQUIREMENT_CHECKPOINT" in c["review_flags"]
    exc = [e for e in result["governed_exceptions"]
            if e["exception"] == "DUPLICATE_REQUIREMENT_CHECKPOINT"]
    assert len(exc) == 1 and exc[0]["req_id"] == dup_id


def test_substantive_support_summary_counts_unknown_explicitly(monkeypatch):
    """Un Finding sin veredicto sustantivo se cuenta como UNKNOWN, nunca se
    absorbe en NOT_APPLICABLE (eso presentaria un vacio como 'no aplica')."""
    result = _run_verified_pipeline_with_positive_citation(
        monkeypatch, _d_assessments(["MET"] * 5))
    summary = result["substantive_support_summary"]
    assert set(summary) == set(ce.SUBSTANTIVE_SUPPORT_VALUES)
    assert summary["UNKNOWN"] == 0            # el motor siempre fija el veredicto
    assert sum(summary.values()) == len(result["findings"])


def test_verified_pipeline_technical_failure_chunk_blocks_documentation_gap(monkeypatch):
    """Gate central del roadmap: un chunk con fallo tecnico de ejecucion
    cuenta como rejected_by_verifier para el pipeline verificado -> la
    conclusion es EVALUATION_INCOMPLETE, NUNCA DOCUMENTATION_GAP, aunque
    todos los demas chunks respondieran 'evidencia_insuficiente'."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    call_n = {"i": 0}

    def flaky_generate(*a, **k):
        call_n["i"] += 1
        if call_n["i"] == 1:
            return {"response": "esto no es JSON valido"}
        return _ollama_response(_all_insufficient())

    monkeypatch.setattr(ollama_client, "generate", flaky_generate)
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    assert result["technical_execution_failures"]  # confirma que el fallo tecnico si ocurrio
    # Solo los requisitos con applicability_value='expected' en document_type
    # 'FS' pasan por la rama que bloquea DOCUMENTATION_GAP ante chunks
    # rejected_by_verifier (absence_consolidator.py P3 reforzado); los demas
    # (cross_reference_expected/optional) tienen su propia regla, fuera de
    # alcance de este gate.
    for req_id in ("21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)"):
        c = result["verified_conclusions"][req_id]
        assert c["conclusion"] == "EVALUATION_INCOMPLETE", (req_id, c)
        assert "ABSENCE_BLOCKED_BY_REJECTED_CHUNKS" in c["review_flags"]


# ---------------------------------------------------------------------------
# W5 V2 Fase F -- cableado de D a substantive_support (2026-07-25).
# ---------------------------------------------------------------------------

def test_compute_substantive_support_positive_accepted_is_supported():
    assert ce._compute_substantive_support("cumple", True) == "SUPPORTED"
    assert ce._compute_substantive_support("cumple_parcialmente", True) == "SUPPORTED"


def test_compute_substantive_support_positive_not_accepted_is_not_supported():
    # Fail-closed: False Y None (checkpoint reanudado pre-fase, sin D) ->
    # NOT_SUPPORTED para un estado positivo. Solo True explicito sustenta.
    assert ce._compute_substantive_support("cumple", False) == "NOT_SUPPORTED"
    assert ce._compute_substantive_support("cumple", None) == "NOT_SUPPORTED"
    assert ce._compute_substantive_support("cumple_parcialmente", None) == "NOT_SUPPORTED"


def test_compute_substantive_support_non_positive_is_not_applicable():
    for estado in ("no_cumple", "evidencia_insuficiente", "no_aplica"):
        assert ce._compute_substantive_support(estado, True) == "NOT_APPLICABLE"
        assert ce._compute_substantive_support(estado, None) == "NOT_APPLICABLE"


# ── P2 (2026-07-27): "aplicabilidad aprobada" es precondicion VERIFICADA ──

def test_applicability_rule_approved_is_read_not_assumed(monkeypatch):
    """Defecto reproducido: evaluate_chunked() pasaba
    applicability_rule_approved=True fijo, comentado como "verificado por
    _require_matrix_approved". Esa guardia NO lo verifica: con
    run_context='validation' deja pasar la matriz sin aprobar. El motor
    afirmaba entonces una aprobacion humana inexistente, justo el flag del
    que depende que NOT_APPLICABLE sea legal con fuente pendiente (§13.3).

    Fail-closed esperado: el valor se LEE de la matriz real. (El escenario
    real alcanzable es run_context='validation' con la matriz sin aprobar;
    aqui se sustituye el lector para aislar la precondicion sin arrastrar la
    escritura de evidencia de validacion.)"""
    from factory.regulatory import absence_consolidator, applicability

    seen = []
    real = absence_consolidator.apply_conclusion_preconditions

    def _spy(c, **kw):
        seen.append(kw["applicability_rule_approved"])
        return real(c, **kw)

    monkeypatch.setattr(absence_consolidator, "apply_conclusion_preconditions", _spy)
    monkeypatch.setattr(applicability, "matrix_approved", lambda: False)

    _run_verified_pipeline_with_positive_citation(monkeypatch, _d_assessments(["MET"] * 5))

    assert seen, "apply_conclusion_preconditions no fue invocada"
    assert all(v is False for v in seen), (
        "el motor siguio afirmando applicability_rule_approved=True con la matriz sin aprobar")


def test_applicability_rule_approved_true_when_matrix_is_approved(monkeypatch):
    """Contraparte: con la matriz human_confirmed (estado real hoy) el flag
    llega True -- la correccion no degrada el caso legitimo."""
    from factory.regulatory import absence_consolidator

    seen = []
    real = absence_consolidator.apply_conclusion_preconditions

    def _spy(c, **kw):
        seen.append(kw["applicability_rule_approved"])
        return real(c, **kw)

    monkeypatch.setattr(absence_consolidator, "apply_conclusion_preconditions", _spy)
    _run_verified_pipeline_with_positive_citation(monkeypatch, _d_assessments(["MET"] * 5))
    assert seen and all(v is True for v in seen)


# ===========================================================================
# R2.1 Causa 1 (docs_plan/R2_1_CORRECCION_JUDGMENT_RECALL.md sec.2,
# 2026-08-10): normalizacion de kerning espurio ANTES del anclaje, dentro
# de build_page_chunks() -- no se afloja _is_anchored, se limpia el ruido
# de extraccion que ya rechazaba una cita real de la fase de juicio de R2
# (P1, judgment_recall=0/6 diagnosticado en docs_plan/R2_DESIGN_DETALLADO.md).
# ===========================================================================

# Texto real (pypdf 4.3.1, RW-0005 p.45-46), reutilizado tal cual de
# test_evidence_verifier_v2.CHUNK20_TEXT -- mismo caso real, no un
# fixture sintetico nuevo.
from factory.tests.test_evidence_verifier_v2 import CHUNK20_QUOTE, CHUNK20_TEXT  # noqa: E402

# Candidato real rank-1 devuelto por retriever.retrieve_top_k(RW-0005,
# '21_CFR_11.10(e)', k=5) -- capturado 2026-08-10 contra el corpus real,
# NO el mismo string que CHUNK20_TEXT (ese es el caso real de P5/
# ALCOA_CONTEMPORANEOUS, con membrete de pagina de por medio -- P1 no
# cruza el membrete, asi que su cita real termina antes de llegar ahi).
P1_CHUNK_TEXT = (
    'ller B \nSerialization B \nVial Syringe Labeler  B \nParts Washer / Sterilizer  B \n'
    'Clean Steam Generator B \nWaste Lift and Neutralization  B \nWater for Injection  B \n'
    'Weigh / Dispense B \nAlarm Details B \nAlarm Limit Modification (page 1 of 2) E \n'
    'Alarm Limit Modification2 (page 2 of 2) E \n3Table 4-2: Security Code Assignments for '
    'Graphic Displays \n \n2 Screen access is defined by the first code (least rest rictive), '
    'additional codes indicate objects on screen are \nsubject to additional restrictions \n '
    'Project: Mark Cuban Cost Plus Drug Company, PBC – \n MCCPDC - SCADA and PCS MISC. PLC '
    'System \n \nFunctional Specification for the MCCPDC - SCADA and PCS MISC. PLC System  \n \n \n'
    'ID code: 215115305 -FS (V1.2) Page 45 of 58 \n© 2022 Rockwell Automation, Inc. All Rights '
    'Reserved / Author: Buol, Scott \n5 Data \nF11.00: Databases and Historical Logging \n'
    'This function implements the following user requirement(s)  \nUR3.3.6 Data retentio n time '
    'on the system \n1. The system shall have provision for retaining 1 year of historical data '
    'locally before it is \narchived in an alternate location for safe keeping.   \nUR5.4.7 '
    '[URS-PCS-SR-041] The PLC system shall co mmunicate with a plant historian (collect and '
    '\ntransfer data).   \n F11.01: Process Historian \nThis system contains the Rockwell '
    'FactoryTalk Historian SE software and server which \nsatisfies the requirement to collect '
    'and transfer data. \n F11.02: Critical Data Records \nThis system maintains the following '
    'critical runtime data records: \n FactoryTalk View SE alarm log and activity log data '
    'are stored in the corresponding \ndatabases as analog, digital and string values.     \n '
    'Analog, digital and string device tags that are transferred from the PLC to the '
    '\nFactoryTalk View SE system. \nF12.00: Audit Trail \nThis function implements the following '
    'user requirement(s)  \nUR3.3.1 Every time a critical alarm threshold is modified and audit '
    'trail record shall be generated.  The \nrecord shall contain the following fields  \n1. Date '
    'and time stamps of the change \n2. Original threshold value \n3. Threshold value after '
    'change \n4. User ID of the individual who has changed the threshold value (performer) \n5. '
    'Full name of the individual who has changed the threshold value (performer) \n6. Meaning of '
    'signature (performer) \n7. User ID of the individual who has approved the change (approver) '
    '\n8. Full name of the individual who has approved the change (approver) \n9. Meaning of '
    'signature (approver).  \nUR3.3.2 Every time a critical alarm condition occurs an audit trail '
    'record shall be generated with the \nfollowing fields  \n1. Alarm date and time stamps  \n2. '
    'Alarm tag 3. Alarm value \n4. Alarm description \n5. A similar record shall be generated '
    'wheneve r a critical alarm condition returns to normal \ncondition.  \n'
)

# Cita real emitida por el modelo (raw_response persistido,
# factory/regulatory/pilot_run/checkpoints/raw_responses/chunked-965e5cf6ee5d/
# task-b737fdf292e3.txt.gz, corrida real del batch de R2 diagnosticado en
# docs_plan/R2_DESIGN_DETALLADO.md) -- termina en "...normal condition.",
# nunca cruza el salto de pagina/membrete que sigue despues en el chunk.
P1_QUOTE = (
    "UR3.3.1 Every time a critical alarm threshold is modified and audit trail record shall be "
    "generated. The record shall contain the following fields 1. Date and time stamps of the "
    "change 2. Original threshold value 3. Threshold value after change 4. User ID of the "
    "individual who has changed the threshold value (performer) 5. Full name of the individual "
    "who has changed the threshold value (performer) 6. Meaning of signature (performer) 7. User "
    "ID of the individual who has approved the change (approver) 8. Full name of the individual "
    "who has approved the change (approver) 9. Meaning of signature (approver). UR3.3.2 Every "
    "time a critical alarm condition occurs an audit trail record shall be generated with the "
    "following fields 1. Alarm date and time stamps 2. Alarm tag 3. Alarm value 4. Alarm "
    "description 5. A similar record shall be generated whenever a critical alarm condition "
    "returns to normal condition."
)


def test_join_kerning_split_words_fixes_real_p1_artifact():
    """'wheneve r' -> 'whenever' (unico artefacto real de kerning en este
    chunk) -- reproduce exactamente el caso que R2.1 diagnostico como
    Causa 1 de judgment_recall=0/6."""
    assert "wheneve r" in CHUNK20_TEXT
    fixed = ce._join_kerning_split_words(CHUNK20_TEXT)
    assert "wheneve r" not in fixed
    assert "whenever a critical alarm condition returns" in fixed


def test_join_kerning_split_words_fixes_real_p3_artifact():
    """'retentio n' -> 'retention' -- mismo artefacto, caso real de P3
    (docs_plan/R2_DESIGN_DETALLADO.md, 'Investigacion de P3')."""
    text = "UR3.3.6 Data retentio n time on the system"
    fixed = ce._join_kerning_split_words(text)
    assert "retentio n" not in fixed
    assert "retention time" in fixed


def test_join_kerning_split_words_never_merges_real_separate_words():
    """Riesgo inverso explicito de la orden R2.1 (sec.2.2): dos palabras
    reales separadas por un espacio real NUNCA se fusionan. 'a'/'i' son
    las UNICAS palabras reales de una sola letra en ingles -- exclusion
    exhaustiva, no una lista parcial a completar despues."""
    cases = [
        "I will go there",
        "a cat sat on a mat",
        "as a rule of thumb",
        "one item per line, a description follows",
    ]
    for text in cases:
        assert ce._join_kerning_split_words(text) == text, f"fusiono indebidamente: {text!r}"


def test_join_kerning_split_words_does_not_touch_uppercase_grade_labels():
    """Etiquetas reales de una letra del corpus Rockwell ('Labeler  B',
    grado/clase) son siempre MAYUSCULA -- fuera del alcance del patron
    (solo minusculas), no deben alterarse."""
    text = "Vial Syringe Labeler  B \nAlarm Details B"
    assert ce._join_kerning_split_words(text) == text


def test_build_page_chunks_applies_kerning_fix_to_every_page():
    """build_page_chunks es el punto compartido por evaluate_chunked() (fase
    de juicio) Y por indexer.py (indexacion BM25, via su propia llamada a
    esta misma funcion) -- limpiar aqui beneficia a ambos sin tocar
    indexer.py/bm25.py/query_builder.py/retriever.py (R2.1 sec.1.3)."""
    chunks = ce.build_page_chunks([P1_CHUNK_TEXT], max_chars=10000)
    assert all("wheneve r" not in c["text"] for c in chunks)
    assert any("whenever a critical alarm condition returns" in c["text"] for c in chunks)


def test_is_anchored_accepts_real_p1_citation_after_kerning_fix():
    """Regresion directa del hallazgo de R2.1 (docs_plan/R2_DESIGN_DETALLADO.md,
    Causa 1): la cita real de 913 caracteres que el modelo emitio para P1
    (RW-0005, 21_CFR_11.10(e), corrida real de la fase de juicio de R2)
    daba _is_anchored=False solo por el artefacto de kerning "wheneve r"
    -- tras el fix, ancla. chunk['text'] pasa por build_page_chunks(),
    mismo camino real que evaluate_chunked()."""
    chunks = ce.build_page_chunks([P1_CHUNK_TEXT], max_chars=10000)
    assert ce._is_anchored(P1_QUOTE, chunks[0]["text"]) is True


def test_is_anchored_still_rejects_p1_citation_without_kerning_fix():
    """Contraparte de control: sobre el texto CRUDO (sin pasar por
    build_page_chunks, kerning intacto), la misma cita real sigue
    rechazada -- confirma que el fix, no una casualidad del fixture, es
    lo que cambia el resultado."""
    assert ce._is_anchored(P1_QUOTE, P1_CHUNK_TEXT) is False


def test_annex11_4_reference_list_still_rejected_after_kerning_fix():
    """Test bloqueante explicito de la orden R2.1 (sec.2.4): el fix de
    kerning NUNCA debe hacer pasar el falso positivo ya conocido de
    ANNEX11_4 (GAMP5 citado dentro de una lista de referencias numeradas
    '[N]') -- ese rechazo es de detect_reference_list_context, un
    mecanismo distinto, y debe seguir intacto."""
    from factory.regulatory import semantic_evidence_verification as sev

    source = (
        "REFERENCES [6] ISPE Baseline Guide [7] ISA-88 [8] Good Automated "
        "Manufacturing Practice, GAMP5 [9] 21 CFR Part 11 [10] EU Annex 11"
    )
    quote = "Good Automated Manufacturing Practice, GAMP5"
    fixed = ce._join_kerning_split_words(source)
    assert sev.detect_reference_list_context(quote, fixed) is True


# ===========================================================================
# CONTINUACION_FASE0_P4_FASE1.md Bloque 1 (2026-08-14): fix de la asimetria
# furniture LLM/verificador diagnosticada en INFORMATION_LOSS_ANALYSIS.md --
# antes de este fix, _strip_page_furniture solo se aplicaba en la
# normalizacion interna de evidence_verifier.match_citation() (transitoria,
# nunca mutaba chunk['text']); el texto que build_prompt() enviaba al LLM
# seguia con el membrete de pagina intacto. build_page_chunks() ahora
# reutiliza evidence_verifier.strip_page_furniture (superficie unica, misma
# regex _PAGE_FURNITURE_RE, sin reimplementar nada) en el mismo punto donde
# ya se aplica el fix de kerning.
# ===========================================================================

def test_build_page_chunks_strips_page_furniture_from_every_page():
    """chunk['text'] ya no contiene el membrete de plantilla Rockwell --
    antes de este fix, este assert fallaba (el membrete solo se removia
    en la ruta de verificacion, nunca en la ruta que ve el LLM)."""
    chunks = ce.build_page_chunks([P1_CHUNK_TEXT], max_chars=10000)
    assert "Rockwell Automation, Inc. All Rights Reserved" not in chunks[0]["text"]
    assert "ID code: 215115305" not in chunks[0]["text"]
    # Contenido real (no furniture) se preserva intacto.
    assert "F11.00: Databases and Historical Logging" in chunks[0]["text"]
    assert "UR3.3.1 Every time a critical alarm threshold" in chunks[0]["text"]


def test_build_page_chunks_furniture_strip_reuses_evidence_verifier_single_surface(monkeypatch):
    """Superficie unica (regla dura del Bloque 1.1): build_page_chunks()
    debe invocar evidence_verifier.strip_page_furniture(), nunca una
    regex propia duplicada. Spy sobre la funcion real del modulo --
    confirma reuso real, no una coincidencia de comportamiento."""
    from factory.regulatory import evidence_verifier as ev

    calls = []
    original = ev.strip_page_furniture

    def _spy(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(ev, "strip_page_furniture", _spy)
    ce.build_page_chunks(["hello world"], max_chars=10000)
    assert calls == ["hello world"]


def test_evidence_verifier_strip_page_furniture_is_the_same_object_as_private():
    """El alias publico es una asignacion directa, no una copia -- una
    sola implementacion de la regex/funcion en todo el repo."""
    from factory.regulatory import evidence_verifier as ev
    assert ev.strip_page_furniture is ev._strip_page_furniture


def test_match_citation_still_works_on_furniture_free_chunk():
    """Regresion: evidence_verifier.match_citation() no cambia firma ni
    comportamiento -- sigue comparando contra chunk['text'], ahora ya sin
    furniture desde el origen (idempotente: su propia normalizacion
    interna vuelve a aplicar la misma regex sobre texto ya limpio, sin
    efecto adverso)."""
    from factory.regulatory.evidence_verifier import match_citation

    chunks = ce.build_page_chunks([P1_CHUNK_TEXT], max_chars=10000)
    mtype, _score = match_citation(P1_QUOTE, chunks[0]["text"])
    assert mtype in ("exact", "normalized", "despaced")


# ===========================================================================
# R2.2 §2 (docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md, 2026-08-10): el modo
# JUICIO (candidate pool top-k, cobertura parcial por diseno) NUNCA puede
# emitir DOCUMENTATION_GAP/PROVISIONAL_GAP -- hallazgo real: P2/P5 (Opcion A)
# cerraron PROVISIONAL_GAP con evidencia real presente fuera del pool visto.
# ===========================================================================

def test_baseline_mode_default_still_provisional_gap_no_regression(monkeypatch):
    """Regresion explicita: full_document_coverage=True (default, ningun
    llamador existente lo cambia) sigue produciendo PROVISIONAL_GAP como
    siempre -- mismo escenario exacto que
    test_verified_pipeline_all_insufficient_across_all_chunks_is_provisional_gap,
    repetido aqui para contrastar linea por linea con el modo juicio de
    abajo."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] == "PROVISIONAL_GAP"


def test_judgment_mode_negative_never_emits_gap_falls_to_evaluation_incomplete(monkeypatch, isolated_review_queue):
    """El mismo escenario exacto que el test anterior (mismos chunks, mismo
    payload 'evidencia_insuficiente' en todos), pero con
    full_document_coverage=False (modo juicio, como lo usa judgment.py) --
    debe caer a EVALUATION_INCOMPLETE/ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE,
    NUNCA PROVISIONAL_GAP ni DOCUMENTATION_GAP."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS",
                                  full_document_coverage=False)
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c["review_flags"]
    assert c["conclusion"] not in ("PROVISIONAL_GAP", "DOCUMENTATION_GAP")


def test_judgment_mode_negative_dispatched_to_human_review_queue(monkeypatch, isolated_review_queue):
    """R2.2 §2: el techo negativo del modo juicio se encola en la MISMA
    cola R1.8 que un positivo bajo revision -- 'no encontrado en los
    candidatos vistos' es accionable por un humano, no un resultado mudo.
    Declara cuantos candidatos vio (cobertura real), nunca una cita
    inventada (no hay evidencia observada que citar)."""
    from factory.layer9 import human_review_queue as hrq

    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS",
                                  full_document_coverage=False)
    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"]
    assert len(matches) == 1
    entry = matches[0]
    assert entry["summary"]["conclusion"] == "EVIDENCE_NOT_LOCATED_IN_CANDIDATES"
    assert entry["summary"]["page"] is None
    assert entry["summary"]["evidence_quote"] == ""
    flags = entry["summary"]["review_flags"]
    assert any(f.startswith("PARTIAL_COVERAGE_CANDIDATES_SEEN=") for f in flags)
    assert result["governed_exceptions"] == []


def test_baseline_mode_default_never_dispatches_partial_coverage_entry(monkeypatch, isolated_review_queue):
    """Contraparte de control: con full_document_coverage=True (default),
    el mismo escenario negativo NUNCA genera una entrada
    EVIDENCE_NOT_LOCATED_IN_CANDIDATES -- ese despacho es exclusivo del
    modo juicio. Baseline SÍ despacha (Tier-1, ver test siguiente), pero
    con la conclusión de baseline real (PROVISIONAL_GAP), nunca la de
    modo juicio."""
    from factory.layer9 import human_review_queue as hrq

    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                        run_context="production", use_verified_pipeline=True, document_type="FS")
    pending = hrq.list_pending()
    assert all(e["summary"]["conclusion"] != "EVIDENCE_NOT_LOCATED_IN_CANDIDATES" for e in pending)


# ===========================================================================
# Tier-1 (2026-08-11, .claude/plans/wise-bubbling-toucan.md): el modo
# BASELINE tambien despacha DOCUMENTATION_GAP/PROVISIONAL_GAP a la cola
# R1.8 -- red de seguridad adicional (no una correccion de bug como el
# modo juicio): la conclusion NUNCA cambia, cobertura completa es real.
# ===========================================================================

def test_baseline_gap_dispatched_to_review_queue_conclusion_unchanged(monkeypatch, isolated_review_queue):
    from factory.layer9 import human_review_queue as hrq

    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS")
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] == "PROVISIONAL_GAP"  # sin cambios frente al baseline de siempre

    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"]
    assert len(matches) == 1
    entry = matches[0]["summary"]
    assert entry["conclusion"] == "PROVISIONAL_GAP"
    assert entry["page"] is None
    assert entry["evidence_quote"] == ""
    assert "BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT" in entry["review_flags"]
    assert entry["candidates"] == []  # baseline no tiene pool de fusion
    assert result["governed_exceptions"] == []


def test_judgment_mode_gap_still_never_uses_baseline_dispatch(monkeypatch, isolated_review_queue):
    """Contraste explicito: en modo JUICIO, la rama nueva de Tier-1
    (full_document_coverage=True) nunca se activa -- sigue siendo
    EVALUATION_INCOMPLETE/EVIDENCE_NOT_LOCATED_IN_CANDIDATES, nunca
    DOCUMENTATION_GAP/PROVISIONAL_GAP con el flag de baseline."""
    from factory.layer9 import human_review_queue as hrq

    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                        run_context="production", use_verified_pipeline=True, document_type="FS",
                        full_document_coverage=False)
    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"]
    assert len(matches) == 1
    flags = matches[0]["summary"]["review_flags"]
    assert "BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT" not in flags
    assert matches[0]["summary"]["conclusion"] == "EVIDENCE_NOT_LOCATED_IN_CANDIDATES"


# ===========================================================================
# M4 (2026-08-18, docs_plan/M4_IMPLEMENTACION.md, AD-3): retrieval_mode=
# 'top_k_fusion' con candidate_metadata >= M4_ABSENCE_RANK_THRESHOLD
# promueve coverage_complete a True para absence_consolidator -- 0 LLM,
# mismos escenarios de arriba, contrastados linea por linea.
# ===========================================================================

def _candidate_metadata(n: int) -> list[dict]:
    return [
        {"chunk_index": i, "page_start": i + 1, "page_end": i + 1,
         "bm25_rank": i + 1, "embedding_rank": i + 1, "fusion_rank": i + 1}
        for i in range(n)
    ]


def test_m4_threshold_helper_pure_function():
    """Unidad pura, sin mocks: _top_k_fusion_coverage_complete()."""
    assert ce._top_k_fusion_coverage_complete("top_k_fusion", _candidate_metadata(3), 3) is True
    assert ce._top_k_fusion_coverage_complete("top_k_fusion", _candidate_metadata(5), 3) is True
    assert ce._top_k_fusion_coverage_complete("top_k_fusion", _candidate_metadata(2), 3) is False
    assert ce._top_k_fusion_coverage_complete("top_k_fusion", None, 3) is False
    assert ce._top_k_fusion_coverage_complete("top_k_fusion", [], 3) is False
    assert ce._top_k_fusion_coverage_complete("full_chunk", _candidate_metadata(5), 3) is False


def test_m4_top_k_fusion_threshold_met_emits_gap_not_incomplete(monkeypatch, isolated_review_queue):
    """Mismo escenario exacto (evidencia_insuficiente en todos los chunks)
    que test_judgment_mode_negative_never_emits_gap_falls_to_evaluation_incomplete,
    pero con retrieval_mode='top_k_fusion' y candidate_metadata de longitud
    3 (== M4_ABSENCE_RANK_THRESHOLD) -- ahora SÍ debe emitir una conclusión
    accionable (PROVISIONAL_GAP/DOCUMENTATION_GAP, nunca EVALUATION_INCOMPLETE),
    exactamente el objetivo de M4."""
    pages = ["Pagina uno sin relacion. " * 100,
             "Pagina dos sin relacion. " * 100,
             "Pagina tres sin relacion. " * 100]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS",
                                  full_document_coverage=False, retrieval_mode="top_k_fusion",
                                  candidate_metadata=_candidate_metadata(3))
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] in ("DOCUMENTATION_GAP", "PROVISIONAL_GAP")
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" not in c["review_flags"]


def test_m4_top_k_fusion_below_threshold_still_incomplete_no_regression(monkeypatch, isolated_review_queue):
    """Mismo escenario, pero candidate_metadata de longitud 2
    (< M4_ABSENCE_RANK_THRESHOLD=3) -- M4 NO aplica, sigue cayendo a
    EVALUATION_INCOMPLETE/ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE, mismo
    comportamiento que sin M4. Confirma que el umbral es real, no
    decorativo."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS",
                                  full_document_coverage=False, retrieval_mode="top_k_fusion",
                                  candidate_metadata=_candidate_metadata(2))
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c["review_flags"]


def test_m4_top_k_fusion_without_candidate_metadata_no_regression(monkeypatch, isolated_review_queue):
    """retrieval_mode='top_k_fusion' pero SIN candidate_metadata (llamador
    que no lo pasa) -- M4 no puede aplicar (no hay nada que medir contra
    el umbral), cae al comportamiento de siempre. Mismo escenario que
    test_judgment_mode_negative_never_emits_gap_falls_to_evaluation_incomplete
    salvo por retrieval_mode."""
    pages = ["Pagina uno sin relacion. " * 150, "Pagina dos sin relacion. " * 150]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                                  run_context="production", use_verified_pipeline=True, document_type="FS",
                                  full_document_coverage=False, retrieval_mode="top_k_fusion")
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] == "EVALUATION_INCOMPLETE"
    assert "ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE" in c["review_flags"]


def test_m4_gap_dispatched_to_review_queue_with_ranking_and_threshold(monkeypatch, isolated_review_queue):
    """Requisito explícito de M4 (docs_plan/M4_IMPLEMENTACION.md, bloque
    'QUÉ CONSTRUIR' punto 3): auditable, no una caja negra -- el finding
    encolado trae el umbral usado, el ranking completo de candidatos
    evaluados (todos "descartados" por construcción), y el flag que marca
    que fue M4 quien promovió la cobertura, distinto del despacho de modo
    JUICIO normal (_dispatch_partial_coverage_review) y del de BASELINE
    (_dispatch_baseline_gap_review)."""
    from factory.layer9 import human_review_queue as hrq

    pages = ["Pagina uno sin relacion. " * 100,
             "Pagina dos sin relacion. " * 100,
             "Pagina tres sin relacion. " * 100]
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
                        run_context="production", use_verified_pipeline=True, document_type="FS",
                        full_document_coverage=False, retrieval_mode="top_k_fusion",
                        candidate_metadata=_candidate_metadata(3))
    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "21_CFR_11.10(e)"]
    assert len(matches) == 1
    entry = matches[0]["summary"]
    assert entry["conclusion"] in ("DOCUMENTATION_GAP", "PROVISIONAL_GAP")
    flags = entry["review_flags"]
    assert "M4_ABSENCE_TOP_K_FUSION_COVERAGE_COMPLETE" in flags
    assert "M4_ABSENCE_RANK_THRESHOLD_USED=3" in flags
    assert "M4_ABSENCE_CANDIDATES_SEARCHED=3" in flags
    assert len(entry["candidates"]) == 3
    assert entry["candidates"][0]["fusion_rank"] == 1
    assert "BASELINE_GAP_PENDING_HUMAN_REVIEW_KNOWN_PARAPHRASE_LIMIT" not in flags
    assert not any(f.startswith("PARTIAL_COVERAGE_CANDIDATES_SEEN=") for f in flags)
