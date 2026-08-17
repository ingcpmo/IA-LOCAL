# M3 — `retrieval_mode="top_k_fusion"` en el camino de producción

**Fecha:** 2026-08-17. **Fase:** `GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`
§"FASE M3 — Recuperación en el camino de producción (sin LLM)".
**Objetivo (AD-2):** conectar `judgment_candidate_pool`/la fusión RRF
(hasta ahora diagnóstico, nunca productizado) al runner de producción
(`corpus_runner.run_corpus_batch`, `run_context='production'`), como modo
paralelo seleccionable, nunca activo por defecto.

## Qué se construyó

`chunked_engine.evaluate_chunked()` ya tenía TODO lo necesario para este
modo (`full_document_coverage=False`, `evaluation_profile`/
`target_requirement_ids`, `candidate_metadata`, `page_numbers`) — nunca
usado desde el camino de producción, solo desde `judgment.py`
(diagnóstico, gated por `PILOT_EXECUTION`). M3 no tocó esa función salvo
para agregar el campo `retrieval_mode` (puramente declarativo, entra al
fingerprint).

- `corpus_runner.run_corpus_batch(..., retrieval_mode: str = "full_chunk", calls_already_used_for_embed: int = 0)`.
  `"top_k_fusion"`: 1 llamada de `evaluate_chunked` POR
  `requirement_id` admitido (Evidence Pack completo, gate 4) en vez de 1
  llamada por unidad barriendo el documento completo. Cada llamada recibe
  el candidate pool top-5 de `judgment_candidate_pool.
  build_fusion_candidate_pool()` — la misma función, sin cambios, ya
  medida 7/7 en V1.
- `chunked_engine.build_run_fingerprint(..., retrieval_mode="full_chunk")`
  — nuevo campo, mismo patrón default-preserva-comportamiento que
  `evaluation_profile`. Un checkpoint `top_k_fusion` nunca puede
  reanudarse como `full_chunk` ni viceversa (verificado,
  `test_fingerprint_differs_between_retrieval_modes`).
- **Preflight de `EMBED_EXECUTION`, ANTES de cualquier llamada de
  cualquier tipo** (decisión explícita de esta sesión, no del diseño
  original): `_preflight_embed_budget()` calcula, sin gastar nada, cuántas
  llamadas de embedding necesitaría el lote completo (chunks pendientes
  de indexar `structure_aware=True` + 1 consulta por par único
  `(document_id, requirement_id)` — nunca cacheada, confirmado en V1) y
  resuelve la EMBED_EXECUTION vigente real (`embed_runner.
  _select_embed_execution_instance`, reutilizada, nunca duplicada). Si no
  cabe: el lote entero se detiene con `stop_reason="HARD_STOP_EMBED_CALLS"`,
  todas las unidades `NOT_STARTED_HARD_STOP` — ninguna llamada de JUICIO
  se gasta primero para descubrir a mitad de camino que el embedding no
  alcanza. Esta es la respuesta a la pregunta abierta en la propuesta de
  M3 ("¿qué pasa si el lote necesita más embeddings de los que quedan?"):
  pre-flight antes de empezar, mismo principio fail-closed que D4-A ya
  aplica al presupuesto de juicio.
- `UnitOutcome.run_ids: list[str]` (aditivo): en modo `top_k_fusion` una
  unidad dispara N `evaluate_chunked` (uno por requisito), cada uno con
  su propio `run_id` — se agregan (suma de `calls_made`/`wall_seconds`/
  `technical_execution_failures`) en un único `UnitOutcome`, con la lista
  completa de `run_ids` para trazabilidad. `[]` en modo `full_chunk`.

## Tests (0 LLM, `factory/tests/test_m3_retrieval_mode.py`, 9/9 verde)

Todo mockeado (`evaluate_chunked`, `build_fusion_candidate_pool`,
`run_embed_batch`) — lo que se prueba es el CABLEADO, no el recall en sí
(el recall real de `build_fusion_candidate_pool` ya está medido end-to-end
sin mocks en V1, 7/7 — repetirlo aquí gastaría presupuesto de
`EMBED_EXECUTION` de nuevo sin necesidad).

- `full_chunk` (default, sin pasar `retrieval_mode`): comportamiento
  idéntico a siempre — regresión.
- `top_k_fusion` nunca se activa implícitamente (default del parámetro
  verificado por firma).
- Preflight de embedding: cabe → sigue; no cabe → `HARD_STOP_EMBED_CALLS`
  antes de cualquier llamada de juicio (`judgment_calls == 0` verificado).
- Cableado real de una unidad: `evaluate_chunked` se llama exactamente 1
  vez por requirement_id admitido, con `full_document_coverage=False`,
  `evaluation_profile="H2H4"`, `target_requirement_ids=[req_id]`,
  `candidate_metadata`/`per_unit_text`/`page_numbers` derivados
  correctamente del pool fusionado.
- Defensa en profundidad: si `run_embed_batch` de una unidad concreta
  reporta `HARD_STOP_CALLS` (reconciliación manual desactualizada pese al
  preflight del lote), la unidad falla explícito
  (`EmbedBudgetInsufficientError`) — nunca sigue con candidatos sin
  embeddings completos.
- Fingerprint: `full_chunk` vs `top_k_fusion` producen fingerprints
  distintos; el default sigue siendo `full_chunk` (retrocompatible).

Suite completa post-cambio: sin regresiones en `test_corpus_runner.py`
(10/10), `test_gmpai_chunked_engine.py`, `test_checkpoint_fingerprint_
invalidation.py`, `test_r2_retrieval.py`/`test_r2_embed.py`/
`test_r2_3_d1_fusion_candidate_pool.py`/`test_r2_judgment.py`,
`test_m2_section_aware_chunking.py`, `test_common_contract_composer.py`
(166/166 en esa selección).

## Qué NO se ejecutó en esta fase

Ninguna corrida real: `retrieval_mode="top_k_fusion"` está construido,
probado y sin activar. Corresponde a V2 (medición decisiva de juicio
requisito-céntrico) decidir si se usa para una corrida real — esa fase
exige autorización de presupuesto de `PILOT_EXECUTION`/`CORPUS_
AUTHORIZATION` y firma de Capa 9 ANTES de la primera llamada, sin
excepción, por diseño ya establecido en el roadmap.
