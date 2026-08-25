# REPORTE DE CIERRE — PLAN_FIX_COLISION_CONTAINER_NAME_ARIA
Generado por Claude Code (Capa 8) — 2026-08-25.

Decisiones de Cesar (Fase A): alcance COMPLETO (`name:` + renombrar
`container_name`), nombre de proyecto `hotelbot-legacy` (verificado sin
conflicto con ningún contenedor/proyecto/red/volumen existente antes de
aplicar), huérfanos `hotelbot-postgres-1`/`hotelbot-redis-1` NO tocados.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN
──────────────────────────────────────────────────────────────────────────────

**Fase B — evidencia previa:** snapshot del YAML original en
`docs_plan/_archive/hotelbot_docker-compose_pre_fix_20260825.yml` (SÍ
versionado, a diferencia de `hotelbot/` que está completamente
`.gitignore`d). Labels vivos de ARIA + huérfanos re-confirmados
idénticos al preflight del mismo día antes de tocar el archivo.

**Fase C — fix aplicado** a `/home/ing_cpmo/hotelbot/docker-compose.yml`
(archivo NUNCA versionado, edición fuera de git):
```diff
+name: hotelbot-legacy
+
 services:
   postgres:
     image: postgres:16-alpine
-    container_name: gmp-postgres
+    container_name: hotelbot-legacy-postgres
   ...
   redis:
-    container_name: gmp-redis
+    container_name: hotelbot-legacy-redis
   ...
   api:
-    container_name: gmp-api
+    container_name: hotelbot-legacy-api
```
Ningún otro campo del archivo se tocó (`ports`, `volumes`, `environment`,
`depends_on` idénticos). Sin `docker compose build/up/down/restart` en
ningún momento de esta fase.

**Fase D — verificación, sin levantar nada:**
```
docker compose config (desde hotelbot/) -> name: hotelbot-legacy
container_name resueltos: hotelbot-legacy-postgres/-redis/-api
```
`docker inspect` sobre los 12 contenedores relevantes (ARIA x6, huérfanos
x2, `gmp-*` x3, `factory-api`) confirmó CERO cambios de estado o de label
— la edición del YAML en reposo no tocó ningún contenedor vivo.

**Fase E — cierre:** `hotelbot/README_ESTADO_REAL.md` actualizado
(gitignorado, no en git) documentando el fix, el estado previo, y lo que
sigue sin resolver.

──────────────────────────────────────────────────────────────────────────────
RESULTADO
──────────────────────────────────────────────────────────────────────────────

```
RIESGO_A (docker compose down sin -p bajaría ARIA por coincidencia de
    project=hotelbot) = CERRADO -- proyecto efectivo ahora es
    hotelbot-legacy, ya no coincide con la etiqueta histórica de ARIA
RIESGO_B (container_name colisiona con gmp-* de produccion en un up) =
    CERRADO -- container_name ahora son hotelbot-legacy-postgres/-redis/-api
RIESGO_RESIDUAL_SIN_RESOLVER = ports: 5432/6379/8000 fijos, idénticos a
    producción -- colisionarían si ambos stacks corrieran a la vez.
    Fuera de alcance de este fix (ataca etiqueta de proyecto + nombre de
    contenedor, no puertos). No se investigaron ni se tocaron los 2
    contenedores huérfanos.
CONTENEDORES_VIVOS_AFECTADOS = 0 (verificado antes y después, sin cambio)
ARCHIVO_EDITADO = hotelbot/docker-compose.yml (fuera de git, sin commit
    posible ni necesario)
EVIDENCIA_VERSIONADA = docs_plan/_archive/hotelbot_docker-compose_pre_fix_20260825.yml
    + este reporte + docs_plan/PLAN_FIX_COLISION_CONTAINER_NAME_ARIA.md
PLAN_STATUS = CERRADO
```
