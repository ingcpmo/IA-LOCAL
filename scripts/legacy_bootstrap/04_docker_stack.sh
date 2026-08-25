#!/bin/bash
# ============================================================
# Script 04: Docker Stack — API + PostgreSQL + Redis
# Ollama corre en el HOST, no dentro del compose
# Proyecto raíz: /home/ing_cpmo
# ============================================================

set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

PROJECT_DIR="/home/ing_cpmo"
OLLAMA_API="http://localhost:11434"
API_HEALTH="http://localhost:8000/health"

pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    ((PASS+=1))
}

fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    ((FAIL+=1))
}

warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    ((WARN+=1))
}

sec() {
    echo -e "\n${BLUE}${BOLD}▶ $1${NC}"
}

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  Script 04 — Docker Stack API + PostgreSQL + Redis${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}  Nota: Ollama corre en el HOST, API accede por host-gateway:11434${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Ubicación del proyecto
# ============================================================

sec "Validando raíz del proyecto"

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    pass "Directorio raíz encontrado: $PROJECT_DIR"
else
    fail "No existe el directorio raíz esperado: $PROJECT_DIR"
fi

pass "Directorio activo: $(pwd)"

# ============================================================
# Validaciones previas
# ============================================================

sec "Validaciones previas"

if [ -f ".env" ]; then
    pass ".env encontrado"
else
    fail ".env no encontrado en $PROJECT_DIR"
fi

if [ -f "docker-compose.yml" ]; then
    pass "docker-compose.yml encontrado"
elif [ -f "compose.yml" ]; then
    pass "compose.yml encontrado"
else
    fail "No se encontró docker-compose.yml ni compose.yml en $PROJECT_DIR"
fi

if command -v docker >/dev/null 2>&1; then
    pass "Docker disponible: $(docker --version)"
else
    fail "Docker no disponible"
fi

if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose disponible: $(docker compose version | head -1)"
else
    fail "Docker Compose no disponible"
fi

if docker info >/dev/null 2>&1; then
    pass "Docker accesible sin sudo"
else
    fail "Docker no accesible sin sudo en esta sesión"
fi

SWAP_KB="$(grep SwapTotal /proc/meminfo | awk '{print $2}')"

if (( SWAP_KB >= 3000000 )); then
    pass "Swap activa: $(free -h | awk '/Swap/ {print $2}')"
else
    fail "Swap insuficiente o no activa"
fi

AVAIL_MB="$(( $(grep MemAvailable /proc/meminfo | awk '{print $2}') / 1024 ))"

if (( AVAIL_MB >= 5000 )); then
    pass "RAM disponible: ${AVAIL_MB} MB"
else
    warn "RAM disponible ajustada: ${AVAIL_MB} MB"
fi

FREE_KB="$(df / | tail -1 | awk '{print $4}')"
FREE_GB="$(( FREE_KB / 1024 / 1024 ))"

if (( FREE_KB >= 10000000 )); then
    pass "Disco libre suficiente: ${FREE_GB} GB"
else
    fail "Disco libre bajo: ${FREE_GB} GB"
fi

# ============================================================
# Validar Ollama en host
# ============================================================

sec "Verificando Ollama en host"

if curl -sf "${OLLAMA_API}/api/version" >/dev/null 2>&1; then
    OLLAMA_VER="$(curl -s "${OLLAMA_API}/api/version" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo '?')"
    pass "Ollama accesible en host:11434 — versión ${OLLAMA_VER}"
else
    warn "Ollama no responde en ${OLLAMA_API}; la API puede levantar, pero las consultas al modelo fallarán"
fi

if ollama list 2>/dev/null | grep -q "mistral:7b-instruct-q4_K_M"; then
    pass "Modelo mistral:7b-instruct-q4_K_M disponible en Ollama"
else
    warn "Modelo mistral:7b-instruct-q4_K_M no confirmado en ollama list"
fi

# ============================================================
# Validar variables mínimas del .env
# ============================================================

sec "Validando variables .env"

if grep -q "^DATABASE_URL=" .env; then
    pass "DATABASE_URL definido"
else
    fail "DATABASE_URL no definido en .env"
fi

if grep -q "^REDIS_URL=" .env; then
    pass "REDIS_URL definido"
else
    fail "REDIS_URL no definido en .env"
fi

if grep -q "^OLLAMA_BASE_URL=" .env; then
    pass "OLLAMA_BASE_URL definido"
else
    fail "OLLAMA_BASE_URL no definido en .env"
fi

if grep -q "^OLLAMA_MODEL=mistral:7b-instruct-q4_K_M" .env; then
    pass "OLLAMA_MODEL configurado correctamente"
else
    warn "OLLAMA_MODEL no coincide con mistral:7b-instruct-q4_K_M"
fi

# ============================================================
# Construir imagen API
# ============================================================

sec "Construyendo imagen Docker de la API"

if (( FAIL == 0 )); then
    echo "  Primera construcción puede tardar por dependencias Python, torch CPU o embeddings."

    if docker compose build api; then
        pass "Imagen API construida"
    else
        fail "Falló docker compose build api"
    fi
else
    warn "Build omitido por fallos previos"
fi

# ============================================================
# Levantar PostgreSQL y Redis
# ============================================================

sec "Levantando PostgreSQL y Redis"

if (( FAIL == 0 )); then
    if docker compose up -d postgres redis; then
        pass "PostgreSQL y Redis enviados a levantar"
    else
        fail "Falló docker compose up -d postgres redis"
    fi

    sleep 8

    if docker compose ps postgres | grep -qi "running\|up"; then
        pass "Contenedor PostgreSQL en ejecución"
    else
        warn "PostgreSQL no aparece en ejecución todavía"
    fi

    if docker compose ps redis | grep -qi "running\|up"; then
        pass "Contenedor Redis en ejecución"
    else
        warn "Redis no aparece en ejecución todavía"
    fi

    if docker compose exec -T postgres pg_isready -U gmp_user -q >/dev/null 2>&1; then
        pass "PostgreSQL responde con pg_isready"
    else
        warn "PostgreSQL aún no responde con pg_isready"
    fi

    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        pass "Redis responde PONG"
    else
        warn "Redis aún no responde PONG"
    fi
else
    warn "PostgreSQL y Redis omitidos por fallos previos"
fi

# ============================================================
# Levantar API
# ============================================================

sec "Levantando API"

if (( FAIL == 0 )); then
    if docker compose up -d api; then
        pass "API enviada a levantar"
    else
        fail "Falló docker compose up -d api"
    fi

    echo "  Esperando healthcheck de API en ${API_HEALTH}"
    MAX=120
    C=0

    while ! curl -sf "${API_HEALTH}" >/dev/null 2>&1; do
        sleep 5
        C=$((C+5))
        echo -n "."
        if (( C >= MAX )); then
            break
        fi
    done

    echo ""

    if curl -sf "${API_HEALTH}" >/dev/null 2>&1; then
        pass "API respondiendo en :8000"
    else
        warn "API no responde aún en :8000/health"
    fi
else
    warn "API omitida por fallos previos"
fi

# ============================================================
# Estado del stack
# ============================================================

sec "Estado del stack"

if docker compose ps; then
    pass "docker compose ps ejecutado"
else
    fail "No fue posible obtener estado del stack"
fi

echo ""

if docker stats --no-stream --format "  {{.Name}}: CPU={{.CPUPerc}} MEM={{.MemUsage}}" 2>/dev/null; then
    pass "docker stats obtenido"
else
    warn "No fue posible obtener docker stats"
fi

# ============================================================
# Logs mínimos si API no responde
# ============================================================

sec "Validación de logs mínimos"

if curl -sf "${API_HEALTH}" >/dev/null 2>&1; then
    pass "No se requieren logs de error de API"
else
    warn "Últimas líneas de logs de API:"
    docker compose logs --tail=40 api || true
fi

# ============================================================
# Validación final de servicios
# ============================================================

sec "Validación final de servicios"

if docker compose ps postgres | grep -qi "running\|up"; then
    pass "PostgreSQL activo"
else
    fail "PostgreSQL no está activo"
fi

if docker compose ps redis | grep -qi "running\|up"; then
    pass "Redis activo"
else
    fail "Redis no está activo"
fi

if docker compose ps api | grep -qi "running\|up"; then
    pass "API activa"
else
    fail "API no está activa"
fi

if curl -sf "${API_HEALTH}" >/dev/null 2>&1; then
    pass "Healthcheck API OK"
else
    warn "Healthcheck API no confirmado"
fi

# ============================================================
# Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 04 finalizó con fallos críticos${NC}"
    echo -e "  Revisar stack: ${BLUE}docker compose ps${NC}"
    echo -e "  Logs API     : ${BLUE}docker compose logs api --tail=100${NC}"
    echo -e "  Logs DB      : ${BLUE}docker compose logs postgres --tail=100${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 04 completado con advertencias — revisar antes de continuar${NC}"
    echo -e "  Proyecto : ${BLUE}${PROJECT_DIR}${NC}"
    echo -e "  API      : ${BLUE}http://localhost:8000${NC}"
    echo -e "  Ollama   : ${BLUE}${OLLAMA_API}${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 04 completado correctamente — Docker stack levantado${NC}"
echo -e "  Proyecto : ${BLUE}${PROJECT_DIR}${NC}"
echo -e "  API      : ${BLUE}http://localhost:8000${NC}"
echo -e "  Health   : ${BLUE}${API_HEALTH}${NC}"
echo -e "  Ollama   : ${BLUE}${OLLAMA_API}${NC}"
echo -e "  Siguiente: ${BLUE}bash scripts/05_python_venv.sh${NC}"
exit 0
