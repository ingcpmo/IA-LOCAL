# W5.3 — Fase 5.4: persistencia en el runner v2 + primera corrida real completa

Fecha: 2026-07-17/18. Estado: **sin commit** (pendiente tu revisión).

## Bloques 5.4.1/5.4.2 — wiring + tests (mocks, Gate 0)

`run_validation_evidence()` (`factory/regulatory/tools/run_validation_evidence.py`)
ya no descarta `all_records` — los persiste vía `write_validation_evidence()`
(mismo escritor de Fase 5.2/5.3), con el mismo contrato de 3 estados que
`evaluate_chunked()`:

```
escritura exitosa -> VALIDATION_EVIDENCE_COMPLETE, golden_dataset_eligible=True
escritura fallida -> VALIDATION_EVIDENCE_INCOMPLETE + error real, golden_dataset_eligible=False
                      (el analisis/records SI se completan igual, probado)
```

`document_sha256` ahora se calcula del archivo real (`citation_locator.sha256_file()`),
ya no es un campo ausente. 9 tests nuevos/actualizados, todos verdes en el
primer intento real.

## Incidente encontrado y corregido en esta fase (disclosure completo)

Al inspeccionar el directorio real de evidencia tras la corrida (Bloque
5.4.3) encontré **13 archivos de contaminación de tests** mezclados con el
real: `test_run_context_audit.py` (4 archivos, desde antes de Fase 5.3 —
nunca se actualizó para aislar `VALIDATION_EVIDENCE_BASE` cuando esa fase
cableó la persistencia) y `test_run_validation_evidence_runner.py` (9
archivos, tests que llaman al runner real sin mockear la ruta de
escritura). Corregido:
- `test_run_context_audit.py`: la función `_run()` ahora aísla
  `writer.VALIDATION_EVIDENCE_BASE` en `tmp_path` siempre.
- `test_run_validation_evidence_runner.py`: fixture `autouse=True` que
  aísla la ruta para **todos** los tests del archivo, sin excepción —
  ningún test futuro en este archivo puede volver a escribir en el
  directorio real por descuido.
- Los 13 archivos de contaminación se identificaron por `document_sha256`
  (`sha-run-context` literal o el hash de un PDF sintético de prueba,
  ninguno coincidía con el hash real de FS_v1.2) y se eliminaron —
  conservado únicamente `w5v3-validation-40523ef722ef.json` (el real).
- El directorio `validation_evidence/` había quedado con permisos
  `root:root` (el contenedor corre como root) — imposible de gestionar
  con git desde el host. Se corrigió el propietario a `ing_cpmo:ing_cpmo`
  (`docker exec chown`) manteniendo el archivo en `0640` — mismo nivel de
  restricción, dueño correcto.

**Lección de proceso**: cuando una fase cablea persistencia real dentro de
una ruta ya ejercitada por tests existentes, hay que auditar TODOS los
tests que tocan esa ruta, no solo los nuevos de la fase — Fase 5.3 mockeó
correctamente sus propios tests nuevos pero no revisó el test histórico
(`test_run_context_audit.py`, de Fase 4) que empezó a tener un efecto
secundario nuevo sin que nadie lo tocara.

## Bloque 5.4.3 — corrida real (única ejecución real de esta fase)

`run_id w5v3-validation-40523ef722ef`, documento real (`215115305 SCADA-PCS
Misc PLC System FS_v1.2.pdf`, `document_sha256 56095a75...` — mismo hash
real conocido desde el piloto FS_v1.2 original), `document_type=FS`,
`document_type_source=human_assigned`, **19/19 requisitos reales del
catálogo** (vía `--all-catalog-requirements`, Bloque 5.3.3/5.4), 3 chunks
por requisito (`coverage=partial`, declarado), `run_by="Cesar (autorizado
via instruccion explicita de ejecutar Fase 5.4, sesion 2026-07-17)"`.
Duración real: **21:18:29 → 23:39:15 UTC (~2h21m)**.

| Métrica | Valor |
|---|---|
| Registros totales | 57 (19 requisitos × 3 chunks) |
| `verified` | 31 |
| `rejected_by_verifier` | 21 (100% por `schema_validation_failed`) |
| `review_required` | 5 (100% por `RELEVANCE_REVIEW_REQUIRED`) |
| `manifest_incomplete` | 0/57 (0%) — `model_digest` obtenido en las 57 llamadas |
| `validation_evidence_status` | **VALIDATION_EVIDENCE_COMPLETE** |
| `golden_dataset_eligible` | **True** |

**Conclusiones documento-nivel** (19/19, `coverage=partial`):
`DOCUMENTED_AND_SUPPORTED` (5, todos Part 11), `DOCUMENTATION_GAP` (11,
Annex 11 mayoría + ALCOA+ mayoría), `CROSS_REFERENCE_MISSING` (2:
`ANNEX11_4`, `ALCOA_ACCURATE` — consistente con la matriz: ambos marcados
`cross_reference_expected`, no `expected`), `PARTIALLY_DOCUMENTED` (1:
`ALCOA_CONTEMPORANEOUS`).

**Lectura honesta de la tasa de rechazo (37%, n=57)**: el 100% de los 21
rechazos fue por `schema_validation_failed` (el modelo no siempre respeta
el JSON Schema pese a pasarlo como `format`), no por citas inventadas ni
fallas de verificación de contenido — mismo patrón ya visto en Fase 4
(n=6, tasa similar). Con n=57 esta tasa es más representativa que la de
Fase 4, pero sigue siendo **un solo documento, 3 de 29 chunks reales** —
no se generaliza a "la tasa esperada en producción" sin una muestra que
cubra más documentos y el 100% de los chunks.

**El check de relevancia (V5, Fase 2) funcionó con datos reales**: 5/57
registros cayeron en `review_required` por `RELEVANCE_REVIEW_REQUIRED` —
exactamente el mecanismo diseñado para atrapar el patrón C1/C3 (cita
anclada pero fuera de tema), ahora confirmado disparándose con inferencia
real, no solo en el Golden Dataset reconstruido.

## Gate 0

- Suite completa: **624 passed**, 1 skipped, **60 fallos idénticos al
  baseline `262917e`** por nombre y causa (séptima verificación
  consecutiva sin desviación en este ciclo).
- Selfcheck host: `PASS=4 FAIL=0`.
- Directorio de evidencia real limpio: **1 solo archivo**, el real.

## Diff

```
 M factory/regulatory/tools/run_validation_evidence.py   (document_sha256 + wiring del escritor)
 M factory/tests/test_run_validation_evidence_runner.py  (fixture autouse + 2 tests nuevos + fix de aislamiento)
 M factory/tests/test_run_context_audit.py               (fix de aislamiento, incidente de esta fase)
?? factory/docs/W5_3_FASE5_4_CIERRE.md
?? factory/regulatory/validation_evidence/w5v3-validation-40523ef722ef.json  (evidencia real, 57 registros, ~73 KB)
```

## Estado de producción

```
PRODUCTION_ENABLEMENT = BLOCKED
```
Sin cambios. Toda la corrida real fue `run_context='validation'`; ningún
prompt de producción tocado; `evaluate_chunked()` en el camino de
producción sigue sin invocar nada de este catálogo.

## Pendiente real / recomendación para W5.5

- `factory/regulatory/validation_evidence/` va a crecer con cada corrida
  real futura (73 KB esta vez) — considerar si conviene excluir el
  contenido (no la carpeta) de git a partir de cierto tamaño/volumen, o
  mantenerlo como evidencia versionada (decisión de gobernanza, no técnica
  — no la tomo unilateralmente aquí).
- La tasa real de `schema_validation_failed` (37%, n=57) sugiere que, si
  se decide alguna vez activar P3 en producción (reescribir prompts,
  recomendación abierta desde W5v2), convendría además reforzar el prompt
  de `_default_prompt()` con un ejemplo de salida válida — hoy solo
  describe el contrato en texto, sin ejemplo few-shot.
