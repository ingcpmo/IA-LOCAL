#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
LOG_DIR="${PROJECT_ROOT}/logs"
REPORT_FILE="${LOG_DIR}/phase5-$(date +%Y%m%d-%H%M%S).log"
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

wait_cmd() {
  local description="$1"
  local attempts="$2"
  local sleep_seconds="$3"
  shift 3
  local n
  for n in $(seq 1 "${attempts}"); do
    if "$@" >/dev/null 2>&1; then
      pass "${description}"
      return 0
    fi
    sleep "${sleep_seconds}"
  done
  fail "${description} no alcanzo estado esperado"
}

main() {
  log "ARIA Phase 5"
  log "Fecha: $(date -Iseconds)"
  log "Project root: ${PROJECT_ROOT}"

  [[ -f "${PROJECT_ROOT}/docker-compose.local.yml" ]] || fail "Falta docker-compose.local.yml"
  detect_compose
  pass "Compose detectado"

  info "Levantando stack requerido para Asterisk"
  compose up -d postgres redis ollama vosk kokoro-tts ai-engine orchestrator asterisk >> "${REPORT_FILE}" 2>&1 || fail "No fue posible iniciar stack de Fase 5"

  wait_cmd "PostgreSQL listo" 24 5 docker exec aria-postgres pg_isready -U "${DB_USER:-aria}"
  wait_cmd "Redis listo" 24 5 bash -lc '[[ "$(docker exec aria-redis redis-cli ping 2>/dev/null || true)" == "PONG" ]]'
  wait_cmd "AI Engine /health OK" 30 5 curl -sf http://localhost:8001/health
  wait_cmd "Orchestrator /health OK" 30 5 curl -sf http://localhost:8000/health
  wait_cmd "Asterisk CLI responde" 30 5 docker exec aria-asterisk asterisk -rx "core show version"

  info "Verificando uptime de Asterisk"
  docker exec aria-asterisk asterisk -rx "core show uptime" | tee -a "${REPORT_FILE}" || fail "Asterisk uptime no disponible"

  info "Verificando PJSIP transports"
  docker exec aria-asterisk asterisk -rx "pjsip show transports" | tee -a "${REPORT_FILE}" || fail "PJSIP transports no disponible"
  pass "PJSIP transports OK"

  info "Verificando queue ai-campaign"
  if docker exec aria-asterisk asterisk -rx "queue show ai-campaign" >> "${REPORT_FILE}" 2>&1; then
    pass "Queue ai-campaign visible"
  else
    warn "Queue ai-campaign no visible aun; no bloquea Fase 5"
  fi

  info "Verificando estado ARI"
  docker exec aria-asterisk asterisk -rx "ari show status" | tee -a "${REPORT_FILE}" || fail "ARI no disponible desde CLI"
  pass "ARI CLI OK"

  info "Verificando endpoint HTTP de ARI"
  if curl -sf --max-time 5 http://localhost:8088/ari/api-docs/resources.json >/dev/null 2>&1; then
    pass "ARI HTTP accesible"
  else
    warn "ARI HTTP no respondio a /ari/api-docs/resources.json; revisar auth/http.conf si es necesario"
  fi

  pass "Fase 5 completada"
  info "Reporte: ${REPORT_FILE}"
}

main "$@"
