# CAMPAÑA DE VALIDACIÓN POST-HARDENING — ANALIZADOR DOCUMENTAL GMP V2

**Fecha:** 2026-08-28 · **Autoridad:** Capa 9 = Cesar · **Tipo:** validación (read-only sobre código CODE-COMPLETE).
**BASELINE_ORIGINAL:** `c4e8296` (tag `pre-hardening-20260828` / `baseline/pre-hardening-original`).
**HARDENING_HEAD:** `ceae307` (WP-A … WP-G, PR #2 MERGED).

**Objetivo.** Demostrar con evidencia que los cambios corrigieron o contuvieron los problemas que
originaron el hardening, sin introducir regresiones, y declarar honestamente lo que aún **no** está
validado.

**Restricciones respetadas.** No se etiquetaron los 40 casos con IA · no se firmó ningún artefacto
humano · WP-B ENFORCE **no** activado · WP-D real **no** activado · `PRODUCTION_ENABLEMENT` sin cambio ·
sin cambios de código, sin rediseño.

---

## MATRIZ DE VALIDACIÓN (16 casos)

### 1 · Reproducibilidad WP-A
- **ORIGINAL_PROBLEM:** D-4 — `run_id` y `manifest.generated_at` wall-clock; sin digest que ligue inputs + versiones de artefactos + código + resultado.
- **BASELINE_BEHAVIOR:** dos corridas idénticas producían paquetes distintos (timestamps); "misma entrada ⇒ mismo resultado" no demostrable.
- **HARDENING_CONTROL:** `run_fingerprint.py` — `INPUT_CONFIG_FINGERPRINT` + `FINDINGS_FINGERPRINT` (identidad) separados de `RUN_ATTESTATION` (metadata); `SOURCE_ATTESTATION` = cierre estático de imports `factory.*` por AST.
- **TEST_METHOD:** 2 × `v2_runtime.run_v2_pipeline` sobre los 6 documentos; comparar los dos fingerprints; verificar que el timestamp difiere.
- **EXPECTED_RESULT:** ambos fingerprints idénticos; counts idénticos; timestamp distinto.
- **ACTUAL_RESULT:** `INPUT_CONFIG_FINGERPRINT` idéntico (`c46fbe67…`), `FINDINGS_FINGERPRINT` idéntico (`b5196a71…`), counts `342/90/24` idénticos, `timestamp_utc` distinto. `test_run_fingerprint.py` 23/23.
- **EVIDENCE_ARTIFACT:** `audit_summary/audit_metadata.json` de dos corridas; `factory/tests/test_run_fingerprint.py`.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** el fingerprint cambia ante cualquier edición de fuente (incl. comentarios) — comportamiento correcto, no riesgo.

### 2 · RW-0009 / extraction adequacy WP-B
- **ORIGINAL_PROBLEM:** NG-1 / D-2 — el pipeline procesaba un documento que no leyó y seguía adelante; no distinguía "el documento dice que no" de "no se pudo leer".
- **BASELINE_BEHAVIOR:** RW-0009 (2 páginas, 0 secciones, `toc_anchored=false`) entraba al análisis sin marca de inadecuación.
- **HARDENING_CONTROL:** `extraction_adequacy.py` — verdict `{ANALYZABLE, DEGRADED, NOT_ANALYZABLE}` por señales técnicas de extracción; **piso absoluto role-independiente** decisivo; `analysis_coverage.json` es artefacto de LIMITACIÓN, no Finding GMP.
- **TEST_METHOD:** `assess_corpus([6 docs])`.
- **EXPECTED_RESULT:** RW-0009 → `NOT_ANALYZABLE`; los otros 5 → `ANALYZABLE`; umbrales `DRAFT_UNSIGNED`.
- **ACTUAL_RESULT:** RW-0009 → `NOT_ANALYZABLE` por regla `absolute_floor:no_structure_and_thin`; RW-0005/0006/0011/0012/0014 → `ANALYZABLE`; `thresholds_signed = false`. `test_extraction_adequacy.py` 28/28.
- **EVIDENCE_ARTIFACT:** `analysis_coverage.json` de la corrida; `factory/tests/test_extraction_adequacy.py`; `docs_plan/WP_C_BENCHMARK_EXTRACCION_20260828.md`.
- **PASS_FAIL:** **PASS** (modo OBSERVE)
- **RESIDUAL_RISK:** las heurísticas son `DRAFT` — no gate hasta firma de Capa 9 (WP-B ENFORCE pendiente).

### 3 · `ABSENCE_DEPENDENT` / `INDETERMINATE`
- **ORIGINAL_PROBLEM:** el binario "presencia/ausencia" no modelaba la realidad; "ausencia" se confundía con "el método no pudo concluir".
- **BASELINE_BEHAVIOR:** ningún campo distinguía la base epistémica de un finding.
- **HARDENING_CONTROL:** `evidence_basis ∈ {PRESENCE, ABSENCE_DEPENDENT, INDETERMINATE}` — campo aditivo poblado por post-pass (`findings/evidence_basis.stamp`), sin tocar la lógica de ningún detector. `REGULATORY_INCONCLUSIVE` → `INDETERMINATE` (limitación de método). Sin valor `ABSENCE` puro.
- **TEST_METHOD:** clasificación por subtipo + histograma de una corrida real.
- **EXPECTED_RESULT:** `REGULATORY_INCONCLUSIVE` → INDETERMINATE; desviaciones por ausencia → ABSENCE_DEPENDENT; `INTERFACE_INCONSISTENCY` / `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` / `REGULATORY_COMPLIANT_EVIDENCE` → PRESENCE; ningún ABSENCE puro.
- **ACTUAL_RESULT:** corrida real (`analysis_coverage.json`): `by_basis = {INDETERMINATE: 348, ABSENCE_DEPENDENT: 108}`, PRESENCE 0 en este corpus, ABSENCE puro 0. Mapeo por subtipo verificado en `test_extraction_adequacy.py`.
- **EVIDENCE_ARTIFACT:** `analysis_coverage.json`; `factory/regulatory/findings/evidence_basis.py`; tests.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** ninguno relevante.

### 4 · Contaminación de `REQUIREMENT_NOT_TESTED`
- **ORIGINAL_PROBLEM:** NG-1 confirmado — 70 `REQUIREMENT_NOT_TESTED` (de 90 funcionales) son artefacto mecánico de `tested_by = 0` (D-1), no desviaciones reales.
- **BASELINE_BEHAVIOR:** los 70 se emitían como `MACHINE_DEVIATION_CANDIDATE` sin ninguna señal de que dependían de una región del grafo vacía.
- **HARDENING_CONTROL:** `coverage_dependencies` por finding (en `analysis_coverage.json`): `required_roles / required_capabilities / coverage_status / would_degrade / reason`. Modo OBSERVE: 0 supresiones, 0 Findings GMP nuevos, 0 cambio de risk/remediation/state.
- **TEST_METHOD:** corrida real de 6 documentos; inspeccionar `would_degrade_histogram` y los subtipos marcados.
- **EXPECTED_RESULT:** los 70 `REQUIREMENT_NOT_TESTED` + los 8 `ORPHAN_DESIGN_ELEMENT` salen `would_degrade = true` (capacidad `test_object_extraction` / `graph.tested_by_edges` ausente); 0 suprimidos.
- **ACTUAL_RESULT:** `would_degrade_true = 78` = `{REQUIREMENT_NOT_TESTED: 70, ORPHAN_DESIGN_ELEMENT: 8}`; `coverage_status = MISSING`; `reason = "capacidades ausentes: ['test_object_extraction', 'graph.tested_by_edges']"`. `suppressed = 0`, `new_gmp_findings = 0`.
- **EVIDENCE_ARTIFACT:** `analysis_coverage.json` → `coverage_dependencies` + `would_degrade_histogram`; `audit_metadata.wp_b_effect`.
- **PASS_FAIL:** **PASS** (contaminación surfaced y contenida; corrección efectiva = WP-B ENFORCE, pendiente de firma)
- **RESIDUAL_RISK:** en OBSERVE los 70 siguen visibles como findings — un consumidor que no lea `coverage_dependencies` los tomaría por reales. Se cierra con ENFORCE (decisión de Capa 9).

### 5 · Test extraction WP-D (sintético)
- **ORIGINAL_PROBLEM:** D-1 — `extract_document.py` sin etapa de extracción de `Test`; `build_test()` sin llamadores de producción; `test rows = 0` en los 6 documentos.
- **BASELINE_BEHAVIOR:** ningún objeto `Test` en el modelo canónico ⇒ mitad de prueba del grafo inanida.
- **HARDENING_CONTROL:** `extract_tests.py` (parser determinista + guardas anti-FP) + etapa aditiva en `extract_document.py` **gobernada por flag `V2_TEST_EXTRACTION` (OFF por default)**; con OFF la salida es idéntica y `EXTRACTION_VERSION` no cambia.
- **TEST_METHOD:** `wp_d_test_extraction.run_wp_d_synthetic()` — URS + FS + SAT sintéticos; el cuerpo del SAT pasa por `extract_tests_for_document` (código real) con 6 casos válidos + 5 líneas-ruido.
- **EXPECTED_RESULT:** exactamente 6 `Test` (SAT-001..006); las 5 líneas-ruido (paginación, TOC, cabecera, prosa sin id, id pelado) NO generan test; `document_egress_bytes = 0`.
- **ACTUAL_RESULT:** `N_TESTS_EXTRACTED = 6`, ids `SAT-001..SAT-006`, `ANTI_FP_OK = true`, `ALL_PASSED = true`, `egress = 0`. `test_extract_tests.py` 22/22 (incl. E2E con PDF sintético: flag OFF → 0 tests + versión base; flag ON → tests + `+tests-v1`).
- **EVIDENCE_ARTIFACT:** `factory/regulatory/validation_v2/wp_d_test_extraction.py`; `factory/tests/test_extract_tests.py`.
- **PASS_FAIL:** **PASS** (sintético)
- **RESIDUAL_RISK:** validado solo sintéticamente. Sobre el corpus RW real, `tested_by` sigue en 0 (ver caso 16).

### 6 · `tested_by` / `verifies` (sintético)
- **ORIGINAL_PROBLEM:** NG-5 — `tested_by` = 0 y `verifies` = 0 en el corpus real (STARVED_FROM_EXTRACTION); el linker de `graph/build.py` estaba correcto pero inanido.
- **BASELINE_BEHAVIOR:** con 0 nodos `Test`, `_link_to_tests` y `verifies` nunca disparaban.
- **HARDENING_CONTROL:** WP-D puebla nodos `Test`; `graph/build.py` **NO se toca** (linker ya correcto).
- **TEST_METHOD:** `run_wp_d_synthetic()` — comparar `edges_by_rel` contra la verdad-terreno del fixture.
- **EXPECTED_RESULT:** `tested_by > 0`; 0 regresión en `implemented_by` / `designed_by`; `REQUIREMENT_NOT_TESTED` solo para los requisitos no probados.
- **ACTUAL_RESULT:** `tested_by = 12` (de 0); `implemented_by = 8` (sin cambio); `designed_by = 0` (no hay DS en el fixture); `REQUIREMENT_NOT_TESTED` solo para `UR-WD-007/008`. **`verifies` NO aparece en `edges_by_rel`** — el SAT sintético no cita ids del catálogo de requisitos, y la arista `verifies` liga `test → requirement` del catálogo.
- **EVIDENCE_ARTIFACT:** `run_wp_d_synthetic()` → `edges_by_rel`; `factory/tests/test_extract_tests.py::test_wp_d_synthetic_gate_passes`.
- **PASS_FAIL:** **PASS** sobre el gate declarado del PLAN (`tested_by > 0` + 0 regresión).
- **RESIDUAL_RISK:** la arista `verifies` no está ejercitada — requiere un SAT que cite ids del catálogo (21 CFR / Annex 11). No demostrada.

### 7 · WP-E `metric_envelope`
- **ORIGINAL_PROBLEM:** NG-3 — métricas de gate publicadas sin tamaño de muestra, definición ni declaración de contaminación.
- **BASELINE_BEHAVIOR:** `TECHNICAL_GATE = PASS (0.90)` se citaba sin contexto.
- **HARDENING_CONTROL:** `metric_envelope.py` — `require_envelope()` fail-closed sobre 5 campos (`suite_version + size + definition + reportable_range + contamination_statement`); `reportable_range ∈ [lo,hi] | {UNKNOWN, INDICATIVE_ONLY, NOT_A_GATE, SYNTHETIC_ONLY}`; `value=None` solo con sentinel; intervalo de Wilson.
- **TEST_METHOD:** invocar `require_envelope` con campos faltantes; `wrap` con los 5; `wilson_interval(9,10)`.
- **EXPECTED_RESULT:** `require_envelope` lanza si falta un campo; `wrap` produce los 5; Wilson devuelve `[lo,hi]` válido.
- **ACTUAL_RESULT:** `fail_closed = true`; `wrap` cubre los 5 campos; `wilson_interval(9,10) = [0.5958, 0.9821]`. `test_wp_e_measurement_independence.py` 14/14.
- **EVIDENCE_ARTIFACT:** `factory/regulatory/validation_v2/metric_envelope.py`; tests.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** el gate solo obliga donde se invoca; su adopción en todas las métricas publicadas es convención, no forzada globalmente.

### 8 · Held-out — status
- **ORIGINAL_PROBLEM:** D-3 — `technical_suite_c` con builder de corpus acoplado al runner; `anchor` == frase literal insertada por el builder; ground truth del mismo autor que las reglas.
- **BASELINE_BEHAVIOR:** el benchmark técnico "probaba que la regla dispara en un documento escrito para que dispare".
- **HARDENING_CONTROL:** `held_out_technical_corpus.yaml` (`DRAFT_UNSIGNED`) + `held_out_corpus.py` — builder `build_seed_corpus` **separado** del runner; **match estructural** `[finding_class, subtype, document, page_band]`; procedencia `REG/DOM/ADV`; `assert_usable_as_gate()` fail-closed exige `SIGNED` **y** `author ∉ {autor de las reglas}`.
- **TEST_METHOD:** `status()`, `is_usable_as_gate()`, `assert_usable_as_gate()`, `_rules_author()`, `run_held_out_dry()`.
- **EXPECTED_RESULT:** `DRAFT_UNSIGNED`; no usable como gate; `assert` lanza; `rules_author == "Capa 9 (Cesar)"`; dry-run `reportable_range = NOT_A_GATE`; egress 0.
- **ACTUAL_RESULT:** `status = DRAFT_UNSIGNED`, `usable_as_gate = false`, `assert_raises = true`, `rules_author = "Capa 9 (Cesar)"`, `dry_range = NOT_A_GATE`, `egress = 0`. `test_wp_e_...` verifica que un firmado por el MISMO autor sigue sin ser gate y por un autor independiente sí lo sería.
- **EVIDENCE_ARTIFACT:** `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml`; `held_out_corpus.py`; tests.
- **PASS_FAIL:** **PASS** (mecanismo) · **BLOCKED_HUMAN** (uso real)
- **RESIDUAL_RISK:** el rango reportable REAL del gate técnico depende de que un autor independiente (≠ Capa 9) pueble y firme el held-out. Hasta entonces: `SYNTHETIC_ONLY`.

### 9 · Muestra real de 40 casos (WP-E.4)
- **ORIGINAL_PROBLEM:** NG-4 — el rango reportable de los gates no transfiere al corpus real; nunca hubo TP/FP sobre datos reales.
- **BASELINE_BEHAVIOR:** el "0 findings / 0 FP" del reporte maestro §E quedó obsoleto tras la ampliación de subtipos (línea base real = 90, 70 de ellos artefacto de D-1).
- **HARDENING_CONTROL:** `real_corpus_adjudication.py` — `sample_for_adjudication()` produce una **hoja de tipo `EMITTED_FINDINGS_REVIEW`**: muestra DETERMINISTA, estratificada por `(class, subtype)`, prioriza `would_degrade`, todos los casos son **findings EMITIDOS**. `label_options` = `{TP, FP, COVERAGE_LIMITED}` — **sin FN/TN**. `score_emitted_review()` calcula **PRECISION/PPV** (= TP/(TP+FP)) + intervalo de Wilson + proporción `COVERAGE_LIMITED`, y **falla cerrado** ante etiquetas `FN`/`TN`.
- **ALCANCE METODOLÓGICO (correcto):** una muestra de findings **emitidos** permite medir **directamente**: `TP`, `FP`, `PRECISION/PPV`, `proporción COVERAGE_LIMITED`. **NO permite medir `recall` / `FN` / `TN`** — no contiene información sobre desviaciones que deberían haberse detectado y **no** se emitieron. `RECALL_REPORTABLE = UNKNOWN` (siempre, en este conjunto).
- **PARA MEDIR RECALL/FN:** se define un **segundo conjunto humano independiente**, `real_corpus_opportunities.yaml` (`DRAFT_UNSIGNED`) — QA revisa **el corpus** (no los findings) y enumera las oportunidades de detección que deberían existir. Cada oportunidad **debe** traer los 9 campos de `OPPORTUNITY_REQUIRED_FIELDS` (`opportunity_id · expected_class · expected_subtype · document · page_band · expected_topic_or_requirement · human_evidence_anchor · basis · reviewer_note`); **`human_evidence_anchor` y `basis` los completa QA, nunca la IA**; si falta un campo, `score_recall()` **falla cerrado**. `score_recall()` cruza esas oportunidades contra los findings emitidos con **matching UNO-A-UNO** (conjunto `consumed`: un mismo finding acredita **a lo sumo una** oportunidad; `one_to_one` verificado) → `TP`/`FN` → `recall`. La coincidencia de página es un **parámetro explícito del protocolo**, `page_match_policy.tolerance_pages` (**default 0** = la página del finding cae **dentro** del `page_band`; no se usa ±3 implícito), declarado en el yaml y probado. **FAIL-CLOSED** (`RECALL_REPORTABLE = UNKNOWN`, `usable = false`) mientras el yaml esté `DRAFT_UNSIGNED` o vacío. `TN`/especificidad **solo** si se pueblan `negative_units` con `analysis_unit` definida y anclaje humano (9 campos de `NEGATIVE_UNIT_REQUIRED_FIELDS`, fail-closed); no se inventan TN → `SPECIFICITY_REPORTABLE = UNKNOWN`.
- **TEST_METHOD:** generar la hoja (`seed=7, n=40`); `score_emitted_review` sin etiquetas y con etiquetas simuladas (solo TP/FP/COVERAGE_LIMITED); `score_recall` con el yaml de oportunidades `DRAFT_UNSIGNED`; tests sintéticos de matching uno-a-uno (k+1 oportunidades sobre una clave con k findings → TP=k, FN=1, ningún finding repetido) y de política de página (tol=0 → FN; tol=6 → TP).
- **EXPECTED_RESULT:** 40 casos `PENDING`, **0 etiquetados por IA**, `adjudicator: null`, `sample_type = EMITTED_FINDINGS_REVIEW`, los **mismos 40 `finding_id`** que la muestra anterior (preservados); `score_emitted_review` → `PRECISION_REPORTABLE = UNKNOWN` (sin etiquetas), `RECALL_REPORTABLE = UNKNOWN` (siempre), fail-closed ante FN/TN; `score_recall` → `RECALL_REPORTABLE = UNKNOWN`, `usable = false`, `one_to_one` verificado, `page_match_policy = {tolerance_pages: 0}`, `TN = None`, `SPECIFICITY_REPORTABLE = UNKNOWN`.
- **ACTUAL_RESULT:** `factory/regulatory/pilot_run/adjudication/wpe4-qa-20260828.yaml` — 40 casos, 40 `PENDING`, 0 AI-labeled, `adjudicator = null`, `status = DRAFT_UNSIGNED`, `sample_type = EMITTED_FINDINGS_REVIEW`, `label_options = [TP, FP, COVERAGE_LIMITED]`, **40 `finding_id` idénticos** (conjunto y orden) a la muestra previa — verificado por digest; sin FN/TN. `score_emitted_review` (sin etiquetas): `PRECISION_REPORTABLE = UNKNOWN`, `RECALL_REPORTABLE = UNKNOWN`; con etiquetas simuladas TP/FP/COVERAGE_LIMITED: `PRECISION_REPORTABLE = [lo,hi]` (Wilson), `RECALL_REPORTABLE = UNKNOWN`; etiqueta `FN`/`TN` → `AdjudicationMethodError`. `score_recall` (oportunidades `DRAFT_UNSIGNED`): `RECALL_REPORTABLE = UNKNOWN`, `usable = false`, `page_match_policy = {tolerance_pages: 0}`, `TN = None`, `SPECIFICITY_REPORTABLE = UNKNOWN`. Tests de matching uno-a-uno y de política de página: **PASS**.
- **EVIDENCE_ARTIFACT:** `factory/regulatory/pilot_run/adjudication/wpe4-qa-20260828.yaml`; `factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml`; `factory/regulatory/validation_v2/real_corpus_adjudication.py`; `factory/tests/test_wp_e_measurement_independence.py` (22).
- **PASS_FAIL:** **PASS** (paquete de precisión listo; método corregido: fail-closed para recall/FN/TN) · **BLOCKED_HUMAN** (adjudicación QA de la muestra + poblado/firma del conjunto de oportunidades).
- **RESIDUAL_RISK:** `PRECISION_REPORTABLE` de los gates funcional/técnico sobre datos reales solo se conocerá cuando QA etiquete los 40. `RECALL_REPORTABLE` sobre datos reales sigue **`UNKNOWN`** hasta que QA pueble (9 campos por oportunidad, `human_evidence_anchor`+`basis` incluidos) y firme `real_corpus_opportunities.yaml`. `SPECIFICITY_REPORTABLE` sigue **`UNKNOWN`** hasta que existan `negative_units` firmadas con `analysis_unit` definida.

### 10 · WP-F — no auto-cualificación
- **ORIGINAL_PROBLEM:** D-5 — la cualificación V2 vivía en prosa + un dict ad-hoc de `run_suite_c_formal()`.
- **BASELINE_BEHAVIOR:** no había un contrato máquina-legible ni un checker re-ejecutable; nada impedía "auto-declarar" un estado.
- **HARDENING_CONTROL:** `qualification_contract.yaml` (`DRAFT`) + `qualification_contract.py` — valor esperado LEÍDO de fuente citada (nunca literal); `decide_overall()` (función pura) solo devuelve `DRAFT_BASELINE | GATES_MET_AS_QUALIFIED | FAIL_REQUALIFICATION_REQUIRED`; reproduce el fingerprint (WP-A); compara SHAs de 14 disparadores.
- **TEST_METHOD:** `run_contract()`; intentar cargar un contrato con `expected_value` literal.
- **EXPECTED_RESULT:** `overall = DRAFT_BASELINE`; `qualified_version = null`; `system_never_self_qualifies = true`; el loader rechaza el literal; ningún camino devuelve `QUALIFIED` / `COMPLIANT`.
- **ACTUAL_RESULT:** `overall = DRAFT_BASELINE`, `qualified_version = null`, `system_never_self_qualifies = true`, 10/10 casos PASS contra sus umbrales citados, `fingerprint.match = "N/A (contrato DRAFT)"` (no pase silencioso). `test_qualification_contract.py` 17/17 (incl. rechazo del literal y `decide_overall` nunca `QUALIFIED`).
- **EVIDENCE_ARTIFACT:** `factory/regulatory/requirement_catalog/qualification_contract.yaml`; `qualification_contract.py`; tests; `docs_plan/WP_F_CONTRATO_CUALIFICACION_20260828.md`.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** el contrato es `DRAFT`; su valor como registro de cualificación depende de la firma humana (Capa 9). Los gates técnico/funcional viajan con `reportable_range = SYNTHETIC_ONLY`.

### 11 · WP-G — read-only
- **ORIGINAL_PROBLEM:** D-6 — 23 módulos JS de Mission Control, 0 referencias a `/api/v1/v2-analyzer/*`; `MISSION_CONTROL_V2 : UI_VISIBLE = NO`.
- **BASELINE_BEHAVIOR:** una corrida V2 solo era visible por `curl`.
- **HARDENING_CONTROL:** `v2_analyzer_view.js` — `refreshV2Analyzer()` + `openV2Run()`; consume los 6 endpoints GET; muestra fingerprint (WP-A), adecuación por documento (WP-B) y `evidence_basis`; banner "SOLO LECTURA"; `esc()` antes de todo `innerHTML`.
- **TEST_METHOD:** estático (grep de métodos de escritura, paths, wiring) + funcional (FastAPI bare + router, verificar que los endpoints exponen los 3 datos y que POST/DELETE → 404/405).
- **EXPECTED_RESULT:** 0 llamadas de escritura; solo paths `/runs*`; cableado en nav + `main.js` + `refresh.js`; los endpoints exponen fingerprint + `adequacy_verdicts` + `evidence_basis`.
- **ACTUAL_RESULT:** 0 `method:'POST'|'PUT'|'PATCH'|'DELETE'` en el archivo; único patrón `fetch(V2 + path, {headers})`; nav `data-v="v2analyzer"` + `<section id="v-v2analyzer">` presentes; `test_wp_g_mission_control_panel.py` 6/6 (incl. el test funcional que confirma que `audit_metadata` trae los fingerprints + `adequacy_verdicts` + `analysis_coverage_mode`, y que cada finding trae `evidence_basis`).
- **EVIDENCE_ARTIFACT:** `factory/ui/js/mission_control/v2_analyzer_view.js`; `factory/tests/test_wp_g_mission_control_panel.py`; `docs_plan/WP_G_PANEL_V2_MISSION_CONTROL_20260828.md`.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** ninguno relevante; el panel es visualización.

### 12 · `DOCUMENT_EGRESS = 0`
- **ORIGINAL_PROBLEM:** invariante LOCAL-ONLY — ningún documento del cliente sale del servidor.
- **BASELINE_BEHAVIOR:** `network_locked()` ya existía; el hardening no debía romperlo.
- **HARDENING_CONTROL:** todas las corridas WP-* bajo `network_locked()`; ninguna descarga; ningún proveedor externo.
- **TEST_METHOD:** leer `document_egress_bytes` / `llm_calls` de cada corrida de la campaña.
- **EXPECTED_RESULT:** `document_egress_bytes = 0` y `llm_calls = 0` en todas.
- **ACTUAL_RESULT:** `v2_runtime` egress 0 / llm 0 · `wp_d_test_extraction` egress 0 · `held_out_dry` egress 0 · `real_corpus_technical` egress 0 · `suite_c_formal` egress 0.
- **EVIDENCE_ARTIFACT:** `audit_metadata.json` (`document_egress_bytes`, `llm_calls`); resultados de `run_held_out_dry` / `run_wp_d_synthetic`.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** si Capa 9 autoriza OCR (WP-D real), la descarga de assets será un evento gobernado a hashear en el fingerprint — declarado en `docs_plan/WP_C…§5`.

### 13 · Regresión global y EXC-1..EXC-5
- **ORIGINAL_PROBLEM:** el hardening no debe introducir regresiones; la suite global no debe declararse PASS mientras exista el exit code 1.
- **BASELINE_BEHAVIOR (`c4e8296`, reporte maestro):** `5 failed / 2781 passed / 79 skipped / 1 xfailed` · pytest exit code **1**.
- **HARDENING_CONTROL:** cada paquete WP-* con gate transversal `NEW_REGRESSION_FAILURES = 0` y `EXC-1..EXC-5` sin cambio de identidad.
- **TEST_METHOD:** `pytest factory/tests/ -q` sobre `HEAD = ceae307`.
- **EXPECTED_RESULT:** los mismos 5 fallos (EXC-1..EXC-5), 0 nuevos; `passed` = 2781 + Σ(tests nuevos de WP-A..G).
- **ACTUAL_RESULT:** `5 failed / 2891 passed / 79 skipped / 1 xfailed` · exit code **1**. Los 5 = `test_corpus_runner::…d4a_232`, `test_governance_ui_deploy_consistency_live::…routes_are_live`, `test_mission_evidence_readers::…health`, `test_new_managers::{test_passing_tests,test_failing_tests}` — **idénticos** al baseline. `passed` +110 = 23 (WP-A) + 28 (WP-B) + 22 (WP-D) + 14 (WP-E) + 17 (WP-F) + 6 (WP-G) [WP-C = solo doc]. `NEW_REGRESSION_FAILURES = 0` en todo el arco.
- **EVIDENCE_ARTIFACT:** salida de `pytest`; commits `598e60e`..`ceae307` (cada uno con su delta de tests).
- **PASS_FAIL:** **PASS** (0 regresiones; la suite global **NO se declara PASS** — exit 1 por las 5 EXC).
- **RESIDUAL_RISK:** EXC-1..EXC-5 solo se re-verifican en el entorno de origen (`/home/ing_cpmo`, servicios arriba) — aceptadas por Capa 9, 0 impacto V2.

### 14 · CURRENT rollback
- **ORIGINAL_PROBLEM:** el hardening no debe degradar la reversibilidad del cutover.
- **BASELINE_BEHAVIOR:** `routing = v2` con `cutover.set_routing_mode("current")` / env `V2_ANALYZER_ROUTING` para volver a CURRENT.
- **HARDENING_CONTROL:** ningún commit de WP-A..G toca `cutover.py` / `analyzer_router.py` / `routing.txt` / el motor CURRENT.
- **TEST_METHOD:** `git diff --name-only c4e8296..ceae307` filtrado por esos archivos; `test_shadow_and_cutover.py`.
- **EXPECTED_RESULT:** 0 archivos de cutover/routing/CURRENT en el diff; `routing_mode()` sigue resolviendo; `set_routing_mode` disponible.
- **ACTUAL_RESULT:** `git diff` → `(none — CURRENT/routing/graph untouched)`; `cutover.routing_mode() = "v2"`, `analyzer_router.active_engine() = "V2"`, `set_routing_mode` presente; `test_shadow_and_cutover.py` 11/11.
- **EVIDENCE_ARTIFACT:** `git diff --name-only c4e8296..ceae307`; `factory/tests/test_shadow_and_cutover.py`.
- **PASS_FAIL:** **PASS**
- **RESIDUAL_RISK:** `routing.txt` gitignored — la propagación del cutover a otros entornos sigue siendo manual (ya documentado).

### 15 · D-8 — `refers_to`
- **ORIGINAL_PROBLEM:** D-8 — `graph/build.py` describe la arista `refers_to` en el docstring pero no la puebla (`add_edge("refers_to")` no existe). Deuda separada, sin paquete asignado.
- **BASELINE_BEHAVIOR:** `refers_to = 0` en el corpus real; el docstring induce a error sobre la capacidad real.
- **HARDENING_CONTROL:** **ninguno** — el hardening la identificó y la declaró explícitamente como deuda separada fuera de alcance (PLAN §3.1 D-8, §NG-5).
- **TEST_METHOD:** `grep -c 'add_edge("refers_to")' factory/regulatory/graph/build.py` en `HEAD`.
- **EXPECTED_RESULT:** 0 (sin cambio) + declaración honesta en el PLAN.
- **ACTUAL_RESULT:** `0`. Registrada como D-8 en `PLAN_HARDENING…` §3.1 y §NG-5, y en el comentario de hand-off del PR #2.
- **EVIDENCE_ARTIFACT:** `factory/regulatory/graph/build.py`; `docs_plan/PLAN_HARDENING_ANALIZADOR_GMP_LOCAL_V2.md` (D-8).
- **PASS_FAIL:** **PASS** (declaración honesta verificada) — el problema D-8 **sigue abierto**.
- **RESIDUAL_RISK:** `refers_to` no poblado; sin paquete asignado. Bajo impacto (heurística conservadora; ningún detector lo requiere hoy).

### 16 · WP-D real / RW-0003 — pendiente explícito
- **ORIGINAL_PROBLEM:** el cuerpo real del SAT vive en RW-0003 (`SAT3 Scanned-1.pdf`, 204 páginas, 100% imagen), **no** en RW-0009 (transmittal de 2 páginas). Sin OCR local, no hay forma de extraerlo.
- **BASELINE_BEHAVIOR:** `tested_by = 0` sobre el corpus RW real (D-1 + D-2).
- **HARDENING_CONTROL:** WP-C lo identificó y lo documentó como problema de **procedencia del corpus + capacidad OCR ausente**, no de extracción. WP-D dejó la etapa de `Test` lista pero **flag OFF** para no forzar un salto de `EXTRACTION_VERSION` sin decisión.
- **TEST_METHOD:** benchmark de extracción (5 extractores locales) + caracterización de RW-0003; revisión de disponibilidad OCR local.
- **EXPECTED_RESULT:** declarar explícitamente el bloqueo (ingesta de RW-0003 + descarga OCR + salto gobernado de `EXTRACTION_VERSION`) como decisión de Capa 9, no como fallo.
- **ACTUAL_RESULT:** documentado en `docs_plan/WP_C_BENCHMARK_EXTRACCION_20260828.md` §4–§6 y en `qualification_contract.yaml` como contingencia `CT-WP-D-REAL` (`BLOCKED_GOVERNANCE`). Sin OCR local instalado (verificado: sin tesseract / docling / pymupdf / easyocr). `tested_by` sobre corpus real = 0 (sin cambio, esperado con flag OFF).
- **EVIDENCE_ARTIFACT:** `docs_plan/WP_C_BENCHMARK_EXTRACCION_20260828.md`; `qualification_contract.yaml` (`CT-WP-D-REAL`).
- **PASS_FAIL:** **BLOCKED_CORPUS_OCR** (pendiente explícito, declarado; no es PASS ni FAIL)
- **RESIDUAL_RISK:** hasta ingerir RW-0003 con OCR y saltar `EXTRACTION_VERSION`, WP-D no aporta `tested_by > 0` sobre datos reales, y `REQUIREMENT_NOT_TESTED` real seguirá siendo `would_degrade` (contenido por WP-B, no corregido).

---

## RESUMEN DE PROBLEMAS ORIGINALES

| Estado | Problemas |
|---|---|
| **RESUELTOS** (corregidos) | D-4 (fingerprint → WP-A) · D-6 (UI → WP-G) · D-5 (contrato de cualificación → WP-F, artefacto+checker) · NG-8 (provenance de config → WP-A `run_attestation`) · NG-2 / NG-2b (contradicciones 0-vs-90 / 285-vs-342 → reconciliadas, eran malentendidos) · NG-5 (aristas vacías → diagnosticadas por familia) · D-1 **en código** (etapa de `Test` → WP-D, flag OFF) |
| **CONTENIDOS** (no corregidos, honestamente acotados) | NG-1 (ausencia sin precondición → WP-B OBSERVE: `analysis_coverage` + `would_degrade`; corrección = ENFORCE, pendiente) · NG-3 / NG-4 (gates no medidos sobre datos reales / rango no transfiere → WP-E: `metric_envelope` fuerza `SYNTHETIC_ONLY` + held-out + muestra de 40; rango real pendiente humano) · D-2 (SAT ilegible → WP-C: es un transmittal, causa raíz identificada; SAT real = RW-0003, pendiente gobernanza) · NG-7 (cambio de `EXTRACTION_VERSION` invalida el shadow → declarado; WP-D flag OFF evita dispararlo) · D-3 (suites acopladas → contenido para Suite C firmado; resuelto en el instrumento nuevo held-out) |
| **ABIERTOS** | D-8 (`refers_to` no poblado; sin paquete) · NG-6 (`remediation_limit=8` sin criterio de selección declarado; sin paquete) · D-1 **sobre corpus real** (RW-0003 + OCR + `EXTRACTION_VERSION`; bloqueado en gobernanza) · arista `verifies` no ejercitada (downstream de D-1 real) |

---

## VEREDICTO

- **REDESIGN_REQUIRED = NO.** Ningún caso de validación expuso un defecto arquitectónico. Cada brecha
  restante es o bien aditiva-corregible con una firma humana, o una dependencia declarada de
  gobernanza/corpus (RW-0003 + OCR).
- **HARDENING_EFFECTIVENESS_TECHNICAL = HIGH.** Los problemas tratables en código
  (reproducibilidad → WP-A · integridad de la medición → WP-E `metric_envelope` · extracción de `Test`
  en código → WP-D · visibilidad UI → WP-G · provenance de configuración → WP-A `run_attestation`) están
  **resueltos**; los que no se pueden "arreglar" sin gobernanza o un SAT legible están **contenidos y
  declarados** (WP-B OBSERVE, WP-C, `SYNTHETIC_ONLY`); **0 regresiones** introducidas en todo el arco.
- **REAL_CORPUS_EFFECTIVENESS = NOT_YET_DETERMINED.** La eficacia sobre datos reales **todavía no está
  medida** porque siguen pendientes: **WP-E.4** — conjunto A (adjudicación humana de los 40 findings
  emitidos → `PRECISION_REPORTABLE`, **no** recall) **y** conjunto B (`real_corpus_opportunities.yaml`,
  QA enumera las oportunidades de detección sobre el corpus → `RECALL_REPORTABLE`; hoy `UNKNOWN`,
  fail-closed); **WP-E.3** (held-out firmado por autor independiente → el gate técnico deja de ser
  `SYNTHETIC_ONLY`); **WP-D real** (RW-0003 + OCR + `EXTRACTION_VERSION` → `tested_by > 0` sobre corpus
  real y re-evaluación de `would_degrade`). Hasta que esos se cierren, no se puede afirmar que el
  hardening corrigió los problemas **sobre el corpus real**, solo que los
  **contuvo** y dejó el instrumento para medirlo.
- La suite global **NO** se declara PASS: `pytest` sigue con exit code 1 por EXC-1..EXC-5 (aceptadas).

---

## NEXT_ACTION (orden)

Ninguna es acción de código. Todas son firmas / decisiones humanas de Capa 9 / QA.

1. **Adjudicación humana de los 40 casos (WP-E.4 · conjunto A)** — QA etiqueta
   `factory/regulatory/pilot_run/adjudication/wpe4-qa-20260828.yaml` (40 findings EMITIDOS, `PENDING`,
   0 IA) con **`TP` / `FP` / `COVERAGE_LIMITED`** + `adjudicator`. Da `PRECISION/PPV` + proporción
   `COVERAGE_LIMITED`. **NO** da recall/FN (`score_emitted_review` falla cerrado ante FN/TN).
   **En paralelo — WP-E.4 · conjunto B (ground truth de recall):** QA revisa **el corpus** (no los
   findings) y puebla `factory/regulatory/requirement_catalog/real_corpus_opportunities.yaml` con las
   oportunidades de detección que deberían existir — cada una con los 9 campos obligatorios, incluidos
   **`human_evidence_anchor` y `basis` que completa QA** (no la IA); el matching contra los findings es
   **uno-a-uno** y la tolerancia de página es el parámetro explícito `page_match_policy.tolerance_pages`
   (default 0). Opcionalmente `negative_units` con `analysis_unit` definida. Luego firma
   (`status: SIGNED` + `adjudicator`). Sin este conjunto, `RECALL_REPORTABLE = UNKNOWN`; sin
   `negative_units` firmadas, `SPECIFICITY_REPORTABLE = UNKNOWN`.
2. **Held-out independiente (WP-E.3)** — un autor `≠ "Capa 9 (Cesar)"` puebla
   `held_out_technical_corpus.yaml` con casos reales, cita las cláusulas de los `REG`, aprueba los `ADV`,
   fija umbrales; luego firma (`status: SIGNED` + `author`).
3. **Scoring real + `reportable_range`** — `score_emitted_review()` sobre la hoja adjudicada →
   `PRECISION_REPORTABLE`; `score_recall()` sobre el conjunto de oportunidades firmado →
   `RECALL_REPORTABLE`; `run_held_out_dry()` sobre el held-out firmado. Recién entonces los gates
   funcional/técnico tienen rango REAL (deja de ser `SYNTHETIC_ONLY`).
4. **Decisión RW-0003 / OCR + validación WP-D real** — Capa 9 autoriza ingesta de RW-0003, descarga de
   OCR (Tesseract, Apache-2.0) y salto gobernado de `EXTRACTION_VERSION` con re-derivación de stores;
   se ejecuta WP-D sobre el corpus real y se verifica `tested_by > 0` con muestra revisada a mano.
5. **Reevaluar `would_degrade`** — con `tested_by` poblado, recomputar `coverage_dependencies`: cuántos
   de los 70 `REQUIREMENT_NOT_TESTED` + 8 `ORPHAN_DESIGN_ELEMENT` pasan a `coverage_status = OK`
   (cobertura resuelta → el finding es **evaluable**, todavía **sujeto a adjudicación humana** — no
   implica que sea una desviación confirmada) y cuántos persisten como brecha de cobertura.
6. **Decisión WP-B ENFORCE** — con lo anterior, Capa 9 firma `extraction_adequacy_thresholds.yaml` y
   decide activar el modo enforce (degradar los `would_degrade` restantes a `MACHINE_INCONCLUSIVE` con
   `COVERAGE_LIMITATION`).
7. **Firma WP-F** — Capa 9 fija `qualified_version`, congela `qualified_against.artifact_sha256` +
   `fingerprints`, pone `reviewer` por caso, `status: SIGNED`; `run_contract()` pasa de `DRAFT_BASELINE`
   a veredicto.
8. **Triage D-8 / NG-6** — decidir si `refers_to` (D-8) y el criterio de selección de
   `remediation_limit` (NG-6) se convierten en paquetes o quedan como deuda aceptada.

---

*Validación read-only. Sin cambios de código, sin firmas, sin WP-B ENFORCE, sin WP-D real, sin cambio de
`PRODUCTION_ENABLEMENT`. Los 40 casos de adjudicación quedan PENDING — sin etiquetar por IA.*
