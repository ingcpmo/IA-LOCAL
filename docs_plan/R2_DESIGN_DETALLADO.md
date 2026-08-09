# R2 — Diseño detallado: recuperación determinista de evidencia

**Fecha:** 2026-08-09. **Estado:** SOLO DISEÑO. No implementado, no ejecutado.
**Alcance autorizado:** `docs_plan/R1_CIERRE_Y_PREP_R2.md` sección 4 —
diseño + medición de recuperación pura (cero LLM). La fase de JUICIO
(recall real con LLM sobre los top-k) queda fuera, requiere
`PILOT_EXECUTION` nueva firmada por Cesar.

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

## Pendiente de decisión de Cesar antes de implementar

1. ~~¿Autorizar `chromadb`...?~~ — **RESUELTO 2026-08-09**: TF-IDF/BM25,
   stdlib puro, sin dependencia nueva (ver arriba).
2. Confirmar `k` (propuesto: 5, mismo orden de magnitud que
   `knowledge/retriever.py` usa hoy con `n_results=2`, ajustado al alza
   porque aquí no hay un LLM conversacional filtrando después).
3. Autorizar la implementación real (`bm25.py`/indexer/query_builder/
   retriever + tests) como corrida separada, con la medición de
   recuperación pura sobre RW-0005/RW-0011 (documentos de los 7
   positivos) como su entregable — sin tocar el juicio LLM todavía.
