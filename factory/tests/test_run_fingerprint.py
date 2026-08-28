"""WP-A -- tests del fingerprint de corrida (run_fingerprint.py).

Cubre: determinismo · inmunidad reloj/host/pid · sensibilidad por componente ·
estabilidad de FINDINGS_FINGERPRINT ante reordenamiento · scoping de artefactos
consumidos · attestation refleja el codigo cargado · degradacion limpia sin git ·
ausencia de rutas absolutas en la identidad.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from factory.regulatory.validation_v2 import run_fingerprint as rf

_BASE = dict(
    entrypoint="v2_runtime",
    inputs=[{"document_id": "D2", "sha256": "b" * 64}, {"document_id": "D1", "sha256": "a" * 64}],
    extraction_version="canonical-v1-2026-08",
    consumed_artifacts={"foo.yaml": {"version": "1.1", "sha256": "c" * 64}},
    applied_thresholds={"T": 0.9},
    findings=[],
)


def _fp(**over):
    kw = dict(_BASE)
    kw.update(over)
    return rf.compute_fingerprints(**kw)


def _finding(**kw):
    base = dict(
        finding_class="TechnicalFinding", subtype="X_GAP", severity="MEDIUM",
        document="RW-0005", page=3, section="4.1", source_hash="h" * 64,
        source_text="the quote", requirement_id="UR1", regulatory_basis=None,
        technical_basis="rule C01", risk={"band": "MEDIUM"}, confidence=0.7,
        machine_state="MACHINE_DEVIATION_CANDIDATE", human_state="UNREVIEWED",
        rationale="because", evidence_ids=["e1", "e2"], related_finding_ids=[],
        provenance=SimpleNamespace(agent_id="a", extraction_version="canonical-v1-2026-08",
                                   subcriterion_ref=None, adjudicator_state=None, graph_path=None,
                                   run_id="RUN-VOLATILE"),
    )
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
def test_determinism_same_inputs_same_digests():
    a, b = _fp(), _fp()
    assert a["input_config_fingerprint"] == b["input_config_fingerprint"]
    assert a["findings_fingerprint"] == b["findings_fingerprint"]
    assert len(a["input_config_fingerprint"]) == 64


def test_execution_metadata_is_not_identity(monkeypatch):
    a = _fp(wall_clock_seconds=1.0)
    monkeypatch.setattr(rf.socket, "gethostname", lambda: "OTHER-HOST")
    monkeypatch.setattr(rf.os, "getpid", lambda: 999999)
    b = _fp(wall_clock_seconds=987.0)
    assert a["input_config_fingerprint"] == b["input_config_fingerprint"]
    assert a["findings_fingerprint"] == b["findings_fingerprint"]
    assert b["run_attestation"]["host"] == "OTHER-HOST"
    assert b["run_attestation"]["pid"] == 999999
    assert b["run_attestation"]["wall_clock_seconds"] == 987.0


@pytest.mark.parametrize("mutate", [
    lambda kw: kw.__setitem__("inputs", [{"document_id": "D1", "sha256": "z" * 64},
                                         {"document_id": "D2", "sha256": "b" * 64}]),
    lambda kw: kw.__setitem__("extraction_version", "canonical-v2-9999-99"),
    lambda kw: kw.__setitem__("consumed_artifacts", {"foo.yaml": {"version": "9.9", "sha256": "c" * 64}}),
    lambda kw: kw.__setitem__("consumed_artifacts", {"foo.yaml": {"version": "1.1", "sha256": "d" * 64}}),
    lambda kw: kw.__setitem__("applied_thresholds", {"T": 0.5}),
])
def test_input_config_sensitivity_per_component(mutate):
    base = _fp()["input_config_fingerprint"]
    kw = dict(_BASE)
    mutate(kw)
    assert rf.compute_fingerprints(**kw)["input_config_fingerprint"] != base


def test_input_config_sensitivity_to_source_attestation(monkeypatch):
    base = _fp()["input_config_fingerprint"]
    monkeypatch.setattr(rf, "static_import_closure",
                        lambda entry: [("factory/x/y.py", "0" * 64)])
    assert _fp()["input_config_fingerprint"] != base


def test_input_config_sensitivity_to_python_minor(monkeypatch):
    base = _fp()["input_config_fingerprint"]
    real = rf.source_attestation

    def fake_att(entry):
        att = real(entry)
        att["python_version_mm"] = "9.99"
        return att

    monkeypatch.setattr(rf, "source_attestation", fake_att)
    assert _fp()["input_config_fingerprint"] != base


def test_findings_fingerprint_semantic_sensitivity():
    base = rf.findings_fingerprint([_finding()])
    assert rf.findings_fingerprint([_finding(subtype="Y_GAP")]) != base
    assert rf.findings_fingerprint([_finding(source_text="different quote")]) != base
    assert rf.findings_fingerprint([_finding(risk={"band": "HIGH"})]) != base


def test_findings_fingerprint_ignores_list_order_and_volatile_ids():
    f1, f2 = _finding(document="RW-0005", page=1), _finding(document="RW-0006", page=2)
    assert rf.findings_fingerprint([f1, f2]) == rf.findings_fingerprint([f2, f1])
    # run_id de provenance es volatil -> NO debe afectar
    fa = _finding()
    fb = _finding()
    fb.provenance.run_id = "RUN-OTHER"
    assert rf.findings_fingerprint([fa]) == rf.findings_fingerprint([fb])


def test_findings_fingerprint_is_findings_scoped_not_package():
    out = rf.findings_fingerprint([_finding()])
    # es sha256 sobre un objeto {schema, count, findings}, no sobre artefactos de paquete
    assert isinstance(out, str) and len(out) == 64
    assert rf.FINDINGS_SCHEMA == "wp-a/findings/1"


def test_consumed_artifact_scoping_per_entrypoint():
    v2 = rf.consumed_artifacts_for("v2_runtime")
    sc = rf.consumed_artifacts_for("suite_c_formal")
    rc = rf.consumed_artifacts_for("real_corpus_technical")
    assert "technical_suite_c.yaml" not in v2
    assert "technical_suite_c.yaml" in sc
    assert "technical_suite_c.yaml" not in rc
    for s in (v2, sc, rc):
        assert "technical_completeness_rules.yaml" in s
        assert "risk_matrix.yaml" in s
    # los artefactos reales existen y traen version+sha256 (no ABSENT)
    assert v2["technical_completeness_rules.yaml"]["sha256"] != "ABSENT"
    assert v2["technical_completeness_rules.yaml"]["version"] == "1.1"


def test_consumed_artifacts_tier1_requirements_hash_is_order_independent():
    a = rf.consumed_artifacts_for("v2_runtime", tier1_requirements=["X", "Y", "Z"])
    b = rf.consumed_artifacts_for("v2_runtime", tier1_requirements=["Z", "X", "Y"])
    assert a["_TIER1_REQUIREMENTS"]["sha256"] == b["_TIER1_REQUIREMENTS"]["sha256"]
    c = rf.consumed_artifacts_for("v2_runtime", tier1_requirements=["X", "Y"])
    assert c["_TIER1_REQUIREMENTS"]["sha256"] != a["_TIER1_REQUIREMENTS"]["sha256"]


def test_source_attestation_manifest_is_repo_relative_and_real():
    att = rf.source_attestation("factory.regulatory.validation_v2.v2_runtime")
    paths = [m["path"] for m in att["module_manifest"]]
    assert paths, "manifest vacio"
    assert paths == sorted(paths)
    for p in paths:
        assert not p.startswith("/"), p
        assert "/home/" not in p, p
    assert "factory/regulatory/validation_v2/run_fingerprint.py" in paths
    assert "factory/regulatory/graph/build.py" in paths
    assert "factory/regulatory/findings/technical_findings.py" in paths
    assert len(att["module_manifest_sha256"]) == 64


def test_source_attestation_digest_reflects_manifest(monkeypatch):
    d1 = rf.source_attestation_digest(
        {"entrypoint": "e", "module_manifest_sha256": "AAA", "python_version_mm": "3.12"})
    d2 = rf.source_attestation_digest(
        {"entrypoint": "e", "module_manifest_sha256": "BBB", "python_version_mm": "3.12"})
    assert d1 != d2


def test_git_is_advisory_and_degrades_cleanly(monkeypatch):
    def boom(*a, **k):
        raise OSError("no git here")

    monkeypatch.setattr(rf.subprocess, "run", boom)
    g = rf._git_advisory()
    assert g == {"commit": "UNKNOWN", "dirty": None, "describe": None}
    # y el fingerprint sigue computando
    out = _fp()
    assert len(out["input_config_fingerprint"]) == 64
    assert out["run_attestation"]["source_attestation"]["git"]["commit"] == "UNKNOWN"


def test_git_commit_not_in_identity():
    out = _fp()
    real_commit = rf._git_advisory().get("commit")
    blob = json.dumps(out["input_config"], sort_keys=True)
    if real_commit and real_commit != "UNKNOWN":
        assert real_commit not in blob
    # tampoco host/pid/timestamp
    assert out["run_attestation"]["host"] not in blob
    assert "timestamp_utc" not in blob


def test_no_absolute_paths_in_identity():
    out = _fp()
    blob = json.dumps(out["input_config"], sort_keys=True)
    assert str(rf._REPO_ROOT) not in blob
    assert "/home/" not in blob


def test_schema_digests_scoped_and_sensitive(monkeypatch):
    sd = rf.schema_digests()
    assert set(sd) == {"canonical_schema_digest", "graph_schema_digest"}
    assert sd["canonical_schema_digest"] == rf._schema_digest(
        ("factory/regulatory/canonical/model.py", "factory/regulatory/canonical/persistence.py"))
    monkeypatch.setattr(rf, "_SCHEMA_SOURCES",
                        {"canonical_schema_digest": ("factory/regulatory/graph/store.py",),
                         "graph_schema_digest": ("factory/regulatory/graph/store.py",)})
    assert rf.schema_digests()["canonical_schema_digest"] != sd["canonical_schema_digest"]


def test_unknown_entrypoint_rejected():
    with pytest.raises(KeyError):
        rf.compute_fingerprints(entrypoint="nope", inputs=[], extraction_version="v",
                                consumed_artifacts={}, applied_thresholds={}, findings=[])
    with pytest.raises(KeyError):
        rf.consumed_artifacts_for("nope")


def test_run_attestation_has_mandatory_engine_and_routing_source():
    ra = _fp()["run_attestation"]
    assert "active_engine" in ra and ra["active_engine"]
    assert ra["routing_source"] in ("env", "file", "default")


def test_inputs_are_sorted_by_document_id():
    out = _fp()
    ids = [i["document_id"] for i in out["input_config"]["inputs"]]
    assert ids == sorted(ids) == ["D1", "D2"]
