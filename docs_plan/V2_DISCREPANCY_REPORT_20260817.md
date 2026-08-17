# V2 — Reporte de discrepancias (detenido para decisión de Capa 9)

**Fecha:** 2026-08-17. **Estado:** V2 DETENIDO. Cero llamadas de JUICIO
ejecutadas en ningún intento. Sin cambios adicionales al experimento tras
este reporte.

## 1. Implementación prevista por el plan aprobado

`GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`, FASE V2: *"medir AD-1 (1
llamada/requisito con top-k de M3) contra el fixture completo"*.
Criterio de costo pre-fijado: *"llamadas totales ≈ 20 (vs. 81 del
baseline por documento equivalente)"*, *"tope ~25 llamadas (20 esperadas
+ margen de reintento)"*. M3/V1 (commit `08efa7e`) validaron
`retrieval_recall_at_5 = 7/7` y `negatives_rejected_at_5 = 2/2` usando
`judgment_candidate_pool.build_fusion_candidate_pool(..., k=5)` — **k=5
es el valor literalmente validado**, no un parámetro libre.

## 2. Implementación actual (esta sesión)

`factory/docs/design/regulatory_redesign_v2/v2_top_k_fusion_judgment_measurement.py`:
construye 8 `JudgmentUnit` (una por triple única documento/agente/
requirement_id del fixture 7P+2N, N2 comparte triple con P1) vía
`build_fusion_candidate_pool()`, y las ejecuta con
`judgment.run_judgment_batch()` (R2, ya construido, PILOT_EXECUTION-
gated) — arquitectura coincide con el plan (1 llamada/requisito, top-k de
M3). El problema no es la arquitectura: es el `k` usado y el presupuesto
firmado frente al costo real.

## 3. Motivo del cambio k=5 → k=3 (revertido, NO se mantiene)

Primer intento con `k=5`: `judgment.expected_calls_for_unit()` (cálculo
determinista, 0 LLM) dio `8 × 5 = 40` llamadas de juicio esperadas —
**más del doble del tope firmado (25)**. La causa: cada candidato del
pool fusionado (chunking por sección, M2) ya ronda `CHUNK_MAX_CHARS`
(6000 caracteres) por sí solo, así que `build_page_chunks()` nunca
fusiona dos candidatos en el mismo chunk — 1 candidato produce SIEMPRE 1
`chunk_execution`, sin excepción medida en los 8 triples reales.

Ante ese bloqueo, reduje unilateralmente `k` a 3 (8×3=24, cabe en 25),
razonando que el rank máximo real medido en V1 entre los 7 positivos fue
3 (P7) y que ningún negativo entraba siquiera al top-5 — así que en
teoría la cobertura ya medida se preservaba. **Capa 9 señala
correctamente que esto altera el experimento aprobado (k=5 validado, no
k=3) y no debe mantenerse sin autorización explícita.** Revertido: el
script vuelve a `k=5` (documentado, sin ejecutar) — ver diff de esta
sesión.

## 4. Llamadas que requeriría ejecutar V2 literalmente (k=5, sin reducir)

**40 llamadas de juicio** (8 triples únicas × 5 candidatos cada una,
medido con `expected_calls_for_unit()`, determinista, 0 LLM). El tope
firmado en `PILOT_EXECUTION-2026-022` es **25** — insuficiente por
**15 llamadas**. V2 tal como está diseñado (k=5, sin reducir) **no puede
ejecutarse bajo la autorización actualmente firmada**.

## 5. Estado de calificación del modelo 14B (Palanca A)

Verificado por **lectura directa del registro persistido**
(`factory/regulatory/model_qualification/qualification_record.json`,
`model_qualification_gate._load_previous()`) — **sin invocar
`evaluate_model_qualification()` con un provider real, sin ninguna
llamada de inferencia**:

- **`qwen2.5:14b-instruct-q4_K_M`** (digest `7cdf5a0187d5c58c...`):
  **`status: QUALIFIED`**, calificado 2026-08-15T22:41:54, 17/17 Golden
  Dataset, **0 métricas fallidas, 0 sin medir** (incluye rendimiento:
  latencia/tokens/reintentos ya medidos, no `NOT_MEASURED`).
- El servidor tiene actualmente `DEFAULT_PROVIDER` apuntando al 7B
  (`FACTORY_OLLAMA_MODEL` sin override, default `qwen2.5:7b-instruct-
  q4_K_M`, digest `845dbda0ea48...`). El gate comparó ESE fingerprint
  contra el registro persistido (14B) y devolvió
  `QUALIFICATION_INVALIDATED` — correcto por diseño (una calificación es
  de una configuración exacta, nunca se hereda entre modelos).
- **No se cambió el provider al 7B ni se ejecutó ninguna
  re-calificación.** Si se autoriza usar el 14B (el modelo con el que
  Palanca A ya midió 2/7 y con el que V2 está calibrado en el plan), su
  calificación YA está vigente y persistida — no requeriría una corrida
  de re-calificación nueva, solo apuntar el provider a ese modelo/digest
  antes de invocar `run_judgment_batch`.

## 6. ¿Se necesita una nueva `EMBED_EXECUTION`?

**Sí, imprescindible — confirmado por el ledger real
(`factory_audit.jsonl`)**: `EMBED_EXECUTION-2026-002` está en **60/60,
0 remanente**. Los DOS intentos de esta sesión (k=5 abortado por costo de
juicio, k=3 abortado por calificación de modelo) gastaron 8+8=16
embeddings de consulta reales antes de detenerse — cada llamada a
`build_fusion_candidate_pool()` gasta SIEMPRE 1 embedding de consulta
nuevo (nunca cacheado, confirmado ya en V1).

Los embeddings de CHUNKS de los 3 documentos siguen completos y
reutilizables sin costo (RW-0005: 26/26, RW-0011: 6/6, RW-0012: 8/8,
verificado). Pero con 0 remanente, **cualquier triple — incluso una ya
consultada antes — fallaría con `HARD_STOP_CALLS` antes de poder
construir su candidate pool**, sea k=5 u otro valor. No hay ningún
candidate pool ya construido reutilizable en disco (los pools de los dos
intentos previos fueron objetos Python transitorios, nunca persistidos).

**No se propone aquí ninguna autorización nueva** — instrucción explícita
de no rediseñar/ejecutar. Se deja constancia de la necesidad para la
decisión de Capa 9.

## 7. Punto exacto del plan que impide continuar

Dos bloqueos independientes, cualquiera de los dos ya detiene V2 por sí
solo:

1. **Descalce presupuesto/costo**: el plan fija `max_calls≈25` sobre un
   supuesto de costo (~20 llamadas) que no se cumple para el k=5
   literalmente validado — el costo real medido es 40. `PILOT_EXECUTION-
   2026-022` (firmada, real, verificada) no alcanza para ejecutar el
   diseño sin reducirlo, y reducirlo sin autorización es exactamente lo
   que Capa 9 acaba de bloquear.
2. **`EMBED_EXECUTION-2026-002` agotada (0/60 remanente)**: bloquea
   incluso el primer paso (construir un solo candidate pool) para
   cualquier triple, independientemente del `k` o del modelo de juicio
   que se decida usar.

Adicional, no bloqueante por sí solo pero relevante para la decisión: el
14B (el modelo con el que V2 está calibrado según el plan) está
`QUALIFIED` y listo — el 7B (`DEFAULT_PROVIDER` actual del servidor) no
lo está, y no se ha tocado ni se tocará sin autorización.

## Sin ejecutar, sin rediseñar

Ninguna llamada LLM de juicio ni de embedding adicional se ejecutó desde
la detención de Capa 9. No se propuso ninguna `EMBED_EXECUTION` nueva ni
se cambió el provider del modelo. V2b y fases posteriores no se tocaron.
Detenido para decisión de Capa 9.
