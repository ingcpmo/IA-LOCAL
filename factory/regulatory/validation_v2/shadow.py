"""Shadow mode (V2, B9) -- FASE 11 §1.

Corre el pipeline V2 (B3 EvidenceBundle -> B4 juicio -> B5 Finding) EN
PARALELO a CURRENT, sobre el mismo input, y **SIN EFECTOS**:
  - NO encola a `human_review_queue`
  - NO emite RemediationDirective al almacén real
  - NO escribe audit de producción
Los artefactos van a `factory/regulatory/pilot_run/v2_shadow/<run_id>/`.

`shadow_guard()` es una barrera dura: si algo intenta tocar la cola de
revisión real durante un shadow run, lanza `ShadowEffectViolation`.

B9a (este código): orquestación + guarda + comparador, con provider
MOCKEADO en los tests. B9b (cutover real -- cablear cutover.routing_mode()
en corpus_runner) es una decisión de Capa 9, no está aquí.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.regulatory.findings.from_verdicts import regulatory_findings_from_verdicts
from factory.regulatory.findings.report_v2 import build_report
from factory.regulatory.retrieval.evidence_bundle import build_bundles_for_requirement
from factory.regulatory.v2_judgment.judgment_v2 import evaluate_bundle

_SHADOW_ROOT = (Path(__file__).resolve().parents[1] / "pilot_run" / "v2_shadow")


class ShadowEffectViolation(RuntimeError):
    """Un shadow run intentó un efecto de producción (encolar, auditar,
    emitir directiva). Fail-closed."""


@contextmanager
def shadow_guard():
    """Bloquea las escrituras de producción mientras esté activo."""
    import factory.layer9.human_review_queue as hrq

    real_enqueue = hrq.enqueue
    real_enqueue_finding = hrq.enqueue_finding_for_review
    real_enqueue_gov = getattr(hrq, "enqueue_governance_candidate_for_review", None)

    def _blocked(*a, **k):
        raise ShadowEffectViolation(
            "shadow run intentó encolar a human_review_queue -- prohibido sin cutover")

    hrq.enqueue = _blocked
    hrq.enqueue_finding_for_review = _blocked
    if real_enqueue_gov:
        hrq.enqueue_governance_candidate_for_review = _blocked
    try:
        yield
    finally:
        hrq.enqueue = real_enqueue
        hrq.enqueue_finding_for_review = real_enqueue_finding
        if real_enqueue_gov:
            hrq.enqueue_governance_candidate_for_review = real_enqueue_gov


@dataclass
class ShadowResult:
    run_id: str
    document_id: str
    requirement_ids: list
    findings: list = field(default_factory=list)      # Finding[] (B5)
    report: dict = field(default_factory=dict)
    artifact_dir: str = ""
    calls_made: int = 0


def run_shadow(document_id: str, requirement_ids: list[str], *, provider,
               run_id: str | None = None, canon_dir=None, extraction_version: str = "canonical-v1-2026-08",
               shadow_root: Path = _SHADOW_ROOT, persist: bool = True) -> ShadowResult:
    """`provider`: ModelProvider (mockeado en B9a). Requiere canonical_store
    poblado (B1) para `document_id`."""
    run_id = run_id or f"v2shadow-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    res = ShadowResult(run_id=run_id, document_id=document_id, requirement_ids=list(requirement_ids))

    with shadow_guard():
        pairs = []
        for req_id in requirement_ids:
            kw = {"canon_dir": canon_dir} if canon_dir is not None else {}
            bundles = build_bundles_for_requirement(document_id, req_id, **kw)
            for b in bundles:
                v = evaluate_bundle(b, provider=provider)
                res.calls_made += v.calls_made
                pairs.append((v, b))
        res.findings = regulatory_findings_from_verdicts(
            pairs, document_id=document_id, extraction_version=extraction_version,
            run_id=run_id, agent_id="v2_shadow")

    res.report = build_report(res.findings, document_id=document_id, run_id=run_id)

    if persist:
        d = shadow_root / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "report.json").write_text(
            json.dumps(res.report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        (d / "meta.json").write_text(json.dumps({
            "run_id": run_id, "document_id": document_id, "requirement_ids": requirement_ids,
            "calls_made": res.calls_made, "no_effects": True,
            "note": "SHADOW -- sin encolar, sin directivas, sin audit de producción",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        res.artifact_dir = str(d)
    return res
