# M4.1 — Reporte de ejecución

**Fecha:** 2026-08-18. Ejecutado según `docs_plan/M4_1_CORRECCION_SEGUNDA_SENAL.md`.
Corrige un defecto de diseño en M4 (commit `9718fd7`): el umbral de
cobertura (recuperación) se usaba solo para autorizar una conclusión
sobre confiabilidad de juicio — propiedad distinta, ya confirmada NO
confiable para evidencia parafraseada (2/7, 3 veces: H1-H4, Palanca A,
V2). 0 llamadas LLM.

## Qué se construyó

- **`_lexical_evidence_absent(per_unit_text, req_id)`** (nueva, pura):
  reutiliza `query_builder.build_retrieval_query()` (citation_text +
  evidence_min_criteria + requirement_terms.yaml — las mismas fuentes
  gobernadas que ya arman la recuperación real, nunca `weak_keywords`
  solo) y `bm25.tokenize()` para la normalización. Filtra tokens de
  longitud < 4 (mismo umbral que `_is_topically_relevant()` ya usa en
  este archivo). Falla cerrado: sin texto/req_id, sin
  `evidence_min_criteria` en el catálogo, o sin términos útiles tras el
  filtro → `False` (M4 no se activa).
- **`_top_k_fusion_coverage_complete()`** ahora exige **AND**, no una
  sola condición: `len(candidate_metadata) >= umbral` **y**
  `_lexical_evidence_absent(...)`. Firma ampliada con `per_unit_text`/
  `req_id` (keyword-only, con default `None` — ningún llamador existente
  se rompe).
- Comentario de `M4_ABSENCE_RANK_THRESHOLD` actualizado: distingue
  explícitamente "garantía de recuperación" de "garantía de juicio
  confiable".
- La entrada de cola (`_dispatch_m4_absence_review`) **no cambió** — el
  contenido enriquecido (umbral, ranking, extractos) es idéntico en
  ambos casos; solo cambia si esa función llega a invocarse.

## Tests (0 LLM)

- `test_m4_threshold_helper_pure_function` (actualizado): ahora prueba
  las 4 combinaciones de la tabla AND — umbral cumplido+sin solapamiento
  → `True`; umbral cumplido+sin texto/req_id → `False`; umbral
  cumplido+CON solapamiento → `False`; umbral no cumplido → `False`
  (short-circuit, no llega a evaluar léxico).
- `test_m4_lexical_overlap_blocks_gap_stays_incomplete` (nuevo): caso
  análogo a P2/P5 real (texto con "audit trail"/"timestamp"/
  "electronicos") — confirma `EVALUATION_INCOMPLETE`, no
  `DOCUMENTATION_GAP`.
- `test_m4_top_k_fusion_threshold_met_emits_gap_not_incomplete`
  (docstring actualizado, mismo texto sin relación de antes — ahora
  exercitando explícitamente la rama AND con ambas condiciones
  verdaderas): sigue en verde, confirma que M4 sigue teniendo alcance
  útil para el caso sin solapamiento léxico.
- Los otros 2 tests de M4 (`below_threshold`, `without_candidate_metadata`)
  no necesitaron cambios — el `AND` corta en la primera condición antes
  de llegar al chequeo léxico.

**Resultado real:**
```
factory/tests/test_gmpai_chunked_engine.py -k "m4 or judgment_mode or baseline"
  → 12 passed (11 anteriores + 1 nuevo)

+ test_absence_consolidator.py + test_m3_retrieval_mode.py
+ test_r2_3_d1_fusion_candidate_pool.py
  → 131 passed (0 regresiones)

factory/tests/ (suite completa, DOS corridas)
  → 2523 passed, 14 failed, 5 skipped, 1 xfailed, 2 errors (1198s)
  → IDÉNTICO en número Y en identidad de fallos a la corrida de
    verificación de M4 original (2522 passed antes de añadir el test
    nuevo de M4.1 -- +1 exacto). Los 14 failed/2 errors son la MISMA
    lista exacta (contaminación real del store de gobernanza de esta
    sesión + disco 75%, ya verificados pre-existentes con git stash
    antes del commit de M4). 0 regresiones nuevas.
```

## Replay del fixture completo (0 LLM, sobre datos ya pagados de V2)

`_lexical_evidence_absent()` corrido contra el texto REAL de cada
candidato (índice de recuperación real, mismo que evaluó el modelo en
V2 — no texto sintético):

| Caso | Requisito | `_lexical_evidence_absent` | Resultado con M4.1 |
|---|---|---|---|
| **P2** | `21_CFR_11.10(g)` | `False` (comparte "access", tabla de seguridad, etc.) | **`EVALUATION_INCOMPLETE`** (antes: `DOCUMENTATION_GAP`) |
| **P5** | `ALCOA_CONTEMPORANEOUS` | `False` (comparte "date"/"time"/audit trail) | **`EVALUATION_INCOMPLETE`** (antes: `DOCUMENTATION_GAP`) |
| **P6** | `21_CFR_211.68(b)` | `False` | **`EVALUATION_INCOMPLETE`** (antes: `DOCUMENTATION_GAP`) |
| **P7** | `21_CFR_211.68(b)` | `False` | **`EVALUATION_INCOMPLETE`** (antes: `DOCUMENTATION_GAP`) |
| P4 | `ALCOA_ATTRIBUTABLE` | `True` (sin overlap) — **irrelevante**: `applicability('ALCOA_ATTRIBUTABLE','DS')=='review_required'`, M4 nunca llega a evaluarse (bloqueado aguas arriba, mismo hallazgo que M4 original) | sin cambio, `EVALUATION_INCOMPLETE`/`APPLICABILITY_UNRESOLVED` |
| N1 | `ANNEX11_4` | n/a | sin cambio, `CROSS_REFERENCE_MISSING` (rama no depende de cobertura) |
| Sintético (sin términos relacionados) | — | `True` | `DOCUMENTATION_GAP` — confirma que M4 conserva alcance útil |

**Los 4 casos reales con sospecha alta de falso negativo (P2/P5/P6/P7)
vuelven, los 4, a `EVALUATION_INCOMPLETE`** — no solo P2/P5 como
anticipaba la instrucción; P6/P7 también comparten léxico con su
requisito (la frase de calibración/credenciales ya identificada en la
investigación del 2026-08-15 contiene vocabulario del propio Evidence
Pack). Ningún caso real del fixture queda promovido a
`DOCUMENTATION_GAP` por M4 en este momento — **`ACTIONABLE_WITHOUT_HUMAN`
baja de 4/7 (M4 original) a 0/7 con los datos reales disponibles hoy**;
la corrección prioriza precisión de etiqueta sobre alcance, tal como
pedía la instrucción.

## Entrega

```
LEXICAL_CHECK_IMPLEMENTED =   SÍ -- _lexical_evidence_absent(), reutiliza
                               build_retrieval_query()/bm25.tokenize(),
                               0 líneas de tokenización reimplementadas
M4_NOW_REQUIRES_AND =         confirmado -- _top_k_fusion_coverage_complete()
                               exige umbral de rango AND ausencia léxica
P2_P5_RELABELED =             EVALUATION_INCOMPLETE (confirmado, real)
P6_P7_RESULT =                EVALUATION_INCOMPLETE (real, NO asumido --
                               ambos comparten léxico con su requisito,
                               verificado contra el índice real)
SYNTHETIC_GAP_STILL_WORKS =   SÍ -- confirmado con test + replay directo
NEGATIVES_STILL_REJECTED =    N1 sin cambio (rama no depende de cobertura);
                               N2 no es una triple real de producción
                               (ver docs_plan/M4_IMPLEMENTACION.md)
CODE_CHANGED =                2 archivos (chunked_engine.py, test_gmpai_
                               chunked_engine.py), diff mostrado en chat,
                               NO commiteado todavía
TESTS_NEW =                   2 nuevos/actualizados, 12/12 en la
                               selección M4, 131/131 en la selección
                               ampliada, 0 regresiones en la suite
                               completa (2 corridas idénticas, 2523
                               passed/14 failed/2 errors, misma lista
                               exacta de fallos preexistentes)
PRODUCTION_ENABLEMENT =       BLOCKED (sin cambio)
```

## DETENERSE — pendiente de Cesar

Diff mostrado en chat. **Sin commit sin autorización explícita** —
causa raíz separada del commit de M4 original (`9718fd7`), tal como
pide la instrucción.
