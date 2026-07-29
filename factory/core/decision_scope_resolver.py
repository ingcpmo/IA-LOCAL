"""DecisionScopeResolver — W5 V2, G1.6.

UNICA superficie de lectura de decisiones de gobernanza. Mismo patron que
`path_policy`: todos preguntan aqui, nadie implementa su propia version.

Por que existe: la auditoria del 2026-07-29 (GOVERNANCE_STATE_AUDIT.md, A-2/A-3)
encontro que la fabrica sabia QUE estaba autorizado y no lo consultaba nunca.
`approved_source_ids` tenia 17 ocurrencias en 4 archivos -- escritura,
transporte, UI y tests -- y CERO lecturas para autorizar. Ninguno de los cinco
consumidores (reverificacion, packs, planner, baseline, release) importaba una
sola decision. Por eso una fuente pudo entrar al registry sin cobertura de D1 y
nada lo noto.

Si al terminar la implementacion este modulo existe pero nadie lo llama, el
trabajo no sirvio de nada: esa es la razon de
factory/tests/test_decision_resolver_no_bypass.py.

Reglas duras (DECISION_SCOPE_RESOLVER_SPEC.md §3):
  R-1  Presencia en un registry NO concede autorizacion.
  R-4  Fail-closed: indisponible o corrupto => authorized=False, SIN excepcion
       que un try/except del llamador pueda convertir en "siga adelante".
  R-5  Read-only absoluto: no escribe auditoria, no muta, no cachea en disco.
  R-6  No interpreta intenciones: solo pertenencia a un conjunto materializado.
  R-7  No conoce a sus consumidores: cero ramas `if caller == ...`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from factory.services import decision_store_v2 as store
from factory.services import paths

# --- CoverageBasis -----------------------------------------------------------
# authorized=True SOLO para los dos primeros. Todo lo demas es False.
HUMAN_CONFIRMED_EXPLICIT = "HUMAN_CONFIRMED_EXPLICIT"
HUMAN_CONFIRMED_SNAPSHOT = "HUMAN_CONFIRMED_SNAPSHOT"
RECONSTRUCTED_PENDING_FORMAL_CORRECTION = "RECONSTRUCTED_PENDING_FORMAL_CORRECTION"
NOT_COVERED = "NOT_COVERED"
REVOKED = "REVOKED"
SUPERSEDED_ONLY = "SUPERSEDED_ONLY"
PROPOSAL_ONLY = "PROPOSAL_ONLY"
RESOLVER_UNAVAILABLE = "RESOLVER_UNAVAILABLE"
FAMILY_UNKNOWN = "FAMILY_UNKNOWN"
INVALID_RECORD = "INVALID_RECORD"

_AUTHORIZING = frozenset({HUMAN_CONFIRMED_EXPLICIT, HUMAN_CONFIRMED_SNAPSHOT})


class ResolverConfigurationError(RuntimeError):
    """La UNICA excepcion que este modulo lanza: fallo de despliegue.

    decision_families.yaml ausente o invalido no es un dato malo, es un
    despliegue roto, y debe impedir el arranque en vez de degradar a
    "no autorizado" -- que seria indistinguible de una denegacion legitima.
    """


@dataclass(frozen=True)
class ScopeResolution:
    authorized: bool
    decision_family: str
    target_id: str
    covering_instances: tuple[str, ...]
    effective_snapshot_hash: str | None
    coverage_basis: str
    denial_reason: str | None
    resolved_at: str
    families_registry_hash: str | None


@dataclass(frozen=True)
class CoverageReport:
    decision_family: str
    registry_ids: tuple[str, ...]
    covered_ids: tuple[str, ...]
    uncovered_ids: tuple[str, ...]
    revoked_ids: tuple[str, ...]
    reconstructed_only_ids: tuple[str, ...]
    invalid_instances: tuple[str, ...]
    registry_hash_now: str | None
    registry_hash_at_last_decision: str | None
    registry_drift_since_decision: bool
    # Sin esto, `registry_drift_since_decision=False` es ambiguo: no distingue
    # "no hay drift" de "no se puede saber". La D1 reconstruida no tiene
    # registry_hash_at_decision -- nadie puede saber hoy el hash que tenia
    # registry.json a las 00:15:15Z del 29-jul -- y devolver False a secas
    # se leeria como tranquilidad. Es el mismo colapso de dimensiones que
    # SOURCE_LIFECYCLE_SPEC.md §2.2 prohibe.
    drift_determinable: bool
    pending_resignature_instances: tuple[str, ...]
    active_instances: tuple[str, ...]
    unavailable_reason: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deny(family: str, target_id: str, basis: str, reason: str,
          fam_hash: str | None = None) -> ScopeResolution:
    return ScopeResolution(
        authorized=False, decision_family=family, target_id=target_id,
        covering_instances=(), effective_snapshot_hash=None,
        coverage_basis=basis, denial_reason=reason,
        resolved_at=_now(), families_registry_hash=fam_hash,
    )


# ---------------------------------------------------------------------------
# Carga defensiva
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Loaded:
    ok: bool
    families: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    fam_hash: str | None = None
    error: str | None = None


def _load(store_file: Path | None) -> _Loaded:
    try:
        families = store.load_families()
        fam_hash = store.families_registry_hash()
    except store.FamiliesRegistryError as exc:
        # Despliegue roto: se propaga. Ver ResolverConfigurationError.
        raise ResolverConfigurationError(str(exc)) from exc

    path = store_file or store.STORE_FILE
    if not path.is_file():
        return _Loaded(False, families, [], fam_hash,
                       f"almacen de decisiones no encontrado: {path}")
    try:
        records = store.read_all(path)
    except Exception as exc:  # noqa: BLE001 -- fail-closed, nunca propagar
        return _Loaded(False, families, [], fam_hash,
                       f"almacen ilegible ({type(exc).__name__}: {exc})")
    return _Loaded(True, families, records, fam_hash, None)


def _partition(records: list[dict], families: dict, family: str):
    """(validos_de_la_familia, ids_de_invalidos). Un registro invalido NUNCA
    se descarta en silencio: se reporta."""
    valid, invalid = [], []
    for r in records:
        if r.get("decision_family") != family:
            continue
        res = store.validate_record(r, families=families, store_file=None)
        (valid if res.valid else invalid).append(r)
    return valid, [r.get("decision_instance_id", "<sin id>") for r in invalid]


def _effective_coverage(valid: list[dict], statuses: dict[str, str]):
    """(cubiertos, revocados, instancias_cubridoras_por_id).

    Union de los que otorgan, menos la union de los que revocan. La resta va
    despues a proposito: retirar autorizacion es la operacion segura, y por
    tanto la que domina sobre un ADDENDUM posterior del mismo id.
    """
    covered: dict[str, list[dict]] = {}
    revoked: set[str] = set()
    for r in valid:
        iid = r["decision_instance_id"]
        if statuses.get(iid) != "ACTIVE":
            continue
        if r["decision_origin"] != "human_confirmed":
            continue
        if r["decision_type"] == "REVOCATION":
            # Sin filtrar por `decision`: revocar RESTRINGE, y restringir es la
            # operacion segura. Una REVOCATION mal etiquetada debe retirar
            # igualmente.
            revoked.update(r["resolved_target_ids"])
        elif (r["decision_type"] in store.COVERING_TYPES
                and r["decision"] in store.GRANTING_DECISIONS):
            for tid in r["resolved_target_ids"]:
                covered.setdefault(tid, []).append(r)
    for tid in revoked:
        covered.pop(tid, None)
    return covered, revoked


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def resolve(decision_family: str, target_id: str, *,
            store_file: Path | None = None) -> ScopeResolution:
    """Read-only. Nunca lanza salvo ResolverConfigurationError."""
    loaded = _load(store_file)

    if decision_family not in loaded.families:
        return _deny(decision_family, target_id, FAMILY_UNKNOWN,
                     f"familia {decision_family!r} no declarada en decision_families.yaml",
                     loaded.fam_hash)

    if loaded.families[decision_family].get("never_authorizes"):
        return _deny(decision_family, target_id, NOT_COVERED,
                     f"la familia {decision_family} nunca autoriza por declaracion",
                     loaded.fam_hash)

    if not loaded.ok:
        return _deny(decision_family, target_id, RESOLVER_UNAVAILABLE,
                     loaded.error or "almacen no disponible", loaded.fam_hash)

    valid, invalid_ids = _partition(loaded.records, loaded.families, decision_family)
    statuses = store.project_status(valid)
    covered, revoked = _effective_coverage(valid, statuses)

    if target_id in revoked:
        return _deny(decision_family, target_id, REVOKED,
                     "cobertura retirada por una REVOCATION vigente", loaded.fam_hash)

    if target_id in covered:
        instances = covered[target_id]
        native = [r for r in instances if r.get("provenance") != "RECONSTRUCTED_SNAPSHOT"]
        if not native:
            return _deny(
                decision_family, target_id, RECONSTRUCTED_PENDING_FORMAL_CORRECTION,
                "solo lo cubre un snapshot RECONSTRUIDO: permite leer el historico "
                "sin ambiguedad, no autoriza. Requiere la correccion formal.",
                loaded.fam_hash,
            )
        basis = (HUMAN_CONFIRMED_SNAPSHOT
                 if any(r["selection_mode"] == "ALL_SNAPSHOT" for r in native)
                 else HUMAN_CONFIRMED_EXPLICIT)
        effective = sorted(set(covered) - revoked)
        return ScopeResolution(
            authorized=True, decision_family=decision_family, target_id=target_id,
            covering_instances=tuple(r["decision_instance_id"] for r in native),
            effective_snapshot_hash=store.compute_target_set_hash(effective),
            coverage_basis=basis, denial_reason=None,
            resolved_at=_now(), families_registry_hash=loaded.fam_hash,
        )

    # No cubierto: distinguir POR QUE, que es lo que el informe necesita.
    for r in valid:
        if (statuses.get(r["decision_instance_id"]) == "SUPERSEDED"
                and target_id in r["resolved_target_ids"]):
            return _deny(decision_family, target_id, SUPERSEDED_ONLY,
                         f"solo lo cubria {r['decision_instance_id']}, ya supersedida",
                         loaded.fam_hash)
    for r in valid:
        if (r["decision_origin"] == "agent_proposed"
                and target_id in r["resolved_target_ids"]):
            return _deny(decision_family, target_id, PROPOSAL_ONLY,
                         f"solo existe la propuesta {r['decision_instance_id']}, sin confirmar",
                         loaded.fam_hash)

    if invalid_ids:
        # Un id que solo aparecia en registros invalidos: decirlo, no fingir
        # que simplemente "no esta cubierto".
        for r in loaded.records:
            if (r.get("decision_family") == decision_family
                    and r.get("decision_instance_id") in invalid_ids
                    and target_id in (r.get("resolved_target_ids") or [])):
                return _deny(decision_family, target_id, INVALID_RECORD,
                             f"lo cubriria {r['decision_instance_id']}, pero ese registro "
                             f"viola una invariante y no autoriza", loaded.fam_hash)

    reason = "ningun registro ACTIVE human_confirmed de esta familia lo incluye"
    # Un NOT_COVERED mudo oculta el caso mas importante: la familia SI tiene
    # una decision firmada, pero se firmo sin declarar alcance. Decirlo cambia
    # la accion del lector -- no es "falta decidir", es "hay que re-firmar".
    pending = [r["decision_instance_id"] for r in valid
               if r["status"] == "INVALID_PENDING_RESIGNATURE"]
    if pending:
        reason += (f". Existe {', '.join(pending)} firmada APPROVE SIN declarar objetivo: "
                   "requiere re-firma con alcance explicito (fase G2'), no una decision nueva")
    if invalid_ids:
        reason += f" (ademas hay {len(invalid_ids)} registro(s) invalido(s): {invalid_ids})"
    return _deny(decision_family, target_id, NOT_COVERED, reason, loaded.fam_hash)


def resolve_many(decision_family: str, target_ids, *,
                 store_file: Path | None = None) -> dict[str, ScopeResolution]:
    return {tid: resolve(decision_family, tid, store_file=store_file) for tid in target_ids}


def coverage_report(decision_family: str, *,
                    store_file: Path | None = None) -> CoverageReport:
    """Cobertura de la familia frente al registry vigente. Read-only.

    `uncovered_ids` es la senal que habria cazado el alta de Part 211 el mismo
    2026-07-29 a las 02:25, en vez de en una auditoria posterior.
    """
    loaded = _load(store_file)
    empty = CoverageReport(
        decision_family=decision_family, registry_ids=(), covered_ids=(),
        uncovered_ids=(), revoked_ids=(), reconstructed_only_ids=(),
        invalid_instances=(), registry_hash_now=None,
        registry_hash_at_last_decision=None, registry_drift_since_decision=False,
        drift_determinable=False, pending_resignature_instances=(),
        active_instances=(),
    )

    if decision_family not in loaded.families:
        return CoverageReport(**{**empty.__dict__,
                                 "unavailable_reason": f"familia {decision_family!r} no declarada"})
    if not loaded.ok:
        return CoverageReport(**{**empty.__dict__, "unavailable_reason": loaded.error})

    valid, invalid_ids = _partition(loaded.records, loaded.families, decision_family)
    statuses = store.project_status(valid)
    covered, revoked = _effective_coverage(valid, statuses)

    reconstructed_only = tuple(sorted(
        tid for tid, insts in covered.items()
        if all(r.get("provenance") == "RECONSTRUCTED_SNAPSHOT" for r in insts)
    ))
    truly_covered = tuple(sorted(set(covered) - set(reconstructed_only)))

    registry_ids: tuple[str, ...] = ()
    registry_hash_now = None
    try:
        ids, registry_hash_now = store.resolve_all_snapshot(
            decision_family, families=loaded.families)
        registry_ids = tuple(ids)
    except Exception:  # noqa: BLE001 -- familias sin target_registry (D4, D5)
        registry_ids = tuple(sorted(set(covered) | revoked))

    last_hash = None
    for r in sorted(valid, key=lambda x: x["recorded_at"]):
        if r.get("registry_hash_at_decision"):
            last_hash = r["registry_hash_at_decision"]

    uncovered = tuple(sorted(
        set(registry_ids) - set(truly_covered) - set(reconstructed_only) - revoked
    ))

    return CoverageReport(
        decision_family=decision_family,
        registry_ids=registry_ids,
        covered_ids=truly_covered,
        uncovered_ids=uncovered,
        revoked_ids=tuple(sorted(revoked)),
        reconstructed_only_ids=reconstructed_only,
        invalid_instances=tuple(invalid_ids),
        registry_hash_now=registry_hash_now,
        registry_hash_at_last_decision=last_hash,
        registry_drift_since_decision=bool(
            last_hash and registry_hash_now and last_hash != registry_hash_now),
        drift_determinable=bool(last_hash and registry_hash_now),
        pending_resignature_instances=tuple(sorted(
            r["decision_instance_id"] for r in valid
            if r["status"] == "INVALID_PENDING_RESIGNATURE")),
        active_instances=tuple(
            iid for iid, st in sorted(statuses.items()) if st == "ACTIVE"),
        unavailable_reason=None,
    )


def is_authorized(decision_family: str, target_id: str, *,
                  store_file: Path | None = None) -> bool:
    """Atajo booleano. Existe para call sites que solo ramifican, pero el
    `denial_reason` de resolve() es lo que debe llegar al informe."""
    return resolve(decision_family, target_id, store_file=store_file).authorized
