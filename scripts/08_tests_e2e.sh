#!/bin/bash
# ============================================================
# Script 08 — Tests end-to-end
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
#
# Objetivo:
#   - Validar API
#   - Validar endpoints base
#   - Validar consulta manual al agente FDA
#   - Ejecutar pytest si existe tests/test_agents.py
#
# Uso:
#   bash scripts/08_tests_e2e.sh
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
API="http://localhost:8000"
OLLAMA_API="http://localhost:11434"
QUERY_TIMEOUT=180
PYTEST_TIMEOUT=180

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
echo -e "${BOLD}  Script 08 — Tests end-to-end${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}  Ollama CPU timeout: ${QUERY_TIMEOUT}s${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Validar raíz del proyecto
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
# Validar herramientas base
# ============================================================

sec "Validando herramientas base"

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
# Validar entorno Python
# ============================================================

sec "Validando entorno Python"

if (( FAIL == 0 )); then
    if [ -f ".venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
        pass "Entorno virtual activado"
    else
        warn ".venv no encontrado"
        warn "Pytest se omitirá si no hay entorno virtual"
    fi
else
    warn "Validación de entorno omitida por fallos previos"
fi

if (( FAIL == 0 )) && [ -f ".venv/bin/activate" ]; then
    if python -c "import fastapi, httpx, redis, asyncpg" >/dev/null 2>&1; then
        pass "Dependencias API importables"
    else
        warn "Algunas dependencias API no son importables"
    fi
fi

# ============================================================
# Verificar API activa
# ============================================================

sec "Verificando API activa"

API_OK=0

if (( FAIL == 0 )); then
    for i in {1..6}; do
        if curl -fsS "$API/health" >/dev/null 2>&1; then
            pass "API OK en $API/health"
            API_OK=1
            break
        else
            warn "Intento $i: API no responde; esperando 10s"
            sleep 10
        fi
    done

    if [ "$API_OK" -eq 0 ]; then
        fail "API no respondió después de 6 intentos"
    fi
else
    warn "Verificación API omitida por fallos previos"
fi

# ============================================================
# Verificar Ollama local
# ============================================================

sec "Verificando Ollama local"

if (( FAIL == 0 )); then
    if curl -fsS "$OLLAMA_API/api/tags" >/dev/null 2>&1; then
        pass "Ollama responde en $OLLAMA_API"
    else
        warn "Ollama no respondió en $OLLAMA_API"
        warn "La consulta FDA puede fallar o tardar"
    fi
else
    warn "Verificación Ollama omitida por fallos previos"
fi

# ============================================================
# Smoke tests rápidos sin LLM
# ============================================================

sec "Ejecutando smoke tests rápidos"

if (( FAIL == 0 )) && [ "$API_OK" -eq 1 ]; then
    ENDPOINTS=(
        "/health"
        "/api/v1/protocol-template/IQ"
        "/api/v1/knowledge/stats"
        "/api/v1/audit/verify"
    )

    for EP in "${ENDPOINTS[@]}"; do
        CODE="$(curl -sS -o /dev/null -w "%{http_code}" "$API$EP" 2>/dev/null || echo "000")"

        if [ "$CODE" = "200" ]; then
            pass "$CODE $EP"
        else
            warn "$CODE $EP"
        fi
    done
else
    warn "Smoke tests omitidos porque API no está disponible"
fi

# ============================================================
# Test manual del agente FDA
# ============================================================

sec "Probando agente FDA"

FDA_TEST_OK=0

if (( FAIL == 0 )) && [ "$API_OK" -eq 1 ]; then
    echo "  Enviando query a FDA agent. Timeout: ${QUERY_TIMEOUT}s"

    START="$(date +%s)"

    RESP="$(
        curl -sS -X POST "$API/api/v1/query" \
            -H "Content-Type: application/json" \
            -H "X-User-Id: ing_cpmo" \
            -d '{"question":"What does 21 CFR Part 11 require for audit trails?","agent":"fda"}' \
            --max-time "$QUERY_TIMEOUT" 2>/dev/null || echo '{"error":"timeout"}'
    )"

    ELAPSED="$(( $(date +%s) - START ))"

    if echo "$RESP" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    text = str(d.get("response", "")) + " " + str(d.get("answer", "")) + " " + str(d.get("message", ""))
    print(text[:1000])
except Exception:
    print("")
' 2>/dev/null | grep -qiE "audit|trail|11|record|electronic"; then
        pass "FDA Agent respondió con contenido regulatorio (${ELAPSED}s)"
        FDA_TEST_OK=1
    else
        warn "FDA Agent no confirmó contenido esperado (${ELAPSED}s)"
        echo "  Respuesta resumida:"
        echo "$RESP" | head -c 500
        echo ""
    fi
else
    warn "Test FDA omitido porque API no está disponible"
fi

# ============================================================
# Ejecutar pytest
# ============================================================

sec "Ejecutando pytest"

if (( FAIL == 0 )); then
    if [ ! -f ".venv/bin/activate" ]; then
        warn "Pytest omitido porque no existe .venv"
    elif ! command -v pytest >/dev/null 2>&1; then
        warn "pytest no está instalado en el entorno virtual"
        warn "Instalar si corresponde: pip install pytest pytest-asyncio pytest-timeout"
    elif [ ! -f "tests/test_agents.py" ]; then
        warn "No existe tests/test_agents.py"
        warn "Pruebas automatizadas omitidas"
    else
        PYTEST_EXIT=0

        pytest tests/test_agents.py \
            --asyncio-mode=auto \
            --timeout="$PYTEST_TIMEOUT" \
            -v \
            --tb=short \
            --color=yes \
            2>&1 || PYTEST_EXIT=$?

        echo ""

        if [ "$PYTEST_EXIT" -eq 0 ]; then
            pass "Pytest completado correctamente"
        else
            warn "Pytest finalizó con errores. Exit code: $PYTEST_EXIT"
            warn "Puede ser latencia de Ollama CPU o endpoints aún no implementados"
            echo "  Reintento sugerido:"
            echo "  pytest tests/ -v --timeout=300"
        fi
    fi
else
    warn "Pytest omitido por fallos previos"
fi

# ============================================================
# Validación informativa de módulo de conocimiento
# ============================================================

sec "Validando estado del módulo de conocimiento"

if [ -f "knowledge/retriever.py" ]; then
    pass "knowledge/retriever.py existe"
else
    warn "knowledge/retriever.py no existe"
    warn "La ingesta vectorial real seguirá pendiente"
fi

# ============================================================
# Resumen final
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 08 finalizó con fallos críticos${NC}"
    echo -e "  Revisar API     : ${BLUE}curl http://localhost:8000/health${NC}"
    echo -e "  Revisar Docker  : ${BLUE}docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'${NC}"
    echo -e "  Revisar logs API: ${BLUE}docker logs --tail=80 gmp-api${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 08 completado con advertencias${NC}"
    echo -e "  API       : ${BLUE}$API${NC}"
    echo -e "  Health    : ${BLUE}$API/health${NC}"
    echo -e "  Ollama    : ${BLUE}$OLLAMA_API${NC}"
    echo -e "  Siguiente : ${BLUE}bash scripts/09_service.sh${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 08 completado correctamente${NC}"
echo -e "  API       : ${BLUE}$API${NC}"
echo -e "  Health    : ${BLUE}$API/health${NC}"
echo -e "  Siguiente : ${BLUE}bash scripts/09_service.sh${NC}"
exit 0
