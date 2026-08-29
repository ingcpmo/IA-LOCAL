# WP-E — INDEPENDENCIA DE MEDICIÓN Y MEDICIÓN SOBRE CORPUS REAL

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar
**Baseline de código:** `fix/clon-local-validacion` @ `760e0f4` (WP-D cerrado).
**Motiva:** D-3, NG-2, NG-3, NG-4, NG-5. **Restricción:** los fixtures ya firmados
(`technical_suite_c.yaml`, `technical_completeness_rules.yaml`) **no se tocan ni se re-puntúan**.

---

## WP-E.1 — Diagnóstico previo (SIN CÓDIGO) — EJECUTADO 2026-08-28

Prerrequisito de WP-E. Resultados ya incorporados a `PLAN_HARDENING…` NG-2 / NG-2b / NG-5:

- **NG-2 (0 vs 90 findings funcionales) — RECONCILIADA:** desincronización de versión. El "0" contó 3
  subtipos el 2026-08-27; el "90" es la E2E posterior con `REQUIREMENT_NOT_TESTED` (70) +
  `IMPLEMENTATION_WITHOUT_REQUIREMENT` (20) ya activos. **Línea base funcional real = 90 (70 artefacto de
  D-1 + 20).** El "0 findings / 0 FP" del reporte maestro §E queda obsoleto.
- **NG-2b (285 vs 342 regulatory) — RECONCILIADA:** la corrida archivada usó 5 documentos (sin RW-0009);
  342 = 57 × 6 con RW-0009 incluido. No es cambio de código.
- **NG-5 (aristas vacías) — DIAGNOSTICADAS una por una:** `tested_by`/`verifies` = STARVED_FROM_EXTRACTION
  (D-1, cerrado en WP-D bajo flag); `contradicts` = CORPUS_LIMITATION; `refers_to` = NOT_IMPLEMENTED en el
  builder (deuda separada D-8); `supports` = CORRECT_BY_DESIGN. `INTERFACE_INCONSISTENCY` y
  `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` **no ejercitados sobre datos reales** (TP real 0/0).

---

## WP-E.2 — Separación física builder / runner ; anchors ≠ frase literal

### D-3 confirmado en HEAD
`technical_suite_c.py` tiene `build_suite_c_corpus()` (builder del corpus) **y** `run_suite_c_dry/formal()`
(runner) en el mismo módulo; y `run_suite_c_dry` empareja findings por `c.anchor in f.source_text`, donde
`c.anchor` (p.ej. `"nightly backup of the application database"`) **es la frase literal** que
`build_suite_c_corpus` inserta. Acoplamiento de validez de constructo.

### Lo que WP-E hace (y lo que NO hace)
- **NO** se retrofitea `technical_suite_c` ni se re-puntúa su resultado firmado (TP=9, FN=C07, FP=0,
  recall 0.90). Queda **documentado como limitación conocida** del instrumento firmado.
- **SÍ** se establece el patrón correcto en el instrumento nuevo (WP-E.3): builder en un módulo
  **separado** (`held_out_corpus.build_seed_corpus`) del runner, y **match estructural** — el ground
  truth describe `(finding_class, subtype, document, page_band)`, **nunca** una cadena de texto que el
  detector deba contener. Verificado por test (`test_held_out_ground_truth_has_no_literal_phrase`,
  `test_held_out_builder_is_separate_module_from_suite_c_runner`).

---

## WP-E.3 — Corpus held-out (independiente por construcción)

| Componente | Ruta | Estado |
|---|---|---|
| Artefacto de ground truth | `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml` | **`DRAFT_UNSIGNED`** |
| Loader + builder separado + runner de match estructural | `factory/regulatory/validation_v2/held_out_corpus.py` | implementado |

**Independencia por construcción:**
- `assert_usable_as_gate()` es **fail-closed**: exige `status: SIGNED` **y** `author` **∉**
  `excluded_authors ∪ {signed_by de technical_completeness_rules.yaml}` = **∉ {"Capa 9 (Cesar)"}**.
  Mientras `author: null` / `DRAFT_UNSIGNED` → **no es un gate**; el runner devuelve números
  `reportable_range = NOT_A_GATE`.
- **Match estructural** (`match_policy.by = [finding_class, subtype, document, page_band]`,
  `page_band_tolerance = 3`). El ground truth no puede "escribir" la cadena que el detector busca.
- **Procedencia por caso** (validada en el loader):
  `REG` (derivado de cláusula normativa citada → `source_clause` obligatorio) ·
  `DOM` (conocimiento del revisor → `reviewer_rationale`) ·
  `ADV` (propuesto por máquina → entra **solo** con `human_approved: true`).
- **Umbrales fijados ex-ante** en `thresholds:` (aplican solo cuando `status == SIGNED`).

**Semilla sintética** (5 casos: 2 REG, 1 DOM, 1 ADV, 1 negativo). Corrida `run_held_out_dry()`:
`usable_as_gate=false`, TP 2/4, FN 2/4, FP 1, `reportable_range=NOT_A_GATE`, `document_egress_bytes=0`,
desglose por `provenance_tag`. **La semilla es un placeholder** — un autor independiente (QA/Validation,
≠ Capa 9) la reemplaza con casos reales, cita las cláusulas de los REG, aprueba los ADV, fija los
umbrales y firma. Solo entonces es un gate.

---

## WP-E.4 — Dos mediciones SEPARADAS sobre el corpus real (precisión ≠ recall ≠ especificidad)

**Corrección metodológica 2026-08-28.** Una muestra de findings **emitidos** solo contiene información
sobre lo que el sistema **sí** dijo. No permite derivar FN (lo que el sistema **no** dijo) ni TN.
Por eso hay ahora **tres artefactos distintos**, cada uno mide **una** cosa:

| Medición | Artefacto (ground truth) | Qué revisa QA | Métrica | Estado |
|---|---|---|---|---|
| **Precisión real / PPV** | `real_corpus_adjudication.yaml` (plantilla) + hoja `wpe4-qa-20260828.yaml` | los **40 findings emitidos** de la muestra | TP, FP, **PRECISION/PPV** (Wilson), proporción `COVERAGE_LIMITED` | `DRAFT_UNSIGNED` — 40 casos `PENDING` |
| **Recall real / FN** | `real_corpus_opportunities.yaml` | **el corpus** (URS/FS/DS), enumera las desviaciones que **deberían** detectarse — **sin** partir de los findings; luego **confirma** el match oportunidad↔finding (`matched_finding_id` + `match_confirmed_by` + `match_note`) | TP (confirmado), FN, **recall = TP/(TP+FN)** | `DRAFT_UNSIGNED` — `opportunities: []` |
| **Especificidad / TN** | `real_corpus_opportunities.yaml → negative_units` | secciones/unidades donde el control **está presente y completo** → el sistema **no** debe emitir finding | TN, especificidad | **UNKNOWN** — `negative_units: []` |

Scorer: `factory/regulatory/validation_v2/real_corpus_adjudication.py` (implementado).

### A) Precisión — `sample_for_adjudication()` + `score_emitted_review()`
1. `sample_for_adjudication(run_dir, n=40, seed=7)` → muestra **determinista**, **estratificada** por
   `(finding_class, subtype)` de una corrida `v2_runtime` persistida, **priorizando** los `would_degrade`.
   `sample_type: EMITTED_FINDINGS_REVIEW`; `label_options: [TP, FP, COVERAGE_LIMITED]`; ancla el
   `input_config_fingerprint`.
2. Adjudicador humano (QA/Validation — **nunca la máquina**) pone `label ∈ {TP, FP, COVERAGE_LIMITED}`.
   `COVERAGE_LIMITED` = el finding no es sólidamente evaluable en este corpus (mitad de prueba vacía /
   RW-0009 `NOT_ANALYZABLE`) → fuera de numerador y denominador, se reporta aparte.
3. `score_emitted_review()` → **fail-closed**: si aparece `FN` o `TN` en la hoja, **lanza**
   `AdjudicationMethodError` (no derivables de findings emitidos). Devuelve
   `PRECISION_REPORTABLE` (Wilson o `UNKNOWN`), `proportion_coverage_limited`, y
   **`RECALL_REPORTABLE = UNKNOWN` siempre** — envuelto en `metric_envelope`.

### B) Recall — `real_corpus_opportunities.yaml` + `score_recall()`
- QA lee **cada documento del corpus** y registra toda oportunidad de detección que **debería** existir,
  **independientemente** de si el analizador la emitió. Campos **obligatorios** por oportunidad
  (`OPPORTUNITY_REQUIRED_FIELDS`, los valida el scorer — si falta uno, **fail-closed**):
  `opportunity_id · expected_class · expected_subtype · document · page_band ·
  expected_topic_or_requirement · human_evidence_anchor · basis · reviewer_note`.
  **`human_evidence_anchor` y `basis` los completa QA, nunca la IA.**
- **`page_band` con validación ESTRICTA:** `[int, int]`, `start ≤ end`, ambos `> 0` — cualquier otra
  forma (float, string, longitud ≠ 2, negativo, invertido) → **fail-closed**. Ídem `negative_units.scope`.
- **El TP de recall depende de la CONFIRMACIÓN HUMANA de la correspondencia, no de inferencia
  estructural.** El scorer **propone** candidatos estructurales
  (`per_opportunity[].structural_candidate_finding_ids`) por `(class, subtype, document, página
  dentro de [page_band ± tolerance_pages])`, pero **no** los cuenta como acierto. QA rellena en cada
  oportunidad, al adjudicar:
  - `matched_finding_id` — el finding emitido que **QA confirma** que corresponde,
  - `match_confirmed_by` — quién lo confirma,
  - `match_note` — por qué corresponde.
  **TP** = oportunidad con match confirmado; **FN** = oportunidad sin match confirmado (aunque tenga
  candidatos estructurales).
- **Matching UNO-A-UNO** (fail-closed): un `matched_finding_id` no puede confirmarse en dos
  oportunidades; `matched_finding_id` y `match_confirmed_by` van juntos; el finding confirmado debe
  existir entre los findings emitidos de la corrida. `one_to_one = true` verificado.
- **`page_match_policy.tolerance_pages`** (**default 0**) es parámetro explícito del protocolo y
  **solo gobierna la propuesta de candidatos**, no el TP. Probado (`tol=0` → 0 candidatos;
  `tol=6` → candidatos), y `structural_match_alone_is_not_tp` (candidatos presentes → FN sin confirmación).
- Mientras `opportunities` esté `DRAFT_UNSIGNED` o vacío → **`RECALL_REPORTABLE = UNKNOWN`**
  (fail-closed, `usable=false`).

### C) Especificidad / TN
- **UNKNOWN salvo** que `negative_units` esté poblado y firmado, con `analysis_unit` explícita
  (`section | document | page_range` — qué **es** una unidad negativa) y anclaje humano. Campos
  obligatorios: `unit_id · analysis_unit · document · scope · expected_class · expected_subtype ·
  human_evidence_anchor · basis · reviewer_note` (`NEGATIVE_UNIT_REQUIRED_FIELDS`, fail-closed).
- **No se inventan TN.** Sin `negative_units`: `SPECIFICITY_REPORTABLE = UNKNOWN`, `TN = None`.

**Muestra de precisión regenerada hoy** (para QA): 40 casos, seed 7, 6 documentos,
`sample_type = EMITTED_FINDINGS_REVIEW`, los **mismos 40 `finding_id`** que la muestra anterior
(preservados; verificado por digest), todos `PENDING`.
`real_corpus_opportunities.yaml` y `negative_units` quedan **vacíos** → recall y especificidad reales
**siguen siendo UNKNOWN** hasta que QA los pueble y firme.

---

## WP-E — GATE: sobre de métrica (`metric_envelope.py`)

Toda métrica publicada **debe** viajar con los 5 campos o `require_envelope()` **lanza** (fail-closed):

```
metric · value · suite_version · size · definition · reportable_range · contamination_statement
```

`reportable_range` = intervalo `[lo, hi]` **o** uno de `{UNKNOWN, INDICATIVE_ONLY, NOT_A_GATE,
SYNTHETIC_ONLY}`. `value = None` **solo** permitido con un sentinel (métrica aún no medible).

**Consecuencia para las métricas ya publicadas:**
- `TECHNICAL_GATE = PASS (recall 0.90)` → `suite_version = technical_suite_c@1.0-benchmark (SIGNED)`,
  `size = 10 positivos`, `reportable_range = SYNTHETIC_ONLY` (corpus sintético del autor de las reglas),
  `contamination_statement = "autor del ground truth == autor de las reglas; anchors == frases del
  builder (D-3); sin corpus held-out ni muestra real adjudicada"`.
- `FUNCTIONAL_GATE = PASS (16/16)` → `reportable_range = SYNTHETIC_ONLY` (defect_corpus, mismo autor).
- El **rango reportable REAL** de ambos gates se obtendrá de WP-E.3 (held-out firmado por autor
  independiente) y WP-E.4: **precisión** de la muestra de 40 findings emitidos adjudicada por QA;
  **recall** del conjunto independiente de oportunidades de detección; **especificidad** solo si hay
  `negative_units` firmadas. **Hasta entonces: `SYNTHETIC_ONLY`**, y recall/especificidad reales `UNKNOWN`.

---

## LO QUE NECESITA UN HUMANO (no es código)

1. **Autor independiente** (QA/Validation, ≠ Capa 9) que pueble `held_out_technical_corpus.yaml` con
   casos reales, cite las cláusulas normativas de los `REG`, apruebe los `ADV`, fije los umbrales y firme.
2. **Adjudicador QA** que etiquete la muestra de 40 findings emitidos (`wpe4-qa-20260828.yaml`,
   labels `TP | FP | COVERAGE_LIMITED`) → produce por primera vez la **precisión real**.
3. **Autor QA independiente** que pueble `real_corpus_opportunities.yaml` revisando el corpus (no los
   findings), complete `human_evidence_anchor` y `basis` de cada oportunidad, **confirme** la
   correspondencia con cada finding (`matched_finding_id` + `match_confirmed_by` + `match_note`) o la
   deje sin confirmar (→ FN), y — si aplica — `negative_units` con `analysis_unit`, y firme. Solo
   entonces son reportables **recall** y **especificidad** reales.
4. **Capa 9**: firma del held-out (como Golden Dataset adicional, no sustituto) y aceptación del rango
   reportable resultante.

---

## RESTRICCIÓN Y ROLLBACK

- `technical_suite_c.yaml` / `technical_completeness_rules.yaml` **intactos**; su resultado firmado no se
  re-puntúa. El held-out es **adicional**.
- Aditivo: las suites actuales corren igual. Revertir WP-E = borrar los archivos nuevos
  (`held_out_corpus.py`, `real_corpus_adjudication.py`, `held_out_technical_corpus.yaml`,
  `real_corpus_adjudication.yaml`, `real_corpus_opportunities.yaml`) + los tests. Sin cambio de
  `EXTRACTION_VERSION`, sin re-derivación.

---

*Aditivo. Sin re-puntuación de fixtures firmados. Sin LLM, sin red, sin descargas. Artefactos held-out y
de adjudicación en `DRAFT_UNSIGNED` — pendientes de autoría/etiquetado humano y firma de Capa 9.*
