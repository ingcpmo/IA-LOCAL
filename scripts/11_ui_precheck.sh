#!/bin/bash
# ============================================================
# Script 11 — Precheck interfaz visual
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
#
# Objetivo:
#   - Revisar estructura actual del proyecto
#   - Verificar si existe frontend/static
#   - Revisar Dockerfile
#   - Revisar CORS y rutas en app/main.py
#   - Revisar requirements.txt
#   - Revisar contenedores, UFW y health API
#   - Definir archivos que requieren creación/modificación
#
# Uso:
#   bash scripts/11_ui_precheck.sh
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
REPORT_DIR="$PROJECT_DIR/logs/ui"
REPORT_FILE="$REPORT_DIR/ui_precheck_$(date +%Y%m%d_%H%M%S).log"

pass(){ echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS+=1)); }
warn(){ echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN+=1)); }
fail(){ echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL+=1)); }
sec(){ echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }

run_report() {
    local title="$1"
    shift
    {
        echo ""
        echo "================================================================"
        echo "$title"
        echo "================================================================"
        echo "\$ $*"
        "$@" 2>&1 || true
    } | tee -a "$REPORT_FILE"
}

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  Script 11 — Precheck interfaz visual${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Preparar reporte
# ============================================================

sec "Preparando reporte"

if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    pass "Directorio raíz encontrado: $PROJECT_DIR"
else
    fail "No existe el directorio raíz esperado: $PROJECT_DIR"
fi

mkdir -p "$REPORT_DIR"
: > "$REPORT_FILE"
pass "Reporte creado: $REPORT_FILE"

{
    echo "GMP AI Copilot — UI Precheck"
    echo "Fecha: $(date)"
    echo "Host: $(hostname)"
    echo "Usuario: $(whoami)"
    echo "Proyecto: $PROJECT_DIR"
} >> "$REPORT_FILE"

# ============================================================
# Estructura Python
# ============================================================

sec "Revisando estructura Python del proyecto"

run_report "Estructura del proyecto — archivos Python" \
    find "$PROJECT_DIR" -name "*.py" -not -path "*/.venv/*" -not -path "*/logs/*"

if find "$PROJECT_DIR" -name "*.py" -not -path "*/.venv/*" -not -path "*/logs/*" | grep -q "app/main.py"; then
    pass "app/main.py encontrado"
else
    fail "app/main.py no encontrado"
fi

if [ -d "$PROJECT_DIR/app" ]; then
    pass "Directorio app/ existe"
    run_report "Contenido de app/" ls -la "$PROJECT_DIR/app/"
else
    fail "Directorio app/ no existe"
fi

# ============================================================
# Revisar frontend/static
# ============================================================

sec "Revisando interfaz estática"

if [ -d "$PROJECT_DIR/app/static" ]; then
    pass "app/static/ existe"
    run_report "Contenido de app/static/" ls -la "$PROJECT_DIR/app/static/"
else
    warn "app/static/ NO existe todavía"
fi

if [ -f "$PROJECT_DIR/app/static/index.html" ]; then
    pass "app/static/index.html existe"
else
    warn "app/static/index.html no existe"
fi

if [ -f "$PROJECT_DIR/app/static/app.js" ]; then
    pass "app/static/app.js existe"
else
    warn "app/static/app.js no existe"
fi

if [ -f "$PROJECT_DIR/app/static/styles.css" ]; then
    pass "app/static/styles.css existe"
else
    warn "app/static/styles.css no existe"
fi

# ============================================================
# Dockerfile
# ============================================================

sec "Revisando Dockerfile"

if [ -f "$PROJECT_DIR/Dockerfile" ]; then
    pass "Dockerfile encontrado"
    run_report "Dockerfile actual" cat "$PROJECT_DIR/Dockerfile"

    if grep -q "COPY.*app" "$PROJECT_DIR/Dockerfile"; then
        pass "Dockerfile copia app/"
    else
        warn "Dockerfile no muestra COPY app/"
    fi

    if grep -q "static" "$PROJECT_DIR/Dockerfile"; then
        pass "Dockerfile menciona static"
    else
        warn "Dockerfile no menciona static explícitamente"
    fi
else
    fail "Dockerfile no encontrado"
fi

# ============================================================
# Revisar CORS y rutas
# ============================================================

sec "Revisando CORS y rutas en app/main.py"

if [ -f "$PROJECT_DIR/app/main.py" ]; then
    run_report "CORS y rutas detectadas en main.py" \
        sh -c "grep -n \"CORSMiddleware\\|allow_origins\\|StaticFiles\\|FileResponse\\|serve_ui\\|@app.get.*/\" '$PROJECT_DIR/app/main.py' 2>/dev/null | head -40"

    if grep -q "CORSMiddleware" "$PROJECT_DIR/app/main.py"; then
        pass "CORSMiddleware detectado"
    else
        warn "CORSMiddleware no detectado en app/main.py"
    fi

    if grep -q "StaticFiles" "$PROJECT_DIR/app/main.py"; then
        pass "StaticFiles detectado"
    else
        warn "StaticFiles no detectado"
    fi

    if grep -q "FileResponse" "$PROJECT_DIR/app/main.py"; then
        pass "FileResponse detectado"
    else
        warn "FileResponse no detectado"
    fi

    if grep -q '@app.get("/")' "$PROJECT_DIR/app/main.py"; then
        pass "Ruta GET / detectada"
    else
        warn "Ruta GET / no detectada"
    fi

    if grep -q "/health" "$PROJECT_DIR/app/main.py"; then
        pass "Ruta /health detectada"
    else
        fail "Ruta /health no detectada"
    fi
else
    fail "No se puede revisar app/main.py porque no existe"
fi

# ============================================================
# Requirements
# ============================================================

sec "Revisando requirements.txt"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pass "requirements.txt encontrado"
    run_report "requirements.txt" cat "$PROJECT_DIR/requirements.txt"

    if grep -q "fastapi" "$PROJECT_DIR/requirements.txt"; then
        pass "FastAPI declarado en requirements"
    else
        fail "FastAPI no aparece en requirements"
    fi

    if grep -q "uvicorn" "$PROJECT_DIR/requirements.txt"; then
        pass "Uvicorn declarado en requirements"
    else
        fail "Uvicorn no aparece en requirements"
    fi
else
    fail "requirements.txt no encontrado"
fi

# ============================================================
# Docker Compose y contenedores
# ============================================================

sec "Revisando contenedores"

if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    pass "docker-compose.yml encontrado"
else
    fail "docker-compose.yml no encontrado"
fi

run_report "Estado de contenedores docker compose" docker compose ps

if docker ps --format '{{.Names}}' | grep -q '^gmp-api$'; then
    pass "Contenedor gmp-api activo"
else
    fail "Contenedor gmp-api no está activo"
fi

if docker ps --format '{{.Names}}' | grep -q '^gmp-postgres$'; then
    pass "Contenedor gmp-postgres activo"
else
    fail "Contenedor gmp-postgres no está activo"
fi

if docker ps --format '{{.Names}}' | grep -q '^gmp-redis$'; then
    pass "Contenedor gmp-redis activo"
else
    fail "Contenedor gmp-redis no está activo"
fi

# ============================================================
# UFW
# ============================================================

sec "Revisando UFW"

run_report "UFW puertos" sudo ufw status

if sudo ufw status | grep -q "8000/tcp"; then
    pass "UFW permite puerto 8000"
else
    warn "UFW no muestra puerto 8000 permitido"
fi

if sudo ufw status | grep -q "80/tcp"; then
    pass "UFW permite puerto 80"
else
    warn "UFW no muestra puerto 80 permitido"
fi

# ============================================================
# Health API
# ============================================================

sec "Revisando health actual de la API"

HEALTH="$(curl -s http://localhost:8000/health 2>/dev/null || echo '{}')"
echo "$HEALTH" | python3 -m json.tool 2>/dev/null | tee -a "$REPORT_FILE" || echo "API no responde" | tee -a "$REPORT_FILE"

if echo "$HEALTH" | grep -q '"api":"ok"'; then
    pass "API health reporta api=ok"
else
    fail "API health no reporta api=ok"
fi

if echo "$HEALTH" | grep -q '"ollama":"ok"'; then
    pass "API health reporta ollama=ok"
else
    warn "API health no reporta ollama=ok"
fi

if echo "$HEALTH" | grep -q '"postgres":"ok"'; then
    pass "API health reporta postgres=ok"
else
    warn "API health no reporta postgres=ok"
fi

if echo "$HEALTH" | grep -q '"redis":"ok"'; then
    pass "API health reporta redis=ok"
else
    warn "API health no reporta redis=ok"
fi

# ============================================================
# Definición de archivos requeridos para UI
# ============================================================

sec "Definiendo archivos requeridos para la interfaz visual"

echo ""
echo "Archivos que probablemente deben CREARSE:"
echo "  /home/ing_cpmo/app/static/index.html"
echo "  /home/ing_cpmo/app/static/app.js"
echo "  /home/ing_cpmo/app/static/styles.css"

{
    echo ""
    echo "================================================================"
    echo "DEFINICIÓN TÉCNICA — Archivos a crear/modificar"
    echo "================================================================"
    echo ""
    echo "CREAR:"
    echo "  app/static/index.html"
    echo "  app/static/app.js"
    echo "  app/static/styles.css"
    echo ""
    echo "MODIFICAR si no existe soporte static:"
    echo "  app/main.py"
    echo ""
    echo "Revisar solo si Dockerfile no copia app/:"
    echo "  Dockerfile"
    echo ""
    echo "No tocar:"
    echo "  PostgreSQL"
    echo "  Redis"
    echo "  Ollama"
    echo "  UFW, salvo que se decida exponer puerto 80"
    echo "  Contenedores aria-*"
    echo "  Contenedores hotelbot-*"
} | tee -a "$REPORT_FILE"

if [ ! -d "$PROJECT_DIR/app/static" ]; then
    warn "Crear directorio app/static/"
fi

if [ -f "$PROJECT_DIR/app/main.py" ]; then
    if ! grep -q "StaticFiles" "$PROJECT_DIR/app/main.py"; then
        warn "Modificar app/main.py para montar archivos estáticos"
    fi

    if ! grep -q "FileResponse" "$PROJECT_DIR/app/main.py"; then
        warn "Modificar app/main.py para servir index.html en /"
    fi

    if ! grep -q "CORSMiddleware" "$PROJECT_DIR/app/main.py"; then
        warn "Evaluar CORS si la UI se sirve desde origen distinto"
    fi
fi

# ============================================================
# Resumen final
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

echo ""
echo -e "Reporte generado:"
echo -e "  ${BLUE}$REPORT_FILE${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Precheck UI finalizó con fallos críticos${NC}"
    echo "  No construir UI hasta corregir fallos base."
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Precheck UI completado con advertencias${NC}"
    echo "  Se puede continuar si las advertencias corresponden a archivos UI aún no creados."
    exit 0
fi

echo -e "${GREEN}✓ Precheck UI completado correctamente${NC}"
exit 0
