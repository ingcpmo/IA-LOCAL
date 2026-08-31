"""H-7 (2026-08-29) -- cobertura gobernada + riesgo que consume `evidence_basis`.

Diseño: docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md §H-7.
Capacidad técnica COMPLETA + probada; ENFORCE **NO** se activa en producción
(GATE D-2). En OBSERVE: 0 cambio de risk/severity/state, `findings_fingerprint`
intacto.
"""
from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from factory.regulatory.findings.risk import compute_risk
from factory.regulatory.requirement_catalog import gxp_criticality_loader as gx
from factory.regulatory.validation_v2 import coverage_mode as cm

_FINDINGS_FP_OBSERVE = "b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e"
#: baseline ENFORCE tras D-2 APPROVE (D-2-H7-20260830). REQUALIFICATION_REQUIRED=SÍ.
_FINDINGS_FP_ENFORCE = "fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d"
_GRAPH_FP = "88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05"
_DOCS = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]
_WOULD_DEGRADE = 78          # R-1 N-3, afinado en H-7
_RW0009_INDETERMINATE = 57   # R-5


# ---------------------------------------------------------------------------
# 1 · analysis_coverage_mode como parámetro gobernado
# ---------------------------------------------------------------------------
def _write_mode_yaml(tmp: Path, *, mode: str, signed: bool) -> Path:
    sig = ('decided_by: "Cesar"\ndecision_ref: "D-2-x"\ndecision_date: "2026-08-29"\n'
           if signed else "decided_by: null\ndecision_ref: null\ndecision_date: null\n")
    p = tmp / "analysis_coverage_mode.yaml"
    p.write_text(f"mode: {mode}\n{sig}", encoding="utf-8")
    return p


def test_mode_defaults_to_observe(tmp_path):
    p = _write_mode_yaml(tmp_path, mode="OBSERVE", signed=False)
    r = cm.resolve(p)
    assert r["requested_mode"] == "OBSERVE"
    assert r["effective_mode"] == "OBSERVE"
    assert r["downgrade_reason"] is None


def test_enforce_requested_but_unsigned_falls_back_to_observe(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "_thresholds_signed", lambda: True)      # thresholds OK
    p = _write_mode_yaml(tmp_path, mode="ENFORCE", signed=False)      # pero YAML sin firma
    r = cm.resolve(p)
    assert r["requested_mode"] == "ENFORCE"
    assert r["effective_mode"] == "OBSERVE"                          # fail-safe
    assert "sin firma de Capa 9" in r["downgrade_reason"]


def test_enforce_requested_signed_but_thresholds_unsigned_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "_thresholds_signed", lambda: False)     # thresholds NO firmados
    p = _write_mode_yaml(tmp_path, mode="ENFORCE", signed=True)
    r = cm.resolve(p)
    assert r["effective_mode"] == "OBSERVE"
    assert "extraction_adequacy_thresholds" in r["downgrade_reason"]


def test_enforce_effective_only_when_both_signed(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "_thresholds_signed", lambda: True)
    p = _write_mode_yaml(tmp_path, mode="ENFORCE", signed=True)
    r = cm.resolve(p)
    assert r["effective_mode"] == "ENFORCE"
    assert r["downgrade_reason"] is None


def test_production_mode_config_is_enforce_post_d2():
    """Tras D-2 APPROVE (decision_ref D-2-H7-20260830) el fichero gobernado del
    repo está en ENFORCE con firma, y extraction_adequacy_thresholds.yaml SIGNED."""
    r = cm.resolve()
    assert r["requested_mode"] == "ENFORCE"
    assert r["effective_mode"] == "ENFORCE"
    assert r["thresholds_signed"] is True and r["mode_config_signed"] is True
    assert r["decision_ref"] == "D-2-H7-20260830"


# ---------------------------------------------------------------------------
# 2 · criticidad GxP estructurada
# ---------------------------------------------------------------------------
def test_gxp_criticality_levels():
    assert gx.level_for("21_CFR_11.10(e)") == "HIGH"        # audit trail
    assert gx.level_for("ALCOA_LEGIBLE") == "MEDIUM"
    assert gx.level_for("no-such-requirement") == "MEDIUM"  # default == literal actual
    assert gx.status() == "SIGNED"                          # firmado en D-2 (D-2-H7-20260830)


def test_different_criticality_produces_different_band():
    lo = compute_risk("REGULATORY_GAP", "MAJOR", "LOW").band
    hi = compute_risk("REGULATORY_GAP", "MAJOR", "HIGH").band
    assert lo != hi


# ---------------------------------------------------------------------------
# 3 · compute_risk -- OBSERVE inerte, ENFORCE degrada
# ---------------------------------------------------------------------------
_HIST_KEYS = {"subtype", "severity", "gxp_impact", "severity_w", "gxp_impact_w",
              "probability_w", "detectability_w", "score", "band", "matrix_version"}


def test_observe_as_dict_is_byte_identical_shape():
    d = compute_risk("REGULATORY_GAP", "MAJOR", "MEDIUM").as_dict()
    assert set(d) == _HIST_KEYS
    # pasar los params H-7 en OBSERVE no cambia nada
    d2 = compute_risk("REGULATORY_GAP", "MAJOR", "MEDIUM",
                      evidence_basis="ABSENCE_DEPENDENT", coverage_status="MISSING",
                      mode="OBSERVE").as_dict()
    assert d2 == d


def test_enforce_degrades_absence_dependent_missing():
    r = compute_risk("REQUIREMENT_NOT_TESTED", "MAJOR", "HIGH",
                     evidence_basis="ABSENCE_DEPENDENT", coverage_status="MISSING", mode="ENFORCE")
    d = r.as_dict()
    assert d["enforced_degraded"] is True
    assert set(d) > _HIST_KEYS  # incluye los campos H-7
    assert d["band_pre_enforce"] != d["band"] or d["band"] == "LOW"


@pytest.mark.parametrize("eb,cs", [("PRESENCE", "OK"), ("INDETERMINATE", "OK"),
                                   ("ABSENCE_DEPENDENT", "OK")])
def test_enforce_spares_non_would_degrade(eb, cs):
    r = compute_risk("REGULATORY_GAP", "CRITICAL", "HIGH",
                     evidence_basis=eb, coverage_status=cs, mode="ENFORCE")
    assert r.enforced_degraded is False
    assert r.band == r.band_pre_enforce


def test_enforce_rule_applies_even_if_already_low():
    """La regla APLICA a todo would_degrade; band_changed distingue si se movió."""
    r = compute_risk("REGULATORY_COMPLIANT_EVIDENCE", "MINOR", "LOW",
                     evidence_basis="ABSENCE_DEPENDENT", coverage_status="DEGRADED", mode="ENFORCE")
    assert r.enforced_degraded is True
    assert r.band == "LOW" and r.band_changed is False


# ---------------------------------------------------------------------------
# 4 · E2E -- OBSERVE (lo que se envía) y ENFORCE (probado, no activado)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _observe_audit():
    """Fuerza OBSERVE (el repo ya está en ENFORCE tras D-2) para seguir validando
    que en OBSERVE H-7 es metadata/presentación pura y `findings_fingerprint` ==
    la referencia OBSERVE `b5196a71…`."""
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    mp = pytest.MonkeyPatch()
    tmp = Path(tempfile.mkdtemp(prefix="h7-obs-cfg-"))
    mp.setattr(cm, "_MODE_PATH", _write_mode_yaml(tmp, mode="OBSERVE", signed=False))
    mp.setattr(cm, "_thresholds_signed", lambda: False)
    base = Path(tempfile.mkdtemp(prefix="h7-obs-"))
    try:
        run_v2_pipeline(_DOCS, project_id="H7-OBS-T", run_id="o1", report_base=base)
        audit = json.loads((base / "o1" / "audit_summary" / "audit_metadata.json").read_text())
    finally:
        mp.undo()   # el patch solo debe vivir durante la corrida; no filtrar a otros tests
    return base, audit


def test_e2e_observe_does_not_move_findings_or_graph(_observe_audit):
    _, a = _observe_audit
    assert a["findings_fingerprint"] == _FINDINGS_FP_OBSERVE
    assert a["graph_snapshot_fingerprint"] == _GRAPH_FP
    assert a["analysis_coverage_mode"] == "OBSERVE"
    assert a["analysis_coverage_enforce_effect"]["findings_degraded"] == 0


def test_e2e_observe_two_queues_coherent(_observe_audit):
    _, a = _observe_audit
    q = a["coverage_queues"]
    an, bl = q["ACTIONABLE_NOW"]["count"], q["BLOCKED_BY_COVERAGE_OR_EVIDENCE"]["count"]
    total = a["n_regulatory"] + a["n_functional"] + a["n_technical"]
    assert an + bl == total
    br = q["BLOCKED_BY_COVERAGE_OR_EVIDENCE"]["by_reason"]
    assert br["missing_or_degraded_coverage"] == _WOULD_DEGRADE
    assert br["missing_or_degraded_coverage"] == a["coverage_would_degrade"]["would_degrade_true"]
    assert q["BLOCKED_BY_COVERAGE_OR_EVIDENCE"]["rw0009_subset_count"] == _RW0009_INDETERMINATE


def test_e2e_observe_report_has_two_queue_section(_observe_audit):
    base, _ = _observe_audit
    md = (base / "o1" / "informe_hallazgos_v2.md").read_text()
    assert "dos colas gobernadas" in md
    assert "ACTIONABLE_NOW" in md and "BLOCKED_BY_COVERAGE_OR_EVIDENCE" in md


def test_e2e_enforce_is_the_governed_production_path_post_d2():
    """Tras D-2 APPROVE el repo YA está en ENFORCE (sin monkeypatch). La regla
    aplica a EXACTAMENTE los `would_degrade_true`; `findings_fingerprint` == la
    baseline ENFORCE `fdc29721…` (REQUALIFICATION_REQUIRED=SÍ) y es determinista;
    0 findings suprimidos; el grafo no cambia."""
    from factory.regulatory.validation_v2 import v2_runtime as vr
    assert cm.resolve()["effective_mode"] == "ENFORCE"      # config del repo, sin patch

    base = Path(tempfile.mkdtemp(prefix="h7-enf-"))
    vr.run_v2_pipeline(_DOCS, project_id="H7-ENF-T", run_id="e1", report_base=base)
    vr.run_v2_pipeline(_DOCS, project_id="H7-ENF-T", run_id="e2", report_base=base)
    a1 = json.loads((base / "e1" / "audit_summary" / "audit_metadata.json").read_text())
    a2 = json.loads((base / "e2" / "audit_summary" / "audit_metadata.json").read_text())

    assert a1["analysis_coverage_mode"] == "ENFORCE"
    ee = a1["analysis_coverage_enforce_effect"]
    assert ee["findings_degraded"] == a1["coverage_would_degrade"]["would_degrade_true"] == _WOULD_DEGRADE
    assert 0 < ee["band_actually_lowered"] <= _WOULD_DEGRADE
    assert a1["findings_fingerprint"] == _FINDINGS_FP_ENFORCE          # baseline ENFORCE post-D-2
    assert a1["findings_fingerprint"] == a2["findings_fingerprint"]    # determinista
    assert a1["graph_snapshot_fingerprint"] == _GRAPH_FP              # el grafo no cambia
    # sin supresión de findings ni cambio del gate humano
    n1 = a1["n_regulatory"] + a1["n_functional"] + a1["n_technical"]
    assert n1 == 456 and a1["human_gate_intact"] is True and a1["forbidden_states_present"] is False
