#!/usr/bin/env bash
# ensure_ollama_access.sh — Idempotente.
# Garantiza que la red Docker de un proyecto custom tenga acceso UFW
# al proceso Ollama nativo del host en el puerto 11434.
#
# Uso:
#   bash factory/scripts/ops/ensure_ollama_access.sh <project_id>
#
# Requiere: sudo (para ufw), docker, python3 con factory/ en el path.
# Seguro de correr N veces: si la regla ya existe no hace nada.

set -euo pipefail

PORT=11434
PROJECT_ID="${1:?Uso: $0 <project_id>}"
FACTORY_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; NC='\033[0m'; B='\033[1m'

ok()   { echo -e "  ${G}[OK]${NC}   $1"; }
info() { echo -e "  ${B}[INFO]${NC} $1"; }
warn() { echo -e "  ${Y}[WARN]${NC} $1"; }
fail() { echo -e "  ${R}[FAIL]${NC} $1"; exit 1; }

echo -e "${B}=== ensure_ollama_access — project: ${PROJECT_ID} ===${NC}"
echo "  host: $(hostname) | $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ── 1. Detectar red Docker del proyecto ──────────────────────────────────────

info "Buscando red Docker para '${PROJECT_ID}'..."
NETWORK_NAME=$(docker network ls --format "{{.Name}}" \
    | grep -i "${PROJECT_ID}" | head -1 || true)

if [[ -z "$NETWORK_NAME" ]]; then
    fail "No se encontró red Docker con nombre que contenga '${PROJECT_ID}'"
fi
ok "Red encontrada: ${NETWORK_NAME}"

# ── 2. Obtener subred ────────────────────────────────────────────────────────

SUBNET=$(docker network inspect "$NETWORK_NAME" \
    --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null | head -1)

if [[ -z "$SUBNET" ]]; then
    fail "No se pudo obtener la subred de la red '${NETWORK_NAME}'"
fi
ok "Subred: ${SUBNET}"

# ── 3. Verificar si la regla UFW ya existe ───────────────────────────────────

info "Verificando reglas UFW existentes para ${SUBNET} → :${PORT}..."
EXISTING=$(sudo ufw status | grep -F "${SUBNET}" | grep -F "${PORT}" || true)

if [[ -n "$EXISTING" ]]; then
    ok "Regla ya existe — nada que hacer (idempotente)."
    echo ""
    echo "  Reglas UFW activas para :${PORT}:"
    sudo ufw status | grep -F "${PORT}" | sed 's/^/    /'
    exit 0
fi

# ── 4. Añadir regla UFW ──────────────────────────────────────────────────────

info "Añadiendo regla: allow from ${SUBNET} to any port ${PORT} proto tcp"
sudo ufw allow from "${SUBNET}" to any port ${PORT} proto tcp \
    comment "Allow ${PROJECT_ID} to Ollama"
ok "Regla UFW añadida."

# ── 5. Registrar en audit factory ───────────────────────────────────────────

info "Registrando evento en factory_audit.jsonl..."
python3 - <<PYEOF
import sys
sys.path.insert(0, '${FACTORY_DIR}')
from factory.core.audit_writer import write_event
entry = write_event('network_access_configured', '${PROJECT_ID}', {
    'action': 'ufw_allow_added',
    'subnet': '${SUBNET}',
    'port': ${PORT},
    'network': '${NETWORK_NAME}',
    'proto': 'tcp',
    'comment': 'Allow ${PROJECT_ID} to Ollama',
})
print(f"  entry_id={entry.get('entry_id','?')}")
PYEOF
ok "Evento auditado en factory_audit.jsonl."

# ── 6. Mostrar estado final ──────────────────────────────────────────────────

echo ""
echo "  Reglas UFW activas para :${PORT}:"
sudo ufw status | grep -F "${PORT}" | sed 's/^/    /'
echo ""
ok "ensure_ollama_access completado para '${PROJECT_ID}'."
