"""
Fase 1 (`factory/docs/document_remediation_evolution/IMPLEMENTATION_ROADMAP.md`)
— verificación real de acceso y comparación de hash de las fuentes
regulatorias gobernadas en `factory/regulatory/sources/registry.json`.

Regla dura: este módulo NUNCA escribe en `registry.json` ni reinterpreta
`regulatory_currency_status`. `schemas/source_registry_entry_v1.json` fija
ese campo a un enum de UN único valor posible (`pending_reverification`) a
propósito -- su descripción dice literalmente "NUNCA 'verified_current'/
'current' en este ciclo". Ese diseño fail-closed ya endurecido no se toca
aquí: el resultado de cada verificación real vive en un log append-only
separado (`source_currency_log.jsonl`, ver `factory/services/paths.py`).

Qué SÍ verifica, de forma real (nunca simulada, nunca inventada):
  - accesibilidad HTTP de `official_source_url` (GET real, con timeout,
    siguiendo redirects)
  - si responde 200: sha256 del contenido descargado, comparado contra
    `sha256_original` ya gobernado

Qué NO afirma: que el contenido siga siendo la versión vigente de la
norma -- eso requeriría conocimiento normativo externo que este módulo no
tiene. Por eso el resultado se llama `content_matches_governed_copy`
("el contenido que hay hoy en la URL coincide con lo que tenemos
gobernado"), nunca "vigente"/"current".

Mismo patrón de auditoría (`run_by` real obligatorio, 1 evento por
ejecución) que `regulatory_connector_service.py` (W6.3) ya usa -- sin rate
limit de cupo diario porque este checker opera sobre un conjunto fijo y
pequeño de fuentes ya gobernadas (hoy 3), no sobre consultas abiertas.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import httpx

from factory.services import paths

TIMEOUT_S = 15.0
USER_AGENT = "gmp-ai-factory-source-currency-checker/1.0 (read-only; verifica accesibilidad+hash)"
MIN_INTERVAL_BETWEEN_SOURCES_S = 2.0  # anti-ráfaga entre fuentes distintas


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def check_source(entry: dict) -> dict:
    """Verifica UNA fuente ya gobernada (una entrada real de registry.json).
    No escribe nada -- solo retorna el resultado. Función pura respecto a
    disco/log; separada de check_all_governed_sources() para poder testear
    la lógica de comparación sin persistencia ni auditoría."""
    source_id = entry["source_id"]
    url = entry.get("official_source_url")
    checked_at = _now()
    if not url:
        return {
            "source_id": source_id, "checked_at": checked_at, "url": None,
            "http_status": None, "reachable": False,
            "downloaded_sha256": None, "governed_sha256_original": entry.get("sha256_original"),
            "content_matches_governed_copy": None,
            "note": "sin official_source_url declarada",
        }
    try:
        resp = _http_get(url)
    except Exception as e:
        return {
            "source_id": source_id, "checked_at": checked_at, "url": url,
            "http_status": None, "reachable": False,
            "downloaded_sha256": None, "governed_sha256_original": entry.get("sha256_original"),
            "content_matches_governed_copy": None,
            "note": f"error de red: {type(e).__name__}: {e}",
        }

    reachable = resp.status_code == 200
    downloaded_sha256 = None
    content_matches = None
    if reachable:
        downloaded_sha256 = hashlib.sha256(resp.content).hexdigest()
        content_matches = downloaded_sha256 == entry.get("sha256_original")

    return {
        "source_id": source_id, "checked_at": checked_at, "url": url,
        "http_status": resp.status_code, "reachable": reachable,
        "downloaded_sha256": downloaded_sha256,
        "governed_sha256_original": entry.get("sha256_original"),
        "content_matches_governed_copy": content_matches,
        "note": None,
    }


def _append_log(result: dict) -> None:
    paths.SOURCE_CURRENCY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(result, ensure_ascii=False) + "\n"
    with open(paths.SOURCE_CURRENCY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        import os
        os.fsync(f.fileno())


def check_all_governed_sources(run_by: str, sources: list[dict]) -> list[dict]:
    """Verifica cada fuente de `sources` (el llamador pasa
    `load_source_registry()["sources"]` en producción; permite fixtures en
    tests sin tocar el registry.json real). Registra cada resultado en el
    log append-only, audita exactamente 1 evento agregado. NUNCA modifica
    registry.json."""
    from factory.services import test_console_service as _console
    name = _console.validate_run_by(run_by)

    results = []
    for i, entry in enumerate(sources):
        if i > 0:
            time.sleep(MIN_INTERVAL_BETWEEN_SOURCES_S)
        result = check_source(entry)
        result["run_by"] = name
        _append_log(result)
        results.append(result)

    from factory.core.audit_writer import write_event
    write_event("regulatory_source_currency_checked", "regulatory_intel", {
        "sources_checked": len(results),
        "reachable": sum(1 for r in results if r["reachable"]),
        "content_matches_governed_copy": sum(1 for r in results if r["content_matches_governed_copy"]),
        "run_by": name,
    })
    return results
