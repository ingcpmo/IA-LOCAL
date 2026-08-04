"""Firma con echo-back de propuestas `ARTIFACT_VERSION` — panel ARQ
2026-08-04 (`docs_plan/W5V2_ARQ_DESBLOQUEO_FIRMA_CATALOGO.md`).

Por que existe un modulo separado, no una ampliacion de
`governance_service.confirm()`: ese `confirm()` generico lo usan los seis
paneles de gobernanza, y ya se aprendio el costo de ampliar una funcion
compartida sin caso real en el resto de ellos (ver `artifact_version_apply.py`,
intento revertido de tocar `applicability.py` compartido con
`chunked_engine.py`). Aqui el caso real es concreto (el humano debe firmar
EXACTAMENTE lo que ve, byte a byte) y no aplica a los otros cinco paneles
todavia -- generalizar sin ese quinto caso repetiria el mismo error.

Ciclo de vida derivado (nunca declarado a mano) de una propuesta
`ARTIFACT_VERSION` para un `artifact_path`:

  PROPOSED    agent_proposed, sin confirmar, no expirada, no abandonada.
  SIGNED      tiene un registro `human_confirmed` que la confirma, pero
              ningun `version_record` referencia esa confirmacion todavia
              (confirmada, apply() pendiente -- paso separado y posterior).
  APPLIED     confirmada Y aplicada: algun `version_record` real tiene
              `approved_by_decision` == el `decision_instance_id` de la
              confirmacion.
  WITHDRAWN   expirada, abandonada o rechazada -- nunca se puede firmar.

`SUPERSEDED` no es un estado de UNA propuesta: es una relacion entre DOS
(una PROPOSED cuyo `artifact_hash_before`/`from_version` ya no coincide con
el estado vivo porque OTRA se aplico despues) -- se expone como campo
`payload_complete`/`matches_live_state`, no como un quinto valor de
`status`, para no inventar un estado que el modelo de decisiones no
registra."""
from __future__ import annotations

from pathlib import Path

from factory.core import artifact_version_guard as guard
from factory.services import decision_store_v2 as store
from factory.services import governance_service as gov

FAMILY = "ARTIFACT_VERSION"
REQUIRED_PAYLOAD_FIELDS = (
    "artifact_path", "artifact_hash_before", "from_version", "to_version",
    "expected_hash_after", "change_reason",
)

STATUS_PROPOSED = "PROPOSED"
STATUS_SIGNED = "SIGNED"
STATUS_APPLIED = "APPLIED"
STATUS_WITHDRAWN = "WITHDRAWN"


class ProposalMismatchError(Exception):
    """El echo-back del firmante no coincide byte a byte con lo almacenado."""


class DuplicateSignatureError(Exception):
    """Esta propuesta ya fue resuelta (firmada o rechazada) por otro registro."""


def _payload_complete(payload: dict) -> bool:
    return all(payload.get(f) not in (None, "") for f in REQUIRED_PAYLOAD_FIELDS)


def _derive_status(record: dict, *, all_records: list[dict],
                   version_records: list[dict]) -> str:
    iid = record["decision_instance_id"]
    state = gov.proposal_state(iid, records=all_records)
    if state in (gov.PROPOSAL_ABANDONED, gov.PROPOSAL_EXPIRED):
        return STATUS_WITHDRAWN
    confirm = next((r for r in all_records if r.get("confirms_instance_id") == iid), None)
    if confirm is None:
        return STATUS_PROPOSED
    if confirm.get("decision") != "APPROVE":
        return STATUS_WITHDRAWN
    confirm_id = confirm["decision_instance_id"]
    applied = any(vr.get("approved_by_decision") == confirm_id for vr in version_records)
    return STATUS_APPLIED if applied else STATUS_SIGNED


def list_artifact_version_proposals(artifact_path: str, *,
                                    store_file: Path | None = None,
                                    versions_store_file: Path | None = None
                                    ) -> list[dict]:
    """Propuestas `ARTIFACT_VERSION` filtradas por `artifact_path` EXACTO
    (nunca por prefijo, nunca "la primera") -- lee EXCLUSIVAMENTE
    `decisions_v2` (el unico almacen canonico; no existe un almacen legacy
    vivo para esta familia -- `ARTIFACT_VERSION` nacio ya en el modelo
    nuevo, G1.1). Cada entrada trae su `state_hash` vigente para que el
    firmante pueda reenviarlo intacto."""
    all_records = store.read_all(store_file)
    version_records = guard.read_version_records(versions_store_file)
    # De FAMILIA, no global: sign_artifact_version_proposal() reenvia este
    # valor como family_state_hash a confirm() (mismo ambito que ya usaba
    # el JS via GOV.family_state_hashes.ARTIFACT_VERSION -- bug real
    # encontrado el 2026-08-04 al probar el CLI fallback con almacen
    # temporal: esta funcion devolvia el hash GLOBAL, que confirm()
    # entonces comparaba contra el de familia y siempre daba 409).
    current_state_hash = gov.family_state_hash(FAMILY, store_file=store_file)

    out = []
    for r in all_records:
        if r.get("decision_family") != FAMILY:
            continue
        if r.get("decision_origin") != "agent_proposed":
            continue
        if artifact_path not in (r.get("resolved_target_ids") or []):
            continue
        payload = r.get("payload") or {}
        out.append({
            "proposal_id": r["decision_instance_id"],
            "artifact_path": artifact_path,
            "from_version": payload.get("from_version"),
            "to_version": payload.get("to_version"),
            "artifact_hash_before": payload.get("artifact_hash_before"),
            "expected_hash_after": payload.get("expected_hash_after"),
            "change_reason": payload.get("change_reason"),
            "created_at": r["recorded_at"],
            "created_by": r.get("proposed_by_id"),
            "status": _derive_status(r, all_records=all_records, version_records=version_records),
            "payload_complete": _payload_complete(payload),
            "state_hash": current_state_hash,
        })
    return sorted(out, key=lambda p: p["created_at"])


def sign_artifact_version_proposal(*, proposal_id: str, artifact_path: str,
                                   from_version: str, to_version: str,
                                   artifact_hash_before: str,
                                   expected_hash_after: str,
                                   state_hash: str, reason: str,
                                   approved_by_id: str,
                                   approved_by_display_name: str | None = None,
                                   store_file: Path | None = None,
                                   versions_store_file: Path | None = None) -> dict:
    """El humano firma EXACTAMENTE lo que ve: cada campo recibido se
    compara byte a byte contra la propuesta ALMACENADA antes de confirmar
    nada. Cualquier discrepancia (incluida una `state_hash` vieja) aborta
    sin escribir -- nunca se firma "lo mas parecido"."""
    proposals = list_artifact_version_proposals(
        artifact_path, store_file=store_file, versions_store_file=versions_store_file)
    proposal = next((p for p in proposals if p["proposal_id"] == proposal_id), None)
    if proposal is None:
        raise ProposalMismatchError(
            f"proposal_id={proposal_id!r} no existe para artifact_path={artifact_path!r}")

    if proposal["status"] != STATUS_PROPOSED:
        raise DuplicateSignatureError(
            f"{proposal_id!r} ya no esta PROPOSED (status={proposal['status']!r}) -- "
            "ya fue firmada, aplicada o retirada")

    echo = {
        "artifact_path": artifact_path, "from_version": from_version,
        "to_version": to_version, "artifact_hash_before": artifact_hash_before,
        "expected_hash_after": expected_hash_after,
    }
    stored = {k: proposal[k] for k in echo}
    mismatches = {k: (echo[k], stored[k]) for k in echo if echo[k] != stored[k]}
    if mismatches:
        raise ProposalMismatchError(
            f"el echo-back no coincide con la propuesta almacenada: {mismatches!r} -- "
            "el panel mostraba un estado distinto al actual, recarga antes de firmar")

    # `confirm()` genérico ya valida state_hash/identidad/duplicado (I-11,
    # 409/422) -- no se reimplementa aqui, solo se traduce su resultado.
    return gov.confirm(
        proposal_id, approved_by_id=approved_by_id,
        approved_by_display_name=approved_by_display_name, reason=reason,
        family_state_hash=state_hash, store_file=store_file)
