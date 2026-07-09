# W8 Fase 0 — Hardening de superficie de red (P0)

**Fecha:** 2026-07-09 · **Arranque autorizado por Cesar** (aprobación del
roadmap W8). Cero funcionalidad nueva; cero cambios en código de aplicación.

## 1. Hallazgo: la exposición era mayor que la registrada

El hallazgo previo se registró como "puerto 9000 expuesto". La verificación
en vivo mostró algo más amplio y más grave:

| Hecho verificado | Evidencia |
|---|---|
| La VM tiene IP pública | `35.243.160.0` (metadata GCP), `ens4` |
| 12 contenedores publicaban en `0.0.0.0` | `docker ps` |
| **Docker salta UFW** | `DOCKER-USER` vacía + 104 reglas DNAT en `nat/DOCKER` |
| Escaneo externo activo | IPs públicas en logs de factory-api y gmp-api |
| **`gmp-redis` en 0.0.0.0:6379 SIN contraseña** | `CONFIG GET requirepass` → vacío; `PING` → `+PONG` sin auth |
| Postgres/Redis de las 2 soluciones custom expuestos | 5433, 5434, 6380, 6381 |

Las reglas UFW para 8000/9000 eran en gran medida **decorativas**: el tráfico
a contenedores es FORWARD y atraviesa `DOCKER-USER` (vacía), no las cadenas
de UFW. Es un modo de fallo clásico de Docker + UFW.

**Escaneo observado (solo sondas, nunca rutas reales de la app):**
`GET /`, `/favicon.ico`, `/robots.txt`, `/sitemap.xml`, `/security.txt`,
`POST /mcp`, `GET /sse` (búsqueda de servidores MCP expuestos), desde
`66.132.195.103`, `66.132.172.187`, `81.4.164.154`, `71.6.135.131` (Shodan),
`45.156.128.10`, `65.49.1.x`. **Ninguna IP pública tocó jamás
`/mission-control` ni `/api/v1/layer9`**; todo el uso legítimo entra por el
gateway del host (`172.19.0.1`). No hay indicio de acceso autenticado ni de
compromiso; los endpoints exigen `x-api-key`. El Redis sin auth, en cambio,
no exige nada — de ahí la criticidad.

## 2. Aplicado en esta fase

### 2.1 Rebind a loopback de los datos de las soluciones custom
`deployments/oos_hplc_investigator/docker-compose.yml` y
`deployments/lab_qc_project/docker-compose.yml`: `"5434:5432"` →
`"127.0.0.1:5434:5432"` y equivalentes para 5433, 6380, 6381.
Seguro por construcción: los servicios se hablan por **DNS de Docker**
(`DATABASE_URL=postgresql://…@oos_hplc_investigator_postgres:5432/…`), no
por puertos del host. El puerto sigue disponible en `127.0.0.1` para
`psql`/backups. Recreados los 4 contenedores de datos; APIs no tocadas.

### 2.2 Defensa en profundidad: cadena `DOCKER-USER`
6 reglas `DROP` para tráfico que entra por `ens4` hacia puertos de datos de
contenedor (`-m conntrack --ctorigdstport`, correcto post-DNAT):
**6379, 5432** (stack base) y 6380, 6381, 5433, 5434 (custom, cinturón y
tirantes). El tráfico entre contenedores llega por `br-*` y el del host por
`lo`: no coinciden con las reglas.

Esto **mitiga el Redis sin contraseña del stack base sin tocar el
`docker-compose.yml` base** (archivo prohibido).

### 2.3 Persistencia (autorizada por Cesar)
`/usr/local/sbin/docker-user-hardening.sh` + unidad oneshot
`docker-user-hardening.service` (`After=docker.service`, `RemainAfterExit`,
`enabled`). Idempotente (`iptables -C` antes de insertar) y reversible
(`systemctl disable`). Verificado: re-ejecución no duplica reglas; tras
vaciar la cadena (simulacro de reinicio) la unidad reconstruye las 6.

### 2.4 Verificación post-cambio
4 APIs en `200` (8000, 9000, 8101, 8102) · conectividad interna
app→Postgres/Redis verificada en gmp-api y oos_hplc_investigator_api ·
acceso local a 5432/6379/5434/6381 intacto · `aria-*` (6) y `hotelbot-*` (2)
Up y sin tocar · backup de los 3 compose en
`backups/factory/w8_fase0_20260709T051938Z/`.

### 2.5 Trazabilidad de los artefactos del host (cierre de fase)
El script y la unidad de §2.3 se instalaron primero como estado manual del
host. Para el cierre de fase quedaron **versionados en
`factory/scripts/ops/host-hardening/`** (v1.0.0): copias byte-exactas,
`SHA256SUMS` (`8849b20f…` el script, `609ed9a6…` la unidad), procedimiento
de instalación/rollback en su `README.md`, y `verify_installed.sh` (solo
lectura) que comprueba hash instalado = repo, unidad enabled+active y las 6
reglas presentes. Ejecutado en el cierre: **PASS 5/5**. Fuente de verdad: el
repo; el host es artefacto instalado.

## 3. Decisiones de Cesar en esta fase (2026-07-09)

1. **Acceso a Mission Control: directo por IP pública.** Por tanto las APIs
   (8000, 9000, 8101, 8102) **NO se rebindean** a loopback: hacerlo dejaría
   a Cesar fuera de su propia consola. La superficie HTTP queda abierta,
   protegida por `x-api-key`.
2. **Persistencia: autorizada** (§2.3, aplicada).
3. **Stack base: solo firewall.** No se toca `docker-compose.yml` ni `.env`
   base. `gmp-redis`/`gmp-postgres` quedan tapados por `DOCKER-USER`, no
   corregidos de raíz.

## 4. Riesgo residual (abierto, con dueño)

1. **`gmp-redis` sigue sin `requirepass`** y publicado en `0.0.0.0` a nivel
   de Docker: solo el firewall lo tapa. Si un atacante obtiene ejecución en
   el host o en cualquier contenedor con ruta a la red del base, el Redis
   cede sin autenticación. Arreglo de raíz pendiente de autorización sobre
   archivos prohibidos (decisión §3.3, revisable).
2. **Superficie HTTP expuesta a internet** (4 APIs). `x-api-key` es la única
   barrera; no hay TLS (tráfico y clave viajan en claro), ni rate limiting,
   ni bloqueo de fuerza bruta. El escaneo activo ya está documentado.
   **Recomendación siguiente (W8 F0.1)**: allowlist de IP de origen en
   `DOCKER-USER` para 9000 (requiere la IP de Cesar) o, mejor, reverse proxy
   con TLS + auth delante — el acceso por IP pública sin cifrar a una
   consola que gobierna un sistema GMP es un hallazgo de auditoría por sí
   mismo.
3. **Firewall VPC de GCP no inspeccionado**: define la exposición real.
   Solo Cesar puede verificarlo (`gcloud compute firewall-rules list`).
4. Los 3 Redis siguen sin `requirepass` (los 2 custom ya solo en loopback).

## 5. Estado

Exposición crítica **mitigada y persistente**: el Redis sin auth del stack
base ya no es alcanzable desde `ens4`, y la mitigación sobrevive a un
reinicio. Superficie de datos de las soluciones custom **cerrada de raíz**.
Riesgo residual §4 documentado con dueño. Fase 0 **cerrada** en su alcance
aprobado; §4.2 se propone como W8 F0.1. Alcance principal commiteado en
`e59a553`; el cierre añade la trazabilidad §2.5 (artefactos del host
versionados con SHA-256, verificador PASS 5/5).
