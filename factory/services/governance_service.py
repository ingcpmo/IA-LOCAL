"""Servicio de gobernanza — W5 V2 G1.15.

Lógica de los seis endpoints de GOVERNANCE_UI_SPEC.md §3. `layer9.py` es una
capa HTTP fina sobre esto, como el resto de W5.

NO ES UNA SUPERFICIE DE DECISION NUEVA. Es la MISMA familia, el MISMO almacén
y el MISMO resolver, expuestos a un humano por HTTP. Los seis paneles de la UI
son vistas sobre una familia, no sistemas aparte -- por eso no hay un endpoint
por panel.

Reglas transversales que este módulo implementa (§1):

  U-1  Todo GET es de solo lectura. Jamás escribe auditoría ni promueve nada.
  U-2  Cada POST genera EXACTAMENTE UN evento (lo emite `append_record`).
  U-3  422 identidad genérica, con la función única de `identity_policy`.
  U-4  409 por duplicación Y por `state_hash` obsoleto (control optimista).
  U-5  Registrar NO ejecuta. Ninguna decisión dispara sus efectos aquí.

SOBRE EL CONTROL OPTIMISTA (§1.1)
---------------------------------
Cada GET devuelve un `state_hash` y cada POST lo reenvía. Sin esto, dos
pestañas abiertas producen decisiones firmadas sobre datos que ya no existen
-- que es exactamente el escenario que produjo el fork de la cadena de
auditoría (dos escritores con la cabeza cacheada), trasladado a la capa
humana. El mismo error, un nivel más arriba.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from factory.core import artifact_version_guard as _artifacts
from factory.core import audit_writer as _audit
from factory.core import decision_scope_resolver as _resolver
from factory.core import identity_policy as _identity
from factory.services import decision_store_v2 as store

GOVERNED_FAMILIES = ("D1", "D2", "D3", "D4", "D5")


class GovernanceNotFoundError(LookupError):
    """404 -- la propuesta o la decisión previa no existe."""


class StaleStateError(RuntimeError):
    """409 -- el estado cambió entre el GET y el POST."""


# ---------------------------------------------------------------------------
# state_hash
# ---------------------------------------------------------------------------

def compute_state_hash(*, store_file: Path | None = None) -> str:
    """Huella de TODO lo que un panel muestra antes de firmar.

    Incluye el almacén de decisiones, el registro de familias, los registries
    objetivo y la cabeza de la cadena de auditoría. Si cambia cualquiera de
    ellos, lo que el humano leyó ya no es lo que hay, y firmar sobre eso es
    firmar a ciegas.

    Deliberadamente NO incluye relojes ni contadores: dos lecturas seguidas
    sin cambios reales deben dar el mismo hash, o el control optimista se
    convierte en un 409 permanente y alguien lo desactiva.
    """
    parts: list[str] = []

    records = store.read_all(store_file)
    parts.append(hashlib.sha256(
        json.dumps(records, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest())

    try:
        parts.append(store.families_registry_hash())
    except Exception:  # noqa: BLE001 -- despliegue roto: entra como marca
        parts.append("FAMILIES_UNAVAILABLE")

    for family in GOVERNED_FAMILIES:
        try:
            _ids, registry_hash = store.resolve_all_snapshot(family)
            parts.append(f"{family}:{registry_hash}")
        except Exception:  # noqa: BLE001 -- familias sin target_registry
            parts.append(f"{family}:N/A")

    walk = _audit._walk_chain(_audit.AUDIT_FILE)
    parts.append(f"audit:{walk['total']}:{walk['chain_errors']}:{walk['hash_errors']}")

    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _require_fresh(state_hash: str | None, *, store_file: Path | None = None) -> None:
    if state_hash is None:
        # Se exige explícitamente en vez de asumir: un POST sin `state_hash`
        # es un cliente que no leyó, no un cliente al día.
        raise StaleStateError(
            "falta `state_hash`: hay que leer el estado antes de firmarlo")
    actual = compute_state_hash(store_file=store_file)
    if state_hash != actual:
        raise StaleStateError(
            f"state_hash obsoleto (leido {state_hash[:12]}…, actual {actual[:12]}…): "
            "el estado cambio entre la lectura y la firma. Recarga y revisa."
        )


# ---------------------------------------------------------------------------
# GET -- solo lectura (U-1)
# ---------------------------------------------------------------------------

def get_coverage(family: str, *, store_file: Path | None = None) -> dict:
    report = _resolver.coverage_report(family, store_file=store_file)
    return {**report.__dict__,
            "registry_ids": list(report.registry_ids),
            "covered_ids": list(report.covered_ids),
            "uncovered_ids": list(report.uncovered_ids),
            "revoked_ids": list(report.revoked_ids),
            "reconstructed_only_ids": list(report.reconstructed_only_ids),
            "invalid_instances": list(report.invalid_instances),
            "pending_resignature_instances": list(report.pending_resignature_instances),
            "active_instances": list(report.active_instances)}


def _critical_path(coverage: dict, audit: dict, artifacts: dict) -> list[dict]:
    """Los gates G1..G8 con su estado y QUE FALTA para cerrarlos.

    Una tarjeta bloqueada tiene que decir por qué en la propia tarjeta (U-7):
    un bloqueo sin motivo es indistinguible de un fallo.
    """
    d1_uncovered = coverage.get("D1", {}).get("uncovered_ids", [])
    d1_reconstructed = coverage.get("D1", {}).get("reconstructed_only_ids", [])
    d2_uncovered = coverage.get("D2", {}).get("uncovered_ids", [])
    forks_sin_aceptar = audit.get("unbacked_known_fork_entry_ids", [])

    def gate(gid, label, done, blocked_by):
        return {"gate": gid, "label": label,
                "status": "CERRADO" if done else ("LISTO" if not blocked_by else "BLOQUEADO"),
                "blocked_by": blocked_by}

    g2_done = not d1_uncovered and not d1_reconstructed
    return [
        gate("G1", "Modelo, resolver y enforcement", True, []),
        gate("G2", "Correccion D1 + D1-A", g2_done,
             [] if not g2_done else []),
        gate("G3", "Reverificacion de fuentes", False,
             [] if g2_done else ["G2: ninguna fuente esta autorizada todavia"]),
        gate("G4", "Versionado de artefactos", False,
             [] if artifacts.get("records_in_store") else
             ["bootstrap de artifact_versions.jsonl sin ejecutar"]),
        gate("G5", "D2-A: aprobacion de Evidence Packs", False,
             ["G3: la vigencia de las fuentes no esta verificada"] if not g2_done
             else (["packs sin cobertura D2"] if d2_uncovered else [])),
        gate("G6", "Matriz de aplicabilidad", False, []),
        gate("G7", "Excepcion de auditoria", False,
             [f"fork sin excepcion firmada: {forks_sin_aceptar}"] if forks_sin_aceptar else []),
        gate("G8", "Retirada de los escritores legacy", False,
             ["G2-G7 abiertos"]),
    ]


def get_state(*, store_file: Path | None = None) -> dict:
    """El GET que alimenta el índice de los seis paneles. Solo lectura.

    Si algo no se puede leer, se declara en `unavailable_reason` en vez de
    devolver un valor por defecto: un `uncovered` vacío porque el backend
    falló es indistinguible de uno vacío de verdad, y esa ambigüedad es la
    que este trabajo entero existe para eliminar (§10).
    """
    families = store.load_families()
    coverage = {f: get_coverage(f, store_file=store_file) for f in GOVERNED_FAMILIES}
    audit = _audit.verify_chain()
    artifacts = _artifacts.guard_report(decision_store_file=store_file)

    return {
        "families": {name: {"label": spec.get("label"),
                            "target_kind": spec.get("target_kind"),
                            "selection_modes": spec.get("selection_modes"),
                            "consumers": spec.get("consumers"),
                            "requires_human_confirmation": spec.get("requires_human_confirmation")}
                     for name, spec in families.items()},
        "coverage": coverage,
        "artifacts": {"status": artifacts["status"],
                      "artifacts_seen": artifacts["artifacts_seen"],
                      "records_in_store": artifacts["records_in_store"],
                      "fail_count": artifacts["fail_count"],
                      "warn_count": artifacts["warn_count"]},
        "audit": {k: audit[k] for k in (
            "content_hash_integrity", "chain_continuity", "historical_fork_present",
            "new_forks_since_baseline", "new_fork_entry_ids",
            "unbacked_known_fork_entry_ids", "part11_compliant",
            "log_count", "hash_errors", "chain_errors")},
        "critical_path": _critical_path(coverage, audit, artifacts),
        # U-5: la leyenda viaja con los datos, no solo en el HTML. Un cliente
        # que solo consuma la API tiene que ver la misma advertencia.
        "notice": ("Registrar una decision NO ejecuta sus efectos: no reverifica "
                   "fuentes, no lanza corridas y no promueve ningun estado."),
        "state_hash": compute_state_hash(store_file=store_file),
        "read_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# POST -- propuesta y confirmacion
# ---------------------------------------------------------------------------

def propose(family: str, *, target_ids, decision: str = "APPROVE",
            decision_type: str = "ORIGINAL", selection_mode: str = "EXPLICIT_LIST",
            proposed_by_id: str, reason: str = "", payload: dict | None = None,
            supersedes_instance_id: str | None = None,
            amendment_sequence: int = 0,
            store_file: Path | None = None) -> dict:
    """Registra una PROPUESTA (`agent_proposed`). No autoriza nada.

    El resolver solo cuenta `human_confirmed`, así que una propuesta es
    exactamente eso: visible, auditada y sin efecto. Es la mitad del ciclo que
    el Sistema A tenía y el B no.

    `proposed_by_id` se valida con `validate_actor`, no con
    `validate_identity`: quien propone puede ser un agente, y exigirle nombre
    humano produciría un campo falso o una suplantación. Lo que impide que sea
    un bypass es que una propuesta no otorga cobertura.
    """
    _identity.validate_actor(proposed_by_id, field="proposed_by_id")

    record = store.build_record(
        decision_family=family,
        decision_type=decision_type,
        selection_mode=selection_mode,
        resolved_target_ids=list(target_ids),
        decision=decision,
        decision_origin="agent_proposed",
        proposed_by_id=proposed_by_id,
        supersedes_instance_id=supersedes_instance_id,
        amendment_sequence=amendment_sequence,
        reason=reason,
        payload=payload,
        store_file=store_file,
    )
    return store.append_record(record, store_file=store_file)


def _find(instance_id: str, records: list[dict]) -> dict:
    for r in records:
        if r.get("decision_instance_id") == instance_id:
            return r
    raise GovernanceNotFoundError(f"no existe la decision {instance_id!r}")


def _closing_record(instance_id: str, *, decision: str, decision_type: str,
                    by_id: str, by_name: str | None, reason: str,
                    field: str, store_file: Path | None) -> dict:
    """Registro humano que cierra una propuesta. NUNCA borra la propuesta.

    El almacén es append-only y la cadena es Part 11: rechazar es añadir el
    rechazo, no hacer desaparecer lo rechazado. Quien audite tiene que poder
    ver qué se propuso y que se dijo que no.
    """
    _identity.validate_identity(by_id, field=field)
    records = store.read_all(store_file)
    proposal = _find(instance_id, records)

    if proposal.get("decision_origin") != "agent_proposed":
        raise store.DecisionConflictError(
            f"{instance_id} no es una propuesta pendiente "
            f"(decision_origin={proposal.get('decision_origin')!r})")

    already = [r for r in records if r.get("confirms_instance_id") == instance_id]
    if already:
        raise store.DecisionConflictError(
            f"{instance_id} ya fue resuelta por "
            f"{already[0]['decision_instance_id']} ({already[0]['decision']})")

    record = store.build_record(
        decision_family=proposal["decision_family"],
        decision_type=decision_type,
        selection_mode=proposal["selection_mode"],
        resolved_target_ids=proposal["resolved_target_ids"],
        decision=decision,
        decision_origin="human_confirmed",
        approved_by_id=by_id,
        approved_by_display_name=by_name or by_id,
        confirms_instance_id=instance_id,
        supersedes_instance_id=proposal.get("supersedes_instance_id"),
        amendment_sequence=proposal.get("amendment_sequence", 0),
        reason=reason,
        payload=proposal.get("payload"),
        store_file=store_file,
    )
    return store.append_record(record, store_file=store_file)


def confirm(instance_id: str, *, approved_by_id: str,
            approved_by_display_name: str | None = None, reason: str = "",
            state_hash: str | None = None,
            store_file: Path | None = None) -> dict:
    """Confirma una propuesta. AQUI se materializa el snapshot.

    "Aquí" es la palabra que importa: el conjunto objetivo se resuelve y se
    congela en el momento de la firma, no al leerlo. Guardar `"ALL"` como
    comodín abierto y resolverlo más tarde es exactamente lo que dejó a
    Part 211 fuera de una D1 que decía cubrirlo todo.
    """
    _require_fresh(state_hash, store_file=store_file)
    return _closing_record(
        instance_id, decision="APPROVE", decision_type="ORIGINAL",
        by_id=approved_by_id, by_name=approved_by_display_name,
        reason=reason, field="approved_by_id", store_file=store_file)


def reject(instance_id: str, *, rejected_by_id: str,
           rejected_by_display_name: str | None = None, reason: str = "",
           state_hash: str | None = None,
           store_file: Path | None = None) -> dict:
    """Rechaza una propuesta. La propuesta NO se borra.

    `decision="REJECT"` no otorga cobertura: hasta G1.15 sí lo hacía -- el
    resolver miraba `decision_type` y no `decision`, así que un rechazo
    firmado concedía justo lo que rechazaba. Ver `GRANTING_DECISIONS`.
    """
    if not (reason or "").strip():
        raise store.DecisionValidationError(
            "un rechazo exige motivo: rechazar sin decir por que no es gobernanza")
    _require_fresh(state_hash, store_file=store_file)
    return _closing_record(
        instance_id, decision="REJECT", decision_type="ORIGINAL",
        by_id=rejected_by_id, by_name=rejected_by_display_name,
        reason=reason, field="rejected_by_id", store_file=store_file)


def return_to_proposer(instance_id: str, *, returned_by_id: str,
                       returned_by_display_name: str | None = None,
                       comment: str = "", state_hash: str | None = None,
                       store_file: Path | None = None) -> dict:
    """Devuelve la propuesta a quien la hizo, con comentario.

    `DEFER` y no `REJECT`: devolver para ajustes no es negar. Tampoco otorga
    nada -- solo `APPROVE` y `PARTIAL` otorgan.
    """
    if not (comment or "").strip():
        raise store.DecisionValidationError(
            "devolver exige comentario: sin el, el proponente no sabe que ajustar")
    _require_fresh(state_hash, store_file=store_file)
    return _closing_record(
        instance_id, decision="DEFER", decision_type="ORIGINAL",
        by_id=returned_by_id, by_name=returned_by_display_name,
        reason=comment, field="returned_by_id", store_file=store_file)
