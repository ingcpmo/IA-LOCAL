"""
Fase 1 (`factory/docs/document_remediation_evolution/IMPLEMENTATION_ROADMAP.md`)
— `broken_link_report`: evalúa fallos de acceso consecutivos sobre el
historial ya escrito por `source_currency_checker.py`
(`factory/regulatory/source_currency_log.jsonl`) y marca una fuente como
`REGULATORY_SOURCE_UNVERIFIED` cuando las últimas `min_consecutive_failures`
verificaciones reales fueron todas inalcanzables (404/timeout/error de red).

Regla dura (`TARGET_REGULATORY_ARCHITECTURE.md` §3): este módulo NUNCA
reemplaza ni sugiere una `official_source_url` nueva -- solo notifica para
que un humano decida (mismo patrón de aprobación explícita que
`applicability_matrix.approval` y `human_review_queue.py`). El resultado de
cada evaluación se acumula en un log append-only separado
(`broken_link_report.jsonl`, ver `factory/services/paths.py`); no reescribe
`source_currency_log.jsonl` ni `registry.json`.

Solo mira `reachable` (accesibilidad HTTP), nunca
`content_matches_governed_copy` -- un hash que no coincide no es un enlace
roto, es una discrepancia de contenido; mezclar ambas señales inventaría un
significado que `TARGET_REGULATORY_ARCHITECTURE.md` no le da a este reporte.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from factory.services import paths

DEFAULT_MIN_CONSECUTIVE_FAILURES = 3

STATUS_OK = "OK"
STATUS_UNVERIFIED = "REGULATORY_SOURCE_UNVERIFIED"
STATUS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_currency_log() -> list[dict]:
    if not paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def evaluate_source(
    source_id: str,
    log_entries: list[dict],
    min_consecutive_failures: int = DEFAULT_MIN_CONSECUTIVE_FAILURES,
) -> dict:
    """Evalúa UNA fuente contra su propio historial ya registrado.
    Función pura respecto a disco -- separada de build_report() para poder
    testear la lógica de umbral sin persistencia ni auditoría."""
    history = sorted(
        (e for e in log_entries if e["source_id"] == source_id),
        key=lambda e: e["checked_at"],
    )
    last_n = history[-min_consecutive_failures:]

    if len(last_n) < min_consecutive_failures:
        status = STATUS_INSUFFICIENT_HISTORY
    elif all(e["reachable"] is False for e in last_n):
        status = STATUS_UNVERIFIED
    else:
        status = STATUS_OK

    return {
        "source_id": source_id,
        "evaluated_at": _now(),
        "min_consecutive_failures": min_consecutive_failures,
        "checks_considered": len(last_n),
        "last_checked_at": last_n[-1]["checked_at"] if last_n else None,
        "status": status,
    }


def _append_report(entry: dict) -> None:
    paths.BROKEN_LINK_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(paths.BROKEN_LINK_REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        import os
        os.fsync(f.fileno())


def build_report(
    run_by: str,
    source_ids: list[str],
    min_consecutive_failures: int = DEFAULT_MIN_CONSECUTIVE_FAILURES,
) -> list[dict]:
    """Evalúa cada `source_id` (el llamador pasa los `source_id` de
    `load_source_registry()["sources"]` en producción; permite subconjuntos
    en tests) contra el historial real de `source_currency_log.jsonl`.
    Registra cada resultado en el log append-only, audita exactamente 1
    evento agregado. NUNCA modifica `registry.json` ni sugiere una URL."""
    from factory.services import test_console_service as _console
    name = _console.validate_run_by(run_by)

    log_entries = _read_currency_log()
    results = []
    for source_id in source_ids:
        result = evaluate_source(source_id, log_entries, min_consecutive_failures)
        result["run_by"] = name
        _append_report(result)
        results.append(result)

    from factory.core.audit_writer import write_event
    write_event("regulatory_broken_link_report_generated", "regulatory_intel", {
        "sources_evaluated": len(results),
        "flagged_unverified": sum(1 for r in results if r["status"] == STATUS_UNVERIFIED),
        "insufficient_history": sum(1 for r in results if r["status"] == STATUS_INSUFFICIENT_HISTORY),
        "run_by": name,
    })
    return results
