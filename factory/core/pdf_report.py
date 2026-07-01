"""
Renderiza el dict del agregador GMP (factory.api.routes.layer9._build_gmp_report)
como PDF profesional congelado (W4.1 / Tarea 3). Recibe el dict YA sanitizado —
este módulo no sanitiza, solo dibuja.
"""

from fpdf import FPDF, XPos, YPos


def _s(value, fallback="no disponible"):
    if value in (None, "", [], {}):
        return fallback
    return value


_PUNCT_MAP = str.maketrans({
    "→": "->", "←": "<-",  # → ←
    "–": "-", "—": "-",    # – —
    "‘": "'", "’": "'",    # ' '
    "“": '"', "”": '"',    # " "
    "…": "...",                 # …
})


def _safe(text) -> str:
    """Las fuentes core de fpdf2 (Helvetica) solo soportan cp1252. La
    puntuacion Unicode comun (flechas, guiones largos, comillas curvas) se
    normaliza a su equivalente ASCII antes de codificar; cualquier otro
    caracter fuera de charset se sustituye en vez de romper el PDF."""
    normalized = str(text).translate(_PUNCT_MAP)
    return normalized.encode("cp1252", errors="replace").decode("cp1252")


class _GmpReportPDF(FPDF):
    project_id = "misión"
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
    pdf.cell(0, 9, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(3)


def _p(pdf: FPDF, text, size: float = 9.5, bold: bool = False, color=(40, 40, 40)) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.2, _safe(text))
    pdf.ln(1)


def render_gmp_report_pdf(report: dict) -> bytes:
    """Construye el PDF a partir del MISMO dict que expone GET /gmp-report."""
    meta = report.get("meta", {}) or {}
    project_id = meta.get("project_id") or "misión"

    pdf = _GmpReportPDF(format="A4", unit="mm")
    pdf.project_id = project_id
    pdf.gen_date = (meta.get("generated_at") or "")[:19].replace("T", " ")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── Portada ──
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 14, "Informe de Evaluacion Funcional GMP", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    for label, key in [
        ("Mision", "project_id"), ("Cliente", "client_type"),
        ("RC canonico", "canonical_rc"), ("Generado", "generated_at"),
        ("Estado deployment", "deployment_status"),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, f"{label}:")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, _safe(_s(meta.get(key))), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_fill_color(235, 245, 235)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 90, 30)
    pdf.multi_cell(
        0, 6,
        "  Evidencia real, no fabricada. Los datos faltantes se muestran como "
        "\"no disponible\".",
        fill=True,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    _h1(pdf, "Resumen ejecutivo")
    _p(pdf, _s(report.get("executive_summary")))

    _h1(pdf, "Objetivo de la mision")
    mo = report.get("mission_objective", {}) or {}
    _p(pdf, _s(mo.get("objective")))
    if mo.get("regulatory_scope"):
        _p(pdf, "Alcance regulatorio: " + ", ".join(mo["regulatory_scope"]))

    _h1(pdf, "Caso farmaceutico planteado")
    pc = report.get("pharma_case")
    if isinstance(pc, dict):
        _p(pdf, _s(pc.get("raw_objective")))
        if pc.get("domains"):
            _p(pdf, "Dominios: " + ", ".join(pc["domains"]), size=8.5)
    else:
        _p(pdf, _s(pc))

    _h1(pdf, "Agentes evaluados")
    ae = report.get("agents_evaluated", {}) or {}
    _p(pdf, "Perfiles heredados: " + (", ".join(ae.get("profiles_inherited") or []) or "no disponible"))
    _p(pdf, "Agentes nuevos: " + (", ".join(ae.get("new_agents") or []) or "no disponible"))
    _p(pdf, f"Total: {ae.get('total', 0)}")

    _h1(pdf, "Pruebas PASS/FAIL por agente")
    rba = report.get("results_by_agent") or []
    if not rba:
        _p(pdf, "No se han ejecutado pruebas funcionales aun para esta mision.")
    for block in rba:
        _p(pdf, block.get("agent_id", "?"), bold=True, size=10.5)
        for t in block.get("tests", []):
            line = f"[{t.get('result')}] {t.get('title') or t.get('test_id')} - {t.get('endpoint')}"
            _p(pdf, line, size=8.5)
        pdf.ln(1)

    _h1(pdf, "Interpretacion farmaceutica")
    for line in (report.get("pharma_interpretation") or ["no disponible"]):
        _p(pdf, "- " + str(line))

    _h1(pdf, "Implicacion GMP (OOS / HPLC / ALCOA+)")
    gi = report.get("gmp_implication", {}) or {}
    for key, label in [("oos", "OOS"), ("hplc", "HPLC/SST"), ("alcoa", "ALCOA+")]:
        _p(pdf, f"{label}: {_s(gi.get(key))}")

    _h1(pdf, "Uso de reglas Python vs Ollama local")
    rv = report.get("rules_vs_llm", {}) or {}
    _p(pdf, _s(rv.get("explanation")))
    _p(pdf, "Endpoints deterministicos: " + (", ".join(rv.get("deterministic_endpoints") or []) or "no disponible"), size=8.5)
    _p(pdf, "Endpoints LLM local: " + (", ".join(rv.get("llm_endpoints") or []) or "no disponible"), size=8.5)

    _h1(pdf, "Auditoria y trazabilidad")
    at = report.get("audit_traceability", {}) or {}
    _p(pdf, f"RC canonico: {_s(at.get('canonical_rc'))}")
    _p(pdf, f"Eventos de prueba registrados: {at.get('test_events_count', 0)}")

    _h1(pdf, "Limitaciones")
    for line in (report.get("limitations") or ["no disponible"]):
        _p(pdf, "- " + str(line))

    _h1(pdf, "Pendientes antes de go-live")
    for line in (report.get("pending_before_golive") or ["no disponible"]):
        _p(pdf, "- " + str(line))

    _h1(pdf, "Impacto operativo esperado")
    _p(pdf, _s(report.get("operational_impact")), size=8.5)

    _h1(pdf, "Conclusion")
    _p(pdf, _s(report.get("conclusion")), size=8.5)

    out = pdf.output()
    return bytes(out)
