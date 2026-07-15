"""
GMPAI — Readiness de correccion por documento (13 Rockwell restantes tras el
piloto sobre "215115305-T-041 SAT3 Completed.pdf") y matriz de aplicabilidad
por tipo documental.

Este modulo es puramente de CLASIFICACION sobre datos ya existentes del RC
canonico (pipeline_pilot_llm.json vía gmpai_artifact_service). No reprocesa
documentos, no invoca agentes. SCADA queda fuera (18/32 documentos, sin
findings de cumplimiento en este RC — no forma parte de este analisis).

Aplicabilidad regulatoria por tipo documental (ver seccion 2 del encargo):
juicio razonado, NO una determinacion regulatoria autoritativa — requiere
confirmacion de QA/Validacion. Los checkpoints de ALCOA+ (atributos de un
REGISTRO: quien/cuando/original/exacto) aplican con fuerza a documentos que
son registros de ejecucion (SAT, protocolos completados), y con mucha menos
fuerza a documentos de diseno estatico (arquitectura, narrativas de control,
listados de alarmas) que no son "registros" en el sentido GxP.
"""

from __future__ import annotations

PILOTED_DOCUMENT = "215115305-T-041 SAT3 Completed.pdf"

# doc_type -> (part11_aplica, annex11_aplica, alcoa_aplica, nota)
APPLICABILITY_BY_DOC_TYPE = {
    "URS": (True, True, "parcial", "Debe ESPECIFICAR requisitos de Part11/Annex11/ALCOA+ a implementar, no demostrarlos ejecutados."),
    "FS": (True, True, "parcial", "Debe describir COMO se implementan los controles; no es evidencia de ejecucion real."),
    "DS": (True, True, "parcial", "Diseno detallado; misma logica que FS."),
    "ARCHITECTURE": ("parcial", True, False, "Topologia/seguridad de red si aplica (Annex11); ALCOA+ no aplica (no es un registro)."),
    "CONTROL_NARRATIVE": ("parcial", "parcial", False, "Describe logica de control, no genera registros GxP evaluables por ALCOA+."),
    "ALARM_IO_LISTING": (False, "parcial", False, "Lista de puntos I/O — no es un sistema con firma electronica ni un registro; ALCOA+ es un error de categoria aqui."),
    "SAT": (True, True, True, "Registro de ejecucion real de pruebas — los 3 marcos aplican con fuerza plena."),
    "PROTOCOL_TEMPLATE": (True, True, True, "Protocolo IQ/OQ/PQ — mismo nivel que SAT, ausente en este corpus (REM-GMPAI-001)."),
    "TRANSMITTAL": (False, False, False, "Documento de transmision/tapa — no contiene controles evaluables."),
    "REPORT": ("depende", "depende", "depende", "Depende del contenido real del reporte (resultados vs narrativa)."),
    "OTHER": ("no_determinado", "no_determinado", "no_determinado", "Tipo no identificado con confianza — requiere clasificacion manual antes de evaluar aplicabilidad."),
}


def applicability_matrix() -> list[dict]:
    return [
        {"tipo_documental": t, "part11_aplica": p11, "annex11_aplica": a11, "alcoa_aplica": alc, "nota": nota}
        for t, (p11, a11, alc, nota) in APPLICABILITY_BY_DOC_TYPE.items()
    ]


def _is_scanned(chars: int, pages: int) -> bool:
    return pages > 0 and (chars / pages) < 50


def build_readiness_matrix(pdata: dict) -> list[dict]:
    """pdata: pipeline_pilot_llm.json ya cargado (via
    gmpai_artifact_service.load_canonical_pipeline_data()[1]) — no relee
    disco. Excluye SCADA (no tiene records/classifications en este RC) y el
    documento ya piloteado."""
    version_by_path = {}
    for v in pdata.get("version_decisions", []):
        for m in v.get("members", []):
            version_by_path[m] = v

    findings_by_doc: dict[str, list[dict]] = {}
    for f in pdata.get("findings", []):
        if f["agente_responsable"] == "requirements_traceability_agent":
            continue
        findings_by_doc.setdefault(f["documento"], []).append(f)

    rows = []
    for r in pdata.get("records", []):
        fn = r["filename"]
        if fn == PILOTED_DOCUMENT:
            continue
        rel = r["relative_path"]
        cls = pdata.get("classifications", {}).get(rel, {})
        chars = r["text_chars"]
        pages = r["page_or_sheet_count"]
        scanned = _is_scanned(chars, pages)
        over_limit = chars > 6000
        pct_analyzed = round(min(6000, chars) / chars * 100, 1) if chars else 0.0
        vd = version_by_path.get(rel, {})
        doc_findings = findings_by_doc.get(fn, [])
        by_status: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        for f in doc_findings:
            by_status[f["estado"]] = by_status.get(f["estado"], 0) + 1
            by_agent[f["agente_responsable"]] = by_agent.get(f["agente_responsable"], 0) + 1

        doc_type = cls.get("doc_type", "OTHER")
        applicability = APPLICABILITY_BY_DOC_TYPE.get(doc_type, APPLICABILITY_BY_DOC_TYPE["OTHER"])
        applicability_uncertain = applicability[0] in (False, "parcial", "no_determinado") or \
            applicability[2] in (False, "parcial", "no_determinado")
        # "no aplica duro": el tipo documental esta bien clasificado (alta
        # confianza) Y al menos un marco es HARD False (no "parcial") — mas
        # fuerte que una simple ambiguedad de aplicabilidad.
        hard_not_applicable = (
            cls.get("confidence") is not None and cls.get("confidence", 0) >= 0.9
            and (applicability[0] is False or applicability[2] is False)
        )

        decision, reasons = _decide_readiness(
            scanned=scanned, over_limit=over_limit, pct_analyzed=pct_analyzed,
            version_conflict=vd.get("version_conflict", False),
            classification_confidence=cls.get("confidence", 0.0),
            applicability_uncertain=applicability_uncertain,
            hard_not_applicable=hard_not_applicable,
        )

        rows.append({
            "nombre": fn,
            "version": rel.split("/")[-1],
            "sha256": r["sha256_computed"],
            "tipo_documental": doc_type,
            "clasificacion_confianza": cls.get("confidence"),
            "paginas": pages,
            "chars_extraidos": chars,
            "supera_6000_chars": over_limit,
            "truncado_por_max_doc_chars": over_limit,  # _MAX_DOC_CHARS=6000 sigue activo (no corregido en esta entrega)
            "pct_aproximado_analizado": pct_analyzed,
            "es_escaneado": scanned,
            "calidad_extraccion": "degradada_sin_texto_util" if scanned else (
                "aceptable" if r["extraction_ok"] else "fallida"),
            "agentes_que_analizaron": sorted(by_agent.keys()),
            "findings_por_agente": by_agent,
            "findings_por_clasificacion": by_status,
            "citas_pagina_seccion_disponibles": False,  # confirmado: 0 findings con cita real en todo el RC
            "texto_original_disponible": not scanned,
            "documento_donde_se_detecto": fn,
            "documento_destino_sugerido": fn if not scanned and applicability[0] not in (False,) else "no_determinado (revision humana)",
            "conflicto_de_version": vd.get("version_conflict", False),
            "decision_preparacion": decision,
            "motivos": reasons,
        })
    return rows


_READINESS_TO_CORRECTION_TYPE = {
    "OCR_OR_EXTRACTION_REQUIRED": "request_evidence",
    "REANALYSIS_REQUIRED": "human_decision_required",
    "NO_APPLICABLE_CORRECTION": "formal_justification",
    "DRAFT_READY": None,  # se decide por finding (classify_correction), no por documento
}


def build_finding_destination_matrix(pdata: dict, readiness_rows: list[dict]) -> list[dict]:
    """Extiende la matriz finding->correccion con source_document/
    target_document/correction_type para los 13 documentos Rockwell
    restantes (excluye el ya piloteado y SCADA). No reprocesa nada: es una
    clasificacion determinista sobre findings ya existentes + la matriz de
    aplicabilidad + el readiness por documento ya calculado arriba."""
    readiness_by_doc = {r["nombre"]: r for r in readiness_rows}
    out = []
    for f in pdata.get("findings", []):
        doc = f["documento"]
        if doc == PILOTED_DOCUMENT or doc not in readiness_by_doc:
            continue
        readiness = readiness_by_doc[doc]
        decision = readiness["decision_preparacion"]
        correction_type = _READINESS_TO_CORRECTION_TYPE.get(decision, "human_decision_required")
        if decision == "NO_APPLICABLE_CORRECTION":
            target = f"no_aplica a {readiness['tipo_documental']} (revisar si el requisito corresponde a otro documento/sistema)"
            reason = APPLICABILITY_BY_DOC_TYPE.get(readiness["tipo_documental"], APPLICABILITY_BY_DOC_TYPE["OTHER"])[3]
        elif decision == "OCR_OR_EXTRACTION_REQUIRED":
            target = doc
            reason = "documento sin texto util extraible — requiere extraccion/OCR confiable antes de evaluar el finding"
        elif decision == "REANALYSIS_REQUIRED":
            target = doc
            reason = "; ".join(readiness["motivos"]) or "requiere reanalisis antes de generar correccion"
        else:
            target = doc
            reason = "documento listo para correccion (ver matriz finding->correccion estandar)"

        out.append({
            "finding_id": f"{f['agente_responsable']}|{doc}|{f['requisito_regulatorio']}",
            "source_document": doc,
            "source_page_or_section": f.get("pagina_o_seccion") or "n/a",
            "target_document": target,
            "correction_type": correction_type,
            "reason": reason,
            "readiness_decision": decision,
            "estado_finding": f["estado"],
        })
    return out


def summarize_destination_matrix(rows: list[dict]) -> dict:
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["correction_type"]] = by_type.get(r["correction_type"], 0) + 1
    return {"total": len(rows), "por_correction_type": by_type}


def _decide_readiness(*, scanned: bool, over_limit: bool, pct_analyzed: float,
                       version_conflict: bool, classification_confidence: float,
                       applicability_uncertain: bool, hard_not_applicable: bool = False) -> tuple[str, list[str]]:
    reasons = []
    if scanned:
        reasons.append("documento sin texto util extraible (escaneado, findings via fallback sin llamada real al modelo)")
        return "OCR_OR_EXTRACTION_REQUIRED", reasons
    if hard_not_applicable:
        reasons.append("tipo documental bien identificado (confianza alta) pero 1+ marco regulatorio NO aplica "
                        "(error de categoria) — los findings contra ese marco son candidatos a falso positivo, "
                        "independientemente del truncamiento")
        return "NO_APPLICABLE_CORRECTION", reasons
    if applicability_uncertain and classification_confidence and classification_confidence < 0.99:
        reasons.append(f"tipo documental con aplicabilidad parcial/no determinada para 1+ de los 3 marcos evaluados")
    if version_conflict:
        reasons.append("conflicto de version sin resolver dentro de la misma familia documental — no se sabe cual version es vigente")
    if over_limit:
        reasons.append(f"solo ~{pct_analyzed}% del documento fue analizado (truncado por _MAX_DOC_CHARS=6000, sin corregir)")
    if classification_confidence is not None and classification_confidence < 0.6:
        reasons.append(f"clasificacion de tipo documental con confianza baja ({classification_confidence})")

    if version_conflict or over_limit or (classification_confidence is not None and classification_confidence < 0.6):
        return "REANALYSIS_REQUIRED", reasons
    if applicability_uncertain:
        reasons.append("1+ marco regulatorio no aplica claramente a este tipo documental — revisar findings antes de redactar")
        return "NO_APPLICABLE_CORRECTION", reasons
    return "DRAFT_READY", reasons
