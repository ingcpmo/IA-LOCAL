# WP-F — PAQUETE DE EVIDENCIA (plan de fortalecimiento H-1…H-10)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Baseline de código:** HEAD `ab40f3b`
(rama `fix/clon-local-validacion`). Sin commit, sin push. Clon local de validación.

```
WP_F_STATUS           = INCOMPLETE
H8                    = INCOMPLETE_PENDING_HUMAN_GROUND_TRUTH
H10                   = PASS_PENDING_HUMAN_PRODUCTION_ACTIVATION
QUALIFICATION_BLOCKER = H8_HUMAN_GROUND_TRUTH_MISSING
QUALIFICATION_BLOCKER = H10_HUMAN_SAMPLE_VERIFICATION_PENDING
QUALIFICATION_BLOCKER = LEDGER_UNCOMMITTED
QUALIFICATION_BLOCKER = HUMAN_SIGNATURES_PENDING (H-1…H-7, D-2)
```

**No se auto-declara** `QUALIFIED` / `QA_APPROVED` / `RELEASED` / `CAPA_CLOSED` /
`FINAL_GMP_APPROVAL`. Marcadores mantenidos: `HUMAN_FINAL_AUTHORITY=REQUIRED` ·
`PRODUCTION_ENABLEMENT=NOT_ENABLED` · `REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM`.

---

## 0 · D-1 — Intended use (integrado, NO "n/a")

```
CURRENT_INTENDED_USE  = GMP_DECISION_SUPPORT_TOOL
SYSTEM_OF_RECORD      = NO
HUMAN_FINAL_AUTHORITY = REQUIRED
REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM
PRODUCTION_ENABLEMENT = NOT_ENABLED
```

El sistema **analiza** documentos GMP contra regulación/gobernanza y **prepara** hallazgos,
borradores controlados y evidencia anclada para revisión humana. **No** decide cumplimiento,
**no** aprueba documentos, **no** cierra CAPA, **no** libera lote. El documento original es la
fuente maestra y nunca se sobrescribe. La IA no sustituye a QA / Capa 9.

---

## 1 · Estado por hito

| Hito | Estado | Cierre | Evidencia clave |
|---|---|---|---|
| **H-1** identidad / mutadores | ACCEPTED (firma humana pendiente) | `CIERRE_H1_H2_H3_20260829.md` | `test_h1_identity_critical_mutators.py` |
| **H-2** audit trail aislado | ACCEPTED | idem | `test_h2_audit_trail_isolated_from_tests.py` |
| **H-2b** review_queue aislado | ACCEPTED | `CIERRE_H2B_H4_20260829.md` | `test_r2_3_judgment_relabel_consistency.py` |
| **H-3** `finding_record_id` | ACCEPTED | `CIERRE_H1_H2_H3_20260829.md` | `test_h3_finding_record_id.py` |
| **H-4** snapshot inmutable del grafo | ACCEPTED (`b5196a71…` estable) | `CIERRE_H2B_H4_20260829.md` | `test_h4_graph_snapshot.py` |
| **H-5F** hardening Factory | PASS | `CIERRE_H5F_H6F_20260829.md` | `test_h5f_hardening.py` ; `egress_controls` |
| **H-6F** backup/restore F-STATE | PASS | idem | `restore_factory_state.py` 14/14 |
| **H-7** coverage_mode gobernado | CLOSED (ENFORCE por D-2) | `CIERRE_D2_H7_ENFORCE_20260830.md` | `findings_degraded=78` ; `findings_suppressed=0` |
| **D-2** firma 3 artefactos + ENFORCE | APPROVE (registrado) | idem | `ARTIFACT_VERSION-2026-019/020` |
| **H-8** evidencia real de desempeño | INSTRUMENT_READY · MÉTRICAS UNKNOWN | `CIERRE_H8_EVIDENCIA_REAL.md` · `PAQUETE_D5_ADJUDICACION_H8_20260830.md` | QA40 40 PENDING · SHA `02b6d3d0…` |
| **D-5** adjudicación humana | **NOT_OCCURRED** (`D5_HUMAN_EVIDENCE_AVAILABLE=NO`) | — | `score_emitted_review`/`score_recall` → UNKNOWN |
| **D-3** descargas OCR | EJECUTADO (preautorizado) | `D3_DOWNLOAD_MANIFEST_20260830.md` | rapidocr 1.4.4 + docling 2.123.1 + torch 2.13.0+cpu, offline |
| **H-9** benchmark de extracción (204 pág) | **PASS** | `CIERRE_H9_BENCHMARK_EXTRACCION_20260830.md` §5 | `_h9_full/H9_BENCH_RESULTS_FULL.json` |
| **D-4** selección de extractor | **APPROVE · CONDITIONS_MET=YES · SELECTED=docling** | `CIERRE_H9_…_20260830.md` §4 | `ARTIFACT_VERSION-2026-021` (`decision_ref D-4-H9-20260830`) |
| **H-10** habilitación agrupada | **`H10_TECHNICAL_ACCEPTANCE = PASS`** · `PRODUCTION_ACTIVATION = PENDING_HUMAN_VERIFICATION` | `CIERRE_H10_CAPACIDAD_20260830.md` · `CIERRE_H10_DRIFT_CANONICAL_20260830.md` | `canonical_store_v2/` + `graph_store_v2/` + `pilot_run/h10_extraction_v2_20260830/` |

---

## 2 · H-8 — INCOMPLETE para qualification

`D5_ADJUDICATION = NOT_OCCURRED` · `D5_HUMAN_EVIDENCE_AVAILABLE = NO`. Verificado en vivo:

```
qa40_adjudication_sheet.yaml     -> 40/40 casos label: PENDING ; status: DRAFT_UNSIGNED
real_corpus_opportunities.yaml   -> opportunities: []  negative_units: []  status: DRAFT_UNSIGNED
held_out_technical_corpus.yaml   -> status: DRAFT_UNSIGNED ; rules_author: None
score_emitted_review(...)        -> PRECISION_REPORTABLE: UNKNOWN
score_recall(...)                -> RECALL / SPECIFICITY: UNKNOWN

QA40_SAMPLE_PRECISION = UNKNOWN
REAL_RECALL           = UNKNOWN
REAL_SPECIFICITY      = UNKNOWN
```

Instrumento construido y verificado (`H8_INSTRUMENT_READY = YES`). Falta el contenido humano.
La IA **no** auto-asigna `TP`/`FP`/`COVERAGE_LIMITED`/ground truth/oportunidades/unidades negativas.
`QA40_SHA` inmutable, no re-muestreada.

---

## 3 · H-10 — `H10_TECHNICAL_ACCEPTANCE = PASS`

Salto gobernado `canonical-v1-2026-08 → canonical-v1-2026-08+tests-v1` **materializado por el
flujo productivo real** en stores nuevos y físicamente separados (`canonical_store_v2/`,
`graph_store_v2/`, `pilot_run/h10_extraction_v2_20260830/`). `canonical_store/` de producción
**byte-idéntico** antes/después; `_EXT_VER`/`_CANON` **sin tocar** → producción sigue en v1.

| Métrica | Valor |
|---|---|
| OCR (docling, por lotes de 24 pág) — RW-0003 | peak RSS **4 475 MB** · 1 222 s · `DOCUMENT_EGRESS=0` · contenedores BD intactos |
| `TEST_OBJECTS_RW0003` | **165** (RW-0009: 1 · total nodos test: 166) |
| `TESTS_WITH_REQUIREMENT_REF` / sin | 3 (F05.05, UR3.2.3) / 162 |
| `TESTED_BY` | **17** (RW-0006→RW-0003: 6 · RW-0005→RW-0003: 11 · via `3.2.3`, `F05.05`) |
| `VERIFIES` | 0 — N/A (el SAT cita refs de proyecto/función, no ids del catálogo regulatorio) |
| `REFERS_TO` | **350** (0 dangling · 0 fabricadas · edge-source-claims 100 % sustantivas) |
| `SYSTEM_COMPONENT` / `ACTOR` | 47 / 13 (mención literal + diccionario cerrado + provenance) |
| `IMPLEMENTED_BY` / `DESIGNED_BY` | 1120→1120 / 190→190 (**0 regresión**) |
| `CONTRADICTS` / `SUPPORTS` | 0→0 / sin cambio (**NO modificados**) |
| `TABLE_SEMANTICS` | RW-6: 97 tablas con rol (preservado) · RW-0003: 194/199 con rol |
| `FABRICATED_TESTS` / `_EDGES` / `_EVIDENCE` | 0 / 0 / 0 |
| `DETERMINISTIC_RUNS` | PASS (RUN1 == RUN2: 3 fingerprints + todos los conteos) |
| `CANONICAL_DRIFT_EXPLAINED` | YES — `PREEXISTING_CLONE_DRIFT` (no causado por H-10) |
| `INPUT_CONFIG_FINGERPRINT` | `0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f` |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4` |
| `FINDINGS_FINGERPRINT` | `2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f` |
| `FINDINGS_TOTAL` | 456 (RW-6) → 674 (RW-6 + RW-0003) |
| `ROLLBACK` | PASS (v1 intacto ; `_EXT_VER` sin tocar) |
| `H10_HUMAN_SAMPLE_VERIFICATION` | **PENDING** (`H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`, 77 filas) |
| `PRODUCTION_ACTIVATION` | **PENDING_HUMAN_VERIFICATION** |

---

## 4 · Regresión final (H-1…H-10; H-1…H-7 solo TEST)

`pytest factory/tests/` (2026-08-30): **`PASSED=3002 · FAILED=6 · SKIPPED=79 · XFAILED=1`** (344 s).

```
HISTORICAL_ACCEPTED_FAILURES (⊂ baseline 9-EXC):
    test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas          (entorno)
    test_mission_evidence_readers::test_deployment_exists_and_health                    (entorno)
LEDGER_GUARD_FAILURES (store == git HEAD ; AUTO-CLEAR al commitear ; 3 registros: D-2 x2 + D-4):
    test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store
    test_governance_endpoints::test_the_two_stores_stayed_independent
    test_governance_signature_flow_g21::test_n13_no_test_in_this_file_touched_the_real_store
    test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store

NEW_REGRESSIONS = 0
```

```
QA40_CHANGED                     = NO   (SHA 02b6d3d0… ; production stores sin cambio)
AUDIT_TRAIL_CHANGED_BY_TESTS     = NO
REVIEW_QUEUE_CHANGED_BY_TESTS    = NO
PRODUCTION_CANONICAL_STORE       = BYTE-IDÉNTICO (md5 de árbol antes/después)
PRODUCTION_GRAPH_STORE (tracked) = GIT-CLEAN
```

Suite exit ≠ 0 → **NO se llama GREEN/PASS.**

### Ledger gobernado — `LEDGER_UNCOMMITTED = YES` (desviación conocida, no regresión lógica)

```
decisions_v2.jsonl = HEAD 251 + 3 sin commitear:
   ARTIFACT_VERSION-2026-019  (D-2 ORIGINAL)
   ARTIFACT_VERSION-2026-020  (D-2 CORRECTION — identidad decisor 'Cesar')
   ARTIFACT_VERSION-2026-021  (D-4 ORIGINAL — SELECTED=docling, decision_ref D-4-H9-20260830)
Todos validan (validate_record: valid=True). test_decision_migration (sync A/B/v2): PASS.
La misión prohíbe commit -> los 4 guards store==git-HEAD fallan por esto y AUTO-LIMPIAN al commitear.
```

---

## 5 · Fingerprints

```
Producción (D-2, canonical_store congelado — CON el clone-drift preexistente, código HEAD):
  INPUT_CONFIG   = 3c8b0036107b824f0919dafba3bc7ebb12f3ec9af62be973e934cc8cc889fcaf
  GRAPH_SNAPSHOT = 88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05
  FINDINGS       = fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d
  Baseline OBSERVE (rollback): FINDINGS = b5196a71…

H-10 (canonical_store_v2 / graph_store_v2 ; RW-6 + RW-0003 ; código del working tree ; re-extracción LIMPIA del clon ; 2x idénticas):
  INPUT_CONFIG   = 0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f
  GRAPH_SNAPSHOT = 8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4
  FINDINGS       = 2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f
```

Los fingerprints v2 no son directamente comparables con la baseline D-2: (a) `source_attestation_digest`
cambió por el código nuevo (extract_entities, hook OCR, table-tests, refers_to); (b) el `canonical_store_v2`
es una **re-extracción LIMPIA del clon** — el store de producción tiene *clone-drift* pre-existente
(p.ej. RW-0012: 595 claims vs 258, con páginas fantasma). Ver `CIERRE_H10_DRIFT_CANONICAL_20260830.md`.

---

## 6 · Artefactos del paquete

```
docs_plan/CIERRE_H1_H2_H3_20260829.md            docs_plan/CIERRE_H2B_H4_20260829.md
docs_plan/R1B_PREVIO_H5_H6_20260829.md           docs_plan/REDISENO_H5_H6_POST_R1B_20260829.md
docs_plan/CIERRE_H5F_H6F_20260829.md             docs_plan/CIERRE_H7_TECNICO_Y_GATE_D2_20260829.md
docs_plan/CIERRE_D2_H7_ENFORCE_20260830.md       docs_plan/CIERRE_H8_EVIDENCIA_REAL.md
docs_plan/PAQUETE_D5_ADJUDICACION_H8_20260830.md docs_plan/D3_DOWNLOAD_MANIFEST_20260830.md
docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md        docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION_20260830.md
docs_plan/CIERRE_H10_CAPACIDAD_20260830.md         docs_plan/CIERRE_H10_DRIFT_CANONICAL_20260830.md
docs_plan/PAQUETE_D6_QUALIFICATION_20260830.md     docs_plan/CIERRE_TECNICO_PLAN_H1_H10_20260830.md
docs_plan/INFORME_MAESTRO_EJECUCION_GMP_AI_FACTORY_H1_H10_20260830.md
docs_plan/_h9_full/{H9_BENCH_RESULTS_FULL.json, H10_REDERIVE_RESULTS.json, H10_RW0003_INGEST.json,
                    H10_FINAL_VALIDATION.json, final_regression_h10b.log, *.log}
factory/regulatory/pilot_run/h10_extraction_v2_20260830/{H10_VERSION_JUMP_RESULT.json,
                    H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json, run1/, run2/}
factory/scripts/ops/{h9_extraction_benchmark, h10_test_extraction_rederivation, h10_execute_version_jump,
                     h10_ingest_rw0003, h10_final_validation}.py
factory/regulatory/canonical/extract_entities.py
factory/regulatory/canonical_store_v2/ , graph_store_v2/
```

---

## 7 · Campos de cierre WP-F

```
WP_F_STATUS                  = INCOMPLETE
QUALIFICATION_BLOCKERS       = H8_HUMAN_GROUND_TRUTH_MISSING ; H10_HUMAN_SAMPLE_VERIFICATION_PENDING ;
                               LEDGER_UNCOMMITTED ; HUMAN_SIGNATURES_PENDING
D1                           = CURRENT_INTENDED_USE=GMP_DECISION_SUPPORT_TOOL ; SYSTEM_OF_RECORD=NO
H1..H7                       = ACCEPTED / PASS / CLOSED  (regresión TEST ONLY, NEW_REGRESSIONS=0)
D2                           = APPROVE (registrado)
H8                           = INCOMPLETE_PENDING_HUMAN_GROUND_TRUTH ; REAL_PRECISION = REAL_RECALL = REAL_SPECIFICITY = UNKNOWN
D5                           = NOT_OCCURRED
D3                           = DONE
H9                           = PASS ; RECOMMENDED_EXTRACTOR = docling
D4                           = APPROVE ; CONDITIONS_MET = YES ; SELECTED = docling (registrado)
H10                          = PASS_PENDING_HUMAN_PRODUCTION_ACTIVATION
NEW_REGRESSIONS              = 0
DOCUMENT_EGRESS              = 0  (medido: H-9, ingesta RW-0003, H-10, salto, pipeline)
AUTO_DECLARATIONS            = NINGUNA
HUMAN_FINAL_AUTHORITY        = REQUIRED
```
