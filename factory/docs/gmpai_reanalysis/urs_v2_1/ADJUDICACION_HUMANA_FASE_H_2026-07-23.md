# Adjudicación humana — Fase H (baseline formal), corrida URS v2.1

**Adjudicado por:** Cesar (Capa 9), 2026-07-23.
**Corrida adjudicada:** `w5v3-validation-2dbce2f4fb42` (121 llamadas, 11
requisitos aplicables × 11 chunks, documento
`215115305 SCADA-PCS Misc PLC System URS v2.1.pdf`,
SHA-256 `d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8`).
Referencias completas (con citas literales, gitignored,
`INTERNAL_VALIDATION_EVIDENCE`): `factory/regulatory/validation_evidence/
URS_V2_1_BASELINE_AUDIT.md` y `URS_V2_1_PIPELINE_COMPARISON.json`. Este
registro es la versión sanitizada de la decisión, apta para el repositorio.

**Regla de esta adjudicación:** ninguno de los tres puntos siguientes
modifica los artefactos crudos de la corrida (`result.json`, checkpoint,
`URS_V2_1_BASELINE_AUDIT.md`) — es una capa de decisión humana superpuesta,
igual que ya declaraba la nota de auditoría previa para `ANNEX11_4`.

## 1. ANNEX11_4 (gestión de riesgo del sistema computarizado)

**Decisión: RECHAZAR como evidencia.** La única cita verificada (página 5)
ancla literalmente pero coincide con el umbral de relevancia por una sola
palabra dentro del título de un estándar referenciado (tabla de
"Standards and Regulations"), no dentro de una descripción de un proceso
de gestión de riesgo del sistema en sí. Confirmado con la regla
determinista construida en Fase F de W5 V2
(`semantic_evidence_verification.detect_reference_list_context`, que
generaliza exactamente este patrón).

`conclusion_as_computed_by_pipeline = DOCUMENTED_AND_SUPPORTED` queda
**revertida** a `PENDING_EVIDENCE` para efectos de esta adjudicación — sin
evidencia sustantiva confirmada en esta corrida para `ANNEX11_4`.

## 2. 24 de los 25 `review_required` (patrón recurrente)

**Decisión: DESCARTAR EN BLOQUE, no en revisión individual.** Los 24
comparten la misma causa raíz ya identificada en la auditoría: mención
genérica y repetida de la familia regulatoria (21 CFR Part 11 / GAMP5) en
2 fragmentos reciclados del documento (chunk 2, págs. 4-5: lista de
normas referenciadas; chunk 9, pág. 21: beneficios genéricos de
cumplimiento), sin evidencia específica del requisito evaluado en cada
caso. Ninguno constituye evidencia sustantiva.

Requisitos afectados por este descarte en bloque: `21_CFR_11.10(a)`,
`21_CFR_11.10(d)`, `21_CFR_11.10(e)`, `21_CFR_11.10(g)`,
`21_CFR_11.50_11.70`, `ANNEX11_9`, `ANNEX11_12`, `ALCOA_ATTRIBUTABLE`,
`ALCOA_CONTEMPORANEOUS`, `ALCOA_ACCURATE` (más el remanente de
`ANNEX11_4`, ya adjudicado por separado en el punto 1).

## 3. 3 `rejected_by_verifier` (citation_not_found)

**Decisión: tratar como error técnico, no como fabricación del modelo.**
Los 3 casos (`21_CFR_11.10(a)` chunk 7/pág. 17; `21_CFR_11.50_11.70`
chunk 3/pág. 8 y chunk 7/pág. 17) quedan marcados `EVALUATION_INCOMPLETE`
— candidatos a reintento en una corrida futura (posible artefacto de
extracción/chunking, no una cita inventada por el modelo). Nunca se
cuentan como evidencia positiva ni negativa mientras no se reintenten.

## Efecto sobre el estado de la corrida

Con los 3 puntos anteriores adjudicados, ningún registro de esta corrida
queda sin resolución humana. Confirmado por revisión de
`absence_consolidator.consolidate()` (auditoría previa): ningún requisito
de esta corrida llegó a `DOCUMENTATION_GAP`, por lo que esta adjudicación
no revierte ninguna conclusión de ausencia documental — solo cierra el
estado de revisión pendiente sobre conclusiones ya `SUPPORTING_EVIDENCE_
UNDER_REVIEW`/`PARTIALLY_DOCUMENTED`.

```
ANNEX11_4_ADJUDICATED = REJECTED_AS_EVIDENCE
REVIEW_REQUIRED_24_ADJUDICATED = DISCARDED_AS_NOISE
REJECTED_BY_VERIFIER_3_ADJUDICATED = EVALUATION_INCOMPLETE_TECHNICAL_ERROR
ALL_PENDING_RECORDS_RESOLVED = true
FORMAL_BASELINE_READY = true
SAFE_TO_USE_AS_BASELINE = true
REGULATORY_COMPLIANCE = NOT_DETERMINED
```

`REGULATORY_COMPLIANCE` permanece `NOT_DETERMINED` — esta adjudicación
resuelve el estado de revisión pendiente de la corrida (Fase H), **no**
declara cumplimiento regulatorio, que sigue siendo una decisión humana
separada y posterior (QA/Validación, fuera de este roadmap).

---

## Precisión de alcance (reconciliación, 2026-07-28)

Esta nota **no modifica ninguna decisión de arriba**. Precisa a qué se
refiere el `FORMAL_BASELINE_READY = true` del bloque anterior, porque leído
sin contexto se confundió con el baseline formal del W5 actual.

`FORMAL_BASELINE_READY = true` aplica **exclusivamente a la corrida
histórica `w5v3-validation-2dbce2f4fb42`** (URS v2.1, motor anterior,
catálogo v1.0, 2026-07-23): ninguno de sus registros quedó sin resolución
humana. Es un hecho cerrado sobre esa corrida.

**No convierte esa corrida en el baseline formal del W5 V2 actual**, que
sigue bloqueado por razones ajenas a esta adjudicación — las 3 fuentes
regulatorias siguen sin reverificar y los 19 Evidence Packs siguen
provisionales:

```
HUMAN_ADJUDICATION_STATUS          = COMPLETED
HISTORICAL_URS_BASELINE_EXISTS     = true
CURRENT_W5_FORMAL_BASELINE_READY   = false
FORMAL_BASELINE_STATUS             = BLOCKED_PENDING_SOURCE_REVERIFICATION
SOURCE_VERIFICATION_STATUS         = PENDING_REVERIFICATION  (3/3 fuentes)
FORMAL_RELEASE_GATE                = BLOCKED
REGULATORY_COMPLIANCE              = NOT_DETERMINED
```

No se readjudicó nada: los 25 `review_required` y los 3
`rejected_by_verifier` quedaron resueltos aquí el 2026-07-23 y esa decisión
se conserva intacta.
