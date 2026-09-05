# CF-6 v2.0 · R4 — Informe comparativo: ORIGINAL_27 / DIAGNOSTIC_15 / RANDOM_STRATIFIED_40

**Fecha:** 2026-09-05 · Adjudicación humana de Capa 9 sobre las tres particiones de
`REAL_ADJUDICATED`. **0 llamadas LLM. `relevance_model.py`, thresholds, IDF/fórmula y Composer
sin modificar.**

## Las tres particiones, separadas (nunca mezcladas en una sola métrica)

| Partición | Cómo se seleccionó | n | TP | FP | FN | TN | precision | recall | specificity | FPR | exact_agreement |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ORIGINAL_27` | 7 secciones de la muestra congelada de R2 (`SAMPLE_MANIFEST`) | 27 | 0 | 1 | 2 | 24 | 0.0 | 0.0 | 0.960 | 0.040 | — |
| `DIAGNOSTIC_NEAR_THRESHOLD_15` | Los 15 candidatos más cercanos al umbral 0.12 (no representativo, no aleatorio) | 15 | 1 | 5 | 0 | 9 | 0.167 | 1.0 | 0.643 | 0.357 | 0.267 |
| `RANDOM_STRATIFIED_40` | Aleatorio, estratificado por `requirement_id` (semilla 20260905), único representativo | 40 | 1 | 1 | 2 | 36 | 0.50 | 0.333 | 0.973 | 0.027 | 0.375 |

## Lectura, sin recalibrar nada

**`RANDOM_STRATIFIED_40` es la primera evidencia representativa** (no seleccionada por
cercanía al umbral, no limitada a 2 requisitos) de que el problema de recall observado en
`sec-0005` **no es un caso aislado**:

- **2 falsos negativos**, en **dos requisitos distintos** a los de `ORIGINAL_27`
  (`ANNEX11_9`, `21_CFR_11.10(g)`) — el modelo dijo `IRRELEVANT`, Capa 9 confirmó `RELEVANT`.
  Ninguno comparte requisito con los 2 FN de `sec-0005` (`21_CFR_11.50_11.70`). El patrón
  generaliza a través del corpus, no es específico de un requisito o documento.
- **1 falso positivo** (`ANNEX11_17`) — mucho menos frecuente que en `DIAGNOSTIC_15` (donde 5/15
  eran FP), consistente con que `DIAGNOSTIC_15` estaba deliberadamente sesgada hacia el ruido
  cerca del umbral (no una muestra para estimar tasas globales, tal como se instruyó desde el
  principio).
- **`DIAGNOSTIC_15` sigue sin mostrar ningún FN** — confirma que su valor fue diagnosticar el
  problema de PRECISIÓN (palabras genéricas como "can"), no el de recall; el de recall solo
  aparece en una muestra verdaderamente aleatoria.

## Comparación de recall entre particiones — la señal más fuerte hasta ahora

```
ORIGINAL_27            recall = 0.0    (n=2 positivos -- ruido estadístico extremo)
RANDOM_STRATIFIED_40    recall = 0.333  (n=3 positivos -- primera estimación con algo más
                                        de base, aunque todavía pequeña)
```

Con solo 3 positivos reales confirmados en la muestra aleatoria, `recall=0.333` **tampoco es
una estimación estable** — pero la dirección (recall bajo, por debajo de cualquier umbral
razonable) se sostiene en dos muestras independientes construidas de forma distinta
(`ORIGINAL_27` por selección de sección; `RANDOM_STRATIFIED_40` por aleatorización real). Esto
es más fuerte que cualquier resultado del fixture sintético (v1 o v2), que nunca reprodujo un
solo FN real.

## Casos concretos para inspección (los 2 FN de RANDOM_STRATIFIED_40)

```
rec-8dd53df9991ab844 (ANNEX11_9): "UR3.3.1 Every time a critical alarm threshold is modified
  and audit trail record shall be generated." -- modelo IRRELEVANT, Capa 9: RELEVANT
rec-b9f11dd9d3963b94 (21_CFR_11.10(g)): "previously, with the proper credentials, the input
  points can be simulated for calibration or other" -- modelo IRRELEVANT, Capa 9: RELEVANT
```

Ninguno de los dos comparte vocabulario de superficie con el sub-criterio que Capa 9 confirma
que satisfacen (evaluado contra el conjunto agregado del requisito, sin `matched_subcriterion_id`
específico en ambos casos) -- el mismo patrón de fondo que `sec-0005`: contenido genuinamente
relevante, expresado sin ecoar el vocabulario gobernado.

## Invariantes

`LLM_CALLS=0` en toda la ronda de adjudicación · `relevance_model.py`/thresholds/IDF/Composer
sin tocar · `decomposition.yaml` sin escrituras · las tres particiones permanecen separadas en
sus artefactos propios (`CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json`,
`CF6_v2_R4_DIAGNOSTIC_15_ADJUDICATED.json`, `CF6_v2_R4_RANDOM_STRATIFIED_40.json` +
`CF6_v2_R4_RANDOM_STRATIFIED_40_RESULT.json`).

## STOP

No se recalibró nada. No se tocó el Composer. El total de pares reales adjudicados hasta ahora
es 27+15+40=82 (con solapamiento cero entre particiones) -- mayor que antes, pero `recall` sigue
estimado sobre pocos positivos (2 en `ORIGINAL_27`, 3 en `RANDOM_STRATIFIED_40`). Decisión
pendiente de Capa 9: si esta señal (recall bajo confirmado en muestra aleatoria, en 2 requisitos
adicionales) es suficiente para decidir el camino de remediación, o si hace falta seguir
ampliando antes de decidir entre recalibrar / evaluar `fusion` (R3) / ambos.
