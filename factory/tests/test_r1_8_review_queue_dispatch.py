"""
R1.8 (docs_plan/R1_CIERRE_Y_PREP_R2.md, 2026-08-09) -- hallazgo abierto de
R1.7: SUPPORTING_EVIDENCE_UNDER_REVIEW llegaba hasta
result["verified_conclusions"] como campo consultable, pero nada lo
despachaba a un humano. chunked_engine.evaluate_chunked() ahora encola esos
findings en la cola de revision humana ya existente
(factory/layer9/human_review_queue.py) en el camino de escritura del run.

Ollama SIEMPRE mockeado. review_queue.jsonl SIEMPRE aislado
(conftest.py::isolated_review_queue, autouse). El caso P5 usa la respuesta
REAL y persistida del modelo -- replay offline, cero llamadas nuevas."""
from __future__ import annotations

import json
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client
from factory.layer9 import human_review_queue as hrq

ALCOA_PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "alcoa_prompts.yaml"
ANNEX11_PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "annex11_prompts.yaml"
PART11_PROMPT_PATH = Path(__file__).parent.parent / "engines" / "gmpai_integrity" / "prompts" / "part11_prompts.yaml"

_P5_CHECKPOINT_PATH = (
    Path(__file__).parent.parent / "regulatory" / "pilot_run"
    / "r1_5_h2h4_chunked-596f70cc4520" / "checkpoint.json"
)


def _ollama_response(payload: dict) -> dict:
    return {"response": json.dumps(payload), "done": True, "done_reason": "stop"}


def _run_single_checkpoint(monkeypatch, prompt_path, agent_id, req_id, estado, evidencia, pages,
                            document_type="FS"):
    payload = {"checkpoints": [
        {"req_id": req_id, "estado": estado, "evidencia_exacta": evidencia,
         "brecha": "n/a", "recomendacion": "n/a"},
    ]}
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    return ce.evaluate_chunked(
        prompt_path, agent_id, "1.0.0", pages,
        "Rockwell", "doc.pdf", "1.0", "path/doc.pdf", "sha-test",
        run_context="production", use_verified_pipeline=True, document_type=document_type,
        evaluation_profile="H2H4", target_requirement_ids=[req_id],
    )


def test_p5_real_replay_produces_exactly_one_queue_entry(monkeypatch, isolated_review_queue):
    """P5 real (replay offline). SUPPORTING_EVIDENCE_UNDER_REVIEW debe
    generar exactamente una entrada en cola, con los campos completos:
    run_id, requirement_id, documento, pagina, la cita anclada real, y el
    flag OBSERVED_ONLY_UNVERIFIED."""
    raw = json.loads(_P5_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    real_payload = json.loads(raw["chunk_executions"][0]["raw_response"])
    evidencia_real = real_payload["checkpoints"][0]["evidencia_exacta"]

    monkeypatch.setattr(ollama_client, "generate", lambda *a, **k: _ollama_response(real_payload))
    monkeypatch.setattr(ollama_client, "show_digest", lambda: "sha256:fake-digest")
    monkeypatch.setattr(ollama_client, "ollama_version", lambda: "0.0.0-test")
    pages = [evidencia_real + "  " + "Resto de la pagina sin relacion. " * 60]
    result = ce.evaluate_chunked(
        ALCOA_PROMPT_PATH, "alcoa_plus_agent", "1.0.0", pages,
        "Rockwell", "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf", "1.2",
        "path/doc.pdf", "sha-test", run_context="production",
        use_verified_pipeline=True, document_type="FS",
        evaluation_profile="H2H4", target_requirement_ids=["ALCOA_CONTEMPORANEOUS"],
    )
    assert result["verified_conclusions"]["ALCOA_CONTEMPORANEOUS"]["conclusion"] == \
        "SUPPORTING_EVIDENCE_UNDER_REVIEW"

    pending = hrq.list_pending()
    matches = [e for e in pending if e["summary"]["requirement_id"] == "ALCOA_CONTEMPORANEOUS"]
    assert len(matches) == 1
    entry = matches[0]
    assert entry["entry_type"] == "finding_review"
    assert entry["status"] == "pending"
    assert entry["summary"]["run_id"] == result["run_id"]
    assert entry["summary"]["document_id"] == "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf"
    assert entry["summary"]["evidence_quote"] == evidencia_real
    assert "OBSERVED_ONLY_UNVERIFIED" in entry["summary"]["review_flags"]
    assert entry["summary"]["conclusion"] == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    # Regresión (hallazgo real, 2026-08-09): "finding_enqueued_for_review"
    # faltaba en audit_writer.VALID_EVENTS -- el despacho a la cola SÍ
    # escribía la entrada real, pero su evento de auditoría fallaba en
    # silencio (capturado aquí, en governed_exceptions). Corregido en
    # audit_writer.py; este assert evita que un evento nuevo futuro
    # reintroduzca el mismo patrón sin que ningún test lo note.
    assert result["governed_exceptions"] == []


def test_negative_annex11_4_generates_no_queue_entry(monkeypatch, isolated_review_queue):
    """ANNEX11_4 (GAMP5 en lista de referencias) nunca llega a
    SUPPORTING_EVIDENCE_UNDER_REVIEW -- no hay evidencia que revisar, no
    debe generar ninguna entrada en cola."""
    annex_doc = (
        "[6]  21 CFR Part 11 Electronic Records, Electronic Signatures\n"
        "[7]  21 CFR Part 211 Current GMP for finished Pharmaceuticals\n"
        "[8]  Good Automated Manufacturing Practice, Guide for Validation (GAMP5)\n"
        "[9]  Control programming specification\n"
        + "Relleno de pagina sin relacion. " * 60
    )
    result = _run_single_checkpoint(
        monkeypatch, ANNEX11_PROMPT_PATH, "eu_annex11_agent", "ANNEX11_4",
        "cumple_parcialmente", "Good Automated Manufacturing Practice, Guide for Validation (GAMP5)",
        [annex_doc],
    )
    assert result["verified_conclusions"]["ANNEX11_4"]["conclusion"] != "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert hrq.list_pending() == []


def test_wrong_topic_case_also_dispatched_to_queue(monkeypatch, isolated_review_queue):
    """Version verificada del caso wrong-topic (R1.7): tambien debe quedar
    encolada -- es la MISMA senal debil que P5 (SUPPORTING_EVIDENCE_UNDER_
    REVIEW), no una excepcion al despacho."""
    wrong_topic_doc = "Logins, logouts, and login attempts must be recorded in the Audit Trail. " * 20
    result = _run_single_checkpoint(
        monkeypatch, PART11_PROMPT_PATH, "fda_part11_agent", "21_CFR_11.10(d)",
        "cumple_parcialmente", "Logins, logouts, and login attempts must be recorded in the Audit Trail",
        [wrong_topic_doc],
    )
    assert result["verified_conclusions"]["21_CFR_11.10(d)"]["conclusion"] == \
        "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    pending = hrq.list_pending()
    assert len(pending) == 1
    assert pending[0]["summary"]["requirement_id"] == "21_CFR_11.10(d)"
    assert result["governed_exceptions"] == []
