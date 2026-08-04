"""G8 — fórmula de presupuesto/tiempo de corrida (§5.2 de
`MODEL_REQUALIFICATION_AND_D4A_SPEC.md`), parametrizada, SIN llenar ningún
campo de D4-A: el propio spec lo prohíbe explícitamente (§5.1/§5.3, "D4-A
SE CALCULA EN G8, DESPUÉS DEL PACK FINAL. NO LLENAR ANTES") mientras el pack
`21_CFR_211.68(b)` (G4a) siga con 0 criterios reales aprobados -- cualquier
cifra hoy describiría el catálogo de HOY, no el final.

`output_token_budget()` (el paso `budget(d,a)` de la fórmula) NO se
reimplementa aquí: ya existe, probado y en uso real en
`factory/engines/gmpai_integrity/chunked_engine.py` (redondeo a múltiplo de
512, confirmado contra las corridas reales citadas en su propio docstring).
Este módulo solo añade lo que faltaba: `calls_for_document()` y
`estimated_minutes()`, verificados contra los ÚNICOS tres puntos de datos
reales completos que existen hoy (los tres agentes de RW-0005, único
documento con desglose por-agente publicado en
`factory/docs/W5V2_PLAN_CORRIDAS_CORPUS.md` §3/§57) -- NUNCA contra cifras
inventadas.

`min_per_1k_tokens = 5.8` es el parámetro más frágil (una sola corrida, un
agente, un documento -- ver spec §5.2): se declara aquí como constante
explícita, a la espera de que la recalificación (G6 §4) mida
`latency_p50`/`latency_p95` reales y lo sustituya."""
from __future__ import annotations

from factory.engines.gmpai_integrity.chunked_engine import output_token_budget

#: Medido en UNA corrida real (eu_annex11_agent sobre FS_v1.2, 2026-07-28:
#: 27 chunks, num_predict=3072, 481 min, 0 fallos técnicos). Ver spec §5.2 y
#: el hallazgo de fragilidad ahí mismo -- sustituir por p50/p95 medidos en
#: la recalificación (G6 §4), no seguir asumiendo este valor indefinidamente.
MIN_PER_1K_TOKENS = 5.8


def calls_for_document(chunks: int, n_qualifying_agents: int) -> int:
    """`calls(d,a) = chunks(d) × |agentes con R(d,a) ≠ ∅|` (spec §5.2).

    `chunks` es el conteo REAL tras filtrado por matriz de aplicabilidad
    (nunca estimado por caracteres sin el `chunk_correction` medido -- ver
    spec §5.2, 27 chunks reales vs. 23 estimados por caracteres en RW-0005).
    """
    if chunks < 0 or n_qualifying_agents < 0:
        raise ValueError(f"valores invalidos: {chunks=} {n_qualifying_agents=}")
    return chunks * n_qualifying_agents


def estimated_minutes(calls: int, budget_tokens: int, *,
                      min_per_1k_tokens: float = MIN_PER_1K_TOKENS) -> float:
    """`time(d,a) = calls(d,a) × (budget(d,a) / 1000) × min_per_1k_tokens`
    (spec §5.2). Verificada contra los 3 puntos de datos reales de RW-0005
    (ver `test_corpus_budget_formula.py`)."""
    if calls < 0 or budget_tokens < 0:
        raise ValueError(f"valores invalidos: {calls=} {budget_tokens=}")
    return calls * (budget_tokens / 1000) * min_per_1k_tokens


def budget_and_time_for_agent_on_document(*, n_checkpoints: int, n_criteria: int,
                                          chunks: int,
                                          min_per_1k_tokens: float = MIN_PER_1K_TOKENS
                                          ) -> tuple[int, float]:
    """Un (documento, agente): reusa `output_token_budget()` real (nunca
    reimplementado) para `budget(d,a)`, y aquí solo compone `calls`/`time`.
    `n_qualifying_agents=1` porque este helper mide UN agente sobre UN
    documento -- para el total del documento, sumar sobre los agentes
    aplicables (ver `calls_for_document` para el conteo agregado real)."""
    budget = output_token_budget(n_checkpoints, n_criteria)
    calls = calls_for_document(chunks, 1)
    minutes = estimated_minutes(calls, budget, min_per_1k_tokens=min_per_1k_tokens)
    return budget, minutes
