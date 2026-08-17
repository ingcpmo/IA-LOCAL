# V1 — retrieval_recall_at_5 bajo chunking por sección (M2), resultado real

**Fecha:** 2026-08-17. **Fase:** `GMP_AI_FACTORY_ARQUITECTURA_OBJETIVO.md`
§"FASE M2 + V1". **Autorización usada:** `EMBED_EXECUTION-2026-002`
(human_confirmed, Cesar, 2026-08-10) — sin proponer una nueva, con
presupuesto vigente verificado antes de gastar una sola llamada.
**Costo real:** 34 llamadas de embedding esta corrida (26 chunks nuevos
de RW-0005 + 8 consultas únicas por par documento/requisito), acumulado
44/60 contra la autorización (16 de margen restante). Cero llamadas de
juicio LLM — instrumento 100% determinista salvo el embedding vectorial.

## Resultado crudo (sin ajustar la narrativa)

```
retrieval_recall_at_5   = 7/7   (positivos P1-P7, todos dentro del top-5 fusionado)
negatives_rejected_at_5 = 2/2   (N1/ANNEX11_4, N2/tabla de contenidos, ambos fuera del top-5)
```

**Criterio de la fase (bloqueante): ≥7/7 Y negativos 2/2 fuera — CUMPLIDO.**
No degrada el 7/7 ya medido en R2.2 con el chunking anterior; el resultado
es reproducido bajo el chunking nuevo (M2, sección-consciente para
RW-0005; fallback idéntico al legacy para RW-0011/RW-0012, que no tienen
Tabla de Contenido parseable).

## Detalle por caso

| label | documento | requirement_id | página objetivo | rank en pool fusionado |
|---|---|---|---|---|
| P1 | RW-0005 | 21_CFR_11.10(e) | 46 | 1 |
| P2 | RW-0005 | 21_CFR_11.10(g) | 40 | 1 |
| P3 | RW-0005 | ANNEX11_17 | 45 | **2** (antes: fuera del top-5, rank 9-20 según el fix — ver `test_r2_retrieval.py`) |
| P4 | RW-0011 | ALCOA_ATTRIBUTABLE | 13 | 1 |
| P5 | RW-0005 | ALCOA_CONTEMPORANEOUS | 46 | 2 |
| P6 | RW-0011 | 21_CFR_211.68(b) | 13 | 2 |
| P7 | RW-0012 | 21_CFR_211.68(b) | 14 | 3 |
| N1 | RW-0005 | ANNEX11_4 | 2 | fuera (null) |
| N2 | RW-0005 | 21_CFR_11.10(e) | 4 | fuera (null) |

**Hallazgo real, no buscado a propósito:** P3 (el caso que motivó la
Parte 2 de M2 — el chunk que mezclaba retención con contenido de
Security no relacionado) entra al top-5 real por primera vez en toda la
historia de este fixture (BM25 solo: fuera del top-10 original, top-10
tras el fix de kerning; BM25+fusión con chunking legacy: no medido
explícitamente pero el pool nunca se había reportado con P3 en rank
≤5). Con chunking por sección, rank 2. Consistente con la hipótesis de
M2 (menos ruido estructural en el chunk → mejor señal para BM25 y
embeddings), aunque este documento no aísla la causa exacta (fusión +
chunking cambiaron juntos, no una variable a la vez) — reportado tal
cual, no una prueba causal aislada.

## Construcción del índice, por documento

| documento | `toc_anchored` | chunks legacy | chunks sección-conscientes | fuente de embeddings usada |
|---|---|---|---|---|
| RW-0005 | True | 29 | 26 (índice `__section_aware`, nuevo, 26/26 embebidos esta corrida) | nuevo |
| RW-0011 | False | 6 | 6 (idéntico — fallback, ver M2) | legacy, ya embebido (0 llamadas nuevas) |
| RW-0012 | False | 8 | 8 (idéntico — fallback, ver M2) | legacy, ya embebido (0 llamadas nuevas) |

RW-0011/RW-0012 reutilizan sus embeddings legacy sin gastar una sola
llamada nueva — el chunking bajo `structure_aware=True` para estos dos
documentos es mecánicamente idéntico al legacy (sin Tabla de Contenido
parseable, `build_page_chunks` cae al chunking por tamaño de siempre),
así que se referenciaron por la clave legacy en vez de duplicar el
índice — decisión tomada ANTES de gastar presupuesto, no una
optimización posterior.

## Código que hizo esto posible (cambios de esta sesión, además de M2)

- `factory/regulatory/retrieval/indexer.py`: `build_index()`/`load_index()`
  ganan `structure_aware: bool = False` — bajo `True`, calcula
  `document_structure_extractor.extract_structure()` sobre el mismo
  `per_page_text` (pypdf) ya usado por el indexador y lo pasa a
  `build_page_chunks(structure=...)`; persiste bajo una clave de archivo
  distinta (`{sha256}__section_aware.json`) para nunca pisar el índice
  legacy.
- `factory/regulatory/retrieval/embed_index.py`,
  `factory/regulatory/retrieval/retriever.py`,
  `factory/regulatory/retrieval/embed_runner.py`,
  `factory/regulatory/retrieval/judgment_candidate_pool.py`: mismo
  parámetro `structure_aware: bool = False` enhebrado end-to-end, mismo
  patrón de default-preserva-comportamiento que el resto de M2. Sin este
  hilo, `embed_runner.run_embed_batch()` habría leído/escrito SIEMPRE la
  clave legacy (resuelve `document_sha256` real internamente vía
  `corpus_runner._resolve_document_path`), mezclando embeddings de dos
  chunkings distintos bajo el mismo `chunk_index` — corrupción de datos
  evitada, no solo un bug potencial.
- `factory/docs/design/regulatory_redesign_v2/v1_section_aware_recall_measurement.py`:
  script de medición (no un test permanente — llama a Ollama real vía la
  autorización vigente). Reusa exclusivamente los módulos ya
  gobernados/probados de R2.2/R2.3 (mismo patrón que el propio proyecto
  exige: nunca medir una config ganadora fuera del flujo real).

## Qué significa esto para el roadmap

El gate bloqueante de esta fase ("si la recuperación degrada, no se
avanza a M3") **no se activó** — M2 no degradó la recuperación, la
mantuvo en 7/7 y de hecho mejoró el rank de P3, el caso que motivó la
mitad de M2. **M3 (conectar `judgment_candidate_pool`/fusión al runner
de producción, modo `retrieval_mode` seleccionable) queda desbloqueada
para proponerse — no ejecutada todavía, pendiente de instrucción
explícita de Cesar**, mismo patrón de "una fase a la vez, diff mostrado
antes de la siguiente" ya establecido en el proyecto.
