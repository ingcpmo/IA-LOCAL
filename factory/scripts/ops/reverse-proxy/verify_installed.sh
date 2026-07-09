#!/bin/bash
# W8 F0.1 — Verifica que el reverse proxy instalado en el host coincide con
# el repo (fuente de verdad) y sigue operativo. SOLO LECTURA: no modifica nada.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

check() { # $1=descripcion $2=resultado(0/!=0)
  if [ "$2" -eq 0 ]; then echo "OK   $1"; else echo "FAIL $1"; FAIL=1; fi
}

H_CF=$(sha256sum /etc/caddy/Caddyfile 2>/dev/null | cut -d' ' -f1)
E_CF=$(grep ' Caddyfile$' "$DIR/SHA256SUMS" | cut -d' ' -f1)
[ -n "$H_CF" ] && [ "$H_CF" = "$E_CF" ]; check "Caddyfile instalado = repo ($E_CF)" $?

systemctl is-enabled --quiet caddy; check "servicio caddy enabled" $?
systemctl is-active  --quiet caddy; check "servicio caddy active" $?

ss -tln 2>/dev/null | grep -q ':443 '; check "puerto 443 escuchando" $?

[ "$FAIL" -eq 0 ] && echo "RESULTADO: PASS" || echo "RESULTADO: FAIL"
exit "$FAIL"
