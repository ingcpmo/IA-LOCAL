"""R4-T1.0v2 (2026-08-13, docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md) —
`RemediationDirective`: el registro del Acto 2 (autoría humana de la
corrección), distinto del Acto 1 (adjudicar el hallazgo, ya cubierto por
`human_review_queue.mark_reviewed()`). Ninguna entrada de la cola de
revisión, por sí sola, produce `proposed_text` -- ese campo es SIEMPRE
provisto por el llamador humano identificado (`authored_by_id`), nunca
generado por este módulo ni por ningún agente.

Solo dispara sobre un hallazgo YA confirmado cuya conclusión sea una
brecha real (`DOCUMENTATION_GAP`/`PROVISIONAL_GAP`) -- confirmar
`SUPPORTING_EVIDENCE_UNDER_REVIEW` significa "no hay brecha" (nada que
remediar) y `EVALUATION_INCOMPLETE` significa una contradicción sin
resolver (un humano debe decidir qué sección es la vigente, no redactar
un reemplazo todavía) -- ver hallazgo 2 de
docs_plan/R4_T1_PLAN_POR_FASES.md.

Append-only, mismo patrón que el resto de la fábrica: una directiva
nunca se reescribe, una corrección posterior se registra como una nueva
entrada con `status=SUPERSEDED` en la anterior."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from factory.core.audit_writer import write_event
from factory.core.identity_policy import validate_identity
from factory.regulatory.corpus_runner import _resolve_document_path
from factory.regulatory.regulatory_catalog import RegulatoryCatalogError, known_entry_ids
from factory.regulatory.semantic_evidence_verification import verify_anchor
from factory.layer9.human_review_queue import get_entry

REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECTIVES_FILE = REPO_ROOT / "factory" / "layer9" / "remediation_directives.jsonl"

_CHANGE_TYPES = {"ADD", "REPLACE", "DELETE"}
_STATUSES = {"DRAFT", "SUBMITTED", "SUPERSEDED"}
# Único disparador válido (hallazgo 2 del arco R4-T1, corregido):
# confirmar una brecha real. SUPPORTING_EVIDENCE_UNDER_REVIEW confirmado
# significa "no hay brecha" -- nunca dispara una directiva.
# EVALUATION_INCOMPLETE (contradicción bloqueada) tampoco -- un humano
# debe decidir qué sección es la vigente, eso no es este acto.
VALID_TRIGGER_CONCLUSIONS = frozenset({"DOCUMENTATION_GAP", "PROVISIONAL_GAP"})

_DIRECTIVE_REQUIRED_FIELDS = {
    "directive_id", "finding_rc_id", "document_id", "document_sha256", "requirement_id",
    "change_type", "proposed_text", "target_location", "original_text",
    "regulatory_citation", "rationale", "authored_by_id", "authored_by_display_name",
    "authored_at", "status",
}


class RemediationDirectiveError(Exception):
    """Fail-closed: la directiva propuesta no puede aceptarse -- el
    llamador decide qué hacer con el rechazo (nunca se acepta a medias)."""


@dataclass(frozen=True)
class TargetLocation:
    page_start: int
    page_end: int
    section: str | None = None


def _validate_target_location(target_location: dict, *, total_pages: int) -> TargetLocation:
    if not isinstance(target_location, dict):
        raise RemediationDirectiveError("target_location: debe ser un dict {page_start, page_end, section?}")
    page_start = target_location.get("page_start")
    page_end = target_location.get("page_end")
    if not isinstance(page_start, int) or not isinstance(page_end, int):
        raise RemediationDirectiveError("target_location.page_start/page_end: deben ser int")
    if page_start < 1 or page_end < page_start:
        raise RemediationDirectiveError(
            f"target_location: page_start/page_end inválidos (page_start={page_start}, page_end={page_end})")
    if page_end > total_pages:
        raise RemediationDirectiveError(
            f"target_location: page_end={page_end} excede las páginas reales del documento ({total_pages})")
    section = target_location.get("section")
    if section is not None and not isinstance(section, str):
        raise RemediationDirectiveError("target_location.section: debe ser str o None")
    return TargetLocation(page_start=page_start, page_end=page_end, section=section)


def _extract_target_text(path: Path, location: TargetLocation) -> str:
    import pypdf
    reader = pypdf.PdfReader(str(path))
    pages = reader.pages[location.page_start - 1:location.page_end]
    return "\n".join((p.extract_text() or "") for p in pages)


def validate_remediation_directive(directive: dict) -> None:
    """Valida FORMA -- campos obligatorios, tipos, enums. No repite las
    validaciones de negocio (finding confirmado, drift, anclaje) que ya
    corrieron en `propose_remediation_directive()` antes de construir el
    dict; esta función es la que un caller externo (endpoint HTTP) debe
    correr también sobre cualquier directiva ya persistida, sin volver a
    tocar la cola/el documento."""
    name = "RemediationDirective"
    extra = set(directive.keys()) - _DIRECTIVE_REQUIRED_FIELDS
    if extra:
        raise RemediationDirectiveError(f"{name}: propiedades inesperadas no permitidas: {sorted(extra)}")
    missing = _DIRECTIVE_REQUIRED_FIELDS - set(directive.keys())
    if missing:
        raise RemediationDirectiveError(f"{name}: faltan campos obligatorios: {sorted(missing)}")

    if directive["change_type"] not in _CHANGE_TYPES:
        raise RemediationDirectiveError(f"{name}.change_type: inválido {directive['change_type']!r}")
    if directive["status"] not in _STATUSES:
        raise RemediationDirectiveError(f"{name}.status: inválido {directive['status']!r}")
    if not str(directive["proposed_text"]).strip():
        raise RemediationDirectiveError(f"{name}.proposed_text: no puede estar vacío")
    if directive["change_type"] in ("REPLACE", "DELETE") and not str(directive.get("original_text") or "").strip():
        raise RemediationDirectiveError(
            f"{name}: change_type={directive['change_type']!r} exige original_text no vacío")
    if directive["change_type"] == "ADD" and directive.get("original_text") is not None:
        raise RemediationDirectiveError(f"{name}: change_type=ADD no admite original_text (no hay nada que reemplazar)")

    citations = directive.get("regulatory_citation")
    if not isinstance(citations, list) or not citations:
        raise RemediationDirectiveError(f"{name}.regulatory_citation: debe ser una lista no vacía")
    if not all(isinstance(c, str) and c.strip() for c in citations):
        raise RemediationDirectiveError(f"{name}.regulatory_citation: cada elemento debe ser un str no vacío")

    if not str(directive["rationale"]).strip():
        raise RemediationDirectiveError(f"{name}.rationale: no puede estar vacío")


def propose_remediation_directive(
    *, finding_rc_id: str, change_type: str, proposed_text: str, target_location: dict,
    regulatory_citation: list[str], rationale: str, authored_by_id: str,
    authored_by_display_name: str | None = None, original_text: str | None = None,
) -> dict:
    """ÚNICA función de creación real -- ningún otro punto del módulo
    escribe `factory/layer9/remediation_directives.jsonl`. `proposed_text`
    y `original_text` vienen TAL CUAL del llamador -- este módulo nunca
    los genera, resume ni completa."""
    authored_by_id = validate_identity(authored_by_id, field="authored_by_id")

    entry = get_entry(finding_rc_id)
    if entry is None or entry.get("entry_type") != "finding_review":
        raise RemediationDirectiveError(f"finding_rc_id={finding_rc_id!r}: no existe una entrada finding_review real")
    if entry.get("status") != "confirmed":
        raise RemediationDirectiveError(
            f"finding_rc_id={finding_rc_id!r}: status={entry.get('status')!r} -- solo un hallazgo 'confirmed' "
            "puede originar una directiva (Acto 1 debe completarse antes que el Acto 2)")
    summary = entry.get("summary") or {}
    conclusion = summary.get("conclusion")
    if conclusion not in VALID_TRIGGER_CONCLUSIONS:
        raise RemediationDirectiveError(
            f"finding_rc_id={finding_rc_id!r}: conclusion={conclusion!r} no es un disparador válido -- "
            f"solo {sorted(VALID_TRIGGER_CONCLUSIONS)} representan una brecha real confirmada "
            "(SUPPORTING_EVIDENCE_UNDER_REVIEW confirmado significa 'no hay brecha'; "
            "EVALUATION_INCOMPLETE es una contradicción sin resolver, no una brecha)")

    document_id = summary.get("document_id")
    requirement_id = summary.get("requirement_id")
    try:
        path, live_sha256 = _resolve_document_path(document_id)
    except Exception as e:  # noqa: BLE001 -- CorpusDocumentDriftError u otro fallo real de resolución
        raise RemediationDirectiveError(
            f"document_id={document_id!r}: no se pudo resolver/verificar el documento real: {e}") from e

    if change_type not in _CHANGE_TYPES:
        raise RemediationDirectiveError(f"change_type: inválido {change_type!r}")

    import pypdf
    total_pages = len(pypdf.PdfReader(str(path)).pages)
    location = _validate_target_location(target_location, total_pages=total_pages)

    if change_type in ("REPLACE", "DELETE"):
        if not (original_text or "").strip():
            raise RemediationDirectiveError(f"change_type={change_type!r} exige original_text no vacío")
        source_text = _extract_target_text(path, location)
        status, match_type = verify_anchor(original_text, source_text)
        if status != "PASS" or match_type == "fuzzy":
            raise RemediationDirectiveError(
                f"original_text no ancla literalmente en target_location (páginas "
                f"{location.page_start}-{location.page_end} de {document_id}) -- match_type={match_type!r}; "
                "nunca se acepta un reemplazo sobre texto no verificado en el documento real")
    elif original_text is not None:
        raise RemediationDirectiveError("change_type=ADD no admite original_text")

    try:
        known = known_entry_ids()
    except RegulatoryCatalogError as e:
        raise RemediationDirectiveError(f"catálogo regulatorio no disponible: {e}") from e
    unknown = [c for c in regulatory_citation if c not in known]
    if unknown:
        raise RemediationDirectiveError(f"regulatory_citation: entradas no existen en el catálogo real: {unknown}")

    if not (proposed_text or "").strip():
        raise RemediationDirectiveError("proposed_text: no puede estar vacío -- autoría humana obligatoria")
    if not (rationale or "").strip():
        raise RemediationDirectiveError("rationale: no puede estar vacío")

    now = datetime.now(timezone.utc).isoformat()
    directive = {
        "directive_id": f"DIR-{finding_rc_id}-{now}".replace(":", "").replace(".", ""),
        "finding_rc_id": finding_rc_id,
        "document_id": document_id,
        "document_sha256": live_sha256,
        "requirement_id": requirement_id,
        "change_type": change_type,
        "proposed_text": proposed_text,
        "target_location": {
            "page_start": location.page_start, "page_end": location.page_end, "section": location.section,
        },
        "original_text": original_text,
        "regulatory_citation": list(regulatory_citation),
        "rationale": rationale,
        "authored_by_id": authored_by_id,
        "authored_by_display_name": authored_by_display_name,
        "authored_at": now,
        "status": "SUBMITTED",
    }
    validate_remediation_directive(directive)

    DIRECTIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DIRECTIVES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(directive, ensure_ascii=False) + "\n")

    write_event("remediation_directive_authored", document_id, {
        "directive_id": directive["directive_id"], "finding_rc_id": finding_rc_id,
        "requirement_id": requirement_id,
        "change_type": change_type, "authored_by_id": authored_by_id,
    })
    return directive


def list_directives(*, finding_rc_id: str | None = None) -> list[dict]:
    if not DIRECTIVES_FILE.exists():
        return []
    out = []
    for line in DIRECTIVES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if finding_rc_id is None or d.get("finding_rc_id") == finding_rc_id:
            out.append(d)
    return out


def get_directive(directive_id: str) -> dict | None:
    """R4-T1.0v2 cierre P0 (verificacion 2026-08-18, docs_plan/
    VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md, hallazgo I): unica funcion
    real de resolucion por directive_id -- la usa
    remediation_package_service.create_package() para exigir que todo
    RemediationChange tenga una RemediationDirective real y SUBMITTED
    detras, cerrando el bypass por el que un `change` con
    proposed_content arbitrario podia llegar al endpoint de creacion de
    paquetes sin pasar por el Acto 2 (autoria humana)."""
    for d in list_directives():
        if d["directive_id"] == directive_id:
            return d
    return None
