"""
G3 (`W5V2_REGULATORY_REDESIGN`) — `artifact_type_mismatch_report`: evalúa
"no comparable" (`comparable: False`) consecutivo sobre el historial ya
escrito por `source_currency_checker.py`
(`factory/regulatory/source_currency_log.jsonl`) y marca una fuente como
`ARTIFACT_TYPE_MISMATCH` cuando las últimas `min_consecutive_mismatches`
verificaciones reales encontraron sistemáticamente un tipo de artefacto
servido distinto del gobernado (URL viva, pero HTML donde se archivó un
PDF/TXT, por ejemplo).

Hermano deliberadamente SEPARADO de `broken_link_report.py`, no una
extensión suya: ese módulo mide únicamente `reachable` y su propio
docstring dice explícitamente que mezclar `comparable`/
`content_matches_governed_copy` ahí "inventaría un significado que
`TARGET_REGULATORY_ARCHITECTURE.md` no le da a este reporte". El caso que
motiva este módulo (real, encontrado en la primera corrida de G3:
`ecfr_21cfr_part11`/`mhra_gxp_di_guidance_2018` sirven HTML/página de
publicaciones donde lo gobernado es TXT/PDF) es un tipo de discrepancia
distinto de un enlace roto -- la URL responde 200, el problema es que
apunta al artefacto equivocado -- y por eso necesita su propio reporte en
vez de forzar el existente a significar dos cosas.

Regla dura, igual que `broken_link_report.py` (`TARGET_REGULATORY_ARCHITECTURE.md`
§3): este módulo NUNCA reemplaza ni sugiere una `official_source_url`
nueva -- solo notifica para que un humano decida. Log append-only separado
(`artifact_type_mismatch_report.jsonl`); no reescribe `source_currency_log.jsonl`
ni `registry.json`.

Solo mira `comparable` (tal como lo calcula `source_currency_checker.
_comparability()`), nunca `reachable` -- una fuente inalcanzable es
competencia de `broken_link_report.py`, no de este módulo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from factory.services import paths

DEFAULT_MIN_CONSECUTIVE_MISMATCHES = 3

STATUS_OK = "OK"
STATUS_ARTIFACT_TYPE_MISMATCH = "ARTIFACT_TYPE_MISMATCH"
STATUS_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_source(
    source_id: str,
    log_entries: list[dict],
    min_consecutive_mismatches: int = DEFAULT_MIN_CONSECUTIVE_MISMATCHES,
) -> dict:
    """Evalúa UNA fuente contra su propio historial ya registrado. Función
    pura respecto a disco, mismo patrón que `broken_link_report.evaluate_source()`.
    Entradas anteriores a G3 no tienen la clave `comparable` -- `.get()`
    las trata como `None`, nunca como mismatch, así que no cuentan a favor
    de un status que ellas mismas no midieron."""
    history = sorted(
        (e for e in log_entries if e["source_id"] == source_id),
        key=lambda e: e["checked_at"],
    )
    last_n = history[-min_consecutive_mismatches:]

    if len(last_n) < min_consecutive_mismatches:
        status = STATUS_INSUFFICIENT_HISTORY
    elif all(e.get("comparable") is False for e in last_n):
        status = STATUS_ARTIFACT_TYPE_MISMATCH
    else:
        status = STATUS_OK

    return {
        "source_id": source_id,
        "evaluated_at": _now(),
        "min_consecutive_mismatches": min_consecutive_mismatches,
        "checks_considered": len(last_n),
        "last_checked_at": last_n[-1]["checked_at"] if last_n else None,
        "status": status,
    }


def _append_report(entry: dict) -> None:
    paths.ARTIFACT_TYPE_MISMATCH_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(paths.ARTIFACT_TYPE_MISMATCH_REPORT_FILE, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        import os
        os.fsync(f.fileno())


def build_report(
    run_by: str,
    source_ids: list[str],
    min_consecutive_mismatches: int = DEFAULT_MIN_CONSECUTIVE_MISMATCHES,
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
        result = evaluate_source(source_id, log_entries, min_consecutive_mismatches)
        result["run_by"] = name
        _append_report(result)
        results.append(result)

    from factory.core.audit_writer import write_event
    write_event("regulatory_artifact_type_mismatch_report_generated", "regulatory_intel", {
        "sources_evaluated": len(results),
        "flagged_mismatch": sum(1 for r in results if r["status"] == STATUS_ARTIFACT_TYPE_MISMATCH),
        "insufficient_history": sum(1 for r in results if r["status"] == STATUS_INSUFFICIENT_HISTORY),
        "run_by": name,
    })
    return results


def _read_currency_log() -> list[dict]:
    if not paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries
