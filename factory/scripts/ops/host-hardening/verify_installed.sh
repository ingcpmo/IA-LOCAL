#!/bin/bash
# W8 F0 — Verifica que el hardening instalado en el host coincide con el
# repo (fuente de verdad) y sigue operativo. SOLO LECTURA: no modifica nada.
set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

check() { # $1=descripcion $2=resultado(0/!=0)
  if [ "$2" -eq 0 ]; then echo "OK   $1"; else echo "FAIL $1"; FAIL=1; fi
}

# 1. Hashes de los archivos instalados contra SHA256SUMS del repo
H_SH=$(sha256sum /usr/local/sbin/docker-user-hardening.sh 2>/dev/null | cut -d' ' -f1)
H_SVC=$(sha256sum /etc/systemd/system/docker-user-hardening.service 2>/dev/null | cut -d' ' -f1)
E_SH=$(grep ' docker-user-hardening.sh$' "$DIR/SHA256SUMS" | cut -d' ' -f1)
E_SVC=$(grep ' docker-user-hardening.service$' "$DIR/SHA256SUMS" | cut -d' ' -f1)
[ -n "$H_SH" ] && [ "$H_SH" = "$E_SH" ]; check "script instalado = repo ($E_SH)" $?
[ -n "$H_SVC" ] && [ "$H_SVC" = "$E_SVC" ]; check "unidad instalada = repo ($E_SVC)" $?

# 2. Unidad habilitada y activa
systemctl is-enabled --quiet docker-user-hardening.service; check "unidad enabled" $?
systemctl is-active  --quiet docker-user-hardening.service; check "unidad active" $?

# 3. Las 6 reglas de Fase 0 + las 4 de Fase 0.1 presentes en DOCKER-USER
N0=$(iptables -S DOCKER-USER 2>/dev/null | grep -c 'W8-F0:')
N01=$(iptables -S DOCKER-USER 2>/dev/null | grep -c 'W8-F0.1:')
[ "$N0" -eq 6 ]; check "6 reglas W8-F0 en DOCKER-USER (halladas: $N0)" $?
[ "$N01" -eq 4 ]; check "4 reglas W8-F0.1 en DOCKER-USER (halladas: $N01)" $?

[ "$FAIL" -eq 0 ] && echo "RESULTADO: PASS" || echo "RESULTADO: FAIL"
exit "$FAIL"
