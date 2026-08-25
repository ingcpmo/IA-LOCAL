#!/bin/bash
# Checkpoint read-only de retiro de /home/ing_cpmo/hotelbot -- programado
# por Cesar (Capa 9) tras el cutover real de ARIA (Fase 3 de
# docs_plan/PLAN_DESACOPLE_HOTELBOT_ARIA.md, 2026-08-25T22:36:06Z).
#
# 100% SOLO LECTURA. No borra, mueve, detiene ni reinicia nada. No toca
# hotelbot/, ARIA/, ni ningun contenedor. Solo lee y reporta.
#
# Uso: checkpoint_hotelbot_decommission.sh <LABEL>
#   LABEL: "checkpoint1_24h" o "checkpoint2_72h" (o "baseline" para la
#   captura inicial post-cutover)
set -uo pipefail

LABEL="${1:?uso: checkpoint_hotelbot_decommission.sh <label>}"
BASE_DIR="/home/ing_cpmo/backups/decommission_checkpoints"
BASELINE_FILE="$BASE_DIR/baseline.txt"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_MD="/home/ing_cpmo/docs_plan/DECOMMISSION_CHECKPOINT_${LABEL}_${TS}.md"
SNAPSHOT_FILE="$BASE_DIR/snapshot_${LABEL}_${TS}.txt"

mkdir -p "$BASE_DIR"

{
echo "=== SNAPSHOT $LABEL @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo
echo "--- 1. DOCKER: contenedores completos ---"
docker ps -a --format "{{.Names}}\t{{.Image}}\t{{.Status}}"
echo
echo "--- 1b. DOCKER: labels compose de cada contenedor ---"
for c in $(docker ps -a --format "{{.Names}}"); do
  docker inspect "$c" --format '{{.Name}} | project={{index .Config.Labels "com.docker.compose.project"}} | working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} | config_files={{index .Config.Labels "com.docker.compose.project.config_files"}}'
done
echo
echo "--- 1c. DOCKER: bind mounts de todos los contenedores ---"
for c in $(docker ps -a --format "{{.Names}}"); do
  docker inspect "$c" --format '{{range .Mounts}}{{if eq .Type "bind"}}'"$c"': {{.Source}} -> {{.Destination}}
{{end}}{{end}}'
done
echo
echo "--- 1d. DOCKER: networks ---"
docker network ls
echo
echo "--- 1e. DOCKER: volumes ---"
docker volume ls
echo
echo "--- 2. ARIA: origen del proyecto ---"
docker compose ls -a 2>&1
echo
echo "--- 2b. ARIA: health de servicios reales ---"
for c in aria-ai-engine aria-tts aria-orchestrator aria-celery-worker aria-ollama aria-asterisk aria-postgres-1 aria-redis-1; do
  docker inspect "$c" --format '{{.Name}}: status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}} exitcode={{.State.ExitCode}}' 2>&1
done
echo
echo "--- 3. HOST: systemd, cron, procesos, scripts referenciando hotelbot ---"
echo "systemd:"
for u in $(systemctl list-units --all --type=service --no-legend 2>/dev/null | awk '{print $1}'); do
  systemctl cat "$u" 2>/dev/null | grep -qi "hotelbot" && echo "  MATCH: $u"
done
echo "crontab:"
crontab -l 2>&1 | grep -i hotelbot || echo "  sin coincidencias"
echo "procesos:"
ps aux | grep -i hotelbot | grep -v grep || echo "  sin procesos"
echo "scripts operativos:"
grep -rl "hotelbot" /home/ing_cpmo/scripts/ /home/ing_cpmo/factory/scripts/ 2>/dev/null || echo "  sin coincidencias"
echo
echo "--- 4. FILESYSTEM/GIT: estado de hotelbot/ ---"
cd /home/ing_cpmo/hotelbot 2>/dev/null && {
  echo "git status (dentro del propio checkout):"
  git status --short 2>&1
  echo "HEAD:"
  git log --oneline -1 2>&1
} || echo "  /home/ing_cpmo/hotelbot no accesible"
echo
echo "=== FIN SNAPSHOT ==="
} > "$SNAPSHOT_FILE" 2>&1

# --- comparación contra baseline (si existe) ---
DIFF_SECTION=""
if [ -f "$BASELINE_FILE" ] && [ "$LABEL" != "baseline" ]; then
  DIFF_SECTION="$(diff "$BASELINE_FILE" "$SNAPSHOT_FILE" || true)"
fi

# --- veredicto determinístico: referencias activas a hotelbot ---
HOTELBOT_REFS=$(grep -c "/home/ing_cpmo/hotelbot" "$SNAPSHOT_FILE" || true)
HOTELBOT_REFS=${HOTELBOT_REFS:-0}

if [ "$LABEL" = "baseline" ]; then
  cp "$SNAPSHOT_FILE" "$BASELINE_FILE"
fi

{
echo "# CHECKPOINT DE RETIRO — hotelbot/ ($LABEL)"
echo "Generado automáticamente (solo lectura) — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo '```'
cat "$SNAPSHOT_FILE"
echo '```'
echo
if [ -n "$DIFF_SECTION" ]; then
  echo "## DIFERENCIA CONTRA BASELINE (post-cutover)"
  echo '```diff'
  echo "$DIFF_SECTION"
  echo '```'
else
  echo "## Sin diferencia contra baseline (o es la propia captura de baseline)."
fi
echo
echo "## Veredicto determinístico"
echo "HOTELBOT_PATH_REFERENCES_FOUND = $HOTELBOT_REFS"
echo "(cuenta líneas del snapshot que mencionan /home/ing_cpmo/hotelbot -- 0 es lo esperado si ya no participa en runtime activo. Este script NO decide SAFE_TO_DECOMMISSION_HOTELBOT -- eso requiere revisión humana de este reporte por Cesar.)"
} > "$OUT_MD"

echo "Reporte escrito en: $OUT_MD"

# --- auto-limpieza: remover esta propia entrada de crontab tras ejecutar ---
if crontab -l 2>/dev/null | grep -q "CHECKPOINT_HOTELBOT_${LABEL}"; then
  crontab -l 2>/dev/null | grep -v "CHECKPOINT_HOTELBOT_${LABEL}" | crontab -
fi
