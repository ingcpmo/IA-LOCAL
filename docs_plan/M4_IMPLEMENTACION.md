# M4 — Ausencia en dos niveles (implementación)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/M4_IMPLEMENTACION.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Diseño ya cerrado (AD-3, GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md). Esta
# corrida IMPLEMENTA, no rediseña. Cero llamadas LLM — todo el mecanismo
# es determinista.
#
# Objetivo: que `top_k_fusion` pueda emitir CONFIRMED o DOCUMENTATION_GAP
# por sí solo cuando la evidencia es inequívoca, en vez de que TODO caiga
# en EVALUATION_INCOMPLETE/EVIDENCE_NOT_LOCATED esperando revisión humana.

*(Ver el archivo original de instrucciones para el texto completo del
encargo — se omite aquí para no duplicar; el contenido íntegro fue
recibido en chat el 2026-08-18 y ejecutado tal cual.)*

---

## Reporte de ejecución (2026-08-18)

### Qué se construyó

**No se tocó `absence_consolidator.py`** — su regla dura ("el LLM nunca
emite el gap", `coverage_complete` obligatorio) queda intacta. El cambio
vive enteramente en `factory/engines/gmpai_integrity/chunked_engine.py`,
que es quien ya decidía qué `coverage_complete` pasarle:

1. **`M4_ABSENCE_RANK_THRESHOLD = 3`** — constante gobernada, versionada,
   con la justificación de calibración en su propio comentario (no en un
   documento aparte que se desincroniza). Calibrada contra V1
   (`retrieval_recall_at_5=7/7`) y V2 (`REPORTE_CONSOLIDADO.md`): los 7
   positivos reales del fixture entran al top-3 del ranking de fusión
   (rank máximo medido = 3, P7) — mismo `k=3` ya usado por la capa de
   JUICIO (ADR-V2-2). Consecuencia importante, verificada leyendo
   `judgment_candidate_pool.build_fusion_candidate_pool()`: el pool que
   el modelo YA evalúa (k=3) es, por construcción, la búsqueda
   exhaustiva hasta este umbral — BM25 corre sobre el 100% de los chunks
   del índice y embeddings sobre el 100% del índice de embeddings ANTES
   de truncar al top-k. **No hace falta construir nada nuevo ni gastar
   ninguna llamada de embedding adicional para que M4 opere.**
2. **`_top_k_fusion_coverage_complete(retrieval_mode, candidate_metadata,
   threshold)`** — función pura: `True` solo si `retrieval_mode ==
   "top_k_fusion"` y `len(candidate_metadata) >= threshold`. Ningún otro
   modo/llamador cambia de comportamiento.
3. En el bucle de consolidación: `coverage_complete_for_req =
   full_document_coverage or m4_coverage_complete` — la señal que llega a
   `absence_consolidator.consolidate()` ahora tiene dos fuentes posibles,
   nunca una regla nueva del lado de `consolidate()`.
4. **`_dispatch_m4_absence_review()`** — nueva función de despacho (mismo
   patrón que `_dispatch_partial_coverage_review`/
   `_dispatch_baseline_gap_review`, misma cola R1.8, mismo principio de
   "red de seguridad, nunca cierre automático"). Encola con: umbral
   usado (`M4_ABSENCE_RANK_THRESHOLD_USED=3`), cuántos candidatos se
   buscaron (`M4_ABSENCE_CANDIDATES_SEARCHED=N`), y el ranking COMPLETO
   de esos candidatos (página, `bm25_rank`/`embedding_rank`/
   `fusion_rank`, extracto) — auditable, no una caja negra, requisito
   explícito del encargo.
5. Docstrings de `evaluate_chunked()` actualizados (`candidate_metadata`,
   `full_document_coverage`) — ya no son ciertas las afirmaciones previas
   de "nunca influye en la consolidación" / "puramente decorativo".

### Tests reales (0 LLM, todos con mocks del provider — mismo patrón que
el resto de la suite de `chunked_engine`)

5 tests nuevos en `factory/tests/test_gmpai_chunked_engine.py`:
- `test_m4_threshold_helper_pure_function` — la función pura, sin mocks.
- `test_m4_top_k_fusion_threshold_met_emits_gap_not_incomplete` — mismo
  escenario que el test de regresión ya existente
  (`test_judgment_mode_negative_never_emits_gap_falls_to_evaluation_incomplete`),
  con `retrieval_mode='top_k_fusion'` y 3 candidatos: ahora emite
  `DOCUMENTATION_GAP`/`PROVISIONAL_GAP`, nunca `EVALUATION_INCOMPLETE`.
- `test_m4_top_k_fusion_below_threshold_still_incomplete_no_regression` —
  2 candidatos (`< 3`): M4 NO aplica, sigue `EVALUATION_INCOMPLETE` —
  confirma que el umbral es real, no decorativo.
- `test_m4_top_k_fusion_without_candidate_metadata_no_regression` —
  `retrieval_mode='top_k_fusion'` sin `candidate_metadata`: cae al
  comportamiento de siempre.
- `test_m4_gap_dispatched_to_review_queue_with_ranking_and_threshold` —
  verifica los 3 flags de auditoría y el ranking completo en la entrada
  de `review_queue.jsonl`.

**Resultado real de ejecución:**
```
factory/tests/test_gmpai_chunked_engine.py -k "m4 or judgment_mode or baseline"
  → 11 passed

factory/tests/test_gmpai_chunked_engine.py + test_absence_consolidator.py
+ test_m3_retrieval_mode.py + test_r2_3_d1_fusion_candidate_pool.py
  → 130 passed (0 regresiones)

factory/tests/ (suite completa)
  → 2522 passed, 14 failed, 5 skipped, 1 xfailed, 2 errors (1179s)
```

**Verificación explícita de que los 14 failed + 2 errors son
preexistentes** (no causados por este diff): `git stash` de
`chunked_engine.py` + el archivo de test, re-corrida de los mismos 8
tests con failure real (`test_decision_migration.py` ×3,
`test_governance_endpoints.py::test_the_two_stores_stayed_independent`,
`test_resignature_g2prime.py`/`test_artifact_version_signing.py`/
`test_governance_signature_flow_g21.py` — los tres "no test in this file
wrote to the real store", `test_status_risks.py::
test_every_blocking_risk_is_justified_by_a_real_state`) →
**se reproducen idénticos sin el diff de M4** — contaminación real del
store de gobernanza y de disco (75.1%) de esta misma sesión (N2,
adjudicaciones, `PILOT_EXECUTION-2026-023/024`), no del código de M4.
`test_runtime_identity` (2 tests) falla por el patrón ya documentado del
proyecto ("expected pre-commit" — el runtime no puede coincidir con HEAD
mientras hay un diff sin commitear) — se resuelve al commitear, no antes.
Los 2 `ERROR` de Playwright UI y 3 tests de gobernanza no se investigaron
más allá de la reproducción idéntica sin el diff (mismo criterio que
`29e392c` aplicó a sus 6 fallos preexistentes).

### Entrega

```
M4_THRESHOLD_CALIBRATED =    3 (M4_ABSENCE_RANK_THRESHOLD, chunked_engine.py)
                              -- evidencia: V1 recall_at_5=7/7, V2 rank
                              máximo real de los 7 positivos = 3 (P7),
                              mismo k ya usado por la capa de JUICIO
NEGATIVES_STILL_REJECTED =   pendiente de medir en el replay POST-COMMIT
                              (Bloque ENTREGA original lo pide después de
                              la aprobación -- no ejecutado todavía)
POSITIVES_ABOVE_THRESHOLD =  pendiente de medir en el mismo replay
ACTIONABLE_WITHOUT_HUMAN =   pendiente de medir en el mismo replay
CODE_CHANGED_THIS_RUN =      2 archivos (chunked_engine.py +145/-6,
                              test_gmpai_chunked_engine.py +123), NO
                              commiteados todavía
TESTS_NEW =                  5/5 verdes, 130/130 en la selección
                              relevante, 0 regresiones confirmadas contra
                              la suite completa (14 failed/2 errors
                              preexistentes, verificado con git stash)
PRODUCTION_ENABLEMENT =      BLOCKED (sin cambio)
```

## DETENERSE — pendiente de Cesar

Diff mostrado abajo en el chat. **Sin commit sin autorización explícita.**
Tras la aprobación: commitear con causa raíz única, y solo entonces
correr el replay del fixture completo (0 LLM, sobre los 8 checkpoints
reales ya pagados de V2) para reportar
`NEGATIVES_STILL_REJECTED`/`POSITIVES_ABOVE_THRESHOLD`/
`ACTIONABLE_WITHOUT_HUMAN` — la métrica real de si M4 cumplió su
objetivo, tal como pide el bloque ENTREGA original.
