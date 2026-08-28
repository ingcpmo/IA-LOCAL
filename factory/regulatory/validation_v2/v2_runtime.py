"""Runtime V2 E2E -- FASE 11 / B9b. Cierra REPORTING_GAP_CONFIRMED=YES.

Orquesta el analizador V2 de punta a punta para un conjunto de documentos y
PERSISTE los resultados bajo el destino operativo EXISTENTE
`GMPAI/reports/gmpai_document_validation/<run_id>/` (sin raices nuevas),
reutilizando la convencion de layout y el marcado de
`factory/services/gmpai_artifact_service.py` /
`factory/services/candidate_document_generator.py`.

Pipeline:
  ingestion (canonical_store ya poblado, B1)
   -> graph (B2)
   -> retrieval/evidence (B3, BM25 determinista)
   -> regulatory findings   (Tier-1 / Palanca C, CERO LLM)
   -> functional findings    (B6a determinista)
   -> technical findings     (B6b v1+v2 determinista, artefacto v1.1 SIGNED)
   -> risk (determinista, risk_matrix.yaml)
   -> remediation (Finding -> Directive -> candidate -> redline -> manifest)
   -> reporting (report_v2)
   -> persistence + hashes + manifest + package_receipt + audit metadata

CERO LLM. Bajo `network_locked()` -> DOCUMENT_EGRESS = 0. Los artefactos
generados quedan marcados "MACHINE GENERATED -- BORRADOR, NO APROBADO" y
NUNCA en estado QA_APPROVED / RELEASED / CAPA_CLOSED / FINAL_GMP_APPROVAL.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from factory.regulatory.findings import report_v2
from factory.regulatory.findings.functional_findings import graph_functional_findings
from factory.regulatory.findings.regulatory_tier1 import regulatory_tier1_findings
from factory.regulatory.findings.remediation_v2 import (
    MACHINE_GENERATED_MARK, QA_STATUS_DRAFT, RemediationChain, apply_and_redline,
    build_proposal, to_current_pipeline_change,
)
from factory.regulatory.findings.technical_findings import graph_technical_findings
from factory.regulatory.graph import build as gb
from factory.regulatory.validation_v2.local_only import network_locked

_CANON = Path("factory/regulatory/canonical_store")
_GRAPH = Path("factory/regulatory/graph_store")
_EXT_VER = "canonical-v1-2026-08"

# destino operativo EXISTENTE -- se resuelve dinamicamente (clon local o servidor)
_REPORT_BASE_CANDIDATES = (
    Path("/home/cmay/ivr-ia/GMPAI/reports/gmpai_document_validation"),
    Path("/home/ing_cpmo/GMPAI/reports/gmpai_document_validation"),
    Path("GMPAI/reports/gmpai_document_validation"),
)

# sub-criterios regulatorios evaluados por Tier-1 (determinista)
_TIER1_REQUIREMENTS = [
    "21_CFR_11.10(d)", "21_CFR_11.10(e)", "21_CFR_11.10(g)", "21_CFR_11.50_11.70",
    "ANNEX11_7.1", "ANNEX11_9", "ANNEX11_12", "ANNEX11_17",
    "ALCOA_ATTRIBUTABLE", "ALCOA_LEGIBLE", "ALCOA_CONTEMPORANEOUS", "ALCOA_ORIGINAL",
]

_FORBIDDEN = ("QA_APPROVED", "RELEASED", "CAPA_CLOSED", "FINAL_GMP_APPROVAL", "APPROVED")


def _report_base() -> Path:
    for c in _REPORT_BASE_CANDIDATES:
        if c.parent.exists():
            return c
    return _REPORT_BASE_CANDIDATES[-1]


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _finding_row(f) -> dict:
    p = f.provenance
    return {
        "finding_id": f.finding_id, "class": f.finding_class, "subtype": f.subtype,
        "severity": f.severity, "document": f.document, "page": f.page,
        "section": f.section, "source_text": f.source_text, "source_hash": f.source_hash,
        "requirement": f.requirement_id or getattr(p, "subcriterion_ref", None),
        "regulatory_basis": f.regulatory_basis, "technical_basis": f.technical_basis,
        "evidence": {"anchored_quote": f.source_text, "evidence_ids": list(f.evidence_ids)},
        "risk": f.risk, "rationale": f.rationale,
        "provenance": {"document_id": p.document_id, "extraction_version": p.extraction_version,
                       "run_id": p.run_id, "agent_id": p.agent_id,
                       "subcriterion_ref": getattr(p, "subcriterion_ref", None),
                       "adjudicator_state": getattr(p, "adjudicator_state", None),
                       "graph_path": getattr(p, "graph_path", None)},
        "confidence": f.confidence, "machine_state": f.machine_state,
        "human_state": f.human_state, "related_finding_ids": list(f.related_finding_ids),
    }


def _proposed_text_for(f) -> str:
    """Texto de remediacion DETERMINISTA y templado (CERO LLM). Es un
    borrador: nombra el comportamiento requerido, no lo redacta 'a medida'."""
    basis = f.regulatory_basis or f.technical_basis or f.requirement_id or "la fuente normativa aplicable"
    return (f"[{MACHINE_GENERATED_MARK}] Anadir a la seccion correspondiente una descripcion "
            f"explicita del comportamiento requerido por {basis} que el analizador NO encontro "
            f"anclado en el documento (ver rationale del hallazgo {f.finding_id}). "
            f"Este texto es un BORRADOR -- NO APROBADO; requiere redaccion y revision de QA.")


def run_v2_pipeline(document_ids: list[str], *, project_id: str = "V2-E2E",
                    run_id: str | None = None, canon_dir: Path = _CANON,
                    graph_dir: Path = _GRAPH, report_base: Path | None = None,
                    remediation_limit: int = 8) -> dict:
    run_id = run_id or "v2e2e-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = Path(report_base) if report_base else _report_base()
    run_dir = base / run_id
    (run_dir / "compliance_matrices").mkdir(parents=True, exist_ok=True)
    (run_dir / "agent_reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "corrected_documents").mkdir(parents=True, exist_ok=True)
    (run_dir / "remediation").mkdir(parents=True, exist_ok=True)
    (run_dir / "audit_summary").mkdir(parents=True, exist_ok=True)

    started = datetime.now(timezone.utc).isoformat()
    with network_locked() as egress:
        # --- graph (B2) ---
        docs_typed = []
        for did in document_ids:
            docs_typed.append((did, _doc_type(did, canon_dir)))
        counts = gb.build_project_graph(project_id, docs_typed, canon_dir=canon_dir, graph_dir=graph_dir)

        # --- regulatory (Tier-1 / Palanca C, CERO LLM) ---
        reg: list = []
        for did in document_ids:
            try:
                reg += regulatory_tier1_findings(
                    did, _TIER1_REQUIREMENTS, extraction_version=_EXT_VER, run_id=run_id,
                    canon_dir=canon_dir)
            except Exception:  # noqa: BLE001 -- un requisito sin catalogo no aborta la corrida
                continue

        # --- functional (B6a determinista) ---
        func = graph_functional_findings(
            project_id, document_ids, extraction_version=_EXT_VER, run_id=run_id,
            canon_dir=canon_dir, graph_dir=graph_dir)

        # --- technical (B6b v1+v2 determinista, artefacto v1.1 SIGNED) ---
        tech = graph_technical_findings(
            project_id, document_ids, extraction_version=_EXT_VER, run_id=run_id,
            canon_dir=canon_dir, graph_dir=graph_dir)

    all_findings = reg + func + tech
    _assert_no_forbidden(all_findings)

    # --- persistence: findings + evidence/provenance ---
    _write_json(run_dir / "regulatory_findings.json", [_finding_row(f) for f in reg])
    _write_json(run_dir / "functional_findings.json", [_finding_row(f) for f in func])
    _write_json(run_dir / "technical_findings.json", [_finding_row(f) for f in tech])
    _write_json(run_dir / "evidence_provenance.json",
                [{"finding_id": f.finding_id, "document": f.document, "page": f.page,
                  "section": f.section, "source_hash": f.source_hash,
                  "extraction_version": f.provenance.extraction_version,
                  "anchored_quote": f.source_text} for f in all_findings])

    # --- remediation chain: Finding -> Directive -> candidate -> redline -> manifest ---
    # candidate/redline .docx materializados REUTILIZANDO candidate_document_generator
    # de CURRENT (sin duplicar arquitectura). Todos MACHINE GENERATED / NOT_QA_APPROVED.
    from factory.services.candidate_document_generator import (
        generate_candidate_document, generate_redline_document,
    )
    remediation = []
    rem_candidates = [f for f in all_findings
                      if f.machine_state in ("MACHINE_DEVIATION_CANDIDATE", "MACHINE_CONFIRMED_FINDING")][:remediation_limit]
    # agrupar por documento destino para generar 1 candidate/redline .docx por doc
    by_target: dict[str, list] = {}
    props_by_finding: dict[str, object] = {}
    redlines_by_finding: dict[str, object] = {}
    for f in rem_candidates:
        prop = build_proposal(f, proposed_text=_proposed_text_for(f), change_type="insert_after")
        redline = apply_and_redline(prop)
        props_by_finding[f.finding_id] = prop
        redlines_by_finding[f.finding_id] = redline
        by_target.setdefault(prop.target_document, []).append(f)

    docx_shas: dict[str, dict] = {}   # doc_id -> {candidate_sha, redline_sha, insertion_manifest}
    for doc_id, fs in by_target.items():
        try:
            structure = _structure_from_canon(doc_id, canon_dir)
            changes = [_current_change(props_by_finding[f.finding_id], structure) for f in fs]
            cand = generate_candidate_document(structure, changes)
            red, ins_manifest = generate_redline_document(structure, changes)
            cpath = run_dir / "corrected_documents" / f"{doc_id}_candidate.docx"
            rpath = run_dir / "corrected_documents" / f"{doc_id}_redline.docx"
            cand.save(str(cpath)); red.save(str(rpath))
            docx_shas[doc_id] = {
                "candidate_path": str(cpath), "redline_path": str(rpath),
                "candidate_sha256": _sha256_bytes(cpath.read_bytes()),
                "redline_sha256": _sha256_bytes(rpath.read_bytes()),
                "insertion_manifest": ins_manifest,
            }
        except Exception as e:  # noqa: BLE001 -- un doc sin estructura utilizable no aborta la cadena
            docx_shas[doc_id] = {"error": f"{type(e).__name__}: {e}"}

    for f in rem_candidates:
        prop = props_by_finding[f.finding_id]
        redline = redlines_by_finding[f.finding_id]
        chain = RemediationChain(finding=f, proposal=prop, redline=redline)
        ds = docx_shas.get(prop.target_document, {})
        if ds.get("candidate_sha256"):
            manifest = chain.build_manifest(
                candidate_doc_sha256=ds["candidate_sha256"],
                redline_doc_sha256=ds["redline_sha256"],
                insertion_manifest={"entries": ds["insertion_manifest"]},
                require_docx=True)
        else:
            manifest = chain.build_manifest()   # fallback: cadena de texto (docx no materializable para ese doc)
        change = to_current_pipeline_change(prop)
        row = {
            "finding_id": f.finding_id,
            "directive": {"proposal_id": prop.proposal_id, "target_document": prop.target_document,
                          "change_type": prop.change_type, "mark": prop.mark},
            "candidate_excerpt_hash": redline.candidate_excerpt_hash,
            "redline_diff_hash": _sha256_bytes(redline.diff_unified.encode()),
            "candidate_document_path": ds.get("candidate_path"),
            "candidate_document_format": "docx" if ds.get("candidate_path") else None,
            "redline_document_path": ds.get("redline_path"),
            "redline_document_format": "docx" if ds.get("redline_path") else None,
            "manifest": manifest,
            "current_pipeline_change": change,
            "qa_status": QA_STATUS_DRAFT,
            "mark": MACHINE_GENERATED_MARK,
        }
        remediation.append(row)
        (run_dir / "remediation" / f"{prop.proposal_id}.json").write_text(
            json.dumps(row, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        (run_dir / "remediation" / f"{prop.proposal_id}.manifest.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        (run_dir / "remediation" / f"{prop.proposal_id}.redline.diff").write_text(
            redline.diff_unified, encoding="utf-8")

    # --- final report (report_v2) ---
    rep = report_v2.build_report(all_findings, document_id=project_id, run_id=run_id)
    md = report_v2.render_markdown(rep)
    (run_dir / "informe_hallazgos_v2.md").write_text(md, encoding="utf-8")
    _write_json(run_dir / "compliance_matrices" / "final_report_v2.json", rep)

    # --- audit metadata ---
    finished = datetime.now(timezone.utc).isoformat()
    audit = {
        "run_id": run_id, "project_id": project_id, "engine": "V2",
        "documents": document_ids, "extraction_version": _EXT_VER,
        "started_at": started, "finished_at": finished,
        "llm_calls": 0, "embedding_calls": 0,
        "local_only": egress.local_only, "document_egress_bytes": egress.document_egress_bytes,
        "graph_edges": counts.get("edges_by_rel", counts),
        "n_regulatory": len(reg), "n_functional": len(func), "n_technical": len(tech),
        "n_remediation_drafts": len(remediation),
        "human_gate_intact": all(f.human_state == "UNREVIEWED" for f in all_findings),
        "forbidden_states_present": False,
        "mark": MACHINE_GENERATED_MARK, "qa_status": QA_STATUS_DRAFT,
        "routing_note": ("Regulatory en modo Tier-1 / Palanca C (contingencia determinista). "
                         "NUNCA aprobacion automatica."),
    }
    _write_json(run_dir / "audit_summary" / "audit_metadata.json", audit)

    # --- manifest + SHA256SUMS + package_receipt (convencion gmpai_artifact_service) ---
    files = sorted(p for p in run_dir.rglob("*") if p.is_file())
    sums_lines = []
    for p in files:
        rel = p.relative_to(run_dir).as_posix()
        sums_lines.append(f"{_sha256_bytes(p.read_bytes())}  {rel}")
    manifest = {
        "schema": "v2_analyzer_run",
        "run_id": run_id, "project_id": project_id, "engine": "V2",
        "generated_at": finished, "mark": MACHINE_GENERATED_MARK, "qa_status": QA_STATUS_DRAFT,
        "artifacts": [p.relative_to(run_dir).as_posix() for p in files],
        "counts": {"regulatory": len(reg), "functional": len(func), "technical": len(tech),
                   "remediation_drafts": len(remediation)},
        "gates_ref": "docs_plan/CIERRE_FASE_10_ANALIZADOR_GMP_LOCAL_V2.md",
    }
    mb = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    (run_dir / "manifest.json").write_bytes(mb)
    sums_lines.append(f"{_sha256_bytes(mb)}  manifest.json")
    (run_dir / "SHA256SUMS.txt").write_text("\n".join(sums_lines) + "\n", encoding="utf-8")

    zip_path = run_dir / "paquete_final.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in run_dir.rglob("*"):
            if p.is_file() and p.name != "paquete_final.zip":
                z.write(p, p.relative_to(run_dir).as_posix())
    receipt = {
        "run_id": run_id, "run_dir": str(run_dir),
        "zip_filename": "paquete_final.zip",
        "zip_sha256_final": _sha256_bytes(zip_path.read_bytes()),
        "manifest_sha256": _sha256_bytes(mb),
        "sha256sums_sha256": _sha256_bytes((run_dir / "SHA256SUMS.txt").read_bytes()),
        "engine": "V2", "mark": MACHINE_GENERATED_MARK, "qa_status": QA_STATUS_DRAFT,
        "generated_at": finished,
    }
    (run_dir / "package_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "run_id": run_id, "run_dir": str(run_dir), "report_base": str(base),
        "n_regulatory": len(reg), "n_functional": len(func), "n_technical": len(tech),
        "n_remediation_drafts": len(remediation),
        "local_only": egress.local_only, "document_egress_bytes": egress.document_egress_bytes,
        "llm_calls": 0,
        "human_gate_intact": audit["human_gate_intact"],
        "package_receipt": receipt,
        "informe": str(run_dir / "informe_hallazgos_v2.md"),
    }


def _structure_from_canon(doc_id: str, canon_dir: Path) -> dict:
    """Reconstruye la `structure` que consume candidate_document_generator
    (secciones nivel-1 con `numero/titulo/pagina_inicio/parrafos`) desde el
    canonical_store (B1). Sin re-parsear el PDF."""
    from factory.regulatory.canonical.persistence import CanonicalStore
    with CanonicalStore(doc_id, store_dir=canon_dir) as s:
        secs = sorted((dict(x) for x in s.all("section")),
                      key=lambda x: (x.get("pagina_inicio") or 0))
        claims = list(s.all("claim"))
    if not secs:
        raise ValueError(f"{doc_id}: sin secciones nivel-1 en el canonical_store")
    by_sec: dict[str, list[str]] = {}
    for c in sorted(claims, key=lambda c: (c.get("pagina") or 0)):
        by_sec.setdefault(c.get("section_id"), []).append(c.get("source_text") or "")
    return {
        "texto_previo_a_primera_seccion": [],
        "secciones": [{
            "numero": str(sec.get("numero") or i + 1),
            "titulo": sec.get("titulo") or f"Seccion {i + 1}",
            "pagina_inicio": int(sec.get("pagina_inicio") or 1),
            "parrafos": by_sec.get(sec.get("section_id"), []),
        } for i, sec in enumerate(secs)],
    }


def _current_change(proposal, structure: dict) -> dict:
    """Adapta un RemediationProposal V2 al shape `changes[]` de
    candidate_document_generator de CURRENT. `change_type` -> CONTENT_ADDITION
    (único caso validado del pipeline docx). Marca preservada."""
    first_page = structure["secciones"][0]["pagina_inicio"]
    page_start = max(int(proposal.target_page or first_page), first_page)
    return {
        "change_id": proposal.proposal_id,
        "change_type": "CONTENT_ADDITION",
        "proposed_content": (f"[{MACHINE_GENERATED_MARK}] {proposal.proposed_text}"
                             if MACHINE_GENERATED_MARK not in proposal.proposed_text
                             else proposal.proposed_text),
        "citations": [{"page_start": page_start}],
        "finding_id": proposal.finding_id,
        "mark": MACHINE_GENERATED_MARK,
    }


def _doc_type(did: str, canon_dir: Path) -> str:
    from factory.regulatory.canonical.persistence import CanonicalStore
    try:
        with CanonicalStore(did, store_dir=canon_dir) as s:
            docs = list(s.all("document"))
            return docs[0].get("tipo", "OTHER") if docs else "OTHER"
    except Exception:  # noqa: BLE001
        return "OTHER"


def _assert_no_forbidden(findings) -> None:
    for f in findings:
        if f.human_state in _FORBIDDEN or f.machine_state in _FORBIDDEN:
            raise RuntimeError(f"estado prohibido en {f.finding_id}: {f.human_state}/{f.machine_state}")


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    r = run_v2_pipeline(["RW-0005", "RW-0006", "RW-0011", "RW-0012", "RW-0014"],
                        project_id="RW-V2-E2E")
    print(json.dumps({k: v for k, v in r.items() if k != "package_receipt"}, indent=1, ensure_ascii=False))
