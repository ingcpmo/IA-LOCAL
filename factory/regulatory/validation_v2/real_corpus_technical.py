"""Validación TECHNICAL sobre el corpus REAL Rockwell -- SEPARADA del benchmark.

Corre B6b v1 (grafo) + v2 (reglas de completitud gobernadas, context-scoped
v1.1) sobre RW-0005/0006/0009/0011/0012/0014 y persiste findings reales con
todos los campos. NO usa C01..C20 como obligación. Determinista, sin LLM,
bajo `network_locked()` (DOCUMENT_EGRESS = 0).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from factory.regulatory.findings.technical_findings import graph_technical_findings
from factory.regulatory.graph import build as gb
from factory.regulatory.validation_v2.local_only import network_locked

CANON_DIR = Path("factory/regulatory/canonical_store")
GRAPH_DIR = Path("factory/regulatory/graph_store")
OUT_ROOT = Path("factory/regulatory/pilot_run/technical_real_corpus")
PROJECT_ID = "RW-TECH-REAL"
_EXT_VER = "canonical-v1-2026-08"

RW_DOCS = [("RW-0005", "FS"), ("RW-0006", "URS"), ("RW-0009", "SAT"),
           ("RW-0011", "DS"), ("RW-0012", "DS"), ("RW-0014", "DS")]


def _finding_dict(f) -> dict:
    p = f.provenance
    return {
        "finding_id": f.finding_id,
        "class": f.finding_class,
        "subtype": f.subtype,
        "severity": f.severity,
        "document": f.document,
        "page": f.page,
        "section": f.section,
        "source_text": f.source_text,
        "source_hash": f.source_hash,
        "requirement": f.requirement_id or getattr(p, "subcriterion_ref", None),
        "regulatory_basis": f.regulatory_basis,
        "technical_basis": f.technical_basis,
        "evidence": {"anchored_quote": f.source_text, "evidence_ids": list(f.evidence_ids)},
        "risk": f.risk,
        "rationale": f.rationale,
        "provenance": {
            "document_id": p.document_id,
            "extraction_version": p.extraction_version,
            "run_id": p.run_id,
            "agent_id": p.agent_id,
            "subcriterion_ref": getattr(p, "subcriterion_ref", None),
            "graph_path": getattr(p, "graph_path", None),
        },
        "confidence": f.confidence,
        "machine_state": f.machine_state,
        "human_state": f.human_state,
        "related_finding_ids": list(f.related_finding_ids),
        "evidence_basis": getattr(f, "evidence_basis", None),   # WP-B
    }


def run_real_corpus_technical(out_root: Path = OUT_ROOT, run_id: str | None = None,
                              canon_dir: Path = CANON_DIR, graph_dir: Path = GRAPH_DIR) -> dict:
    run_id = run_id or "rw-tech-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    with network_locked() as egress:
        counts = gb.build_project_graph(PROJECT_ID, RW_DOCS, canon_dir=canon_dir, graph_dir=graph_dir)
        stats: dict = {}
        findings = graph_technical_findings(
            PROJECT_ID, [d for d, _ in RW_DOCS], extraction_version=_EXT_VER,
            run_id=run_id, canon_dir=canon_dir, graph_dir=graph_dir, stats=stats)
    finished = datetime.now(timezone.utc).isoformat()

    # WP-B OBSERVE: adecuación de extracción + evidence_basis (metadata aditiva; 0 supresión).
    from factory.regulatory.findings import evidence_basis as _eb
    from factory.regulatory.validation_v2 import extraction_adequacy as _adq
    _eb.stamp(findings)
    _rw_ids = [d for d, _ in RW_DOCS]
    _graph_edges = counts.get("edges_by_rel", counts) if isinstance(counts, dict) else {}
    try:
        _assessment = _adq.assess_corpus(_rw_ids, canon_dir)
        _assessment["mode"] = "OBSERVE"
        _cov_deps = _eb.coverage_dependencies(findings, _assessment,
                                              graph_edges=_graph_edges, canon_dir=canon_dir)
        analysis_coverage = {
            "mode": "OBSERVE",
            "thresholds_artifact": _assessment.get("thresholds_artifact"),
            "thresholds_signed": _assessment.get("thresholds_signed"),
            "coverage_statement": _adq.coverage_statement(_assessment),
            "adequacy_by_document": _assessment.get("by_document", {}),
            "adequacy_verdicts": _assessment.get("verdicts", {}),
            "role_stats_observational": _assessment.get("role_stats_observational", {}),
            "coverage_dependencies": _cov_deps,
            "would_degrade_histogram": _eb.histogram(_cov_deps),
        }
    except Exception as e:  # noqa: BLE001
        analysis_coverage = {"mode": "OBSERVE", "error": f"{type(e).__name__}: {e}"}

    fds = [_finding_dict(f) for f in findings]
    by_subtype: dict[str, int] = {}
    by_doc: dict[str, int] = {}
    for d in fds:
        by_subtype[d["subtype"]] = by_subtype.get(d["subtype"], 0) + 1
        by_doc[d["document"]] = by_doc.get(d["document"], 0) + 1

    # WP-A: fingerprint de corrida (100% aditivo).
    from factory.regulatory.validation_v2 import run_fingerprint as _fp
    _wall = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
    _fpr = _fp.compute_fingerprints(
        entrypoint="real_corpus_technical",
        inputs=_fp.inputs_from_canon([d for d, _ in RW_DOCS], canon_dir),
        extraction_version=_EXT_VER,
        consumed_artifacts=_fp.consumed_artifacts_for("real_corpus_technical"),
        applied_thresholds={},
        findings=findings,
        wall_clock_seconds=_wall,
    )

    meta = {
        "run_id": run_id, "project_id": PROJECT_ID,
        "documents": RW_DOCS, "extraction_version": _EXT_VER,
        "governed_rules": "technical_completeness_rules.yaml v1.1 SIGNED (context_scoped)",
        "started_at": started, "finished_at": finished,
        "local_only": egress.local_only,
        "document_egress_bytes": egress.document_egress_bytes,
        "graph_edges": counts.get("edges_by_rel", counts),
        "stats": stats,
        "n_findings": len(fds),
        "by_subtype": by_subtype, "by_document": by_doc,
        "input_config_fingerprint": _fpr["input_config_fingerprint"],
        "findings_fingerprint": _fpr["findings_fingerprint"],
        "schema_digests": _fpr["schema_digests"],
        "input_config": _fpr["input_config"],
        "run_attestation": _fpr["run_attestation"],
        "analysis_coverage": analysis_coverage,   # WP-B OBSERVE
        "note": ("Validación real, NO benchmark. Todos los findings human_state=UNREVIEWED "
                 "-> revisión humana. OD-1..OD-5 se conservan como observaciones (ver "
                 "docs_plan/VALIDACION_TECNICA_CORPUS_REAL_RW.md), NO cambian Suite C."),
    }
    (out_dir / "technical_findings.json").write_text(
        json.dumps({"meta": meta, "findings": fds}, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"out_dir": str(out_dir), **meta}


if __name__ == "__main__":
    r = run_real_corpus_technical()
    print(json.dumps({k: v for k, v in r.items() if k != "stats"}, indent=1, ensure_ascii=False))
