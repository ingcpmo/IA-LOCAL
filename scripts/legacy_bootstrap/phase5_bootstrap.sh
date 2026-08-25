#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
TEMPLATE_ROOT="${TEMPLATE_ROOT:-/home/cesar/IVR+IA/PLAN DE IMPLEMENTACION/Kimi_Agent_Plan de ejecución secuencial/aria/03-code/src}"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_FILE="${LOG_DIR}/phase5-bootstrap-$(date +%Y%m%d-%H%M%S).log"

log() { mkdir -p "${LOG_DIR}"; printf '%s\n' "$*" | tee -a "${REPORT_FILE}"; }
fail() { log "[FAIL] $*"; exit 1; }
pass() { log "[PASS] $*"; }
info() { log "[INFO] $*"; }

copy_path_if_missing() {
  local relative_path="$1"
  local source_path="${TEMPLATE_ROOT}/${relative_path}"
  local target_path="${PROJECT_ROOT}/${relative_path}"

  if [[ -e "${target_path}" ]]; then
    pass "Presente: ${relative_path}"
    return 0
  fi

  [[ -e "${source_path}" ]] || fail "No existe plantilla para ${relative_path}"
  mkdir -p "$(dirname "${target_path}")"
  cp -R "${source_path}" "${target_path}"
  pass "Copiado: ${relative_path}"
}

main() {
  log "ARIA Bootstrap Servicios Fase 5"
  log "Fecha: $(date -Iseconds)"
  log "Project root: ${PROJECT_ROOT}"
  log "Template root: ${TEMPLATE_ROOT}"

  [[ -d "${TEMPLATE_ROOT}" ]] || fail "Template root no existe"
  mkdir -p "${PROJECT_ROOT}"

  copy_path_if_missing "docker-compose.local.yml"
  copy_path_if_missing ".env.example"
  copy_path_if_missing "Makefile"
  copy_path_if_missing "infra/postgres"
  copy_path_if_missing "infra/redis"
  copy_path_if_missing "infra/nginx"
  copy_path_if_missing "scripts/health-check.sh"
  copy_path_if_missing "scripts/seed-db.sh"
  copy_path_if_missing "services/orchestrator"
  copy_path_if_missing "services/ai-engine"
  copy_path_if_missing "services/asterisk"
  copy_path_if_missing "services/celery-workers"
  copy_path_if_missing "services/dashboard"
  copy_path_if_missing "services/kokoro-tts"

  mkdir -p \
    "${PROJECT_ROOT}/recordings" \
    "${PROJECT_ROOT}/infra/nginx/ssl" \
    "${PROJECT_ROOT}/infra/postgres/backups" \
    "${PROJECT_ROOT}/logs" \
    "${PROJECT_ROOT}/data/ollama" \
    "${PROJECT_ROOT}/data/vosk"
  pass "Directorios runtime listos"

  pass "Bootstrap completado"
  info "Reporte: ${REPORT_FILE}"
}

main "$@"
