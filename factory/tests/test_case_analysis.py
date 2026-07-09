"""
W7 Fase B — Tests del análisis de casos regulatorios por agente.

Garantías fijadas (contrato de Fase A aprobado por Cesar):
  - trigger: solo "manual" (403); principal con nombre real (422)
  - elegibilidad: caso y misión existentes (404); análisis pendiente de
    decisión bloquea uno nuevo (409)
  - evidencia del prompt: exactamente los 6 ítems del diseño, caso objetivo
    trust=external con tope propio; SIN otros casos de la memoria
  - cases.jsonl JAMÁS se reescribe (byte-idéntico tras generar y decidir)
  - registro versionado inmutable: prompt/respuesta intactos tras decisión
  - accept solo marca el registro y audita: no toca dossier ni documentos
  - request_changes regenera en modo revisión (ledger + temp 0.0)
  - formato inválido → 1 reintento → format_invalid archivado + evento failed
  - guard anti-truncado y errores Ollama → fallo gobernado auditado
  - caso stale → flag stale_case (declara, no bloquea)
  - auditoría: 1 evento por acto; read_analysis nunca audita
  - estructural: el módulo no importa httpx ni nombra el endpoint de
    aprobación; su única vía LLM es la referencia de módulo a W6.5
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import case_analysis_service as svc
from factory.services import dossier_agent_review_service as review
from factory.services import paths as svc_paths

MANUAL = {"mode": "manual", "principal": "Cesar", "authorization_ref": None}

CASE_ID = "openfda_enforcement:TEST-001"
STALE_CASE_ID = "openfda_enforcement:TEST-002"

GOOD_CASE_RESPONSE = """### Relevancia para la misión

- [E: case] El caso es un recall Class II por Lack of Assurance of Sterility.
- [E: mission] La misión cubre investigación OOS de HPLC con trazabilidad ALCOA+.

### Impacto potencial en el sistema validado

- [SE] No hay evidencia local de que el producto del caso esté en el alcance del laboratorio.

### Acciones recomendadas (condicionadas a revisión QA)

- [REF: 21 CFR 211.192] Una investigación documentada sería exigible si QA determina relación con el alcance.

## Limitaciones

- Corpus regulatorio parcial: toda referencia queda sujeta a verificación humana.
"""


def _case(case_id: str, consulted_at: str, reason: str) -> dict:
    return {
        "case_id": case_id, "source_id": "openfda_enforcement",
        "authority": "FDA", "case_type": "drug_recall",
        "classification": "Class II", "recall_status": "Ongoing",
        "product": "Producto Inyectable USP 5 mL", "reason": reason,
        "recalling_firm": "Firma Test LLC",
        "recall_initiation_date": "20260512", "report_date": "20260610",
        "consulted_at": consulted_at, "last_checked": consulted_at,
        "keywords": ["Class II"], "tags": ["sterility"],
        "summary": f"Class II · {reason}",
        "content_hash": "sha256:feedcafe", "embedding_ref": None,
        "url": "https://api.fda.gov/drug/enforcement.json?search=x",
        "freshness": {"stale_after_days": 30}, "relevance": None,
    }


@pytest.fixture()
def case_env(tmp_path, monkeypatch, isolated_audit):
    """Misión demo + design proposal + perfiles + memoria con 2 casos (uno
    fresco → qa_oos_profile; uno stale con señales DI → integrity) + Ollama
    de W6.5 mockeado con GOOD_CASE_RESPONSE."""
    missions = tmp_path / "missions"; missions.mkdir()
    (missions / "demo.yaml").write_text(
        "status: approved\n"
        "objective: Investigar OOS de HPLC con trazabilidad ALCOA+\n"
        "client_type: pharma_qc_lab\n"
        "regulatory_scope: [21_CFR_PART_11, ALCOA_PLUS]\n"
        "constraints: [Aprobación humana requerida]\n", encoding="utf-8")

    designs = tmp_path / "designs"; (designs / "demo").mkdir(parents=True)
    (designs / "demo" / "agent_design_proposal.yaml").write_text(
        "agents:\n"
        "  - {agent_id: qa_oos_profile, decision: profile, base_agent: qa,\n"
        "     rationale: OOS cabe en QA}\n", encoding="utf-8")

    profiles = tmp_path / "profiles"; profiles.mkdir()
    (profiles / "qa_profiles.yaml").write_text(
        "profiles:\n"
        "  qa_oos_profile:\n"
        "    corpus_available: ['21 CFR 211.160, 211.165, 211.192 — texto público']\n"
        "    corpus_pending: [FDA OOS Guidance 2022]\n", encoding="utf-8")
    (profiles / "integrity_profiles.yaml").write_text(
        "profiles:\n"
        "  integrity_lims_profile:\n"
        "    corpus_available: [21 CFR Part 11 texto público]\n"
        "    corpus_pending: []\n", encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases_file = tmp_path / "cases.jsonl"
    cases_file.write_text(
        json.dumps(_case(CASE_ID, now, "Lack of Assurance of Sterility")) + "\n"
        + json.dumps(_case(STALE_CASE_ID, "2026-01-01T00:00:00Z",
                           "data integrity failure in audit trail records")) + "\n",
        encoding="utf-8")

    for name, val in [("MISSIONS_DIR", missions), ("DESIGNS_BASE", designs),
                      ("PROFILES_DIR", profiles),
                      ("CASE_MEMORY_FILE", cases_file),
                      ("AUDIT_FILE", isolated_audit),
                      ("TEST_CATALOGS_DIR", tmp_path / "catalogs"),
                      ("VALIDATION_BASE", tmp_path / "validation"),
                      ("CASE_ANALYSES_BASE", tmp_path / "case_analyses")]:
        monkeypatch.setattr(svc_paths, name, val)

    monkeypatch.setattr(review, "_ollama_generate",
                        lambda prompt, temperature=0.2:
                        {"response": GOOD_CASE_RESPONSE})
    return tmp_path


def _audit_events(env):
    f = env / "factory_audit_test.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]


# ── Generación ────────────────────────────────────────────────────────────────

def test_analyze_creates_versioned_record(case_env):
    out = svc.analyze_case("demo", CASE_ID, MANUAL)
    assert out["status"] == "agent_analysis_proposed"
    assert out["version"] == 1
    assert out["mode"] == "draft"
    assert out["agent"]["primary"] == "qa_oos_profile"

    rec = svc.read_analysis("demo", CASE_ID)
    # routing determinista W6.4 registrado en el record
    assert rec["routing"] == {"agent_id": "qa_oos_profile",
                              "reason": rec["routing"]["reason"],
                              "deterministic": True}
    # evidencia: exactamente los 6 ítems del diseño de Fase A, en orden
    ids = [s["id"] for s in rec["evidence_sources"]]
    assert ids == ["mission", "agents", "case", "case_presentation",
                   "detail_status", "compare"]
    # el caso y su presentación son EXTERNOS; ningún otro caso entra
    trust = {s["id"]: s["trust"] for s in rec["evidence_sources"]}
    assert trust["case"] == "external"
    assert trust["case_presentation"] == "external"
    assert not any(i.startswith("case:") for i in ids)
    # gobierno completo
    assert rec["prompt"]["set_version"] == "1.0.0"
    assert rec["prompt"]["template_sha256"] and rec["prompt"]["rendered_sha256"]
    assert rec["model"]["options"]["temperature"] == review.TEMPERATURE
    assert rec["case_ref"]["content_hash"] == "sha256:feedcafe"
    assert rec["case_ref"]["stale"] is False
    assert rec["decision"] is None
    assert "sin valor regulatorio" in rec["regulatory_note"]
    # el prompt centró el caso y avisa que el detalle no está persistido
    assert "CASO OBJETIVO: " + CASE_ID in rec["governance"]["prompt_full"]
    assert "no está persistido" in rec["governance"]["prompt_full"]

    events = _audit_events(case_env)
    gen = [e for e in events if e["event_type"] == "case_analysis_generated"]
    assert len(gen) == 1
    assert gen[0]["project_id"] == "demo"
    assert gen[0]["data"]["case_id"] == CASE_ID
    assert gen[0]["data"]["requested_by"] == "Cesar"
    assert gen[0]["data"]["case_content_hash"] == "sha256:feedcafe"


def test_trigger_manual_only(case_env):
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("demo", CASE_ID, {"mode": "auto", "principal": "Cesar"})
    assert e.value.status_code == 403
    assert _audit_events(case_env) == []


def test_unknown_case_and_mission_404(case_env):
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("demo", "openfda_enforcement:NOPE", MANUAL)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("ghost", CASE_ID, MANUAL)
    assert e.value.status_code == 404


def test_pending_analysis_blocks_new_draft(case_env):
    svc.analyze_case("demo", CASE_ID, MANUAL)
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("demo", CASE_ID, MANUAL)
    assert e.value.status_code == 409
    assert "pendiente" in str(e.value.detail)


def test_stale_case_flagged_not_blocked(case_env):
    out = svc.analyze_case("demo", STALE_CASE_ID, MANUAL)
    assert out["status"] == "agent_analysis_proposed"
    assert "stale_case" in out["flags"]
    rec = svc.read_analysis("demo", STALE_CASE_ID)
    assert rec["case_ref"]["stale"] is True
    # señales DI del caso → routing integrity con supporting qa
    assert rec["agent"]["primary"] == "integrity_lims_profile"
    assert rec["agent"]["supporting"] == ["qa_oos_profile"]


# ── Memoria y dossier intactos ────────────────────────────────────────────────

def test_cases_jsonl_never_rewritten(case_env):
    before = svc_paths.CASE_MEMORY_FILE.read_bytes()
    svc.analyze_case("demo", CASE_ID, MANUAL)
    svc.decide_analysis("demo", CASE_ID, "accept", "Cesar")
    assert svc_paths.CASE_MEMORY_FILE.read_bytes() == before


def test_accept_marks_record_only(case_env):
    svc.analyze_case("demo", CASE_ID, MANUAL)
    out = svc.decide_analysis("demo", CASE_ID, "accept", "Cesar",
                              reason="útil como señal para la misión")
    assert out["analysis_status"] == "accepted"
    rec = svc.read_analysis("demo", CASE_ID)
    assert rec["status"] == "accepted"
    assert rec["decision"]["decided_by"] == "Cesar"
    # accept NO toca el dossier: validation/ sigue sin existir
    assert not (svc_paths.VALIDATION_BASE / "demo").exists()
    dec = [e for e in _audit_events(case_env)
           if e["event_type"] == "case_analysis_decision"]
    assert len(dec) == 1 and dec[0]["data"]["new_status"] == "accepted"


def test_reject_requires_reason(case_env):
    svc.analyze_case("demo", CASE_ID, MANUAL)
    with pytest.raises(HTTPException) as e:
        svc.decide_analysis("demo", CASE_ID, "reject", "Cesar")
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        svc.decide_analysis("demo", CASE_ID, "bless", "Cesar", reason="x")
    assert e.value.status_code == 422


def test_decision_requires_pending_analysis(case_env):
    with pytest.raises(HTTPException) as e:
        svc.decide_analysis("demo", CASE_ID, "accept", "Cesar")
    assert e.value.status_code == 409
    svc.analyze_case("demo", CASE_ID, MANUAL)
    svc.decide_analysis("demo", CASE_ID, "reject", "Cesar", reason="no aplica")
    with pytest.raises(HTTPException) as e:
        svc.decide_analysis("demo", CASE_ID, "accept", "Cesar")
    assert e.value.status_code == 409


def test_request_changes_regenerates_in_revision_mode(case_env):
    svc.analyze_case("demo", CASE_ID, MANUAL)
    v1 = svc.read_analysis("demo", CASE_ID, version=1)
    out = svc.decide_analysis("demo", CASE_ID, "request_changes", "Cesar",
                              reason="separa la negación en su propia viñeta")
    assert out["new_analysis"]["version"] == 2
    assert out["new_analysis"]["mode"] == "revision"
    v2 = svc.read_analysis("demo", CASE_ID, version=2)
    assert v2["revision"]["mode"] == "revision"
    assert v2["revision"]["based_on_version"] == 1
    assert v2["revision"]["guidance_ledger"] == [
        "separa la negación en su propia viñeta"]
    assert v2["model"]["options"]["temperature"] == review.TEMPERATURE_REVISION
    assert "[RESPUESTA_ANTERIOR INICIO]" in v2["governance"]["prompt_full"]
    # inmutabilidad: v1 conserva prompt/respuesta; solo status+decision anexados
    v1_after = svc.read_analysis("demo", CASE_ID, version=1)
    assert v1_after["status"] == "changes_requested"
    assert v1_after["response"] == v1["response"]
    assert v1_after["governance"]["prompt_full"] == v1["governance"]["prompt_full"]


def test_w71_revision_identical_flags_guidance_unapplied(case_env):
    """[A6/A9] W7.1: el mock devuelve SIEMPRE la misma respuesta → la
    revisión es idéntica a v1 → flag en record + evento y confianza baja;
    el draft v1 no se flaggea (prev_response solo existe en revisión)."""
    svc.analyze_case("demo", CASE_ID, MANUAL)
    svc.decide_analysis("demo", CASE_ID, "request_changes", "Cesar",
                        reason="elimina la viñeta redundante")
    v1 = svc.read_analysis("demo", CASE_ID, version=1)
    assert "guidance_unapplied" not in v1["flags"]
    v2 = svc.read_analysis("demo", CASE_ID, version=2)
    assert "guidance_unapplied" in v2["flags"]
    assert v2["confidence"] == "baja"
    assert any(f["type"] == "guidance_unapplied"
               for f in v2["verifier"]["findings"])
    gen = [e for e in _audit_events(case_env)
           if e["event_type"] == "case_analysis_generated"]
    assert "guidance_unapplied" not in gen[-2]["data"]["flags"]   # draft
    assert "guidance_unapplied" in gen[-1]["data"]["flags"]       # revisión


# ── Fallos gobernados ─────────────────────────────────────────────────────────

def test_format_invalid_archived_and_audited(case_env, monkeypatch):
    monkeypatch.setattr(review, "_ollama_generate",
                        lambda prompt, temperature=0.2:
                        {"response": "texto sin viñetas etiquetadas"})
    out = svc.analyze_case("demo", CASE_ID, MANUAL)
    assert out["status"] == "format_invalid"
    rec = svc.read_analysis("demo", CASE_ID)
    assert rec["status"] == "format_invalid"
    assert rec["governance"]["format_retry"] is True
    failed = [e for e in _audit_events(case_env)
              if e["event_type"] == "case_analysis_failed"]
    assert len(failed) == 1 and failed[0]["data"]["reason"] == "format_invalid"


def test_ollama_down_fails_governed(case_env, monkeypatch):
    def _boom(prompt, temperature=0.2):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(review, "_ollama_generate", _boom)
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("demo", CASE_ID, MANUAL)
    assert e.value.status_code == 503
    failed = [ev for ev in _audit_events(case_env)
              if ev["event_type"] == "case_analysis_failed"]
    assert len(failed) == 1 and failed[0]["data"]["reason"] == "ollama_unreachable"
    assert not (svc_paths.CASE_ANALYSES_BASE / "demo").exists()


def test_prompt_too_long_fails_governed(case_env, monkeypatch):
    monkeypatch.setattr(review, "NUM_CTX", 100)
    with pytest.raises(HTTPException) as e:
        svc.analyze_case("demo", CASE_ID, MANUAL)
    assert e.value.status_code == 413
    failed = [ev for ev in _audit_events(case_env)
              if ev["event_type"] == "case_analysis_failed"]
    assert len(failed) == 1 and failed[0]["data"]["reason"] == "prompt_too_long"


# ── Lectura ───────────────────────────────────────────────────────────────────

def test_read_analysis_never_audits(case_env):
    svc.analyze_case("demo", CASE_ID, MANUAL)
    n = len(_audit_events(case_env))
    svc.read_analysis("demo", CASE_ID)
    svc.read_analysis("demo", CASE_ID, version=1)
    assert len(_audit_events(case_env)) == n
    with pytest.raises(HTTPException) as e:
        svc.read_analysis("demo", STALE_CASE_ID)
    assert e.value.status_code == 404


# ── Estructural ───────────────────────────────────────────────────────────────

def test_structural_no_http_no_approval(case_env):
    """Cero egreso HTTP propio y cero contacto con la aprobación del dossier:
    la única vía LLM es la referencia de módulo a W6.5 (monkeypatcheable)."""
    src = Path(svc.__file__).read_text(encoding="utf-8")
    assert "import httpx" not in src
    assert "approve_document" not in src
    assert "_review._ollama_generate" in src
    assert "requests." not in src
