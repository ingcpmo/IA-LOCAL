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
pequeño de fuentes ya gobernadas (hoy 4), no sobre consultas abiertas.

W5 V2 G1.7 -- COBERTURA DE DECISIÓN ANTES DE LA RED
---------------------------------------------------
Este módulo es el consumidor C-1 del `DecisionScopeResolver`. La comprobación
va al PRINCIPIO de `check_source()`, antes de `_http_get`, y no en el nivel
de arriba: reverificar una fuente es salir a Internet a por algo que nadie
firmó que se pudiera usar, y una guardia en `check_all_governed_sources()`
dejaría abierto el bypass de llamar a `check_source()` directamente.

Consecuencia esperada y correcta: mientras la Corrección D1 y D1-A no estén
registradas (G2), NINGUNA fuente es reverificable -- incluidas las tres
antiguas, que solo respalda un snapshot reconstruido. G3 va después de G2 por
construcción, no porque alguien recuerde el orden.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from factory.core import decision_scope_resolver as _resolver
from factory.services import paths

DECISION_FAMILY = "D1"

TIMEOUT_S = 15.0
USER_AGENT = "gmp-ai-factory-source-currency-checker/1.0 (read-only; verifica accesibilidad+hash)"
MIN_INTERVAL_BETWEEN_SOURCES_S = 2.0  # anti-ráfaga entre fuentes distintas


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _denied(source_id: str, url: str | None, checked_at: str, entry: dict,
            scope) -> dict:
    """Resultado de una fuente sin cobertura humana. `reachable` es None, no
    False: False afirmaría que se intentó el acceso y falló. No se intentó."""
    return {
        "source_id": source_id, "checked_at": checked_at, "url": url,
        "http_status": None, "reachable": None,
        "downloaded_sha256": None,
        "governed_sha256_original": entry.get("sha256_original"),
        "content_matches_governed_copy": None,
        "authorized_by_decision": False,
        "reverification_allowed": False,
        "coverage_basis": scope.coverage_basis,
        "covering_decisions": list(scope.covering_instances),
        "note": f"REVERIFICATION_NOT_AUTHORIZED: {scope.denial_reason}",
    }


def check_source(entry: dict, *, decision_store_file: Path | None = None) -> dict:
    """Verifica UNA fuente ya gobernada (una entrada real de registry.json).
    No escribe nada -- solo retorna el resultado. Separada de
    check_all_governed_sources() para poder testear la lógica de comparación
    sin persistencia ni auditoría.

    Ya no es pura respecto a disco: LEE la cobertura de decisión antes de
    nada. Es deliberado -- una función pura que sale a Internet sin preguntar
    si alguien lo autorizó es precisamente el agujero que G1 cierra.
    """
    source_id = entry["source_id"]
    url = entry.get("official_source_url")
    checked_at = _now()

    # PRIMERA comprobación, antes de tocar la red. Fail-closed: si el
    # resolver no puede responder, no se accede.
    scope = _resolver.resolve(DECISION_FAMILY, source_id,
                              store_file=decision_store_file)
    if not scope.authorized:
        return _denied(source_id, url, checked_at, entry, scope)

    authorized_meta = {
        "authorized_by_decision": True,
        "reverification_allowed": True,
        "coverage_basis": scope.coverage_basis,
        "covering_decisions": list(scope.covering_instances),
    }

    if not url:
        return {
            "source_id": source_id, "checked_at": checked_at, "url": None,
            "http_status": None, "reachable": False,
            "downloaded_sha256": None, "governed_sha256_original": entry.get("sha256_original"),
            "content_matches_governed_copy": None,
            **authorized_meta,
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
            **authorized_meta,
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
        **authorized_meta,
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


def check_all_governed_sources(run_by: str, sources: list[dict], *,
                               decision_store_file: Path | None = None) -> list[dict]:
    """Verifica cada fuente de `sources` (el llamador pasa
    `load_source_registry()["sources"]` en producción; permite fixtures en
    tests sin tocar el registry.json real). Registra cada resultado en el
    log append-only, audita exactamente 1 evento agregado. NUNCA modifica
    registry.json.

    Una fuente sin cobertura se registra en el log igual que las demás -- que
    se intentó reverificar algo no autorizado es un hecho auditable, no algo
    que se omita en silencio.
    """
    from factory.services import test_console_service as _console
    name = _console.validate_run_by(run_by)

    results = []
    real_accesses = 0
    for entry in sources:
        # Pre-consulta barata y read-only solo para saber si HABRÁ tráfico: el
        # intervalo anti-ráfaga debe pagarse ANTES de la petición, y una
        # denegación no genera ninguna. `check_source` vuelve a resolver y
        # sigue siendo la guardia autoritativa -- esto no la sustituye.
        if _resolver.resolve(DECISION_FAMILY, entry["source_id"],
                             store_file=decision_store_file).authorized:
            if real_accesses:
                time.sleep(MIN_INTERVAL_BETWEEN_SOURCES_S)
            real_accesses += 1
        result = check_source(entry, decision_store_file=decision_store_file)
        result["run_by"] = name
        _append_log(result)
        results.append(result)

    denied = [r for r in results if not r.get("authorized_by_decision")]
    from factory.core.audit_writer import write_event
    write_event("regulatory_source_currency_checked", "regulatory_intel", {
        "sources_checked": len(results),
        "reachable": sum(1 for r in results if r["reachable"]),
        "content_matches_governed_copy": sum(1 for r in results if r["content_matches_governed_copy"]),
        "reverification_not_authorized": len(denied),
        "not_authorized_source_ids": [r["source_id"] for r in denied],
        "run_by": name,
    })
    return results
