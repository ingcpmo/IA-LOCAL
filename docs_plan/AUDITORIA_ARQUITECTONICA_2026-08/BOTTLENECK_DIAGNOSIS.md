# A.2 — Diagnóstico del cuello de botella (§13, §23)

**Pregunta central**: ¿cuánto del fallo en P2/P4/P5/P7 proviene de
extracción / representación / chunking / retrieval / contexto / ausencia
de estructura / el LLM?

## Dato que acota la respuesta (ya cerrado, no re-derivado)

R2 midió, con tres vías independientes:

1. BM25 solo: `retrieval_recall_at_5 = 4/7`.
2. Fusión BM25+embeddings (RRF): `retrieval_recall_at_5 = 7/7` — la
   recuperación ya NO es el cuello para P2/P5.
3. Re-medición del JUICIO con el pool de fusión perfecto
   (`PILOT_EXECUTION-2026-012`): P2 y P5 llegaron al top-5, evidencia
   correcta en rank 2 de 5 — el modelo **aun así no los reconoció (0/2)**.

**Conclusión ya confirmada para P2/P5**: el cuello de botella es el
modelo (7B) sobre evidencia parafraseada, no la recuperación ni la
extracción. Confirmado con tres mediciones independientes, no hipótesis.
Esta auditoría no repite esa medición.

## Lo que esta auditoría SÍ investigó de nuevo: P6/P7

P2/P5 son casos de **paráfrasis** (la evidencia está presente pero
reformulada). P6/P7 son sospechosos de una causa DISTINTA: **dilución por
ruido tabular** — la prosa relevante podría estar presente literalmente
pero sepultada en un chunk dominado por una tabla.

### Evidencia real extraída en esta auditoría

Página real usada por P6 (`GMPAI/source/Rockwell/MCCPDC EMS Control Block
Narrative revB.pdf`, página índice 12 = "Page 13 of 14" impresa,
confirmada contra `docs_plan/W5V2_PILOTO1_REPORTE.md:24` y
`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md:37`).

- Texto completo de la página: **2427 caracteres**.
- Contiene íntegra "Table 4-8: Vaporized Hydrogen Peroxide Signals" (filas
  de tags `ALH-33002-03 DO`, `AIT-33002-01 AI`, …) inmediatamente antes de
  la sección "4.4 Operator Interface".
- Prosa relevante real (la que debía anclar el requisito): *"with the
  proper credentials, the input points can be simulated for calibration
  or other maintenance activities"* — ~110 caracteres, **~4.5% del texto
  de esa página**.
- El chunk real de producción es aún mayor que una página
  (`build_page_chunks` agrupa hasta `CHUNK_MAX_CHARS=6000`), por lo que la
  proporción real de prosa relevante frente al chunk completo es
  **menor al 4.5%**, probablemente por debajo del 2%.

### Límite honesto de esta medición

El checkpoint reejecutable exacto de esa corrida (el chunk exacto que
recibió el modelo en el Piloto 1 para p.12/13) **no está preservado**
en `factory/regulatory/pilot_run/checkpoints/` — los checkpoints
presentes cubren solo páginas 1-5 de RW-0011/RW-0012. El reporte
narrativo (`W5V2_PILOTO1_REPORTE.md`) documenta el resultado agregado
(`chunk_observation=not_observed_in_chunk`) pero no tiene una sección de
diagnóstico dedicada a P6/P7 con el mismo nivel de detalle que P1.

**Por tanto**: hay evidencia real y medible de que la tabla domina el
texto del chunk (ratio de ruido cuantificado, no especulado). Pero **no
hay un experimento re-ejecutado con checkpoint preservado que aísle si
separar tabla de prosa habría cambiado el resultado del modelo en P6/P7**
— a diferencia de P2/P5, donde el experimento con evidencia perfectamente
aislada sí se corrió y el resultado no mejoró (0/2).

## ACTUALIZACIÓN 2026-08-14 — Cierre de P4 (Bloque 0, `CONTINUACION_FASE0_P4_FASE1.md`) y verificación mecánica de P6/P7 (Bloque 2)

### P4 — diagnosticado, cierre de R8

`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md:35,37` confirma que **P4 y P6
comparten literalmente el mismo documento, la misma página y el mismo
pasaje fuente** (RW-0011, página 12): P4 se juzga contra
`ALCOA_ATTRIBUTABLE`, P6 contra `21_CFR_211.68(b)`, pero ambos leen el
mismo chunk. Verificado por re-extracción directa (`pdfplumber`, dentro
de `factory-api`, solo lectura) del PDF real
(`GMPAI/source/Rockwell/MCCPDC EMS Control Block Narrative revB.pdf`,
página índice 12): mismo texto de 2427 caracteres, misma tabla "Table
4-8: Vaporized Hydrogen Peroxide Signals", misma oración de prosa de 110
caracteres (4.53% de la página).

**Conclusión P4**: mismo tipo de caso que P6 — hipótesis de dilución
tabular, con la misma evidencia de apoyo y la misma advertencia (no
confirmado causalmente). No es paráfrasis (distinto de P2/P5). No
requiere un experimento adicional propio: cualquier medición sobre el
chunk de P6 cubre automáticamente a P4 (mismo chunk, distinto
`requirement_id` a verificar en el mismo prompt/checkpoint).

**R8 (RISK_REGISTER.md) queda CERRADO** con esta evidencia — ver
actualización en ese documento.

### P6 — verificación mecánica real (Bloque 2, `pdfplumber.extract_tables()`)

Extracción real (no simulada) de la página 12 (RW-0011) dentro del
contenedor `factory-api`: `extract_tables()` devuelve 2 tablas — tabla 0
es el bloque de cabecera/furniture del documento (1 fila, metadata de
página), tabla 1 es la tabla real de señales I/O (3 filas: cabecera +
`ALH-33002-03 DO` + `AIT-33002-01 AI`). **La oración de prosa relevante
("with the proper credentials, the input points can be simulated for
calibration or other maintenance activities") queda completamente FUERA
de ambas tablas extraídas** — vive en el texto de la sección "4.4
Operator Interface", después de la tabla.

**Resultado mecánico P6/P4: la tabla SÍ se separa limpiamente de la
prosa.** Confirma el criterio 2.2 del Bloque 2 en sentido positivo — la
Fase 3 del experimento (2 llamadas LLM) queda justificada para este
caso, sujeta a aprobación de Cesar sobre qué `PILOT_EXECUTION` usar.

### P7 — HALLAZGO NUEVO que corrige la agrupación previa "P6/P7 = misma hipótesis"

Extracción real de la página 13 (RW-0012, documento real distinto,
SHA-256 `de7b70c2...` confirmado contra
`factory/regulatory/scope/source_baseline_allowlist.yaml:196-203`):
texto de 2139 caracteres, contiene la misma oración de prosa casi
idéntica ("with the proper credentials, the input points can be
simulated for calibration or other maintenance activities", sección
"4.3 Operator Interface"). **Pero `extract_tables()` en esta página
devuelve UNA sola tabla — el mismo bloque de cabecera/furniture (1
fila) — sin ninguna tabla de contenido real (no hay tabla de señales
I/O en esta página).**

**Esto contradice la agrupación previa de la auditoría original**, que
trató a P6 y P7 como el mismo tipo de caso ("posible dilución tabular")
por compartir un pasaje casi idéntico. La evidencia real muestra que
**la prosa de P7 NO está diluida por ninguna tabla** — vive en contexto
limpio, de la misma forma que un caso de paráfrasis (P2/P5). Si P7
efectivamente falló en anclar (dato heredado de la auditoría anterior,
no re-verificado en este Bloque), la causa más probable por esta nueva
evidencia es el mismo límite de juicio del modelo que P2/P5 — **no**
dilución tabular. Recomendación: **excluir a P7 del alcance de la Fase 3
del experimento tabular** (no tiene sentido aislar una tabla que no
existe en su chunk); si Cesar quiere investigar P7 más a fondo, debe
tratarse como candidato al mismo bucket que P2/P5, no al de P6/P4.

### CORRECCIÓN 2026-08-15 (docs_plan/CONTINUACION_CIERRE_ESTRATEGICO.md, Bloque 0) — P7 pasa de INFERENCE a lectura textual directa, pero la clasificación final queda OPEN_DECISION

El párrafo anterior trataba a P7 como si su causa ya estuviera resuelta
por analogía con P2/P5 — eso era **INFERENCE sin lectura del texto
real**, exactamente el mismo tipo de sobregeneralización que el
`RISK_REGISTER.md` marca como riesgo transversal principal. Corregido:

**FACT (lectura directa del texto completo de la página, 2026-08-15)**:
el pasaje relevante SÍ existe en RW-0012 p.13, sección "4.3 Operator
Interface": *"Each of the input signals is displayed in engineering
units on the HMI. As mentioned previously, with the proper credentials,
the input points can be simulated for calibration or other maintenance
activities."* — **casi verbatim** respecto al de P4/P6 (RW-0011), NO
parafraseado. Este es el mismo patrón de eco léxico que hizo funcionar a
P1, no el patrón de paráfrasis de P2/P5. La hipótesis "P7 = mismo bucket
que P2/P5" del párrafo anterior queda **contradicha por el propio texto**.

**FACT (verificado en `W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`, 4 filas
de experimentos H1-H6 independientes)**: P7 falló consistentemente en la
historia real medida (`no_cumple`/`evidencia_insuficiente`/`not_found`
en las 4 filas) — no era una asunción, hubo medición real, aunque el
checkpoint específico no se preservó.

**Tercera hipótesis, no considerada antes, con apoyo real parcial**: los
checkpoints reales propios de esta sesión para P6 (mismo agente
`fda_cgmp_211_agent`, mismo `req_id`, `chunked-554544f4090f` y
`chunked-510444cedc9b`) muestran un Evidence Pack de **7 criterios**
amplios (control técnico de cambios en registros maestros,
identificación de personal autorizado, exactitud de I/O, etc.) — la
oración de calibración/credenciales solo toca tangencialmente uno de
esos criterios, nunca los cubre todos. Es decir: **incluso un modelo que
reconociera la oración literal seguiría teniendo motivo legítimo para
marcar la mayoría de los 7 criterios como NOT_MET/NOT_ASSESSABLE** — lo
que abre la posibilidad de que el fallo histórico de P7 no sea un "miss"
de reconocimiento, sino una evaluación correcta de evidencia insuficiente
frente a un criterio regulatorio amplio.

**OPEN_DECISION, no forzado a FACT**: no existe checkpoint histórico
propio de P7 preservado (mismo límite documentado desde la primera
versión de este documento), y esta corrida tiene la regla dura de cero
llamadas LLM — no se puede re-ejecutar P7 para confirmar cuál de las dos
lecturas es la real (miss de reconocimiento vs. evaluación
multi-criterio correcta). **P7 NO se suma como sexto caso confirmado a
la conclusión del cuello de botella** — queda fuera del conteo de casos
confirmados por experimento directo hasta que exista su propio
checkpoint real (re-ejecución futura, con aprobación de Cesar).

## ACTUALIZACIÓN 2026-08-15 — Corrida real de P4/P6 ejecutada (2 llamadas LLM, aprobadas por Cesar)

Ejecutada vía `corpus_runner.run_pilot_sample_batch()` (`PILOT_EXECUTION-2026-010`,
2/25 de presupuesto), `evaluation_profile=H2H4`, sobre RW-0011 p.12 (0-based),
con el pipeline YA CORREGIDO (fix de furniture simétrico del Bloque 1).
Checkpoints preservados: `factory/regulatory/pilot_run/checkpoints/
chunked-5a439f3fde11.checkpoint.json` (P4) y `chunked-554544f4090f.checkpoint.json`
(P6) — cierra R9 del `RISK_REGISTER.md`.

**Resultado real**: ambos `estado="evidencia_insuficiente"`,
`evidencia_exacta=""`, todos los `criterion_assessments` en `NOT_MET` —
el modelo NO ancló la evidencia en ninguno de los dos. Mismo resultado
que la corrida histórica.

**CORRECCIÓN METODOLÓGICA IMPORTANTE, no maquillada**: esta corrida real
**NO fue el "brazo C" (aislar la prosa de la tabla)** diseñado en
`EXPERIMENT_PLAN.md` — fue una revalidación del pipeline actual (fix de
furniture aplicado, pero SIN construir ninguna representación
`Table`/`EvidenceUnit` que separe la prosa de la tabla). El chunk que
recibió el modelo en esta corrida real (`text_chars=2514`) sigue siendo
tabla+prosa mezcladas en texto plano, igual que siempre — nunca se aisló
la oración de 110 caracteres al frente del prompt como proponía el
diseño del brazo C. Error de ejecución propio: se confundió "disparar la
Fase 3 aprobada" con "construir y ejecutar el experimento C completo" —
solo se hizo lo primero.

**Lo que esta corrida SÍ confirma**: el fix de furniture (Bloque 1), por
sí solo, NO resuelve P4/P6 — consistente con la advertencia ya escrita
en este documento (una mejora de representación parcial no garantiza
cambiar el juicio). **Lo que esta corrida NO confirma ni descarta**: si
aislar la prosa de la tabla (el experimento C real, todavía no
construido) cambiaría el resultado — esa pregunta sigue abierta,
requeriría construir la entidad `Table`/`EvidenceUnit` (ver
`DOCUMENT_NORMALIZATION_ARCHITECTURE.md`/`EVIDENCE_ARCHITECTURE.md`) y
gastar una llamada LLM nueva, con aprobación separada de Cesar.

## ACTUALIZACIÓN 2026-08-15 (segunda) — Experimento C REAL ejecutado (2 llamadas más, aprobadas por Cesar)

Corregido el error metodológico de arriba: se construyó de verdad la
representación aislada — texto real de la página 12 (RW-0011) con la
tabla de señales I/O (`Table 4-8`) y el bloque de cabecera/pie de
plantilla (distinto del template FS de RW-0005, `_PAGE_FURNITURE_RE` no
lo cubre — removido a mano para este experimento) eliminados, prosa
relevante en su posición narrativa natural, sin reordenar (una sola
variable manipulada: ruido tabular, no posición). Verificación mecánica
previa (0 llamadas): prosa presente íntegra, ningún fragmento de tabla
presente — confirmado antes de gastar la llamada. Texto final: **1670
caracteres** (vs. 2427 originales) — la prosa relevante pasa de ~4.5% a
**~6.6%** del texto total.

Ejecutado vía `chunked_engine.evaluate_chunked()` directo (no
`run_pilot_sample_batch`, que no acepta texto pre-aislado), replicando a
mano las mismas verificaciones de gobernanza (`model_qualification_gate`,
`PILOT_EXECUTION-2026-010` seleccionada, sin proponer ninguna nueva) —
mismo `CheckpointStore` real, mismo `run_context='pilot'`, checkpoints
preservados: `chunked-8e2b20bfa511.checkpoint.json` (P4 aislado) y
`chunked-510444cedc9b.checkpoint.json` (P6 aislado).

**Resultado real**: **idéntico al de la corrida sin aislar.** Ambos
`estado="evidencia_insuficiente"`, `evidencia_exacta=""`, todos los
criterios `NOT_MET`/`NOT_ASSESSABLE`. Remover la tabla por completo y
dejar la prosa en contexto narrativo limpio **no cambió el juicio del
modelo**.

**Esto SÍ responde la pregunta central de la auditoría, con evidencia
directa, no inferida**: la hipótesis de dilución tabular para P4/P6
queda **REFUTADA por experimento real**, no solo sin confirmar. El mismo
patrón que R2 ya había cerrado para P2/P5 (evidencia perfectamente
aislada, juicio sin cambio) se replica aquí de forma independiente para
una causa estructuralmente distinta (ruido tabular vs. paráfrasis) — dos
vías de medición distintas convergiendo en la misma conclusión: el techo
es del modelo de 7B, no de ninguna etapa de representación o extracción.

## BOTTLENECK_CONCLUSION (actualizada 2026-08-15, corregida — P7 no forzado)

Se responde por caso, no en bloque — el brief pedía una respuesta única
del §23 pero la evidencia real no la sostiene como una sola letra. Con el
experimento C real completado, la conclusión es sólida para 4 casos; P7
queda explícitamente fuera del conteo (ver corrección arriba):

| Caso | Cuello de botella | Nivel de evidencia |
|---|---|---|
| P2, P5 (paráfrasis) | **F — el modelo/LLM**, no representación ni recuperación | **FACT** — 3 mediciones independientes, R2 |
| P4, P6 (dilución tabular, mismo chunk) | **F — el modelo/LLM, REFUTADA la hipótesis de representación por experimento real**: tabla removida por completo, prosa en contexto limpio (1670 chars, ratio 6.6%), mismo resultado que con la tabla presente | **FACT** — corrida real `chunked-8e2b20bfa511`/`chunked-510444cedc9b` (aislado) vs. `chunked-5a439f3fde11`/`chunked-554544f4090f` (sin aislar), checkpoints preservados |
| P7 | **NO clasificado** — texto verbatim (no paráfrasis), sin tabla, pero posible evidencia genuinamente insuficiente frente a un Evidence Pack de 7 criterios amplios (no un miss de reconocimiento necesariamente) | **OPEN_DECISION** — sin checkpoint histórico propio, sin re-ejecución en esta corrida (regla dura: cero LLM) |

**Conclusión final, precisa (corrige "5 casos" de la versión anterior de
este documento)**: **4 de los 5 casos positivos fallidos del fixture
7P+2N (P2, P4, P5, P6) están confirmados por experimento directo** —
comparten la misma causa raíz, el techo de juicio del modelo de 7B, no
una deficiencia de representación, extracción, chunking o recuperación.
Ninguna mejora de pipeline (kerning, furniture, fusión semántica de
retrieval, aislamiento completo de ruido tabular) movió el resultado en
ninguno de esos 4 casos. **P7 sigue sin causa confirmada** — su texto
verbatim contradice la hipótesis de paráfrasis, su página sin tabla
contradice la hipótesis de dilución, y la única explicación con apoyo
real (Evidence Pack de 7 criterios amplios sobre P6/mismo agente) es
INFERENCE, no un hecho verificado sobre el propio P7. Tratarlo como
quinto caso confirmado sería exactamente la sobregeneralización que
`RISK_REGISTER.md` marca como el riesgo transversal más importante de
todo este arco.

**Riesgo de diseño explícito para Cesar**: construir un DOM/EvidenceUnit
para atacar P6/P7 (dilución tabular) es una apuesta razonable dado el
ratio de ruido medido, PERO el precedente de P2/P5 (evidencia perfecta
entregada al modelo y aun así 0/2 de juicio) es una advertencia real de
que aislar la prosa de la tabla podría no mover el resultado si la causa
real de P6/P7 también es un límite del modelo, no de representación. La
única forma de saberlo es el experimento C descrito en `EXPERIMENT_PLAN.md`
— no se debe invertir en construir la representación tabular completa
antes de correr ese experimento barato.

## Qué NO se debe concluir de este documento

- No se concluye que "toda mejora de representación es inútil" — eso
  sería sobregeneralizar el hallazgo de P2/P5 (paráfrasis) a P6/P7
  (dilución), que es una causa estructuralmente distinta y no medida
  todavía.
- No se concluye tampoco que el DOM resolverá P6/P7 — sería lo opuesto,
  sobregeneralizar sin experimento.
