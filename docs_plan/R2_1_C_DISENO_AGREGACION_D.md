# R2.1 Opción C — Diseño: agregación de D (sufficiency) entre chunks

**Fecha:** 2026-08-10. **Estado: SOLO DISEÑO, nada implementado.** Este
documento se muestra para aprobación de Cesar antes de escribir una sola
línea de código de producción.

## 1. Diagnóstico exacto (recordatorio, ya confirmado con datos reales)

`semantic_evidence_verification.verify_sufficiency()` en sí **está bien
diseñada** — su regla "un criterio `NOT_ASSESSABLE` invalida todo el D"
es correcta *para el input que recibe*. El defecto real está en
`chunked_engine.py`:

- `verify_evidence_abcd()` (línea 1353) se llama **una vez por chunk**,
  con el `criterion_assessments` de ESE chunk únicamente.
- Al cerrar el requisito, se elige `best = candidates[0]` (línea 1627) —
  un solo candidato/chunk — y su `d_sufficiency` individual pasa a ser
  el D final del hallazgo (línea 1653). El resto de los chunks (que
  pudieron haber confirmado OTROS criterios) se descartan sin combinar.

Con 9 criterios mínimos típicos y un documento real donde ningún pasaje
único cubre los 9, el resultado es casi siempre `NOT_ASSESSABLE` — no
importa cuán bueno sea el recall.

## 2. Principio de diseño

**No tocar la lógica de `verify_sufficiency()`.** Su regla fail-closed
por criterio ya es correcta y ya tiene su propia protección de anclaje
(`verify_anchor`) y de contrato (`_find_contract_violations`) — tocarla
sería el mismo tipo de error que "aflojar `_is_anchored`" que ya se
evitó en Causa 1. **El fix es agregar el INPUT antes de evaluarlo**: en
vez de darle a `verify_sufficiency()` el `criterion_assessments` de un
solo chunk, darle la UNIÓN de lo que TODOS los chunks de esa unidad
confirmaron — reutilizando exactamente las mismas reglas de anclaje y
contrato que ya existen, solo aplicadas por chunk antes de combinar.

**Invariante que se preserva sin excepción**: la agregación combina
evidencia real y anclada de DISTINTAS SECCIONES DEL MISMO DOCUMENTO
para el MISMO requisito — nunca entre documentos distintos, nunca entre
requisitos distintos. Es exactamente lo que hace un revisor humano real
(leer todo el documento antes de concluir), no una relajación del
criterio de evidencia.

## 3. Mecanismo propuesto

### 3.1 Nueva función: `verify_sufficiency_aggregated()`

En `semantic_evidence_verification.py`, junto a `verify_sufficiency()`
(sin modificarla — queda intacta para todo llamador existente,
retrocompatible):

```python
def _classify_criteria_for_chunk(
    criterion_assessments: list, source_text: str, ordered_real_criteria: list,
) -> tuple[set, set, set, list, list]:
    """Extraido de verify_sufficiency() (líneas 277-301), sin cambiar su
    lógica -- helper reutilizado por el camino de un solo chunk (sin
    cambios) y por el camino agregado (nuevo). Retorna
    (confirmed_met, confirmed_not_met, confirmed_not_assessable, discarded_unanchored,
    contract_violations) para ESTE chunk únicamente."""
    violations = _find_contract_violations(criterion_assessments, ordered_real_criteria)
    if violations:
        return set(), set(), set(), [], violations
    # ... (mismo bucle que ya existe en verify_sufficiency(), líneas 288-301)


def verify_sufficiency_aggregated(
    requirement_id: str,
    per_chunk: list[tuple[list | None, str]],  # (criterion_assessments, chunk_source_text) por CADA chunk de la unidad
) -> tuple[str, str, dict]:
    """Mismo contrato de retorno que verify_sufficiency() (d_sufficiency,
    d_reason, detail) -- pero el input es la evidencia de TODOS los
    chunks de una misma unidad (documento + requirement_id), nunca uno
    solo. Reutiliza _classify_criteria_for_chunk() por chunk, nunca
    reimplementa el anclaje ni la validacion de contrato.

    Reglas de combinacion (nuevas, explicitas):
    - Un chunk con violaciones de contrato se EXCLUYE de la agregacion
      (no invalida a los demas chunks -- si TODOS los chunks violan
      contrato, cae a NOT_ASSESSABLE explicito con el detalle de cada
      violacion, igual que hoy para un chunk unico).
    - Un criterio queda MET si algun chunk lo confirma con anclaje real
      (verify_anchor PASS en el texto de ESE chunk).
    - CONTRADICCION (nueva, dura): si un criterio queda MET (anclado) en
      un chunk Y NOT_MET en otro -> NUNCA se resuelve en silencio.
      Se agrega a un set `contradicted`, fuerza el D final a
      NOT_ASSESSABLE con reason='CRITERION_CONTRADICTION_ACROSS_CHUNKS'
      y el detalle de en qué chunks. Mismo principio que
      `test_contradiction_between_chunks_is_detected_not_silently_resolved`
      ya aplica a nivel de estado/checkpoint.
    - Si no hay contradiccion: mismas reglas finales que
      verify_sufficiency() ya aplica (missing -> NOT_ASSESSABLE;
      not_assessable/discarded en al menos un criterio -> NOT_ASSESSABLE;
      todos MET -> MET; ninguno MET -> NOT_MET; mezcla -> PARTIALLY_MET).
    """
```

### 3.2 `chunked_engine.py` — dónde se conecta

Cambio mínimo, sin tocar A/B/C (siguen siendo por-chunk, correctos tal
como están):

1. Dentro del bucle actual por chunk (~línea 1352), **además** de
   llamar `verify_evidence_abcd()` como hoy (para A/B/C del candidato),
   acumular `(criterion_assessments, chunk["text"])` en un nuevo dict
   `criterion_assessments_by_req[req_id]` — uno por chunk, sin
   descartar ninguno.
2. Al cerrar cada requisito (donde hoy se hace `best = candidates[0]`,
   ~línea 1627), **después** de elegir `best` para A/B/C/evidencia
   textual (sin cambios ahí), llamar UNA vez:
   ```python
   d_status, d_reason, d_detail = sev.verify_sufficiency_aggregated(
       req_id, criterion_assessments_by_req[req_id])
   ```
3. Reemplazar `best.get("d_sufficiency")` (línea 1653) por `d_status`
   agregado — y recalcular `substantive_evidence_accepted`/
   `operational_result` combinando el A/B/C de `best` con este D
   agregado (mismo `ABCDResult`, solo con el campo D reemplazado —
   `substantive_evidence_accepted` ya es una property calculada sobre
   los 4 campos, no necesita cambios propios).
4. **Corrección durante la implementación** (2026-08-10): el punto 4
   original de este diseño ("mismo patrón para el pipeline verificado")
   partía de una suposición incorrecta. Verificado en código:
   `verified_pipeline_adapter.build_finding_record()` **nunca usa D** —
   `verified_records_by_req`/`verified_conclusions` solo llevan
   `chunk_observation`/`status` (observado o no), no sufficiency. El
   único lugar donde D llega a una conclusión final es el `Finding`
   legado (`finding_by_req`), que **ambos** pipelines (legado y
   verificado) leen para `_apply_preconditions()` — un solo punto de
   cambio (§3.2 puntos 1-3) alcanza para los dos, no hacía falta un
   segundo swap.

### 3.3 Alcance real de la mejora — límite honesto, no maquillado

**Esto ayuda mucho más al pipeline BASELINE (documento completo, todos
los chunks) que a la fase de JUICIO de R2 (top-k de BM25, k=5-10).** En
baseline, la agregación tiene acceso a TODO el documento — si el
criterio 5 vive en la página 12 y el criterio 2 en la página 46, ambos
chunks están entre los procesados y se combinan. En R2 (judgment.py),
el candidate pool es SOLO los k chunks que BM25 recuperó para el
`req_id` — si el resto de los criterios vive en páginas que BM25 no
priorizó, la agregación no tiene esos chunks para combinar y el
resultado seguiría siendo `NOT_ASSESSABLE` igual. **No se estima aquí
cuánto sube el recall real en cada pipeline** — requeriría re-correr
Golden Dataset (determinista, gratis) para baseline, y una nueva
re-medición real (con costo) para R2, ninguna de las dos hecha en este
diseño.

## 4. Plan de tests (deterministas, sin LLM — antes de cualquier commit)

Reutilizando datos reales ya capturados (mismo principio que Causa 1):

- **Caso P1 real reconstruido**: 5 chunks reales de la corrida de §4
  (`chunked-ff6bd88a4987`) — chunk 1 con 2 MET/2 NOT_MET/5
  NOT_ASSESSABLE, chunks 2-5 con `criterion_assessments` vacío/todo
  NOT_ASSESSABLE (contenido no relacionado). Verificar que el resultado
  agregado sigue siendo `NOT_ASSESSABLE` (los otros 4 chunks no aportan
  nada nuevo — este caso NO se rescata, y el test debe probarlo
  explícitamente, no asumirlo).
- **Caso sintético de rescate real**: 2 chunks sintéticos, cada uno con
  4-5 criterios MET anclados y el resto NOT_ASSESSABLE, sin solapamiento
  entre ellos y cubriendo los 9 reales entre los dos → agregado debe dar
  `MET`. Prueba que el mecanismo de agregación funciona cuando SÍ hay
  cobertura distribuida.
- **Caso de contradicción**: mismo criterio MET (anclado) en un chunk,
  NOT_MET en otro → debe degradar a `NOT_ASSESSABLE` con
  `CRITERION_CONTRADICTION_ACROSS_CHUNKS`, nunca resolverse en silencio.
  Test bloqueante, mismo criterio que el resto del proyecto.
- **Chunk con contrato violado entre chunks válidos**: un chunk con
  `criterion_index` inválido no debe invalidar a los demás chunks
  válidos de la misma unidad (excluir ese chunk, no todo el resultado).
- **Regresión**: `verify_sufficiency()` (sin agregación, un solo chunk)
  sigue exactamente igual — todos sus tests actuales deben seguir en
  verde sin modificarlos.
- **Regresión del Golden Dataset**: correr `run_all()` (determinista)
  con el cambio aplicado — debe seguir en 8/8 (o declarar
  explícitamente si algún caso cambia de resultado y por qué, nunca en
  silencio).

## 5. Qué NO cambia (reafirmado)

- `verify_sufficiency()` (un solo chunk) — intacta, mismo comportamiento
  para cualquier otro llamador.
- A (anclaje), B (fuente), C (relevancia semántica) — siguen siendo
  por-chunk/por-cita, sin cambios.
- Ningún umbral se afloja. Ninguna evidencia se acepta sin anclaje real
  en su propio chunk de origen.
- `retrieve_top_k`/`bm25.py`/`query_builder.py`/`indexer.py` — no
  tocados (mismo principio que R2.1 completo hasta ahora).

## 6. Siguiente paso

Si Cesar aprueba este diseño: implementar `_classify_criteria_for_chunk`
+ `verify_sufficiency_aggregated` + el cableado en `chunked_engine.py`
(§3.2, ambos pipelines legacy y verificado), con los tests del §4,
mostrar diff, correr suite completa, pedir aprobación de commit — mismo
protocolo de todas las corridas anteriores de R2.1. Después de eso,
recién ahí correr el Golden Dataset (gratis) para confirmar que sigue
8/8, y evaluar si vale la pena el plan de re-medición del §4 de
`R2_1_DECISION_PACKAGE.md` con esta mejora ya aplicada.
