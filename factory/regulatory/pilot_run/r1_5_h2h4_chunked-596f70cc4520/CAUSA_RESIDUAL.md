# Causa residual — por qué P5 no llega a "observed" pese a anclar de verdad

**Hallazgo, 2026-08-09, R1.5 Bloque 3.** No es un problema de recall del
modelo ni un defecto de la productización de `evaluation_profile=H2H4`
(esa parte funciona correctamente, ver `checkpoint.json`). Es un defecto
preexistente en `chunked_engine._is_topically_relevant()`, nunca antes
detectado porque los scripts experimentales H2/H4 no lo ejercían.

## Evidencia

1. **El modelo SÍ produjo una cita real y anclada:**
   `checkpoint.json` → `chunk_executions[0].raw_response` →
   `estado: "cumple_parcialmente"`,
   `evidencia_exacta: "FactoryTalk View SE provides an electronic signature feature for capturing operator actions performed in the production system. This feature is available in an E-Signature control, as well as the native button, numeric, and string input objects."`

2. **Verificado independientemente con el verificador REAL de producción**
   (`factory/regulatory/evidence_verifier.match_citation`, no una
   aproximación):
   ```
   match_citation(cita, texto_real_pagina_45) -> ("normalized", 1.0)
   ```
   Score perfecto. La cita existe literalmente en la página 45 del PDF
   real (`215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf`).

3. **`chunked_engine._is_anchored()` (el chequeo interno simplificado)
   también da `True`** sobre el mismo chunk real construido por
   `build_page_chunks()` — no es un problema de chunking ni de extracción
   de texto.

4. **Pero `_is_topically_relevant()` devuelve `False`:**
   ```python
   label = "Contemporaneous — registrado en el momento"  # ESPAÑOL
   quote = "FactoryTalk View SE provides an electronic signature..."  # INGLÉS
   _is_topically_relevant(quote, label)  # -> False
   ```
   La heurística (`chunked_engine.py` línea ~595) extrae palabras
   significativas (≥4 caracteres, sin stopwords) de la parte del label
   después del guión largo — aquí: `"registrado"`, `"momento"` — y exige
   que al menos una aparezca literalmente en la cita. Como el label está
   en español y el documento/cita están en inglés, **ninguna palabra
   española puede aparecer nunca** en una cita real de un documento en
   inglés. La heurística rechaza evidencia genuina por mismatch de
   idioma, no por falta de relevancia real.

5. **Consecuencia en `verified_records_by_req`:** como
   `_is_topically_relevant` es `False`, `valid_candidate` se vuelve
   `False` (línea ~1223: `valid_candidate = valid_candidate and
   topically_relevant`), y el candidato pasado a
   `verified_pipeline_adapter.build_finding_record` queda con
   `estado="evidencia_insuficiente"` (degradado) y `evidencia_exacta=""`
   — de ahí `chunk_observation: "not_observed_in_chunk"` en el registro
   verificado final, pese a que la cita original SÍ anclaba.

## Por qué H2/H4 (los scripts experimentales) no lo vieron

- `h2_experiment.py` mide anclaje con `ce._is_anchored(evidencia, doc_text)`
  **directo** — nunca llama a `_is_topically_relevant`.
- `h4_experiment.py` mide anclaje con
  `evidence_verifier.match_citation(evidencia, doc_text)` **directo** —
  tampoco llama a `_is_topically_relevant`.

El gate de relevancia temática (agregado 2026-07-16, post-mortem
C1-FDA-11.10d/C3-ANNEX11-12, para evitar que una cita real pero
FUERA DE TEMA se acepte como evidencia de un requisito distinto) es
exclusivo del camino real de `evaluate_chunked()`. Ninguna medición de
H1-H4 lo ejerció nunca. Es decir: **incluso una productización perfecta
de H2+H4 iba a chocar con este mismo rechazo en producción** — no es un
defecto de la productización de R1.5, es un defecto preexistente que
R1.5 fue la primera corrida en exponer, precisamente porque fue la
primera vez que se corrió H2+H4 por el flujo real completo.

## Alcance del hallazgo (no confirmado más allá de este caso)

Todos los labels de los prompts YAML gobernados
(`factory/engines/gmpai_integrity/prompts/*.yaml`) están en español; los
documentos fuente reales (Rockwell) están en inglés. Es razonable
sospechar que este mismatch afecta a más de un requirement_id, pero
**no se verificó sistemáticamente** — sería el primer paso de cualquier
corrida futura que decida corregir esto.

## Qué NO se hizo (y por qué)

No se modificó `_is_topically_relevant()`. Es un validador existente;
tocarlo está fuera del alcance autorizado de la corrida R1.5
(`docs_plan/R1_5_PRODUCTIZACION_H2H4.md`, que prohíbe R2 y cualquier cosa
más allá de la productización + validación). La prohibición central del
proyecto (nunca aflojar validadores para inflar recall) exige, además,
que cualquier corrección aquí se revalide contra el fixture set completo
— incluidos los negativos (`ANNEX11_4`) — antes de aplicarse, para
demostrar que no se abre una puerta a falsos positivos. Queda como
decisión pendiente de Cesar.
