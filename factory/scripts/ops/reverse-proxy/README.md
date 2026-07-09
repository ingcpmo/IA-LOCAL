# Reverse proxy TLS — Mission Control y APIs (W8 F0.1)

**Versión:** v1.1.0 · **Estado:** Fase 1 desplegada con **certificado real
de Let's Encrypt** (no autofirmado), validada en local (2026-07-09). Fase 2
(cierre de los puertos directos 8000/9000/8101/8102) **BLOQUEADA**: el
puerto 443 aún no es alcanzable desde internet — ver §"Bloqueo activo,
único paso pendiente" antes de tocar nada más.

**Fuente de verdad: este directorio.** El `/etc/caddy/Caddyfile` instalado
es una copia exacta de `Caddyfile` (verificar con `SHA256SUMS`). Cambios
futuros: editar aquí, `caddy validate`, nuevo hash, reinstalar — nunca
editar `/etc/caddy/Caddyfile` directamente.

## Qué resuelve

Las 4 consolas/APIs (Mission Control 9000, gmp-api 8000, lab_qc 8101,
oos_hplc 8102) estaban expuestas a internet **sin TLS**: la `x-api-key`
viajaba en claro. Caddy termina TLS en el puerto 443 con **certificado
público de confianza real** (Let's Encrypt, sin avisos de navegador) y
hace de reverse proxy hacia `127.0.0.1:<puerto original>`; Mission Control
además exige Basic Auth (segunda barrera, solo en la consola — las 3 APIs
conservan únicamente su `x-api-key`, para no romper consumidores
automatizados que no mandan Basic Auth).

## Topología: un puerto público, 4 nombres, certificado real

No hay dominio propio para esta VM. Se usa **sslip.io**, servicio DNS
wildcard público y gratuito sin registro: cualquier nombre terminado en
`<ip-con-guiones>.sslip.io` resuelve automáticamente a esa IP — verificado
que `35-243-160-0.sslip.io` resuelve a `35.243.160.0` desde el host y es
DNS público real (lo resuelve cualquiera, no solo esta VM). Esto permite
que Let's Encrypt valide el reto ACME (HTTP-01, puerto 80) y emita
certificados de confianza pública real — **confirmado en este despliegue**
(ver `SHA256SUMS`/log de Caddy): los 4 certificados fueron emitidos y son
verificables con `openssl x509` sin `-k`/`-insecure`.

Se descartaron dos alternativas antes de llegar a esta, ambas probadas en
este mismo despliegue y documentadas para no repetir la depuración:

1. **IP pública desnuda como nombre de sitio** — sin SNI (típico al
   conectar directo por IP, inválida per RFC 6066), Caddy resuelve el
   certificado por la IP **local** del socket, que tras el NAT 1:1 de GCP
   nunca es la IP pública. El certificado nunca calzaría.
2. **Nombre `.local` con CA propia de Caddy (`tls internal`)** — funciona
   técnicamente (SNI real), pero el certificado es autofirmado: cada
   navegador cliente lo rechaza por defecto y exige un paso manual de
   confianza. No es una solución final sostenible; se mantiene documentado
   como fallback solo si Let's Encrypt dejara de ser viable.

Si más adelante se quiere un dominio de marca propia, basta apuntar un
registro DNS (A o CNAME) a `35.243.160.0` y cambiar los 4 nombres en el
`Caddyfile` — cambio de minutos, Caddy vuelve a emitir automáticamente.

| Nombre (SNI) | Backend | Auth extra |
|---|---|---|
| `mission-control.35-243-160-0.sslip.io` | `127.0.0.1:9000` (factory-api) | Basic Auth (`cesar`) |
| `gmp-api.35-243-160-0.sslip.io` | `127.0.0.1:8000` | ninguna (x-api-key propia) |
| `lab-qc.35-243-160-0.sslip.io` | `127.0.0.1:8101` | ninguna |
| `oos-hplc.35-243-160-0.sslip.io` | `127.0.0.1:8102` | ninguna |

**No requiere ninguna configuración en tu máquina** (a diferencia del
diseño anterior con `.local`): los nombres son DNS público real, se
resuelven solos. Solo abrir `https://mission-control.35-243-160-0.sslip.io/`
una vez que el bloqueo de abajo esté resuelto.

Usuario/clave de Mission Control: entregados a Cesar fuera de este repo
(no se commitea la contraseña en texto plano; el `Caddyfile` solo contiene
el hash bcrypt).

## Bloqueo activo (2026-07-09): 443 no alcanzable desde internet — único paso pendiente

Evidencia exacta, verificada con un vantage point externo real (fuera de
la VM):

- **Puerto 80: alcanzable.** Prueba: Let's Encrypt completó el reto ACME
  HTTP-01 de los 4 nombres y emitió los 4 certificados reales (ver arriba)
  — eso solo es posible si los servidores de validación de Let's Encrypt,
  que están en internet, pudieron conectar al puerto 80 de esta VM.
- **Puerto 443: NO alcanzable.** `ECONNREFUSED` en una prueba directa
  desde fuera, repetida tras la emisión de los certificados.

UFW e `iptables` locales permiten ambos puertos (verificado). La
diferencia de comportamiento entre 80 y 443 confirma que el bloqueo está
específicamente en el **firewall de VPC de GCP**, no en el host. El
`gcloud` de esta VM está autenticado (cuenta de servicio de la instancia)
pero **sin scopes para leer ni modificar reglas de firewall**
(`gcloud compute firewall-rules list` → "insufficient authentication
scopes") — confirmado de nuevo en esta sesión.

**Único comando que hace falta, ejecutado por Cesar desde su propia
máquina o Cloud Shell** (instancia `ivr-ia`, zona `us-east1-b`, red
`default`, sin network tags — confirmado vía metadata de la instancia sin
necesitar scopes de `gcloud`; como el 80 ya pasa, probablemente ya existe
una regla amplia que solo le falta el 443 — revisar con
`gcloud compute firewall-rules list` antes de crear una nueva, para
editarla en vez de duplicar):

```bash
gcloud compute firewall-rules create allow-caddy-https \
  --network=default --direction=INGRESS --action=ALLOW \
  --rules=tcp:443 --source-ranges=0.0.0.0/0
```

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

## Rollback de Fase 1 (probado en vivo, 2026-07-09)

```bash
sudo systemctl disable --now caddy
```

Libera el puerto 443 de inmediato. Verificado: el acceso directo antiguo
(8000/9000/8101/8102) no se ve afectado en ningún momento porque Fase 2
(los DROP) no se ha aplicado — el rollback es un simple apagado del
proceso adicional, sin tocar nada preexistente. Para volver a levantarlo:
`sudo systemctl enable --now caddy`.

**Nota sobre renovación:** los certificados de Let's Encrypt duran 90
días; Caddy renueva solo (~30 días antes de expirar) reusando el mismo
reto HTTP-01 en el puerto 80. Por eso 80 debe seguir abierto de forma
permanente en la VPC, no solo para la emisión inicial.

## Notas de la implementación (para no repetir la depuración)

1. **Caddy corre como usuario `caddy` sin sudo.** En el diseño anterior
   con `tls internal`, sin la opción `skip_install_trust` Caddy intentaba
   instalar su CA en el almacén de confianza del SO vía `sudo tee`, fallaba
   en modo no interactivo, y la emisión de certificados quedaba en error.
   Ya no aplica con Let's Encrypt (no hay CA local que instalar), pero se
   deja la nota por si se vuelve a necesitar el fallback autofirmado.
2. **El esquema `https://` es obligatorio** en la dirección del sitio.
   Caddy solo infiere HTTPS automáticamente para `:443` sin nombre; con
   nombre de host, sigue siendo necesario declarar `https://` o el bloque
   queda en texto plano.
3. **Nombre de host, no IP**, como dirección de sitio — ver §Topología.
