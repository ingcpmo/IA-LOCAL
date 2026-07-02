"""
W4.1.1 — Tests del compositor de PDF robusto (18 secciones).

Prueba compose_robust_report() a nivel de unidad (payload construido a mano,
igual de forma que lo entrega _build_gmp_report) y helpers de deduplicación /
trazabilidad. No depende del deployment Docker.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import factory.api.routes.layer9 as layer9
import factory.core.pdf_report_robust as pdf_robust
import factory.layer9.mission_control as mission_control
import factory.core.port_registry as port_registry

PROJECT = "test_pdf_robust_proj"
GMP_SECRET = "gmp-super-secret-robust-key-0001"

_SECTION_TITLES = [
    "Informe de Evaluacion Funcional GMP",  # Sección 1 — Portada
    "Resumen ejecutivo",
    "Introduccion de la mision",
    "Objetivo detallado de la mision creada",
    "Trazabilidad objetivo-agente-evidencia",
    "Caso farmaceutico planteado",
    "Objetivos funcionales de la mision",
    "Agentes creados o reutilizados",
    "Resultados de pruebas funcionales por agente",
    "Interpretacion por agente",
    "Funcionamiento operativo esperado",
    "Flujo operativo propuesto",
    "Reglas Python vs Ollama local",
    "Auditoria y trazabilidad",
    "Limitaciones",
    "Pendientes antes de go-live",
    "Impacto operativo esperado",
    "Conclusion",
    "Anexo tecnico",
]


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _text(pdf_bytes: bytes) -> str:
    """Con pdf.compress=False el contenido queda legible en claro dentro del
    stream; decodificar como latin1 alcanza para buscar subcadenas, igual que
    `strings` sobre el archivo (evidencia GMP del plan)."""
    return pdf_bytes.decode("latin1", errors="replace")


def _minimal_payload(project_id=PROJECT) -> dict:
    return {
        "meta": {
            "project_id": project_id, "client_type": "no_disponible",
            "canonical_rc": "no_disponible", "generated_at": "2026-07-01T00:00:00+00:00",
            "deployment_status": "no_desplegado",
        },
        "executive_summary": "No se han ejecutado pruebas funcionales aun para esta mision.",
        "mission_objective": {"task_summary": "no_disponible"},
        "pharma_case": "no_disponible",
        "agents_evaluated": {"total": 0},
        "results_by_agent": [],
        "rules_vs_llm": {},
        "audit_traceability": {},
        "operational_impact": "Estimacion 30%-60% (ESTIMACION, no medicion).",
        "limitations": [],
        "pending_before_golive": [],
        "conclusion": (
            "Sin datos aun. Estos agentes funcionan como apoyo a QA/QC y no "
            "reemplazan la decision humana ni liberan lotes automaticamente."
        ),
    }


def _result(test_id, run_at, result="PASS", **extra):
    return {
        "test_id": test_id, "title": f"titulo {test_id}", "endpoint": "POST /api/v1/x",
        "result": result, "run_by": "Tester", "run_at": run_at,
        "relevant_datum": "no disponible", "uses_llm": False, "llm_evidence": None,
        **extra,
    }


# ── compose_robust_report: forma básica ─────────────────────────────────────

def test_compose_robust_report_returns_nonempty_pdf_bytes():
    b = pdf_robust.compose_robust_report(_minimal_payload(), "sin_diseno_inexistente")
    assert isinstance(b, bytes)
    assert len(b) > 0
    assert b[:4] == b"%PDF"


def test_compose_robust_report_contains_all_18_section_titles():
    payload = _minimal_payload()
    b = pdf_robust.compose_robust_report(payload, "sin_diseno_inexistente")
    text = _strip_accents(_text(b)).lower()
    faltantes = [t for t in _SECTION_TITLES if _strip_accents(t).lower() not in text]
    assert not faltantes, f"Faltan titulos de seccion en el PDF: {faltantes}"


def test_compose_robust_report_missing_requirement_spec_shows_no_disponible():
    # Proyecto sin carpeta de diseño: sección 4/5 no deben inventar contenido.
    payload = _minimal_payload()
    b = pdf_robust.compose_robust_report(payload, "proyecto_sin_design_dir")
    text = _text(b)
    assert "no disponible" in text.lower()
    assert "ejemplo" not in text.lower()


# ── dedupe_last_by_test_id ───────────────────────────────────────────────────

def test_dedupe_last_by_test_id_keeps_only_latest_run_per_test_id_in_body():
    results_by_agent = [{
        "agent_id": "agent_a",
        "uses_llm": False,
        "tests": [
            _result("oos_create_out_of_spec", "2026-01-01T00:00:00+00:00", result="FAIL"),
            _result("oos_create_out_of_spec", "2026-01-03T00:00:00+00:00", result="PASS"),
            _result("oos_create_out_of_spec", "2026-01-02T00:00:00+00:00", result="FAIL"),
            _result("oos_create_in_spec", "2026-01-01T00:00:00+00:00", result="PASS"),
        ],
    }]
    body, appendix = pdf_robust.dedupe_last_by_test_id(results_by_agent)

    assert len(body) == 1
    body_tests = body[0]["tests"]
    assert len(body_tests) == 2  # 1 fila por test_id
    latest = next(t for t in body_tests if t["test_id"] == "oos_create_out_of_spec")
    assert latest["run_at"] == "2026-01-03T00:00:00+00:00"
    assert latest["result"] == "PASS"

    # El anexo conserva las N ejecuciones originales, sin tocar.
    assert appendix is results_by_agent
    assert len(appendix[0]["tests"]) == 4


def test_compose_robust_report_body_dedupes_appendix_keeps_all_runs():
    # test_id corto: en la tabla del anexo (columnas angostas) un test_id
    # largo puede envolverse en varias líneas/Tj y dejar de aparecer como
    # subcadena contigua en el stream — no es un fallo del compositor, es
    # una limitación de contar substrings sobre texto envuelto en celda.
    payload = _minimal_payload()
    payload["results_by_agent"] = [{
        "agent_id": "agent_a",
        "uses_llm": False,
        "tests": [
            _result("t_oos1", "2026-01-01T00:00:00+00:00", result="FAIL"),
            _result("t_oos1", "2026-01-03T00:00:00+00:00", result="PASS"),
            _result("t_oos1", "2026-01-02T00:00:00+00:00", result="FAIL"),
        ],
    }]
    b = pdf_robust.compose_robust_report(payload, "sin_diseno_inexistente")
    text = _text(b)
    # El test_id aparece: 1 vez en cuerpo (Seccion 8, dedupe) + 3 veces en anexo (Seccion 18, sin dedupe).
    assert text.count("t_oos1") >= 4


# ── Sección 12 — Reglas Python vs Ollama ────────────────────────────────────

def test_section_12_without_used_llm_uses_explanatory_text_not_no_disponible():
    payload = _minimal_payload()
    payload["results_by_agent"] = [{
        "agent_id": "agent_a", "uses_llm": False,
        "tests": [_result("oos_create_out_of_spec", "2026-01-01T00:00:00+00:00", uses_llm=False)],
    }]
    b = pdf_robust.compose_robust_report(payload, "sin_diseno_inexistente")
    text = _text(b).lower()
    assert "no atribuye resultados funcionales al llm" in text


def test_section_12_with_used_llm_shows_model_and_elapsed_seconds():
    payload = _minimal_payload()
    payload["results_by_agent"] = [{
        "agent_id": "agent_a", "uses_llm": True,
        "tests": [_result(
            "hplc_review_llm", "2026-01-01T00:00:00+00:00",
            uses_llm=True,
            llm_evidence={"model": "llama3.2:latest", "elapsed_seconds": 1.23, "ollama_status": "ok"},
        )],
    }]
    b = pdf_robust.compose_robust_report(payload, "sin_diseno_inexistente")
    text = _text(b)
    assert "llama3.2:latest" in text
    assert "1.23" in text


# ── sanitización de secretos ─────────────────────────────────────────────────
# compose_robust_report() por sí solo solo redacta por patrón/nombre de clave
# (capa defensiva); el valor real de un secreto se enmascara aguas arriba, en
# _build_gmp_report() -> sanitize_for_report(secret_values=[...]) (W4.1). Por
# eso esta prueba pasa por el endpoint completo, como
# test_gmp_report_pdf_does_not_contain_gmp_api_key en test_gmp_report.py.

def test_compose_robust_report_redacts_known_secret_key_names():
    payload = _minimal_payload()
    payload["GMP_API_KEY"] = "cualquier-valor-secreto"
    b = pdf_robust.compose_robust_report(payload, "sin_diseno_inexistente")
    assert b"cualquier-valor-secreto" not in b


def test_compose_robust_report_conclusion_has_mandatory_no_replace_clause():
    b = pdf_robust.compose_robust_report(_minimal_payload(), "sin_diseno_inexistente")
    text = _text(b).lower()
    assert "no reemplazan la decision" in text or "no reemplaza la decision" in text


# ── integración end-to-end vía el endpoint (evidencia real de diseño) ───────

def _write_mission(missions_dir: Path, project_id: str) -> None:
    mission = {
        "project_id": project_id, "status": "approved", "client_type": "test_client",
        "objective": "Objetivo de prueba.", "regulatory_scope": ["TEST_SCOPE"],
        "created_at": "2026-01-01T00:00:00+00:00", "approved_at": "2026-01-02T00:00:00+00:00",
        "history": [{"event": "approved", "by": "TestApprover", "at": "2026-01-02T00:00:00+00:00"}],
    }
    missions_dir.mkdir(parents=True, exist_ok=True)
    (missions_dir / f"{project_id}.yaml").write_text(yaml.dump(mission), encoding="utf-8")


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self._json_body = json_body

    def json(self):
        return self._json_body


@pytest.fixture()
def robust_pdf_env(tmp_path, monkeypatch, isolated_audit):
    root = tmp_path / "factory_root"
    missions_dir = root / "layer9" / "missions"
    designs_dir = root / "designs"
    rc_dir = root / "release_candidates"
    dep_dir = root / "deployments"
    ws_dir = root / "workspaces"
    catalogs_dir = root / "test_catalogs"
    results_dir = root / "test_results"
    for d in (missions_dir, designs_dir, rc_dir, dep_dir, ws_dir, catalogs_dir):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(layer9, "_FACTORY_ROOT", root)
    monkeypatch.setattr(layer9, "_DESIGNS_BASE", designs_dir)
    monkeypatch.setattr(layer9, "_RC_BASE_W3", rc_dir)
    monkeypatch.setattr(layer9, "_DEP_BASE", dep_dir)
    monkeypatch.setattr(layer9, "_WS_BASE_W3", ws_dir)
    monkeypatch.setattr(layer9, "_AUDIT_FILE", isolated_audit)
    monkeypatch.setattr(layer9, "_TEST_CATALOGS_DIR", catalogs_dir)
    monkeypatch.setattr(layer9, "_TEST_RESULTS_DIR", results_dir)
    monkeypatch.setattr(mission_control, "MISSIONS_DIR", missions_dir)
    monkeypatch.setattr(pdf_robust, "_DESIGNS_BASE", designs_dir)

    monkeypatch.setattr(
        port_registry, "get_allocated_ports",
        lambda pid: {"api": 9999} if pid == PROJECT else None,
    )
    monkeypatch.setattr(layer9.httpx, "get", lambda *a, **k: _FakeResponse(200, {"api": "ok"}))

    _write_mission(missions_dir, PROJECT)
    return {
        "missions_dir": missions_dir, "designs_dir": designs_dir, "rc_dir": rc_dir,
        "dep_dir": dep_dir, "ws_dir": ws_dir, "catalogs_dir": catalogs_dir,
        "results_dir": results_dir, "audit_file": isolated_audit,
    }


def _write_full_evidence(env: dict) -> None:
    design_dir = env["designs_dir"] / PROJECT
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "requirement_spec.yaml").write_text(yaml.dump({
        "raw_objective": "Caso farmacéutico de prueba OOS/HPLC.",
        "domains": ["OOS", "HPLC"],
        "client_needs": ["necesidad 1"],
    }), encoding="utf-8")
    (design_dir / "agent_design_proposal.yaml").write_text(yaml.dump({
        "project_id": PROJECT,
        "agents": [
            {"agent_id": "qa_oos_profile", "decision": "profile", "base_agent": "base",
             "rationale": "detecta OOS", "routing_key": "oos"},
            {"agent_id": "hplc_data_review_agent", "decision": "new_agent", "base_agent": None,
             "rationale": "revisa HPLC/SST/RSD", "routing_key": "hplc"},
        ],
    }), encoding="utf-8")
    (design_dir / "pending_documents.yaml").write_text(yaml.dump({
        "documents": [{"id": "DOC1", "title": "Guia pendiente", "status": "PENDING_DOCUMENT"}],
    }), encoding="utf-8")

    catalog = {
        "project_id": PROJECT, "catalog_version": "1.0",
        "agents": [{
            "agent_id": "qa_oos_profile",
            "tests": [{
                "test_id": "oos_create_out_of_spec", "title": "Detecta OOS",
                "endpoint": "POST /api/v1/oos", "payload": {}, "expect": {},
            }],
        }],
    }
    (env["catalogs_dir"] / f"{PROJECT}.yaml").write_text(yaml.dump(catalog), encoding="utf-8")

    env["results_dir"].mkdir(parents=True, exist_ok=True)
    records = [
        {
            "test_id": "oos_create_out_of_spec", "endpoint": "POST /api/v1/oos", "payload": {},
            "response_status": 200, "response_excerpt": "{}",
            "assertion": {"received_value": "OOS"}, "result": "FAIL", "detail": None, "latency_ms": 3.0,
            "agent_id": "qa_oos_profile", "run_by": "Tester", "run_at": "2026-01-03T00:00:00+00:00",
        },
        {
            "test_id": "oos_create_out_of_spec", "endpoint": "POST /api/v1/oos", "payload": {},
            "response_status": 200, "response_excerpt": "{}",
            "assertion": {"received_value": "OOS"}, "result": "PASS", "detail": None, "latency_ms": 3.0,
            "agent_id": "qa_oos_profile", "run_by": "Tester", "run_at": "2026-01-05T00:00:00+00:00",
        },
    ]
    with (env["results_dir"] / f"{PROJECT}.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    dep_dir = env["dep_dir"] / PROJECT
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / ".env").write_text(f"GMP_API_KEY={GMP_SECRET}\n", encoding="utf-8")


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def test_endpoint_gmp_report_pdf_end_to_end_has_traceability_table(robust_pdf_env):
    _write_full_evidence(robust_pdf_env)
    resp = layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert resp.media_type == "application/pdf"
    text = _text(resp.body)
    assert "Detectar resultados OOS" in text  # fila de la tabla de trazabilidad
    assert "qa_oos_profile" in text


def test_endpoint_gmp_report_pdf_does_not_audit_by_default(robust_pdf_env, isolated_audit):
    _write_full_evidence(robust_pdf_env)
    before = _count_lines(isolated_audit)
    layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert _count_lines(isolated_audit) == before


def test_endpoint_gmp_report_pdf_does_not_contain_real_deployment_secret(robust_pdf_env):
    """Limite real de sanitizacion: el valor del secreto se enmascara en
    _build_gmp_report() antes de llegar a compose_robust_report()."""
    _write_full_evidence(robust_pdf_env)
    resp = layer9.get_gmp_report_pdf(PROJECT, record_by=None)
    assert GMP_SECRET.encode() not in resp.body
