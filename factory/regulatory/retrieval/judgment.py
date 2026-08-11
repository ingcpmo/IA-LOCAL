"""R2 — fase de JUICIO (docs_plan/R2_DESIGN_DETALLADO.md, `.claude/plans/
sharded-riding-turing.md`, 2026-08-09): mide si el juicio LLM sobre un
candidate pool curado por BM25 (`retriever.retrieve_top_k`) encuentra
evidencia genuina mejor que el baseline (documento completo, chunk por
chunk, 2/7 medido en H1-H4).

Medición DIAGNÓSTICA, no todavía una etapa productizada del pipeline
estándar -- si confirma que vale la pena, productizarla dentro de
`corpus_runner.py` (con sus propios tests/gates) es una decisión
SEPARADA y posterior, no implícita en esta corrida.

Reutiliza, nunca duplica, la gobernanza real ya probada de
`corpus_runner.run_pilot_sample_batch`:
  - `_select_pilot_execution_instance` (PILOT_EXECUTION vigente + budget)
  - `model_qualification_gate` (calificación del modelo)
  - `chunked_engine.CheckpointStore` + `evaluate_chunked(run_context='pilot')`
  - `factory.core.audit_writer.write_event` (mismo patrón de evento)

Diferencia de diseño frente a `PilotSampleUnit` (deliberada, ver el plan):
`PilotSampleUnit.page_indices` re-extrae páginas COMPLETAS del PDF --
adecuado para extractos cortos elegidos a mano, pero infla el candidate
pool de R2 a rangos de página enteros (medido: hasta el documento
COMPLETO en documentos cortos). `JudgmentUnit` alimenta directamente el
TEXTO de los chunks ya recuperados por BM25 como `per_unit_text` --
exactamente lo que el retriever seleccionó, ni más ni menos."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from factory.engines.gmpai_integrity import chunked_engine as ce
from factory.engines.gmpai_integrity.chunked_engine import build_page_chunks
from factory.engines.gmpai_integrity.model_provider import DEFAULT_PROVIDER, ModelProvider
from factory.regulatory import model_qualification_gate as mqg
from factory.regulatory.corpus_runner import (
    CorpusRunNotAuthorizedError,
    PILOT_CHECKPOINT_DIR,
    PILOT_RUN_AGENT_VERSION,
    _PROMPT_PATH_BY_AGENT,
    _resolve_document_path,
    _select_pilot_execution_instance,
)
from factory.core.audit_writer import write_event


@dataclass
class JudgmentUnit:
    """Una llamada real de la fase de juicio de R2: el candidate pool que
    `retriever.retrieve_top_k(document_sha256, requirement_id, k)` ya
    devolvió para un (documento, requisito) -- nunca páginas re-extraídas
    del PDF, nunca el documento completo."""
    document_id: str
    document_type: str
    agent_id: str
    requirement_id: str
    candidate_chunks: list[dict]  # tal cual los devuelve retrieve_top_k
    selection_reason: str = ""


@dataclass
class JudgmentUnitOutcome:
    document_id: str
    requirement_id: str
    status: str  # COMPLETED | NOT_STARTED_HARD_STOP | FAILED
    run_id: str | None = None
    calls_made_this_invocation: int = 0
    wall_seconds: float = 0.0
    chunk_observation: str | None = None  # 'observed' | 'not_observed_in_chunk' | None (sin verified_conclusions)
    conclusion: str | None = None
    error: str | None = None


@dataclass
class JudgmentBatchSummary:
    units: list[JudgmentUnitOutcome] = field(default_factory=list)
    stop_reason: str = "BATCH_COMPLETE"
    total_calls_made: int = 0
    total_wall_seconds: float = 0.0
    selected_pilot_instance_id: str | None = None


def expected_calls_for_unit(unit: JudgmentUnit) -> int:
    """Cuántas llamadas reales va a hacer esta unidad -- calculado ANTES
    de gastar presupuesto, con `build_page_chunks` (determinista, sin
    LLM, gratis): la re-chunking del texto YA recuperado no siempre
    consolida (los chunks recuperados ya rondan `CHUNK_MAX_CHARS`), así
    que el costo real puede ser mayor a 1 por unidad."""
    texts = [c["text"] for c in unit.candidate_chunks]
    if not texts:
        return 0
    return len(build_page_chunks(texts))


def run_judgment_batch(units: list[JudgmentUnit], *,
                        provider: ModelProvider | None = None,
                        checkpoint_dir: Path = PILOT_CHECKPOINT_DIR,
                        decision_store_file: Path | None = None,
                        progress_file: Path | None = None) -> JudgmentBatchSummary:
    """Mismas guardias que `run_pilot_sample_batch`, en el mismo orden:
    PILOT_EXECUTION vigente con budget real -> calificación del modelo ->
    checkpoint store compartido -> hard-stop ANTES de gastar una llamada
    que excedería el presupuesto (nunca arranca una unidad a medias).

    progress_file (opcional): si se provee, se le agrega (append, JSONL)
    el resultado de CADA unidad apenas termina -- no hay que esperar a
    que el batch entero termine para ver progreso real. El progreso POR
    LLAMADA individual (dentro de una unidad con expected_calls>1) ya es
    observable vía los checkpoints de `evaluate_chunked` en
    `checkpoint_dir`, que se guardan después de cada chunk -- esto no lo
    duplica, solo agrega la vista de nivel-unidad."""
    provider = provider or DEFAULT_PROVIDER
    if not units:
        return JudgmentBatchSummary(stop_reason="NO_UNITS")

    document_ids = sorted({u.document_id for u in units})
    selection = _select_pilot_execution_instance(document_ids, decision_store_file=decision_store_file)
    max_calls = selection["payload"].get("max_calls")
    if not isinstance(max_calls, int) or max_calls <= 0:
        raise CorpusRunNotAuthorizedError(
            f"PILOT_EXECUTION vigente sin max_calls válido: {max_calls!r}")

    status = mqg.evaluate_model_qualification(provider).status
    mqg.require_inference_authorized(status, call_type=mqg.CALL_TYPE_INFERENCE, run_context="pilot")

    checkpoint_store = ce.CheckpointStore(checkpoint_dir)
    summary = JudgmentBatchSummary(selected_pilot_instance_id=selection["selected_instance_id"])

    for unit in units:
        expected = expected_calls_for_unit(unit)
        if expected == 0:
            outcome = JudgmentUnitOutcome(
                document_id=unit.document_id, requirement_id=unit.requirement_id,
                status="FAILED", error="candidate_chunks vacío -- nada que juzgar")
            summary.units.append(outcome)
            _append_progress(progress_file, outcome)
            continue
        if summary.total_calls_made + expected > max_calls:
            outcome = JudgmentUnitOutcome(
                document_id=unit.document_id, requirement_id=unit.requirement_id,
                status="NOT_STARTED_HARD_STOP")
            summary.units.append(outcome)
            _append_progress(progress_file, outcome)
            summary.stop_reason = "HARD_STOP_CALLS"
            break

        path, doc_sha256 = _resolve_document_path(unit.document_id)
        per_unit_text = [c["text"] for c in unit.candidate_chunks]

        t0 = time.monotonic()
        try:
            result = ce.evaluate_chunked(
                _PROMPT_PATH_BY_AGENT[unit.agent_id], agent_id=unit.agent_id,
                agent_version=PILOT_RUN_AGENT_VERSION,
                per_unit_text=per_unit_text,
                sistema="r2_judgment_phase", documento=unit.document_id,
                version="v1", archivo=str(path), document_sha256=doc_sha256,
                run_context="pilot", checkpoint_store=checkpoint_store,
                use_verified_pipeline=True, document_type=unit.document_type,
                retry_technical_failures=True, provider=provider,
                evaluation_profile="H2H4", target_requirement_ids=[unit.requirement_id],
                # R2.2 §2 (2026-08-10, docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md):
                # per_unit_text aqui es SIEMPRE un candidate pool top-k de
                # BM25 (unit.candidate_chunks), nunca el documento completo
                # -- cobertura parcial por diseno. Sin esto, un negativo
                # real (nada observado en los chunks vistos) podia cerrar
                # PROVISIONAL_GAP como si fuera ausencia confirmada del
                # documento entero (hallazgo real: P2/P5 en la re-medicion
                # de Opcion A).
                full_document_coverage=False,
            )
        except Exception as e:  # noqa: BLE001 -- nunca se traga: se registra y se relanza
            wall = time.monotonic() - t0
            outcome = JudgmentUnitOutcome(
                document_id=unit.document_id, requirement_id=unit.requirement_id,
                status="FAILED", wall_seconds=wall, error=f"{type(e).__name__}: {e}")
            summary.units.append(outcome)
            _append_progress(progress_file, outcome)
            summary.total_wall_seconds += wall
            summary.stop_reason = "TECHNICAL_FAILURE"
            _write_judgment_batch_event(summary, document_ids)
            raise

        wall = time.monotonic() - t0
        new_calls = len(result["chunk_executions"])
        conclusion = (result.get("verified_conclusions") or {}).get(unit.requirement_id) or {}
        outcome = JudgmentUnitOutcome(
            document_id=unit.document_id, requirement_id=unit.requirement_id,
            status="COMPLETED", run_id=result["run_id"], calls_made_this_invocation=new_calls,
            wall_seconds=wall,
            chunk_observation="observed" if conclusion.get("chunks_observed", 0) > 0 else "not_observed_in_chunk",
            conclusion=conclusion.get("conclusion"),
        )
        summary.units.append(outcome)
        _append_progress(progress_file, outcome)
        summary.total_calls_made += new_calls
        summary.total_wall_seconds += wall

    _write_judgment_batch_event(summary, document_ids)
    return summary


def _append_progress(progress_file: Path | None, outcome: JudgmentUnitOutcome) -> None:
    if progress_file is None:
        return
    import json
    from dataclasses import asdict

    progress_file.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(outcome), ensure_ascii=False) + "\n")


def _write_judgment_batch_event(summary: JudgmentBatchSummary, document_ids: list[str]) -> None:
    write_event("r2_judgment_batch_completed", "regulatory_intel", {
        "document_ids": document_ids,
        "stop_reason": summary.stop_reason,
        "total_calls_made": summary.total_calls_made,
        "total_wall_seconds": round(summary.total_wall_seconds, 1),
        "units_completed": sum(1 for u in summary.units if u.status == "COMPLETED"),
        "units_failed": sum(1 for u in summary.units if u.status == "FAILED"),
        "selected_pilot_instance_id": summary.selected_pilot_instance_id,
    })
