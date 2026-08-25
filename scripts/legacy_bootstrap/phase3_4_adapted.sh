#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_FILE="${LOG_DIR}/phase3-4-adaptada-$(date +%Y%m%d-%H%M%S).log"
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

main() {
  log "ARIA Phase 3+4 Adaptada (Ollama nativo)"
  log "Fecha: $(date -Iseconds)"
  log "Project root: ${PROJECT_ROOT}"

  [[ -f "${PROJECT_ROOT}/docker-compose.local.yml" ]] || fail "Falta docker-compose.local.yml"
  [[ -d "${PROJECT_ROOT}/services/kokoro-tts" ]] || fail "Falta services/kokoro-tts"

  detect_compose
  pass "Compose detectado"

  info "Verificando Ollama nativo"
  command -v ollama >/dev/null 2>&1 || fail "Ollama nativo no esta en PATH"
  ollama list >/dev/null 2>&1 || fail "Ollama nativo no responde"
  pass "Ollama nativo OK"

  info "Verificando modelo mistral"
  ollama list | grep -q "mistral" || fail "mistral no esta disponible en Ollama nativo"
  pass "Modelo mistral verificado"

  info "Descargando modelo llama3.2 en Ollama nativo"
  ollama pull llama3.2 >> "${REPORT_FILE}" 2>&1 || fail "Fallo pull de llama3.2"
  pass "Modelo llama3.2 descargado"

  info "Verificando modelos disponibles"
  ollama list | tee -a "${REPORT_FILE}"
  ollama list | grep -q "llama3.2" || fail "llama3.2 no aparece en ollama list"
  pass "Modelos IA verificados"

  info "Adaptando docker-compose para usar Ollama nativo"
  sed -i 's|OLLAMA_URL=${OLLAMA_URL:-http://ollama:11434}|OLLAMA_URL=${OLLAMA_URL:-http://host.docker.internal:11434}|g' "${PROJECT_ROOT}/docker-compose.local.yml"
  pass "Compose adaptado a Ollama nativo"

  info "Validando compose completo"
  compose config >> "${REPORT_FILE}" 2>&1 || fail "docker-compose.local.yml no valida"
  pass "Compose config OK"

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
