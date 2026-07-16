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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
    assert len(calls) == len(result["chunk_executions"]) >= 2
    assert result["chunk_executions"][0]["page_start"] == 1
    assert result["chunk_executions"][-1]["page_end"] == 3
    assert len(result["findings"]) == 5
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
    assert len(result["contradictions"]) == 0
    finding = next(f for f in result["findings"] if f["requisito_regulatorio"].startswith("21_CFR_11.10(d)"))
    assert finding["estado"] == "cumple_parcialmente"
    assert "not_observed_in_chunk" in finding["brecha"]


def test_chunk_execution_metadata_complete(monkeypatch):
    pages = ["texto " * 500]

    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(_all_insufficient()))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: None)
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test")
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

    result_1 = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                    "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-resume",
                                    checkpoint_store=store)
    # El chunk 2 (indice 1) fallo (ok=False) pero el run completo igual.
    assert any(not ce_["ok"] for ce_ in result_1["chunk_executions"])
    checkpoint = store.load(result_1["run_id"])
    assert checkpoint["completed"] is True

    # Reanudacion explicita: buscar resumible tras marcar el checkpoint como
    # incompleto (simula interrupcion real antes de terminar) y confirmar que
    # NO se re-ejecutan los chunks ya guardados.
    partial_state = {**checkpoint, "chunk_executions": checkpoint["chunk_executions"][:1], "completed": False}
    store.save(result_1["run_id"], partial_state)
    resumable = store.find_resumable("sha-resume", "fda_part11_agent")
    assert resumable is not None
    assert len(resumable["chunk_executions"]) == 1

    calls["n"] = 0
    result_2 = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                    "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-resume",
                                    checkpoint_store=store)
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
    result = ce.evaluate_chunked(PROMPT_PATH, "fda_part11_agent", "1.0.0", pages,
                                  "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-audit")

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event_type"] == "gmpai_chunked_analysis_run"
    assert entry["data"]["run_id"] == result["run_id"]
    assert entry["data"]["document_sha256"] == "sha-audit"
