#!/usr/bin/env python3
"""Bootstrap del almacén de versiones de artefactos — W5 V2 G1.13.

Fotografía el estado observado de las cinco clases de artefacto y emite un
`version_record` inicial por cada una.

EL BOOTSTRAP FOTOGRAFIA, NO APRUEBA
-----------------------------------
Todos los registros salen con `approved_by_decision: null` y `bootstrap:
true`. No es un descuido ni un TODO: es la diferencia entre saber qué había
en disco un día concreto y afirmar que alguien lo autorizó. La guardia de
Gate 0 trata `null` como WARN, nunca como aprobación, y un artefacto con
`approved_by_decision: null` no habilita conclusiones formales.

DRY-RUN POR DEFECTO
-------------------
Sin `--apply` no se escribe nada: se imprime lo que se escribiría. Mismo
patrón que `migrate_decisions_to_v2.py`, y por la misma razón -- un script de
gobernanza que escribe por defecto es un script que alguien ejecuta "para ver
qué hace" y deja el almacén sembrado.

Es APPEND-ONLY: si el almacén ya existe, los registros nuevos se añaden al
final. Nunca se reescribe ni se deduplica; el último registro de un
`artifact_id` es el vigente, y la historia previa se conserva.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.core import artifact_version_guard as guard

BOOTSTRAP_NOTE = (
    "Registro inicial del estado observado el {date}. NO representa una "
    "aprobacion humana. Los artefactos con approved_by_decision=null no "
    "habilitan conclusiones formales."
)


def build_bootstrap_records(*, repo: Path | None = None,
                            store_file: Path | None = None) -> list[dict]:
    """Un `version_record` por artefacto SIN registro previo.

    Los que ya tienen registro se dejan en paz: rebootstrapear un artefacto
    ya versionado sobrescribiria su historia con una foto sin firma, que es
    justo lo contrario de lo que este almacen existe para conservar.
    """
    existing = guard.read_version_records(store_file)
    known = {r.get("artifact_id") for r in existing}
    note = BOOTSTRAP_NOTE.format(
        date=datetime.now(timezone.utc).date().isoformat())

    return [
        guard.build_version_record(
            state,
            previous_version=None,
            previous_sha256=None,
            approved_by_decision=None,
            bootstrap=True,
            bootstrap_note=note,
        )
        for state in guard.enumerate_artifacts(repo=repo)
        if state.artifact_id not in known
    ]


def append_records(records: list[dict], store_file: Path | None = None) -> Path:
    path = store_file or guard.STORE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="escribe de verdad; sin este flag no toca nada")
    parser.add_argument("--store", type=Path, default=None,
                        help="almacén alternativo (por defecto artifact_versions.jsonl)")
    args = parser.parse_args()

    records = build_bootstrap_records(store_file=args.store)
    by_class: dict[str, int] = {}
    for r in records:
        by_class[r["artifact"]] = by_class.get(r["artifact"], 0) + 1

    print(f"artefactos sin version_record: {len(records)}")
    for cls in guard.ARTIFACT_CLASSES:
        print(f"  {cls:22s} {by_class.get(cls, 0)}")
    print(f"  todos con approved_by_decision=null (el bootstrap no aprueba)")

    if not args.apply:
        print("\nDRY-RUN: no se ha escrito nada. Usa --apply para escribir.")
        for r in records[:3]:
            print("  " + json.dumps(r, ensure_ascii=False)[:160] + "...")
        return 0

    path = append_records(records, args.store)
    print(f"\nESCRITO: {len(records)} registros añadidos a {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
