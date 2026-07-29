"""
Tests — clasificacion de estado real de ejecucion de los 8 agentes de
gmpai_document_validation (distinto de "findings" y de "tests tecnicos").

Contexto: la auditoria de runtime confirmo que el RC v1.4 canonico no
persiste run_id/task_id/timestamp por documento/agente (un solo script,
un solo JSON agregado) — por eso ningun agente puede ser EXECUTED_VERIFIED
sobre esa corrida, aunque el resultado sea real y verificable
(RESULT_RECOVERED). Estos tests fijan esa clasificacion contra el RC
canonico real (no reprocesan documentos ni invocan agentes).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.services import gmpai_artifact_service as svc
from factory.services import gmpai_agent_execution_status as aes

EXPECTED_AGENTS = {
    "doc_inventory_version_agent", "doc_classification_agent",
    "fda_part11_agent", "eu_annex11_agent", "alcoa_plus_agent",
    "requirements_traceability_agent", "compliance_risk_agent", "final_review_agent",
}


def _real_report_data():
    return svc.build_final_report_data()


def test_classifies_exactly_the_declared_agent_roster():
    """EXPECTED_AGENTS es el roster declarado a proposito (un agente nuevo
    debe pasar por aqui conscientemente). El `len(rows) == 8` que habia
    debajo no anadia nada: repetia el tamano del propio roster y obligaba a
    editar dos sitios para el mismo cambio."""
    data = _real_report_data()
    rows = aes.build_agent_execution_status(data)
    assert {r["agent_id"] for r in rows} == EXPECTED_AGENTS
    assert len(rows) == len(EXPECTED_AGENTS)


def test_no_agent_is_executed_verified_on_canonical_rc():
    """El RC canonico v1.4 no tiene run_id/task_id/timestamp por ejecucion:
    ningun agente debe clasificarse EXECUTED_VERIFIED sobre esos datos."""
    data = _real_report_data()
    rows = aes.build_agent_execution_status(data)
    assert all(r["estado_evidencia"] != "EXECUTED_VERIFIED" for r in rows)
    assert all(r["task_id_run_id_disponible"] is False for r in rows)
    assert all(r["timestamps_por_ejecucion_disponibles"] is False for r in rows)


def test_no_agent_is_configured_only_or_failed():
    """Los 8 agentes SI produjeron resultado real (findings/records/
    matrices no vacios) — no estan solo configurados ni fallaron."""
    data = _real_report_data()
    rows = aes.build_agent_execution_status(data)
    assert all(r["estado_evidencia"] not in ("CONFIGURED_ONLY", "FAILED") for r in rows)


def test_integrity_agents_detect_real_llm_calls_vs_fallback():
    """fda_part11_agent/eu_annex11_agent/alcoa_plus_agent deben mostrar
    llamadas reales > 0 (documentos con texto extraible) Y detectar el
    fallback de los documentos escaneados sin OCR real.

    El `== 2` congelaba cuantos escaneados hay hoy en el corpus. Lo que de
    verdad prueba que la deteccion funciona es que sea >0 y que los tres
    agentes, que ven exactamente el mismo corpus, coincidan: si uno contara
    distinto, la deteccion dependeria del agente y no del documento."""
    data = _real_report_data()
    rows = {r["agent_id"]: r for r in aes.build_agent_execution_status(data)}
    integridad = ("fda_part11_agent", "eu_annex11_agent", "alcoa_plus_agent")
    fallbacks = {rows[a]["llamadas_fallback_sin_texto"] for a in integridad}
    for agent_id in integridad:
        assert rows[agent_id]["llamadas_reales_detectadas"] > 0, agent_id
    assert len(fallbacks) == 1, f"los 3 agentes ven el mismo corpus: {fallbacks}"
    assert fallbacks.pop() > 0, "el fallback por documento sin texto debe detectarse"


def test_summary_counts_match_rows():
    data = _real_report_data()
    rows = aes.build_agent_execution_status(data)
    summary = aes.summarize_agent_execution_status(rows)
    assert summary["total_agentes"] == len(rows)
    assert sum(summary["por_estado"].values()) == len(rows)


def test_build_final_report_data_embeds_agent_execution_status():
    data = _real_report_data()
    assert "agent_execution_status" in data
    assert "agent_execution_summary" in data
    assert len(data["agent_execution_status"]) == len(EXPECTED_AGENTS)
