"""
Capa 8 Tier-1 — Requirement Interpreter.

Lee una misión desde Capa 9 y extrae dominios, alcance regulatorio,
necesidades del cliente y restricciones para producir un requirement_spec.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "LIMS": ["lims", "laboratory information", "muestras", "samples", "acceso", "audit trail"],
    "HPLC": ["hplc", "cromatograf", "sst", "picos", "integración", "inyección", "secuencia"],
    "OOS": ["oos", "out of specification", "out-of-specification", "investigación", "fase i", "fase ii", "oos guidance"],
    "DATA_INTEGRITY": ["data integrity", "integridad de datos", "alcoa", "21 cfr part 11", "part 11", "audit trail"],
    "CAPA": ["capa", "corrective action", "preventive action", "5-why", "fishbone", "fta", "fault tree"],
}

REGULATORY_KEYWORDS: dict[str, list[str]] = {
    "21_CFR_PART_211": ["21 cfr part 211", "21 cfr 211", "part 211", "cfr 211"],
    "21_CFR_PART_820": ["21 cfr part 820", "21 cfr 820", "part 820", "cfr 820"],
    "21_CFR_PART_11": ["21 cfr part 11", "21 cfr 11", "part 11", "cfr 11"],
    "ALCOA_PLUS": ["alcoa+", "alcoa plus", "alcoa"],
}

PENDING_DOC_MARKERS = [
    "fda oos guidance 2022",
    "fda data integrity guidance 2018",
    "usp <621>",
    "usp <1058>",
    "ich q2",
]


@dataclass
class RequirementSpec:
    project_id: str
    domains: list[str]
    regulatory_scope: list[str]
    dual_use: bool
    part11_required: bool
    alcoa_plus_required: bool
    client_needs: list[str]
    constraints: list[str]
    pending_documents: list[str]
    raw_objective: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "domains": self.domains,
            "regulatory_scope": self.regulatory_scope,
            "dual_use": self.dual_use,
            "part11_required": self.part11_required,
            "alcoa_plus_required": self.alcoa_plus_required,
            "client_needs": self.client_needs,
            "constraints": self.constraints,
            "pending_documents": self.pending_documents,
            "raw_objective": self.raw_objective,
        }


def parse_requirement(mission: dict) -> dict:
    """Convierte el payload de misión en campos normalizados."""
    return {
        "project_id": mission.get("project_id", ""),
        "objective": mission.get("objective", ""),
        "regulatory_scope": mission.get("regulatory_scope", []),
        "documents": mission.get("documents", {}),
        "constraints": mission.get("constraints", []),
        "client_type": mission.get("client_type", ""),
    }


def extract_domains(objective: str) -> list[str]:
    """Detecta dominios funcionales presentes en el texto de la misión."""
    text = objective.lower()
    detected = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            detected.append(domain)
    return detected


def extract_regulatory_scope(mission: dict) -> dict[str, Any]:
    """
    Extrae alcance regulatorio combinando campos explícitos y texto libre.
    Retorna scope estructurado con flags dual_use, part11, alcoa+.
    """
    declared = [s.replace(" ", "_").upper() for s in mission.get("regulatory_scope", [])]
    text = (mission.get("objective", "") + " " + " ".join(declared)).lower()

    scope_flags: dict[str, bool] = {}
    for reg, keywords in REGULATORY_KEYWORDS.items():
        scope_flags[reg] = any(kw in text for kw in keywords)

    dual_use = scope_flags.get("21_CFR_PART_211", False) and scope_flags.get("21_CFR_PART_820", False)

    return {
        "declared": declared,
        "detected_flags": scope_flags,
        "dual_use": dual_use,
        "part11_required": scope_flags.get("21_CFR_PART_11", False),
        "alcoa_plus_required": scope_flags.get("ALCOA_PLUS", False),
    }


def extract_client_needs(objective: str) -> list[str]:
    """Extrae las necesidades funcionales del cliente desde el objetivo."""
    text = objective.lower()
    needs = []
    domain_to_need = {
        "LIMS": "Gestión de datos LIMS con audit trail y control de acceso",
        "HPLC": "Revisión de datos HPLC (SST, integración de picos, secuencias)",
        "OOS": "Investigación OOS Fase I/II conforme FDA OOS Guidance 2022",
        "DATA_INTEGRITY": "Control de integridad de datos (ALCOA+ / 21 CFR Part 11)",
        "CAPA": "Gestión de CAPA de laboratorio (5-Why, Fishbone, FTA)",
    }
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            needs.append(domain_to_need[domain])
    return needs


def extract_constraints(mission: dict) -> list[str]:
    """Extrae restricciones del campo constraints de la misión."""
    return list(mission.get("constraints", []))


def _detect_pending_documents(mission: dict) -> list[str]:
    """Detecta documentos marcados como pending en el campo documents."""
    docs = mission.get("documents", {})
    pending = []
    for doc_name, status in docs.items():
        if str(status).lower() in ("pending", "none", ""):
            pending.append(doc_name)
        elif doc_name.lower() in " ".join(PENDING_DOC_MARKERS):
            pending.append(doc_name)
    return pending


def generate_requirement_spec(project_id: str, mission: dict) -> RequirementSpec:
    """
    Punto de entrada principal.
    Interpreta la misión completa y genera un RequirementSpec estructurado.
    """
    parsed = parse_requirement(mission)
    objective = parsed["objective"]
    domains = extract_domains(objective)
    reg_scope = extract_regulatory_scope(mission)
    client_needs = extract_client_needs(objective)
    constraints = extract_constraints(mission)
    pending_docs = _detect_pending_documents(mission)

    spec = RequirementSpec(
        project_id=project_id,
        domains=domains,
        regulatory_scope=reg_scope["declared"],
        dual_use=reg_scope["dual_use"],
        part11_required=reg_scope["part11_required"],
        alcoa_plus_required=reg_scope["alcoa_plus_required"],
        client_needs=client_needs,
        constraints=constraints,
        pending_documents=pending_docs,
        raw_objective=objective,
    )

    write_event("layer8_requirement_interpreted", project_id, {
        "domains": domains,
        "dual_use": reg_scope["dual_use"],
        "part11_required": reg_scope["part11_required"],
        "pending_documents_count": len(pending_docs),
    })

    return spec
