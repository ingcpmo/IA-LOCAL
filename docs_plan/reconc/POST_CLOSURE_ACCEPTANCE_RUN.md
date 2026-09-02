# POST-CLOSURE ACCEPTANCE RUN — READ ONLY

**Fecha:** 2026-09-02 · **Modo:** READ-ONLY, sin nuevas decisiones, sin fixes, sin commits.
**Fuente única:** tag `reconc-arc-closure`.
**Clon de aceptación:** `/tmp/arc_acceptance/clone` (separado del origen).
**Intérprete:** `/home/cmay/ivr-ia/.venv/bin/python` (Python 3.11.15) con `PYTHONPATH` = clon.
**Objetivo:** demostrar desde cero que el código del cierre F0-F9 incorpora los cambios ejecutados
y reproduce los resultados aprobados. **No se reabrió ninguna fase.**

---

## 1–3 · Clon limpio + checkout + verificación de HEAD

```
git clone --no-local /home/cmay/ivr-ia /tmp/arc_acceptance/clone
git checkout reconc-arc-closure
git rev-parse HEAD  ->  56bd36a1d9fba4a0968d5c8a7ff88e5744361189
git rev-parse --short HEAD  ->  56bd36a       ESPERADO = 56bd36a   ✅ MATCH
```

---

## 4 · Los cambios de código están contenidos en el tag (git + sha256)

Todos los ficheros presentes en `reconc-arc-closure`, con el commit `reconc(...)` que introdujo
el cambio y su sha256 actual en el clon:

| fichero | sha256 (clon @ 56bd36a) | commit de introducción del cambio | coincide con reporte de fase |
|---|---|---|---|
| `factory/regulatory/document_structure_extractor.py` | `56236c1ace2800ed32c5be9712a0761a2084c969cb6527954c6f64104552a11a` | `09656e1` — **F1** (`\.?` en heading/TOC regex) | F1: extractor WT sha256 `56236c1ace…` ✅ |
| `factory/regulatory/graph/build.py` | `64d9e7d90a543879e06022a8fd4f8865af0bc9ea8e4a74d64abf67c9bde0a5c5` | `4c64a05` — **F2-r1** (3× `sorted()`: `_link_chain` L244, `_link_to_tests` L365, `_link_contradictions` L504) | F2-r1: fix de determinismo del grafo ✅ |
| `factory/scripts/ops/materialize_stores.py` | `6b3ab58301fdbf4a897954b5212226a422c73b3662ed7bf3bd46545ed80ae321` | añadido `8c4e7ab` (F2), reescrito `4c64a05` (F2-r1) | F2-r1: `_PDF_MAP` verificado por sha256, `--runs`/`--apply` ✅ |
| `factory/scripts/ops/r_par_delta_v1_v2.py` | `a1571739f91035c13f6412b399ab447816e06f52fd515f3f04b31b393313a8c2` | `484abea` — **F3** (sin rutas efímeras, `_resolve_rw0003_store`, `--check`) | F3: `_RW0003_DET` eliminado ✅ |
| `factory/tests/test_document_structure_extractor.py` | `498f79b58c05dbd6f73f9965ce30b05d49787c6cab6038c6826a82a4840179a8` | `09656e1` — **F1** (+3 tests: período, guarda de subsección, regresión 8 secciones) | F1 ✅ |
| `factory/tests/test_extraction_adequacy.py` | `e24b9b3451ed727062ec1b7b9895804ae21407d76828af915293cba1ebfbcc51` | `4c64a05` — **F2-r1** (`:214` `(342,90,26)→(342,90,25)`) | F2-r1 ✅ |
| `factory/tests/test_run_fingerprint.py` | `ab6777696ce817bd9f820960823dbddd8cc5d404e0eff8937ba2a5bc59f7e0e1` | `24549a3` (pre-reconc); F5 estableció que **pasa sin cambios** sobre la nueva baseline | F5 §6 ✅ |

`git show 4c64a05 -- factory/regulatory/graph/build.py` muestra las 3 líneas `+ ... sorted(...)`.

**`CODE_CHANGES_PRESENT = YES`.**

---

## 5 · Solo los 6 PDF del corpus, con SHA256 verificado

Copiados a `clon/GMPAI/source/Rockwell/` (primer path de búsqueda de `materialize_stores.py`).
**No se copió `canonical_store` ni `graph_store` del origen.**

| doc | PDF | SHA256 | vs `_PDF_MAP` / manifest |
|---|---|---|---|
| RW-0005 | `215115305 SCADA-PCS Misc PLC System FS_v1.2.pdf` | `56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb` | ✅ |
| RW-0006 | `215115305 SCADA-PCS Misc PLC System URS v2.1.pdf` | `d9e24467a66d52fb1a641b6de901ceff1dcdaf66af1ae80cb94a433c40c939c8` | ✅ |
| RW-0009 | `215115305-T-041 SAT3 Completed.pdf` | `2edb00a3eae471926f41f6d6b707874e52c78c29ebc583ad6da6c4cf961009eb` | ✅ |
| RW-0011 | `MCCPDC EMS Control Block Narrative revB.pdf` | `13bc6f50c4cee50211d6877249cbacd19e797b0cb93e58e3579c037be68fbf53` | ✅ |
| RW-0012 | `MCCPDC PCS Signal Interface Control Block Narrative.pdf` | `de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71` | ✅ |
| RW-0014 | `MCCPDC WFI Control Block Narrative revB.pdf` | `8a67414d90ba28c8ee3cf9939d3be0d670ed7c8794a61f049b07ebe07ebf4ccb` | ✅ |

`ALL_6_PDF_SHA256_MATCH = True`. Clon sin `canonical_store/` ni `graph_store/` antes del paso 6.

---

## 6 · Regeneración de stores desde cero (procedimiento F2-r1)

```
PYTHONHASHSEED=random  materialize_stores.py --runs 3 --baseline-manifest VALIDATION_BASELINE_MANIFEST.json
  base = /tmp/arc_acceptance/clone/GMPAI/source/Rockwell   (PDFs del clon, NO del origen)
  DETERMINISTA canonical: True   graph: True
```

| doc | LOGICAL (clon, 3 corridas) | sections | claims | vs manifest |
|---|---|---|---|---|
| RW-0005 | `8e7196a007f02274…` | 8 | 1409 | ✅ True |
| RW-0006 | `7da433b41c111d29…` | 8 | 515 | ✅ True |
| RW-0009 | `4922562de36feaa7…` | 0 | 62 | ✅ True |
| RW-0011 | `1f2676308d557f7d…` | 8 | 317 | ✅ True |
| **RW-0012** | `155eb281df9105e2…` | **8** | **258** | ✅ True |
| RW-0014 | `a180fdc1c5d0be28…` | 8 | 369 | ✅ True |
| graph `RW-TECH-REAL.sqlite3` | `3ead71532cf44fab` | — | nodes 3000 / edges 1330 | ✅ True |

```
canonical deterministic = TRUE   (3 corridas idénticas)
graph deterministic     = TRUE
logical hashes == VALIDATION_BASELINE_MANIFEST  (canonical 6/6 True, graph True)
RW-0012 = 8 secciones / 258 claims           ✅
```

`CLEAN_REBUILD = PASS`. (`--apply` posterior materializó los stores del clon in-situ para los
pasos 7 y 11; el origen NO se tocó.)

---

## 7 · Targeted versionado de F2-r1

```
pytest  test_completeness_rules_v1_2.py  test_technical_findings.py  test_run_fingerprint.py
        test_wp_e_measurement_independence.py  test_extraction_adequacy.py
->  124 passed, 24 warnings in 27.85s
```

`TARGETED = 124 passed` ✅

---

## 8 · `test_document_structure_extractor.py`

```
->  11 passed, 1 skipped in 2.51s
```
✅ (esperado 11 passed, 1 skipped)

---

## 9 · `test_run_fingerprint.py`

```
->  23 passed in 2.60s
```
✅ (esperado 23 passed)

---

## 10 · `r_par_delta_v1_v2.py --check`

```
SELFCHECK OK: sin rutas efimeras hardcodeadas
exit 0
```
✅ 0 rutas efímeras.

---

## 11 · R-PAR A/B/C — dos corridas

| métrica | RUN 1 | RUN 2 | esperado |
|---|---|---|---|
| `A_n` | 457 | 457 | 457 ✅ |
| `B_n` | 457 | 457 | 457 ✅ |
| `C_n` | 458 | 458 | 458 ✅ |
| `determinism {A,B,C}` | `{true,true,true}` | `{true,true,true}` | true ✅ |
| `AB_only_A` | 0 | 0 | 0 ✅ |
| `AB_only_B` | 0 | 0 | 0 ✅ |
| `BC_only_C` | 1 | 1 | 1 ✅ |
| `BC_band_changed` | 0 | 0 | — |
| `BC_refers_to` (B→C) | 0 → 201 | 0 → 201 | — |
| `document_egress_bytes` (A/B/C) | 0 / 0 / 0 | 0 / 0 / 0 | 0 ✅ |
| `human_gate_intact` (A/B/C) | True / True / True | True / True / True | true ✅ |
| RUN1 == RUN2 (estructura, sin volátiles) | **True** | | |

Hashes de salida (byte) vs `F6_hashes.json` **committeado**:

| fichero | sha256 (acceptance run) | F6_hashes.json | |
|---|---|---|---|
| `findings_A.json` | `b43b548b63e90014e7e9fc3b8cc9f98d8a24c2699a5e1711069336efc6cd4558` | `b43b548b…` | ✅ idéntico |
| `findings_B.json` | `b43b548b63e90014e7e9fc3b8cc9f98d8a24c2699a5e1711069336efc6cd4558` | `b43b548b…` | ✅ idéntico (== A) |
| `findings_C.json` | `e0dd292483ac7546bff47da705c4f07889ad258af3209186ce24379172bdba0d` | `e0dd2924…` | ✅ idéntico |

`RPAR_ABC_REPRODUCIBLE = YES`.

---

## 12 · Escenario D

`D_status = SKIPPED_NO_STORE` en ambas corridas. **No se evaluó D como requisito** (corrección 5
del plan: `E2_READY`/`E3A_READY` dependen de A/B/C, no de D).

---

## 13 · Full pytest — INVENTARIO (sin corregir nada)

3106 tests colectados. Ejecutado en 6 sub-lotes (el suite completo se mata en background cerca
del final por límite del entorno; los sub-lotes son estables):

| sub-lote | passed | failed | skipped |
|---|---:|---:|---:|
| `test_[a-e]*` | 888 | 8 | 5 (+1 xfail) |
| `test_[f-h]*` | 637 | 12 | 48 |
| `test_[i-r]*` | 935 | 10 | 36 |
| `test_s*` | 218 | 2 | 6 |
| `test_t*` | 62 | 0 | 0 |
| `test_[u-z]*` | 238 | 0 | 0 |
| **TOTAL** | **2978** | **32** | **95 (+1 xfail)** |

### 13.A · `EXPECTED_STALE_HARDENING_FAILURE` = 4

Los 3 ficheros que F5 §5 dejó **listados para corrección mecánica autorizada de Capa 9** (baseline
de fingerprint hardcodeada pre-de-contaminación de RW-0012). El valor **producido** por el clon
limpio == la baseline F5; el test falla sólo porque compara contra el hash viejo:

| test | valor actual (clon) | valor hardcodeado (stale) |
|---|---|---|
| `test_h4_graph_snapshot.py::test_e2e_findings_fingerprint_matches_post_h1h2h3_baseline` | `693fc746e645b168…` (= F5 OBSERVE) | `b5196a7177c92a91…` |
| `test_h5f_hardening.py::test_h5f_does_not_move_findings_or_graph_fingerprint` | `693fc746e645b168…` | `b5196a7177c92a91…` |
| `test_h7_coverage_governance.py::test_e2e_observe_does_not_move_findings_or_graph` | `693fc746e645b168…` | `b5196a7177c92a91…` |
| `test_h7_coverage_governance.py::test_e2e_enforce_is_the_governed_production_path_post_d2` | `235f724a738ce783…` (= F5 ENFORCE) | `fdc29721e9566dfe…` |

Estos 4 confirman positivamente el rebaseline de F5: el clon limpio genera exactamente
`693fc746…` (OBSERVE) y `235f724a…` (ENFORCE).

### 13.B · `NEW_REGRESSION` = 0

Las otras 28 fallas **no tocan** ninguno de los 4 módulos cambiados por el arco. Todas se
explican por el diseño del experimento (clon limpio, sin runtime, solo 6 PDFs):

| causa | tests | nº |
|---|---|---|
| **Falta `factory/audit/factory_audit.jsonl`** (untracked; NO se copió, por instrucción). Los tests esperan un fork/ruptura en la cadena real; sin fichero la cadena lee `VERIFIED` | `test_audit_fork_governance` (f01/f02/f04/f08), `test_gate0_extended::…real_chain…`, `test_g7_audit_exception_readiness::…store_it_was_asked_about`, `test_status_risks::…fork_from_corruption`, `test_release_decision_coverage::…production_chain` | 8 |
| **Falta `factory/regulatory/source_currency_log.jsonl`** (untracked) | `test_g3_reverification_launcher` (6 casos) | 6 |
| **App no escribe `factory/logs/access.jsonl`** (sin servidor) | `test_access_log` (4 casos) | 4 |
| **Sin API HTTP corriendo** (health/deployment/423) | `test_mission_evidence_readers::test_deployment_exists_and_health`, `test_release_decision_coverage::test_endpoint_returns_423_not_409` | 2 |
| **Parche PRE-EXISTENTE fuera de alcance** (`remediation_directive.py` +127 líneas "Causa B / fcntl supersede", declarado en F0 §2, **nunca commiteado por ninguna fase**; el clon no lo tiene → `TypeError: … unexpected keyword 'supersedes_directive_id'`) | `test_remediation_directive_endpoint` (4), `test_remediation_package_service::…superseded_directive`, `test_release_decision_coverage::test_an_unbacked_fork_blocks_and_is_named` | 6 |
| **Workspace de clon en detached HEAD** | `test_runtime_identity::TestFailClosedGuard::test_assert_passes_on_a_reproducible_runtime` (`workspace presente=False`) | 1 |
| **Config v2 completa ausente** | `test_shadow_and_cutover::test_shadow_run_v2_no_effects_and_reversible` | 1 |

Ninguna es atribuible a `document_structure_extractor.py`, `graph/build.py`,
`materialize_stores.py` ni `r_par_delta_v1_v2.py`. El targeted (124), extractor (11+1s),
fingerprint (23) y R-PAR A/B/C pasan y reproducen la baseline committeada exactamente.

`NEW_REGRESSIONS = 0` · `KNOWN_STALE_TEST_FAILURES = 4`.

---

## 14 · El repo ORIGEN no cambió

Comparado con el snapshot tomado antes de la prueba, tras todo el acceptance run:

| item | pre | post | |
|---|---|---|---|
| HEAD | `56bd36a1d9fba4…` | `56bd36a1d9fba4…` | ✅ MATCH |
| rama | `fix/clon-local-validacion` | idem | ✅ |
| `decisions_v2.jsonl` sha256 | `e6d93354…` (263 líneas) | `e6d93354…` (263) | ✅ MATCH |
| `factory_audit.jsonl` sha256 | `bb694027…` (101097 líneas) | `bb694027…` (101097) | ✅ MATCH |
| `canonical_store` (árbol) | `71a711e4…` | `71a711e4…` | ✅ MATCH |
| `graph_store` (árbol) | `3c1975f3…` | `3c1975f3…` | ✅ MATCH |
| `git status` count | 85 | 85 | ✅ |
| tags | 17 (14 `reconc-*`) | 17 (14 `reconc-*`) | ✅ sin mover |
| reflog top | `56bd36a … commit: reporte de cierre` | idem | ✅ |

Todo el trabajo (clon, PDFs, regeneración de stores, backups, `_r_par/`, reportes) ocurrió en
`/tmp/arc_acceptance/`. `GOVERNANCE_STATE_GIT_REPRODUCIBLE = YES`.

---

## CONCLUSIÓN

```
FINAL_TAG                          = reconc-arc-closure
FINAL_COMMIT                       = 56bd36a
CODE_CHANGES_PRESENT              = YES
CLEAN_REBUILD                      = PASS
TARGETED                           = 124 passed
RPAR_ABC_REPRODUCIBLE             = YES   (A=457, B=457, C=458; RUN1==RUN2; findings_A/B/C sha256 == F6_hashes.json)
NEW_REGRESSIONS                    = 0
KNOWN_STALE_TEST_FAILURES         = 4    (test_h4_graph_snapshot ·1, test_h5f_hardening ·1, test_h7_coverage_governance ·2 — F5 §5, valores producidos == baseline F5)
GOVERNANCE_STATE_GIT_REPRODUCIBLE = YES
```

**El código del tag `reconc-arc-closure` incorpora los cambios ejecutados en F0-F9 y reproduce,
desde un clon limpio con sólo los 6 PDF, los resultados aprobados**: stores deterministas con
logical hashes == manifest, RW-0012 = 8 secc / 258 claims, targeted 124, R-PAR A/B/C byte-idéntico
a `F6_hashes.json`, 0 rutas efímeras, egress 0, gate humano intacto. Las únicas fallas del suite
completo son las 4 stale de hardening ya registradas en F5 (pendientes de corrección mecánica
autorizada) y 28 fallas ambientales del clon aislado (sin runtime / sin API / parche pre-existente
fuera de alcance) — **ninguna regresión nueva**.

*No se corrigió nada. No se hizo commit. Origen intacto. DETENIDO.*
