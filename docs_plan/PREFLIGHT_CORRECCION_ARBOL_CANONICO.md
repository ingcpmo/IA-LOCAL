# PREFLIGHT CORREGIDO — CONSOLIDACIÓN SOBRE EL ÁRBOL REAL (/home/ing_cpmo)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/PREFLIGHT_CORRECCION_ARBOL_CANONICO.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# Autoridad: Capa 9 = Cesar. Rol: Arquitecto Principal.
# SUPERSEDE la Decisión D1 de PLAN_DEFINITIVO_CONSOLIDACION.md — esa
# decisión estaba construida sobre una premisa YA REFUTADA por el propio
# reporte de auditoría (AUDITORIA_CONSOLIDACION_DIRECTORIO_REPORTE.md,
# líneas 18-32): el árbol canónico y vivo es `/home/ing_cpmo`, NO
# `/home/ing_cpmo/hotelbot` (checkout secundario, desactualizado, 60
# cambios sin commitear, .gitignored por el repo real).
#
# NO ejecutar Fase 0/1/2/3/4/5 del plan anterior tal como estaban escritas.
# Esta corrida es SOLO preflight de solo lectura — cero mv, cero commit,
# cero docker up/down, cero modificación de ningún archivo.

────────────────────────────────────────────────────────────────────────────
YA RESUELTO (no re-verificar — citado del reporte existente)
────────────────────────────────────────────────────────────────────────────

CANONICAL_REPO = /home/ing_cpmo (HEAD 6a5e741, referenciado por
    gmp-copilot.service, backup.sh, watch_source_origin_status.sh)
STALE_CHECKOUT = /home/ing_cpmo/hotelbot (HEAD idéntico 6a5e741 pero 60
    cambios sin commitear; ignorado por .gitignore:1 del repo real)
ACTIVE_RUNTIME_SOURCE = /home/ing_cpmo/factory (1.6 GB, .env real, audit
    trail activo, identity_keys.yaml, deployments/lab_qc_project/data)

────────────────────────────────────────────────────────────────────────────
DECISIÓN CORREGIDA SOBRE hotelbot/
────────────────────────────────────────────────────────────────────────────

NO se renombra, NO se mueve, NO se borra `/home/ing_cpmo/hotelbot`
("no bloquear ni eliminar", instrucción explícita de Cesar). Se deja
donde está, con dos acciones mínimas y de bajo riesgo:

1. Crear `hotelbot/README_ESTADO_REAL.md` documentando explícitamente:
   "Este NO es el árbol canónico de GMP AI Factory. Es un checkout
   secundario desactualizado (ver auditoría 2026-08-25). El árbol real
   vive en /home/ing_cpmo. No usar este directorio para desarrollo ni
   despliegue." — para que nadie, humano o agente, vuelva a confundirlo.
2. El Hallazgo 1 (docker-compose.yml de hotelbot acoplado históricamente
   a los contenedores ARIA protegidos) SIGUE siendo un riesgo real e
   independiente de cuál árbol sea canónico — se resuelve igual que en
   el plan anterior (Fase 0 original: `name: gmp-ai-factory` explícito en
   ese YAML, verificación de solo lectura, sin tocar los 2 contenedores
   huérfanos). Esto se mantiene sin cambios.

La consolidación real deja de ser "renombrar hotelbot" y pasa a ser
"ordenar el árbol real que hoy vive suelto en `/home/ing_cpmo`, sin
tocar GMPAI/, data/, .cache/, backups/ (dependencias externas, correcto
que sigan fuera) ni hotelbot/ (checkout secundario, se documenta y se
deja quieto)". Esto es un cambio de escala: el árbol real tiene 11 GB,
`.env` en uso activo, cadena de auditoría escribiéndose en este momento,
y referencias reales de cron/systemd — significativamente más riesgo que
mover el checkout pequeño y aislado que el plan anterior asumía.

────────────────────────────────────────────────────────────────────────────
PREFLIGHT OBLIGATORIO (adoptado del análisis técnico externo, corregido)
────────────────────────────────────────────────────────────────────────────

Nada de esto se ejecuta como parte de la migración todavía — es
diagnóstico puro, antes de diseñar el `mv` real.

1. **Precedencia de identidad Compose:** verificar `name:` en
   `/home/ing_cpmo/docker-compose.yml`, CUALQUIER `COMPOSE_PROJECT_NAME`
   en `.env`/shell/systemd unit de los servicios reales, y el nombre de
   proyecto EFECTIVO (`docker compose config --format json | grep name`)
   desde `/home/ing_cpmo` como directorio de trabajo real. Confirmar que
   el resultado final es inequívoco (no solo que el YAML lo declara).

2. **Auditoría de rutas relativas ANTES de mover cualquier
   docker-compose.yml:** listar cada `build.context`, `volumes`,
   `env_file`, `configs`, `secrets`, bind mount en
   `/home/ing_cpmo/docker-compose.yml` y
   `/home/ing_cpmo/factory/docker-compose.factory.yml`. Para cada ruta
   relativa, calcular explícitamente a qué ruta absoluta resolvería SI el
   archivo se moviera a una subcarpeta `docker/` — confirmar antes de
   proponer ese movimiento en cualquier plan futuro, no asumir que
   `docker compose config` validando sin error significa que las rutas
   físicas son correctas.

3. **Baseline de tests PRE-migración:** correr `factory/tests/` completo
   AHORA, desde el estado actual sin tocar, y persistir el resultado
   exacto (PASS/FAIL/ERROR, lista completa) en un archivo — es la única
   forma de demostrar después `NEW_REGRESSIONS=0` por diferencia real de
   conjuntos, no por comparación con memoria.

4. **Referencias externas de solo lectura:** listar el contenido real de
   `crontab -l`, las unidades systemd relevantes
   (`systemctl cat gmp-copilot.service` y cualquier otra que referencie
   `/home/ing_cpmo`), y cualquier script en `scripts/ops/` que hardcodee
   rutas — sin modificar nada, solo inventariar qué se rompería si el
   árbol real cambia de ubicación.

5. **Inventario tracked/untracked para D8 (artefactos legacy):** para
   cada candidato a mover (`cuda_installer.pyz` si existe en la raíz
   real, logs sueltos, backups puntuales): estado en Git
   (`git ls-files` vs. `git status --short`), tamaño exacto, y una
   revisión de contenido (no solo tamaño) buscando patrones de
   credenciales (`grep -iE "ghp_|github_pat_|api[_-]?key|password"`)
   antes de decidir si se versiona, se excluye, o se documenta aparte.

────────────────────────────────────────────────────────────────────────────
ENTREGA
────────────────────────────────────────────────────────────────────────────

```
CANONICAL_REPO = /home/ing_cpmo (confirmado, sin re-verificar)
HOTELBOT_STATUS = documentado con README_ESTADO_REAL.md, sin tocar
COMPOSE_IDENTITY_CONFLICTS = (resultado real del punto 1)
COMPOSE_RELATIVE_PATH_RISK = (mapa de rutas del punto 2, con destino
    calculado si se movieran los YAML)
PRE_MIGRATION_TEST_BASELINE = (archivo con el resultado completo)
EXTERNAL_PATH_REFERENCES = (crontab, systemd, scripts — inventario)
LEGACY_ARTIFACT_GIT_STATUS = (punto 5, por archivo)
ARIA_COMPOSE_NAME_FIX = (aplicado a hotelbot/docker-compose.yml,
    independiente del resto)
READY_TO_DESIGN_REAL_MIGRATION_PLAN = YES/NO
```

No modificar archivos. No mover directorios (salvo el README nuevo dentro
de `hotelbot/`, que es creación, no movimiento). No commit del árbol real
sin diff + aprobación. No Docker up/down/restart. Detenerse para revisión
de Cesar — el plan de migración real (Fase 1-5, reescrito sobre el árbol
correcto) se diseña en una corrida posterior, con estos datos en mano, no
antes.
