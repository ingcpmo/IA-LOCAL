#!/bin/bash
# ============================================================
# Script 03: Ollama + mistral:7b-instruct-q4_K_M en CPU
# Servidor qsg: AMD EPYC 7B12, 4 vCPU, 15 GB RAM, sin GPU
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

MODEL="mistral:7b-instruct-q4_K_M"
MODEL_NAME_CHECK="mistral:7b-instruct-q4_K_M"
OLLAMA_API="http://localhost:11434"
MODEL_RAM_GB=5

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
echo -e "${BOLD}  Script 03 — Ollama + mistral:7b-instruct-q4_K_M CPU${NC}"
echo -e "${BOLD}  Servidor qsg: AMD EPYC 4vCPU | 15 GB RAM | Sin GPU${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Validación previa del servidor
# ============================================================

sec "Validación previa"

if grep -qi "debian" /etc/os-release; then
    pass "Sistema Debian detectado"
else
    fail "Sistema no identificado como Debian"
fi

NCPU="$(nproc)"
if (( NCPU >= 4 )); then
    pass "CPU disponible: ${NCPU} vCPU"
else
    warn "CPU limitada: ${NCPU} vCPU"
fi

AVAIL_MB="$(( $(grep MemAvailable /proc/meminfo | awk '{print $2}') / 1024 ))"
if (( AVAIL_MB >= 6000 )); then
    pass "RAM disponible: ${AVAIL_MB} MB — suficiente para ${MODEL}"
else
    warn "RAM disponible baja: ${AVAIL_MB} MB — modelo requiere aproximadamente ${MODEL_RAM_GB} GB"
fi

SWAP_KB="$(grep SwapTotal /proc/meminfo | awk '{print $2}')"
if (( SWAP_KB >= 3000000 )); then
    pass "Swap activa: $(free -h | awk '/Swap/ {print $2}')"
else
    warn "Swap insuficiente o no activa"
fi

FREE_KB="$(df / | tail -1 | awk '{print $4}')"
FREE_GB="$(( FREE_KB / 1024 / 1024 ))"

if (( FREE_KB >= 10000000 )); then
    pass "Disco libre suficiente: ${FREE_GB} GB"
else
    fail "Disco libre insuficiente: ${FREE_GB} GB"
fi

if command -v curl >/dev/null 2>&1; then
    pass "curl disponible"
else
    fail "curl no disponible"
fi

if command -v python3 >/dev/null 2>&1; then
    pass "python3 disponible: $(python3 --version)"
else
    fail "python3 no disponible"
fi

# ============================================================
# Instalar o validar Ollama
# ============================================================

sec "Instalando o validando Ollama"

if command -v ollama >/dev/null 2>&1; then
    pass "Ollama ya instalado: $(ollama --version 2>/dev/null | head -1)"
else
    echo "  Descargando instalador oficial de Ollama..."

    if curl -fsSL https://ollama.com/install.sh | sh; then
        pass "Instalador de Ollama ejecutado"
    else
        fail "Falló la instalación de Ollama"
    fi

    if command -v ollama >/dev/null 2>&1; then
        pass "Ollama instalado: $(ollama --version 2>/dev/null | head -1)"
    else
        fail "Ollama no quedó disponible después de instalar"
    fi
fi

# ============================================================
# Configuración systemd para CPU
# ============================================================

sec "Configurando Ollama para CPU"

if (( FAIL == 0 )); then
    sudo mkdir -p /etc/systemd/system/ollama.service.d/

    cat > /tmp/ollama_cpu.conf << 'CONFEOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_NUM_THREAD=4"
Environment="CUDA_VISIBLE_DEVICES="
CONFEOF

    sudo cp /tmp/ollama_cpu.conf /etc/systemd/system/ollama.service.d/override.conf
    pass "Override systemd creado para Ollama CPU"

    sudo systemctl daemon-reload
    pass "systemctl daemon-reload ejecutado"

    if sudo systemctl enable ollama >/dev/null 2>&1; then
        pass "Servicio Ollama habilitado"
    else
        fail "No fue posible habilitar servicio Ollama"
    fi

    if sudo systemctl restart ollama; then
        pass "Servicio Ollama reiniciado"
    else
        fail "No fue posible reiniciar servicio Ollama"
    fi
fi

# ============================================================
# Verificación del servicio Ollama
# ============================================================

sec "Verificando servicio Ollama"

if systemctl is-active --quiet ollama 2>/dev/null; then
    pass "Servicio Ollama activo en systemd"
else
    fail "Servicio Ollama no está activo"
fi

MAX=60
C=0

while ! curl -sf "${OLLAMA_API}/api/version" >/dev/null 2>&1; do
    sleep 2
    C=$((C+2))
    echo -n "."
    if (( C >= MAX )); then
        echo ""
        fail "API Ollama no respondió en ${MAX}s"
        break
    fi
done

echo ""

if curl -sf "${OLLAMA_API}/api/version" >/dev/null 2>&1; then
    OLLAMA_VER="$(curl -s "${OLLAMA_API}/api/version" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo '?')"
    pass "API Ollama activa — versión: ${OLLAMA_VER}"
else
    fail "API Ollama no disponible en ${OLLAMA_API}"
fi

# ============================================================
# Descargar modelo
# ============================================================

sec "Validando modelo ${MODEL}"

if (( FAIL == 0 )); then
    if ollama list 2>/dev/null | grep -q "${MODEL_NAME_CHECK}"; then
        pass "Modelo ya descargado: ${MODEL}"
    else
        echo "  Descargando modelo ${MODEL}..."
        echo "  Tamaño aproximado: 4 GB"

        if ollama pull "${MODEL}"; then
            pass "Modelo descargado correctamente: ${MODEL}"
        else
            fail "Falló la descarga del modelo ${MODEL}"
        fi
    fi
fi

# ============================================================
# Test de inferencia
# ============================================================

sec "Test de inferencia CPU"

if (( FAIL == 0 )); then
    echo "  Ejecutando prueba de inferencia. En CPU puede tardar."

    RESPONSE="$(
        timeout 180 ollama run "${MODEL}" \
        "Reply with exactly these 3 words: GMP_CPU_OK" \
        --nowordwrap 2>/dev/null | head -5 | tr -d '\n' || true
    )"

    if echo "${RESPONSE}" | grep -qi "GMP_CPU_OK\|GMP\|OK"; then
        pass "Inferencia CPU funcional — respuesta detectada: ${RESPONSE}"
    else
        warn "Inferencia no confirmó texto esperado. Respuesta recibida: '${RESPONSE:-sin respuesta}'"
    fi
else
    warn "Test de inferencia omitido por fallos previos"
fi

# ============================================================
# RAM después de carga
# ============================================================

sec "Validando RAM posterior"

TOTAL_KB="$(grep MemTotal /proc/meminfo | awk '{print $2}')"
AVAIL_KB="$(grep MemAvailable /proc/meminfo | awk '{print $2}')"
USED_KB="$(( TOTAL_KB - AVAIL_KB ))"

if command -v bc >/dev/null 2>&1; then
    USED_GB="$(echo "scale=1; ${USED_KB} / 1024 / 1024" | bc)"
    AVAIL_GB="$(echo "scale=1; ${AVAIL_KB} / 1024 / 1024" | bc)"
else
    USED_GB="$(( USED_KB / 1024 / 1024 ))"
    AVAIL_GB="$(( AVAIL_KB / 1024 / 1024 ))"
fi

pass "RAM usada: ${USED_GB} GB | RAM disponible: ${AVAIL_GB} GB"

if (( AVAIL_KB >= 4000000 )); then
    pass "RAM disponible posterior suficiente"
else
    warn "RAM disponible posterior baja"
fi

# ============================================================
# Listar modelos
# ============================================================

sec "Modelos disponibles"

if ollama list; then
    pass "Listado de modelos obtenido"
else
    fail "No fue posible listar modelos de Ollama"
fi

# ============================================================
# Validación de configuración aplicada
# ============================================================

sec "Validando override systemd"

if [ -f /etc/systemd/system/ollama.service.d/override.conf ]; then
    pass "Override existe: /etc/systemd/system/ollama.service.d/override.conf"

    if grep -q "OLLAMA_HOST=0.0.0.0" /etc/systemd/system/ollama.service.d/override.conf; then
        pass "OLLAMA_HOST configurado para escuchar en 0.0.0.0"
    else
        warn "OLLAMA_HOST no aparece configurado como 0.0.0.0"
    fi

    if grep -q "OLLAMA_NUM_THREAD=4" /etc/systemd/system/ollama.service.d/override.conf; then
        pass "OLLAMA_NUM_THREAD=4 configurado"
    else
        warn "OLLAMA_NUM_THREAD=4 no aparece en override"
    fi
else
    fail "No existe override systemd de Ollama"
fi

# ============================================================
# Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 03 finalizó con fallos críticos${NC}"
    echo -e "  Revisar servicio: ${BLUE}journalctl -u ollama -n 50 --no-pager${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 03 completado con advertencias — revisar antes de continuar${NC}"
    echo -e "  Modelo: ${BLUE}${MODEL}${NC}"
    echo -e "  API   : ${BLUE}${OLLAMA_API}${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 03 completado correctamente — Ollama listo${NC}"
echo -e "  Modelo   : ${BLUE}${MODEL}${NC}"
echo -e "  API      : ${BLUE}${OLLAMA_API}${NC}"
echo -e "  Modo     : ${BLUE}CPU, 4 threads, 1 modelo cargado${NC}"
echo -e "  Siguiente: ${BLUE}bash scripts/06_project.sh${NC}"
exit 0
