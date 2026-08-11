"""
Capa 9 — Human Review Queue.

Cola de RCs pendientes de revisión humana.
Persiste en factory/layer9/review_queue.jsonl (append-only).
"""

from __future__ import annotations

import fcntl
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from factory.core.audit_writer import write_event

REVIEW_QUEUE_FILE = Path(__file__).parent / "review_queue.jsonl"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_all() -> list[dict]:
    if not REVIEW_QUEUE_FILE.exists():
        return []
    entries = []
    for line in REVIEW_QUEUE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _rewrite(entries: list[dict]) -> None:
    REVIEW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_FILE.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


def enqueue(rc_id: str, project_id: str, summary: dict) -> dict:
    """Añade un RC a la cola de revisión humana."""
    entry = {
        "rc_id": rc_id,
        "project_id": project_id,
        "enqueued_at": _ts(),
        "status": "pending",
        "summary": summary,
    }
    REVIEW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = REVIEW_QUEUE_FILE.with_suffix(".lock")
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(REVIEW_QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    write_event("rc_enqueued", project_id, {
        "rc_id": rc_id,
        "summary": summary,
    })
    return entry


_CANDIDATES_HONESTY_NOTE = (
    "Estos candidatos son RECUPERACION (BM25 + embeddings semanticos, "
    "fusionados por RRF), NO evidencia validada -- ningun candidato tiene "
    "anclaje A/B/C/D. La medicion 7/7 en recall_at_5 es del fixture de "
    "referencia (docs_plan/R2_2_CIERRE_Y_CAPA_SEMANTICA.md §4.4); en un "
    "documento nuevo la recuperacion NO garantiza que la evidencia real "
    "este dentro de este top-k. Revisa los pasajes, no los asumas correctos."
)


def enqueue_finding_for_review(*, run_id: str, requirement_id: str, document_id: str,
                                page: int | None, evidence_quote: str, conclusion: str,
                                review_flags: list[str], agent_id: str,
                                candidates: list[dict] | None = None) -> dict:
    """R1.8 (2026-08-09, docs_plan/R1_CIERRE_Y_PREP_R2.md): despacha un
    finding con conclusion SUPPORTING_EVIDENCE_UNDER_REVIEW a la MISMA cola
    de revisión humana que ya usan los Release Candidates -- mismo almacén
    append-only, mismo locking, mismo evento de auditoría por escritura.

    No es un Release Candidate real; usa un item_id sintético
    ('finding-{run_id}-{requirement_id}') en el campo 'rc_id' para
    reutilizar list_pending()/mark_reviewed() sin reescribirlos -- ambos
    solo requieren ese campo + 'status', son agnósticos al tipo de
    contenido. 'entry_type' distingue esta clase de entrada de un RC real
    para cualquier consumidor (UI, reporte) que necesite filtrar.

    Nunca cambia la conclusion ni la promueve -- es solo la notificación
    de que hay evidencia observada, anclada, que necesita confirmación
    humana (CLAUDE.md: sin declaración de cumplimiento por el sistema).

    candidates (R2.3 §4, 2026-08-11, docs_plan/R2_3_CONSOLIDACION_Y_TIER1.md):
    opcional -- lista de dicts {chunk_index, page_start, page_end, bm25_rank,
    embedding_rank, fusion_rank, excerpt} del modo JUICIO (candidate pool de
    fusión semántica). '[]' (nunca None) cuando no aplica, para que ningún
    consumidor tenga que chequear presencia de la clave. Cuando hay
    candidatos, `summary["candidates_honesty_note"]` se adjunta SIEMPRE --
    son recuperación, no evidencia validada (§4.2)."""
    item_id = f"finding-{run_id}-{requirement_id}"
    summary = {
        "run_id": run_id,
        "requirement_id": requirement_id,
        "document_id": document_id,
        "page": page,
        "evidence_quote": evidence_quote,
        "conclusion": conclusion,
        "review_flags": review_flags,
        "agent_id": agent_id,
        "candidates": candidates or [],
    }
    if candidates:
        summary["candidates_honesty_note"] = _CANDIDATES_HONESTY_NOTE
    entry = {
        "schema_version": "finding_review_v2",
        "rc_id": item_id,
        "entry_type": "finding_review",
        "project_id": document_id,
        "enqueued_at": _ts(),
        "status": "pending",
        "summary": summary,
    }
    REVIEW_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = REVIEW_QUEUE_FILE.with_suffix(".lock")
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(REVIEW_QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    write_event("finding_enqueued_for_review", document_id, {
        "rc_id": item_id,
        "requirement_id": requirement_id,
        "run_id": run_id,
        "conclusion": conclusion,
    })
    return entry


def list_pending() -> list[dict]:
    """Retorna los RCs con status='pending'."""
    return [e for e in _read_all() if e.get("status") == "pending"]


def get_queue_summary() -> dict:
    """Conteo por estado."""
    entries = _read_all()
    summary: dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0, "returned": 0}
    for e in entries:
        st = e.get("status", "pending")
        if st in summary:
            summary[st] += 1
    return summary


def mark_reviewed(rc_id: str, decision: str, reviewer: str, *,
                   confirmed_page: int | None = None,
                   confirmed_quote: str | None = None) -> dict:
    """Actualiza el estado de un RC en la cola. `reviewer` no puede ser una
    identidad reservada -- valida contra `factory.core.identity_policy`
    (UNA sola lista de identidades reservadas en toda la fábrica, W5 V2
    G1.15; ver docstring de ese módulo -- ocho copias distintas de esta
    lista fue exactamente el defecto que ese módulo cierra, así que este
    archivo NO define la suya).

    confirmed_page/confirmed_quote (R2.3 §4.3, 2026-08-11): opcionales --
    cuando un humano confirma evidencia real señalada entre los
    `candidates` de una entrada de modo JUICIO (§4), el registro guarda la
    página+cita que el humano señaló. Persistido en la MISMA entrada
    (`human_confirmed_evidence`), un solo evento de auditoría igual que
    cualquier otra revisión -- esto alimenta al futuro Golden Dataset con
    positivos nuevos verificados por un humano real, no por el modelo."""
    from factory.core.identity_policy import validate_identity
    reviewer = validate_identity(reviewer, field="reviewer")

    entries = _read_all()
    updated = False
    for e in entries:
        if e.get("rc_id") == rc_id:
            e["status"] = decision
            e["reviewer"] = reviewer
            e["reviewed_at"] = _ts()
            if confirmed_quote is not None:
                e["human_confirmed_evidence"] = {
                    "page": confirmed_page, "quote": confirmed_quote,
                    "confirmed_by": reviewer, "confirmed_at": e["reviewed_at"],
                }
            updated = True
            project_id = e.get("project_id", "unknown")
            break

    if not updated:
        raise FileNotFoundError(f"RC '{rc_id}' no encontrado en la cola")

    _rewrite(entries)

    event_data = {
        "rc_id": rc_id,
        "decision": decision,
        "reviewer": reviewer,
    }
    if confirmed_quote is not None:
        event_data["human_confirmed_evidence"] = True
    write_event("rc_reviewed", project_id, event_data)
    return {"rc_id": rc_id, "decision": decision, "reviewer": reviewer}
