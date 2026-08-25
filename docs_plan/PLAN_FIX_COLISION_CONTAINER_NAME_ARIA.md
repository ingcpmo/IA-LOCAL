# PLAN — FIX DE LA COLISIÓN container_name / PROYECTO COMPOSE EN hotelbot/
# Diseño puro, cero ejecución. Cierra el hallazgo ampliado de
# docs_plan/PREFLIGHT_CORRECCION_ARBOL_CANONICO_REPORTE.md
# ("ARIA_COMPOSE_NAME_FIX = NO APLICADO"), que quedó explícitamente
# contemplado (no resuelto) en el bloque "DECISIÓN CORREGIDA SOBRE
# hotelbot/" de docs_plan/PREFLIGHT_CORRECCION_ARBOL_CANONICO.md.

──────────────────────────────────────────────────────────────────────────────
EL PROBLEMA, EN CONCRETO
──────────────────────────────────────────────────────────────────────────────

`/home/ing_cpmo/hotelbot/docker-compose.yml` (34 líneas, sin `name:`
declarado) define hoy 3 servicios (`postgres`, `redis`, `api`) con:

```
container_name: gmp-postgres / gmp-redis / gmp-api   <- IDÉNTICOS a los
    contenedores de producción reales que corren desde
    /home/ing_cpmo/docker-compose.yml (proyecto Compose "ing_cpmo")
ports: 5432 / 6379 / 8000                              <- IDÉNTICOS también
```

Y, por separado, los contenedores ARIA reales (`aria-ai-engine`,
`aria-tts`, `aria-orchestrator`, `aria-celery-worker`, `aria-ollama`,
`aria-asterisk`) más 2 huérfanos (`hotelbot-postgres-1`,
`hotelbot-redis-1`) siguen etiquetados por Docker con
`com.docker.compose.project=hotelbot`, apuntando exactamente a ese mismo
archivo — una etiqueta histórica, de cuando ese YAML definía otra cosa.

**Dos riesgos distintos, con distinta mitigación:**

**Riesgo A — `docker compose down` desde `hotelbot/` sin `-p`:** sin
`name:` declarado, el proyecto efectivo se deriva del nombre del
directorio → `hotelbot`. Ese es EXACTAMENTE el mismo valor que ya llevan
etiquetados los contenedores ARIA y los 2 huérfanos. `docker compose down`
opera por filtro de label de proyecto, no por lo que esté definido HOY en
el YAML — bajaría TODOS los contenedores con `project=hotelbot`, ARIA
incluido, violando la prohibición explícita de `CLAUDE.md`.

**Riesgo B — `docker compose up` desde `hotelbot/`:** intentaría crear
contenedores llamados `gmp-postgres`/`gmp-redis`/`gmp-api` (nombre global
único en Docker) y bindear los puertos `5432`/`6379`/`8000` — todos ya
ocupados por los contenedores de producción reales. Hoy esto casi
seguro FALLA con error de puerto/nombre ya en uso (protección accidental,
no diseñada) — pero es un comportamiento no verificado formalmente y no
hay que depender de que siga siendo así si algo cambia (p. ej. si el
stack real está caído por otra razón en el momento en que alguien corre
esto por error).

`name:` explícito en el YAML **resuelve el Riesgo A completamente**
(rompe el vínculo automático con la etiqueta `hotelbot` — un `down` sin
`-p` ya no alcanzaría a ARIA). **No resuelve el Riesgo B** — los
`container_name` seguirían colisionando si alguien alguna vez consigue
correr `up` (p. ej. con los contenedores reales caídos).

──────────────────────────────────────────────────────────────────────────────
FASE A — DECISIÓN DE ALCANCE (gate, antes de tocar el archivo)
──────────────────────────────────────────────────────────────────────────────

Tres preguntas, cada una independiente:

**A.1 — Alcance del fix:**
- Mínimo (lo ya contemplado originalmente): solo agregar `name:` — resuelve
  Riesgo A, dejando Riesgo B tal cual.
- Completo (recomendado): agregar `name:` + renombrar los 3
  `container_name` a algo que no colisione (p. ej. `hotelbot-legacy-postgres`/
  `-redis`/`-api`) — resuelve A y B.

**A.2 — Nombre de proyecto a usar en `name:`.** Candidatos:
  `hotelbot-legacy`, `hotelbot-stale-checkout`, `gmp-ai-factory-hotelbot`.
  Cualquiera sirve mientras NO sea `hotelbot` (el valor actual/implícito,
  que es justo lo que hay que romper) ni `ing_cpmo`/`factory` (los
  proyectos reales). Recomendado: `hotelbot-legacy` — corto, explícito
  sobre qué es.

**A.3 — Los 2 contenedores huérfanos** (`hotelbot-postgres-1`,
`hotelbot-redis-1`, Up 17h+, healthy, no definidos en el YAML actual, sin
ningún consumidor conocido): ¿se dejan como están (este plan no los toca,
solo evita que un `down` futuro los alcance por accidente), o se
investiga primero si algo los usa antes de decidir si detenerlos? Este
plan **no propone detenerlos** — son un hallazgo aparte, y pararlos sin
saber qué los sostiene sería una acción nueva de riesgo no acotado, fuera
del propósito de este documento (romper el vínculo `down` accidental, no
limpiar recursos huérfanos).

**Gate:** sin A.1/A.2 resueltos, no se edita el archivo.

──────────────────────────────────────────────────────────────────────────────
FASE B — EVIDENCIA PREVIA (antes de tocar el archivo)
──────────────────────────────────────────────────────────────────────────────

`hotelbot/` está completamente `.gitignore`d desde la raíz real — un
cambio ahí NUNCA queda en el historial de git, a diferencia de todo lo
demás tocado en esta sesión. Para no perder trazabilidad de un cambio de
seguridad real:

B.1. Copiar el `hotelbot/docker-compose.yml` actual (antes de editar) a
     `docs_plan/_archive/hotelbot_docker-compose_pre_fix_20260825.yml` —
     SÍ versionado (docs_plan/ no está ignorado), sirve de evidencia de
     "qué decía antes" sin depender de que `hotelbot/` exista mañana.

B.2. Capturar de nuevo, en el mismo momento, los labels vivos de los
     contenedores ARIA + huérfanos (`docker inspect`, solo lectura) —
     confirmar que siguen exactamente en el mismo estado que documentó el
     preflight, antes de tocar nada. Si algo cambió desde entonces
     (alguien reinició algo, un contenedor nuevo apareció), DETENERSE y
     reportarlo — no asumir que el estado sigue igual.

──────────────────────────────────────────────────────────────────────────────
FASE C — APLICAR EL FIX
──────────────────────────────────────────────────────────────────────────────

Contenido exacto (asumiendo Fase A.1 = "Completo", A.2 = `hotelbot-legacy`
— ajustar si Cesar elige otra combinación):

```yaml
name: hotelbot-legacy

services:
  postgres:
    image: postgres:16-alpine
    container_name: hotelbot-legacy-postgres
    ...
  redis:
    image: redis:7-alpine
    container_name: hotelbot-legacy-redis
    ...
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: hotelbot-legacy-api
    ...
```

Solo cambian: la línea `name:` nueva al inicio, y los 3 valores de
`container_name:`. Nada más del archivo se toca — mismos `ports:`,
`volumes:`, `environment:`, `depends_on:`. (Los `ports:` fijos al host
podrían, en teoría, seguir colisionando si alguna vez ambos stacks
corrieran a la vez — pero eso ya es el comportamiento actual, no lo
empeora ni lo arregla este fix, y no está en el alcance de "romper el
vínculo con `project=hotelbot`"; cambiarlos requeriría decidir si
`hotelbot/` necesita levantarse alguna vez de verdad, lo cual contradice
su propio estado "checkout secundario, no usar" — se deja explícitamente
fuera).

Si Fase A.1 = "Mínimo": solo se agrega la línea `name: hotelbot-legacy`
(o el nombre elegido), sin tocar los 3 `container_name:`.

**Ejecución:** un solo `Edit` sobre `hotelbot/docker-compose.yml`. No
requiere `docker compose build/up/down/restart` — es un cambio de archivo
en reposo, los contenedores reales (ARIA, gmp-*) no se reinician ni se
tocan por editar este YAML (Compose solo actúa cuando alguien invoca un
comando sobre ese archivo).

──────────────────────────────────────────────────────────────────────────────
FASE D — VERIFICACIÓN (sin levantar nada)
──────────────────────────────────────────────────────────────────────────────

D.1. `cd hotelbot && docker compose config --format json | grep -m1 name`
     debe devolver el nuevo nombre (`hotelbot-legacy`), no `hotelbot` ni
     `ing_cpmo` — confirma que el proyecto efectivo cambió sin necesidad
     de levantar ningún contenedor.

D.2. Confirmar, de nuevo con `docker inspect` (solo lectura), que los
     contenedores ARIA + huérfanos + `gmp-*`/`factory-api` reales siguen
     exactamente en el mismo estado que en B.2 — el edit de un YAML en
     reposo no debería tocar ningún contenedor vivo, pero se verifica
     igual, no se asume.

D.3. **No se ejecuta ningún `docker compose up`/`down` real en esta
     fase** — ni desde `hotelbot/` ni desde la raíz. Verificar que el
     proyecto cambió de nombre (D.1) es suficiente para confirmar que
     el Riesgo A quedó cerrado; probarlo "de verdad" con un `down` real
     sería introducir exactamente el riesgo que se está mitigando.

──────────────────────────────────────────────────────────────────────────────
FASE E — CIERRE
──────────────────────────────────────────────────────────────────────────────

E.1. Actualizar `hotelbot/README_ESTADO_REAL.md` (ya existe, gitignorado)
     con una línea confirmando que el fix se aplicó y la fecha — para que
     quien lo lea después sepa que esto ya no es una advertencia teórica
     abierta.

E.2. Commit del ÚNICO archivo que sí queda en git:
     `docs_plan/_archive/hotelbot_docker-compose_pre_fix_20260825.yml`
     (evidencia de B.1) + un reporte corto documentando el resultado de
     D.1/D.2. `hotelbot/docker-compose.yml` en sí NUNCA aparece en el
     diff de git — sigue gitignorado, como debe ser.

E.3. Actualizar memoria del proyecto: el hallazgo abierto
     "no ejecutar docker compose desde hotelbot/" pasa de "riesgo activo
     sin mitigar" a "Riesgo A mitigado (name: propio), Riesgo B mitigado
     solo si se eligió el alcance completo en A.1 — de lo contrario sigue
     abierto y debe seguir documentado como tal."

──────────────────────────────────────────────────────────────────────────────
LO QUE ESTE PLAN NO HACE (a propósito)
──────────────────────────────────────────────────────────────────────────────

- No detiene ni toca ningún contenedor vivo (ARIA, huérfanos, `gmp-*`,
  `factory-api`).
- No decide el destino final de `/home/ing_cpmo/hotelbot/` como
  directorio — eso sigue siendo una decisión aparte, ya fuera de alcance
  desde el preflight.
- No resuelve la colisión de `ports:` si alguna vez ambos stacks
  intentaran correr simultáneamente — solo la de `container_name` (y,
  si se elige el alcance mínimo, ni siquiera esa).
- No investiga ni limpia los 2 contenedores huérfanos.

Me detengo aquí — Fase A es el único gate antes de que este plan sea
ejecutable en detalle.
