"""W5.6 (ETAPA 4) -- reprocesamiento OFFLINE de un run de validation_evidence
ya persistido, aplicando una version corregida de evidence_verifier.py /
absence_consolidator.py (fix del hallazgo real: cita literal del chunk 20
de "215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf" rechazada por
citation_not_found debido a membrete de pagina + kerning del PDF -- ver
docstrings de evidence_verifier.py y absence_consolidator.py).

Contrato estricto:
  - NUNCA llama a Ollama (no importa ollama_client, no hay generate_fn).
  - NUNCA modifica el JSON historico de origen (solo lectura).
  - El chunk_text se RECONSTRUYE deterministicamente desde el documento
    fuente (mismo build_page_chunks/sanitize_document que la corrida
    original) y se ancla por chunk_sha256 -- si algun chunk_sha256 del run
    historico no aparece en la reconstruccion, ese registro se preserva TAL
    CUAL (status original) y se marca RECONSTRUCTION_MISMATCH, nunca se
    inventa o se fuerza una verificacion sin poder reproducir el chunk.
  - El resultado es un run DERIVADO nuevo (run_id propio,
    derived_from_run_id apuntando al run historico), escrito con el mismo
    escritor gobernado (write_validation_evidence + write_sanitized_manifest)
    que un run real -- mismas garantias de atomicidad/permisos/alcance de
    Git, distinto solo en que run_context sigue siendo 'validation' y
    ollama_called=False."""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks, sanitize_document
from factory.regulatory.absence_consolidator import consolidate
from factory.regulatory.applicability import applicability
from factory.regulatory.evidence_verifier import load_requirement_terms, verify_llm_output
from factory.regulatory.requirement_catalog.citation_locator import sha256_file


def _module_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rebuild_chunks_by_sha256(document_path: Path, extractor) -> dict:
    per_unit_text = extractor(document_path)
    all_chunks = build_page_chunks(per_unit_text)
    by_sha = {}
    for c in all_chunks:
        c["text"] = sanitize_document(c["text"])
        by_sha[hashlib.sha256(c["text"].encode()).hexdigest()] = c
    return by_sha


@dataclass
class ReverificationResult:
    run_id: str
    derived_from_run_id: str
    raw: dict


def reverify_run(
    source_run: dict,
    source_manifest: dict,
    document_path: Path,
    extractor,
    *,
    run_by: str,
) -> ReverificationResult:
    """source_run: dict completo tal como quedo persistido por
    write_validation_evidence() para el run historico (con 'run_id',
    'document_sha256', 'content': {'all_records', 'per_requirement_
    conclusions'}) -- NO trae document_type/chunks_used (esos campos solo
    viven en el manifiesto sanitizado, ver validation_evidence_manifest.py).
    source_manifest: el .manifest.json correspondiente (versionable, sin
    texto de documento), fuente de esa metadata. Ninguno de los dos se
    muta -- se leen y se construye un resultado nuevo."""
    source_run = {**source_run, **{
        k: v for k, v in source_manifest.items()
        if k not in ("content", "records", "manifest_sha256")
    }}
    document_sha256 = sha256_file(document_path)
    if document_sha256 != source_run["document_sha256"]:
        raise ValueError(
            f"document_sha256 no coincide: run historico esperaba "
            f"{source_run['document_sha256']}, el documento en {document_path} "
            f"tiene {document_sha256} -- no se puede reverificar de forma "
            f"trazable contra un documento distinto."
        )

    chunks_by_sha = _rebuild_chunks_by_sha256(document_path, extractor)
    source_records = source_run["content"]["all_records"]

    known_req_ids = _known_req_ids(source_records)
    records_by_req: dict[str, list[dict]] = {}
    all_records_out = []
    reconstruction_mismatches = 0

    for rec in source_records:
        req_id = (rec.get("llm_output") or {}).get("requirement_id")
        if req_id is None:
            # rechazado antes del verificador (schema/json/transport) -- el
            # requirement_id vive solo en el prompt, no en el registro; se
            # preserva tal cual, no aporta re-verificacion posible.
            all_records_out.append(dict(rec, reverification="NOT_APPLICABLE_NO_LLM_OUTPUT"))
            continue

        chunk_sha = rec["execution_manifest"]["chunk_sha256"]
        chunk = chunks_by_sha.get(chunk_sha)
        new_rec = dict(rec)
        if chunk is None:
            new_rec["reverification"] = "RECONSTRUCTION_MISMATCH"
            reconstruction_mismatches += 1
        else:
            terms = load_requirement_terms(req_id)
            verification = verify_llm_output(rec["llm_output"], chunk, known_req_ids, terms)
            new_rec["status"] = verification.status
            new_rec["rejection_reason"] = verification.rejection_reason
            new_rec["review_flags"] = verification.review_flags
            new_rec["reverification"] = "REVERIFIED_W56"
            new_rec["reverification_checks"] = verification.checks
            new_rec["status_before_reverification"] = rec["status"]

        all_records_out.append(new_rec)
        records_by_req.setdefault(req_id, []).append(new_rec)

    coverage_complete = source_run["chunks_used"] >= source_run["total_chunks_real"]
    per_requirement_conclusions = {}
    for req_id, recs in records_by_req.items():
        app = applicability(req_id, source_run["document_type"])
        conclusion = consolidate(req_id, source_run["document_type"], app["value"], recs,
                                  coverage_complete=coverage_complete)
        per_requirement_conclusions[req_id] = {
            "conclusion": conclusion.conclusion,
            "chunks_evaluated": conclusion.chunks_evaluated,
            "chunks_observed": conclusion.chunks_observed,
            "review_flags": conclusion.review_flags,
        }

    status_counts: dict[str, int] = {}
    for r in all_records_out:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    run_id = f"w5v3-validation-{uuid.uuid4().hex[:12]}"
    verifier_path = Path(__file__).resolve().parents[1] / "evidence_verifier.py"
    consolidator_path = Path(__file__).resolve().parents[1] / "absence_consolidator.py"

    raw = {
        "run_id": run_id,
        "run_context": "validation",
        "run_by": run_by,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "document": str(document_path),
        "document_sha256": document_sha256,
        "document_type": source_run["document_type"],
        "document_type_source": source_run["document_type_source"],
        "total_chunks_real": source_run["total_chunks_real"],
        "chunks_used": source_run["chunks_used"],
        "coverage": source_run["coverage"],
        "model": source_run["model"],
        "model_digest": source_run["model_digest"],
        "ollama_version": source_run["ollama_version"],
        "records_by_status": status_counts,
        "per_requirement_conclusions": per_requirement_conclusions,
        # -- trazabilidad del reproceso (W5.6, ETAPA 4) --
        "derived_from_run_id": source_run["run_id"],
        "reprocessing_reason": (
            "W5.6: evidence_verifier.py (tier 'despaced' + "
            "_strip_page_furniture) y absence_consolidator.py "
            "(DOCUMENTED_AND_SUPPORTED exige >=1 observed verified) "
            "corregidos tras hallazgo real en chunk 20 (citation_not_found "
            "indebido)."
        ),
        "ollama_called": False,
        "reconstruction_mismatches": reconstruction_mismatches,
        "verifier_module_sha256": _module_sha256(verifier_path),
        "consolidator_module_sha256": _module_sha256(consolidator_path),
        "PRODUCTION_ENABLEMENT": "BLOCKED",
    }

    return ReverificationResult(
        run_id=run_id,
        derived_from_run_id=source_run["run_id"],
        raw={**raw, "all_records": all_records_out},
    )


def _known_req_ids(records: list[dict]) -> set:
    return {
        (r.get("llm_output") or {}).get("requirement_id")
        for r in records
        if (r.get("llm_output") or {}).get("requirement_id")
    }


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True, type=Path,
                         help="Ruta al JSON de validation_evidence historico (solo lectura).")
    parser.add_argument("--source-manifest", required=True, type=Path,
                         help="Ruta al .manifest.json correspondiente (metadata: document_type, chunks_used, etc).")
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--run-by", required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    import pypdf

    def _pdf_extractor(path: Path) -> list[str]:
        reader = pypdf.PdfReader(str(path))
        return [(p.extract_text() or "") for p in reader.pages]

    source_run = json.loads(args.source_run.read_text(encoding="utf-8"))
    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    result = reverify_run(source_run, source_manifest, args.document, _pdf_extractor, run_by=args.run_by)

    from factory.regulatory.validation_evidence_manifest import write_sanitized_manifest
    from factory.regulatory.validation_evidence_writer import write_validation_evidence

    write_validation_evidence(
        run_id=result.run_id,
        document_sha256=result.raw["document_sha256"],
        run_context="validation",
        content={
            "all_records": result.raw.pop("all_records"),
            "per_requirement_conclusions": result.raw["per_requirement_conclusions"],
        },
    )
    write_sanitized_manifest(run_id=result.run_id, raw=result.raw)

    output = json.dumps(result.raw, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    _cli()
