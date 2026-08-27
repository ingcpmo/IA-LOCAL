"""Remediación V2 con CADENA CAUSAL exigida (B7) --
docs_plan/ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md FASE 8.

Cadena obligatoria, verificada estructuralmente:

    Finding -> RemediationDirective -> candidate document -> redline -> manifest

`build_manifest()` REHÚSA emitir si falta cualquier eslabón o cualquier
hash de artefacto. Todo artefacto lleva la marca obligatoria
"MACHINE GENERATED -- BORRADOR, NO APROBADO". El documento original NUNCA
se modifica (este módulo no escribe archivos: produce la especificación
de cambios + el manifest; la cirugía docx real la hace el pipeline de
CURRENT `regulatory_document_package_pipeline` sin que B7 lo toque).

PROHIBIDO, sin excepción: convertir cualquiera de estos artefactos en
QA_APPROVED / RELEASED / CAPA_CLOSED / FINAL_GMP_APPROVAL. `human_state`
del Finding no lo cambia este módulo.

Determinista, sin LLM, sin descargas.
"""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from factory.regulatory.findings.taxonomy import FORBIDDEN_STATES, Finding

MACHINE_GENERATED_MARK = "MACHINE GENERATED -- BORRADOR, NO APROBADO"
QA_STATUS_DRAFT = "NOT_QA_APPROVED"

# Estados de Finding que pueden originar una propuesta de remediación.
_REMEDIABLE_MACHINE_STATES = frozenset({
    "MACHINE_CONFIRMED_FINDING", "MACHINE_DEVIATION_CANDIDATE",
})


class RemediationChainError(RuntimeError):
    """La cadena finding -> directive -> candidate -> redline -> manifest
    está incompleta. Fail-closed: no se emite manifest."""


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _guard_no_forbidden(*values) -> None:
    for v in values:
        if isinstance(v, str) and v in FORBIDDEN_STATES:
            raise RemediationChainError(
                f"estado prohibido en la cadena de remediación: {v!r} -- la IA nunca aprueba")


# ── Eslabón 1-2: Finding -> RemediationDirective ────────────────────────

@dataclass
class RemediationProposal:
    proposal_id: str
    finding_id: str
    requirement_id: str | None
    target_document: str
    target_section: str | None
    target_page: int
    original_excerpt: str            # literal del documento (Claim.source_text del Finding)
    original_hash: str
    proposed_text: str               # el texto de reemplazo/adición propuesto
    change_type: str                 # "replace" | "insert_after"
    rationale: str
    traceability: dict = field(default_factory=dict)   # {requirement_id, evidence_ids, graph_path}
    mark: str = MACHINE_GENERATED_MARK

    def __post_init__(self) -> None:
        _guard_no_forbidden(self.change_type, self.proposed_text[:64])
        if not self.proposed_text.strip():
            raise RemediationChainError("RemediationProposal sin proposed_text")
        if self.original_hash != _sha256(self.original_excerpt):
            raise RemediationChainError("original_hash no corresponde a original_excerpt")
        if self.change_type not in ("replace", "insert_after"):
            raise ValueError(f"change_type inválido: {self.change_type!r}")


def build_proposal(finding: Finding, *, proposed_text: str,
                   change_type: str = "replace",
                   graph_path: list | None = None) -> RemediationProposal:
    """Solo para Findings en un estado remediable. El original_excerpt es
    la cita del Finding (Claim.source_text); nunca se re-extrae ni se toca
    el documento."""
    if finding.machine_state not in _REMEDIABLE_MACHINE_STATES:
        raise RemediationChainError(
            f"Finding en estado {finding.machine_state!r} no origina remediación "
            f"(remediables: {sorted(_REMEDIABLE_MACHINE_STATES)})")
    _guard_no_forbidden(finding.machine_state, finding.human_state)
    pid = "rem-" + hashlib.sha256(
        f"{finding.finding_id}\x1f{proposed_text}".encode("utf-8")).hexdigest()[:16]
    return RemediationProposal(
        proposal_id=pid, finding_id=finding.finding_id,
        requirement_id=finding.requirement_id,
        target_document=finding.document, target_section=finding.section,
        target_page=finding.page, original_excerpt=finding.source_text,
        original_hash=finding.source_hash, proposed_text=proposed_text.strip(),
        change_type=change_type, rationale=finding.rationale,
        traceability={
            "requirement_id": finding.requirement_id,
            "evidence_ids": list(finding.evidence_ids),
            "graph_path": graph_path or (finding.provenance.graph_path or []),
            "subcriterion_ref": finding.provenance.subcriterion_ref,
        },
    )


# ── Eslabón 3-4: candidate + redline (texto, determinista) ──────────────

@dataclass
class TextRedline:
    proposal_id: str
    diff_unified: str
    candidate_excerpt: str           # el excerpt tras aplicar el cambio
    candidate_excerpt_hash: str
    mark: str = MACHINE_GENERATED_MARK


def apply_and_redline(proposal: RemediationProposal) -> TextRedline:
    """Aplica el cambio propuesto SOBRE EL EXCERPT (no sobre el documento)
    y produce un redline de texto determinista. El documento original en
    disco no se toca."""
    orig = proposal.original_excerpt
    if proposal.change_type == "replace":
        candidate = proposal.proposed_text
    else:  # insert_after
        candidate = f"{orig.rstrip()}\n{proposal.proposed_text}"
    diff = "\n".join(difflib.unified_diff(
        orig.splitlines(), candidate.splitlines(),
        fromfile=f"{proposal.target_document}:orig", tofile=f"{proposal.target_document}:candidate",
        lineterm="",
    ))
    return TextRedline(
        proposal_id=proposal.proposal_id, diff_unified=diff,
        candidate_excerpt=candidate, candidate_excerpt_hash=_sha256(candidate),
    )


def to_current_pipeline_change(proposal: RemediationProposal) -> dict:
    """Adaptador al formato `changes[]` que consume el pipeline docx de
    CURRENT (`candidate_document_generator.generate_candidate_document`),
    sin importarlo ni acoplarse a python-docx."""
    return {
        "page_start": proposal.target_page,
        "section": proposal.target_section,
        "change_type": proposal.change_type,
        "original_text": proposal.original_excerpt,
        "new_text": proposal.proposed_text,
        "rationale": proposal.rationale,
        "finding_id": proposal.finding_id,
        "mark": MACHINE_GENERATED_MARK,
    }


# ── Eslabón 5: manifest (rehúsa si la cadena está incompleta) ───────────

@dataclass
class RemediationChain:
    finding: Finding
    proposal: RemediationProposal
    redline: TextRedline

    def _validate_links(self) -> None:
        if self.proposal.finding_id != self.finding.finding_id:
            raise RemediationChainError("proposal.finding_id != finding.finding_id")
        if self.redline.proposal_id != self.proposal.proposal_id:
            raise RemediationChainError("redline.proposal_id != proposal.proposal_id")
        if self.proposal.original_hash != self.finding.source_hash:
            raise RemediationChainError("proposal.original_hash != finding.source_hash")
        _guard_no_forbidden(self.finding.machine_state, self.finding.human_state)

    def build_manifest(self, *, candidate_doc_sha256: str | None = None,
                       redline_doc_sha256: str | None = None,
                       insertion_manifest: dict | None = None,
                       require_docx: bool = False) -> dict:
        """Emite el manifest SOLO si la cadena completa está presente.
        `require_docx=True` exige además los hashes de los .docx reales
        (candidato + redline) y el insertion_manifest del pipeline de
        CURRENT. Con `require_docx=False` (default) la cadena mínima es
        finding -> proposal -> text-redline -> manifest."""
        self._validate_links()
        if require_docx and not (candidate_doc_sha256 and redline_doc_sha256 and insertion_manifest):
            raise RemediationChainError(
                "require_docx=True pero faltan candidate_doc_sha256 / redline_doc_sha256 / "
                "insertion_manifest -- manifest NO emitido")
        chain = [
            {"link": "finding", "id": self.finding.finding_id,
             "hash": self.finding.source_hash, "machine_state": self.finding.machine_state},
            {"link": "remediation_directive", "id": self.proposal.proposal_id,
             "hash": _sha256(self.proposal.proposed_text)},
            {"link": "candidate", "excerpt_hash": self.redline.candidate_excerpt_hash,
             "docx_sha256": candidate_doc_sha256},
            {"link": "redline", "diff_hash": _sha256(self.redline.diff_unified),
             "docx_sha256": redline_doc_sha256},
        ]
        return {
            "manifest_kind": "remediation_v2",
            "qa_status": QA_STATUS_DRAFT,
            "mark": MACHINE_GENERATED_MARK,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_document": self.proposal.target_document,
            "requirement_id": self.proposal.requirement_id,
            "traceability": self.proposal.traceability,
            "chain": chain,
            "chain_complete": True,
            "docx_backed": bool(candidate_doc_sha256 and redline_doc_sha256),
            "human_state": self.finding.human_state,   # sigue UNREVIEWED; la IA no lo cambia
            "note": ("Cadena finding -> directive -> candidate -> redline -> manifest verificada. "
                     "BORRADOR generado por máquina. NO es aprobación, NO cierra CAPA, NO libera "
                     "lote. Requiere sign-off humano (CLAUDE.md)."),
        }
