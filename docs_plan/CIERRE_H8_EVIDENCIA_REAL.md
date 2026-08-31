# CIERRE H-8 — EVIDENCIA REAL DE DESEMPEÑO

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Gate previo:** **D-5** (adjudicación humana).
**Instrumento:** `docs_plan/PAQUETE_D5_ADJUDICACION_H8.md` · `H8_INSTRUMENT_READY = YES`.

---

## 0 · Estado — NORMALIZADO

```
D5_ADJUDICATION              = NOT_OCCURRED
D5_HUMAN_EVIDENCE_AVAILABLE  = NO
```

**Corrección de terminología (misión §1):** una redacción previa de este documento decía
`D-5 = APPROVED` interpretando la instrucción de misión "apruebo las firmas cesar" como si
D-5 estuviera cerrado. **No lo está.** Lo que existe es *autorización/preparación* del gate,
**no adjudicación humana de contenido**: los 40 casos QA40 siguen `PENDING`,
`opportunities: []`, `negative_units: []`, held-out `DRAFT_UNSIGNED`. La máquina **no puede**
y **no debe** sustituir la adjudicación (regla dura: `TP`/`FP`/`COVERAGE_LIMITED`, ground
truth, oportunidades y unidades negativas son trabajo humano).

En consecuencia, y **por diseño fail-closed**:

```
QA40_SAMPLE_PRECISION = UNKNOWN     (40/40 casos PENDING)
REAL_RECALL           = UNKNOWN     (0 oportunidades de detección enumeradas/firmadas)
REAL_SPECIFICITY      = UNKNOWN     (0 unidades negativas enumeradas/firmadas)
```

No se estima ninguna. `score_emitted_review()` y `score_recall()` devuelven `UNKNOWN` /
fail-closed hasta que exista el contenido humano.

---

## 1 · Lo que SÍ está listo y verificado (instrumento)

| Componente | Estado | Evidencia |
|---|---|---|
| **Muestra QA40** | 40 casos, `label: PENDING`, en ruta protegida `factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml` (runtime `:ro`, H-5F) | `qa40_finding_ids_sha256 = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32` — **inmutable**, no re-muestreada; estable bajo ENFORCE (D-2) porque `finding_id` no depende de la banda de riesgo |
| **Direccionamiento inequívoco (H-3)** | cada caso trae `finding_record_id` + `finding_id` + `case_id` determinista | — |
| **Evidencia por caso** | criterio/subcriterio, `regulatory_basis`/`technical_basis`, `document`/`section`/`page`/`source_hash`, ancla exacta SIN truncar, `evidence_basis`, `coverage_status`, `would_degrade`, `graph_path` (H-4), `proposed_machine_finding` (severidad, banda pre/post-ENFORCE, `machine_state`, `confidence`, `rationale`) | `real_corpus_adjudication.sample_for_adjudication()` extendida (aditiva) |
| **Oportunidades de detección + unidades negativas** | instrumento vacío, `DRAFT_UNSIGNED`, campos obligatorios + validación fail-closed | `factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml` |
| **Procedencia held-out** | REG / DOM / ADV; REG exige `source_clause`, ADV exige `human_approved` | `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml` (DRAFT_UNSIGNED) |
| **metric_envelope** | 5 campos (`metric`, `suite_version`, `definition`, `reportable_range`, `contamination_statement`) + intervalo de Wilson para muestras pequeñas | `factory/regulatory/validation_v2/metric_envelope.py` |
| **Contaminación declarada** | muestra determinista (seed=7) del run de referencia; etiquetado humano; `source_input_config_fingerprint` en la hoja | campos `contamination_statement` de `score_emitted_review` / `score_recall` |
| **Ruta protegida** | los 4 ficheros viven en `requirement_catalog/`, montado **read-only** en el runtime endurecido (H-5F) — el analizador **no puede modificarlos** | — |

---

## 2 · Qué falta para números reales (contenido humano — no lo produce la IA)

`docs_plan/PAQUETE_D5_ADJUDICACION_H8.md` §1-§4:

```
QA40_PENDING_CASES             = 40   -> label ∈ {TP, FP, COVERAGE_LIMITED} + human_evidence_anchor + held_out_provenance_tag ; luego status: SIGNED
DETECTION_OPPORTUNITIES_PENDING = 0   -> QA enumera OPP-xxxx leyendo el corpus (9 campos c/u) + confirmación de match (3 campos)
NEGATIVE_UNITS_PENDING          = 0   -> QA enumera NEG-xxxx (9 campos c/u)
HELD_OUT_SIGNATURE_PENDING      = YES -> revisar + status: SIGNED + rules_author
```

**Al recibir ese contenido**, la misión continúa automáticamente:
`QA40_SAMPLE_PRECISION = TP/(TP+FP)` (sobre 40 no-COVERAGE_LIMITED) + Wilson ·
`REAL_RECALL = TP/(TP+FN)` (oportunidades) · `REAL_SPECIFICITY = TN/(TN+FP_spec)` (unidades
negativas) — cada una con su `metric_envelope`; `UNKNOWN` si sigue faltando denominador.
Se regenera este documento con los valores reales.

---

## 3 · Campos de cierre

```
H8_INSTRUMENT_READY          = YES
H8_ADJUDICATION_DATA         = PENDING   (D5_ADJUDICATION=NOT_OCCURRED; contenido humano no provisto)
D5_HUMAN_EVIDENCE_AVAILABLE  = NO        (QA40 40/40 PENDING · opportunities [] · negative_units [] · held_out DRAFT_UNSIGNED)
H8_EVIDENCE_STATUS           = INCOMPLETE_PENDING_HUMAN_GROUND_TRUTH
QA40_SAMPLE_PRECISION        = UNKNOWN
REAL_RECALL                  = UNKNOWN
REAL_SPECIFICITY             = UNKNOWN
QA40_SHA (inmutable)         = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
QA40_RESAMPLED               = NO
FINDING_ADDRESSING           = finding_record_id (H-3)
PROTECTED_PATH               = factory/regulatory/requirement_catalog/  (runtime :ro, H-5F)
IA_SELF_ADJUDICATED          = NO  (0 TP/FP/COVERAGE_LIMITED/ground-truth/opportunity/negative_unit asignados por la máquina)
```

Verificación fail-closed en vivo (2026-08-30): `score_emitted_review(qa40_adjudication_sheet.yaml)`
→ `labeled=false`, `PRECISION_REPORTABLE=UNKNOWN`, `RECALL_REPORTABLE=UNKNOWN`;
`score_recall(...)` → `RECALL=UNKNOWN`, `SPECIFICITY=UNKNOWN`.

### Efecto sobre qualification (misión EJECUCIÓN AUTÓNOMA FINAL)

- **H-8 permanece INCOMPLETO para qualification.** `QUALIFICATION_BLOCKER = H8_HUMAN_GROUND_TRUTH_MISSING`.
- La ausencia de adjudicación D-5 **no bloquea** el trabajo técnico de **H-9** y **H-10**
  (extracción/OCR, `V2_TEST_EXTRACTION`, grafo), que son independientes de esa evidencia.
  El plan continúa automáticamente a H-9; H-8 se retoma sólo cuando exista la adjudicación
  humana (sin auto-re-adjudicación, sin inventar valores).
- Marcadores mantenidos: `HUMAN_FINAL_AUTHORITY=REQUIRED` · `PRODUCTION_ENABLEMENT=NOT_ENABLED` ·
  `REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM`.

H-8 queda **con el instrumento cerrado y las métricas reales en `UNKNOWN`** hasta la
adjudicación de contenido. La ejecución continúa con **H-9** (D-3 preautorizado).
