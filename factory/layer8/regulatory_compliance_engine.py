"""
Capa 8 Tier-1 — Regulatory Compliance Engine.

Genera la matriz regulatoria, el corpus manifest y la evaluación de compliance.
REGLA DURA: nunca emite texto normativo largo.
validate_no_unsupported_regulatory_claims actúa como gate anti-texto-normativo:
si detecta un párrafo tipo CFR/FDA/USP/ICH, ABORTA y marca PENDING_DOCUMENT.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event
from factory.layer8.requirement_interpreter import RequirementSpec

# ── Patrones que indican texto normativo largo ─────────────────────────────────

_REGULATORY_TEXT_PATTERNS = [
    r"\b21\s+cfr\s+\d+\.\d+\b",                 # 21 CFR 211.68 etc.
    r"\bfda\s+(guidance|draft\s+guidance)\b",    # FDA guidance / draft guidance
    r"\busp\s+<\d+>\b",                          # USP <621> etc.
    r"\bich\s+q\d+",                             # ICH Q2 etc.
    r"\b(section|§)\s+\d+\.\d+(\.\d+)?\b",      # Section 211.68.1 etc.
    r"shall\s+be\s+\w+\s+in\s+accordance\s+with",  # frase normativa típica
    r"the\s+requirements\s+of\s+(21\s+cfr|usp|ich|fda)",
]

_MIN_PARAGRAPH_LENGTH = 120  # caracteres — umbral para considerar "párrafo largo"


class RegulatoryTextDetected(Exception):
    """Lanzada cuando se detecta texto normativo largo en lugar de artefactos estructurados."""


def validate_no_unsupported_regulatory_claims(text: str, source_id: str = "") -> dict[str, Any]:
    """
    Gate anti-texto-normativo.
    Si el texto contiene patrones de CFR/FDA/USP/ICH Y supera el umbral de longitud,
    ABORTA y retorna {"blocked": True, "reason": ..., "pending_marker": "PENDING_DOCUMENT"}.
    """
    if len(text) < _MIN_PARAGRAPH_LENGTH:
        return {"blocked": False}

    for pattern in _REGULATORY_TEXT_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return {
                "blocked": True,
                "reason": (
                    f"Texto normativo detectado (patrón: {pattern!r}). "
                    "No se emite contenido regulatorio sin fuente PDF validada."
                ),
                "pending_marker": "PENDING_DOCUMENT",
                "source_id": source_id or "unknown",
                "action": "Marcar como PENDING_DOCUMENT y agregar a pending_documents list.",
            }

    return {"blocked": False}


def generate_regulatory_matrix(spec: RequirementSpec) -> dict[str, Any]:
    """
    Genera la matriz regulatoria como artefacto estructurado.
    Nunca incluye texto normativo; solo referencias y estado de fuente.
    """
    matrix: dict[str, Any] = {
        "project_id": spec.project_id,
        "requirements": [],
    }

    domain_to_regs = {
        "LIMS": [("21_CFR_PART_11", "Audit trail LIMS"), ("ALCOA_PLUS", "Trazabilidad de datos")],
        "HPLC": [("21_CFR_PART_211", "Análisis de datos analíticos"), ("ICH_Q2R1", "Validación HPLC")],
        "OOS": [("21_CFR_PART_211", "Investigación OOS"), ("FDA_OOS_GUIDANCE_2022", "Procedimiento OOS")],
        "DATA_INTEGRITY": [("21_CFR_PART_11", "Electronic records"), ("ALCOA_PLUS", "Principios ALCOA+")],
        "CAPA": [("21_CFR_PART_211", "CAPA sistema"), ("21_CFR_PART_820", "CAPA dispositivos")],
    }

    source_status = {
        "21_CFR_PART_11": "available_as_reference",
        "21_CFR_PART_211": "available_as_reference",
        "21_CFR_PART_820": "available_as_reference",
        "ALCOA_PLUS": "available_as_reference",
        "FDA_OOS_GUIDANCE_2022": "PENDING_DOCUMENT",
        "ICH_Q2R1": "PENDING_DOCUMENT",
        "FDA_DI_GUIDANCE_2018": "PENDING_DOCUMENT",
        "USP_621": "PENDING_DOCUMENT",
        "USP_1058": "PENDING_DOCUMENT",
    }

    for domain in spec.domains:
        for reg_ref, requirement_label in domain_to_regs.get(domain, []):
            status = source_status.get(reg_ref, "PENDING_DOCUMENT")
            matrix["requirements"].append({
                "domain": domain,
                "regulation_ref": reg_ref,
                "requirement": requirement_label,
                "source_status": status,
                "text": "PENDING_DOCUMENT — fuente PDF requerida antes de go-live" if status == "PENDING_DOCUMENT" else None,
            })

    write_event("layer8_regulatory_matrix_generated", spec.project_id, {
        "domains_covered": spec.domains,
        "requirements_count": len(matrix["requirements"]),
        "pending_count": sum(1 for r in matrix["requirements"] if r["source_status"] == "PENDING_DOCUMENT"),
    })
    return matrix


def generate_corpus_manifest(spec: RequirementSpec) -> dict[str, Any]:
    """
    Genera el manifest del corpus RAG con colecciones y estado de ingesta.
    Documentos no disponibles quedan en estado 'pending'.
    """
    manifest = {
        "project_id": spec.project_id,
        "collections": [],
    }

    collection_map = [
        ("lims_audit_trail", "LIMS", ["21_CFR_PART_11"], "pending"),
        ("hplc_validation", "HPLC", ["ICH_Q2R1", "USP_621"], "pending"),
        ("oos_investigations", "OOS", ["FDA_OOS_GUIDANCE_2022", "21_CFR_PART_211"], "pending"),
        ("data_integrity", "DATA_INTEGRITY", ["FDA_DI_GUIDANCE_2018", "ALCOA_PLUS"], "pending"),
        ("capa_lab", "CAPA", ["21_CFR_PART_211", "21_CFR_PART_820"], "pending"),
    ]

    for coll_name, domain, sources, status in collection_map:
        if domain in spec.domains:
            manifest["collections"].append({
                "name": coll_name,
                "domain": domain,
                "sources": sources,
                "status": status,
                "note": "PENDING_DOCUMENT — requiere PDF validado para ingesta. Ver pending_documents.",
            })

    return manifest


def generate_pending_documents(spec: RequirementSpec) -> list[dict[str, Any]]:
    """Lista los documentos pendientes de adquisición para el corpus."""
    pending = [
        {"id": "FDA_OOS_GUIDANCE_2022", "title": "FDA OOS Guidance 2022", "status": "PENDING_DOCUMENT",
         "url_hint": "https://www.fda.gov/media/xxxxxx/download (verificar URL oficial)"},
        {"id": "FDA_DI_GUIDANCE_2018", "title": "FDA Data Integrity Guidance 2018", "status": "PENDING_DOCUMENT",
         "url_hint": "https://www.fda.gov/media/xxxxxx/download (verificar URL oficial)"},
        {"id": "USP_621", "title": "USP <621> Chromatography", "status": "PENDING_DOCUMENT",
         "url_hint": "Requiere suscripción USP (https://www.usp.org/)"},
        {"id": "USP_1058", "title": "USP <1058> Analytical Instrument Qualification", "status": "PENDING_DOCUMENT",
         "url_hint": "Requiere suscripción USP (https://www.usp.org/)"},
        {"id": "ICH_Q2R1", "title": "ICH Q2(R1) Validation of Analytical Procedures", "status": "PENDING_DOCUMENT",
         "url_hint": "https://www.ich.org/page/quality-guidelines (verificar URL oficial)"},
    ]
    # Filtrar solo los relevantes según los documentos declarados en la misión
    relevant_ids = [d["id"] for d in pending if any(
        p.lower() in d["title"].lower() for p in spec.pending_documents
    )] or [d["id"] for d in pending]
    return [d for d in pending if d["id"] in relevant_ids]


def generate_compliance_assessment(spec: RequirementSpec) -> dict[str, Any]:
    """
    Genera la evaluación de compliance con claims soportados y limitaciones.
    Nunca fabrica texto normativo; declara limitaciones explícitamente.
    """
    return {
        "project_id": spec.project_id,
        "supported_claims": [
            "Arquitectura de agentes diseñada para dominios: " + ", ".join(spec.domains),
            "Routing multi-agente con trazabilidad en factory_audit.jsonl",
            "Estructura de corpus lista para ingesta cuando se aporten PDFs",
        ],
        "unsupported_claims": [
            "Validación de texto regulatorio — requiere PDFs oficiales no disponibles",
            "Cumplimiento afirmativo de CFR/USP/ICH — no evaluado sin fuente primaria",
        ],
        "limitations": [
            "Todos los documentos regulatorios están en estado PENDING_DOCUMENT",
            "go-live requiere ingesta completa del corpus con PDFs validados",
            "No se ha generado ni reproducido texto de regulaciones para este artefacto",
        ],
        "dual_use_note": (
            "Solución marcada como dual-use (21 CFR Part 211 + 820). "
            "Requiere revisión legal antes de go-live." if spec.dual_use else None
        ),
    }
