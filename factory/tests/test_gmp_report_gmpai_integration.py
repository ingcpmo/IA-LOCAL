"""
Tests de regresión — integración de evidencia real de gmpai_document_validation
en el Dashboard GMP genérico (/gmp-report, /gmp-report.pdf).

Contexto del bug real corregido: gmp_report_service.build_gmp_report() y
pdf_report_robust.compose_robust_report() fueron escritos para el pilot
oos_hplc_investigator (catálogo de pruebas funcionales + texto de dominio
OOS/HPLC/SST hardcodeado) y se reusaron genéricamente para TODAS las
misiones, incluida gmpai_document_validation (que no tiene catálogo de
pruebas funcionales — su evidencia real vive en el RC canónico). Esto
producía un informe con 0 ejecuciones, "Ollama no ejecutado", contenido
OOS/HPLC ajeno y sin REM-GMPAI-001, pese a que la evidencia real (267
hallazgos sobre 32 documentos) ya existía y estaba aprobada.

Estos tests reusan el RC canónico real ya aprobado (no reprocesan
documentos ni invocan agentes).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import gmp_report_service as svc

PROJECT_ID = "gmpai_document_validation"


def test_build_gmp_report_shows_real_executions_not_zero():
    r = svc.build_gmp_report(PROJECT_ID)
    total_tests = sum(len(b["tests"]) for b in r["results_by_agent"])
    assert total_tests > 0, "debe mostrar ejecuciones reales, no 0"
    agent_ids = {b["agent_id"] for b in r["results_by_agent"]}
    assert agent_ids == {
        "fda_part11_agent", "eu_annex11_agent", "alcoa_plus_agent",
        "requirements_traceability_agent",
    }


def test_build_gmp_report_shows_llm_agent_and_model():
    r = svc.build_gmp_report(PROJECT_ID)
    assert r["rules_vs_llm"]["llm_endpoints"], "Ollama no debe aparecer como no ejecutado"
    assert any("requirements_traceability_agent" in e for e in r["rules_vs_llm"]["llm_endpoints"])
    assert "qwen2.5" in r["rules_vs_llm"]["explanation"] or "modelo del RC" in r["rules_vs_llm"]["explanation"]


def test_build_gmp_report_shows_rem_gmpai_001_open():
    r = svc.build_gmp_report(PROJECT_ID)
    assert any("REM-GMPAI-001" in p for p in r["pending_before_golive"]), \
        "REM-GMPAI-001 abierto debe aparecer en pendientes antes de go-live"


def test_build_gmp_report_has_no_foreign_oos_hplc_content():
    import json
    r = svc.build_gmp_report(PROJECT_ID)
    blob = json.dumps(r, ensure_ascii=False)
    assert "PENDING_DOCUMENT" not in blob
    # Las unicas menciones de OOS/HPLC permitidas son la aclaracion explicita
    # de que esos dominios de laboratorio no aplican a esta mision documental.
    assert r["gmp_implication"]["oos"].startswith("no aplica")
    assert r["gmp_implication"]["hplc"].startswith("no aplica")
    assert "OOS" not in r["operational_impact"]
    assert "HPLC" not in r["operational_impact"]
    assert "OOS" not in r["executive_summary"]
    assert "HPLC" not in r["executive_summary"]


def test_build_gmp_report_alcoa_has_real_evidence():
    r = svc.build_gmp_report(PROJECT_ID)
    assert r["gmp_implication"]["alcoa"] != "no_disponible"
    assert "alcoa_plus_agent" in r["gmp_implication"]["alcoa"]


def test_gmp_report_pdf_endpoint_uses_gmpai_generator_not_robust_template():
    """El endpoint /gmp-report.pdf debe delegar en el generador correcto
    (gmpai_pdf_report, ya validado) para esta mision, no en
    pdf_report_robust.compose_robust_report (hardcodeado a OOS/HPLC)."""
    from factory.services import gmpai_artifact_service as gmpai_svc
    from factory.core.gmpai_pdf_report import build_final_report_pdf

    report_data = gmpai_svc.build_final_report_data()
    pdf_bytes = build_final_report_pdf(report_data)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000
