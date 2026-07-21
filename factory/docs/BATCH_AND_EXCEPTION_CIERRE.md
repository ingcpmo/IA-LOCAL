# BATCH_AND_EXCEPTION — Cierre de fase

**Proyecto:** gmpai_document_validation (flujo genérico, aplicable a cualquier
proyecto de validación documental de la fábrica).
**Fecha de cierre:** 2026-07-21.
**Commit de checkpoint previo:** `b76060f` (diseño + servicio base).
**Este cierre agrega:** Fase 1 (contratos formales), Fase 2 (escritura
segura), Fase 3 (integración API controlada, no productiva), Fase 4
(validación integrada) + correcciones de aislamiento de auditoría, claridad
de rutas API y fuente regulatoria única.

## Objetivo (sin cambios desde el diseño aprobado)

El sistema genera automáticamente el documento candidato + informe de
remediación sin que ningún chunk individual requiera aprobación humana; el
juicio humano se concentra en las excepciones HIGH_RISK y en la decisión de
paquete (MEDIUM_RISK por lote, LOW_RISK informativo); la liberación final es
el único punto bloqueado.

## 1. Aislamiento de auditoría — PASS

Corrección aplicada: `test_remediation_package_service.py` y
`test_remediation_package_concurrency.py` aíslan
`factory.core.audit_writer.AUDIT_FILE` (+ reset de `_last_entry_hash`) hacia
un archivo temporal por test. Verificado con `md5sum` y con un test dedicado
byte-a-byte (`test_remediation_package_audit_isolation.py`) que el archivo
real permanece idéntico antes/después de ejercitar un ciclo completo (6
tipos de evento).

### 9,105 eventos sintéticos históricos — ACCEPTED_DEVIATION

Antes de esta corrección, corridas de prueba de esta misma tarea escribieron
eventos reales en `factory/audit/factory_audit.jsonl` (sin aislar). Se
documentan aquí, **sin borrarlos ni reescribir la cadena histórica**
(append-only por diseño de `audit_writer.py`):

| project_id | eventos |
|---|---|
| `gmpai_document_validation_test` | 530 |
| `gmpai_document_validation_concurrency_test` | 161 |
| `synthetic_demo_project` | 3 |
| `synthetic_demo_project_v2` | 8,411 |
| **Total** | **9,105** |

- **Rango temporal:** `2026-07-21T04:19:27.768831+00:00` a
  `2026-07-21T05:10:43.563307+00:00`.
- **Clasificación:** `ACCEPTED_DEVIATION` — contenido auténtico y no
  destructivo (no corrompe la cadena, no representa datos de producción
  falsos ya que los `project_id` son inequívocamente sintéticos/de prueba),
  pero mezclado con eventos reales de fábrica por un error de aislamiento ya
  corregido. No requiere remediación retroactiva porque el principio
  append-only del audit trail prohíbe editar o eliminar entradas ya escritas.
- **hash_errors = 0** (verificado con `verify_chain()`): estos eventos no
  comprometen la integridad criptográfica de la cadena.
- **Cadena histórica no modificada**: ninguna entrada previa a esta fase fue
  alterada, reordenada ni eliminada.

## 2. Rutas API — 5 operaciones sobre 4 paths, sin endpoint de release

Verificado offline (sin tocar el contenedor), por `app.routes` y por
`app.openapi()` generado en memoria — ambas fuentes coinciden:

| Método | Path | Operación |
|---|---|---|
| POST | `/api/v1/remediation-packages/{project_id}/{package_id}/{version}` | crear paquete |
| GET | `/api/v1/remediation-packages/{project_id}/{package_id}/{version}` | consultar paquete |
| POST | `/api/v1/remediation-packages/{project_id}/{package_id}/{version}/exceptions/{change_id}` | ExceptionReviewRecord (HIGH_RISK) |
| POST | `/api/v1/remediation-packages/{project_id}/{package_id}/{version}/medium-risk-batch` | MediumRiskBatchDecision |
| POST | `/api/v1/remediation-packages/{project_id}/{package_id}/{version}/decision` | PackageDecisionRecord |

**Ningún endpoint de `ReleaseRecord` existe en el router.** `create_release_record()`
sigue disponible únicamente a nivel de servicio (`remediation_package_service.py`),
sin exposición HTTP.

## 3. Fuente regulatoria — catálogo canónico único

`factory/regulatory/requirement_catalog/requirements.yaml` (cargado y
validado fail-closed por `requirement_catalog_loader.py`) es el **único**
catálogo regulatorio: 19 entradas (`citation_sha256` recalculado y
verificado, `source_id` resuelto contra `source_registry.json`,
`review_status=covered`). `factory/regulatory/regulatory_catalog.py` es un
adaptador de nombres que delega 100% en ese loader — no reparsea los prompts
YAML de los agentes (eso habría sido una segunda fuente de verdad, corregido
en esta fase). Consistencia verificada 19/19 en
`test_regulatory_catalog.py`.

## 4. Gate 0

```
py_compile:    OK (2092+ archivos)
pytest:        813 passed, 1 skipped
audit chain:   WARN (fork concurrente preexistente desde 2026-06-15, hash_errors=0) — aceptado
factory_status: PASS 26 / WARN 3 / FAIL 0
PASS=5 FAIL=0 — Gate 0 OK
```

## Estado de despliegue

```
API_IMPLEMENTED     = true   (5 endpoints wireados en factory/api/main.py)
API_LIVE_IN_CONTAINER = false (factory-api NO reiniciado; --reload deshabilitado desde W5-F0-1, requiere restart explícito aprobado)
DEPLOYMENT_STATUS   = NOT_DEPLOYED
DOCUMENT_RELEASED   = false  (sin ReleaseRecord; endpoint de release deliberadamente no expuesto)
PRODUCTION_ENABLEMENT = BLOCKED
```

## Archivos de esta fase

- `factory/api/main.py` (modificado — wiring del router nuevo)
- `factory/services/remediation_package_service.py` (modificado — locking, escritura atómica, validación de schemas)
- `factory/tests/test_remediation_package_service.py` (modificado — fixtures con citas/artefactos válidos + aislamiento de auditoría)
- `factory/api/routes/remediation_packages.py` (nuevo)
- `factory/regulatory/regulatory_catalog.py` (nuevo — adaptador sobre el catálogo canónico)
- `factory/services/remediation_package_schemas.py` (nuevo)
- `factory/tests/test_regulatory_catalog.py` (nuevo)
- `factory/tests/test_remediation_package_audit_isolation.py` (nuevo)
- `factory/tests/test_remediation_package_concurrency.py` (nuevo)
- `factory/tests/test_remediation_package_schemas.py` (nuevo)
