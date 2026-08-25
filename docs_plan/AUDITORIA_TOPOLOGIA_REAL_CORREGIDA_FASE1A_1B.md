# FASE 1A/1B — RECONSTRUCCIÓN READ-ONLY DE LA TOPOLOGÍA ARIA
Generado por Claude Code (Capa 8) — 2026-08-25/26, bajo autorización de
Capa 9 (Cesar) para FASE 1 ÚNICAMENTE de
`docs_plan/PLAN_DESACOPLE_HOTELBOT_ARIA.md`. **100% solo lectura.** Cero
`docker up/down/restart/rm/create`. Cero mv/rm/mkdir/touch sobre el
filesystem real. El YAML de la Fase 1B es un artefacto de diseño, NUNCA
ejecutado.

Fuentes: `docker ps -a`, `docker inspect`, `docker network inspect`,
`docker volume inspect`, `docker image inspect`, `docker logs`. Ningún
valor fue inventado — todo lo que sigue está tomado literal de esas
salidas o marcado explícitamente como no determinado.

**Nota sobre secretos:** las contraseñas reales (Redis, Postgres,
`SECRET_KEY`, `ASTERISK_ARI_PASSWORD`) y la IP pública del host
aparecieron en texto plano en `docker inspect` (no hay mecanismo de
secretos real en este stack — es una debilidad preexistente, no algo que
esta auditoría introduce). Se confirmó que son consistentes entre los
servicios que las comparten, pero **no se transcriben aquí ni en el YAML
reconstruido** — se reemplazan por `${VARIABLE}`.

────────────────────────────────────────────────────────────────────────────
FASE 1A — MAPA COMPLETO
────────────────────────────────────────────────────────────────────────────

**Inventario total del host — 18 contenedores, 0 sin clasificar:**
`gmp-api/postgres/redis` (GMP_COMPONENT), `factory-api` (GMP_COMPONENT),
`lab_qc_project_*`/`oos_hplc_investigator_*` (soluciones custom de la
Factory, GMP_COMPONENT), y los 8 de ARIA/backend abajo. **Ningún
componente ARIA adicional a los 8 ya conocidos** — confirmado por
`docker ps -a` sin filtrar: no hay `vosk`, `kokoro-tts`, `dashboard`,
`nginx` corriendo pese a que existen en la definición histórica de
`/home/ing_cpmo/ARIA/03-code/src/docker-compose.local.yml` (ese archivo
describe un stack de desarrollo local que NO es el que corre en
producción hoy).

**Red:** una sola, `hotelbot_aria_net` (bridge, local), con los 8
contenedores + nada más.

**Volúmenes:** 7, todos con prefijo `hotelbot_`, todos atados a un
contenedor existente (ninguno realmente huérfano):
`hotelbot_postgres_data` (47MB), `hotelbot_redis_data` (8KB),
`hotelbot_ollama_models` (4.1GB), `hotelbot_vosk_models` (68MB),
`hotelbot_asterisk_{sounds,logs,spool}` (~1.5MB combinado).

**Imágenes:** 6 custom (`hotelbot-ai-engine`, `hotelbot-tts`,
`hotelbot-orchestrator`, `hotelbot-celery-worker`, `hotelbot-ollama`,
`hotelbot-asterisk`, todas construidas 2026-04-26, sin Dockerfile fuente
localizable hoy — imposible reconstruir el `build:`, solo el `image:`
final) + 2 oficiales reutilizadas (`postgres:16-alpine`,
`redis:7-alpine`, mismas imágenes que usa el stack GMP, sin relación
funcional).

### Tabla por componente

| Servicio | Imagen@digest | WorkingDir | User | Entrypoint | Cmd | Restart | Healthcheck (test / interval / timeout / retries / start_period) | Recursos | Red | Puertos publicados | depends_on (label real) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ai-engine` | `hotelbot-ai-engine@sha256:8b699158…eecdbe0` | `/app` | (root, sin `User` declarado) | — | `uvicorn app.main:app --host 0.0.0.0 --port 7001 --workers 1` | `unless-stopped` | `curl -sf http://localhost:7001/health` / 10s / 5s / 15 / 30s | mem 4GiB, 2.0 CPU | `hotelbot_aria_net` | `7001/tcp`, `7010-7049/udp` | `ollama:healthy`, `tts:healthy`, `redis:healthy` |
| `tts` | `hotelbot-tts@sha256:0b2c70d6…d650c2f` | `/app` | root | — | `uvicorn app.main:app --host 0.0.0.0 --port 5500` | `unless-stopped` | `curl -sf http://localhost:5500/health` / 10s / 5s / 12 / 30s | mem 1GiB, 2.0 CPU | `hotelbot_aria_net` | (ninguno, solo interno) | (ninguno) |
| `orchestrator` | `hotelbot-orchestrator@sha256:fedea2eb…4a8c8b` | `/app` | root | — | `sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --access-log"` | `unless-stopped` | `curl -sf http://localhost:8000/health` / 10s / 5s / 12 / 30s | sin límite declarado | `hotelbot_aria_net` | (ninguno, solo interno) | `postgres:healthy`, `redis:healthy` |
| `celery-worker` | `hotelbot-celery-worker@sha256:2c3cd7b4…e99979b` | `/app` | root | — | `celery -A app.tasks.celery_app worker --loglevel=info --concurrency=8 -Q calls,campaigns,default` | `unless-stopped` | `celery inspect ping` / 30s / 15s / 5 / 30s | sin límite declarado | `hotelbot_aria_net` | (ninguno) | `redis:healthy`, `postgres:healthy` |
| `ollama` | `hotelbot-ollama@sha256:b166ed16…c66003` | (no declarado) | root | `/entrypoint.sh` | (ninguno adicional) | `unless-stopped` | `ollama list` / 15s / 10s / 30 / 2m | mem 8GiB, 3.0 CPU | `hotelbot_aria_net` | (ninguno, solo interno) | (ninguno) |
| `asterisk` | `hotelbot-asterisk@sha256:39a3b3be…33a4130` | `/` | root | `/docker-entrypoint.sh` | (ninguno adicional) | `unless-stopped` | `curl -sf http://localhost:8088/ari/asterisk/info -u aria:${ASTERISK_ARI_PASSWORD}` / 10s / 5s / 15 / 20s | sin límite declarado | `hotelbot_aria_net` | `5060/tcp`, `5060/udp`, `8088/tcp`, `10000-10049/udp` | (ninguno) |
| `postgres` (svc real: `hotelbot-postgres-1`) | `postgres:16-alpine@sha256:cf78e766…fc20685` | `/` | root | `docker-entrypoint.sh` | `postgres` | `unless-stopped` | `pg_isready -U aria -d aria` / 5s / 5s / 12 / 0s | sin límite declarado | `hotelbot_aria_net` | (ninguno, solo interno) | (ninguno) |
| `redis` (svc real: `hotelbot-redis-1`) | `redis:7-alpine@sha256:ff02b58f…fe28eadf` | `/data` | root | `docker-entrypoint.sh` | `redis-server --requirepass ${REDIS_PASSWORD} --save 60 1 --loglevel warning` | `unless-stopped` | `redis-cli -a ${REDIS_PASSWORD} ping` / 5s / 3s / 12 / 0s | sin límite declarado | `hotelbot_aria_net` | (ninguno, solo interno) | (ninguno) |

### Variables de entorno por servicio (sanitizadas)

```
ai-engine:      RTP_PORT_START=7010, RTP_PORT_END=7049, RTP_BIND_HOST=0.0.0.0,
                TTS_URL=http://tts:5500, OLLAMA_URL=http://ollama:11434,
                REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/1,
                VOSK_MODEL_PATH=/models/vosk-model-small-en-us-0.15,
                LLM_MODEL=mistral
tts:            TTS_VOICE=en_US-lessac-medium, TTS_SAMPLE_RATE=8000
orchestrator:   DATABASE_URL=postgresql+asyncpg://aria:${POSTGRES_PASSWORD}@postgres:5432/aria,
                REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0,
                MAX_CONCURRENT_CALLS=7, SECRET_KEY=${ARIA_SECRET_KEY},
                AI_ENGINE_URL=http://ai-engine:7001,
                ASTERISK_ARI_USER=aria, ASTERISK_ARI_PASSWORD=${ASTERISK_ARI_PASSWORD},
                ASTERISK_ARI_URL=http://asterisk:8088, ASTERISK_ARI_APP=hotelbot,
                ENVIRONMENT=development
celery-worker:  mismas ASTERISK_*/REDIS_URL/DATABASE_URL/SECRET_KEY/
                MAX_CONCURRENT_CALLS/AI_ENGINE_URL que orchestrator
ollama:         OLLAMA_HOST=0.0.0.0, OLLAMA_NUM_PARALLEL=2,
                OLLAMA_MAX_LOADED_MODELS=1, LLM_MODEL=mistral,
                NVIDIA_VISIBLE_DEVICES=all, NVIDIA_DRIVER_CAPABILITIES=compute,utility
                (heredadas de la imagen base -- este host no expuso GPU
                real en la inspección de hoy, no se confirma uso efectivo)
asterisk:       ASTERISK_ARI_PASSWORD=${ASTERISK_ARI_PASSWORD},
                PUBLIC_IP=${PUBLIC_IP}, SIP_TRUNK_HOST=(vacío),
                SIP_TRUNK_USER=(vacío), SIP_TRUNK_PASSWORD=(vacío)
postgres:       POSTGRES_USER=aria, POSTGRES_DB=aria,
                POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
redis:          (la contraseña va en el `command`, no en env — ver tabla)
```

### Bind mounts / volúmenes, íntegro

```
ai-engine:      vol hotelbot_vosk_models -> /models
ollama:         vol hotelbot_ollama_models -> /root/.ollama
asterisk:       vol hotelbot_asterisk_sounds -> /var/lib/asterisk/sounds
                vol hotelbot_asterisk_logs   -> /var/log/asterisk
                vol hotelbot_asterisk_spool  -> /var/spool/asterisk
                bind hotelbot/asterisk/docker-entrypoint.sh -> /docker-entrypoint.sh  [VACÍO -- ver causa raíz]
                bind hotelbot/asterisk/etc/asterisk -> /etc/asterisk-templates        [VACÍO]
postgres:       vol hotelbot_postgres_data -> /var/lib/postgresql/data
                bind hotelbot/postgres/init -> /docker-entrypoint-initdb.d           [VACÍO, inofensivo para Postgres]
redis:          vol hotelbot_redis_data -> /data
tts, orchestrator, celery-worker: sin mounts propios
```

### `ARIA_ASTERISK_EXIT127_ROOT_CAUSE` — causa raíz confirmada, no inferida

`docker inspect aria-asterisk` → `.State.Error` (texto exacto, generado
por el runtime OCI en el intento de arranque más reciente):

```
failed to create task for container: failed to create shim task: OCI
runtime create failed: runc create failed: unable to start container
process: error during container init: error mounting
"/home/ing_cpmo/hotelbot/asterisk/docker-entrypoint.sh" to rootfs at
"/docker-entrypoint.sh": mount src=.../docker-entrypoint.sh,
dst=/docker-entrypoint.sh, flags=MS_BIND|MS_REC: not a directory: Are
you trying to mount a directory onto a file (or vice-versa)?
```

La imagen (`ENTRYPOINT ["/docker-entrypoint.sh"]`) espera un ARCHIVO en
esa ruta dentro del contenedor. El bind mount de origen en el host
(`hotelbot/asterisk/docker-entrypoint.sh`) es hoy un DIRECTORIO VACÍO
(auto-creado por Docker cuando el path esperado no existe). Montar un
directorio sobre lo que el runtime espera como archivo hace fallar el
`create` del contenedor a nivel OCI, antes de ejecutar un solo byte de
Asterisk — de ahí el `Exited (127)`.

**Línea de tiempo, reconstruida de los propios timestamps del contenedor:**
`StartedAt=2026-08-19T22:35:51Z` (arranque exitoso anterior — los logs
muestran "Asterisk Ready", app Stasis creada, conexiones WebSocket
aceptadas, y luego "Asterisk cleanly ending (0)", un apagado limpio, no
un crash). `FinishedAt=2026-08-24T22:59:10Z` — el intento de
recreación/reinicio en esa fecha es el que falla con el error de mount
de arriba. Coincide EXACTAMENTE con el mtime de los 3 directorios vacíos
(`Aug 24 22:59`, ya documentado en la auditoría previa) — el archivo real
dejó de existir (o nunca se recreó tras alguna operación sobre ese path)
justo en ese momento, y el siguiente intento de arranque de Asterisk lo
heredó roto. **No se investigó qué proceso causó ese cambio en esa fecha
— es un hecho observado, no una hipótesis sobre el agente causante.**

**`ORIGINAL_COMPOSE_STATUS=NOT_FOUND_IN_INSPECTED_SOURCES`** — buscado en
el git propio de `hotelbot/` (2 commits, ninguno de ARIA), en
`/home/ing_cpmo/ARIA/03-code/src/` (existe un pariente no coincidente,
`docker-compose.local.yml`), y en `backups/` del árbol real (fuera de
alcance recorrer los backups completos en esta corrida read-only
acotada a Fase 1). No se declara "irrecuperable" — solo no encontrado en
las fuentes inspeccionadas hoy.

──────────────────────────────────────────────────────────────────────────────
CÁLCULO DE COMPLETITUD
──────────────────────────────────────────────────────────────────────────────

```
RUNTIME_RECONSTRUCTION_COMPLETENESS = ALTA (8/8 servicios con imagen@digest,
    entrypoint/cmd, env completo, mounts, red, puertos, restart policy y
    healthcheck con timing exacto, capturados en vivo)
CRITICAL_UNKNOWN_FIELDS = NINGUNO -- nada bloquea reproducir el runtime
    actual tal cual corre hoy (se declara `image:` directo, no se
    necesita `build:` para reproducir el estado en ejecución)
NONCRITICAL_UNKNOWN_FIELDS =
    - Dockerfile/build context de las 6 imágenes hotelbot-* (perdido,
      irrelevante para reproducir el runtime YA CONSTRUIDO, relevante
      solo si algún día hay que reconstruir las imágenes desde cero)
    - contenido real que deberían tener los 3 bind mounts vacíos de
      Asterisk/Postgres (no se puede reconstruir desde inspección en
      vivo -- nunca se ejecutó con contenido real capturable)
    - si `aria-ollama` usa GPU real en este host (env vars NVIDIA
      heredadas de la imagen base, sin confirmación de hardware GPU
      presente)
READY_TO_DRAFT_RECONSTRUCTED_COMPOSE = YES
```

──────────────────────────────────────────────────────────────────────────────
FASE 1B — docker-compose.aria.reconstructed.yml (DISEÑO, NO EJECUTAR)
──────────────────────────────────────────────────────────────────────────────

Ver archivo separado:
`docs_plan/docker-compose.aria.reconstructed.yml`

Reproduce el runtime tal cual está HOY: mismas imágenes por digest,
mismos puertos, mismas redes, mismos volúmenes (declarados `external:
true` — nunca crea volúmenes nuevos), mismo Postgres/Redis, sin
modernizar nada, sin corregir Asterisk, sin tocar `hotelbot/`. Secretos
vía `${VARIABLE}`, nunca copiados literales desde `docker inspect`.

### Validación estática runtime vs. compose — mismatches encontrados

```
1. build vs image: el YAML reconstruido usa `image:` con digest fijo
   para los 6 servicios hotelbot-* (no hay Dockerfile fuente para un
   `build:` fiel) -- funcionalmente idéntico mientras esas imágenes
   sigan existiendo en el daemon local; SE ROMPE si se intenta usar en
   otro host sin exportar/importar esas imágenes primero (no hay
   registry conocido que las tenga).
2. bind mounts de asterisk/postgres: declarados en el YAML apuntando a
   las mismas rutas relativas (`./asterisk/docker-entrypoint.sh`, etc.)
   -- el YAML por sí solo NO arregla que esos paths estén vacíos; un
   `docker compose up` real con este archivo, sobre un `hotelbot/` con
   esos paths tal como están hoy, REPRODUCIRÍA el mismo fallo de
   aria-asterisk, no lo corrige (correcto, por diseño: no modernizar,
   no corregir Asterisk).
3. `com.docker.compose.replace` visto en labels de `orchestrator` y
   `asterisk` (evidencia de que esos 2 contenedores puntuales fueron
   recreados al menos una vez reemplazando un contenedor anterior del
   mismo nombre) -- no afecta la reconstrucción, es ruido histórico, se
   documenta por transparencia.
4. `aria-ollama`: env vars NVIDIA presentes pero sin confirmación de GPU
   real -- el YAML las reproduce tal cual (fiel al runtime), sin agregar
   ni quitar reserva de GPU en `deploy:`, porque el contenedor vivo no
   tiene ninguna reserva de GPU declarada en `HostConfig` (mem/cpu límites
   sí, GPU no) -- serían no-op heredados de la imagen base, no una
   dependencia real confirmada.
```

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
ARIA_RUNTIME_COMPONENTS = ai-engine, tts, orchestrator, celery-worker,
    ollama, asterisk (6 servicios de aplicación) + postgres, redis
    (2 de backend) = 8 contenedores, ninguno adicional detectado
ARIA_SHARED_LEGACY_DEPENDENCIES = hotelbot/asterisk/docker-entrypoint.sh,
    hotelbot/asterisk/etc/asterisk, hotelbot/postgres/init (bind mounts
    en vivo hacia el checkout hotelbot/, vacíos hoy)
ARIA_DATABASE_BACKEND = hotelbot-postgres-1 (postgres:16-alpine, DB "aria")
ARIA_REDIS_BACKEND = hotelbot-redis-1 (redis:7-alpine)
ARIA_NETWORK_TOPOLOGY = red única hotelbot_aria_net (bridge), 8
    contenedores, DNS por nombre de servicio Compose (postgres/redis/
    ollama/tts/ai-engine/asterisk), sin segmentación interna
HOTELBOT_RUNTIME_DEPENDENCIES = 3 bind mounts (ver arriba), todos VACÍOS,
    estructuralmente requeridos para cualquier recreación futura
ARIA_ASTERISK_EXIT127_ROOT_CAUSE = bind mount de host (directorio vacío,
    auto-creado) sobre un path que la imagen espera como archivo
    (entrypoint) -- falla a nivel OCI runtime, confirmado por
    .State.Error textual, con línea de tiempo exacta (StartedAt 2026-08-19,
    FinishedAt 2026-08-24T22:59:10Z, coincidente con el mtime de los
    directorios vacíos)
RUNTIME_RECONSTRUCTION_COMPLETENESS = ALTA
CRITICAL_UNKNOWN_FIELDS = NINGUNO
NONCRITICAL_UNKNOWN_FIELDS = Dockerfiles/build context perdidos; contenido
    real perdido de los 3 bind mounts; uso real de GPU en aria-ollama
    sin confirmar
RECONSTRUCTED_COMPOSE_CREATED = YES
RECONSTRUCTED_COMPOSE_PATH = docs_plan/docker-compose.aria.reconstructed.yml
RUNTIME_VS_COMPOSE_MISMATCHES = 4 (ver sección de validación arriba, ninguno
    bloqueante para el propósito de "documentar el runtime tal cual",
    todos relevantes si algún día se intenta EJECUTAR este archivo)
READY_TO_DESIGN_PHASE_2 = YES (con las Fase 0 de PLAN_DESACOPLE_HOTELBOT_ARIA.md
    -- ARIA_OPERATIONAL_AUTHORITY=UNRESOLVED -- pendientes de definir
    quién aprueba tocar ARIA antes de que Fase 2 pueda ejecutarse, no solo
    diseñarse)

READY_FOR_PHASE_2 = NO
READY_FOR_PHASE_3 = NO
CUTOVER_AUTHORIZED = NO
```

STOP. No se levantó ningún stack. No se detuvo/reinició/recreó ningún
contenedor. No se tocaron volúmenes, redes, datos, `hotelbot/` ni GMP AI
Factory. No hay commit/push de esta corrida — queda para aprobación
explícita de Capa 9.
