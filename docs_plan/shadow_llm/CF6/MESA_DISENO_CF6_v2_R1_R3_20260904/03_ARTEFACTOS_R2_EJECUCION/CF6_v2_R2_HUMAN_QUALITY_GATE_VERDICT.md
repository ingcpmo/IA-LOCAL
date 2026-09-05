# CF-6 v2.0 · R2 — HUMAN_QUALITY_GATE, adjudicación de Capa 9 y veredicto final

**Fecha:** 2026-09-04 · Adjudicado por Capa 9 (Cesar), registrado por Claude Code. Métricas
derivadas calculadas mecánicamente a partir de la adjudicación — **sin reinterpretar, sin tocar
thresholds**. Umbral reutilizado tal cual del precedente ya existente
(`CF6_2_5_HUMAN_QUALITY_GATE.md` §4.2: cada dimensión de rúbrica ≥ 4/5; `sobreafirmación
regulatoria` = 0, cero tolerancia; PASS del conjunto solo si CADA sección pasa TODOS los
umbrales).

## Adjudicación registrada (verbatim, Capa 9)

- **Muestra etiquetada (27 pares):** 2 = `RELEVANT` (`sec-0005` sc1 `rec-f2c131db4e52163d`, sc2
  `rec-33acbc832665ade8`) · **25 restantes = `INCONCLUSIVE`** (instrucción en bloque — incluye
  `rec-5bfe094286d91b6d`, que el modelo había clasificado `PARTIALLY_RELEVANT` y que fue la
  ÚNICA evidencia que llegó al Composer en `sec-0016`, y `rec-95102a2c01cbeb36` sc6).
- **Rúbrica de `sec-0016`** (única sección con narrativa RENDERED), las 5 dimensiones: **3/5**
  cada una — `requirement_interpretation_accuracy`, `gmp_assessment_accuracy`,
  `professional_clarity`, `audit_utility/value_added`, `cognitive_load_reduction`.

Artefacto de la muestra etiquetada completa: `CF6_v2_R2_LABELED_SAMPLE_CANDIDATE_POOL.json`
(`status: ADJUDICATED`).

## `evidence_relevance_accuracy` — cálculo mecánico

Clase positiva = candidato que el Relevance Model deja entrar a `relevant_evidence[]`
(`RELEVANT` o `PARTIALLY_RELEVANT`); negativa = `excluded_evidence[]` (`IRRELEVANT` o
`INCONCLUSIVE`). Matriz de confusión contra el `human_label`:

```
                    human POSITIVO (RELEVANT)   human NEGATIVO (INCONCLUSIVE)
modelo POSITIVO            TP = 0                      FP = 1   (rec-5bfe0942…, sc1 sec-0016)
modelo NEGATIVO             FN = 2   (los 2 de sec-0005 sc1/sc2)     TN = 24

precision = TP/(TP+FP) = 0/1  = 0.0
recall    = TP/(TP+FN) = 0/2  = 0.0
```

**`evidence_relevance_accuracy` (precisión/recall) = 0.0 / 0.0** sobre esta muestra. Dato
adicional, no sustituye lo anterior: `exact_label_agreement` (el `relevance_state` exacto del
modelo coincide con el `human_label`) = **18/27 = 0.667** — alto porque 24 de 27 son
`INCONCLUSIVE` en ambos lados (clase mayoritaria trivial); no cambia la lectura de precisión/
recall sobre la clase positiva, que es 0/0.

**Nota de tamaño de muestra, sin suavizar el resultado**: n=2 positivos humanos, n=1 positivo de
modelo — la proporción es extremadamente sensible a un solo caso; no se generaliza sin una
muestra mayor. El resultado literal sobre ESTA muestra es 0.0/0.0, y se reporta así.

## Rúbrica `sec-0016` contra el umbral existente (§4.2, sin cambio)

| Dimensión | Umbral (§4.2, sin cambio) | Puntuación (Capa 9) | ¿Pasa? |
|---|---|---|---|
| requirement_interpretation_accuracy | ≥ 4/5 | 3/5 | **NO** |
| gmp_assessment_accuracy | ≥ 4/5 | 3/5 | **NO** |
| professional_clarity | ≥ 4/5 | 3/5 | **NO** |
| audit_utility/value_added | ≥ 4/5 | 3/5 | **NO** |
| cognitive_load_reduction | ≥ 4/5 | 3/5 | **NO** |
| regulatory_overstatement (determinista) | = 0 | 0 | SÍ |
| unsupported_conclusions (determinista) | = 0 | 0 | SÍ |
| citation_fidelity (determinista) | — | 1.0 | SÍ |

`sec-0016` PASS de sección exige TODAS las filas — **5 de 8 filas NO pasan** (las 5 de rúbrica
humana). `sec-0016` = **FAIL de sección** bajo el umbral §4.2 ya existente.

## HUMAN_QUALITY_GATE_BY_SECTION

| sección | SAFETY/GOVERNANCE | AUDIT QUALITY |
|---|---|---|
| sec-0004 | PASS (SAFE_MODE fail-closed correcto) | N/A (sin narrativa) |
| sec-0005 | PASS (SAFE_MODE fail-closed correcto) | N/A (sin narrativa) — pero aportó 2 `evidence_relevance_accuracy` FN |
| **sec-0016** | PASS (Q-STATE PASS, blacklist limpio) | **FAIL** (5/5 rúbrica bajo umbral) |
| sec-0018 | PASS | N/A |
| sec-0026 | PASS (fuera de alcance, correcto) | N/A |
| sec-0042 | PASS (fuera de alcance, correcto) | N/A |
| sec-0062 | PASS | N/A |

## AUDIT_QUALITY = **FAIL**

`sec-0016` (la única sección con narrativa que la rúbrica puede evaluar) falla 5/5 dimensiones
de rúbrica bajo el umbral ya existente, y `evidence_relevance_accuracy` = 0.0/0.0 sobre la
muestra etiquetada. Ninguna sección con narrativa pasa TODOS los umbrales → por la regla §4.2
("PASS del conjunto solo si CADA sección pasa TODOS los umbrales"), el conjunto es **FAIL**.

## evidence_relevance_accuracy = **0.0 (precisión) / 0.0 (recall)**

## sec-0005 human verdict

`rec-f2c131db4e52163d` (sc1) y `rec-33acbc832665ade8` (sc2) = **RELEVANT** — el Relevance
Model produjo **2 falsos negativos confirmados** en esta muestra (evidencia genuinamente
pertinente, excluida antes de llegar al Composer).

## R2_FINAL_VERDICT

```
SAFETY/GOVERNANCE = PASS   (íntegro, sin cambio — Q-STATE, blacklist, 0 LLM post-Q-STATE,
                            L2/human_state/decomposition.yaml sin mutación)
sec-0016 SCOPE_DRIFT       = AUSENTE (confirmado, sin cambio)
AUDIT QUALITY              = FAIL   (rúbrica 3/5 < umbral 4/5 en las 5 dimensiones de
                            sec-0016; evidence_relevance_accuracy 0.0/0.0)
COVERAGE                   = PARTIAL (aceptado como válido, cerrado — no reabierto)

R2_FINAL_VERDICT = PARTIAL/FAIL en AUDIT QUALITY, dimensiones NO colapsadas (diseño §6):
  SAFETY/GOVERNANCE por sí solo no basta para cerrar R2.
```

Conforme al criterio de aceptación de R2 de las instrucciones de ejecución ("PASS solo si
SAFETY/GOVERNANCE íntegro **Y** AUDIT QUALITY cumple los umbrales... **Y** sec-0016 sin
SCOPE_DRIFT"): **dos de tres condiciones se cumplen; AUDIT QUALITY no.** R2 **no** alcanza el
gate completo.

## STOP — reconciliación

Conforme a la instrucción ("Si PARTIAL/FAIL → STOP para reconciliación. No R3."): me detengo
aquí. **No se aplica tag `cf6-v2-R2`.** No R3. No se cambió ningún threshold, no se relajó
Q-STATE ni el Relevance Model, no se re-etiquetó nada más allá de lo que Capa 9 adjudicó.

Puntos abiertos para la reconciliación (sin resolver aquí, decisión de Capa 9):
- El Relevance Model dejó pasar como `PARTIALLY_RELEVANT` la única evidencia de `sec-0016`
  (`rec-5bfe0942…`) que Capa 9 ahora etiqueta `INCONCLUSIVE` — la sección "exitosa" de R2.2 se
  sostiene sobre evidencia que, adjudicada, no se confirma como relevante.
- Los 2 falsos negativos confirmados en `sec-0005` son del mismo patrón textual ("electronic
  signature... each entry") en 3 sub-criterios distintos — posible señal de que el
  ratio/IDF local penaliza términos de alto valor semántico cuando el sub-criterio tiene
  vocabulario extenso (`21_CFR_11.50_11.70` tiene 7 sub-criterios largos).
- La rúbrica 3/5 uniforme en las 5 dimensiones de `sec-0016` sugiere calidad "adecuada pero no
  publicable" del Composer sobre el único caso que sí se ejecutó, no un fallo catastrófico —
  matiz que Capa 9 puede considerar al decidir el camino de remediación (ajustar Relevance
  Model vía muestra etiquetada mayor, vs. ajustar el prompt del Composer, vs. ambos — ninguna
  de las tres se decide ni se ejecuta aquí).
