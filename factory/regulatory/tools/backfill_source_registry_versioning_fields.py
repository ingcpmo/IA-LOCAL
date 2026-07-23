"""W5 V2, Fase B -- backfill de una sola vez de los campos de versionado
agregados al schema `source_registry_entry_v1` (version, effective_date,
supersedes, reverification_due) sobre las 3 fuentes ya gobernadas en
`factory/regulatory/sources/registry.json`.

Distinto de `human_source_update.py`: ese módulo es el único punto de
escritura para `official_source_url`/`sha256_original`/
`official_source_description` (cambio de IDENTIDAD de la fuente, gate
fail-closed que exige `REGULATORY_SOURCE_UNVERIFIED` real). Este backfill
NO cambia identidad, URL ni hash de ninguna fuente -- solo agrega metadatos
de versión/vigencia citados LITERALMENTE del propio texto ya gobernado
(sin descargar nada nuevo), así que no requiere el mismo gate. Aun así,
nunca inventa un valor: donde el documento no declara una fecha/edición
única, el valor es una nota explícita 'NO_DISPONIBLE (motivo)', nunca un
placeholder silencioso.

Evidencia real citada (verificada leyendo las copias canónicas ya
gobernadas en esta corrida, ver factory/regulatory/sources/derived/):

  eu_gmp_annex11: "Status of the document: revision 1" +
    "Deadline for coming into operation: 30 June 2011"
    (texto de factory/regulatory/sources/sha256/8ec11211.../OFFICIAL_EU_GMP_ANNEX11.pdf)

  mhra_gxp_di_guidance_2018: "MHRA GXP Data Integrity Guidance and
    Definitions; Revision 1: March 2018"
    (texto de factory/regulatory/sources/sha256/e05dda11.../OFFICIAL_MHRA_GXP_DI_GUIDANCE_2018.pdf)

  ecfr_21cfr_part11: eCFR es texto consolidado sin edición discreta; el
    propio archivo declara un header de gobernanza "vigente al
    2026-07-01" (fecha de copia, no de vigencia normativa) y el cuerpo
    del texto solo menciona "effective on or after August 20, 1997" en
    el contexto puntual de la excepción de firmas de 11.1(c), no como
    fecha general de todo el Part 11 -- no se generaliza esa cita puntual
    a una fecha de vigencia global.

`supersedes` y `reverification_due` quedan null en las 3: no hay versión
anterior gobernada de ninguna, y no existe todavía una política de
cadencia de reverificación aprobada por Capa 9 (backlog explícito, no un
olvido).
"""
from __future__ import annotations

import json
from pathlib import Path

REGISTRY_PATH = Path("factory/regulatory/sources/registry.json")

_BACKFILL: dict[str, dict] = {
    "ecfr_21cfr_part11": {
        "version": "NO_DISPONIBLE (eCFR es texto consolidado, sin edición discreta declarada)",
        "effective_date": (
            "NO_DISPONIBLE (eCFR es texto vivo continuamente actualizado; "
            "el header de gobernanza declara 'vigente al 2026-07-01' como "
            "fecha de copia, no de vigencia normativa; el cuerpo del texto "
            "cita 'effective on or after August 20, 1997' solo en el "
            "contexto puntual de la excepcion de firmas en 11.1(c), no "
            "como fecha general de todo el Part 11)"
        ),
        "supersedes": None,
        "reverification_due": None,
    },
    "eu_gmp_annex11": {
        "version": "revision 1",
        "effective_date": "2011-06-30",
        "supersedes": None,
        "reverification_due": None,
    },
    "mhra_gxp_di_guidance_2018": {
        "version": "Revision 1",
        "effective_date": "2018-03",
        "supersedes": None,
        "reverification_due": None,
    },
}


def backfill(registry_path: Path = REGISTRY_PATH) -> dict:
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    missing = set(_BACKFILL) - {s["source_id"] for s in data["sources"]}
    if missing:
        raise ValueError(f"source_id sin mapeo de backfill ni en registry.json: {missing}")
    unmapped = {s["source_id"] for s in data["sources"]} - set(_BACKFILL)
    if unmapped:
        raise ValueError(
            f"registry.json tiene fuentes sin entrada de backfill definida: {unmapped} "
            "-- agregar su mapeo citando evidencia real antes de continuar."
        )
    for source in data["sources"]:
        source.update(_BACKFILL[source["source_id"]])
    return data


def main() -> None:
    data = backfill()
    REGISTRY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"OK: {len(data['sources'])} fuentes actualizadas en {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
