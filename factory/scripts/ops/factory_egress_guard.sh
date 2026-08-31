#!/bin/sh
# ============================================================================
# H-5F (2026-08-29) -- NETWORK_LEVEL_CONTROL de egress para factory-api.
#
# Deny-by-default en la cadena OUTPUT del network namespace del contenedor.
# Permite EXCLUSIVAMENTE:
#   - loopback
#   - respuestas de conexiones entrantes ya establecidas (health :9000, UI)
#   - 127.0.0.0/8 (incl. resolver DNS embebido de Docker 127.0.0.11)
#   - la gateway del bridge SOLO en tcp/11434  -> Ollama LOCAL del host
#   - el propio subnet del bridge -> contenedores hermanos locales
# Cualquier otro destino saliente -> REJECT con icmp-net-unreachable, de modo
# que connect() falla de inmediato con ENETUNREACH ("FAIL por RED"), no un
# timeout. Esto es lo que permite declarar EGRESS_GUARANTEE=FORBIDDEN.
#
# El monkeypatch Python (local_only.network_locked) es defensa ADICIONAL en
# proceso; este guard es la prueba de aislamiento a nivel de red.
#
# Requiere: cap_add: NET_ADMIN (ver factory/docker-compose.factory.yml).
# Desactivable solo por FACTORY_EGRESS_GUARD=off (para diagnóstico explícito).
# ============================================================================
set -e

if [ "${FACTORY_EGRESS_GUARD:-on}" = "off" ]; then
    echo "[egress-guard] DESACTIVADO (FACTORY_EGRESS_GUARD=off) -- sin aislamiento de red" >&2
    exec "$@"
fi

if ! command -v iptables >/dev/null 2>&1; then
    echo "[egress-guard] FATAL: iptables ausente en la imagen -- no se puede aplicar NETWORK_LEVEL_CONTROL" >&2
    exit 97
fi
if ! iptables -L OUTPUT >/dev/null 2>&1; then
    echo "[egress-guard] FATAL: sin permiso para iptables (falta cap_add: NET_ADMIN)" >&2
    exit 98
fi

GW="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
IFACE="$(ip route 2>/dev/null | awk '/^default/ {print $5; exit}')"
[ -z "$IFACE" ] && IFACE=eth0
SUBNET="$(ip -o -f inet addr show "$IFACE" 2>/dev/null | awk '{print $4}')"

echo "[egress-guard] gw=${GW:-<none>} iface=${IFACE} subnet=${SUBNET:-<none>}" >&2

iptables -F OUTPUT
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -d 127.0.0.0/8 -j ACCEPT
if [ -n "$GW" ]; then
    iptables -A OUTPUT -d "$GW" -p tcp --dport 11434 -j ACCEPT      # Ollama local
    iptables -A OUTPUT -d "$GW" -p icmp -j ACCEPT                   # PMTU / diag
    iptables -A OUTPUT -d "$GW" -j REJECT --reject-with icmp-net-unreachable
fi
[ -n "$SUBNET" ] && iptables -A OUTPUT -d "$SUBNET" -j ACCEPT       # hermanos locales
iptables -A OUTPUT -j REJECT --reject-with icmp-net-unreachable     # todo lo demás
iptables -P OUTPUT DROP

echo "[egress-guard] OUTPUT bloqueado por defecto. Allowlist:" >&2
iptables -S OUTPUT >&2
echo "[egress-guard] arrancando: $*" >&2

exec "$@"
