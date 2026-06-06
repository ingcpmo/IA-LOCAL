#!/bin/bash
# ============================================================
# OPS — Ingestar un nuevo documento PDF/TXT
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
#
# Uso:
#   bash scripts/ops/ingest_doc.sh ARCHIVO.pdf [fda|iq|all]
#   bash scripts/ops/ingest_doc.sh ARCHIVO.txt [fda|iq|all]
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
DOC="${1:-}"
TARGET="${2:-all}"

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
echo -e "${BOLD}  OPS — Ingesta documental PDF/TXT${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Validar parámetros
# ============================================================

sec "Validando parámetros"

if [ -z "$DOC" ]; then
    fail "No se indicó archivo"
    echo ""
    echo "Uso:"
    echo "  bash scripts/ops/ingest_doc.sh ARCHIVO.pdf [fda|iq|all]"
    echo "  bash scripts/ops/ingest_doc.sh ARCHIVO.txt [fda|iq|all]"
fi

case "$TARGET" in
    fda|iq|all)
        pass "Target válido: $TARGET"
        ;;
    *)
        fail "Target inválido: $TARGET. Valores permitidos: fda, iq, all"
        ;;
esac

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
# Validar documento origen
# ============================================================

sec "Validando documento origen"

if (( FAIL == 0 )); then
    if [ -f "$DOC" ]; then
        pass "Archivo encontrado: $DOC"
    else
        fail "El archivo no existe: $DOC"
    fi
else
    warn "Validación de documento omitida por fallos previos"
fi

if (( FAIL == 0 )); then
    EXT="${DOC##*.}"
    EXT_LOWER="$(echo "$EXT" | tr '[:upper:]' '[:lower:]')"

    case "$EXT_LOWER" in
        pdf|txt|md)
            pass "Extensión soportada: .$EXT_LOWER"
            ;;
        *)
            warn "Extensión no estándar: .$EXT_LOWER"
            warn "Se copiará el archivo, pero la ingesta puede no soportarlo"
            ;;
    esac
fi

# ============================================================
# Preparar destino documental
# ============================================================

sec "Preparando repositorio documental"

if (( FAIL == 0 )); then
    mkdir -p data/regulations/fda
    mkdir -p data/regulations/iq
    mkdir -p data/regulations/all
    mkdir -p logs

    pass "Directorios documentales disponibles"

    BASENAME="$(basename "$DOC")"

    case "$TARGET" in
        fda)
            DEST="data/regulations/fda/$BASENAME"
            ;;
        iq)
            DEST="data/regulations/iq/$BASENAME"
            ;;
        all)
            DEST="data/regulations/all/$BASENAME"
            ;;
    esac

    if cp "$DOC" "$DEST"; then
        pass "Documento copiado a: $DEST"
    else
        fail "No se pudo copiar documento a: $DEST"
    fi
else
    warn "Preparación documental omitida por fallos previos"
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
        fail "No existe .venv/bin/activate"
    fi
else
    warn "Activación del entorno omitida por fallos previos"
fi

if (( FAIL == 0 )); then
    if python -c "import sentence_transformers, chromadb, langchain" >/dev/null 2>&1; then
        pass "Dependencias RAG disponibles"
    else
        fail "Dependencias RAG no disponibles"
    fi
fi

# ============================================================
# Validar módulo original de ingesta
# ============================================================

sec "Validando módulo DocumentIngester"

INGESTER_AVAILABLE=0

if (( FAIL == 0 )); then
    if [ -f "knowledge/retriever.py" ]; then
        pass "Módulo encontrado: knowledge/retriever.py"

        if python - << 'PYEOF'
import sys
sys.path.insert(0, ".")
from knowledge.retriever import DocumentIngester
print("DocumentIngester importable")
PYEOF
        then
            pass "DocumentIngester importable"
            INGESTER_AVAILABLE=1
        else
            fail "DocumentIngester no es importable desde knowledge.retriever"
        fi
    else
        warn "No existe knowledge/retriever.py"
        warn "Documento copiado, pero la indexación vectorial queda pendiente"
    fi
else
    warn "Validación de DocumentIngester omitida por fallos previos"
fi

# ============================================================
# Ejecutar ingesta vectorial
# ============================================================

sec "Ejecutando ingesta vectorial"

if (( FAIL == 0 )) && [ "$INGESTER_AVAILABLE" -eq 1 ]; then
    python - << PYEOF
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, ".")

from knowledge.retriever import DocumentIngester

target = "${TARGET}"
dest = Path("${DEST}")

collections = []

if target in ("fda", "all"):
    collections.append("gmp_fda_regulations")

if target in ("iq", "all"):
    collections.append("gmp_iq_oq_pq")

if not collections:
    raise RuntimeError(f"No hay colecciones configuradas para target={target}")

d = DocumentIngester()

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    shutil.copy2(dest, tmp_path / dest.name)

    for col in collections:
        n = d.ingest_directory(str(tmp_path), col)
        print(f"  {col}: {n} chunks")

print("Ingesta completada")
PYEOF

    pass "Ingesta vectorial ejecutada"
elif (( FAIL == 0 )); then
    warn "Ingesta vectorial omitida porque DocumentIngester aún no existe"
else
    warn "Ingesta vectorial omitida por fallos previos"
fi

# ============================================================
# Validar API
# ============================================================

sec "Validando API local"

if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    pass "API responde en http://localhost:8000/health"
else
    warn "API no respondió en /health"
fi

# ============================================================
# Resumen final
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Ingesta documental finalizó con fallos críticos${NC}"
    echo -e "  Uso:"
    echo -e "  ${BLUE}bash scripts/ops/ingest_doc.sh ARCHIVO.pdf [fda|iq|all]${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Documento procesado con advertencias${NC}"
    echo -e "  Documento copiado: ${BLUE}${DEST:-N/D}${NC}"
    echo -e "  Verificar API    : ${BLUE}curl http://localhost:8000/health${NC}"
    echo -e "  Verificar stats  : ${BLUE}curl http://localhost:8000/api/v1/knowledge/stats${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Documento ingerido correctamente${NC}"
echo -e "  Documento copiado: ${BLUE}${DEST}${NC}"
echo -e "  Verificar stats  : ${BLUE}curl http://localhost:8000/api/v1/knowledge/stats${NC}"
exit 0
