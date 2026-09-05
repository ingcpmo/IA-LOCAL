"""SHADOW · CF-6 v2.0 · R4/E1 — Q-STATE-7: verificación de SCOPE_DRIFT en la
SALIDA del Composer contra `decomposition.yaml`.

Implementa la decisión de Capa 9 (2026-09-04, instrucción "RECONCILIACIÓN
POST-R2 + EJECUCIÓN R4" §1): el plan CF-6 v2.0 declara Q-STATE 1..7; el
código auditado (`composer_gate.py`) solo tenía 1..6. Q-STATE-7 nunca se
portó. Se implementa aquí, SIN retirarse, y **sin modificar
`relevance_model.py`** (solo se reutiliza su función de tokenización, por
lectura -- `rm._tokenize` -- ninguna fórmula ni umbral de esa Relevance
Model se toca).

**Qué protege, y por qué es una superficie DISTINTA del Relevance Model**:
el Relevance Model (R1) filtra la ENTRADA (qué evidencia ve el LLM). Q-STATE-7
verifica la SALIDA (qué afirma el LLM en sus campos de texto libre). El
diagnóstico de R2 (`sec-0016`, campo `procedural_responsibility`) mostró que
el LLM puede elaborar contenido de un sub-criterio DISTINTO al que la
evidencia realmente cubre -- "alta de cuentas, cambio de privilegios,
revocación de cuentas" (sc2/sc3/sc5 de `21_CFR_11.10(d)`) cuando la única
evidencia entregada cubría solo sc1 (control de acceso). El Relevance Model
no puede prevenir esto: ya hizo su trabajo antes de que el LLM escribiera.

**Regla, determinista y fija (no es un umbral de relevancia, no se ajusta
como parte de ninguna calibración de R4)**: para cada campo de texto libre
de la salida del Composer, y para cada sub-criterio del `requirement_id`
que NO está cubierto por `evidence_basis` (es decir, no es el
`matched_subcriterion_id` de ningún item de `relevant_evidence[]` realmente
usado), se cuenta el solapamiento de tokens de contenido (léxico plano,
sin IDF, sin ponderación) entre el campo y el texto (ES+EN) de ese
sub-criterio no cubierto. `>= _DRIFT_MIN_MATCHED` términos en común ->
violación. `_DRIFT_MIN_MATCHED` es una constante de ESTE módulo, no
comparte valor ni justificación con `_PARTIAL_MIN_MATCHED`/
`_RELEVANT_MIN_MATCHED` de `relevance_model.py` -- son mecanismos distintos
para propósitos distintos (relevancia de entrada vs. deriva de salida).

Bloqueante y fail-closed, coherente con el resto del sistema: lo que no
pasa cae a `SAFE_MODE` (se integra en `compose_section`/`verify_qstate`
por quien orqueste la corrida -- este módulo solo produce el veredicto,
no decide el modo de render).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.regulatory.requirement_catalog.requirement_decomposition_loader import (
    get_subcriteria,
)
from factory.regulatory.shadow import relevance_model as rm

# Constante propia de Q-STATE-7. NO es un umbral de relevancia (no se toca en
# ninguna calibración de R4, no se comparte con relevance_model.py).
_DRIFT_MIN_MATCHED = 2

_FREE_TEXT_FIELDS = ("observed_system_capability", "technical_assessment",
                    "procedural_responsibility", "gap_or_open_question",
                    "assessment_rationale")


@dataclass
class QState7Result:
    passed: bool
    violations: list[str] = field(default_factory=list)
    checked_fields: tuple = _FREE_TEXT_FIELDS

    def as_dict(self) -> dict:
        return {"passed": self.passed, "violations": list(self.violations),
                "checked_fields": list(self.checked_fields)}


def _subcriterion_terms(sc: dict) -> set:
    return set(rm._tokenize(sc.get("text", "")) + rm._tokenize(sc.get("text_en", "")))


def check_scope_drift(structured: dict, requirement_id: str,
                      covered_subcriterion_ids: set) -> QState7Result:
    """`structured`: contrato R1 de salida del Composer (post Q-STATE-1..6).
    `covered_subcriterion_ids`: los `matched_subcriterion_id` de
    `relevant_evidence[]` que el Composer SÍ recibió (calculados en R1, no
    aquí). Cualquier sub-criterio del requisito fuera de este conjunto es
    "no cubierto" -- mencionarlo con suficiente solapamiento léxico en un
    campo de texto libre es SCOPE_DRIFT."""
    all_subs = get_subcriteria(requirement_id)
    uncovered = [sc for sc in all_subs if sc["id"] not in covered_subcriterion_ids]
    violations: list[str] = []

    for field_name in _FREE_TEXT_FIELDS:
        text = structured.get(field_name)
        if not isinstance(text, str) or not text.strip():
            continue
        field_terms = set(rm._tokenize(text))
        for sc in uncovered:
            sc_terms = _subcriterion_terms(sc)
            overlap = field_terms & sc_terms
            if len(overlap) >= _DRIFT_MIN_MATCHED:
                violations.append(
                    f"Q-STATE-7: {field_name!r} introduce contenido del sub-criterio "
                    f"NO cubierto {requirement_id}::{sc['id']} "
                    f"(overlap={sorted(overlap)})")

    return QState7Result(passed=not violations, violations=violations)


def contract_spec() -> dict:
    return {
        "schema": "SHADOW_CF6_V2_QSTATE7_SPEC/v1",
        "check": "Q-STATE-7 (scope drift de salida contra decomposition.yaml)",
        "checked_fields": list(_FREE_TEXT_FIELDS),
        "drift_min_matched": _DRIFT_MIN_MATCHED,
        "note": ("Constante propia, no comparte valor con los umbrales del Relevance Model "
                "(_PARTIAL_MIN_MATCHED/_RELEVANT_MIN_MATCHED de relevance_model.py). "
                "No se ajusta como parte de ninguna calibración de R4."),
        "reuses_read_only": ["relevance_model._tokenize"],
        "modifies_relevance_model": False,
        "bloqueante": True,
        "fail_mode": "SAFE_MODE (misma plantilla determinista que Q-STATE-1..6)",
    }
