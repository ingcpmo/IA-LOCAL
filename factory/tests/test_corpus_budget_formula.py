"""G8 -- fórmula de presupuesto/tiempo (§5.2 de
MODEL_REQUALIFICATION_AND_D4A_SPEC.md), verificada contra los ÚNICOS tres
puntos de datos reales completos publicados hoy: los tres agentes de
RW-0005 (`factory/docs/W5V2_PLAN_CORRIDAS_CORPUS.md` §3/§57). NUNCA se
inventan cifras para los otros documentos del plan (RW-0006/0011/0012/0014):
el desglose por-agente de esos no está publicado, así que no se fabrica.

Q-10 (tabla del spec §7) queda PARCIALMENTE cubierto: la fórmula reproduce
los 3 datos reales que existen, no el agregado de 147 llamadas/34,3 h (eso
exigiría el desglose por-agente de los otros 4 documentos, que no existe
como dato publicado -- ver docstring del módulo)."""
from __future__ import annotations

import pytest

from factory.regulatory.corpus_budget_formula import (
    MIN_PER_1K_TOKENS, budget_and_time_for_agent_on_document,
    calls_for_document, estimated_minutes,
)

# Los tres agentes reales de RW-0005 (58 pags, 27 chunks tras filtrado),
# citados en W5V2_PLAN_CORRIDAS_CORPUS.md:
#   eu_annex11:  5 checkpoints, 20 criterios -> budget 3072, YA EJECUTADO
#                27 chunks / 481 min / 0 fallos tecnicos (la corrida BASE
#                de la que sale MIN_PER_1K_TOKENS=5.8 -- ver spec §5.2).
#   fda_part11:  4 checkpoints (req), 22 criterios -> budget 3584, 9,4 h.
#   alcoa_plus:  9 checkpoints (req), 25 criterios -> budget 4096, 10,7 h.
RW_0005_CHUNKS = 27


def test_output_token_budget_matches_the_two_confirmed_real_values():
    """`output_token_budget()` (chunked_engine.py) no se reimplementa aqui
    -- se usa tal cual, y se confirma que sigue dando los valores YA
    verificados contra corridas reales (docstring propio de esa funcion)."""
    from factory.engines.gmpai_integrity.chunked_engine import output_token_budget
    assert output_token_budget(5, 20) == 3072   # eu_annex11
    assert output_token_budget(9, 25) == 4096   # alcoa_plus
    assert output_token_budget(4, 22) == 3584   # fda_part11


def test_eu_annex11_reproduces_the_base_real_run_exactly():
    """Esta es LA corrida de la que sale MIN_PER_1K_TOKENS -- por
    construccion, con el valor medido, la formula debe reproducir 481 min
    exacto (o casi, por redondeo de 5,8)."""
    budget, minutes = budget_and_time_for_agent_on_document(
        n_checkpoints=5, n_criteria=20, chunks=RW_0005_CHUNKS)
    assert budget == 3072
    assert minutes == pytest.approx(481, rel=0.01)


def test_fda_part11_reproduces_9_4_hours_within_5_percent():
    budget, minutes = budget_and_time_for_agent_on_document(
        n_checkpoints=4, n_criteria=22, chunks=RW_0005_CHUNKS)
    assert budget == 3584
    hours = minutes / 60
    assert hours == pytest.approx(9.4, rel=0.05)


def test_alcoa_plus_reproduces_10_7_hours_within_5_percent():
    budget, minutes = budget_and_time_for_agent_on_document(
        n_checkpoints=9, n_criteria=25, chunks=RW_0005_CHUNKS)
    assert budget == 4096
    hours = minutes / 60
    assert hours == pytest.approx(10.7, rel=0.05)


def test_calls_for_document_is_chunks_times_qualifying_agents():
    assert calls_for_document(27, 1) == 27
    assert calls_for_document(27, 3) == 81
    assert calls_for_document(0, 5) == 0


def test_calls_for_document_rejects_negative_inputs():
    with pytest.raises(ValueError):
        calls_for_document(-1, 1)
    with pytest.raises(ValueError):
        calls_for_document(1, -1)


def test_estimated_minutes_rejects_negative_inputs():
    with pytest.raises(ValueError):
        estimated_minutes(-1, 100)
    with pytest.raises(ValueError):
        estimated_minutes(1, -100)


def test_estimated_minutes_is_monotonic_in_calls_and_budget():
    """Invariante de la formula: mas llamadas o mas presupuesto nunca puede
    dar MENOS tiempo estimado -- nunca deberia poder "ahorrarse" tiempo
    subiendo cualquiera de los dos factores."""
    base = estimated_minutes(10, 1000)
    assert estimated_minutes(11, 1000) > base
    assert estimated_minutes(10, 1001) > base


def test_min_per_1k_tokens_is_the_documented_fragile_constant():
    """Cambiar esta constante sin volver a medir p50/p95 reales (G6 §4) es
    exactamente el riesgo que el spec senala -- este test la fija como
    literal para que un cambio silencioso se note en el diff, no en produccion."""
    assert MIN_PER_1K_TOKENS == 5.8
