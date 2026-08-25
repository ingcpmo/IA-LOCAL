# REPORTE FINAL DE SESIÓN — 2026-08-25
Cierra: Decisión 1 operativa, preflight + plan de migración del árbol
canónico (Fases 1-5), fix de colisión ARIA, e investigación de causa raíz
de las 6 fallas preexistentes de `factory/tests`.

──────────────────────────────────────────────────────────────────────────────
DÓNDE VIVE TODO EL CÓDIGO — RESPUESTA DIRECTA
──────────────────────────────────────────────────────────────────────────────

**Todo el código del proyecto está alojado en `/home/ing_cpmo`** (el HOME
real del usuario en el servidor `ivr-ia`, confirmado sin symlinks —
`readlink -f` devuelve la misma ruta). Es el único árbol que:
- Referencian `gmp-copilot.service` (systemd), `crontab -l`, y todos los
  scripts de `scripts/ops/`.
- Tiene el `.env` real en uso, la cadena de auditoría activa
  (`factory/audit/factory_audit.jsonl`, 70,757+ entradas y creciendo), y
  el HEAD real de git (`e26e988` al cierre de esta sesión).

`/home/ing_cpmo/hotelbot` NO es el árbol canónico — es un segundo
checkout del mismo repositorio remoto, desactualizado, 34MB, excluido a
propósito vía `.gitignore` desde 2026-08-25. Documentado con su propio
`README_ESTADO_REAL.md` para que nadie vuelva a confundirlo.

──────────────────────────────────────────────────────────────────────────────
ARQUITECTURA DE DIRECTORIOS, TAL COMO QUEDÓ HOY
──────────────────────────────────────────────────────────────────────────────

```
/home/ing_cpmo/                              [10 GB total]
│
├── CÓDIGO DEL PROYECTO (versionado en git, origin=github.com:ingcpmo/hotelbot,
│   rama gmp-ai-factory-server)
│   ├── app/                 260K  — GMP AI Copilot (producto base :8000)
│   ├── knowledge/            32K  — base de conocimiento del Copilot
│   ├── factory/              1.7G — GMP AI Factory, capas 7-9 (:9000)
│   │   ├── api/, core/, services/, regulatory/, layer9/, ui/  ← código
│   │   ├── tests/            ← suite de 2704 tests
│   │   ├── audit/            ← runtime real: audit trail, NO es código
│   │   ├── deployments/      ← runtime real: workspaces de soluciones custom
│   │   └── .env, __pycache__ ← runtime/secretos, gitignorado
│   ├── scripts/              244K — automatización operativa
│   │   ├── ops/              ← scripts vigentes (backup.sh, etc. — usados por cron)
│   │   └── legacy_bootstrap/ ← NUEVO hoy: 16 scripts de setup inicial, archivados
│   ├── tests/                 72K — tests de nivel raíz
│   ├── docker-compose.yml, Dockerfile, requirements.txt  ← infra Copilot
│   ├── factory/docker-compose.factory.yml                ← infra Factory
│   └── docs_plan/            3.4M — planificación y gobernanza (activo)
│       └── _archive/         ← NUEVO hoy: docs_factory/ (congelado 2026-07-28)
│
├── DATOS / RUNTIME (no código, correctamente fuera de git)
│   ├── data/                 319M — datos vivos de la app (volumen Docker)
│   ├── GMPAI/                 271M — corpus regulatorio externo (Rockwell/SCADA),
│   │                                 dependencia real de ~20 archivos de factory/
│   ├── backups/               1.4G — respaldos
│   │   └── legacy_root_artifacts_20260825/  ← NUEVO hoy: logs/tarballs archivados
│   ├── logs/                   21M — logs de cron/systemd
│   └── .cache/chroma/          — ChromaDB, montado como volumen en gmp-api
│
├── ENTORNO / HERRAMIENTAS (regenerable, no es "el proyecto")
│   ├── .venv/                 1.9G — venv Python del host
│   ├── .local/, .cache/       ~3G  — cachés de pip/playwright/etc.
│   ├── .npm/, .nvm/, .codex/  ~1.2G — tooling de otros lenguajes/CLIs
│   ├── node_modules/           202M
│   └── .git/                    37M — historial del repo real
│
├── PROYECTOS AJENOS, NO TOCAR (fuera del alcance de GMP AI Factory)
│   ├── ARIA/                   500K — proyecto ARIA IVR (código propio, separado)
│   └── hotelbot/                34M — checkout secundario obsoleto (ver arriba);
│                                       su docker-compose.yml ya no colisiona con
│                                       producción (fix de hoy, name: hotelbot-legacy)
│
└── .claude/                    278M — memoria de sesión, planes, config del agente
```

**Separación arquitectónica permanente** (sin cambios hoy, reconfirmada):
`app/` + `docker-compose.yml` (raíz) = GMP AI Copilot, producto base
(:8000). `factory/` + `factory/docker-compose.factory.yml` = GMP AI
Factory, capas 7-9 (:9000). Ninguno de los dos `docker-compose.yml` se
movió ni se moverá — se verificó que toda ruta relativa de ambos se
rompe con un `mv` a subcarpeta.

──────────────────────────────────────────────────────────────────────────────
CIERRES DE HOY (orden cronológico)
──────────────────────────────────────────────────────────────────────────────

| # | Qué se cerró | Commit(s) |
|---|---|---|
| 1 | Decisión 1 (motor de análisis operativo) registrada formalmente | `b0c79b8`, `78b6370` |
| 2 | Preflight de solo lectura sobre el árbol real | `72d591f` |
| 3 | Plan de migración Fase 3 (reordenar artefactos sueltos) | `6d5ba29` |
| 4 | Plan de migración Fase 4 (Rockwell zips corruptos borrados, `cuda_installer.pyz` fuera del repo) | `b526924` |
| 5 | Plan de migración Fase 5 (verificación final, `NEW_REGRESSIONS=0`) | `ce8581b` |
| 6 | Fix de colisión `container_name`/proyecto Compose con ARIA | `e26e988` |
| 7 | Investigación de causa raíz de las 6 fallas preexistentes de tests | (solo lectura, sin commit — ver abajo) |

Todo pusheado a `origin/gmp-ai-factory-server`. HEAD final: `e26e988`.

──────────────────────────────────────────────────────────────────────────────
CAUSA RAÍZ DE LAS FALLAS PREEXISTENTES — DOCUMENTADO, NO CORREGIDO
──────────────────────────────────────────────────────────────────────────────

Decisión explícita de hoy: **no corregir**, no era necesario (nada
bloqueante, nada de esto causado por el trabajo de esta sesión).

- `test_status_risks.py::test_every_blocking_risk_is_justified_by_a_real_state`:
  disco real al 72.9-76% (`factory/api/routes/status.py:167-172` dispara
  `RISK_DISK_USAGE` en `>70%` pese a describir "umbral de alerta: 80%");
  el test nunca tuvo una rama para verificar ese tipo de riesgo contra
  estado real (sí la tiene para `RISK_REMEDIATION_*` y `RISK_AUDIT_CHAIN`).
  Hueco de cobertura preexistente, expuesto ahora porque el disco cruzó
  70% por primera vez.
- 3 fallas de Playwright (`test_governance_catalog_version_playwright.py`
  x2, `test_review_queue_finding_ui_playwright.py` x1): reproducidas 2
  veces en aislado con el mismo resultado exacto, mientras tests hermanos
  con el mismo helper y el mismo servidor pasan siempre. Causa raíz:
  el servidor tiene solo 2 vCPU con `load average≈1.0` crónico (~15
  contenedores corriendo permanentemente) — timeouts fijos de Playwright
  (15-30s) quedan al borde de la varianza de scheduling. No es un defecto
  funcional del producto.

──────────────────────────────────────────────────────────────────────────────
PENDIENTES REGISTRADOS, SIN BLOQUEAR NADA
──────────────────────────────────────────────────────────────────────────────

- Ports fijos (`5432`/`6379`/`8000`) en `hotelbot/docker-compose.yml`
  seguirían colisionando con producción si ambos stacks corrieran a la
  vez — fuera de alcance del fix de hoy (atacaba etiqueta de proyecto y
  `container_name`, no puertos).
- 2 contenedores huérfanos (`hotelbot-postgres-1`, `hotelbot-redis-1`) —
  documentados, no investigados ni detenidos.
- Decisión 2 (capacidad de liberación de documentos) — `NOT_BUILT`,
  explícitamente separada de la Decisión 1.
- Gap de cobertura de `test_status_risks.py` para `RISK_DISK_USAGE` —
  documentado arriba, decidido explícitamente no corregir hoy.
