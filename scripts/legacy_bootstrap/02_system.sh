#!/bin/bash
# ============================================================
# Script 02: Paquetes del sistema Debian 12
# Instalación y validación de dependencias base
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

echo -e "${BOLD}== Script 02 — Paquetes sistema Debian 12 ==${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Validar sistema operativo
# ============================================================

sec "Validando Debian 12"

if grep -qi "debian" /etc/os-release; then
    VER="$(grep VERSION_ID /etc/os-release | cut -d'"' -f2 || true)"
    PRETTY="$(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2 || true)"

    if [ "${VER:-0}" = "12" ]; then
        pass "Sistema compatible: ${PRETTY}"
    else
        warn "Sistema Debian detectado, pero no versión 12: ${PRETTY}"
    fi
else
    fail "El sistema no parece ser Debian"
fi

# ============================================================
# Actualizar sistema
# ============================================================

sec "Actualizando repositorios y paquetes"

if sudo apt update; then
    pass "apt update ejecutado correctamente"
else
    fail "apt update falló"
fi

if sudo apt upgrade -y; then
    pass "apt upgrade ejecutado correctamente"
else
    fail "apt upgrade falló"
fi

# ============================================================
# Instalar dependencias base
# ============================================================

sec "Instalando dependencias base"

if sudo apt install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    unzip \
    jq \
    bc \
    tree \
    htop \
    lsof \
    net-tools \
    ufw \
    ca-certificates \
    gnupg \
    lsb-release \
    python3-pip \
    python3-venv \
    libpq-dev \
    postgresql-client \
    redis-tools; then

    pass "Dependencias base instaladas"
else
    fail "Falló la instalación de dependencias base"
fi

# ============================================================
# Validar comandos principales
# ============================================================

sec "Validando comandos instalados"

for cmd in curl wget git unzip jq bc tree htop lsof ufw python3 pip3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        pass "$cmd disponible"
    else
        fail "$cmd no disponible"
    fi
done

if command -v psql >/dev/null 2>&1; then
    pass "postgresql-client disponible: $(psql --version | head -1)"
else
    fail "postgresql-client no disponible"
fi

if command -v redis-cli >/dev/null 2>&1; then
    pass "redis-tools disponible: $(redis-cli --version)"
else
    fail "redis-tools no disponible"
fi

# ============================================================
# Docker Compose plugin
# ============================================================

sec "Docker Compose plugin"

if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose disponible: $(docker compose version | head -1)"
else
    warn "Docker Compose no disponible; intentando instalar docker-compose-plugin"

    if sudo apt install -y docker-compose-plugin; then
        pass "docker-compose-plugin instalado"
    else
        fail "No fue posible instalar docker-compose-plugin"
    fi

    if docker compose version >/dev/null 2>&1; then
        pass "Docker Compose validado: $(docker compose version | head -1)"
    else
        fail "Docker Compose sigue sin estar disponible"
    fi
fi

# ============================================================
# Grupo docker
# ============================================================

sec "Validando grupo docker"

if getent group docker >/dev/null 2>&1; then
    pass "Grupo docker existe"
else
    warn "Grupo docker no existe"
fi

if groups "$(whoami)" | grep -qw docker; then
    pass "Usuario $(whoami) pertenece al grupo docker"
else
    warn "Usuario $(whoami) no pertenece al grupo docker"

    if sudo usermod -aG docker "$(whoami)"; then
        pass "Usuario $(whoami) agregado al grupo docker"
        warn "La sesión actual puede requerir cierre/reingreso o ejecutar: newgrp docker"
    else
        fail "No fue posible agregar el usuario al grupo docker"
    fi
fi

if docker info >/dev/null 2>&1; then
    pass "Docker accesible sin sudo en esta sesión"
else
    warn "Docker no accesible sin sudo en esta sesión actual"
fi

# ============================================================
# Firewall UFW
# ============================================================

sec "Configurando firewall UFW"

if command -v ufw >/dev/null 2>&1; then
    pass "UFW instalado"

    sudo ufw allow 22/tcp comment "SSH" >/dev/null 2>&1 || warn "No fue posible registrar regla SSH 22/tcp"
    sudo ufw allow 8000/tcp comment "GMP API" >/dev/null 2>&1 || warn "No fue posible registrar regla GMP API 8000/tcp"

    if echo "y" | sudo ufw enable >/dev/null 2>&1; then
        pass "UFW habilitado"
    else
        warn "UFW no pudo habilitarse automáticamente o ya estaba activo"
    fi

    if sudo ufw status | grep -q "Status: active"; then
        pass "UFW activo"
    else
        warn "UFW no aparece activo"
    fi

    if sudo ufw status | grep -q "22/tcp"; then
        pass "Puerto SSH 22/tcp permitido"
    else
        fail "Puerto SSH 22/tcp no aparece permitido"
    fi

    if sudo ufw status | grep -q "8000/tcp"; then
        pass "Puerto 8000/tcp permitido"
    else
        warn "Puerto 8000/tcp no aparece permitido"
    fi
else
    fail "UFW no está instalado"
fi

# ============================================================
# Validación final de versiones
# ============================================================

sec "Versiones finales"

if command -v docker >/dev/null 2>&1; then
    pass "Docker: $(docker --version)"
else
    fail "Docker no disponible"
fi

if docker compose version >/dev/null 2>&1; then
    pass "Docker Compose: $(docker compose version | head -1)"
else
    fail "Docker Compose no disponible"
fi

if command -v python3 >/dev/null 2>&1; then
    pass "Python: $(python3 --version)"
else
    fail "Python3 no disponible"
fi

if command -v pip3 >/dev/null 2>&1; then
    pass "pip: $(pip3 --version | awk '{print $1, $2}')"
else
    fail "pip3 no disponible"
fi

# ============================================================
# Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 02 finalizó con fallos críticos${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 02 completado con advertencias — revisar antes de continuar${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 02 completado correctamente${NC}"
echo -e "  Siguiente: ${BLUE}bash scripts/03_ollama.sh${NC}"
exit 0
