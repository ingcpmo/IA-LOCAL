# Hardening persistente del host — cadena DOCKER-USER (W8 Fase 0 + Fase 0.1)

**Versión:** v1.1.0 · **Fase 0 instalada:** 2026-07-09 (aprobado por Cesar,
informe `factory/docs/W8_FASE0_HARDENING.md` §2.2–2.3). **Fase 0.1 (cierre
de 8000/9000/8101/8102) instalada:** 2026-07-10, tras confirmar 443
alcanzable desde internet (prueba de navegador real de Cesar + checker
externo independiente) — ver `reverse-proxy/README.md`.

**Fuente de verdad: este directorio.** Los archivos instalados en el host
son artefactos de despliegue de estas copias versionadas. Cualquier cambio
se hace primero aquí (nueva versión + nuevo `SHA256SUMS` + commit) y después
se reinstala en el host. Nunca al revés.

## Contenido

| Archivo en repo | Instalado en | Modo | SHA-256 |
|---|---|---|---|
| `docker-user-hardening.sh` | `/usr/local/sbin/docker-user-hardening.sh` | `root:root 0755` | `218086e9dc7d82cb1fccb9256f6bbd09891bf21b0980fb7a4261e03f8ab74840` |
| `docker-user-hardening.service` | `/etc/systemd/system/docker-user-hardening.service` | `root:root 0644` | `609ed9a6966409d35a2ed07cc60e65857beea58f9da496955e33463d8e8b877d` |

`SHA256SUMS` contiene los mismos hashes en formato verificable
(`sha256sum -c SHA256SUMS`).

## Qué hace

Docker crea la cadena `DOCKER-USER` **vacía** en cada arranque, de modo que
los puertos publicados por contenedores saltan UFW. El script inserta:

- **Fase 0** (6 reglas, comentario `W8-F0:`): tráfico entrante por `ens4`
  hacia los puertos de datos (6379, 5432, 6380, 6381, 5433, 5434).
- **Fase 0.1** (4 reglas, comentario `W8-F0.1:`): tráfico entrante por
  `ens4` hacia los puertos directos de Mission Control/APIs (8000, 9000,
  8101, 8102) — cerrados porque ahora se sirven por Caddy en 443 con TLS
  real (ver `../reverse-proxy/`). Caddy llega a los backends por
  `127.0.0.1`, que no pasa por `ens4` y por tanto nunca se bloquea.

Ambas usan `-m conntrack --ctorigdstport` (correcto post-DNAT). Idempotente:
comprueba con `iptables -C` antes de insertar. La unidad `oneshot`
(`After=docker.service`, `RemainAfterExit`) reaplica las 10 reglas tras
cada arranque de Docker.

No toca tráfico entre contenedores (`br-*`) ni del host (`lo`).

## Verificar que el host no ha derivado del repo

```bash
sudo bash factory/scripts/ops/host-hardening/verify_installed.sh
```

Solo lectura. Comprueba: hash de los 2 archivos instalados contra
`SHA256SUMS`, unidad `enabled` + `active`, y las 6 reglas presentes en
`DOCKER-USER`.

## Instalación / reinstalación (idéntica a la aplicada el 2026-07-09)

```bash
sudo install -o root -g root -m 0755 docker-user-hardening.sh /usr/local/sbin/docker-user-hardening.sh
sudo install -o root -g root -m 0644 docker-user-hardening.service /etc/systemd/system/docker-user-hardening.service
sudo systemctl daemon-reload
sudo systemctl enable --now docker-user-hardening.service
```

## Rollback

Completo (Fase 0 + Fase 0.1 — deja el host como antes de W8, todos los
puertos vuelven a quedar alcanzables desde internet: hacerlo solo con
causa):

```bash
sudo systemctl disable --now docker-user-hardening.service
sudo iptables -S DOCKER-USER | grep 'W8-F0' | sed 's/^-A/-D/' | while read -r r; do eval "sudo iptables $r"; done
```

Solo Fase 0.1 (reabre 8000/9000/8101/8102 sin tocar Fase 0 ni la unidad
systemd — usar si algo falla con Caddy/443 y hace falta el acceso directo
de vuelta mientras se investiga):

```bash
sudo iptables -S DOCKER-USER | grep 'W8-F0.1:' | sed 's/^-A/-D/' | while read -r r; do eval "sudo iptables $r"; done
```

**Nota:** el `eval` es obligatorio — el comentario de la regla contiene
espacios y dos puntos; sin `eval`, `$r` se parte en varios argumentos por
`word splitting` de bash y `iptables` falla con `Bad argument`. Probado en
vivo (2026-07-10): quitar las 4 reglas de Fase 0.1 → 0 reglas → reaplicar
con el script (idempotente) → 4 reglas de nuevo, sin tocar las 6 de Fase 0.

Para restaurar Fase 0.1 tras un rollback puntual: reejecutar
`docker-user-hardening.sh` (reinserta solo lo que falte, es idempotente).
