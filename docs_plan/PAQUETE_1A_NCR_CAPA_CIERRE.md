# PAQUETE 1a — candidatos NCR/CAPA/change-control

Fecha: 2026-08-19. Decisiones de Cesar: regla conservadora del diseño,
los 3 tipos de una vez, investigar fuente de recurrencia antes de
implementar.

## Investigación previa: fuente de recurrencia

`factory/layer9/review_queue.jsonl` (append-only, nunca se borra ni
reescribe salvo mutación de `status` en el mismo registro — confirmado en
código, no solo en docstring) ya es una fuente real y usable: 38 entradas
`finding_review` reales en el archivo de producción, con solo 11 pares
`(requirement_id, document_id)` distintos — la mayoría ya recurre.
`DOCUMENTATION_GAP`/`PROVISIONAL_GAP` ya se enqueuean ahí desde
`_dispatch_baseline_gap_review`/`_dispatch_m4_absence_review`
(`chunked_engine.py`). No hizo falta construir un índice nuevo — solo una
función de consulta.

## Implementado: NCR + CAPA (regla real, con recurrencia)

- `factory/layer9/human_review_queue.py`:
  `count_prior_finding_occurrences()` (recurrencia real, excluye
  `superseded`), `enqueue_governance_candidate_for_review()` (nuevo
  `entry_type='governance_candidate'`, mismo patrón append-only/locking
  que `enqueue_finding_for_review()`), `mark_candidate_reviewed()`
  (decisión humana, `human_classification` obligatorio si `confirmed`,
  nunca hereda la sugerencia en silencio).
- `factory/services/governance_candidate_classifier.py`: regla exacta
  aprobada — `DOCUMENTATION_GAP`/`PROVISIONAL_GAP` sin ocurrencia previa
  → NCR; con ≥1 ocurrencia previa → CAPA; cualquier otra conclusión → sin
  candidato.
- `factory/engines/gmpai_integrity/chunked_engine.py`: nuevo
  `_dispatch_governance_candidate()`, llamado desde
  `_dispatch_baseline_gap_review()` y `_dispatch_m4_absence_review()` —
  mismo patrón no-bloqueante que el resto de los `_dispatch_*` (un fallo
  aquí nunca tumba el run, se registra en `governed_exceptions`).
- `factory/api/routes/layer9.py`: `POST /review/candidates/{rc_id}/decide`
  (`Depends(require_identity)`, Paquete 2), mismo patrón que
  `/review/findings/{rc_id}/decide`.
- `factory/core/audit_writer.py`: nuevo evento válido
  `governance_candidate_enqueued_for_review`.

## CHANGE_CONTROL — deliberadamente NO auto-sugerido

Auditado el vocabulario real de `review_flags`
(`absence_consolidator.py`): `"DEVIATION_IDENTIFIED": "PROVISIONAL_DEVIATION"`
está declarado en el mapeo de conclusión provisional pero **ningún
productor del pipeline lo emite jamás** (grep confirmado, única aparición
en todo `factory/`). No existe hoy ninguna señal objetiva de "desviación
de procedimiento" distinta de "falta de evidencia". Mapear esto desde
`review_flags` existentes (p.ej. `*_BLOCKED_BY_OPEN_CONTRADICTION`, que
en realidad significa "chunks contradictorios", no desviación de
procedimiento) habría sido inventar una señal — exactamente lo que este
paquete prohíbe.

`CHANGE_CONTROL` queda como tipo válido en el esquema — el humano puede
reclasificar manualmente un NCR/CAPA sugerido como change-control vía
`human_classification` en `/review/candidates/{rc_id}/decide` — pero el
clasificador automático nunca lo sugiere. Pendiente de que Cesar defina
una señal real si quiere que se sugiera automáticamente en el futuro.

## Efecto colateral encontrado y corregido: colisión con consumidores existentes de `list_pending()`

Al enqueuear una segunda entrada (`governance_candidate`) con el mismo
`(run_id, requirement_id)` que el `finding_review` ya existente, dos
consumidores que no filtraban por `entry_type` se veían afectados:

- `factory/regulatory/tier1_report.py` construía `pending_by_req` sin
  filtrar `entry_type` — el candidato (entrada posterior en el archivo)
  pisaba el `rc_id` real del finding en el diccionario. Corregido:
  filtro explícito a `entry_type == "finding_review"`.
- `factory/ui/js/mission_control/review.js::renderReview()` clasificaba
  todo lo que no fuera `finding_review` como RC real (`rcs`), lo que
  habría intentado pedir un diff inexistente para un `governance_candidate`.
  Corregido: excluido explícitamente de ambos buckets — sin panel propio
  todavía (ver K2 de Paquete 4, mismo alcance "completar superficie de
  UI").
- Dos tests existentes de `test_gmpai_chunked_engine.py`
  (`test_m4_gap_dispatched_to_review_queue_with_ranking_and_threshold`,
  `test_baseline_gap_dispatched_to_review_queue_conclusion_unchanged`)
  asumían un único `pending` por `requirement_id` — actualizados con el
  mismo filtro.

## Tests

- `factory/tests/test_governance_candidate_classifier.py` — 17 tests
  (recurrencia, clasificación NCR/CAPA, exclusión de superseded, encolado,
  decisión humana con override, identidad reservada, entry_type incorrecto).
- `factory/tests/test_governance_candidate_decision_endpoint.py` — 9 tests
  HTTP (confirmar, override de tipo, 422 sin clasificación, rechazo, 401
  sin identidad, 409 doble decisión, 404 entry_type incorrecto).
- `factory/tests/test_gmpai_chunked_engine.py::test_documentation_gap_also_dispatches_a_governance_candidate` —
  integración real vía `evaluate_chunked()` (Ollama mockeado), confirma
  que el candidato se encola ADEMÁS del finding_review, nunca en su lugar.

## Resultado

```
NCR_CAPA_IMPLEMENTED =        SI (regla real, recurrencia via review_queue.jsonl)
CHANGE_CONTROL_IMPLEMENTED =  NO -- sin señal objetiva real, declarado
                               explícitamente NOT_TRIGGERABLE, tipo válido
                               para reclasificación humana manual
NEVER_AUTO_CLOSES =           SI (solo sugiere, cola humana obligatoria,
                               mark_candidate_reviewed exige identidad real)
RECURRENCE_SOURCE =           review_queue.jsonl (existente, no se
                               construyó índice nuevo)
COLLATERAL_FIXES =            2 (tier1_report.py, review.js) + 2 tests
                               existentes actualizados
TESTS =                       26 nuevos + 2 actualizados, todos pasan;
                               suite dirigida 168/168
CODE_CHANGED =                7 archivos de producción + 3 archivos de
                               test + este doc
PRODUCTION_ENABLEMENT =       BLOCKED
```

## Siguiente paso

Mostrar diff a Cesar y esperar aprobación antes de commit. Panel de UI
para `governance_candidate` queda pendiente, mismo alcance que K2 de
Paquete 4.
