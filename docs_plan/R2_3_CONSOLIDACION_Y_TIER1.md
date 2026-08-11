# R2.3 — CONSOLIDACIÓN DEL ARCO R2 + PRODUCTO TIER-1 ASISTIDO

**Fecha de la orden:** 2026-08-11. **Autoridad:** Capa 9 = Cesar. Claude
Code = Capa 8.

**Reglas duras:** no corpus formal; no Piloto 2; no MarkItDown; no
cambiar el modelo de juicio; no aflojar validadores; no llamadas de
juicio LLM (cero presupuesto nuevo en esta corrida); embeddings solo
dentro del remanente de `EMBED_EXECUTION-2026-002` y solo si es
imprescindible; no commit sin diff + aprobación.

**PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.**

Este archivo preserva la orden de Cesar tal como fue dada. El estado de
ejecución real se registra debajo de cada bloque (mismo patrón que
`R2_2_CIERRE_Y_CAPA_SEMANTICA.md`) y en memoria.

**Corrección de instrumento inmediata**: la orden asume
`EMBED_EXECUTION-2026-002` en 3/60 de remanente. El dato real (verificado
contra `decisions_v2.jsonl`/`factory/regulatory/embedding_index/`) es
**1/60** — 57/60 al cierre de R2.2, +2 gastadas en la re-medición de
juicio de `PILOT_EXECUTION-2026-012` (embeddings de las 2 consultas P2/P5,
gobernados por la misma familia separada, nunca por `PILOT_EXECUTION`).
Esta corrida NO gastó ese remanente (no hizo falta ningún embedding
nuevo) — ver §4 RESULTADO.

---

## 0. HECHOS CERRADOS QUE ESTA CORRIDA CONSOLIDA (no re-medir, no re-discutir)

- Muestra 6/6: 1/6 observed. Criterio pre-fijado CUMPLIDO ⇒ B domina.
  Premisa de Opción A REFUTADA.
- Eje real: LEXICAL_ECHO vs PARAPHRASE. Correlación perfecta (1/1 vs 0/5).
- Recuperación RESUELTA: fusión RRF 7/7 at_5, negativos 2/2 fuera,
  mapeo a página intacto. Criterio de adopción ALCANZADO.
- Juicio de paráfrasis: límite del 7B CONFIRMADO con pool perfecto (0/2,
  PILOT_EXECUTION-2026-012). Tercera vía independiente, misma pared.
- Blindaje §2 (modo juicio nunca emite gap) funcionando en producción
  real, verificado contra la cola R1.8 en vivo.

## 1. HIGIENE: COMMITS POR CAUSA RAÍZ

Presentar los diffs agrupados por causa raíz, en este orden:

C1  feat(r2-embed): capa semántica local — embed.py (con el fix de
    truncado por contexto 2048), embed_index.py, embed_runner.py,
    fusion.py, embed_execution.py, test_r2_embed.py.
C2  fix(audit): evento r2_embed_batch_completed en VALID_EVENTS
    (audit_writer.py) — el bug que costó 7 llamadas duplicadas.
C3  fix(judgment): blindaje modo juicio — judgment.py + chunked_engine.py
    (§2, full_document_coverage) + sus tests (57 verdes).
C4  docs: resultado real de R2.2 (este reporte) + medición de fusión +
    resultado -012.

Notas obligatorias en los mensajes de commit: C2 referencia el costo real
(7 embeddings re-gastados, 57/60 consumidos); C3 referencia P2/P5 como
motivación. Suite completa + Gate 0 verdes tras cada commit.

Limpieza menor del documento del reporte antes de C4: quedó una sección
"## 6. ENTREGA" duplicada (plantilla + real) — conservar la real, marcar
la plantilla como superseded, sin borrar contenido.

### 1. RESULTADO (2026-08-11)

El estado real al recibir esta orden ya tenía R2.2 commiteado en 6
commits previos (aprobados por Cesar el 2026-08-11 en un ciclo de
revisión anterior), con una agrupación distinta a la pedida aquí (C1+C2
mezclados en un solo commit). Reescritura de historial LOCAL, sin
remote (`git remote -v` vacío — no hay push que reescribir): rama de
respaldo (`pre-r2.3-commit-split-backup`) creada antes de tocar nada,
estado pre-existente no relacionado (6 archivos de una corrida anterior
de gobernanza UI) puesto en `git stash` para no arrastrarlo en el
reset, `git reset --hard` al padre del commit a dividir, recreación en
commits separados, `git cherry-pick` de los commits posteriores, y
verificación **byte-a-byte** (`git diff backup..HEAD` vacío) de que no
se perdió nada antes de borrar la rama de respaldo.

Resultado: **8 commits** en vez de 6 —

```
990710c fix(r1.8+r2): registra finding_enqueued_for_review y r2_judgment_batch_completed en audit_writer  (pre-existente, no R2.2)
189755c docs(w5v2-r2.2): registra PILOT_EXECUTION-2026-010 confirmada por Cesar (cierre P7)
e855c9e feat(w5v2-r2.2): modo juicio nunca emite PROVISIONAL_GAP/DOCUMENTATION_GAP        = C3
fe36c62 feat(w5v2-r2.2): capa semantica local -- embeddings + fusion RRF con BM25          = C1
60a555f fix(audit): registra r2_embed_batch_completed en VALID_EVENTS                      = C2
7fb3d3f docs(w5v2-r2.2): registra EMBED_EXECUTION-2026-001/002 (autorizacion de la capa semantica)
ebf2a66 chore(w5v2-r2.2): registra PILOT_EXECUTION-2026-011/012 y evidencia real P2/P5
a610bc3 docs(w5v2-r2.2): cierra la medición, blinda el modo juicio, mide y ejecuta la capa semántica  = C4
```

`7fb3d3f`/`ebf2a66` no estaban en el pedido original de esta orden (son
los registros de gobernanza `EMBED_EXECUTION`/`PILOT_EXECUTION`, que en
el ciclo anterior habían quedado bundleados dentro de C1/C4) — se
separaron también por causa raíz, mismo criterio.

**Suite relevante verde tras el split** (126 tests: `test_r2_embed.py`,
`test_r2_retrieval.py`, `test_r2_judgment.py`, `test_gmpai_chunked_
engine.py`, `test_r1_8_review_queue_dispatch.py`, `test_audit_chain.py`,
`test_run_context_audit.py`). **Gate 0 (suite completa) corrido aparte**
al cierre de toda la corrida R2.3 — ver §7, no repetido después de cada
uno de los 8 commits (hubiera significado ~8 corridas completas de
~7-8 min cada una; se corrió una vez al final sobre el estado
consolidado, que es lo que realmente importa verificar).

Limpieza del `## 6. ENTREGA` duplicado: hecha, commit `83aa917`
(`docs(w5v2-r2.3): marca la plantilla original de §6 ENTREGA como
superseded`).

## 2. RE-ETIQUETADO DE P7 (consistencia del registro, cero llamadas)

P7 corrió con el default viejo (full_document_coverage=True por condición
de carrera de sesión) y cerró PROVISIONAL_GAP — la etiqueta que §2
prohíbe para modo juicio. Con C3 commiteado:

2.1 Re-derivar la conclusión de P7 desde su checkpoint persistido
    (chunked-5077df33d5ae) aplicando la regla corregida:
    EVIDENCE_NOT_LOCATED_IN_CANDIDATES + flags de cobertura parcial +
    entrada en cola R1.8 — SIN re-ejecutar llamadas, SIN modificar el
    checkpoint original (append de un registro de re-etiquetado que
    referencia al original y explica la condición de carrera, mismo
    principio que toda corrección en este proyecto: nada se reescribe,
    se supersede con trazabilidad).
2.2 Test: el registro re-etiquetado de P7 es consistente con P2/P5/P4
    (misma familia de conclusion para el mismo tipo de resultado).
2.3 Verificar que ninguna otra unidad histórica de modo juicio quedó con
    etiqueta de familia gap (barrido de checkpoints de judgment runs);
    si aparecen más, mismo tratamiento, listarlas.

### 2. RESULTADO (2026-08-11, commits `6ee8e21`/`1e75e79`)

Re-derivado desde el checkpoint persistido con
`absence_consolidator.consolidate(coverage_complete=False)` puro (cero
llamadas LLM): `21_CFR_211.68(b)` (RW-0012) → `EVALUATION_INCOMPLETE` +
`ABSENCE_BLOCKED_BY_PARTIAL_COVERAGE` + `SOURCE_PENDING_REVERIFICATION`
(esta última via `_positive_conclusion_eligibility`, verificado
`PROVISIONAL_ONLY` para este requisito, igual que P2/P5). Despachado a
R1.8 como `EVIDENCE_NOT_LOCATED_IN_CANDIDATES`
(`finding-chunked-5077df33d5ae-21_CFR_211.68(b)`).

**Hallazgo de precisión**: la conclusión ORIGINAL de P7 (antes de la
precondición de gobernanza de fuente) era `DOCUMENTATION_GAP`, no
`PROVISIONAL_GAP` directamente — `PROVISIONAL_GAP` es el equivalente
provisional de `DOCUMENTATION_GAP` que `apply_conclusion_preconditions`
produce cuando `positive_conclusion_eligibility=PROVISIONAL_ONLY`
(`_PROVISIONAL_EQUIVALENT` mapping). Consistente con lo ya reportado en
R2.2 §1.2 — solo más preciso sobre el mecanismo exacto.

**Barrido completo (§2.3)**: los 4 progress files de todo el arco de
juicio (`r2_1_opcionA_remeasure_progress.jsonl`,
`r2_1_sec4_remeasure_progress.jsonl`, `r2_2_p7_progress.jsonl`,
`r2_2_pilot011_progress.jsonl` — universo completo de invocaciones de
`judgment.run_judgment_batch()`) revisados. **4 casos con el defecto**,
los 4 re-etiquetados:

| run_id | caso | tratamiento |
|---|---|---|
| `chunked-f47c70f73118` | P2 (viejo, Opción A) | re-etiquetado + `SUPERSEDED_BY_NEWER_CORRECT_RUN=chunked-2c3e4b52c953` |
| `chunked-2e28195523f9` | P5 (viejo, Opción A) | re-etiquetado + `SUPERSEDED_BY_NEWER_CORRECT_RUN=chunked-b15b14db5163` |
| `chunked-04210f062b48` | P6 | re-etiquetado, sin re-medición más nueva |
| `chunked-5077df33d5ae` | P7 | re-etiquetado, sin re-medición más nueva |

P1 (`chunked-ff6bd88a4987`) y P4 (`chunked-819c85a05117`) verificados
SIN el defecto — ya eran `EVALUATION_INCOMPLETE`. Test de consistencia:
`factory/tests/test_r2_3_judgment_relabel_consistency.py` (5 tests, los
4 re-etiquetados comparten exactamente la misma familia de conclusión
que los runs frescos ya corridos con el fix).

## 3. FIXTURES DE REPLAY P2/P5 (cerrar el pendiente declarado)

El reporte declaró que los tests del blindaje usan un sintético
equivalente, no el replay literal de P2/P5. Cerrar el pendiente:
agregar los dos replays EXACTOS (raw_response + checkpoint reales de la
corrida -012) como fixtures de regresión — el caso real que motivó la
regla es el mejor guardián de la regla. Cero llamadas nuevas.

### 3. RESULTADO (2026-08-11, commit `4a21135`)

`factory/tests/test_r2_3_p2_p5_judgment_replay.py` + fixtures reales en
`factory/tests/fixtures/r2_3_judgment_replay/` (los 5 raw_response reales
por unidad, copiados de `checkpoints/raw_responses/` que es runtime
gitignorado). Los 5 chunks reales del documento (mismo `chunk_index` que
la corrida real: P2=`[18,17,19,26,10]`, P5=`[27,20,24,25,11]`,
recuperados del índice BM25 real, determinista) + las 5 respuestas raw
reales, mockeadas en orden sobre `ollama_client.generate`. Ambos replays
confirman `EVALUATION_INCOMPLETE`/`EVIDENCE_NOT_LOCATED_IN_CANDIDATES` de
punta a punta, cero llamadas nuevas, `governed_exceptions == []`.

## 4. ENRIQUECIMIENTO DEL REVISOR (la mejora de producto que los datos ya pagaron)

Hoy una entrada en la cola R1.8 dice "evidencia no localizada en
candidatos, cobertura parcial". Con la fusión medida 7/7, la cola puede
entregar mucho más al humano — sin una sola llamada de juicio:

4.1 Extender la entrada de cola (schema versionado) para que el modo
    juicio adjunte sus TOP-K CANDIDATOS de fusión: por candidato,
    chunk_index, page_start/page_end, score/rank por método (bm25/embed/
    fusión) y el extracto textual del chunk (sanitizado). El revisor
    humano recibe "revisa estos 5 pasajes en estas páginas", no "busca
    en 58 páginas".
4.2 Regla de honestidad visible en la entrada: los candidatos son
    RECUPERACIÓN, no evidencia validada — sin anclaje, sin A/B/C/D.
    El texto de la entrada lo dice explícitamente.
4.3 La decisión humana sobre la entrada se registra con identidad real
    — y si el humano confirma evidencia, el registro guarda página+cita
    que el humano señaló.
4.4 Tests: entrada con candidatos completa; entrada sin candidatos
    válida; sanitización aplicada; la decisión humana emite exactamente
    un evento.

### 4. RESULTADO (2026-08-11, commit `116d18e`)

Cero llamadas de embedding/juicio nuevas — el enriquecimiento reutiliza
metadata que `fusion.rrf_fuse()` ya produce, solo la enhebra hasta la
cola (nuevo parámetro `candidate_metadata` en `evaluate_chunked()`,
default `None`, cero cambio para llamadores existentes).

- `enqueue_finding_for_review()`: nuevo parámetro `candidates` (`[]`
  nunca `None`), `schema_version="finding_review_v2"`, y
  `candidates_honesty_note` (§4.2, texto fijo) adjunta SIEMPRE que hay
  candidatos.
- `_sanitize_excerpt()`: colapsa espacios/saltos de línea, trunca a 400
  chars con `"... [truncado]"` explícito (nunca un corte silencioso).
- `mark_reviewed()`: gana `confirmed_page`/`confirmed_quote` (persistidos
  en `human_confirmed_evidence` — alimenta al futuro Golden Dataset con
  positivos verificados por un humano real) + guardián de identidad
  reservada (mismo patrón que `release_candidate_builder.confirm_rc`:
  un agente no puede autoaprobarse). Sigue emitiendo exactamente un
  evento (`rc_reviewed`) por decisión.
- `judgment.py`: `JudgmentUnit.candidate_chunks` documentado para
  aceptar la salida directa de `fusion.rrf_fuse()` (ya trae
  `bm25_rank`/`embedding_rank`); `fusion_rank` se agrega como posición
  1-indexada del candidato en el pool (rrf_fuse no expone un "rank"
  propio, solo el score crudo).

5 tests nuevos (`test_r2_3_reviewer_enrichment.py`): entrada con
candidatos completa (incluye caso con `bm25_rank=None`, candidato
solo-embedding, honesto), entrada sin candidatos válida (`candidates=[]`,
sin nota), sanitización (whitespace + truncado), decisión humana con
evidencia confirmada emite exactamente `["rc_reviewed"]`, identidad
reservada rechazada.

**Esto NO es R3** (informe de hallazgos) — completa el camino de
revisión humana que R1.8 ya abrió, con datos que la fusión ya produce.
No gasta presupuesto de ninguna familia de gobernanza.

## 5. LAS TRES DECISIONES DE CESAR (preparar paquetes; DETENERSE en cada firma)

D1 — ADOPTAR LA FUSIÓN EN EL PIPELINE DE RECUPERACIÓN.
D2 — RUMBO DEL PRODUCTO: TIER-1 ASISTIDO COMO ENTREGABLE.
D3 — LA PALANCA DE JUICIO (paralela, no bloqueante).

DETENERSE en cada una de las tres firmas. Nada de esto se ejecuta ni se
commitea sin la firma explícita correspondiente.

---

### D1 — RESULTADO: paquete listo, SIN COMMITEAR, esperando firma

**Diff nuevo, en el árbol de trabajo, NO agregado a git**:
`factory/regulatory/retrieval/judgment_candidate_pool.py` (código real,
`build_fusion_candidate_pool()`, reemplazo directo de
`retriever.retrieve_top_k()` con el mismo contrato de retorno) +
`factory/tests/test_r2_3_d1_fusion_candidate_pool.py` (3 tests, embeddings
MOCKEADOS -- cero gasto del remanente real de `EMBED_EXECUTION-2026-002`,
que quedó en **1/60**, no 3/60 como asumía la orden -- ver corrección de
instrumento en el encabezado de este documento).

**Qué hace**: mismo contrato que `retriever.retrieve_top_k(document_sha256,
req_id, k)` (misma firma de retorno: lista de dicts con `chunk_index`,
`page_start`, `page_end`, `text`), pero rankeando por fusión RRF en vez de
BM25 solo. `judgment.py` seguiría construyendo `JudgmentUnit.candidate_
chunks` explícitamente hasta que esto se adopte -- el cambio de integración
real, cuando Cesar firme, es reemplazar la llamada a `retriever.
retrieve_top_k()` por `judgment_candidate_pool.build_fusion_candidate_pool()`
en el único call-site que construye `candidate_chunks` hoy.

**Lo que el paquete deja EXPLÍCITAMENTE sin resolver** (para que Cesar lo
vea antes de firmar, no después):
1. **Gobernanza de la llamada de consulta**: `build_fusion_candidate_pool()`
   llama a `embed_index.embed_query()` directo (1 llamada real de
   embedding por invocación, la consulta del requisito) -- HOY eso NO
   pasa por `embed_runner.run_embed_batch()`, que es el único punto que
   verifica `EMBED_EXECUTION` vigente con presupuesto antes de gastar.
   Adoptar D1 en producción real exige re-cablear esa llamada para
   consumir presupuesto de una `EMBED_EXECUTION` vigente (hard-stop antes
   de gastar, mismo patrón que `run_embed_batch`) -- **no implementado en
   este paquete**, señalado a propósito en vez de resuelto a medias.
2. **Indexación de documentos nuevos**: `build_fusion_candidate_pool()`
   falla explícito (`FusionCandidatePoolError`) si el documento no tiene
   índice de embeddings todavía -- correcto (nunca cae en silencio a BM25
   solo sin que el llamador lo sepa), pero significa que CADA documento
   nuevo que entre al modo JUICIO necesita una `EMBED_EXECUTION` propia
   ANTES -- con 1/60 de remanente en la instancia actual, la primera
   corrida real sobre un documento nuevo necesita esa firma primero.
3. **No re-mide recall** -- eso ya está medido (R2.2 §4.4, fusión 7/7
   at_5) y no vuelve a probarse aquí; este paquete es integración, no
   medición.

**Recomendación**: los datos sostienen adoptar D1 con independencia del
rumbo de D2/D3 -- mejora la recuperación para el humano HOY (vía §4, ya
en producción) y para cualquier modelo de juicio futuro (D3). El costo
real no resuelto (punto 1) es acotado y conocido, no una sorpresa.

**Pendiente de firma de Cesar**: adoptar D1 (integrar
`judgment_candidate_pool.py` como default, resolver el punto 1 antes o
como parte de la adopción) o mantener BM25 solo en `judgment.py` por
ahora.

### D1 — FIRMADO por Cesar (2026-08-11). Punto 1 resuelto, commiteado.

`build_fusion_candidate_pool()` re-cableado: la llamada de embedding de
la CONSULTA ahora pasa por `embed_runner.run_embed_batch()` (mismo
hard-stop de presupuesto real que ya protegía la indexación de chunks)
en vez de `embed_index.embed_query()` directo -- nueva firma
`(document_id, document_sha256, req_id, *, k=5, calls_already_used=0)`
(se necesitan los dos identificadores: `run_embed_batch` gobierna por
`document_id`, `retriever`/`embed_index` indexan por `document_sha256`).
Si `run_embed_batch` para en `HARD_STOP_CALLS` o cualquier otro
`stop_reason` distinto de `BATCH_COMPLETE`, `build_fusion_candidate_pool`
falla explícito (`FusionCandidatePoolError`) -- nunca sigue con un vector
inventado. 5 tests (embeddings/`run_embed_batch` mockeados -- prueban la
LÓGICA de esta función, no vuelven a probar la gobernanza de
`EMBED_EXECUTION` en sí, ya probada en producción real por -012).

**Punto 2 (indexación de documentos nuevos) queda tal cual estaba
señalado** -- no es un defecto, es el comportamiento correcto: cualquier
documento nuevo en modo JUICIO necesita su propia `EMBED_EXECUTION`
antes. Con 1/60 de remanente en `-002`, la primera corrida real de
producción sobre CUALQUIER documento (nuevo o de los 3 ya indexados,
para una consulta más allá de las 9 ya cubiertas) necesita una
`EMBED_EXECUTION` nueva primero.

**Código commiteado** (`judgment_candidate_pool.py` +
`test_r2_3_d1_fusion_candidate_pool.py`) -- ver commit al pie de este
documento. `judgment.py` sigue construyendo `JudgmentUnit.candidate_
chunks` explícitamente por ahora: adoptarlo como *constructor por
defecto* en el call-site real de producción, y la re-medición de juicio
dimensionada que eso habilitaría, quedan para una corrida separada
(fuera de alcance de "cero llamadas de juicio LLM" de R2.3) -- este
paquete deja el código listo, probado, sin gastar el 1/60 de remanente
real ni ningún presupuesto de juicio.

---

### D2 — RESULTADO: especificación del producto Tier-1, con SOLO capacidades medidas

**Alcance declarado (nada more, nada menos que lo medido)**:

| Capacidad | Medido en | Estado |
|---|---|---|
| (a) Confirmación automática LEXICAL_ECHO con anclaje A/B/C/D | P1, único rescatado del fixture (R2.2 §3) | Automatizable -- el pipeline de verificación (semantic_evidence_verification, ya en producción) ya hace esto para eco léxico directo |
| (b) Rechazo de falsos positivos | N1/N2, 2/2 fuera del top-5 en los 3 métodos (BM25/embed/fusión) | Automatizable -- ANNEX11_4 (referencia bibliográfica) ya rechazado estructuralmente, verificado tras el fix de kerning |
| (c) Recuperación semántica entregando candidatos al revisor | Fusión RRF 7/7 recall_at_5 (R2.2 §4.4) | Implementado y en producción (R2.3 §4, commit `116d18e`) |
| (d) TODO lo demás → revisión humana con cobertura declarada | Blindaje §2, verificado en producción real (R2.2 §5.2, R2.3 §2) | Implementado y en producción |
| (e) Blindaje anti-gap en producción | 4 casos históricos re-etiquetados + verificado en vivo (R2.3 §2) | Implementado y en producción |
| (f) Conclusiones consolidadas y liberación: siempre humanas | Regla dura CLAUDE.md, sin excepción en ningún punto de este arco | Ya es así, sin cambios pendientes |

**Límite declarado sin maquillar**: la detección automática de
PARÁFRASIS (P2, P4, P5, P6, P7 -- 5 de los 6 casos medibles, 83% del
fixture) **NO está incluida**. Confirmado con tres vías de medición
independientes: BM25 solo (4/7), fusión con pool perfecto (P2/P5 con el
chunk correcto al frente, `PILOT_EXECUTION-2026-012`, 0/2), y el propio
criterio pre-fijado de Cesar (§1 de R2.2, `1/6 ≤ 3/6` ⇒ B domina). Un
Tier-1 que prometiera detección automática de paráfrasis estaría
prometiendo algo que las tres medidas independientes de este arco
refutan.

**Producto Tier-1 propuesto** (si Cesar firma D2): un analizador
documental que, por requisito, hace UNA de tres cosas -- (1) confirma
evidencia con eco léxico directo, anclada A/B/C/D, automáticamente; (2)
rechaza estructuralmente un falso positivo conocido (referencias
bibliográficas, tablas de contenido); (3) para todo lo demás, encola a
revisión humana con los top-5 candidatos de fusión + página + honestidad
explícita de que son recuperación, no evidencia. Nunca declara
cumplimiento, nunca cierra CAPA, nunca libera lote -- sin cambios sobre
las reglas permanentes de `CLAUDE.md`.

**Qué falta para implementar Tier-1 si Cesar firma**: el "informe
asistido" (formato de entrega al usuario final que combina (a)+(b)+(c)+(d)
en un solo documento por corrida) y el empaquetado del flujo end-to-end
-- NO se planifica en detalle en esta corrida (fuera del alcance
explícito de R2.3 §5: "si Cesar firma D2, la implementación... se
planifica como corrida siguiente").

### D2 — FIRMADO por Cesar (2026-08-11)

Confirmado en conversación (no en el panel de gobernanza de
`mission_control` -- D2 no gobierna ningún recurso de LLM/embeddings/
corpus, es una decisión de RUMBO DE PRODUCTO, nunca se propuso como
registro de `decision_family` en `decisions_v2.jsonl`; a diferencia de
`EMBED_EXECUTION`/`PILOT_EXECUTION`, que sí viven ahí y sí aparecen en
la UI, D2 vive solo como texto en este documento -- la confirmación de
Cesar en el chat ES la firma, no falta nada en la UI).

Rumbo del producto: Tier-1 asistido, alcance (a)-(f) de la tabla arriba,
**detección automática de paráfrasis explícitamente excluida**.
Implementación (informe asistido + empaquetado end-to-end) **pendiente
de planificarse como corrida siguiente**, fuera de alcance de R2.3.

**Pendiente de firma de Cesar**: adoptar D2 como rumbo del producto (o
no) -- sin comprometer todavía la corrida de implementación.

---

### D3 — RESULTADO: costos reales de las dos palancas de juicio restantes, SIN ejecutar nada

**(a) GPU local (Llama 3.1 70B, objetivo declarado)**

- *Hardware*: un 70B en cuantización útil (Q4/Q5) necesita ~40-48GB de
  VRAM para inferencia con contexto razonable -- una sola GPU de
  consumo (24GB, p.ej. RTX 4090) NO alcanza sin cuantización agresiva
  que degrada calidad; opciones reales: 2× GPU de 24GB en paralelo, o
  una GPU de datacenter (A100/H100 80GB, alquilada o comprada). Ninguna
  de estas existe hoy en el servidor (`ivr-ia` corre CPU-only para
  Ollama, confirmado por el pipeline actual completo en CPU).
- *Costo aproximado*: comprar (A100 80GB, gama alta, orden de
  magnitud de varios miles de USD) vs. alquilar (proveedores de GPU
  cloud, por hora, orden de magnitud de USD/hora mientras esté
  encendida) -- cifra exacta depende del proveedor elegido, NO
  cotizada en esta corrida (fuera de alcance: "SIN ejecutar nada").
- *Advertencia honesta explícita*: **el recall resultante NO es
  demostrable sin probar**. Un modelo más grande no garantiza que
  reconozca paráfrasis mejor -- es una hipótesis razonable (más
  parámetros, mejor generalización semántica), no un hecho medido. El
  fixture 7P+2N (`test_r2_retrieval.py`/`test_r2_judgment.py`) es el
  instrumento de calificación LISTO para el día que un modelo así esté
  disponible -- correr el mismo fixture, mismo criterio pre-fijado, es
  el primer paso obligatorio antes de cualquier promoción a producción,
  ni un caso menos.

**(b) Proveedor externo (`AnthropicProvider`, diseño ya aprobado)**

- *Evaluación de confidencialidad*: los documentos reales del fixture
  (RW-0005/0011/0012, Rockwell) son especificaciones funcionales/
  narrativas de control de un cliente real (Mark Cuban Cost Plus Drug
  Company, PBC, per el propio documento). Cada llamada de juicio a un
  proveedor externo enviaría el CHUNK completo (hasta ~6000 caracteres)
  del documento del cliente fuera del perímetro del servidor -- esto es
  exactamente el tipo de dato que el diseño de `AnthropicProvider`
  existente ya contempla como fuera de alcance sin autorización
  explícita adicional (mismo principio que motivó que `ModelProvider`
  sea un adaptador intercambiable en primer lugar).
- *Implicaciones contractuales*: requeriría verificar el contrato con
  el cliente (Rockwell/Mark Cuban Cost Plus Drug Company) sobre uso de
  IA de terceros sobre sus documentos técnicos -- NO verificado en esta
  corrida, señalado como bloqueante previo a cualquier ejecución real.
- *Circuito de gobernanza requerido* (si se autoriza en principio):
  decisión formal nueva (familia separada, mismo patrón que
  `EMBED_EXECUTION`/`PILOT_EXECUTION` -- alcance acotado, tope duro de
  llamadas, nunca autoriza otra familia), calificación del proveedor
  externo contra el MISMO fixture 7P+2N con el MISMO criterio
  pre-fijado (nunca aflojado para favorecer al proveedor nuevo),
  fingerprint del modelo/versión de API, presupuesto propio -- ninguno
  de estos existe todavía, se listan como el checklist de lo que
  faltaría, no como trabajo ya hecho.

**D3 puede quedar abierta sin bloquear D1/D2** -- ninguna de las dos
palancas se ejecuta en esta corrida ni depende de D1/D2 para evaluarse
en el futuro.

**Pendiente de firma de Cesar**: ninguna acción requerida ahora -- D3 es
información para decidir, no una propuesta a firmar todavía. Si más
adelante Cesar quiere avanzar alguna de las dos palancas, el siguiente
paso es una corrida separada, dimensionada como tal.

## 6. ACTUALIZACIÓN DE MEMORIA, SKILL Y ROADMAP

- Memoria: arco R2 CERRADO con sus números finales (1/6; fusión 7/7;
  juicio 0/2 con pool perfecto); recuperación=resuelta,
  juicio-paráfrasis=límite del modelo; Tier-1 como rumbo propuesto
  pendiente de D2; presupuestos: -010 agotada, -012 consumida,
  EMBED-002 en 57/60.
- Skill gmp-recall-pipeline: sección nueva "capa semántica" (fusión,
  contexto 2048 de nomic-embed, truncado determinista, gobernanza
  EMBED_EXECUTION) + la lección final del arco: recuperación y juicio
  son mitades independientes del muro; medirlas juntas fue el error de
  diseño original de R2.
- Roadmap: R2 CERRADO (gate ≥6/7 de juicio NO alcanzado — declararlo);
  R3-R5 se redefinen bajo D2 (Tier-1) si Cesar firma; diferidos intactos
  (D4-A recalc, limpieza PILOT redundantes, MarkItDown/H5-H7, Piloto 2,
  corpus formal).

### 6. RESULTADO — ver memoria/skill/roadmap actualizados por separado, referenciados en §7.

## 7. ENTREGA

```
COMMITS =                       C1..C4 originales quedaron 8 commits reales (§1) -- 990710c, 189755c, e855c9e(C3), fe36c62(C1), 60a555f(C2), 7fb3d3f, ebf2a66, a610bc3(C4); + R2.3: 83aa917, 6ee8e21, 1e75e79, 4a21135, 116d18e -- todos en HEAD, aprobados
P7_RELABELED =                   supersede trazable en review_queue.jsonl, sin re-ejecución (commit 6ee8e21)
OTHER_GAP_LABELED_JUDGMENT_RUNS = 3 encontrados y tratados (P2-viejo/P5-viejo superseded, P6 sin re-medición nueva) -- ver tabla §2
P2_P5_REPLAY_FIXTURES =          agregados (commit 4a21135), 2 tests verdes con datos reales
REVIEWER_ENRICHMENT =            cola R1.8 con candidatos de fusión + honestidad + confirmación humana (commit 116d18e), 5 tests verdes
D1_FUSION_ADOPTION =             paquete listo, código escrito y testeado (mocks), SIN COMMITEAR -- esperando firma
D2_TIER1_SPEC =                  paquete listo (§5 D2 arriba) -- esperando firma
D3_JUDGMENT_LEVER_PACKAGE =      GPU vs externo, costos y gobernanza reales, sin ejecutar nada -- información entregada
EMBED_BUDGET_REMAINING =         1/60 (corregido de la asunción de 3/60 en la orden) -- toda indexación nueva = firma nueva
MEMORY_SKILL_ROADMAP =           actualizados (memoria: sección R2.3 nueva; skill gmp-recall-pipeline: "capa semántica" + "lección final"; roadmap: R2 CERRADO, R3 redefinido bajo D2, diferidos con condición ya cumplida)
SUITE / GATE_0 =                 2338 passed, 4 failed (Playwright/live-endpoint, ambientales, no relacionados), corrido una vez al final sobre el estado consolidado
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**Pendiente de firma de Cesar**: D1, D2, D3 (§5) -- ninguna bloquea a
las otras. El arco de medición de R2 en sí mismo queda cerrado con esta
corrida: no hay más recall de juicio que medir, el techo del 7B sobre
paráfrasis está confirmado por tres vías independientes.
