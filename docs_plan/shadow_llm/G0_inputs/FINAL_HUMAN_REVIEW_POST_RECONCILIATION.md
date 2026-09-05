# FINAL HUMAN REVIEW — POST-RECONCILIATION (Plan v1.1, arco F0-F9)

**Documento autocontenido para revisión humana de Capa 9.**
**Fecha de la corrida:** 2026-09-02 · **Ejecutor:** Claude Code (Capa 8) · **Modo:** READ-ONLY.
No reabre F0-F9 · no implementa fixes · no corrige tests · no crea decisiones de gobernanza ·
no ejecuta PILOT-035 · no inicia R2 · no habilita producción.

**Fuente de verdad:** rama `fix/clon-local-validacion` · tag de aceptación **`reconc-acceptance-v1` → `0e1e88a`** ·
código del cierre **`reconc-arc-closure` → `56bd36a`**.
**Clon de verificación:** `/tmp/final_human_review/clone` (separado del origen), `git checkout reconc-acceptance-v1`.

---

## 1. Executive Summary

El arco de reconciliación F0-F9 (8 discrepancias D1-D8) se ejecutó fase a fase con auditoría
independiente de Devin, cruce de la mesa (`VERDICT_F8 = PASS`) y gate humano de Capa 9 (F9:
E2 y E3-A firmados por Mission Control). Esta corrida FINAL reconstruye **todo desde cero** en un
clon limpio con **sólo los 6 PDF del corpus** (sha256 verificado) y demuestra objetivamente:

- **`CODE_CHANGES_PRESENT = YES`** — los cambios F1/F2-r1/F3 están en el HEAD final (`git show` + sha256).
- **`CLEAN_REBUILD = PASS`** — stores regenerados 3× de forma determinista; 6/6 logical hashes
  canónicos + graph logical hash == `VALIDATION_BASELINE_MANIFEST`; RW-0012 = **8 secciones / 258 claims**.
- **Extractor:** PRE = **0/8**, FINAL = **8/8** en RW-0011/RW-0012/RW-0014 (`GROUND_TRUTH_SHA256 = 2f7a00dc…`).
- **`TARGETED_RESULT = 124 passed / 0 failed`**.
- **Fingerprints** reproducidos **exactos** (INPUT_CONFIG `3fcb3ae8…`, GRAPH_SNAPSHOT `2fdda0e2…`,
  FINDINGS ENFORCE `235f724a…`, OBSERVE `693fc746…`), counts **342/90/25**, RUN1 == RUN2.
- **`RPAR_ABC_REPRODUCIBLE = YES`** — A=457, B=457, C=458; RUN1==RUN2; `findings_A/B/C.json`
  sha256 **byte-idénticos a `F6_hashes.json`**; `only_in_A = only_in_B = 0`; `only_in_C = 1`
  (`TEST_WITHOUT_REQUIREMENT` / RW-0009 / LOW); egress 0; human gate intacto; D = `SKIPPED_NO_STORE`.
- **Full suite:** 2978 passed / **32 failed** / 95 skipped — **idéntico a Acceptance V1**.
  **`NEW_REGRESSIONS = 0`**. `KNOWN_STALE_HARDENING_FAILURES = 4` (F5 §5, ya registradas).
- **Governance:** `E2_GATE_SIGNED = YES`, `E3A_GATE_SIGNED = YES` (verificado READ-ONLY en el
  ledger; propose→confirm, `approved_by_id=Cesar`, `status=ACTIVE`). Sin hand-edit.
- **Se mantienen bloqueados:** `R2_READY_TO_RESUME = NO`, `PILOT_EXECUTION-2026-035 = HOLD`,
  `LLM_CALLS = 0`, `PRODUCTION_ENABLEMENT = BLOCKED`.
- **Origen intacto** antes y después (HEAD/ledger/audit trail/stores/tags sin cambio).

**`FINAL_HUMAN_REVIEW_RECOMMENDATION = ACCEPT_WITH_FOLLOW_UP`** — la reconciliación reproduce
objetivamente todos los resultados aprobados desde un clon limpio; los 7 follow-ups abiertos
(§13) son conocidos, documentados y no bloquean el desarrollo, pero deben resolverse antes de
`FINAL_QUALIFICATION`.

---

## 2. Objetivo de la reconciliación

Resolver 8 discrepancias (D1-D8) entre el **diseño** del rediseño regulatorio V2 y su
**ejecución**, sin rediseñar H-1…H-10, dejando una base:

- reproducible desde clon limpio + corpus + manifest (sin stores heredados del entorno),
- con extracción de estructura correcta para las plantillas MAVERICK (encabezados "N. TÍTULO"),
- con `canonical_store` limpio (RW-0012 sin contaminación WFI),
- con `graph_store` determinista,
- con fingerprints re-baselinados sobre el estado limpio,
- con el ledger reconciliado sin hand-edits,
- apta para que Capa 9 firme E2 (paridad v1↔v2) y E3-A (base limpia).

---

## 3. Baseline PRE (estado antes del arco)

| dimensión | estado PRE |
|---|---|
| HEAD real | `9096005` (descubierto en F0; el plan v1.0 asumía `6be0626`) |
| Extractor | `_HEADING_RE = ^(\d{1,2})\s+(...)$` → **no reconoce** "1. OBJECTIVE"; RW-0011/0012/0014 = **0 secciones de nivel 1** |
| `canonical_store` RW-0012 | **contaminado**: 13 secciones / 595 claims (8 WFI de RW-0014 + 5 PCS reales); causa `b4b_runner._PDF_BY_DOC["RW-0012"]` → PDF WFI |
| `graph_store` | **no determinista**: `attrs.via_ref` last-write-wins por orden de `set` (PYTHONHASHSEED) |
| Stores | dependientes del entorno; sin procedimiento de regeneración; doble hash sin definir |
| `r_par_delta_v1_v2.py` | leía `_RW0003_DET = Path("/tmp/claude-1000/.../RW-0003_ingested.sqlite3")` → abort en clon limpio |
| Fingerprints | históricos/contaminados (`88f15b69`, `fdc29721`, `b5196a71`, …) medidos sobre store contaminado |
| Ledger | `ARTIFACT_VERSION-2026-022..025` reusados (ID_COLLISION); `E1_SIGNATURE_HISTORY.md` divergente |
| Baseline técnico | `(342, 90, 26)` — el `26` era artefacto de la contaminación de RW-0012 |
| E2 / E3-A | no firmables (base no confiable) |

Ledger PRE (F0): 259 líneas, sha256 `1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4`.

---

## 4. Cambios de código implementados (contenidos en `reconc-acceptance-v1` / `0e1e88a`)

Todos verificados en el clon: `git cat-file -e HEAD:<archivo>` = YES.

| archivo | sha256 (HEAD final) | commit del cambio | diff |
|---|---|---|---|
| `factory/regulatory/document_structure_extractor.py` | `56236c1ace2800ed32c5be9712a0761a2084c969cb6527954c6f64104552a11a` | **`09656e1`** (F1) | `_HEADING_RE` / `_TOC_ENTRY_RE`: `(\d{1,2})\s+` → `(\d{1,2})\.?\s+` (4 líneas) |
| `factory/tests/test_document_structure_extractor.py` | `498f79b58c05dbd6f73f9965ce30b05d49787c6cab6038c6826a82a4840179a8` | **`09656e1`** (F1) | +97 líneas: test período, guarda de subsección, regresión "8 secciones nivel 1" |
| `factory/regulatory/graph/build.py` | `64d9e7d90a543879e06022a8fd4f8865af0bc9ea8e4a74d64abf67c9bde0a5c5` | **`4c64a05`** (F2-r1) | 3× `sorted()`: `_link_chain` (`for ref in sorted(shared)`), `_link_to_tests` (`sorted(trefs & set(...))`), `_link_contradictions` (`sorted(ref_claims.items())`) |
| `factory/scripts/ops/materialize_stores.py` | `6b3ab58301fdbf4a897954b5212226a422c73b3662ed7bf3bd46545ed80ae321` | añadido `8c4e7ab` (F2), reescrito **`4c64a05`** (F2-r1) | `_PDF_MAP` declarado + verificado por sha256; `--runs`, `--apply` (con backup), `--baseline-manifest`; `logical_hash_sqlite` (BYTE vs LOGICAL, `F2_HASH_DEFINITION.md`) |
| `factory/tests/test_extraction_adequacy.py` | `e24b9b3451ed727062ec1b7b9895804ae21407d76828af915293cba1ebfbcc51` | **`4c64a05`** (F2-r1) | `:214` `assert (len(reg),len(func),len(tech)) == (342,90,26)` → `== (342,90,25)` + comentario ("`26` era artefacto de la contaminación de RW-0012") |
| `factory/scripts/ops/r_par_delta_v1_v2.py` | `a1571739f91035c13f6412b399ab447816e06f52fd515f3f04b31b393313a8c2` | **`484abea`** (F3) | elimina `_RW0003_DET = Path("/tmp/claude-1000/...")` y su `shutil.copy2`; añade `_resolve_rw0003_store(manifest)` (None si `status != AVAILABLE`), `_skipped_scenario` (`status: SKIPPED_NO_STORE`), `_selfcheck` (patrones compuestos), `--check` / `--dry-run-abc`; A fail-closed contra el manifest (+135 / -25) |

Cadena de commits del arco (13 tags): `reconc-F0`(3749569) · `-F1`(09656e1) · `-F1-r1`(414557f) ·
`-F2`(8c4e7ab) · `-F2-r1`(4c64a05) · `-F3`(484abea) · `-F4`(6b34051) · `-F5`(ab8a896) ·
`-F6`(9930fc5) · `-F7`(a9567c1) · `-F8`(4233df7) · `-F9`(2a5e222) · `-F9-r1`(d55694f) ·
`reconc-arc-closure`(56bd36a) · `reconc-acceptance-v1`(0e1e88a). Lineal, sin merges;
`reconc-F1`/`-F2`/`-F9` históricos no movidos.

---

## 5. Cambios de comportamiento demostrados (clon limpio, esta corrida)

| # | comportamiento | evidencia reproducida |
|---|---|---|
| 1 | Extractor reconoce "N. TÍTULO" | `F1_measure.py`: HEAD-limpio `toc_anchored=False n=0`; con-cambio `toc_anchored=True n=8` en RW-0011/0012/0014 |
| 2 | RW-0012 des-contaminado | `materialize_stores.py`: RW-0012 = **8 secciones / 258 claims** (PRE 13/595) |
| 3 | `graph_store` determinista | `materialize_stores.py --runs 3`: `DETERMINISTA graph: True`; graph LOGICAL `3ead71532cf44fab…` idéntico 3/3 |
| 4 | Stores reconstruibles desde corpus + manifest | 6/6 canonical logical + graph logical == `VALIDATION_BASELINE_MANIFEST`; `pdf_map_source = DECLARADO en _PDF_MAP (verificado por sha256); NO se leen stores del origen` |
| 5 | R-PAR sin ruta efímera | `r_par_delta_v1_v2.py --check` → `SELFCHECK OK: sin rutas efimeras hardcodeadas`, exit 0 |
| 6 | Clone-drift eliminado | R-PAR A↔B: `only_in_A = 0`, `only_in_B = 0`, `band_changed = 0`; `findings_A.json == findings_B.json` byte a byte (`b43b548b…`) |
| 7 | Fingerprints reproducibles y re-baselinados | `run_v2_pipeline` ×2: los 4 digests exactos + counts 342/90/25; RUN1==RUN2 |
| 8 | Governance E2/E3-A firmable y firmada | ledger: `AV-2026-026/027` (E2) y `AV-2026-028/029` (E3-A), `human_confirmed` por `Cesar`, `ACTIVE` |

---

## 6. Tabla PRE → FIX → FINAL

| # | ESTADO PRE / PROBLEMA | CAMBIO IMPLEMENTADO | ESTADO FINAL REPRODUCIDO |
|---|---|---|---|
| 1 | **Extractor**: `\d{1,2}\s+` no reconoce "1. OBJECTIVE" → RW-0011/0012/0014 = **0/8** secciones | regex `(\d{1,2})\.?\s+` en `_HEADING_RE` y `_TOC_ENTRY_RE` (F1, `09656e1`), contra ground truth humano `2f7a00dc…` | **8/8** en los 3 documentos (`F1_measure.py`: PRE 0/8, FINAL 8/8) |
| 2 | **RW-0012**: 13 secciones / 595 claims **contaminados** (`b4b_runner` mapea RW-0012→PDF WFI) | `_PDF_MAP` declarado con el PDF correcto (PCS Signal Interface) + sha256; re-materialización limpia (F2-r1) | **8 secciones / 258 claims** (determinista, 3/3) |
| 3 | **graph_store**: no determinista (`via_ref` last-write-wins por orden de `set`) | 3× `sorted()` en `build.py` (F2-r1). Probado que NO mueve la topología | graph LOGICAL `3ead71532cf44fab…` **idéntico 3/3** con `PYTHONHASHSEED=random` |
| 4 | **Stores**: dependientes del entorno; sin regeneración; doble hash sin definir | `materialize_stores.py` (F2/F2-r1) + `F2_HASH_DEFINITION.md` (BYTE vs LOGICAL) congelado antes de medir | **reconstruibles** desde 6 PDF + manifest; 6/6 canonical + graph logical == manifest |
| 5 | **R-PAR**: `_RW0003_DET` en `/tmp/claude-1000/...` → abort en clon limpio | fuente = manifest; `_resolve_rw0003_store` (None si no AVAILABLE); `_skipped_scenario`; A fail-closed (F3, `484abea`) | **A/B/C reproducibles**; `--check` OK 0 rutas efímeras; **D = `SKIPPED_NO_STORE`** (no aborta, no es requisito de E2/E3-A) |
| 6 | **Clone drift**: no reconciliado (extracción de producción ≠ re-extracción limpia) | F1 (extractor) + F2-r1 (stores limpios) + F5 (rebaseline) | R-PAR A↔B: **`only_in_A = 0` / `only_in_B = 0`**; findings A==B byte a byte |
| 7 | **Fingerprints**: históricos/contaminados (`88f15b69` / `fdc29721` / `b5196a71`) | F5 rebaseline sobre HEAD limpio, counts 342/90/25; 9 digests marcados HISTÓRICOS | `INPUT_CONFIG 3fcb3ae8…` · `GRAPH_SNAPSHOT 2fdda0e2…` · `FINDINGS ENFORCE 235f724a…` / `OBSERVE 693fc746…`, **RUN1==RUN2** |
| 8 | **Governance**: ID_COLLISION + reconciliación incompleta del ledger + `E1_SIGNATURE_HISTORY.md` divergente | F4 (clasificación por id, 0 hand-edits, D6/D7 cerrados, D8 alineado) + F9 (verificación de firmas humanas) | **E2 y E3-A firmados por mecanismo gobernado** (`AV-2026-026..029`, `human_confirmed`/`Cesar`/`ACTIVE`). **El bug del generador de IDs NO está corregido** — sigue como carry-forward (§13.2) |

---

## 7. Rebuild desde clon limpio

```
git clone --no-local /home/cmay/ivr-ia /tmp/final_human_review/clone
git checkout reconc-acceptance-v1        HEAD = 0e1e88a8751ebd8426530ee7303659b29e340042   ✅
git status --porcelain                    (vacío — checkout limpio)

# Sólo 6 PDF provistos (clon SIN canonical_store / graph_store / _r_par previos):
ALL_6_PDF_SHA256_MATCH = True   (vs VALIDATION_BASELINE_MANIFEST.pdf_map)
  RW-0005 56095a75…  RW-0006 d9e24467…  RW-0009 2edb00a3…
  RW-0011 13bc6f50…  RW-0012 de7b70c2…  RW-0014 8a67414d…

PYTHONHASHSEED=random  materialize_stores.py --runs 3 --baseline-manifest VALIDATION_BASELINE_MANIFEST.json
  DETERMINISTA canonical: True   graph: True
  vs_manifest: canonical = {6/6 True}   graph = {True}
```

| doc | LOGICAL (3/3) | sections | claims |
|---|---|---|---|
| RW-0005 | `8e7196a007f02274240a492b19ee5f459d2b72b8573f02a729c21b4698901ffa` | 8 | 1409 |
| RW-0006 | `7da433b41c111d29224c66ab5dd794ef26de51c33cb6a2e993d8066a6b0ee6c8` | 8 | 515 |
| RW-0009 | `4922562de36feaa7bdc91ac67d01cec9e8a42ab8806eea45b44c80fcf6eb03c9` | 0 | 62 |
| RW-0011 | `1f2676308d557f7d8a53776f27bd0b64b24bc562ae57fd0494885e3386632492` | 8 | 317 |
| **RW-0012** | `155eb281df9105e26804c9f812db14b5e183758ab49a03bdf0308c915bcdbda4` | **8** | **258** |
| RW-0014 | `a180fdc1c5d0be286f84c6dd20eb684f84f0b1488b5b53d73ee6ab0ebf724e12` | 8 | 369 |
| graph `RW-TECH-REAL.sqlite3` | `3ead71532cf44fab4eea71867ef572b96aab3f69bfc0524739ea7b4e69224081` | — | nodes 3000 / edges 1330 |

```
CANONICAL_DETERMINISTIC = TRUE
GRAPH_DETERMINISTIC     = TRUE
6/6 canonical logical hashes == manifest
graph logical hash == manifest
RW-0012 = 8 secciones / 258 claims
```

`CLEAN_REBUILD = PASS`.

---

## 8. Resultados de tests

### 8.1 Extractor (Step 3)

```
F1_measure.py    RW-0011 / RW-0012 / RW-0014:  PRE = 0/8   FINAL = 8/8   (DELTA = 8 en los 3)
GROUND_TRUTH_SHA256 = 2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39   (coincidencia exacta con F1-r1)
pytest factory/tests/test_document_structure_extractor.py  ->  11 passed, 1 skipped
```

### 8.2 Targeted v1.2 (Step 4)

```
pytest -q  factory/tests/test_completeness_rules_v1_2.py  factory/tests/test_technical_findings.py \
           factory/tests/test_run_fingerprint.py  factory/tests/test_wp_e_measurement_independence.py \
           factory/tests/test_extraction_adequacy.py
->  124 passed, 24 warnings in 28.21s          0 failed
```

`TARGETED_RESULT = 124 passed / 0 failed`.

### 8.3 `test_run_fingerprint.py` (Step 5)

```
->  23 passed
```

### 8.4 Full suite (Step 7) — 3106 tests colectados, 8 sub-lotes

| sub-lote | passed | failed | skipped |
|---|---:|---:|---:|
| `test_[a-e]*` | 888 | 8 | 5 (+1 xfail) |
| `test_f*` | 90 | 0 | 0 |
| `test_g*` | 421 | 8 | 43 |
| `test_h*` | 126 | 4 | 5 |
| `test_[i-r]*` | 935 | 10 | 36 |
| `test_s*` | 218 | 2 | 6 |
| `test_t*` | 62 | 0 | 0 |
| `test_[u-z]*` | 238 | 0 | 0 |
| **TOTAL** | **2978** | **32** | **95 (+1 xfail)** |

**Comparación con Acceptance V1: 2978 passed / 32 failed / 95 skipped — IDÉNTICO.** Ningún
resultado cambió. **NO se declara `FULL_SUITE_GREEN`** (hay 32 failures).

#### Clasificación de las 32 fallas

**A · `KNOWN_STALE_HARDENING_FAILURE` = 4** — F5 §5, baseline de fingerprint hardcodeada
pre-de-contaminación. El clon limpio **produce** exactamente la baseline F5; el test falla sólo
por comparar contra el hash viejo:

| test | valor producido (clon) | hardcodeado (stale) |
|---|---|---|
| `test_h4_graph_snapshot.py::test_e2e_findings_fingerprint_matches_post_h1h2h3_baseline` | `693fc746e645b168…` (= F5 OBSERVE) | `b5196a7177c92a91…` |
| `test_h5f_hardening.py::test_h5f_does_not_move_findings_or_graph_fingerprint` | `693fc746e645b168…` | `b5196a7177c92a91…` |
| `test_h7_coverage_governance.py::test_e2e_observe_does_not_move_findings_or_graph` | `693fc746e645b168…` | `b5196a7177c92a91…` |
| `test_h7_coverage_governance.py::test_e2e_enforce_is_the_governed_production_path_post_d2` | `235f724a738ce783…` (= F5 ENFORCE) | `fdc29721e9566dfe…` |

**B · `ENVIRONMENTAL_OR_RUNTIME_DEPENDENCY` = 22** — el clon aislado no tiene runtime/servidor;
se le proveyeron SÓLO los 6 PDF (por instrucción). Ninguna toca los 4 módulos del arco:

| causa | tests | nº |
|---|---|---|
| Falta `factory/audit/factory_audit.jsonl` (untracked, NO copiado). Los tests esperan un fork/ruptura en la cadena real; sin fichero la cadena lee `VERIFIED` | `test_audit_fork_governance` (f01/f02/f04/f08) · `test_gate0_extended::…real_chain…` · `test_g7_audit_exception_readiness::…store_it_was_asked_about` · `test_status_risks::…fork_from_corruption` · `test_release_decision_coverage::…production_chain` | 8 |
| Falta `factory/regulatory/source_currency_log.jsonl` (untracked) | `test_g3_reverification_launcher` (6 casos) | 6 |
| App no escribe `factory/logs/access.jsonl` (sin servidor) | `test_access_log` (4 casos) | 4 |
| Sin API HTTP corriendo (health / 423) | `test_mission_evidence_readers::test_deployment_exists_and_health` · `test_release_decision_coverage::test_endpoint_returns_423_not_409` | 2 |
| Workspace de clon en detached HEAD | `test_runtime_identity::TestFailClosedGuard::test_assert_passes_on_a_reproducible_runtime` | 1 |
| Config v2 completa ausente | `test_shadow_and_cutover::test_shadow_run_v2_no_effects_and_reversible` | 1 |

**C · `PRE_EXISTING_OUT_OF_SCOPE` = 6** — `factory/services/remediation_directive.py` tiene un
parche PRE-EXISTENTE de +127 líneas ("Causa B / fcntl supersede", **declarado en F0 §2**,
**nunca commiteado por ninguna fase del arco**). El clon (que sólo tiene lo commiteado) no lo
lleva → `TypeError: propose_remediation_directive() got an unexpected keyword argument 'supersedes_directive_id'`:

| test | nº |
|---|---|
| `test_remediation_directive_endpoint` (`succeeds_for_confirmed_gap`, `rejects_supporting_evidence_trigger`, `rejects_empty_proposed_text`, `get_directives_lists_created_ones`) | 4 |
| `test_remediation_package_service::test_create_package_rejects_superseded_directive` | 1 |
| `test_release_decision_coverage::test_an_unbacked_fork_blocks_and_is_named` (mismo bundle out-of-scope) | 1 |

**D · `NEW_REGRESSION` = 0.** Ninguna falla es atribuible a
`document_structure_extractor.py`, `graph/build.py`, `materialize_stores.py` ni
`r_par_delta_v1_v2.py`. El targeted (124), extractor (11+1s), fingerprint (23) y R-PAR A/B/C
pasan y reproducen la baseline committeada exactamente.

```
KNOWN_STALE_HARDENING_FAILURES = 4
ENVIRONMENTAL_OR_RUNTIME_DEPENDENCY = 22
PRE_EXISTING_OUT_OF_SCOPE = 6
NEW_REGRESSIONS = 0
```

---

## 9. R-PAR final (Step 6)

```
r_par_delta_v1_v2.py --check   ->   SELFCHECK OK: sin rutas efimeras hardcodeadas   (exit 0)
```

| métrica | RUN 1 | RUN 2 | esperado |
|---|---|---|---|
| A status / n_findings | OK / **457** | OK / **457** | 457 ✅ |
| B status / n_findings | OK / **457** | OK / **457** | 457 ✅ |
| C status / n_findings | OK / **458** | OK / **458** | 458 ✅ |
| D status | `SKIPPED_NO_STORE` | `SKIPPED_NO_STORE` | SKIPPED_NO_STORE ✅ (no es requisito de E2/E3-A) |
| `determinism {A,B,C}` | `{true,true,true}` | `{true,true,true}` | true ✅ |
| A↔B `only_in_A` / `only_in_B` / `band_changed` | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 ✅ |
| B↔C `only_in_C` | 1 | 1 | 1 ✅ (`TEST_WITHOUT_REQUIREMENT` / RW-0009 / LOW) |
| B↔C `refers_to` (B→C) | 0 → 201 | 0 → 201 | — |
| `document_egress_bytes` (A/B/C) | 0/0/0 | 0/0/0 | 0 ✅ |
| `human_gate_intact` (A/B/C) | True/True/True | True/True/True | True ✅ |
| RUN1 == RUN2 (estructura, sin volátiles) | **True** | | |

Hashes de salida vs `F6_hashes.json` **committeado** (ambas corridas):

| fichero | sha256 (final run) | F6_hashes.json |
|---|---|---|
| `findings_A.json` | `b43b548b63e90014e7e9fc3b8cc9f98d8a24c2699a5e1711069336efc6cd4558` | `b43b548b…` ✅ |
| `findings_B.json` | `b43b548b63e90014e7e9fc3b8cc9f98d8a24c2699a5e1711069336efc6cd4558` | `b43b548b…` ✅ (== A) |
| `findings_C.json` | `e0dd292483ac7546bff47da705c4f07889ad258af3209186ce24379172bdba0d` | `e0dd2924…` ✅ |
| `findings_D.json` | `2ba3a8bd02ace0acefc0069edd7f0a1d2470d806a6e3532cb69dcf921aa11f10` | `2ba3a8bd…` ✅ |

`RPAR_ABC_REPRODUCIBLE = YES`.

---

## 10. Fingerprints finales (Step 5 — `run_v2_pipeline` ×2 + variante OBSERVE)

| fingerprint | RUN 1 | RUN 2 | esperado (F5 baseline) | |
|---|---|---|---|---|
| `INPUT_CONFIG_FINGERPRINT` | `3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668` | idéntico | `3fcb3ae8…` | ✅ |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` | idéntico | `2fdda0e2…` | ✅ |
| `FINDINGS_FINGERPRINT` (ENFORCE, modo gobernado por defecto) | `235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` | idéntico | `235f724a…` | ✅ |
| `FINDINGS_FINGERPRINT` (OBSERVE, variante) | `693fc746e645b168386537c7dbce8c6394b582fb6c031ebf62e44189b748a368` | — | `693fc746…` | ✅ |
| counts REGULATORY / FUNCTIONAL / TECHNICAL | **342 / 90 / 25** | 342 / 90 / 25 | 342 / 90 / 25 | ✅ |
| `llm_calls` / `document_egress_bytes` / `human_gate_intact` | 0 / 0 / True | 0 / 0 / True | — | ✅ |

`RUN1 == RUN2` (los 3 digests + counts). El modo efectivo se resuelve de
`analysis_coverage_mode.yaml` (firma D-2 `D-2-H7-20260830` + `extraction_adequacy_thresholds.yaml` SIGNED)
→ `ENFORCE`; la variante OBSERVE se obtuvo apuntando `coverage_mode` a un YAML `mode: OBSERVE`
temporal (sólo medición; sin cambio de código ni de config del repo).

---

## 11. Estado de governance E2 / E3-A (Step 9 — verificación READ-ONLY del ledger)

| gate | propose | confirm humano | `decision_ref` | `target_set_hash` | `status` |
|---|---|---|---|---|---|
| **E2** — delta R-PAR v1↔v2 | `ARTIFACT_VERSION-2026-026` (`agent_proposed`, `mission_control_ui`) | `ARTIFACT_VERSION-2026-027` (`human_confirmed`, `approved_by_id = Cesar`, `confirms_instance_id = -026`) | `E2-RPAR-20260831` | `e10fc3a969e22cea7396286e1babb15f56637168314318af3f5ed63af57abe30` | **ACTIVE** |
| **E3-A** — base canónica CLEAN | `ARTIFACT_VERSION-2026-028` (`agent_proposed`, `mission_control_ui`) | `ARTIFACT_VERSION-2026-029` (`human_confirmed`, `approved_by_id = Cesar`, `confirms_instance_id = -028`) | `E3A-CLEANBASE-20260831` | `46758dfa79fa340eb075230831f2867e813d103ddb7ff316e553725a7de542e2` | **ACTIVE** |

Audit trail: eventos `layer9_decision_recorded` `entry_id` `be29ee53…` → `568b5e3a…` →
`982f888c…` → `21d377a8…`, cadena de hash continua (`prev_entry_hash` == `entry_hash` anterior),
`side_effects_applied = false`. Detalle en `F9_HUMAN_DECISION.md`.

```
E2_READY  = YES        E2_GATE_SIGNED  = YES
E3A_READY = YES        E3A_GATE_SIGNED = YES

R2_READY_TO_RESUME       = NO
PILOT_EXECUTION-2026-035  = HOLD
LLM_CALLS                 = 0
PRODUCTION_ENABLEMENT     = BLOCKED
```

Esta corrida **no creó ninguna decisión**.

---

## 12. Integridad / no hand-edit

**Origen antes y después de la corrida final — sin cambios:**

| item | pre | post | |
|---|---|---|---|
| HEAD | `0e1e88a8751ebd84…` | `0e1e88a8751ebd84…` | ✅ MATCH |
| `decisions_v2.jsonl` sha256 | `e6d93354…` (263 líneas) | `e6d93354…` (263) | ✅ MATCH |
| `factory_audit.jsonl` sha256 | `bb694027…` (101097 líneas) | `bb694027…` (101097) | ✅ MATCH |
| `canonical_store` (árbol) | `71a711e4…` | `71a711e4…` | ✅ MATCH |
| `graph_store` (árbol) | `3c1975f3…` | `3c1975f3…` | ✅ MATCH |
| `git status` count | 85 | 85 | ✅ |
| tags | 18 (15 `reconc-*`) | 18 (15 `reconc-*`) | ✅ sin mover |
| `reconc-arc-closure` / `reconc-acceptance-v1` | `56bd36a` / `0e1e88a` | idem | ✅ |

**Ledger sin hand-edit** (heredado de F4/F9): las únicas líneas añadidas desde el baseline del
arco (`1b0c7cf8…`, 259 líneas) son las 4 de E1 (pre-F0) + 4 de E2/E3-A (F9), **todas
append-only escritas por el servicio Mission Control** (`git diff HEAD` = 0 borradas / 8 añadidas).

Todo el trabajo de esta corrida ocurrió en `/tmp/final_human_review/`.
`GOVERNANCE_STATE_GIT_REPRODUCIBLE = YES`.

---

## 13. Limitaciones y carry-forward NO cerrados

**No se esconden ni se declaran corregidos.**

| # | ítem | estado |
|---|---|---|
| 1 | **4 tests de hardening stale** (`test_h4_graph_snapshot` ·1, `test_h5f_hardening` ·1, `test_h7_coverage_governance` ·2) — baseline de fingerprint hardcodeada `88f15b69`/`fdc29721`/`b5196a71`. F5 §5 los dejó listados para corrección mecánica autorizada por Capa 9 (mismo tipo que `test_extraction_adequacy.py:214`). **Todavía fallan.** El valor que producen == baseline F5, así que la corrección es sólo actualizar la constante. | **ABIERTO** — requiere autorización de Capa 9 |
| 2 | **Bug del generador de IDs** `decision_store_v2.next_instance_id:189` — acuña `max()` del JSONL revertible, no del audit trail append-only. Los IDs `AV-2026-026..029` de E2/E3-A **colisionan** con entradas sólo-audit-trail del 2026-08-31 (otros artefactos; distinguibles por `decision_date`/`decision_ref`/`target_set_hash`/`entry_id`). **NO corregido** — sigue como carry-forward; el ledger no se reescribe. | **ABIERTO** — fase/decisión propia |
| 3 | **`ARTIFACT_VERSION-2026-024..028` (2026-08-31) `NO_RECONCILIABLE`** — artefactos no identificables desde el audit trail (F4 §2). | **ABIERTO** — requiere aceptación explícita de Capa 9 |
| 4 | **Escenario D del R-PAR / RW-0003** (SAT) `SKIPPED_NO_STORE` — `rw0003_store` no disponible en gobernanza (`CT-WP-D-REAL` / `D-4-H9`). Es capacidad nueva, no paridad; no condicionó E2/E3-A. | **ABIERTO** — para habilitar: `rw0003_store.status = AVAILABLE` + store gobernado |
| 5 | **P4 — persistencia del ledger en git** — las 4 líneas de servicio de `decisions_v2.jsonl` (E1-3 + E1_ACCEPTANCE; y ahora E2/E3-A) siguen **sin commitear** (working tree del origen). | **ABIERTO** — con OK explícito de Capa 9; nunca hand-edit |
| 6 | **Out-of-scope pre-sesión** — `remediation_directive.py` (+127), `test_remediation_directive.py` (+123), `test_r4_t1_1v2_cold_chain_validation.py`, `test_release_decision_coverage.py` (+10): cambios de sesiones previas (Causa B), **declarados en F0 §2**, **ninguna fase del arco los commitea**. Causan 6 fallas en el full suite del clon. | **ABIERTO** — decisión de Capa 9 aparte; congelados como patches en `F0_diffs/` |
| 7 | **D5-D2 / revisión realmente independiente** — el corpus técnico held-out necesita un autor independiente (Maria Torres ≠ Cesar) para `FINAL_QUALIFICATION` y `reportable_range != SYNTHETIC_ONLY`. Ya `DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT`. | **ABIERTO** — requerido para FINAL_QUALIFICATION |

---

## 14. Qué está aprobado y qué NO

### Aprobado / demostrado

- Los cambios de código F1/F2-r1/F3 están en el HEAD final y son los que producen el
  comportamiento correcto.
- La base (canonical + graph) es **reproducible desde cero** con sólo los 6 PDF + manifest,
  determinista, con RW-0012 limpio.
- Los fingerprints F5 (`3fcb3ae8` / `2fdda0e2` / `235f724a` / `693fc746`) y los counts 342/90/25
  se reproducen exactamente; R-PAR A/B/C byte-idéntico a `F6_hashes.json`.
- **E2 y E3-A están firmados** por Capa 9 mediante el mecanismo gobernado (propose→confirm,
  `Cesar`, `ACTIVE`), sin hand-edit del ledger ni del audit trail.
- `E2_READY = YES`, `E3A_READY = YES`.

### NO aprobado / NO habilitado por esta corrida

- **NO** se declara `FULL_SUITE_GREEN` (32 failures: 4 stale + 22 ambientales + 6 out-of-scope).
- **NO** se corrige el bug del generador de IDs — sigue carry-forward.
- **NO** se corrigen los 4 tests de hardening stale.
- `R2_READY_TO_RESUME = NO` · `PILOT_EXECUTION-2026-035 = HOLD` · `LLM_CALLS = 0` ·
  `PRODUCTION_ENABLEMENT = BLOCKED`.
- **NO** `FINAL_QUALIFICATION` — pendiente D5-D2 con autor independiente.
- **NO** liberación de lote, **NO** cierre de CAPA, **NO** declaración de cumplimiento.

---

## 15. Conclusión para revisión humana

La reconciliación F0-F9 **reproduce objetivamente**, desde un clon limpio con sólo los 6 PDF del
corpus, todos los resultados aprobados: extractor 8/8, RW-0012 8 secc/258 claims, stores
deterministas == manifest, targeted 124, fingerprints F5 exactos, R-PAR A/B/C byte-idéntico a
`F6_hashes.json`, 0 rutas efímeras, egress 0, gate humano intacto. **No se detectó ninguna
regresión nueva** (`NEW_REGRESSIONS = 0`); las 32 fallas del full suite son 4 stale ya
registradas en F5 + 28 dependencias de entorno/out-of-scope no atribuibles al arco. Las firmas
humanas de E2 y E3-A están presentes y son verificables en el mecanismo gobernado, sin hand-edit.

Quedan **7 follow-ups abiertos** (§13), todos conocidos y documentados; el nº 1 (tests stale) y
el nº 2 (generador de IDs) son los más relevantes para cerrar antes de `FINAL_QUALIFICATION`.

**`FINAL_HUMAN_REVIEW_RECOMMENDATION = ACCEPT_WITH_FOLLOW_UP`.**

---

## 16. Anexo — comandos, commits, tags y hashes

### Comandos ejecutados (clon `/tmp/final_human_review/clone`, `PYTHONPATH=.`, venv 3.11.15)

```
git clone --no-local /home/cmay/ivr-ia /tmp/final_human_review/clone
git checkout reconc-acceptance-v1
# 6 PDF -> GMPAI/source/Rockwell/  (sha256 verificado vs VALIDATION_BASELINE_MANIFEST.pdf_map)
PYTHONHASHSEED=random  python factory/scripts/ops/materialize_stores.py --runs 3 --baseline-manifest docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json
                        python factory/scripts/ops/materialize_stores.py --apply
PYTHONPATH=. python docs_plan/reconc/F1_measure.py
pytest -q factory/tests/test_document_structure_extractor.py
pytest -q factory/tests/test_completeness_rules_v1_2.py factory/tests/test_technical_findings.py \
          factory/tests/test_run_fingerprint.py factory/tests/test_wp_e_measurement_independence.py \
          factory/tests/test_extraction_adequacy.py
# run_v2_pipeline(RW-6) x2 (ENFORCE) + 1 variante OBSERVE  -> audit_summary/audit_metadata.json
python factory/scripts/ops/r_par_delta_v1_v2.py --check
python factory/scripts/ops/r_par_delta_v1_v2.py   (x2)
pytest -q factory/tests/  (full, 8 sub-lotes por rango de nombre)
```

### Tags / commits

```
FINAL_ACCEPTANCE_TAG    = reconc-acceptance-v1
FINAL_ACCEPTANCE_COMMIT = 0e1e88a
ARC_CODE_CLOSURE_TAG    = reconc-arc-closure
ARC_CODE_CLOSURE_COMMIT = 56bd36a
cambios de código        = F1 09656e1 · F2-r1 4c64a05 · F3 484abea
```

### Hashes de referencia

```
PDF        RW-0005 56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb
           RW-0006 d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8
           RW-0009 2edb00a3eae471926f41f6d6b707874e52c78c29ebc583ad6da6c4cf961009eb
           RW-0011 13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53
           RW-0012 de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71
           RW-0014 8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb
canonical  RW-0005 8e7196a007f02274…  RW-0006 7da433b41c111d29…  RW-0009 4922562de36feaa7…
LOGICAL    RW-0011 1f2676308d557f7d…  RW-0012 155eb281df9105e2…  RW-0014 a180fdc1c5d0be28…
graph LOGICAL   3ead71532cf44fab4eea71867ef572b96aab3f69bfc0524739ea7b4e69224081
ground truth     2f7a00dc9aad66bca7ee7195f9a19518fa0228bb0e5430a43fef772ab0b28f39
INPUT_CONFIG     3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668
GRAPH_SNAPSHOT   2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620
FINDINGS ENFORCE 235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23
FINDINGS OBSERVE 693fc746e645b168386537c7dbce8c6394b582fb6c031ebf62e44189b748a368
R-PAR      findings_A/B b43b548b63e90014e7e9fc3b8cc9f98d8a24c2699a5e1711069336efc6cd4558
           findings_C   e0dd292483ac7546bff47da705c4f07889ad258af3209186ce24379172bdba0d
           findings_D   2ba3a8bd02ace0acefc0069edd7f0a1d2470d806a6e3532cb69dcf921aa11f10
ledger (origen)  e6d9335405c60680bfe11c561458a7a41fcaaee87526b24a5eb3fc9e0f0dceed  (263 líneas; baseline del arco 1b0c7cf8…, 259)
audit trail (origen)  bb694027ba22fe29cee0976e3a745e954effbb60903cea914a61aa5c257749e5  (101097 líneas)
E2  target_set_hash    e10fc3a969e22cea7396286e1babb15f56637168314318af3f5ed63af57abe30
E3-A target_set_hash   46758dfa79fa340eb075230831f2867e813d103ddb7ff316e553725a7de542e2
```

### Bloque de cierre

```
FINAL_ACCEPTANCE_TAG              = reconc-acceptance-v1
FINAL_ACCEPTANCE_COMMIT           = 0e1e88a
CODE_CHANGES_PRESENT              = YES
CLEAN_REBUILD                     = PASS
TARGETED_RESULT                   = 124 passed / 0 failed
RPAR_ABC_REPRODUCIBLE            = YES
NEW_REGRESSIONS                   = 0
KNOWN_STALE_HARDENING_FAILURES    = 4
E2_GATE_SIGNED                    = YES
E3A_GATE_SIGNED                   = YES
R2_READY_TO_RESUME                = NO
PILOT_035                         = HOLD
PRODUCTION_ENABLEMENT             = BLOCKED

FINAL_HUMAN_REVIEW_RECOMMENDATION = ACCEPT_WITH_FOLLOW_UP
```

*Corrida READ-ONLY. Sin fixes, sin commits, sin decisiones de gobernanza. Origen intacto. DETENIDO.*
