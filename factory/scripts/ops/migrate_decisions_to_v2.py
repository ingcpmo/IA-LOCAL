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


def is_stale(store_file: Path | None = None, **kwargs) -> dict:
    """Compara el almacen con la proyeccion ACTUAL de los almacenes legacy.

    Existe porque la migracion es un disparo unico y los almacenes legacy
    siguen vivos: una escritura legacy posterior deja el v2 desincronizado y
    nada lo notaba. Read-only.
    """
    target = store_file or store.STORE_FILE
    projected = serialize(adapter.project_all(**kwargs))
    actual = target.read_text(encoding="utf-8") if target.is_file() else ""
    return {
        "store_exists": target.is_file(),
        "stale": actual != projected,
        "records_in_store": len(store.read_all(target)) if target.is_file() else 0,
        "records_projected": len(projected.splitlines()),
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


def run(apply: bool = False, *, force: bool = False,
        out_file: Path | None = None,
        legacy_a: Path | None = None, legacy_b: Path | None = None,
        registry_file: Path | None = None, emit_audit: bool = True) -> dict:
    src_a = legacy_a or adapter.LEGACY_A_FILE
    src_b = legacy_b or adapter.LEGACY_B_FILE
    target = out_file or store.STORE_FILE

    before = {"a": _sha256(src_a), "b": _sha256(src_b)}

    projected = adapter.project_all(legacy_a=src_a, legacy_b=src_b,
                                    registry_file=registry_file)
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
        if nativos and not force:
            raise WouldDiscardNativeRecords(
                f"{target} contiene {len(nativos)} registro(s) NATIVO(s) que esta "
                f"migracion borraria: {nativos}. Son firmas hechas por la "
                "superficie humana, no proyecciones. Usa --force solo si de verdad "
                "quieres descartarlas."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
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
    args = ap.parse_args()

    try:
        s = run(apply=args.apply, force=args.force)
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
