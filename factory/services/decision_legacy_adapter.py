"""Adaptador de lectura de los dos almacenes historicos — W5 V2, G1.4.

Proyecta al schema `decision_record_v1` los registros de:

  Sistema A  factory/layer9/decisions/decisions.jsonl        (9 registros)
  Sistema B  factory/layer9/decisions/w5_human_decisions.jsonl (5 registros)

NO reescribe nada. Los ficheros de entrada se abren en modo lectura y su
sha256 debe ser identico antes y despues (verificacion V-2 de la migracion).

Tres decisiones de honestidad que conviene no deshacer:

1. `LEGACY_UNMAPPED` para las 4 decisiones del Sistema A que no son de
   gobernanza del corpus (agent_design, 2 de deploy, resolucion de
   contradicciones de FS_v1.2). Forzarlas a una familia real seria FABRICAR
   cobertura. Se proyectan legibles y no autorizantes.

2. La D1 historica se proyecta con `provenance=RECONSTRUCTED_SNAPSHOT` y su
   evidencia completa. Eso permite LEER el historico sin ambiguedad; NO
   sustituye a la Correccion D1 formal (G2). El resolver lo trata como
   `authorized=False`.

3. D2/D3/D4/D5 se firmaron sin ningun objetivo -- `approved_pack_ids` es
   opcional en record_decision() y no se envio; D3/D4/D5 ni siquiera tienen
   campo de objetivo. Se proyectan con `resolved_target_ids: []` y
   `status=INVALID_PENDING_RESIGNATURE`. Inventarles un alcance seria
   fabricar lo que un humano no firmo.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.services import decision_store_v2 as store
from factory.services import paths

LEGACY_A_FILE = paths.FACTORY_ROOT / "layer9" / "decisions" / "decisions.jsonl"
LEGACY_B_FILE = paths.FACTORY_ROOT / "layer9" / "decisions" / "w5_human_decisions.jsonl"
SOURCES_REGISTRY = paths.FACTORY_ROOT / "regulatory" / "sources" / "registry.json"

# decision -> decision del schema nuevo.
_DECISION_MAP = {
    "approve": "APPROVE",
    "reject": "REJECT",
    "defer": "DEFER",
    "conditional_approve": "PARTIAL",
    "APPROVE": "APPROVE",
    "PARTIAL": "PARTIAL",
    "REJECT": "REJECT",
}

_UNMAPPED = "LEGACY_UNMAPPED"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _family_for_action(action: str, families: dict) -> str:
    for name, spec in families.items():
        if spec.get("legacy_action") == action:
            return name
    return _UNMAPPED


def _family_for_w5_id(decision_id: str, families: dict) -> str:
    for name, spec in families.items():
        if spec.get("legacy_w5_decision_id") == decision_id:
            return name
    return _UNMAPPED


# ---------------------------------------------------------------------------
# Reconstruccion del snapshot de la D1 historica
# ---------------------------------------------------------------------------

def reconstruct_d1_snapshot(signed_at: str, *,
                            registry_file: Path | None = None) -> tuple[list[str], dict]:
    """Ids del registry cuyo `copied_at` es ANTERIOR a la firma. (ids, evidencia).

    Metodo deliberadamente simple y auditable. En el caso real el margen no es
    de segundos sino de 2 h 10 min (D1 firmada 00:15:15Z; Part 211 copiada
    02:25:06Z), asi que la deduccion no depende de precision de reloj.
    """
    path = registry_file or SOURCES_REGISTRY
    data = json.loads(path.read_text(encoding="utf-8"))
    considered, included = [], []
    for s in data.get("sources", []):
        copied = s.get("copied_at", "")
        considered.append({"source_id": s["source_id"], "copied_at": copied})
        if copied and copied < signed_at:
            included.append(s["source_id"])
    evidence = {
        "decision_signed_at": signed_at,
        "method": "ids del registry con copied_at < decision_signed_at",
        "registry_entries_considered": considered,
        "excluded_as_later": sorted(
            e["source_id"] for e in considered if e["source_id"] not in included),
        "confidence": "HIGH",
        "confidence_basis": (
            "Los copied_at son inequivocos y el margen es de horas, no de segundos. "
            "Ningun evento de auditoria registra alta o baja de fuente en el intervalo."
        ),
    }
    return sorted(included), evidence


# ---------------------------------------------------------------------------
# Proyeccion
# ---------------------------------------------------------------------------

def project_system_a(records: list[dict], families: dict, *,
                     counters: dict | None = None) -> list[dict]:
    out = []
    # `counters` puede venir compartido con `project_system_b` (ver
    # `project_all`): LEGACY_UNMAPPED es la unica familia que ambos sistemas
    # pueden producir (Sistema A via accion no mapeada, Sistema B via
    # `legacy_w5_decision_id` no mapeado) -- sin contador compartido, cada
    # funcion numera desde 001 por su cuenta y dos decisiones DISTINTAS
    # terminan con el mismo decision_instance_id (colision real detectada
    # 2026-08-23: LEGACY_UNMAPPED-2026-001 asignado tanto a un registro de
    # 2026-06-13 del Sistema A como a uno de 2026-08-13 del Sistema B).
    if counters is None:
        counters = {}
    id_map: dict[str, str] = {}

    for r in sorted(records, key=lambda x: x["timestamp"]):
        family = _family_for_action(r.get("action", ""), families)
        year = int(r["timestamp"][:4])
        key = (family, year)
        counters[key] = counters.get(key, 0) + 1
        instance_id = f"{family}-{year}-{counters[key]:03d}"
        id_map[r["decision_id"]] = instance_id

        meta = r.get("metadata") or {}
        targets = []
        if family != _UNMAPPED:
            if meta.get("source_id"):
                targets = [meta["source_id"]]
            elif meta.get("matrix_version"):
                targets = [str(meta["matrix_version"])]
        # Sin objetivo deducible con evidencia => sigue vacio, y el registro
        # queda invalido. Nunca se rellena con un valor plausible.

        origin = r.get("decision_origin", "human_confirmed")
        confirms = meta.get("confirms_decision_id")
        # `fcf933e7`/`caa2421d` rehacen el alta anterior: su propio rationale
        # dice "REHACE el alta tras corregir repo_relative()". Tipificarlas
        # como CORRECTION convierte dos hechos sueltos en uno corregido (A-7).
        is_redo = "REHACE" in (r.get("rationale") or "").upper()
        dtype = "CORRECTION" if is_redo else "ORIGINAL"

        status = "ACTIVE" if targets or family == _UNMAPPED else "INVALID_PENDING_RESIGNATURE"
        if family == _UNMAPPED:
            status = "ACTIVE"

        rec = store.build_record(
            decision_family=family,
            decision_type=dtype,
            selection_mode="EXPLICIT_LIST",
            resolved_target_ids=targets,
            decision=_DECISION_MAP.get(r.get("decision", ""), "APPROVE"),
            decision_origin=origin,
            approved_by_id=r.get("decided_by") if origin == "human_confirmed" else None,
            approved_by_display_name=r.get("decided_by") if origin == "human_confirmed" else None,
            proposed_by_id=r.get("decided_by") if origin == "agent_proposed" else None,
            confirms_instance_id=id_map.get(confirms) if confirms else None,
            supersedes_instance_id=None,
            amendment_sequence=0,
            reason=r.get("rationale", ""),
            payload={**meta, "legacy_decision_id": r["decision_id"],
                     "legacy_action": r.get("action"),
                     "legacy_project_id": r.get("project_id")},
            provenance="MIGRATED_FROM_SYSTEM_A",
            status=status,
            decision_date=r["timestamp"],
            recorded_by=r.get("recorded_by"),
            decision_instance_id=instance_id,
        )
        rec["recorded_at"] = r["timestamp"]
        if status == "INVALID_PENDING_RESIGNATURE":
            rec["invalid_reason"] = "sin resolved_target_ids deducible con evidencia"
        # CORRECTION exige supersedes_instance_id (I-6). El rehacer supersede
        # a la confirmacion humana previa de la MISMA familia.
        if dtype == "CORRECTION":
            prev = [o for o in out
                    if o["decision_family"] == family
                    and o["decision_origin"] == origin]
            if prev:
                rec["supersedes_instance_id"] = prev[-1]["decision_instance_id"]
            else:
                rec["decision_type"] = "ORIGINAL"
        out.append(rec)
    return out


def project_system_b(records: list[dict], families: dict, *,
                     registry_file: Path | None = None,
                     counters: dict | None = None) -> list[dict]:
    """Proyecta el Sistema B, incluidas sus CORRECCIONES.

    Una correccion legacy trae todo lo necesario y el adaptador lo descartaba:
    `record_type="correction"`, `supersedes_recorded_at` (apunta al original),
    `correction_reason` (el motivo, bajo OTRO nombre que `reason`) y
    `corrected_fields`. Se emitia como un segundo ORIGINAL, con tres
    consecuencias reales:

      - la relacion de supersesion se PERDIA;
      - los dos quedaban ACTIVE, asi que "que D1 es la vigente" pasaba a ser
        ambiguo en v2 mientras el almacen legacy lo sabia perfectamente;
      - al no tiparse CORRECTION, esquivaba I-6 sin que nada lo notara.

    Salio a la luz cuando Cesar corrigio la cadencia de D1 (1 -> 3 meses) por la
    UI legacy DESPUES de la migracion: el defecto era invisible mientras no
    hubiera ninguna correccion en el almacen.
    """
    out = []
    if counters is None:
        counters = {}
    # recorded_at -> instance_id, para resolver `supersedes_recorded_at`. Se
    # indexa por marca de tiempo porque es lo que el registro legacy guarda;
    # no se adivina por familia ni por posicion.
    by_recorded_at: dict[str, str] = {}
    for r in sorted(records, key=lambda x: x["recorded_at"]):
        did = r["decision_id"]
        family = _family_for_w5_id(did, families)
        year = int(r["recorded_at"][:4])
        key = (family, year)
        counters[key] = counters.get(key, 0) + 1
        instance_id = f"{family}-{year}-{counters[key]:03d}"

        targets: list[str] = []
        mode = "EXPLICIT_LIST"
        provenance = "MIGRATED_FROM_SYSTEM_B"
        evidence = None

        raw_sources = r.get("approved_source_ids")
        if family == "D1" and raw_sources is not None:
            if isinstance(raw_sources, str) and raw_sources.strip().upper() == "ALL":
                mode = "ALL_SNAPSHOT"
                provenance = "RECONSTRUCTED_SNAPSHOT"
                targets, evidence = reconstruct_d1_snapshot(
                    r["decision_date"], registry_file=registry_file)
            else:
                targets = list(raw_sources)
        elif r.get("approved_pack_ids"):
            targets = list(r["approved_pack_ids"])

        status = "ACTIVE" if targets else "INVALID_PENDING_RESIGNATURE"

        payload = {"legacy_decision_id": did, "legacy_notes": r.get("notes", "")}
        for k in ("reverification_cadence_months", "reverification_authority"):
            if k in r:
                payload[k] = r[k]

        # Una correccion legacy se tipa CORRECTION y conserva a QUIEN supersede.
        es_correccion = r.get("record_type") == "correction"
        supersedes = by_recorded_at.get(r.get("supersedes_recorded_at") or "")
        dtype = "CORRECTION" if (es_correccion and supersedes) else "ORIGINAL"
        if es_correccion:
            # El motivo vive en `correction_reason`, no en `reason`. Si el
            # original no se puede resolver se degrada a ORIGINAL en vez de
            # emitir una CORRECTION que apunta al vacio: I-6 la marcaria
            # invalida y perderiamos tambien el registro.
            payload["legacy_corrected_by"] = r.get("corrected_by")
            payload["legacy_corrected_fields"] = r.get("corrected_fields")
            if not supersedes:
                payload["correction_unresolved"] = (
                    "record_type=correction pero supersedes_recorded_at "
                    f"{r.get('supersedes_recorded_at')!r} no resuelve a ningun "
                    "registro proyectado; se conserva como ORIGINAL y se declara")

        rec = store.build_record(
            decision_family=family,
            decision_type=dtype,
            selection_mode=mode,
            resolved_target_ids=targets,
            decision=_DECISION_MAP.get(r.get("decision", ""), "APPROVE"),
            decision_origin="human_confirmed",
            approved_by_id=r.get("approved_by"),
            approved_by_display_name=r.get("approved_by"),
            amendment_sequence=0,
            reason=(r.get("correction_reason") or "") if es_correccion
                   else r.get("notes", ""),
            payload=payload,
            provenance=provenance,
            reconstruction_evidence=evidence,
            status=status,
            decision_date=r["decision_date"],
            decision_instance_id=instance_id,
            supersedes_instance_id=supersedes if dtype == "CORRECTION" else None,
        )
        rec["recorded_at"] = r["recorded_at"]
        by_recorded_at[r["recorded_at"]] = instance_id
        if status == "INVALID_PENDING_RESIGNATURE":
            rec["invalid_reason"] = (
                f"{did} se firmo APPROVE sin declarar objetivo: record_decision() no "
                "exige approved_pack_ids y D3/D4/D5 no tienen campo de objetivo. "
                "Requiere re-firma con alcance explicito (fase G2')."
            )
        out.append(rec)
    return out


def project_all(*, legacy_a: Path | None = None, legacy_b: Path | None = None,
                registry_file: Path | None = None) -> list[dict]:
    """Los registros historicos proyectados, en orden cronologico.

    `counters` se comparte entre ambas llamadas para que LEGACY_UNMAPPED
    -- la unica familia que ambos sistemas pueden producir -- numere de
    forma global y nunca colisione entre Sistema A y Sistema B. Sistema A
    se proyecta primero: sus IDs ya migrados (001..009) quedan intactos;
    Sistema B simplemente continua la secuencia.
    """
    families = store.load_families()
    counters: dict = {}
    a = project_system_a(_read_jsonl(legacy_a or LEGACY_A_FILE), families,
                        counters=counters)
    b = project_system_b(_read_jsonl(legacy_b or LEGACY_B_FILE), families,
                         registry_file=registry_file, counters=counters)
    return sorted(a + b, key=lambda r: r["recorded_at"])
