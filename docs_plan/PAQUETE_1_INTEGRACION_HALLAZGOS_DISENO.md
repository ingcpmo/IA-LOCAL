# PAQUETE 1 — Integración de hallazgos (causa raíz F + G) — DISEÑO, sin implementar

Fecha: 2026-08-19. Solicitado por Cesar: "empieza con el paquete 1".
Investigación de código previa (solo lectura, sin cambios) resumida abajo.
`CODE_CHANGED = 0` en este documento.

## Alcance exacto (según `VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md`, líneas 91-100)

1. **(a)** Generar candidatos NCR/CAPA/change-control desde un hallazgo
   real — SOLO detectar → sugerir clasificación → fundamento → cola
   humana. NUNCA cerrar CAPA/NCR automáticamente.
2. **(b)** Unificar `tier1_report.py` + `gap_assessment_finding_mapper.py`
   en un único artefacto de informe por hallazgo (evidencia + página +
   riesgo + recomendación + trazabilidad), reutilizando ambos módulos,
   sin inventar campos cuando falte el dato.
3. Incluye el cierre de hallazgo **A** (page_numbers) como parte de este
   paquete, no aparte.

## Lo que ya existe (confirmado en código, no supuesto)

### Hallazgo A — page_numbers: un solo caller real con el defecto

`build_page_chunks()` (`factory/engines/gmpai_integrity/chunked_engine.py:704-744`)
cae a numeración `1..N` por posición cuando no recibe `page_numbers` —
correcto SOLO si `per_unit_text` trae el documento completo en orden
desde la página 1.

Auditados todos los callers de `evaluate_chunked()`/`build_page_chunks()`
en producción (excluidos tests/calibración/workspaces gitignored):

| Caller | ¿Pasa `page_numbers`? | ¿Correcto? |
|---|---|---|
| `corpus_runner.py:395-409` | Sí | — |
| `corpus_runner.py:606-620` | Sí | — |
| `corpus_runner.py:757-767` | No | Correcto — documento completo en orden |
| `tier1_report.py:218-233` | No | Correcto — documento completo en orden |
| `retrieval/indexer.py`, `reverify_offline.py`, `run_validation_evidence.py`, `w5v2_evidence_run.py` | No | Correcto — documento completo en orden |
| **`regulatory/retrieval/judgment.py:169-188`** | **No** | **Defecto real** — `per_unit_text` es un pool de candidatos (`unit.candidate_chunks`, `full_document_coverage=False`), no el documento completo. El fallback 1..N etiqueta mal la página de cada chunk. |

**Cierre de A**: un cambio acotado y de bajo riesgo — pasar
`page_numbers=[c["page_start"] for c in candidate_chunks]` en
`judgment.py:169-188`, exactamente el mismo patrón ya usado en
`corpus_runner.py:606-620` para el mismo tipo de entrada (pool de
candidatos). No requiere decisión de Cesar — es una corrección técnica
directa, análoga a J.

### Parte (b) — informe unificado: qué hay que conectar, no rehacer

- `tier1_report.py::generate_tier1_report()` ya produce, por requisito,
  bucket + evidencia + página + `review_queue_rc_id` (cuando aplica) vía
  `RequirementOutcome`. Nunca corre LLM dos veces — reutiliza
  `evaluate_chunked()`.
- `gap_assessment_finding_mapper.py::map_finding_to_remediation_change()`
  ya produce, por finding, riesgo (`change_risk`/`change_risk_basis`) +
  recomendación (`proposed_content`/`change_reason`) + fundamento completo
  por campo (`rules: dict[str,str]`) — exactamente el "fundamento" que
  pide la parte (a) también.
- **El punto de unión real**: ambos consumen la MISMA fase intermedia
  (`absence_consolidator.consolidate()` dentro del pipeline verificado de
  `chunked_engine.py`), pero hoy nadie pasa el `DocumentConclusion` de uno
  al otro en producción — `gap_assessment_finding_mapper.py` acepta
  `verified_conclusion` opcional (línea 424-428, docstring: "ningún
  llamador de producción lo pasa todavía"). El artefacto unificado de (b)
  es, en esencia, **un nuevo generador que llama a los dos módulos
  existentes para el mismo `(run_id, requirement_id)` y combina sus
  salidas en un dict**, sin reescribir ninguno.

### Parte (a) — candidatos NCR/CAPA/change-control: el patrón de cola humana ya existe, la clasificación NO

`human_review_queue.py` ya tiene el patrón exacto que pide (a):
`enqueue_finding_for_review()` (fail-closed, `status="pending"` fijo,
`entry_type="finding_review"`, nunca auto-cierra) +
`GET /review-queue` + `POST /review/findings/{rc_id}/decide` (con
`Depends(require_identity)` desde el Paquete 2, validación de campos
según el tipo/conclusión). Extender este patrón con un `entry_type`
nuevo (p.ej. `"governance_candidate"`) y un endpoint hermano es mecánico.

**Lo que NO existe y hay que diseñar con Cesar**: la lógica de
CLASIFICACIÓN (¿qué hallazgo se sugiere como NCR, cuál como CAPA, cuál
como change-control?). Hay dos silos desconectados con enfoques
distintos, ninguno integrado a `review_queue.jsonl`:

- `factory/workspaces/lab_qc_project/app/rules.py` (workspace gitignored,
  no trackeado) — 10 reglas por keyword-matching sobre texto libre
  (`GMP_RULES`, `RuleResult(risk_level, action, regulatory_basis)`) —
  puramente advisory, nunca ejecuta nada.
- `factory/workspaces_archive/r6_change_control_20260625/app/models.py`
  (SÍ trackeado, pero archivado) — modelo de datos real
  (`CRStatus`, `CRPriority`, `ImpactAssessment` con
  `risk_level`/`validation_required`/`capa_required` derivados de
  `priority` por una tabla determinista) — **pero su propio endpoint
  `approve_change_request()` cambia `status` directo desde un POST, sin
  pasar por cola humana ni `mark_reviewed()`** — es precisamente el
  antipatrón que este paquete no debe copiar.

Ninguno de los dos silos define una regla real "esta ausencia/desviación
documental → sugerir NCR" vs "→ sugerir CAPA" vs "→ sugerir
change-control". Esa es una decisión regulatoria, no una que yo deba
inventar. Ejemplo concreto de la ambigüedad: un
`DOCUMENTATION_GAP` confirmado por `absence_consolidator` — ¿siempre
sugiere NCR (hallazgo documental puntual)? ¿CAPA si el mismo requisito ya
apareció ausente en una corrida anterior (recurrencia)? ¿Change-control
si la brecha implica que el procedimiento real no coincide con el SOP?

## Preguntas para Cesar antes de implementar

1. **Regla de clasificación real**: ¿qué mapea un `conclusion`/`bucket`
   de `absence_consolidator`/`tier1_report` a "candidato sugerido"?
   Propuesta mínima de arranque (defecto conservador, editable):
   - `DOCUMENTATION_GAP` confirmado (sin recurrencia conocida) →
     candidato NCR.
   - Mismo `requirement_id` + mismo `document_id` con
     `DOCUMENTATION_GAP` en ≥2 corridas distintas → candidato CAPA
     (recurrencia).
   - `SUPPORTING_EVIDENCE_UNDER_REVIEW` con `review_flags` que impliquen
     desviación de procedimiento (no solo falta de evidencia) → candidato
     change-control.
   - Todo lo demás: sin candidato sugerido (el humano puede clasificar
     manualmente, como ya ocurre hoy — `PRODUCTION_BLOCKER = NO` según el
     propio hallazgo F).
   ¿Aprobás esta regla de arranque, la ajustás, o preferís que el sistema
   NUNCA sugiera un tipo específico (solo "hay una brecha, clasificá vos")
   en esta primera iteración?
2. **Alcance de (a) en esta iteración**: ¿implementamos los 3 tipos
   (NCR/CAPA/change-control) de una vez, o arrancamos con NCR únicamente
   (el caso sin ambigüedad de recurrencia) y CAPA/change-control quedan
   para una iteración siguiente una vez validado el patrón con NCR?
3. **Fuente de recurrencia para CAPA**: detectar "mismo requisito ausente
   en ≥2 corridas" requiere leer corridas históricas (¿`corpus_runner`
   logs? ¿`decisions_v2.jsonl`? ¿un índice nuevo?) — ¿hay ya una fuente
   confiable de "historial de hallazgos por requisito+documento", o hay
   que construirla en este paquete?

## Lo que SÍ puedo ejecutar sin más decisiones de Cesar

- Cierre de **A** (`judgment.py` — pasar `page_numbers` reales del pool
  de candidatos): acotado, sin ambigüedad, mismo patrón que
  `corpus_runner.py:606`.
- Estructura del generador de informe unificado (parte b): combinar
  `RequirementOutcome` de `tier1_report.py` +
  `MappedChange`/`rules` de `gap_assessment_finding_mapper.py` para el
  mismo `(run_id, requirement_id)` en un solo dict — sin inventar campos
  cuando uno de los dos no tenga dato para ese requisito (p.ej. un
  requisito `CONFIRMED` nunca pasó por `gap_assessment_finding_mapper`
  porque no hay gap que mapear; el informe debe decir eso explícito, no
  omitir el campo en silencio).
- Estructura de cola humana para (a) (nuevo `entry_type`, endpoint
  hermano a `/review/findings/{rc_id}/decide`) — el ENVOLTORIO es
  mecánico; lo que falta es la regla de clasificación (pregunta 1).

## Propuesta de secuencia si Cesar aprueba

1. Cierre de A (independiente, sin dependencias, un commit propio).
2. Generador de informe unificado (b) — depende solo de módulos ya
   probados, sin necesidad de la regla de clasificación de (a).
3. Candidatos NCR/CAPA/change-control (a) — una vez resueltas las 3
   preguntas de arriba.

Cada uno con su propio commit, tests, y aprobación antes del siguiente —
mismo patrón que Paquete 2.
