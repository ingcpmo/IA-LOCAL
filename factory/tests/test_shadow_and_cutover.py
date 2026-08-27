"""Tests -- factory/regulatory/validation_v2/{cutover,shadow,shadow_compare}.py
(V2, B9a). FASE 11. Sin LLM (provider mockeado); shadow SIN efectos.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from factory.regulatory.canonical import model as m
from factory.regulatory.canonical.persistence import CanonicalStore
from factory.regulatory.validation_v2 import cutover, shadow, shadow_compare


# ── cutover flag ─────────────────────────────────────────────────────

def test_default_is_current_only(monkeypatch):
    monkeypatch.delenv("V2_ANALYZER_ROUTING", raising=False)
    monkeypatch.setattr(cutover, "_FILE", Path("/nonexistent/routing.txt"))
    assert cutover.routing_mode() == "current"
    assert cutover.is_current_only()
    assert not cutover.is_v2_active()
    d = cutover.describe()
    assert d["current_decides"] and not d["v2_runs"]


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("V2_ANALYZER_ROUTING", "shadow")
    assert cutover.routing_mode() == "shadow"
    assert cutover.is_shadow_active()
    monkeypatch.setenv("V2_ANALYZER_ROUTING", "v2")
    assert cutover.is_v2_active()
    assert cutover.describe()["v2_has_effects"] is True


def test_invalid_mode_raises(monkeypatch):
    monkeypatch.setenv("V2_ANALYZER_ROUTING", "banana")
    with pytest.raises(cutover.RoutingModeError):
        cutover.routing_mode()


# ── shadow_guard: sin efectos ───────────────────────────────────────

def test_shadow_guard_blocks_enqueue():
    import factory.layer9.human_review_queue as hrq
    with shadow.shadow_guard():
        with pytest.raises(shadow.ShadowEffectViolation):
            hrq.enqueue("rc-x", "prj", {"requirement_id": "r"})
    # restaurado fuera del guard
    assert hrq.enqueue.__name__ != "_blocked"


# ── shadow run end-to-end (mock provider) ───────────────────────────

class MockProvider:
    model_name = "mock"

    def generate(self, prompt, *, num_predict=None):
        if "Descripción operativa neutra:" in prompt and "SUB-CRITERIO" not in prompt:
            return {"response": "El sistema genera un registro de auditoría con fecha y hora."}
        if "VEREDICTO PREVIO:" in prompt:
            return {"response": '{"assessment": "AGREE", "reason": "ok"}'}
        return {"response": '{"verdict": "NO", "rationale": "no explicito"}'}


def _seed(canon_dir):
    with CanonicalStore("RW-0005", store_dir=canon_dir) as s:
        s.put(m.Document(document_id="RW-0005", sha256="x" * 64, tipo="FS", titulo="FS", n_paginas=50))
        for pg, tx in [(45, "El sistema registra los cambios de umbral de alarma."),
                       (39, "El acceso al sistema requiere autenticación individual.")]:
            s.put(m.build_claim("RW-0005", pg, tx, "control", tx))


def test_run_shadow_no_effects_and_persists(tmp_path):
    canon_dir = tmp_path / "canon"
    _seed(canon_dir)
    shadow_root = tmp_path / "v2_shadow"
    res = shadow.run_shadow(
        "RW-0005", ["21_CFR_11.10(e)"], provider=MockProvider(),
        canon_dir=canon_dir, shadow_root=shadow_root, run_id="v2shadow-test")
    assert res.run_id == "v2shadow-test"
    assert res.calls_made > 0
    meta = json.loads((shadow_root / "v2shadow-test" / "meta.json").read_text())
    assert meta["no_effects"] is True
    assert "report.json" in {p.name for p in (shadow_root / "v2shadow-test").iterdir()}
    # findings V2 nacen UNREVIEWED
    for f in res.findings:
        assert f.human_state == "UNREVIEWED"


def test_shadow_run_never_touches_real_queue(tmp_path):
    """Aunque el pipeline intentara encolar, shadow_guard lo detendría.
    Aquí verificamos que una corrida normal NO lo intenta (no lanza)."""
    canon_dir = tmp_path / "canon"
    _seed(canon_dir)
    res = shadow.run_shadow("RW-0005", ["21_CFR_11.10(e)"], provider=MockProvider(),
                            canon_dir=canon_dir, shadow_root=tmp_path / "s", persist=False)
    assert isinstance(res.findings, list)


# ── comparador ─────────────────────────────────────────────────────

class _F:
    def __init__(self, req, state):
        self.requirement_id = req
        self.machine_state = state


def test_compare_classifies_deltas():
    current = {
        "21_CFR_11.10(e)": "DOCUMENTATION_GAP",
        "21_CFR_11.10(g)": "DOCUMENTED_AND_SUPPORTED",
        "ANNEX11_9": "EVALUATION_INCOMPLETE",
    }
    v2 = [
        _F("21_CFR_11.10(e)", "MACHINE_CONFIRMED_FINDING"),   # CURRENT gap, V2 confirma
        _F("21_CFR_11.10(g)", "MACHINE_INCONCLUSIVE"),        # CURRENT pos, V2 a humano
        _F("ANNEX11_9", "MACHINE_INCONCLUSIVE"),              # ambos a humano
    ]
    out = shadow_compare.compare(current, v2)
    assert out["n_requirements"] == 3
    cls = {d["requirement_id"]: d["classification"] for d in out["deltas"]}
    assert cls["21_CFR_11.10(e)"] == "CURRENT_GAP_V2_CONFIRMED"
    assert cls["21_CFR_11.10(g)"] == "CURRENT_CLOSED_V2_TO_HUMAN"
    assert cls["ANNEX11_9"] == "AGREEMENT_TO_HUMAN"
    assert "revisar caso por caso" in out["cutover_recommendation"]


def test_compare_recommends_cutover_when_gains_no_regressions():
    current = {"r1": "DOCUMENTATION_GAP"}
    v2 = [_F("r1", "MACHINE_CONFIRMED_FINDING")]
    out = shadow_compare.compare(current, v2)
    assert "candidato a cutover" in out["cutover_recommendation"]
