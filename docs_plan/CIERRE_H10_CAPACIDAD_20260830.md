# CIERRE H-10 — HABILITACIÓN AGRUPADA DE CAPACIDAD

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Baseline de código:** HEAD `ab40f3b`.
**Diseño rector:** `docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md` §H-10.
Sin commit, sin push, sin edición manual de ledgers. Marcadores mantenidos:
`HUMAN_FINAL_AUTHORITY=REQUIRED` · `PRODUCTION_ENABLEMENT=NOT_ENABLED` ·
`REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM`.

```
H9  = PASS
D4  = APPROVE · CONDITIONS_MET = YES · SELECTED = docling  (ARTIFACT_VERSION-2026-021, decision_ref D-4-H9-20260830)

H10_TECHNICAL_ACCEPTANCE = PASS
PRODUCTION_ACTIVATION      = PENDING_HUMAN_VERIFICATION   (verificación de la muestra de relaciones nuevas)
```

---

## 1 · Acceptance original de H-10 (§13 de la misión) — checklist

| Criterio | Valor | OK |
|---|---|---|
| docling SAT ingest completed **safely** | RW-0003 (204 pág, 100 % imagen) ingerido por **lotes de 24 pág** con liberación de memoria: **peak RSS 4 475 MB** (vs 9 300 MB de una vez), 1 222 s, `DOCUMENT_EGRESS=0`. Contenedores de BD intactos. | ✔ |
| Test extraction from **real SAT evidence** works | `extract_tests.py::extract_tests_from_tables` consume las tablas de ejecución que docling reconstruye → **165 `Test`** de RW-0003 con provenance completa (page + source_text + hash). | ✔ |
| `tested_by > 0` | **17** aristas, todas **cross-documento**: `RW-0006 (URS) → RW-0003 (SAT)` = 6, `RW-0005 (FS) → RW-0003 (SAT)` = 11. Vía refs reales `3.2.3` (requisito URS) y `F05.05` (función FS). | ✔ |
| `verifies > 0` where applicable | **0** — el SAT referencia requisitos de **proyecto** (`3.2.3`) y **funciones** (`F05.05`), no ids del **catálogo regulatorio** (`21_CFR_11.10(e)`, `ANNEX11_*`). `verifies` (test→requirement del catálogo) sólo aplica cuando un test cita un id de catálogo; **este SAT no lo hace**. La trazabilidad a regulación va indirecta por la cadena `tested_by`+`implemented_by`+`regulated_by`. **N/A, no es una brecha.** | ✔ (N/A) |
| `implemented_by` regression = 0 | 1120 → **1120** | ✔ |
| `designed_by` regression = 0 | 190 → **190** | ✔ |
| `refers_to` backed by real nodes/evidence | **350**; 100 % con destino `system_component`/`actor` real; 100 % con ancla; 0 dangling; edge source-claims 100 % sustantivas (guarda `_is_reference_list_line`). | ✔ |
| table semantics preserved/validated | RW-6: **97** tablas con rol (v1, preservadas). RW-0003: **194/199** tablas docling con rol de columna determinista (`map_column_roles`). Sin estructura inferida. | ✔ |
| canonical drift explained | `CANONICAL_DRIFT_EXPLAINED = YES` · `PREEXISTING_CLONE_DRIFT` (`docs_plan/CIERRE_H10_DRIFT_CANONICAL_20260830.md`). No causado por H-10. | ✔ |
| `fabricated_tests = 0` | Todo `Test` tiene descripción sustantiva ≥ 15 chars **Y** (ref real **O** token de resultado) **Y** provenance. `DO_NOT_CREATE_TEST` en caso contrario. | ✔ |
| `fabricated_edges = 0` | Chequeos automáticos: `tested_by` de upstream (claim/section/requirement) a `test`; `refers_to` a entidad; todas con provenance. | ✔ |
| `fabricated_evidence = 0` | 0 ids de requisito sintéticos (regex estricta `_TABLE_REQREF_RE`: sólo `F\d\d.\d\d`, CFR, Annex, `XX-[HS]R-NNN`, `URx.y.z`). El ruido OCR (`NA PASS 03`) queda descartado. | ✔ |
| deterministic runs = PASS | H10_RUN_1 vs H10_RUN_2: **INPUT_CONFIG / GRAPH_SNAPSHOT / FINDINGS idénticos**; `tested_by`/`verifies`/`refers_to`/`implemented_by`/`designed_by` idénticos. | ✔ |
| `DOCUMENT_EGRESS = 0` | Medido en ingesta, re-derivación y salto (network_locked). | ✔ |
| `rollback = PASS` | `canonical_store/` + `graph_store/` v1 **byte-idénticos** antes/después; `_EXT_VER`/`_CANON` de `v2_runtime.py` sin tocar → producción sigue en v1 sin ninguna acción. Flag OFF reproduce v1. | ✔ |
| `NEW_REGRESSIONS = 0` | `pytest factory/tests/` = `6 failed · 3002 passed`; los 6 ∈ baseline 9-EXC. | ✔ |

**Todos los criterios técnicos originales se cumplen → `H10_TECHNICAL_ACCEPTANCE = PASS`.**
(El acceptance NO se rebajó tras ver resultados: `verifies=0` está justificado como N/A por la
naturaleza del SAT, no reinterpretado como opcional.)

---

## 2 · Cifras

```
EXTRACTION_VERSION_BEFORE  = canonical-v1-2026-08
EXTRACTION_VERSION_AFTER   = canonical-v1-2026-08+tests-v1   (materializado en canonical_store_v2/ + graph_store_v2/)
OCR_EXTRACTOR              = docling  (offline, enable_remote_services=false, assets locales, por lotes de 24 pág)

TEST_OBJECTS_RW0003            = 165
TESTS_WITH_REQUIREMENT_REF     = 3     (refs reales: F05.05, UR3.2.3 / 3.2.3)
TESTS_WITHOUT_REQUIREMENT_REF  = 162   (casos reales sin id de requisito recuperable en el OCR -> Test creado, sin arista de traza)
TEST_NODES_TOTAL (RW-6+RW-0003)= 166   (165 RW-0003 + 1 RW-0009)

TESTED_BY   = 17   (RW-0006->RW-0003: 6 ; RW-0005->RW-0003: 11 ; via 3.2.3 y F05.05)
VERIFIES    = 0    (N/A: el SAT no cita ids del catálogo regulatorio)
REFERS_TO   = 350
SYSTEM_COMPONENT = 47
ACTOR            = 13

IMPLEMENTED_BY_BEFORE / AFTER = 1120 / 1120
DESIGNED_BY_BEFORE / AFTER    = 190 / 190
CONTRADICTS_BEFORE / AFTER    = 0 / 0   (NO modificado)
SUPPORTS                      = sin cambio (lo puebla el Adjudicator)

TABLE_SEMANTICS = RW-6: 97 tablas con rol (preservado) · RW-0003: 194/199 tablas docling con rol

FABRICATED_TESTS    = 0
FABRICATED_EDGES    = 0
FABRICATED_EVIDENCE = 0
DETERMINISTIC_RUNS  = PASS
DOCUMENT_EGRESS     = 0
ROLLBACK            = PASS
NEW_REGRESSIONS     = 0

INPUT_CONFIG_FINGERPRINT   = 0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f
GRAPH_SNAPSHOT_FINGERPRINT = 8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4
FINDINGS_FINGERPRINT       = 2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f
FINDINGS_TOTAL             = 456 (CONTROL, RW-6) -> 674 (RW-6 + RW-0003)   (RW-0003 aporta sus propios hallazgos técnicos/regulatorios)

H10_HUMAN_SAMPLE_VERIFICATION = PENDING
H8_HUMAN_GROUND_TRUTH         = MISSING
```

---

## 3 · Qué se implementó (componentes internos de H-10, NO work packages nuevos)

| Componente | Cambio |
|---|---|
| **A · OCR docling** | `extract_document.py`: `_docling_content(pdf)` procesa **por lotes** (`_DOCLING_BATCH_PAGES=24`, `gc.collect()` entre lotes) y devuelve texto + tablas estructuradas. `extract_document(..., ocr=True)` cae a docling **sólo** si pdfplumber recupera < 8 chars/pág. Ruta de producción por defecto (`ocr=None`) **sin cambio**. |
| **B · Test desde tablas** | `extract_tests.py::extract_tests_from_tables(document_id, tables, doc_type)`: detecta la tabla de ejecución del SAT por firma de columnas (`Test Description` + `Result/Expected/Actual`), crea UN `Test` por escenario con provenance por página, `verifies_requirement_ids` sólo con refs reales (`_TABLE_REQREF_RE` estricta), `resultado` del token PASS/FAIL. `DO_NOT_CREATE_TEST` si no hay descripción sustantiva o no hay (ref real ∨ resultado). |
| **B · linker** | `build.py::_link_to_tests` / `verifies` **sin cambios de lógica** — ya eran correctos; ahora tienen `Test` reales que consumir. |
| **C · Entidades** | `extract_entities.py` (NUEVO): NER cerrada + mención literal + provenance; ancla preferente **en prosa** (no en lista de referencias, `_is_citation_anchor`). `model.build_system_component`/`build_actor` (con Provenance). `build.py::_link_refers_to` + guarda `_is_reference_list_line`. |
| **D · Roles de tabla** | `table_structure_extractor.map_column_roles` aplicado también a las tablas docling (194/199 mapeadas). Preservado en v1 (97 tablas RW-6). |
| **`contradicts`/`supports`** | **NO tocados.** |

**Archivos modificados/creados:**
```
M  factory/regulatory/canonical/model.py               +Provenance en Actor/SystemComponent ; +build_system_component / build_actor
M  factory/regulatory/canonical/extract_document.py    +_docling_content (lotes) ; +_looks_image_only ; +ocr= ; tablas docling -> Table + roles ; extract_tests_from_tables
M  factory/regulatory/canonical/extract_tests.py       +extract_tests_from_tables ; +_TABLE_REQREF_RE (estricta)
?? factory/regulatory/canonical/extract_entities.py    NUEVO
M  factory/regulatory/graph/build.py                   +_link_refers_to ; +_is_reference_list_line
?? factory/tests/test_extract_entities.py              NUEVO (4)
M  factory/tests/test_graph_build_and_trace.py         +test_h10_refers_to_by_literal_entity_mention
?? factory/scripts/ops/h10_test_extraction_rederivation.py   harness fase aislada
?? factory/scripts/ops/h10_execute_version_jump.py           salto gobernado a stores paralelos
?? factory/scripts/ops/h10_ingest_rw0003.py                  ingesta OCR controlada en memoria
?? factory/scripts/ops/h10_final_validation.py               CONTROL / RUN1 / RUN2
?? factory/regulatory/canonical_store_v2/  , graph_store_v2/  stores del salto (v1 intacto)
?? factory/regulatory/pilot_run/h10_extraction_v2_20260830/   paquete + H10_VERSION_JUMP_RESULT.json + H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json
```

---

## 4 · Muestra para verificación HUMANA

`factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`
- **77 filas**: las **17** `tested_by` completas + **60** `refers_to` (primeras por `edge_id`).
- Por fila: `relation`, `source_document`, `page`, `exact_source_anchor`, `source_node`/`kind`/`label`,
  `destination_node`/`kind`/`label`, `requirement_or_ref`, `provenance_hash`; `HUMAN_VERIFIED` /
  `HUMAN_VERDICT` / `HUMAN_NOTE` **vacíos** (la máquina no marca ninguna).
- `sample_sha256` fijado. `H10_HUMAN_SAMPLE_VERIFICATION = PENDING`.

Esto **no impide** `H10_TECHNICAL_ACCEPTANCE = PASS`; **sí impide** la activación productiva
(`PRODUCTION_ACTIVATION = PENDING_HUMAN_VERIFICATION`) y la qualification.

---

## 5 · Salto de `EXTRACTION_VERSION` — materializado, NO activado

`factory/scripts/ops/h10_execute_version_jump.py` (+ RW-0003 del store ingerido):
`canonical-v1-2026-08 → canonical-v1-2026-08+tests-v1` en `canonical_store_v2/` + `graph_store_v2/`
+ paquete `pilot_run/h10_extraction_v2_20260830/`.

```
v1_stores_preserved        = YES   (md5 de árbol canonical_store/ + graph_store/ idéntico antes/después)
determinism_2x             = PASS  (3 fingerprints idénticos run1 vs run2)
document_egress_bytes      = 0
human_gate_intact          = true
_EXT_VER / _CANON (prod)   = SIN TOCAR   -> producción sigue en canonical-v1-2026-08
```

**Rollback:** no requiere acción — producción nunca cambió. Los stores `_v2` son adicionales.

---

## 6 · Regresión

`pytest factory/tests/` (2026-08-30): **`6 failed · 3002 passed · 79 skipped · 1 xfailed`** (344 s).

```
HISTORICAL_ACCEPTED_FAILURES (⊂ baseline 9-EXC):
  Entorno / servicios en vivo:
    test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas
    test_mission_evidence_readers::test_deployment_exists_and_health
LEDGER_GUARD_FAILURES (store == git HEAD; AUTO-CLEAR al commitear; 3 registros: D-2 x2 + D-4):
    test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store
    test_governance_endpoints::test_the_two_stores_stayed_independent
    test_governance_signature_flow_g21::test_n13_no_test_in_this_file_touched_the_real_store
    test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store

NEW_REGRESSIONS = 0
```

Tests nuevos verdes: `test_extract_entities.py` (4) · `test_graph_build_and_trace::test_h10_refers_to…` (1).
`test_extract_tests`, `test_canonical_model`, `test_table_structure_extractor`,
`test_h4_graph_snapshot` (`b5196a71…` sin mover): PASS. Suite exit ≠ 0 → **no GREEN**.

---

## 7 · Impacto de H-10 sobre H-8

```
QA40_SOURCE_UNITS_STILL_RESOLVABLE   = YES   (production canonical_store/graph_store SIN CAMBIO ; _EXT_VER en v1 ;
                                             QA40 cubre RW-0005/0006/0011/0012/0014 — todos resolubles)
EXISTING_HUMAN_GROUND_TRUTH_AVAILABLE = NO
H8_READJUDICATION_REQUIRED            = NO    (sin activación productiva ; y sin ground truth que re-adjudicar.
                                             Si en el futuro se activa +tests-v1 sobre re-extracción limpia, los
                                             finding_id de QA40 se re-resuelven — pero seguiría sin ground truth humano.)
QA40_RESAMPLED                        = NO
QA40_SHA (inmutable)                  = 02b6d3d0b6fadb1f882c4e63b7f7421dd387268ddabe5b5f16abfa5d9d360d32
QA40_SAMPLE_PRECISION / REAL_RECALL / REAL_SPECIFICITY = UNKNOWN   (sin inventar)
H8_HUMAN_GROUND_TRUTH_MISSING         = YES
```
