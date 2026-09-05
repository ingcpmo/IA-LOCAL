# CF-6 v2.0 · R4 — Precision-fix mínimo: `"can"` añadido a stopwords

**Fecha:** 2026-09-05 · Autorización de Capa 9: "precision-fix mínimo basado en evidencia
observada... empezando por `can` si corresponde". **No se tocan thresholds, fórmula/IDF ni
Composer.** No se añaden `must`/`may` (riesgo de significado regulatorio no descartado).

## Registro pre-modificación (evidencia)

```
token: "can"

FP concretos que provoca (3, todos DIAGNOSTIC_NEAR_THRESHOLD_15, mismo sub-criterio):
  rec-3369a8711e5f16a3  | 21_CFR_11.10(e)::sc9 | "The operator can acknowledge an alarm"
  rec-814e1e0e05380e78  | 21_CFR_11.10(e)::sc9 | "...input points can be simulated..."
  rec-850828e07185d641  | 21_CFR_11.10(e)::sc9 | "...request water delivery..."

requisitos afectados (dónde vive "can" en decomposition.yaml, df=3/84 sub-criterios):
  21_CFR_11.10(a)::sc5   "the system can discern invalid or altered records..."
  21_CFR_11.10(e)::sc9   "the audit trail can be exported or copied for inspection"
  21_CFR_211.68(b)::sc1  "...who can change master production and control records"

riesgo de eliminar señal válida: BAJO/NULO -- en las 3 ubicaciones "can" es un verbo modal
  auxiliar puro; el contenido discriminante real vive en otras palabras ("discern/invalid/
  altered/records", "exported/copied/inspection", "restricts/change/master/production/
  records"). Ningún caso donde "can" sea el ancla semántica del sub-criterio.

Otros tokens en los FP confirmados (printed, access/control, person/point, archiving/data) --
  NO calificaron: son palabras de contenido específicas (df bajo, semánticamente centrales),
  eliminarlas arriesgaría destruir señal válida.
```

## Cambio aplicado

`factory/regulatory/shadow/relevance_model.py::_BASIC_STOPWORDS` -- 1 token añadido (`"can"`).
Ninguna otra línea de la fórmula, del IDF local ni de los umbrales (`_RELEVANT_MIN_RATIO`,
`_PARTIAL_MIN_RATIO`, `_RELEVANT_MIN_MATCHED`, `_PARTIAL_MIN_MATCHED`) se tocó -- verificado en
test (`TestThresholdsAndFormulaUntouched`).

## Remedición sobre las 3 particiones reales (metodología corregida)

**Nota de proceso**: la primera remedición usó por error `matched_subcriterion_id` almacenado en
los pools (a veces `None` por una particularidad de cómo `classify()` reporta el mejor
sub-criterio cuando el único evaluado, vía `rationale_l2`, da `ratio=0`/`n_matched=0` -- el valor
inicial `best=(0.0,0,...,None)` nunca se actualiza en ese caso). Usar ese `None` disparaba modo
agregado (contra los 8 sub-criterios) en vez de repetir el sub-criterio realmente targeteado por
el pipeline original, produciendo 2 falsos "nuevos FP" que NO eran un efecto real del fix.
Corregido: la remedición usa `relevance_model.classify_entry()` sobre las entradas reales
(mismo camino que el pipeline de producción), no `classify()` con un `subcriterion_id` inferido
del pool.

| Partición | FP antes→después | FN antes→después | recall antes→después | specificity antes→después |
|---|---|---|---|---|
| `ORIGINAL_27` | 1→1 | 2→2 | 0.0→0.0 | 0.960→0.960 |
| `DIAGNOSTIC_NEAR_THRESHOLD_15` | 5→2 | 0→0 | 1.0→1.0 | 0.643→0.857 |
| `RANDOM_STRATIFIED_40` | 1→1 | 2→2 | 0.333→0.333 | 0.973→0.973 |

**Cambios exactos** (los 3 predichos, ninguno más): `rec-3369a8711e5f16a3`,
`rec-814e1e0e05380e78`, `rec-850828e07185d641` — los 3 pasan de `PARTIALLY_RELEVANT` a
`IRRELEVANT`, coincidiendo con `human_label=IRRELEVANT` en los 3 (de FP a TN). Ningún otro
candidato de las 3 particiones cambió de estado.

## Verificación de los criterios de aceptación

```
FP no aumentan          ✓  (bajan en DIAGNOSTIC_15: 5→2; iguales en ORIGINAL_27 y RANDOM_STRATIFIED_40)
FN no aumentan          ✓  (idénticos en las 3: 2, 0, 2)
recall no empeora       ✓  (idéntico en las 3: 0.0, 1.0, 0.333)
specificity mejora/mant ✓  (mejora en DIAGNOSTIC_15: 0.643→0.857; igual en las otras 2)
```

**Los 4 criterios se cumplen. No se revierte.**

## Invariantes

`LLM_CALLS=0` · thresholds/IDF/fórmula sin cambio · `decomposition.yaml` sin escrituras ·
Composer sin tocar · `301 passed -k shadow` (1 failed pre-existente no relacionado, sin cambio) ·
10 tests nuevos (`test_shadow_relevance_model_precision_fix.py`).

## STOP

Precision-fix aplicado y verificado. El problema de recall (2 FN en `ORIGINAL_27`, 2 FN en
`RANDOM_STRATIFIED_40`, en 3 requisitos distintos) **permanece sin cambio** -- este fix nunca
pretendió atacarlo, y no lo hizo. Decisión pendiente de Capa 9: camino de remediación para el
recall (recalibración ya descartada por evidencia; `fusion`/R3 sigue siendo la vía
técnicamente indicada, no autorizada todavía).
