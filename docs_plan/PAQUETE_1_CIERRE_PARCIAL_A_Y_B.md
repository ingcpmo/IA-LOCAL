# PAQUETE 1 — cierre parcial: A (page_numbers) + (b) informe unificado

Fecha: 2026-08-19. Autorizado por Cesar: ejecutar A y (b) ahora; (a)
(candidatos NCR/CAPA/change-control) queda para después, pendiente de
resolver la regla de clasificación (ver
`docs_plan/PAQUETE_1_INTEGRACION_HALLAZGOS_DISENO.md`).

## Cierre de hallazgo A

`factory/regulatory/retrieval/judgment.py` — `run_judgment_batch()` no
pasaba `page_numbers` a `ce.evaluate_chunked()` pese a que
`unit.candidate_chunks` es siempre un pool de candidatos (no el documento
completo, `full_document_coverage=False`), así que `build_page_chunks()`
caía al fallback 1..N por posición dentro del pool en vez de la página
real del documento.

**Fix**: `page_numbers=[c["page_start"] for c in unit.candidate_chunks]`
— mismo patrón ya usado en `corpus_runner.py:606-620` para el mismo tipo
de entrada.

Auditados todos los demás callers de `evaluate_chunked()`/
`build_page_chunks()` en producción: ninguno más tiene el defecto — o ya
pasan `page_numbers` (`corpus_runner.py:395,606`) o legítimamente
dependen del fallback 1..N porque su entrada es el documento completo en
orden (`tier1_report.py`, `corpus_runner.py:757`, `indexer.py`,
`reverify_offline.py`, `run_validation_evidence.py`,
`w5v2_evidence_run.py`).

**Test**: `test_page_numbers_passed_are_the_real_candidate_page_starts`
(`factory/tests/test_r2_judgment.py`) — verificado que falla sin el fix
(`assert None == [5, 5, 12]`) y pasa con él.

## Cierre de (b) — informe unificado por hallazgo

Nuevo módulo `factory/services/unified_finding_report.py`:
`build_unified_finding_report(tier1, ...)` combina un `Tier1Report` ya
generado (`tier1_report.py`) con findings narrativos ya existentes
(`gap_assessment_finding_mapper.py`, forma `findings_completos_*.json`)
para el mismo `requirement_id` — sin reescribir ninguno de los dos
módulos, sin disparar ninguna corrida ni llamada LLM nueva.

**Hallazgo de diseño real** (documentado en el módulo): los dos módulos
hablan vocabularios distintos y no hay traducción determinista conocida
de uno a otro — `gap_assessment_finding_mapper` exige campos narrativos
(`clasificacion_brecha`, `severidad`, `recomendacion`, etc.) que
`chunked_engine`/`tier1_report` no producen. Inventar esa traducción
habría violado la regla central del paquete ("sin inventar campos"). La
solución: la unión es opcional y explícita por estado —

- `MAPPED`: existe un finding narrativo real para ese requisito y mapeó
  limpio → riesgo + recomendación + trazabilidad completa (`rules`)
  poblados tal cual los produce `gap_assessment_finding_mapper`.
- `NO_GAP_ASSESSMENT_DATA`: no hay finding narrativo para ese requisito
  (el caso normal en una corrida Tier-1 en vivo hoy) — declarado
  explícito, nunca inventado.
- `NOT_MAPPABLE`: hay finding narrativo pero
  `NotMappableToCurrentSchema` lo rechazó — se propaga el motivo real,
  nunca se oculta ni se fuerza un mapeo.

`render_unified_finding_markdown()` — mismo patrón texto→texto que
`render_tier1_markdown()`, reutiliza el mismo banner de cumplimiento y la
misma función de etiqueta PROVISIONAL (`_estado_label`), sin duplicar
texto.

**Tests**: `factory/tests/test_unified_finding_report.py`, 7 tests, usa
el fixture real `findings_completos_FS_v1_2_v4.json` (mismo que
`test_gap_assessment_finding_mapper.py`) para los 3 casos (MAPPED —
ANNEX11_7.1/FSV12-07 HIGH_RISK; NOT_MAPPABLE — ALCOA_AVAILABLE/FSV12-19
por ambigüedad de página; NO_GAP_ASSESSMENT_DATA — requisito sin
narrativo asociado), más verificación de que ningún campo se inventa y
que el markdown nunca declara cumplimiento.

## Resultado

```
A_CLOSED =                    SI (judgment.py, page_numbers reales del pool)
B_UNIFIED_REPORT_BUILT =      SI (factory/services/unified_finding_report.py)
B_REUSES_BOTH_MODULES =       SI (0 reglas reimplementadas de tier1_report.py
                               ni de gap_assessment_finding_mapper.py)
B_NEVER_INVENTS_FIELDS =      SI (3 estados explícitos: MAPPED/
                               NO_GAP_ASSESSMENT_DATA/NOT_MAPPABLE)
TESTS =                       107/107 (suite dirigida: tier1_report,
                               gap_assessment_finding_mapper, r2_judgment,
                               unified_finding_report)
CODE_CHANGED =                3 archivos (judgment.py, nuevo
                               unified_finding_report.py, 2 archivos de test)
PACKAGE_1A_STATUS =           DIFERIDO — pendiente regla de clasificación
                               NCR/CAPA/change-control (Cesar)
PRODUCTION_ENABLEMENT =       BLOCKED
```

## Siguiente paso

Mostrar diff a Cesar y esperar aprobación antes de commit. Parte (a)
sigue en `docs_plan/PAQUETE_1_INTEGRACION_HALLAZGOS_DISENO.md`, pendiente
de las 3 preguntas de clasificación.
