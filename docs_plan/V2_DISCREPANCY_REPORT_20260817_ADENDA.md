# V2 — Adenda al reporte de discrepancias: verificación de la decisión arquitectónica

**Fecha:** 2026-08-17. Responde a la "Decisión Arquitectónica — Corrección
de AD-1 y desbloqueo de V2" recibida de Cesar. **Cero llamadas LLM ni de
embedding ejecutadas al preparar esta adenda** (verificación 100% contra
código fuente y archivos persistidos en disco).

## Lo que la decisión arquitectónica acierta, verificado

1. **AD-1 corregido ("hasta k llamadas/requisito, agregación
   determinista, no agrupamiento") ya es exactamente lo que la
   implementación actual hace — no hace falta ningún cambio de código
   para esto.** `evaluate_chunked(per_unit_text=[k textos], full_document_
   coverage=False, ...)` nunca agrupó los k pasajes en un solo prompt:
   `build_page_chunks()` los trata como entradas independientes y, como
   cada candidato ya ronda `CHUNK_MAX_CHARS`, nunca se fusionan — el
   motor ya hace 1 llamada real por candidato, siempre. La ambigüedad de
   atribución cruzada que motivó la decisión nunca pudo haber ocurrido en
   el código real, porque el mecanismo de agrupamiento que se temía
   nunca se implementó.
2. **La agregación determinista que pide el Bloque A.3 ya existe y ya
   está conectada** — `factory/regulatory/semantic_evidence_verification.
   py::verify_sufficiency_aggregated()`, invocada por `chunked_engine.
   evaluate_chunked()` en la línea 1860 de `chunked_engine.py`, en el
   mismo camino que `full_document_coverage=False` ya usa. **No se
   necesita ni se escribió ningún código nuevo de agregación.**
3. **"Sin early-stop"** también ya es el comportamiento real: `evaluate_
   chunked()` procesa TODOS los chunks de la lista, siempre — no hay
   ninguna ruta de corte anticipado en el código actual.
4. **k=3 aplicado** (`v2_top_k_fusion_judgment_measurement.py`, `_K = 3`):
   justificado por los ranks reales de V1 (máximo medido = 3, P7) — no
   excluye ningún positivo conocido. 8 triples × 3 = **24 llamadas de
   juicio**, dentro del tope firmado de `PILOT_EXECUTION-2026-022` (25).
5. **`PILOT_EXECUTION-2026-021`/`-022` no necesitan una propuesta
   nueva** — el tope de 25 ya cubre 24.
6. **Modelo 7B confirmado como el correcto para V2** (Palanca A ya midió
   14B sin mejora) — no se toca el provider, consistente con la
   verificación de calificación ya reportada.

## Corrección factual necesaria: reuso del candidate pool de V1

La decisión afirma: *"V2 no debe construir ninguna consulta de embedding
nueva... V2 lee ese resultado ya persistido, no lo recalcula"* y
`EMBED_EXECUTION_NEW_REQUIRED = false`.

**Verificado contra el código y el disco — esta premisa no se sostiene
con el estado actual del sistema:**

- `judgment_candidate_pool.build_fusion_candidate_pool()` (la función que
  V1 y el intento de V2 usan) **calcula el ranking fusionado en cada
  llamada** — nunca persiste el resultado (la lista de candidatos
  rankeados con su texto/metadata). Solo persiste, en disco, dos cosas
  DISTINTAS y ya reutilizables sin costo:
  - `factory/regulatory/retrieval_index/*.json` — índice BM25 (chunks +
    términos), sin ranking por requisito.
  - `factory/regulatory/embedding_index/*.json` — **vectores de CHUNK**
    (26/26 RW-0005, 6/6 RW-0011, 8/8 RW-0012), reutilizables sin costo.
- Lo que falta y NO se persiste en ningún lado: el **vector de CONSULTA**
  (embedding del texto del requisito) y el ranking RRF resultante. Cada
  llamada a `build_fusion_candidate_pool()` recalcula la consulta vía
  `embed_runner.run_embed_batch(..., queries={req_id: texto})`, que
  **siempre** ejecuta `embed_mod.embed_text(text, model=model)` sin
  ninguna verificación de caché — confirmado en el código
  (`embed_runner.py`, rama de queries) y confirmado empíricamente: los 3
  intentos reales de esta sesión (V1 + 2 intentos de V2) gastaron
  8+8+8=24 embeddings de consulta reales, uno por cada invocación, para
  las MISMAS 8 triples cada vez.
- **`EMBED_EXECUTION-2026-002` está en 60/60 (0 remanente)**, confirmado
  en `factory_audit.jsonl`. Con 0 remanente, la primera llamada a
  `build_fusion_candidate_pool()` para cualquier triple —aunque ya se
  haya consultado antes— falla con `HARD_STOP_CALLS` antes de construir
  el pool. **No hay ningún camino de código actual que evite esto.**

**Lo que SÍ sería legítimo (no implementado aquí, pendiente de
decisión):** agregar una capa de persistencia de vectores de consulta
(cachear `query_vectors` por `requirement_id` la primera vez que se
calculan) para que corridas FUTURAS no vuelvan a pagar este costo. Eso
es un cambio de código real (no trivial: afecta el contrato de
`embed_runner.run_embed_batch`/`build_fusion_candidate_pool`, y decidir
si el caché de una consulta sigue siendo válido cuando cambia el
catálogo de requisitos es una decisión de diseño en sí misma) — no lo
implementé sin autorización explícita, y en cualquier caso **no ayuda a
esta corrida**: los vectores de consulta de las 8 triples nunca se
guardaron en ninguno de los 3 intentos reales ya hechos.

## Costo real recalculado para ejecutar V2 tal como está corregido

```
Llamadas de JUICIO:     8 triples x k=3 = 24   (cabe en PILOT_EXECUTION-2026-022, tope 25)
Llamadas de EMBEDDING:  8 consultas nuevas      (NO caben -- EMBED_EXECUTION-2026-002 en 60/60, 0 remanente)
```

**V2, con el diseño ya corregido (k=3, sin agrupar, agregación existente,
7B), sigue bloqueado — no por la arquitectura de juicio (ya correcta),
sino por presupuesto de embedding agotado.** El campo
`EMBED_EXECUTION_NEW_REQUIRED = false` de la decisión recibida no se
sostiene contra el estado real verificado; se necesitan como mínimo 8
llamadas de embedding nuevas (una ampliación de `EMBED_EXECUTION-2026-002`
o una nueva autorización de esa familia) antes de poder ejecutar V2.

## Estado del código

`v2_top_k_fusion_judgment_measurement.py` actualizado: `k=3`, comentarios
corregidos, **sin ejecutar**. Si se invocara tal cual con el estado
actual, fallaría de forma segura y explícita (`FusionCandidatePoolError`,
`HARD_STOP_CALLS`) en la primera triple, antes de gastar cualquier
llamada de juicio — el mismo patrón fail-closed ya usado en todo el
proyecto.

## Sin ejecutar, sin proponer, sin V2b

Ninguna llamada LLM ni de embedding se ejecutó al preparar esta adenda.
No se propuso ninguna `EMBED_EXECUTION` nueva (fuera del alcance
solicitado). V2b y fases posteriores sin tocar. Detenido para decisión
de Capa 9 sobre el único bloqueo real restante: presupuesto de embedding.
