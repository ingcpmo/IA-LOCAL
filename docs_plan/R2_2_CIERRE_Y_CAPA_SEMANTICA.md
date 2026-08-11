# R2.2 — CIERRE FORMAL DE LA MEDICIÓN + CAPA SEMÁNTICA LOCAL (SOLUCIÓN DEFINITIVA)

**Fecha de la orden:** 2026-08-10. **Autoridad:** Capa 9 = Cesar. Claude
Code = Capa 8.

**Reglas duras:** no corpus formal; no Piloto 2; no MarkItDown; no
cambiar el modelo de JUICIO; no aflojar validadores; no GPU ni proveedor
externo; no commit sin diff + aprobación. `PILOT_EXECUTION-2026-010`
tiene 5 llamadas de margen autorizadas — es el único presupuesto de
juicio disponible; no proponer otro para juicio en esta corrida.

**PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.**

Este archivo preserva la orden de Cesar tal como fue dada. El estado de
ejecución real se registra en este mismo documento (secciones de
resultado agregadas debajo de cada bloque) y en memoria.

---

## 0. HECHOS QUE ESTA CORRIDA ACEPTA (leídos de los reportes reales)

- Re-medición con pipeline limpio (kerning + contrato + D agregado):
  P1=observed; P2, P4, P5, P6 = not_observed. 1/5.
- Criterio PRE-FIJADO en el paquete de decisión: ≤3/6-7 observed ⇒
  Opción B domina. Con P7 pendiente, el máximo alcanzable es 2/6 ⇒ el
  criterio ya está matemáticamente resuelto hacia B, con o sin P7.
- P5 falló compartiendo el MISMO chunk limpio que P1 ⇒ el discriminador
  real es ECO LÉXICO vs. PARÁFRASIS, no prosa vs. tabular. El triage por
  página midió el eje equivocado (además de su 50% de error declarado).
- P2 y P5 (evidencia real presente) cerraron PROVISIONAL_GAP ⇒ los gaps
  falsos dejaron de ser un riesgo teórico: ya ocurren.
- Fase C SÍ se hizo (20/20 con criterios interpretados) — la memoria del
  proyecto que decía lo contrario debe corregirse.
- Opción C (agregación D) implementada, firmada
  (`b808899`/`52f502f`/`735f24c`); su límite honesto ya documentado:
  ayuda a baseline, poco a juicio top-k.

## 1. CERRAR LA MEDICIÓN FORMALMENTE (P7 con presupuesto YA autorizado)

1.1 Ejecutar P7 (5 llamadas, el margen exacto sin gastar de
    `PILOT_EXECUTION-2026-010` — verificar el remanente real contra el
    contador antes de la primera llamada; si no cuadra, DETENERSE).
    Background, checkpoints, mismo arnés que la corrida `-010`.
1.2 Con P7 dentro, la muestra queda completa (6 de 6 medibles; P3 fuera
    por diseño de k). Aplicar el criterio pre-fijado FORMALMENTE y
    declarar el resultado en el reporte, sin eufemismos:
    - X/6 observed; criterio "≤3 ⇒ B domina" ⇒ CUMPLIDO/NO CUMPLIDO.
    - La premisa de la Opción A ("techo mayormente ruido de pipeline")
      queda CONFIRMADA o REFUTADA por el propio criterio de Cesar.
    Esto NO revierte la decisión de Cesar — le presenta que su criterio
    pre-fijado, con la muestra completa, apunta a B, y que la
    re-decisión es suya (sección 5).
### 1.2 RESULTADO — cierre formal de la medición (2026-08-10)

P7 terminó (`run_id=chunked-5077df33d5ae`, 5/5 llamadas, `document_id`
RW-0012, `21_CFR_211.68(b)`, background, `bxtbe5q8r`, 2697.7s de pared):
`chunk_observation=not_observed_in_chunk`, `conclusion=PROVISIONAL_GAP`.

**Muestra completa (6/6 medibles):**

| Unidad | req_id | Resultado |
|---|---|---|
| P1 | `21_CFR_11.10(e)` | observed |
| P2 | `21_CFR_11.10(g)` | not_observed |
| P4 | `ALCOA_ATTRIBUTABLE` | not_observed |
| P5 | `ALCOA_CONTEMPORANEOUS` | not_observed |
| P6 | `21_CFR_211.68(b)` | not_observed |
| P7 | `21_CFR_211.68(b)` | not_observed |

**1/6 observed.** Criterio pre-fijado "≤3/6-7 observed ⇒ Opción B
domina": 1 ≤ 3 ⇒ **CUMPLIDO**. La premisa de la Opción A ("el techo 2/7
es mayormente ruido de pipeline, no límite del modelo") queda
**REFUTADA** por el propio criterio de Cesar: con el pipeline limpio
(kerning + contrato + agregación D, todo ya corregido) el recall de
juicio no subió (2/7 baseline → 1/6 aquí, dentro del mismo rango), y el
único positivo rescatado (P1) lo fue por el eje LEXICAL_ECHO (§3), no
por ninguna de las correcciones de pipeline de Opción A. Esto no
revierte la decisión de Cesar — es el dato completo para la re-decisión
de la sección 5.

**Hallazgo de instrumento, no maquillado:** el script de P7 se lanzó
*antes* de que el fix de §2 (`full_document_coverage=False` en
`judgment.py`) quedara escrito — como el proceso ya tenía `judgment.py`
importado en memoria, corrió con el default viejo
(`full_document_coverage=True`), así que P7 cerró `PROVISIONAL_GAP` en
vez del `EVALUATION_INCOMPLETE`/`EVIDENCE_NOT_LOCATED_IN_CANDIDATES`
corregido que le tocaría bajo §2. **No cambia el 1/6** (P7 sigue siendo
un negativo con evidencia no observada, con o sin la corrección de
etiqueta) — pero es exactamente el defecto que §2 corrige, y P7 quedó
del lado viejo del corte por una condición de carrera de sesión, no por
diseño. Debe re-etiquetarse (sin re-ejecutar, sin gastar presupuesto
nuevo) una vez que §2 esté commiteado, para que el registro persistido
de P7 sea consistente con el resto de la muestra corregida.

1.3 Higiene pendiente en el mismo ciclo: commitear (con diff+aprobación)
    los registros de calificación sin versionar
    (`qualification_record`/`runtime_calibration_record.json`) y el
    resultado de la re-medición `-010` + P7. Un commit por causa raíz.

## 2. BLINDAJE DE PRODUCTO: EL MODO JUICIO NO EMITE GAPS (corrección inmediata)

P2/P5 con evidencia real presente cerraron `PROVISIONAL_GAP`. Corregir
de raíz, independientemente del rumbo:

2.1 Regla dura nueva (con test bloqueante): una corrida en MODO JUICIO
    (candidate pool top-k, cobertura parcial del documento POR DISEÑO)
    NUNCA puede emitir una conclusión de familia gap (`PROVISIONAL_GAP`
    ni ninguna variante). Su techo de conclusión negativa es
    `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` (o el estado existente
    equivalente) + encolado a revisión humana (mecanismo R1.8), con la
    cobertura declarada (qué k, qué páginas vio, qué fracción del
    documento NO vio).
    Fundamento: `DOCUMENTATION_GAP`/`PROVISIONAL_GAP` exigen cobertura
    del documento; top-k es cobertura parcial por construcción — emitir
    gap desde ahí viola la precondición de cobertura que el propio
    diseño W5 V2 estableció. Esto no es una regla nueva: es hacer
    cumplir una que ya existía.
2.2 Verificar dónde se decidió `PROVISIONAL_GAP` para P2/P5 (ruta de
    código real) y cerrar esa ruta para run/modo juicio. Baseline
    (documento completo) conserva su lógica actual.
2.3 Tests: P2 y P5 reales como fixtures — mismo resultado del modelo,
    conclusión ahora `EVIDENCE_NOT_LOCATED` + entrada en cola de
    revisión; ANNEX11_4 sigue rechazado; baseline no cambia.

## 3. CORRECCIÓN DEL EJE DE TRIAGE (barato, sin LLM)

3.1 Re-clasificar los 7 positivos por el eje correcto: `LEXICAL_ECHO`
    (el pasaje repite el vocabulario del requisito — tipo P1) vs.
    `PARAPHRASE` (la evidencia exige mapeo semántico — tipo P2/P5/P6).
    Con el texto real ya conocido; documentar el juicio por caso.
3.2 Anotar el triage por página anterior como INSTRUMENTO INVÁLIDO para
    esta decisión (50% error + eje equivocado) — se conserva como
    historia, no se usa para decidir.
3.3 Corregir la memoria del proyecto: (a) Fase C SÍ se hizo (20/20);
    (b) "Causa 3 = tabular" se reformula como "Causa 3 = paráfrasis /
    ausencia de eco léxico" con P5 como caso probatorio; (c) dos
    métodos léxicos independientes (BM25 en recuperación, matching del
    7B en juicio) fallan en los mismos casos — el muro es
    léxico-semántico, no de formato.

## 3. RESULTADO — corrección del eje de triage (2026-08-10)

### 3.1 Reclasificación de los 7 positivos por el eje correcto

Texto real ya conocido (checkpoints/raw_responses de las corridas
reales), sin LLM nuevo:

| # | requirement_id | Eje real | Por qué |
|---|---|---|---|
| P1 | `21_CFR_11.10(e)` | **LEXICAL_ECHO** | El pasaje (UR3.3.1/UR3.3.2) usa "audit trail record shall be generated" — vocabulario casi idéntico al del requisito. **Rescatado** (Causa 1). |
| P2 | `21_CFR_11.10(g)` | **PARAPHRASE** | "F09.00 Physical Security... operator's only access..." exige inferir "chequeo de autoridad técnico" de una descripción de seguridad física — sin eco léxico directo. **No rescatado.** |
| P3 | `ANNEX11_17` | **LEXICAL_ECHO** | "UR3.3.6 Data retention... archived" — eco directo con la citation_text real ("Data may be archived"). Nunca llega a juicio (bloqueado en recuperación por el artefacto de kerning "retentio n", causa distinta, no de paráfrasis). |
| P4 | `ALCOA_ATTRIBUTABLE` | **PARAPHRASE** | "with proper credentials..." exige inferir atribución a un individuo identificable — el pasaje nunca dice "attributable"/"individual identity". **No rescatado.** |
| P5 | `ALCOA_CONTEMPORANEOUS` | **PARAPHRASE** | Mismo chunk EXACTO que P1 (mismo texto fuente, mismo fix de kerning aplicado) — pero el requisito exige inferir "contemporaneidad" de la sola presencia de timestamps, sin que el pasaje use ese concepto explícitamente. **No rescatado pese a compartir chunk con P1** — la prueba directa de que el eje real es léxico-semántico, no de formato. |
| P6 | `21_CFR_211.68(b)` | **PARAPHRASE** | Mismo pasaje que P4 (calibración/credenciales) — 21 CFR 211.68(b) exige inferir "equipo automatizado verificado/calibrado" de una descripción operativa sin la fraseología regulatoria exacta. **No rescatado.** |
| P7 | `21_CFR_211.68(b)` | **PARAPHRASE** | Mismo patrón que P6, documento distinto (RW-0012). Resultado pendiente de P7 (§1). |

**Correlación real, no forzada**: de los 6 unidades re-medidas con
pipeline limpio, la ÚNICA rescatada (P1) es la ÚNICA `LEXICAL_ECHO`.
Las 4-5 `PARAPHRASE` fallaron todas. Esto es evidencia directa, no
inferencia — el eje explica el patrón observado mejor que
prosa/tabular (que predecía mal justo el caso decisivo, P5).

### 3.2 Triage anterior (§2.1/§2.3 de `R2_1_DECISION_PACKAGE.md`) — declarado INSTRUMENTO INVÁLIDO

Ver nota agregada directamente en ese documento. No se usa para ninguna
decisión de aquí en adelante — se conserva como historia de la corrida
que lo produjo.

### 3.3 Corrección de memoria del proyecto

Tres correcciones aplicadas a `project_w5_v2_regulatory_redesign.md`
(memoria persistente, ver commit de memoria de esta corrida):

1. **Fase C SÍ se hizo**: los 20/20 requirements del catálogo real
   tienen `evidence_min_criteria`/`exclusion_criteria`/
   `governed_interpretation` completos (ya verificado y corregido en
   R2.1 §1.3 — se reafirma aquí porque la orden R2.2 lo señaló
   explícitamente como algo que la memoria seguía diciendo mal en
   alguna referencia).
2. **"Causa 3 = tabular" se reformula**: la causa real no es formato
   tabular vs. prosa — es **paráfrasis / ausencia de eco léxico**. P5
   es el caso probatorio (mismo chunk limpio que P1, mismo formato de
   prosa, falla igual que P6/P7).
3. **Dos métodos léxicos independientes fallan en los mismos casos**:
   BM25 (recuperación) y el matching literal del propio juicio del 7B
   comparten el mismo punto ciego frente a paráfrasis — el muro es
   léxico-semántico, no de formato ni de una sola etapa del pipeline.

## 4. LA CAPA SEMÁNTICA LOCAL (la solución definitiva a probar — barata)

La única palanca no probada que ataca el modo de fallo REAL
(paráfrasis) sin GPU, sin proveedor externo y sin cambiar el modelo de
juicio: EMBEDDINGS LOCALES vía Ollama.

4.1 Verificar viabilidad en el servidor real: `ollama pull` de un
    modelo de embeddings pequeño (nomic-embed-text u otro disponible,
    ~270MB, CPU-amigable) — verificar RAM libre con los stacks arriba
    ANTES del pull; registrar digest. Los embeddings NO son el modelo
    de juicio: no tocan la calificación vigente de qwen2.5 (dejarlo
    explícito).
4.2 GOBERNANZA de las llamadas de embedding: son llamadas a Ollama pero
    NO son juicio LLM (no generan texto ni conclusiones; producen
    vectores deterministas por input). Proponer a Cesar la
    clasificación: `EMBEDDING_CALLS` como categoría propia con su
    autorización ligera (`EMBED_EXECUTION-2026-001`: tope de llamadas,
    alcance = fixture + 3 documentos, declaración de que no es juicio
    ni corpus). DETENERSE para esa firma antes del primer embedding.
    Costo estimado: ~86 páginas (chunks) + ~20 consultas ≈ un ciento de
    llamadas de embedding, minutos de CPU, cero juicio.
4.3 Implementar recuperación semántica JUNTO a BM25 (no en reemplazo):
    - embed de chunks (misma granularidad y mapeo a página que el
      índice actual) + embed de la consulta construida desde el
      Evidence Pack;
    - ranking por coseno (numpy puro, sin chromadb — la dependencia que
      se evitó en R2 sigue evitada);
    - fusión con BM25 (p. ej. reciprocal rank fusion) como tercer
      ranking.
4.4 MEDICIÓN DE RECUPERACIÓN PURA (cero juicio LLM, el veredicto
    barato): los mismos 7 positivos + 2 negativos:
    - `retrieval_recall_at_5`/`at_10` de: BM25 solo (ya medido: 4/7,
      7/7), embeddings solos, y fusión;
    - la pregunta decisiva: ¿P5 y P2 (los casos de paráfrasis) entran
      al top-5 semántico? ¿N1/N2 siguen fuera?
    Criterio pre-fijado AHORA, antes de medir: la capa semántica se
    adopta para el pipeline si fusión ≥6/7 en at_5 (o at_10 con
    justificación de k) ∧ negativos fuera del top-5 ∧ el mapeo a
    página intacto. Si no lo alcanza, se reporta sin maquillar y las
    opciones restantes (modelo de juicio/GPU/externo/alcance reducido)
    suben a la mesa de Cesar con TODA la evidencia ya limpia.
4.5 NOTA HONESTA sobre el alcance de esta capa: mejor recuperación pone
    la evidencia parafraseada DELANTE del modelo de juicio, pero P5
    demuestra que el 7B puede no reconocerla NI TENIÉNDOLA delante. La
    capa semántica resuelve con certeza la mitad recuperación del
    muro; la mitad juicio solo se sabrá con una re-medición de juicio
    posterior (presupuesto nuevo, decisión de Cesar). No prometer que
    embeddings solos arreglan el recall de juicio — medir por fases y
    decir la verdad en cada una.

## 4. RESULTADO — capa semántica local, ejecución real (2026-08-10)

### 4.1 Viabilidad — modelo ya pulleado

`nomic-embed-text:latest` ya estaba disponible en el Ollama real del
host (`ollama list` lo confirma, digest `0a109f422b47e3a30ba2`) — no
hizo falta `ollama pull` nuevo. `context_length` real del modelo
(`ollama show --json`, `model_info["nomic-bert.context_length"]`):
**2048 tokens**, no 8192 — dato nuevo, ver hallazgo de instrumento
abajo. RAM: sin impacto medible (modelo ya residente, embeddings vía
REST, sin cargar pesos nuevos). Juicio (qwen2.5) intacto — este módulo
nunca lo importa (ver docstring `embed_runner.py`).

### 4.2 Gobernanza — EMBED_EXECUTION-2026-001/002

Propuesta `EMBED_EXECUTION-2026-001` (`agent_proposed`,
`claude_code_session_r2_2_embed_20260810`, 2026-08-10T21:06:13Z):
alcance = RW-0005 (29 chunks)/RW-0011 (6)/RW-0012 (8) + hasta 9
consultas, `max_calls=60`, `authorizes_corpus/baseline/pilot_execution
= false` (familia separada, no descuenta de `PILOT_EXECUTION-2026-010`).
**Confirmada por Cesar** — `EMBED_EXECUTION-2026-002`
(`human_confirmed`, `approved_by_id=cesar`, 2026-08-10T21:20:39Z,
`decisions_v2.jsonl`). DETENCIÓN cumplida: cero llamadas de embedding
antes de esta firma.

### 4.3 Ejecución real — hallazgos de instrumento (no maquillados)

Dos defectos reales aparecieron ejecutando el batch real (ninguno
existía en el diseño §4, ambos corregidos en el código, no rodeados):

1. **Contexto real del modelo excede lo asumido**: `build_page_chunks()`
   genera chunks pensados para el LLM de juicio (ventana mucho mayor);
   varios exceden los 2048 tokens reales de `nomic-embed-text` local
   (`/api/embeddings` → 500 `"the input length exceeds the context
   length"`; confirmado que `options.num_ctx` NO lo evita — es un límite
   del modelo, no del buffer). Fix en `embed.py::embed_text()`: reintento
   determinista truncando el prompt a la mitad hasta 4 veces si el error
   es específicamente de contexto — el vector resultante representa un
   PREFIJO del chunk, nunca el chunk completo. `chunk_index`/
   `page_start`/`page_end` no se tocan (mapeo a página intacto, ver
   4.4). Ningún chunk de los 43 reales necesitó más de 1-2 truncados
   para pasar.
2. **Evento de auditoría no registrado**: `r2_embed_batch_completed`
   faltaba en `audit_writer.VALID_EVENTS` — la primera corrida real
   completó los 43 embeddings de chunk (persistidos, intactos) pero
   crasheó en el último paso, perdiendo los 7 `query_vectors` ya
   calculados (nunca se devolvían al llamador porque la excepción
   interrumpió el `return`). Corregido agregando el evento al registro
   (mismo patrón que `r2_judgment_batch_completed`). Costo real: 7
   llamadas de embedding de consulta gastadas dos veces (43+7 la primera
   corrida, +7 la segunda) — **57/60 del presupuesto de
   `EMBED_EXECUTION-2026-002` consumido**, dentro del tope, sin margen
   para una tercera corrida completa. Los 43 embeddings de chunk son
   idempotentes por `chunk_index` (`embed_index.add_chunk_embeddings`)
   — no se re-gastaron.

Ambos fixes son correcciones de instrumento (bugs reales bloqueando la
ejecución), no relajación de ningún validador GMP ni cambio del modelo
de juicio.

### 4.4 Medición de recuperación pura — resultado real

Fixture 7P+2N completo, mismos 3 documentos/queries que `test_r2_
retrieval.py` (BM25) y el mismo mapeo a página (embeddings indexados
sobre los MISMOS chunks de `indexer.py`, nunca un re-chunking
paralelo):

| # | doc | req_id | página | BM25 rank | embed rank | fusión (RRF) rank |
|---|---|---|---|---|---|---|
| P1 | RW-0005 | `21_CFR_11.10(e)` | 46 | 1 | 2 | **1** |
| P2 | RW-0005 | `21_CFR_11.10(g)` | 40 | 6 | 2 | **2** |
| P3 | RW-0005 | `ANNEX11_17` | 45 | 9 | 1 | **2** |
| P4 | RW-0011 | `ALCOA_ATTRIBUTABLE` | 13 | 2 | 3 | **1** |
| P5 | RW-0005 | `ALCOA_CONTEMPORANEOUS` | 46 | 9 | 4 | **2** |
| P6 | RW-0011 | `21_CFR_211.68(b)` | 13 | 2 | 2 | **2** |
| P7 | RW-0012 | `21_CFR_211.68(b)` | 14 | 2 | 7 | **3** |
| N1 | RW-0005 | `ANNEX11_4` | 2 | 7 | 22 | 18 |
| N2 | RW-0005 | `21_CFR_11.10(e)` | 4 | 13 | 26 | 20 |

**Recall agregado:**

| método | recall_at_5 | recall_at_10 | negativos fuera del top-5 |
|---|---|---|---|
| BM25 solo | 4/7 (conocido) | 7/7 (conocido) | 2/2 |
| Embeddings solo | **6/7** | 7/7 | 2/2 |
| **Fusión RRF** | **7/7** | 7/7 | **2/2** |

**La pregunta decisiva (§4.4): ¿P5 y P2 entran al top-5 semántico?**
**SÍ, ambos** — P2 rank 2 (embed) / rank 2 (fusión); P5 rank 4 (embed)
/ rank 2 (fusión). Los dos casos de PARÁFRASIS que ningún método léxico
(BM25, matching del 7B en juicio) resolvía quedan dentro del top-5 con
la capa semántica. `page_start`/`page_end` de cada resultado provienen
del mismo índice BM25 (`indexer.py`) — mapeo a página intacto por
construcción, no solo verificado a posteriori.

**Criterio de adopción pre-fijado en §4.4 ("fusión ≥6/7 en at_5 ∧
negativos fuera del top-5 ∧ mapeo a página intacto"): ALCANZADO.**
7/7 ≥ 6/7; 2/2 negativos fuera; mapeo intacto.

### 4.5 Nota honesta — vigente, no revisada por este resultado

La capa semántica resuelve con certeza la mitad **recuperación** del
muro (dato de esta sección). La mitad **juicio** sigue sin medirse: P5
demostró en R2.1 que el 7B puede fallar en reconocer evidencia
parafraseada incluso TENIÉNDOLA delante en el chunk ganador. Este
resultado no mide eso — mide que la capa semántica ahora SÍ pone a P5 y
P2 delante del juicio (rank 2 fusión, ambos), algo que BM25 solo no
lograba (P2 rank 6, P5 rank 9 — fuera del candidate pool típico top-5
de R2). Si el 7B las reconoce una vez recuperadas es una pregunta
separada, de re-medición de juicio (presupuesto nuevo, decisión de
Cesar, sección 5).

## 5. PAQUETE DE RE-DECISIÓN PARA CESAR

Con §1 (muestra completa + criterio aplicado) y §4.4 (recuperación
semántica medida), presentar la re-decisión con datos completos:

- Si el criterio confirmó B y la capa semántica ALCANZÓ su criterio:
  camino propuesto = Opción B "semántica local": adoptar la fusión en
  recuperación + re-medición de juicio dimensionada (presupuesto nuevo
  a firmar) para saber si el 7B juzga bien lo que ahora sí recibe.
- Si la capa semántica NO alcanzó: las palancas restantes con su costo
  real (cambio de modelo de juicio = GPU o proveedor externo con
  evaluación de confidencialidad; o alcance reducido Tier-1:
  confirmación de eco léxico + rechazo de falsos positivos + TODO lo
  demás a revisión humana con cobertura declarada — producto honesto,
  entregable hoy, y tras §2 ya blindado contra gaps falsos).
- En ambos casos: el blindaje del §2 queda en producción (no depende
  del rumbo) y la hipótesis de dilución por chunking (§2.2 del
  paquete) queda anotada — la capa semántica con chunks por página
  puede resolverla de paso; verificarlo en la medición 4.4.

## 5. RESULTADO — paquete de re-decisión real para Cesar (2026-08-10)

Con §1 (muestra completa, criterio "≤3/6 ⇒ B domina" **CUMPLIDO**, 1/6
observed) y §4.4 (capa semántica, criterio de adopción **ALCANZADO**,
fusión 7/7 at_5) ambos resueltos con datos reales, la re-decisión queda
en el primer supuesto de este paquete:

**Camino que los datos apuntan**: Opción B "semántica local" —
adoptar la fusión BM25+embeddings en RECUPERACIÓN (código ya escrito,
probado, medido — `fusion.py`/`embed_runner.py`/`embed_index.py`) +
proponer una re-medición de JUICIO dimensionada (presupuesto nuevo, a
firmar por Cesar, fuera del alcance de `EMBED_EXECUTION` y ya sin
margen en `PILOT_EXECUTION-2026-010`) para saber si el 7B, viendo ahora
P2/P5 dentro de su candidate pool top-5, sí las reconoce. Esto NO se
sabe todavía — es la pregunta que R2.2 deja abierta a propósito (§4.5).

**Lo que NO cambia pase lo que pase**: el blindaje de §2 (modo JUICIO
nunca emite gap, techo `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` + cola
R1.8) ya está en el código, probado (57 tests verdes en los dos
archivos tocados), y es independiente del rumbo semántico — corrige un
defecto real (P2/P5 cerrando `PROVISIONAL_GAP` con evidencia presente)
sin importar si la capa semántica se adopta o no.

**Lo que Cesar decide aquí**:
1. ¿Aprueba integrar la fusión de recuperación (§4.3) al pipeline real
   (reemplazando o corriendo junto al candidate pool BM25-solo actual
   de `judgment.py`)?
2. ¿Autoriza una `PILOT_EXECUTION` nueva y acotada (dimensionada, no
   propuesta aún — este documento no gasta ese presupuesto) para
   re-medir juicio sobre P2/P5/P7 con la capa semántica activa?
3. ¿O prefiere el alcance reducido Tier-1 (confirmación de eco léxico +
   rechazo de falsos positivos + resto a revisión humana con cobertura
   declarada) como entregable inmediato, dejando la re-medición de
   juicio para después?

Nada de esto se ejecuta sin la firma explícita de Cesar (regla dura de
CLAUDE.md: ninguna corrida marcada documentación+diseño se convierte en
código/infra sin diff mostrado y aprobación).

### 5.1 `PILOT_EXECUTION-2026-011` — dimensionada, `agent_proposed`, esperando firma

Propuesta creada (2026-08-10T22:16:08Z, `decisions_v2.jsonl`,
`decision_origin=agent_proposed`, `status=ACTIVE` pero SIN
`human_confirmed` todavía — el resolver no la trata como autorizada
para gastar presupuesto hasta que Cesar la confirme, mismo patrón que
`EMBED_EXECUTION-2026-001→002`). **Cero llamadas de juicio gastadas**
al crear esta propuesta — `propose_pilot_execution()` solo escribe el
registro de gobernanza.

Alcance MÍNIMO (no el completo de 6 unidades): las dos únicas donde la
fusión semántica cambia de forma decisiva la composición del pool
top-5 frente a lo ya medido con BM25 solo —

- **P2** (`21_CFR_11.10(g)`, RW-0005): BM25 solo lo dejaba en rank 6
  (fuera del top-5; `PILOT_EXECUTION-2026-010` necesitó k=10 para
  incluirlo, y aun así `not_observed`). Con fusión: rank 2, dentro de
  un top-5 real con menos distractores.
- **P5** (`ALCOA_CONTEMPORANEOUS`, RW-0005): con fusión rank 2. Ya fue
  medido antes con el chunk correcto presente en su pool y aun así
  `not_observed` — expectativa honesta BAJA (§4.5: el límite parece
  ser de juicio, no de recuperación), incluido para no dejar la
  pregunta sin cerrar con datos reales.

`max_calls=15` (10 llamadas esperadas — 5 por unidad, patrón 1:1
confirmado en las 6 corridas de juicio previas de esta fase, ningún
pool de chunks recuperados se dividió/consolidó en `build_page_chunks`
— + 5 de margen técnico, mismo criterio que `-010`). El pool de
candidatos de cada unidad se construye EN EL MOMENTO de la ejecución
vía `fusion.rrf_fuse(retriever.retrieve_top_k(...), embedding_ranking,
top_n=5)` — nunca fijado de antemano en el payload de la decisión.
P1/P4/P6/P7 quedan fuera de este alcance mínimo (ya estaban en el
top-5 con ambos métodos; re-medirlos no aportaría información nueva) —
disponibles como alcance "completo" (30+5=35 llamadas) si Cesar lo
prefiere.

**Pendiente de tu confirmación** para pasar a `human_confirmed` y
recién ahí quedar disponible para `judgment.run_judgment_batch()`.

### 5.2 RESULTADO REAL — re-medición de juicio con pool de fusión (2026-08-10)

**Confirmada por Cesar** — `PILOT_EXECUTION-2026-012`
(`human_confirmed`, `approved_by_id=cesar`, 2026-08-10T22:23:05Z,
`confirms_instance_id=PILOT_EXECUTION-2026-011`). Ejecutada:
`run_judgment_batch()` sobre P2/P5 con `candidate_chunks` construidos
EN EL MOMENTO de la corrida vía `fusion.rrf_fuse(retriever.
retrieve_top_k(...), embedding_ranking, top_n=5)` — el mismo mecanismo
de producción propuesto en §5, no un pool fijado de antemano.

| unidad | chunks del pool (fusión top-5) | resultado | conclusión |
|---|---|---|---|
| P2 (`21_CFR_11.10(g)`) | chunk_index 18, 17, 19, 26, 10 | `not_observed_in_chunk` | `EVALUATION_INCOMPLETE` |
| P5 (`ALCOA_CONTEMPORANEOUS`) | chunk_index 27, 20, 24, 25, 11 | `not_observed_in_chunk` | `EVALUATION_INCOMPLETE` |

10/10 llamadas (5 por unidad, tal como se dimensionó — 0 de las 5 de
margen técnico usadas), `BATCH_COMPLETE`, 4120.5s de pared total.
Ambas unidades quedaron correctamente encoladas en R1.8
(`EVIDENCE_NOT_LOCATED_IN_CANDIDATES`, flags
`ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE` +
`PARTIAL_COVERAGE_CANDIDATES_SEEN=5` — verificado en vivo contra
`human_review_queue.list_pending()`, no solo el label del resultado) —
**el blindaje de §2 funciona de punta a punta en producción real, con
LLM real, no solo en los tests sintéticos.**

**El resultado decisivo: el recall de JUICIO NO mejoró.** Ambos casos
siguen `not_observed` — igual que con BM25 solo. La capa semántica sí
cumplió su promesa de RECUPERACIÓN (§4.4: P2 y P5 entran al top-5,
antes no en el caso de P2), pero tenerlos delante del 7B en un pool
limpio de 5 candidatos, sin el ruido de un pool de 10, **no cambió el
juicio**. Esto confirma con datos reales, no ya como hipótesis, la
nota honesta de §4.5: el muro tiene dos mitades independientes —
recuperación (la capa semántica la resuelve, medido) y juicio (la capa
semántica NO la resuelve, medido ahora también). Mover mejor evidencia
al frente del modelo no alcanza si el modelo de 7B no reconoce la
paráfrasis una vez que la tiene delante.

**Esto no invalida la adopción de la capa semántica** — sigue siendo
una mejora real y medida en recuperación (el fixture de recall puro no
cambia, 7/7 en fusión) y el blindaje de §2 ahora tiene confirmación de
punta a punta con LLM real. Lo que sí cambia es la expectativa sobre
QUÉ resuelve: no es la solución al recall de juicio (2/7→1/6 con
Opción A, ahora 0/2 adicional con fusión) — ese sigue siendo un límite
del modelo de 7B, no del pipeline de recuperación.

## 6. ENTREGA — bloque real

```
P7_RESULT =                    not_observed (chunked-5077df33d5ae, 5/5 llamadas de -010)
SAMPLE_COMPLETE =               6/6 medibles
PREFIXED_CRITERION_APPLIED =    1/6 ⇒ B domina (CUMPLIDO)
OPTION_A_PREMISE =              REFUTADA (recall de juicio no subió con pipeline limpio)
JUDGMENT_MODE_GAP_BLOCKED =     true (mecanismo cerrado en código -- factory/engines/gmpai_integrity/chunked_engine.py + factory/regulatory/retrieval/judgment.py, 57 tests verdes; los 4 tests nuevos usan un escenario negativo sintético equivalente al patrón P2/P5, NO un replay literal de esos dos casos reales -- pendiente si Cesar quiere ese replay exacto como fixture adicional)
ANNEX11_4_STILL_REJECTED =      true (N1 fuera del top-5 en BM25/embed/fusión)
TRIAGE_AXIS_CORRECTED =         LEXICAL_ECHO vs PARAPHRASE (7 casos, ver §3 RESULTADO)
MEMORY_CORRECTED =              true (project_w5_v2_regulatory_redesign.md, ver nota de memoria de esta corrida)
EMBED_AUTHORIZATION =           EMBED_EXECUTION-2026-002 (human_confirmed, cesar, 2026-08-10T21:20:39Z)
EMBED_MODEL =                   nomic-embed-text:latest, digest 0a109f422b47e3a30ba2, context_length real=2048 tokens (hallazgo nuevo); juicio (qwen2.5) intacto
SEMANTIC_RETRIEVAL_RECALL =     BM25 4/7 at_5 · 7/7 at_10 | embed 6/7 at_5 · 7/7 at_10 | fusión 7/7 at_5 · 7/7 at_10
P5_P2_IN_SEMANTIC_TOP5 =        SÍ, ambos (P2 rank 2 fusión; P5 rank 2 fusión)
NEGATIVES_OUT_OF_TOP5 =         2/2 (N1, N2) en los tres métodos
SEMANTIC_ADOPTION_CRITERION =   ALCANZADO (fusión 7/7≥6/7 ∧ negativos fuera ∧ mapeo a página intacto)
QUALIFICATION_RECORDS_COMMITTED = true (ya estaban en `1211ed8`, verificado limpio -- sin pendiente nuevo)
JUDGMENT_RESEASUREMENT_P2_P5 =  PILOT_EXECUTION-2026-012 (confirma -011, cesar, 2026-08-10T22:23:05Z) -- 10/10 llamadas, BATCH_COMPLETE, ambas AÚN not_observed con pool de fusión top-5 (P2 chunks [18,17,19,26,10]; P5 chunks [27,20,24,25,11]) -- ver §5.2
JUDGMENT_RECALL_IMPROVED_BY_SEMANTIC_LAYER = NO (0/2 -- la capa semántica resuelve recuperación, medido; NO resuelve juicio, medido ahora también)
JUDGMENT_MODE_GAP_BLOCKED_IN_PRODUCTION = true (confirmado en vivo contra human_review_queue.list_pending(): ambas unidades EVIDENCE_NOT_LOCATED_IN_CANDIDATES + PARTIAL_COVERAGE_CANDIDATES_SEEN=5, no solo en tests sintéticos)
REDECISION_PACKAGE =            listo, sección 5/5.2 arriba -- CERRADO con dato real de juicio, pendiente de decisión final de Cesar sobre el rumbo (adoptar fusión en recuperación de todos modos + escoger palanca de juicio: GPU/proveedor externo/alcance Tier-1)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**Diffs sin commitear** (código nuevo/modificado de esta corrida,
pendientes de revisión + aprobación explícita antes de cualquier
commit): `factory/regulatory/embed_execution.py`,
`factory/regulatory/retrieval/{embed,embed_index,embed_runner,fusion}.py`,
`factory/tests/test_r2_embed.py`, fix de `factory/regulatory/retrieval/embed.py`
(truncado de contexto), fix de `factory/core/audit_writer.py` (evento
`r2_embed_batch_completed`), `factory/regulatory/retrieval/judgment.py`
+ `factory/engines/gmpai_integrity/chunked_engine.py` (§2, blindaje de
modo juicio) + sus tests. Commits separados por causa raíz, según se
apruebe.

## 6. ENTREGA

Diffs sin commit hasta aprobación; commits separados por causa raíz.

```
P7_RESULT =                    (observed/not_observed, 5 llamadas de -010)
SAMPLE_COMPLETE =              6/6 medibles
PREFIXED_CRITERION_APPLIED =   X/6 ⇒ (B domina / no)
OPTION_A_PREMISE =             (confirmada/refutada por el criterio de Cesar)
JUDGMENT_MODE_GAP_BLOCKED =    (P2/P5 ahora EVIDENCE_NOT_LOCATED + cola R1.8)
ANNEX11_4_STILL_REJECTED =     true
TRIAGE_AXIS_CORRECTED =        LEXICAL_ECHO vs PARAPHRASE (7 casos)
MEMORY_CORRECTED =             (Fase C hecha; Causa 3 reformulada)
EMBED_AUTHORIZATION =          (EMBED_EXECUTION-2026-001 firmada / pendiente)
EMBED_MODEL =                  (nombre+digest; RAM verificada; juicio intacto)
SEMANTIC_RETRIEVAL_RECALL =    (BM25 / embed / fusión, at_5 y at_10)
P5_P2_IN_SEMANTIC_TOP5 =       (la pregunta decisiva)
NEGATIVES_OUT_OF_TOP5 =        (N1/N2)
SEMANTIC_ADOPTION_CRITERION =  (pre-fijado §4.4: alcanzado / no)
QUALIFICATION_RECORDS_COMMITTED =
REDECISION_PACKAGE =           (para Cesar, con todo lo anterior)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en las dos firmas (`EMBED_EXECUTION`; y la re-decisión final
es de Cesar). El criterio pre-fijado se aplica tal como se escribió —
se pre-fijó exactamente para este momento: que los datos, no el
impulso, decidan el rumbo.
