# R3-T1.4 — Defecto de agregación multi-chunk (B3): falsa contradicción

Autoridad: Capa 9 = Cesar. Claude Code = Capa 8. Corrida de corrección de
validador (capa D). **COMMITEADO** — `e823015` (2026-08-12), tras mostrar
el diff completo de los 3 archivos y recibir tu aprobación explícita
("lo apruebo"). Actualizado el 2026-08-12 (R3-T1.5 §0.1) para corregir la
divergencia con `R3_T1_3_VIABILIDAD_F2.md` §5(ii), que ya reportaba el
commit correctamente — este encabezado había quedado desactualizado desde
antes del commit.

**Cero llamadas LLM gastadas.** Toda la validación es por replay sobre
checkpoints históricos ya pagados (`chunked-943a62bcbb85`, 29/29 chunks) y
por tests unitarios sintéticos, ejecutados dentro del contenedor
`factory-api` (mismo código de producción, montado en vivo — no una copia).

──────────────────────────────────────────────────────────────────────────
## 0. Lo que R3_T1_3 estableció (aceptado sin re-verificar)
──────────────────────────────────────────────────────────────────────────

B1 (bloqueado por diseño), B2 (variabilidad de muestreo, no incapacidad) y
B3 (bloqueador real: agregación multi-chunk) — ver
`docs_plan/R3_T1_3_VIABILIDAD_F2.md`.

──────────────────────────────────────────────────────────────────────────
## 1. Caracterización exacta del defecto
──────────────────────────────────────────────────────────────────────────

**Ubicación**: `factory/regulatory/semantic_evidence_verification.py`,
`verify_sufficiency_aggregated()` (línea ~348 original) →
`_classify_criteria_for_chunk()` (línea ~289 original), y la regla de
contradicción en `verify_sufficiency_aggregated()` (línea ~423 original:
`contradicted = sorted(all_met & all_not_met)`).

**Cómo combina los votos (antes del fix)**: cada chunk aporta, por
criterio, un voto MET/NOT_MET/NOT_ASSESSABLE. La unión de todos los MET y
todos los NOT_MET across chunks se calcula; si un criterio aparece en
ambos conjuntos → `contradicted` → `NOT_ASSESSABLE` forzado, "nunca
resuelto en silencio". Esta regla es correcta **cuando ambos votos son
genuinos**.

**El núcleo del problema, confirmado con datos reales** (checkpoint
`chunked-943a62bcbb85`, requisito `21_CFR_11.10(e)`, criterios 2
"Timestamp de fecha/hora" y 3 "Registro de entradas y acciones"):

| chunk_index | páginas | `estado` (campo de mas alto nivel, ya emitido por el modelo) | criterio 2/3 |
|---|---|---|---|
| 20 (ancla) | 45-46 | `cumple_parcialmente` | **MET**, cita real ("Date and time stamps...") |
| 0, 4, 5, 8, 9, 10, 11, 13, 14, 15, 16, 17, 22, 23, 24, 25 (16 de 28) | varias | `evidencia_insuficiente` | NOT_MET, `evidence_quote=""`, justificación boilerplate: *"No se menciona timestamp de fecha/hora"* / *"No se menciona registro de entradas y acciones"* |

El propio prompt en producción (`factory/engines/gmpai_integrity/prompts/part11_prompts.yaml`,
regla 4: *"Que no mencione un control no implica incumplimiento del
sistema"*; regla 6: *"Si no estás seguro de si un criterio se cumple, usa
NOT_ASSESSABLE — nunca omitas un criterio"*) ya instruye al modelo a usar
`NOT_ASSESSABLE`, no `NOT_MET`, cuando un chunk simplemente no trata el
tema. El modelo (`qwen2.5:7b`) viola esa regla de forma sistemática: emite
`NOT_MET` boilerplate en chunks que su **propio campo `estado`** (calculado
en la misma respuesta, para el mismo checkpoint) ya clasifica como
`evidencia_insuficiente` — es decir, el modelo se contradice a sí mismo
entre dos campos de su propia salida.

**Las tres situaciones que hoy se colapsan en "NOT_MET" (sección 1.3 del
plan), confirmadas con datos reales**:
- **(a)** chunk relevante (`estado≠evidencia_insuficiente/no_aplica`),
  evidencia cumple → `MET` — chunk 20, idx 2/3.
- **(b)** chunk relevante, evidencia VIOLA → `NOT_MET` genuino — chunk 20
  mismo, idx 1/4 (`estado=cumple_parcialmente`, pero esos criterios sin
  cita); y el caso real encontrado en `21_CFR_11.10(d)` entre los chunks 19
  (`cumple_parcialmente`, MET con cita real) y 20 (`cumple_parcialmente`,
  NOT_MET) — **contradicción real, dos chunks relevantes en desacuerdo
  genuino**, ver sección 3.
- **(c)** chunk irrelevante, simplemente no contiene evidencia →
  `NOT_MET` (defecto), debería ser "sin señal" — los 16+ chunks
  `evidencia_insuficiente` de la tabla arriba.

El defecto es exactamente que (c) se cuenta como (b) en la agregación.

──────────────────────────────────────────────────────────────────────────
## 2. Diseño de la corrección — y la prueba de que no es aflojamiento
──────────────────────────────────────────────────────────────────────────

**¿La señal para separar (c) de (b) ya existe?** SÍ — sin necesitar cambio
de schema ni re-medición. El campo `estado` (`cumple | cumple_parcialmente
| no_cumple | evidencia_insuficiente | no_aplica`) ya lo emite el modelo en
cada respuesta, para cada `req_id`, en el mismo checkpoint (verificado
leyendo `chunked_engine.py` línea 114: `_VALID_ESTADOS`, y confirmado en el
raw_response real de todos los chunks). No se inventó ninguna señal nueva
del modelo.

**Gap encontrado (no del fix, sino de instrumentación)**: `estado` se
calculaba en `chunked_engine.py` pero **no se adjuntaba** a la tupla
`(criterion_assessments, chunk_text)` que alimenta
`verify_sufficiency_aggregated()` — se descartaba después de usarse solo
para la lógica de *findings* (que sí distingue `has_evidence`/`not_observed`
desde 2026-07-16, línea 1573-1581 de `chunked_engine.py`, pero solo a nivel
de *finding*, nunca a nivel de la agregación D por criterio). El fix es
**puramente de agregación + instrumentación**, no de schema del modelo —
determinado ANTES de implementar, como pedía la sección 2.2 del plan.

**Cambios de código**:

1. `factory/regulatory/semantic_evidence_verification.py`:
   - Nueva constante `_OFF_TOPIC_CHUNK_ESTADOS = frozenset({"evidencia_insuficiente", "no_aplica"})`.
   - `_classify_criteria_for_chunk(criterion_assessments, source_text, chunk_estado=None)`:
     nuevo parámetro opcional. Si `chunk_estado` está en
     `_OFF_TOPIC_CHUNK_ESTADOS`, un `NOT_MET` de ese chunk se reclasifica a
     `NOT_ASSESSABLE` (nunca a `MET` — nunca fabrica evidencia). Default
     `None` preserva el comportamiento exacto anterior (usado por
     `verify_sufficiency()`, un solo chunk, que NUNCA pasa `chunk_estado` y
     por tanto no cambia).
   - `verify_sufficiency_aggregated()`: acepta tuplas de 2 O 3 elementos
     (`(criterion_assessments, texto)` o `(criterion_assessments, texto,
     estado)`) — retrocompatible con todo llamador/test existente.
2. `factory/engines/gmpai_integrity/chunked_engine.py`: el `estado` ya
   calculado se adjunta como 3er elemento al poblar
   `criterion_assessments_by_req` (ambos puntos: ejecución en vivo y
   reanudación desde checkpoint) y se guarda en `_criterion_assessments_for_d`
   del checkpoint para que una reanudación futura lo recupere. Checkpoints
   viejos (sin este campo) devuelven `None` → comportamiento idéntico al
   de antes del fix, nunca roto.
3. `factory/tests/test_semantic_evidence_verification.py`: 5 tests nuevos
   (sección 4).

**Por qué esto NO es aflojar el validador — argumento, no solo afirmación**:
- Un `NOT_MET` reclasificado nunca se convierte en `MET` — se convierte en
  `NOT_ASSESSABLE`, que es el estado MÁS conservador del sistema (nunca
  contribuye a una conclusión positiva; fuerza incertidumbre real si no se
  resuelve en otro chunk). Downgradear NOT_MET→NOT_ASSESSABLE es estrictamente
  más estricto, nunca más laxo.
- La regla de contradicción dura (`contradicted = met & not_met`) **sigue
  intacta, sin tocar una sola línea de su lógica** — solo cambia qué cuenta
  como voto antes de llegar a ella. Un `NOT_MET` genuino (chunk relevante)
  sigue pudiendo contradecir; solo un `NOT_MET` de un chunk que el propio
  modelo ya declaró fuera de tema deja de poder hacerlo.
- El caso de ausencia total (ningún chunk trata el tema) pasa de
  `NOT_MET` (una negativa "confiada") a `NOT_ASSESSABLE` (incertidumbre
  real) — un cambio en la dirección MÁS conservadora, no menos, y coherente
  con la propia regla 4 del prompt ("que no mencione un control no implica
  incumplimiento").

──────────────────────────────────────────────────────────────────────────
## 3. Validación por replay (cero llamadas LLM)
──────────────────────────────────────────────────────────────────────────

### 3.1 Tabla ANTES/DESPUÉS (checkpoint histórico real, 29/29 chunks, `estado` recuperado del `raw_response` completo — el gap de instrumentación, no de lógica, descrito arriba)

| Requisito | ANTES (código sin fix) | DESPUÉS (código con fix) | Clasificación de lo que cambió |
|---|---|---|---|
| `21_CFR_11.10(e)` | `NOT_ASSESSABLE` — *"contradiccion real entre chunks en 2 criterio(s)"* (crit 2 y 3: MET en chunk 20 vs NOT_MET boilerplate en 16 chunks off-topic) | `PARTIALLY_MET` — *"2/9 criterios confirmados"*, sin `contradicted` en el detalle | (c)→corregido: los 16 NOT_MET off-topic se reclasifican a NOT_ASSESSABLE y dejan de colisionar con el MET real; los NOT_MET genuinos de crit 1,4-9 (del propio chunk 20, relevante) permanecen intactos |
| `21_CFR_11.10(d)` | `NOT_ASSESSABLE` — *"contradiccion real... 1 criterio"* (crit "Mecanismo de control de acceso...": MET en chunk 19 vs NOT_MET en chunk 20, AMBOS `estado=cumple_parcialmente`) | `NOT_ASSESSABLE` — **misma razón, sin cambios** | (b) genuino: chunk 19 (`cumple_parcialmente`, MET con cita real) y chunk 20 (`cumple_parcialmente`, NOT_MET) están AMBOS relevantes y en desacuerdo real — el fix correctamente NO lo toca |
| `21_CFR_11.50_11.70` | `NOT_MET` — *"ningun criterio minimo confirmado"* | `NOT_MET` — sin cambios | Todos los chunks relevantes coinciden en negativo genuino; no había falsa contradicción que corregir |

**Nota de honestidad sobre el valor histórico guardado en el checkpoint**:
el checkpoint `chunked-943a62bcbb85` tiene almacenado
`d_sufficiency=PARTIALLY_MET` para el candidato del chunk 20 en aislado
(calculado en su momento por `verify_sufficiency()`, un solo chunk, ANTES
de que existiera la agregación multi-chunk de R2.1 Opción C). El resultado
POST-FIX de la agregación completa (`PARTIALLY_MET`, sección arriba)
**coincide exactamente** con ese valor histórico de un solo chunk — el fix
no inventa un resultado nuevo, restaura el mismo resultado honesto que el
sistema ya había calculado antes de que la agregación (con su defecto)
lo enmascarara.

### 3.2 Los 4 guardianes obligatorios (sección 2.3 del plan) — todos pasan

```
$ docker exec factory-api python3 -m pytest factory/tests/test_semantic_evidence_verification.py -v
...
TestVerifySufficiencyAggregated::test_off_topic_chunk_boilerplate_not_met_does_not_poison_real_evidence PASSED
TestVerifySufficiencyAggregated::test_off_topic_chunk_reproduces_real_11_10_e_partial_case PASSED
TestVerifySufficiencyAggregated::test_genuine_contradiction_between_two_relevant_chunks_still_blocks PASSED
TestVerifySufficiencyAggregated::test_absence_across_all_chunks_never_fabricates_met PASSED
TestVerifySufficiencyAggregated::test_missing_chunk_estado_matches_pre_fix_behavior_exactly PASSED
TestVerifyEvidenceABCD::test_annex11_4_like_false_positive_never_accepted PASSED
... 47 passed
```

- **CONTRADICCIÓN GENUINA PRESERVADA**: `test_genuine_contradiction_between_two_relevant_chunks_still_blocks`
  — dos chunks `estado∈{cumple_parcialmente, no_cumple}` en desacuerdo →
  sigue `NOT_ASSESSABLE` con `contradicted` no vacío. **PASS.**
- **ANNEX11_4 sigue rechazado**: `test_annex11_4_like_false_positive_never_accepted`
  no toca la agregación (es validación C, lista de referencias), no se
  modificó ninguna línea de esa ruta — confirmado en verde sin cambios.
  **PASS.**
- **AUSENCIA REAL preservada**: `test_absence_across_all_chunks_never_fabricates_met`
  — 5 chunks, todos `evidencia_insuficiente`, todos NOT_MET boilerplate →
  `NOT_ASSESSABLE` (nunca MET, nunca una negativa "confiada" fabricada).
  **PASS.**
- **Caso real (c) de 11.10(e) corregido**: `test_off_topic_chunk_reproduces_real_11_10_e_partial_case`
  — reproduce el caso real exacto (sección 3.1), confirma
  `contradicted` ausente y `met=={crit2,crit3}` preservado. **PASS.**
- **Retrocompatibilidad estricta** (no pedida explícitamente pero
  necesaria para "no aflojar" nada por omisión): `test_missing_chunk_estado_matches_pre_fix_behavior_exactly`
  — tuplas de 2 elementos (checkpoints/llamadores viejos) reproducen el
  comportamiento exacto de antes del fix. **PASS.**

### 3.3 Suite completa + Gate 0

```
$ docker exec factory-api python3 -m pytest factory/tests/test_semantic_evidence_verification.py factory/tests/test_gmpai_chunked_engine.py -q
103 passed
```

Se intentó correr `factory/tests/` completo (2434 tests) dentro del
contenedor `factory-api`. **No termina en este entorno** — no por un
defecto del fix, sino por una limitación ambiental ya documentada
(`docs_plan/R3_T1_2_F0_EVIDENCIA/RESUMEN.md`, "Gate 0"): un bloque grande
de tests depende de invocar el CLI `docker` (inexistente DENTRO del propio
contenedor donde corre pytest — `FileNotFoundError: [Errno 2] No such file
or directory: 'docker'`, confirmado en `test_access_log_file_created`) o de
un servidor Mission Control vivo alcanzable por red. Ninguno de esos
archivos (`test_access_log.py`, `test_artifact_version_apply.py`,
`test_mission_evidence_readers.py`, `test_mission_summary.py`,
`test_path_policy.py`, etc.) importa ni ejercita
`semantic_evidence_verification.py` ni `chunked_engine.py` — verificado
por grep, cero solapamiento con los archivos de este fix.

Confirmado explícitamente en la corrida verbosa (`-v --tb=no`) sobre la
suite completa: **los dos archivos que este fix modifica siguen 100% en
verde** — `test_semantic_evidence_verification.py` (47/47, incluidos los 5
guardianes nuevos) y `test_gmpai_chunked_engine.py` (56/56, sin una sola
línea distinta de `PASSED`). Ningún test preexistente se modificó en su
aserción original.

──────────────────────────────────────────────────────────────────────────
## 4. Re-evaluación de la viabilidad de F2 (con B3 corregido)
──────────────────────────────────────────────────────────────────────────

**4.1 — `21_CFR_11.10(e)` alcanza `PARTIALLY_MET` (2/9), NO `MET`
(CONFIRMED)** con el fix, sobre el documento real completo (RW-0005). El
fix resuelve la FALSA contradicción, pero **no rescata cobertura que el
documento genuinamente no tiene** (los criterios 1, 4-9 permanecen sin
evidencia real en ningún chunk de las 29 evaluadas) — esto es exactamente
lo que R3_T1_3 §0 ya había encontrado por otra vía (ningún chunk del
documento completo cubre esos criterios). **CONFIRMED sigue sin ser
alcanzable para este documento/requisito, no por B3, sino por cobertura
real del documento** — B1 y B3 combinados ya no bloquean, pero el
contenido del documento sí. Esto es una conclusión honesta, no un fallo:
la Opción B/RAMA B de R3_T1_3 (criterio redefinido,
`SUPPORTING_EVIDENCE_UNDER_REVIEW`) sigue siendo la vía correcta para este
caso concreto — con la diferencia de que ahora el estado que llega a cola
humana es `PARTIALLY_MET` honesto (2/9, con contradicted vacío), no
`NOT_ASSESSABLE` por una contradicción fabricada.

**4.2 — Generalización**: no se puede afirmar que el fix por sí solo hace
CONFIRMED alcanzable para 11.10(e) en general — depende del documento. En
documentos donde la evidencia de los 9 criterios SÍ está distribuida en
distintos chunks (el caso de diseño original de R2.1 Opción C,
`test_criteria_scattered_across_two_chunks_combine_to_met`), el fix es
justamente lo que permite que la agregación llegue a MET sin ser
derribada por chunks irrelevantes intercalados — ese es el valor real del
fix para F2 en general, no solo para este documento puntual.

**4.3 — B1 sigue siendo la decisión de Cesar pendiente** (paquete ya
preparado en `R3_T1_3_VIABILIDAD_F2.md` §1) — sin cambios de esta corrida.
No se promovió el flag, no se tocó el catálogo.

**4.4 — Variabilidad de B2 (sección 4.2 del plan)**: sigue viva. El fix de
B3 no la elimina — un chunk relevante puede seguir, en una corrida dada, no
citar `evidence_location` (como pasó en F1) o dar NOT_MET donde otra
corrida daría MET (como se ve entre `chunked-50534e75927c` y
`chunked-943a62bcbb85` para el mismo chunk p.45-46, idx 5-9: NOT_ASSESSABLE
en una corrida, NOT_MET en otra). **El criterio de F2 debe contemplar
esto**: CONFIRMED alcanzable ≠ CONFIRMED garantizado en cada corrida —
una corrida que no alcance CONFIRMED puede necesitar reintento de chunk, no
relajación del validador.

**4.5 — Fingerprint/economía**: el fix cambia código de producción
(`chunked_engine.py`, `semantic_evidence_verification.py`) — cualquier
corrida NUEVA de F2 corre con este código corregido, no con el de F1
(`prompt_version=1.1.1` sin cambios, pero la lógica de agregación D sí
cambió). El cache de F1/F1.5 (que nunca se gastó, ver R3_T1_3) sigue sin
usarse por B1, no por este fix. El replay de la sección 3 es
**diagnóstico**, no cache de producción — una corrida real de F2 volvería
a ejecutar los chunks con el código nuevo, no reutiliza estos resultados
replay.

──────────────────────────────────────────────────────────────────────────
## 5. Hallazgo colateral y alcance
──────────────────────────────────────────────────────────────────────────

**5.1 — Impacto histórico en el recall agregado**: B3 probablemente
deprimió el recall AGREGADO (no el recall por-chunk, que ya se medía
correctamente) en toda corrida multi-chunk previa que pasara por
`verify_sufficiency_aggregated()` desde su introducción (R2.1 Opción C,
2026-08-10) — cualquier requisito con evidencia concentrada en 1-2 chunks
de un documento largo, rodeado de chunks irrelevantes emitiendo `NOT_MET`
boilerplate en violación de la regla 4/6 del prompt, habría chocado con
esta falsa contradicción y caído a `NOT_ASSESSABLE` en vez de
`MET`/`PARTIALLY_MET`. **Esto NO significa que el límite de paráfrasis del
7B (el riesgo central de R2, recall 2/7 medido) se resuelva** — son capas
distintas: R2 mide si el modelo RECONOCE evidencia parafraseada; B3 es un
defecto de CÓMO SE AGREGA evidencia ya reconocida across chunks. Ambos
límites son reales y separados; corregir B3 no toca el límite de
paráfrasis.

**5.2 — Tipo de fix**: agregación pura + instrumentación (opción 2.1 del
plan), NO cambio de schema del modelo. No requiere re-medición para
validarse (se validó por replay), aunque una corrida NUEVA de F2 sí
generará checkpoints con el campo `estado` ya presente en
`_criterion_assessments_for_d` desde el primer chunk.

**5.3 — Pendientes de F0 (baratos, sin cambios en esta corrida)**: Gate 0
Playwright/HTTP y `part11_prompts.yaml` fantasma — ambos ya documentados
en corridas anteriores, sin acción nueva aquí (fuera de alcance de esta
corrida, que es específicamente sobre B3).

──────────────────────────────────────────────────────────────────────────
## 6. Entrega
──────────────────────────────────────────────────────────────────────────

```
B3_ROOT_CAUSE =               semantic_evidence_verification.verify_sufficiency_aggregated(),
                              contradicted = all_met & all_not_met (linea ~423 original) --
                              cuenta NOT_MET boilerplate de chunks off-topic
                              (estado=evidencia_insuficiente/no_aplica) como voto
                              genuino, colisionando con MET real de otro chunk
SIGNAL_FOR_C_EXISTS =         SI -- campo `estado` (chunked_engine._VALID_ESTADOS),
                              ya emitido por el modelo, no capturado hasta ahora en
                              criterion_assessments_by_req (gap de instrumentacion,
                              no de schema)
FIX_TYPE =                    agregacion pura + instrumentacion, validado por replay,
                              CERO llamadas LLM nuevas
FIX_IS_NOT_LOOSENING_PROOF =  NOT_MET -> NOT_ASSESSABLE unicamente (nunca -> MET);
                              regla de contradiccion intacta; retrocompatible con
                              tuplas de 2 elementos (None = comportamiento previo)
GENUINE_CONTRADICTION_BLOCKED = true (test_genuine_contradiction_between_two_relevant_chunks_still_blocks
                              PASA; caso real 11.10(d) chunk19 vs chunk20 confirmado
                              NOT_ASSESSABLE sin cambios)
ANNEX11_4_STILL_REJECTED =    true (test_annex11_4_like_false_positive_never_accepted
                              PASA, ruta C no tocada)
ABSENCE_STILL_BLOCKS =        true (test_absence_across_all_chunks_never_fabricates_met
                              PASA -- NOT_ASSESSABLE, nunca MET)
REPLAY_BEFORE_AFTER =         11.10(e): NOT_ASSESSABLE(falsa contradiccion) -> PARTIALLY_MET(2/9, honesto);
                              11.10(d): NOT_ASSESSABLE(contradiccion real) -> sin cambios (correcto)
CONFIRMED_NOW_ACHIEVABLE =    para 11.10(e) en ESTE documento: NO (cobertura real del
                              documento, no B1/B3, lo bloquea); en general (documentos
                              con evidencia distribuida entre chunks): SI, sujeto a B1
B1_REMAINING =                sin cambios -- decision de Cesar pendiente (R3_T1_3 s1)
B2_SAMPLING_NOTE =            sigue viva; F2 debe contemplar reintento de chunk, no
                              relajacion de validador
F2_VIABLE_AFTER_FIX =         RAMA B para 11.10(e)/RW-0005 especificamente (cobertura
                              real insuficiente); RAMA A viable en general para
                              requisitos con evidencia distribuida, sujeto a B1
FINGERPRINT_F2 =              codigo de agregacion D cambio -- una corrida F2 nueva no
                              reutiliza cache de F1/F1.5 (que de todos modos nunca se
                              gasto); prompt_version=1.1.1 sin cambios
HISTORICAL_RECALL_IMPACT =    B3 deprimia el recall AGREGADO (no el reconocimiento
                              por-chunk) en toda corrida multi-chunk desde R2.1 Opcion C;
                              no afecta ni resuelve el limite de parafrasis (R2, separado)
NEXT_SIGNATURES =             (i) [CUMPLIDA 2026-08-12, commit e823015] aprobar
                              este commit (diff + 5 tests nuevos,
                              factory/regulatory/semantic_evidence_verification.py +
                              factory/engines/gmpai_integrity/chunked_engine.py +
                              factory/tests/test_semantic_evidence_verification.py);
                              (ii) ARTIFACT_VERSION-2026-019 (018 ya ocupado por otra
                              propuesta sin confirmar, ver R3_T1_3_VIABILIDAD_F2.md §5(iii))
                              + decision de elegibilidad B1;
                              (iii) autorizacion de F2 solo despues de (i)+(ii)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**COMMITEADO.** Fix diseñado, implementado, validado por replay y
commiteado (`e823015`, 2026-08-12) tras revisión del diff y aprobación
explícita de Cesar. Pendiente al momento de este commit: (a) [CUMPLIDA]
tu revisión del diff (3 archivos), (b) resultado
final de la suite completa (corriendo en background al cierre de este
informe), (c) tu aprobación explícita antes de `git commit`.
