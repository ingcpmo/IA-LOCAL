# PAQUETE DE GATES HUMANOS — POST R-PAR

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Preparado por:** Capa 8 (Claude Code).
**Tipo:** preparación READ-ONLY. **No contiene ninguna decisión humana.** El objetivo es dejar
exactamente lo que Capa 9 debe decidir ahora.

Estado técnico aceptado: `TECHNICAL_VALIDATION_COMPLETE=YES · H10_TECHNICAL_ACCEPTANCE=PASS ·
R_PAR=PASS · MATERIAL_REGRESSION=NO · ALL_MATERIAL_DELTAS_EXPLAINED=YES · RETURN_TO_DESIGN_REQUIRED=NO`.

Sin cambios de código analítico, sin rediseño, sin QA40, sin auto-adjudicación, sin flip de
`_EXT_VER`/`_CANON`, sin activación, sin commit.

---

## 1 · E1 — REVISIÓN HUMANA DE LA MUESTRA H-10

**Archivo (no modificado):**
`factory/regulatory/pilot_run/h10_extraction_v2_20260830/H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json`

```
SAMPLE_ROWS                  = 77
TESTED_BY_ROWS               = 17   (todas las aristas tested_by de la corrida)
REFERS_TO_ROWS               = 60   (muestra determinista por edge_id ; total en el grafo = 350)
VERIFIES_ROWS                = 0    (N/A estructural — el SAT no cita ids del catálogo regulatorio, RR-3)
SAMPLE_SHA256                = f56d4babe7e8466368c9a6dbefe26e3716186f96e2658c68cf2f0469f5244f20
HUMAN_FIELDS_COMPLETE_SCHEMA = YES  (cada fila trae HUMAN_VERIFIED / HUMAN_VERDICT / HUMAN_NOTE, vacíos)
ROWS_UNASSIGNED              = 77 / 77   (la máquina no ha marcado ninguna)
```

Campos por fila (todos presentes): `relation · source_document · page · exact_source_anchor ·
source_node · source_kind · source_label · destination_node · destination_kind ·
destination_label · requirement_or_ref · provenance_hash · HUMAN_VERIFIED · HUMAN_VERDICT ·
HUMAN_NOTE`.

**El humano decide por fila:** `CORRECT` · `WRONG_NODE` · `SPURIOUS` · `AMBIGUOUS`.

### 1.1 · `tested_by` — 17 filas (todas)

Origen: `RW-0006` (URS) → RW-0003 : 6 · `RW-0005` (FS) → RW-0003 : 11. Vía referencias reales
`3.2.3` / `UR3.2.3` (requisito URS) y `F05.05` (función FS). Destino: nodos `test` de RW-0003
(páginas 157, 158, 192). `provenance_hash`: `8b054b04…` (pág 192, vía `3.2.3`), `cd0bf8a2…` /
`b81489fb…` (págs 157/158, vía `F05.05`).

| # | src_doc | page | src→dst | ref | prov_hash (12) | dest = test de RW-0003, pág |
|---|---|---|---|---|---|---|
| 1 | RW-0006 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 2 | RW-0005 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 3 | RW-0005 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 4 | RW-0005 | 157 | claim→test | `F05.05` | `cd0bf8a2144e` | 157 |
| 5 | RW-0005 | 192 | claim→test | `UR3.2.3` | `8b054b046f67` | 192 |
| 6–9 | RW-0006 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 10 | RW-0005 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 11 | RW-0005 | 158 | claim→test | `F05.05` | `b81489fbaa3f` | 158 |
| 12 | RW-0006 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 13 | RW-0005 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |
| 14 | RW-0005 | 192 | claim→test | `UR3.2.3` | `8b054b046f67` | 192 |
| 15 | RW-0005 | 157 | claim→test | `F05.05` | `cd0bf8a2144e` | 157 |
| 16 | RW-0005 | 158 | claim→test | `F05.05` | `b81489fbaa3f` | 158 |
| 17 | RW-0005 | 192 | claim→test | `3.2.3` | `8b054b046f67` | 192 |

> **Nota de revisión:** `exact_source_anchor` de las filas `tested_by` empieza por la cabecera
> de la tabla de ejecución del SAT (`Item | Test Description | Expected Result | …`) seguida del
> escenario; `source_label` / `destination_label` en el JSON traen el texto del claim y del test.
> Abrir el JSON para el ancla completa. Punto de juicio: ¿cada claim fuente (URS/FS) que
> menciona `3.2.3` / `F05.05` se refiere realmente al mismo requisito/función que prueba ese
> caso SAT, o es una coincidencia de identificador?

### 1.2 · `refers_to` — 60 filas (muestra de 350)

Todas `claim → system_component` (excepto 1 `→ actor` = `Administrator`). `requirement_or_ref =
literal_name` (mención literal, diccionario cerrado). Distribución de la muestra por entidad
destino: `FactoryTalk` 16 · `FactoryTalk View` 14 · `CP01` 7 · `CompactLogix` 5 ·
`FactoryTalk View SE` 4 · `engineering workstation` 4 · `ControlLogix` 3 · `PCS-CP01` 2 ·
`FactoryTalk Historian` 1 · `FactoryTalk Linx` 1 · `PCS-CP-01` 1 · `thin client` 1 ·
`Administrator` 1. Por documento fuente: RW-0005 44 · RW-0014 7 · RW-0006 4 · RW-0011 3 ·
RW-0012 2.

Anclas de ejemplo (fila / documento / página / ancla): `1 / RW-0005 / 9 / "FactoryTalk Linx
Enterprise 6.21.00 Server"` · `3 / RW-0005 / 13 / "Allen-Bradley 1756-L83E ControlLogix 5580
Controller…"` · `7 / RW-0012 / 4 / "PCS – Process Control System (This project's panel is named
PCS-CP01…)"` · `11 / RW-0011 / 4 / "XAH-00001-06 DO PCS Status Indicator on PCS-CP-01 PCS"`.

> **Punto de juicio:** las aristas parten 100 % de claims sustantivas (la guarda
> `_is_reference_list_line` descarta las entradas de bibliografía). El juicio humano es sobre
> si la mención del nombre del componente en el claim constituye una **referencia funcional**
> (`CORRECT`) o es sólo una cita de catálogo/BOM sin relación de diseño (`SPURIOUS` / `AMBIGUOUS`).

```
E1_STATUS = READY_FOR_HUMAN
```

---

## 2 · E2 — PAQUETE R-PAR PARA APROBACIÓN HUMANA

**Archivo:** `docs_plan/R_PAR_DELTA_V1_V2_20260831.md` · crudo: `docs_plan/_r_par/R_PAR_RAW.json`
+ `docs_plan/_r_par/findings_{A,B,C,D}.json`.

Cuatro escenarios sobre el corpus de paridad de 6 documentos, mismo HEAD, ENFORCE:

| | findings | GRAPH_SNAPSHOT | FINDINGS | DETERMINISTIC | EGRESS |
|---|---|---|---|---|---|
| **A** V1 PROD | 456 | `88f15b69…` | `fdc29721…` | YES | 0 |
| **B** V1 CLEAN | 456 | `2fdda0e2…` | `926986c5…` | YES | 0 |
| **C** H10 CLEAN | 457 | `547157d6…` | `ec4c5a7d…` | YES | 0 |
| **D** H10 + RW-0003 SAT | 674 | `8ce23f30…` | `2b1a300a…` | YES | 0 |

A reproduce EXACTAMENTE la baseline D-2 (`88f15b69…` / `fdc29721…`).

**A→B — clone drift:** 100 % en RW-0012 (595 vs 258 claims; páginas fantasma 17/18;
sobre-segmentación de la pág 5). 35 findings regulatorios de la pág 5 **re-anclados** a claims
distintos; conteo total, distribución y bandas **idénticos**. `disappearance` = 38 sin
emparejar por `finding_record_id` → 3 emparejan por semántica → 35 verdaderamente sólo en A.
`UNEXPLAINED = 0`. `MATERIAL_REGRESSION = NO`. La ruta limpia ancla en páginas reales.

**B→C — efecto puro H-10:** **estrictamente aditivo.** `+1` `TEST_WITHOUT_REQUIREMENT`
(RW-0009, legítimo), `+348` `refers_to`, `+45` `system_component`, `+13` `actor`, `+1` `test`.
`removed = 0` · `band_changed = 0` · `implemented_by 1120→1120` · `designed_by 190→190` ·
`contradicts/supports` intactos.

**C→D — efecto de RW-0003:** `+165` Test · `+17` `tested_by` (via `3.2.3` / `F05.05`) · `+199`
tablas (194 con rol). **`RESOLVED_FINDINGS = 2`** (`REQUIREMENT_NOT_TESTED` de RW-0006). ·
`NEW_EVIDENCE_VISIBILITY = 162` (`TEST_WITHOUT_REQUIREMENT` — RR-1). · `NEW_FINDINGS = 57`
(`REGULATORY_INCONCLUSIVE` sobre RW-0003). · `ACTIONABLE_NOW +8`. · `band_changed = 0`.

**Decisión humana solicitada (no respondida aquí):**

```
E2_RPAR_ACCEPT = APPROVE / REJECT
E2_STATUS      = READY_FOR_HUMAN
```

---

## 3 · E3-A — ACEPTACIÓN DE LA BASELINE CANDIDATA (canonical CLEAN)

**No se realiza ningún flip.** E3-A es **únicamente** aceptar el canonical limpio como baseline
candidata. **No equivale a `PRODUCTION_ENABLEMENT` ni a cutover.**

```
CURRENT_BASELINE      = canonical-v1-2026-08
                        (canonical_store/ de producción — CON clone-drift preexistente ;
                         fingerprints D-2 : INPUT_CONFIG 3c8b0036… · GRAPH_SNAPSHOT 88f15b69… · FINDINGS fdc29721…)
CANDIDATE_BASELINE    = canonical-v1-2026-08+tests-v1
                        (canonical_store_v2/ + graph_store_v2/ — re-extracción LIMPIA del clon + RW-0003 SAT ;
                         fingerprints : INPUT_CONFIG 0de04225… · GRAPH_SNAPSHOT 8ce23f30… · FINDINGS 2b1a300a… ;
                         2 corridas frescas idénticas)

RW0012_PROD_CLAIMS    = 595
RW0012_CLEAN_CLAIMS   = 258   (re-extracción HEAD flag-OFF = 258 == H-10 v2 ; fresh ⊂ prod ; only_fresh = 0)

CLONE_DRIFT_EXPLAINED = YES   (PREEXISTING_CLONE_DRIFT ; docs_plan/CIERRE_H10_DRIFT_CANONICAL_20260830.md)
MATERIAL_REGRESSION   = NO    (código HEAD flag-OFF reproduce el 258 ; H-10 no toca extract_claims_for_section)
ROLLBACK_AVAILABLE    = YES   (canonical_store/ + graph_store/ v1 byte-idénticos ; _EXT_VER/_CANON sin tocar ;
                               borrar canonical_store_v2/ no afecta a producción)
```

Precondición: E1 aceptado (las aristas nuevas de la baseline candidata verificadas) y E2
aceptado (deltas caracterizados).

**Decisión humana solicitada (no respondida aquí):**

```
E3A_CANONICAL_CLEAN_ACCEPT = APPROVE / REJECT
E3A_STATUS                 = READY_FOR_HUMAN
```

---

## 4 · IMPACTO SOBRE H-8 ANTES DE D-5 (sin modificar QA40)

QA40 se generó de una corrida con `INPUT_CONFIG_FINGERPRINT = 3c8b0036…` = **escenario A /
baseline D-2**. `qa40_finding_ids_sha256 = 02b6d3d0…`. 40 casos, `DRAFT_UNSIGNED`.

**Resolución de los 40 `finding_record_id` de QA40 contra cada escenario:**

| Escenario | resuelven por `finding_record_id` |
|---|---|
| A (V1 PROD = D-2 baseline) | **40 / 40** |
| C (H10 CLEAN, RW-6) | 39 / 40 |
| **D (H10 + SAT = baseline candidata)** | **39 / 40** |

El único caso que NO resuelve en C/D: **`ADJ-34140454ec` — RW-0012 · `ALCOA_ATTRIBUTABLE_GAP` ·
pág 5**. Es uno de los 35 findings re-anclados por el clone-drift de RW-0012 (§2, A→B). El
hallazgo analítico **sigue existiendo en D** (RW-0012 `ALCOA_ATTRIBUTABLE_GAP` HIGH está en el
conjunto de D), pero anclado a otro claim → otro `source_hash` → otro `finding_record_id` (no
empareja tampoco por `(document, subtype, source_hash)`).

```
QA40_CAN_BE_APPLIED_TO_FINAL_V2_CANDIDATE = PARTIAL   (39/40 direccionan sin cambio ; 1 requiere re-resolución)
FINDING_RECORD_IDS_REQUIRE_RERESOLUTION   = YES        (1 caso : ADJ-34140454ec, RW-0012 ALCOA_ATTRIBUTABLE_GAP p5)
QA40_RESAMPLING_REQUIRED                  = NO          (el conjunto de casos NO cambia ; el hallazgo del caso
                                                        afectado persiste en D ; es re-anclaje, no desaparición.
                                                        Prohibido remuestrear automáticamente.)
```

### 4.1 · Qué debe hacerse ANTES de adjudicar D-5 para que las métricas correspondan a la versión que se cualificará

```
Paso 0  (E3-A)  Aceptar la baseline candidata (canonical CLEAN + RW-0003).  -> fija la versión que se cualificará.
Paso 1          Re-generar el DIRECCIONAMIENTO de QA40 (finding_record_id / finding_id) contra el escenario D
                (la baseline candidata), por procedimiento gobernado y DETERMINISTA:
                  - el CONJUNTO de 40 casos NO cambia (no se re-muestrea) ;
                  - 39 casos: finding_record_id idéntico -> sin acción ;
                  - 1 caso (ADJ-34140454ec): decisión humana explícita ->
                       (a) RE-RESOLVER: apuntar al finding_record_id del MISMO hallazgo RW-0012 ALCOA_ATTRIBUTABLE_GAP
                           pág 5 en D (re-anclado por clone-drift), o
                       (b) marcar SUPERSEDED_BY_EXTRACTION_V2 si Capa 9 juzga que el nuevo ancla no es equivalente.
                  - recomputar qa40_finding_ids_sha256 con la receta actual sobre los finding_id de D
                    (nuevo hash inmutable para la versión candidata ; el 02b6d3d0… queda como el de la baseline D-2).
Paso 2  (E4)   Adjudicar D-5 sobre la hoja QA40 YA ALINEADA a D -> QA40_SAMPLE_PRECISION / REAL_RECALL /
                REAL_SPECIFICITY corresponden a la versión candidata que D-6 cualificará.
```

> Alternativa (peor): adjudicar D-5 sobre la QA40 actual (alineada a A / D-2). Entonces las
> métricas describirían la baseline D-2, **no** la versión candidata — y habría que re-mapear
> igualmente el caso `ADJ-34140454ec`. Por eso el orden correcto es **E3-A antes de D-5**.

```
D5_READINESS                   = BLOCKED_UNTIL_E3A   (la adjudicación debe ir sobre la versión que se cualificará)
QA40_FINAL_VERSION_ALIGNMENT   = REQUIRED : re-resolución determinista de 1/40 direccionamientos + recompute de SHA
                                 tras E3-A ; SIN remuestreo ; SIN cambiar el contenido de los 40 casos.
```

---

## 5 · COMMIT CANDIDATO E6 — LISTAS EXACTAS (NO SE HACE COMMIT)

Comandos ejecutados (sólo lectura): `git status --short` · `git diff --name-status` ·
`git diff -- factory/layer9/decisions/decisions_v2.jsonl`. **No stage. No commit.**

### GOVERNED_LEDGER_FILES  (append-only, Part 11 — +3 registros vs HEAD)

```
factory/layer9/decisions/decisions_v2.jsonl
   + ARTIFACT_VERSION-2026-019  (D-2 ORIGINAL, APPROVE, decision_ref D-2-H7-20260830)
   + ARTIFACT_VERSION-2026-020  (D-2 CORRECTION seq=1, supersedes 019, decisor 'Cesar' canónico)
   + ARTIFACT_VERSION-2026-021  (D-4 ORIGINAL, APPROVE, SELECTED=docling, decision_ref D-4-H9-20260830)
   -> los 3 validan (validate_record: valid=True) ; test_decision_migration (sync A/B/v2): PASS
```

### GOVERNED_CONFIG_FILES  (firmados en D-2)

```
M  factory/regulatory/requirement_catalog/extraction_adequacy_thresholds.yaml   (status: SIGNED)
??  factory/regulatory/requirement_catalog/analysis_coverage_mode.yaml           (mode: ENFORCE + firma Cesar)
??  factory/regulatory/requirement_catalog/gxp_criticality.yaml                  (status: SIGNED + firma)
```

### CANDIDATE_CODE_FILES  (H-4 / H-5F / H-7 / H-8 / H-10 — este arco)

```
M  factory/regulatory/canonical/model.py                 (H-10: Provenance en Actor/SystemComponent ; build_system_component / build_actor)
M  factory/regulatory/canonical/extract_document.py      (H-10: _docling_content por lotes ; ocr= ; tablas docling -> Table+roles ; extract_tests_from_tables)
M  factory/regulatory/canonical/extract_tests.py         (H-10: extract_tests_from_tables ; _TABLE_REQREF_RE)
??  factory/regulatory/canonical/extract_entities.py      (H-10: NUEVO — NER cerrada anclada)
M  factory/regulatory/graph/build.py                     (H-10: _link_refers_to ; _is_reference_list_line)
M  factory/regulatory/findings/risk.py                   (H-7: compute_risk evidence_basis/coverage_status/mode)
M  factory/regulatory/validation_v2/run_fingerprint.py   (H-4 + H-7: graph_snapshot topología ; artefactos H-7)
M  factory/regulatory/validation_v2/v2_runtime.py        (H-4 + H-5F + H-7: snapshot inmutable ; egress_controls ; coverage_mode)
M  factory/regulatory/validation_v2/local_only.py        (H-5F: probe_external_reachability ; egress_control_state)
M  factory/regulatory/validation_v2/real_corpus_adjudication.py  (H-8: sample_for_adjudication campos aditivos)
??  factory/regulatory/requirement_catalog/gxp_criticality_loader.py  (H-7: NUEVO)
??  factory/regulatory/validation_v2/coverage_mode.py     (H-7: NUEVO)
M  factory/api/main.py                                   (H-5F: CORS allowlist ; fail-closed FACTORY_API_KEY)
M  factory/Dockerfile                                    (H-5F: iptables/iproute2 ; egress guard entrypoint)
M  factory/docker-compose.factory.yml                    (H-5F: red aislada ; NET_ADMIN ; mounts mínimos)
```

### TEST_FILES  (este arco)

```
??  factory/tests/test_h1_identity_critical_mutators.py
??  factory/tests/test_h2_audit_trail_isolated_from_tests.py
??  factory/tests/test_h3_finding_record_id.py
??  factory/tests/test_h4_graph_snapshot.py
??  factory/tests/test_h5f_hardening.py
??  factory/tests/test_h7_coverage_governance.py
??  factory/tests/test_extract_entities.py
M  factory/tests/test_graph_build_and_trace.py           (+test_h10_refers_to_by_literal_entity_mention)
M  factory/tests/test_extraction_adequacy.py             (D-2: refleja SIGNED)
M  factory/tests/test_wp_g_mission_control_panel.py       (fixture OBSERVE)
M  factory/tests/test_r2_3_judgment_relabel_consistency.py  (H-2b: review_queue_copy)
M  factory/tests/conftest.py                             (aislamiento review_queue — puede ser de misión previa; revisar)
```

### OPS_SCRIPTS  (este arco)

```
??  factory/scripts/ops/h9_extraction_benchmark.py
??  factory/scripts/ops/h10_test_extraction_rederivation.py
??  factory/scripts/ops/h10_execute_version_jump.py
??  factory/scripts/ops/h10_ingest_rw0003.py
??  factory/scripts/ops/h10_final_validation.py
??  factory/scripts/ops/r_par_delta_v1_v2.py
??  factory/scripts/ops/factory_state_manifest.py
??  factory/scripts/ops/restore_factory_state.py
??  factory/scripts/ops/factory_backup_retention.py
??  factory/scripts/ops/backup_factory_state.sh
??  factory/scripts/ops/factory_egress_guard.sh
```

### EVIDENCE_DOCS  (cierres + paquetes de este arco)

```
??  docs_plan/CIERRE_H1_H2_H3_20260829.md  (ó CIERRE_BLOQUE_H1_H2_H3_20260829.md — revisar duplicado)
??  docs_plan/CIERRE_H2B_H4_20260829.md      ??  docs_plan/CIERRE_H5F_H6F_20260829.md
??  docs_plan/CIERRE_H7_TECNICO_Y_GATE_D2_20260829.md   ??  docs_plan/CIERRE_H7_ENFORCE_D2_20260830.md
??  docs_plan/CIERRE_D2_H7_ENFORCE_20260830.md          ??  docs_plan/CIERRE_H8_EVIDENCIA_REAL.md
??  docs_plan/PAQUETE_D5_ADJUDICACION_H8_20260830.md    ??  docs_plan/D3_DOWNLOAD_MANIFEST_20260830.md
??  docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION.md         ??  docs_plan/CIERRE_H9_BENCHMARK_EXTRACCION_20260830.md
??  docs_plan/CIERRE_H10_CAPACIDAD_20260830.md          ??  docs_plan/CIERRE_H10_DRIFT_CANONICAL_20260830.md
??  docs_plan/WP_F_PAQUETE_EVIDENCIA_20260830.md        ??  docs_plan/PAQUETE_D6_QUALIFICATION_20260830.md
??  docs_plan/CIERRE_TECNICO_PLAN_H1_H10_20260830.md    ??  docs_plan/INFORME_MAESTRO_EJECUCION_GMP_AI_FACTORY_H1_H10_20260830.md
??  docs_plan/R_PAR_DELTA_V1_V2_20260831.md             ??  docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md  (este doc)
??  docs_plan/R0_BASELINE_ANCLADO.md · R1_REVALIDACION_HALLAZGOS_HEAD.md · R1B_PREVIO_H5_H6_20260829.md ·
     R2_CONTAMINACION_AUDIT_TRAIL.md · R3_INVENTARIO_MUTADORES.md · R4_IMPACTO_UNICIDAD_FINDING_ID.md ·
     R5_DIAGNOSTICO_ARISTAS.md · REDISENO_H5_H6_POST_R1B_20260829.md · GATE_D3_DESCARGAS_H9.md ·
     H9_PREPARACION_BENCHMARK_EXTRACCION.md
```

### GENERATED_STORES_NOT_TO_COMMIT   (regenerables ; NO al repo ; requieren entrada en `.gitignore`)

```
factory/regulatory/canonical_store_v2/                        (4.8 MB — stores del salto ; regenerable)
factory/regulatory/graph_store_v2/                            (1.2 MB — idem)
factory/regulatory/pilot_run/h10_extraction_v2_20260830/      (12 MB — paquetes de corrida + muestra humana*)
factory/regulatory/validation_v2/_h9_assets/                  (1.4 GB — modelos docling/torch/ONNX ; NUNCA al repo)
docs_plan/_h9_full/                                           (220 KB — JSON de benchmark + logs de regresión)
docs_plan/_r_par/                                             (1.4 MB — R_PAR_RAW.json + findings_{A..D}.json)
```
> *La muestra `H10_NEW_RELATIONS_SAMPLE_FOR_HUMAN.json` es evidencia de gate humano; Capa 9 decide
> si va a un repositorio de evidencia (no al árbol de código) o se conserva fuera de git.

### TEMP_FILES_NOT_TO_COMMIT / FUERA DEL ALCANCE DE ESTE ARCO

```
.claude/settings.local.json · software_inventory.txt · factory/layer9/remediation_directives.jsonl (R1.8 previo)
factory/docs/design/regulatory_redesign_v2/*.py  (scripts de diseño de misiones previas)
factory/regulatory/corpus_run/ · factory/remediation_packages/ · factory/regulatory/pilot_run/{adjudication,fase2_*,fase5_*,n2_isolated_*,paso_a_*}/
factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/*.docx  (M — binarios de misión previa)
Muchos M en factory/api/routes/*, factory/regulatory/findings/taxonomy.py, factory/core/audit_writer.py,
factory/services/*, y varios test_* : provienen de misiones ANTERIORES (p.ej. commit d84a7c2 "WP-B OBSERVE").
```

### Veredicto

```
CONTROLLED_COMMIT_READINESS   = NOT_READY
READY_FOR_CONTROLLED_COMMIT   = NO
Motivos:
  1. El árbol de trabajo mezcla este arco (H-1…H-10 / R-PAR) con cambios de MÚLTIPLES misiones previas
     (M en factory/api/routes/*, taxonomy.py, audit_writer.py, services/*, .docx, etc.). Capa 9 debe
     DEFINIR EL ALCANCE EXACTO del commit gobernado antes de hacer stage.
  2. Directorios generados sin entrada en .gitignore — canonical_store_v2/, graph_store_v2/, _h9_assets/
     (1.4 GB), _h9_full/, _r_par/, pilot_run/h10_extraction_v2_20260830/. Deben gitignorarse ANTES del commit.
  3. Hay que resolver duplicados de nombre en docs_plan (p.ej. CIERRE_H1_H2_H3 vs CIERRE_BLOQUE_H1_H2_H3 ;
     PAQUETE_D5_ADJUDICACION_H8 vs _20260830).
  4. E6 (commit) debe ir DESPUÉS de E1/E2/E3-A y de la re-resolución de QA40 (§4.1 Paso 1), para que el
     árbol que se commitea sea coherente con la versión candidata aceptada.
```

---

## 6 · SECUENCIA GOBERNADA — RECONCILIACIÓN

El informe maestro tenía lenguaje que admite dos lecturas. **Lectura correcta, sin reglas nuevas**
(consistente con `DISENO_H1_H10_ACTUALIZADO_R0_R5` y los cierres): la **activación productiva NO
es prerrequisito de la qualification**, pero la qualification **cualifica una VERSIÓN concreta**,
y esa versión debe ser la baseline candidata aceptada (E3-A) para que las métricas de H-8
correspondan. Por tanto E3-A precede a D-5.

Cinco fases distintas, **ninguna ejecutada aquí**:

```
FASE 1 — CANDIDATE BASELINE ACCEPTANCE            [gate humano ; NO es producción]
   E1  verificar la muestra H-10 (77 relaciones)                        -> H10_HUMAN_SAMPLE_VERIFICATION = VERIFIED
   E2  aceptar R-PAR                                                     -> E2_RPAR_ACCEPT = APPROVE
   E3-A aceptar el canonical CLEAN + RW-0003 como baseline candidata     -> E3A_CANONICAL_CLEAN_ACCEPT = APPROVE
   (post) re-resolución determinista del direccionamiento de QA40 a la versión candidata (§4.1 Paso 1) ; SIN remuestreo
   Resultado: CANDIDATE_BASELINE = canonical-v1-2026-08+tests-v1 ACEPTADA.  _EXT_VER/_CANON SIN TOCAR.

FASE 2 — QUALIFICATION (D-6)                      [gate humano ; NO es producción]
   E4  D-5 : adjudicar y firmar QA40 (ya alineada a la versión candidata) + oportunidades + unidades negativas
        + held-out  -> QA40_SAMPLE_PRECISION / REAL_RECALL / REAL_SPECIFICITY (metric_envelope)
   E5  firmas humanas de Capa 9 / QA sobre H-1…H-7 y D-2
   E6  commit gobernado y controlado del ledger + código + config + tests + ops + evidencia
        (con alcance definido por Capa 9 ; .gitignore para stores generados)  -> limpia los 4 guards store==git-HEAD
   D-6 : decisión humana de qualification  -> QUALIFIED_VERSION = canonical-v1-2026-08+tests-v1  (o NOT_ELIGIBLE_YET)

FASE 3 — PRODUCTION ENABLEMENT                    [decisión de gobernanza SEPARADA de D-6]
   Capa 9 decide PRODUCTION_ENABLEMENT = ENABLED para la versión cualificada.
   Requiere D-6 = QUALIFIED. No lo otorga automáticamente ninguna fase anterior.

FASE 4 — CUTOVER                                  [cambio técnico ejecutado]
   flip en factory/regulatory/validation_v2/v2_runtime.py:
     _CANON  = canonical_store  -> canonical_store_v2      (línea 45)
     _GRAPH  = graph_store      -> graph_store_v2          (línea 46)
     _EXT_VER = "canonical-v1-2026-08" -> "canonical-v1-2026-08+tests-v1"   (línea 47)
   + re-extracción LIMPIA del corpus completo con el código HEAD (ya materializada en canonical_store_v2/)
   + registrar la nueva baseline de los 3 fingerprints (INPUT_CONFIG 0de04225… / GRAPH_SNAPSHOT 8ce23f30… / FINDINGS 2b1a300a…)

FASE 5 — POST-CUTOVER REGRESSION                  [verificación post-cambio]
   pytest factory/tests/ completo  -> NEW_REGRESSIONS = 0 esperado ; los 4 guards store==git-HEAD limpios (por E6)
   verificación de fingerprints en vivo == baseline registrada en FASE 4
   confirmación de rollback: revertir el flip vuelve a canonical-v1-2026-08 sin pérdida (stores v1 intactos)
```

Distinciones clave:
- **E3-A (candidate baseline acceptance) ≠ CUTOVER ≠ PRODUCTION_ENABLEMENT.** E3-A no toca
  `_EXT_VER`/`_CANON`; sólo declara que la versión candidata es aceptable como objeto a cualificar.
- **D-6 (qualification) NO requiere activación productiva.** Se alcanza con FASE 1 + FASE 2.
- **PRODUCTION_ENABLEMENT (FASE 3) es una decisión de gobernanza separada** que exige D-6 = QUALIFIED.
- **CUTOVER (FASE 4) es sólo el cambio técnico** una vez concedido PRODUCTION_ENABLEMENT.

```
GOVERNED_SEQUENCE_TO_D6         = FASE 1 (E1 -> E2 -> E3-A -> re-resolución QA40) -> FASE 2 (E4 -> E5 -> E6 -> D-6)
GOVERNED_SEQUENCE_TO_PRODUCTION = ... -> D-6 = QUALIFIED -> FASE 3 (PRODUCTION_ENABLEMENT) -> FASE 4 (CUTOVER) -> FASE 5 (post-cutover regression)
```

---

## 7 · CAMPOS DE CIERRE DEL PAQUETE

```
E1_STATUS                        = READY_FOR_HUMAN
E2_STATUS                        = READY_FOR_HUMAN
E3A_STATUS                       = READY_FOR_HUMAN

D5_READINESS                     = BLOCKED_UNTIL_E3A   (la adjudicación debe ir sobre la versión que se cualificará)
QA40_FINAL_VERSION_ALIGNMENT     = REQUIRED : re-resolución determinista de 1/40 direccionamientos (ADJ-34140454ec) +
                                   recompute de qa40_finding_ids_sha256 tras E3-A. SIN remuestreo. SIN cambiar los 40 casos.

CONTROLLED_COMMIT_READINESS      = NOT_READY  (alcance del commit por definir por Capa 9 ; .gitignore para stores generados ;
                                   E6 va después de E1/E2/E3-A y de la re-resolución de QA40)

GOVERNED_SEQUENCE_TO_D6          = E1 -> E2 -> E3-A -> re-resolución QA40 -> E4 (D-5) -> E5 (firmas) -> E6 (commit) -> D-6
GOVERNED_SEQUENCE_TO_PRODUCTION  = [GOVERNED_SEQUENCE_TO_D6] -> D-6=QUALIFIED -> PRODUCTION_ENABLEMENT -> CUTOVER (flip _EXT_VER/_CANON/_GRAPH) -> POST-CUTOVER REGRESSION

DECISIONS_TAKEN_BY_MACHINE       = NINGUNA
CLAIMS_THAT_MUST_NOT_BE_MADE     = QA_APPROVED=NO · QUALIFIED=NO · RELEASED=NO · CAPA_CLOSED=NO ·
                                   FINAL_GMP_APPROVAL=NO · PRODUCTION_ENABLEMENT=NOT_ENABLED ·
                                   REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM
```

**STOP.** Este paquete prepara las decisiones de Capa 9; no las toma.
