"""Las 7 clases de Finding + constructores + estados (V2, B5) -- FASE 7.

Determinista, sin LLM. `human_state` inmutable desde código de IA:
la única mutación sancionada es `set_human_state(f, ..., reviewer=...)`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, fields

# ── Clases y subtipos permitidos ─────────────────────────────────────────

FINDING_CLASSES = (
    "RegulatoryFinding", "FunctionalFinding", "TechnicalFinding",
    "TraceabilityFinding", "DataIntegrityFinding", "SecurityFinding",
    "TestCoverageFinding",
)

SUBTYPES: dict[str, tuple[str, ...]] = {
    "RegulatoryFinding": (
        "REGULATORY_GAP", "REGULATORY_PARTIAL", "REGULATORY_COMPLIANT_EVIDENCE",
        "REGULATORY_INCONCLUSIVE",
    ),
    "FunctionalFinding": (
        "REQUIREMENT_NOT_IMPLEMENTED", "IMPLEMENTATION_WITHOUT_REQUIREMENT",
        "CONTRADICTORY_FUNCTIONAL_BEHAVIOR",
    ),
    "TechnicalFinding": (
        "TECHNICAL_DESIGN_GAP", "AUDIT_TRAIL_DESIGN_GAP", "BACKUP_RECOVERY_GAP",
        "TIME_SYNC_GAP", "INTERFACE_INCONSISTENCY", "REDUNDANCY_GAP",
    ),
    "TraceabilityFinding": (
        "REQUIREMENT_NOT_TRACED", "ORPHAN_DESIGN_ELEMENT", "BROKEN_TRACE_LINK",
    ),
    "DataIntegrityFinding": (
        "ALCOA_ATTRIBUTABLE_GAP", "ALCOA_CONTEMPORANEOUS_GAP", "ALCOA_ORIGINAL_GAP",
        "ALCOA_ACCURATE_GAP", "ALCOA_COMPLETE_GAP", "AUDIT_TRAIL_INTEGRITY_GAP",
    ),
    "SecurityFinding": (
        "ACCESS_CONTROL_GAP", "SECURITY_CONTROL_GAP", "AUTHORITY_CHECK_GAP",
        "PHYSICAL_SECURITY_GAP",
    ),
    "TestCoverageFinding": (
        "REQUIREMENT_NOT_TESTED", "TEST_WITHOUT_REQUIREMENT", "PARTIAL_TEST_COVERAGE",
    ),
}

# ── Estados ─────────────────────────────────────────────────────────────

MACHINE_STATES = (
    "MACHINE_CONFIRMED_FINDING",     # el hallazgo está confirmado por la máquina (evidencia anclada)
    "MACHINE_DEVIATION_CANDIDATE",   # candidato a desviación, evidencia suficiente pero no cerrada
    "MACHINE_REMEDIATION_PROPOSAL",  # lleva una propuesta de remediación adjunta (B7)
    "MACHINE_INCONCLUSIVE",          # la máquina no pudo concluir; va a revisión
)

HUMAN_STATES = ("UNREVIEWED", "ACCEPTED", "REJECTED", "CHANGES_REQUESTED")

#: Estados que la IA NUNCA puede fijar, en ningún campo. Un intento de
#: ponerlos por código no-humano lanza.
FORBIDDEN_STATES = frozenset({
    "QA_APPROVED", "RELEASED", "CAPA_CLOSED", "FINAL_GMP_APPROVAL", "APPROVED",
})

CONFIDENCE = ("HIGH", "MEDIUM", "LOW")


class FindingProvenanceError(ValueError):
    """Finding sin provenance completo -- no se construye (fail-closed)."""


class ForbiddenStateError(ValueError):
    """Intento de fijar QA_APPROVED / RELEASED / CAPA_CLOSED /
    FINAL_GMP_APPROVAL desde código -- la IA nunca aprueba."""


class HumanStateViolation(RuntimeError):
    """Intento de cambiar `human_state` sin pasar por
    `set_human_state(..., reviewer=<nombre real>)`."""


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _det_id(document: str, class_: str, subtype: str, page: int, source_text: str) -> str:
    raw = "\x1f".join([document, class_, subtype, str(page), source_text])
    return "fnd-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class FindingProvenance:
    document_id: str
    extraction_version: str
    run_id: str | None = None
    agent_id: str | None = None
    adjudicator_state: str | None = None    # estado del B4 adjudicator, si aplica
    subcriterion_ref: str | None = None
    graph_path: list | None = None          # para findings cross-documento (B6)


@dataclass
class Finding:
    finding_id: str
    finding_class: str
    subtype: str
    severity: str                            # propuesto por el agente: LOW|MAJOR|CRITICAL|...
    document: str
    page: int
    section: str | None
    source_text: str                         # literal -- la cita
    source_hash: str
    rationale: str
    confidence: str                          # HIGH|MEDIUM|LOW
    machine_state: str
    provenance: FindingProvenance
    evidence_ids: list = field(default_factory=list)
    requirement_id: str | None = None
    regulatory_basis: str | None = None
    technical_basis: str | None = None
    risk: dict | None = None                 # RiskResult.as_dict() (B5 risk.py)
    related_finding_ids: list = field(default_factory=list)
    #: NUNCA se toca por código de IA. Ver set_human_state().
    human_state: str = "UNREVIEWED"
    reviewer: str | None = None
    reviewed_at: str | None = None

    def __post_init__(self) -> None:
        if self.finding_class not in FINDING_CLASSES:
            raise ValueError(f"finding_class inválida: {self.finding_class!r}")
        if self.subtype not in SUBTYPES[self.finding_class]:
            raise ValueError(
                f"subtype {self.subtype!r} no válido para {self.finding_class} "
                f"(permitidos: {SUBTYPES[self.finding_class]})")
        if self.machine_state not in MACHINE_STATES:
            raise ValueError(f"machine_state inválido: {self.machine_state!r}")
        if self.machine_state in FORBIDDEN_STATES:
            raise ForbiddenStateError(self.machine_state)
        if self.confidence not in CONFIDENCE:
            raise ValueError(f"confidence inválida: {self.confidence!r}")
        if self.human_state != "UNREVIEWED":
            raise HumanStateViolation(
                "un Finding nace SIEMPRE con human_state=UNREVIEWED")
        # provenance obligatorio
        if not self.document or not (self.source_text or "").strip():
            raise FindingProvenanceError("Finding sin document o source_text")
        if not isinstance(self.page, int) or self.page < 1:
            raise FindingProvenanceError(f"page inválida: {self.page!r}")
        if self.source_hash != _sha256(self.source_text):
            raise FindingProvenanceError("source_hash no corresponde a source_text")
        if not self.provenance or not self.provenance.document_id or not self.provenance.extraction_version:
            raise FindingProvenanceError("provenance incompleto")


def build_finding(finding_class: str, subtype: str, *, severity: str, document: str,
                  page: int, source_text: str, rationale: str, confidence: str,
                  machine_state: str, provenance: FindingProvenance,
                  section: str | None = None, evidence_ids: list | None = None,
                  requirement_id: str | None = None, regulatory_basis: str | None = None,
                  technical_basis: str | None = None, risk: dict | None = None,
                  related_finding_ids: list | None = None) -> Finding:
    return Finding(
        finding_id=_det_id(document, finding_class, subtype, page, source_text),
        finding_class=finding_class, subtype=subtype, severity=severity,
        document=document, page=page, section=section, source_text=source_text,
        source_hash=_sha256(source_text), rationale=rationale, confidence=confidence,
        machine_state=machine_state, provenance=provenance,
        evidence_ids=list(evidence_ids or []), requirement_id=requirement_id,
        regulatory_basis=regulatory_basis, technical_basis=technical_basis,
        risk=risk, related_finding_ids=list(related_finding_ids or []),
    )


def set_human_state(finding: Finding, new_state: str, *, reviewer: str,
                    reviewed_at: str | None = None) -> Finding:
    """ÚNICA vía sancionada para cambiar `human_state`. Exige un
    `reviewer` con nombre real (mismo criterio que `human_review_queue`).
    Rechaza los estados prohibidos. Devuelve una copia (no muta)."""
    if not (reviewer or "").strip():
        raise HumanStateViolation("set_human_state exige un reviewer con nombre real")
    if new_state in FORBIDDEN_STATES:
        raise ForbiddenStateError(new_state)
    if new_state not in HUMAN_STATES:
        raise ValueError(f"human_state inválido: {new_state!r}")
    from datetime import datetime, timezone
    data = {f.name: getattr(finding, f.name) for f in fields(finding)}
    data["human_state"] = new_state
    data["reviewer"] = reviewer
    data["reviewed_at"] = reviewed_at or datetime.now(timezone.utc).isoformat()
    # reconstruir sin re-disparar la guardia de __post_init__ sobre human_state
    f = Finding.__new__(Finding)
    for k, v in data.items():
        object.__setattr__(f, k, v)
    return f


def as_dict(finding: Finding) -> dict:
    out = {}
    for f in fields(finding):
        v = getattr(finding, f.name)
        out[f.name] = dict(v.__dict__) if isinstance(v, FindingProvenance) else v
    return out
