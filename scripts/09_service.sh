#!/bin/bash
# ============================================================
# Script 09 — Systemd service + backup cron
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
#
# Objetivo:
#   - Habilitar Docker en arranque
#   - Crear servicio systemd gmp-copilot
#   - Crear script de backup
#   - Configurar cron de backup, health y RAM
#   - Ejecutar primer backup
#
# Uso:
#   bash scripts/09_service.sh
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
WARN=0
FAIL=0

PROJECT_DIR="/home/ing_cpmo"
SERVICE_NAME="gmp-copilot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_USER="$(whoami)"

pass() {
    echo -e "  ${GREEN}[PASS]${NC} $1"
    ((PASS+=1))
}

warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    ((WARN+=1))
}

fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    ((FAIL+=1))
}

sec() {
    echo -e "\n${BLUE}${BOLD}▶ $1${NC}"
}

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  Script 09 — Systemd + Backup Cron${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Validar raíz
# ============================================================

sec "Validando raíz del proyecto"

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    pass "Directorio raíz encontrado: $PROJECT_DIR"
else
    fail "No existe el directorio raíz esperado: $PROJECT_DIR"
fi

if (( FAIL == 0 )); then
    pass "Directorio activo: $(pwd)"
fi

# ============================================================
# Validar archivos base
# ============================================================

sec "Validando archivos base"

if (( FAIL == 0 )); then
    if [ -f "docker-compose.yml" ]; then
        pass "docker-compose.yml encontrado"
    else
        fail "No existe docker-compose.yml en $PROJECT_DIR"
    fi

    if [ -f ".env" ]; then
        pass ".env encontrado"
    else
        warn ".env no encontrado"
    fi

    mkdir -p logs
    mkdir -p data/backups
    mkdir -p data/chroma
    mkdir -p data/audit_logs
    mkdir -p scripts/ops

    pass "Directorios logs, backups, chroma y audit_logs disponibles"
else
    warn "Validación de archivos omitida por fallos previos"
fi

# ============================================================
# Validar comandos requeridos
# ============================================================

sec "Validando comandos requeridos"

if command -v docker >/dev/null 2>&1; then
    pass "docker disponible: $(docker --version)"
else
    fail "docker no disponible"
fi

if docker compose version >/dev/null 2>&1; then
    pass "docker compose disponible: $(docker compose version | head -1)"
else
    fail "docker compose no disponible"
fi

if command -v systemctl >/dev/null 2>&1; then
    pass "systemctl disponible"
else
    fail "systemctl no disponible"
fi

if command -v crontab >/dev/null 2>&1; then
    pass "crontab disponible"
else
    fail "crontab no disponible"
fi

if command -v gzip >/dev/null 2>&1; then
    pass "gzip disponible"
else
    fail "gzip no disponible"
fi

if command -v tar >/dev/null 2>&1; then
    pass "tar disponible"
else
    fail "tar no disponible"
fi

if command -v curl >/dev/null 2>&1; then
    pass "curl disponible"
else
    fail "curl no disponible"
fi

# ============================================================
# Validar sudo
# ============================================================

sec "Validando permisos sudo"

if (( FAIL == 0 )); then
    if sudo -n true >/dev/null 2>&1; then
        pass "sudo disponible sin contraseña interactiva"
    else
        warn "sudo puede solicitar contraseña"
        if sudo true; then
            pass "sudo validado"
        else
            fail "No se pudo validar sudo"
        fi
    fi
else
    warn "Validación sudo omitida por fallos previos"
fi

# ============================================================
# Habilitar Docker
# ============================================================

sec "Habilitando Docker en arranque"

if (( FAIL == 0 )); then
    if sudo systemctl enable docker >/dev/null 2>&1; then
        pass "Docker habilitado en startup"
    else
        fail "No se pudo habilitar Docker"
    fi

    if systemctl is-active docker >/dev/null 2>&1; then
        pass "Docker está activo"
    else
        warn "Docker no está activo; intentando iniciar"
        if sudo systemctl start docker >/dev/null 2>&1; then
            pass "Docker iniciado"
        else
            fail "No se pudo iniciar Docker"
        fi
    fi
else
    warn "Habilitación Docker omitida por fallos previos"
fi

# ============================================================
# Crear servicio systemd
# ============================================================

sec "Creando servicio systemd gmp-copilot"

if (( FAIL == 0 )); then
    sudo tee "$SERVICE_FILE" > /dev/null << SVCEOF
[Unit]
Description=GMP AI Copilot — FDA Qualification Platform
After=network.target docker.service ollama.service
Requires=docker.service

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStartPre=/usr/bin/docker compose -f $PROJECT_DIR/docker-compose.yml pull --quiet
ExecStart=/usr/bin/docker compose -f $PROJECT_DIR/docker-compose.yml up
ExecStop=/usr/bin/docker compose -f $PROJECT_DIR/docker-compose.yml down
Restart=always
RestartSec=30
StandardOutput=append:$PROJECT_DIR/logs/gmp-copilot.log
StandardError=append:$PROJECT_DIR/logs/gmp-copilot-error.log

[Install]
WantedBy=multi-user.target
SVCEOF

    if [ -f "$SERVICE_FILE" ]; then
        pass "Servicio creado: $SERVICE_FILE"
    else
        fail "No se creó el archivo de servicio"
    fi

    if sudo systemctl daemon-reload >/dev/null 2>&1; then
        pass "systemd daemon-reload ejecutado"
    else
        fail "Falló systemctl daemon-reload"
    fi

    if sudo systemctl enable "$SERVICE_NAME" >/dev/null 2>&1; then
        pass "Servicio $SERVICE_NAME habilitado"
    else
        fail "No se pudo habilitar $SERVICE_NAME"
    fi
else
    warn "Creación de servicio omitida por fallos previos"
fi

# ============================================================
# Crear script de backup
# ============================================================

sec "Creando script de backup"

if (( FAIL == 0 )); then
    cat > "$PROJECT_DIR/scripts/ops/backup.sh" << BKEOF
#!/bin/bash
# ============================================================
# GMP AI Copilot — Backup
# Proyecto raíz: $PROJECT_DIR
# ============================================================

set -euo pipefail

export PATH="\$PATH:/usr/sbin:/sbin"

PROJECT_DIR="$PROJECT_DIR"
BACKUP_DIR="\$PROJECT_DIR/data/backups"
DATE="\$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS=30

mkdir -p "\$BACKUP_DIR"

echo "[\$(date)] Backup iniciado"

cd "\$PROJECT_DIR"

# PostgreSQL
if docker compose -f "\$PROJECT_DIR/docker-compose.yml" ps postgres >/dev/null 2>&1; then
    if docker compose -f "\$PROJECT_DIR/docker-compose.yml" exec -T postgres \
        pg_dump -U gmp_user gmp_copilot 2>/dev/null | \
        gzip > "\$BACKUP_DIR/postgres_\${DATE}.sql.gz"; then
        echo "  PostgreSQL: OK"
    else
        echo "  PostgreSQL: ERROR"
    fi
else
    echo "  PostgreSQL: ERROR — contenedor no disponible"
fi

# ChromaDB
if [ -d "\$PROJECT_DIR/data/chroma" ]; then
    if tar -czf "\$BACKUP_DIR/chroma_\${DATE}.tar.gz" \
        -C "\$PROJECT_DIR/data" chroma/ 2>/dev/null; then
        echo "  ChromaDB: OK"
    else
        echo "  ChromaDB: ERROR"
    fi
else
    echo "  ChromaDB: OMITIDO — directorio no existe"
fi

# Audit logs
if [ -d "\$PROJECT_DIR/data/audit_logs" ]; then
    if tar -czf "\$BACKUP_DIR/audit_\${DATE}.tar.gz" \
        -C "\$PROJECT_DIR/data" audit_logs/ 2>/dev/null; then
        echo "  Audit logs: OK"
    else
        echo "  Audit logs: ERROR"
    fi
else
    echo "  Audit logs: OMITIDO — directorio no existe"
fi

# Limpieza por retención
find "\$BACKUP_DIR" -type f -mtime +\${RETENTION_DAYS} -delete 2>/dev/null || true

echo "[\$(date)] Backup completado. Archivos: \$(find "\$BACKUP_DIR" -type f | wc -l)"
BKEOF

    chmod +x "$PROJECT_DIR/scripts/ops/backup.sh"

    if [ -x "$PROJECT_DIR/scripts/ops/backup.sh" ]; then
        pass "Script backup creado: scripts/ops/backup.sh"
    else
        fail "No se creó correctamente scripts/ops/backup.sh"
    fi
else
    warn "Creación de backup omitida por fallos previos"
fi

# ============================================================
# Crear scripts auxiliares status/logs
# ============================================================

sec "Creando scripts auxiliares de operación"

if (( FAIL == 0 )); then
    cat > "$PROJECT_DIR/scripts/ops/status.sh" << 'STEOF'
#!/bin/bash
# GMP AI Copilot — Estado general

set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

PROJECT_DIR="/home/ing_cpmo"
cd "$PROJECT_DIR"

echo "== GMP AI Copilot status =="
echo ""
echo "Fecha: $(date)"
echo "Host : $(hostname)"
echo ""

echo "== Systemd =="
systemctl is-enabled gmp-copilot 2>/dev/null || true
systemctl is-active gmp-copilot 2>/dev/null || true
echo ""

echo "== Docker containers =="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo ""

echo "== API health =="
curl -sf http://localhost:8000/health || echo "API DOWN"
echo ""

echo ""
echo "== Ollama tags =="
curl -sf http://localhost:11434/api/tags 2>/dev/null | head -c 500 || echo "OLLAMA DOWN"
echo ""

echo ""
echo "== Disk =="
df -h /
echo ""

echo "== Memory =="
free -h
echo ""

echo "== Backups =="
ls -lah "$PROJECT_DIR/data/backups" 2>/dev/null | tail -20 || true
STEOF

    chmod +x "$PROJECT_DIR/scripts/ops/status.sh"

    cat > "$PROJECT_DIR/scripts/ops/logs.sh" << 'LGEOF'
#!/bin/bash
# GMP AI Copilot — Logs helper
# Uso:
#   bash scripts/ops/logs.sh api
#   bash scripts/ops/logs.sh postgres
#   bash scripts/ops/logs.sh redis
#   bash scripts/ops/logs.sh service
#   bash scripts/ops/logs.sh backup

set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

TARGET="${1:-api}"

case "$TARGET" in
    api)
        docker logs --tail=120 -f gmp-api
        ;;
    postgres)
        docker logs --tail=120 -f gmp-postgres
        ;;
    redis)
        docker logs --tail=120 -f gmp-redis
        ;;
    service)
        tail -n 120 -f /home/ing_cpmo/logs/gmp-copilot.log
        ;;
    service-error)
        tail -n 120 -f /home/ing_cpmo/logs/gmp-copilot-error.log
        ;;
    backup)
        tail -n 120 -f /home/ing_cpmo/logs/backup.log
        ;;
    *)
        echo "Uso: bash scripts/ops/logs.sh [api|postgres|redis|service|service-error|backup]"
        exit 1
        ;;
esac
LGEOF

    chmod +x "$PROJECT_DIR/scripts/ops/logs.sh"

    pass "scripts/ops/status.sh creado"
    pass "scripts/ops/logs.sh creado"
else
    warn "Scripts auxiliares omitidos por fallos previos"
fi

# ============================================================
# Configurar cron jobs
# ============================================================

sec "Configurando cron jobs"

if (( FAIL == 0 )); then
    CRON_BK="0 3 * * * $PROJECT_DIR/scripts/ops/backup.sh >> $PROJECT_DIR/logs/backup.log 2>&1"
    CRON_HK="*/5 * * * * curl -sf http://localhost:8000/health >/dev/null 2>&1 || echo \"\$(date): API DOWN\" >> $PROJECT_DIR/logs/health.log"
    CRON_RAM="0 */6 * * * free -h >> $PROJECT_DIR/logs/ram_monitor.log 2>&1"

    (
        crontab -l 2>/dev/null | grep -v "GMP Copilot" | grep -v "$PROJECT_DIR/scripts/ops/backup.sh" | grep -v "localhost:8000/health" | grep -v "ram_monitor.log" || true
        echo "# GMP Copilot"
        echo "$CRON_BK"
        echo "$CRON_HK"
        echo "$CRON_RAM"
    ) | crontab -

    if crontab -l 2>/dev/null | grep -q "$PROJECT_DIR/scripts/ops/backup.sh"; then
        pass "Cron backup configurado 03:00"
    else
        fail "Cron backup no quedó configurado"
    fi

    if crontab -l 2>/dev/null | grep -q "localhost:8000/health"; then
        pass "Cron health check configurado cada 5 minutos"
    else
        fail "Cron health check no quedó configurado"
    fi

    if crontab -l 2>/dev/null | grep -q "ram_monitor.log"; then
        pass "Cron RAM monitor configurado cada 6 horas"
    else
        fail "Cron RAM monitor no quedó configurado"
    fi
else
    warn "Cron omitido por fallos previos"
fi

# ============================================================
# Ejecutar primer backup
# ============================================================

sec "Ejecutando primer backup"

if (( FAIL == 0 )); then
    BACKUP_EXIT=0
    bash "$PROJECT_DIR/scripts/ops/backup.sh" || BACKUP_EXIT=$?

    if [ "$BACKUP_EXIT" -eq 0 ]; then
        pass "Primer backup ejecutado"
    else
        warn "Primer backup terminó con código $BACKUP_EXIT"
    fi

    BACKUP_COUNT="$(find "$PROJECT_DIR/data/backups" -type f 2>/dev/null | wc -l || echo 0)"
    if [ "$BACKUP_COUNT" -gt 0 ]; then
        pass "Archivos de backup encontrados: $BACKUP_COUNT"
    else
        warn "No se encontraron archivos de backup"
    fi
else
    warn "Primer backup omitido por fallos previos"
fi

# ============================================================
# Validaciones finales del servicio
# ============================================================

sec "Validaciones finales"

if (( FAIL == 0 )); then
    if systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        pass "Servicio $SERVICE_NAME habilitado en systemd"
    else
        warn "Servicio $SERVICE_NAME no aparece habilitado"
    fi

    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        pass "API responde después de configurar servicio"
    else
        warn "API no respondió después de configurar servicio"
    fi

    if curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
        pass "Ollama responde después de configurar servicio"
    else
        warn "Ollama no respondió después de configurar servicio"
    fi
else
    warn "Validaciones finales omitidas por fallos previos"
fi

# ============================================================
# Recordatorio de pendientes funcionales
# ============================================================

sec "Pendientes funcionales registrados"

warn "Pendiente: POST /api/v1/query no existe"
warn "Pendiente: GET /api/v1/knowledge/stats no existe"
warn "Pendiente: GET /api/v1/audit/verify no existe"
warn "Pendiente: GET /api/v1/protocol-template/IQ no existe"
warn "Pendiente: knowledge/retriever.py no existe"
warn "Pendiente: tests/test_agents.py no existe"

# ============================================================
# Resumen final
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 09 finalizó con fallos críticos${NC}"
    echo -e "  Revisar servicio : ${BLUE}sudo systemctl status gmp-copilot${NC}"
    echo -e "  Revisar Docker   : ${BLUE}docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'${NC}"
    echo -e "  Logs API         : ${BLUE}bash scripts/ops/logs.sh api${NC}"
    echo -e "  Logs servicio    : ${BLUE}bash scripts/ops/logs.sh service-error${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 09 completado con advertencias${NC}"
    echo -e "  Servicio : ${BLUE}sudo systemctl status gmp-copilot${NC}"
    echo -e "  Estado   : ${BLUE}bash scripts/ops/status.sh${NC}"
    echo -e "  Logs API : ${BLUE}bash scripts/ops/logs.sh api${NC}"
    echo -e "  Backup   : ${BLUE}bash scripts/ops/backup.sh${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 09 completado correctamente${NC}"
echo -e "  Servicio : ${BLUE}sudo systemctl status gmp-copilot${NC}"
echo -e "  Estado   : ${BLUE}bash scripts/ops/status.sh${NC}"
echo -e "  Logs API : ${BLUE}bash scripts/ops/logs.sh api${NC}"
echo -e "  Backup   : ${BLUE}bash scripts/ops/backup.sh${NC}"
exit 0
