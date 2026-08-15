# A.1 — Análisis de pérdida de información por transición

**Estado**: hallazgo de auditoría. No implementa nada. No modifica código.
**Fuente**: inspección de código real (file:line) + evidencia ya pagada en
`docs_plan/W5V2_PILOTO1_REPORTE.md` y checkpoints de
`factory/regulatory/pilot_run/checkpoints/`. Donde no hay evidencia
directa, se declara explícitamente en vez de asumir.

## Pipeline real auditado

```
ORIGINAL → EXTRACCIÓN → NORMALIZACIÓN → CHUNKING → RETRIEVAL → LLM → VALIDACIÓN
```

## ORIGINAL → EXTRACCIÓN

- Extractor real: `pdfplumber.extract_text()`
  (`factory/regulatory/document_structure_extractor.py:38-40`).
- **Pérdida confirmada — kerning**: el extractor parte palabras a mitad
  ("whenever" → "wheneve r", "retention" → "retentio n"), caso real
  RW-0005 p.45-46. Fix ya aplicado ANTES del chunking en
  `chunked_engine.py:594-604` (`_join_kerning_split_words`).
- **Pérdida confirmada — membrete de página (furniture)**: la plantilla
  Rockwell inserta texto de cabecera/pie repetido entre páginas
  consecutivas de un mismo chunk. Detectado y removido solo en la
  VERIFICACIÓN (`evidence_verifier.py:71-79`, `_PAGE_FURNITURE_RE`) — **no
  se remueve del texto que efectivamente ve el LLM**. Esto es una
  asimetría real: el verificador ve texto más limpio que el modelo de
  juicio.
- **Pérdida confirmada — viñetas de fuente privada**: U+F0B7
  (Wingdings/Symbol) reformateadas por el modelo como "- " ASCII al citar.
  Sin fix, el ratio de similitud de `SequenceMatcher` caía de 0.93 por 9
  caracteres de marcador — cero cambio real de contenido. Fix:
  `_strip_bullet_markers` (`evidence_verifier.py:86-104`).
- **Pérdida NO resuelta, declarada explícitamente en el propio código**:
  `document_structure_extractor.py` (docstring, líneas 9-16) reconoce que
  no distingue subsecciones sin numeración propia. Límite documentado, no
  parcheado.
- Metadata de estilo/fuente no se preserva en ningún punto — no hay
  evidencia de que esto haya causado un fallo real medido (distinto del
  caso de las viñetas U+F0B7, que sí se resolvió).

## EXTRACCIÓN → NORMALIZACIÓN

Los tres fixes de arriba (kerning, furniture, viñetas) son la
normalización real que existe hoy. No hay una etapa de normalización
separada y nombrada como tal — vive repartida entre `chunked_engine.py`
(antes del chunking) y `evidence_verifier.py` (en verificación, no en lo
que ve el modelo). Esta asimetría (furniture removido para el
verificador pero no para el LLM) es un hallazgo de esta auditoría, no
documentado antes.

## NORMALIZACIÓN → CHUNKING

- `chunked_engine.py:675-709` (`build_page_chunks`): agrupa páginas
  completas hasta `CHUNK_MAX_CHARS=6000` (línea 55), con solapamiento de
  cola (`overlap_chars`), separador `\n\f\n` entre páginas (línea 707).
- **No preserva estructura de tabla ni de sección.** Concatena texto de
  página como bloque plano.
- **Pérdida real confirmada por caso**: RW-0011 p.12 (0-based) mezcla una
  tabla completa de señales I/O ("Table 4-8: Vaporized Hydrogen Peroxide
  Signals") inmediatamente seguida de la prosa relevante para
  21_CFR_211.68(b)/ALCOA_ATTRIBUTABLE. Ver `BOTTLENECK_DIAGNOSIS.md` (A.2)
  para la cuantificación real del ratio prosa/ruido de este caso — es la
  base evidencial del caso P6/P7.
- P3 (chunk 45-46 mezcla retención documental con Historian/Audit Trail):
  citado en el brief como caso de pérdida de cohesión temática por
  chunking por página fija; no se reextrajo el chunk exacto en esta
  sesión (declarado, no verificado de nuevo — ya estaba documentado antes
  de esta auditoría).

## CHUNKING → RETRIEVAL

- BM25 solo: `retrieval_recall_at_5 = 4/7` (medido, R2).
- Fusión BM25 + embeddings locales (`nomic-embed-text`, RRF determinista):
  `retrieval_recall_at_5 = 7/7` (medido, R2, `docs_plan/R2_2_CIERRE_Y_
  CAPA_SEMANTICA.md`). Esta transición está **resuelta y medida** — no se
  encontró evidencia de pérdida adicional en retrieval más allá de lo ya
  cerrado en R2. No se re-deriva aquí.

## RETRIEVAL → LLM

Esta es la transición central del "muro" ya confirmado por R2 con tres
mediciones independientes: incluso con el chunk correcto entregado al
modelo (pool de fusión perfecto, evidencia en rank 2 de 5), el juicio
sobre P2/P5 se quedó en 0/2 (`PILOT_EXECUTION-2026-012`). La pérdida en
esta transición específica **es del modelo**, no de una etapa de
representación previa — confirmado, no hipótesis, para el caso de
evidencia parafraseada.

Reproducción aislada adicional (`docs_plan/W5V2_PILOTO1_REPORTE.md` §5):
con texto correcto y completo en el prompt, el modelo marcó 9/9 criterios
`NOT_ASSESSABLE`, `evidencia_exacta=""` en ese caso — mismo patrón.

## LLM → VALIDACIÓN

`evidence_verifier.verify_llm_output()` (líneas 192-266) es
determinista: no reintroduce pérdida propia, pero tampoco puede recuperar
lo que el modelo nunca extrajo. Es la etapa que **funciona** — filtra
"cumple_parcialmente sin cita" y otros falsos positivos; se mantiene
intacta por diseño (ver `EVIDENCE_ARCHITECTURE.md`).

## Resumen de pérdida por transición

| Transición | Pérdida confirmada | Resuelta hoy | Evidencia |
|---|---|---|---|
| Original→Extracción | kerning, furniture, viñetas privadas | Sí (3/3, salvo asimetría furniture LLM vs verificador) | `evidence_verifier.py:14-104`, `chunked_engine.py:594-604` |
| Extracción→Normalización | asimetría furniture LLM/verificador | No | hallazgo nuevo de esta auditoría |
| Normalización→Chunking | dilución prosa/tabla (P6/P7), pérdida de cohesión temática (P3) | No | `chunked_engine.py:675-709`, RW-0011 p.12 |
| Chunking→Retrieval | — (resuelto en R2) | Sí | `R2_2_CIERRE_Y_CAPA_SEMANTICA.md` |
| Retrieval→LLM | techo de juicio del modelo sobre evidencia parafraseada | No — es límite del modelo, no de pipeline | R2, `PILOT_EXECUTION-2026-012` |
| LLM→Validación | ninguna adicional (etapa determinista, funciona) | Sí | `evidence_verifier.py:192-266` |

**Conclusión honesta**: de las pérdidas reales identificadas, solo dos
quedan sin resolver: (1) la asimetría furniture LLM/verificador (barata de
corregir, sin caso de fallo medido que la atribuya directamente — riesgo
bajo, esfuerzo bajo); (2) la dilución prosa/tabla en chunking (posible
causa de P6/P7, sin experimento que confirme causalidad — ver
`BOTTLENECK_DIAGNOSIS.md`). El techo de juicio del modelo sobre evidencia
parafraseada (P2/P5) **no es una pérdida de esta cadena** — es un límite
de capacidad del modelo confirmado independientemente de cualquier mejora
de representación.
