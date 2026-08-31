"""H-4 (2026-08-29) -- snapshot INMUTABLE del grafo por corrida + digest SEPARADO.

Diseno (ajuste previo a la implementacion, paso 3 de la mision):
  - El grafo es un artefacto DERIVADO, NO una entrada.
  - `INPUT_CONFIG_FINGERPRINT` NO lo incorpora (nunca hubo `graph_state_digest`
    dentro de input_config; este test lo fija como invariante).
  - Se calcula `GRAPH_SNAPSHOT_FINGERPRINT` por separado (topologia del grafo).
  - `RUN_ATTESTATION.fingerprints` liga los tres: input_config / graph_snapshot /
    findings. Ninguno contiene al otro.

Criterios de aceptacion cubiertos:
  C1  same inputs               -> same graph fingerprint   (determinista, cross-proceso)
  C2  modified graph            -> different graph fingerprint
  C3  graph_path exists          for graph-dependent findings
  C4  prior run snapshot         remains unchanged (inmutable por run_id)
  +   findings_fingerprint       == linea base post-H1/H2/H3 (b5196a71...)
  +   input_config_fingerprint   independiente del grafo
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.regulatory.validation_v2 import run_fingerprint as rf

#: linea base post-H1/H2/H3 (docs_plan/CIERRE_BLOQUE_H1_H2_H3_20260829.md).
_FINDINGS_FP_BASELINE = "b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e"

_DOCS = ["RW-0005", "RW-0006", "RW-0009", "RW-0011", "RW-0012", "RW-0014"]


# ---------------------------------------------------------------------------
# unit -- normalize_graph_snapshot / graph_snapshot_fingerprint
# ---------------------------------------------------------------------------
def _nodes():
    return [
        {"node_id": "n2", "kind": "claim", "document_id": "D1", "label": "beta", "attrs": {"pagina": 2}},
        {"node_id": "n1", "kind": "requirement", "document_id": None, "label": "alpha", "attrs": {}},
        {"node_id": "n3", "kind": "section", "document_id": "D1", "label": "gamma", "attrs": {"numero": "4.1"}},
    ]


def _edges():
    return [
        {"src_id": "n1", "dst_id": "n2", "rel": "implemented_by", "attrs": {"via_ref": "5.2.5"}},
        {"src_id": "n3", "dst_id": "n2", "rel": "designed_by", "attrs": {}},
    ]


def test_graph_fingerprint_is_input_order_independent():
    a = rf.normalize_graph_snapshot(_nodes(), _edges())
    b = rf.normalize_graph_snapshot(list(reversed(_nodes())), list(reversed(_edges())))
    assert rf.graph_snapshot_fingerprint(a) == rf.graph_snapshot_fingerprint(b)
    assert a["node_count"] == 3 and a["edge_count"] == 2


def test_graph_fingerprint_ignores_non_topological_attrs():
    """`edge.attrs['via_ref']` lo escribe build._safe_edge con 'ultimo ref que
    caso gana'; el orden de iteracion del set de refs varia con PYTHONHASHSEED
    entre procesos. Misma topologia, distinto via_ref -> MISMO fingerprint."""
    base = rf.normalize_graph_snapshot(_nodes(), _edges())
    e2 = _edges()
    e2[0]["attrs"] = {"via_ref": "PCSSR011"}          # mismo (src,dst,rel), otra glosa
    n2 = _nodes()
    n2[0]["attrs"] = {"pagina": 999, "extra": "x"}     # attrs de nodo tambien fuera del digest
    variant = rf.normalize_graph_snapshot(n2, e2)
    assert rf.graph_snapshot_fingerprint(base) == rf.graph_snapshot_fingerprint(variant)


@pytest.mark.parametrize("mutate", ["drop_edge", "add_edge", "rename_node", "retype_edge", "move_edge"])
def test_modified_graph_changes_fingerprint(mutate):
    base = rf.normalize_graph_snapshot(_nodes(), _edges())
    ns, es = _nodes(), _edges()
    if mutate == "drop_edge":
        es = es[:-1]
    elif mutate == "add_edge":
        es.append({"src_id": "n1", "dst_id": "n3", "rel": "regulated_by", "attrs": {}})
    elif mutate == "rename_node":
        ns[0]["label"] = ns[0]["label"] + " (edited)"
    elif mutate == "retype_edge":
        es[0]["rel"] = "designed_by"
    elif mutate == "move_edge":
        es[0]["dst_id"] = "n3"
    variant = rf.normalize_graph_snapshot(ns, es)
    assert rf.graph_snapshot_fingerprint(base) != rf.graph_snapshot_fingerprint(variant)


def test_graph_fingerprint_deterministic_across_processes():
    """Se construye el snapshot desde los 4 GraphStore que quedaron en
    factory/regulatory/graph_store/ (cada uno poblado por una corrida distinta,
    potencialmente bajo otro PYTHONHASHSEED). La topologia es identica ->
    el fingerprint debe coincidir. Si no hay stores, se omite."""
    store_dir = Path("factory/regulatory/graph_store")
    pids = [p.stem for p in store_dir.glob("*.sqlite3")] if store_dir.exists() else []
    fps: dict[str, str] = {}
    for pid in pids:
        try:
            snap = rf.graph_snapshot_from_store(pid, store_dir)
        except Exception:
            continue
        if snap["node_count"] == 3342 and snap["edge_count"] == 1344:   # topologia del corpus RW de 6 docs
            fps[pid] = rf.graph_snapshot_fingerprint(snap)
    if len(fps) < 2:
        pytest.skip("menos de 2 GraphStore del corpus RW-6 disponibles para comparar")
    assert len(set(fps.values())) == 1, f"graph fingerprint no determinista entre stores: {fps}"


# ---------------------------------------------------------------------------
# unit -- separacion de los tres fingerprints
# ---------------------------------------------------------------------------
_CF_BASE = dict(
    entrypoint="v2_runtime",
    inputs=[{"document_id": "D1", "sha256": "a" * 64}],
    extraction_version="canonical-v1-2026-08",
    consumed_artifacts={"foo.yaml": {"version": "1", "sha256": "c" * 64}},
    applied_thresholds={},
    findings=[],
)


def test_graph_snapshot_is_not_part_of_input_config_fingerprint():
    without = rf.compute_fingerprints(**_CF_BASE)
    snap = rf.normalize_graph_snapshot(_nodes(), _edges())
    with_graph = rf.compute_fingerprints(**_CF_BASE, graph_snapshot=snap)
    # el grafo NO mueve input_config ...
    assert without["input_config_fingerprint"] == with_graph["input_config_fingerprint"]
    # ... y sin grafo el digest derivado es None; con grafo, es un sha256.
    assert without["graph_snapshot_fingerprint"] is None
    assert with_graph["graph_snapshot_fingerprint"] == rf.graph_snapshot_fingerprint(snap)
    # cambiar la topologia mueve SOLO graph_snapshot_fingerprint.
    snap2 = rf.normalize_graph_snapshot(_nodes(), _edges()[:-1])
    other = rf.compute_fingerprints(**_CF_BASE, graph_snapshot=snap2)
    assert other["input_config_fingerprint"] == with_graph["input_config_fingerprint"]
    assert other["graph_snapshot_fingerprint"] != with_graph["graph_snapshot_fingerprint"]


def test_run_attestation_ties_the_three_fingerprints():
    snap = rf.normalize_graph_snapshot(_nodes(), _edges())
    out = rf.compute_fingerprints(**_CF_BASE, graph_snapshot=snap)
    tied = out["run_attestation"]["fingerprints"]
    assert set(tied) == {"input_config_fingerprint", "graph_snapshot_fingerprint", "findings_fingerprint"}
    assert tied["input_config_fingerprint"] == out["input_config_fingerprint"]
    assert tied["graph_snapshot_fingerprint"] == out["graph_snapshot_fingerprint"]
    assert tied["findings_fingerprint"] == out["findings_fingerprint"]


def test_findings_fingerprint_unaffected_by_graph_path_value():
    """provenance.graph_path es un PUNTERO a un artefacto derivado -- se puebla
    (v2_runtime._stamp_graph_path) sin mover findings_fingerprint, porque
    _normalized_finding fija su valor a None."""
    def _f(graph_path):
        p = SimpleNamespace(agent_id="a", extraction_version="v", subcriterion_ref=None,
                            adjudicator_state=None, graph_path=graph_path, run_id="R")
        return SimpleNamespace(
            finding_id="fnd-x", finding_class="RegulatoryFinding", subtype="MISSING",
            severity="HIGH", document="RW-0006", page=6, section="4", source_hash="h" * 64,
            source_text="q", requirement_id="ANNEX11_9", regulatory_basis="Annex 11 #9",
            technical_basis=None, risk={"band": "HIGH"}, confidence=0.6,
            machine_state="MACHINE_DEVIATION_CANDIDATE", human_state="UNREVIEWED",
            rationale="r", evidence_ids=[], related_finding_ids=[], provenance=p)
    none_fp = rf.findings_fingerprint([_f(None)])
    stamped_fp = rf.findings_fingerprint([_f(["graph_snapshot/graph_snapshot.json",
                                              {"graph_snapshot_fingerprint": "z" * 64}])])
    assert none_fp == stamped_fp


# ---------------------------------------------------------------------------
# integration -- pipeline E2E real (0 LLM, Tier-1 / Palanca C)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _two_runs():
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    from factory.regulatory.validation_v2 import coverage_mode as _cm
    # H-4 se aceptó en OBSERVE y su criterio (independencia grafo↔findings) no
    # depende del modo de cobertura. Tras D-2 el repo está en ENFORCE, así que se
    # fuerza OBSERVE aquí para reproducir la baseline documentada `b5196a71…`.
    import pytest as _pt
    _mp = _pt.MonkeyPatch()
    _cfg = Path(tempfile.mkdtemp(prefix="h4-obs-cfg-")) / "analysis_coverage_mode.yaml"
    _cfg.write_text("mode: OBSERVE\ndecided_by: null\ndecision_ref: null\ndecision_date: null\n")
    _mp.setattr(_cm, "_MODE_PATH", _cfg)
    _mp.setattr(_cm, "_thresholds_signed", lambda: False)
    base = Path(tempfile.mkdtemp(prefix="h4-e2e-"))
    try:
        run_v2_pipeline(_DOCS, project_id="H4-E2E", run_id="r1", report_base=base)
        r1_snap_bytes_before = (base / "r1" / "graph_snapshot" / "graph_snapshot.json").read_bytes()
        run_v2_pipeline(_DOCS, project_id="H4-E2E", run_id="r2", report_base=base)
        r1_snap_bytes_after = (base / "r1" / "graph_snapshot" / "graph_snapshot.json").read_bytes()
        _out = SimpleNamespace(
            base=base,
            a1=json.loads((base / "r1" / "audit_summary" / "audit_metadata.json").read_text()),
            a2=json.loads((base / "r2" / "audit_summary" / "audit_metadata.json").read_text()),
            r1_before=r1_snap_bytes_before,
            r1_after=r1_snap_bytes_after,
        )
    finally:
        _mp.undo()   # el override OBSERVE solo vive durante la corrida; nunca filtra a otros tests
    return _out


def _all_finding_rows(run_dir: Path):
    rows = []
    for k in ("regulatory", "functional", "technical"):
        rows += json.loads((run_dir / f"{k}_findings.json").read_text())
    return rows


def test_e2e_same_inputs_same_graph_fingerprint(_two_runs):
    # C1: dos corridas de los mismos documentos -> mismo graph_snapshot_fingerprint.
    assert _two_runs.a1["graph_snapshot_fingerprint"] == _two_runs.a2["graph_snapshot_fingerprint"]
    assert _two_runs.a1["input_config_fingerprint"] == _two_runs.a2["input_config_fingerprint"]
    assert _two_runs.a1["findings_fingerprint"] == _two_runs.a2["findings_fingerprint"]


def test_e2e_findings_fingerprint_matches_post_h1h2h3_baseline(_two_runs):
    assert _two_runs.a1["findings_fingerprint"] == _FINDINGS_FP_BASELINE


def test_e2e_attestation_ties_three_and_audit_exposes_graph_digest(_two_runs):
    a1 = _two_runs.a1
    tied = a1["run_attestation"]["fingerprints"]
    assert tied["input_config_fingerprint"] == a1["input_config_fingerprint"]
    assert tied["graph_snapshot_fingerprint"] == a1["graph_snapshot_fingerprint"]
    assert tied["findings_fingerprint"] == a1["findings_fingerprint"]
    assert a1["graph_snapshot_path"] == "graph_snapshot/graph_snapshot.json"


def test_e2e_graph_dependent_findings_carry_graph_path(_two_runs):
    # C3: todo hallazgo dependiente del estado del grafo lleva provenance.graph_path
    # apuntando al snapshot inmutable, con el fingerprint que coincide.
    rows = _all_finding_rows(_two_runs.base / "r1")
    gp_subtypes = {"REQUIREMENT_NOT_TESTED", "ORPHAN_DESIGN_ELEMENT", "IMPLEMENTATION_WITHOUT_REQUIREMENT"}
    dependent = [r for r in rows
                 if r.get("evidence_basis") == "ABSENCE_DEPENDENT" or r.get("subtype") in gp_subtypes]
    assert dependent, "el corpus RW-6 deberia producir hallazgos dependientes del grafo"
    snap_fp = _two_runs.a1["graph_snapshot_fingerprint"]
    for r in dependent:
        gpath = r.get("provenance", {}).get("graph_path")
        assert gpath, f"sin graph_path: {r['finding_id']} ({r.get('subtype')})"
        assert gpath[0] == "graph_snapshot/graph_snapshot.json"
        assert gpath[1]["graph_snapshot_fingerprint"] == snap_fp


def test_e2e_non_dependent_findings_do_not_get_a_graph_path(_two_runs):
    rows = _all_finding_rows(_two_runs.base / "r1")
    gp_subtypes = {"REQUIREMENT_NOT_TESTED", "ORPHAN_DESIGN_ELEMENT", "IMPLEMENTATION_WITHOUT_REQUIREMENT"}
    non_dependent = [r for r in rows
                     if r.get("evidence_basis") != "ABSENCE_DEPENDENT" and r.get("subtype") not in gp_subtypes]
    # ninguno recibe graph_path por el post-pass (solo lo tendrian si ya lo traian,
    # p.ej. familias refers_to/contradicts que hoy no se emiten).
    assert all(not r.get("provenance", {}).get("graph_path") for r in non_dependent)


def test_e2e_prior_run_snapshot_is_immutable(_two_runs):
    # C4: la corrida r2 NO altera el snapshot de r1.
    assert _two_runs.r1_before == _two_runs.r1_after
    snap = json.loads(_two_runs.r1_before)
    assert snap["run_id"] == "r1"
    assert snap["graph_snapshot_fingerprint"] == _two_runs.a1["graph_snapshot_fingerprint"]
    # y el fingerprint es re-derivable del contenido del propio snapshot.
    assert rf.graph_snapshot_fingerprint(snap) == _two_runs.a1["graph_snapshot_fingerprint"]


def test_e2e_snapshot_is_never_overwritten(_two_runs):
    # re-usar run_id + report_base -> el guardia de H-4 aborta (nunca se pisa).
    from factory.regulatory.validation_v2.v2_runtime import run_v2_pipeline
    with pytest.raises(RuntimeError, match="NUNCA se sobrescribe"):
        run_v2_pipeline(_DOCS, project_id="H4-E2E", run_id="r1", report_base=_two_runs.base)
