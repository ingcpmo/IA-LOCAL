#!/bin/bash
# v1.1.0 — W8 Fase 0 + Fase 0.1. GMP AI Factory. Reaplica las reglas
# DOCKER-USER tras arrancar Docker (Docker crea la cadena vacía en cada
# arranque; sin esto, los puertos de contenedor quedan alcanzables desde
# internet saltando UFW). Idempotente: -C comprueba antes de insertar.
# Reversible: systemctl disable, o retirar solo las reglas de una fase
# filtrando por su comentario (ver README).
set -u
IFACE="${IFACE:-ens4}"
PORTS_FASE0="6379 5432 6380 6381 5433 5434"
COMMENT_FASE0="W8-F0: datos de contenedor no expuestos a internet"
# Fase 0.1: cierre del acceso directo a Mission Control y las 3 APIs ahora
# que Caddy (127.0.0.1, no afectado por estas reglas) las expone por TLS
# en 443. Requiere 443 alcanzable desde internet — ver reverse-proxy/README.md.
PORTS_FASE01="8000 9000 8101 8102"
COMMENT_FASE01="W8-F0.1: acceso directo cerrado, usar Caddy 443"

for i in $(seq 1 30); do
  iptables -L DOCKER-USER -n >/dev/null 2>&1 && break
  sleep 2
done
iptables -L DOCKER-USER -n >/dev/null 2>&1 || { echo "DOCKER-USER ausente; Docker no arrancó"; exit 1; }

apply_rules() { # $1=lista de puertos $2=comentario
  local ports="$1" comment="$2"
  for PORT in $ports; do
    if ! iptables -C DOCKER-USER -i "$IFACE" -p tcp -m conntrack --ctorigdstport "$PORT" \
          -j DROP -m comment --comment "$comment" 2>/dev/null; then
      iptables -I DOCKER-USER 1 -i "$IFACE" -p tcp -m conntrack --ctorigdstport "$PORT" \
          -j DROP -m comment --comment "$comment"
      echo "regla añadida: $PORT ($comment)"
    else
      echo "regla ya presente: $PORT ($comment)"
    fi
  done
}

apply_rules "$PORTS_FASE0" "$COMMENT_FASE0"
apply_rules "$PORTS_FASE01" "$COMMENT_FASE01"
