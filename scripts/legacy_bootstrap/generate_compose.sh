#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-/home/ing_cpmo/ARIA/03-code/src}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.local.yml"

echo "[INFO] Project root: ${PROJECT_ROOT}"
mkdir -p "${PROJECT_ROOT}"

if [[ -f "${COMPOSE_FILE}" ]]; then
  cp "${COMPOSE_FILE}" "${COMPOSE_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
  echo "[WARN] Ya existia docker-compose.local.yml; se creo backup"
fi

cat > "${COMPOSE_FILE}" <<'EOF'
#===============================================================================
# ARIA - Docker Compose Local Stack
# Stack completo de desarrollo local para el asistente IA de llamadas ARIA.
# Incluye: PostgreSQL, Redis, Ollama (LLM local), Vosk (STT), Kokoro (TTS),
# Asterisk 20 LTS, AI Engine, Orchestrator, Celery Workers, Dashboard, Nginx.
#===============================================================================
services:
  postgres:
    image: postgres:15-alpine
    container_name: aria-postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${DB_USER:-aria}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-change_me}
      POSTGRES_DB: ${DB_NAME:-aria}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-aria} -d ${DB_NAME:-aria}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend

  redis:
    image: redis:7-alpine
    container_name: aria-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - redis_data:/data
      - ./infra/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - backend

  ollama:
    image: ollama/ollama:latest
    container_name: aria-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    mem_limit: 10G
    environment:
      - OLLAMA_KEEP_ALIVE=-1
      - OLLAMA_MAX_LOADED_MODELS=2
      - OLLAMA_NUM_PARALLEL=4
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    networks:
      - backend

  vosk:
    image: alphacep/kaldi-es:latest
    container_name: aria-vosk
    restart: unless-stopped
    ports:
      - "2700:2700"
    volumes:
      - vosk_model:/opt/vosk-model-es
    healthcheck:
      test: ["CMD", "python3", "-c", "import socket; s=socket.socket(); s.connect(('localhost',2700)); s.close()"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend

  kokoro-tts:
    build:
      context: ./services/kokoro-tts
      dockerfile: Dockerfile
    container_name: aria-kokoro-tts
    restart: unless-stopped
    ports:
      - "8002:8002"
    environment:
      - KOKORO_VOICE=${KOKORO_VOICE:-af_sarah}
      - KOKORO_SAMPLE_RATE=24000
    volumes:
      - kokoro_voices:/app/voices
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend

  asterisk:
    build:
      context: ./services/asterisk
      dockerfile: Dockerfile
    container_name: aria-asterisk
    restart: unless-stopped
    network_mode: host
    cap_add:
      - NET_ADMIN
    environment:
      - ASTERISK_ARI_URL=${ASTERISK_ARI_URL:-http://localhost:8088}
      - ARI_USERNAME=${ARI_USERNAME:-aria}
      - ARI_PASSWORD=${ARI_PASSWORD:-change_me}
    volumes:
      - asterisk_data:/var/lib/asterisk
      - asterisk_etc:/etc/asterisk
      - ./recordings:/var/spool/asterisk/monitor:rw
      - ./services/asterisk/config:/etc/asterisk/custom:ro
    healthcheck:
      test: ["CMD", "asterisk", "-rx", "core show uptime"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 45s
    depends_on:
      ai-engine:
        condition: service_started
      orchestrator:
        condition: service_started

  ai-engine:
    build:
      context: ./services/ai-engine
      dockerfile: Dockerfile
    container_name: aria-ai-engine
    restart: unless-stopped
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-aria}:${DB_PASSWORD}@postgres:5432/${DB_NAME:-aria}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - OLLAMA_URL=${OLLAMA_URL:-http://ollama:11434}
      - VOSK_URL=${VOSK_URL:-ws://vosk:2700}
      - TTS_URL=${TTS_URL:-http://kokoro-tts:8002}
      - ARI_URL=${ASTERISK_ARI_URL:-http://host.docker.internal:8088}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_started
      vosk:
        condition: service_started
      kokoro-tts:
        condition: service_started
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - backend
      - frontend

  orchestrator:
    build:
      context: ./services/orchestrator
      dockerfile: Dockerfile
    container_name: aria-orchestrator
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-aria}:${DB_PASSWORD}@postgres:5432/${DB_NAME:-aria}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - AI_ENGINE_URL=http://ai-engine:8001
      - JWT_SECRET=${JWT_SECRET}
      - ARI_URL=${ASTERISK_ARI_URL:-http://host.docker.internal:8088}
      - ARI_USERNAME=${ARI_USERNAME:-aria}
      - ARI_PASSWORD=${ARI_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - backend
      - frontend

  celery-worker:
    build:
      context: ./services/celery-workers
      dockerfile: Dockerfile
    container_name: aria-celery-worker
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-aria}:${DB_PASSWORD}@postgres:5432/${DB_NAME:-aria}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/1
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/2
      - AI_ENGINE_URL=http://ai-engine:8001
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "celery -A tasks inspect ping | grep -q 'OK'"]
      interval: 20s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - backend

  dashboard:
    build:
      context: ./services/dashboard
      dockerfile: Dockerfile
    container_name: aria-dashboard
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
      - REACT_APP_WS_URL=ws://localhost:8000/ws
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s
    networks:
      - frontend

  nginx:
    image: nginx:alpine
    container_name: aria-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infra/nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      orchestrator:
        condition: service_healthy
      dashboard:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - frontend

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  ollama_data:
    driver: local
  vosk_model:
    driver: local
  kokoro_voices:
    driver: local
  asterisk_data:
    driver: local
  asterisk_etc:
    driver: local

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
EOF

echo "[PASS] docker-compose.local.yml creado en ${COMPOSE_FILE}"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    (cd "${PROJECT_ROOT}" && docker compose -f docker-compose.local.yml config >/dev/null)
    echo "[PASS] docker compose config OK"
  elif command -v docker-compose >/dev/null 2>&1; then
    (cd "${PROJECT_ROOT}" && docker-compose -f docker-compose.local.yml config >/dev/null)
    echo "[PASS] docker-compose config OK"
  else
    echo "[WARN] No se encontro compose para validar sintaxis"
  fi
fi
