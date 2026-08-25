# REPORTE DE CIERRE — PLAN_MIGRACION_ARBOL_CANONICO_FASES_1_5
Generado por Claude Code (Capa 8) — 2026-08-25. Cierra
`docs_plan/PLAN_MIGRACION_ARBOL_CANONICO_FASES_1_5.md`.

──────────────────────────────────────────────────────────────────────────────
RESUMEN DE EJECUCIÓN
──────────────────────────────────────────────────────────────────────────────

```
FASE 1 (gate de decisiones) -- RESUELTA por Cesar en chat:
  - Rockwell zips: BORRAR los dos
  - cuda_installer.pyz: ELIMINAR del repo
  - docker-compose.yml/Dockerfile: CONFIRMADO, no se mueven (permanente)

FASE 2 (preparación) -- EJECUTADA:
  - 3 carpetas destino creadas
  - snapshot backups/pre_consolidacion_root_20260825.tar.gz (6.8MB, 53
    entradas, gitignorado, no commiteado -- es respaldo local, no artefacto
    de repo)

FASE 3 (bajo riesgo) -- EJECUTADA, commit 6d5ba29 (pusheado):
  - scripts/legacy_bootstrap/ (16 scripts, versionados -- decisión de
    Cesar: valen más como archivo en git que como archivo solo-disco)
  - backups/legacy_root_artifacts_20260825/ (logs, tarballs, diff, backup
    puntual -- 100% renames puros, sin cambio de contenido)
  - docs_plan/_archive/docs_factory_20260728/ (docs_factory/ completo)

FASE 4 (sensible) -- EJECUTADA, commit b526924 (pusheado):
  - Rockwell (1).zip + Rockwell (1)_(1).zip: BORRADOS. Hallazgo no
    anticipado en el plan original: ambos estaban CORRUPTOS (mismo MD5,
    pero `unzip`/`zipfile` no pueden leer el directorio central) --
    ningún riesgo real perdido al borrarlos, el contenido real ya vive
    extraído en GMPAI/source/Rockwell/.
  - cuda_installer.pyz: git rm + regla nueva en .gitignore.

FASE 5 (verificación final) -- ESTE REPORTE:
```

──────────────────────────────────────────────────────────────────────────────
5.1 — BASELINE DE TESTS, ESTADO FINAL vs. PRE-MIGRACIÓN
──────────────────────────────────────────────────────────────────────────────

Tres corridas completas de `factory/tests` en esta sesión, sin timeout
artificial, en tres puntos del árbol:

```
Pre-migración (HEAD 72d591f, docs_plan/PREFLIGHT_ARBOL_CANONICO_20260825/
  pre_migration_test_baseline.txt):
    4 failed, 2641 passed, 5 skipped, 1 xfailed, 2 errors -- 881.41s

Post-Fase 3 (HEAD 6d5ba29):
    4 failed, 2641 passed, 5 skipped, 1 xfailed, 2 errors -- 870.13s

Post-Fase 4 (HEAD b526924, estado final):
    4 failed, 2641 passed, 5 skipped, 1 xfailed, 2 errors -- 872.02s
```

Las 6 fallas (4 failed + 2 errors) son EXACTAMENTE las mismas en las tres
corridas, mismo nombre de test carácter por carácter:
```
test_governance_catalog_version_playwright.py::test_button_enabled_and_signs_with_full_echo_back_when_valid
test_governance_catalog_version_playwright.py::test_409_proposal_mismatch_is_rendered_persistently
test_governance_catalog_version_playwright.py::test_409_stale_state_is_rendered_persistently
test_status_risks.py::test_every_blocking_risk_is_justified_by_a_real_state
test_review_queue_finding_ui_playwright.py::test_missing_identity_key_shows_visible_error_and_never_advances
test_review_queue_finding_ui_playwright.py::test_confirm_with_valid_identity_sends_exactly_one_decide_call
```

**`NEW_REGRESSIONS = 0`**, confirmado por diferencia real de conjuntos en
cada paso, no por conteo. Estas 6 fallas son preexistentes a este plan
(ya documentadas en `CIERRE_PENDIENTES_PASO_B_Y_GATE_PRODUCCION_REPORTE.md`
del 23-08 y reconfirmadas en el preflight del 25-08) y quedan fuera de
alcance — no se investigó su causa raíz en ningún punto de este plan.

──────────────────────────────────────────────────────────────────────────────
5.2 — IDENTIDAD COMPOSE
──────────────────────────────────────────────────────────────────────────────

```
gmp-api, gmp-postgres, gmp-redis -> com.docker.compose.project = ing_cpmo
factory-api                      -> com.docker.compose.project = factory
```
Idéntico al preflight (`PREFLIGHT_CORRECCION_ARBOL_CANONICO_REPORTE.md`,
punto 1) — consistente con la decisión de no mover ningún
`docker-compose.yml`.

──────────────────────────────────────────────────────────────────────────────
5.3 — REFERENCIAS EXTERNAS
──────────────────────────────────────────────────────────────────────────────

`crontab -l` y `systemctl cat gmp-copilot.service` releídos en vivo:
contenido textualmente idéntico al capturado en el preflight. Las 3 rutas
que referencian (`docker-compose.yml`, `scripts/ops/backup.sh`,
`factory/scripts/ops/watch_source_origin_status.sh`) siguen existiendo
exactamente donde estaban — ninguna de las Fases 3/4 tocó `scripts/ops/`
ni ningún archivo de infraestructura.

──────────────────────────────────────────────────────────────────────────────
5.4 — SMOKE CHECK DOCKER COMPOSE CONFIG
──────────────────────────────────────────────────────────────────────────────

```
docker compose config --quiet                                    -> exit 0
docker compose -f factory/docker-compose.factory.yml config --quiet -> exit 0
```
Ambos resuelven limpio desde `/home/ing_cpmo`. No sustituye a 5.2 (config
no valida rutas físicas, solo sintaxis) pero confirma que no se introdujo
ningún error de sintaxis YAML en el proceso (ninguno de los dos archivos
se tocó, de hecho).

──────────────────────────────────────────────────────────────────────────────
5.5 — COMMITS
──────────────────────────────────────────────────────────────────────────────

```
6d5ba29  docs(consolidacion): Fase 3 -- ordenar artefactos sueltos de la raiz
b526924  chore(consolidacion): Fase 4 -- disponer Rockwell zips y cuda_installer.pyz
```
Ambos con diff mostrado y aprobación explícita antes de commitear, y
pusheados a `origin/gmp-ai-factory-server` tras confirmación explícita
separada, según lo pedido durante toda la sesión.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
FASE_1_DECISIONES = resueltas (Rockwell: borrar; cuda_installer.pyz:
    eliminar; compose files: no se mueven, permanente)
FASE_2_PREPARACION = completa (carpetas + snapshot)
FASE_3_COMMIT = 6d5ba29 (pusheado)
FASE_4_COMMIT = b526924 (pusheado)
NEW_REGRESSIONS = 0 (3 corridas completas, mismo resultado exacto)
COMPOSE_IDENTITY = sin cambios (ing_cpmo / factory)
EXTERNAL_REFERENCES = sin cambios (crontab, systemd, scripts/ops/)
DOCKER_COMPOSE_CONFIG = limpio en ambos stacks
PLAN_STATUS = CERRADO
```

Fuera de alcance, sin resolver, registrado para el futuro (no de este
plan): la colisión de `container_name` entre `hotelbot/docker-compose.yml`
y los contenedores `gmp-*` de producción (hallazgo ampliado del
preflight) — decisión propia de Cesar, sobre un directorio fuera de
alcance de este plan.
