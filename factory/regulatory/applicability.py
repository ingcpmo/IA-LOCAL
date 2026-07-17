"""Matriz de aplicabilidad v2 (W5 Ciclo 1, Fase 3, Bloque 3.2). Fail-closed:
lo no contemplado va a revision, nunca a omision silenciosa (P1)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

MATRIX_PATH = Path(__file__).parent / "applicability_matrix.yaml"
VALID = {"expected", "optional", "cross_reference_expected",
         "out_of_document_scope", "review_required"}


class MatrixNotApprovedError(Exception):
    """approval.status != human_confirmed y se intento usar en produccion
    (run_context != 'validation'). Bloque 3.3, fail-closed."""


@lru_cache(maxsize=1)
def load_matrix() -> dict:
    data = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    for rid, m in (data.get("requirements") or {}).items():
        if m.get("default") != "review_required":
            raise ValueError(f"{rid}: default debe ser review_required (P1)")
        for k, v in m.items():
            if k in ("default", "evidence_expected_in"):
                continue
            if v not in VALID:
                raise ValueError(f"Valor invalido: {rid}.{k}={v}")
    return data


def require_matrix_approved_for_production(run_context: str) -> None:
    """Bloque 3.3: si la matriz no esta human_confirmed, el pipeline solo
    puede ejecutarse con run_context='validation'. Cualquier otro contexto
    (ej. 'production') con matriz pending_human_confirmation es un error
    fail-closed explicito -- nunca un warning silencioso."""
    approval = load_matrix().get("approval", {})
    if approval.get("status") != "human_confirmed" and run_context != "validation":
        raise MatrixNotApprovedError(
            f"applicability_matrix.yaml no esta aprobada "
            f"(approval.status={approval.get('status')!r}) -- "
            f"run_context={run_context!r} no permitido. Solo 'validation' "
            f"puede ejecutar con una matriz sin aprobar."
        )


def applicability(requirement_id: str, document_type: str) -> dict:
    reqs = (load_matrix().get("requirements") or {})
    entry = reqs.get(requirement_id)
    if entry is None:
        return {"value": "review_required",
                "reason": "requirement_not_in_matrix",
                "evidence_expected_in": []}
    value = entry.get(document_type, entry.get("default"))
    result = {"value": value, "evidence_expected_in": entry.get("evidence_expected_in", [])}
    if document_type not in {k for k in entry if k not in ("default", "evidence_expected_in")}:
        result["reason"] = "document_type_not_mapped_for_requirement"
    return result


def known_requirement_ids() -> set:
    return set((load_matrix().get("requirements") or {}).keys())


# ---------------------------------------------------------------------------
# Bloque 3.4 — Guardia de tipo documental
# ---------------------------------------------------------------------------

DOCUMENT_TYPE_CONFIDENCE_THRESHOLD = 0.9


def document_type_guard(document_type_source: str, confidence: float | None = None) -> dict:
    """Segun Fase 0 §5: document_type no existe hoy como campo estructurado
    en el motor -- esta guardia es la regla que se aplicara en cuanto exista.

    - 'human_assigned' -> confiable, sin flag.
    - cualquier otro origen (ej. 'inferred') con confidence None o < 0.9 ->
      DOCUMENT_TYPE_UNCONFIRMED: la matriz NO se aplica como definitiva y
      TODAS las conclusiones del documento deben heredar el flag (fail-
      closed -- una clasificacion documental dudosa nunca produce
      conclusiones limpias, P1)."""
    if document_type_source == "human_assigned":
        return {"document_type_source": "human_assigned", "confirmed": True, "flags": []}
    if confidence is None or confidence < DOCUMENT_TYPE_CONFIDENCE_THRESHOLD:
        return {
            "document_type_source": document_type_source,
            "confirmed": False,
            "flags": ["DOCUMENT_TYPE_UNCONFIRMED"],
        }
    return {"document_type_source": document_type_source, "confirmed": True, "flags": []}


def pre_inference_filter(requirement_id: str, document_type: str) -> dict | None:
    """Aplica la matriz ANTES de gastar ninguna llamada a Ollama. Devuelve
    un resultado terminal (dict) para out_of_document_scope/review_required
    -- en ese caso el llamador NO debe invocar generate_controlled(). Para
    expected/optional/cross_reference_expected devuelve None (seguir con
    inferencia normal; app['value'] se pasa al consolidador de Fase 2)."""
    app = applicability(requirement_id, document_type)

    if app["value"] == "out_of_document_scope":
        return {
            "requirement_id": requirement_id,
            "conclusion": "OUT_OF_DOCUMENT_SCOPE",
            "evidence_expected_in": app["evidence_expected_in"],
            "source": "applicability_matrix_v2",
        }

    if app["value"] == "review_required":
        return {
            "requirement_id": requirement_id,
            "conclusion": "APPLICABILITY_REVIEW_REQUIRED",
            "reason": app.get("reason", "document_type_not_mapped"),
            "source": "applicability_matrix_v2",
        }

    return None
