"""Tests — CF-6 v2.0 · R4/E1 — tabla de equivalencia de fases. SHADOW, sin LLM."""
from __future__ import annotations

import pytest

from factory.regulatory.shadow import phase_equivalence_table as pt
from factory.regulatory.shadow import cf6_pilot_scope as scope


def test_full_corpus_run_class_covers_both_generations():
    tokens = pt.tokens_for("FULL_CORPUS_RUN_POST_GATE")
    assert "cf6-3" in tokens
    assert "cf6-v2-r5" in tokens


def test_unknown_class_raises_fail_closed():
    with pytest.raises(KeyError):
        pt.tokens_for("NOT_A_REAL_CLASS")


def test_gate_c_cf6_3_now_accepts_v2_nomenclature():
    """El defecto que costó 2 rondas de ledger en R2: un scope que dice
    'CF6-v2-R5' debía fallar c_cf6_3 (v1). Con la tabla, ahora coincide."""
    tokens = scope._SCOPE_TOKENS["c_cf6_3"]
    blob = '{"selection_reason": "corrida completa bajo la arquitectura R1-R3 (diseño §13, R5)"}'.lower()
    assert any(t.lower() in blob for t in tokens if t)


def test_gate_still_requires_explicit_coverage_no_bare_cf6_wildcard():
    """No se relaja: 'cf6' solo no debe ser suficiente para c_cf6_3 (a
    diferencia de d_execution_type_json_structure, que sí acepta 'cf6' como
    comodín genérico de formato)."""
    assert "cf6" not in {t.lower() for t in scope._SCOPE_TOKENS["c_cf6_3"]}


def test_spec_is_versioned_and_signed():
    s = pt.spec()
    assert s["table_version"] == "1"
    assert s["signed_by"] == "Capa 9 (Cesar)"
    assert "FULL_CORPUS_RUN_POST_GATE" in s["classes"]
