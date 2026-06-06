#!/bin/bash
# ============================================================
# GMP AI Copilot — Backup
# Proyecto raíz: /home/ing_cpmo
# ============================================================

set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

PROJECT_DIR="/home/ing_cpmo"
BACKUP_DIR="$PROJECT_DIR/data/backups"
DATE="$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup iniciado"

cd "$PROJECT_DIR"

# PostgreSQL
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps postgres >/dev/null 2>&1; then
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres         pg_dump -U gmp_user gmp_copilot 2>/dev/null |         gzip > "$BACKUP_DIR/postgres_${DATE}.sql.gz"; then
        echo "  PostgreSQL: OK"
    else
        echo "  PostgreSQL: ERROR"
    fi
else
    echo "  PostgreSQL: ERROR — contenedor no disponible"
fi

# ChromaDB
if [ -d "$PROJECT_DIR/data/chroma" ]; then
    if tar -czf "$BACKUP_DIR/chroma_${DATE}.tar.gz"         -C "$PROJECT_DIR/data" chroma/ 2>/dev/null; then
        echo "  ChromaDB: OK"
    else
        echo "  ChromaDB: ERROR"
    fi
else
    echo "  ChromaDB: OMITIDO — directorio no existe"
fi

# Audit logs
if [ -d "$PROJECT_DIR/data/audit_logs" ]; then
    if tar -czf "$BACKUP_DIR/audit_${DATE}.tar.gz"         -C "$PROJECT_DIR/data" audit_logs/ 2>/dev/null; then
        echo "  Audit logs: OK"
    else
        echo "  Audit logs: ERROR"
    fi
else
    echo "  Audit logs: OMITIDO — directorio no existe"
fi

# Limpieza por retención
find "$BACKUP_DIR" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

echo "[$(date)] Backup completado. Archivos: $(find "$BACKUP_DIR" -type f | wc -l)"
