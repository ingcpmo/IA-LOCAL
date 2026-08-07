#!/usr/bin/env bash
# factory/scripts/ops/watch_source_origin_status.sh
#
# Vigilancia PERSISTENTE (cron del sistema, no session-only) del ambar de
# origen que bloquea G3/G5/G8 -- ver docs_plan/W5V2_ARQ_RETOMAR_Y_FINALIZAR.md
# Bloque 4.1 y la memoria de project_w5_v2_regulatory_redesign (actualizacion
# 2026-08-05 (4)/(5)/(6)).
#
# `ecfr_21cfr_part11` y `ecfr_21cfr_part211` estan en
# FIRST_INGESTION_NO_PRIOR_KNOWN_HASH_TO_COMPARE en
# factory/regulatory/sources/registry.json -- eso "se resuelve con el
# tiempo, no con una correccion" (source_lifecycle.py lineas ~159-162): solo
# una segunda reingesta/regobernanza real futura de esas fuentes especificas
# puede cambiarlo. Este script NUNCA escribe nada -- solo LEE registry.json
# y, si el estado de cualquiera de las dos deja de empezar por
# "FIRST_INGESTION_NO_PRIOR_KNOWN_HASH", lo declara con un log append-only
# bien visible para que alguien lo note en la proxima sesion (no hay canal
# de notificacion push persistente disponible fuera de una sesion de Claude
# Code).
#
# Fail-closed: cualquier error de lectura/parseo se registra como ALERTA
# (mejor un falso positivo revisado a mano que un cambio real silencioso).
set -euo pipefail

FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REGISTRY="$FACTORY_DIR/regulatory/sources/registry.json"
LOG="$FACTORY_DIR/../logs/source_origin_status_watch.log"
WATCHED_SOURCES=("ecfr_21cfr_part11" "ecfr_21cfr_part211")

mkdir -p "$(dirname "$LOG")"

PYBIN="python3"
if [[ -x "$FACTORY_DIR/../.venv/bin/python3" ]]; then
    PYBIN="$FACTORY_DIR/../.venv/bin/python3"
fi

now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -f "$REGISTRY" ]]; then
    echo "$now ALERT registry.json no encontrado en $REGISTRY -- vigilancia no pudo leer nada" >> "$LOG"
    exit 0
fi

"$PYBIN" - "$REGISTRY" "$LOG" "$now" "${WATCHED_SOURCES[@]}" <<'PYEOF'
import json
import sys

registry_path, log_path, now, *watched = sys.argv[1:]

try:
    with open(registry_path, encoding="utf-8") as fh:
        data = json.load(fh)
    sources = {s.get("source_id"): s for s in data.get("sources", [])}
except Exception as exc:  # noqa: BLE001 -- fail-closed, se declara como alerta
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"{now} ALERT registry.json ilegible ({type(exc).__name__}: {exc})\n")
    raise SystemExit(0)

lines = []
for source_id in watched:
    entry = sources.get(source_id)
    if entry is None:
        lines.append(f"{now} ALERT {source_id} ya no aparece en registry.json -- revisar manualmente")
        continue
    status = str(entry.get("official_origin_status") or "")
    if not status.startswith("FIRST_INGESTION_NO_PRIOR_KNOWN_HASH"):
        lines.append(
            f"{now} ALERT {source_id}: official_origin_status cambio del ambar esperado -- "
            f"ahora es {status[:120]!r}. Revisar G3/G5/G8 y avisar a Cesar.")
    else:
        lines.append(f"{now} OK {source_id}: sigue en el ambar esperado (FIRST_INGESTION...)")

with open(log_path, "a", encoding="utf-8") as log:
    for line in lines:
        log.write(line + "\n")
PYEOF
