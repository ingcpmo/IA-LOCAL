"""B4b -- corrida REAL de medición del recall V2 sobre el fixture 7P+2N.

docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md FASE 10 (Suite A) +
docs_plan/PREPARACION_PILOT_EXECUTION_B4B.md.

Requiere:
  - los 3 prompts de juicio V2 FIRMADOS (prompts.assert_all_signed()),
  - una PILOT_EXECUTION vigente (human_confirmed) que cubra RW-0005/0011/0012
    con presupuesto suficiente,
  - qwen2.5:7b calificado (model_qualification_gate).

Se ejecuta bajo `local_only.network_locked` -> verifica DOCUMENT_EGRESS = 0.
Checkpoints por unidad (resumible). Hard-stop en `max_calls` antes de
gastar una llamada que lo excedería.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.canonical.persistence import STORE_DIR as CANON_DIR
from factory.regulatory.corpus_runner import _select_pilot_execution_instance
from factory.regulatory.findings.risk import compute_risk  # noqa: F401  (mantiene el paquete importado)
from factory.regulatory.retrieval.evidence_bundle import build_bundles_for_requirement
from factory.regulatory.v2_judgment import prompts
from factory.regulatory.v2_judgment.adjudicator import (
    MACHINE_CONFIRMED, MACHINE_PARTIAL, MACHINE_REJECTED,
)
from factory.regulatory.v2_judgment.judgment_v2 import evaluate_bundle
from factory.regulatory.validation_v2 import gates
from factory.regulatory.validation_v2.local_only import network_locked

_OUT_ROOT = CANON_DIR.parent / "pilot_run" / "v2_b4b"

# Fixture 7P+2N (W5V2_RECALL_FIXTURE_SET_DRAFT.md), sin re-etiquetar.
FIXTURE = [
    ("P1", "positive", "RW-0005", "fda_part11_agent",   "21_CFR_11.10(e)"),
    ("P2", "positive", "RW-0005", "fda_part11_agent",   "21_CFR_11.10(g)"),
    ("P3", "positive", "RW-0005", "eu_annex11_agent",   "ANNEX11_17"),
    ("P4", "positive", "RW-0011", "alcoa_plus_agent",   "ALCOA_ATTRIBUTABLE"),
    ("P5", "positive", "RW-0005", "alcoa_plus_agent",   "ALCOA_CONTEMPORANEOUS"),
    ("P6", "positive", "RW-0011", "fda_cgmp_211_agent", "21_CFR_211.68(b)"),
    ("P7", "positive", "RW-0012", "fda_cgmp_211_agent", "21_CFR_211.68(b)"),
    ("N1", "negative", "RW-0005", "eu_annex11_agent",   "ANNEX11_4"),
    ("N2", "negative", "RW-0005", "fda_part11_agent",   "21_CFR_11.10(e)"),
]

_ROCKWELL = [
    Path("/home/cmay/ivr-ia/GMPAI/source/Rockwell"),
    Path("/home/ing_cpmo/GMPAI/source/Rockwell"),
]
_PDF_BY_DOC = {
    "RW-0005": "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf",
    "RW-0011": "MCCPDC EMS Control Block Narrative revB.pdf",
    "RW-0012": "MCCPDC WFI Control Block Narrative revB.pdf",
}


@dataclass
class UnitResult:
    case_id: str
    kind: str
    document_id: str
    requirement_id: str
    n_subcriteria: int = 0
    calls_made: int = 0
    wall_seconds: float = 0.0
    anchored: bool = False
    fabricated_citation: bool = False   # variante estricta: imposible por construcción
    schema_valid: bool = True
    rejected_count: int = 0
    subcriterion_states: dict = field(default_factory=dict)
    best_quote: str | None = None
    best_page: int | None = None
    error: str | None = None
    hard_stopped: bool = False


def _ensure_canonical(document_ids, canon_dir):
    from factory.regulatory.canonical.extract_document import extract_document
    from factory.regulatory.canonical.persistence import CanonicalStore
    base = next((b for b in _ROCKWELL if b.exists()), None)
    for did in document_ids:
        try:
            with CanonicalStore(did, store_dir=canon_dir) as s:
                if s.all("claim"):
                    continue
        except Exception:  # noqa: BLE001
            pass
        if base is None:
            raise RuntimeError("corpus Rockwell no disponible para poblar canonical_store")
        pdf = base / _PDF_BY_DOC[did]
        tipo = "FS" if did == "RW-0005" else "DS"
        extract_document(pdf, did, tipo=tipo, store_dir=canon_dir)


def _expected_calls(bundles) -> int:
    # A + B por candidato, + Critic (~1 por bundle en el peor caso). Conservador.
    return sum(len(b.candidate_claims) * 2 + 1 for b in bundles)


def run_b4b(*, provider=None, canon_dir=CANON_DIR, out_root: Path = _OUT_ROOT,
            run_id: str | None = None, max_candidates: int = 2,
            variant: str = "strict") -> dict:
    provider = provider or DEFAULT_PROVIDER
    run_id = run_id or f"b4b-{variant}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts.assert_all_signed(variant=variant)

    document_ids = sorted({u[2] for u in FIXTURE})
    selection = _select_pilot_execution_instance(document_ids)
    max_calls = (selection.get("payload") or {}).get("max_calls")
    if not isinstance(max_calls, int) or max_calls <= 0:
        raise RuntimeError(f"PILOT_EXECUTION sin max_calls válido: {max_calls!r}")
    pilot_instance = selection.get("selected_instance_id")

    status = mqg.evaluate_model_qualification(provider).status
    mqg.require_inference_authorized(status, call_type=mqg.CALL_TYPE_INFERENCE, run_context="pilot")

    _ensure_canonical(document_ids, canon_dir)

    meta = {
        "run_id": run_id, "pilot_instance": pilot_instance, "max_calls": max_calls,
        "model": getattr(provider, "model_name", "?"), "max_candidates": max_candidates, "variant": variant,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "fixture_units": len(FIXTURE), "no_effects": True,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    results: list[UnitResult] = []
    calls_made = 0
    stop_reason = "COMPLETE"

    with network_locked() as egress:
        for case_id, kind, doc, agent, req in FIXTURE:
            ur = UnitResult(case_id=case_id, kind=kind, document_id=doc, requirement_id=req)
            t0 = time.monotonic()
            try:
                bundles = build_bundles_for_requirement(doc, req, canon_dir=canon_dir,
                                                        max_candidates=max_candidates)
                ur.n_subcriteria = len(bundles)
                exp = _expected_calls(bundles)
                if calls_made + exp > max_calls:
                    ur.hard_stopped = True
                    ur.wall_seconds = round(time.monotonic() - t0, 1)
                    results.append(ur)
                    _checkpoint(out_dir, results, calls_made)
                    stop_reason = "HARD_STOP_CALLS"
                    break
                for b in bundles:
                    v = evaluate_bundle(b, provider=provider, variant=variant)
                    calls_made += v.calls_made
                    ur.calls_made += v.calls_made
                    ur.subcriterion_states[b.subcriterion_id] = v.state
                    if v.state == MACHINE_REJECTED:
                        ur.rejected_count += 1
                    if v.state in (MACHINE_CONFIRMED, MACHINE_PARTIAL) and v.best_quote:
                        ur.anchored = True
                        ur.best_quote = ur.best_quote or v.best_quote
                        ur.best_page = ur.best_page or v.best_page
            except Exception as e:  # noqa: BLE001 -- se registra y se sigue con la siguiente unidad
                ur.error = f"{type(e).__name__}: {e}"
            ur.wall_seconds = round(time.monotonic() - t0, 1)
            results.append(ur)
            _checkpoint(out_dir, results, calls_made)

    # ── gates ──────────────────────────────────────────────────────────
    case_results = [{
        "case_id": r.case_id, "kind": r.kind, "anchored": r.anchored,
        "fabricated_citation": r.fabricated_citation,
        "schema_valid": r.schema_valid,
        "latency_s": r.wall_seconds,
    } for r in results if not r.hard_stopped]
    gate_report = gates.evaluate_regulatory(case_results)
    interpretation = gates.interpret_regulatory(gate_report)

    report = {
        "meta": {**meta, "finished_at": datetime.now(timezone.utc).isoformat(),
                 "calls_made": calls_made, "stop_reason": stop_reason},
        "local_only": egress.local_only,
        "document_egress_bytes": egress.document_egress_bytes,
        "egress_attempts": egress.attempts,
        "units": [asdict(r) for r in results],
        "gate_report": gate_report.as_dict(),
        "regulatory_interpretation": interpretation,
        "note": ("Instrumento único: el fixture. NO se relajó ningún validador. "
                 "N2 comparte doc+requisito con P1 -- la recuperación V2 es a nivel de "
                 "documento, así que N2 mide lo mismo que P1 (la evidencia real de audit "
                 "trail SÍ está en RW-0005). El negativo estructural que V2 debe rechazar "
                 "es N1 (ANNEX11_4, GAMP5 en lista de referencias)."),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str),
                                         encoding="utf-8")
    return report


def _checkpoint(out_dir: Path, results: list[UnitResult], calls_made: int) -> None:
    (out_dir / "checkpoint.json").write_text(json.dumps({
        "calls_made": calls_made,
        "units_done": [r.case_id for r in results],
        "units": [asdict(r) for r in results],
        "at": datetime.now(timezone.utc).isoformat(),
    }, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    rep = run_b4b()
    print(json.dumps({
        "stop_reason": rep["meta"]["stop_reason"],
        "calls_made": rep["meta"]["calls_made"],
        "local_only": rep["local_only"],
        "document_egress_bytes": rep["document_egress_bytes"],
        "gate_all_passed": rep["gate_report"]["all_passed"],
        "regulatory_interpretation": rep["regulatory_interpretation"],
        "gates": {g["name"]: g["value"] for g in rep["gate_report"]["gates"]},
        "units": {u["case_id"]: {"anchored": u["anchored"], "calls": u["calls_made"],
                                 "wall_s": u["wall_seconds"], "states": u["subcriterion_states"],
                                 "error": u["error"]}
                  for u in rep["units"]},
    }, indent=1, ensure_ascii=False))
