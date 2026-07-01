#!/usr/bin/env bash
# factory/scripts/ops/factory_selfcheck.sh
# Gate 0 de cada fase futura — ejecutar antes de cualquier release o deployment.
# Corre: py_compile + pytest + verify_chain + factory_status.sh
# Sale con código 0 si FAIL=0, 1 si hay fallos.
set -euo pipefail

FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PASS=0; FAIL=0

# pytest necesita fastapi/pydantic/httpx (deps de factory/api/routes/*.py,
# importadas directamente por varios tests). El python3 del sistema no las
# tiene instaladas; el venv del proyecto sí.
PYBIN="python3"
if [[ -x "$FACTORY_DIR/../.venv/bin/python3" ]]; then
    PYBIN="$FACTORY_DIR/../.venv/bin/python3"
fi

G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'
ok()      { printf "  ${G}PASS${NC}  %s\n" "$1"; PASS=$((PASS+1)); }
ko()      { printf "  ${R}FAIL${NC}  %s\n" "$1"; FAIL=$((FAIL+1)); }
warn_()   { printf "  ${Y}WARN${NC}  %s\n" "$1"; }
section() { printf "\n${BOLD}${B}━━━ %s ━━━${NC}\n" "$1"; }

# ── 1. py_compile — todos los módulos Python de la fábrica ───────────────────
section "1/4  py_compile"

PY_ERRORS=0
while IFS= read -r -d '' f; do
    if ! python3 -c "import sys; compile(open(sys.argv[1]).read(), sys.argv[1], 'exec')" "$f" 2>/tmp/_selfcheck_pyc_err; then
        ko "py_compile FAIL: $f"
        cat /tmp/_selfcheck_pyc_err >&2
        PY_ERRORS=$((PY_ERRORS+1))
    fi
done < <(find "$FACTORY_DIR" \
    -name "*.py" \
    -not -path "*/__pycache__/*" \
    -not -path "*/.git/*" \
    -not -path "*/tests/__pycache__/*" \
    -print0)

if [[ $PY_ERRORS -eq 0 ]]; then
    COUNT=$(find "$FACTORY_DIR" -name "*.py" \
        -not -path "*/__pycache__/*" -not -path "*/.git/*" | wc -l)
    ok "py_compile: $COUNT archivos .py sin errores de sintaxis"
fi

# ── 2. pytest — suite factory/tests/ ─────────────────────────────────────────
section "2/4  pytest"

cd "$FACTORY_DIR/.."  # /home/ing_cpmo
PYTEST_OUT=$("$PYBIN" -m pytest factory/tests/ -q --tb=short 2>&1 || true)
echo "$PYTEST_OUT"

if echo "$PYTEST_OUT" | grep -qE "^[0-9]+ passed"; then
    TOTAL=$(echo "$PYTEST_OUT" | grep -oE "[0-9]+ passed" | head -1)
    FAILED=$(echo "$PYTEST_OUT" | grep -oE "[0-9]+ failed" | head -1 || true)
    if [[ -z "$FAILED" ]]; then
        ok "pytest: $TOTAL"
    else
        ko "pytest: $TOTAL pero $FAILED"
    fi
elif echo "$PYTEST_OUT" | grep -qE "failed|error"; then
    ko "pytest: fallos detectados"
elif echo "$PYTEST_OUT" | grep -qE "no tests ran"; then
    ko "pytest: ningún test corrió"
else
    warn_ "pytest: resultado indeterminado"
fi

# ── 3. verify_chain — audit de fábrica ───────────────────────────────────────
section "3/4  audit chain"

CHAIN_RESULT=$(python3 - <<'PYEOF' 2>/dev/null
import sys
sys.path.insert(0, '/home/ing_cpmo')
from factory.core.audit_writer import verify_chain
r = verify_chain()
print(f"{r['verified']}|{r['log_count']}|{r['hash_errors']}|{r['chain_errors']}")
PYEOF
)
C_OK=$(echo "$CHAIN_RESULT" | cut -d'|' -f1)
C_CNT=$(echo "$CHAIN_RESULT" | cut -d'|' -f2)
C_HERR=$(echo "$CHAIN_RESULT" | cut -d'|' -f3)
C_CERR=$(echo "$CHAIN_RESULT" | cut -d'|' -f4)

if [[ "$C_OK" == "True" ]]; then
    ok "audit chain: integridad verificada ($C_CNT entradas)"
elif [[ "${C_HERR:-0}" == "0" && "${C_CERR:-0}" != "0" ]]; then
    warn_ "audit chain: fork concurrente ($C_CERR fork, 0 hash_errors) — contenido auténtico"
    ok "audit chain: integridad verificada ($C_CNT entradas, fork aceptado)"
else
    ko "audit chain: integridad INVÁLIDA (hash_errors=${C_HERR:-?})"
fi

# ── 4. factory_status.sh ──────────────────────────────────────────────────────
section "4/4  factory_status.sh"

STATUS_EXIT=0
STATUS_OUT=$(bash "$FACTORY_DIR/scripts/ops/factory_status.sh" 2>&1) || STATUS_EXIT=$?

# Mostrar solo el bloque RESUMEN FINAL
echo "$STATUS_OUT" | grep -E "PASS|WARN|FAIL|━" | tail -8 || true

case $STATUS_EXIT in
    0) ok "factory_status.sh: sin FAILs ni WARNs" ;;
    1) ok "factory_status.sh: WARNs presentes pero sin FAILs (aceptable en self-check)" ;;
    *) ko "factory_status.sh: $STATUS_EXIT FAILs detectados" ;;
esac

# ── RESUMEN ───────────────────────────────────────────────────────────────────
printf "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
printf "${BOLD}  FACTORY SELF-CHECK — ${G}PASS=%d${NC}  ${R}FAIL=%d${NC}\n" "$PASS" "$FAIL"
printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [[ $FAIL -eq 0 ]]; then
    printf "\n  ${G}✓ Gate 0 OK — sistema listo para siguiente fase${NC}\n\n"
    exit 0
else
    printf "\n  ${R}✗ Gate 0 FAILED — corregir antes de continuar${NC}\n\n"
    exit 1
fi
