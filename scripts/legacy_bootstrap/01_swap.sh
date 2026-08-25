#!/bin/bash
# ============================================================
# Script 01: Swap 4 GB — ejecución segura
# Crea, activa y valida /swapfile para protección OOM
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

echo -e "${BOLD}== Script 01 — Swap 4 GB ==${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Estado inicial
# ============================================================

sec "Estado inicial de swap"

SWAP_KB="$(grep SwapTotal /proc/meminfo | awk '{print $2}')"
SWAP_H="$(free -h | awk '/Swap/ {print $2}')"

if (( SWAP_KB >= 3000000 )); then
    pass "Swap ya activa: ${SWAP_H}"

    if grep -qE '^[^#].*/swapfile[[:space:]]+none[[:space:]]+swap' /etc/fstab; then
        pass "Persistencia en /etc/fstab ya configurada"
    else
        warn "Swap activa, pero /swapfile no aparece activo en /etc/fstab"
        echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
        pass "Entrada /swapfile agregada a /etc/fstab"
    fi

else
    warn "Swap actual insuficiente: ${SWAP_H}"
fi

# ============================================================
# Validar disco
# ============================================================

sec "Verificando espacio disponible"

FREE_KB="$(df / | tail -1 | awk '{print $4}')"

if command -v bc >/dev/null 2>&1; then
    FREE_GB="$(echo "scale=1; $FREE_KB / 1024 / 1024" | bc)"
else
    FREE_GB="$((FREE_KB / 1024 / 1024))"
    warn "bc no instalado — disco mostrado sin decimales"
fi

if (( FREE_KB >= 6000000 )); then
    pass "Disco libre suficiente: ${FREE_GB} GB"
else
    fail "Disco libre insuficiente para swap 4 GB: ${FREE_GB} GB"
fi

# ============================================================
# Crear o reutilizar /swapfile
# ============================================================

sec "Preparando /swapfile"

if (( FAIL == 0 )); then

    if [ -f /swapfile ]; then
        SIZE_BYTES="$(stat -c%s /swapfile)"
        SIZE_MB="$((SIZE_BYTES / 1024 / 1024))"

        if (( SIZE_MB >= 3900 )); then
            pass "/swapfile ya existe con tamaño adecuado: ${SIZE_MB} MB"
        else
            warn "/swapfile existe, pero tamaño insuficiente: ${SIZE_MB} MB"
            sudo swapoff /swapfile 2>/dev/null || true
            sudo rm -f /swapfile
            pass "/swapfile anterior removido"
        fi
    fi

    if [ ! -f /swapfile ]; then
        echo "  Creando /swapfile de 4 GB..."

        if sudo fallocate -l 4G /swapfile 2>/dev/null; then
            pass "/swapfile creado con fallocate"
        else
            warn "fallocate no disponible o falló; usando dd"
            sudo dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress
            pass "/swapfile creado con dd"
        fi
    fi

    sudo chmod 600 /swapfile
    pass "Permisos aplicados: 600"

fi

# ============================================================
# Inicializar swap
# ============================================================

sec "Inicializando swap"

if (( FAIL == 0 )); then

    if swapon --show | grep -q "/swapfile"; then
        pass "/swapfile ya está activo"
    else
        sudo mkswap /swapfile >/dev/null
        pass "mkswap aplicado a /swapfile"

        sudo swapon /swapfile
        pass "/swapfile activado con swapon"
    fi

fi

# ============================================================
# Persistencia
# ============================================================

sec "Configurando persistencia"

if (( FAIL == 0 )); then

    if grep -qE '^[^#].*/swapfile[[:space:]]+none[[:space:]]+swap' /etc/fstab; then
        pass "/swapfile ya está registrado en /etc/fstab"
    else
        echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
        pass "/swapfile agregado a /etc/fstab"
    fi

fi

# ============================================================
# Swappiness
# ============================================================

sec "Configurando swappiness"

if (( FAIL == 0 )); then

    sudo sysctl -w vm.swappiness=10 >/dev/null
    pass "vm.swappiness aplicado en runtime: 10"

    if grep -q "^vm.swappiness=" /etc/sysctl.conf; then
        sudo sed -i 's/^vm.swappiness=.*/vm.swappiness=10/' /etc/sysctl.conf
        pass "vm.swappiness actualizado en /etc/sysctl.conf"
    else
        echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf >/dev/null
        pass "vm.swappiness agregado a /etc/sysctl.conf"
    fi

fi

# ============================================================
# Validación final
# ============================================================

sec "Validación final"

SWAP_NOW_KB="$(grep SwapTotal /proc/meminfo | awk '{print $2}')"
SWAP_NOW_H="$(free -h | awk '/Swap/ {print $2}')"

if (( SWAP_NOW_KB >= 3000000 )); then
    pass "Swap activa: ${SWAP_NOW_H}"
else
    fail "Swap sigue insuficiente: ${SWAP_NOW_H}"
fi

if swapon --show | grep -q "/swapfile"; then
    pass "swapon confirma /swapfile activo"
else
    fail "swapon no muestra /swapfile activo"
fi

if grep -qE '^[^#].*/swapfile[[:space:]]+none[[:space:]]+swap' /etc/fstab; then
    pass "/etc/fstab contiene entrada persistente de /swapfile"
else
    fail "/etc/fstab no contiene entrada persistente de /swapfile"
fi

CURRENT_SWAPPINESS="$(sysctl -n vm.swappiness)"

if [ "$CURRENT_SWAPPINESS" = "10" ]; then
    pass "swappiness activo: $CURRENT_SWAPPINESS"
else
    warn "swappiness actual diferente de 10: $CURRENT_SWAPPINESS"
fi

echo ""
free -h
echo ""
swapon --show

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Swap no quedó correctamente configurada${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Swap configurada con advertencias${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Swap 4 GB configurada y validada correctamente${NC}"
exit 0
