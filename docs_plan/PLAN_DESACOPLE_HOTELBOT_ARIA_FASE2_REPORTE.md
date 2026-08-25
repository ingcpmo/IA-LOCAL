# FASE 2 — VALIDACIÓN EN STACK AISLADO — REPORTE
Autorizado por Cesar (Capa 9): `ARIA_OPERATIONAL_AUTHORITY=CESAR`,
"autorizo Fase 2". Ejecutada 2026-08-25/26 según
`docs_plan/PLAN_DESACOPLE_HOTELBOT_ARIA.md`.

──────────────────────────────────────────────────────────────────────────────
ALCANCE EJECUTADO
──────────────────────────────────────────────────────────────────────────────

Proyecto Compose completamente aislado, nombres/red/volúmenes/puertos
TODOS distintos de los reales: `aria-cutover-test` (`docs_plan/
docker-compose.aria.cutover-test.yml`), red `aria_cutover_test_net`,
volúmenes `aria-cutover-test_test_{postgres,redis}_data` (nuevos,
vacíos — nunca los 7 volúmenes `hotelbot_*` reales), puertos
`15432/16379/18000` (nunca `5432/6379/8000` reales).

**Servicios con lógica real, probados en compose completo:** `postgres`,
`redis`, `orchestrator`, `celery-worker` — los que ejecutan migraciones,
manejan colas y hablan con la base de datos.

**Servicios sin lógica de negocio propia, probados con `docker run`
aislado (más liviano, sin cadena de dependencias):** `tts`, `ollama`.

**Excluido a propósito de esta corrida:** `asterisk` (ya se sabe que
falla por el bind mount vacío — repetirlo no aporta información nueva, y
su rango de puertos UDP/SIP es más delicado de aislar sin motivo). Y
`ai-engine` en modo compose completo (requiere `ollama`+`tts`+`redis`
sanos simultáneos; su imagen/env/cmd ya están capturados con
completitud ALTA en la Fase 1 — no se consideró necesario para el
objetivo de esta fase).

──────────────────────────────────────────────────────────────────────────────
RESULTADOS
──────────────────────────────────────────────────────────────────────────────

**postgres, redis:** `healthy` en segundos, sin incidentes.

**orchestrator:** `healthy`. Logs confirman migración real aplicada
limpio: `Running upgrade -> 0001, initial schema` (una sola migración
existente). `GET /health` → `200 OK`,
`{"status":"ok","service":"orchestrator"}`. Los `WARNING ARI WebSocket
disconnected, retrying` son esperados y correctos (no hay `asterisk` en
este stack de prueba) — mismo patrón de reintento con backoff que ya se
ve en los logs del `aria-orchestrator` real.

**celery-worker:** `healthy`. Se conectó a Redis, registró las 3 colas
reales (`calls`, `campaigns`, `default`) y las 5 tareas reales
(`mark_stale_calls`, `pause/resume/start_campaign_task`,
`originate_call`) — confirma que el comando/imagen reconstruidos son
exactos.

**tts (run aislado):** arrancó, cargó la voz Piper
(`en_US-lessac-medium`), `GET /health` → `200 OK`,
`{"status":"ok","service":"tts","voice":"en_US-lessac-medium"}`.

**ollama (run aislado):** arrancó, `ollama list` respondió
inmediatamente (tabla vacía — sin modelo, correcto para un contenedor
nuevo sin el volumen real). **Hallazgo no anticipado:** el
`/entrypoint.sh` de la imagen dispara automáticamente un `pull` del
modelo (~4.4GB, consistente con el tamaño real de
`hotelbot_ollama_models`) al arrancar si no lo encuentra — explica por
qué ese volumen real pesa 4.1GB. Detenido a propósito antes de completar
la descarga (contenedor efímero, `--rm`, sin volumen real de por medio —
cero dato retenido).

**Limpieza:** `docker compose down -v` sobre el proyecto de prueba —
0 contenedores, 0 red, 0 volúmenes de prueba remanentes, confirmado.
Los 8 contenedores reales (`aria-*`, `hotelbot-postgres-1`,
`hotelbot-redis-1`) verificados en el mismo estado exacto antes y
después (`Up 23h`/`Exited (127) 23h`, sin cambios) — cero impacto.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
PHASE_2_EXECUTED = SI
ISOLATED_STACK_NAME = aria-cutover-test
REAL_RESOURCES_TOUCHED = NINGUNO (0 contenedores/red/volumen/puerto reales)
SERVICES_VALIDATED_FULL_COMPOSE = postgres, redis, orchestrator, celery-worker (4/4 healthy)
SERVICES_VALIDATED_STANDALONE = tts, ollama (2/2 arrancan y responden correctamente)
SERVICES_NOT_VALIDATED_THIS_PHASE = asterisk (conocido roto, no repetido a proposito),
    ai-engine (completitud ya ALTA desde Fase 1, no ejecutado en cadena completa)
MIGRATION_VALIDATED = SI (alembic upgrade head, 0001 initial schema, sin errores)
RECONSTRUCTED_COMPOSE_ACCURACY = CONFIRMADA para los 4 servicios probados en
    compose completo -- imagen/env/cmd/depends_on producen el comportamiento
    esperado sin ajustes
NEW_FINDING = ollama descarga el modelo automaticamente al arrancar si no
    esta presente (explica el tamano real de hotelbot_ollama_models)
CLEANUP_VERIFIED = SI (0 recursos de prueba remanentes)
REAL_CONTAINERS_UNCHANGED = SI (mismo estado exacto antes/despues)

READY_FOR_PHASE_3 = NO (sin cambios -- requiere aprobacion explicita
    adicional, ventana de mantenimiento, y el dueno operativo real de
    ARIA, no solo Cesar desde GMP AI Factory)
CUTOVER_AUTHORIZED = NO
```

STOP. No se ejecutó ningún cutover real, ningún `docker stop/rm` sobre
contenedores reales, ningún cambio a `hotelbot/` ni a volúmenes/redes
reales. Detenido para revisión y siguiente autorización explícita de
Capa 9.
