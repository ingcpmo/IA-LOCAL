# Glosario canónico — vocabulario de clasificación (hallazgo E)

Cierra hallazgo E de `EVALUACION_FINAL_ANALIZADOR_GMP_Y_PLAN_CIERRE.md`:
"3 taxonomías coexisten (conclusion / bucket / status) sin Enum formal."
Este documento **solo consolida nombres — no cambia ningún comportamiento
de código**. Ninguna taxonomía se convirtió en Enum: sigue siendo texto
libre en cada módulo, ahora documentado en un solo lugar.

## Por qué existen 3-4 taxonomías distintas

Cada una responde una pregunta distinta, en una capa distinta del
pipeline. No son sinónimos — son niveles de abstracción diferentes sobre
el mismo hallazgo, más dos taxonomías de `status` de vidas útiles que no
tienen relación entre sí y comparten accidentalmente el nombre de campo.

## 1. `conclusion` — el veredicto más granular (nivel chunk/requisito)

**Dueño canónico**: `factory/engines/gmpai_integrity/chunked_engine.py`
(el verificador ABCD). Es la salida directa del pipeline de evaluación —
el vocabulario más detallado, nunca se resume aquí.

| Valor | Significado |
|---|---|
| `DOCUMENTED_AND_SUPPORTED` | Evidencia ancla, cita real verificada. |
| `PARTIALLY_DOCUMENTED` | Evidencia parcial, ancla pero no cubre todo el requisito. |
| `PROVISIONALLY_DOCUMENTED` | Igual que arriba, pero la fuente regulatoria sigue `PENDING_REVERIFICATION`. |
| `PROVISIONALLY_PARTIALLY_DOCUMENTED` | Parcial + fuente pendiente de reverificación. |
| `DOCUMENTATION_GAP` | Ausencia confirmada — todos los chunks relevantes evaluados, sin evidencia. |
| `PROVISIONAL_GAP` | Igual, con fuente `PENDING_REVERIFICATION`. |
| `EVALUATION_INCOMPLETE` | Cobertura no completa o algún chunk `rejected_by_verifier` — nunca se afirma nada positivo ni negativo. |
| `SUPPORTING_EVIDENCE_UNDER_REVIEW` | Hay evidencia candidata, pendiente de confirmación humana. |
| `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` | El candidate pool no trajo nada relevante. |
| `NOT_APPLICABLE` | El requisito no aplica a este tipo documental. |
| `CROSS_REFERENCE_MISSING` | La evidencia se espera en otro documento. |
| `NOT_OBSERVED_OPTIONAL` | Aplicabilidad opcional, sin evidencia — benigno. |

## 2. `bucket` — la misma clasificación, resumida para un informe humano

**Dueño canónico**: `factory/regulatory/tier1_report.py`. Es
`conclusion` (tabla 1) agrupado en 5 categorías más gruesas, vía
`_bucket_for_conclusion()` — **no es un concepto nuevo, es un renombre +
agrupación** del mismo dato.

| `bucket` | `conclusion` que agrupa |
|---|---|
| `CONFIRMED` | `DOCUMENTED_AND_SUPPORTED`, `PARTIALLY_DOCUMENTED`, `PROVISIONALLY_DOCUMENTED`, `PROVISIONALLY_PARTIALLY_DOCUMENTED` |
| `NEEDS_HUMAN_REVIEW` | `SUPPORTING_EVIDENCE_UNDER_REVIEW`, `DOCUMENTATION_GAP`, `PROVISIONAL_GAP`, `EVALUATION_INCOMPLETE`, `EVIDENCE_NOT_LOCATED_IN_CANDIDATES` |
| `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| `CROSS_REFERENCE` | `CROSS_REFERENCE_MISSING` |
| `OPTIONAL_NOT_OBSERVED` | `NOT_OBSERVED_OPTIONAL` |
| *(fail-closed)* | cualquier `conclusion` desconocida → `NEEDS_HUMAN_REVIEW`, nunca `CONFIRMED` |

## 3. `status` — TRES conceptos distintos que comparten nombre de campo

**Esto es el defecto real que describe el hallazgo E**: el mismo nombre
de campo (`status`) nombra tres vidas útiles sin relación entre sí, sin
prefijo que las distinga.

### 3a. `status` de entrada en cola de revisión (RC / finding_review)
**Dueño**: `factory/layer9/human_review_queue.py`.
Valores: `pending`, `approved`, `rejected`, `returned`, `superseded`.

### 3b. `status` de registro de decisión gobernada (decision_store_v2)
**Dueño**: `factory/services/decision_store_v2.py`. Campo libre fijado
por el caller — **no confundir con `decision_origin`** (campo aparte:
`agent_proposed` / `human_confirmed`, la garantía central de gobernanza).

### 3c. `status` de paquete de remediación (CandidatePackage)
**Dueño**: `factory/services/remediation_package_service.py`. Valores
incluyen `AWAITING_PACKAGE_DECISION` (consumido en vivo por
`factory/ui/js/mission_control/remediation.js`).

## Regla de lectura rápida

- ¿Hablás de un requisito individual, nivel chunk? → `conclusion`.
- ¿Hablás de un informe Tier-1 resumido para un humano? → `bucket`
  (siempre derivado de `conclusion`, nunca fuente independiente).
- ¿Hablás del ciclo de vida de una entrada en cola de revisión? → `status`
  (3a — `human_review_queue.py`).
- ¿Hablás del ciclo de vida de un registro de decisión gobernada? →
  `status`/`decision_origin` (3b — `decision_store_v2.py`).
- ¿Hablás del ciclo de vida de un paquete de remediación completo? →
  `status` (3c — `remediation_package_service.py`).

## Alcance explícitamente NO cubierto por este documento

- No se formaliza `conclusion` como Enum de Python (opcional en el
  hallazgo original) — tocar tipos reales en `chunked_engine.py` es un
  cambio de comportamiento potencial, fuera del alcance "solo
  documentación" de este paquete.
- No se renombra ningún campo en código ni en las respuestas de API —
  este glosario documenta el estado real, no lo cambia.
