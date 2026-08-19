"""Paquete 1a (VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md, BLOQUE 3, causa
raíz F): clasificación determinista y SUGERIDA de un hallazgo real hacia
NCR o CAPA. Nunca crea NCR ni CAPA real, nunca cierra nada -- solo
detecta -> sugiere clasificación -> fundamento -> cola humana
(`factory.layer9.human_review_queue.enqueue_governance_candidate_for_review`).
El humano decide siempre, vía `mark_candidate_reviewed()`.

REGLA DE CLASIFICACIÓN (aprobada por Cesar, 2026-08-19,
docs_plan/PAQUETE_1_INTEGRACION_HALLAZGOS_DISENO.md, "propuesta
conservadora del diseño"):

  - `conclusion` en {DOCUMENTATION_GAP, PROVISIONAL_GAP} (ausencia
    confirmada por `absence_consolidator.consolidate()`, nunca el LLM
    directo) y CERO ocurrencias previas del mismo
    (requirement_id, document_id) en `review_queue.jsonl`
    -> candidato NCR.
  - Misma condición, con >=1 ocurrencia previa (recurrencia real,
    contada por `human_review_queue.count_prior_finding_occurrences()`)
    -> candidato CAPA.
  - Cualquier otra `conclusion` -> ningún candidato sugerido (el humano
    clasifica manualmente, como ya ocurre hoy -- hallazgo F declara
    explícitamente `PRODUCTION_BLOCKER = NO`).

CHANGE_CONTROL DELIBERADAMENTE NO IMPLEMENTADO EN ESTA ITERACIÓN
--------------------------------------------------------------------
La regla original (documento de diseño) preveía disparar un candidato de
change-control desde `review_flags` que implicaran "desviación de
procedimiento" (vs. simple falta de evidencia). Auditado el vocabulario
REAL de `review_flags` (`factory/regulatory/absence_consolidator.py`):
existe una entrada `"DEVIATION_IDENTIFIED": "PROVISIONAL_DEVIATION"` en
el mapeo de conclusión provisional (línea ~177), pero NINGÚN productor
del pipeline la emite jamás -- verificado por grep, única aparición en
todo `factory/`. No hay hoy ninguna señal objetiva de "desviación de
procedimiento" distinta de "falta de evidencia" en los datos reales.

Mapear esto desde alguna combinación de `review_flags` existentes (p.ej.
`*_BLOCKED_BY_OPEN_CONTRADICTION`, que en realidad significa
"observaciones contradictorias entre chunks", no "el procedimiento real
se desvía del SOP") sería inventar una señal que el dato no sostiene --
exactamente lo que este paquete prohíbe ("sin inventar campos cuando
falte el dato", mismo principio que `unified_finding_report.py`).

`CHANGE_CONTROL` queda declarado como tipo válido en el esquema
(`human_review_queue._GOVERNANCE_CANDIDATE_TYPES`) para que un humano
pueda reclasificar manualmente un NCR/CAPA sugerido como change-control
si su propio juicio lo amerita -- pero el clasificador automático NUNCA
lo sugiere en esta iteración."""
from __future__ import annotations

from dataclasses import dataclass

NCR = "NCR"
CAPA = "CAPA"
CHANGE_CONTROL = "CHANGE_CONTROL"

# absence_consolidator.consolidate() es el ÚNICO productor real de estas
# dos conclusiones -- el LLM directo nunca las emite (regla P3/W5.5, ver
# absence_consolidator.py). Clasificar sobre cualquier otra conclusion
# sería sugerir NCR/CAPA sobre una ausencia que nadie confirmó.
_GAP_CONCLUSIONS = frozenset({"DOCUMENTATION_GAP", "PROVISIONAL_GAP"})


@dataclass(frozen=True)
class GovernanceCandidateSuggestion:
    suggested_type: str
    rationale: str
    prior_occurrences: int


def classify_finding_for_governance_candidate(
    *, requirement_id: str, document_id: str, run_id: str, conclusion: str,
) -> GovernanceCandidateSuggestion | None:
    """Devuelve una sugerencia o None (sin candidato) -- nunca lanza sobre
    un caso normal (conclusion fuera del alcance de este clasificador).
    `prior_occurrences` se calcula SIEMPRE contra el estado real de
    `review_queue.jsonl` en el momento de la llamada -- nunca cacheado, para
    que la recurrencia refleje corridas ya registradas hasta este instante."""
    if conclusion not in _GAP_CONCLUSIONS:
        return None

    from factory.layer9.human_review_queue import count_prior_finding_occurrences
    prior = count_prior_finding_occurrences(
        requirement_id, document_id, exclude_run_id=run_id, conclusions=_GAP_CONCLUSIONS)

    if prior == 0:
        return GovernanceCandidateSuggestion(
            suggested_type=NCR,
            rationale=(
                f"conclusion='{conclusion}' (ausencia confirmada por absence_consolidator, "
                "nunca por el LLM directo) sin ocurrencia previa registrada de "
                f"({requirement_id}, {document_id}) en review_queue.jsonl -- primera aparición, "
                "se sugiere NCR."
            ),
            prior_occurrences=0,
        )
    return GovernanceCandidateSuggestion(
        suggested_type=CAPA,
        rationale=(
            f"conclusion='{conclusion}' con {prior} ocurrencia(s) previa(s) registrada(s) de "
            f"({requirement_id}, {document_id}) en review_queue.jsonl (corridas con run_id "
            f"distinto de '{run_id}', excluidas las 'superseded' por ser defecto técnico, no "
            "ausencia real) -- recurrencia real, se sugiere CAPA."
        ),
        prior_occurrences=prior,
    )
