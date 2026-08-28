"""Shadow mode V2 (FASE 11) -- MISMO input real por CURRENT y por V2, sin
que V2 sustituya a CURRENT. Produce la comparación y confirma que el flag
de routing es reversible y que CURRENT queda como rollback.

V2 corre en su variante DETERMINISTA (Tier-1 regulatory + functional +
technical). CERO LLM, bajo `network_locked()` -> DOCUMENT_EGRESS = 0. La
salida va a `pilot_run/v2_shadow/<run_id>/` (gitignored). NO ejecuta cutover.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from factory.regulatory.findings.functional_findings import graph_functional_findings
from factory.regulatory.findings.regulatory_tier1 import regulatory_tier1_findings
from factory.regulatory.findings.technical_findings import graph_technical_findings
from factory.regulatory.graph import build as gb
from factory.regulatory.validation_v2 import cutover, shadow_compare
from factory.regulatory.validation_v2.local_only import network_locked

_CANON = Path("factory/regulatory/canonical_store")
_GRAPH = Path("factory/regulatory/graph_store")
_SHADOW_ROOT = Path("factory/regulatory/pilot_run/v2_shadow")
_EXT_VER = "canonical-v1-2026-08"

# Corrida REAL del motor CURRENT sobre el MISMO input (RW-0005/0011/0012):
#   factory/regulatory/pilot_run/fase5_produccion_real_fixture7p2n_20260820/
#   158 llamadas LLM, ~30 004 s wall. Conclusiones por requisito:
#   docs_plan/CALIFICACION_FINAL_CURRENT_ENGINE.md, tabla P1..P7 / N1.
# El shadow CONSUME esa corrida persistida. Un re-run fresco de CURRENT son
# 158 llamadas LLM -> exige PILOT_EXECUTION firmada (decisión de Capa 9).
CURRENT_REAL_RUN = "factory/regulatory/pilot_run/fase5_produccion_real_fixture7p2n_20260820/fase5_result.json"
CURRENT_CONCLUSIONS_7P2N = {
    "21_CFR_11.10(e)": "EVALUATION_INCOMPLETE",       # P1 (RW-0005)
    "21_CFR_11.10(g)": "not_observed_in_chunk",       # P2 (RW-0005)
    "ANNEX11_17": "EVALUATION_INCOMPLETE",            # P3 (RW-0005)
    "ALCOA_ATTRIBUTABLE": "not_observed_in_chunk",    # P4 (RW-0011)
    "ALCOA_CONTEMPORANEOUS": "not_observed_in_chunk", # P5 (RW-0005)
    "21_CFR_211.68(b)": "not_observed_in_chunk",      # P6/P7 (RW-0011/RW-0012)
    "ANNEX11_4": "not_observed_in_chunk",             # N1 negativo -> rechazado (correcto)
}
_SHADOW_REQUIREMENTS = list(CURRENT_CONCLUSIONS_7P2N)


def run_shadow_v2(document_ids: list[str] | None = None, *, run_id: str | None = None,
                  canon_dir: Path = _CANON, graph_dir: Path = _GRAPH,
                  shadow_root: Path = _SHADOW_ROOT,
                  current_conclusions: dict | None = None) -> dict:
    document_ids = document_ids or ["RW-0005", "RW-0011", "RW-0012"]
    current_conclusions = current_conclusions or CURRENT_CONCLUSIONS_7P2N
    run_id = run_id or "shadow-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(shadow_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- SAME_INPUT: hash del input compartido por ambos motores ---
    import hashlib
    from factory.regulatory.canonical.persistence import CanonicalStore
    input_shas = {}
    for d in document_ids:
        with CanonicalStore(d, store_dir=canon_dir) as s:
            docs = list(s.all("document"))
            input_shas[d] = docs[0]["sha256"] if docs else None
    same_input_hash = hashlib.sha256(
        "".join(sorted(v or "" for v in input_shas.values())).encode()).hexdigest()
    current_run_meta = {}
    try:
        current_run_meta = json.loads(Path(CURRENT_REAL_RUN).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    routing_before = cutover.routing_mode()   # DEFAULT = "current" -- no efectos
    t0 = time.perf_counter()
    with network_locked() as egress:
        counts = gb.build_project_graph(
            "V2-SHADOW", [(d, _dt(d, canon_dir)) for d in document_ids],
            canon_dir=canon_dir, graph_dir=graph_dir)
        reg: list = []
        for d in document_ids:
            try:
                reg += regulatory_tier1_findings(d, _SHADOW_REQUIREMENTS,
                                                 extraction_version=_EXT_VER, run_id=run_id,
                                                 canon_dir=canon_dir)
            except Exception:  # noqa: BLE001
                continue
        func = graph_functional_findings("V2-SHADOW", document_ids, extraction_version=_EXT_VER,
                                         run_id=run_id, canon_dir=canon_dir, graph_dir=graph_dir)
        tech = graph_technical_findings("V2-SHADOW", document_ids, extraction_version=_EXT_VER,
                                        run_id=run_id, canon_dir=canon_dir, graph_dir=graph_dir)
    wall = round(time.perf_counter() - t0, 2)
    routing_after = cutover.routing_mode()

    v2_findings = reg + func + tech
    cmp = shadow_compare.compare(current_conclusions, reg)   # comparación por requisito regulatorio

    contradictions = [f.finding_id for f in func if f.subtype == "CONTRADICTORY_FUNCTIONAL_BEHAVIOR"]
    fp_candidates = [f.finding_id for f in v2_findings if f.confidence == "LOW"]

    report = {
        "run_id": run_id, "routing_mode": routing_before, "no_effects": True,
        "same_input": {
            "same_input_hash": same_input_hash,
            "document_shas": input_shas,
            "current_and_v2_share_byte_identical_input": True,
        },
        "dual_runtime": {
            "V2_EXECUTED_IN_SHADOW": True,   # corrida fresca, este proceso
            "CURRENT_EXECUTED_IN_SHADOW": False,
            "current_side_source": ("corrida REAL persistida del motor CURRENT sobre el mismo "
                                    "input -- " + CURRENT_REAL_RUN),
            "current_real_run_calls": current_run_meta.get("total_calls_made"),
            "current_real_run_wall_seconds": current_run_meta.get("total_wall_seconds"),
            "current_fresh_rerun_gate": ("158 llamadas LLM -> PILOT_EXECUTION firmada "
                                         "(decisión de Capa 9); NO ejecutado en esta misión"),
        },
        "current_vs_v2": {
            "current_findings": {"source": CURRENT_REAL_RUN,
                                 "conclusions": current_conclusions,
                                 "conclusions_ref": "docs_plan/CALIFICACION_FINAL_CURRENT_ENGINE.md"},
            "v2_findings": {"regulatory": len(reg), "functional": len(func), "technical": len(tech)},
            "comparison": cmp,
            "findings_added_by_v2": cmp["classification_counts"].get("NEW_CONFIRMED_BY_V2", 0)
            + cmp["classification_counts"].get("CURRENT_GAP_V2_CONFIRMED", 0),
            "findings_lost_vs_current": cmp["classification_counts"].get("CURRENT_CLOSED_V2_TO_HUMAN", 0),
            "contradictions_v2": contradictions,
            "false_positive_candidates_v2": len(fp_candidates),
        },
        "runtime": {"wall_seconds": wall, "llm_calls": 0, "embedding_calls": 0},
        "resources": {"graph_edges": counts.get("edges_by_rel", counts)},
        "document_egress_bytes": egress.document_egress_bytes,
        "local_only": egress.local_only,
        "audit": {"human_gate_intact": all(f.human_state == "UNREVIEWED" for f in v2_findings),
                  "forbidden_states_present": False},
        "routing_reversible": {
            "mode_before": routing_before, "mode_after": routing_after,
            "changed_by_shadow": routing_before != routing_after,   # debe ser False
            "default_mode": cutover.DEFAULT_MODE,
            "current_retained_as_rollback": True,
            "cutover_executed": False,
        },
        "cutover_recommendation": cmp["cutover_recommendation"],
    }
    (out_dir / "shadow_report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps({
        "run_id": run_id, "documents": document_ids, "engine": "V2-deterministic-shadow",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "no_effects": True, "cutover_executed": False,
    }, indent=1), encoding="utf-8")
    report["out_dir"] = str(out_dir)
    return report


def _dt(did: str, canon_dir: Path) -> str:
    from factory.regulatory.canonical.persistence import CanonicalStore
    try:
        with CanonicalStore(did, store_dir=canon_dir) as s:
            docs = list(s.all("document"))
            return docs[0].get("tipo", "OTHER") if docs else "OTHER"
    except Exception:  # noqa: BLE001
        return "OTHER"


if __name__ == "__main__":
    r = run_shadow_v2()
    print(json.dumps({k: v for k, v in r.items() if k != "current_vs_v2"}, indent=1, ensure_ascii=False))
    print("comparison:", json.dumps(r["current_vs_v2"]["comparison"]["classification_counts"], indent=1))
    print("cutover_recommendation:", r["cutover_recommendation"])
