"""Confirmación gobernada de que una segunda reingesta real coincide con el
origen -- familia `SOURCE_ORIGIN_VERIFICATION` (G3, DEC-B).

Cierra el hallazgo estructural documentado en
`docs_plan/W5V2_ARQ_RETOMAR_Y_FINALIZAR.md` Bloque 1 (y la memoria de
`project_w5_v2_regulatory_redesign`, actualizaciones 2026-08-05 (4)/(5)/(6)):
`source_lifecycle.py._dim_official_origin_verification()` deja una fuente en
ámbar `FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE` hasta que exista "un
segundo punto de comparación en el tiempo" contra el mismo origen oficial --
pero ANTES de este módulo no existía ningún escritor capaz de promover ese
campo tras esa segunda observación real. Los 3 candidatos ya existentes NO
sirven para este caso:
  - `reverify_governed_sources.py` SÍ hace la comparación real (descarga +
    hash), pero solo escribe a `source_currency_log.jsonl` -- nunca toca
    `official_origin_status`.
  - `human_source_update.py` solo edita URL/descripción.
  - `human_source_regovernance.py` es el único escritor de
    `official_origin_status`, pero está diseñado para un artefacto que
    CAMBIA DE TIPO (p.ej. TEXT->XML) -- exige declarar el campo de nuevo
    porque preservarlo afirmaría una verificación que nunca ocurrió sobre un
    archivo distinto. Aplicarlo aquí sería el caso opuesto: el archivo NO
    cambió de tipo, solo se confirmó por segunda vez.

Distinta de `SOURCE_CURRENCY` (`source_currency_confirmation.py`): aquella
declara VIGENCIA NORMATIVA (juicio regulatorio de que la norma sigue
aplicando hoy); esta declara PROCEDENCIA DEL ARCHIVO (que existe una segunda
observación real contra el mismo origen oficial). Un hash idéntico prueba
esto último, nunca lo primero -- por eso son familias separadas, mismo
criterio arquitectónico que ya separa `broken_link_report` de
`artifact_type_mismatch_report`.

Mismo ciclo propose -> confirm -> apply que el resto de la fábrica:

  propose_source_origin_verification()  agent_proposed, deriva el payload de
                                          la ÚLTIMA entrada real del log --
                                          nunca acepta el hash como parámetro
                                          humano. Exige official_origin_status
                                          VIVO en el ámbar exacto (fail-closed:
                                          nunca re-promueve una fuente que ya
                                          no está en ese estado, ni una que
                                          nunca estuvo).
  confirm                                governance_service.confirm() ya
                                          genérico -- sin campo nuevo que
                                          escribir aquí.
  apply_source_origin_verification()     único punto de escritura de
                                          `official_origin_status` para esta
                                          transición. Re-verifica AL MOMENTO
                                          DE APLICAR que la evidencia sigue
                                          siendo la más reciente y sigue
                                          coincidiendo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov
from factory.services import paths

DECISION_FAMILY = "SOURCE_ORIGIN_VERIFICATION"
REQUIRED_PAYLOAD_FIELDS = (
    "source_id", "reviewed_log_checked_at", "reviewed_downloaded_sha256",
    "governed_sha256_original", "prior_official_origin_status",
)

REGISTRY_FILE = Path(__file__).parent / "sources" / "registry.json"

#: Prefijo ámbar exacto que `source_lifecycle.py` exige para dejar de ser
#: NOT_COMPARABLE_FIRST_INGESTION -- ver `_dim_official_origin_verification()`.
FIRST_INGESTION_PREFIX = "FIRST_INGESTION_NO_PRIOR_KNOWN_HASH"


class SourceOriginVerificationError(Exception):
    pass


def _read_currency_log() -> list[dict]:
    if not paths.SOURCE_CURRENCY_LOG_FILE.exists():
        return []
    entries = []
    for line in paths.SOURCE_CURRENCY_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _latest_log_entry(source_id: str, entries: list[dict]) -> dict | None:
    matches = [e for e in entries if e.get("source_id") == source_id]
    return max(matches, key=lambda e: e["checked_at"]) if matches else None


def _read_registry() -> dict:
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def _find_entry(registry: dict, source_id: str) -> dict:
    entry = next((s for s in registry["sources"] if s["source_id"] == source_id), None)
    if entry is None:
        raise SourceOriginVerificationError(f"{source_id!r} no existe en sources/registry.json")
    return entry


def propose_source_origin_verification(source_id: str, *, proposed_by_id: str,
                                       decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) que una segunda reingesta real ya coincidió
    con el origen, basado en la ÚLTIMA verificación real del log.

    Sin campo de juicio humano libre (a diferencia de SOURCE_CURRENCY): este
    payload no afirma vigencia normativa, solo procedencia del archivo -- un
    hecho que el hash ya prueba por sí mismo, no una interpretación."""
    entry = _find_entry(_read_registry(), source_id)
    current_status = str(entry.get("official_origin_status") or "")
    if not current_status.startswith(FIRST_INGESTION_PREFIX):
        raise SourceOriginVerificationError(
            f"{source_id!r}: official_origin_status vivo ({current_status!r}) no está en el "
            f"ámbar {FIRST_INGESTION_PREFIX!r} -- nada que promover (ni ya verificado, ni "
            "en ningún otro estado que este mecanismo deba tocar)")

    entries = _read_currency_log()
    latest = _latest_log_entry(source_id, entries)
    if latest is None:
        raise SourceOriginVerificationError(f"{source_id!r} no tiene ninguna verificación en el log")
    if latest.get("comparable") is not True or latest.get("content_matches_governed_copy") is not True:
        raise SourceOriginVerificationError(
            f"{source_id!r}: la última verificación ({latest.get('checked_at')}) no es "
            f"comparable=True/matches=True (comparable={latest.get('comparable')!r}, "
            f"content_matches_governed_copy={latest.get('content_matches_governed_copy')!r}) -- "
            "no hay segunda observación real que promover")

    payload = {
        "source_id": source_id,
        "reviewed_log_checked_at": latest["checked_at"],
        "reviewed_downloaded_sha256": latest["downloaded_sha256"],
        "governed_sha256_original": entry["sha256_original"],
        "prior_official_origin_status": current_status,
    }
    reason = (
        f"Segunda reingesta real ({latest['checked_at']}) coincide con el origen oficial "
        f"ya gobernado (sha256={entry['sha256_original'][:16]}...) -- promueve de "
        f"{FIRST_INGESTION_PREFIX} a VERIFIED_AGAINST_PRIOR_KNOWN_HASH."
    )
    return gov.propose(
        DECISION_FAMILY, target_ids=[source_id], decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=reason, payload=payload, store_file=decision_store_file)


def apply_source_origin_verification(source_id: str, *, decision_instance_id: str,
                                     decision_store_file: Path | None = None,
                                     now: datetime | None = None) -> dict:
    """Único punto de escritura de `official_origin_status` para la
    transición FIRST_INGESTION -> VERIFIED_AGAINST_PRIOR_KNOWN_HASH.
    Fail-closed en cada paso -- nada se escribe hasta validar cobertura real,
    payload completo, y que la evidencia SIGA siendo válida al momento de
    aplicar (no solo al proponer/firmar)."""
    scope = resolver.resolve(DECISION_FAMILY, source_id, store_file=decision_store_file)
    if not scope.authorized:
        raise SourceOriginVerificationError(f"{source_id!r} no está autorizado: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise SourceOriginVerificationError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan cobertura "
            f"({scope.covering_instances!r}) -- no se aplica con una decisión que no es la "
            "que lo autoriza")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise SourceOriginVerificationError(f"{decision_instance_id!r} no se encuentra en el almacén")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise SourceOriginVerificationError(f"payload incompleto, faltan: {missing}")
    if payload["source_id"] != source_id:
        raise SourceOriginVerificationError(
            f"la decisión autoriza source_id={payload['source_id']!r}, no {source_id!r}")

    # Re-verificar AL MOMENTO DE APLICAR: la evidencia que el humano vio al
    # firmar pudo quedar superada por una corrida posterior del checker.
    entries = _read_currency_log()
    latest = _latest_log_entry(source_id, entries)
    if latest is None or latest["checked_at"] < payload["reviewed_log_checked_at"]:
        raise SourceOriginVerificationError(
            f"{source_id!r}: no hay ninguna verificación tan reciente como la declarada "
            "en el payload -- el log parece haberse movido hacia atrás")
    if latest.get("comparable") is not True or latest.get("content_matches_governed_copy") is not True:
        raise SourceOriginVerificationError(
            f"{source_id!r}: la verificación MÁS RECIENTE ({latest['checked_at']}) ya no es "
            "comparable=True/matches=True -- la evidencia quedó superada desde que se firmó, "
            "no se aplica sobre un estado que ya no es cierto")

    registry = _read_registry()
    entry = _find_entry(registry, source_id)
    if entry["sha256_original"] != payload["governed_sha256_original"]:
        raise SourceOriginVerificationError(
            f"sha256_original vivo ({entry['sha256_original']}) no coincide con el declarado "
            f"en el payload ({payload['governed_sha256_original']}) -- el registry cambió "
            "desde que se propuso")
    current_status = str(entry.get("official_origin_status") or "")
    if current_status != payload["prior_official_origin_status"]:
        raise SourceOriginVerificationError(
            f"official_origin_status vivo ({current_status!r}) ya no coincide con el declarado "
            f"al proponer ({payload['prior_official_origin_status']!r}) -- nada que aplicar, "
            "o el registry cambió desde que se propuso")

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    before = current_status
    after = f"VERIFIED_AGAINST_PRIOR_KNOWN_HASH_{stamp}_REVERIFICATION"
    entry["official_origin_status"] = after

    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    from factory.core.audit_writer import write_event
    write_event("regulatory_source_origin_verified", "regulatory_intel", {
        "source_id": source_id, "decision_instance_id": decision_instance_id,
        "before": before, "after": after,
        "reviewed_log_checked_at": payload["reviewed_log_checked_at"],
    })

    return {"source_id": source_id, "before": before, "after": after,
            "decision_instance_id": decision_instance_id}
