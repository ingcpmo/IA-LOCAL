# AUDITORÍA READ-ONLY DE TOPOLOGÍA REAL — CORRECCIÓN POST-HALLAZGO ARIA/hotelbot
Generado por Claude Code (Capa 8) — 2026-08-25. 100% solo lectura. Cero
mv/rm/mkdir/touch. Cero docker up/down/restart/rm. Cero commit/push de
este documento en el momento de escribirlo (se commitea después, con
aprobación explícita, igual que el resto de la sesión). Cero edición de
ningún archivo, incluidos los ya creados hoy.

SUPERSEDE a `MAPA_REALIDAD_OPERATIVA.md` (nunca ejecutado) en el punto
específico de clasificar `hotelbot-postgres-1`/`hotelbot-redis-1` como
"huérfanos" — no lo son.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 0 — EL FIX DE HOY (e26e988) NO TOCÓ NADA EN VIVO
──────────────────────────────────────────────────────────────────────────────

**0.1 — labels sin cambio**, confirmado por `docker inspect` sobre los 8
contenedores relevantes: TODOS siguen con `project=hotelbot`,
`config_files=/home/ing_cpmo/hotelbot/docker-compose.yml` — exactamente
los labels con los que fueron creados. Docker no retro-etiqueta
contenedores existentes al editar el YAML; confirmado con evidencia, no
supuesto.

**0.2 — estado/health idéntico**, confirmado por `docker ps -a`:
```
aria-ai-engine: Up 22h (healthy)        aria-tts: Up 22h (healthy)
aria-orchestrator: Up 22h (healthy)     aria-celery-worker: Up 22h (healthy)
aria-ollama: Up 22h (healthy)           aria-asterisk: Exited (127) 22h ago
hotelbot-postgres-1: Up 22h (healthy)   hotelbot-redis-1: Up 22h (healthy)
```
Mismo patrón exacto documentado antes del fix. `LIVE_FIX_VERIFIED_INERT = CONFIRMADO`.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — MAPA DE TOPOLOGÍA REAL
──────────────────────────────────────────────────────────────────────────────

| Contenedor | project | working_dir | networks | mounts (origen→destino) | puertos expuestos | DNS/env hacia otros servicios | Clasificación |
|---|---|---|---|---|---|---|---|
| `gmp-api` | `ing_cpmo` | `/home/ing_cpmo` | `ing_cpmo_default` | bind: `data/`, `.cache/chroma`, `app/`, `knowledge/` | 8000 | `postgres:5432`, `redis:6379` (mismo proyecto) | **GMP_COMPONENT** |
| `gmp-postgres` | `ing_cpmo` | `/home/ing_cpmo` | `ing_cpmo_default` | vol: `ing_cpmo_gmp_postgres_data`; bind: `scripts/sql/init.sql` | 5432 | — | **GMP_COMPONENT** |
| `gmp-redis` | `ing_cpmo` | `/home/ing_cpmo` | `ing_cpmo_default` | vol: `ing_cpmo_gmp_redis_data` | 6379 | — | **GMP_COMPONENT** |
| `factory-api` | `factory` | `/home/ing_cpmo/factory` | `factory_default` | bind: `backups/factory`, `factory/` completo, `GMPAI/` | 8000 | — | **GMP_COMPONENT** |
| `aria-ai-engine` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | vol: `hotelbot_vosk_models` | 7001 + rango RTP UDP | — | **ARIA_COMPONENT** |
| `aria-tts` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | (ninguno) | 5500 | — | **ARIA_COMPONENT** |
| `aria-orchestrator` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | (ninguno) | 8000 | `postgres:5432` (DB `aria`), `redis:6379/0` | **ARIA_COMPONENT** |
| `aria-celery-worker` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | (ninguno) | 8000 | `postgres:5432` (DB `aria`), `redis:6379/0` | **ARIA_COMPONENT** |
| `aria-ollama` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | vol: `hotelbot_ollama_models` (4.1GB) | 11434 | — | **ARIA_COMPONENT** |
| `aria-asterisk` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | vol: `hotelbot_asterisk_{sounds,logs,spool}`; **bind: `hotelbot/asterisk/docker-entrypoint.sh`→`/docker-entrypoint.sh` (VACÍO), `hotelbot/asterisk/etc/asterisk`→`/etc/asterisk-templates` (VACÍO)** | — | — | **ARIA_COMPONENT** (roto — `Exited 127`, consistente con entrypoint bind-mounteado vacío) |
| `hotelbot-postgres-1` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | vol: `hotelbot_postgres_data` (47MB); **bind: `hotelbot/postgres/init`→`/docker-entrypoint-initdb.d` (VACÍO)** | 5432 | service=`postgres` — resuelto por DNS de `aria-orchestrator`/`aria-celery-worker` | **SHARED_OR_LEGACY_DEPENDENCY** |
| `hotelbot-redis-1` | `hotelbot` | `/home/ing_cpmo/hotelbot` | `hotelbot_aria_net` | vol: `hotelbot_redis_data` (8KB) | 6379 | service=`redis` — resuelto por DNS de `aria-orchestrator`/`aria-celery-worker`/`aria-ai-engine` | **SHARED_OR_LEGACY_DEPENDENCY** |

**Confirmado explícitamente:** `hotelbot-postgres-1`/`hotelbot-redis-1` =
`SHARED_OR_LEGACY_DEPENDENCY`, NUNCA `UNUSED` — son el backend real y
saludable de `aria-orchestrator`/`aria-celery-worker` vía resolución DNS
de Compose (`service: postgres`/`service: redis` en el mismo proyecto
`hotelbot`, única coincidencia de esos nombres en la red
`hotelbot_aria_net`).

**Los 3 bind mounts de `hotelbot/` re-confirmados VACÍOS**, mismo mtime
exacto que en el hallazgo previo (`Aug 24 22:59`, sin cambios):
`asterisk/docker-entrypoint.sh`, `asterisk/etc/asterisk`, `postgres/init`.
**Qué pasaría si el path dejara de existir:** para `hotelbot-postgres-1`
(sano hoy pese al bind vacío — Postgres simplemente no corre scripts de
init si el directorio está vacío, comportamiento normal): si el
contenedor se recreara o el host reiniciara y Docker necesitara re-crear
el mount, un `docker-entrypoint-initdb.d` que apunta a un path
inexistente hace fallar el `docker compose up`/`start` de ese servicio
(Docker no autocrea el path si el compose ya no lo referencia desde un
proyecto activo, o falla explícitamente según la versión/configuración).
Para `aria-asterisk`: ya está roto (`Exited 127`) precisamente por este
patrón — si algún día se repara el entrypoint real, ese path DEBE existir
con contenido real. **Es una dependencia estructural real de continuidad
operativa, no cosmética** — aplica igual de cara a cualquier reinicio
futuro del host o recreación de estos contenedores.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — INTEGRIDAD DEL CORPUS ROCKWELL
──────────────────────────────────────────────────────────────────────────────

**2.1 — Inventario actual:** `GMPAI/source/Rockwell/` = 14 archivos, 139MB.

**2.2 — Verificación hash contra `factory/regulatory/scope/
source_baseline_allowlist.yaml`:** 14/14 entradas (`RW-0001`…`RW-0014`)
con SHA-256 calculado en vivo sobre cada archivo real y comparado
carácter por carácter contra el valor de la allowlist. **0 faltantes, 0
discrepancias de hash.**

**2.3 — Los zips borrados en la sesión anterior (`Rockwell (1).zip`,
`Rockwell (1)_(1).zip`, ambos corruptos) NO eran la única copia de nada:**
existe `GMPAI/incoming/Rockwell.zip` (125,183,847 bytes, MD5
`bcf108b0233119fac60ac79293ee5f94` — DISTINTO de los dos borrados,
`e5c13094012bd6cc06019633b4997fc2`), verificado ÍNTEGRO en esta corrida
(`zipfile.testzip()` → `None`, 15 entradas legibles). Este es el archivo
canónico de ingesta; los 14 archivos ya extraídos en `source/Rockwell/`
(verificados 2.2) son el corpus de trabajo real. Los dos `.zip` sueltos
en la raíz del HOME eran copias redundantes y corruptas de un archivo que
YA tenía una copia sana en su ubicación canónica — la decisión de
borrarlos (sesión anterior) queda confirmada como correcta, no revisada
a la baja.

**2.4 — `ROCKWELL_CORPUS_INTEGRITY = CONFIRMADO`.** Sin discrepancias en
ningún punto de 2.1-2.3.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — CORRECCIÓN DE MEMORIA
──────────────────────────────────────────────────────────────────────────────

Corregido en `project_consolidacion_arbol_canonico.md` (entrada nueva,
sin reescribir la anterior) y en el índice `MEMORY.md`: donde decía
"huérfanos, documentados, sin tocar" ahora dice "dependencia compartida
activa de ARIA (backend real de aria-orchestrator/aria-celery-worker vía
hotelbot_aria_net), NO huérfana, NO removible sin desacople deliberado".

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
LIVE_FIX_VERIFIED_INERT = CONFIRMADO
CANONICAL_GMP_ROOT = /home/ing_cpmo (HEAD 33b5f99 al momento de esta corrida)
ARIA_ROOT = /home/ing_cpmo/ARIA (proyecto separado, no auditado en detalle -- fuera de alcance)
HOTELBOT_GIT_STATUS = LEGACY/STALE (HEAD 6a5e741, git limpio salvo cambios de HOY)
HOTELBOT_RUNTIME_STATUS = REFERENCED (bind mounts activos de aria-asterisk
    y hotelbot-postgres-1, vacios hoy pero estructuralmente requeridos)
HOTELBOT_REQUIRED_PATHS = hotelbot/asterisk/docker-entrypoint.sh,
    hotelbot/asterisk/etc/asterisk, hotelbot/postgres/init
ARIA_DATABASE_BACKEND = hotelbot-postgres-1 (via hotelbot_aria_net, service=postgres)
ARIA_REDIS_BACKEND = hotelbot-redis-1 (via hotelbot_aria_net, service=redis)
SHARED_NETWORKS = hotelbot_aria_net (8 contenedores: 6 ARIA + 2 backend)
PORT_COLLISIONS = confirmado, ya documentado y ya mitigado parcialmente
    (container_name/project ya no colisionan desde e26e988; puertos
    5432/6379/8000 siguen siendo el mismo valor fijo que produccion,
    sin resolver, fuera de alcance de ese fix)
ROCKWELL_CORPUS_INTEGRITY = CONFIRMADO (14/14 archivos, 0 discrepancias)
MISSING_REGULATORY_ARTIFACTS = NINGUNO
RUNTIME_TOPOLOGY_CONFIRMED = YES
SAFE_TO_USE_HOTELBOT_AS_SANDBOX = NO (confirmado, sin cambios)
SAFE_TO_DECOMMISSION_HOTELBOT = NO (confirmado, sin cambios -- dependencia
    estructural de ARIA, no solo de codigo)
BLOCKERS_REQUIRING_DESIGN = desacople controlado de hotelbot/ARIA (mover
    los bind mounts de asterisk/postgres a un path fuera de un checkout
    de codigo desechable, y decidir el destino real de esos 2
    contenedores backend) -- fuera de alcance de esta corrida
MEMORY_CORRECTED = SI (project_consolidacion_arbol_canonico.md + MEMORY.md)
```
