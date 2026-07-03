"""
W6.2 — Tests del generador del dossier CSV/GAMP 5.

Garantías fijadas:
  - la generación NUNCA produce estado approved
  - clasificación por clase: facts→draft, judgment→needs_human_review,
    evidencia requerida ausente→missing_evidence (con lista `missing`)
  - anti-invención: todo doc lleva el encabezado "sin valor regulatorio";
    secciones sin dato dicen SIN EVIDENCIA
  - un doc approved no se sobrescribe si su contenido no cambió; si la
    evidencia subyacente cambia, la aprobación se invalida explícitamente
  - approve: solo humano real (nombres reservados 422), doc no generado 409,
    missing_evidence 422, doble aprobación 409
  - auditoría: exactamente 1 evento por generate y 1 por approve;
    read_document no audita
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import dossier_generator_service as svc
from factory.services import paths as svc_paths
from factory.services import validation_readiness_service as vr


@pytest.fixture()
def dossier_env(tmp_path, monkeypatch, isolated_audit):
    """Misión con evidencia parcial realista + rutas a tmp + auditoría aislada."""
    missions = tmp_path / "missions"; missions.mkdir()
    (missions / "demo.yaml").write_text(
        "status: approved\n"
        "objective: Investigar OOS de HPLC con trazabilidad ALCOA+\n"
        "client_type: pharma_qc_lab\n"
        "regulatory_scope: [21_CFR_PART_11, ALCOA_PLUS]\n"
        "constraints: [Sin datos reales de pacientes, Aprobación humana requerida]\n"
        "documents: {ICH_Q10: PENDING}\n"
        "history: [{event: approved, by: Cesar}]\n", encoding="utf-8")

    designs = tmp_path / "designs"; (designs / "demo").mkdir(parents=True)
    (designs / "demo" / "agent_design_proposal.yaml").write_text(
        "agents:\n"
        "  - {agent_id: qa_oos_profile, decision: profile, base_agent: qa,\n"
        "     rationale: OOS cabe en QA, routing_key: oos}\n", encoding="utf-8")

    catalogs = tmp_path / "catalogs"; catalogs.mkdir()
    (catalogs / "demo.yaml").write_text(
        "agents:\n"
        "  - agent_id: qa_oos_profile\n"
        "    tests:\n"
        "      - {test_id: T1, endpoint: 'POST /api/v1/query'}\n", encoding="utf-8")

    results = tmp_path / "test_results"; results.mkdir()
    (results / "demo.jsonl").write_text(
        json.dumps({"test_id": "T1", "result": "PASS", "run_by": "Cesar"}) + "\n",
        encoding="utf-8")

    for name, val in [("MISSIONS_DIR", missions), ("DESIGNS_BASE", designs),
                      ("TEST_CATALOGS_DIR", catalogs), ("TEST_RESULTS_DIR", results),
                      ("RC_BASE", tmp_path / "rcs"), ("WS_BASE", tmp_path / "ws"),
                      ("DEP_BASE", tmp_path / "deps"),
                      ("VALIDATION_BASE", tmp_path / "validation"),
                      ("AUDIT_FILE", isolated_audit)]:
        monkeypatch.setattr(svc_paths, name, val)

    # build_mission_summary construye rutas desde FACTORY_ROOT (no parchea
    # MISSIONS_DIR): se sustituye por un resumen fixture coherente con el tmp.
    from factory.services import mission_evidence_service as _ev

    def fake_summary(pid):
        return {
            "project_id": pid,
            "mission": {"status": "approved", "approved_by": "Cesar"},
            "design": {"files": [], "agents_summary":
                       {"agent_ids": ["qa_oos_profile"], "profiles_inherited": 1, "new_agents": 0}},
            "workspace": {"files_visible": 0},
            "tests": None,
            "rcs": {"count": 0, "canonical": None},
            "deployment": {"exists": False, "api_port": None, "health_ok": False},
            "audit": {"event_count_filtered": 0},
        }
    monkeypatch.setattr(_ev, "build_mission_summary", fake_summary)
    return tmp_path


def _audit_lines(audit_file):
    if not audit_file.exists():
        return []
    return [json.loads(l) for l in audit_file.read_text(encoding="utf-8").splitlines() if l.strip()]


# ── Generación ────────────────────────────────────────────────────────────────

def test_generate_never_approves(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    out = vr.read_validation_package("demo")
    assert out["counts"]["approved"] == 0
    assert out["counts"]["not_started"] == 0     # los 22 generados


def test_generate_classifies_by_kind(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    by_id = {d["doc_id"]: d for d in vr.read_validation_package("demo")["documents"]}
    assert by_id["urs"]["status"] == "draft"                    # facts con evidencia
    assert by_id["traceability_matrix"]["status"] == "draft"
    assert by_id["intended_use"]["status"] == "needs_human_review"   # judgment
    # estrategia de pruebas = justificación riesgo-basada → siempre juicio QA
    assert by_id["test_strategy"]["status"] == "needs_human_review"
    assert by_id["pq"]["status"] == "missing_evidence"          # sin fuente posible
    assert by_id["periodic_review"]["status"] == "missing_evidence"
    # deployment no existe en el fixture → docs que lo requieren caen a missing
    assert by_id["iq"]["status"] == "missing_evidence"
    assert "deployment" in by_id["iq"]["missing"]


def test_generated_content_honest(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    doc = svc.read_document("demo", "intended_use")
    assert "sin valor regulatorio" in doc["content"]
    assert "Investigar OOS de HPLC" in doc["content"]           # evidencia real
    assert svc.SIN_EVIDENCIA in doc["content"]                  # juicio pendiente
    assert "*Fuente: " in doc["content"]                        # pointers
    matrix = svc.read_document("demo", "traceability_matrix")["content"]
    assert "qa_oos_profile" in matrix and "T1" in matrix and "PASS" in matrix
    assert "URS-01" in matrix and "Cesar" in matrix             # atribución del operador
    urs = svc.read_document("demo", "urs")["content"]
    assert "URS-01" in urs
    assert "URS-02" not in urs      # constraints NO se numeran como URS (pueden
    #                                 ser acciones de pipeline, no requisitos)
    frs = svc.read_document("demo", "frs")["content"]
    assert "FRS-01" in frs and "POST /api/v1/query" in frs      # matriz FRS del catálogo


def test_generate_requires_real_name(dossier_env):
    with pytest.raises(HTTPException) as e:
        svc.generate_dossier("demo", "human")
    assert e.value.status_code == 422


def test_generate_audits_exactly_one_event(dossier_env, isolated_audit):
    svc.generate_dossier("demo", "Cesar")
    events = _audit_lines(isolated_audit)
    gen = [e for e in events if e.get("event_type") == "validation_dossier_generated"]
    assert len(gen) == 1
    assert gen[0]["data"]["generated_by"] == "Cesar"


# ── Aprobación humana ─────────────────────────────────────────────────────────

def test_approve_flow_and_guards(dossier_env, isolated_audit):
    with pytest.raises(HTTPException) as e:      # no generado aún
        svc.approve_document("demo", "urs", "Cesar")
    assert e.value.status_code == 409

    svc.generate_dossier("demo", "Cesar")
    with pytest.raises(HTTPException) as e:      # nombre reservado
        svc.approve_document("demo", "urs", "admin")
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:      # missing_evidence no aprobable
        svc.approve_document("demo", "pq", "Cesar")
    assert e.value.status_code == 422

    out = svc.approve_document("demo", "urs", "Cesar")
    assert out["status"] == "approved"
    with pytest.raises(HTTPException) as e:      # doble aprobación
        svc.approve_document("demo", "urs", "Cesar")
    assert e.value.status_code == 409

    approvals = [e for e in _audit_lines(isolated_audit)
                 if e.get("event_type") == "validation_doc_approved"]
    assert len(approvals) == 1 and approvals[0]["data"]["doc_id"] == "urs"


def test_approved_doc_survives_regeneration_if_unchanged(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    svc.approve_document("demo", "traceability_matrix", "Cesar")
    out = svc.generate_dossier("demo", "Cesar")
    assert "traceability_matrix" in out["skipped_approved"]
    by_id = {d["doc_id"]: d for d in vr.read_validation_package("demo")["documents"]}
    assert by_id["traceability_matrix"]["status"] == "approved"


def test_approved_doc_invalidated_when_evidence_changes(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    svc.approve_document("demo", "oq", "Cesar")
    # nueva evidencia: se registra otra ejecución funcional
    results = svc_paths.TEST_RESULTS_DIR / "demo.jsonl"
    results.write_text(results.read_text(encoding="utf-8")
                       + json.dumps({"test_id": "T1", "result": "FAIL", "run_by": "Cesar"}) + "\n",
                       encoding="utf-8")
    out = svc.generate_dossier("demo", "Cesar")
    assert "oq" in out["invalidated"]
    dossier = svc._load_dossier("demo")
    entry = dossier["documents"]["oq"]
    assert entry["status"] == "needs_human_review"
    assert entry["invalidated_approval"]["approved_by"] == "Cesar"


# ── Lectura ───────────────────────────────────────────────────────────────────

def test_read_document_never_audits(dossier_env, isolated_audit):
    svc.generate_dossier("demo", "Cesar")
    before = len(_audit_lines(isolated_audit))
    svc.read_document("demo", "urs")
    assert len(_audit_lines(isolated_audit)) == before


def test_read_document_404s(dossier_env):
    svc.generate_dossier("demo", "Cesar")
    with pytest.raises(HTTPException) as e:
        svc.read_document("demo", "doc_inventado")
    assert e.value.status_code == 404
