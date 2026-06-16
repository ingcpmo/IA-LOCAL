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

echo "GMP AI Factory — Mission Control UI"
echo "Archivo: $UI_FILE"
echo "Puerto:  $PORT"
echo ""
echo "Abrir en navegador:"
echo "  http://35.243.160.0:$PORT/mission_control.html"
echo ""
echo "Ruta recomendada por Factory API:"
echo "  http://35.243.160.0:9000/mission-control"
echo ""
echo "IMPORTANTE:"
echo "- Esta UI es solo interfaz de control."
echo "- Las acciones reales pasan por la API factory en puerto 9000."
echo "- No guardar API keys en navegador."
echo "- No exponer secretos."
echo ""
cd "$(dirname "$UI_FILE")"
python3 -m http.server "$PORT"
