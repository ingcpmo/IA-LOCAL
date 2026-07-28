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

from factory.engines.gmpai_integrity.model_provider import (
    DEFAULT_PROVIDER,
    ControlledGenerationNotSupportedError,
    ModelProvider,
    supports_controlled_generation,
)
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
    # Checkpoint/resume (Fase 3, gate real 551-llamadas): si se provee,
    # cada llamada real a Ollama se persiste ahi de inmediato (append-only,
    # JSONL) y se reusa en invocaciones futuras -- nunca se repite una
    # llamada ya completada para el mismo document_sha256. Sin esto, el
    # comportamiento es identico al de siempre (todo en memoria, un solo
    # proceso, sin reanudacion).
    checkpoint_path: Path | None = None
    # max_calls acota cuantas llamadas NUEVAS a Ollama hace esta invocacion
    # (no cuenta las reusadas del checkpoint) -- permite correr "por
    # lotes" un universo grande (19 requisitos x N chunks) sin mantener un
    # solo proceso corriendo horas: cada lote hace como mucho max_calls
    # llamadas nuevas y termina limpio, dejando el resto para la proxima
    # invocacion (mismo checkpoint_path).
    max_calls: int | None = None
    progress_callback: "callable | None" = None  # type: ignore[assignment]


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
    # Checkpoint/resume: cuantas llamadas NUEVAS hizo esta invocacion
    # (distinto de records_total, que incluye las reusadas del checkpoint);
    # batch_complete=False significa que quedaron requisitos sin resolver
    # por agotar max_calls -- en ese caso NUNCA se llama a consolidate()
    # para esos requisitos (evitaria un DOCUMENTATION_GAP/FULL_COVERAGE
    # ficticio con cobertura parcial, mismo principio que coverage_complete
    # en absence_consolidator) ni se persiste validation_evidence (Fase
    # 5.4) -- eso solo ocurre en la invocacion que de verdad completa todo.
    calls_made_this_invocation: int = 0
    batch_complete: bool = True
    pending_requirement_ids: list = field(default_factory=list)


def _checkpoint_key(document_sha256: str, requirement_id: str, chunk_index: int) -> str:
    return f"{document_sha256}::{requirement_id}::{chunk_index}"


def _load_checkpoint(checkpoint_path: Path, document_sha256: str) -> dict[str, dict]:
    """Solo reusa entradas del MISMO document_sha256 -- un checkpoint de un
    documento distinto (o una version distinta del mismo archivo) nunca se
    confunde con evidencia real de este run."""
    entries: dict[str, dict] = {}
    if not checkpoint_path.exists():
        return entries
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("document_sha256") != document_sha256:
            continue
        key = _checkpoint_key(document_sha256, entry["requirement_id"], entry["chunk_index"])
        entries[key] = entry
    return entries


def _append_checkpoint(checkpoint_path: Path, entry: dict) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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


def run_validation_evidence(config: EvidenceRunConfig,
                            provider: ModelProvider | None = None) -> EvidenceRunResult:
    """Ejecuta el pipeline v2 completo (filtro de aplicabilidad ->
    generate_controlled -> verify_llm_output -> consolidate) sobre un
    documento real, SIEMPRE run_context='validation'. No escribe evento de
    auditoría por si solo -- el caller decide si y como auditar (ver
    write_audit_event() abajo, opcional).

    provider (2026-07-28, default None -- cero cambio de comportamiento para
    todo llamador existente): implementación de ModelProvider a usar; None
    usa DEFAULT_PROVIDER (OllamaProvider, el mismo cliente de siempre).

    Por qué se añade: hasta hoy este runner llamaba a
    `ollama_client.generate_controlled()`, `show_digest()`, `ollama_version()`
    y `OLLAMA_MODEL` DIRECTAMENTE, saltándose la abstracción de Fase D. Era
    el único incumplimiento real del gate 14 de la sección 22 del plan
    ("100% de agentes híbridos con ModelProvider") en código git-trackeado, y
    hacía imposible ejecutar la evidencia regulatoria contra otro modelo sin
    tocar el módulo. Toda la metadata del manifiesto (`model`,
    `model_digest`, `ollama_version`) pasa a leerse del provider: si no, el
    artefacto mentiría al inyectar uno distinto."""
    if config.extractor is None:
        raise ValueError("config.extractor es obligatorio (funcion Path -> list[str] por pagina)")

    document_sha256 = sha256_file(Path(config.document_path))
    per_unit_text = config.extractor(config.document_path)
    all_chunks = build_page_chunks(per_unit_text)
    chunks_used = all_chunks[: config.max_chunks] if config.max_chunks else all_chunks
    for c in chunks_used:
        c["text"] = sanitize_document(c["text"])
    # W5.5: misma condicion que "coverage" mas abajo -- coverage_complete se
    # pasa a consolidate() para que DOCUMENTATION_GAP nunca se declare con
    # cobertura parcial (P3 reforzado, absence_consolidator.py).
    coverage_complete = not config.max_chunks or config.max_chunks >= len(all_chunks)

    provider = provider if provider is not None else DEFAULT_PROVIDER
    # Fail-closed antes de gastar una sola llamada: si el provider inyectado
    # no ofrece la ruta controlada, se aborta. NUNCA se cae de vuelta a
    # ollama_client -- eso produciria evidencia regulatoria atribuida a un
    # modelo que no es el inyectado.
    if not supports_controlled_generation(provider):
        raise ControlledGenerationNotSupportedError(
            f"{type(provider).__name__} no ofrece generate_controlled(); la evidencia "
            f"regulatoria exige la ruta con schema forzado finding_llm_v1."
        )
    model_digest = provider.show_digest()
    ollama_version_str = provider.runtime_version()

    run_id = f"w5v3-validation-{uuid.uuid4().hex[:12]}"
    result = EvidenceRunResult(run_id=run_id)
    all_records = []

    checkpoint_entries: dict[str, dict] = {}
    if config.checkpoint_path is not None:
        checkpoint_entries = _load_checkpoint(config.checkpoint_path, document_sha256)

    total_calls_possible = len(config.requirement_ids) * len(chunks_used)
    calls_made = 0
    budget_exhausted = False

    for req_id in config.requirement_ids:
        terminal = pre_inference_filter(req_id, config.document_type)
        if terminal is not None:
            result.ollama_calls_avoided += len(chunks_used)
            result.per_requirement_conclusions[req_id] = terminal
            continue

        app = applicability(req_id, config.document_type)
        terms = load_requirement_terms(req_id)
        records = []
        requirement_incomplete = False

        for chunk in chunks_used:
            ckpt_key = (
                _checkpoint_key(document_sha256, req_id, chunk["chunk_index"])
                if config.checkpoint_path is not None else None
            )
            cached = checkpoint_entries.get(ckpt_key) if ckpt_key else None

            if cached is not None:
                record = cached["record"]
            elif budget_exhausted or (config.max_calls is not None and calls_made >= config.max_calls):
                # Presupuesto de este lote agotado -- este requisito (y
                # cualquier otro que quede) NO se consolida en esta
                # invocacion, para no fingir cobertura completa.
                requirement_incomplete = True
                budget_exhausted = True
                continue
            else:
                prompt = _default_prompt(req_id, chunk["text"])
                gen = provider.generate_controlled(prompt, chunk, run_context="validation")
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
                if gen["execution_manifest"].get("manifest_incomplete"):
                    result.manifest_incomplete_count += 1
                calls_made += 1

                if config.checkpoint_path is not None:
                    entry = {
                        "document_sha256": document_sha256, "requirement_id": req_id,
                        "chunk_index": chunk["chunk_index"], "record": record,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    }
                    _append_checkpoint(config.checkpoint_path, entry)

                if config.progress_callback is not None:
                    config.progress_callback({
                        "requirement_id": req_id, "chunk_index": chunk["chunk_index"],
                        "calls_made_this_invocation": calls_made,
                        "total_calls_possible": total_calls_possible,
                        "status": record["status"],
                    })

            records.append(record)
            all_records.append(record)

        if requirement_incomplete:
            result.pending_requirement_ids.append(req_id)
            result.per_requirement_conclusions[req_id] = {"status": "PENDING_BATCH_INCOMPLETE"}
            continue

        conclusion = consolidate(req_id, config.document_type, app["value"], records,
                                  coverage_complete=coverage_complete)
        result.per_requirement_conclusions[req_id] = {
            "conclusion": conclusion.conclusion,
            "chunks_evaluated": conclusion.chunks_evaluated,
            "chunks_observed": conclusion.chunks_observed,
            "review_flags": conclusion.review_flags,
        }

    result.calls_made_this_invocation = calls_made
    result.batch_complete = not result.pending_requirement_ids

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
        "model": provider.model_name,
        "model_digest": model_digest,
        "ollama_version": ollama_version_str,
        "records_by_status": status_counts,
        "per_requirement_conclusions": result.per_requirement_conclusions,
    }

    if not result.batch_complete:
        # Fase 3 (551-llamadas por lotes): este lote agoto max_calls antes
        # de resolver todos los requisitos -- NUNCA se persiste
        # validation_evidence/manifiesto de un universo incompleto (se
        # confundiria con un run real terminado). El checkpoint en disco
        # ya tiene cada llamada real hecha hasta ahora; la proxima
        # invocacion con el mismo checkpoint_path continua desde ahi.
        result.validation_evidence_status = "BATCH_INCOMPLETE_NOT_PERSISTED"
        result.golden_dataset_eligible = False
        result.raw["validation_evidence_status"] = result.validation_evidence_status
        result.raw["golden_dataset_eligible"] = result.golden_dataset_eligible
        result.raw["pending_requirement_ids"] = result.pending_requirement_ids
        result.raw["calls_made_this_invocation"] = result.calls_made_this_invocation
        return result

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
    result.raw["calls_made_this_invocation"] = result.calls_made_this_invocation

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
    parser.add_argument("--checkpoint", type=Path, default=None,
                         help="Ruta JSONL append-only. Si se provee, las llamadas ya hechas para el "
                              "mismo document_sha256 se reusan (resume) y las nuevas se persisten de "
                              "inmediato, una por una -- nunca se pierde progreso si el proceso muere.")
    parser.add_argument("--max-calls", type=int, default=None,
                         help="Tope de llamadas NUEVAS a Ollama en esta invocacion (no cuenta las "
                              "reusadas del checkpoint). Permite correr un universo grande 'por lotes': "
                              "cada invocacion hace como mucho --max-calls llamadas y termina limpio; "
                              "volver a invocar con el mismo --checkpoint continua donde quedo.")
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

    def _progress(event: dict) -> None:
        print(
            f"[{event['calls_made_this_invocation']}] req={event['requirement_id']} "
            f"chunk={event['chunk_index']} status={event['status']} "
            f"({datetime.now(timezone.utc).isoformat()})",
            file=sys.stderr, flush=True,
        )

    config = EvidenceRunConfig(
        document_path=args.document,
        document_type=args.document_type,
        document_type_source=args.document_type_source,
        requirement_ids=requirement_ids,
        max_chunks=args.max_chunks,
        run_by=args.run_by,
        extractor=_pdf_extractor,
        checkpoint_path=args.checkpoint,
        max_calls=args.max_calls,
        progress_callback=_progress,
    )
    result = run_validation_evidence(config)
    output = json.dumps(result.raw, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    print(output)
    print(
        f"batch_complete={result.batch_complete} "
        f"calls_made_this_invocation={result.calls_made_this_invocation} "
        f"pending_requirement_ids={result.pending_requirement_ids}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    _cli()
