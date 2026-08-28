# DEUDA DE REGRESIÓN — reproducción, análisis, clasificación y solicitud de excepción a Capa 9

**Fecha:** 2026-08-28. **Contexto:** clon del repo en `/home/cmay/ivr-ia` (el origen es
`ing_cpmo@ivr-ia`, `/home/ing_cpmo`). **pytest exit code real de la suite completa: 1.**

## Estado

| | antes de la misión V2 | tras Bloque 9 |
|---|---|---|
| fallos | 7 (documentados en turnos previos) | **5** (3 corregidos) |
| passed | 2770 | **2779** (+11 tests nuevos de la misión V2) |

**Los 5 fallos restantes NO son defectos de V2, NO los introdujo esta misión, y NO
tocan `factory/regulatory/{canonical,graph,findings,validation_v2,requirement_catalog}`
ni ningún módulo del analizador V2.** Causa raíz común: **este es un CLON en
`/home/cmay/ivr-ia`**, y el código/config/tests de estos 5 casos asumen la ruta del
servidor de origen `/home/ing_cpmo` y/o servicios en vivo.

## Corregidos en esta misión (3)

| test | causa | fix aplicado |
|---|---|---|
| `test_artifact_type_mismatch_report::test_never_writes_registry_json_or_currency_log` | `Path("/home/ing_cpmo/factory/regulatory/artifact_type_mismatch_report.py")` hardcodeado | `Path(__file__).resolve().parents[1] / "regulatory" / ...` |
| `test_broken_link_report::test_never_writes_registry_json_or_currency_log` | idem `broken_link_report.py` | idem |
| `test_source_currency_checker::test_never_writes_registry_json` | idem `source_currency_checker.py` | idem |

Son guard-tests que leen un `.py` como texto para verificar que no usa `.write_text(`;
el fix sólo cambia cómo se resuelve la ruta al fuente. Sin efecto funcional.

## Reproducidos, analizados y clasificados — solicitud de EXCEPCIÓN (5)

### EXC-1 · `test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas`
- **Reproducción:** `CorpusDocumentDriftError: 'RW-0005': archivo no encontrado en /home/ing_cpmo/GMPAI/source/Rockwell/215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`
- **Causa raíz:** `corpus_runner._resolve_document_path` resuelve el corpus del motor
  CURRENT (config D4a) contra `/home/ing_cpmo/GMPAI/source/`. En el clon los PDFs están
  en `/home/cmay/ivr-ia/GMPAI/source/`.
- **Clasificación:** infraestructura de CONFIG del motor CURRENT (fuera del alcance V2).
  Determinista, reproducible. Arreglarlo = editar config de rutas de CURRENT.
- **Riesgo si se acepta:** ninguno para V2. El plan de corpus de CURRENT no participa
  del analizador V2 ni del cutover propuesto (V2 corre sobre `canonical_store/`).

### EXC-2 · `test_governance_ui_deploy_consistency_live::test_deploy_freshness_all_source_routes_are_live`
- **Reproducción:** intermitente — PASA en varias corridas, FALLA en otras.
- **Causa raíz:** test marcado `_live`: consulta rutas de deploy en vivo. En este
  entorno los servicios no están todos arriba de forma estable.
- **Clasificación:** test de integración con servicios en vivo. No determinista aquí.
- **Riesgo si se acepta:** ninguno para V2 (no toca el analizador). Debe re-evaluarse
  en el entorno de origen con los servicios arriba.

### EXC-3 · `test_mission_evidence_readers::test_deployment_exists_and_health`
- **Reproducción:** `assert False is True` sobre `health_ok` de `oos_hplc_investigator`
  (api_port 8102).
- **Causa raíz:** requiere un deployment respondiendo `/health` en el puerto 8102, que
  no está levantado en este entorno.
- **Clasificación:** test de servicio en vivo. Determinista dado el entorno (siempre
  falla sin el servicio).
- **Riesgo si se acepta:** ninguno para V2.

### EXC-4 / EXC-5 · `test_new_managers::TestTestExecutionManager::test_passing_tests` y `::test_failing_tests`
- **Reproducción:** `assert False is True` / `assert 0 >= 1` (0 tests ejecutados por el
  manager). Traceback en `/home/ing_cpmo/factory/tests/test_new_managers.py`.
- **Causa raíz:** `TestExecutionManager` lanza un subproceso de pytest resolviendo la
  raíz del repo como `/home/ing_cpmo`; en el clon ese árbol no existe -> 0 tests
  colectados -> conteos 0.
- **Clasificación:** asunción de ruta de clon dentro de un manager de infraestructura
  (fuera del alcance V2). Determinista, reproducible.
- **Riesgo si se acepta:** ninguno para V2 (el manager no participa del analizador).

## Recomendación

- **Corregidos (3):** ya en verde.
- **EXC-1..EXC-5:** solicitar a Capa 9 **aceptación formal como excepción de clon**
  (`ACCEPTED_WITH_DOCUMENTED_EXCEPTION`), con la condición de re-verificarlos en el
  entorno de origen (`/home/ing_cpmo`, servicios arriba) antes del cutover real.
  Ninguno bloquea la funcionalidad del analizador V2; todos fallan por
  ruta-de-clon o servicio-no-levantado, no por lógica.

## Para el reporte de readiness

```
FULL_REGRESSION_STATUS = 2779 passed / 5 failed / 79 skipped / 1 xfailed  (pytest exit=1)
   - 5 failed = deuda de clon/servicio-en-vivo, reproducida y clasificada (EXC-1..EXC-5)
   - 0 de esos 5 toca el analizador V2
   - pendiente: aceptación formal de excepción por Capa 9 (decisión GMP humana)
```
