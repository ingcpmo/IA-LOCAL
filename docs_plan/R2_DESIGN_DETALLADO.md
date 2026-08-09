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

`knowledge/retriever.py` (base gmp-api) es el único código Chroma
existente en el repo, y tiene un defecto real para nuestro caso: extrae
el PDF completo con `pypdf` concatenando TODAS las páginas antes de
chunkear (`_extract_text`), así que **pierde el número de página** — el
metadata de cada chunk solo guarda `{source, chunk, directory}`, nunca
`page_start`/`page_end`. R2 necesita mapeo chunk→página real (todo el
resto del sistema, desde `evidence_verifier` hasta `absence_consolidator`,
opera sobre rangos de página) — así que R2 **no reutiliza
`_extract_text`/`_split_text` de `knowledge/retriever.py`**, reutiliza en
su lugar `chunked_engine.build_page_chunks()` (ya tiene chunking
page-aware, ya probado, ya en producción) para construir los chunks a
indexar, y solo toma de `knowledge/retriever.py` el patrón de **cliente**
Chroma (`PersistentClient`, `hnsw:space: cosine`).

**Dependencia nueva para `factory/`**: no existe ningún cliente ChromaDB
en la capa `factory/` hoy (solo en soluciones cliente bajo
`workspaces/`/`deployments/`, capa de producto, no de plataforma). Añadir
`chromadb` como dependencia de `factory/` es una decisión de plataforma
nueva — señalada aquí explícitamente para que Cesar la vea antes de
autorizar la ejecución, no asumida en silencio. Alternativa sin
dependencia nueva evaluada y descartada por ahora: TF-IDF/BM25 puro
(stdlib o `scikit-learn`, ya usado en otras partes del repo) — más simple
pero peor recall semántico que embeddings; queda anotada como opción B si
Cesar prefiere no traer ChromaDB a la plataforma.

## Diseño del módulo

```
factory/regulatory/retrieval/
├── indexer.py       # construye/actualiza la coleccion Chroma de un documento
├── query_builder.py # construye la query desde el Evidence Pack (ver abajo)
└── retriever.py      # top-k determinista, mapeo a pagina, sin LLM
```

### `indexer.py` — indexación del documento objetivo

- Reutiliza `chunked_engine.build_page_chunks(per_unit_text, max_chars, overlap_chars)`
  para obtener los chunks reales (con `page_start`/`page_end`) — mismo
  chunking que ya usa el pipeline de juicio, para que un pasaje
  recuperado sea directamente comparable/reutilizable por
  `evaluate_chunked()` después.
- Una colección Chroma **por documento** (`document_sha256` como parte
  del nombre de colección — nunca mezclar documentos distintos en una
  sola colección, evita que un requirement_id de un documento recupere
  contenido de otro por accidente).
- Metadata por chunk: `{document_sha256, chunk_index, page_start, page_end,
  has_overlap_prefix}` — suficiente para que el consumidor reconstruya
  la ubicación real sin volver a tocar el PDF.
- Reindexación: si el documento ya tiene colección con el mismo
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
    page_end, text, distance}. NUNCA llama a un LLM. NUNCA decide si un
    candidato es evidencia valida -- eso sigue siendo trabajo exclusivo
    de evaluate_chunked()/verify_llm_output/absence_consolidator, R2 no
    los toca ni los antecede en autoridad, solo en orden de presentacion."""
```

`query()` de Chroma (`include=["documents","metadatas","distances"]`,
`n_results=k`) sobre la colección del documento — mismo patrón de
`knowledge/retriever.py:159-163`, sin filtros de metadata adicionales por
ahora (el filtro real es "una colección por documento", ya aplicado al
indexar).

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

1. ¿Autorizar `chromadb` como dependencia nueva de `factory/` (plataforma,
   no solo cliente), o preferir la alternativa B (TF-IDF/BM25 sin
   dependencia nueva)?
2. Confirmar `k` (propuesto: 5, mismo orden de magnitud que
   `knowledge/retriever.py` usa hoy con `n_results=2`, ajustado al alza
   porque aquí no hay un LLM conversacional filtrando después).
3. Autorizar la implementación real (indexer/query_builder/retriever +
   tests) como corrida separada, con la medición de recuperación pura
   sobre RW-0005/RW-0011 (documentos de los 7 positivos) como su
   entregable — sin tocar el juicio LLM todavía.
