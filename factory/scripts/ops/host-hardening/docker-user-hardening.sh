#!/bin/bash
# W8 Fase 0 — GMP AI Factory. Reaplica las reglas DOCKER-USER tras arrancar
# Docker (Docker crea la cadena vacía en cada arranque; sin esto, los puertos
# de datos de contenedor quedan alcanzables desde internet saltando UFW).
# Idempotente: -C comprueba antes de insertar. Reversible: systemctl disable.
set -u
IFACE="${IFACE:-ens4}"
PORTS="6379 5432 6380 6381 5433 5434"
COMMENT="W8-F0: datos de contenedor no expuestos a internet"

for i in $(seq 1 30); do
  iptables -L DOCKER-USER -n >/dev/null 2>&1 && break
  sleep 2
done
iptables -L DOCKER-USER -n >/dev/null 2>&1 || { echo "DOCKER-USER ausente; Docker no arrancó"; exit 1; }

for PORT in $PORTS; do
  if ! iptables -C DOCKER-USER -i "$IFACE" -p tcp -m conntrack --ctorigdstport "$PORT" \
        -j DROP -m comment --comment "$COMMENT" 2>/dev/null; then
    iptables -I DOCKER-USER 1 -i "$IFACE" -p tcp -m conntrack --ctorigdstport "$PORT" \
        -j DROP -m comment --comment "$COMMENT"
    echo "regla añadida: $PORT"
  else
    echo "regla ya presente: $PORT"
  fi
done
