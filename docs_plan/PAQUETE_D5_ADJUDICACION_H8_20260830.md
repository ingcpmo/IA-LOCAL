# PAQUETE D-5 — ADJUDICACIÓN HUMANA H-8 (evidencia real de desempeño)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Gate:** **D-5** — STOP humano OBLIGATORIO.
**Precede:** `docs_plan/CIERRE_D2_H7_ENFORCE_20260830.md` (D-2 = PASS · H-7 = CLOSED ·
`analysis_coverage_mode` efectivo = **ENFORCE**).

`H8_INSTRUMENT_READY = YES`. **La máquina construyó el instrumento VACÍO; NO lo rellenó.**
La IA **no puede** auto-asignar: `TP` · `FP` · `COVERAGE_LIMITED` · ground truth ·
`REAL_RECALL` · `REAL_SPECIFICITY` · oportunidad de detección real · unidad negativa real.
Ausencia de evidencia recuperada **no** se convierte en `FP`/`TP` automáticamente.

Sin la adjudicación humana, y por diseño fail-closed:
`QA40_SAMPLE_PRECISION = UNKNOWN` · `REAL_RECALL = UNKNOWN` · `REAL_SPECIFICITY = UNKNOWN`
(verificado: `score_emitted_review` y `score_recall` devuelven `UNKNOWN`).

---

## 0 · Cifras exactas

```
QA40_CASES_TO_ADJUDICATE          = 40    (todos `label: PENDING`)
DETECTION_OPPORTUNITIES_TO_ADJUDICATE = 0 enumeradas  -> QA las escribe leyendo el corpus
NEGATIVE_UNITS_TO_ADJUDICATE      = 0 enumeradas       -> QA las escribe
HELD_OUT_SIGNATURE_TO_PROVIDE     = 1    (held_out_technical_corpus.yaml: status DRAFT_UNSIGNED, rules_author null, 5 casos)
```

- **Muestra QA40 INMUTABLE.** `QA40_SHA = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32`.
  **No se re-muestrea.** Preservada bajo ENFORCE (el conjunto de `finding_id` no depende de la
  banda de riesgo). Direccionamiento por **`finding_record_id`** (H-3).
- **Corpus:** RW-0005 / RW-0006 / RW-0009 / RW-0011 / RW-0012 / RW-0014.
- Hoja generada bajo la config gobernada REAL (**ENFORCE**, `decision_ref D-2-H7-20260830`):
  `proposed_machine_finding` refleja la banda post-ENFORCE.

---

## 1 · ARTIFACT_PATHS (ruta protegida — el runtime endurecido la monta `:ro`, H-5F)

```
1. factory/regulatory/requirement_catalog/qa40_adjudication_sheet.yaml       (40 casos EMITIDOS -> precisión/PPV)
2. factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml     (oportunidades de detección -> recall ; unidades negativas -> especificidad)
3. factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml     (held-out técnico -> firma)
```

Verificado: `docker exec factory-api touch …/qa40_adjudication_sheet.yaml.probe` →
`Read-only file system`. El analizador **no puede** modificar estos ficheros.

---

## 2 · REQUIRED_HUMAN_FIELDS

### 2.1 · `qa40_adjudication_sheet.yaml` — por cada uno de los 40 casos

La hoja YA trae toda la evidencia disponible (no hay que buscarla): `finding_record_id`,
`finding_id`, `finding_class`, `subtype`, `criterion` / `subcriterion_ref`,
`regulatory_basis` / `technical_basis`, `document` / `section` / `page` / `source_hash`,
`anchored_quote` (texto exacto, SIN truncar), `evidence_ids`, `evidence_basis`,
`coverage_status`, `coverage_required_capabilities`, `would_degrade`, `graph_path`
(referencia al snapshot de grafo cuando aplica), `proposed_machine_finding`
(severidad, `risk_band`, `risk_band_pre_enforce`, `risk_mode`, `machine_state`, `confidence`, `rationale`).

**QA rellena SOLO:**

| Campo | Valores | Regla |
|---|---|---|
| `label` | `TP` \| `FP` \| `COVERAGE_LIMITED` | `TP` = desviación real y correctamente caracterizada · `FP` = no es desviación real, o caracterización incorrecta · `COVERAGE_LIMITED` = no evaluable sólidamente en ESTE corpus (p.ej. depende de la mitad de prueba vacía / RW-0009 `NOT_ANALYZABLE`). **`COVERAGE_LIMITED` sale del numerador Y del denominador de precisión.** |
| `human_evidence_anchor` | texto | cita / página EXACTA que sustenta la decisión |
| `adjudicator_note` | texto | por qué |
| `held_out_provenance_tag` | `REG` \| `DOM` \| `ADV` \| (vacío) | `REG` = expectativa de cláusula regulatoria citable · `DOM` = juicio de dominio GMP · `ADV` = adversarial/sintético |

**PROHIBIDO:** etiquetas `FN` / `TN` en esta hoja (no derivables de findings emitidos →
`score_emitted_review` falla cerrado). FN/recall → §2.2. TN/especificidad → §2.3.

**Al terminar los 40:** `status: SIGNED` · `adjudicator: "<nombre real>"` · `adjudicated_at: "<ISO-8601>"`.

### 2.2 · `real_corpus_opportunities.yaml` → `opportunities:` (recall real / FN)

QA lee EL CORPUS (no los findings) y registra toda desviación que DEBERÍA detectarse. Por
oportunidad (todos obligatorios; falta uno → `score_recall` falla cerrado):

```
opportunity_id · expected_class · expected_subtype · document · page_band ([int,int], start<=end, >0)
expected_topic_or_requirement · human_evidence_anchor · basis · reviewer_note
```
Confirmación de match (la pone QA al adjudicar; la IA NO):
```
matched_finding_id · match_confirmed_by · match_note
```
- `matched_finding_id` + `match_confirmed_by` juntos; el finding debe existir en la corrida.
- **Uno-a-uno:** un `matched_finding_id` no acredita dos oportunidades.
- Sin los 3 campos → esa oportunidad cuenta como **FN**.
- `recall = TP / (TP + FN)`.

### 2.3 · `real_corpus_opportunities.yaml` → `negative_units:` (especificidad / TN)

Por unidad (todos obligatorios):
```
unit_id · analysis_unit (section|document|page_range) · document · scope ([int,int], start<=end, >0)
expected_class · expected_subtype · human_evidence_anchor · basis · reviewer_note · human_verified: true
```
`TN` = unidad donde el analizador NO emitió el hallazgo prohibido · `FP_spec` = donde sí.
**No se inventan TN.** Sin unidades negativas: `SPECIFICITY_REPORTABLE = UNKNOWN`.

**Al terminar:** en `real_corpus_opportunities.yaml` → `status: SIGNED` · `adjudicator` · `adjudicated_at`.

### 2.4 · `held_out_technical_corpus.yaml` — firma

Revisar los 5 casos (`case_id`, `provenance_tag` ∈ {REG,DOM,ADV}, `expected`, `match`),
confirmar que los `REG` traen `source_clause` y los `ADV` traen `human_approved: true`, y firmar:
`status: SIGNED` · `rules_author: "<nombre real>"` (≠ autor del corpus semilla).

---

## 3 · HOW_TO_REVIEW

1. Editar los 3 ficheros **en el host** (el runtime los ve `:ro`; QA/Validation los edita fuera del contenedor).
2. Direccionar cada caso QA40 por `finding_record_id` (único; `finding_id` puede colisionar).
3. No modificar ningún campo de evidencia ya presente — solo añadir los campos humanos.
4. Firmar cada fichero (`status: SIGNED` + identidad real) cuando esté completo y revisado.
5. Avisar a Capa 8 con la ruta y el estado. La máquina entonces:
   - `QA40_SAMPLE_PRECISION = TP/(TP+FP)` sobre los 40 no-COVERAGE_LIMITED + intervalo de Wilson
   - `REAL_RECALL = TP/(TP+FN)` sobre las oportunidades
   - `REAL_SPECIFICITY = TN/(TN+FP_spec)` sobre las unidades negativas
   - cada métrica con su **metric_envelope** (5 campos + contaminación); `UNKNOWN` si falta denominador
   - regenera `docs_plan/CIERRE_H8_EVIDENCIA_REAL.md` con los valores reales
   - continúa a H-9 (gate **D-3** para descargas).

---

## 4 · Campos

```
H8_INSTRUMENT_READY               = YES
QA40_CASES_TO_ADJUDICATE          = 40
DETECTION_OPPORTUNITIES_TO_ADJUDICATE = 0 (enumerar)
NEGATIVE_UNITS_TO_ADJUDICATE      = 0 (enumerar)
HELD_OUT_SIGNATURE_TO_PROVIDE     = 1

QA40_SHA (inmutable)              = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
QA40_RESAMPLED                    = NO
FINDING_ADDRESSING                = finding_record_id (H-3)
GOVERNED_MODE_AT_GENERATION       = ENFORCE
PROTECTED_PATH                    = factory/regulatory/requirement_catalog/  (runtime :ro, H-5F)
IA_SELF_ADJUDICATED               = NO

REAL_RECALL / REAL_SPECIFICITY / QA40_SAMPLE_PRECISION = UNKNOWN  (fail-closed hasta adjudicación)
```

**STOP OBLIGATORIO EN D-5.** No se calcula ninguna métrica real, no se continúa a H-9, no se
inventa la adjudicación. Sin commit, sin push.
