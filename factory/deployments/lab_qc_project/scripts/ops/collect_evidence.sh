#!/bin/bash
# ============================================================
# OPS — Recolectar evidencia para Claude Code
# Proyecto raíz: /home/ing_cpmo
# Uso: bash scripts/ops/collect_evidence.sh
# ============================================================

set -euo pipefail
export PATH="$PATH:/usr/sbin:/sbin"

PROJECT_DIR="/home/ing_cpmo"
OUT_DIR="$PROJECT_DIR/logs/evidence"
DATE_TAG="$(date +%Y%m%d_%H%M%S)"
CASE_DIR="$OUT_DIR/claude_evidence_$DATE_TAG"
TAR_FILE="$OUT_DIR/claude_evidence_$DATE_TAG.tar.gz"

mkdir -p "$CASE_DIR"

echo "Recolectando evidencia en: $CASE_DIR"

cd "$PROJECT_DIR"

# 1. Reporte manual para Claude
cp "$PROJECT_DIR/CLAUDE_SERVER_EVIDENCE.md" "$CASE_DIR/CLAUDE_SERVER_EVIDENCE.md" 2>/dev/null || true

# 2. Estado operativo
bash "$PROJECT_DIR/scripts/ops/status.sh" > "$CASE_DIR/status_output.log" 2>&1 || true

# 3. Health API
curl -sS http://localhost:8000/health > "$CASE_DIR/api_health.json" 2>&1 || true

# 4. Endpoints pendientes
{
echo "POST /api/v1/query"
curl -sS -i -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ing_cpmo" \
  -d '{"question":"What does 21 CFR Part 11 require for audit trails?","agent":"fda"}' || true

echo ""
echo "GET /api/v1/knowledge/stats"
curl -sS -i http://localhost:8000/api/v1/knowledge/stats || true

echo ""
echo "GET /api/v1/audit/verify"
curl -sS -i http://localhost:8000/api/v1/audit/verify || true

echo ""
echo "GET /api/v1/protocol-template/IQ"
curl -sS -i http://localhost:8000/api/v1/protocol-template/IQ || true
} > "$CASE_DIR/endpoints_check.log" 2>&1

# 5. Docker
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' > "$CASE_DIR/docker_ps.log" 2>&1 || true
docker compose -f "$PROJECT_DIR/docker-compose.yml" ps > "$CASE_DIR/docker_compose_ps.log" 2>&1 || true

# 6. Systemd
{
systemctl is-enabled gmp-copilot || true
systemctl is-active gmp-copilot || true
systemctl status gmp-copilot --no-pager || true
} > "$CASE_DIR/systemd_gmp_copilot.log" 2>&1

# 7. Firewall
sudo ufw status numbered > "$CASE_DIR/ufw_status.log" 2>&1 || true

# 8. Ollama
{
curl -sS http://localhost:11434/api/tags || true
echo ""
docker exec gmp-api sh -lc 'python - << "PY"
import httpx
for url in [
    "http://host.docker.internal:11434/api/tags",
    "http://172.18.0.1:11434/api/tags"
]:
    try:
        r = httpx.get(url, timeout=5)
        print(url, r.status_code)
    except Exception as e:
        print(url, type(e).__name__, str(e))
PY' || true
} > "$CASE_DIR/ollama_connectivity.log" 2>&1

# 9. Archivos clave sin secretos
cp "$PROJECT_DIR/docker-compose.yml" "$CASE_DIR/docker-compose.yml" 2>/dev/null || true
cp "$PROJECT_DIR/app/main.py" "$CASE_DIR/app_main.py" 2>/dev/null || true
cp "$PROJECT_DIR/scripts/ops/status.sh" "$CASE_DIR/status.sh" 2>/dev/null || true
cp "$PROJECT_DIR/scripts/ops/backup.sh" "$CASE_DIR/backup.sh" 2>/dev/null || true
cp "$PROJECT_DIR/scripts/ops/ingest_doc.sh" "$CASE_DIR/ingest_doc.sh" 2>/dev/null || true

# 10. Estructura de archivos
find "$PROJECT_DIR" -maxdepth 3 -type f \
  ! -path "$PROJECT_DIR/.env" \
  ! -path "$PROJECT_DIR/.venv/*" \
  ! -path "$PROJECT_DIR/data/backups/*" \
  ! -path "$PROJECT_DIR/logs/evidence/*" \
  | sort > "$CASE_DIR/project_files.txt" 2>/dev/null || true

# 11. Backups
ls -lah "$PROJECT_DIR/data/backups" > "$CASE_DIR/backups_list.log" 2>&1 || true

# 12. Python packages clave
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
  source "$PROJECT_DIR/.venv/bin/activate"
  pip list | grep -Ei "fastapi|uvicorn|httpx|redis|asyncpg|sentence|chroma|langchain|torch|pytest|nvidia|cuda|triton" \
    > "$CASE_DIR/python_packages_key.log" 2>&1 || true
fi

# 13. Resumen final
cat > "$CASE_DIR/README_EVIDENCE.txt" << README
GMP AI Copilot — Evidence package for Claude Code

Generated: $(date)
Project: /home/ing_cpmo
Server: $(hostname)
User: $(whoami)

Purpose:
This package proves that infrastructure is already implemented.
Claude Code should NOT reinstall or recreate infrastructure.

Main validated state:
- API /health works.
- PostgreSQL works.
- Redis works.
- Ollama works.
- API connects to Ollama.
- Docker stack is active.
- systemd gmp-copilot is enabled/active.
- UFW rule for Docker to Ollama exists.
- backups exist.
- remaining work is functional API implementation.

Known pending:
- POST /api/v1/query
- GET /api/v1/knowledge/stats
- GET /api/v1/audit/verify
- GET /api/v1/protocol-template/IQ
- knowledge/retriever.py
- tests/test_agents.py
README

# Crear paquete
tar -czf "$TAR_FILE" -C "$OUT_DIR" "$(basename "$CASE_DIR")"

echo ""
echo "Evidencia generada:"
echo "$CASE_DIR"
echo ""
echo "Paquete comprimido:"
echo "$TAR_FILE"
echo ""
echo "Contenido:"
tar -tzf "$TAR_FILE" | sed 's/^/  /'
