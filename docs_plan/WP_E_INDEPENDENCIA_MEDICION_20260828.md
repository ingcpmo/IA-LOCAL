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

## WP-E.4 — Muestra adjudicada del corpus real → rango reportable

| Componente | Ruta | Estado |
|---|---|---|
| Plantilla de hoja de adjudicación | `factory/regulatory/requirement_catalog/real_corpus_adjudication.yaml` | **`DRAFT_UNSIGNED`** |
| Sampler + scorer | `factory/regulatory/validation_v2/real_corpus_adjudication.py` | implementado |

**Flujo:**
1. `sample_for_adjudication(run_dir, n, seed)` → muestra **determinista** y **estratificada** por
   `(finding_class, subtype)` de una corrida `v2_runtime` persistida, **priorizando** los findings con
   `would_degrade = true` (WP-B) porque son los que más informan el rango. Escribe una hoja con cada
   caso en `label: PENDING` y ancla el `input_config_fingerprint` de la corrida.
2. Un **adjudicador humano** (QA/Validation — **nunca la máquina**) rellena `label ∈
   {TP, FP, FN, TN, COVERAGE_LIMITED}`. `COVERAGE_LIMITED` = el finding no es sólidamente evaluable en
   este corpus (p.ej. depende de la mitad de prueba vacía / RW-0009 `NOT_ANALYZABLE`) → **se excluye del
   numerador y denominador** de recall/precisión y se reporta aparte.
3. `score_sheet()` → TP/FN/FP + **rango reportable** (intervalo de Wilson) + declaración de contaminación,
   envuelto en `metric_envelope`. **Sin etiquetas → `REPORTABLE_RANGE = UNKNOWN` (no publicable).**

**Muestra generada hoy** (para QA): 40 casos de una corrida de 6 documentos, seed 7; distribución por
subtipo incluye 16 `REQUIREMENT_NOT_TESTED`, 3 `ORPHAN_DESIGN_ELEMENT`, 3 `REGULATORY_INCONCLUSIVE`, etc.;
≥ 19 casos `would_degrade`. **Estado: PENDIENTE de etiquetado humano** → el rango reportable de los gates
FUNCIONAL/TÉCNICO sobre datos reales **sigue siendo desconocido** hasta que QA la adjudique.

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
  independiente) y WP-E.4 (muestra real adjudicada por QA). **Hasta entonces: `SYNTHETIC_ONLY`.**

---

## LO QUE NECESITA UN HUMANO (no es código)

1. **Autor independiente** (QA/Validation, ≠ Capa 9) que pueble `held_out_technical_corpus.yaml` con
   casos reales, cite las cláusulas normativas de los `REG`, apruebe los `ADV`, fije los umbrales y firme.
2. **Adjudicador QA** que etiquete la muestra de `real_corpus_adjudication` (40 casos generados hoy) →
   produce por primera vez el rango reportable de los gates sobre datos reales.
3. **Capa 9**: firma del held-out (como Golden Dataset adicional, no sustituto) y aceptación del rango
   reportable resultante.

---

## RESTRICCIÓN Y ROLLBACK

- `technical_suite_c.yaml` / `technical_completeness_rules.yaml` **intactos**; su resultado firmado no se
  re-puntúa. El held-out es **adicional**.
- Aditivo: las suites actuales corren igual. Revertir WP-E = borrar los 4 archivos nuevos + 1 yaml +
  el test. Sin cambio de `EXTRACTION_VERSION`, sin re-derivación.

---

*Aditivo. Sin re-puntuación de fixtures firmados. Sin LLM, sin red, sin descargas. Artefactos held-out y
de adjudicación en `DRAFT_UNSIGNED` — pendientes de autoría/etiquetado humano y firma de Capa 9.*
