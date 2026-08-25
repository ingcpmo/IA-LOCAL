#!/bin/bash
# ============================================================
# Script 05: Python 3.11 venv + requirements
# GMP AI Copilot
# Proyecto raíz: /home/ing_cpmo
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
FAIL=0
WARN=0

PROJECT_DIR="/home/ing_cpmo"
VENV_DIR=".venv"
REQ_FILE="requirements.txt"
EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"

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

echo -e "${BOLD}================================================================${NC}"
echo -e "${BOLD}  Script 05 — Python 3.11 venv + requirements${NC}"
echo -e "${BOLD}  Proyecto raíz: /home/ing_cpmo${NC}"
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
# Validaciones previas
# ============================================================

sec "Validaciones previas"

if command -v python3 >/dev/null 2>&1; then
    PY_VER="$(python3 --version)"
    pass "python3 disponible: $PY_VER"
else
    fail "python3 no disponible"
fi

if python3 -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
    pass "Python cumple versión mínima 3.11"
else
    fail "Python no cumple versión mínima 3.11"
fi

if python3 -m venv --help >/dev/null 2>&1; then
    pass "Módulo venv disponible"
else
    fail "python3-venv no disponible"
fi

if [ -f "$REQ_FILE" ]; then
    pass "requirements.txt encontrado"
else
    fail "requirements.txt no encontrado en $PROJECT_DIR"
fi

if [ -f "app/main.py" ]; then
    pass "API app/main.py encontrada"
else
    warn "app/main.py no encontrada"
fi

if [ -f ".env" ]; then
    pass ".env encontrado"
else
    warn ".env no encontrado"
fi

# ============================================================
# Crear entorno virtual
# ============================================================

sec "Creando entorno virtual Python"

if (( FAIL == 0 )); then
    if [ -d "$VENV_DIR" ]; then
        pass ".venv ya existe"
    else
        if python3 -m venv "$VENV_DIR"; then
            pass ".venv creado correctamente"
        else
            fail "No se pudo crear .venv"
        fi
    fi
else
    warn "Creación de .venv omitida por fallos previos"
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pass "Entorno virtual activado"
else
    fail "No existe $VENV_DIR/bin/activate"
fi

# ============================================================
# Actualizar herramientas base
# ============================================================

sec "Actualizando pip, setuptools y wheel"

if (( FAIL == 0 )); then
    if python -m pip install --upgrade pip wheel
    python -m pip install "setuptools<82"; then
        pass "pip, setuptools y wheel actualizados"
    else
        fail "Falló actualización de pip/setuptools/wheel"
    fi
else
    warn "Actualización de herramientas omitida por fallos previos"
fi

# ============================================================
# Instalar dependencias
# ============================================================

sec "Instalando dependencias desde requirements.txt"

if (( FAIL == 0 )); then
    REQ_COUNT="$(grep -vE '^\s*#|^\s*$' "$REQ_FILE" | wc -l | awk '{print $1}')"
    echo "  Dependencias declaradas: $REQ_COUNT"

    if pip install -r "$REQ_FILE"; then
        pass "Dependencias instaladas desde requirements.txt"
    else
        fail "Falló instalación de dependencias"
    fi
else
    warn "Instalación de dependencias omitida por fallos previos"
fi

# ============================================================
# Dependencias opcionales para embeddings / RAG
# ============================================================

sec "Validando dependencias de embeddings"

if (( FAIL == 0 )); then
    if python -c "import sentence_transformers" >/dev/null 2>&1; then
        pass "sentence-transformers instalado"
    else
        warn "sentence-transformers no está instalado en requirements.txt"
        warn "Se omite predescarga de embeddings"
    fi

    if python -c "import chromadb" >/dev/null 2>&1; then
        pass "chromadb instalado"
    else
        warn "chromadb no está instalado en requirements.txt"
    fi

    if python -c "import langchain" >/dev/null 2>&1; then
        pass "langchain instalado"
    else
        warn "langchain no está instalado en requirements.txt"
    fi

    if python -c "import ollama" >/dev/null 2>&1; then
        pass "ollama python package instalado"
    else
        warn "ollama python package no está instalado en requirements.txt"
    fi
else
    warn "Validación de dependencias opcionales omitida por fallos previos"
fi

# ============================================================
# Pre-descargar modelo embeddings si está disponible
# ============================================================

sec "Pre-descargando modelo de embeddings"

if (( FAIL == 0 )); then
    if python -c "import sentence_transformers" >/dev/null 2>&1; then
        if python - << PYEOF
from sentence_transformers import SentenceTransformer

model_name = "all-MiniLM-L6-v2"
m = SentenceTransformer(model_name)
t = m.encode(["GMP qualification test"])
print(f"Embeddings OK: {len(t[0])} dims, en CPU")
PYEOF
        then
            pass "Modelo embeddings listo: all-MiniLM-L6-v2"
        else
            warn "Falló predescarga del modelo embeddings; se descargará en primera ejecución"
        fi
    else
        warn "Predescarga omitida: sentence-transformers no instalado"
    fi
else
    warn "Predescarga omitida por fallos previos"
fi

# ============================================================
# Validar imports principales
# ============================================================

sec "Validando imports principales"

if (( FAIL == 0 )); then
    if python -c "import fastapi; print(fastapi.__version__)" >/dev/null 2>&1; then
        pass "FastAPI importable"
    else
        fail "FastAPI no importable"
    fi

    if python -c "import uvicorn; print(uvicorn.__version__)" >/dev/null 2>&1; then
        pass "Uvicorn importable"
    else
        fail "Uvicorn no importable"
    fi

    if python -c "import httpx; print(httpx.__version__)" >/dev/null 2>&1; then
        pass "httpx importable"
    else
        fail "httpx no importable"
    fi

    if python -c "import redis; print(redis.__version__)" >/dev/null 2>&1; then
        pass "redis importable"
    else
        fail "redis no importable"
    fi

    if python -c "import asyncpg; print(asyncpg.__version__)" >/dev/null 2>&1; then
        pass "asyncpg importable"
    else
        fail "asyncpg no importable"
    fi
else
    warn "Validación de imports omitida por fallos previos"
fi

# ============================================================
# Validar sintaxis de la API
# ============================================================

sec "Validando sintaxis de app/main.py"

if [ -f "app/main.py" ]; then
    if python -m py_compile app/main.py; then
        pass "Sintaxis app/main.py válida"
    else
        fail "Error de sintaxis en app/main.py"
    fi
else
    warn "No se valida sintaxis porque app/main.py no existe"
fi

# ============================================================
# Resumen del entorno
# ============================================================

sec "Resumen del entorno Python"

echo "  Python:        $(python --version 2>/dev/null || echo 'N/D')"
echo "  Pip:           $(pip --version 2>/dev/null || echo 'N/D')"
echo "  FastAPI:       $(python -c 'import fastapi; print(fastapi.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  Uvicorn:       $(python -c 'import uvicorn; print(uvicorn.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  httpx:         $(python -c 'import httpx; print(httpx.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  redis:         $(python -c 'import redis; print(redis.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  asyncpg:       $(python -c 'import asyncpg; print(asyncpg.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  LangChain:     $(python -c 'import langchain; print(langchain.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  ChromaDB:      $(python -c 'import chromadb; print(chromadb.__version__)' 2>/dev/null || echo 'No instalado')"
echo "  Ollama pkg:    $(python -c 'import ollama; print(getattr(ollama, \"__version__\", \"instalado\"))' 2>/dev/null || echo 'No instalado')"
echo "  Venv:          ${PROJECT_DIR}/${VENV_DIR}"

# ============================================================
# Resumen final
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 05 finalizó con fallos críticos${NC}"
    echo -e "  Revisar requirements: ${BLUE}${PROJECT_DIR}/${REQ_FILE}${NC}"
    echo -e "  Revisar venv       : ${BLUE}${PROJECT_DIR}/${VENV_DIR}${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 05 completado con advertencias${NC}"
    echo -e "  Activar entorno: ${BLUE}source ${PROJECT_DIR}/${VENV_DIR}/bin/activate${NC}"
    echo -e "  Nota: algunas dependencias RAG/embeddings no están en requirements.txt"
    exit 0
fi

echo -e "${GREEN}✓ Script 05 completado correctamente${NC}"
echo -e "  Activar entorno: ${BLUE}source ${PROJECT_DIR}/${VENV_DIR}/bin/activate${NC}"
echo -e "  Proyecto       : ${BLUE}${PROJECT_DIR}${NC}"
exit 0
