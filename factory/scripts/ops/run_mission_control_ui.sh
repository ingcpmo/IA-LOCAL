#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ing_cpmo"
UI_FILE="$PROJECT_ROOT/factory/ui/mission_control.html"
PORT="${1:-9090}"

if [ ! -f "$UI_FILE" ]; then
  echo "ERROR: No existe $UI_FILE"
  echo "Primero copia 09_consola_capa9_mission_control.html a factory/ui/mission_control.html"
  exit 1
fi

echo "GMP AI Factory - Mission Control UI"
echo "Archivo: $UI_FILE"
echo "Puerto:  $PORT"
echo ""
echo "Abrir en navegador:"
echo "  http://34.75.21.142:$PORT/mission_control.html"
echo ""
echo "IMPORTANTE:"
echo "- Esta UI es solo interfaz de control."
echo "- Las acciones reales pasan por la API factory en el puerto 9000."
echo "- No se guardan API keys en el navegador."
echo ""
cd "$(dirname "$UI_FILE")"
python3 -m http.server "$PORT"
