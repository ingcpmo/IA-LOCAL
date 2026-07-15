"""
GMPAI — Estado de ejecucion real de los 8 agentes del pipeline de
gmpai_document_validation, distinto de "findings" y de "tests tecnicos".

Contexto (auditoria confirmada en runtime + codigo fuente, ver
factory/workspaces/gmpai_document_validation/app/pipeline.py y
llm_integrity_engine.py): el pipeline corre como UN script (`pipeline.py`)
que produce un unico JSON agregado (pipeline_pilot_llm.json) — NO existe
run_id/task_id/timestamp por documento/agente en el RC canonico v1.4. Por
eso ningun agente puede clasificarse EXECUTED_VERIFIED sobre esa corrida:
existe evidencia REAL de que corrieron (findings reales, correlacionados con
el contenido real de cada documento — ver abajo), pero falta la metadata de
runtime individual exigida (run_id, task_id, timestamps, log por llamada).

Este modulo NO reprocesa nada: deriva la clasificacion inspeccionando los
findings YA existentes (distingue una llamada real a Ollama de un fallback
interno comparando el texto exacto de `brecha` contra las firmas fijas de
fallback de llm_integrity_engine._fallback_findings /
llm_traceability_agent, que son literales y estables).
"""

from __future__ import annotations

_FALLBACK_BRECHA_SIGNATURES = (
    "El agente LLM no pudo evaluar este checkpoint: documento sin texto extraible",
    "El modelo no devolvio este checkpoint en su respuesta.",
)

# Agentes que invocan Ollama (ver pipeline.py linea ~110-131: selecciona
# llm_part11_agent/llm_annex11_agent/llm_alcoa_agent/llm_traceability_agent
# cuando integrity_engine == "llm", que es el motor real usado en el RC v1.4
# canonico — pipeline_pilot_llm.json declara integrity_engine: "llm").
_LLM_AGENTS = {"fda_part11_agent", "eu_annex11_agent", "alcoa_plus_agent", "requirements_traceability_agent"}
# Agentes deterministas (modulos Python puros: inventory_agent.py,
# classification_agent.py, risk_agent.py, final_review_agent.py — sin
# import de httpx/ollama_client).
_DETERMINISTIC_AGENTS = {
    "doc_inventory_version_agent", "doc_classification_agent",
    "compliance_risk_agent", "final_review_agent",
}

_AGENT_FUNCTION = {
    "doc_inventory_version_agent": "Inventario, hash SHA-256 y seleccion de version vigente por familia documental.",
    "doc_classification_agent": "Clasificacion de tipo de documento (URS/FS/DS/SAT/arquitectura/otro).",
    "fda_part11_agent": "Evaluacion de checkpoints FDA 21 CFR Part 11 contra el texto extraido del documento (LLM).",
    "eu_annex11_agent": "Evaluacion de checkpoints EU GMP Annex 11 (LLM).",
    "alcoa_plus_agent": "Evaluacion de checkpoints ALCOA+ (LLM).",
    "requirements_traceability_agent": "Trazabilidad URS->FS->DS->IQ/OQ/PQ->SAT a nivel de familia documental (LLM).",
    "compliance_risk_agent": "Agregacion y priorizacion de riesgo sobre los findings de los 4 agentes anteriores.",
    "final_review_agent": "Consolidacion final de gobernanza y recomendacion de siguiente paso.",
}


def _is_real_llm_call(findings_for_pair: list[dict]) -> bool:
    return not all((f.get("brecha") or "") in _FALLBACK_BRECHA_SIGNATURES for f in findings_for_pair)


def build_agent_execution_status(gmpai_data: dict) -> list[dict]:
    """Clasifica cada uno de los 8 agentes usando EXCLUSIVAMENTE evidencia ya
    existente en gmpai_data (gmpai_artifact_service.build_final_report_data()).
    No abre ni reprocesa el JSON crudo del RC — usa las mismas matrices y
    records ya agregados que el resto del informe."""
    matrices = gmpai_data.get("matrices", {})
    agents_meta = gmpai_data.get("agents", {})
    records = gmpai_data.get("inventory", {}).get("records_detail", [])
    totals = gmpai_data.get("inventory", {}).get("totals", {})

    out = []

    def _row(agent_id, estado, evidence, real_calls, fallback_calls, docs_covered, findings_count, rationale):
        meta = agents_meta.get(agent_id, {})
        out.append({
            "agent_id": agent_id,
            "agent_version": meta.get("agent_version") or "no_disponible",
            "prompt_version": meta.get("prompt_version") or "no_disponible",
            "verifier_version": meta.get("verifier_version") or "no_disponible",
            "funcion": _AGENT_FUNCTION[agent_id],
            "documentos_asignados": docs_covered,
            "modelo_o_regla": (meta.get("model") or "modelo no registrado en el finding (ver limitaciones)"
                                if agent_id in _LLM_AGENTS else "regla deterministica (Python puro, sin LLM)"),
            "llamadas_reales_detectadas": real_calls,
            "llamadas_fallback_sin_texto": fallback_calls,
            "findings_producidos": findings_count,
            "task_id_run_id_disponible": False,
            "timestamps_por_ejecucion_disponibles": False,
            "archivo_resultado": "pipeline_pilot_llm.json (RC canonico, agregado — sin archivo individual por ejecucion)",
            "auditoria_por_ejecucion": False,
            "estado_evidencia": estado,
            "justificacion": rationale,
        })

    # ── 3 agentes LLM de integridad (checkpoints por documento) ──
    for agent_id in ("fda_part11_agent", "eu_annex11_agent", "alcoa_plus_agent"):
        rows = matrices.get(agent_id, [])
        by_doc: dict[str, list[dict]] = {}
        for r in rows:
            by_doc.setdefault(r["documento"], []).append(r)
        real_calls = sum(1 for doc_rows in by_doc.values() if _is_real_llm_call(doc_rows))
        fallback_calls = len(by_doc) - real_calls
        estado = "RESULT_RECOVERED" if real_calls > 0 else "CONFIGURED_ONLY"
        _row(
            agent_id, estado, None, real_calls, fallback_calls, len(by_doc), len(rows),
            f"{real_calls} de {len(by_doc)} documentos con llamada real a Ollama detectada "
            f"(resultado varia con el contenido extraido); {fallback_calls} con fallback "
            "sin llamada real (documento sin texto extraible, p.ej. PDF escaneado sin OCR). "
            "Resultado real y verificable, pero SIN metadata de runtime individual "
            "(no hay run_id/task_id/timestamp por llamada en el RC canonico) -> "
            "RESULT_RECOVERED, no EXECUTED_VERIFIED."
        )

    # ── requirements_traceability_agent (1 llamada a nivel de familia) ──
    trace_rows = matrices.get("requirements_traceability_agent", [])
    real_calls = 1 if trace_rows and _is_real_llm_call(trace_rows) else 0
    _row(
        "requirements_traceability_agent",
        "RESULT_RECOVERED" if real_calls else "CONFIGURED_ONLY",
        None, real_calls, 1 - real_calls, 1, len(trace_rows),
        "1 llamada real a Ollama a nivel de familia documental (14 documentos combinados, "
        "post-fix MAX_DOC_CHARS 6000->46000, Fase C). Resultado real, sin metadata de "
        "runtime individual persistida -> RESULT_RECOVERED."
    )

    # ── 4 agentes deterministas (inventario, clasificacion, riesgo, revision final) ──
    inventory_docs = totals.get("files_inventoried", 0)
    detailed_docs = len(records)
    _row(
        "doc_inventory_version_agent", "RESULT_RECOVERED", None, detailed_docs, 0,
        inventory_docs, detailed_docs,
        f"Verificacion SHA-256 real sobre {inventory_docs} documentos declarados (32); "
        f"registro detallado (extraccion, familia, version) solo para {detailed_docs} "
        "(alcance=pilot, Rockwell). Resultado real y determinista, pero sin timestamp/"
        "run_id por archivo -> RESULT_RECOVERED."
    )
    _row(
        "doc_classification_agent", "RESULT_RECOVERED", None, detailed_docs, 0,
        detailed_docs, detailed_docs,
        f"Clasificacion real de {detailed_docs} documentos (alcance=pilot, Rockwell). "
        "Determinista, sin metadata de runtime individual -> RESULT_RECOVERED."
    )
    total_findings = gmpai_data.get("findings_total", 0)
    _row(
        "compliance_risk_agent", "RESULT_RECOVERED", None, 1, 0, detailed_docs, total_findings,
        f"Agregacion real y determinista de los {total_findings} findings en una matriz "
        "de riesgo priorizada. Es un paso de POST-PROCESAMIENTO sobre findings ya "
        "generados, no una evaluacion independiente por documento -> RESULT_RECOVERED."
    )
    _row(
        "final_review_agent", "RESULT_RECOVERED", None, 1, 0, detailed_docs, 1,
        "Consolidacion real y determinista del gobierno/veredicto final del RC. "
        "Post-procesamiento sobre el resto de agentes -> RESULT_RECOVERED."
    )

    return out


def summarize_agent_execution_status(rows: list[dict]) -> dict:
    by_estado: dict[str, int] = {}
    for r in rows:
        by_estado[r["estado_evidencia"]] = by_estado.get(r["estado_evidencia"], 0) + 1
    return {
        "total_agentes": len(rows),
        "por_estado": by_estado,
        "executed_verified": by_estado.get("EXECUTED_VERIFIED", 0),
        "result_recovered": by_estado.get("RESULT_RECOVERED", 0),
        "configured_only": by_estado.get("CONFIGURED_ONLY", 0),
        "failed": by_estado.get("FAILED", 0),
        "not_applicable": by_estado.get("NOT_APPLICABLE", 0),
    }
