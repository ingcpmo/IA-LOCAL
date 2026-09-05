# CF-6 v2.0 · R4 — Evaluación de embeddings en el Relevance Model (2026-09-05)

**Autorización de Capa 9:** "autoriza evaluar la integración de embeddings en el Relevance
Model" — respuesta directa al hallazgo de que 2 falsos negativos reales tienen
`ratio=0.0, n_matched=0` (cero solapamiento léxico), un techo que ningún ajuste de umbral
sobre el mecanismo actual puede cruzar.

**Gobernanza:** `EMBED_EXECUTION-2026-012` (propose) → `-013` (human_confirmed, Cesar, ACTIVE)
— familia separada de `PILOT_EXECUTION`, no la autoriza, no compite por su presupuesto. Modelo
`nomic-embed-text:latest` (Ollama local, 100% local, sin egress). **101 llamadas de embedding**
reales (56 citas únicas + 45 sub-criterios únicos), dentro del tope de 250. **Esto es medición,
no implementación** — `relevance_model.py` no se tocó, ningún threshold cambió, el Composer no
se tocó.

## Método

Sobre los **82 pares ya adjudicados por Capa 9** (`ORIGINAL_27` + `DIAGNOSTIC_NEAR_THRESHOLD_15`
+ `RANDOM_STRATIFIED_40`, sin re-etiquetar ninguno): para cada par, `embed_text()` de la cita y
del sub-criterio correspondiente, `cosine_similarity()` entre ambos vectores. Sin
`canonical_store` (vacío en este entorno) — embeddings ad hoc sobre texto ya extraído en L2 y en
`decomposition.yaml`.

## El resultado que motivó la evaluación — confirmado

```
rec-8dd53df9991ab844 (ANNEX11_9, RELEVANT):        ratio léxico=0.0  →  coseno=0.6749
rec-b9f11dd9d3963b94 (21_CFR_11.10(g), RELEVANT):  ratio léxico=0.0  →  coseno=0.4832
```

**Ambos casos donde el mecanismo léxico no tiene absolutamente ninguna señal (n_matched=0)
obtienen similitud de embeddings sustancialmente por encima de cero** — el primero
particularmente alto (0.67). Esto confirma la hipótesis: la información que el sub-criterio y
la cita comparten es semántica, no léxica, y los embeddings sí la capturan en al menos estos
2 casos concretos.

## Distribución global (las 82, sin partición CALIBRATION/HELDOUT -- exploratorio)

```
                    n    media    mín     máx     mediana
RELEVANT (+PARTIAL) 6    0.599    0.483   0.680   0.609
INCONCLUSIVE        42   0.548    0.447   0.714   0.531
IRRELEVANT          34   0.474    0.378   0.670   0.461
```

Hay separación de medias en la dirección esperada (RELEVANT > INCONCLUSIVE > IRRELEVANT), pero
**con solapamiento sustancial entre las tres distribuciones** (el máximo de `IRRELEVANT`,
0.670, cae dentro del rango de `RELEVANT`). No es una señal limpia por sí sola.

## Comparación directa, mismo conjunto de 82 pares

```
                          precisión   recall   TP   FP   FN   TN
Léxico (mecanismo actual)   0.222      0.333    2    7    4   69
Coseno solo (mejor F1,
  umbral no verificado
  en held-out)              0.429      0.500    3    4    3   72
```

**El coseno solo, con un umbral elegido sobre estos mismos 82 puntos (optimista, sin
partición de verificación), supera al mecanismo léxico actual en precisión y en recall
simultáneamente sobre este conjunto** — 1 verdadero positivo más, 3 falsos positivos menos, 1
falso negativo menos.

## Limitaciones, dichas sin suavizar

- **n=6 positivos totales** (`RELEVANT`+`PARTIALLY_RELEVANT`) en las 82 -- calcular un "mejor
  umbral" sobre exactamente los mismos 6 puntos que se usan para evaluarlo es optimista por
  construcción; no hay partición CALIBRATION/HELDOUT en esta evaluación (a diferencia del
  fixture sintético de R4, que sí la tenía). El resultado es una **señal, no una prueba**.
- El solapamiento entre distribuciones (IRRELEVANT llega a 0.670, dentro del rango RELEVANT)
  significa que un umbral único sobre coseno, igual que el léxico, tendría sus propios errores
  -- no es una solución sin fricción, es una señal **distinta y aparentemente complementaria**.
- No se probó combinar ambas señales (léxica + coseno) -- eso es diseño, no medición, y queda
  fuera de esta evaluación.

## Conclusión, sin proponer diseño

Los embeddings **sí capturan información que el mecanismo léxico actual no puede ver por
construcción** (los 2 casos de `ratio=0.0` lo demuestran directamente) y, en esta muestra
pequeña, una clasificación basada solo en coseno iguala o supera al mecanismo léxico actual en
ambas dimensiones. La limitación de tamaño de muestra (n=6 positivos) significa que esto es
evidencia a favor de investigar la integración, no una validación suficiente para diseñarla o
desplegarla. La decisión de cómo integrar esta señal (reemplazo, combinación con el léxico,
umbral separado, etc.) es de diseño y queda para quien defina esa arquitectura -- no se propone
aquí.

## Invariantes

`LLM_CALLS=0` (embeddings ≠ LLM de juicio, familia separada) · `relevance_model.py` sin
modificar · thresholds/IDF/fórmula sin cambio · Composer sin tocar · `decomposition.yaml` sin
escrituras · ledger append-only (+2 líneas, `EMBED_EXECUTION-2026-012/-013`) · 6 tests nuevos ·
`-k shadow`: 317 passed, 1 failed (misma falla pre-existente no relacionada).

## STOP

Evaluación entregada. No se implementó ninguna integración. No se modificó
`relevance_model.py`. Decisión pendiente de Capa 9: si autoriza diseñar (no solo evaluar) la
integración de esta señal, con qué mecanismo (combinación, reemplazo, umbral propio) y con qué
muestra de validación (la actual, n=6 positivos, es insuficiente para calibrar nada en
producción).
