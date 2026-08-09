"""
R1.7 (docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md, seccion "R1.7" del
roadmap, 2026-08-09) -- el pipeline verificado (el que usa
corpus_runner/produccion) deja de usar chunked_engine._is_topically_relevant()
como pre-filtro de rechazo duro. Se mantiene solo su componente
deterministico y ya probado (semantic_evidence_verification.
detect_reference_list_context) como unico rechazo duro adicional al
anclaje literal; la relevancia lexica deja de bloquear y fluye tal cual a
evidence_verifier.verify_llm_output() (V5, sin tocar), que YA la traduce a
status='review_required' cuando es debil -- y absence_consolidator.py YA
sabe tratar eso de forma segura (SUPPORTING_EVIDENCE_UNDER_REVIEW, nunca
promovido a una conclusion positiva confirmada).

Ollama SIEMPRE mockeado. El caso P5 usa la respuesta REAL y persistida del
modelo (factory/regulatory/pilot_run/r1_5_h2h4_chunked-596f70cc4520/) --
replay offline, cero llamadas nuevas, mismo criterio que R1_6 seccion 4.3.

El pipeline LEGACY (result["findings"]) no se toca -- sigue usando
_is_topically_relevant sin cambios (ver test_gmpai_chunked_engine.py::
test_topically_irrelevant_citation_is_rejected, que sigue verde sin
modificarse)."""
from __future__ import annotations

import json
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity import ollama_client

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


def test_p5_real_evidence_reaches_observed_flagged_for_review(monkeypatch):
    """Replay offline de la respuesta REAL y persistida del modelo para P5
    (run_id=chunked-596f70cc4520, RW-0005, p.45, ALCOA_CONTEMPORANEOUS).
    Antes de R1.7: not_observed_in_chunk / evidencia_insuficiente (rechazo
    por mismatch de idioma). Despues de R1.7: la evidencia real (anclaje
    score 1.0, verificado independientemente en R1.5/R1.6) deja de
    perderse -- llega a 'observed' y queda flageada para revision humana
    (SUPPORTING_EVIDENCE_UNDER_REVIEW), nunca una aprobacion silenciosa."""
    raw = json.loads(_P5_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    real_payload = json.loads(raw["chunk_executions"][0]["raw_response"])
    evidencia_real = real_payload["checkpoints"][0]["evidencia_exacta"]
    assert "FactoryTalk View SE" in evidencia_real  # confirma que es la cita real, no un fixture

    monkeypatch.setattr(ollama_client, "generate",
                         lambda *a, **k: _ollama_response(real_payload))
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
    c = result["verified_conclusions"]["ALCOA_CONTEMPORANEOUS"]
    assert c["chunks_observed"] == 1, "la evidencia real ya no debe perderse -- antes de R1.7 era 0"
    assert c["conclusion"] == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert "OBSERVED_ONLY_UNVERIFIED" in c["review_flags"]
    assert c["conclusion"] not in ("DOCUMENTED_AND_SUPPORTED", "PROVISIONALLY_DOCUMENTED"), (
        "nunca una aprobacion silenciosa -- la relevancia lexica es debil, debe quedar flageada")


def test_annex11_4_reference_list_still_never_observed_through_verified_pipeline(monkeypatch):
    """N1 del fixture set, por el pipeline verificado (no el golden dataset
    sintetico). El rechazo ahora viene del mecanismo estructural real
    (detect_reference_list_context), no de una coincidencia de idioma --
    pero el resultado observable debe ser identico: nunca observed."""
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
    c = result["verified_conclusions"]["ANNEX11_4"]
    assert c["chunks_observed"] == 0
    assert c["conclusion"] not in ("DOCUMENTED_AND_SUPPORTED", "PROVISIONALLY_DOCUMENTED",
                                    "SUPPORTING_EVIDENCE_UNDER_REVIEW")


def test_n2_table_of_contents_mention_still_never_reaches_positive_conclusion(monkeypatch):
    """N2 del fixture set (docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md):
    pagina 3 (0-based) de RW-0005 real, tabla de contenidos --
    'F12.00: Audit Trail .............................................. 45'.
    Mencion superficial de la palabra clave exacta del requisito, en un
    contexto (indice) que no aporta evidencia sustantiva ninguna.

    Nota importante (no cubierta por detect_reference_list_context, que
    solo detecta listas de referencias '[N]' entre corchetes -- un patron
    estructural DISTINTO del de una tabla de contenidos con guiones de
    punto): el escenario realista (el modelo no reporta criterion_
    assessments para una mencion tan debil, mismo patron que P5 real en
    R1.5 cuando la evidencia es insuficiente) queda protegido por D
    (NOT_ASSESSABLE sin criterion_assessments -> _apply_preconditions
    nunca promueve a una conclusion positiva). Esto NO es nuevo de R1.6/
    R1.7 -- ya era asi antes (el label 'Audit trail seguro con timestamp'
    tambien contiene 'audit'/'trail' literalmente, asi que incluso
    _is_topically_relevant original habria dejado pasar esta cita)."""
    toc_doc = (
        "5 Data .......................................................................... 45\n"
        "F11.00: Databases and Historical Logging ........................ 45\n"
        "F12.00: Audit Trail .............................................................. 45\n"
        "F13.00: Long-Term Archiving and Data Retrieval .............. 47\n"
        "F14.00: Backup and recovery ............................................ 47\n"
        + "Relleno de pagina sin relacion. " * 60
    )
    result = _run_single_checkpoint(
        monkeypatch, PART11_PROMPT_PATH, "fda_part11_agent", "21_CFR_11.10(e)",
        "cumple_parcialmente", "F12.00: Audit Trail .............................................................. 45",
        [toc_doc],
    )
    c = result["verified_conclusions"]["21_CFR_11.10(e)"]
    assert c["conclusion"] not in ("DOCUMENTED_AND_SUPPORTED", "PROVISIONALLY_DOCUMENTED")


def test_wrong_topic_same_language_flagged_not_silently_verified(monkeypatch):
    """Version verificada de test_topically_irrelevant_citation_is_rejected
    (que sigue probando el pipeline legacy sin cambios). Por el pipeline
    verificado, una cita real, anclada, pero de otro tema NO debe volverse
    'verified' silenciosamente -- debe quedar observada pero flageada para
    revision humana, igual que P5 (misma naturaleza de senal debil)."""
    wrong_topic_doc = "Logins, logouts, and login attempts must be recorded in the Audit Trail. " * 20
    result = _run_single_checkpoint(
        monkeypatch, PART11_PROMPT_PATH, "fda_part11_agent", "21_CFR_11.10(d)",
        "cumple_parcialmente", "Logins, logouts, and login attempts must be recorded in the Audit Trail",
        [wrong_topic_doc],
    )
    c = result["verified_conclusions"]["21_CFR_11.10(d)"]
    assert c["chunks_observed"] == 1
    assert c["conclusion"] == "SUPPORTING_EVIDENCE_UNDER_REVIEW"
    assert c["conclusion"] not in ("DOCUMENTED_AND_SUPPORTED", "PROVISIONALLY_DOCUMENTED")
