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
from datetime import datetime, timedelta, timezone
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


class MissingStateTokenError(ValueError):
    """422 -- el POST no trae ningún token de estado.

    Se separa de `StaleStateError` porque son fallos distintos y colapsarlos
    engañó a un humano durante toda una sesión: la UI recibía
    "409 falta state_hash" y el 409 decía "recarga y revisa", cuando recargar
    no arreglaba nada -- el campo no viajaba. Un campo ausente es un contrato
    incumplido (422); un campo presente y viejo es un conflicto (409).
    """


# Vida de una propuesta sin confirmar. Pasado el plazo deja de ser firmable:
# una propuesta de hace semanas describe un estado que su firmante ya no está
# viendo, y firmarla es firmar a ciegas con apariencia de trámite.
PROPOSAL_TTL_HOURS = 24

PROPOSAL_PROPOSED = "PROPOSED"
PROPOSAL_CONFIRMED = "CONFIRMED"
PROPOSAL_ABANDONED = "ABANDONED"
PROPOSAL_EXPIRED = "EXPIRED"

# Marca de abandono. Va en `payload` y no en `status` porque el almacén es
# append-only: el estado de una propuesta NO se edita, se deriva de los
# registros que la cierran. Cambiar el `status` de la línea original exigiría
# reescribirla, que es justo lo que Part 11 prohíbe.
ABANDON_MARKER = "proposal_abandoned"


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


def family_state_hash(family: str, *, store_file: Path | None = None) -> str:
    """Huella de lo que afecta A UNA FAMILIA. Alcance quirúrgico del control.

    `compute_state_hash` resume TODO: el almacén completo, las cinco familias y
    la cadena de auditoría entera. Con eso, aprobar un pack de D2 -- o cualquier
    evento de auditoría de cualquier proyecto -- invalidaba una firma de D1 que
    seguía siendo perfectamente válida. En una fábrica con varias superficies
    escribiendo, eso convierte el control optimista en una lotería: el firmante
    pierde por hechos que no le conciernen ni cambian lo que está firmando.

    Aquí entran solo los registros DE la familia, su registry objetivo y el
    registro de familias. NO entra la cadena de auditoría global: crece con
    cualquier lectura auditada de cualquier parte del sistema, así que meterla
    hacía el hash volátil por motivos ajenos a la decisión.
    """
    parts: list[str] = [f"family:{family}"]

    propios = [r for r in store.read_all(store_file)
               if r.get("decision_family") == family]
    parts.append(hashlib.sha256(
        json.dumps(propios, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")).hexdigest())

    try:
        parts.append(store.families_registry_hash())
    except Exception:  # noqa: BLE001 -- despliegue roto: entra como marca
        parts.append("FAMILIES_UNAVAILABLE")

    try:
        _ids, registry_hash = store.resolve_all_snapshot(family)
        parts.append(f"registry:{registry_hash}")
    except Exception:  # noqa: BLE001 -- familias sin target_registry
        parts.append("registry:N/A")

    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def active_instance_of(family: str, *, store_file: Path | None = None) -> str | None:
    """Instancia vigente y FIRMADA de la familia, o None.

    Es el segundo control y no es redundante con el hash: dice explícitamente
    QUÉ se está corrigiendo. Un cliente que propone corregir la D1-2026-002 y
    firma cuando la vigente ya es otra está corrigiendo algo que dejó de existir
    -- y el mensaje de error puede decirlo con nombres, no con dos hashes que
    nadie puede comparar a mano.
    """
    activas = get_coverage(family, store_file=store_file).get(
        "confirmed_active_instances") or []
    return activas[-1] if activas else None


def _require_fresh(state_hash: str | None, *, store_file: Path | None = None,
                   hash_family: str | None = None,
                   family: str | None = None,
                   expected_active_instance_id: str | None = None) -> None:
    """Control optimista. Ausencia => 422; presente y viejo => 409.

    `hash_family` es el ÁMBITO del hash: con familia se compara el de esa
    familia (recomendado), sin ella el global, que se conserva para los clientes
    que aún lo mandan. `family` es la familia de la propuesta y solo sirve para
    el segundo control; son parámetros distintos a propósito, porque un cliente
    antiguo manda un hash global sobre una propuesta que sí tiene familia y las
    dos comprobaciones deben poder aplicarse por separado.
    """
    if state_hash is None:
        # Contrato incumplido, NO conflicto: recargar no añade un campo que el
        # cliente nunca envió, y decirle "recarga y revisa" lo manda a perseguir
        # un fantasma. Esto costó una sesión entera de diagnóstico.
        raise MissingStateTokenError(
            "falta `state_hash`/`family_state_hash`: el POST de firma debe "
            "reenviar el token que devolvió /propose. No es un conflicto de "
            "estado: el campo no viajaba en la peticion.")

    actual = (family_state_hash(hash_family, store_file=store_file) if hash_family
              else compute_state_hash(store_file=store_file))
    if state_hash != actual:
        ambito = f"de la familia {hash_family}" if hash_family else "global"
        raise StaleStateError(
            f"state_hash obsoleto {ambito} (leido {state_hash[:12]}…, actual "
            f"{actual[:12]}…): el estado cambio entre la lectura y la firma. "
            "Recarga y revisa."
        )

    if expected_active_instance_id is not None and family is not None:
        vigente = active_instance_of(family, store_file=store_file)
        if vigente != expected_active_instance_id:
            raise StaleStateError(
                f"la decision vigente de {family} ya no es "
                f"{expected_active_instance_id!r} sino {vigente!r}: la propuesta "
                "se construyo sobre una vigencia que cambio. Recarga y revisa.")


# ---------------------------------------------------------------------------
# Ciclo de vida de una propuesta -- DERIVADO, nunca editado (append-only)
# ---------------------------------------------------------------------------

def _expired(record: dict, *, now: datetime | None = None) -> bool:
    ahora = now or datetime.now(timezone.utc)
    try:
        nacida = datetime.fromisoformat(record["recorded_at"])
    except (KeyError, ValueError):
        return False
    return (ahora - nacida) > timedelta(hours=PROPOSAL_TTL_HOURS)


def proposal_state(instance_id: str, *, store_file: Path | None = None,
                   records: list[dict] | None = None,
                   now: datetime | None = None) -> str:
    """Estado de una propuesta, DERIVADO de los registros que la cierran.

    No se almacena: el almacén es append-only y `status` no se puede reescribir.
    Derivarlo tiene además la propiedad que importa para una auditoría -- el
    estado es siempre reproducible desde los hechos, no un campo que alguien
    pudo dejar desactualizado.
    """
    recs = records if records is not None else store.read_all(store_file)
    prop = _find(instance_id, recs)
    if prop.get("decision_origin") != "agent_proposed":
        return PROPOSAL_CONFIRMED   # ya nació firmada: no es una propuesta

    cierres = [r for r in recs if r.get("confirms_instance_id") == instance_id]
    for c in cierres:
        if (c.get("payload") or {}).get(ABANDON_MARKER):
            return PROPOSAL_ABANDONED
    if any(c["decision"] == "APPROVE" for c in cierres):
        return PROPOSAL_CONFIRMED
    if cierres:
        # Rechazada o devuelta: cerrada, y desde luego no firmable.
        return PROPOSAL_ABANDONED
    return PROPOSAL_EXPIRED if _expired(prop, now=now) else PROPOSAL_PROPOSED


def list_proposals(family: str | None = None, *,
                   store_file: Path | None = None) -> list[dict]:
    """Propuestas con su estado derivado. Read-only.

    Existe para que una propuesta huérfana sea VISIBLE como huérfana. Las 46 de
    D1 aparecían indistinguibles de decisiones en la lista de `active_instances`
    porque su `status` es ACTIVE -- que en el esquema significa "no superseded",
    no "vigente como decisión".
    """
    recs = store.read_all(store_file)
    salida = []
    for r in recs:
        if r.get("decision_origin") != "agent_proposed":
            continue
        if family and r.get("decision_family") != family:
            continue
        salida.append({
            "decision_instance_id": r["decision_instance_id"],
            "decision_family": r["decision_family"],
            "decision_type": r["decision_type"],
            "target_set_hash": r["target_set_hash"],
            "proposed_by_id": r.get("proposed_by_id"),
            "recorded_at": r["recorded_at"],
            "proposal_state": proposal_state(r["decision_instance_id"], records=recs),
            "grants_coverage": False,
        })
    return salida


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
            "active_instances": list(report.active_instances),
            "confirmed_active_instances": list(report.confirmed_active_instances)}


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
        # El motivo dice QUE falta, medido. Decia "G2: ninguna fuente esta
        # autorizada todavia", y tras la Correccion D1 eso era falso —3 de 4
        # autorizadas— justo en la pantalla que Cesar usa para decidir. Un
        # mensaje que afirma menos de lo que hay invita a re-firmar lo ya
        # firmado, y es plausiblemente lo que produjo la tercera firma.
        gate("G3", "Reverificacion de fuentes", False,
             [] if g2_done else [
                 "G2: falta cobertura humana de " + ", ".join(
                     sorted(set(d1_uncovered) | set(d1_reconstructed)))
                 + (f" ({len(d1_uncovered)} sin cubrir"
                    f"{f', {len(d1_reconstructed)} solo reconstruida(s)' if d1_reconstructed else ''})")
             ]),
        gate("G4", "Versionado de artefactos", False,
             [] if artifacts.get("records_in_store") else
             ["bootstrap de artifact_versions.jsonl sin ejecutar"]),
        gate("G5", "D2-A: aprobacion de Evidence Packs", False,
             ["G3: la vigencia de las fuentes no esta verificada"] if not g2_done
             else (["packs sin cobertura D2"] if d2_uncovered else [])),
        gate("G6", "Matriz de aplicabilidad", False, []),
        # G7 se CIERRA cuando no queda ningun fork sin respaldo, y esta LISTO
        # cuando la prevencion esta completa: lo unico que falta entonces es la
        # decision humana que el panel existe para registrar.
        #
        # Decia `blocked_by: "fork sin excepcion firmada"`, y eso era un bloqueo
        # circular con consecuencia real: `panelCard` deshabilita "Abrir panel"
        # en todo gate BLOQUEADO, asi que la unica superficie para firmar la
        # excepcion quedaba detras de un boton que la propia falta de firma
        # apagaba. La tarjeta se veia en el indice y no se podia abrir.
        #
        # "Falta tu firma" NO es una precondicion: es el trabajo pendiente, igual
        # que en G2 —que por eso figura LISTO y no BLOQUEADO con "falta firmar la
        # Correccion D1"—. La precondicion de verdad es la prevencion: aceptar
        # una excepcion cuya prevencion no esta implementada es aceptar que vuelva
        # a pasar (spec §7).
        gate("G7", "Excepcion de auditoria", not forks_sin_aceptar,
             [] if _audit.preventive_measures_complete() else
             ["medidas preventivas de §7 incompletas: aceptar una excepcion sin "
              "prevencion es aceptar que vuelva a pasar"]),
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
    audit = _audit.verify_chain(decision_store_file=store_file)
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
        # G7: el estado de las 5 medidas preventivas viaja DERIVADO del backend.
        # Gobierna el boton "Aceptar" del panel de excepcion, y por eso no puede
        # ser una lista de literales que alguien flipee a mano en el JS.
        "preventive_measures": _audit.preventive_measures(),
        "preventive_measures_complete": _audit.preventive_measures_complete(),
        "critical_path": _critical_path(coverage, audit, artifacts),
        # U-5: la leyenda viaja con los datos, no solo en el HTML. Un cliente
        # que solo consuma la API tiene que ver la misma advertencia.
        "notice": ("Registrar una decision NO ejecuta sus efectos: no reverifica "
                   "fuentes, no lanza corridas y no promueve ningun estado."),
        "state_hash": compute_state_hash(store_file=store_file),
        # Por familia, para que un POST pueda reenviar el ámbito CORRECTO. Sin
        # esto el cliente solo tenía el global y el servidor lo comparaba contra
        # el de familia: dos ámbitos distintos, 409 inmediato.
        "family_state_hashes": {f: family_state_hash(f, store_file=store_file)
                                for f in GOVERNED_FAMILIES},
        "active_instances": {f: active_instance_of(f, store_file=store_file)
                             for f in GOVERNED_FAMILIES},
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
            state_hash: str | None = None,
            family_state_hash: str | None = None,
            store_file: Path | None = None) -> dict:
    """Registra una PROPUESTA (`agent_proposed`). No autoriza nada.

    El resolver solo cuenta `human_confirmed`, así que una propuesta es
    exactamente eso: visible, auditada y sin efecto. Es la mitad del ciclo que
    el Sistema A tenía y el B no.

    `proposed_by_id` se valida con `validate_actor`, no con
    `validate_identity`: quien propone puede ser un agente, y exigirle nombre
    humano produciría un campo falso o una suplantación. Lo que impide que sea
    un bypass es que una propuesta no otorga cobertura.

    `state_hash` es OPCIONAL aquí y OBLIGATORIO en `confirm`, y esa asimetría
    es el punto: proponer no otorga nada, así que una propuesta sobre un estado
    viejo es inocua; firmar sobre un estado viejo no lo es. Cuando el cliente
    sí lo manda -- la UI lo hace -- se valida aquí, que es donde de verdad
    sirve: es el PRIMER acto del ciclo que toca el almacén, y por tanto el
    único momento en que el hash que el humano leyó todavía describe el estado.

    G2.1: el `state_hash` devuelto NO es decorativo. Antes, la UI proponía y
    después firmaba reenviando el hash del GET previo; pero el propose acababa
    de escribir en el almacén que `compute_state_hash` resume, así que el hash
    del humano quedaba obsoleto por su propia acción y el confirm daba 409
    SIEMPRE -- sin concurrencia, sin segunda pestaña, con un solo usuario. El
    control optimista se había vuelto un bloqueo total: 32 propuestas D1
    huérfanas y cero firmas. La cadena correcta es leer -> proponer (valida lo
    leído) -> firmar (valida lo que devolvió el propose), y así ningún eslabón
    valida contra un estado que el propio ciclo invalidó.
    """
    _identity.validate_actor(proposed_by_id, field="proposed_by_id")
    # Los dos nombres tienen ALCANCES distintos y no son intercambiables:
    # `state_hash` es el global (el que devuelve GET /governance/state) y
    # `family_state_hash` el de la familia. Interpretar el global como si fuera
    # de familia produce un 409 inmediato -- pasó al introducir el control por
    # familia, y el propose empezó a rechazar el hash que la UI acababa de leer.
    if family_state_hash is not None:
        _require_fresh(family_state_hash, store_file=store_file, hash_family=family)
    elif state_hash is not None:
        _require_fresh(state_hash, store_file=store_file)

    # REUTILIZAR antes que acumular. Un doble clic, un reintento tras un 409 o
    # dos pestañas producían una propuesta NUEVA idéntica cada vez: así se
    # llegó a 46 propuestas D1 que eran un único acto repetido. Si ya existe una
    # equivalente y viva del mismo actor, se devuelve ESA.
    equivalente = _reusable_proposal(
        family, target_ids=list(target_ids), decision_type=decision_type,
        proposed_by_id=proposed_by_id, store_file=store_file)
    if equivalente is not None:
        return _with_tokens(equivalente, family, store_file=store_file, reused=True)

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
    written = store.append_record(record, store_file=store_file)
    return _with_tokens(written, family, store_file=store_file, reused=False)


def _with_tokens(record: dict, family: str, *, store_file: Path | None,
                 reused: bool) -> dict:
    """Añade a la respuesta los tokens que `confirm` va a exigir.

    Viajan FUERA del registro almacenado: son estado de sesión del ciclo de
    firma, no hechos de la decisión, y el esquema declara
    `additionalProperties: false`.

    Que los devuelva /propose y no un GET posterior es lo que hace el ciclo
    cerrable: /propose es el acto que cambia el estado, así que es el único que
    puede entregar un token que describa el estado DESPUÉS de ese cambio.
    """
    return {
        **record,
        "proposal_id": record["decision_instance_id"],
        "proposal_hash": record["target_set_hash"],
        "expected_active_instance_id": active_instance_of(
            family, store_file=store_file),
        "family_state_hash": family_state_hash(family, store_file=store_file),
        # `state_hash` conserva su significado GLOBAL. Devolver aquí el de
        # familia bajo el nombre viejo haría que un cliente antiguo comparara
        # dos ámbitos distintos y viera un conflicto donde no lo hay.
        "state_hash": compute_state_hash(store_file=store_file),
        "proposal_state": proposal_state(record["decision_instance_id"],
                                         store_file=store_file),
        "reused_existing_proposal": reused,
    }


def _reusable_proposal(family: str, *, target_ids: list[str], decision_type: str,
                       proposed_by_id: str,
                       store_file: Path | None = None) -> dict | None:
    """Propuesta viva y equivalente del mismo actor, si existe.

    Equivalente = misma familia, mismo tipo, mismo conjunto objetivo (por
    `target_set_hash`, no por el orden de la lista) y mismo proponente. Viva =
    en estado PROPOSED: una EXPIRED, ABANDONED o CONFIRMED no se reutiliza,
    porque reutilizarlas sería revivir algo que ya se cerró.
    """
    objetivo = store.compute_target_set_hash(sorted(set(target_ids)))
    recs = store.read_all(store_file)
    vivas = [
        r for r in recs
        if r.get("decision_family") == family
        and r.get("decision_origin") == "agent_proposed"
        and r.get("decision_type") == decision_type
        and r.get("target_set_hash") == objetivo
        and r.get("proposed_by_id") == proposed_by_id
        and proposal_state(r["decision_instance_id"], records=recs) == PROPOSAL_PROPOSED
    ]
    return sorted(vivas, key=lambda r: r["recorded_at"])[-1] if vivas else None


def abandon(instance_id: str, *, abandoned_by_id: str,
            abandoned_by_display_name: str | None = None, reason: str = "",
            store_file: Path | None = None) -> dict:
    """Abandona una propuesta de forma gobernada. NO la borra.

    Es la salida limpia para el residuo: una propuesta que nadie va a firmar
    deja de aparecer como firmable sin que haya que tocar su línea. El registro
    de abandono es un hecho más, con autor y motivo, y `never_authorizes` no
    aplica aquí porque un abandono no otorga nada por construcción: DEFER no
    está en `GRANTING_DECISIONS`.
    """
    if not (reason or "").strip():
        raise store.DecisionValidationError(
            "abandonar exige motivo: dejar residuo sin explicar es lo que "
            "obligo a escribir dos anotaciones de registro")
    return _closing_record(
        instance_id, decision="DEFER", decision_type="ORIGINAL",
        by_id=abandoned_by_id, by_name=abandoned_by_display_name,
        reason=reason, field="returned_by_id", store_file=store_file,
        payload={ABANDON_MARKER: True})


def _find(instance_id: str, records: list[dict]) -> dict:
    for r in records:
        if r.get("decision_instance_id") == instance_id:
            return r
    raise GovernanceNotFoundError(f"no existe la decision {instance_id!r}")


def _closing_record(instance_id: str, *, decision: str, decision_type: str | None,
                    by_id: str, by_name: str | None, reason: str,
                    field: str, store_file: Path | None,
                    payload: dict | None = None) -> dict:
    """Registro humano que cierra una propuesta. NUNCA borra la propuesta.

    El almacén es append-only y la cadena es Part 11: rechazar es añadir el
    rechazo, no hacer desaparecer lo rechazado. Quien audite tiene que poder
    ver qué se propuso y que se dijo que no.

    `decision_type=None` significa CONSERVAR el de la propuesta, y es lo que
    hace `confirm()`. Antes se fijaba a `"ORIGINAL"` mientras se heredaba el
    `amendment_sequence`, con dos consecuencias: un ADDENDUM confirmado violaba
    I-5, y **confirmar una CORRECTION producía un ORIGINAL** -- exactamente el
    mismo defecto que `project_system_b` tenía con las correcciones legacy, que
    se acababa de corregir. La forma del acto la decide la propuesta; la firma
    solo dice quién y cuándo.

    Un rechazo o una devolución SÍ son ORIGINAL y con `amendment_sequence=0`:
    no enmiendan nada, declinan. Heredar el alcance de enmienda de la propuesta
    haría que un "no" pareciera una corrección.
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

    # Una propuesta caducada no se firma. Se abandona o se propone de nuevo:
    # firmar algo de hace dias es firmar un estado que el firmante ya no ve.
    # Abandonar sí se permite -- es la salida gobernada del residuo.
    estado = proposal_state(instance_id, records=records)
    if estado == PROPOSAL_EXPIRED and not (payload or {}).get(ABANDON_MARKER):
        raise store.DecisionConflictError(
            f"{instance_id} esta EXPIRED (mas de {PROPOSAL_TTL_HOURS} h sin "
            "resolver): vuelve a proponer sobre el estado actual en vez de "
            "firmar una lectura vieja.")

    conserva = decision_type is None
    tipo = proposal["decision_type"] if conserva else decision_type
    record = store.build_record(
        decision_family=proposal["decision_family"],
        decision_type=tipo,
        selection_mode=proposal["selection_mode"],
        resolved_target_ids=proposal["resolved_target_ids"],
        decision=decision,
        decision_origin="human_confirmed",
        approved_by_id=by_id,
        approved_by_display_name=by_name or by_id,
        confirms_instance_id=instance_id,
        supersedes_instance_id=(proposal.get("supersedes_instance_id")
                               if conserva else None),
        amendment_sequence=(proposal.get("amendment_sequence", 0)
                            if conserva else 0),
        reason=reason,
        payload={**(proposal.get("payload") or {}), **(payload or {})} or None,
        store_file=store_file,
    )
    return store.append_record(record, store_file=store_file)


def _proposal_family(instance_id: str, *, store_file: Path | None) -> str | None:
    try:
        return _find(instance_id, store.read_all(store_file)).get("decision_family")
    except GovernanceNotFoundError:
        return None


def equivalent_signed_decision(family: str, *, decision_type: str,
                               target_set_hash: str,
                               store_file: Path | None = None) -> dict | None:
    """Decisión ya FIRMADA y vigente equivalente a la que se va a firmar.

    Equivalente = misma familia, mismo tipo y mismo conjunto objetivo (por
    `target_set_hash`, no por el orden de la lista). Vigente = `status ACTIVE`,
    `human_confirmed` y otorgante (`APPROVE`): un REJECT o una DEFER no impiden
    volver a intentar el acto, y una superseded ya no es la vigente.

    **Solo cuenta si nació de confirmar una propuesta** (`confirms_instance_id`).
    Ese filtro es el que mantiene la regla estrecha, y no está por conveniencia:
    sin él, cualquier decisión previa registrada por otra vía —una firma directa,
    un snapshot— convertía la siguiente firma equivalente en un no-op, y
    **silenciar una decisión real es peor que duplicarla**. Lo que se dedupe es el
    ciclo propose→confirm consigo mismo, que es exactamente donde estaba el
    agujero: `_reusable_proposal` ya lo hacía en `/propose` mirando solo
    propuestas, y esto es su mitad simétrica en `/confirm`.
    """
    vigente = None
    for r in store.read_all(store_file):
        if (r.get("decision_family") == family
                and r.get("decision_type") == decision_type
                and r.get("target_set_hash") == target_set_hash
                and r.get("decision_origin") == "human_confirmed"
                and r.get("confirms_instance_id")
                and r.get("decision") in store.GRANTING_DECISIONS
                and r.get("status") == "ACTIVE"):
            vigente = r  # la última en orden de inserción
    return vigente


def confirm(instance_id: str, *, approved_by_id: str,
            approved_by_display_name: str | None = None, reason: str = "",
            state_hash: str | None = None,
            family_state_hash: str | None = None,
            expected_active_instance_id: str | None = None,
            store_file: Path | None = None) -> dict:
    """Confirma una propuesta. AQUI se materializa el snapshot.

    "Aquí" es la palabra que importa: el conjunto objetivo se resuelve y se
    congela en el momento de la firma, no al leerlo. Guardar `"ALL"` como
    comodín abierto y resolverlo más tarde es exactamente lo que dejó a
    Part 211 fuera de una D1 que decía cubrirlo todo.

    El control es de FAMILIA, no global: se compara contra el estado de la
    familia de la propuesta, así que aprobar un pack de D2 ya no invalida una
    firma de D1 que sigue siendo válida. `family_state_hash` es el nombre
    preferido; `state_hash` se acepta como alias para los clientes que aún lo
    envían y se interpreta con el mismo alcance.
    """
    familia = _proposal_family(instance_id, store_file=store_file)
    # Se resuelve la familia ANTES de exigir el token para que una propuesta
    # inexistente dé 404 y no un 422 sobre un campo que da igual.
    if familia is None:
        raise GovernanceNotFoundError(f"no existe la decision {instance_id!r}")

    # Cada nombre con SU ámbito. `family_state_hash` es el preferido;
    # `state_hash` se sigue aceptando con su semántica global de siempre, para
    # no romper a un cliente que aún lo envíe.
    _require_fresh(
        family_state_hash if family_state_hash is not None else state_hash,
        store_file=store_file,
        hash_family=familia if family_state_hash is not None else None,
        family=familia,
        expected_active_instance_id=expected_active_instance_id)

    # IDEMPOTENCIA. El dedupe de G2.1 cubria /propose y no /confirm, y eso dejaba
    # un agujero con consecuencia regulatoria: Cesar firmo la Correccion D1 tres
    # veces (D1-2026-049/050/051) y las tres quedaron ACTIVE, cada una
    # confirmando una propuesta huerfana distinta y superseding a D1-2026-002. Un
    # solo acto humano acuñado como tres decisiones autoritativas distintas — y un
    # auditor no puede saber cual es LA decision.
    #
    # No es un 409: repetir un acto que ya esta hecho no es un conflicto, y
    # devolver error invita al tercer clic. Se devuelve la decision que YA existe,
    # marcada, sin escribir nada. El almacen es append-only: la forma de no
    # duplicar es no anexar, no borrar despues.
    # Solo sobre una propuesta VIVA Y FIRMABLE. Las guardias de `_closing_record`
    # —esta propuesta ya se resolvio (409), esta EXPIRED, esta ABANDONED— miden
    # otra cosa y tienen que seguir disparando ANTES: si alguien firma desde una
    # pagina de hace dias, lo que necesita oir es que su lectura caduco, no un
    # "ya estaba firmada" que no explica por que su papel no valia.
    # La identidad se valida ANTES del corto-circuito. Lo aprendi por el test
    # vivo: con la validacion solo dentro de `_closing_record`, una identidad
    # reservada recibia 201 "ya estaba firmada" en vez de 422, o sea el endpoint
    # respondia con estado de firma a quien no puede firmar. Que no se escriba
    # nada no lo hace inocuo: sigue siendo un control de Part 11 saltado.
    _identity.validate_identity(approved_by_id, field="approved_by_id")

    registros = store.read_all(store_file)
    propuesta = _find(instance_id, registros)
    if proposal_state(instance_id, records=registros) == PROPOSAL_PROPOSED:
        ya_firmada = equivalent_signed_decision(
            familia, decision_type=propuesta["decision_type"],
            target_set_hash=propuesta["target_set_hash"], store_file=store_file)
        if ya_firmada is not None:
            return {**ya_firmada,
                    "already_signed": True,
                    "signed_by_id": ya_firmada.get("approved_by_id"),
                    "signed_at": ya_firmada.get("recorded_at"),
                    "requested_proposal_id": instance_id}

    return {**_closing_record(
        instance_id, decision="APPROVE", decision_type=None,   # conserva el de la propuesta
        by_id=approved_by_id, by_name=approved_by_display_name,
        reason=reason, field="approved_by_id", store_file=store_file),
        "already_signed": False}


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
