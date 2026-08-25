#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_FILE="${LOG_DIR}/phase3-4-completa-$(date +%Y%m%d-%H%M%S).log"
PROJECT_NAME="$(basename "${PROJECT_ROOT}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"

COMPOSE_CMD=()

log() { mkdir -p "${LOG_DIR}"; printf '%s\n' "$*" | tee -a "${REPORT_FILE}"; }
fail() { log "[FAIL] $*"; exit 1; }
pass() { log "[PASS] $*"; }
info() { log "[INFO] $*"; }
warn() { log "[WARN] $*"; }

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    fail "No se encontro docker compose ni docker-compose"
  fi
}

compose() {
  (
    cd "${PROJECT_ROOT}"
    "${COMPOSE_CMD[@]}" -f docker-compose.local.yml "$@"
  )
}

wait_http() {
  local url="$1"
  local attempts="${2:-30}"
  local sleep_seconds="${3:-5}"
  local n
  for n in $(seq 1 "${attempts}"); do
    if curl -sf --max-time 5 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_seconds}"
  done
  return 1
}

main() {
  log "ARIA Phase 3+4 Completa"
  log "Fecha: $(date -Iseconds)"
  log "Project root: ${PROJECT_ROOT}"

  [[ -f "${PROJECT_ROOT}/docker-compose.local.yml" ]] || fail "Falta docker-compose.local.yml"
  [[ -d "${PROJECT_ROOT}/services/kokoro-tts" ]] || fail "Falta services/kokoro-tts"

  detect_compose
  pass "Compose detectado"

  info "Validando compose completo"
  compose config >> "${REPORT_FILE}" 2>&1 || fail "docker-compose.local.yml no valida"
  pass "Compose config OK"

  info "Iniciando Ollama para descarga de modelos"
  compose up -d ollama >> "${REPORT_FILE}" 2>&1 || fail "No fue posible iniciar ollama"
  wait_http "http://localhost:11434/api/tags" 30 5 || fail "Ollama no quedo listo"
  pass "Ollama listo"

  info "Descargando modelo mistral"
  docker exec aria-ollama ollama pull mistral >> "${REPORT_FILE}" 2>&1 || fail "Fallo pull de mistral"
  pass "Modelo mistral descargado"

  info "Descargando modelo llama3.2"
  docker exec aria-ollama ollama pull llama3.2 >> "${REPORT_FILE}" 2>&1 || fail "Fallo pull de llama3.2"
  pass "Modelo llama3.2 descargado"

  info "Verificando modelos disponibles"
  docker exec aria-ollama ollama list | tee -a "${REPORT_FILE}"
  docker exec aria-ollama ollama list | grep -q "mistral" || fail "mistral no aparece en ollama list"
  docker exec aria-ollama ollama list | grep -q "llama3.2" || fail "llama3.2 no aparece en ollama list"
  pass "Modelos IA verificados"

  info "Verificando imagen base Vosk"
  docker image inspect alphacep/kaldi-es:latest >/dev/null 2>&1 || fail "Imagen alphacep/kaldi-es:latest no existe"
  pass "Imagen base Vosk presente"

  info "Construyendo imagenes de Fase 4"
  compose build --parallel ai-engine orchestrator celery-worker dashboard asterisk kokoro-tts >> "${REPORT_FILE}" 2>&1 || fail "Fallo build de aplicaciones core"
  pass "Build paralelo completado"

  info "Verificando imagenes resultantes"
  local service
  for service in ai-engine orchestrator celery-worker dashboard asterisk kokoro-tts; do
    docker image inspect "${PROJECT_NAME}-${service}" >/dev/null 2>&1 || fail "Falta imagen ${PROJECT_NAME}-${service}"
    pass "Imagen ${PROJECT_NAME}-${service} OK"
  done

  pass "Fase 3 completa: modelos descargados"
  pass "Fase 4 completa: imagenes construidas"
  info "Reporte: ${REPORT_FILE}"
}

main "$@"
