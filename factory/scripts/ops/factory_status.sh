#!/usr/bin/env bash
# factory_status.sh — GMP AI Factory ops status check
# Cubre todos los stacks (Docker 1/2/3+), resources, audit y registry.
# Objetivo: PASS ≥ 20, WARN=0, FAIL=0
set -euo pipefail

PASS=0; WARN=0; FAIL=0
FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
FACTORY_ENV="$FACTORY_DIR/.env"
BASE_ENV="/home/ing_cpmo/.env"

# Colores
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; B='\033[0;34m'; NC='\033[0m'
BOLD='\033[1m'

pass()  { echo -e "  ${G}PASS${NC}  $1"; PASS=$((PASS+1));  }
warn()  { echo -e "  ${Y}WARN${NC}  $1"; WARN=$((WARN+1));  }
fail()  { echo -e "  ${R}FAIL${NC}  $1"; FAIL=$((FAIL+1));  }
info()  { echo -e "  ${B}INFO${NC}  $1"; }
section() { echo -e "\n${BOLD}${B}=== $1 ===${NC}"; }

# Leer API key con fallback (archivo → container env)
FACTORY_API_KEY=""
if [[ -f "$FACTORY_ENV" ]]; then
    FACTORY_API_KEY=$(grep -m1 "^FACTORY_API_KEY=" "$FACTORY_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
fi
if [[ -z "$FACTORY_API_KEY" ]]; then
    FACTORY_API_KEY=$(docker exec factory-api printenv FACTORY_API_KEY 2>/dev/null || true)
fi

_curl_check() {
    local label="$1" url="$2" key="${3:-}"
    local args=(-sf -o /dev/null -w "%{http_code}" --max-time 5)
    [[ -n "$key" ]] && args+=(-H "x-api-key: $key")
    local code
    code=$(curl "${args[@]}" "$url" 2>/dev/null || echo "000")
    if [[ "$code" == "200" ]]; then
        pass "$label → HTTP $code"
    elif [[ "$code" == "000" ]]; then
        fail "$label → sin respuesta (timeout/down)"
    else
        warn "$label → HTTP $code"
    fi
}

_json_field() {
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null || echo ""
}

# ─────────────────────────────────────────────────────
section "DOCKER 1 — Base GMP AI Copilot (:8000)"
# ─────────────────────────────────────────────────────
BASE_KEY=""
if [[ -f "$BASE_ENV" ]]; then
    BASE_KEY=$(grep -m1 "^GMP_API_KEY=" "$BASE_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
fi

for ctr in gmp-api gmp-postgres gmp-redis aria-ollama; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$ctr" 2>/dev/null || echo "missing")
    if [[ "$STATUS" == "running" ]]; then
        pass "docker ps: $ctr → running"
    else
        fail "docker ps: $ctr → $STATUS"
    fi
done

_curl_check "GET /health (base)" "http://localhost:8000/health" "$BASE_KEY"
_curl_check "GET /api/v1/audit/verify (base)" "http://localhost:8000/api/v1/audit/verify" "$BASE_KEY"
_curl_check "GET /api/v1/knowledge/stats (base)" "http://localhost:8000/api/v1/knowledge/stats" "$BASE_KEY"

# ─────────────────────────────────────────────────────
section "DOCKER 2 — Factory API (:9000)"
# ─────────────────────────────────────────────────────
for ctr in factory-api; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$ctr" 2>/dev/null || echo "missing")
    if [[ "$STATUS" == "running" ]]; then
        pass "docker ps: $ctr → running"
    else
        fail "docker ps: $ctr → $STATUS"
    fi
done

_curl_check "GET /health (factory)" "http://localhost:9000/health" "$FACTORY_API_KEY"
_curl_check "GET /api/v1/status/full" "http://localhost:9000/api/v1/status/full" "$FACTORY_API_KEY"
_curl_check "GET /api/v1/status/resources" "http://localhost:9000/api/v1/status/resources" "$FACTORY_API_KEY"
_curl_check "GET /api/v1/projects" "http://localhost:9000/api/v1/projects" "$FACTORY_API_KEY"
_curl_check "GET /api/v1/deployments" "http://localhost:9000/api/v1/deployments" "$FACTORY_API_KEY"

# Audit check via verify_chain local (distingue corrupción de fork concurrente)
AUDIT_DETAIL=$(python3 - <<'PYEOF' 2>/dev/null
import sys; sys.path.insert(0,'/home/ing_cpmo')
from factory.core.audit_writer import verify_chain
r = verify_chain()
print(f"{r['verified']}|{r['log_count']}|{r['hash_errors']}|{r['chain_errors']}")
PYEOF
)
A_OK=$(echo "$AUDIT_DETAIL" | cut -d'|' -f1)
A_CNT=$(echo "$AUDIT_DETAIL" | cut -d'|' -f2)
A_HERR=$(echo "$AUDIT_DETAIL" | cut -d'|' -f3)
A_CERR=$(echo "$AUDIT_DETAIL" | cut -d'|' -f4)
if [[ "$A_OK" == "True" ]]; then
    pass "Audit chain verificado ($A_CNT entradas)"
elif [[ "${A_HERR:-0}" == "0" && "${A_CERR:-0}" != "0" ]]; then
    warn "Audit chain: fork de escritura concurrente ($A_CERR fork, 0 hash_errors) — contenido auténtico"
else
    fail "Audit chain INVÁLIDO (hash_errors=${A_HERR:-?})"
fi

# ─────────────────────────────────────────────────────
section "DOCKER 3..N — Soluciones Custom"
# ─────────────────────────────────────────────────────
PORTS_FILE="$FACTORY_DIR/registry/ports.yaml"
if [[ ! -f "$PORTS_FILE" ]]; then
    warn "registry/ports.yaml no encontrado"
else
    # Leer allocations con python
    ALLOCATIONS=$(python3 -c "
import yaml, json
with open('$PORTS_FILE') as f:
    d = yaml.safe_load(f)
allocs = d.get('allocations', {})
for pid, info in allocs.items():
    port = info.get('ports', {}).get('api', '')
    if port:
        print(f'{pid}:{port}')
" 2>/dev/null || true)

    if [[ -z "$ALLOCATIONS" ]]; then
        warn "No hay soluciones custom en registry"
    else
        while IFS=: read -r pid port; do
            # U7: saltar health checks para proyectos sin deployment activo
            DEP_DIR="$FACTORY_DIR/deployments/$pid"
            if [[ ! -d "$DEP_DIR" ]]; then
                info "Solución custom '$pid': puerto $port reservado, sin deployment activo aún"
                continue
            fi

            # Container healthcheck
            CTRS=$(docker ps --filter "name=${pid}" --format "{{.Names}}" 2>/dev/null || true)
            if [[ -n "$CTRS" ]]; then
                pass "docker ps: ${pid} containers activos"
            else
                warn "docker ps: ${pid} — sin contenedores running"
            fi

            # API health
            DEP_ENV="$FACTORY_DIR/deployments/$pid/.env"
            DEP_KEY=""
            [[ -f "$DEP_ENV" ]] && DEP_KEY=$(grep -m1 "^GMP_API_KEY=" "$DEP_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
            _curl_check "GET /health ($pid :$port)" "http://localhost:$port/health" "$DEP_KEY"
            _curl_check "GET /api/v1/knowledge/stats ($pid)" "http://localhost:$port/api/v1/knowledge/stats" "$DEP_KEY"

            # Quality gates — lectura del reporte cacheado (READ-ONLY, sin ejecutar gates)
            # U5: reemplaza POST /quality-gates (que escribía audit) por GET /gates-report
            GATES_RESP=$(curl -sf --max-time 10 \
                -H "x-api-key: $FACTORY_API_KEY" \
                "http://localhost:9000/api/v1/deployments/$pid/gates-report" 2>/dev/null || echo '{}')
            G_PASS=$(echo "$GATES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('PASS',0))" 2>/dev/null || echo "?")
            G_FAIL=$(echo "$GATES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('FAIL',0))" 2>/dev/null || echo "?")
            G_SKIP=$(echo "$GATES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('summary',{}).get('SKIPPED',0))" 2>/dev/null || echo "?")
            if [[ "$G_FAIL" == "0" && "$G_PASS" != "?" && "$G_PASS" != "0" ]]; then
                pass "Quality gates ($pid): PASS=$G_PASS FAIL=$G_FAIL SKIPPED=$G_SKIP (reporte cacheado)"
            elif [[ "$G_FAIL" == "?" || "$G_PASS" == "0" ]]; then
                warn "Quality gates ($pid): sin reporte cacheado — correr gates manualmente"
            else
                fail "Quality gates ($pid): PASS=$G_PASS FAIL=$G_FAIL SKIPPED=$G_SKIP"
            fi
        done <<< "$ALLOCATIONS"
    fi
fi

# ─────────────────────────────────────────────────────
section "RESOURCES — RAM / Disco / Política"
# ─────────────────────────────────────────────────────
RES_RESP=$(curl -sf --max-time 5 -H "x-api-key: $FACTORY_API_KEY" \
    "http://localhost:9000/api/v1/status/resources" 2>/dev/null || echo '{}')

COMPLIANT=$(echo "$RES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('compliant', False))" 2>/dev/null || echo "False")
MEM_PCT=$(echo "$RES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('memory',{}).get('used_pct','?'))" 2>/dev/null || echo "?")
DISK_PCT=$(echo "$RES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('disk',{}).get('used_pct','?'))" 2>/dev/null || echo "?")
CUSTOM_N=$(echo "$RES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('custom_solutions',{}).get('active','?'))" 2>/dev/null || echo "?")
CUSTOM_MAX=$(echo "$RES_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('custom_solutions',{}).get('max_allowed','2'))" 2>/dev/null || echo "2")

if [[ "$COMPLIANT" == "True" ]]; then
    pass "Recursos dentro de política (RAM ${MEM_PCT}%, Disco ${DISK_PCT}%, Custom ${CUSTOM_N}/${CUSTOM_MAX})"
else
    warn "Recursos fuera de política — RAM ${MEM_PCT}%, Disco ${DISK_PCT}%, Custom ${CUSTOM_N}/${CUSTOM_MAX}"
fi

# RAM check independiente via /proc/meminfo
MEM_TOTAL=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
MEM_AVAIL=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
MEM_USED_MB=$(( (MEM_TOTAL - MEM_AVAIL) / 1024 ))
MEM_TOTAL_MB=$(( MEM_TOTAL / 1024 ))
if [[ $MEM_USED_MB -lt $((MEM_TOTAL_MB * 85 / 100)) ]]; then
    pass "RAM: ${MEM_USED_MB}MB / ${MEM_TOTAL_MB}MB usado"
else
    warn "RAM alta: ${MEM_USED_MB}MB / ${MEM_TOTAL_MB}MB"
fi

# Disco check
DISK_USED=$(df / --output=pcent | tail -1 | tr -d ' %')
if [[ "$DISK_USED" -lt 80 ]]; then
    pass "Disco: ${DISK_USED}% usado"
else
    warn "Disco: ${DISK_USED}% — consider cleanup"
fi

# ─────────────────────────────────────────────────────
section "OLLAMA — Modelos disponibles"
# ─────────────────────────────────────────────────────
OLLAMA_RESP=$(curl -sf --max-time 8 "http://localhost:11434/api/tags" 2>/dev/null || echo '{}')
MODEL_COUNT=$(echo "$OLLAMA_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('models', [])))" 2>/dev/null || echo "0")
if [[ "$MODEL_COUNT" -gt 0 ]]; then
    MODELS=$(echo "$OLLAMA_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join(m['name'] for m in d.get('models',[])[:3]))" 2>/dev/null || echo "?")
    pass "Ollama: $MODEL_COUNT modelos ($MODELS)"
else
    fail "Ollama: sin modelos o inaccesible"
fi

# ─────────────────────────────────────────────────────
section "WORKSPACES Y RELEASES"
# ─────────────────────────────────────────────────────
WS_DIR="$FACTORY_DIR/workspaces"
REL_DIR="$FACTORY_DIR/releases"

WS_COUNT=$(ls "$WS_DIR" 2>/dev/null | wc -l || echo 0)
pass "Workspaces activos: $WS_COUNT"

if [[ -d "$REL_DIR" ]]; then
    REL_COUNT=$(find "$REL_DIR" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | wc -l || echo 0)
    pass "Releases: $REL_COUNT versiones en total"
else
    warn "Directorio releases/ no existe"
fi

# ─────────────────────────────────────────────────────
section "RUNTIME CONFIG"
# ─────────────────────────────────────────────────────
RUNTIME_CFG="$FACTORY_DIR/runtime/runtime_config.yaml"
if [[ -f "$RUNTIME_CFG" ]]; then
    HEADLESS=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUNTIME_CFG')); print(d.get('headless_enabled', False))" 2>/dev/null || echo "?")
    MODE=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUNTIME_CFG')); print(d.get('default_mode', '?'))" 2>/dev/null || echo "?")
    if [[ "$HEADLESS" == "False" || "$HEADLESS" == "false" ]]; then
        pass "runtime_config: headless=$HEADLESS, mode=$MODE"
    else
        warn "runtime_config: headless ACTIVO ($HEADLESS) — verificar intención"
    fi
else
    warn "runtime_config.yaml no encontrado"
fi

# ─────────────────────────────────────────────────────
echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  RESUMEN FINAL${NC}"
echo -e "  ${G}PASS${NC} $PASS   ${Y}WARN${NC} $WARN   ${R}FAIL${NC} $FAIL"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ $FAIL -gt 0 ]]; then
    exit 2
elif [[ $WARN -gt 0 ]]; then
    exit 1
else
    exit 0
fi
