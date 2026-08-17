# V2 — Resultado final y ADRs (Bloques A, B y C YA EJECUTADOS)

**Fecha:** 2026-08-17. **Estado:** V2 EJECUTADO Y COMPLETO (`stop_reason:
BATCH_COMPLETE`). Este documento NO ejecuta nada — es el cierre
documental (Bloque B/entrega + ADRs) que quedaba pendiente. **No se hizo
ninguna llamada LLM ni de embedding al prepararlo.**

## 0. Hallazgo de esta revisión: el plan ya se ejecutó completo

Al retomar la sesión encontré que los Bloques A, B **y C** de la
"Decisión Arquitectónica — Corrección de AD-1 y Desbloqueo de V2" ya
estaban implementados y **ejecutados con llamadas reales**, evidencia
verificada contra disco y el ledger de decisiones
(`factory/layer9/decisions/decisions_v2.jsonl`):

- `PILOT_EXECUTION-2026-021` (agent_proposed, 2026-08-17T16:30:27Z) →
  confirmada por Cesar como `PILOT_EXECUTION-2026-022`
  (human_confirmed, `approved_by_id: cesar`, 2026-08-17T16:34:49Z,
  `max_calls=25`).
- `EMBED_EXECUTION-2026-003` (agent_proposed, 2026-08-17T18:05:26Z) →
  confirmada por Cesar como `EMBED_EXECUTION-2026-004`
  (human_confirmed, `approved_by_id: cesar`, 2026-08-17T18:12:18Z,
  `max_calls=10`, exclusiva para las 8 consultas de V2 — no reindexa
  chunks).
- Re-calificación de runtime del 7B ejecutada (`chunked-abb0e483fcbd`,
  2 llamadas reales, 2026-08-17T18:26:43Z) — confirma explícitamente
  `qwen2.5:7b-instruct-q4_K_M` como modelo activo antes de la primera
  llamada de juicio, cumpliendo Bloque C.3.
- Corrida real de juicio: `v2_top_k_fusion_judgment_measurement.py`
  ejecutado con `_K = 3`, resultado persistido en
  `factory/regulatory/pilot_run/v2_top_k_fusion_20260817/v2_result.json`
  — **24/24 llamadas de juicio realizadas, 8/8 llamadas de embedding de
  consulta realizadas, `stop_reason: BATCH_COMPLETE`, 0 errores**.
  Presupuesto consumido: `PILOT_EXECUTION-2026-022` en 24/25,
  `EMBED_EXECUTION-2026-004` en 8/10.
- 4 hallazgos ya encolados en `factory/layer9/review_queue.jsonl`
  (revisión humana pendiente, como corresponde — ningún hallazgo se
  auto-cierra).

**No se repite ninguna de estas llamadas.** El presupuesto de ambas
autorizaciones tiene margen (`PILOT_EXECUTION-2026-022`: 1 de margen;
`EMBED_EXECUTION-2026-004`: 2 de margen) pero no hay ninguna unidad
pendiente de las 8 planificadas — las 8 triples del fixture ya tienen
resultado `COMPLETED`. Lo único genuinamente pendiente del plan era el
cierre documental (Bloque B, entrega + ADRs), que es lo que este
documento completa.

## 1. Resultado crudo por requisito (Bloque C.4 — detalle sin ocultar)

| Triple | Doc/Agente/Requisito | Candidatos evaluados (obs.) | Agregado | Nota |
|---|---|---|---|---|
| P1+N2 | RW-0005 / fda_part11 / `21_CFR_11.10(e)` | `[observed, no, no]` | `EVALUATION_INCOMPLETE` | Evidencia real y sustantiva encontrada (cita de audit trail UR3.3.1/3.3.2 anclada, `evidence_page=1`) en 1 de 3 candidatos |
| P2 | RW-0005 / fda_part11 / `21_CFR_11.10(g)` | `[no, no, no]` | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | Encolado para revisión humana |
| P3 | RW-0005 / eu_annex11 / `ANNEX11_17` | `[no, observed, no]` | `EVALUATION_INCOMPLETE` | Evidencia real encontrada — caso que motivó M2 (retención/Data) |
| P4 | RW-0011 / alcoa_plus / `ALCOA_ATTRIBUTABLE` | `[no, no, no]` | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | Encolado para revisión humana |
| P5 | RW-0005 / alcoa_plus / `ALCOA_CONTEMPORANEOUS` | `[no, no, no]` | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | Encolado para revisión humana |
| P6 | RW-0011 / fda_cgmp_211 / `21_CFR_211.68(b)` | `[no, no, no]` | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | Encolado para revisión humana |
| P7 | RW-0012 / fda_cgmp_211 / `21_CFR_211.68(b)` | `[no, no, no]` | `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | Encolado para revisión humana |
| N1 | RW-0005 / eu_annex11 / `ANNEX11_4` | `[no, no, no]` | `CROSS_REFERENCE_MISSING` | Rechazado correctamente, sin encolar |

("no" = `not_observed_in_chunk`. Detalle completo, cita por candidato y
`fusion_rank`/`bm25_rank`/`embedding_rank` en `review_queue.jsonl` y en
los checkpoints de `pilot_run/v2_top_k_fusion_20260817/checkpoints/`.)

`EVALUATION_INCOMPLETE`/`ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE` es el
comportamiento fail-closed correcto: con `k=3` (no full-document
coverage), el agregador (`verify_sufficiency_aggregated`,
`chunked_engine.py:1860`) se niega a declarar ausencia — y, para P1/P3,
tampoco declara `CONFIRMED` automáticamente pese a la observación
positiva, porque la confirmación completa exige el resto del pipeline de
anclaje A/B/C/D sobre ese candidato, que este `EVALUATION_INCOMPLETE`
deja abierto para adjudicación humana en vez de auto-confirmar. Ningún
hallazgo se cerró solo.

## 2. Hallazgo central (honesto, no buscado a propósito)

**El techo de recall del modelo se replica una tercera vez, con la
arquitectura ya corregida.** V1 midió `retrieval_recall_at_5 = 7/7`
(el chunk correcto SIEMPRE estaba entre los candidatos recuperados). Con
`k=3` y evaluación de JUICIO real (no solo recuperación), el modelo
7B **solo reconoció evidencia sustantiva en 2 de 7 positivos (P1, P3)**
— exactamente el mismo patrón 2/7 ya confirmado por Palanca A
(`docs_plan` bottleneck 2026-08-15, ver
[[project-bottleneck-confirmado-r4]]).

Esto **descarta definitivamente** la hipótesis de que el problema era
solo de recuperación (M2/M3 ya lo arreglaron — el chunk correcto llega al
modelo). El cuello de botella es la lectura/juicio del modelo 7B sobre un
candidato ya correcto y presente — consistente con el riesgo central ya
declarado en `CLAUDE.md` ("recall del modelo (2/7 medido)").

## 3. Negativos — corrección honesta al criterio "2/2"

- **N1: rechazado correctamente** (`CROSS_REFERENCE_MISSING`, 0/3
  observado). Bloqueante cumplido.
- **N2: NO verificable de forma independiente en este diseño.** N2
  comparte la misma triple (documento/agente/requisito) que P1 —
  decisión de diseño tomada en `PILOT_EXECUTION-2026-021` para ahorrar
  presupuesto ("1 sola llamada real cubre ambos"). El resultado de esa
  triple es un único agregado (`EVALUATION_INCOMPLETE`, con evidencia
  real encontrada para P1). **No hay manera de leer de este resultado si
  el sistema habría rechazado N2 de haberse evaluado por separado** — el
  ahorro de presupuesto tuvo como costo perder esa señal. Corrijo mi
  entrega anterior: el criterio de éxito no es "negativos 2/2
  rechazados", es **"N1 rechazado (1/1 verificable); N2 no medible por
  diseño compartido de triple"**. No se propone gastar presupuesto nuevo
  para separar P1/N2 — es una decisión de Cesar si vale la pena para V2b.

## 4. ADRs — registro formal (Bloque §8 de la decisión arquitectónica)

**ADR-V2-1.** AD-1 original ("1 llamada/requisito", prompt agrupando k
pasajes) se corrige a "hasta k llamadas/requisito, agregación
determinista, sin agrupamiento". Motivo: riesgo de atribución cruzada de
citas en prompts multi-pasaje — rompería el principio no negociable de
"una cita ancla siempre contra UN chunk verificable". Alternativa
rechazada: agrupar los k pasajes en un solo prompt. Estado:
**implementado y ejecutado** — `evaluate_chunked()` ya evalúa cada
candidato de forma independiente, sin cambios de código necesarios.

**ADR-V2-2.** `k=3` para la capa de JUICIO (no 5). Justificado por los
ranks reales medidos en V1 (los 7 positivos conocidos entran en rank ≤3).
No invalida `retrieval_recall_at_5=7/7` de V1 (que sigue midiendo k=5, sin
remedir). Estado: **implementado y ejecutado** — 8×3=24 llamadas reales,
dentro del tope firmado de 25.

**ADR-V2-3 (CORREGIDO respecto al texto original de la decisión).** El
texto original afirmaba "V2 consume el candidate pool persistido de V1
... `EMBED_EXECUTION_NEW_REQUIRED = false`". Verificado contra código y
disco (`V2_DISCREPANCY_REPORT_20260817_ADENDA.md`, §"Corrección factual")
que esa premisa era falsa: `build_fusion_candidate_pool()` nunca persiste
el vector de consulta ni el ranking RRF — solo los embeddings de CHUNK
(reutilizables) y el índice BM25. Por eso se propuso y firmó
`EMBED_EXECUTION-2026-004` (8 consultas nuevas, no una ampliación de la
agotada `-002`). Estado real: **`EMBED_EXECUTION_NEW_REQUIRED = true`,
ya ejecutado con autorización propia** — la premisa original queda
registrada como corregida, no como cumplida tal cual se escribió.

## 5. Entrega final (reemplaza la tabla `Entrega` de la decisión original)

```
AD1_CORRECTED =                 hasta k llamadas/requisito, agregación
                                determinista (no agrupamiento) -- EJECUTADO
K_VALUE =                       3 -- EJECUTADO (24/24 llamadas de juicio)
EMBED_EXECUTION_NEW_REQUIRED =  true (corrección de ADR-V2-3) -- EJECUTADO
                                bajo EMBED_EXECUTION-2026-004 (8/10 usadas)
V1_M3_VALIDITY =                sin cambios, no se remidieron
MODEL_FOR_V2 =                  7B, confirmado por recalificación real
                                (chunked-abb0e483fcbd) antes de la 1a llamada
EARLY_STOP =                    no -- 3 candidatos completos por requisito,
                                confirmado en checkpoints
EXPECTED_CALLS =                24 -- REAL: 24 llamadas de juicio, 0 errores
PILOT_EXECUTION_USADA =         PILOT_EXECUTION-2026-022 (24/25 consumidas)
EMBED_EXECUTION_USADA =         EMBED_EXECUTION-2026-004 (8/10 consumidas)
ADRS_REGISTRADOS =              3 (ADR-V2-1/2/3, este documento)
RECALL_JUICIO_REAL =            2/7 (P1, P3) -- replica el techo ya
                                confirmado por Palanca A, NO una mejora
NEGATIVOS =                     N1 rechazado (1/1 verificable); N2 no
                                medible por diseño de triple compartida
HALLAZGOS_ENCOLADOS =           4 (P2, P4, P5, P6... ver review_queue,
                                pendientes de adjudicación humana)
V2B_STATUS =                    NO autorizado (sin cambios)
PRODUCTION_ENABLEMENT =         BLOCKED
```

## Sin ejecutar nada nuevo

Este documento es puramente de cierre/registro. No se hizo ninguna
llamada LLM ni de embedding al prepararlo. No se propone ninguna
autorización nueva. V2b y fases posteriores sin tocar. Pendiente de
Cesar: adjudicación humana de los 4 hallazgos en `review_queue.jsonl`, y
decidir si el hallazgo de recall 2/7 (idéntico al de Palanca A, ahora con
arquitectura de recuperación ya corregida) cierra la vía de "mejorar
recuperación" como palanca y redirige el roadmap hacia palancas sobre el
propio modelo/prompt de juicio.
