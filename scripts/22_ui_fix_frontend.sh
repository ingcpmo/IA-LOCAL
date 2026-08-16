#!/bin/bash
# ============================================================
# Script 22 — Fix frontend UI desde index.html
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
#
# IP anterior: 35.185.57.245
# IP nueva:    104.196.110.180
#
# Objetivo:
#   - Usar /home/ing_cpmo/index.html como fuente
#   - Copiarlo a app/static/index.html
#   - Reemplazar IP anterior por IP nueva
#   - Respaldar UI anterior
#   - Reconstruir SOLO gmp-api
#   - Validar acceso local y público
#
# Uso:
#   bash scripts/22_ui_fix_frontend.sh
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
STATIC_DIR="$PROJECT_DIR/app/static"
SRC_FILE="$PROJECT_DIR/index.html"

OLD_IP="35.185.57.245"
PUBLIC_IP="104.196.110.180"
PORT="8000"

REPORT_DIR="$PROJECT_DIR/logs/ui"
REPORT_FILE="$REPORT_DIR/ui_fix_frontend_$(date +%Y%m%d_%H%M%S).log"

pass(){ echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS+=1)); }
warn(){ echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN+=1)); }
fail(){ echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL+=1)); }
step(){ echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  Script 22 — Fix frontend UI desde index.html${NC}"
echo -e "${BOLD}  IP pública actual: $PUBLIC_IP${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  Host: $(hostname)"
echo "  Usuario: $(whoami)"
echo "  Fecha: $(date)"

mkdir -p "$REPORT_DIR"
: > "$REPORT_FILE"

# ============================================================
# 1. Validar proyecto
# ============================================================

step "Validando proyecto"

cd "$PROJECT_DIR"

[ -d "$PROJECT_DIR" ] && pass "Proyecto encontrado: $PROJECT_DIR" || fail "No existe $PROJECT_DIR"
[ -f "$PROJECT_DIR/docker-compose.yml" ] && pass "docker-compose.yml encontrado" || fail "docker-compose.yml no encontrado"
[ -d "$PROJECT_DIR/app" ] && pass "Directorio app/ encontrado" || fail "Directorio app/ no encontrado"
[ -f "$PROJECT_DIR/app/main.py" ] && pass "app/main.py encontrado" || fail "app/main.py no encontrado"

# ============================================================
# 2. Validar archivo fuente index.html
# ============================================================

step "Validando archivo fuente index.html"

if [ -f "$SRC_FILE" ]; then
    pass "Archivo fuente encontrado: $SRC_FILE"
else
    fail "No existe $SRC_FILE. Debes subir index.html a /home/ing_cpmo"
fi

SRC_SIZE=$(wc -c < "$SRC_FILE")
SRC_LINES=$(wc -l < "$SRC_FILE")

echo "  Tamaño: $SRC_SIZE bytes" | tee -a "$REPORT_FILE"
echo "  Líneas: $SRC_LINES" | tee -a "$REPORT_FILE"

if [ "$SRC_SIZE" -gt 20000 ]; then
    pass "index.html pesa más de 20 KB"
else
    warn "index.html pesa menos de 20 KB; verificar que no esté truncado"
fi

grep -qi "<!DOCTYPE html" "$SRC_FILE" && pass "DOCTYPE HTML detectado" || fail "El archivo fuente no parece HTML válido"
grep -qi "GMP" "$SRC_FILE" && pass "Referencia GMP detectada" || fail "No se detecta referencia GMP"

# ============================================================
# 3. Backup
# ============================================================

step "Creando backup"

BACKUP_DIR="$PROJECT_DIR/backups/ui_fix_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "$STATIC_DIR/index.html" ]; then
    cp "$STATIC_DIR/index.html" "$BACKUP_DIR/index.previous.html"
    pass "Backup de UI anterior creado"
else
    warn "No existía app/static/index.html anterior"
fi

cp "$SRC_FILE" "$BACKUP_DIR/index.uploaded.html"
cp "$PROJECT_DIR/app/main.py" "$BACKUP_DIR/main.py.bak"

pass "Backup creado en: $BACKUP_DIR"

# ============================================================
# 4. Copiar index.html a app/static/
# ============================================================

step "Copiando index.html a app/static"

mkdir -p "$STATIC_DIR"
cp "$SRC_FILE" "$STATIC_DIR/index.html"

pass "Copiado: $SRC_FILE -> $STATIC_DIR/index.html"

# Reemplazar IP anterior por IP nueva
if grep -q "$OLD_IP" "$STATIC_DIR/index.html"; then
    sed -i "s/$OLD_IP/$PUBLIC_IP/g" "$STATIC_DIR/index.html"
    pass "IP anterior $OLD_IP reemplazada por $PUBLIC_IP"
else
    warn "No se encontró IP anterior $OLD_IP en index.html"
fi

# Reforzar cualquier URL localhost antigua si existiera
if grep -q "35.185.57.245" "$STATIC_DIR/index.html"; then
    sed -i "s/35\.185\.57\.245/$PUBLIC_IP/g" "$STATIC_DIR/index.html"
    pass "Reemplazo adicional de 35.185.57.245 aplicado"
fi

# Validar IP nueva
if grep -q "$PUBLIC_IP" "$STATIC_DIR/index.html"; then
    pass "index.html contiene IP nueva $PUBLIC_IP"
else
    fail "index.html no contiene IP nueva $PUBLIC_IP"
fi

# Validar que no quede IP vieja
if grep -q "$OLD_IP" "$STATIC_DIR/index.html"; then
    warn "Todavía aparece IP anterior $OLD_IP en index.html"
else
    pass "No quedan referencias a IP anterior $OLD_IP"
fi

# ============================================================
# 5. Verificar soporte static en main.py
# ============================================================

step "Verificando soporte de UI en app/main.py"

grep -q "StaticFiles" app/main.py && pass "StaticFiles detectado" || fail "StaticFiles no detectado en app/main.py"
grep -q "FileResponse" app/main.py && pass "FileResponse detectado" || fail "FileResponse no detectado en app/main.py"
grep -q "serve_ui" app/main.py && pass "serve_ui detectado" || warn "serve_ui no detectado"
grep -q "@app.get(\"/\"" app/main.py && pass "Ruta GET / detectada" || warn "Ruta GET / no detectada explícitamente"

# ============================================================
# 6. Verificar Dockerfile
# ============================================================

step "Verificando Dockerfile"

if grep -q "COPY app ./app" Dockerfile; then
    pass "Dockerfile copia app/ completo; incluye app/static/"
else
    warn "Dockerfile no muestra COPY app ./app"
    if grep -q "COPY app/static" Dockerfile; then
        pass "Dockerfile copia app/static explícitamente"
    else
        sed -i '/^EXPOSE 8000/i COPY app/static ./app/static' Dockerfile
        pass "Agregado COPY app/static ./app/static al Dockerfile"
    fi
fi

# ============================================================
# 7. Rebuild solo gmp-api
# ============================================================

step "Reconstruyendo SOLO gmp-api"

docker compose stop api 2>&1 | tee -a "$REPORT_FILE" || true
docker compose build --no-cache api 2>&1 | tee -a "$REPORT_FILE"
docker compose up -d api 2>&1 | tee -a "$REPORT_FILE"

pass "gmp-api reconstruido y levantado"

# ============================================================
# 8. Esperar health
# ============================================================

step "Esperando /health"

MAX_WAIT=120
WAITED=0

until curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; do
    sleep 4
    WAITED=$((WAITED+4))
    echo -n "."
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo ""
        fail "La API no respondió /health después de $MAX_WAIT segundos"
        break
    fi
done
echo ""

curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1 \
    && pass "API responde en /health" \
    || fail "API no responde en /health"

# ============================================================
# 9. Validar UI local
# ============================================================

step "Validando UI local"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/")
echo "  GET / -> HTTP $HTTP_CODE"

[ "$HTTP_CODE" = "200" ] && pass "GET / responde HTTP 200" || fail "GET / no responde HTTP 200"

if curl -s "http://localhost:$PORT/" | grep -qi "GMP"; then
    pass "UI local contiene GMP"
else
    fail "UI local no contiene GMP"
fi

if curl -s "http://localhost:$PORT/" | grep -q "$PUBLIC_IP"; then
    pass "UI local contiene IP nueva $PUBLIC_IP"
else
    warn "UI local no contiene IP nueva explícita"
fi

if curl -s "http://localhost:$PORT/" | grep -q "$OLD_IP"; then
    warn "UI local todavía contiene IP anterior $OLD_IP"
else
    pass "UI local no contiene IP anterior"
fi

# ============================================================
# 10. Validar dentro del contenedor
# ============================================================

step "Validando index.html dentro del contenedor"

if docker exec gmp-api test -f /app/app/static/index.html; then
    pass "index.html encontrado dentro del contenedor: /app/app/static/index.html"
    docker exec gmp-api ls -lh /app/app/static/index.html | tee -a "$REPORT_FILE"
elif docker exec gmp-api test -f /app/static/index.html; then
    pass "index.html encontrado dentro del contenedor: /app/static/index.html"
    docker exec gmp-api ls -lh /app/static/index.html | tee -a "$REPORT_FILE"
else
    fail "No se encontró index.html dentro del contenedor"
fi

# ============================================================
# 11. Validar IP pública nueva
# ============================================================

step "Validando acceso público con IP nueva"

PUBLIC_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://$PUBLIC_IP:$PORT/" 2>/dev/null || echo "TIMEOUT")
echo "  GET http://$PUBLIC_IP:$PORT/ -> $PUBLIC_CODE"

if [ "$PUBLIC_CODE" = "200" ]; then
    pass "UI pública accesible en IP nueva"
else
    warn "UI pública no respondió HTTP 200 en IP nueva. Si localhost funciona, revisar firewall GCP"
fi

PUBLIC_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://$PUBLIC_IP:$PORT/health" 2>/dev/null || echo "TIMEOUT")
echo "  GET http://$PUBLIC_IP:$PORT/health -> $PUBLIC_HEALTH"

if [ "$PUBLIC_HEALTH" = "200" ]; then
    pass "Health público accesible en IP nueva"
else
    warn "Health público no respondió HTTP 200 en IP nueva"
fi

# ============================================================
# 12. Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"
echo ""
echo "Reporte:"
echo "  $REPORT_FILE"
echo ""
echo "URL actual:"
echo "  http://$PUBLIC_IP:$PORT/"
echo ""

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 22 finalizó con fallos${NC}"
    echo "Revisar:"
    echo "  docker compose logs api --tail 80"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 22 completado con advertencias${NC}"
    echo "Si la UI carga en navegador con la IP nueva, puedes continuar."
    exit 0
fi

echo -e "${GREEN}✓ Script 22 completado correctamente${NC}"
exit 0
