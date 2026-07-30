#!/usr/bin/env bash
# factory/scripts/ops/factory_selfcheck.sh
# Gate 0 de cada fase futura — ejecutar antes de cualquier release o deployment.
# Corre: py_compile + pytest + verify_chain (por dimension) + factory_status.sh
#      + validation_evidence scan + consistencia de versiones de artefactos
# Sale con código 0 si FAIL=0, 1 si hay fallos.
set -euo pipefail

FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
# WARNS se cuenta y se muestra: un Gate 0 que anuncia "PASS=6 FAIL=0" mientras
# oculta 29 avisos colapsa las dimensiones igual que el `part11_compliant`
# booleano que G1.14 tuvo que desmontar. Un WARN no bloquea, pero se dice.
PASS=0; FAIL=0; WARNS=0

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
warn_()   { printf "  ${Y}WARN${NC}  %s\n" "$1"; WARNS=$((WARNS+1)); }
section() { printf "\n${BOLD}${B}━━━ %s ━━━${NC}\n" "$1"; }

# ── Veredictos, en funciones para poder PROBARLOS ─────────────────────────────
#
# Están aquí y no inline por una razón concreta: un Gate 0 cuya rama de FAIL
# nadie ha ejecutado nunca es un gate que nadie ha verificado. Extraídas,
# `test_gate0_extended.py` las invoca con valores inyectados y comprueba que la
# corrupción, un fork nuevo y una inconsistencia de versión ponen el gate en
# rojo de verdad.
#
# G7 CERRADO el 2026-07-30: Cesar firmó AUDIT_EXCEPTION-2026-002 sobre
# ab689c7c y FORK_HISTORICO_ES_FAIL pasa a 1, como preveía el spec §6. Antes de
# la firma habría dejado Gate 0 en rojo permanente por una excepción que todavía
# no podía existir, y un gate siempre rojo deja de leerse.
#
# Con la excepción vigente esto NO pone nada en rojo: el fork histórico entra
# ahora por la rama ACCEPTED_WITH_DOCUMENTED_EXCEPTION. Lo que la variable
# enciende es el caso en que la excepción DESAPAREZCA —revocada, superseded o un
# almacén que deje de resolverla— y el fork se quede otra vez sin respaldo. Ahí
# el gate tiene que parar la fábrica, no avisar.
FORK_HISTORICO_ES_FAIL="${FORK_HISTORICO_ES_FAIL:-1}"

# _verdict_audit_chain <hash_errors> <new_forks> <historical> <continuity> <count>
_verdict_audit_chain() {
    local herr="$1" new="$2" hist="$3" cont="$4" cnt="$5"
    if [[ "${herr:-0}" != "0" ]]; then
        ko "audit chain: CONTENT_HASH_INTEGRITY comprometida (hash_errors=$herr) — corrupción de contenido, NO exceptuable"
    elif [[ "${new:-0}" != "0" ]]; then
        ko "audit chain: $new fork(s) NUEVO(s) desde el baseline — se para todo y se investiga"
    elif [[ "$hist" == "True" && "$cont" != "ACCEPTED_WITH_DOCUMENTED_EXCEPTION" ]]; then
        if [[ "$FORK_HISTORICO_ES_FAIL" == "1" ]]; then
            ko "audit chain: fork histórico sin excepción firmada (exigible desde G7)"
        else
            warn_ "audit chain: fork histórico sin excepción firmada — pendiente de decisión AUDIT_EXCEPTION (G7)"
            ok "audit chain: contenido auténtico ($cnt entradas, 0 forks nuevos)"
        fi
    elif [[ "$cont" == "ACCEPTED_WITH_DOCUMENTED_EXCEPTION" ]]; then
        warn_ "audit chain: continuidad ACEPTADA CON EXCEPCIÓN documentada — nunca 'sin errores'"
        ok "audit chain: contenido auténtico ($cnt entradas, excepción vigente)"
    else
        ok "audit chain: integridad verificada ($cnt entradas)"
    fi
}

# _verdict_artifact_versions <status> <fail_count> <warn_count> [codigo_warn]
#
# El cuarto argumento existe porque hay DOS motivos de WARN distintos y el
# mensaje tiene que decir el correcto. Con solo el recuento, tras correr el
# bootstrap de G4 el gate seguia diciendo "sin version_record — bootstrap
# pendiente" sobre 28 artefactos que ya estaban fotografiados: un aviso cierto
# en el numero y falso en la causa, que es peor que no avisar.
_verdict_artifact_versions() {
    local motivo
    case "${4:-}" in
        NO_APPROVING_DECISION)
            motivo="con version_record pero SIN decision que lo apruebe — fotografiados, no aprobados (G4c/G5)" ;;
        NO_VERSION_RECORD)
            motivo="sin version_record — bootstrap pendiente (G4)" ;;
        *)  motivo="con avisos de versionado" ;;
    esac
    case "$1" in
        PASS) ok "artifact versions: hash y versión consistentes en todos los artefactos" ;;
        WARN) warn_ "artifact versions: $3 artefacto(s) $motivo"
              ok "artifact versions: 0 inconsistencias de trazabilidad" ;;
        FAIL) ko "artifact versions: $2 inconsistencia(s) de trazabilidad (ver arriba)" ;;
        *)    ko "artifact versions: la guardia no pudo evaluarse" ;;
    esac
}

# Permite que los tests carguen SOLO las funciones, sin correr la suite entera.
if [[ "${SELFCHECK_LIB_ONLY:-0}" == "1" ]]; then
    return 0 2>/dev/null || exit 0
fi

# ── 1. py_compile — todos los módulos Python de la fábrica ───────────────────
section "1/6  py_compile"

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
section "2/6  pytest"

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

# ── 3. verify_chain — audit de fábrica, POR DIMENSIÓN (W5 V2 G1.17) ──────────
#
# Se evalúa cada dimensión por separado y NINGUNA se deriva de otra. La regla
# anterior colapsaba tres cosas en un booleano y dejaba pasar un "Part-11
# cumplido" sobre una cadena que el propio reporte daba por no verificada.
#
#   CONTENT_HASH_INTEGRITY    FAIL si hash_errors > 0        (corrupción real)
#   NEW_FORKS_SINCE_BASELINE  FAIL si > 0                    (fork nuevo)
#   HISTORICAL_FORK_PRESENT   WARN hoy · FAIL desde G7
#   PART11_COMPLIANCE         INFORMATIVO — nunca criterio de PASS por sí solo
#
# `HISTORICAL_FORK_PRESENT` pasa de WARN a FAIL SOLO a partir de G7, y no es
# indulgencia: antes de G7 la excepción humana todavía no puede existir, y
# dejar Gate 0 en rojo permanente hasta entonces garantiza que se deje de leer.
# Un gate que siempre está rojo no informa de nada.
#
# Usa $PYBIN y no `python3`: desde G1.14 las dimensiones consultan el resolver,
# que arrastra jsonschema. Con el python3 del sistema el módulo degrada a "sin
# excepción demostrable" -- correcto pero menos informativo -- y aquí interesa
# el valor real.
section "3/6  audit chain (por dimensión)"

CHAIN_RESULT=$("$PYBIN" - <<'PYEOF' 2>/dev/null || echo "ERROR"
import sys
sys.path.insert(0, '/home/ing_cpmo')
from factory.core.audit_writer import verify_chain
r = verify_chain()
print("|".join(str(x) for x in (
    r['verified'], r['log_count'], r['hash_errors'], r['chain_errors'],
    r['content_hash_integrity'], r['chain_continuity'],
    r['historical_fork_present'], r['new_forks_since_baseline'],
    r['part11_compliant'],
)))
PYEOF
)
C_OK=$(echo "$CHAIN_RESULT"    | cut -d'|' -f1)
C_CNT=$(echo "$CHAIN_RESULT"   | cut -d'|' -f2)
C_HERR=$(echo "$CHAIN_RESULT"  | cut -d'|' -f3)
C_CERR=$(echo "$CHAIN_RESULT"  | cut -d'|' -f4)
C_CONTENT=$(echo "$CHAIN_RESULT" | cut -d'|' -f5)
C_CONT=$(echo "$CHAIN_RESULT"  | cut -d'|' -f6)
C_HIST=$(echo "$CHAIN_RESULT"  | cut -d'|' -f7)
C_NEW=$(echo "$CHAIN_RESULT"   | cut -d'|' -f8)
C_P11=$(echo "$CHAIN_RESULT"   | cut -d'|' -f9)

if [[ "$CHAIN_RESULT" == "ERROR" || -z "$C_OK" ]]; then
    ko "audit chain: no se pudo leer la cadena (verify_chain falló)"
else
    printf "  %-26s %s\n" "CONTENT_HASH_INTEGRITY" "$C_CONTENT"
    printf "  %-26s %s\n" "CHAIN_CONTINUITY" "$C_CONT"
    printf "  %-26s %s\n" "HISTORICAL_FORK_PRESENT" "$C_HIST"
    printf "  %-26s %s\n" "NEW_FORKS_SINCE_BASELINE" "$C_NEW"
    printf "  %-26s %s  (informativo)\n" "PART11_COMPLIANCE" "$C_P11"
    _verdict_audit_chain "$C_HERR" "$C_NEW" "$C_HIST" "$C_CONT" "$C_CNT"
fi

# ── 4. factory_status.sh ──────────────────────────────────────────────────────
section "4/6  factory_status.sh"

STATUS_EXIT=0
STATUS_OUT=$(bash "$FACTORY_DIR/scripts/ops/factory_status.sh" 2>&1) || STATUS_EXIT=$?

# Mostrar solo el bloque RESUMEN FINAL
echo "$STATUS_OUT" | grep -E "PASS|WARN|FAIL|━" | tail -8 || true

case $STATUS_EXIT in
    0) ok "factory_status.sh: sin FAILs ni WARNs" ;;
    1) ok "factory_status.sh: WARNs presentes pero sin FAILs (aceptable en self-check)" ;;
    *) ko "factory_status.sh: $STATUS_EXIT FAILs detectados" ;;
esac

# ── 5. validation_evidence git-safety scan (Fase 5.4.4, gobernanza) ──────────
# Corre en modo --ci (escanea el árbol TRACKEADO vía git ls-files, no el
# índice staged -- distinto del hook de pre-commit, que .git/hooks/ no
# versiona; este paso es el que SI viaja con el repo y corre en Gate 0/CI
# sin depender de que alguien haya instalado el hook local).
section "5/6  validation_evidence git-safety scan"

SCAN_EXIT=0
SCAN_OUT=$(python3 "$FACTORY_DIR/scripts/ops/scan_validation_evidence_staged.py" --ci 2>&1) || SCAN_EXIT=$?
echo "$SCAN_OUT"

if [[ $SCAN_EXIT -eq 0 ]]; then
    ok "validation_evidence: solo allowlist tracked, sin contenido prohibido"
else
    ko "validation_evidence: escaneo detectó violaciones (ver arriba)"
fi

# ── 6. consistencia de versiones de artefactos (W5 V2 G1.17) ─────────────────
#
# La triple invariante de ARTIFACT_VERSIONING_SPEC §2.1, aplicada a las cinco
# clases de artefacto:
#
#   FAIL  el hash cambió y la versión no        → contenido cambiado en silencio
#   FAIL  la versión cambió y el hash no        → "versionar" para simular revisión
#   FAIL  la versión cambió sin decisión ACTIVE → versionar sin aprobación humana
#   WARN  el artefacto no tiene version_record  → estado inicial, pre-bootstrap
#
# Las tres primeras son FAIL desde el día uno: son corrupción de trazabilidad.
# La cuarta es WARN porque HOY ningún artefacto tiene registro -- el almacén no
# existe y el bootstrap es de G4. Un FAIL aquí pondría Gate 0 en rojo por una
# tarea pendiente, no por un defecto, y ese es el camino más corto para que
# nadie vuelva a mirar el gate.
#
# $PYBIN obligatorio: la guardia lee YAML y consulta el resolver.
section "6/6  consistencia de versiones de artefactos"

VER_OUT=$("$PYBIN" - <<'PYEOF' 2>&1 || echo "STATUS=ERROR"
import sys
sys.path.insert(0, '/home/ing_cpmo')
from factory.core import artifact_version_guard as guard
r = guard.guard_report()
print(f"  {r['artifacts_seen']} artefactos ({', '.join(f'{k}={v}' for k, v in r['by_class'].items())})")
print(f"  {r['records_in_store']} version_record en el almacen")
for f in r["findings"][:12]:
    print(f"  {f['severity']:4s} {f['artifact']}/{f['artifact_id']}: {f['code']}")
if len(r["findings"]) > 12:
    print(f"  … y {len(r['findings']) - 12} mas")
from collections import Counter
warn_codes = Counter(f["code"] for f in r["findings"] if f["severity"] == "WARN")
top = warn_codes.most_common(1)[0][0] if warn_codes else ""
print(f"STATUS={r['status']}|{r['fail_count']}|{r['warn_count']}|{top}")
PYEOF
)
echo "$VER_OUT" | grep -v '^STATUS=' || true
VER_STATUS=$(echo "$VER_OUT" | grep '^STATUS=' | tail -1 | cut -d'=' -f2)
V_ST=$(echo "$VER_STATUS" | cut -d'|' -f1)
V_FAIL=$(echo "$VER_STATUS" | cut -d'|' -f2)
V_WARN=$(echo "$VER_STATUS" | cut -d'|' -f3)
V_CODE=$(echo "$VER_STATUS" | cut -d'|' -f4)

_verdict_artifact_versions "$V_ST" "$V_FAIL" "$V_WARN" "$V_CODE"

# ── RESUMEN ───────────────────────────────────────────────────────────────────
printf "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
printf "${BOLD}  FACTORY SELF-CHECK — ${G}PASS=%d${NC}  ${Y}WARN=%d${NC}  ${R}FAIL=%d${NC}\n" "$PASS" "$WARNS" "$FAIL"
printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [[ $FAIL -eq 0 ]]; then
    printf "\n  ${G}✓ Gate 0 OK — sistema listo para siguiente fase${NC}\n\n"
    exit 0
else
    printf "\n  ${R}✗ Gate 0 FAILED — corregir antes de continuar${NC}\n\n"
    exit 1
fi
