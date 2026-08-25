# PLAN DE DESACOPLE — hotelbot/ARIA
# Diseño puro. Cero ejecución. Cero docker up/down/restart/rm. Cero
# modificación de ningún archivo ni contenedor.
#
# Objetivo: que ARIA deje de depender de rutas dentro de un checkout de
# código de GMP AI Factory ("hotelbot/", marcado para eventual retiro),
# para que ese retiro deje de ser SAFE_TO_DECOMMISSION_HOTELBOT=NO por
# razones estructurales de ARIA.
#
# Basado en: docs_plan/AUDITORIA_TOPOLOGIA_REAL_CORREGIDA.md (mapa de
# topología verificado) y el propio proyecto ARIA en
# /home/ing_cpmo/ARIA/03-code/src/ (ver nota en Fase 0).

────────────────────────────────────────────────────────────────────────────
POR QUÉ ESTO ES DELICADO — LEER ANTES DE DISEÑAR NADA MÁS
────────────────────────────────────────────────────────────────────────────

`CLAUDE.md` es explícito: "Contenedores `aria-*` y `hotelbot-*` —
PROHIBIDO modificar". Este plan no autoriza tocarlos — diseña CÓMO se
podría hacer, con qué pasos, riesgos y aprobaciones, para que Cesar
decida si y cuándo ejecutarlo, probablemente con el dueño real de ARIA en
la conversación (esta sesión trabaja para GMP AI Factory, no es la
autoridad operativa de ARIA).

**Hallazgo que condiciona todo el diseño:** el archivo que creó los 8
contenedores vivos hoy (`config_files=/home/ing_cpmo/hotelbot/
docker-compose.yml`) YA NO EXISTE en esa forma — fue sobrescrito con
contenido de GMP AI Copilot sin que la versión que definía ARIA quedara
commiteada nunca (`git log` de ese archivo, dentro del propio repo de
`hotelbot/`, solo muestra 2 commits de Copilot, nunca de ARIA). **No hay
ninguna fuente de verdad recuperable, byte-exacta, del compose original
de ARIA.** La única vía posible es reconstruirlo desde la configuración
EN VIVO de los contenedores (`docker inspect`), no restaurarlo desde
ningún archivo.

Existe `/home/ing_cpmo/ARIA/03-code/src/docker-compose.local.yml` — una
definición del stack ARIA "oficial" de ese proyecto — pero **no coincide**
con lo que corre hoy: usa `postgres:15-alpine` (vivo: `16-alpine`),
`container_name: aria-postgres` explícito (vivo: auto-generado
`hotelbot-postgres-1`, sin `container_name`), y separa `vosk`/`kokoro-tts`
como servicios propios con imágenes públicas (vivo: fusionados dentro de
imágenes custom `hotelbot-ai-engine`/`hotelbot-tts`, construidas
2026-04-26, sin Dockerfile fuente localizable hoy en ningún checkout).
Es un pariente histórico del stack real, útil como referencia de diseño,
NO como archivo a aplicar directamente — usarlo sin reconciliar
diferencia por diferencia recrearía contenedores distintos a los que
corren ahora.

**Consecuencia de diseño:** este plan NO puede ser "mover un archivo y
listo". Tiene que ser un cutover controlado, con downtime de ARIA
asumido y aprobado explícitamente, en una ventana de mantenimiento — no
hay forma de hacerlo sin al menos recrear los 8 contenedores bajo un
nuevo `working_dir`/proyecto.

────────────────────────────────────────────────────────────────────────────
FASE 0 — DECISIONES BLOQUEANTES (gate, antes de escribir un solo YAML)
────────────────────────────────────────────────────────────────────────────

0.1. **¿Quién aprueba tocar ARIA?** Este plan lo diseña Capa 8 de GMP AI
     Factory; ejecutarlo implica recrear contenedores de un sistema
     protegido explícitamente por `CLAUDE.md`. Requiere aprobación
     explícita de Cesar Y, si existe, del responsable operativo real de
     ARIA — no es una decisión que deba tomarse solo desde el contexto
     de GMP AI Factory.

0.2. **¿Se acepta downtime de ARIA?** El cutover implica detener y
     recrear `aria-orchestrator`, `aria-celery-worker`,
     `hotelbot-postgres-1`, `hotelbot-redis-1` (mínimo) — llamadas en
     curso de IVR se cortarían. Se necesita una ventana de mantenimiento
     explícita, no una ejecución "en caliente" en medio de operación.

0.3. **¿Dónde vive el nuevo compose file?** Candidatos:
     - `/home/ing_cpmo/ARIA/03-code/src/` (ya es "el proyecto ARIA real",
       pero su `docker-compose.local.yml` actual no coincide con lo vivo
       — habría que decidir si se reemplaza ese archivo o se agrega uno
       nuevo `docker-compose.production.yml` al lado).
     - Un directorio nuevo, dedicado, fuera de cualquier checkout de
       código de GMP AI Factory o de Copilot (p. ej.
       `/home/ing_cpmo/ARIA/deploy/`).
     Recomendado: la segunda opción — no mezclar el compose de producción
     real con el árbol `03-code/src/` que ya tiene su propia definición
     de "stack local de desarrollo", para no generar la misma ambigüedad
     que causó este problema.

0.4. **¿Se resuelven los 3 bind mounts vacíos (`asterisk/
     docker-entrypoint.sh`, `asterisk/etc/asterisk`, `postgres/init`) o
     se eliminan de la definición?** Dado que su contenido real está
     perdido (no recuperable de git ni de ningún backup localizado en
     esta sesión): opción A, reescribir un `docker-entrypoint.sh` y
     config de Asterisk NUEVOS desde cero (reparando además el
     `Exited 127` de `aria-asterisk`, que hoy está roto por esto mismo)
     — requiere a alguien con conocimiento real de la configuración de
     Asterisk de ARIA, fuera del alcance de Capa 8; opción B, quitar esos
     bind mounts de la definición reconstruida y asumir que
     `aria-asterisk` seguirá sin funcionar hasta que se resuelva aparte
     (no empeora nada — ya está roto hoy).

**Gate:** sin respuesta a 0.1-0.4, no se escribe el YAML reconstruido de
la Fase 1 en forma final (sí se puede preparar como borrador).

────────────────────────────────────────────────────────────────────────────
FASE 1 — RECONSTRUCCIÓN DEL COMPOSE DESDE INSPECCIÓN EN VIVO (solo lectura)
────────────────────────────────────────────────────────────────────────────

Para cada uno de los 8 contenedores (`aria-ai-engine`, `aria-tts`,
`aria-orchestrator`, `aria-celery-worker`, `aria-ollama`, `aria-asterisk`,
`hotelbot-postgres-1`, `hotelbot-redis-1`), extraer con `docker inspect`
(ya hecho parcialmente en la auditoría de hoy, se completa aquí):
imagen exacta (por digest, no solo tag, para poder fijarla), variables de
entorno completas, comando/entrypoint, políticas de reinicio, mounts
(volúmenes nombrados + binds), puertos publicados, red.

Producto de esta fase: un `docker-compose.aria.reconstructed.yml`
**candidato**, generado por inspección, NO aplicado. Cada volumen nombrado
actual (`hotelbot_postgres_data`, `hotelbot_redis_data`,
`hotelbot_ollama_models`, `hotelbot_vosk_models`,
`hotelbot_asterisk_{sounds,logs,spool}`) se referencia como **externo**
(`external: true`) — el objetivo es que el cutover REUTILICE los
volúmenes existentes con sus datos reales, nunca cree volúmenes nuevos
vacíos.

Verificación obligatoria antes de pasar a Fase 2: `docker compose
-f docker-compose.aria.reconstructed.yml config` debe resolver limpio,
y una revisión manual campo por campo contra el `docker inspect` de cada
contenedor vivo — no basta con que el YAML sea sintácticamente válido.

────────────────────────────────────────────────────────────────────────────
FASE 2 — VALIDACIÓN EN PARALELO, SIN TOCAR LO VIVO
────────────────────────────────────────────────────────────────────────────

Antes de cualquier cutover real: usar el YAML candidato para levantar un
**stack de prueba aislado**, con nombres de proyecto/contenedor/red
DISTINTOS (p. ej. `aria-cutover-test`), SIN los volúmenes reales
(volúmenes nuevos, vacíos, de prueba) y SIN los puertos reales (remapeados
a puertos altos no usados) — para confirmar que las imágenes todavía
arrancan, que `aria-orchestrator` corre sus migraciones sin error contra
una base de datos de prueba, etc. Esto NO reemplaza la Fase 3, pero
reduce el riesgo de que el cutover real falle por una imagen corrupta o
un env var mal transcripto.

Esta fase SÍ implica `docker compose up` — pero sobre un proyecto nuevo,
aislado, sin tocar nada existente. Requiere aprobación explícita antes de
ejecutarla (ya no es solo lectura), aunque su riesgo es bajo.

────────────────────────────────────────────────────────────────────────────
FASE 3 — CUTOVER REAL (ventana de mantenimiento, máximo riesgo)
────────────────────────────────────────────────────────────────────────────

Solo tras Fase 0 (aprobado) y Fase 2 (validado):

3.1. Snapshot de los 4 volúmenes de datos reales
     (`hotelbot_postgres_data`, `hotelbot_redis_data`, y los de Asterisk)
     ANTES de tocar nada — backup real, verificado, no solo "hay un
     volumen Docker" (un `docker run --rm -v hotelbot_postgres_data:/d
     -v $(pwd):/backup alpine tar czf /backup/pre_cutover_postgres.tar.gz
     /d` o equivalente).
3.2. `docker compose -f <archivo antiguo, hotelbot/docker-compose.yml>
     down` NO se ejecuta nunca sobre el proyecto `hotelbot` real (bajaría
     containers por label, no por definición actual — mismo riesgo ya
     documentado). En su lugar: detener los 8 contenedores por NOMBRE
     explícito (`docker stop aria-ai-engine aria-tts ...`), nunca por
     `compose down` de un proyecto cuyo YAML ya no coincide con lo que
     hay que bajar.
3.3. Recrear los 8 servicios con el YAML validado de la Fase 1/2, en su
     ubicación definitiva (Fase 0.3), apuntando a los volúmenes externos
     reales (no a copias).
3.4. Verificar health de los 8, logs de arranque limpios, y (si aplica)
     una llamada de prueba real end-to-end antes de dar el cutover por
     cerrado.
3.5. Solo DESPUÉS de 3.4 confirmado y sostenido en el tiempo (no
     "arrancó una vez") es seguro considerar que `hotelbot/` ya no tiene
     ninguna dependencia estructural de ARIA — recién ahí
     `SAFE_TO_DECOMMISSION_HOTELBOT` podría re-evaluarse a `YES`, con su
     propia auditoría de confirmación, no asumido por este plan.

**Rollback:** si 3.3/3.4 falla, restaurar los 4 volúmenes desde el
snapshot de 3.1 y recrear los contenedores originales apuntando otra vez
a `/home/ing_cpmo/hotelbot/docker-compose.yml` (que para entonces seguiría
existiendo, sin tocar, hasta que el cutover esté 100% confirmado).

────────────────────────────────────────────────────────────────────────────
FASE 4 — SOLO ENTONCES, RETIRO DE hotelbot/
────────────────────────────────────────────────────────────────────────────

Con la Fase 3 cerrada y sostenida: recién ahí `hotelbot/` deja de tener
la dependencia estructural que hoy bloquea su retiro. Decidir su destino
final (archivar, borrar) sigue siendo una decisión aparte — este plan
solo remueve el bloqueante técnico, no decide qué hacer con el directorio
una vez desbloqueado.

────────────────────────────────────────────────────────────────────────────
RESUMEN DE RIESGO POR FASE
────────────────────────────────────────────────────────────────────────────

```
Fase 0: ningún riesgo -- son preguntas
Fase 1: ningún riesgo -- solo lectura, produce un YAML candidato
Fase 2: riesgo bajo -- stack de prueba aislado, nunca toca lo real
Fase 3: riesgo alto -- downtime real de ARIA, cutover de contenedores
        protegidos, requiere ventana de mantenimiento y aprobación
        explícita del dueño de ARIA además de Cesar
Fase 4: ningún riesgo técnico nuevo -- decisión de producto/limpieza
```

No se ejecuta nada de esto en la sesión actual. Fase 0 es el único gate
antes de que la Fase 1 (reconstrucción, solo lectura) pueda empezar en
una corrida futura.
