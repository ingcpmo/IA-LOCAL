"""
W4.1.1 — Compositor de PDF robusto (18 secciones) del Dashboard GMP.

NO reemplaza factory/core/pdf_report.py (W4.1) como modulo — agrega
compose_robust_report(payload, project_id) como funcion nueva e independiente.
Consume EXCLUSIVAMENTE:
  - el dict ya sanitizado que devuelve _build_gmp_report() (W4.1), y
  - los archivos de diseno YA existentes en factory/designs/<project_id>/
    (requirement_spec.yaml, agent_design_proposal.yaml, regulatory_matrix.yaml,
    corpus_manifest.yaml, pending_documents.yaml, compliance_assessment.yaml)
No recolecta datos por su cuenta (no llama endpoints, no ejecuta pruebas).

Los textos narrativos son plantillas de estructura fija; todo valor variable
proviene de la evidencia real anterior. Si una fuente falta, la subseccion
dice "no disponible" — nunca se inventa un dato, fecha, cita o aprobacion.
"""

from pathlib import Path

import yaml as _yaml
from fpdf import FPDF, FontFace, XPos, YPos

from factory.core.pdf_report import _safe
from factory.core.report_sanitizer import sanitize_for_report

_NO_DATA = "no disponible"
_FACTORY_ROOT = Path(__file__).resolve().parent.parent
_DESIGNS_BASE = _FACTORY_ROOT / "designs"

_NO_REPLACE_CLAUSE = (
    "Estos agentes funcionan como apoyo a QA/QC y no reemplazan la decision "
    "humana ni liberan lotes automaticamente."
)

_ROLE_DESCRIPTIONS = {
    "Mission Control": (
        "punto de entrada donde se declara la necesidad del cliente y se "
        "transforma en una mision estructurada."
    ),
    "Capa 8": (
        "agente especializado que analiza el requerimiento, disena los "
        "agentes/perfiles necesarios, genera el workspace y ejecuta pruebas "
        "y quality gates de forma trazable."
    ),
    "Capa 9": (
        "orquestador de fabrica que gestiona el ciclo de vida de la mision "
        "(revision, release candidates, aprobacion humana, auditoria)."
    ),
    "Deployment": (
        "instancia aislada (API + base de datos + cache) donde los agentes "
        "disenados quedan disponibles para pruebas funcionales reales."
    ),
}


# ── Helpers de lectura de diseno (misma fuente permitida que W4.1) ──────────

def _read_yaml_or_none(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def _load_design_files(project_id: str) -> dict:
    design_dir = _DESIGNS_BASE / project_id
    return {
        "requirement_spec": _read_yaml_or_none(design_dir / "requirement_spec.yaml"),
        "agent_design_proposal": _read_yaml_or_none(design_dir / "agent_design_proposal.yaml"),
        "compliance_assessment": _read_yaml_or_none(design_dir / "compliance_assessment.yaml"),
        "regulatory_matrix": _read_yaml_or_none(design_dir / "regulatory_matrix.yaml"),
        "corpus_manifest": _read_yaml_or_none(design_dir / "corpus_manifest.yaml"),
        "pending_documents": _read_yaml_or_none(design_dir / "pending_documents.yaml"),
    }


# ── Tarea 3: deduplicacion + matriz de trazabilidad ─────────────────────────

def dedupe_last_by_test_id(results_by_agent: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Retorna (cuerpo_deduplicado, anexo_completo).
    Cuerpo: 1 fila por test_id (la de run_at mas reciente) por agente.
    Anexo: el mismo results_by_agent original, sin tocar (todas las ejecuciones).
    """
    body: list[dict] = []
    for block in results_by_agent or []:
        tests = block.get("tests") or []
        latest_by_id: dict[str, dict] = {}
        for t in tests:
            tid = t.get("test_id") or _NO_DATA
            existing = latest_by_id.get(tid)
            if existing is None or (t.get("run_at") or "") >= (existing.get("run_at") or ""):
                latest_by_id[tid] = t
        deduped = sorted(latest_by_id.values(), key=lambda x: x.get("test_id") or "")
        body.append({
            "agent_id": block.get("agent_id"),
            "uses_llm": block.get("uses_llm", False),
            "tests": deduped,
        })
    return body, (results_by_agent or [])


_OBJECTIVE_DEFS = [
    {
        "domain": "OOS", "objective": "Detectar resultados OOS",
        "function": "Comparar el resultado analitico contra el limite de especificacion y clasificar el caso como OOS.",
        "match": lambda tid: tid.startswith("oos_") and "out_of_spec" in tid,
        "routing_kw": "oos",
    },
    {
        "domain": "OOS", "objective": "Validar resultados in-spec",
        "function": "Confirmar que un resultado dentro de especificacion no se clasifique como OOS.",
        "match": lambda tid: tid.startswith("oos_") and "in_spec" in tid,
        "routing_kw": "oos",
    },
    {
        "domain": "HPLC", "objective": "Evaluar desempeno HPLC/SST",
        "function": "Validar los criterios de System Suitability Test (SST) de la secuencia cromatografica.",
        "match": lambda tid: tid.startswith("sst_"),
        "routing_kw": "hplc",
    },
    {
        "domain": "HPLC", "objective": "Calcular RSD",
        "function": "Calcular la desviacion estandar relativa (RSD) sobre inyecciones replicadas.",
        "match": lambda tid: tid.startswith("rsd_"),
        "routing_kw": "hplc",
    },
    {
        "domain": "HPLC", "objective": "Detectar anomalias cromatograficas",
        "function": "Detectar picos con area/altura anomala dentro de la secuencia de inyeccion.",
        "match": lambda tid: tid.startswith("peaks_"),
        "routing_kw": "hplc",
    },
    {
        "domain": "DATA_INTEGRITY", "objective": "Validar ALCOA+",
        "function": "Verificar atributos ALCOA+ (Atribuible, Legible, Contemporaneo, Original, Exacto y derivados).",
        "match": lambda tid: tid.startswith("alcoa_"),
        "routing_kw": "integrity",
    },
    {
        "domain": "LIMS", "objective": "Sello de auditoria y trazabilidad",
        "function": "Generar sello de auditoria inmutable asociado al registro LIMS.",
        "match": lambda tid: tid.startswith("audit_"),
        "routing_kw": "lims",
    },
]


def _agent_for_routing_kw(agent_design: dict | None, routing_kw: str) -> str:
    if not agent_design:
        return _NO_DATA
    for agent in agent_design.get("agents", []) or []:
        rk = (agent.get("routing_key") or "").lower()
        if routing_kw in rk:
            return agent.get("agent_id") or _NO_DATA
    return _NO_DATA


def _gmp_interpretation_for(result: str) -> str:
    return {
        "PASS": "El sistema demostro cumplimiento funcional de este objetivo con evidencia real (PASS).",
        "FAIL": "El sistema no cumplio el criterio esperado para este objetivo; requiere revision antes de uso productivo (FAIL).",
        "ERROR": "La prueba no pudo completarse por un error tecnico; no hay evidencia valida de cumplimiento (ERROR).",
        "no_evaluado": "No se ha ejecutado una prueba funcional que demuestre este objetivo todavia.",
    }.get(result, "Sin interpretacion derivable sin evidencia.")


def _status_for(result: str) -> str:
    if result == "PASS":
        return "cumplido"
    if result == "no_evaluado":
        return "pendiente (sin evidencia de prueba funcional)"
    return "parcialmente cumplido (prueba ejecutada, resultado no exitoso)"


def build_traceability_matrix(payload: dict, design: dict) -> list[dict]:
    """
    Cruza objetivos derivados de requirement_spec/regulatory_matrix con
    agents/test-catalog/test-results reales. Nunca inventa objetivos que
    el diseno no soporte: solo incluye objetivos cuyo dominio esta
    presente en requirement_spec.domains (o regulatory_matrix.requirements).
    """
    requirement_spec = design.get("requirement_spec") or {}
    regulatory_matrix = design.get("regulatory_matrix") or {}
    agent_design = design.get("agent_design_proposal")

    domains_present = set(requirement_spec.get("domains") or [])
    if not domains_present:
        domains_present = {r.get("domain") for r in (regulatory_matrix.get("requirements") or []) if r.get("domain")}

    # test_id -> (agent_id, ultimo resultado) a partir del cuerpo deduplicado
    body, _ = dedupe_last_by_test_id(payload.get("results_by_agent") or [])
    test_index: dict[str, dict] = {}
    for block in body:
        for t in block.get("tests", []):
            tid = t.get("test_id")
            if tid:
                test_index[tid] = {**t, "agent_id": block.get("agent_id")}

    rows = []
    for od in _OBJECTIVE_DEFS:
        if domains_present and od["domain"] not in domains_present:
            continue
        matched = [t for tid, t in test_index.items() if od["match"](tid)]
        agent_id = _agent_for_routing_kw(agent_design, od["routing_kw"])
        if matched:
            t = matched[0]
            result = t.get("result") or "no_evaluado"
            rows.append({
                "objective": od["objective"],
                "agent": t.get("agent_id") or agent_id,
                "function": od["function"],
                "test_id": t.get("test_id"),
                "result": result,
                "evidence_source": "test-results",
                "gmp_interpretation": _gmp_interpretation_for(result),
                "status": _status_for(result),
            })
        else:
            rows.append({
                "objective": od["objective"],
                "agent": agent_id,
                "function": od["function"],
                "test_id": _NO_DATA,
                "result": "no_evaluado",
                "evidence_source": "sin evidencia de prueba funcional para este objetivo",
                "gmp_interpretation": _gmp_interpretation_for("no_evaluado"),
                "status": _status_for("no_evaluado"),
            })
    return rows


# ── Render helpers ───────────────────────────────────────────────────────────

class _RobustPDF(FPDF):
    project_id = "mision"
    gen_date = ""

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            f"{self.project_id} . generado {self.gen_date} . "
            f"No reemplaza la decision QA/QC . pagina {self.page_no()}/{{nb}}",
            align="C",
        )


def _h1(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 9, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(3)


def _h2(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _p(pdf: FPDF, text, size: float = 9.5, bold: bool = False, color=(40, 40, 40)) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.2, _safe(text))
    pdf.ln(1)


def _bullets(pdf: FPDF, lines, size: float = 9) -> None:
    for line in (lines or [_NO_DATA]):
        _p(pdf, "- " + str(line), size=size)


def _s(value, fallback=_NO_DATA):
    if value in (None, "", [], {}):
        return fallback
    return value


def _table(pdf: FPDF, headings: list[str], rows: list[list], col_widths: list[float], size: float = 7.5) -> None:
    if not rows:
        _p(pdf, "no disponible", size=8.5)
        return
    pdf.set_font("Helvetica", "", size)
    with pdf.table(
        col_widths=col_widths,
        text_align="LEFT",
        line_height=4.2,
        headings_style=FontFace(emphasis="BOLD", size_pt=size, fill_color=(230, 230, 230)),
    ) as table:
        row = table.row()
        for h in headings:
            row.cell(_safe(h))
        for data_row in rows:
            row = table.row()
            for cell in data_row:
                row.cell(_safe(_s(cell)))


def _test_narrative(t: dict) -> str:
    result = t.get("result")
    title = t.get("title") or t.get("test_id")
    endpoint = t.get("endpoint")
    datum = t.get("relevant_datum")
    if result == "PASS":
        verdict = "El resultado fue PASS: el sistema respondio conforme al criterio esperado para este caso."
        gmp = ("La implicacion GMP es que este comportamiento puede apoyar la deteccion/validacion "
               "prevista, sin liberacion automatica del lote.")
    elif result == "FAIL":
        verdict = "El resultado fue FAIL: la respuesta del sistema no coincidio con el criterio esperado."
        gmp = "La implicacion GMP es que este caso requiere revision del criterio o de la implementacion antes de considerarse funcional."
    elif result == "ERROR":
        verdict = "El resultado fue ERROR: la prueba no pudo completarse (fallo tecnico o de conexion)."
        gmp = "La implicacion GMP es que no existe evidencia valida de funcionamiento para este caso hasta resolver el error."
    else:
        verdict = "Esta prueba no tiene un resultado registrado."
        gmp = "No hay implicacion GMP derivable sin evidencia."
    return (
        f"Prueba '{title}' (test_id={t.get('test_id')}) sobre el endpoint {endpoint}. "
        f"{verdict} Dato evaluado/recibido: {_s(datum)}. {gmp} "
        f"Ejecutado por {_s(t.get('run_by'))} el {_s(t.get('run_at'))}."
    )


# ── Compositor principal ────────────────────────────────────────────────────

def compose_robust_report(payload: dict, project_id: str) -> bytes:
    """Construye el PDF robusto de 18 secciones a partir del payload de /gmp-report."""
    secret_values = []  # el payload ya llega sanitizado por _build_gmp_report;
    # se re-sanitiza aqui como capa defensiva adicional (mismo helper de W4.1).
    payload = sanitize_for_report(payload, secret_values=secret_values)

    design = _load_design_files(project_id)
    requirement_spec = design.get("requirement_spec") or {}
    agent_design = design.get("agent_design_proposal") or {}
    corpus_manifest = design.get("corpus_manifest") or {}
    pending_documents = design.get("pending_documents") or {}

    meta = payload.get("meta", {}) or {}
    body_results, appendix_results = dedupe_last_by_test_id(payload.get("results_by_agent") or [])
    traceability = build_traceability_matrix(payload, design)

    pdf = _RobustPDF(format="A4", unit="mm")
    pdf.project_id = meta.get("project_id") or project_id
    pdf.gen_date = (meta.get("generated_at") or "")[:19].replace("T", " ")
    # Sin compresion: permite verificar contenido (secciones, ausencia de
    # secretos) con `strings` sobre el PDF, tal como exige la evidencia GMP.
    pdf.compress = False
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── SECCION 1 — Portada ──
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 14, _safe("Informe de Evaluacion Funcional GMP"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, _safe("Version del informe: robusto (W4.1.1)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    for label, key in [
        ("Mision", "project_id"), ("Cliente", "client_type"),
        ("RC canonico", "canonical_rc"), ("Fecha de generacion", "generated_at"),
        ("Estado deployment", "deployment_status"),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, _safe(f"{label}:"))
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, _safe(_s(meta.get(key))), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_fill_color(235, 245, 235)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 90, 30)
    pdf.multi_cell(
        0, 6,
        _safe("Evidencia real, no fabricada. Los datos faltantes se muestran como \"no disponible\"."),
        fill=True,
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_fill_color(250, 240, 220)
    pdf.set_text_color(120, 70, 0)
    pdf.multi_cell(
        0, 6,
        _safe("Este informe no reemplaza la decision QA/QC ni libera lotes automaticamente."),
        fill=True,
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # ── SECCION 2 — Resumen ejecutivo ──
    _h1(pdf, "Resumen ejecutivo")
    _p(pdf, _s(payload.get("executive_summary")))
    ae = payload.get("agents_evaluated", {}) or {}
    total_tests = sum(len(b["tests"]) for b in body_results)
    total_pass = sum(1 for b in body_results for t in b["tests"] if t.get("result") == "PASS")
    total_fail = sum(1 for b in body_results for t in b["tests"] if t.get("result") in ("FAIL", "ERROR"))
    pending_entries = pending_documents.get("documents", pending_documents.get("pending", [])) or []
    _p(
        pdf,
        f"Agentes evaluados: {ae.get('total', 0)}. Pruebas funcionales unicas (deduplicadas): {total_tests} "
        f"({total_pass} PASS, {total_fail} FAIL/ERROR). Estado deployment: {_s(meta.get('deployment_status'))}. "
        f"Pendientes regulatorios abiertos: {len(pending_entries)}.",
        size=8.5,
    )

    # ── SECCION 3 — Introduccion de la mision ──
    _h1(pdf, "Introducción de la misión")
    mission_objective = payload.get("mission_objective", {}) or {}
    _p(pdf, _s(mission_objective.get("task_summary")) if mission_objective.get("task_summary") not in (None, "no_disponible") else _s(requirement_spec.get("raw_objective")))
    _p(pdf, "Roles del sistema que participaron en la creacion y operacion de esta mision:", bold=True, size=9)
    for role, desc in _ROLE_DESCRIPTIONS.items():
        _p(pdf, f"{role}: {desc}", size=8.5)

    # ── SECCION 4 — Objetivo detallado + tabla trazabilidad ──
    _h1(pdf, "Objetivo detallado de la misión creada")
    _p(pdf, _s(payload.get("executive_summary")), size=8.5)
    _p(
        pdf,
        "La mision OOS/HPLC transforma una necesidad de laboratorio de control de calidad en una "
        "solucion de agentes especializados que apoyan (sin reemplazar) al analista y a QA/QC: cada "
        "objetivo regulatorio identificado en el diseno se conecta con un agente responsable, una "
        "prueba funcional del catalogo curado y un resultado real medido.",
        size=8.5,
    )
    _h2(pdf, "Trazabilidad objetivo-agente-evidencia")
    _table(
        pdf,
        ["Objetivo", "Agente", "Funcion esperada", "Prueba", "Resultado", "Evidencia", "Interpretacion GMP"],
        [[r["objective"], r["agent"], r["function"], r["test_id"], r["result"], r["evidence_source"], r["gmp_interpretation"]] for r in traceability],
        [26, 22, 32, 22, 16, 30, 42],
    )

    # ── SECCION 5 — Caso farmaceutico planteado ──
    _h1(pdf, "Caso farmacéutico planteado")
    pharma_case = payload.get("pharma_case")
    if isinstance(pharma_case, dict):
        _p(pdf, _s(pharma_case.get("raw_objective")))
        if pharma_case.get("domains"):
            _p(pdf, "Dominios: " + ", ".join(pharma_case["domains"]), size=8.5)
        if pharma_case.get("client_needs"):
            _p(pdf, "Necesidades del cliente:", bold=True, size=8.5)
            _bullets(pdf, pharma_case["client_needs"], size=8.5)
    else:
        _p(pdf, _s(pharma_case))
    _p(
        pdf,
        "Flujo esperado del caso: recepcion del resultado analitico -> comparacion contra "
        "especificacion -> deteccion preliminar OOS/no-OOS -> revision de parametros HPLC "
        "(SST, integracion de picos, RSD) -> validacion de integridad de datos (ALCOA+) -> "
        "generacion de evidencia auditada -> apoyo a la disposicion final humana (QA/QC).",
        size=8.5,
    )

    # ── SECCION 6 — Objetivos funcionales ──
    _h1(pdf, "Objetivos funcionales de la misión")
    _table(
        pdf,
        ["Objetivo", "Agente", "Evidencia", "Resultado", "Estado"],
        [[r["objective"], r["agent"], r["evidence_source"], r["result"], r["status"]] for r in traceability],
        [50, 30, 45, 25, 40],
    )

    # ── SECCION 7 — Agentes creados o reutilizados ──
    _h1(pdf, "Agentes creados o reutilizados")
    tests_by_agent = {b["agent_id"]: b["tests"] for b in body_results}
    agents_list = agent_design.get("agents") or []
    if not agents_list:
        _p(pdf, _NO_DATA)
    for agent in agents_list:
        aid = agent.get("agent_id", "?")
        decision = agent.get("decision")
        tipo = "perfil heredado" if decision == "profile" else ("agente nuevo" if decision == "new_agent" else _s(decision))
        _p(pdf, f"{aid} ({tipo})", bold=True, size=10)
        _p(pdf, _s(agent.get("rationale")), size=8.5)
        if agent.get("base_agent"):
            _p(pdf, f"Perfil base: {agent.get('base_agent')}", size=8)
        tests = tests_by_agent.get(aid)
        if tests:
            passed = sum(1 for t in tests if t.get("result") == "PASS")
            _p(pdf, f"Pruebas que lo validaron: {len(tests)} ({passed} PASS). " + ", ".join(t.get("test_id", "?") for t in tests), size=8)
        else:
            _p(pdf, "sin pruebas funcionales ejecutadas para este agente", size=8)
        pdf.ln(1)

    # ── SECCION 8 — Resultados de pruebas funcionales por agente (cuerpo deduplicado) ──
    _h1(pdf, "Resultados de pruebas funcionales por agente")
    if not body_results:
        _p(pdf, "No se han ejecutado pruebas funcionales aun para esta mision.")
    for block in body_results:
        _p(pdf, block.get("agent_id", "?"), bold=True, size=10.5)
        for t in block.get("tests", []):
            _p(pdf, _test_narrative(t), size=8.3)
        pdf.ln(1)

    # ── SECCION 9 — Interpretacion por agente ──
    _h1(pdf, "Interpretación por agente")
    for agent in agents_list:
        aid = agent.get("agent_id", "?")
        tests = tests_by_agent.get(aid)
        _p(pdf, aid, bold=True, size=10)
        if tests:
            passed = sum(1 for t in tests if t.get("result") == "PASS")
            failed = sum(1 for t in tests if t.get("result") in ("FAIL", "ERROR"))
            _p(
                pdf,
                f"El agente ejecuto {len(tests)} prueba(s) funcional(es) real(es): {passed} PASS, {failed} FAIL/ERROR. "
                f"Esto demuestra {'cumplimiento' if failed == 0 else 'cumplimiento parcial'} del rol declarado "
                f"({_s(agent.get('rationale'))[:180]}). En operacion real apoyaria a QA/QC dentro de su dominio, "
                "sin tomar la decision final. Limite: la evaluacion se basa en el catalogo curado disponible, "
                "no en datos productivos.",
                size=8.3,
            )
        else:
            _p(
                pdf,
                f"Rol diseñado: {_s(agent.get('rationale'))[:220]}. Aun no evaluado funcionalmente: "
                "no hay pruebas ejecutadas registradas para este agente.",
                size=8.3,
            )

    # ── SECCION 10 — Funcionamiento operativo esperado (7x24) ──
    _h1(pdf, "Funcionamiento operativo esperado (7x24)")
    _p(
        pdf,
        "En una operacion productiva madura, los agentes de esta mision podrian operar de forma "
        "continua (7x24) monitoreando resultados analiticos entrantes desde LIMS/API/archivos, "
        "preclasificando resultados como OOS/no-OOS, revisando parametros HPLC (SST/picos/RSD), "
        "validando ALCOA+ sobre los registros, priorizando casos criticos, generando alertas y "
        "evidencia auditada, y escalando a QA/QC para la decision final. El sistema no toma la "
        "decision final de forma autonoma; toda su actividad queda trazada en el registro de auditoria.",
        size=8.5,
    )
    _p(pdf, "Requisitos operativos antes de uso productivo:", bold=True, size=9)
    _bullets(pdf, [
        "Integracion validada con LIMS/CDS de produccion (no simulada).",
        "Roles, permisos y firma electronica conforme 21 CFR Part 11.",
        "Validacion de sistemas computarizados (CSV) del entorno productivo.",
        "SOP documentado del flujo OOS/HPLC/ALCOA+ y aprobacion de QA.",
        "Corpus regulatorio completo (no PENDING_DOCUMENT).",
        "Pruebas con datos reales o representativos del proceso.",
        "Control de cambios formal sobre agentes y catalogo de pruebas.",
    ], size=8.3)

    # ── SECCION 11 — Flujo operativo propuesto ──
    _h1(pdf, "Flujo operativo propuesto")
    _bullets(pdf, [
        "1. Resultado HPLC ingresa al sistema (LIMS/API/archivo).",
        "2. qa_oos_profile evalua el resultado contra especificacion (OOS/in-spec).",
        "3. hplc_data_review_agent revisa SST, RSD y anomalias cromatograficas.",
        "4. integrity_lims_profile valida atributos ALCOA+ del registro.",
        "5. El sistema genera alerta y evidencia trazable (audit trail).",
        "6. QA/QC revisa la evidencia generada.",
        "7. QA/QC decide investigacion / retest / rechazo / liberacion segun SOP.",
        "8. La decision y su evidencia quedan registradas en el audit trail.",
    ], size=8.3)
    _p(pdf, "La ejecucion real de este flujo requiere el ambiente productivo descrito en la Seccion 10 (integracion LIMS/CDS, roles, SOP, corpus regulatorio completo).", size=8)

    # ── SECCION 12 — Reglas Python vs Ollama local ──
    _h1(pdf, "Reglas Python vs Ollama local")
    rv = payload.get("rules_vs_llm", {}) or {}
    any_llm_used = any(t.get("uses_llm") for b in body_results for t in b.get("tests", []))
    if not any_llm_used:
        _p(
            pdf,
            "El catalogo evaluado en este informe contiene pruebas funcionales deterministicas "
            "ejecutadas por reglas Python. La capacidad LLM/Ollama local puede existir como funcion "
            "separada de consulta o interpretacion, pero no fue ejecutada dentro del conjunto de "
            "pruebas resumido en este PDF. Por tanto, este informe no atribuye resultados funcionales al LLM.",
            size=8.5,
        )
    else:
        for block in body_results:
            for t in block.get("tests", []):
                if t.get("uses_llm"):
                    ev = t.get("llm_evidence") or {}
                    _p(
                        pdf,
                        f"{t.get('test_id')} — endpoint: {t.get('endpoint')}, model: {_s(ev.get('model'))}, "
                        f"elapsed_seconds: {_s(ev.get('elapsed_seconds'))}, used_llm: true, "
                        f"ollama_status: {_s(ev.get('ollama_status'))}.",
                        size=8,
                    )
    _p(pdf, "Endpoints deterministicos: " + (", ".join(rv.get("deterministic_endpoints") or []) or _NO_DATA), size=7.5)
    _p(pdf, "Endpoints LLM local: " + (", ".join(rv.get("llm_endpoints") or []) or _NO_DATA), size=7.5)

    # ── SECCION 13 — Auditoria y trazabilidad (ampliada) ──
    _h1(pdf, "Auditoría y trazabilidad")
    at = payload.get("audit_traceability", {}) or {}
    _p(pdf, f"RC canonico: {_s(at.get('canonical_rc'))}")
    _p(pdf, f"sha256: {_s(at.get('rc_sha256'))}", size=8.5)
    _p(pdf, f"Eventos de prueba registrados: {at.get('test_events_count', 0)}", size=8.5)
    events = at.get("last_audit_events") or []
    if events:
        _h2(pdf, "Ultimos eventos relevantes")
        rows = []
        for e in events[:10]:
            data = e.get("data") or {}
            rows.append([
                e.get("event_type"), e.get("timestamp"),
                data.get("run_by") or data.get("record_by") or _NO_DATA,
            ])
        _table(pdf, ["Evento", "Timestamp", "Usuario/run_by"], rows, [70, 60, 60])
    else:
        _p(pdf, _NO_DATA, size=8.5)
    _p(pdf, "La auditoria soporta trazabilidad pero no sustituye validacion regulatoria completa.", size=8)

    # ── SECCION 14 — Limitaciones ──
    _h1(pdf, "Limitaciones")
    _bullets(pdf, payload.get("limitations"), size=8.5)
    limitations_yaml = design.get("compliance_assessment") or {}
    if limitations_yaml.get("limitations"):
        _bullets(pdf, limitations_yaml["limitations"], size=8.5)
    if corpus_manifest.get("collections"):
        pending_collections = [c.get("name") for c in corpus_manifest["collections"] if c.get("status") == "pending"]
        if pending_collections:
            _p(pdf, "Colecciones de corpus pendientes de ingesta: " + ", ".join(pending_collections), size=8)

    # ── SECCION 15 — Pendientes antes de go-live ──
    _h1(pdf, "Pendientes antes de go-live")
    _bullets(pdf, payload.get("pending_before_golive"), size=8.5)
    _bullets(pdf, [
        "Cargar corpus regulatorio completo (resolver PENDING_DOCUMENT).",
        "Validar con datos representativos del proceso productivo.",
        "SOP formal, roles, firmas y permisos de produccion.",
        "Calificacion CSV/IQ/OQ/PQ del entorno si aplica.",
        "Pruebas de seguridad y aprobacion QA.",
        "Monitoreo y control de cambios activos.",
    ], size=8)

    # ── SECCION 16 — Impacto operativo esperado ──
    _h1(pdf, "Impacto operativo esperado")
    _p(pdf, _s(payload.get("operational_impact")), size=8.5)

    # ── SECCION 17 — Conclusion final robusta ──
    _h1(pdf, "Conclusión")
    _p(pdf, _s(payload.get("conclusion")), size=8.5)
    _p(pdf, _NO_REPLACE_CLAUSE, bold=True, size=9)

    # ── SECCION 18 — Anexo tecnico ──
    pdf.add_page()
    _h1(pdf, "Anexo técnico")
    _p(pdf, "Historial completo de ejecuciones (sin deduplicar), ordenado por test_id.", size=8)
    appendix_rows = []
    for block in appendix_results:
        aid = block.get("agent_id")
        for t in sorted(block.get("tests", []), key=lambda x: (x.get("test_id") or "", x.get("run_at") or "")):
            appendix_rows.append([
                t.get("test_id"), t.get("endpoint"), t.get("result"),
                str(t.get("relevant_datum"))[:60], t.get("run_by"), t.get("run_at"), aid,
            ])
    _table(
        pdf,
        ["test_id", "endpoint", "resultado", "recibido", "run_by", "run_at", "agente"],
        appendix_rows,
        [28, 42, 16, 40, 22, 30, 12],
        size=7,
    )

    out = pdf.output()
    return bytes(out)
