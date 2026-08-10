# R2.1 §5 — Paquete de decisión: rumbo del RAQ reenfoque

**Fecha:** 2026-08-10. **Corrida:** análisis sin LLM (orden completa en
`docs_plan/R2_1_DECISION_RUMBO.md`). Cero llamadas de inferencia gastadas
en este documento. Presenta datos, no una recomendación sesgada — la
decisión de rumbo (Opción A/B/C) es de Cesar.

## 1. Estado real consolidado (verificado contra artefactos, no de memoria)

**1.1 Commits en HEAD** (`git log --oneline -5`):
```
f5a8034 docs(w5v2-r2.1): documenta resultado real de la re-medicion §4
d42d919 fix(w5v2-r2.1): corrige Causa 1 (kerning) y Causa 2 (contrato de prompt)
dddfbb2 feat(w5v2-r2): implementa y mide la fase de JUICIO de R2
```
`git status`: árbol limpio salvo lo esperado y no relacionado con R2.1 —
`factory/core/audit_writer.py`, `factory/tests/test_r1_8_review_queue_dispatch.py`
(preexistentes, otro tema) y `factory/regulatory/model_qualification/{qualification_record,runtime_calibration_record}.json`
(actualizados por la recalificación real de §4, sin commitear todavía —
ver nota en §6).

**1.2 Estado de causas** (sin cambios desde el cierre de §4):
- Causa 1 (kerning): **CORREGIDA + CONFIRMADA** — P1 `observed` con
  llamada LLM real.
- Causa 2 (contrato de prompt): **CORREGIDA**, efecto sobre P2 **sin
  confirmar** (no re-medido, faltó presupuesto).
- Causa 3 (límite del modelo): **RECONFIRMADA** con P6 — ver §2 para el
  refinamiento importante encontrado en esta corrida.
- `retrieval_recall_at_5=4/7`, `retrieval_recall_at_10=7/7` (sin cambios
  desde el commit de Causa 1).

**1.3 El bloqueador estructural — CORREGIDO respecto a la hipótesis de la orden.**

La orden R2.1 §1.3 asumía que `evidence_min_criteria` "nunca recibió
interpretación humana desde la Fase C de W5 V2". **Verificado contra el
catálogo real (`requirement_catalog/requirements.yaml`): FALSO.** Los 20
requirements del catálogo (incluidos los 19 del fixture + el usado en
calibración) tienen `evidence_min_criteria`/`exclusion_criteria`/
`governed_interpretation` completos — la interpretación humana de Fase C
**sí se hizo**. Lo que persiste en `PROVISIONAL` es el campo
`evidence_pack_status: human_drafted_provisional` (nunca promovido a un
estado "aprobado" — consistente con lo ya documentado: "cuando eso
exista, `evidence_pack_status` gana un nuevo valor, no definido todavía
en el schema a propósito").

**El bloqueador real es otro, más específico y más grave para el
objetivo del analizador**: `semantic_evidence_verification.verify_sufficiency()`
(línea 313) es **fail-closed todo-o-nada por chunk individual**: si
**cualquier** criterio de los N de `evidence_min_criteria` queda
`NOT_ASSESSABLE` en la respuesta de un chunk, el `d_sufficiency` de ESE
chunk completo cae a `NOT_ASSESSABLE` — sin importar cuántos otros
criterios sí se evaluaron con éxito. Además, `verify_evidence_abcd()` se
calcula **por chunk individual** (`chunked_engine.py` línea 1353), nunca
agregado entre los distintos chunks de una misma unidad — no existe
combinación de "criterio 2 confirmado en el chunk A + criterio 5
confirmado en el chunk B" en una sola conclusión.

Verificado con datos reales de P1 (`chunked-ff6bd88a4987`,
`task-ccb7ccec9223`): de 9 criterios de `21_CFR_11.10(e)`, el modelo
evaluó 2 `MET`, 2 `NOT_MET`, **5 `NOT_ASSESSABLE`** — porque el pasaje
real (página 46) simplemente no menciona control de acceso al audit
trail, retención, ni capacidad de exportación (esos criterios viven, si
existen, en OTRA parte del documento o no existen en absoluto). Con la
regla actual, `d_sufficiency=NOT_ASSESSABLE` es la salida casi
GARANTIZADA para cualquier requisito con ≥4-5 criterios mínimos
evaluado contra un solo pasaje real — que es la situación normal, no la
excepción, en documentación GMP real.

**Consecuencia**: aunque Causa 1/2/3 se corrigieran perfectamente y el
recall del modelo fuera 7/7, **casi ninguna conclusión llegaría a un
estado positivo consolidado** bajo el diseño actual de `verify_sufficiency`
— quedaría en `EVALUATION_INCOMPLETE`/`ABCD_D_NOT_ASSESSABLE` de forma
sistemática. Esto es un techo estructural, independiente del recall, y
potencialmente el cuello de botella de mayor impacto del roadmap. Ver
Opción C.

## 2. Triage de tipo de evidencia (cero LLM)

### 2.1 Los 7 positivos del fixture, por tipo real

| # | requirement_id | Doc/página real | Tipo (texto real, verificado) | ¿Reconocido en re-medición real? |
|---|---|---|---|---|
| P1 | `21_CFR_11.10(e)` | RW-0005 p.46 | **PROSE_STRUCTURED** — lista "UR3.3.1 ... shall ... 1. ... 2. ..." | **SÍ** — `observed` (Causa 1 confirmada) |
| P2 | `21_CFR_11.10(g)` | RW-0005 p.40 | **PROSE_NARRATIVE** — "F09.00 Physical Security... an operator's only access..." | No re-medido (sin presupuesto) |
| P3 | `ANNEX11_17` | RW-0005 p.45 (1-idx) | **PROSE_STRUCTURED** — mismo estilo UR-numerado que P1 | No re-medido (excluido del batch de juicio por diseño — su página entra al top-10 tras el fix, rank 9, pero no fue parte de las 2 unidades re-medidas en §4) |
| P4 | `ALCOA_ATTRIBUTABLE` | RW-0011 p.13 | **PROSE_NARRATIVE**, mismo pasaje que P6 (ver 2.2) | No re-medido directamente |
| P5 | `ALCOA_CONTEMPORANEOUS` | RW-0005 p.46 | **PROSE_STRUCTURED**, literalmente el MISMO pasaje que P1 | No re-medido directamente, pero comparte chunk/artefacto con P1 — inferencia estructural fuerte (no medida) de que se rescataría igual |
| P6 | `21_CFR_211.68(b)` | RW-0011 p.13 | **MIXED** — ver 2.2, hallazgo nuevo de esta corrida | **NO** — sigue `not_observed_in_chunk` tras corregir Causa 1/2 |
| P7 | `21_CFR_211.68(b)` | RW-0012 p.14 | **MIXED**, mismo patrón que P6 ("pasaje casi idéntico") | No re-medido directamente |

### 2.2 Hallazgo nuevo, no contemplado en la orden: P6/P7 no son "evidencia tabular" en sí — son prosa diluida por chunking multipágina

Leído el texto real completo de la página 13 (RW-0011) y 14 (RW-0012)
—no solo el candidato BM25 recuperado, la página fuente completa—: **el
pasaje real que sustenta P4/P6/P7 es una oración de prosa clara**:

> "As mentioned previously, with the proper credentials, the input
> points can be simulated for calibration or other maintenance
> activities."

Esa página (2500 caracteres) es mayormente prosa (secciones "4.3
Tasks/Routines", "4.4 Operator Interface") — solo tiene UNA tabla
pequeña (2 filas, "Table 4-8") al inicio. **El candidato que
`retrieve_top_k` realmente entrega al modelo no es esta página sola**:
es un chunk que agrupa varias páginas consecutivas (12-14), y las
páginas vecinas (especialmente la 12) sí son densamente tabulares
(listados largos de I/O). El modelo recibe la oración real de prosa
**enterrada dentro de un chunk mayormente tabular por construcción del
chunking**, no porque la evidencia en sí sea tabular.

**Esto abre una hipótesis alternativa a "Causa 3 = el modelo no
entiende tablas"**: podría ser, en cambio, "el chunking multipágina
diluye una oración de prosa corta dentro de un chunk dominado por
contenido no relacionado" — un problema de **granularidad de chunking**,
no de comprensión del modelo. **No confirmado** (requeriría una
re-medición con un candidato acotado a una sola página, gastando más
inferencia) — se deja como hallazgo abierto, no como hecho. Si se
confirmara, cambiaría sustancialmente el peso de la Opción A frente a
la B (un fix de chunking es mucho más barato que cambiar de modelo).

### 2.3 Distribución de tipo de evidencia en el corpus completo (muestreo determinista, heurística)

**Método**: clasificación página por página (86 páginas, las 3
documentos completos, no una submuestra) con una heurística
determinista sin LLM: `TABULAR_DENSE` si la página tiene un marcador
"Table N-M:" o ≥15% de líneas con patrón de tag tipo `XX-00000`;
`TABULAR_LIKELY` si >60% de líneas son cortas (<60 caracteres) sin
marcador de tabla; `PROSE` en el resto.

```
RW-0005 (58 pág.): PROSE=21, TABULAR_LIKELY=7, TABULAR_DENSE=30
RW-0011 (14 pág.): PROSE=3,  TABULAR_LIKELY=3, TABULAR_DENSE=8
RW-0012 (14 pág.): PROSE=3,  TABULAR_LIKELY=3, TABULAR_DENSE=8

TOTAL (86 páginas): PROSE=27 (31%), TABULAR_LIKELY=13 (15%), TABULAR_DENSE=46 (53%)
```

**Incertidumbre real de esta heurística, declarada sin maquillar**:
validada contra las 4 páginas ya conocidas del fixture (p.45/46 de
RW-0005, p.13 de RW-0011, p.14 de RW-0012) — **la heurística clasifica
mal 2 de 4 casos conocidos**: la p.45 (P3, prosa real) sale
`TABULAR_LIKELY` (falso positivo, por el patrón de líneas cortas de una
lista numerada de campos, que la heurística confunde con tabla); la
p.13 de RW-0011 (P4/P6, mayormente prosa con una tabla de 2 filas) sale
`TABULAR_DENSE` (falso positivo, el marcador "Table 4-8:" solo dispara
todo el veredicto de la página aunque el resto sea prosa). **Tasa de
error observada: 50% sobre la única muestra de validación disponible.**
La cifra `TABULAR_DENSE=53%` del corpus **probablemente sobreestima**
la densidad tabular real — el patrón de "página con una tabla incrustada
en medio de prosa" (como p.13) se clasifica como 100% tabular cuando en
realidad es mayormente prosa. **No se puede dar un número confiable de
`EVIDENCE_TYPE_DISTRIBUTION` sin una clasificación más fina (por
párrafo/sección, no por página) o sin juicio humano/LLM real** — se
entrega el número igual, con esta advertencia explícita, porque la
orden pidió declarar el método y su incertidumbre, no inventar
precisión que no existe.

## 3. Arreglos de instrumento (propuestos, sin implementar — requieren aprobación)

**3.1 Causa 2 — estado real, sin maquillar**: el fix de prompt
(`d42d919`) está aplicado y commiteado. Su efecto sobre el caso real de
P2 **no está confirmado** — no se puede confirmar sin una llamada LLM
real, y no hay presupuesto. Queda "corregido, pendiente de confirmación
en la próxima ventana de inferencia", explícitamente no cerrado.

**3.2 P1/"N2" comparten candidate pool — defecto de instrumento
confirmado, con causa precisa**: verificado contra la definición real
del fixture (`W5V2_RECALL_FIXTURE_SET_DRAFT.md`): N2 fue diseñado para
probar si el modelo distingue "mención superficial en tabla de
contenidos (p.3)" de "evidencia real (p.45-46)" — un par deliberado,
mismo `requirement_id`/documento a propósito. El defecto real no es el
diseño del fixture, es que **`retrieve_top_k(sha, '21_CFR_11.10(e)', k=5)`
nunca incluye la página 3 (ToC) en el top-5** (confirmado: los 5
candidatos reales son páginas 45-46/18-19/55/56/47-48) — la unidad "N2"
tal como se ejecutó en el batch original terminó siendo, por
casualidad, un duplicado exacto de P1 (mismo candidate pool), sin haber
probado nunca la discriminación que fue diseñada para probar.
  **Propuesta de fix (solo arnés de medición, nunca `retrieve_top_k` de
  producción)**: agregar un parámetro opcional al harness de
  construcción de `JudgmentUnit` para casos de fixture (no a
  `retriever.py`) que permita forzar una página conocida
  (`page_indices` del payload de `PILOT_EXECUTION`) dentro de
  `candidate_chunks`, garantizando que el candidato bajo prueba
  realmente llegue al modelo incluso si BM25 no lo rankea alto. Esto es
  estrictamente un instrumento de prueba — no cambia cómo R2 recupera
  evidencia en producción.
**3.3 P1 duplicado en el batch original — causa no determinable con
certeza**: el script que construyó el batch original de la fase de
juicio (50 llamadas, commit `dddfbb2` documenta el resultado pero el
script en sí nunca se guardó ni se commiteó) no sobrevive para
inspección. No se puede determinar con certeza si fue un error de
construcción del arnés o intencional. **Recomendación de instrumento**:
cualquier arnés futuro debe deduplicar `JudgmentUnit`s por
`(document_id, requirement_id, k)` antes de gastar presupuesto, y
persistir el script que generó el batch junto con el resultado (mismo
principio de trazabilidad que ya aplica al resto del proyecto).
**3.4 Consistencia del fixture tras la corrección de P3 — verificado,
consistente**: `ANNEX11_17`/página 44 (`page_indices`, convención
0-indexada de `_extract_pilot_excerpt`) en el payload de
`PILOT_EXECUTION-2026-004` corresponde a la misma página que "45" usada
en las mediciones de `retrieval_recall` (convención 1-indexada de
`page_start`/`page_end`). **No es un error de datos** — son dos
convenciones de indexado de página distintas coexistiendo en el
proyecto, ya usadas consistentemente cada una en su contexto, pero es
una fuente real de confusión al leer memoria/reportes en paralelo.
Recomendación de instrumento (menor): anotar explícitamente la
convención (0-idx vs 1-idx) junto a cualquier número de página en
reportes futuros.

## 4. Plan de re-medición correctamente dimensionado (diseño, NO ejecutado)

Unidades faltantes para completar la muestra de los 6 positivos
medibles + un segundo control de Causa 3: **P2, P4, P5, P7** (P3 queda
fuera por diseño — su página no entra al top-5 aunque sí al top-10
desde el fix de Causa 1; incluirlo exigiría `k=10` en vez de `k=5`).

| Unidad | k propuesto | Por qué | Costo (llamadas) |
|---|---|---|---|
| P2 | 10 (su página real es rank 6, fuera del top-5) | Confirma Causa 2 | 10 |
| P4 | 5 (rank 2, ya en top-5) | Mismo pasaje que P6 — si P6 sigue fallando, P4 probablemente también; confirma o refuta esa inferencia | 5 |
| P5 | 5 (rank 1 tras el fix — mismo chunk que P1) | Confirma si el mismo mecanismo de Causa 1 rescata a P5 como se infiere | 5 |
| P7 | 5 (rank 2, ya en top-5) | Segundo control de Causa 3/hipótesis de dilución en documento distinto | 5 |
| **Total** | | | **25** |

Si además se quiere probar la hipótesis de dilución por chunking (§2.2)
sobre P6/P7 con un candidato de una sola página (no multipágina): +2
unidades adicionales (k=1, acotado a la página real), +2 llamadas cada
una aprox. → **+4 llamadas** (diseño experimental nuevo, no cubierto
por el arnés actual — requeriría además el fix de instrumento del
§3.2/3.3 aplicado primero).

**Costo total estimado: 25-29 llamadas.** `PILOT_EXECUTION-2026-004`
está agotada (60/60) — esto requeriría una `PILOT_EXECUTION-2026-008`
nueva con `max_calls≈30` (margen incluido), **no propuesta en esta
corrida** por instrucción explícita de la orden.

**Criterio de decisión pre-fijado** (antes de medir, no después):
- Con la muestra completa (P1-P7, 6-7 de 7 según si se incluye P3):
  si **≥5 de 6-7** quedan `observed` tras las correcciones → recall real
  del pipeline corregido soporta **Opción A** (el techo de 2/7 original
  era mayoritariamente ruido de pipeline, no límite del modelo).
- Si **≤3 de 6-7** quedan `observed` → **Opción B** domina (Causa 3 es
  el límite real, corregir extracción/prompt no alcanza).
- Resultado intermedio (4/6-7): mixto, mismo problema de interpretación
  que hoy — necesitaría el experimento de dilución (§2.2) para
  desempatar antes de comprometerse a un rumbo.

## 5. Opciones para Cesar (sin recomendación sesgada)

### OPCIÓN A — Continuar con el modelo actual

Viable si el triage confirma evidencia mayoritariamente prosa
estructurada. Requiere: (1) resolver el bloqueador estructural real
(§1.3 — no es "falta interpretación humana", es el diseño fail-closed
todo-o-nada de `verify_sufficiency` por chunk individual — esto por sí
solo puede necesitar rediseño, con su propia corrida de diseño); (2) la
re-medición dimensionada del §4; (3) aceptar que la evidencia realmente
tabular queda como "sin evidencia localizada → revisión humana", que es
honesto, no un fallo.

### OPCIÓN B — Pivotar

Si el triage (con su incertidumbre declarada, §2.3) y la re-medición
completa muestran que la evidencia tabular/densa domina Y que no es
solo dilución por chunking (§2.2 descartada): embeddings semánticos
(diferido en R1.6), cambio de modelo (H5, requiere GPU o proveedor
externo con evaluación de confidencialidad propia), o redefinir el
alcance del analizador hacia lo que el modelo sí hace bien (rechazo de
falsos positivos — N1 siempre correcto — + evidencia en prosa +
enrutamiento del resto a revisión humana). Esta última no es una
derrota: es un producto entregable hoy.

### OPCIÓN C — Desacoplar (nueva, priorizada por el hallazgo de §1.3)

El bloqueador de `verify_sufficiency` fail-closed (§1.3) es
**independiente del recall** — ninguna mejora de recall (Causa 1/2/3,
ni siquiera un cambio de modelo) genera una conclusión positiva
consolidada mientras la regla "un solo criterio `NOT_ASSESSABLE`
invalida todo D" siga vigente contra pasajes reales que casi nunca
cubren todos los criterios mínimos en un solo chunk. El trabajo de
mayor valor inmediato podría ser **rediseñar la agregación de D across
chunks** (combinar criterios confirmados de distintos chunks de un
mismo requisito, no solo el "mejor" chunk individual) o **revisar si
el fail-closed todo-o-nada es la regla correcta** para el objetivo real
del analizador — antes de gastar más presupuesto de inferencia en
recall. Presentado como posible reordenamiento del roadmap, no como
recomendación.

## 6. Nota operativa (no es parte de la decisión de rumbo)

`factory/regulatory/model_qualification/{qualification_record,runtime_calibration_record}.json`
quedaron actualizados por la recalificación real de §4 (estado
`QUALIFIED` vigente) pero **sin commitear** — son artefactos de estado
real de gobernanza, no deberían quedar indefinidamente fuera de
control de versiones. Se muestra en el diff de entrega (§7 de este
documento) para aprobación junto con el resto.

## 7. Bloque de reporte

```
COMMITS_CONFIRMED =            dddfbb2, d42d919, f5a8034 (todos en HEAD)
CAUSA1 = CORREGIDA_CONFIRMADA (P1 observed)
CAUSA2 = CORREGIDA_SIN_CONFIRMAR (P2 pendiente de LLM)
CAUSA3 = LIMITE_REAL_RECONFIRMADO_CON_HIPOTESIS_ALTERNATIVA_ABIERTA
         (P6 sigue fallando; hallazgo nuevo: evidencia real es prosa,
         posible dilucion por chunking multipagina, no confirmado)
VALIDATION_D_STATUS =          20/20 requirements CON evidence_min_criteria
                               interpretados (Fase C SI se hizo, contra
                               la hipotesis de la orden) -- pero
                               evidence_pack_status sigue
                               human_drafted_provisional en los 20,
                               nunca promovido a aprobado
STRUCTURAL_BLOCKER =           verify_sufficiency() fail-closed todo-o-nada
                               POR CHUNK INDIVIDUAL (no agregado entre
                               chunks) -- 1 criterio NOT_ASSESSABLE tira
                               TODO el D a NOT_ASSESSABLE. Confirmado con
                               datos reales de P1 (2 MET, 2 NOT_MET,
                               5 NOT_ASSESSABLE de 9 -> EVALUATION_INCOMPLETE
                               pese a chunk_observation=observed)
EVIDENCE_TYPE_DISTRIBUTION =   PROSE=31%, TABULAR_LIKELY=15%,
                               TABULAR_DENSE=53% (86 paginas, heuristica
                               determinista) -- INCERTIDUMBRE ALTA:
                               50% de error en la validacion contra los
                               4 casos reales conocidos del fixture,
                               probable sobreestimacion de TABULAR_DENSE
INSTRUMENT_FIXES =             P1/N2 pool compartido (causa precisa
                               encontrada: ToC nunca entra al top-5,
                               fix propuesto sin implementar); P1
                               duplicado (causa no determinable, script
                               original no sobrevive); fixture P3
                               consistente (diferencia es solo
                               convencion de indexado 0-idx vs 1-idx)
REMEASURE_PLAN =               P2(k10)+P4(k5)+P5(k5)+P7(k5) = 25 llamadas;
                               +4 opcional para experimento de dilucion;
                               criterio A/B/mixto fijado ANTES de medir
DECISION_PACKAGE =             Opciones A/B/C presentadas sin sesgo
                               (arriba, seccion 5) -- C es nueva,
                               priorizada por el hallazgo de §1.3
SAMPLE_SUFFICIENCY_NOTE =      2/6 re-medidas != veredicto (confirmado,
                               sin cambios desde §4)
D4_2026_004_STATUS =           PROPOSED (sin cambios)
NEXT_HUMAN_DECISION =          Rumbo A/B/C; si autoriza PILOT_EXECUTION
                               nueva para el plan de re-medicion del §4;
                               si prioriza el bloqueador estructural de
                               verify_sufficiency (Opcion C) antes que
                               mas recall
CORPUS_READY =                 false
PRODUCTION_ENABLEMENT =        BLOCKED
```
