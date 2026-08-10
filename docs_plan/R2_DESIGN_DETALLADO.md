# R2 — Diseño detallado: recuperación determinista de evidencia

**Fecha:** 2026-08-09. **Estado:** IMPLEMENTADO (`factory/regulatory/retrieval/`)
Y MEDIDO contra el fixture real. Autorizado por Cesar tras resolver la
dependencia (BM25 stdlib, sin `chromadb`).
**Alcance autorizado:** `docs_plan/R1_CIERRE_Y_PREP_R2.md` sección 4 —
diseño + medición de recuperación pura (cero LLM). La fase de JUICIO
(recall real con LLM sobre los top-k) sigue fuera, requiere
`PILOT_EXECUTION` nueva firmada por Cesar.

## Resultado real de la medición de recuperación pura (2026-08-09, cero llamadas LLM)

Corrido contra el corpus real (`GMPAI/source/Rockwell/`, mismos 3
documentos de los 7 positivos del fixture: RW-0005, RW-0011, RW-0012),
`k=5` (propuesto) y `k=10` para contexto. Verificado con tests reales
(`factory/tests/test_r2_retrieval.py`), no estimado.

| # | documento | requirement_id | página real (1-idx) | rank del chunk que la cubre | en top-5 | en top-10 |
|---|---|---|---|---|---|---|
| P1 | RW-0005 | `21_CFR_11.10(e)` | 46 | 1 | ✅ | ✅ |
| P2 | RW-0005 | `21_CFR_11.10(g)` | 40 | 6 | ❌ | ✅ |
| P3 | RW-0005 | `ANNEX11_12` [†] | 45 | 20 | ❌ | ❌ |
| P4 | RW-0011 | `ALCOA_ATTRIBUTABLE` | 13 | 2 | ✅ | ✅ |
| P5 | RW-0005 | `ALCOA_CONTEMPORANEOUS` | 46 | 9 | ❌ | ✅ |
| P6 | RW-0011 | `21_CFR_211.68(b)` | 13 | 2 | ✅ | ✅ |
| P7 | RW-0012 | `21_CFR_211.68(b)` | 14 | 2 | ✅ | ✅ |

[†] `ANNEX11_12` era el `req_id` original del fixture, con un error de
etiquetado real (ver "Investigación de P3" abajo). Corregido a
`ANNEX11_17`; re-medido en la sección "Corrección de P3 y re-medición" —
el rank cambia (12 en vez de 20) pero sigue fuera del top-10, y
`retrieval_recall_at_5/10` no cambian.

```
retrieval_recall_at_5  = 4/7
retrieval_recall_at_10 = 6/7
```

Negativos: **N1** (GAMP5 en lista de referencias numeradas, p.2 real de
RW-0005) rank 8 — fuera del top-5. **N2** (mención en tabla de
contenidos, p.4 real de RW-0005) rank 15 — fuera del top-5. Ambos
negativos se comportan correctamente: BM25 no los prioriza para sus
respectivos `requirement_id`.

**Lectura honesta, no maquillada**: P5 (el caso central de R1.6/R1.7)
NO entra en el top-5 — mismo punto ciego, medido de forma independiente.
La causa es la misma que ya se documentó ahí: la evidencia real que un
evaluador (humano o modelo) reconocería como relevante no repite el
vocabulario gobernado (`citation_text`/`evidence_min_criteria`/
`requirement_terms.yaml`) de forma literal — y BM25, igual que la vieja
heurística `_is_topically_relevant`, es un método **léxico**, no
semántico. `P3` tampoco entra ni en el top-10 — investigado en detalle
(ver sección siguiente): la causa principal **no es un defecto de
BM25**, es un error de etiquetado en el fixture set. Esto **no invalida
R2**: `retrieval_recall_at_5=4/7` ya mejora sobre el punto de partida
(el juicio ve 5 candidatos en vez de las 29 páginas completas del
documento en orden secuencial), y `k=10` sube a 6/7 — pero confirma que
BM25 por sí solo probablemente no alcanza el criterio de éxito (`≥6/7`
en la fase de JUICIO, que es un umbral distinto y posterior) sin que el
juicio LLM aporte lo que la recuperación léxica no puede: entender que
una evidencia parafraseada es relevante aunque no comparta vocabulario
literal. Nota para una decisión futura de Cesar, no una propuesta de
esta corrida: si el gate `≥6/7` de R2 no se alcanza con BM25 puro, la
alternativa de embeddings semánticos (H5/`chromadb`, diferida en R1.6)
volvería a ser relevante — se deja anotado, no se reabre esa decisión
aquí.

## Investigación de P3 (2026-08-09, post-medición) — causa raíz encontrada, con dos capas

**Capa 1 (causa principal): el fixture set tiene el `requirement_id` de
P3 mal etiquetado.** El fixture describe el pasaje de P3 como *"UR3.3.6
Data retention — 1 año, archivado en ubicación alterna"*, pero le asigna
`ANNEX11_12`. Verificado contra el catálogo real
(`requirement_catalog_loader.get_requirement`):

- `ANNEX11_12` (`citation_text`): *"Physical and/or logical controls
  should be in place to restrict access to computerised system to
  authorised persons..."* — control de acceso físico/lógico, **tema
  distinto**.
- `ANNEX11_17` (`citation_text`): *"Data may be archived. This data
  should be checked for accessibility, readability and integrity..."*
  — coincide con el pasaje real de P3.

Confirmado leyendo la página 45 real (1-indexada) de RW-0005: contiene
literalmente *"UR3.3.6 Data retention time... retaining 1 year of
historical data locally before it is archived in an alternate location
for safe keeping"* — es la sección de retención de datos, no de
seguridad física/lógica. La query construida para P3 buscaba llaves,
tarjetas, biometría, firewalls — un tema ajeno al de la página. Ningún
método de recuperación, léxico o semántico, iba a encontrar esa página
con esa query. **No se corrigió el fixture set en esta corrida** — es
un artefacto gobernado (`W5V2_RECALL_FIXTURE_SET_DRAFT.md`), corregirlo
requiere aprobación explícita de Cesar, igual que cualquier otro cambio
a contenido gobernado.

**Capa 2 (causa secundaria): incluso con el `req_id` corregido a mano
(`ANNEX11_17`), la página sigue sin entrar al top-10 (rank 12 de 29)**.
Investigado por qué:

1. **Artefacto de extracción del PDF**: el texto extraído dice
   literalmente `"UR3.3.6 Data retentio n time"` — un espacio espurio
   (kerning/fuente del PDF real) parte la palabra "retention" en
   `"retentio"` + `"n"`. Confirmado con el conteo real de términos del
   chunk: `term_counts["retention"] == 0`, pese a que la página sí habla
   de retención — el token completo nunca se forma.
2. **Dilución por chunk mixto**: el chunk que cubre las páginas 45-46
   (736 tokens) mezcla la sección de retención con Historian, Audit
   Trail y Critical Data Records en el mismo bloque de
   `build_page_chunks()` — el conteo de términos relevantes
   (`term_counts["archived"] == 3`) queda diluido frente a chunks más
   homogéneos temáticamente, que puntúan más alto en BM25.

**Conclusión**: el punto ciego de P3 es una combinación de (a) un error
de etiquetado preexistente en el fixture set, no introducido por R2, y
(b) BM25 sin stemming siendo sensible a un artefacto de extracción de
PDF que también preexistía. Ninguno de los dos es un defecto de diseño
de R2 en sí — son hallazgos de datos/gobernanza, registrados para
decisión de Cesar, no corregidos aquí sin autorización.

## Por qué R2 (recordatorio del problema)

El techo de recall medido hasta ahora (2/7, H1-H4) evaluó al modelo
juzgando el DOCUMENTO COMPLETO por chunks secuenciales de tamaño fijo
(`chunked_engine.build_page_chunks()`, `CHUNK_MAX_CHARS`). R1.6/R1.7
mostraron que parte de ese techo era artificial (un gate posterior
descartaba evidencia genuina) — pero incluso corregido eso, el modelo
sigue viendo el documento entero en el orden en que aparece, no el pasaje
más relevante primero. R2 invierte esto: en vez de "juzga todo el
documento, chunk por chunk", recupera primero (determinista, sin LLM) los
K pasajes más relevantes para el requirement_id específico, y solo esos
se le presentan al juicio LLM — mejora la señal de entrada, no reemplaza
ningún validador existente.

## Separación arquitectónica (obligatoria, `CLAUDE.md`)

`factory/regulatory/retrieval/` (capa 9000, GMP AI Factory). **No** toca
`gmp-api`/`knowledge/retriever.py` (:8000, producto base) — ese módulo
sirve una colección propia del producto (`gmp_fda_regulations`/
`gmp_iq_oq_pq`), un caso de uso distinto (RAG conversacional), no
recuperación de evidencia por requirement_id contra un documento bajo
análisis. R2 crea su propia infraestructura de recuperación, separada.

## Investigación previa (evita reinventar, evita copiar un patrón con defecto conocido)

`knowledge/retriever.py` (base gmp-api) es el único código de
recuperación semántica existente en el repo (usa ChromaDB), y tiene un
defecto real para nuestro caso: extrae el PDF completo con `pypdf`
concatenando TODAS las páginas antes de chunkear (`_extract_text`), así
que **pierde el número de página** — el metadata de cada chunk solo
guarda `{source, chunk, directory}`, nunca `page_start`/`page_end`. R2
necesita mapeo chunk→página real (todo el resto del sistema, desde
`evidence_verifier` hasta `absence_consolidator`, opera sobre rangos de
página) — así que R2 **no reutiliza `_extract_text`/`_split_text` de
`knowledge/retriever.py`** en ningún escenario, reutiliza en su lugar
`chunked_engine.build_page_chunks()` (ya tiene chunking page-aware, ya
probado, ya en producción) para construir los chunks a indexar.

**Decisión de Cesar (2026-08-09): TF-IDF/BM25, sin dependencia nueva de
chromadb.** Evaluado además qué tan "sin dependencia nueva" debía ser
la alternativa — corrección de un error de esta misma nota: la versión
anterior afirmaba que `scikit-learn` "ya se usa en otras partes del
repo"; verificado y es **falso** — `scikit-learn` está en el venv solo
como dependencia transitiva de `sentence-transformers`, nunca declarado
en `factory/requirements.txt` ni importado por ningún código de
`factory/`. Decisión final (Cesar, confirmada): **BM25 implementado a
mano con la librería estándar** (`re`, `collections.Counter`, `math`) —
cero paquetes nuevos, ni siquiera `rank_bm25`/`scikit-learn`. Coincide
literalmente con "sin dependencia nueva", no solo "sin chromadb".

## Diseño del módulo

```
factory/regulatory/retrieval/
├── bm25.py           # BM25 puro, stdlib (tokenizacion, IDF, scoring) -- sin dependencias nuevas
├── indexer.py        # construye/actualiza el indice BM25 de un documento
├── query_builder.py  # construye la query desde el Evidence Pack (ver abajo)
└── retriever.py       # top-k determinista, mapeo a pagina, sin LLM
```

### `bm25.py` — Okapi BM25 sin dependencias

Tokenización simple (`re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+", text.lower())`,
mismo patrón de extracción de palabras que ya usa
`chunked_engine._is_topically_relevant`/`_LABEL_STOPWORDS` — reutilizar
el patrón, no una regex nueva inventada). Por documento (colección de
chunks): `collections.Counter` de términos por chunk, longitud de cada
chunk en tokens, longitud promedio de chunk. IDF real por término (fórmula
Okapi estándar, `k1=1.5`, `b=0.75` — valores de referencia de la
literatura, no calibrados a mano, anotado explícitamente para que una
futura sesión no los confunda con un ajuste fino ya hecho):

```python
def idf(term: str, chunks: list[dict]) -> float:
    n_docs = len(chunks)
    n_containing = sum(1 for c in chunks if term in c["term_counts"])
    return math.log((n_docs - n_containing + 0.5) / (n_containing + 0.5) + 1)

def bm25_score(query_terms: list[str], chunk: dict, corpus_idf: dict,
               avg_chunk_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    score = 0.0
    dl = chunk["token_count"]
    for term in query_terms:
        f = chunk["term_counts"].get(term, 0)
        if f == 0:
            continue
        score += corpus_idf.get(term, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_chunk_len))
    return score
```

Sin llamada a LLM, sin librería externa — determinista, mismo input
siempre produce el mismo score.

### `indexer.py` — indexación del documento objetivo

- Reutiliza `chunked_engine.build_page_chunks(per_unit_text, max_chars, overlap_chars)`
  para obtener los chunks reales (con `page_start`/`page_end`) — mismo
  chunking que ya usa el pipeline de juicio, para que un pasaje
  recuperado sea directamente comparable/reutilizable por
  `evaluate_chunked()` después.
- Un índice BM25 **por documento** (`document_sha256` como clave —
  nunca mezclar documentos distintos en un mismo índice, evita que un
  requirement_id de un documento recupere contenido de otro por
  accidente). Estructura simple, serializable a JSON:
  `{document_sha256, avg_chunk_len, chunks: [{chunk_index, page_start,
  page_end, has_overlap_prefix, text, term_counts, token_count}]}`.
- Persistencia: JSON en disco (mismo patrón que otros artefactos de
  `factory/regulatory/`, no requiere infraestructura nueva — sin
  servidor, sin cliente, sin proceso adicional, a diferencia de Chroma).
- Reindexación: si el documento ya tiene índice con el mismo
  `document_sha256`, no reindexar (idempotente, determinista).

### `query_builder.py` — construcción de la query desde el Evidence Pack (regla dura)

Fuente **primaria y obligatoria** (nunca opcional): `citation.citation_text`
(el texto normativo literal, ya gobernado, `requirements.yaml`) +
`evidence_min_criteria` (lista de criterios reales, ya interpretados por
Cesar en Fase C de W5 V2) + los sinónimos ya gobernados de
`requirement_terms.yaml` (`load_requirement_terms(req_id)`, reutilizado
tal cual, sin reimplementar).

**Regla dura explícita del alcance (R1_CIERRE sección 4)**:
`weak_keywords` del catálogo **NUNCA es la única fuente** de una query —
puede complementar, nunca sustituir a `citation_text`/
`evidence_min_criteria`/`requirement_terms.yaml`. Motivo: `weak_keywords`
existe en el catálogo precisamente para marcar términos DÉBILES/
ambiguos (ver Fase C, `governed_interpretation`) — usarlos solos como
única query invitaría exactamente al mismo patrón que produjo el falso
positivo ANNEX11_4 original (keyword aislado sin contexto normativo).

```python
def build_retrieval_query(req_id: str) -> str:
    entry = get_requirement(req_id)  # requirement_catalog_loader, ya existente
    terms = load_requirement_terms(req_id)  # evidence_verifier, ya existente
    parts = [entry["citation"]["citation_text"], *entry["evidence_min_criteria"], *terms]
    return " ".join(parts)
```

Sin llamada a LLM en ningún punto de esta función — determinista, mismo
input siempre produce la misma query.

### `retriever.py` — recuperación top-k, sin juicio

```python
def retrieve_top_k(document_sha256: str, req_id: str, k: int = 5) -> list[dict]:
    """Retorna hasta k chunks candidatos: {chunk_index, page_start,
    page_end, text, bm25_score}. NUNCA llama a un LLM. NUNCA decide si un
    candidato es evidencia valida -- eso sigue siendo trabajo exclusivo
    de evaluate_chunked()/verify_llm_output/absence_consolidator, R2 no
    los toca ni los antecede en autoridad, solo en orden de presentacion."""
```

Carga el índice JSON del documento (`indexer.py`), tokeniza la query
(mismo tokenizador que `bm25.py`), calcula `bm25_score` de cada chunk
contra la query, ordena descendente, retorna los `k` primeros. Sin
filtros adicionales por ahora (el filtro real es "un índice por
documento", ya aplicado al indexar).

## Qué NO cambia (reafirmado, para que no haya ambigüedad al ejecutar)

- El pipeline de juicio (`evaluate_chunked`, `evaluation_profile`,
  `_is_topically_relevant`→`detect_reference_list_context`,
  `verify_llm_output`, `absence_consolidator`, el despacho de R1.8) —
  **ninguno se modifica**. R2 le entrega mejores candidatos (top-k en vez
  de todo el documento en orden secuencial); el juicio sigue siendo
  exactamente el mismo camino ya validado.
- Ningún umbral (`RELEVANCE_THRESHOLD`, `FUZZY_THRESHOLD`).
- El fixture set 7P+2N sigue siendo el único instrumento de medición.

## Métrica de recuperación pura (cero LLM, el entregable de esta fase)

Para cada uno de los 7 positivos del fixture: ¿el pasaje verificado a
mano por Cesar (`W5V2_RECALL_FIXTURE_SET_DRAFT.md`) está **contenido
literalmente** (mismo criterio de `_is_anchored`/`match_citation`, no
una aproximación nueva) dentro de alguno de los top-k chunks recuperados
para ese `req_id`?

```
retrieval_recall_at_k = (positivos cuyo pasaje real esta en el top-k) / 7
```

Para los 2 negativos: ¿el top-k arrastra el pasaje problemático (GAMP5 en
lista de referencias / la mención de tabla de contenidos)? Si lo hace,
no es un fallo de R2 per se (recuperar no es aceptar) — pero se registra,
porque significa que el juicio LLM posterior (R2 fase de juicio, todavía
no autorizada) tendría que volver a rechazarlo correctamente vía
`detect_reference_list_context`/D — exactamente lo que ya hace hoy.

Esta métrica **no consume presupuesto `PILOT_EXECUTION`** — no invoca al
modelo, es indexación + query determinista contra texto ya extraído del
PDF real (mismo texto que ya usa `evaluate_chunked()` hoy).

## Tests propuestos (cuando se implemente)

- `retrieve_top_k` sobre el documento real RW-0005 con la query real de
  `ALCOA_CONTEMPORANEOUS`/`21_CFR_11.10(e)`/`ANNEX11_4`: el pasaje real
  de P1/P2/P3/P5 (los positivos ya verificados a mano sobre RW-0005)
  aparece en el top-5.
- El pasaje de ANNEX11_4 (GAMP5 en lista de referencias) — registrar si
  aparece o no en el top-k, sin asumir un resultado.
- `build_retrieval_query` nunca produce una query vacía o compuesta
  solo de `weak_keywords` (test que falla si algún llamador futuro
  intenta ese atajo).
- Idempotencia de indexación: mismo `document_sha256` no reindexa.

## Estado de las decisiones (actualizado 2026-08-09)

1. ~~¿Autorizar `chromadb`...?~~ — **RESUELTO**: TF-IDF/BM25, stdlib
   puro, sin dependencia nueva.
2. ~~Confirmar `k`~~ — **usado k=5 como propuesto** para el reporte
   principal (`retrieval_recall_at_5`); `k=10` corrido en paralelo solo
   como contexto adicional, no reemplaza el criterio.
3. ~~Autorizar la implementación real~~ — **IMPLEMENTADO Y MEDIDO**
   (`factory/regulatory/retrieval/{bm25,indexer,query_builder,retriever}.py`,
   `factory/tests/test_r2_retrieval.py`, 13 tests). Resultado real arriba.

## Corrección de P3 y re-medición (2026-08-09, autorizada por Cesar)

`req_id` de P3 corregido en `W5V2_RECALL_FIXTURE_SET_DRAFT.md`:
`ANNEX11_12` → `ANNEX11_17` (agente y página sin cambios). Re-medido con
la query correcta: **P3 sigue sin aparecer en el top-10 (rank 12 de
29)** — confirma que la Capa 2 (artefacto de extracción de PDF que
parte "retention" en dos tokens, más dilución del chunk con
Historian/Audit Trail/Critical Data Records) es una causa real e
independiente del etiquetado, no un efecto secundario de la Capa 1.
Corregir el `req_id` mejora la gobernanza del fixture (ahora refleja la
realidad) pero **no cambia** los números medidos:

```
retrieval_recall_at_5  = 4/7   (sin cambios)
retrieval_recall_at_10 = 6/7   (sin cambios, P3 sigue siendo el único
                                 positivo fuera incluso a k=10)
```

Tests actualizados: `test_r2_retrieval.py::test_p3_annex11_17_not_in_top10`
(antes `test_p3_annex11_12_not_in_top10`), rank 12 confirmado con el
`req_id` correcto.

## Resultado real de la fase de JUICIO (ejecutada en background, 2026-08-10)

**Estado de implementación al momento de esta corrida**: `factory/regulatory/retrieval/judgment.py`
+ `factory/tests/test_r2_judgment.py` existen en el árbol de trabajo pero
**no están commiteados** (`git status`: `??` sin trackear). Se documenta
el resultado real igual, tal como se encontró, sin esperar al commit —
regla de "leer antes de escribir" aplicada a la evidencia ya generada.

**Fuente de la evidencia**: `factory/audit/factory_audit.jsonl`, evento
`r2_judgment_batch_completed` (`entry_id 7d184c28-e2c2-4102-88f4-5f60d794306c`),
cruzado con los 8 checkpoints reales en `factory/regulatory/pilot_run/checkpoints/`
que ese evento referencia (uno por unidad).

```
timestamp:                2026-08-10T05:25:50 UTC
document_ids:              [RW-0005, RW-0011, RW-0012]
stop_reason:                BATCH_COMPLETE
total_calls_made:           50
total_wall_seconds:         21626.4  (~6h 00m)
units_completed:            8
units_failed:                0
selected_pilot_instance_id: PILOT_EXECUTION-2026-004
```

Resultado por unidad (checkpoint real, `chunk_observation` de cada chunk
juzgado):

| Unidad | Agente | Documento | requirement_id | Chunks juzgados | Resultado |
|---|---|---|---|---|---|
| P1 | fda_part11_agent | RW-0005 | `21_CFR_11.10(e)` | 5 | `not_observed_in_chunk` en las 5 |
| P1 (repetido) | fda_part11_agent | RW-0005 | `21_CFR_11.10(e)` | 5 | `not_observed_in_chunk` en las 5 |
| P2 | fda_part11_agent | RW-0005 | `21_CFR_11.10(g)` | 10 | `not_observed_in_chunk` en las 10 |
| P4 | alcoa_plus_agent | RW-0011 | `ALCOA_ATTRIBUTABLE` | 5 | `not_observed_in_chunk` en las 5 |
| P5 | alcoa_plus_agent | RW-0005 | `ALCOA_CONTEMPORANEOUS` | 10 | `not_observed_in_chunk` en las 10 |
| P6 | fda_cgmp_211_agent | RW-0011 | `21_CFR_211.68(b)` | 5 | `not_observed_in_chunk` en las 5 |
| P7 | fda_cgmp_211_agent | RW-0012 | `21_CFR_211.68(b)` | 5 | `not_observed_in_chunk` en las 5 |
| N1 | eu_annex11_agent | RW-0005 | `ANNEX11_4` (negativo) | 5 | `not_observed_in_chunk` en las 5 (correcto) |

Suma de llamadas por unidad = 5+5+10+5+10+5+5+5 = 50, cuadra exactamente
con `total_calls_made` del evento de auditoría.

### Por qué P3 no se ejecutó en este batch

**P3 fue excluido del diseño del batch antes de gastar ninguna llamada
real** — no es un fallo de la corrida, es una decisión de diseño
documentada en `.claude/plans/sharded-riding-turing.md` (sección
"Hallazgos de la investigación", punto 4), tomada porque no había nada
real que medir para P3 con este mecanismo:

- La fase de juicio le da al modelo **solo** los chunks que
  `retriever.retrieve_top_k(document_sha256, req_id, k)` devuelve — nunca
  el documento completo. Si la página real de un positivo no entra al
  candidate pool, el modelo JAMÁS la ve, y el resultado (`not_observed`)
  estaría garantizado por construcción, no por una limitación real del
  juicio del modelo — medirlo así sería fabricar un dato, no diagnosticar
  nada.
- Ya estaba confirmado (sección "Corrección de P3 y re-medición" arriba,
  commit `1633216`) que la página real de P3 (p.45, `ANNEX11_17`) **no
  entra ni siquiera al top-10** de BM25 (rank 12 de 29) — ni con `k=5` ni
  con el `k=10` usado para P2/P5 en este mismo batch. Subir `k` más allá
  de 10 para forzar la inclusión de P3 habría disparado el costo de
  llamadas muy por encima del presupuesto disponible (`PILOT_EXECUTION-2026-004`,
  `max_calls=60`) sin garantía de que valiera la pena, y el diseño del
  batch (30 llamadas para P1/P4/P6/P7/N1/N2 a k=5 + 20 para P2/P5 a k=10
  = 50) ya usaba casi todo el margen (10 de 60).
- Causa raíz de por qué P3 no entra al top-10 en primer lugar (ya
  investigada y documentada arriba, sección "Investigación de P3"): un
  artefacto de extracción de PDF parte "retention" en `"retentio n"`
  (mismo tipo de artefacto de kerning que después resultó ser también la
  Causa 1 del diagnóstico de judgment_recall, más abajo) más dilución del
  chunk que mezcla la sección de retención con Historian/Audit
  Trail/Critical Data Records — ninguna de las dos causas es algo que el
  juicio LLM pueda resolver si nunca ve el chunk.

**Consecuencia**: `judgment_recall` se mide sobre 6 positivos (P1, P2,
P4, P5, P6, P7), no sobre los 7 originales del fixture — P3 queda
pendiente de una decisión previa (¿corregir la causa técnica de
extracción/dilución, o subir `k` gastando más presupuesto?) antes de que
tenga sentido incluirlo en cualquier medición de juicio futura.

```
judgment_recall (P1,P2,P4,P5,P6,P7) = 0/6
```

**Lectura honesta, sin maquillar**: las 6 unidades positivas del batch
dieron `not_observed_in_chunk` en el 100% de los chunks juzgados,
incluidas P1/P4/P6/P7 — que sí habían entrado al top-5 de la recuperación
pura (medición anterior, cero LLM). El único resultado correcto es el
negativo N1 (correctamente no observado). Esto es **peor que el baseline
de documento completo (2/7, H1-H4)**: reducir el candidate pool a los
chunks top-k de BM25 no mejoró el recall del juicio LLM, lo llevó a cero
en esta corrida — contradice la hipótesis de diseño de R2 (que un pool
más chico y enfocado ayudaría al juicio del modelo a encontrar evidencia
que sí está presente).

**No investigado en esta corrida** (registrado como pendiente, no
asumido): por qué P1 aparece dos veces en el batch con el mismo
`document_id`/`requirement_id` (dos `JudgmentUnit` distintos con el mismo
target); si el resultado 0/6 se debe a un problema del prompt/formato de
`per_unit_text` cuando recibe chunks ya recortados por BM25 en vez de
páginas completas (`JudgmentUnit` vs `PilotSampleUnit`, ver docstring de
`judgment.py`), a un defecto en cómo `evaluate_chunked` interpreta
`target_requirement_ids` con este tipo de entrada, o a otra causa
distinta. No se investiga ni se corrige nada de esto sin indicación
explícita — se deja documentado como el hallazgo real de esta corrida.

## Diagnóstico de judgment_recall=0/6 (2026-08-10) — tres causas raíz distintas, ninguna corregida

Investigado leyendo las respuestas crudas reales del modelo
(`factory/regulatory/pilot_run/checkpoints/raw_responses/chunked-*/task-*.txt.gz`,
nunca inventadas) y reproduciendo `retriever.retrieve_top_k()` +
`chunked_engine._is_anchored()` a mano contra el corpus real, sin
mockear nada. El 0/6 **no tiene una sola causa** — son tres mecanismos
distintos, cada uno con su propio caso real que lo evidencia.

### Causa 1 (confirmada, reproducible) — `_is_anchored` rechaza una cita real por un artefacto de extracción de PDF

Unidad P1 (`21_CFR_11.10(e)`, RW-0005, candidato rank-1 recuperado =
páginas 45-46): el modelo **sí encontró la evidencia real**
(`estado: cumple_parcialmente`, cita literal de 913 caracteres citando
UR3.3.1/UR3.3.2 completos, checkpoint `chunked-965e5cf6ee5d`, task
`b737fdf292e3`). La cita se rechazó igual (`chunk_observation` final =
`not_observed_in_chunk`) porque el texto fuente real, extraído del PDF,
contiene el artefacto de kerning `"wheneve r"` (espacio espurio que
parte "whenever" en dos) — el modelo cita la palabra correcta
("whenever"), `_is_anchored()` exige coincidencia literal exacta (tras
normalizar espacios) de la CITA COMPLETA contra el chunk, y esa única
palabra rota invalida el match completo (`in` sobre strings largos es
todo-o-nada, no tolera una palabra distinta en medio). Reproducido a
mano:

```python
from factory.regulatory.retrieval import retriever
from factory.regulatory.corpus_runner import _resolve_document_path
from factory.engines.gmpai_integrity.chunked_engine import _is_anchored, build_page_chunks

path, sha = _resolve_document_path('RW-0005')
cands = retriever.retrieve_top_k(sha, '21_CFR_11.10(e)', k=5)
chunks = build_page_chunks([c['text'] for c in cands])
_is_anchored(evidencia_real_citada_por_el_modelo, chunks[0]['text'])  # -> False
```

Mismo patrón exacto ya documentado para P3 (`"retentio n"` partiendo
"retention", ver "Investigación de P3" arriba) — no es un defecto nuevo
de R2, es una fragilidad preexistente de `_is_anchored` (substring
literal tras normalizar espacios) que ya afectaba al baseline, pero se
vuelve más visible aquí porque las citas evaluadas son largas (varias
frases) y basta que UN artefacto de kerning caiga en medio de la cita
para invalidar el match completo.

**Nota adicional encontrada, no atribuible a R2 pero relevante para
futuras corridas**: la unidad "N2" del batch (mismo `req_id`/documento
que P1, pensada como negativo de tabla de contenidos) recibió **el mismo
candidate pool que P1** (checkpoint `chunked-933350a6d3a3`, misma cita de
913 caracteres, mismo rechazo por anchoring) — `retrieve_top_k` depende
solo de `(document_sha256, req_id)`, nunca de qué caso de fixture se está
probando, así que P1 y N2, tal como están construidas hoy, no midieron
nada independiente entre sí en este batch.

### Causa 2 (confirmada) — el modelo afirma un estado positivo sin aportar cita

Unidad P2 (`21_CFR_11.10(g)`, RW-0005, k=10, checkpoint
`chunked-c353d90f9e9c`): en uno de los 10 chunks el modelo devolvió
`estado: cumple_parcialmente` pero `evidencia_exacta` **vacía**. El gate
de anclaje (`anchored = _is_anchored(evidencia, ...) if evidencia else
False`) trata correctamente una cita vacía como no anclada — el
comportamiento del gate es correcto, el problema es que el modelo violó
el contrato del prompt (afirmar cumplimiento sin evidencia citable). No
se investigó en este diagnóstico qué parte del prompt/formato lo originó
— queda como hallazgo, no como causa resuelta.

### Causa 3 (mayoría de los casos) — el modelo genuinamente no reconoce la evidencia en los candidatos que sí la contienen

Unidades P4, P5, P6, P7 y N1 (correcto): **todos** los chunks de estas
unidades — incluidos los que, según `retrieval_recall_at_5` (medición de
recuperación pura, arriba), sí contienen la página real (P4 rank 2, P6
rank 2, P7 rank 2) — recibieron `estado: evidencia_insuficiente` sin
ninguna cita, en el 100% de los chunks evaluados. Verificado a mano para
P6/P7 (`21_CFR_211.68(b)`, RW-0011): el candidato rank-2 real (páginas
12-14, `retriever.retrieve_top_k(sha, '21_CFR_211.68(b)', k=5)`) es
contenido denso de tablas de I/O (nombres de señales, tags,
descripciones técnicas) — la evidencia real que un evaluador humano
reconocería queda diluida entre mucho ruido tabular, mismo patrón de
dilución ya documentado para P3. Esto **no es un defecto de
`judgment.py` ni de la recuperación BM25** — es el mismo límite de
recall del modelo ya medido en H1-H4 (2/7), ahora confirmado
independientemente con un candidate pool más chico: reducir el pool no
ayudó al modelo a reconocer evidencia técnica/tabular parafraseada.

### Qué no se investigó en este diagnóstico (pendiente, si Cesar lo pide)

- Por qué el modelo omite la cita en un estado positivo (Causa 2) — no se
  leyó el prompt completo enviado en ese chunk específico para descartar
  un problema de formato/truncamiento del prompt.
- Si Causa 1 (fragilidad de `_is_anchored`) también explica parte del
  techo 2/7 del baseline original (H1-H4) — no se re-analizaron esas
  corridas viejas.
- Por qué P1 y "N2" comparten candidate pool (limitación de diseño de
  `query_builder.build_retrieval_query`, que depende solo de `req_id`) —
  reportado como hallazgo, sin propuesta de solución todavía.

## Pendiente de decisión de Cesar (siguiente paso)

1. **Causa 1** (`_is_anchored` frágil ante artefactos de kerning del
   PDF): ¿endurecer el anclaje para tolerar una palabra rota aislada
   (p.ej. permitir cierto grado de fuzzy-match en vez de substring
   exacto), con el riesgo real de aflojar un validador que hoy protege
   contra evidencia inventada — decisión sensible, nunca implícita?
2. **Causa 2** (positivo sin cita): ¿investigar el prompt real de ese
   chunk para entender por qué el modelo omitió la cita, antes de decidir
   si amerita una corrección?
3. **Causa 3** (mayoría de los casos, el modelo no reconoce evidencia
   técnica/tabular incluso con candidate pool curado): confirma que R2
   (BM25 + candidate pool más chico) **no resuelve** el techo de recall
   del modelo — cierra, con evidencia real, la hipótesis de diseño
   original de la fase de juicio de R2. Si Cesar quiere seguir atacando
   el recall, la alternativa de embeddings semánticos (diferida, no
   reabierta aquí) o un cambio de modelo vuelven a ser las opciones
   reales sobre la mesa.
4. Decidir si `factory/regulatory/retrieval/judgment.py` +
   `factory/tests/test_r2_judgment.py` (sin commitear) se commitean tal
   cual (como medición diagnóstica ya completa, con su resultado real
   documentado), se corrigen primero (Causa 1/2), o se descartan.
5. `retrieval_recall_at_5=4/7` (recuperación pura, sin cambios) sigue
   siendo válido como métrica de recuperación — las tres causas nuevas
   están en la fase de juicio, no en `retrieve_top_k`.
