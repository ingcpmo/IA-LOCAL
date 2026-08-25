# FASE 3 — CUTOVER REAL — REPORTE
Autorizado por Cesar (Capa 9), confirmando ser también la autoridad
operativa de ARIA: `ARIA_OPERATIONAL_AUTHORITY=CESAR`, "autorizo Fase 3".
Downtime aceptado de inmediato. Ejecutado 2026-08-25/26.

Decisiones de Fase 0 resueltas por Cesar en el momento:
- Autoridad: Cesar cubre tanto GMP AI Factory como ARIA.
- Downtime: aceptado ahora mismo, sin ventana programada.
- Destino del compose: `/home/ing_cpmo/ARIA/deploy/`.
- Bind mounts vacíos: removidos de la definición (no se restaura
  configuración de Asterisk perdida).

──────────────────────────────────────────────────────────────────────────────
HALLAZGO PREVIO A TOCAR NADA — CAMBIA EL RESULTADO ESPERADO PARA ASTERISK
──────────────────────────────────────────────────────────────────────────────

Antes de ejecutar, se verificó (leyendo el contenido real de la imagen
`hotelbot-asterisk`, sin el bind mount vacío encima) que la imagen SÍ
tiene un `/docker-entrypoint.sh` real y funcional (510 bytes). Ese script
depende de `/etc/asterisk-templates/` con contenido real
(`ari.conf`, `pjsip.conf`) para copiarlo a `/etc/asterisk/` — y esa
carpeta **no existe en la imagen**, solo se esperaba del bind mount del
host, cuyo contenido real está perdido. Conclusión correcta, no
optimista: quitar los bind mounts arregla el crash de nivel OCI (el
contenedor pasa a poder *arrancar*), pero Asterisk sigue sin poder
funcionar — el fallo se vuelve más claro y diagnosticable, no desaparece.
Confirmado exactamente así tras el cutover (ver resultado).

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN
──────────────────────────────────────────────────────────────────────────────

**3.1 — Snapshot de datos reales, antes de tocar nada:**
`/home/ing_cpmo/backups/pre_cutover_aria_20260826/` — 5 volúmenes
(`hotelbot_postgres_data`, `hotelbot_redis_data`,
`hotelbot_asterisk_{sounds,logs,spool}`), 6.8MB total, cada `.tar.gz`
verificado íntegro con `tar tzf` antes de continuar.

**3.2 — Contenedores viejos detenidos y removidos por NOMBRE explícito**
(nunca `compose down` del proyecto `hotelbot`, que habría operado por
label sobre contenedores que ya no correspondían al YAML vigente —
riesgo ya documentado en el preflight): los 8 (`aria-ai-engine`,
`aria-tts`, `aria-orchestrator`, `aria-celery-worker`, `aria-ollama`,
`aria-asterisk`, `hotelbot-postgres-1`, `hotelbot-redis-1`) —
`docker stop` (mayoría exit 0, 2 con SIGKILL tras timeout de gracia,
normal) + `docker rm`. Los 7 volúmenes reales confirmados intactos tras
el remove.

**3.3 — Stack nuevo creado** desde
`/home/ing_cpmo/ARIA/deploy/docker-compose.yml` (`name: aria`),
reutilizando la red `hotelbot_aria_net` y los 7 volúmenes reales
(`external: true` — cero datos recreados desde cero). `.env` con las
credenciales reales, gitignorado (`ARIA/` completo está excluido de git
desde antes), permisos `600`.

**Imprevisto encontrado y corregido durante 3.3:** `cpus: "3.0"` de
`ollama` (valor heredado literal del contenedor original) excede los 2
vCPU reales del host — el Docker actual del host lo rechaza en tiempo de
creación (`range of CPUs is from 0.01 to 2.00`). El contenedor original
corría con ese valor porque nunca se re-creó desde que se estableció
(un valor imposible en un contenedor ya en marcha no se re-valida). Se
corrigió a `cpus: "2.0"` — no es una modernización, es un requisito para
poder crear el contenedor en este host. Documentado, no oculto.

**3.4 — Verificación:**
```
aria-ai-engine:      healthy  -- GET /health -> {"status":"ok","service":"ai-engine","active_sessions":0}
aria-tts:             healthy
aria-orchestrator:    healthy -- GET /health -> {"api":"ok","postgres":"ok","redis":"ok","ollama":"ok"}
aria-celery-worker:   healthy
aria-ollama:          healthy
aria-postgres-1:      healthy
aria-redis-1:         healthy -- PONG con la contraseña real
aria-asterisk:        Restarting(1) -- "cp: can't stat '/etc/asterisk-templates/.': No such file or directory"
                       (antes: Exited(127), crash de OCI -- ahora: fallo
                       de aplicación limpio, MISMO resultado funcional
                       -- Asterisk no sirve tráfico -- pero diagnosticable)
```

**Continuidad de datos, verificada con `COUNT(*)` real (no estadísticas
obsoletas de `pg_stat_user_tables`, que mostraban 0 en todo por no haber
corrido `ANALYZE` recién reiniciado):**
```
alembic_version = 1 fila  -- el schema/estado de migración SE PRESERVÓ,
    Alembic no volvió a migrar (a diferencia de la Fase 2, donde el
    volumen era nuevo y sí corrió "Running upgrade -> 0001")
calls, campaigns, leads, audit_log = 0 filas -- YA estaban en 0 antes
    del corte (este ambiente no tenía tráfico real de llamadas
    registrado) -- no es pérdida de datos, es el mismo estado de antes.
```

`docker compose ls -a`: el proyecto `hotelbot` **ya no existe** — solo
queda `aria`, apuntando a `/home/ing_cpmo/ARIA/deploy/docker-compose.yml`.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
PHASE_3_EXECUTED = SI
CUTOVER_RESULT = 7/8 SERVICIOS SANOS (identico o mejor que el estado previo)
DATA_CONTINUITY_VERIFIED = SI (COUNT(*) real, no estadisticas)
BACKUPS_TAKEN = SI, 5 volumenes, /home/ing_cpmo/backups/pre_cutover_aria_20260826/,
    integridad verificada
ROLLBACK_AVAILABLE = SI (backups + hotelbot/docker-compose.yml sigue existiendo
    sin tocar, por si hiciera falta recrear el stack viejo)
UNEXPECTED_FINDING = limite de cpus:3.0 de ollama excedia los 2 vCPU reales
    del host -- corregido a 2.0, documentado
ARIA_ASTERISK_STATUS = SIGUE ROTO, MISMO RESULTADO FUNCIONAL QUE ANTES --
    ahora con fallo limpio (falta /etc/asterisk-templates real) en vez de
    crash de OCI. Reparar Asterisk de verdad requeriria reconstruir su
    configuracion SIP/ARI real, fuera de alcance de este cutover.
HOTELBOT_PROJECT_STATUS = YA NO EXISTE EN DOCKER (docker compose ls -a
    confirma solo "aria")
HOTELBOT_DIRECTORY_STATUS = SIN TOCAR -- /home/ing_cpmo/hotelbot sigue
    existiendo tal cual, con su README_ESTADO_REAL.md y su propio
    docker-compose.yml (ya con el fix hotelbot-legacy de una sesion
    anterior) -- decidir su destino final sigue siendo una decision
    aparte, ahora sin el bloqueante estructural de ARIA
NEXT_STEP = una re-auditoria dedicada de SAFE_TO_DECOMMISSION_HOTELBOT,
    sostenida en el tiempo (no "arranco una vez"), antes de considerar
    borrar el directorio -- no asumido aqui, per diseno del plan original
```

Fase 3 cerrada. Fase 4 (retiro de `hotelbot/`) sigue siendo una decisión
separada de Cesar, no ejecutada en esta corrida.
