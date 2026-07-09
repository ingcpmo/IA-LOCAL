# Reverse proxy TLS — Mission Control y APIs (W8 F0.1)

**Versión:** v1.0.0 · **Estado:** Fase 1 desplegada y validada en local
(2026-07-09). Fase 2 (cierre de los puertos directos 8000/9000/8101/8102)
**BLOQUEADA**: el puerto 443 aún no es alcanzable desde internet — ver
§"Bloqueo activo" antes de tocar nada más.

**Fuente de verdad: este directorio.** El `/etc/caddy/Caddyfile` instalado
es una copia exacta de `Caddyfile` (verificar con `SHA256SUMS`). Cambios
futuros: editar aquí, `caddy validate`, nuevo hash, reinstalar — nunca
editar `/etc/caddy/Caddyfile` directamente.

## Qué resuelve

Las 4 consolas/APIs (Mission Control 9000, gmp-api 8000, lab_qc 8101,
oos_hplc 8102) estaban expuestas a internet **sin TLS**: la `x-api-key`
viajaba en claro. Caddy termina TLS en el puerto 443 y hace de reverse
proxy hacia `127.0.0.1:<puerto original>`; Mission Control además exige
Basic Auth (segunda barrera, solo en la consola — las 3 APIs conservan
únicamente su `x-api-key`, para no romper consumidores automatizados que
no mandan Basic Auth).

## Topología: un puerto público, 4 nombres

No hay dominio DNS público para la VM (NAT 1:1 de GCP, sin hostname
externo). Probado y descartado usar la IP pública como nombre de sitio:
sin SNI (los clientes no mandan SNI válida para IPs, RFC 6066), Caddy
resuelve el certificado por la IP **local** del socket, que tras el NAT de
GCP nunca es la IP pública — el certificado jamás calzaría. La solución:
**4 nombres de host + `tls internal`** (CA local de Caddy), todos servidos
en el mismo puerto 443, enrutados por SNI/Host:

| Nombre (SNI) | Backend | Auth extra |
|---|---|---|
| `mission-control.gmp-factory.local` | `127.0.0.1:9000` (factory-api) | Basic Auth (`cesar`) |
| `gmp-api.gmp-factory.local` | `127.0.0.1:8000` | ninguna (x-api-key propia) |
| `lab-qc.gmp-factory.local` | `127.0.0.1:8101` | ninguna |
| `oos-hplc.gmp-factory.local` | `127.0.0.1:8102` | ninguna |

## Configuración necesaria en el cliente (una vez, en tu máquina — NO en el servidor)

Agregar al archivo hosts 4 líneas apuntando a la IP pública de la VM
(`35.243.160.0`):

- Linux/Mac: `/etc/hosts`
- Windows: `C:\Windows\System32\drivers\etc\hosts` (como administrador)

```
35.243.160.0  mission-control.gmp-factory.local
35.243.160.0  gmp-api.gmp-factory.local
35.243.160.0  lab-qc.gmp-factory.local
35.243.160.0  oos-hplc.gmp-factory.local
```

Después, abrir `https://mission-control.gmp-factory.local/`. El navegador
avisará de certificado no confiable la primera vez (CA propia de Caddy, no
pública) — aceptar la excepción, o importar la CA exportada en
`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt` en el
almacén de confianza de tu SO/navegador para que deje de avisar.

Usuario/clave de Mission Control: entregados a Cesar fuera de este repo
(no se commitea la contraseña en texto plano; el `Caddyfile` solo contiene
el hash bcrypt).

## Bloqueo activo (2026-07-09): 443 no alcanzable desde internet

Confirmado con una prueba real desde fuera de la VM: 443 responde
`ECONNREFUSED` mientras 8000/9000/8101/8102 sí responden. Los puertos
nuevos pasan UFW y `iptables` en el host (verificado local), así que el
bloqueo está en el **firewall de VPC de GCP**, que solo permite hoy los 4
puertos antiguos. El `gcloud` de esta VM no tiene scopes para leer ni
modificar reglas de firewall — **acción pendiente de Cesar**, desde su
propia máquina o Cloud Shell. Datos ya confirmados vía metadata de la
instancia (sin necesitar scopes): instancia `ivr-ia`, zona `us-east1-b`,
red `default`, **sin network tags** (`[]`) — por tanto la nueva regla no
necesita `--target-tags`, igual que las reglas ya vigentes para 8000/9000:

```bash
gcloud compute firewall-rules create allow-caddy-https \
  --project=<PROJECT_ID_o_733435082116> \
  --network=default --direction=INGRESS --action=ALLOW \
  --rules=tcp:443 --source-ranges=0.0.0.0/0
```

(Verificar antes con `gcloud compute firewall-rules list --format="table(name,sourceRanges.list(),allowed[].map().firewall_rule().list())"`
para confirmar el nombre exacto de la regla que hoy permite 8000/9000 y
replicar su mismo patrón para 443, en vez de crear una nueva si ya existe
una regla amplia editable.)
**Hasta que esto no esté confirmado alcanzable, NO se deben aplicar las
reglas DROP de Fase 2** (`factory/scripts/ops/host-hardening/`): cortarían
el único acceso funcional a Mission Control.

## Verificar que el host no ha derivado del repo

```bash
sudo bash factory/scripts/ops/reverse-proxy/verify_installed.sh
```

Solo lectura: hash del Caddyfile instalado vs. repo, servicio
`enabled`+`active`, puerto 443 escuchando.

## Instalación / reinstalación

```bash
caddy validate --config Caddyfile --adapter caddyfile
sudo install -o root -g root -m 0644 Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

## Rollback (probado 2026-07-09)

```bash
sudo systemctl disable --now caddy
```

Libera el puerto 443 de inmediato. Verificado: el acceso directo antiguo
(8000/9000/8101/8102) no se ve afectado en ningún momento porque Fase 2
(los DROP) no se ha aplicado — el rollback es un simple apagado del
proceso adicional, sin tocar nada preexistente. Para volver a levantarlo:
`sudo systemctl enable --now caddy`.

## Notas de la implementación (para no repetir la depuración)

1. **Caddy corre como usuario `caddy` sin sudo.** Sin la opción global
   `skip_install_trust`, intenta instalar su CA en el almacén de confianza
   del SO vía `sudo tee` en cada arranque, falla en modo no interactivo, y
   la emisión de certificados queda en error (todas las rutas responden
   `tlsv1 alert internal error`). `skip_install_trust` evita el intento;
   no hace falta que el propio host confíe en su CA.
2. **El esquema `https://` es obligatorio** en la dirección del sitio.
   Caddy solo infiere HTTPS automáticamente para `:443` sin nombre; con
   nombre de host + puerto explícito por defecto (443), sigue siendo
   necesario declarar `https://` o el bloque queda en texto plano.
3. **Nombre de host, no IP**, como dirección de sitio — ver §Topología.
