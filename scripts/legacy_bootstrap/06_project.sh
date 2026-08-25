#!/bin/bash
# ============================================================
# Script 06: Estructura del proyecto + .env con secrets
# GMP AI Copilot — Proyecto base
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
echo -e "${BOLD}  Script 06 — Estructura del proyecto + .env${NC}"
echo -e "${BOLD}================================================================${NC}"
echo "  $(hostname) | $(whoami) | $(date)"

# ============================================================
# Ubicación del proyecto
# ============================================================

sec "Validando ubicación del proyecto"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Si el script se ejecuta desde el HOME y no desde scripts/,
# se usa el directorio actual como raíz del proyecto.
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
    cd "$PROJECT_DIR"
    pass "Ejecutado desde carpeta scripts/. Raíz del proyecto: $PROJECT_DIR"
else
    PROJECT_DIR="$(pwd)"
    cd "$PROJECT_DIR"
    warn "El script no está dentro de scripts/. Se usará directorio actual como raíz: $PROJECT_DIR"
fi

pass "Directorio activo: $(pwd)"

# ============================================================
# Validaciones previas
# ============================================================

sec "Validaciones previas"

if command -v python3 >/dev/null 2>&1; then
    pass "python3 disponible: $(python3 --version)"
else
    fail "python3 no disponible"
fi

if command -v openssl >/dev/null 2>&1; then
    pass "openssl disponible"
else
    warn "openssl no disponible; se usará python3 para secrets si está disponible"
fi

if command -v sed >/dev/null 2>&1; then
    pass "sed disponible"
else
    fail "sed no disponible"
fi

# ============================================================
# Crear directorios
# ============================================================

sec "Creando estructura de directorios"

mkdir -p \
    data/chroma \
    data/audit_logs \
    data/regulations/fda \
    data/regulations/ich \
    data/regulations/ispe \
    data/regulations/company \
    data/backups \
    logs \
    scripts/sql

for dir in \
    data/chroma \
    data/audit_logs \
    data/regulations/fda \
    data/regulations/ich \
    data/regulations/ispe \
    data/regulations/company \
    data/backups \
    logs \
    scripts/sql; do

    if [ -d "$dir" ]; then
        pass "Directorio creado/validado: $dir"
    else
        fail "No se pudo crear directorio: $dir"
    fi
done

# ============================================================
# Schema SQL PostgreSQL
# ============================================================

sec "Creando schema SQL PostgreSQL"

cat > scripts/sql/init.sql << 'SQLEOF'
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255),
    user_id VARCHAR(255),
    agent_id VARCHAR(100),
    model VARCHAR(100),
    question TEXT,
    response_length INTEGER,
    elapsed_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queries_user ON agent_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_queries_agent ON agent_queries(agent_id);
CREATE INDEX IF NOT EXISTS idx_queries_created_at ON agent_queries(created_at);
SQLEOF

if [ -f scripts/sql/init.sql ]; then
    pass "Schema SQL creado: scripts/sql/init.sql"
else
    fail "No se creó scripts/sql/init.sql"
fi

if grep -q "CREATE TABLE IF NOT EXISTS users" scripts/sql/init.sql; then
    pass "Tabla users definida"
else
    fail "Tabla users no encontrada en init.sql"
fi

if grep -q "CREATE TABLE IF NOT EXISTS agent_queries" scripts/sql/init.sql; then
    pass "Tabla agent_queries definida"
else
    fail "Tabla agent_queries no encontrada en init.sql"
fi

# ============================================================
# Generar .env con secrets
# ============================================================

sec "Generando archivo .env"

if [ -f ".env" ]; then
    BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env "$BACKUP_FILE"
    warn "Backup del .env anterior creado: $BACKUP_FILE"
fi

if command -v python3 >/dev/null 2>&1; then
    APP_SEC="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
    JWT_SEC="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
    pass "Secrets generados con python3"
elif command -v openssl >/dev/null 2>&1; then
    APP_SEC="$(openssl rand -hex 32)"
    JWT_SEC="$(openssl rand -hex 32)"
    pass "Secrets generados con openssl"
else
    fail "No se pudo generar secrets: falta python3 y openssl"
    APP_SEC="REEMPLAZAR_APP_SECRET_KEY"
    JWT_SEC="REEMPLAZAR_JWT_SECRET"
fi

cat > .env << ENVEOF
APP_NAME="GMP AI Copilot"
APP_ENV=staging
APP_SECRET_KEY=${APP_SEC}
DEBUG=false
HOST=0.0.0.0
PORT=8000

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
OLLAMA_TIMEOUT=180
OLLAMA_MAX_TOKENS=2048

CHROMA_PERSIST_DIR=./data/chroma
CHROMA_FDA_COLLECTION=gmp_fda_regulations
CHROMA_IQ_COLLECTION=gmp_iq_oq_pq

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=64

DATABASE_URL=postgresql+asyncpg://gmp_user:gmp_pass@postgres:5432/gmp_copilot
DB_PASS=gmp_pass
DATABASE_POOL_SIZE=5

REDIS_URL=redis://redis:6379/0

JWT_SECRET=${JWT_SEC}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
SESSION_TIMEOUT_MINUTES=15

AUDIT_LOG_DIR=./data/audit_logs
AUDIT_LOG_HASH_ALGO=sha256
KNOWLEDGE_DOCS_DIR=./data/regulations
ENVEOF

chmod 600 .env

if [ -f ".env" ]; then
    pass ".env creado"
else
    fail ".env no fue creado"
fi

if grep -q "^APP_SECRET_KEY=" .env; then
    pass "APP_SECRET_KEY definido"
else
    fail "APP_SECRET_KEY no definido"
fi

if grep -q "^JWT_SECRET=" .env; then
    pass "JWT_SECRET definido"
else
    fail "JWT_SECRET no definido"
fi

if grep -q "^OLLAMA_MODEL=mistral:7b-instruct-q4_K_M" .env; then
    pass "Modelo Ollama configurado en .env"
else
    warn "Modelo Ollama no coincide con mistral:7b-instruct-q4_K_M"
fi

if grep -q "^DATABASE_URL=" .env; then
    pass "DATABASE_URL definido"
else
    fail "DATABASE_URL no definido"
fi

# ============================================================
# .gitignore
# ============================================================

sec "Creando .gitignore"

cat > .gitignore << 'GITEOF'
.env
.env.backup.*
.venv/
__pycache__/
*.pyc
data/
logs/
.DS_Store
*.swp
GITEOF

if [ -f ".gitignore" ]; then
    pass ".gitignore creado"
else
    fail ".gitignore no fue creado"
fi

if grep -q "^.env" .gitignore && grep -q "^data/" .gitignore; then
    pass ".gitignore excluye .env y data/"
else
    warn ".gitignore no excluye correctamente .env o data/"
fi

# ============================================================
# Documentos regulatorios de ejemplo
# ============================================================

sec "Creando documentos regulatorios de ejemplo"

cat > data/regulations/fda/21cfr_part11_key_sections.txt << 'REGEOF'
TITLE: 21 CFR Part 11 - Electronic Records; Electronic Signatures
SOURCE: FDA Code of Federal Regulations Title 21, Chapter I, Part 11

SECTION 11.10 - Controls for closed systems

11.10(a): Validation of systems to ensure accuracy, reliability, consistent intended performance, and the ability to discern invalid or altered records.

11.10(b): The ability to generate accurate and complete copies of records in both human readable and electronic form suitable for inspection, review, and copying by the agency.

11.10(c): Protection of records to enable accurate and ready retrieval throughout the records retention period.

11.10(d): Limiting system access to authorized individuals.

11.10(e): Use of secure, computer-generated, time-stamped audit trails to independently record the date and time of operator entries and actions that create, modify, or delete electronic records. Record changes shall not obscure previously recorded information. Audit trail documentation shall be retained for a period at least as long as required for the subject electronic records and shall be available for agency review and copying.

11.10(f): Use of operational system checks to enforce permitted sequencing of steps and events.

11.10(g): Use of authority checks to ensure only authorized individuals can use the system, electronically sign a record, access the operation or computer system input or output device, alter a record, or perform the operation at hand.

11.10(h): Use of device checks to determine the validity of the source of data input or operational instruction.

11.10(i): Determination that persons who develop, maintain, or use electronic record/electronic signature systems have the education, training, and experience to perform their assigned tasks.

SECTION 11.50 - Signature manifestations
(a) Signed electronic records shall contain information associated with the signing:
(1) The printed name of the signer
(2) The date and time when the signature was executed
(3) The meaning (review, approval, responsibility, authorship)

SECTION 11.70 - Signature/record linking
Electronic signatures shall be linked to their respective electronic records to ensure signatures cannot be excised, copied, or otherwise transferred to falsify an electronic record.

ALCOA+ DATA INTEGRITY PRINCIPLES:
A - Attributable: Traceable to the person who generated it (user ID + timestamp)
L - Legible: Readable and permanent throughout retention period
C - Contemporaneous: Recorded at the time the activity is performed
O - Original: First recording; source data preserved
A - Accurate: Correct, truthful representation
+ Complete: All data including repeated or reanalyzed
+ Consistent: Chronological, no gaps
+ Enduring: On durable media
+ Available: Accessible for review throughout retention period
REGEOF

cat > data/regulations/fda/21cfr_211_equipment.txt << 'REGEOF'
TITLE: 21 CFR Part 211 - Current Good Manufacturing Practice
SECTION: Equipment (Subpart D)

211.63 - Equipment Design, Size, and Location
Equipment used in manufacture, processing, packing, or holding shall be of appropriate design, adequate size, and suitably located to facilitate operations for its intended use and for its cleaning and maintenance.

211.65 - Equipment Construction
Equipment shall be constructed so that surfaces contacting components, in-process materials, or drug products shall not be reactive, additive, or absorptive so as to alter the safety, identity, strength, quality, or purity beyond official or other established requirements.

211.67 - Equipment Cleaning and Maintenance
(a) Equipment shall be cleaned, maintained, and sanitized at appropriate intervals to prevent malfunctions or contamination that would alter safety, identity, strength, quality, or purity.
(b) Written procedures shall be established and followed for cleaning and maintenance.

211.68 - Automatic, Mechanical, and Electronic Equipment
(a) Equipment shall be calibrated, inspected, or checked according to a written program. Written records of calibration checks shall be maintained.
(b) Appropriate controls shall be exercised over computer systems to assure changes in records are made only by authorized personnel. Input/output shall be checked for accuracy. A backup file shall be maintained.

QUALIFICATION REQUIREMENTS:
IQ (Installation Qualification): Verify equipment installed per design specifications.
  - Equipment identification and serial number documentation
  - Utility connections verification (electrical, pneumatic, process)
  - Instrument calibration records with NIST traceability
  - Software version confirmation
  - Materials of construction verification

OQ (Operational Qualification): Verify equipment operates within defined limits.
  - Alarm testing at high and low setpoints
  - Interlock verification
  - Audit trail generation and content
  - User access control (21 CFR Part 11)
  - Emergency stop functionality

PQ (Performance Qualification): Demonstrate consistent performance under production.
  - Minimum 3 consecutive successful production runs
  - Worst-case conditions
  - Batch reproducibility
REGEOF

if [ -f "data/regulations/fda/21cfr_part11_key_sections.txt" ]; then
    pass "Documento FDA Part 11 creado"
else
    fail "Documento FDA Part 11 no fue creado"
fi

if [ -f "data/regulations/fda/21cfr_211_equipment.txt" ]; then
    pass "Documento FDA Part 211 creado"
else
    fail "Documento FDA Part 211 no fue creado"
fi

# ============================================================
# Validación final de estructura
# ============================================================

sec "Validación final de estructura"

if [ -d "data/regulations/fda" ]; then
    pass "Ruta regulatoria FDA disponible"
else
    fail "Ruta regulatoria FDA no disponible"
fi

if [ -d "data/chroma" ]; then
    pass "Ruta Chroma disponible"
else
    fail "Ruta Chroma no disponible"
fi

if [ -d "data/audit_logs" ]; then
    pass "Ruta audit_logs disponible"
else
    fail "Ruta audit_logs no disponible"
fi

if [ -d "logs" ]; then
    pass "Ruta logs disponible"
else
    fail "Ruta logs no disponible"
fi

echo ""
echo "Estructura principal:"
find data -maxdepth 3 -type d | sort
echo ""
echo "Archivos principales:"
ls -lh .env .gitignore scripts/sql/init.sql data/regulations/fda/*.txt 2>/dev/null || true

# ============================================================
# Resumen
# ============================================================

echo ""
echo -e "${BOLD}== RESUMEN: PASS=$PASS WARN=$WARN FAIL=$FAIL ==${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED}✗ Script 06 finalizó con fallos críticos${NC}"
    exit 1
fi

if (( WARN > 0 )); then
    echo -e "${YELLOW}⚠ Script 06 completado con advertencias — revisar antes de continuar${NC}"
    echo -e "  Proyecto: ${BLUE}$(pwd)${NC}"
    exit 0
fi

echo -e "${GREEN}✓ Script 06 completado correctamente — Proyecto listo${NC}"
echo -e "  Proyecto : ${BLUE}$(pwd)${NC}"
echo -e "  .env     : ${BLUE}creado con permisos 600${NC}"
echo -e "  SQL      : ${BLUE}scripts/sql/init.sql${NC}"
echo -e "  Docs FDA : ${BLUE}data/regulations/fda/${NC}"
echo -e "  Siguiente: ${BLUE}bash scripts/04_docker_stack.sh${NC}"
exit 0
