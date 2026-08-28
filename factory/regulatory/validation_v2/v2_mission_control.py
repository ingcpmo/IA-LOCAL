"""Resolvers de Mission Control para las corridas del Analizador V2 (B9b).

Read-only. Leen los artefactos que `v2_runtime.run_v2_pipeline` persiste
bajo `GMPAI/reports/gmpai_document_validation/<run_id>/` (schema
`v2_analyzer_run`). NO reprocesan nada, NO ejecutan inferencia, cero HTTP
externo. Reutilizan el destino operativo existente -- no hay raíz nueva.
"""
from __future__ import annotations

import json
from pathlib import Path

_BASES = (
    Path("/home/cmay/ivr-ia/GMPAI/reports/gmpai_document_validation"),
    Path("/home/ing_cpmo/GMPAI/reports/gmpai_document_validation"),
    Path("GMPAI/reports/gmpai_document_validation"),
)


class V2RunNotFound(RuntimeError):
    pass


def _base() -> Path:
    for b in _BASES:
        if b.exists():
            return b
    return _BASES[-1]


def _is_v2_run(d: Path) -> bool:
    mf = d / "manifest.json"
    if not mf.is_file():
        return False
    try:
        return json.loads(mf.read_text(encoding="utf-8")).get("schema") == "v2_analyzer_run"
    except Exception:  # noqa: BLE001
        return False


def _run_dir(run_id: str) -> Path:
    d = _base() / run_id
    if not _is_v2_run(d):
        raise V2RunNotFound(f"corrida V2 no encontrada: {run_id}")
    return d


def list_v2_runs() -> list[dict]:
    """Resumen de las corridas V2 persistidas, más recientes primero."""
    base = _base()
    out = []
    if not base.exists():
        return out
    for d in sorted(base.iterdir(), reverse=True):
        if not d.is_dir() or not _is_v2_run(d):
            continue
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        out.append({
            "run_id": man.get("run_id"), "project_id": man.get("project_id"),
            "engine": man.get("engine"), "generated_at": man.get("generated_at"),
            "counts": man.get("counts"), "mark": man.get("mark"),
            "qa_status": man.get("qa_status"),
        })
    return out


def get_v2_run(run_id: str) -> dict:
    d = _run_dir(run_id)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    audit = _load(d / "audit_summary" / "audit_metadata.json", {})
    receipt = _load(d / "package_receipt.json", {})
    return {
        "manifest": man, "audit_metadata": audit, "package_receipt": receipt,
        "artifacts": man.get("artifacts", []),
        "human_review_state": {
            "all_unreviewed": audit.get("human_gate_intact"),
            "forbidden_states_present": audit.get("forbidden_states_present"),
            "routing_note": audit.get("routing_note"),
        },
    }


def get_v2_findings(run_id: str, finding_class: str | None = None) -> dict:
    """Findings persistidos por clase. `finding_class` ∈
    {regulatory, functional, technical} o None (todas)."""
    d = _run_dir(run_id)
    files = {"regulatory": "regulatory_findings.json",
             "functional": "functional_findings.json",
             "technical": "technical_findings.json"}
    if finding_class:
        key = finding_class.lower()
        if key not in files:
            raise V2RunNotFound(f"clase desconocida: {finding_class}")
        return {key: _load(d / files[key], [])}
    return {k: _load(d / v, []) for k, v in files.items()}


def get_v2_report(run_id: str) -> str:
    d = _run_dir(run_id)
    p = d / "informe_hallazgos_v2.md"
    if not p.is_file():
        raise V2RunNotFound(f"informe no encontrado para {run_id}")
    return p.read_text(encoding="utf-8")


def get_v2_remediation(run_id: str) -> list[dict]:
    """Propuestas de remediación (Finding → Directive → candidate → redline
    → manifest), todas marcadas MACHINE GENERATED / NOT_QA_APPROVED."""
    d = _run_dir(run_id) / "remediation"
    if not d.is_dir():
        return []
    # los <proposal_id>.json son la propuesta completa; los
    # <proposal_id>.manifest.json son el manifest suelto (se exponen aparte).
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(d.glob("*.json")) if not p.name.endswith(".manifest.json")]


def get_v2_evidence(run_id: str) -> list[dict]:
    return _load(_run_dir(run_id) / "evidence_provenance.json", [])


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default
