"""
GMPAI — Renderiza PDF a partir de los dicts de gmpai_artifact_service:
build_final_report_data() y build_remediation_tracker_data(). Mismo patrón
de core/pdf_report.py (fpdf2, charset cp1252 con normalización de unicode
común). Este módulo no calcula nada — solo dibuja lo que ya viene agregado.
"""

from __future__ import annotations

from fpdf import FPDF, XPos, YPos

_PUNCT_MAP = str.maketrans({
    "→": "->", "←": "<-",
    "–": "-", "—": "-",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "…": "...",
})


def _safe(text) -> str:
    normalized = str(text).translate(_PUNCT_MAP)
    return normalized.encode("cp1252", errors="replace").decode("cp1252")


def _s(value, fallback="no disponible"):
    if value in (None, "", [], {}):
        return fallback
    return value


class _GmpaiPDF(FPDF):
    title_footer = "GMPAI Document Validation"
    gen_date = ""

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            _safe(
                f"{self.title_footer} . generado {self.gen_date} . "
                f"Evaluacion asistida, no aprobacion GMP automatica . pagina {self.page_no()}/{{nb}}"
            ),
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


def _kv(pdf: FPDF, label: str, value, label_w: float = 48) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(label_w, 6, _safe(f"{label}:"), new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 6, _safe(_s(value)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _warn_banner(pdf: FPDF, text: str) -> None:
    pdf.set_fill_color(255, 244, 224)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(140, 90, 10)
    pdf.multi_cell(0, 5.5, "  " + _safe(text), fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


# ── Tracker de remediaciones ─────────────────────────────────────────────────

def build_remediation_tracker_pdf(data: dict) -> bytes:
    pdf = _GmpaiPDF(format="A4", unit="mm")
    pdf.title_footer = "GMPAI Remediation Tracker"
    pdf.gen_date = (data.get("generated_at") or "")[:19].replace("T", " ")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 14, _safe("GMPAI Remediation Tracker"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    _kv(pdf, "Proyecto", data.get("project_id"))
    _kv(pdf, "Generado", pdf.gen_date)
    pdf.ln(4)

    items = data.get("items", [])
    if not items:
        _p(pdf, "Sin items de remediacion registrados.")

    for item in items:
        _h1(pdf, f"{item['id']} — {item['sistema']}")
        _kv(pdf, "Estado", item.get("estado"))
        _kv(pdf, "Clasificacion", item.get("clasificacion"))
        _kv(pdf, "Severidad", item.get("severidad"))
        _kv(pdf, "RC relacionado", item.get("rc_relacionado"))
        _kv(pdf, "Finding relacionado", item.get("finding_relacionado"))
        pdf.ln(2)

        _h2(pdf, "Hallazgo")
        _p(pdf, item.get("hallazgo"))

        _h2(pdf, "Impacto")
        _p(pdf, item.get("impacto"))

        _h2(pdf, "Evidencia revisada")
        for e in item.get("evidencia_revisada", []):
            _p(pdf, "- " + e, size=8.5)

        _h2(pdf, "Accion requerida")
        for a in item.get("accion_requerida", []):
            _p(pdf, "- " + a, size=8.5)

        _kv(pdf, "Responsable propuesto", item.get("responsable_propuesto"))
        _kv(pdf, "Fecha objetivo", item.get("fecha_objetivo"))

        _h2(pdf, "Criterio de cierre")
        for c in item.get("criterio_cierre", []):
            _p(pdf, "- " + c, size=8.5)

        _warn_banner(pdf, item.get("notas", ""))
        pdf.ln(3)

    out = pdf.output()
    return bytes(out)


# ── Informe final de validación documental ──────────────────────────────────

def build_final_report_pdf(data: dict) -> bytes:
    pdf = _GmpaiPDF(format="A4", unit="mm")
    pdf.title_footer = f"GMPAI Document Validation — {data['project']['project_id']}"
    pdf.gen_date = (data.get("generated_at") or "")[:19].replace("T", " ")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    proj = data["project"]
    rc = data["rc_canonical"]

    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 13, _safe("GMPAI Document Validation — Informe Final"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    _kv(pdf, "Mision", proj.get("project_id"))
    _kv(pdf, "Cliente", proj.get("client_type"))
    _kv(pdf, "RC canonico", rc.get("rc_id"))
    _kv(pdf, "Aprobado por", rc.get("approved_by"))
    _kv(pdf, "Marcado canonico por", rc.get("marked_canonical_by"))
    _kv(pdf, "Generado", pdf.gen_date)
    pdf.ln(3)

    _warn_banner(pdf, "Este resultado es una EVALUACION ASISTIDA por agentes de IA, "
                       "NO una aprobacion GMP automatica. Ver Conclusion.")

    _h1(pdf, "1. Objetivo y alcance de la mision")
    _p(pdf, proj.get("objective"))
    _p(pdf, "Alcance regulatorio: " + ", ".join(proj.get("regulatory_scope", [])), size=8.5)
    pdf.ln(1)
    scope = data["scope"]
    _kv(pdf, "Documentos declarados", scope.get("total_documents_declared"))
    _kv(pdf, "Rockwell", scope.get("rockwell_documents"))
    _kv(pdf, "SCADA", scope.get("scada_documents"))
    _kv(pdf, "Con findings de cumplimiento", ", ".join(scope.get("documents_with_compliance_findings", [])))
    pdf.ln(1)
    _warn_banner(pdf, scope.get("limitation", ""))

    _h1(pdf, "2. Inventario documental")
    inv = data["inventory"]["totals"]
    _kv(pdf, "Archivos inventariados", inv.get("files_inventoried"))
    _kv(pdf, "Hash coincidente", inv.get("hash_matches"))
    _kv(pdf, "Hash NO coincidente", inv.get("hash_mismatches"))
    _kv(pdf, "Extraccion OK", inv.get("extraction_ok"))
    _kv(pdf, "Extraccion fallida", inv.get("extraction_failed"))
    _kv(pdf, "Grupos duplicados exactos", inv.get("exact_duplicate_groups"))
    _kv(pdf, "Familias documentales", inv.get("families_count"))
    _kv(pdf, "Conflictos de version", inv.get("version_conflicts"))
    pdf.ln(2)

    _h2(pdf, "Lista completa de documentos declarados (32)")
    for d in data["inventory"]["all_declared_documents"]:
        _p(pdf, "- " + d, size=7.5)

    _h1(pdf, "3. Seleccion de versiones y conflictos")
    vc = data.get("version_conflicts", [])
    if not vc:
        _p(pdf, "Sin conflictos de version detectados.")
    for c in vc:
        _p(pdf, f"Familia: {c['family_key']}", bold=True, size=9)
        _p(pdf, "Miembros: " + ", ".join(c.get("members", [])), size=8)
        _p(pdf, "Motivo: " + _s(c.get("conflict_reason")), size=8)
        pdf.ln(1)

    _h1(pdf, "4. Agentes evaluados y version")
    for aid, meta in data["agents"].items():
        _p(pdf, aid, bold=True, size=10)
        _kv(pdf, "  agent_version", meta.get("agent_version"), label_w=55)
        _kv(pdf, "  prompt_version", meta.get("prompt_version"), label_w=55)
        _kv(pdf, "  modelo Ollama", meta.get("model"), label_w=55)
        _kv(pdf, "  verifier_version", meta.get("verifier_version"), label_w=55)
        _kv(pdf, "  findings generados", meta.get("findings_count"), label_w=55)
        pdf.ln(1)

    _h1(pdf, "4b. Estado real de ejecucion por agente (no confundir con findings)")
    _p(pdf, "Los findings de la seccion 4 son el RESULTADO de una ejecucion, no la ejecucion "
            "en si. Esta seccion clasifica cada agente segun evidencia de runtime real "
            "(no autodeclarada): EXECUTED_VERIFIED requiere run_id+task_id+timestamps+log "
            "por ejecucion; RESULT_RECOVERED significa que el resultado es real y "
            "verificable pero sin esa metadata individual; CONFIGURED_ONLY significa que "
            "no hay evidencia de ejecucion.", size=8)
    aes = data.get("agent_execution_summary", {})
    _kv(pdf, "EXECUTED_VERIFIED", aes.get("executed_verified", 0))
    _kv(pdf, "RESULT_RECOVERED", aes.get("result_recovered", 0))
    _kv(pdf, "CONFIGURED_ONLY", aes.get("configured_only", 0))
    _kv(pdf, "FAILED", aes.get("failed", 0))
    pdf.ln(1)
    for row in data.get("agent_execution_status", []):
        _p(pdf, f"{row['agent_id']} — {row['estado_evidencia']}", bold=True, size=9)
        _p(pdf, f"  {row['funcion']}", size=7.8, color=(90, 90, 90))
        _kv(pdf, "  modelo/regla", row.get("modelo_o_regla"), label_w=55)
        _kv(pdf, "  llamadas reales detectadas", row.get("llamadas_reales_detectadas"), label_w=55)
        _kv(pdf, "  llamadas fallback (sin texto)", row.get("llamadas_fallback_sin_texto"), label_w=55)
        _kv(pdf, "  documentos asignados", row.get("documentos_asignados"), label_w=55)
        _kv(pdf, "  findings producidos", row.get("findings_producidos"), label_w=55)
        _p(pdf, "  " + row.get("justificacion", ""), size=7.2, color=(90, 90, 90))
        pdf.ln(1)

    _h1(pdf, "5. Resultados por estado (findings de cumplimiento)")
    fs = data["findings_by_status"]
    for st in ("cumple", "cumple_parcialmente", "no_cumple", "evidencia_insuficiente", "no_aplica"):
        _kv(pdf, st, fs.get(st, 0))
    _kv(pdf, "TOTAL findings", data.get("findings_total", 0))
    pdf.ln(2)

    _h1(pdf, "6. Matrices de cumplimiento por agente")
    for aid, rows in data["matrices"].items():
        _h2(pdf, aid)
        for r in rows[:25]:
            line = f"[{r['estado']} | {r['severidad']}] {r['documento'][:70]}"
            _p(pdf, line, size=7.8)
            _p(pdf, "  requisito: " + _s(r.get("requisito_regulatorio", ""))[:120], size=7.2, color=(90, 90, 90))
            if r.get("brecha"):
                _p(pdf, "  brecha: " + str(r["brecha"])[:150], size=7.2, color=(150, 60, 30))
        if len(rows) > 25:
            _p(pdf, f"... y {len(rows) - 25} findings adicionales (ver compliance_matrices/{aid}.json)", size=7.5)
        pdf.ln(2)

    _h1(pdf, "6b. Matriz finding -> correccion (resumen)")
    fcs = data.get("finding_correction_summary", {})
    _p(pdf, "Clasificacion determinista (sin reprocesar nada) de los findings reales en: "
            "correccion generable (no_cumple/cumple_parcialmente, con recomendacion "
            "trazable del propio agente), evidencia requerida (evidencia_insuficiente — "
            "nunca se inventan hechos), o decision humana. Matriz completa en "
            "compliance_matrices/finding_correction_matrix.json.", size=8)
    _kv(pdf, "Findings totales", fcs.get("findings_totales", 0))
    _kv(pdf, "Documentos afectados", fcs.get("documentos_afectados", 0))
    _kv(pdf, "Corregibles (propuesta generable)", fcs.get("corregibles", 0))
    _kv(pdf, "Evidencia requerida", fcs.get("evidencia_requerida", 0))
    _kv(pdf, "No aplica (requiere justificacion)", fcs.get("no_aplica_requiere_justificacion", 0))
    _kv(pdf, "Decision humana requerida", fcs.get("decision_humana_requerida", 0))
    pdf.ln(2)

    _h1(pdf, "7. Top riesgos (no_cumple / cumple_parcialmente, priorizados)")
    for r in data.get("top_risks", []):
        _p(pdf, f"[{r['severidad']}] {r['agente_responsable']} — {r['documento'][:80]}", bold=True, size=8.5)
        _p(pdf, "Riesgo: " + _s(r.get("riesgo", "")), size=7.8)
        _p(pdf, "Recomendacion: " + _s(r.get("recomendacion", "")), size=7.8)
        pdf.ln(1)

    _h1(pdf, "8. Remediaciones abiertas")
    for item in data.get("remediation_items", []):
        _p(pdf, f"{item['id']} [{item['estado']}] — {item['hallazgo']}", size=8.5)

    _h1(pdf, "9. Decisiones humanas (historial de RCs)")
    for h in data.get("rc_history", []):
        canon = " (CANONICO)" if h.get("is_canonical") else ""
        _p(pdf, f"{h['version']} — {h['rc_id']}{canon}: {h['status']} por {_s(h.get('approved_by'))}", size=8)

    _h1(pdf, "10. Limitaciones declaradas")
    for l in data.get("limitations", []):
        _p(pdf, "- " + l, size=8.5)

    _h1(pdf, "11. Hashes de evidencia (RC canonico)")
    for fname, sha in rc.get("sha256sums", {}).items():
        _p(pdf, f"{fname}: {sha}", size=7.5)

    _h1(pdf, "12. Gobernanza")
    _p(pdf, data.get("governance_statement", ""), size=8.5)

    _h1(pdf, "13. Conclusion")
    pdf.set_fill_color(235, 245, 235)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 90, 30)
    pdf.multi_cell(0, 6, "  " + _safe(data.get("conclusion", "")), fill=True)
    pdf.set_text_color(0, 0, 0)

    out = pdf.output()
    return bytes(out)
