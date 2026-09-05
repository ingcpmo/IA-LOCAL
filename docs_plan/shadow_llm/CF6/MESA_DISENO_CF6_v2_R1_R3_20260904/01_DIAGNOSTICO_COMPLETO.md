# CF-6 v2.0 · R1–R3 — Diagnóstico técnico completo (para la mesa de diseño)

Este documento analiza causa raíz de cada hallazgo del arco R1–R2 (R3 no se ejecutó). No
propone soluciones definitivas — identifica el mecanismo exacto de cada defecto/limitación con
evidencia reproducible, para que la mesa de diseño decida el camino con datos, no con
intuición. Ningún umbral, prompt firmado ni código de gobernanza se modificó al escribir este
diagnóstico.

---

## 1 · `evidence_relevance_accuracy = 0.0 / 0.0` — el hallazgo central

### Los hechos, sin interpretación

Sobre 27 pares requisito×evidencia adjudicados por Capa 9:

```
TP = 0   FP = 1   FN = 2   TN = 24
precisión = 0/1 = 0.0   recall = 0/2 = 0.0
```

- **El único falso positivo** (`rec-5bfe094286d91b6d`, sec-0016, sub-criterio sc1 de
  `21_CFR_11.10(d)`, "*The system shall implement the security and access control*"): el
  Relevance Model lo clasificó `PARTIALLY_RELEVANT` (ratio ponderado 0.1231, 2 términos:
  `access`, `control`) y por eso fue la ÚNICA evidencia que llegó al Composer — es decir, **la
  única sección que se renderizó en toda la corrida se sostiene sobre el único candidato que
  Capa 9 adjudicó como NO relevante.**
- **Los dos falsos negativos** (sec-0005, `21_CFR_11.50_11.70`, mismo texto citado 3 veces para
  3 sub-criterios distintos — "*With the FactoryTalk View SE electronic signature feature, each
  entry into the FactoryTalk View...*"): sc1 (ratio 0.0909, 3 términos) y sc2 (ratio 0.0811, 3
  términos) quedaron `INCONCLUSIVE`, bajo el umbral `PARTIALLY_RELEVANT≥0.12`. El tercer caso
  (sc6, ratio 0.033, 1 término) no fue adjudicado como falso negativo por Capa 9 (quedó
  `INCONCLUSIVE` en ambos lados).

### Mecanismo exacto (por qué el clasificador se equivocó en ambas direcciones)

`relevance_model.py::_local_idf()` calcula el peso de cada término como `1 / (número de
sub-criterios del MISMO requisito que contienen ese término)`. Esto es correcto en principio
(evita que "process"/"account" —genéricos dentro de un requisito— dominen el ratio), pero tiene
un efecto secundario no anticipado: **penaliza también términos de alto valor semántico cuando
el requisito tiene muchos sub-criterios largos**.

- `21_CFR_11.10(d)` (sec-0016, FALSO POSITIVO): 8 sub-criterios. Los términos `access`/`control`
  aparecen en pocos de los 8 → peso alto → un candidato con solo 2 términos matched cruza el
  umbral parcial (0.12) con ratio 0.1231. El candidato "pasa" con muy poca señal real —
  cualquier mención genérica de "access control" en el documento tiene buena probabilidad de
  cruzar el umbral para ESTE requisito específico.
- `21_CFR_11.50_11.70` (sec-0005, FALSOS NEGATIVOS): 7 sub-criterios, cada uno una oración
  larga y específica ("*cada firma electrónica muestra...*"). El término `signature` (compartido
  por varios sub-criterios de la MISMA firma electrónica) recibe peso bajo (~0.167) precisamente
  PORQUE es el término más central del requisito completo — el IDF local castiga la palabra que
  más debería contar. El candidato tiene 3 términos matched (`each`, `electronic`, `signature`)
  pero el denominador (suma ponderada de TODOS los términos del sub-criterio, que incluye
  palabras únicas de bajo valor como "printed"/"name"/"signer") es grande, así que el ratio
  (0.081-0.091) queda bajo el umbral aunque la cobertura semántica real sea alta.

**Conclusión de mecanismo**: el IDF local, calculado sobre el número de sub-criterios de un
requisito, no es un proxy estable para "qué tan distintivo es este término" cuando el número y
la longitud de los sub-criterios varía mucho entre requisitos (8 sub-criterios cortos vs. 7
sub-criterios largos). El umbral fijo (0.12/0.30) fue calibrado contra 2 casos de `sec-0016`
únicamente (el caso confirmado que motivó R1) — nunca se validó contra un requisito con
sub-criterios largos como `21_CFR_11.50_11.70`.

### Lo que esto NO significa

No significa que el enfoque (Relevance Model determinista, IDF local, sin lista de stopwords a
mano) esté mal concebido — el mecanismo SÍ resolvió el caso para el que se diseñó (`sec-0016`
original) y sigue siendo determinista, trazable y auditable, exactamente como exige el diseño.
Significa que **calibrarlo con n=2 casos confirmados y proyectarlo a 20 requisitos distintos sin
una muestra representativa fue prematuro** — exactamente el mismo patrón de error que el
proyecto ya había aprendido a evitar con el recall del modelo LLM (ver `gmp-recall-pipeline`:
nunca productizar una configuración medida en un solo caso sin revalidarla).

---

## 2 · Cobertura real: 1 de 7 secciones renderizadas

### Los hechos

De 7 secciones de la muestra congelada: 2 fuera de alcance (sin `decomposition.yaml`), 5
elegibles. De esas 5: **4 quedaron con `relevant_evidence[]` vacío** (cayeron a `SAFE_MODE`
fail-closed sin invocar el LLM) y solo 1 (`sec-0016`) tuvo al menos un candidato sobre el
umbral.

### Mecanismo

Es consecuencia directa del §1: el umbral (`_PARTIAL_MIN_RATIO=0.12`, `_RELEVANT_MIN_RATIO=
0.30`, `_RELEVANT_MIN_MATCHED=2`, `_PARTIAL_MIN_MATCHED=1`) resultó, en la práctica, casi
imposible de cruzar para los candidatos reales de `sec-0004`/`sec-0005`/`sec-0018`/`sec-0062` —
el candidato con MAYOR señal en cada una de esas 4 secciones (ratios entre 0.045 y 0.091, ver
tabla completa en `03_ARTEFACTOS_R2_EJECUCION/CF6_v2_R2_HUMAN_QUALITY_GATE.md` §4) quedó
sistemáticamente por debajo de 0.12. Esto sugiere que el umbral 0.12, calibrado sobre 2 puntos
de datos, es demasiado alto para la distribución real de ratios de candidatos genuinamente
recuperados por BM25 — no es evidencia de que esas 4 secciones realmente carecieran de
evidencia pertinente (3 de los candidatos con mayor ratio de esas 4 secciones tratan
literalmente de niveles de acceso/seguridad, el mismo dominio semántico que sus requisitos
`21_CFR_11.10(g)`).

### Comparación con la línea base (v3)

v3 (sin Relevance Model, sin filtro previo) rindió 6/7 (la séptima, `sec-0062`, ya caía a
`SAFE_MODE` por una razón distinta — duplicación de citas). El filtro de R1 pasó de "0 filtro,
6 RENDERED con ruido conocido" a "filtro agresivo, 1 RENDERED sin ruido conocido, pero con
recall aparentemente muy bajo sobre evidencia real". Es el trade-off exacto que el diseño (§14)
anticipó medir, no un error de ejecución — pero la magnitud (83% de las secciones elegibles sin
ningún candidato utilizable) es mayor de lo que cualquier discusión previa había estimado.

---

## 3 · Rúbrica de `sec-0016`: 3/5 en las 5 dimensiones humanas

### Los hechos

`requirement_interpretation_accuracy`, `gmp_assessment_accuracy`, `professional_clarity`,
`audit_utility/value_added`, `cognitive_load_reduction` — las 5 puntuadas uniformemente 3/5 por
Capa 9. Umbral heredado sin cambio: ≥4/5 por dimensión. Las 5 fallan por 1 punto exacto.

### Lo que se puede decir con los datos disponibles (n=1 narrativa)

La salida real de `sec-0016` (ver `03_ARTEFACTOS_R2_EJECUCION/CF6_v2_R2_B_OUTPUTS.jsonl`):

```
observed_system_capability: "No se ha identificado un mecanismo de control de acceso al
  sistema (propio o federado) en la evidencia entregada."
technical_assessment: "El sistema requiere un mecanismo de control de acceso, pero no se ha
  proporcionado evidencia de su implementación."
procedural_responsibility: "El usuario regulado debe definir y documentar el proceso de alta
  de cuentas, cambio de privilegios, revocación de cuentas, y la gestión de cuentas humanas e
  interactivas."
gap_or_open_question: "Se debe verificar si el sistema tiene un mecanismo de control de acceso
  y si este se ha implementado según lo especificado en la sección 3.4.1 del documento."
```

Un patrón visible sin necesidad de rúbrica: `procedural_responsibility` afirma cosas ("alta de
cuentas", "cambio de privilegios", "revocación de cuentas") que **no están en la única evidencia
que el modelo recibió** (`evidence_basis` tiene 1 sola entrada, sobre control de acceso — nada
sobre alta/cambio/revocación de cuentas). Esto no violó Q-STATE (no es una conclusión de
cumplimiento/incumplimiento prohibida, es una elaboración plausible pero no anclada), pero es
exactamente el tipo de "hecho nuevo no sustentado por el input" que la rúbrica humana sí
penaliza y que el validador estructural actual no detecta (`validate_structure_contract` escanea
compliance/CAPA/páginas, no invención de contenido no anclado en campos de texto libre distintos
de `evidence_basis`).

**Hipótesis para la mesa de diseño, no confirmada**: el 3/5 uniforme (mismo puntaje en las 5
dimensiones) puede deberse más a este patrón de "elaboración plausible sin anclaje" en
`procedural_responsibility`/`technical_assessment` que a un problema de claridad o utilidad per
se — pero con n=1 narrativa no se puede distinguir una causa de la otra.

---

## 4 · Error propio en el gate de scope (token `"CF6-3"`)

### Los hechos

`cf6_scope_addendum_v2_r1.py` (primer ADDENDUM) usó `execution_phase: "CF6-v2-R5"` y
`selection_reason` con "corrida completa bajo la arquitectura R1-R3 (diseño §13, R5)" — el
chequeo `c_cf6_3` de `cf6_pilot_scope.py` (heredado de v1.2/v1.3, sin modificar) busca
literalmente `"CF6-3"` / `"cf6_3"` / `"corrida completa cf6"` / `"full cf6"`. Ninguno apareció.
`GATE_RESULT=FAIL` en la primera pasada (`CF6_v2_R2_GATE_RECHECK.md`).

### Causa raíz

Terminología de fases inconsistente entre el diseño v2.0 (que usa `R1`/`R2`/`R3`/`R4`/`R5`
como nombres de fase) y el gate mecánico heredado de v1.2/v1.3 (que espera literalmente
`"CF6-3"` como token de scope, un artefacto de la nomenclatura ANTERIOR). Nadie reconcilió
explícitamente ambos vocabularios antes de redactar el primer ADDENDUM — es un defecto de
comunicación entre el diseño nuevo y una herramienta de verificación vieja que nunca se
actualizó para entender la nomenclatura nueva.

### Costo real

2 rondas adicionales de propose→confirm en el ledger (`-041/-042` insuficiente, `-043/-044`
correctivo) — gobernanza real, trazable, sin coste de seguridad, pero evitable si el gate
mecánico se hubiera revisado ANTES de redactar el primer ADDENDUM, o si el vocabulario de fases
del diseño v2.0 se hubiera mapeado explícitamente a los tokens que el gate heredado reconoce.

---

## 5 · Defecto de integridad de artefactos (dry-run sobrescribió la corrida real)

### Los hechos

`cf6_r2_runner.run_r2()` tenía `out_dir` con un único valor por defecto
(`"docs_plan/shadow_llm/CF6"`), usado tanto para corridas reales como para `dry_run=True`. Tras
ejecutar la corrida real (1 llamada LLM, `sec-0016` RENDERED), se escribió
`test_shadow_cf6_r2_runner.py`, que invoca `run_r2(dry_run=True)` dos veces SIN especificar
`out_dir` — cada invocación sobrescribió `CF6_v2_R2_RUN.json`/`CF6_v2_R2_B_OUTPUTS.jsonl` con la
versión sin LLM (`sec-0016` en `SAFE_MODE`, 0 llamadas). El primer reporte de R2.2 entregado a
Capa 9 citó, por unos minutos, datos de la corrida real leídos de la conversación (correctos)
pero los archivos COMITEADOS en `216a280` eran la versión dry-run (incorrectos) — descubierto
al re-leer el archivo en la siguiente sesión de reconciliación.

### Causa raíz

Ausencia de aislamiento de rutas de salida entre modo de prueba y modo de producción en un
módulo que escribe a disco — un patrón de riesgo genérico de ingeniería de software (no
específico de LLM/GMP), pero con consecuencia regulatoria real en este contexto: el primer
conjunto de "evidencia" presentado como resultado de una corrida real no lo era.

### Remediación aplicada (commit `76ab815`)

`out_dir=None` por defecto → selección automática según `dry_run` (`_REAL_OUT_DIR` vs.
`_DRY_RUN_OUT_DIR`, nunca la misma ruta); tests además pasan `out_dir=tmp_path` explícito (doble
capa). Verificado con test dedicado (`test_dry_run_never_writes_to_real_output_dir`) y
re-ejecución completa de la corrida real preservada intacta tras correr toda la suite.

**Pregunta abierta para la mesa de diseño**: ¿existen otros módulos de este arco (o de arcos
anteriores, CF6-1/1.2/1.3) con el mismo patrón de riesgo (ruta de salida compartida entre test y
producción)? No se auditó exhaustivamente fuera de `cf6_r2_runner.py` en esta ronda.

---

## 6 · Patrones transversales, para la discusión de la mesa de diseño

1. **Todo lo que falló, falló de forma segura.** Ningún hallazgo de este documento representa
   una violación de SAFETY/GOVERNANCE — los 5 son defectos de PRECISIÓN/CALIDAD/PROCESO, nunca
   de fabricación, cumplimiento indebido o fuga de gobernanza. El diseño de defensa en
   profundidad (Q-STATE, blacklist, fail-closed, ledger append-only) se sostuvo bajo estrés real
   en las 5 situaciones.
2. **Todos los defectos de calibración (§1, §2) comparten la misma causa de fondo: decisiones de
   threshold tomadas con 1-2 casos de datos, nunca con una muestra representativa.** Esto no es
   un error de ejecución de esta sesión — es una limitación estructural de cómo se autorizó R1
   (el diseño mismo, §4, ya anticipaba que la calibración necesitaría "un conjunto etiquetado
   por humano" que nunca se construyó antes de ejecutar R2 sobre las 7 secciones reales).
3. **El error de vocabulario (§4) y el defecto de integridad (§5) son ambos, en esencia, fallos
   de comunicación entre partes del sistema que evolucionaron en momentos distintos** (gate
   heredado vs. diseño nuevo; módulo de producción vs. módulo de test) — ninguno tiene relación
   con el Relevance Model, el LLM o la gobernanza regulatoria en sí.
4. **La pregunta que la mesa de diseño necesita resolver no es "¿el Relevance Model funciona?"
   sino "¿con qué tamaño y composición de muestra etiquetada se puede calibrar un clasificador
   de relevancia determinista de forma defendible?"** — 27 pares con solo 3 casos de
   discrepancia no alcanza. R4 (diseño §12) es, literalmente, la respuesta ya prevista a esta
   pregunta; no ejecutarlo todavía fue la decisión correcta de esta sesión, no una omisión.
