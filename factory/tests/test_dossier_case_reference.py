"""
W9 Bloque 2 (Opción A) — Tests de la citación del dossier a análisis de
casos aceptados por ID + versión.

Garantías fijadas (contrato aprobado por Cesar, W8_GROUNDING_PLAN.md
§Bloque 2):
  - solo se referencian análisis en status == "accepted" (422 si no)
  - la referencia trae los 8 campos mínimos exigidos: case_id,
    analysis_version, mission_id, status, puntero+hash, fecha, decisión
    humana, evento de auditoría relacionado
  - JAMÁS copia el texto del análisis (no hay campo `response`/`prompt`)
  - JAMÁS toca content_sha256/status/approved_by del documento citado
  - idempotente: mismo (case_id, version) dos veces en el mismo doc → 409
  - doc inexistente → 404; doc no generado → 409
  - 1 evento de auditoría propio; el evento case_analysis_decision original
    queda byte-idéntico (no se reescribe ni se copia su contenido)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import case_analysis_service as case_svc
from factory.services import dossier_case_reference_service as svc
from factory.services import dossier_generator_service as dossier_svc
from factory.services import dossier_agent_review_service as review
from factory.services import paths as svc_paths

CASE_ID = "openfda_enforcement:REF-001"
DOC_ID = "data_integrity_assessment"

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


@pytest.fixture()
def ref_env(tmp_path, monkeypatch, isolated_audit):
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

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases_file = tmp_path / "cases.jsonl"
    cases_file.write_text(json.dumps({
        "case_id": CASE_ID, "source_id": "openfda_enforcement", "authority": "FDA",
        "case_type": "drug_recall", "classification": "Class II", "recall_status": "Ongoing",
        "product": "Producto Inyectable USP 5 mL", "reason": "Lack of Assurance of Sterility",
        "recalling_firm": "Firma Test LLC", "recall_initiation_date": "20260512",
        "report_date": "20260610", "consulted_at": now, "last_checked": now,
        "keywords": ["Class II"], "tags": ["sterility"],
        "summary": "Class II · Lack of Assurance of Sterility",
        "content_hash": "sha256:feedcafe", "embedding_ref": None,
        "url": "https://api.fda.gov/drug/enforcement.json?search=x",
        "freshness": {"stale_after_days": 30}, "relevance": None,
    }) + "\n", encoding="utf-8")

    validation_base = tmp_path / "validation"
    validation_base.mkdir()

    for name, val in [("MISSIONS_DIR", missions), ("DESIGNS_BASE", designs),
                      ("PROFILES_DIR", profiles),
                      ("CASE_MEMORY_FILE", cases_file),
                      ("AUDIT_FILE", isolated_audit),
                      ("TEST_CATALOGS_DIR", tmp_path / "catalogs"),
                      ("VALIDATION_BASE", validation_base),
                      ("CASE_ANALYSES_BASE", tmp_path / "case_analyses")]:
        monkeypatch.setattr(svc_paths, name, val)

    monkeypatch.setattr(review, "_ollama_generate",
                        lambda prompt, temperature=0.2: {"response": GOOD_CASE_RESPONSE})

    # dossier.yaml con 1 documento ya "generado" (needs_human_review) — no se
    # invoca el generador completo, basta con el esqueleto mínimo que
    # link_case_reference necesita: documents[doc_id] existente.
    (validation_base / "demo").mkdir()
    (validation_base / "demo" / "documents").mkdir()
    (validation_base / "demo" / "documents" / f"{DOC_ID}.md").write_text(
        "# Data Integrity Assessment\n\nSIN EVIDENCIA — requiere aporte humano\n",
        encoding="utf-8")
    (validation_base / "demo" / "dossier.yaml").write_text(
        f"meta: {{version: 1}}\n"
        f"documents:\n"
        f"  {DOC_ID}:\n"
        f"    status: needs_human_review\n"
        f"    content_sha256: abc123\n"
        f"    generated_at: '{now}'\n"
        f"    generated_by: Cesar\n"
        f"    missing: []\n"
        f"    evidence_sources: []\n", encoding="utf-8")

    return tmp_path


def _generate_and_accept(env, version_guidance=None):
    """Genera un draft v1 y lo acepta; devuelve el resultado de accept."""
    case_svc.analyze_case("demo", CASE_ID,
                          {"mode": "manual", "principal": "Cesar", "authorization_ref": None})
    return case_svc.decide_analysis("demo", CASE_ID, "accept", "Cesar")


def _audit_events(env):
    f = env / "factory_audit_test.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_link_requires_accepted_status(ref_env):
    case_svc.analyze_case("demo", CASE_ID,
                          {"mode": "manual", "principal": "Cesar", "authorization_ref": None})
    with pytest.raises(HTTPException) as exc:
        svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    assert exc.value.status_code == 422


def test_link_success_has_all_required_fields(ref_env):
    _generate_and_accept(ref_env)
    out = svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    refs = out["case_references"]
    assert len(refs) == 1
    r = refs[0]
    for field in ("case_id", "analysis_version", "mission_id", "status",
                  "analysis_pointer", "analysis_sha256", "decided_at",
                  "decided_by", "decision", "audit_event_hash",
                  "audit_event_timestamp", "linked_at", "linked_by"):
        assert field in r, f"falta campo requerido: {field}"
    assert r["case_id"] == CASE_ID
    assert r["analysis_version"] == 1
    assert r["mission_id"] == "demo"
    assert r["status"] == "accepted"
    assert r["decision"] == "accept"
    assert r["decided_by"] == "Cesar"
    assert r["linked_by"] == "Cesar"
    assert r["audit_event_hash"].startswith("sha256:")
    # nunca copia texto del análisis
    assert "response" not in r and "prompt" not in r and "prompt_full" not in r


def test_link_analysis_sha256_matches_real_file(ref_env):
    _generate_and_accept(ref_env)
    out = svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    r = out["case_references"][0]
    analysis_file = case_svc._analysis_path("demo", CASE_ID, 1)
    import hashlib
    assert r["analysis_sha256"] == hashlib.sha256(analysis_file.read_bytes()).hexdigest()
    assert r["analysis_pointer"].endswith("v01.json")


def test_link_duplicate_is_conflict(ref_env):
    _generate_and_accept(ref_env)
    svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    with pytest.raises(HTTPException) as exc:
        svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    assert exc.value.status_code == 409


def test_link_unknown_doc_404(ref_env):
    _generate_and_accept(ref_env)
    with pytest.raises(HTTPException) as exc:
        svc.link_case_reference("demo", "no_existe", CASE_ID, 1, "Cesar")
    assert exc.value.status_code == 404


def test_link_doc_not_generated_409(ref_env):
    _generate_and_accept(ref_env)
    with pytest.raises(HTTPException) as exc:
        svc.link_case_reference("demo", "iq", CASE_ID, 1, "Cesar")  # válido pero no generado
    assert exc.value.status_code == 409


def test_link_reserved_name_422(ref_env):
    _generate_and_accept(ref_env)
    with pytest.raises(HTTPException) as exc:
        svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "human")
    assert exc.value.status_code == 422


def test_link_never_touches_document_approval_fields(ref_env):
    _generate_and_accept(ref_env)
    before = dossier_svc._load_dossier("demo")["documents"][DOC_ID].copy()
    svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    after = dossier_svc._load_dossier("demo")["documents"][DOC_ID]
    assert after["status"] == before["status"]
    assert after["content_sha256"] == before["content_sha256"]
    assert "approved_by" not in after


def test_link_audits_exactly_one_event_without_rewriting_decision(ref_env):
    _generate_and_accept(ref_env)
    events_before = _audit_events(ref_env)
    decision_line_before = json.dumps(
        next(e for e in events_before if e["event_type"] == "case_analysis_decision"),
        sort_keys=True)

    svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")

    events_after = _audit_events(ref_env)
    link_events = [e for e in events_after if e["event_type"] == "dossier_case_reference_linked"]
    assert len(link_events) == 1
    assert link_events[0]["data"]["case_id"] == CASE_ID
    assert link_events[0]["data"]["doc_id"] == DOC_ID

    decision_line_after = json.dumps(
        next(e for e in events_after if e["event_type"] == "case_analysis_decision"),
        sort_keys=True)
    assert decision_line_after == decision_line_before  # byte-idéntico, nunca reescrito


def test_read_document_surfaces_case_references(ref_env):
    _generate_and_accept(ref_env)
    svc.link_case_reference("demo", DOC_ID, CASE_ID, 1, "Cesar")
    doc = dossier_svc.read_document("demo", DOC_ID)
    assert len(doc["meta"]["case_references"]) == 1
    assert doc["meta"]["case_references"][0]["case_id"] == CASE_ID
