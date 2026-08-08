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
    calls_for_document, compute_d4a, estimated_minutes,
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


# ---------------------------------------------------------------------------
# D4-A completo -- compute_d4a(), sobre R(d,a) real (corpus_plan.py) y el
# plan de corridas vigente (5 documentos con chunks reales medidos).
# ---------------------------------------------------------------------------

def test_d4a_reproduces_the_two_calibrated_agents_inside_rw_0005():
    """No reimplementa nada: compute_d4a() usa resolve_document_agent_plan()
    + budget_and_time_for_agent_on_document(), ambos ya probados por
    separado. Este test confirma que, DENTRO del total, el desglose de
    RW-0005 sigue conteniendo exactamente los dos contratos ya calibrados
    contra corridas reales (eu_annex11 5cp/20crit, alcoa_plus 9cp/25crit)."""
    d4a = compute_d4a()
    rw0005 = [b for b in d4a["breakdown"] if b["document_id"] == "RW-0005"]
    annex11 = next(b for b in rw0005 if b["agent_id"] == "eu_annex11_agent")
    alcoa = next(b for b in rw0005 if b["agent_id"] == "alcoa_plus_agent")
    assert annex11["n_checkpoints"] == 5 and annex11["n_criteria"] == 20
    assert annex11["budget_tokens"] == 3072
    assert alcoa["n_checkpoints"] == 9 and alcoa["n_criteria"] == 25
    assert alcoa["budget_tokens"] == 4096


def test_d4a_max_calls_is_the_sum_of_all_agent_document_calls():
    d4a = compute_d4a()
    assert d4a["max_calls"] == sum(b["calls"] for b in d4a["breakdown"])
    assert d4a["max_calls"] > 0


def test_d4a_hard_stops_are_always_strictly_above_the_estimate():
    """Q-12 del spec: hard_stop_calls > max_calls y hard_stop_wall_time >
    estimated_runtime_max, siempre."""
    d4a = compute_d4a()
    assert d4a["hard_stop_calls"] > d4a["max_calls"]
    assert d4a["hard_stop_wall_time_hours"] > d4a["estimated_runtime_max_hours"]


def test_d4a_never_fabricates_dispersion_it_has_not_measured():
    """Un solo dato real (MIN_PER_1K_TOKENS) no es una distribucion --
    min/likely/max quedan honestamente iguales, con la bandera explicita,
    en vez de simular p50/p95 con multiplicadores inventados."""
    d4a = compute_d4a()
    assert d4a["estimated_runtime_min_hours"] == d4a["estimated_runtime_likely_hours"] == d4a["estimated_runtime_max_hours"]
    assert d4a["runtime_dispersion_measured"] is False


def test_d4a_declares_the_fixed_checkpoint_fields():
    d4a = compute_d4a()
    assert d4a["checkpoint_mode"] == "per_document"
    assert d4a["resume_fingerprint_required"] is True


def test_d4a_con_dispersion_medida_aplica_la_formula_del_spec():
    """§5.3 del spec: min = p50x0.85, likely = p50, max = p95. Verificado
    con el par real medido en la recalibracion 2026-08-07 (calibration
    per-call: 10.01 y 7.55 min/1k tok -> p50=8.78, p95=9.89)."""
    baseline = compute_d4a()
    dispersed = compute_d4a(p50_measured=8.78, p95_measured=9.89)

    assert dispersed["runtime_dispersion_measured"] is True
    assert dispersed["p50_measured"] == 8.78
    assert dispersed["p95_measured"] == 9.89
    assert "min_per_1k_tokens_used" not in dispersed

    # "likely" con dispersion medida (rate=p50) debe coincidir con el
    # calculo directo al mismo rate por la ruta sin dispersion -- misma
    # R(d,a), mismos chunks, solo cambia la tasa min/1k tokens.
    expected_likely = compute_d4a(min_per_1k_tokens=8.78)["estimated_runtime_likely_hours"]
    assert dispersed["estimated_runtime_likely_hours"] == expected_likely
    assert dispersed["estimated_runtime_likely_hours"] > baseline["estimated_runtime_likely_hours"]
    assert dispersed["estimated_runtime_min_hours"] == round(dispersed["estimated_runtime_likely_hours"] * 0.85, 2)
    assert dispersed["estimated_runtime_max_hours"] == round(
        dispersed["estimated_runtime_likely_hours"] * (9.89 / 8.78), 2)
    assert dispersed["max_calls"] == baseline["max_calls"]
    assert dispersed["hard_stop_wall_time_hours"] == round(dispersed["estimated_runtime_max_hours"] * 1.30, 2)


def test_d4a_sin_dispersion_medida_mantiene_el_comportamiento_historico():
    """El default (sin p50_measured/p95_measured) no cambia -- mismo
    invariante que ya protegia test_d4a_never_fabricates_dispersion..."""
    d4a = compute_d4a()
    assert d4a["runtime_dispersion_measured"] is False
    assert d4a["min_per_1k_tokens_used"] == MIN_PER_1K_TOKENS
    assert "p50_measured" not in d4a and "p95_measured" not in d4a


def test_d4a_declares_which_runs_it_authorizes():
    """El defecto historico de D4_corpus_execution (2026-07-29): se firmo
    APPROVE sin resolved_target_ids, un 'si' sin objeto (spec §5.1). Este
    campo es lo que la propuesta real usa como target_ids -- debe declarar
    los 5 documentos, nunca quedar vacio."""
    d4a = compute_d4a()
    assert d4a["document_ids"] == ["RW-0005", "RW-0006", "RW-0014", "RW-0011", "RW-0012"]
