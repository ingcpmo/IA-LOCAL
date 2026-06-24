# REMEDIATION U5 — Write-on-Read Invariant

**Fecha de cierre:** 2026-06-24  
**Commit de diagnóstico:** post W3 (c902355)

## Descripción del riesgo analizado

El plan U5 identificó un riesgo de "write-on-read": endpoints de observación
llamados por el `refresh()` del frontend podrían ejecutar quality gates y
escribir en `factory_audit.jsonl` sin acción deliberada del operador. Esto
constituiría una violación del invariante Part-11 (la cadena debe crecer solo
ante acciones deliberadas y trazables).

## Resultado del diagnóstico

**El bug NO estaba activo** en el estado actual del código.

Diagnóstico ejecutado el 2026-06-24:
- Línea base de auditoría: 209 entradas
- 3 ciclos completos de `refresh()` (10 endpoints × 3 = 30 llamadas): **delta = +0**
- Ningún endpoint GET ejecuta gates ni escribe auditoría

## Análisis del crecimiento 203 → 209 (+6)

Las 6 entradas generadas en la sesión W1/W2/W3 son todas de acciones
deliberadas implementadas en esos commits:

| # | Evento | Proyecto | Origen |
|---|---|---|---|
| 204 | `release_candidate_approved` | lab_qc_project | W2 — botón Approve RC |
| 205 | `rc_reviewed` | lab_qc_project | W2 — botón Review RC |
| 206 | `layer9_decision_recorded` | r6_change_control | W3 — headless config |
| 207 | `layer8_stop_condition_triggered` | factory_headless_config | W3 — headless config |
| 208 | `layer9_mission_created` | test_u11_dryrun | W3 — crear misión |
| 209 | `layer9_mission_created` | r7_batch_review | W3 — crear misión |

## Arquitectura de auditoría confirmada

Los endpoints GET del refresh son todos read-only:

| Endpoint | Escribe auditoría | Ejecuta gates |
|---|---|---|
| `GET /api/v1/status/full` | NO | NO |
| `GET /api/v1/layer9/missions` | NO | NO |
| `GET /api/v1/layer8/jobs` | NO | NO |
| `GET /api/v1/layer9/review-queue` | NO | NO |
| `GET /api/v1/layer8/status` | NO | NO |
| `GET /api/v1/deployments/{id}` | NO | NO |
| `GET /api/v1/deployments/{id}/gates-report` | NO | NO |
| `GET /api/v1/status/risks` | NO | NO |
| `GET /api/v1/audit/verify` | NO | NO |
| `GET /api/v1/audit/entries` | NO | NO |
| `GET /api/v1/status/resources` | NO | NO |

El executor deliberado es únicamente `POST /api/v1/deployments/{id}/quality-gates`.

## Entradas existentes de pares gates_executed/deployment_gates_validated

Entradas 196-203 (`gates_executed + deployment_gates_validated`) corresponden
a ejecuciones manuales del botón "Ejecutar Quality Gates" en sesiones previas.
Son auténticas, deliberadas, y no constituyen write-on-read.

## Guard de regresión

`factory/tests/test_refresh_readonly.py` — incluido en Gate 0 vía
`factory_selfcheck.sh` (sección 2/4 pytest). Previene re-introducción del bug.

**Declaración Part-11:** ninguna entrada fue eliminada de la cadena.
Todas las entradas son auténticas (ocurrieron por acciones reales).
`hash_errors = 0`, `chain_errors` corresponde a carrera de fetches
concurrentes (no corrupción de contenido).
