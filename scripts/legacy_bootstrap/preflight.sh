#!/bin/bash
# ============================================================
# Script 00: Preflight check para servidor qsg
# Versión corregida para ejecución segura con set -euo pipefail
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

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

echo -e "${BOLD}== Preflight Check — servidor qsg ==${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# OS
# ============================================================

sec "OS Debian 12"

if grep -qi "debian" /etc/os-release; then
    VER="$(grep VERSION_ID /etc/os-release | cut -d'"' -f2 || true)"
    PRETTY="$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2 || true)"

    if [ "${VER:-0}" = "12" ]; then
        pass "Debian 12 (bookworm) confirmado"
    else
        warn "OS detectado: ${PRETTY:-desconocido}"
    fi
else
    warn "Sistema no identificado como Debian"
fi

# ============================================================
# CPU
# ============================================================

sec "CPU"

NCPU="$(nproc)"

if [ "$NCPU" -ge 4 ]; then
    pass "$NCPU vCPUs detectados"
else
    warn "$NCPU vCPUs detectados — esperado mínimo 4"
fi

CPU_MODEL="$(lscpu 2>/dev/null | grep -m1 'Model name' | awk -F: '{print $2}' | xargs || true)"

if [ -n "${CPU_MODEL:-}" ]; then
    pass "CPU detectada: $CPU_MODEL"
else
    warn "No fue posible leer el modelo de CPU"
fi

L3="$(cat /sys/devices/system/cpu/cpu0/cache/index3/size 2>/dev/null || true)"

if [ -n "${L3:-}" ]; then
    pass "L3 cache disponible: $L3"
else
    warn "No fue posible validar L3 cache"
fi

# ============================================================
# Swap
# ============================================================

sec "Swap"

SWAP_KB="$(grep SwapTotal /proc/meminfo | awk '{print $2}')"

if (( SWAP_KB >= 3000000 )); then
    SWAP_H="$(free -h | awk '/Swap/ {print $2}')"
    pass "Swap: ${SWAP_H} — OK"
else
    fail "Swap insuficiente: $(free -h | awk '/Swap/ {print $2}')"
fi

# ============================================================
# RAM
# ============================================================

sec "RAM"

AVAIL="$(grep MemAvailable /proc/meminfo | awk '{print $2}')"
TOTAL="$(grep MemTotal /proc/meminfo | awk '{print $2}')"

if command -v bc >/dev/null 2>&1; then
    TOTAL_GB="$(echo "scale=1; $TOTAL / 1024 / 1024" | bc)"
    AVAIL_GB="$(echo "scale=1; $AVAIL / 1024 / 1024" | bc)"
else
    TOTAL_GB="$((TOTAL / 1024 / 1024))"
    AVAIL_GB="$((AVAIL / 1024 / 1024))"
    warn "bc no instalado — valores de RAM mostrados sin decimales"
fi

pass "RAM total: ${TOTAL_GB} GB"

if (( AVAIL >= 8000000 )); then
    pass "RAM disponible: ${AVAIL_GB} GB — suficiente para mistral:7b"
else
    warn "RAM disponible: ${AVAIL_GB} GB — ajustado"
fi

# ============================================================
# Disco
# ============================================================

sec "Disco"

FREE_KB="$(df / | tail -1 | awk '{print $4}')"

if command -v bc >/dev/null 2>&1; then
    FREE_GB="$(echo "scale=1; $FREE_KB / 1024 / 1024" | bc)"
else
    FREE_GB="$((FREE_KB / 1024 / 1024))"
fi

if (( FREE_KB >= 15000000 )); then
    pass "Disco libre: ${FREE_GB} GB"
else
    warn "Disco libre: ${FREE_GB} GB"
fi

# ============================================================
# Docker
# ============================================================

sec "Docker"

if command -v docker >/dev/null 2>&1; then
    DOCKER_VER="$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1 || true)"
    pass "Docker instalado: ${DOCKER_VER:-versión no detectada}"
else
    fail "Docker no encontrado"
fi

if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        pass "Docker accesible sin sudo"
    else
        warn "Docker instalado, pero no accesible sin sudo"
    fi
fi

if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_VER="$(docker compose version 2>/dev/null | head -1)"
        pass "Docker Compose disponible: $COMPOSE_VER"
    else
        fail "Docker Compose v2 no disponible"
    fi
fi

# ============================================================
# Ollama
# ============================================================

sec "Ollama"

if command -v ollama >/dev/null 2>&1; then
    OLLAMA_VER="$(ollama --version 2>/dev/null | head -1 || true)"
    pass "Ollama instalado: ${OLLAMA_VER:-versión no detectada}"
else
    warn "Ollama no instalado"
fi

if systemctl list-unit-files 2>/dev/null | grep -q '^ollama.service'; then
    if systemctl is-active --quiet ollama 2>/dev/null; then
        pass "Servicio Ollama activo"
    else
        warn "Servicio Ollama instalado, pero no activo"
    fi
else
    warn "Servicio Ollama no registrado en systemd"
fi

# ============================================================
# Python
# ============================================================

sec "Python"

if command -v python3 >/dev/null 2>&1; then
    PY_VER="$(python3 --version 2>/dev/null || true)"

    if python3 --version 2>/dev/null | grep -q "3.1[1-9]"; then
        pass "Python: $PY_VER"
    else
        warn "Python detectado, pero menor a 3.11: $PY_VER"
    fi
else
    warn "Python3 no encontrado"
fi

# ============================================================
# Conectividad
# ============================================================

sec "Conectividad"

if command -v curl >/dev/null 2>&1; then
    if curl -sf --max-time 5 https://ollama.com >/dev/null; then
        pass "ollama.com accesible"
    else
        fail "ollama.com no accesible"
    fi

    if curl -sf --max-time 5 https://pypi.org >/dev/null; then
        pass "pypi.org accesible"
    else
        fail "pypi.org no accesible"
    fi
else
    fail "curl no encontrado"
fi

# ============================================================
# Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ $FAIL verificaciones críticas fallaron${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ $WARN advertencias — revisar antes de continuar${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Servidor listo${NC}"
exit 0
