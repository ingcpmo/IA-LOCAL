"""W5 V2 — decisiones humanas D1–D5.

Superficie mínima gobernada para que las 5 decisiones humanas pendientes de
W5 V2 puedan revisarse y registrarse desde Mission Control.

Por qué existe como componente propio y NO se reutiliza ninguno de los que ya
hay (distinción exigida por el diagnóstico):

  A. Aprobación de misión (`/layer9/missions/{id}/approve`) administra el
     ciclo de vida de una MISIÓN completa.
  B. Cola de revisión (`/layer9/review-queue`) administra RELEASE CANDIDATES
     de una solución construida por Capa 8.
  C. Validación GAMP 5 administra ASSESSMENTS de un paquete de validación.
  D. Estas decisiones son actos de GOBERNANZA REGULATORIA sobre el corpus y
     las fuentes: no tienen misión, ni RC, ni assessment asociado.

Ninguna de A, B o C puede sustituir a D: aprobar una misión no reverifica una
fuente regulatoria, y aprobar un RC no firma los criterios interpretativos de
un Evidence Pack.

Reglas duras:
  - La lectura (`get_decisions_state`) es SOLO LECTURA: no escribe auditoría,
    no promueve estados, no dispara reverificación ni corridas.
  - Registrar una decisión escribe EXACTAMENTE UN evento de auditoría.
  - Identidad genérica ⇒ 422. Decisión ya registrada ⇒ 409.
  - Registrar una decisión NO cambia por sí sola el estado de ninguna fuente,
    pack, misión ni corrida. Es el registro del acto humano; la ejecución de
    sus consecuencias es un paso posterior y separado.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from factory.core.audit_writer import write_event
from factory.services import paths

DECISIONS_FILE = paths.FACTORY_ROOT / "layer9" / "decisions" / "w5_human_decisions.jsonl"

W5_PROJECT_ID = "gmpai_document_validation"

# Mismo criterio que _RESERVED_APPROVERS de layer9/mission_control.py y
# RESERVED_RUN_BY de test_console_service.py -- una decisión regulatoria
# firmada por "human" no identifica a nadie.
RESERVED_IDENTITIES = {
    "", "human", "humano", "agent", "agente", "layer8_agent", "auto",
    "system", "sistema", "admin", "user", "usuario", "factory", "capa8",
    "capa9", "layer8", "layer9", "claude", "qa",
}

VALID_DECISIONS = ("APPROVE", "PARTIAL", "REJECT")

DECISION_IDS = (
    "D1_regulatory_sources",
    "D2_evidence_packs",
    "D3_T039",
    "D4_corpus_execution",
    "D5_regenerate_qa_package",
)


class DecisionValidationError(ValueError):
    """422 -- la decisión no es registrable tal como viene."""


class DecisionAlreadyRecordedError(RuntimeError):
    """409 -- ya existe una decisión registrada para ese decision_id."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_all() -> list[dict]:
    if not DECISIONS_FILE.is_file():
        return []
    out = []
    for line in DECISIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def recorded_decisions() -> dict[str, dict]:
    """decision_id -> última decisión registrada. Solo lectura."""
    return {d["decision_id"]: d for d in _read_all()}


# ---------------------------------------------------------------------------
# Contexto de revisión: datos REALES leídos de sus fuentes gobernadas.
# Nada se inventa; si un fichero no está, el campo queda vacío y se declara.
# ---------------------------------------------------------------------------

def _regulatory_sources_context() -> dict:
    registry = paths.FACTORY_ROOT / "regulatory" / "sources" / "registry.json"
    if not registry.is_file():
        return {"sources": [], "unavailable": "registry.json no encontrado"}
    data = json.loads(registry.read_text(encoding="utf-8"))
    sources = []
    for s in data.get("sources", []):
        sources.append({
            "source_id": s["source_id"],
            "regulation": s.get("official_source_description", ""),
            "jurisdiction": s.get("jurisdiction", ""),
            "official_source_url": s.get("official_source_url", ""),
            "version": s.get("version", ""),
            "effective_date": s.get("effective_date", ""),
            "sha256": s.get("sha256_copy", ""),
            "size_bytes": s.get("size_bytes"),
            "local_integrity_status": s.get("local_integrity_status", ""),
            "current_state": s.get("regulatory_currency_status", ""),
        })
    return {"sources": sources}


def _evidence_packs_context() -> dict:
    try:
        import yaml
        catalog_path = (
            paths.FACTORY_ROOT / "regulatory" / "requirement_catalog" / "requirements.yaml"
        )
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 -- contexto de lectura, nunca tumba la vista
        return {"packs": [], "unavailable": f"{type(e).__name__}: {e}"}
    packs = []
    for rid, entry in (catalog.get("requirements") or {}).items():
        packs.append({
            "requirement_id": rid,
            "source_id": entry.get("source_id", ""),
            "clause": (entry.get("citation") or {}).get("section_page_paragraph", ""),
            "evidence_min_criteria": len(entry.get("evidence_min_criteria") or []),
            "exclusion_criteria": len(entry.get("exclusion_criteria") or []),
            "weak_keywords": len(entry.get("weak_keywords") or []),
            "expected_doc_types": entry.get("expected_doc_types") or [],
            "source_verification_status": entry.get("source_verification_status", ""),
            "pack_lifecycle_status": entry.get("pack_lifecycle_status", ""),
        })
    return {"packs": packs, "catalog_version": catalog.get("catalog_version")}


_STATIC_CONTEXT = {
    "D3_T039": {
        "summary": "RW-0008 (PDF) está en HUMAN_REVIEW_REQUIRED. Evidencia "
                   "convergente indica que es la renderización del DOCM RW-0007.",
        "evidence": [
            "PDF Creator = 'Acrobat PDFMaker 20 for Word' (generado desde Word)",
            "Mismo autor declarado (Scott, Melissa) y mismo nº de páginas (3)",
            "El cuerpo del DOCM está fechado el mismo día en que se creó el PDF",
        ],
        "options": ["DERIVED_DOCUMENT_EXCLUDED (duplicate_of RW-0007)",
                    "Mantener como original independiente"],
        "detail_document": "factory/docs/W5V2_DECISIONES_HUMANAS_PENDIENTES.md",
    },
    "D4_corpus_execution": {
        "summary": "Ejecutar las corridas restantes del corpus tras filtrado.",
        "estimated_llm_calls": 147,
        "estimated_hours": 34.3,
        "analysable_documents": 5,
        "total_documents": 14,
        "cost_if_run_before_approvals": "Cambiar requirements.yaml mueve "
                                        "catalog_sha256 e invalida todos los "
                                        "checkpoints: repetir las ~34 h.",
        "detail_document": "factory/docs/W5V2_PLAN_CORRIDAS_CORPUS.md",
    },
    "D5_regenerate_qa_package": {
        "summary": "Regenerar PKG-FS-V1-2-REAL-CONTROLLED tras cerrarse los dos "
                   "falsos positivos de calidad.",
        "current_gate_status": "DOCUMENT_GENERATION_PARTIAL",
        "note": "Re-evaluación read-only tras los fixes: sin_duplicaciones PASS, "
                "referencias_cruzadas NOT_EVALUATED. El paquete almacenado NO se "
                "regeneró: hacerlo cambia un artefacto gobernado y su fingerprint.",
    },
}

_TITLES = {
    "D1_regulatory_sources": "Fuentes regulatorias — reverificación, cadencia y autoridad",
    "D2_evidence_packs": "Evidence Packs — aprobación de los 19 criterios interpretativos",
    "D3_T039": "T-039 — clasificación de RW-0008 (PDF) frente a RW-0007 (DOCM)",
    "D4_corpus_execution": "Ejecución del corpus restante — aprobación de costo",
    "D5_regenerate_qa_package": "Regeneración del paquete QA de FS_v1.2",
}


def get_decisions_state() -> dict:
    """Estado de D1–D5 + datos necesarios para revisarlas.

    SOLO LECTURA: no escribe auditoría, no promueve ningún estado, no dispara
    reverificación ni corridas. Llamarla mil veces no cambia nada.
    """
    recorded = recorded_decisions()
    decisions = []
    for did in DECISION_IDS:
        entry = {
            "decision_id": did,
            "title": _TITLES[did],
            "status": "RECORDED" if did in recorded else "PENDING",
            "recorded": recorded.get(did),
        }
        if did == "D1_regulatory_sources":
            entry["context"] = _regulatory_sources_context()
        elif did == "D2_evidence_packs":
            entry["context"] = _evidence_packs_context()
        else:
            entry["context"] = _STATIC_CONTEXT[did]
        decisions.append(entry)

    return {
        "decisions": decisions,
        "pending_count": sum(1 for d in decisions if d["status"] == "PENDING"),
        "recorded_count": sum(1 for d in decisions if d["status"] == "RECORDED"),
        # Constantes de gobernanza: ninguna decisión de esta vista las mueve
        # por sí sola.
        "governance": {
            "FORMAL_RELEASE_GATE": "BLOCKED",
            "REGULATORY_COMPLIANCE": "NOT_DETERMINED",
            "PRODUCTION_ENABLEMENT": "BLOCKED",
        },
        "read_only": True,
    }


def _validate_identity(approved_by: str) -> str:
    name = (approved_by or "").strip()
    if not name or name.lower() in RESERVED_IDENTITIES:
        raise DecisionValidationError(
            f"approved_by={approved_by!r} es una identidad genérica o vacía. "
            "Una decisión regulatoria exige el nombre real de quien la firma."
        )
    return name


def record_decision(
    decision_id: str,
    *,
    decision: str,
    approved_by: str,
    notes: str = "",
    decision_date: str | None = None,
    approved_source_ids: list[str] | str | None = None,
    reverification_cadence_months: int | None = None,
    reverification_authority: str | None = None,
    approved_pack_ids: list[str] | str | None = None,
) -> dict:
    """Registra UNA decisión humana. Un solo evento de auditoría.

    No ejecuta ninguna consecuencia: no reverifica fuentes, no promueve packs,
    no lanza corridas, no descongela nada. Registrar ≠ ejecutar.
    """
    if decision_id not in DECISION_IDS:
        raise DecisionValidationError(f"decision_id desconocido: {decision_id!r}")
    if decision not in VALID_DECISIONS:
        raise DecisionValidationError(
            f"decision={decision!r} inválida. Válidas: {list(VALID_DECISIONS)}"
        )
    name = _validate_identity(approved_by)

    if decision_id in recorded_decisions():
        prev = recorded_decisions()[decision_id]
        raise DecisionAlreadyRecordedError(
            f"{decision_id} ya fue decidido por {prev.get('approved_by')} "
            f"el {prev.get('decision_date')}"
        )

    record = {
        "decision_id": decision_id,
        "decision": decision,
        "approved_by": name,
        "decision_date": decision_date or _now(),
        "decision_origin": "human_confirmed",
        "notes": notes or "",
        "recorded_at": _now(),
    }
    if decision_id == "D1_regulatory_sources":
        if approved_source_ids is None:
            raise DecisionValidationError(
                "D1 exige approved_source_ids ('ALL' o lista explícita de source_id)."
            )
        if reverification_cadence_months is None:
            raise DecisionValidationError("D1 exige reverification_cadence_months.")
        if not (reverification_authority or "").strip():
            raise DecisionValidationError("D1 exige reverification_authority.")
        record["approved_source_ids"] = approved_source_ids
        record["reverification_cadence_months"] = int(reverification_cadence_months)
        record["reverification_authority"] = reverification_authority.strip()
    if decision_id == "D2_evidence_packs" and approved_pack_ids is not None:
        record["approved_pack_ids"] = approved_pack_ids

    DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DECISIONS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # UN solo evento. `layer9_decision_recorded` ya existe en VALID_EVENTS y es
    # exactamente esto: una decisión de gobernanza registrada por un humano.
    write_event("layer9_decision_recorded", W5_PROJECT_ID, {
        "scope": "w5_human_decision",
        "decision_id": decision_id,
        "decision": decision,
        "approved_by": name,
        "decision_origin": "human_confirmed",
        "decision_date": record["decision_date"],
        # Se declara explícitamente que registrar no ejecuta.
        "side_effects_applied": False,
    })
    return record
