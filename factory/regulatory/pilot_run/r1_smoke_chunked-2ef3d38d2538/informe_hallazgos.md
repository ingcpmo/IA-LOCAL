# Informe de hallazgos — SMOKE / DEMO, NO APROBADO

**Este documento NO es un baseline formal ni una calificación de cumplimiento.**
Es el entregable mínimo de la Parte 4 del smoke E2E de R1
(`docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md`), generado para demostrar que la
cadena localización→juicio→informe→cola humana ensambla y produce
artefactos trazables — no mide recall (eso es R2) ni cierra R1 como
producto.

## Cobertura de esta corrida

- **Documento:** `RW-0005` (`215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`)
  — SHA-256 `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb`
- **Agente:** `alcoa_plus_agent`
- **Página analizada:** 45 (0-based; página 1 del extracto real extraído)
- **Requisito objetivo del smoke:** `ALCOA_CONTEMPORANEOUS` (caso P5 del
  fixture set de recall, `docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`)
- **Modelo:** `qwen2.5:7b-instruct-q4_K_M` (digest
  `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`),
  Ollama `0.21.2`
- **run_id:** `chunked-2ef3d38d2538` — `run_context=pilot`
- **Autorización:** `PILOT_EXECUTION-2026-006` (seleccionada
  automáticamente por `_select_pilot_execution_instance`, co-cubridora:
  `PILOT_EXECUTION-2026-004`) — 1/1 llamada consumida
- **Duración de la llamada:** 1660.8 s (~27.7 min)
- **Configuración usada:** la del pipeline REAL de producción
  (`run_pilot_sample_batch` → `evaluate_chunked`), que evalúa las 9
  requirement_id del agente `alcoa_plus_agent` en una sola llamada. **No**
  es la configuración H2+H4 (1 requirement/llamada + schema mínimo) de los
  experimentos de recall — esa configuración fue un script de diagnóstico
  aislado (`docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`), nunca se
  incorporó a `run_pilot_sample_batch`. Ver nota honesta más abajo.

## Hallazgo — ALCOA_CONTEMPORANEOUS (requisito objetivo del smoke)

| Campo (los 6 de Cesar) | Valor |
|---|---|
| 1. Qué está mal | **No determinado en esta corrida** — el modelo no localizó evidencia sustantiva para este requisito en el fragmento analizado |
| 2. Por qué no cumple | No aplica — no hay hallazgo de incumplimiento porque no hay evidencia (ver estado honesto abajo); no es lo mismo que "incumple" |
| 3. Requisito/regulación/gobernanza usada | `ALCOA_CONTEMPORANEOUS` — catálogo `factory/regulatory/requirement_catalog/requirements.yaml`, agente `alcoa_plus_agent` |
| 4. Evidencia anclada del documento original | **Ninguna** — `evidencia_exacta: ""`, `evidence_quote: ""` en todos los criterios |
| 5. Riesgo | No evaluable — sin evidencia, no hay base para asignar un nivel de riesgo real |
| 6. Acción recomendada | Ampliar el fragmento/página analizado y/o repetir con recuperación determinista (R2) antes de tratar este requisito como evaluado |

### Estado honesto (§3.2 de `docs_plan/R1_SPEC_CONTRATO_ANALIZADOR.md`)

```
ESTADO: sin_evidencia_localizada
estado_crudo_modelo: "evidencia_insuficiente"
anchored: false
match_type: n/a (no hubo cita que verificar)
pipeline_verificado (verified_records_by_req.ALCOA_CONTEMPORANEOUS):
  chunk_observation: "not_observed_in_chunk"
  status: "verified"  (el propio "no observado" quedó verificado, no es un fallo técnico)
  confidence: 0.7
```

**Sin maquillar:** este resultado contradice la selección de este caso
como "el que ancló limpio en H2/H4" (motivo original de elegirlo para el
smoke, ver `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md`). La razón es que **el
pipeline de producción real usado aquí no es H2/H4** — evalúa las 9
requirement_id del agente en una sola llamada (configuración baseline,
0/7 de recall medido), no 1 requirement/llamada (configuración H2+H4,
2/7 medido, la única que ancló P5). El smoke demuestra correctamente que
la cadena ensambla end-to-end — y también demuestra, sin querer pero
honestamente, que **la configuración H2+H4 nunca se llevó a
`run_pilot_sample_batch`**. Ver `PENDIENTE_DE_APROBACIÓN` en el reporte
final para la decisión que esto implica.

## Otros 8 requirement_id evaluados en la misma llamada (informativo, fuera del alcance del smoke)

El agente completo corrió sobre el mismo fragmento (comportamiento del
pipeline real, no elegido por este smoke). Resumen de estados crudos —
incluido por transparencia, **no** forma parte del hallazgo target de R1:

| requirement_id | estado | anchored |
|---|---|---|
| ALCOA_ATTRIBUTABLE | cumple_parcialmente | ver `checkpoint.json` |
| ALCOA_LEGIBLE | cumple_parcialmente | ver `checkpoint.json` |
| ALCOA_CONTEMPORANEOUS | evidencia_insuficiente | false |
| ALCOA_ORIGINAL | ver `checkpoint.json` | ver `checkpoint.json` |
| ALCOA_ACCURATE | ver `checkpoint.json` | ver `checkpoint.json` |
| ALCOA_COMPLETE | ver `checkpoint.json` | ver `checkpoint.json` |
| ALCOA_CONSISTENT | ver `checkpoint.json` | ver `checkpoint.json` |
| ALCOA_ENDURING | ver `checkpoint.json` | ver `checkpoint.json` |
| ALCOA_AVAILABLE | ver `checkpoint.json` | ver `checkpoint.json` |

Detalle completo: `checkpoint.json` (`verified_records_by_req`) y
`raw_response/task-70b3354a5168.txt.gz` (respuesta cruda completa del
modelo, sin el cap de 8192 caracteres — fix de
`docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`).

## Cobertura y limitaciones (obligatorio, según §3.4 del contrato de R1)

```yaml
coverage_summary:
  requirements_del_smoke: 1 (ALCOA_CONTEMPORANEOUS)
  hallazgo_con_evidencia: 0
  sin_evidencia_localizada: 1
  no_evaluable: 0
  recall_config_used: "baseline (9 req/llamada) -- NO H2+H4"
  known_limitation: >
    Recall del pipeline baseline medido en 0/7 sobre el fixture set 7P+2N
    (docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md). Este smoke confirma
    ese número en un caso real de producción: P5 no ancló. La config H2+H4
    que sí ancló P5 (2/7) es un script de diagnóstico, no está en
    producción. R2 del roadmap (recuperación determinista) es el gate
    bloqueante declarado para resolver esto.
```
