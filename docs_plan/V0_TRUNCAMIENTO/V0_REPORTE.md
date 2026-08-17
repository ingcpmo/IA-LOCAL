# FASE V0 — Cuantificar el artefacto de truncamiento

Ejecutado 2026-08-17 por Claude Code (Capa 8), sobre `/home/ing_cpmo`
(`ing_cpmo@ivr-ia`, rama `main` == `origin/gmp-ai-factory-server`, commit
`5f41d41`). Solo lectura. Costo LLM: 0.

## Alcance real vs. alcance instruido

La instrucción pedía recorrer corridas históricas bajo
`evaluation_profile=BASELINE`, incluyendo la corrida original del fixture
7P+2N y la corrida de la campaña de validación (L4). Verificación previa:

- `evaluation_profile` **no se persiste** en `checkpoint.json` ni en los
  manifests de `factory/regulatory/pilot_run/manifests/` — es un
  parámetro de invocación en memoria (`corpus_runner.py:143`,
  `chunked_engine.py:1053`), no un campo grabado. No es posible etiquetar
  post-hoc con certeza qué corridas corrieron bajo BASELINE vs H2H4,
  salvo cuando el nombre del directorio lo declara explícitamente
  (`r1_5_h2h4_chunked-*`).
- La corrida original del fixture 7P+2N bajo el modelo de producción
  (7B) **no tiene raw persistido en este repositorio**. El único
  directorio con "7p2n" en el nombre
  (`palanca_a_14b_7p2n_20260815/`) usa el modelo experimental
  "Palanca A" 14B contra los documentos reales RW-0005/RW-0011/RW-0012,
  no el fixture sintético P1-P7/N1-N2 con el modelo baseline.
- Los raw de la campaña de validación L4 no se encontraron — consistente
  con lo ya documentado en `factory/docs/W5v2_POSTMORTEM_TRUNCAMIENTO_NUM_PREDICT.md`
  y el registro previo de que se perdieron con el reinicio de la VM
  (`/tmp`).

**Decisión de alcance:** en lugar de detenerme, escaneé **todo** raw
persistido bajo `factory/regulatory/pilot_run/` sin importar el perfil
declarado — es el universo completo de evidencia cruda disponible en
este entorno hoy. Cualquier corrida futura de V0 sobre datos nuevos debe
repetir este escaneo, no asumir que esta cifra es definitiva.

## Método

Script: recorre todo `*.checkpoint.json` bajo `pilot_run/` (recursivo).
Por cada `chunk_execution`: `failure_reason == "output_truncated"` es el
proxy determinista de `done_reason == "length"` — es el mismo campo que
`chunked_engine.classify_model_response()` (línea 479) usa en tiempo
real, no una heurística nueva. Cuando la ejecución fue `ok`, se parsea
`raw_response` y se listan los `estado` de cada checkpoint (`req_id`)
para el cruce con el resultado final.

Tabla completa (247 filas, una por chunk-execution, cada una con
`run_id`/`task_id` real): [`v0_truncation_table.csv`](./v0_truncation_table.csv)

## Resultado agregado

| Contexto (directorio) | Chunk-executions | Truncados | ok=True | Otro fallo |
|---|---|---|---|---|
| `checkpoints/` (Tier-1 real: RW-0005, RW-0011, RW-0012) | 149 | 0 | 148 | 1 (`schema_validation_failed`) |
| `palanca_a_14b_7p2n_20260815/` (modelo 14B, docs reales) | 9 | 0 | 9 | 0 |
| `tier1_dry_run_20260812/` | 87 | 0 | 58 | 29 (`provider_call_failed`) |
| `r1_5_h2h4_chunked-596f70cc4520/` (H2H4 explícito) | 1 | 0 | 1 | 0 |
| `r1_smoke_chunked-2ef3d38d2538/` (smoke) | 1 | 0 | 1 | 0 |
| **TOTAL** | **247** | **0** | **217** | **30** |

**Cero truncamientos (`done_reason='length'`) en las 247 chunk-executions
persistidas en este entorno**, sobre 5 contextos de corrida distintos, 3
agentes/modelos, y 3 documentos reales del corpus Rockwell + el
experimento del modelo 14B. Los 30 fallos "otro" son exclusivamente
`provider_call_failed` (29, conectividad/timeout con Ollama en
`tier1_dry_run_20260812`) y `schema_validation_failed` (1) — ninguno
relacionado con presupuesto de salida.

Ninguna fila truncada existe, por lo que la columna
"¿se hubiera aceptado sin el corte?" queda vacía por construcción — no
hay ningún caso al que aplicarle esa pregunta con los datos disponibles
hoy.

## Qué demuestra (y qué no)

- **Confirma, con datos verificables de este repo**, lo que la sesión
  anterior ya había señalado sin poder citarlo: P-1 (truncamiento) no
  aparece en ningún chunk-execution persistido en este entorno. No es
  evidencia de que P-1 nunca haya ocurrido (los raw de la corrida BASELINE
  original y de L4 simplemente no están aquí) — es evidencia de que,
  sobre TODO lo que sí está disponible para auditar hoy, el artefacto
  declarado no se reproduce.
- **No** permite descomponer el recall 2/7 histórico específicamente,
  porque ese recall se midió sobre el fixture sintético 7P+2N con el
  modelo baseline, y ese raw no está en este repo. La pregunta original
  de V0 ("¿cuánto del recall 2/7 es artefacto de truncamiento?") queda
  sin poder responderse con evidencia anclada — solo se puede decir que,
  en la evidencia disponible, la tasa de truncamiento observada es 0/247.
- Refuerza la recalibración ya propuesta en el commit `5f41d41`: M1
  (presupuesto de salida) se sostiene como corrección preventiva barata,
  no como corrección de un defecto confirmado dentro de este entorno.

## Entrega

```
CHECKPOINT_FILES_SCANNED =     51
CHUNK_EXECUTIONS_TOTAL =       247
TRUNCATED (done_reason=length) = 0
OK =                            217
OTHER_FAILURES =                30 (29 provider_call_failed, 1 schema_validation_failed)
EVALUATION_PROFILE_ORIGINAL_7P2N_BASELINE_RAW = NO_ENCONTRADO_EN_REPO
L4_VALIDATION_CAMPAIGN_RAW =    NO_ENCONTRADO_EN_REPO (confirma perdida ya documentada)
CODE_CHANGED_THIS_RUN =        0 (solo lectura + artefacto de reporte)
```
