# Hardening persistente del host — cadena DOCKER-USER (W8 Fase 0)

**Versión:** v1.0.0 · **Instalado en el host:** 2026-07-09 (aprobado por
Cesar, informe `factory/docs/W8_FASE0_HARDENING.md` §2.2–2.3).

**Fuente de verdad: este directorio.** Los archivos instalados en el host
son artefactos de despliegue de estas copias versionadas. Cualquier cambio
se hace primero aquí (nueva versión + nuevo `SHA256SUMS` + commit) y después
se reinstala en el host. Nunca al revés.

## Contenido

| Archivo en repo | Instalado en | Modo | SHA-256 |
|---|---|---|---|
| `docker-user-hardening.sh` | `/usr/local/sbin/docker-user-hardening.sh` | `root:root 0755` | `8849b20f92fc85ca0ee0fad859f5a7991109239d883ed89490aca2891925529f` |
| `docker-user-hardening.service` | `/etc/systemd/system/docker-user-hardening.service` | `root:root 0644` | `609ed9a6966409d35a2ed07cc60e65857beea58f9da496955e33463d8e8b877d` |

`SHA256SUMS` contiene los mismos hashes en formato verificable
(`sha256sum -c SHA256SUMS`).

## Qué hace

Docker crea la cadena `DOCKER-USER` **vacía** en cada arranque, de modo que
los puertos publicados por contenedores saltan UFW. El script inserta 6
reglas `DROP` para tráfico entrante por `ens4` hacia los puertos de datos
(6379, 5432, 6380, 6381, 5433, 5434), usando `-m conntrack --ctorigdstport`
(correcto post-DNAT). Idempotente: comprueba con `iptables -C` antes de
insertar. La unidad `oneshot` (`After=docker.service`, `RemainAfterExit`)
lo reaplica tras cada arranque de Docker.

No toca los puertos de API (8000, 9000, 8101, 8102) ni tráfico entre
contenedores (`br-*`) ni del host (`lo`).

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

```bash
sudo systemctl disable --now docker-user-hardening.service
# opcional: retirar las reglas ya insertadas sin esperar reinicio
sudo iptables -S DOCKER-USER | grep 'W8-F0' | sed 's/^-A/-D/' | while read -r r; do sudo iptables $r; done
```

Deja el host como antes de W8 F0 (los puertos de datos vuelven a quedar
alcanzables desde internet: hacerlo solo con causa).
