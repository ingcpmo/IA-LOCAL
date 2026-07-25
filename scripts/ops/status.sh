#!/bin/bash
# ============================================================
# OPS — Estado resumido GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
# Uso: bash scripts/ops/status.sh
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
OLLAMA="http://localhost:11434"

pass(){ echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS+=1)); }
warn(){ echo -e "  ${YELLOW}[WARN]${NC} $1"; ((WARN+=1)); }
fail(){ echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL+=1)); }
sec(){ echo -e "\n${BLUE}${BOLD}▶ $1${NC}"; }

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  OPS — Estado resumido GMP AI Copilot${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

sec "Raíz del proyecto"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
    pass "Directorio raíz encontrado: $PROJECT_DIR"
else
    fail "No existe $PROJECT_DIR"
fi

sec "Servicios base"
curl -fsS "$API/health" >/dev/null 2>&1 && pass "API responde en $API/health" || fail "API no responde"
curl -fsS "$OLLAMA/api/tags" >/dev/null 2>&1 && pass "Ollama responde en $OLLAMA" || fail "Ollama no responde"

docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres pg_isready -q 2>/dev/null \
    && pass "PostgreSQL responde" || fail "PostgreSQL no responde"

docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG \
    && pass "Redis responde PONG" || fail "Redis no responde"

sec "Health API"
HEALTH="$(curl -fsS "$API/health" 2>/dev/null || echo '{}')"
echo "  $HEALTH"

echo "$HEALTH" | grep -q '"ollama":"ok"' \
    && pass "API conectada a Ollama" || warn "API no reporta Ollama OK"

sec "Systemd"
systemctl is-enabled gmp-copilot >/dev/null 2>&1 && pass "gmp-copilot habilitado" || warn "gmp-copilot no habilitado"
systemctl is-active gmp-copilot >/dev/null 2>&1 && pass "gmp-copilot activo" || warn "gmp-copilot no activo"

sec "Docker"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || warn "No se pudo consultar Docker"

sec "Recursos"
free -h | sed 's/^/  /'
df -h / | sed 's/^/  /'

RAM_PCT="$(free | awk '/Mem:/{printf "%.0f", $3/$2*100}')"
if (( RAM_PCT > 85 )); then
    warn "RAM al ${RAM_PCT}% — riesgo OOM"
elif (( RAM_PCT > 70 )); then
    warn "RAM al ${RAM_PCT}% — monitorear"
else
    pass "RAM al ${RAM_PCT}% — OK"
fi

DISK_PCT="$(df / | awk 'NR==2{gsub("%","",$5); print $5}')"
if (( DISK_PCT > 90 )); then
    fail "Disco al ${DISK_PCT}%"
elif (( DISK_PCT > 75 )); then
    warn "Disco al ${DISK_PCT}%"
else
    pass "Disco al ${DISK_PCT}% — OK"
fi

sec "Backups"
if [ -d "$PROJECT_DIR/data/backups" ]; then
    ls -lah "$PROJECT_DIR/data/backups" | sed 's/^/  /'
    COUNT="$(find "$PROJECT_DIR/data/backups" -type f | wc -l)"
    [ "$COUNT" -gt 0 ] && pass "Backups encontrados: $COUNT" || warn "No hay backups"
else
    warn "No existe data/backups"
fi

sec "Firewall"
sudo ufw status numbered | sed 's/^/  /' || warn "No se pudo consultar UFW"

sec "Pendientes funcionales"
# gmp-api valida su propia auth vía header X-API-Key (ver app/main.py,
# verify_api_key) -- NO es el basicauth de Mission Control (ese es un
# servicio distinto, puerto 9000, ver /etc/caddy/Caddyfile). La key se lee
# en runtime del propio contenedor, nunca se hardcodea ni se imprime.
API_KEY="$(docker inspect gmp-api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | grep '^GMP_API_KEY=' | cut -d= -f2-)"

if [ -z "$API_KEY" ]; then
    warn "GMP_API_KEY no resuelto desde el contenedor gmp-api -- endpoints protegidos se probaran sin auth"
fi

# /api/v1/query hace inferencia LLM real via Ollama (CPU, sin CUDA por
# restriccion del proyecto) -- puede tardar varios minutos. Timeout amplio
# deliberado; un 000 aqui es timeout real, no fallo de auth.
QUERY_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$API/api/v1/query" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"question":"health check","agent":"auto"}' \
    --max-time 240 2>/dev/null || echo 000)"

[ "$QUERY_CODE" = "200" ] && pass "POST /api/v1/query disponible" \
    || warn "Pendiente: POST /api/v1/query HTTP $QUERY_CODE"

K_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" \
    "$API/api/v1/knowledge/stats" --max-time 15 2>/dev/null || echo 000)"
[ "$K_CODE" = "200" ] && pass "GET /api/v1/knowledge/stats disponible" || warn "Pendiente: GET /api/v1/knowledge/stats HTTP $K_CODE"

A_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" \
    "$API/api/v1/audit/verify" --max-time 15 2>/dev/null || echo 000)"
[ "$A_CODE" = "200" ] && pass "GET /api/v1/audit/verify disponible" || warn "Pendiente: GET /api/v1/audit/verify HTTP $A_CODE"

P_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" \
    "$API/api/v1/protocol-template/IQ" --max-time 15 2>/dev/null || echo 000)"
[ "$P_CODE" = "200" ] && pass "GET /api/v1/protocol-template/IQ disponible" || warn "Pendiente: GET /api/v1/protocol-template/IQ HTTP $P_CODE"

[ -f "$PROJECT_DIR/knowledge/retriever.py" ] && pass "knowledge/retriever.py existe" || warn "Pendiente: knowledge/retriever.py"
[ -f "$PROJECT_DIR/tests/test_agents.py" ] && pass "tests/test_agents.py existe" || warn "Pendiente: tests/test_agents.py"

sec "URLs útiles"
echo -e "  ${BLUE}API:${NC}     $API"
echo -e "  ${BLUE}Health:${NC}  $API/health"
echo -e "  ${BLUE}Ollama:${NC}  $OLLAMA"
echo -e "  ${BLUE}Logs:${NC}    $PROJECT_DIR/logs"
echo -e "  ${BLUE}Backup:${NC}  $PROJECT_DIR/data/backups"

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Estado general con fallos críticos${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Estado operativo con advertencias funcionales${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Estado general OK${NC}"
exit 0
