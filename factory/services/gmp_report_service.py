"""
W5 — Servicio del Dashboard GMP + informe PDF (W4.1/W4.1.1), extraído de
routes/layer9.py sin cambio de comportamiento.

Capa de PRESENTACIÓN sobre W3/W4: consolida evidencia YA existente (summary,
agents, test-catalog, test-results, deployment, audit, rcs, workspace files)
en una estructura narrativa de dos niveles (ejecutivo + técnico). Read-only,
no re-implementa lectura de datos: delega en mission_evidence_service y
test_console_service. Todo campo sin fuente real se expone como
"no_disponible" — nunca se inventa un dato ni texto regulatorio. El
resultado pasa por sanitize_for_report() antes de exponerse.
"""

import os
from pathlib import Path

import yaml as _yaml
from fastapi import HTTPException

from factory.core.report_sanitizer import sanitize_for_report
from factory.layer9.mission_control import get_mission
from factory.services import paths
from factory.services import mission_evidence_service as evidence
from factory.services import test_console_service as console

NO_DATA = "no_disponible"

OPERATIONAL_IMPACT_TEXT = (
    "Los agentes evaluados podrian operar de forma continua (7x24) como apoyo "
    "al monitoreo, preclasificacion y validacion funcional de resultados de "
    "laboratorio: deteccion de resultados fuera de especificacion (OOS), "
    "revision de parametros cromatograficos (HPLC/SST) y validacion de "
    "integridad de datos (ALCOA+), generando evidencia trazable y auditada. "
    "En una operacion madura, esto podria reducir de forma estimada entre 30% "
    "y 60% el tiempo dedicado a revision preliminar, validacion repetitiva y "
    "preparacion de evidencia. Esta cifra es una ESTIMACION de mejora "
    "potencial, no una medicion del entorno actual."
)

CONCLUSION_NO_REPLACE_TEXT = (
    "Estos agentes funcionan como apoyo a QA/QC y NO reemplazan la decision "
    "humana ni liberan lotes de forma automatica. La liberacion de lote y la "
    "disposicion final permanecen bajo responsabilidad del personal QA/QC "
    "calificado. El sistema aporta velocidad, consistencia y evidencia "
    "trazable en las etapas preliminares, manteniendo el control humano en "
    "la decision."
)


def read_yaml_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def read_text_excerpt(path: Path, max_chars: int = 2000) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return None


def is_llm_endpoint(endpoint: str) -> bool:
    return "/api/v1/query" in (endpoint or "")


# ── gmpai_document_validation — integracion de evidencia real ───────────────
# Esta mision NO usa el catalogo de pruebas funcionales (factory/test_catalogs/,
# console.read_catalog) ni un contenedor propio: es un pipeline de analisis
# documental (agentes deterministas + 1 agente LLM real via Ollama) cuya
# evidencia real vive en el RC canonico (pipeline_pilot_llm.json) y en
# factory/docs/gmpai_remediation_tracker.json. Sin esta rama, build_gmp_report()
# reportaba 0 ejecuciones, "Ollama no ejecutado" y texto generico de OOS/HPLC
# (heredado del pilot oos_hplc_investigator) para esta mision, pese a que la
# evidencia real de 267 hallazgos sobre 32 documentos ya existia y estaba
# aprobada. Esta funcion NO reprocesa documentos ni invoca agentes: solo
# reutiliza gmpai_artifact_service.build_final_report_data() (mismos datos ya
# validados en el paquete de cierre) y los remapea al contrato generico.
GMPAI_DOC_VALIDATION_PROJECT_ID = "gmpai_document_validation"
_GMPAI_LLM_AGENTS = {"requirements_traceability_agent"}
_GMPAI_ESTADO_TO_RESULT = {
    "cumple": "PASS",
    "no_cumple": "FAIL",
    "cumple_parcialmente": "FAIL",
    "evidencia_insuficiente": "FAIL",
    "no_aplica": "SKIP",
}
_GMPAI_MAX_FINDINGS_PER_AGENT = 30


def _load_gmpai_document_validation_data() -> dict | None:
    from factory.services import gmpai_artifact_service as gmpai_svc
    try:
        return gmpai_svc.build_final_report_data()
    except gmpai_svc.ArtifactNotFound:
        return None


def _gmpai_results_by_agent(gmpai_data: dict) -> list[dict]:
    """Mapea las matrices de cumplimiento reales (findings del RC canonico) al
    formato results_by_agent[*].tests[*] que ya consume el dashboard/PDF
    genericos — cada finding real se expone como un registro de ejecucion,
    en vez de dejar la lista vacia por no existir un catalogo de pruebas."""
    rc_decided_at = gmpai_data.get("rc_canonical", {}).get("decided_at") or NO_DATA
    out = []
    for aid, rows in gmpai_data.get("matrices", {}).items():
        uses_llm = aid in _GMPAI_LLM_AGENTS
        tests = []
        for r in rows[:_GMPAI_MAX_FINDINGS_PER_AGENT]:
            estado = r.get("estado") or NO_DATA
            tests.append({
                "test_id": (r.get("documento") or NO_DATA)[:80],
                "title": r.get("requisito_regulatorio") or estado,
                "endpoint": f"agente_documental:{aid}" + (
                    " (LLM local Ollama)" if uses_llm else " (reglas deterministicas Python)"),
                "result": _GMPAI_ESTADO_TO_RESULT.get(estado, "FAIL"),
                "run_by": "pipeline_pilot_llm (RC canonico)",
                "run_at": rc_decided_at,
                "relevant_datum": r.get("brecha") or r.get("confianza") or NO_DATA,
                "uses_llm": uses_llm,
                "llm_evidence": None,
            })
        if len(rows) > _GMPAI_MAX_FINDINGS_PER_AGENT:
            tests.append({
                "test_id": NO_DATA,
                "title": f"... y {len(rows) - _GMPAI_MAX_FINDINGS_PER_AGENT} hallazgos adicionales "
                          f"(ver informe final GMPAI / compliance_matrices/{aid}.json)",
                "endpoint": NO_DATA, "result": "SKIP", "run_by": NO_DATA, "run_at": NO_DATA,
                "relevant_datum": NO_DATA, "uses_llm": uses_llm, "llm_evidence": None,
            })
        out.append({"agent_id": aid, "uses_llm": uses_llm, "tests": tests})
    return out


def build_gmp_report(project_id: str) -> dict:
    """
    Agregador read-only del Dashboard GMP (W4.1). NO audita. Reutiliza
    build_mission_summary / read_agents / read_catalog / read_results /
    read_deployment / read_rcs / read_audit — no re-implementa su lógica
    de lectura.
    """
    from datetime import datetime, timezone

    summary = evidence.build_mission_summary(project_id)  # 404 si la misión no existe
    mission_full = get_mission(project_id)

    try:
        agents_result = evidence.read_agents(project_id)
    except HTTPException:
        agents_result = {"agents": [], "summary": {"profiles_inherited": 0, "new_agents": 0}}

    try:
        catalog = console.read_catalog(project_id)
    except HTTPException:
        catalog = None

    test_results = console.read_results(project_id, limit=200)
    deployment = evidence.read_deployment(project_id)
    rcs_result = evidence.read_rcs(project_id)
    audit_result = evidence.read_audit(project_id, limit=100)

    design_dir = paths.DESIGNS_BASE / project_id
    requirement_spec = read_yaml_or_none(design_dir / "requirement_spec.yaml")
    pending_docs_yaml = read_yaml_or_none(design_dir / "pending_documents.yaml") or {}
    task_md = read_text_excerpt(paths.WS_BASE / project_id / "task.md")

    gmpai_data = (
        _load_gmpai_document_validation_data()
        if project_id == GMPAI_DOC_VALIDATION_PROJECT_ID else None
    )
    gmpai_rem_open = (
        [i for i in gmpai_data.get("remediation_items", []) if i.get("estado") == "open"]
        if gmpai_data else []
    )

    # ── meta ──
    mission_block = summary["mission"]
    canonical_rc = summary["rcs"]["canonical"] or NO_DATA
    deployment_status = "desplegado" if deployment.get("health_ok") else "no_desplegado"
    now_iso = datetime.now(timezone.utc).isoformat()

    meta = {
        "project_id": project_id,
        "generated_at": now_iso,
        "client_type": mission_block.get("client_type") or NO_DATA,
        "canonical_rc": canonical_rc,
        "deployment_status": deployment_status,
        "report_source": "evidencia real: summary, agents, test-results, deployment, audit, rcs",
    }

    # ── agentes evaluados ──
    agent_list = agents_result.get("agents", [])
    profiles_inherited = [a["agent_id"] for a in agent_list if a.get("is_inherited")]
    new_agents = [a["agent_id"] for a in agent_list if not a.get("is_inherited")]
    agents_evaluated = {
        "profiles_inherited": profiles_inherited,
        "new_agents": new_agents,
        "total": len(agent_list),
    }

    # ── índice test_id -> (agent_id, test_entry del catálogo) ──
    catalog_index: dict[str, tuple[str, dict]] = {}
    if catalog:
        for agent in catalog.get("agents", []):
            for t in agent.get("tests", []):
                catalog_index[t.get("test_id")] = (agent.get("agent_id"), t)

    # ── resultados por agente (a partir de test-results real, agrupado) ──
    results_by_agent_map: dict[str, list[dict]] = {}
    for rec in test_results.get("results", []):
        agent_id = rec.get("agent_id") or NO_DATA
        catalog_hit = catalog_index.get(rec.get("test_id"))
        title = catalog_hit[1].get("title") if catalog_hit else None
        endpoint = rec.get("endpoint") or (catalog_hit[1].get("endpoint") if catalog_hit else None)
        assertion = rec.get("assertion") or {}
        relevant_datum = assertion.get("received_value")
        if relevant_datum is None:
            relevant_datum = NO_DATA
        results_by_agent_map.setdefault(agent_id, []).append({
            "test_id": rec.get("test_id") or NO_DATA,
            "title": title or NO_DATA,
            "endpoint": endpoint or NO_DATA,
            "result": rec.get("result") or NO_DATA,
            "run_by": rec.get("run_by") or NO_DATA,
            "run_at": rec.get("run_at") or NO_DATA,
            "relevant_datum": relevant_datum,
            "uses_llm": is_llm_endpoint(endpoint if isinstance(endpoint, str) else ""),
            "llm_evidence": rec.get("llm_evidence"),
        })
    if gmpai_data:
        # Esta mision no tiene catalogo de pruebas funcionales (factory/test_catalogs/):
        # su evidencia real de ejecucion vive en el RC canonico, no en test-results.
        results_by_agent = _gmpai_results_by_agent(gmpai_data)
    else:
        results_by_agent = [
            {"agent_id": aid, "uses_llm": any(t["uses_llm"] for t in tests), "tests": tests}
            for aid, tests in results_by_agent_map.items()
        ]

    # ── interpretación farmacéutica (derivada de conteos reales, no inventada) ──
    pharma_interpretation = []
    for block in results_by_agent:
        tests = block["tests"]
        passed = sum(1 for t in tests if t["result"] == "PASS")
        failed = sum(1 for t in tests if t["result"] == "FAIL")
        errored = sum(1 for t in tests if t["result"] == "ERROR")
        pharma_interpretation.append(
            f"Agente {block['agent_id']}: {passed}/{len(tests)} pruebas PASS"
            + (f", {failed} FAIL" if failed else "")
            + (f", {errored} ERROR" if errored else "")
            + "."
        )
    if not pharma_interpretation:
        pharma_interpretation = ["No se han ejecutado pruebas funcionales aun para esta mision."]

    # ── implicación GMP (solo si hay pruebas reales de ese dominio) ──
    def _domain_summary(prefixes: tuple[str, ...]) -> str:
        matched = [
            t for block in results_by_agent for t in block["tests"]
            if any((t.get("test_id") or "").startswith(p) for p in prefixes)
        ]
        if not matched:
            return NO_DATA
        passed = sum(1 for t in matched if t["result"] == "PASS")
        return f"{passed}/{len(matched)} pruebas PASS sobre evidencia real ejecutada."

    if gmpai_data:
        # Esta mision es de validacion documental, no de laboratorio: OOS/HPLC
        # no aplican. ALCOA+ si aplica y tiene evidencia real (alcoa_plus_agent).
        def _gmpai_agent_summary(aid: str) -> str:
            rows = gmpai_data["matrices"].get(aid, [])
            if not rows:
                return NO_DATA
            passed = sum(1 for r in rows if r.get("estado") == "cumple")
            return f"{passed}/{len(rows)} conformes (agente {aid}, evidencia real del RC canonico)."

        gmp_implication = {
            "oos": "no aplica a esta mision (validacion documental, no laboratorio de OOS).",
            "hplc": "no aplica a esta mision (validacion documental, no laboratorio HPLC/SST).",
            "alcoa": _gmpai_agent_summary("alcoa_plus_agent"),
        }
    else:
        gmp_implication = {
            "oos": _domain_summary(("oos_",)),
            "hplc": _domain_summary(("sst_", "peaks_", "rsd_")),
            "alcoa": _domain_summary(("alcoa_", "audit_")),
        }

    # ── reglas vs LLM ──
    if gmpai_data:
        agents_meta = gmpai_data.get("agents", {})
        deterministic_endpoints = sorted(
            f"agente_documental:{aid}" for aid in agents_meta if aid not in _GMPAI_LLM_AGENTS
        )
        llm_endpoints = sorted(
            f"agente_documental:{aid} (modelo Ollama)" for aid in agents_meta if aid in _GMPAI_LLM_AGENTS
        )
        model_used = next((m.get("model") for m in agents_meta.values() if m.get("model")), NO_DATA)
        rules_vs_llm = {
            "deterministic_endpoints": deterministic_endpoints,
            "llm_endpoints": llm_endpoints,
            "explanation": (
                "fda_part11_agent, eu_annex11_agent y alcoa_plus_agent son deterministicos "
                "(modulos Python puros, reglas fijas, sin LLM). requirements_traceability_agent "
                "es el unico agente LLM real: invoca Ollama local (modelo del RC: "
                f"{model_used}) via httpx directo a la API REST de Ollama (no via paquete "
                "Python ollama), para evaluar trazabilidad GAMP 5 URS->FS->DS->IQ/OQ/PQ->SAT. "
                "Nota: requirements_traceability_agent no registra el campo 'model' en sus "
                "propios findings (limitacion conocida); el modelo mostrado es el declarado "
                "por los otros agentes del mismo RC."
            ),
        }
    else:
        all_catalog_tests = [
            (a.get("agent_id"), t)
            for a in (catalog.get("agents", []) if catalog else [])
            for t in a.get("tests", [])
        ]
        deterministic_endpoints = sorted({
            t.get("endpoint") for _, t in all_catalog_tests if not is_llm_endpoint(t.get("endpoint", ""))
        })
        llm_endpoints = sorted({
            t.get("endpoint") for _, t in all_catalog_tests if is_llm_endpoint(t.get("endpoint", ""))
        })
        rules_vs_llm = {
            "deterministic_endpoints": deterministic_endpoints,
            "llm_endpoints": llm_endpoints,
            "explanation": (
                "Los endpoints deterministicos ejecutan logica Python de reglas fijas "
                "(sin LLM); los endpoints LLM invocan Ollama local para inferencia. "
                "El catalogo curado de esta mision se limita a casos aislados y "
                "deterministicos (ver notas del catalogo)."
            ),
        }

    # ── auditoría y trazabilidad ──
    canonical_rc_manifest = next(
        (r for r in rcs_result.get("rcs", []) if r.get("rc_id") == canonical_rc), None
    )
    test_event_types = {"agent_functional_test_executed", "agent_suite_tested"}
    test_events_count = sum(
        1 for e in audit_result.get("events", []) if e.get("event_type") in test_event_types
    )
    audit_traceability = {
        "canonical_rc": canonical_rc,
        "rc_sha256": (canonical_rc_manifest or {}).get("sha256sums") or NO_DATA,
        "test_events_count": test_events_count,
        "last_audit_events": audit_result.get("events", [])[:10],
    }

    # ── pharma_case / mission_objective ──
    if requirement_spec:
        pharma_case = {
            "raw_objective": requirement_spec.get("raw_objective") or NO_DATA,
            "domains": requirement_spec.get("domains") or [],
            "client_needs": requirement_spec.get("client_needs") or [],
            "part11_required": requirement_spec.get("part11_required"),
            "alcoa_plus_required": requirement_spec.get("alcoa_plus_required"),
        }
    else:
        pharma_case = NO_DATA

    mission_objective = {
        "objective": mission_full.get("objective") or NO_DATA,
        "regulatory_scope": mission_full.get("regulatory_scope") or [],
        "task_summary": task_md or NO_DATA,
    }

    # ── limitaciones / pendientes go-live (de pending_documents real) ──
    pending_entries = pending_docs_yaml.get("documents", pending_docs_yaml.get("pending", [])) or []
    limitations = [
        f"{d.get('title', d.get('id', 'documento'))}: {d.get('status', 'PENDING_DOCUMENT')}"
        for d in pending_entries
    ]
    if not limitations:
        limitations = [NO_DATA]

    pending_before_golive = list(limitations) if pending_entries else []
    if canonical_rc == NO_DATA:
        pending_before_golive.append("Sin RC marcado como canonico para esta mision.")
    if deployment_status != "desplegado":
        pending_before_golive.append("Deployment no esta activo/saludable.")
    if not pending_before_golive:
        pending_before_golive = [NO_DATA]

    if gmpai_data:
        # Esta mision es analisis documental puro, sin despliegue Docker por
        # diseno (mission.yaml: "sin Docker — analisis documental puro") — el
        # aviso generico de deployment no aplica y es enganoso aqui. Los
        # pendientes reales son las remediaciones abiertas del tracker
        # (REM-GMPAI-001+), no un pending_documents.yaml vacio.
        limitations = gmpai_data.get("limitations") or [NO_DATA]
        pending_before_golive = [
            f"{i['id']} [{i.get('severidad', '?')}] {i.get('hallazgo', '')}"
            for i in gmpai_rem_open
        ] or [NO_DATA]

    # ── resumen ejecutivo (derivado de conteos reales) ──
    total_tests = sum(len(b["tests"]) for b in results_by_agent)
    total_pass = sum(1 for b in results_by_agent for t in b["tests"] if t["result"] == "PASS")
    total_fail = sum(1 for b in results_by_agent for t in b["tests"] if t["result"] in ("FAIL", "ERROR"))
    if total_tests:
        executive_summary = (
            f"La mision '{project_id}' ha ejecutado {total_tests} pruebas funcionales "
            f"reales sobre {len(agent_list)} agente(s) evaluado(s): {total_pass} PASS, "
            f"{total_fail} FAIL/ERROR. "
            + ("RC canonico marcado. " if canonical_rc != NO_DATA else "Sin RC canonico marcado. ")
            + ("Deployment activo." if deployment_status == "desplegado" else "Deployment no activo.")
        )
    else:
        executive_summary = "No se han ejecutado pruebas funcionales aun para esta mision."

    # ── conclusión (texto obligatorio + mención de pendientes reales) ──
    conclusion_parts = [executive_summary, CONCLUSION_NO_REPLACE_TEXT]
    if pending_entries:
        conclusion_parts.append(
            "Existen documentos regulatorios PENDING_DOCUMENT sin confirmar; deben "
            "resolverse antes de un go-live regulatorio."
        )
    if gmpai_data and gmpai_rem_open:
        conclusion_parts.append(
            f"Existe(n) {len(gmpai_rem_open)} remediacion(es) abierta(s) sin cerrar "
            f"(p.ej. {gmpai_rem_open[0]['id']}: {gmpai_rem_open[0].get('hallazgo', '')}) "
            "pendiente(s) de decision humana antes de cierre regulatorio completo."
        )
    conclusion = " ".join(conclusion_parts)

    operational_impact = (
        (
            "Los 8 agentes de esta mision (doc_inventory_version_agent, "
            "doc_classification_agent, fda_part11_agent, eu_annex11_agent, alcoa_plus_agent, "
            "requirements_traceability_agent, compliance_risk_agent, final_review_agent) "
            "analizan documentacion de validacion (URS, FS, DS, SAT, arquitectura, narrativas "
            "de control) contra FDA 21 CFR Part 11, EU GMP Annex 11 y ALCOA+, generando "
            "matrices de cumplimiento y hallazgos trazables a documento y seccion. Esta es "
            "una EVALUACION ASISTIDA por IA, no una aprobacion GMP automatica. Esta mision "
            "analiza documentacion de validacion de sistemas (URS/FS/DS/SAT/arquitectura); "
            "no analiza resultados analiticos de muestras de laboratorio."
        ) if gmpai_data else OPERATIONAL_IMPACT_TEXT
    )

    report = {
        "meta": meta,
        "executive_summary": executive_summary,
        "mission_objective": mission_objective,
        "pharma_case": pharma_case,
        "agents_evaluated": agents_evaluated,
        "results_by_agent": results_by_agent,
        "pharma_interpretation": pharma_interpretation,
        "gmp_implication": gmp_implication,
        "rules_vs_llm": rules_vs_llm,
        "audit_traceability": audit_traceability,
        "operational_impact": operational_impact,
        "limitations": limitations,
        "pending_before_golive": pending_before_golive,
        "conclusion": conclusion,
    }
    if gmpai_data:
        # Separacion explicita findings vs ejecuciones (ver auditoria REM-GMPAI-001):
        # resultados_by_agent son FINDINGS, no pruebas tecnicas ni ejecuciones
        # verificadas. Este bloque adicional es la clasificacion real de
        # ejecucion por agente y el resumen de la matriz finding->correccion.
        report["results_by_agent_label"] = "Findings por agente (evaluacion de documentos, NO pruebas tecnicas)"
        report["agent_execution_status"] = gmpai_data.get("agent_execution_status", [])
        report["agent_execution_summary"] = gmpai_data.get("agent_execution_summary", {})
        report["finding_correction_summary"] = gmpai_data.get("finding_correction_summary", {})

    secret_values = [
        os.environ.get("FACTORY_API_KEY"),
        os.environ.get("GMP_API_KEY"),
        os.environ.get("ANTHROPIC_API_KEY"),
        os.environ.get("POSTGRES_PASSWORD"),
        console.get_deployment_api_key(project_id),
    ]
    return sanitize_for_report(report, secret_values=secret_values)
