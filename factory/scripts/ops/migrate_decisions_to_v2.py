#!/usr/bin/env python3
"""Migracion de los dos almacenes historicos a decisions_v2.jsonl — W5 V2, G1.5.

    python3 -m factory.scripts.ops.migrate_decisions_to_v2              # dry-run
    python3 -m factory.scripts.ops.migrate_decisions_to_v2 --apply

Garantias (V-1..V-6 de EXTENSIBLE_DECISION_MODEL_SPEC.md §8.2):
  V-1  ningun registro se pierde
  V-2  sha256 de las ENTRADAS identico antes y despues (se abren en lectura)
  V-3  los proyectados pasan las invariantes, salvo los documentados como
       INVALID_PENDING_RESIGNATURE, que se emiten y no autorizan
  V-4  cobertura(D1) == las 3 originales, y part211 NO
  V-5  determinista: dos ejecuciones => mismo sha256 de salida
  V-6  la proyeccion de vigencia se regenera identica

Rollback: `rm decisions_v2.jsonl`. Las entradas nunca se tocaron.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.core.audit_writer import write_event          # noqa: E402
from factory.services import decision_legacy_adapter as adapter  # noqa: E402
from factory.services import decision_store_v2 as store    # noqa: E402

W5_PROJECT_ID = "gmpai_document_validation"

# Provenances que la migracion produce. Un registro con otra es NATIVO: lo
# escribio la superficie humana, no esta proyeccion.
MIGRATION_PROVENANCES = frozenset({
    "MIGRATED_FROM_SYSTEM_A", "MIGRATED_FROM_SYSTEM_B", "RECONSTRUCTED_SNAPSHOT",
})


class WouldDiscardNativeRecords(RuntimeError):
    """`--apply` sobrescribe el fichero entero. Si el almacen ya contiene
    registros NATIVOS -- una firma humana por la UI, por ejemplo -- re-migrar
    los borraria sin dejar rastro.

    Hoy el almacen solo tiene proyecciones y re-migrar es inocuo, pero en cuanto
    Cesar firme la Correccion D1 deja de serlo. La guardia se pone ANTES de que
    exista el problema, no despues.
    """


def native_records(store_file: Path | None = None) -> list[str]:
    """decision_instance_id de los registros que la migracion NO produjo."""
    target = store_file or store.STORE_FILE
    if not target.is_file():
        return []
    return [r["decision_instance_id"] for r in store.read_all(target)
            if r.get("provenance") not in MIGRATION_PROVENANCES]


# Campos que registran CUANDO se grabo el registro, no QUE se decidio. Se
# excluyen de la comparacion de staleness — nunca de lo que se escribe.
#
# `families_registry_hash` es el caso que importa: es una foto del registro de
# familias en el momento de grabar, asi que anadir una familia cambia el hash
# recomputado y los 15 registros migrados aparecen desincronizados de golpe.
# Eso convertiria "anadir una familia" en una operacion que obliga a re-migrar
# el almacen, en contradiccion directa con la REGLA DURA de
# decision_families.yaml: anadir una familia no requiere tocar nada mas. La
# pregunta que responde is_stale() es "escribio alguien en un almacen legacy
# sin re-migrar", y para esa pregunta este hash es ruido.
#
# Va aqui y NO en `serialize()` a proposito: serialize() tambien PRODUCE el
# fichero durante la migracion, y anular el hash ahi borraria procedencia real
# del almacen para siempre.
VOLATILE_ON_COMPARE = ("audit_event_id", "families_registry_hash")

# Solo para registros RECONSTRUCTED_SNAPSHOT (D1 con `approved_source_ids=ALL`):
# `reconstruct_d1_snapshot()` lee el `copied_at` VIVO de sources/registry.json,
# no una foto congelada del momento de la migracion. Una re-gobernanza real
# posterior de una fuente (p.ej. `human_source_regovernance.py` cambiando el
# `copied_at` de `ecfr_21cfr_part11` el 2026-08-03) mueve retroactivamente el
# resultado de esa funcion, aunque los almacenes legacy (decisions.jsonl y el
# otro sistema) — lo unico que is_stale() existe para vigilar segun su propio
# docstring — no cambiaron ni una linea. Sin esto, CUALQUIER re-gobernanza
# futura de una fuente cubierta por D1 dejaria el guardia en rojo permanente
# por un motivo que su propio remedio sugerido (`--apply`) no puede resolver
# sin descartar los registros NATIVOS. Igual que `families_registry_hash`:
# ruido para la pregunta que responde is_stale(), nunca para lo que se
# escribe (`project_all()`/`run()` los siguen calculando y persistiendo tal
# cual, con evidencia real, en cada migracion real).
RECONSTRUCTION_VOLATILE_ON_COMPARE = (
    "resolved_target_ids", "target_set_hash", "reconstruction_evidence",
)


def _comparable(records: list[dict]) -> str:
    """Forma canonica para comparar HECHOS, ignorando artefactos de grabacion."""
    out = []
    for r in records:
        strip = set(VOLATILE_ON_COMPARE)
        if r.get("provenance") == "RECONSTRUCTED_SNAPSHOT":
            strip |= set(RECONSTRUCTION_VOLATILE_ON_COMPARE)
        out.append({k: v for k, v in r.items() if k not in strip})
    return serialize(out)


def is_stale(store_file: Path | None = None, **kwargs) -> dict:
    """Compara la parte PROYECTADA del almacen con la proyeccion actual.

    Existe porque la migracion es un disparo unico y los almacenes legacy
    siguen vivos: una escritura legacy posterior deja el v2 desincronizado y
    nada lo notaba. Read-only.

    G2.1: solo entran en la comparacion los registros con provenance de
    migracion. Antes se comparaba el TEXTO COMPLETO del fichero contra la
    proyeccion, asi que cualquier registro NATIVO -- una firma humana por la
    UI, es decir el proposito entero de v2 -- daba `stale: True` para siempre.
    La funcion ya calculaba `native_records` y no lo usaba en el veredicto. El
    efecto era el peor posible para una guardia: roja de forma permanente, y
    por tanto incapaz de senalar lo unico que existe para detectar. Ignorar los
    NATIVOS no debilita nada -- la migracion nunca los produjo, asi que
    compararlos contra su proyeccion era comparar contra algo que no existe.

    Se compara registro a registro y no texto a texto: `serialize()` normaliza
    el orden de claves y `audit_event_id`, mientras que `append_record` escribe
    con el orden de insercion. Dos ficheros con los mismos hechos y distinto
    orden de claves no estan desincronizados.
    """
    target = store_file or store.STORE_FILE
    exists = target.is_file()
    projected = adapter.project_all(occupied_from=target, **kwargs)
    actual = store.read_all(target) if exists else []
    migrated = [r for r in actual
                if r.get("provenance") in MIGRATION_PROVENANCES]
    return {
        "store_exists": exists,
        "stale": _comparable(migrated) != _comparable(projected),
        "records_in_store": len(actual),
        "records_migrated_in_store": len(migrated),
        "records_projected": len(projected),
        "native_records": native_records(target),
    }


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def serialize(records: list[dict]) -> str:
    """Salida canonica: una linea por registro, orden cronologico estable.

    `audit_event_id` se fuerza a None: la migracion emite UN solo evento
    global, no uno por registro (los eventos originales ya estan en la cadena
    y no se duplican).
    """
    return "".join(
        json.dumps({**r, "audit_event_id": None}, ensure_ascii=False, sort_keys=True) + "\n"
        for r in records
    )


def _reconcile_preserving_natives(target: Path, projected: list[dict]) -> None:
    """Anade SOLO los proyectados cuyo `decision_instance_id` todavia no
    esta en el almacen -- ninguna linea existente se toca, ni NATIVA ni ya
    MIGRADA.

    Deliberadamente NO re-serializa los ya migrados aunque `serialize()`
    produciria hoy un `families_registry_hash` distinto (el registro de
    familias vigente cambia con el tiempo; VOLATILE_ON_COMPARE ya ignora
    ese campo al comparar). Reescribirlos retroactivamente reescribiria la
    foto de una decision ya tomada -- lo unico que puede pasar aqui es
    anadir el registro que un almacen legacy vivo produjo de mas, igual que
    `append_record` anadiria cualquier registro nuevo.

    Existe porque `run(apply=True)` sin esto reescribe el fichero ENTERO
    (`serialize(projected)`) y por tanto exige elegir entre negarse
    (`WouldDiscardNativeRecords`) o `--force` (que SI descarta los
    NATIVOS) en cuanto el almacen deja de ser solo proyecciones -- exactamente
    la situacion que el propio docstring de `WouldDiscardNativeRecords`
    preveia. Esta funcion es la tercera opcion: anadir lo que falta sin
    arriesgar ni una firma humana ni reescribir una decision ya grabada.
    """
    lines = target.read_text(encoding="utf-8").splitlines()
    existing_ids = {json.loads(ln)["decision_instance_id"] for ln in lines if ln.strip()}
    new_lines = [
        json.dumps({**r, "audit_event_id": None}, ensure_ascii=False, sort_keys=True)
        for r in projected if r["decision_instance_id"] not in existing_ids
    ]
    if not new_lines:
        return
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(new_lines) + "\n")


def run(apply: bool = False, *, force: bool = False, merge_natives: bool = False,
        out_file: Path | None = None,
        legacy_a: Path | None = None, legacy_b: Path | None = None,
        registry_file: Path | None = None, emit_audit: bool = True) -> dict:
    src_a = legacy_a or adapter.LEGACY_A_FILE
    src_b = legacy_b or adapter.LEGACY_B_FILE
    target = out_file or store.STORE_FILE

    before = {"a": _sha256(src_a), "b": _sha256(src_b)}

    projected = adapter.project_all(legacy_a=src_a, legacy_b=src_b,
                                    registry_file=registry_file,
                                    occupied_from=target)
    families = store.load_families()

    # El lote se valida contra si mismo: una CORRECTION y la decision que
    # supersede se proyectan en la misma pasada y todavia no estan en disco.
    batch_ids = {r["decision_instance_id"] for r in projected}
    valid, invalid = [], []
    for rec in projected:
        res = store.validate_record(rec, families=families, known_instances=batch_ids)
        (valid if res.valid else invalid).append((rec, res))

    payload = serialize(projected)
    out_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if apply:
        nativos = native_records(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if nativos and not force:
            if not merge_natives:
                raise WouldDiscardNativeRecords(
                    f"{target} contiene {len(nativos)} registro(s) NATIVO(s) que esta "
                    f"migracion borraria: {nativos}. Son firmas hechas por la "
                    "superficie humana, no proyecciones. Usa --merge_natives para "
                    "re-sincronizar sin tocarlos, o --force solo si de verdad "
                    "quieres descartarlas."
                )
            _reconcile_preserving_natives(target, projected)
        else:
            target.write_text(payload, encoding="utf-8")

    after = {"a": _sha256(src_a), "b": _sha256(src_b)}
    inputs_untouched = before == after

    summary = {
        "applied": apply,
        "input_files": {"system_a": str(src_a), "system_b": str(src_b)},
        "input_sha256_before": before,
        "input_sha256_after": after,
        "inputs_untouched": inputs_untouched,
        "records_in": len(adapter._read_jsonl(src_a)) + len(adapter._read_jsonl(src_b)),
        "records_projected": len(projected),
        "records_valid": len(valid),
        "records_invalid": len(invalid),
        "invalid_detail": [
            {"decision_instance_id": r["decision_instance_id"],
             "violations": list(res.violations)}
            for r, res in invalid
        ],
        "pending_resignature": [
            r["decision_instance_id"] for r in projected
            if r["status"] == "INVALID_PENDING_RESIGNATURE"
        ],
        "legacy_unmapped": [
            r["decision_instance_id"] for r in projected
            if r["decision_family"] == "LEGACY_UNMAPPED"
        ],
        "output_file": str(target),
        "output_sha256": out_hash,
    }

    if apply and emit_audit:
        write_event("layer9_decision_store_migrated", W5_PROJECT_ID, {
            "source_files": [str(src_a), str(src_b)],
            "source_sha256": before,
            "records_migrated": len(projected),
            "records_invalid_pending_resignature": len(summary["pending_resignature"]),
            "records_legacy_unmapped": len(summary["legacy_unmapped"]),
            "output_sha256": out_hash,
            "inputs_untouched": inputs_untouched,
            "side_effects_applied": False,
        })

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="escribe decisions_v2.jsonl (por defecto: dry-run)")
    ap.add_argument("--force", action="store_true",
                    help="sobrescribe aunque haya registros NATIVOS (los DESCARTA)")
    ap.add_argument("--merge-natives", action="store_true",
                    help="re-sincroniza solo la parte migrada, preservando los "
                         "registros NATIVOS byte a byte (ni --force ni negarse)")
    args = ap.parse_args()

    try:
        s = run(apply=args.apply, force=args.force, merge_natives=args.merge_natives)
    except WouldDiscardNativeRecords as exc:
        print(f"ABORTADA: {exc}")
        return 2

    print(f"{'APLICADA' if s['applied'] else 'DRY-RUN (nada escrito)'}")
    print(f"  entrada            : {s['records_in']} registros")
    print(f"  proyectados        : {s['records_projected']}")
    print(f"  validos            : {s['records_valid']}")
    print(f"  invalidos          : {s['records_invalid']}")
    print(f"  entradas intactas  : {s['inputs_untouched']}")
    print(f"  sha256 de salida   : {s['output_sha256']}")
    if s["pending_resignature"]:
        print(f"\n  PENDIENTES DE RE-FIRMA (fase G2') — no autorizan nada:")
        for iid in s["pending_resignature"]:
            print(f"    - {iid}")
    if s["legacy_unmapped"]:
        print(f"\n  LEGACY_UNMAPPED (legibles, nunca autorizan):")
        for iid in s["legacy_unmapped"]:
            print(f"    - {iid}")
    if s["invalid_detail"]:
        print(f"\n  VIOLACIONES DE INVARIANTE:")
        for d in s["invalid_detail"]:
            print(f"    - {d['decision_instance_id']}")
            for v in d["violations"]:
                print(f"        {v}")
    return 0 if s["inputs_untouched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
