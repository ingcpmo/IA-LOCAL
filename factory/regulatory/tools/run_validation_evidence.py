"""W5 Ciclo 1 (v2), Fase 5.0 (W5.3), control #6 -- runner de evidencia
VERSIONADO (tracked en git), reemplaza la dependencia del único caller real
anterior de generate_controlled()/evaluate_chunked(), que vivía en
factory/workspaces/gmpai_document_validation/run_chunked_pilot.py
(gitignorado -- ver factory/.gitignore 'workspaces/*'). Ese script sigue
existiendo y sigue siendo válido para el motor v1, pero ya NO es el único
punto tracked que ejercita el pipeline v2 con parámetros reales.

Este módulo es deliberadamente genérico (no hardcodea FS_v1.2 ni un run_id
fijo, a diferencia de factory/docs/gmpai_reanalysis/w5v2_evidence/
w5v2_evidence_run.py, que es un REGISTRO HISTÓRICO congelado de una
ejecución puntual, no un runner reutilizable).

run_context SIEMPRE 'validation' -- este runner nunca acepta 'production'
como parámetro (ProductionNotEnabledError lo bloquearía en
generate_controlled() de todas formas, pero aquí se rechaza incluso antes,
a nivel de CLI, para que el error sea legible sin stacktrace)."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.engines.gmpai_integrity import ollama_client
from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks, sanitize_document
from factory.regulatory.absence_consolidator import consolidate
from factory.regulatory.applicability import applicability, pre_inference_filter
from factory.regulatory.evidence_verifier import load_requirement_terms, verify_llm_output
from factory.regulatory.requirement_catalog.citation_locator import sha256_file


@dataclass
class EvidenceRunConfig:
    document_path: Path
    document_type: str
    document_type_source: str
    requirement_ids: list[str]
    max_chunks: int | None = None
    document_type_confidence: float | None = None
    run_by: str = ""
    extractor: "callable" = None  # type: ignore[assignment]


@dataclass
class EvidenceRunResult:
    run_id: str
    records_by_status: dict = field(default_factory=dict)
    per_requirement_conclusions: dict = field(default_factory=dict)
    ollama_calls_avoided: int = 0
    manifest_incomplete_count: int = 0
    records_total: int = 0
    raw: dict = field(default_factory=dict)
    # Fase 5.4 -- mismo contrato de 3 estados que evaluate_chunked() (Fase
    # 5.3): un fallo de persistencia de all_records NUNCA queda oculto
    # como una corrida sin novedad.
    validation_evidence_status: str = "NOT_ATTEMPTED"
    validation_evidence_error: str | None = None
    golden_dataset_eligible: bool = False
    # Fase 5.4.4 -- manifiesto sanitizado versionable (independiente del
    # resultado de la escritura cruda, ver comentario mas abajo).
    manifest_sanitized_status: str = "NOT_ATTEMPTED"
    manifest_sanitized_error: str | None = None


def _default_prompt(requirement_id: str, chunk_text: str) -> str:
    return (
        "Eres un revisor tecnico. Tu UNICA tarea es OBSERVAR si el fragmento "
        "de documento de abajo contiene evidencia relacionada con el "
        "siguiente requisito regulatorio. NO decidas si el sistema CUMPLE o "
        "NO CUMPLE -- eso lo decide un proceso separado. Responde "
        "EXCLUSIVAMENTE en el formato JSON solicitado.\n\n"
        f"requirement_id: {requirement_id}\n\n"
        "chunk_observation: 'observed' (evidencia clara y directa) | "
        "'partially_observed' (evidencia parcial/indirecta) | "
        "'not_observed_in_chunk' (el fragmento no trata el tema -- esto NO "
        "significa incumplimiento, solo que este fragmento no lo menciona).\n"
        "Si observed/partially_observed: evidence_quote debe ser cita "
        "LITERAL del fragmento. Si not_observed_in_chunk: evidence_quote "
        "vacio.\n\n"
        "confidence: numero decimal ENTRE 0.0 y 1.0 (NUNCA una escala de "
        "0 a 100). Ejemplos validos: 0.0, 0.5, 0.85, 1.0. '100' o '85' NO "
        "son valores validos para este campo.\n\n"
        f"[FRAGMENTO]\n{chunk_text}\n[FIN FRAGMENTO]\n"
    )


def run_validation_evidence(config: EvidenceRunConfig) -> EvidenceRunResult:
    """Ejecuta el pipeline v2 completo (filtro de aplicabilidad ->
    generate_controlled -> verify_llm_output -> consolidate) sobre un
    documento real, SIEMPRE run_context='validation'. No escribe evento de
    auditoría por si solo -- el caller decide si y como auditar (ver
    write_audit_event() abajo, opcional)."""
    if config.extractor is None:
        raise ValueError("config.extractor es obligatorio (funcion Path -> list[str] por pagina)")

    document_sha256 = sha256_file(Path(config.document_path))
    per_unit_text = config.extractor(config.document_path)
    all_chunks = build_page_chunks(per_unit_text)
    chunks_used = all_chunks[: config.max_chunks] if config.max_chunks else all_chunks
    for c in chunks_used:
        c["text"] = sanitize_document(c["text"])

    model_digest = ollama_client.show_digest()
    ollama_version_str = ollama_client.ollama_version()

    run_id = f"w5v3-validation-{uuid.uuid4().hex[:12]}"
    result = EvidenceRunResult(run_id=run_id)
    all_records = []

    for req_id in config.requirement_ids:
        terminal = pre_inference_filter(req_id, config.document_type)
        if terminal is not None:
            result.ollama_calls_avoided += len(chunks_used)
            result.per_requirement_conclusions[req_id] = terminal
            continue

        app = applicability(req_id, config.document_type)
        terms = load_requirement_terms(req_id)
        records = []
        for chunk in chunks_used:
            prompt = _default_prompt(req_id, chunk["text"])
            gen = ollama_client.generate_controlled(prompt, chunk, run_context="validation")
            record_id = f"rec-{uuid.uuid4().hex[:12]}"
            if not gen["ok"] or gen["llm_output"] is None:
                record = {
                    "record_id": record_id, "llm_output": None,
                    "execution_manifest": gen["execution_manifest"],
                    "status": "rejected_by_verifier",
                    # Fase 5.4.4: gen["rejection_reason"] ya viene clasificado
                    # (json_parse_failed/schema_validation_failed/
                    # ollama_transport_failed) por generate_controlled() --
                    # el fallback anterior a "schema_validation_failed"
                    # enmascaraba las otras 2 causas cuando ocurrian.
                    "rejection_reason": gen.get("rejection_reason"),
                    "review_flags": [],
                    # Fase 5.4 (fix ETAPA 1): generate_controlled() ya calculaba
                    # raw_response/errors pero se descartaban aqui -- sin esto,
                    # un rechazo por schema queda sin causa reconstruible despues
                    # (incidente detectado al intentar analizar los 21 rechazos
                    # reales de Fase 5.4: el dato crudo nunca se habia persistido).
                    "raw_response": gen.get("raw_response"),
                    "errors": gen.get("errors") or [],
                }
            else:
                verification = verify_llm_output(gen["llm_output"], chunk, set(config.requirement_ids), terms)
                record = {
                    "record_id": record_id, "llm_output": gen["llm_output"],
                    "execution_manifest": gen["execution_manifest"],
                    "status": verification.status,
                    "rejection_reason": verification.rejection_reason,
                    "review_flags": verification.review_flags,
                    "raw_response": gen.get("raw_response"),
                    "errors": gen.get("errors") or [],
                }
            records.append(record)
            all_records.append(record)
            if gen["execution_manifest"].get("manifest_incomplete"):
                result.manifest_incomplete_count += 1

        conclusion = consolidate(req_id, config.document_type, app["value"], records)
        result.per_requirement_conclusions[req_id] = {
            "conclusion": conclusion.conclusion,
            "chunks_evaluated": conclusion.chunks_evaluated,
            "chunks_observed": conclusion.chunks_observed,
            "review_flags": conclusion.review_flags,
        }

    status_counts: dict[str, int] = {}
    for r in all_records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    result.records_by_status = status_counts
    result.records_total = len(all_records)
    result.raw = {
        "run_id": run_id,
        "run_context": "validation",
        "run_by": config.run_by,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "document": str(config.document_path),
        "document_sha256": document_sha256,
        "document_type": config.document_type,
        "document_type_source": config.document_type_source,
        "total_chunks_real": len(all_chunks),
        "chunks_used": len(chunks_used),
        "coverage": "partial" if config.max_chunks and config.max_chunks < len(all_chunks) else "full",
        "model": ollama_client.OLLAMA_MODEL,
        "model_digest": model_digest,
        "ollama_version": ollama_version_str,
        "records_by_status": status_counts,
        "per_requirement_conclusions": result.per_requirement_conclusions,
    }

    # Fase 5.4, Bloque 5.4.1 -- persistir all_records COMPLETOS (llm_output,
    # execution_manifest, verification), no solo los agregados de arriba.
    # Mismo contrato de 3 estados que evaluate_chunked() (Fase 5.3): un
    # fallo de escritura nunca tumba la corrida ni queda oculto.
    try:
        from factory.regulatory.validation_evidence_writer import write_validation_evidence
        write_validation_evidence(
            run_id=run_id,
            document_sha256=document_sha256,
            run_context="validation",
            content={
                "all_records": all_records,
                "per_requirement_conclusions": result.per_requirement_conclusions,
            },
        )
        result.validation_evidence_status = "VALIDATION_EVIDENCE_COMPLETE"
        result.golden_dataset_eligible = True
    except Exception as e:
        result.validation_evidence_status = "VALIDATION_EVIDENCE_INCOMPLETE"
        result.validation_evidence_error = f"{type(e).__name__}: {e}"
        result.golden_dataset_eligible = False

    result.raw["validation_evidence_status"] = result.validation_evidence_status
    result.raw["golden_dataset_eligible"] = result.golden_dataset_eligible

    # Fase 5.4.4 (gobernanza): manifiesto sanitizado versionable, generado
    # SIEMPRE que haya habido intento de persistencia (aunque haya
    # fallado -- el manifiesto en si no contiene texto del documento, asi
    # que un fallo de la escritura cruda no impide dejar constancia
    # sanitizada de que la corrida ocurrio).
    try:
        from factory.regulatory.validation_evidence_manifest import write_sanitized_manifest
        write_sanitized_manifest(run_id=run_id, raw=result.raw, all_records=all_records)
        result.manifest_sanitized_status = "MANIFEST_WRITTEN"
    except Exception as e:
        result.manifest_sanitized_status = "MANIFEST_WRITE_FAILED"
        result.manifest_sanitized_error = f"{type(e).__name__}: {e}"

    result.raw["manifest_sanitized_status"] = result.manifest_sanitized_status
    return result


def requirement_ids_from_catalog() -> list[str]:
    """Fase 5.3, Bloque 5.3.3: deriva la lista de requirement_id desde el
    catalogo real de Fase 5.2 (requirement_catalog_loader.load_requirements())
    en vez de listarlos a mano en cada invocacion -- una sola fuente de
    verdad. Usa validate_all() primero (fail-closed: si el catalogo no
    valida, esto lanza CatalogValidationError antes de intentar nada)."""
    from factory.regulatory.requirement_catalog.requirement_catalog_loader import (
        load_requirements, validate_all,
    )
    validate_all()  # fail-closed: aborta si el catalogo es invalido
    return list(load_requirements()["requirements"].keys())


def _cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--document-type", required=True)
    parser.add_argument("--document-type-source", required=True,
                         choices=["human_assigned", "inferred"])
    parser.add_argument("--requirement-id", action="append", dest="requirement_ids",
                         help="Repetible. Si se omite, usa TODOS los requirement_id del catalogo (--all-catalog-requirements).")
    parser.add_argument("--all-catalog-requirements", action="store_true",
                         help="Usa requirement_ids_from_catalog() -- fuente unica de verdad (Fase 5.2), en vez de listarlos a mano.")
    parser.add_argument("--max-chunks", type=int, default=None)
    parser.add_argument("--run-by", required=True,
                         help="Identidad real de quien autoriza esta ejecucion (obligatorio, sin default)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.all_catalog_requirements:
        requirement_ids = requirement_ids_from_catalog()
    elif args.requirement_ids:
        requirement_ids = args.requirement_ids
    else:
        parser.error("especificar --requirement-id (uno o mas) o --all-catalog-requirements")

    import pypdf

    def _pdf_extractor(path: Path) -> list[str]:
        reader = pypdf.PdfReader(str(path))
        return [(p.extract_text() or "") for p in reader.pages]

    config = EvidenceRunConfig(
        document_path=args.document,
        document_type=args.document_type,
        document_type_source=args.document_type_source,
        requirement_ids=requirement_ids,
        max_chunks=args.max_chunks,
        run_by=args.run_by,
        extractor=_pdf_extractor,
    )
    result = run_validation_evidence(config)
    output = json.dumps(result.raw, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    _cli()
