# REPORTE — PREFLIGHT_CORRECCION_ARBOL_CANONICO
Generado por Claude Code (Capa 8) — 2026-08-25. Solo lectura. 0 mv, 0 commit
del árbol real, 0 docker up/down/restart, 0 llamadas LLM. Única escritura:
`hotelbot/README_ESTADO_REAL.md` (creación, gitignorado, no requiere commit).

──────────────────────────────────────────────────────────────────────────────
1 — PRECEDENCIA DE IDENTIDAD COMPOSE
──────────────────────────────────────────────────────────────────────────────

```
/home/ing_cpmo/docker-compose.yml        -> SIN 'name:' declarado
factory/docker-compose.factory.yml       -> 'name: factory' explícito (línea 1)
.env (raíz)                              -> sin COMPOSE_PROJECT_NAME
entorno de shell actual                  -> sin COMPOSE_PROJECT_NAME
gmp-copilot.service                      -> invoca 'docker compose -f ... ' sin -p/--project-name
```

Nombre de proyecto EFECTIVO, confirmado por `docker inspect` (labels reales,
no interpretación del YAML):

```
gmp-api, gmp-postgres, gmp-redis  -> com.docker.compose.project = ing_cpmo
                                      (derivado del basename de /home/ing_cpmo,
                                      NO de ningún 'name:' — no existe)
factory-api                       -> com.docker.compose.project = factory
                                      (coincide con el 'name: factory' declarado)
```

**Riesgo para una migración futura:** si `docker-compose.yml` (raíz) se
moviera a una subcarpeta sin declarar `name:` explícito, el proyecto
efectivo cambiaría de `ing_cpmo` a lo que sea que se llame esa subcarpeta
(p. ej. `docker`) — Compose ya NO reconocería los contenedores `gmp-api`/
`gmp-postgres`/`gmp-redis` que hoy corren como parte del mismo proyecto,
con riesgo de recrearlos duplicados o de que `docker compose down` no
alcance a pararlos. Ningún plan de migración debe mover ese archivo sin
fijar `name: ing_cpmo` (o el nombre que se decida) ANTES del `mv`, y
actualizar `gmp-copilot.service` en consecuencia.

──────────────────────────────────────────────────────────────────────────────
2 — RUTAS RELATIVAS: MAPA DE RIESGO SI SE MUEVEN LOS YAML
──────────────────────────────────────────────────────────────────────────────

**`docker-compose.yml` (raíz)** — todas las rutas relativas confirmadas
existentes en su destino actual:

| Referencia | Resuelve HOY a | Si el YAML se moviera a `docker/` |
|---|---|---|
| `build.context: "."` | `/home/ing_cpmo` | `/home/ing_cpmo/docker` — **ROTO** |
| `env_file: ".env"` | `/home/ing_cpmo/.env` | `/home/ing_cpmo/docker/.env` — **ROTO** |
| `./scripts/sql/init.sql` | `/home/ing_cpmo/scripts/sql/init.sql` | `/home/ing_cpmo/docker/scripts/sql/init.sql` — **ROTO** |
| `./data` | `/home/ing_cpmo/data` | `/home/ing_cpmo/docker/data` — **ROTO** |
| `./app` | `/home/ing_cpmo/app` | `/home/ing_cpmo/docker/app` — **ROTO** |
| `./knowledge` | `/home/ing_cpmo/knowledge` | `/home/ing_cpmo/docker/knowledge` — **ROTO** |
| `/home/ing_cpmo/.cache/chroma` | (absoluta) | sin cambio — no depende de dónde viva el YAML |

**`factory/docker-compose.factory.yml`** — ídem:

| Referencia | Resuelve HOY a | Si el YAML se moviera a `factory/docker/` |
|---|---|---|
| `build.context: ".."` | `/home/ing_cpmo` | `/home/ing_cpmo/factory` — **ROTO** (deja de ser la raíz real) |
| `env_file: ".env"` | `/home/ing_cpmo/factory/.env` | `/home/ing_cpmo/factory/docker/.env` — **ROTO** |
| `volumes: "."` (monta TODO `factory/`) | `/home/ing_cpmo/factory` | `/home/ing_cpmo/factory/docker` — **ROTO** (montaría solo la subcarpeta) |
| `../backups/factory` | `/home/ing_cpmo/backups/factory` | `/home/ing_cpmo/factory/backups/factory` — **ROTO**, no existe ahí |
| `../GMPAI` | `/home/ing_cpmo/GMPAI` | `/home/ing_cpmo/factory/GMPAI` — **ROTO** |

**Conclusión dura:** `docker compose config` validaría sintácticamente sin
error en cualquiera de los dos escenarios rotos — no detecta que una ruta
física no existe hasta que el servicio intenta arrancar. Ningún plan futuro
puede mover estos YAML sin (a) reescribir cada ruta relativa a la nueva
profundidad, o (b) fijar `--project-directory`/rutas absolutas explícitas,
y en ambos casos, probarlo con un `up` real antes de considerar la migración
cerrada — no basta con `config` validando limpio.

──────────────────────────────────────────────────────────────────────────────
3 — BASELINE DE TESTS PRE-MIGRACIÓN
──────────────────────────────────────────────────────────────────────────────

Corrida completa, sin timeout artificial (el primer intento con
`timeout 900` cortó pytest al 86% sin resumen final — descartado y
re-ejecutado sin límite). Resultado íntegro persistido en:

```
docs_plan/PREFLIGHT_ARBOL_CANONICO_20260825/pre_migration_test_baseline.txt
```

```
4 failed, 2641 passed, 5 skipped, 1 xfailed, 2 errors, 106731 warnings
en 881.41s (0:14:41). PYTEST_EXIT_CODE=1.

FAILED test_governance_catalog_version_playwright.py::test_button_enabled_and_signs_with_full_echo_back_when_valid
FAILED test_governance_catalog_version_playwright.py::test_409_proposal_mismatch_is_rendered_persistently
FAILED test_governance_catalog_version_playwright.py::test_409_stale_state_is_rendered_persistently
FAILED test_status_risks.py::test_every_blocking_risk_is_justified_by_a_real_state
ERROR test_review_queue_finding_ui_playwright.py::test_missing_identity_key_shows_visible_error_and_never_advances
ERROR test_review_queue_finding_ui_playwright.py::test_confirm_with_valid_identity_sends_exactly_one_decide_call
```

Estos 4 failed + 2 errors coinciden con el subconjunto que el reporte de
`CIERRE_PENDIENTES_PASO_B_Y_GATE_PRODUCCION_REPORTE.md` (2026-08-23) ya
había caracterizado como preexistente y no relacionado con Paso B — con
una mejora real: las fallas de `test_decision_migration.py` (3) y
`test_rate_limiting.py` (1) que ese reporte también listaba como
preexistentes YA NO aparecen, consistente con el fix de
`6a5e741` (colisión de `decision_instance_id`) commiteado después. No se
investigó la causa raíz de las 4 fallas + 2 errores restantes en esta
corrida — es diagnóstico puro, no corrección — quedan como estado
CONOCIDO PRE-MIGRACIÓN contra el cual comparar después del `mv` real.

──────────────────────────────────────────────────────────────────────────────
4 — REFERENCIAS EXTERNAS DE SOLO LECTURA
──────────────────────────────────────────────────────────────────────────────

**crontab (`ing_cpmo`):**
```
*/5 * * * *  curl -sf http://localhost:8000/health ... (no depende de rutas del árbol)
0 * * * *    docker logs gmp-api --since=1h >> /home/ing_cpmo/logs/gmp_api.log
0 */6 * * *  free -h >> /home/ing_cpmo/logs/ram_monitor.log
0 3 * * *    /home/ing_cpmo/scripts/ops/backup.sh >> /home/ing_cpmo/logs/backup.log
17 9 * * *   /home/ing_cpmo/factory/scripts/ops/watch_source_origin_status.sh
```
`crontab root`: sin crontab (confirmado, sin acceso sudo necesario más allá
de `sudo -n` que devolvió "no crontab for root").

**systemd:** única unidad relevante, `gmp-copilot.service` — barrida
completa de TODAS las unidades del sistema buscando `/home/ing_cpmo`
confirmó que ninguna otra la referencia:
```
WorkingDirectory=/home/ing_cpmo
ExecStartPre/ExecStart/ExecStop -> docker compose -f /home/ing_cpmo/docker-compose.yml ...
StandardOutput/StandardError -> /home/ing_cpmo/logs/gmp-copilot*.log
```
Sin `-p`/`--project-name` explícito (ver punto 1). Sin timers propios del
proyecto — los únicos timers activos del sistema son de paquetes del SO
(apt, logrotate, man-db, fstrim, etc.), ninguno referencia este árbol.

**Scripts hardcodeados:**
```
scripts/ops/backup.sh                          -> PROJECT_DIR="/home/ing_cpmo" (línea 11)
factory/scripts/ops/watch_source_origin_status.sh -> SIN ruta hardcodeada
```
Ningún script de `scripts/ops/` ni la unidad systemd mencionan `hotelbot`
— no hay ambigüedad automatizada real entre los dos árboles hoy.

──────────────────────────────────────────────────────────────────────────────
5 — INVENTARIO TRACKED/UNTRACKED DE ARTEFACTOS LEGACY (raíz del árbol real)
──────────────────────────────────────────────────────────────────────────────

Inventario completo de los 68 archivos sueltos en `/home/ing_cpmo` (nivel
superior, sin recursar): **0 casos de `UNTRACKED_NOT_IGNORED`** — todo lo
que no está trackeado está correctamente `.gitignore`d, sin fugas.

**TRACKEADOS que son candidatos a revisión D8** (no son código ni config,
son artefactos de sesiones de trabajo — decisión de mantenerlos o
excluirlos queda para el plan de migración, no se tocan aquí):
```
diagnostico_palanca_A_14B.txt   287518 bytes  -- diagnóstico de sesión
cuda_installer.pyz              235070 bytes  -- instalador binario (zip),
                                                  sin patrones de credenciales
                                                  (`strings` + grep, limpio)
PALANCA_A_14B_7P2N_RUN.log        5180 bytes  -- log de corrida
palanca_A_14B_requalification.log 2084 bytes  -- log de corrida
```

**IGNORADOS de mayor tamaño, confirmados sin fuga** (Rockwell zips 132MB
c/u, tarballs de FASE5, `.bash_history`, `.claude.json`, `index*.html`,
`W5v2_commit_*.diff`, `package-lock.json`, `get-docker.sh`, `backups/`
completo — cada uno con su regla exacta en `.gitignore` verificada vía
`git check-ignore -v`).

`.env` (raíz) y `factory/.env`: ambos confirmados `.gitignore`d — contenido
NO leído ni mostrado, por regla dura del proyecto.

**Hallazgo aparte, sin riesgo:** `factory/=1.1.0` — archivo de 626 bytes,
ignorado, contenido = log de `pip install python-docx>=1.1.0` sin comillas
(clásico error de shell que crea un archivo llamado `=1.1.0`). Sin
credenciales. Curiosidad de limpieza, no bloqueante.

`generate_compose.sh` marcó un falso positivo en el grep de credenciales
(`POSTGRES_PASSWORD: ${DB_PASSWORD:-change_me}`, `ARI_PASSWORD=${ARI_PASSWORD}`)
— son referencias a variables de entorno con default de placeholder, no
secretos reales.

──────────────────────────────────────────────────────────────────────────────
ARIA_COMPOSE_NAME_FIX — HALLAZGO AMPLIADO, NO APLICADO
──────────────────────────────────────────────────────────────────────────────

Verificado en vivo (`docker inspect`, solo lectura) sobre los contenedores
reales:

```
aria-ai-engine, aria-tts, aria-orchestrator, aria-celery-worker, aria-ollama,
aria-asterisk (exited), hotelbot-postgres-1, hotelbot-redis-1
  -> TODOS: com.docker.compose.project = hotelbot
  -> TODOS: config_files = /home/ing_cpmo/hotelbot/docker-compose.yml
  -> TODOS: working_dir  = /home/ing_cpmo/hotelbot
```

Esto confirma el Hallazgo 1 del reporte de auditoría: ese path SÍ fue (o
sigue siendo, por etiqueta histórica) el orquestador real de ARIA. Pero
el contenido ACTUAL de `hotelbot/docker-compose.yml` ya NO define esos
servicios — define `postgres`/`redis`/`api` con
`container_name: gmp-postgres`/`gmp-redis`/`gmp-api`, **idénticos a los
nombres de los contenedores reales de producción** que corren desde
`/home/ing_cpmo/docker-compose.yml` bajo el proyecto `ing_cpmo`.

**Esto es más grave que un simple conflicto de identidad de proyecto:**
un `docker compose up`/`down` ejecutado hoy desde `/home/ing_cpmo/hotelbot`
resolvería el proyecto implícito `hotelbot` (sin `name:` declarado tampoco
ahí), y al intentar gestionar servicios cuyo `container_name` coincide
con contenedores YA EXISTENTES de otro proyecto, el comportamiento de
Docker Compose no es "aislarlos por proyecto" — `container_name` es un
nombre global único en el motor Docker. El riesgo real no es solo
"tocar ARIA por accidente" (aunque el label histórico lo vincula), es que
un `up`/`down` desde ese directorio puede colisionar directamente con los
contenedores `gmp-*` de PRODUCCIÓN.

**No se aplicó ningún cambio a `hotelbot/docker-compose.yml` en esta
corrida** — la instrucción especifica "No modificar archivos" como regla
dura del preflight, con la única excepción explícita del README nuevo.
El campo `name: gmp-ai-factory` propuesto en el plan anterior para ese
archivo:
1. NO se aplicó aquí — queda pendiente de tu aprobación explícita antes
   de tocar ese YAML (aunque sea de bajo riesgo, es una modificación de
   archivo y esta corrida es estrictamente de solo lectura).
2. Aun aplicándose, NO resuelve por sí solo la colisión de
   `container_name` descrita arriba — sólo evita que un comando SIN
   `-p` explícito recaiga en el proyecto implícito `hotelbot`. La
   colisión de nombres de contenedor es un riesgo independiente que
   requiere su propia decisión (renombrar los `container_name` de ese
   YAML, oненне ejecutarlo nunca).

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
CANONICAL_REPO = /home/ing_cpmo (confirmado, sin re-verificar)
HOTELBOT_STATUS = documentado con README_ESTADO_REAL.md (creado, gitignorado,
    sin commit necesario), sin mover ni borrar
COMPOSE_IDENTITY_CONFLICTS = root sin 'name:' (proyecto efectivo implícito
    'ing_cpmo'); factory/ con 'name: factory' explícito y correcto; mover
    el YAML raíz sin fijar 'name:' antes rompe el reconocimiento de los
    contenedores gmp-* existentes
COMPOSE_RELATIVE_PATH_RISK = TODAS las rutas relativas de ambos YAML
    (excepto 1 absoluta) se rompen si el archivo se mueve un nivel más
    profundo — mapa completo en el punto 2, ningún caso sobrevive un mv
    directo sin reescritura
PRE_MIGRATION_TEST_BASELINE = docs_plan/PREFLIGHT_ARBOL_CANONICO_20260825/
    pre_migration_test_baseline.txt — 4 failed, 2641 passed, 5 skipped,
    1 xfailed, 2 errores, 881.41s. Mismo patrón de fallas preexistentes que
    23-08, con 4 fallas menos (fix de decision_migration ya aplicado)
EXTERNAL_PATH_REFERENCES = 1 unidad systemd (gmp-copilot.service) + 2
    entradas de crontab con rutas hardcodeadas + 1 script (backup.sh) con
    PROJECT_DIR hardcodeado — inventario completo en el punto 4, sin
    ambigüedad con hotelbot
LEGACY_ARTIFACT_GIT_STATUS = 68 archivos sueltos en raíz, 0 fugas
    (UNTRACKED_NOT_IGNORED = 0), 4 candidatos trackeados a revisión D8,
    0 patrones de credenciales encontrados en ningún candidato
ARIA_COMPOSE_NAME_FIX = NO APLICADO (regla de solo lectura de esta corrida)
    -- hallazgo ampliado: el riesgo real excede la identidad de proyecto,
    ver sección dedicada arriba
READY_TO_DESIGN_REAL_MIGRATION_PLAN = YES, con las siguientes condiciones
    explícitas para la fase de diseño: (1) todo YAML que se mueva necesita
    su name: fijado y sus rutas relativas reescritas o convertidas a
    absolutas ANTES del mv, probado con un up real, no solo config; (2) la
    colisión de container_name en hotelbot/docker-compose.yml es una
    decisión aparte de Cesar, no cubierta por el fix de 'name:' propuesto;
    (3) el baseline de este reporte es el punto de comparación obligatorio
    para demostrar NEW_REGRESSIONS=0 después del mv real.
```

Me detengo aquí. No se diseña el plan de migración real (Fases 1-5) en
esta corrida — queda para una corrida posterior, con estos datos en mano,
según lo pedido.
