# W5.3 — Fase 5.3: persistencia real de `_by_req_candidates` (solo `validation`)

Fecha: 2026-07-17. Estado: **sin commit** (pendiente tu revisión).

## Decisión de diseño aplicada

**Opción (a)** confirmada: se amplió `path_policy._VALIDATION_EVIDENCE_RUN_ID_RE`
para aceptar tanto `w5v3-validation-<12 hex>` (runner standalone, Fase 5.0)
como `chunked-<12 hex>` (el `run_id` real que genera `evaluate_chunked()`) —
un solo identificador real, sin inventar un segundo ID correlacionado a mano.

## Refinamiento del usuario, aplicado

Se adoptó la recomendación de distinguir explícitamente 3 resultados,
**nunca colapsados en uno solo**:

```
validation + escritura exitosa → analysis_status=ANALYSIS_COMPLETE
                                   validation_evidence_status=VALIDATION_EVIDENCE_COMPLETE
                                   golden_dataset_eligible=True

validation + escritura fallida → analysis_status=ANALYSIS_COMPLETE   (el análisis NO se tumba)
                                   validation_evidence_status=VALIDATION_EVIDENCE_INCOMPLETE
                                   validation_evidence_error=<detalle real>
                                   golden_dataset_eligible=False

production                      → analysis_status=ANALYSIS_COMPLETE
                                   validation_evidence_status=NOT_APPLICABLE_PRODUCTION_CONTEXT
                                   golden_dataset_eligible=False
                                   (comportamiento IDÉNTICO a antes de Fase 5.3)
```

Los 3 campos se propagan también al evento de auditoría
(`gmpai_chunked_analysis_run`), no solo al resultado en memoria — un fallo
de persistencia es consultable en `factory_audit.jsonl` sin inspeccionar
el árbol de evidencia.

**Probado explícitamente** (`test_write_failure_never_hidden_and_never_crashes_analysis`):
se fuerza `EvidenceTooLargeError` vía monkeypatch → el análisis se completa
igual (`findings` calculados, `analysis_status=ANALYSIS_COMPLETE`), el
fallo queda declarado en el resultado Y en el evento de auditoría, nada se
oculta.

## Cambios

| Archivo | Cambio |
|---|---|
| `factory/core/path_policy.py` | Regex de `resolve_validation_evidence` amplía a `chunked-<hex>` |
| `factory/engines/gmpai_integrity/chunked_engine.py` | `_persist_validation_evidence()` nuevo, invocado al final de `evaluate_chunked()`; 3 campos nuevos en `result`; propagados a `_write_audit_event()` |
| `factory/regulatory/tools/run_validation_evidence.py` | `requirement_ids_from_catalog()` nuevo + `--all-catalog-requirements` (deriva del catálogo real de Fase 5.2 en vez de listar a mano) |
| `factory/tests/test_chunked_engine_validation_evidence.py` | **nuevo**, 6 tests (incluye el caso de fallo forzado) |
| `factory/tests/test_run_validation_evidence_runner.py` | +1 test (`requirement_ids_from_catalog` → 19/19) |

## Comportamiento productivo — verificado sin cambio

`test_production_context_writes_nothing_identical_to_before_fase_5_3`:
`run_context='production'` no escribe ningún archivo de evidencia, cero
llamada nueva al escritor. `test_result_chunk_executions_never_leaks_by_req_candidates_in_either_context`:
`result["chunk_executions"]` sigue sin `_by_req_candidates` en ambos
contextos — el contrato de salida existente no cambió.

## Gate 0

- Suite completa: **622 passed** (antes 615), 1 skipped, **60 fallos
  idénticos al baseline `262917e`** por nombre y causa (quinta
  verificación consecutiva en este ciclo, sin desviación nunca).
- Selfcheck host: `PASS=4 FAIL=0`.

## Estado de producción

```
PRODUCTION_ENABLEMENT = BLOCKED
```
Sin cambios. `generate_controlled()` sigue rechazando cualquier
`run_context != 'validation'`; los prompts YAML de producción no fueron
tocados; el camino `run_context='production'` de `evaluate_chunked()`
tiene comportamiento binario-idéntico al de antes de esta fase (probado,
no solo argumentado).

## Pendiente real (no resuelto en esta fase, fuera de alcance)

- **No se ejecutó ninguna corrida real contra Ollama en esta fase** — todo
  lo de arriba está probado con mocks deterministas (mismo patrón que el
  resto de Fase 5.0-5.2). La primera vez que esto capture evidencia real
  de un documento real será la próxima ejecución de
  `run_validation_evidence.py` (Fase 5.0/5.3.3) o de `evaluate_chunked()`
  con `run_context='validation'` sobre un documento real — decisión tuya,
  no ejecutada aquí sin pedirla explícitamente.
- Reescritura de prompts de producción (`estado` → `chunk_observation`)
  sigue sin tocar — es la única vía real para mover
  `PRODUCTION_ENABLEMENT` de `BLOCKED`.
