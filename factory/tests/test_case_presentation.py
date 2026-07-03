"""
W6.4 — Tests de la capa de presentación de la Regulatory Case Memory.

Garantías fijadas:
  - relevancia GMP deriva SOLO de la clasificación FDA (Class I/II/III →
    alta/media/baja; sin clasificación → None aunque haya tags)
  - routing caso→agente determinista: default qa_oos_profile; señales
    analíticas → hplc_data_review_agent; señales DI → integrity_lims_profile
  - found_by_query: persistido en casos nuevos (W6.4+); correlación por
    auditoría para casos previos; ambigüedad → None (nunca se inventa)
  - detail_status cuenta fetches desde la auditoría (light_memory_only /
    detail_fetched_not_persisted); snapshot no soportado
  - cita trazable con case_id, clasificación, fecha, URL, query y hash
  - enriquecer/leer/comparar JAMÁS audita ni modifica cases.jsonl
  - compare: informational_only=True y gmp_decision=False SIEMPRE; cruza
    tags/agentes/pruebas/dossier locales
  - estructural: el módulo no importa httpx ni audit_writer
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import case_presentation_service as svc
from factory.services import paths as svc_paths


def _case(**over):
    base = {
        "case_id": "openfda_enforcement:D-0001-2026",
        "url": 'https://api.fda.gov/drug/enforcement.json?search=recall_number:"D-0001-2026"&limit=1',
        "source_id": "openfda_enforcement",
        "authority": "FDA",
        "consulted_at": "2026-07-03T16:00:00Z",
        "case_type": "drug_recall",
        "classification": "Class II",
        "recall_status": "Ongoing",
        "product": "Sterile Injectable 10mg/mL",
        "reason": "Lack of assurance of sterility",
        "recalling_firm": "Acme Pharma LLC",
        "keywords": ["Class II"],
        "tags": ["sterility"],
        "summary": "Class II · recall D-0001-2026 — Acme Pharma LLC",
        "content_hash": "sha256:abc123",
    }
    base.update(over)
    return base


def _audit_event(event_type, data, ts):
    return json.dumps({"timestamp": ts, "event_type": event_type,
                       "project_id": "regulatory_intel", "data": data})


@pytest.fixture()
def pres_env(tmp_path, monkeypatch):
    monkeypatch.setattr(svc_paths, "CASE_MEMORY_FILE", tmp_path / "cases.jsonl")
    monkeypatch.setattr(svc_paths, "AUDIT_FILE", tmp_path / "audit.jsonl")
    monkeypatch.setattr(svc_paths, "MISSIONS_DIR", tmp_path / "missions")
    monkeypatch.setattr(svc_paths, "DESIGNS_BASE", tmp_path / "designs")
    monkeypatch.setattr(svc_paths, "TEST_CATALOGS_DIR", tmp_path / "catalogs")
    monkeypatch.setattr(svc_paths, "VALIDATION_BASE", tmp_path / "validation")
    return tmp_path


# ── Relevancia GMP ────────────────────────────────────────────────────────────

def test_relevance_derives_only_from_fda_classification(pres_env):
    assert svc._relevance(_case(classification="Class I"))["level"] == "alta"
    assert svc._relevance(_case(classification="Class II"))["level"] == "media"
    assert svc._relevance(_case(classification="Class III"))["level"] == "baja"
    # sin clasificación → None aunque los tags griten OOS: la regla es fija
    r = svc._relevance(_case(classification=None, tags=["oos", "sterility"]))
    assert r["level"] is None
    assert r["derived_from"] == "FDA classification" and r["deterministic"] is True
    assert "NO es juicio GMP" in r["note"]


# ── Routing caso→agente ───────────────────────────────────────────────────────

def test_routing_default_is_qa_oos_profile(pres_env):
    rec = svc._recommend_agent(_case())
    assert rec["agent_id"] == "qa_oos_profile" and rec["deterministic"] is True


def test_routing_analytical_signals_to_hplc_agent(pres_env):
    rec = svc._recommend_agent(_case(
        reason="Assay fail detected by HPLC system suitability testing"))
    assert rec["agent_id"] == "hplc_data_review_agent"


def test_routing_data_integrity_signals_to_integrity_profile(pres_env):
    rec = svc._recommend_agent(_case(
        reason="CGMP deviations: falsified audit trail records in LIMS"))
    assert rec["agent_id"] == "integrity_lims_profile"


# ── found_by_query ────────────────────────────────────────────────────────────

def test_found_by_query_persisted_wins(pres_env):
    c = svc.enrich_case(_case(found_by_query="sterility"))
    assert c["presentation"]["found_by_query"] == "sterility"


def test_found_by_query_correlated_from_audit(pres_env):
    ts = "2026-07-03T16:00:02.100000+00:00"   # 2s después de consulted_at
    svc_paths.AUDIT_FILE.write_text(_audit_event(
        "regulatory_query_executed", {"search_term": "sterility"}, ts) + "\n",
        encoding="utf-8")
    c = svc.enrich_case(_case())
    assert c["presentation"]["found_by_query"] == "sterility"


def test_found_by_query_ambiguous_returns_none(pres_env):
    lines = [
        _audit_event("regulatory_query_executed", {"search_term": "sterility"},
                     "2026-07-03T16:00:30+00:00"),
        _audit_event("regulatory_query_executed", {"search_term": "cgmp"},
                     "2026-07-03T16:02:00+00:00"),
    ]
    svc_paths.AUDIT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    c = svc.enrich_case(_case())
    assert c["presentation"]["found_by_query"] is None      # nunca se inventa
    assert "no registrada" in c["presentation"]["citation"]


# ── Estado del detalle ────────────────────────────────────────────────────────

def test_detail_status_from_audit_fetch_events(pres_env):
    c0 = svc.enrich_case(_case())
    assert c0["presentation"]["detail_status"]["state"] == "light_memory_only"
    lines = [_audit_event("case_detail_fetched",
                          {"case_id": "openfda_enforcement:D-0001-2026"},
                          f"2026-07-03T16:1{i}:00+00:00") for i in range(2)]
    svc_paths.AUDIT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ds = svc.enrich_case(_case())["presentation"]["detail_status"]
    assert ds["state"] == "detail_fetched_not_persisted" and ds["fetch_count"] == 2
    assert ds["last_fetched_at"] == "2026-07-03T16:11:00+00:00"
    assert ds["snapshot"]["supported"] is False


# ── Cita trazable ─────────────────────────────────────────────────────────────

def test_citation_is_traceable(pres_env):
    cit = svc.enrich_case(_case(found_by_query="sterility"))["presentation"]["citation"]
    for fragment in ("openfda_enforcement:D-0001-2026", "Class II",
                     "2026-07-03T16:00:00Z", "api.fda.gov/drug/enforcement.json",
                     "«sterility»", "sha256:abc123"):
        assert fragment in cit


# ── Lectura y garantía read-only ──────────────────────────────────────────────

def test_read_case_by_id_and_unknown(pres_env):
    svc_paths.CASE_MEMORY_FILE.write_text(
        json.dumps(_case()) + "\n", encoding="utf-8")
    c = svc.read_case("openfda_enforcement:D-0001-2026")
    assert c and c["presentation"]["executive_summary"].startswith("Acme Pharma")
    assert svc.read_case("openfda_enforcement:NOPE") is None


def test_enrich_never_writes_memory_nor_audit(pres_env):
    svc_paths.CASE_MEMORY_FILE.write_text(
        json.dumps(_case()) + "\n", encoding="utf-8")
    svc_paths.AUDIT_FILE.write_text(_audit_event(
        "regulatory_query_executed", {"search_term": "sterility"},
        "2026-07-03T16:00:02+00:00") + "\n", encoding="utf-8")
    mem_before = svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8")
    aud_before = svc_paths.AUDIT_FILE.read_text(encoding="utf-8")
    svc.read_case("openfda_enforcement:D-0001-2026")
    svc.enrich_cases([_case()])
    assert svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8") == mem_before
    assert svc_paths.AUDIT_FILE.read_text(encoding="utf-8") == aud_before


# ── Conector W6.3: casos nuevos persisten la query de origen ──────────────────

def test_connector_persists_found_by_query(pres_env, monkeypatch, isolated_audit):
    from factory.services import regulatory_connector_service as conn
    monkeypatch.setattr(svc_paths, "CONNECTOR_STATE_FILE", pres_env / "state.json")
    monkeypatch.setattr(svc_paths, "AUDIT_FILE", isolated_audit)
    monkeypatch.setattr(conn, "MIN_INTERVAL_S", 0)

    class FakeResp:
        status_code = 200
        def json(self):
            return {"results": [{"recall_number": "D-0002-2026",
                                 "classification": "Class I",
                                 "reason_for_recall": "sterility failure"}]}
    monkeypatch.setattr(conn, "_http_get", lambda p: FakeResp())
    out = conn.query_recalls("sterility", 5, "Cesar")
    assert out["cases"][0]["found_by_query"] == "sterility"
    saved = json.loads(svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8"))
    assert saved["found_by_query"] == "sterility"


# ── Comparación informativa con misión ────────────────────────────────────────

@pytest.fixture()
def mission_env(pres_env):
    svc_paths.CASE_MEMORY_FILE.write_text(
        json.dumps(_case(tags=["sterility", "oos"])) + "\n", encoding="utf-8")
    (pres_env / "missions").mkdir()
    (pres_env / "missions" / "demo_mission.yaml").write_text(
        "project_id: demo_mission\nclient_type: pharma\n"
        "objective: Investigación OOS para HPLC en laboratorio QC\n"
        "regulatory_scope: [21_CFR_211_192, ALCOA_PLUS]\n", encoding="utf-8")
    (pres_env / "designs" / "demo_mission").mkdir(parents=True)
    (pres_env / "designs" / "demo_mission" / "agent_design_proposal.yaml").write_text(
        "- agent_id: qa_oos_profile\n- agent_id: hplc_data_review_agent\n",
        encoding="utf-8")
    (pres_env / "catalogs").mkdir()
    (pres_env / "catalogs" / "demo_mission.yaml").write_text(
        "agents:\n  - agent_id: qa_oos_profile\n    tests: [{test_id: t1}, {test_id: t2}]\n",
        encoding="utf-8")
    (pres_env / "validation" / "demo_mission").mkdir(parents=True)
    # formato real W6.2: documents es dict doc_id → {status, ...}
    (pres_env / "validation" / "demo_mission" / "dossier.yaml").write_text(
        "documents:\n  urs: {status: approved}\n"
        "  frs: {status: needs_human_review}\n", encoding="utf-8")
    return pres_env


def test_compare_is_informational_and_crosses_local_facts(mission_env):
    out = svc.compare_with_mission("openfda_enforcement:D-0001-2026", "demo_mission")
    assert out["informational_only"] is True and out["gmp_decision"] is False
    assert out["overlap"]["matched_tags"] == ["oos"]          # "oos" está en el objetivo
    assert "sterility" in out["overlap"]["unmatched_tags"]
    assert out["overlap"]["recommended_agent_in_mission"] is True
    assert out["overlap"]["recommended_agent_tests"] == 2
    assert out["mission"]["dossier"] == {"exists": True, "total_docs": 2, "approved": 1}
    assert out["mission"]["agents"] == ["qa_oos_profile", "hplc_data_review_agent"]


def test_compare_unknown_case_or_mission(mission_env):
    assert svc.compare_with_mission("openfda_enforcement:NOPE", "demo_mission") is None
    out = svc.compare_with_mission("openfda_enforcement:D-0001-2026", "no_mission")
    assert out["error"] == "mission_not_found"


def test_compare_never_audits_nor_writes(mission_env):
    svc_paths.AUDIT_FILE.write_text("", encoding="utf-8")
    before = svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8")
    svc.compare_with_mission("openfda_enforcement:D-0001-2026", "demo_mission")
    assert svc_paths.AUDIT_FILE.read_text(encoding="utf-8") == ""
    assert svc_paths.CASE_MEMORY_FILE.read_text(encoding="utf-8") == before


# ── Estructural: read-only por construcción ───────────────────────────────────

def test_module_never_talks_outbound_or_audits():
    import ast
    tree = ast.parse(Path(svc.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(a.name for a in node.names)
    assert not any("httpx" in name for name in imported)
    assert not any("audit_writer" in name for name in imported)
