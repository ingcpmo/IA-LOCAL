#!/usr/bin/env python3
"""G3 — reverificacion de las fuentes regulatorias gobernadas.

El checkpoint humano de G3 dice: *"Cesar lanza la reverificacion con su nombre y
revisa el resultado"*. `check_all_governed_sources()` existia desde la Fase 1,
pero no habia por donde lanzarla: ni endpoint, ni boton, ni script. Una accion
que un humano tiene que ejecutar y no tiene superficie es una accion que no
ocurre — el mismo agujero que dejo el panel G7 inalcanzable.

QUE HACE, Y QUE NO
------------------
Verifica cada fuente del registry contra su copia canonica local: si responde,
si el contenido sigue coincidiendo y si esta AUTORIZADA por una decision humana
D1 (puerta C-1, `resolve()` es la guardia autoritativa dentro de `check_source`).

**NO cambia el estado de ninguna fuente.** Reverificar no promueve nada: el
lifecycle sale de la cobertura de decision, no de este script. Lo que produce es
evidencia fechada en `source_currency_log.jsonl` (append-only) y UN evento de
auditoria agregado.

**Hace peticiones de red REALES** a los sitios reguladores, con un intervalo
anti-rafaga entre fuentes autorizadas. Por eso `--dry-run` existe y por eso el
modo real exige un nombre propio: la huella queda en el log y en la cadena.

USO
---
    python3 factory/scripts/ops/reverify_governed_sources.py --dry-run
    python3 factory/scripts/ops/reverify_governed_sources.py --run-by "Cesar ..."

`--run-by` se valida con la misma funcion que el resto de la fabrica: un nombre
generico ("system", "admin", "human") se rechaza. Quien lanza una verificacion
regulatoria consta con su nombre.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from factory.core import decision_scope_resolver as _resolver  # noqa: E402
from factory.regulatory import source_currency_checker as checker  # noqa: E402
from factory.regulatory.requirement_catalog import (  # noqa: E402
    requirement_catalog_loader as catalog,
)

FAMILIA = checker.DECISION_FAMILY


def _fuentes() -> list[dict]:
    return catalog.load_source_registry()["sources"]


def _preflight(fuentes: list[dict]) -> list[tuple[str, bool]]:
    """Que dira la puerta C-1 de cada fuente, ANTES de tocar la red.

    Se imprime siempre —tambien en la corrida real— porque una fuente denegada
    no genera trafico y su linea en el log dice algo muy distinto de un fallo de
    red. Verlo antes evita leer el resultado al reves.
    """
    return [(f["source_id"],
             _resolver.resolve(FAMILIA, f["source_id"]).authorized)
            for f in _fuentes()]


def _imprime_preflight(estado: list[tuple[str, bool]]) -> int:
    print("PUERTA C-1 — autorizacion por decision humana (familia D1)")
    for sid, ok in estado:
        print(f"  {'AUTORIZADA' if ok else 'DENEGADA  '}  {sid}")
    denegadas = [s for s, ok in estado if not ok]
    if denegadas:
        print(f"\n  {len(denegadas)} fuente(s) sin cobertura: se registraran en el "
              "log como intento denegado, sin generar trafico.")
    return len(denegadas)


def _imprime_resultados(resultados: list[dict]) -> int:
    print("\nRESULTADO")
    problemas = 0
    for r in resultados:
        if not r.get("authorized_by_decision"):
            estado, detalle = "DENEGADA", "sin cobertura de decision humana"
        elif not r.get("reachable"):
            estado, detalle = "NO ALCANZABLE", str(r.get("error") or "")[:70]
            problemas += 1
        elif r.get("comparable") is False:
            estado = "NO COMPARABLE"
            detalle = str(r.get("note") or "")[:70]
        elif not r.get("content_matches_governed_copy"):
            estado = "CAMBIADA"
            detalle = "el contenido ya NO coincide con la copia canonica local"
            problemas += 1
        else:
            estado, detalle = "COINCIDE", "contenido identico a la copia gobernada"
        print(f"  {estado:<14} {r['source_id']:<32} {detalle}")

    print(f"\n  {len(resultados)} verificadas · {problemas} requieren juicio humano")
    print("\n  Reverificar NO promueve ningun estado: ninguna fuente pasa a "
          "VERIFIED por esta corrida.")
    print("  Lo que cambia el estado es una decision humana, no este script.")
    return problemas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-by", help="nombre real de quien lanza la verificacion")
    ap.add_argument("--dry-run", action="store_true",
                    help="solo la puerta C-1; no toca la red ni escribe nada")
    args = ap.parse_args(argv)

    fuentes = _fuentes()
    print(f"G3 — reverificacion de {len(fuentes)} fuentes gobernadas\n")
    _imprime_preflight(_preflight(fuentes))

    if args.dry_run:
        print("\n--dry-run: no se ha hecho ninguna peticion ni se ha escrito nada.")
        print("Para la corrida real:  --run-by \"<tu nombre>\"")
        return 0

    if not args.run_by:
        print("\nFALTA --run-by. Una verificacion regulatoria consta con el nombre "
              "de quien la lanza;\nno hay un valor por defecto que sea honesto.",
              file=sys.stderr)
        return 2

    from factory.services import test_console_service as console
    try:
        nombre = console.validate_run_by(args.run_by)
    except Exception as e:  # HTTPException fuera de HTTP
        print(f"\nrun_by rechazado: {getattr(e, 'detail', e)}", file=sys.stderr)
        return 2

    print(f"\nLanzando la verificacion real como {nombre!r} "
          "(peticiones de red, con intervalo anti-rafaga)...")
    resultados = checker.check_all_governed_sources(nombre, fuentes)
    problemas = _imprime_resultados(resultados)

    print(f"\nEvidencia: {checker.paths.SOURCE_CURRENCY_LOG_FILE} (append-only)")
    print("Auditoria: 1 evento agregado 'regulatory_source_currency_checked'.")
    # Los problemas NO son fallo del script: son el hallazgo que se buscaba.
    # Devolver != 0 los convertiria en un error de ejecucion y alguien acabaria
    # silenciando el comando en vez de leer el resultado.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
