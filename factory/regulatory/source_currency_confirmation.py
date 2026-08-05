"""Confirmación gobernada de vigencia regulatoria — familia `SOURCE_CURRENCY` (G3).

Cierra el hallazgo de la auditoría de firma (2026-08-05): `source_currency_
checker.py` puede verificar de forma real que el contenido de una fuente
sigue coincidiendo con lo archivado, pero un hash idéntico NO prueba que la
norma siga vigente hoy -- solo que la URL sirve lo mismo que ayer. Esa
diferencia es exactamente por qué el schema de `registry.json` fija
`regulatory_currency_status` a un único valor posible
(`pending_reverification`) y por qué, hasta este módulo, no existía ningún
lugar donde un humano pudiera declarar vigencia real: ni siquiera Cesar,
revisando la evidencia con sus propios ojos, tenía un botón o comando para
decirlo de forma que el sistema lo registrara.

Mismo ciclo propose -> confirm -> apply que el resto de la fábrica:

  propose_source_currency_confirmation()  agent_proposed, deriva el payload
                                            de la ÚLTIMA entrada real del
                                            log -- nunca acepta el hash como
                                            parámetro humano.
  confirm                                  gobernance_service.confirm() ya
                                            genérico -- sin campo nuevo que
                                            escribir aquí.
  apply_source_currency_confirmation()     único punto de escritura de
                                            `regulatory_currency_status`.
                                            Re-verifica AL MOMENTO DE
                                            APLICAR que la evidencia sigue
                                            siendo la más reciente y sigue
                                            coincidiendo -- una firma sobre
                                            evidencia que después quedó
                                            superada no se aplica.

`reverification_due` se deja SIEMPRE en su valor actual (normalmente
`null`): el propio schema exige que "NUNCA se calcule con una cadencia
inventada sin decisión humana explícita" -- fijar un número aquí sería
exactamente lo que esa regla prohíbe. La política de cadencia es un
`human_source_update.py` separado y gobernado, pendiente de que Capa 9 la
decida.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.core import decision_scope_resolver as resolver
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov
from factory.services import paths

DECISION_FAMILY = "SOURCE_CURRENCY"
REQUIRED_PAYLOAD_FIELDS = (
    "source_id", "reviewed_log_checked_at", "reviewed_downloaded_sha256",
    "governed_sha256_original", "regulatory_judgment_note",
)

REGISTRY_FILE = Path(__file__).parent / "sources" / "registry.json"


class SourceCurrencyError(Exception):
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
        raise SourceCurrencyError(f"{source_id!r} no existe en sources/registry.json")
    return entry


def propose_source_currency_confirmation(source_id: str, *, regulatory_judgment_note: str,
                                         proposed_by_id: str,
                                         decision_store_file: Path | None = None) -> dict:
    """Propone (`agent_proposed`) que una fuente sigue vigente, basado en la
    ÚLTIMA verificación real del log.

    `regulatory_judgment_note` es el ÚNICO campo de juicio humano del
    payload: el hash solo prueba que la URL coincide con lo archivado, no
    que la norma siga vigente -- eso lo declara explícitamente quien
    propone, y quien confirma lo revisa antes de firmar.
    """
    entries = _read_currency_log()
    latest = _latest_log_entry(source_id, entries)
    if latest is None:
        raise SourceCurrencyError(f"{source_id!r} no tiene ninguna verificación en el log")
    if latest.get("comparable") is not True or latest.get("content_matches_governed_copy") is not True:
        raise SourceCurrencyError(
            f"{source_id!r}: la última verificación ({latest.get('checked_at')}) no es "
            f"comparable=True/matches=True (comparable={latest.get('comparable')!r}, "
            f"content_matches_governed_copy={latest.get('content_matches_governed_copy')!r}) -- "
            "no se puede proponer vigencia sobre una verificación que no coincidió")
    nota = (regulatory_judgment_note or "").strip()
    if not nota:
        raise SourceCurrencyError(
            "regulatory_judgment_note es obligatorio -- el hash no prueba vigencia normativa, "
            "eso lo declara un humano")

    entry = _find_entry(_read_registry(), source_id)
    payload = {
        "source_id": source_id,
        "reviewed_log_checked_at": latest["checked_at"],
        "reviewed_downloaded_sha256": latest["downloaded_sha256"],
        "governed_sha256_original": entry["sha256_original"],
        "regulatory_judgment_note": nota,
    }
    return gov.propose(
        DECISION_FAMILY, target_ids=[source_id], decision_type="ORIGINAL",
        selection_mode="EXPLICIT_LIST", proposed_by_id=proposed_by_id,
        reason=nota, payload=payload, store_file=decision_store_file)


def apply_source_currency_confirmation(source_id: str, *, decision_instance_id: str,
                                       decision_store_file: Path | None = None) -> dict:
    """Único punto de escritura de `regulatory_currency_status`. Fail-closed
    en cada paso -- nada se escribe hasta validar cobertura real, payload
    completo, y que la evidencia SIGA siendo válida al momento de aplicar
    (no solo al proponer/firmar)."""
    scope = resolver.resolve(DECISION_FAMILY, source_id, store_file=decision_store_file)
    if not scope.authorized:
        raise SourceCurrencyError(f"{source_id!r} no está autorizado: {scope.denial_reason}")
    if decision_instance_id not in scope.covering_instances:
        raise SourceCurrencyError(
            f"{decision_instance_id!r} no es una de las decisiones que otorgan cobertura "
            f"({scope.covering_instances!r}) -- no se aplica con una decisión que no es la "
            "que lo autoriza")

    decision = next((r for r in store.read_all(decision_store_file)
                     if r.get("decision_instance_id") == decision_instance_id), None)
    if decision is None:
        raise SourceCurrencyError(f"{decision_instance_id!r} no se encuentra en el almacén")
    payload = decision.get("payload") or {}
    missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise SourceCurrencyError(f"payload incompleto, faltan: {missing}")
    if payload["source_id"] != source_id:
        raise SourceCurrencyError(
            f"la decisión autoriza source_id={payload['source_id']!r}, no {source_id!r}")

    # Re-verificar AL MOMENTO DE APLICAR: la evidencia que el humano vio al
    # firmar pudo quedar superada por una corrida posterior del checker.
    entries = _read_currency_log()
    latest = _latest_log_entry(source_id, entries)
    if latest is None or latest["checked_at"] < payload["reviewed_log_checked_at"]:
        raise SourceCurrencyError(
            f"{source_id!r}: no hay ninguna verificación tan reciente como la declarada "
            "en el payload -- el log parece haberse movido hacia atrás")
    if latest.get("comparable") is not True or latest.get("content_matches_governed_copy") is not True:
        raise SourceCurrencyError(
            f"{source_id!r}: la verificación MÁS RECIENTE ({latest['checked_at']}) ya no es "
            "comparable=True/matches=True -- la evidencia quedó superada desde que se firmó, "
            "no se aplica sobre un estado que ya no es cierto")

    registry = _read_registry()
    entry = _find_entry(registry, source_id)
    if entry["sha256_original"] != payload["governed_sha256_original"]:
        raise SourceCurrencyError(
            f"sha256_original vivo ({entry['sha256_original']}) no coincide con el declarado "
            f"en el payload ({payload['governed_sha256_original']}) -- el registry cambió "
            "desde que se propuso")
    if entry["regulatory_currency_status"] != "pending_reverification":
        raise SourceCurrencyError(
            f"regulatory_currency_status ya es {entry['regulatory_currency_status']!r} -- "
            "nada que aplicar")

    before = entry["regulatory_currency_status"]
    entry["regulatory_currency_status"] = "verified_current"
    # `reverification_due` NUNCA se calcula aquí: el propio schema exige que
    # nunca se fije una cadencia inventada sin decisión humana explícita de
    # Capa 9 -- se deja intacto (normalmente null, el valor honesto).

    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    from factory.core.audit_writer import write_event
    write_event("regulatory_source_currency_confirmed", "regulatory_intel", {
        "source_id": source_id, "decision_instance_id": decision_instance_id,
        "before": before, "after": "verified_current",
        "reviewed_log_checked_at": payload["reviewed_log_checked_at"],
    })

    return {"source_id": source_id, "before": before, "after": "verified_current",
            "decision_instance_id": decision_instance_id}
