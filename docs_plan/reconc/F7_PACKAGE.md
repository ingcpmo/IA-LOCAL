# F7 — PAQUETE ACUMULADO PARA AUDITORÍA INDEPENDIENTE (Devin)

**Plan de reconciliación v1.1 · FASE 7 · corrección 3.**
**Claude Code NO ejecuta la auditoría F7.** Este documento es la entrega: tags + manifest +
reportes por fase + verificación de coherencia pre-handoff. Devin re-verifica el
encadenamiento (read-only) y que ningún tag posterior invalidó uno previo.

**HEAD = `9930fc5` == `origin/fix/clon-local-validacion`.**

---

## 1. Mapa de tags del arco

| tag | commit | fase | PROPOSED_VERDICT | doc(s) de veredicto |
|---|---|---|---|---|
| `reconc-F0` | `3749569` | F0 — descubrir/congelar estado real | PASS | `BASELINE_PRE_REAL.md`, `F0_*` |
| `reconc-F1` | `09656e1` | F1 — extractor `\.?` (medición mecánica) | (superado por r1) | `F1_verdict.md` |
| `reconc-F1-r1` | `414557f` | **F1 — cierre corregido (ground truth humano-aprobado)** | **PASS** (aprobado Capa 9) | `F1_HUMAN_GROUND_TRUTH_REVIEW.md`, `F1_FINAL_CORRECTIVE_REPORT.md` |
| `reconc-F2` | `8c4e7ab` | F2 — materialización + doble hash | (PARTIAL → r1) | `F2_materialization_log.md`, `F2_HASH_DEFINITION.md` |
| `reconc-F2-r1` | `4c64a05` | **F2 — correctivo (5 problemas de la auditoría)** | **PASS** (aprobado Capa 9) | `F2_R1_CORRECTIVE_REPORT.md` |
| `reconc-F3` | `484abea` | F3 — `r_par_delta` sin rutas efímeras | PASS (aprobado Capa 9) | `F3_verdict.md`, `F3_script_diff.md` |
| `reconc-F4` | `6b34051` | F4 — governance/audit/ledger | PASS (aprobado Capa 9) | `F4_verdict.md` + `F4_*.md` |
| `reconc-F5` | `ab8a896` | F5 — rebaseline de fingerprints | PASS (aprobado Capa 9) | `F5_rebaseline.md` |
| `reconc-F6` | `9930fc5` | F6 — R-PAR completa | PASS (aprobado Capa 9) | `F6_R_PAR_DELTA_FINAL.md`, `F6_hashes.json` |

Cadena lineal, sin merges. `reconc-F1` y `reconc-F2` quedan como **histórico** (superados por
sus `-r1`); no se movieron.

---

## 2. Qué estableció cada fase (para el cruce F8)

| fase | resultado clave | evidencia reproducible |
|---|---|---|
| **F0** | HEAD real descubierto (`9096005`, no `6be0626`). Ledger 259 líneas (`1b0c7cf8`). Targeted real = 124. Working tree clasificado (patches + hashes). 022..025 en el ledger (servicio); 026..032 solo en audit trail. **STOP F0 no disparó** (sin commits de producto ocultos). | `F0_diffs/*.diff` aplican sobre `9096005` ; `F0_stores_manifest.json` ; `F0_ledger_state.md` |
| **F1** | Extractor `\.?` = **CORRECCIÓN** (HEAD-limpio 0/8 secciones en RW-0011/0012/0014 ; con-cambio 8/8 == ground truth **humano-aprobado por Capa 9**, `GROUND_TRUTH_SHA256 = 2f7a00dc…`). Guarda de subsección verificada. Tests 11/1s. | `PYTHONPATH=. python docs_plan/reconc/F1_measure.py` → PRE 0/8 / POST 8/8 ; `pytest -q factory/tests/test_document_structure_extractor.py` |
| **F2-r1** | Stores **regenerables y deterministas** (`materialize_stores.py --runs 3` → canonical + graph LOGICAL idénticos en 3 corridas `PYTHONHASHSEED=random`). **RW-0012 des-contaminado** (13 secc/595 claims → 8/258 ; causa: `b4b_runner._PDF_BY_DOC` mapea RW-0012→WFI). Graph 3342/1344 → **3000/1330**. `build.py` +3 `sorted()` (fix de determinismo, NO mueve `graph_snapshot`: sobre el store contaminado sigue dando `88f15b69`). Targeted **124**. `test_extraction_adequacy.py:214` `(342,90,26)→(342,90,25)` (el 26 era artefacto de la contaminación). Doble hash congelado ANTES de medir (`F2_HASH_DEFINITION.md`, `9ab7c2b`). | `PYTHONHASHSEED=random python materialize_stores.py --runs 3` ; targeted v1.2 (5 archivos) |
| **F3** | `r_par_delta_v1_v2.py` **sin rutas efímeras** (`_RW0003_DET` eliminado ; store RW-0003 desde el manifest = `NO_DISPONIBLE`). D → `SKIPPED_NO_STORE` (nunca aborta). A **fail-closed** contra el manifest (hash lógico por doc). `--check` (0 rutas efímeras) ; `--dry-run-abc`. | `python r_par_delta_v1_v2.py --check` (exit 0) ; `--dry-run-abc` (exit 0) |
| **F4** | **ID_COLLISION probado** (`ARTIFACT_VERSION-2026-022..025` emitidos 2×, `-024/-025` con `target_set_hash` distinto). Causa raíz: `decision_store_v2.next_instance_id:189` acuña `max()` del **JSONL revertible**, no del audit trail. Corrección **propuesta** (no aplicada). D5 clasificado. **D6 CERRADO** por contrato (`technical_completeness_rules.yaml` ∉ `ARTIFACT_CLASSES`). **D7 sin acción** (`AUDIT_EXCEPTION-2026-002` ACTIVE). D8: `E1_SIGNATURE_HISTORY.md` alineado (append-only). **0 hand-edits** (sha ledger `1b0c7cf8` sin cambio). | `grep audit trail 022..032` ; `sed -n '179,189p' decision_store_v2.py` ; `sha256sum decisions_v2.jsonl` |
| **F5** | NUEVA BASELINE HEAD `6b34051`: `INPUT_CONFIG 3fcb3ae8` · `GRAPH_SNAPSHOT 2fdda0e2` · `FINDINGS(ENFORCE) 235f724a` / `(OBSERVE) 693fc746`. Counts 342/90/25. Deterministas (r1==r2), **project-id-independientes**. 9 digests previos → HISTÓRICOS. `findings_fingerprint` = LÓGICO. `test_run_fingerprint.py` 23 passed. 3 tests de hardening con baseline stale → listados para Capa 9. | `run_v2_pipeline ×2` ; `pytest -q factory/tests/test_run_fingerprint.py` |
| **F6** | R-PAR: **A/B/C deterministas** (RUN1==RUN2 en los 3 fingerprints). **Clone-drift A↔B = 0** (`findings_A.json == findings_B.json` byte a byte, sha `b43b548b`). A/B == baseline ENFORCE F5. **B↔C** (H-10) = +1 `TEST_WITHOUT_REQUIREMENT` (RW-0009) + 201 `refers_to`, 0 cambios de banda. `document_egress_bytes=0`, `human_gate_intact=True`. D = `SKIPPED_NO_STORE` (no bloquea E2/E3-A, corrección 5). | `python r_par_delta_v1_v2.py` → `determinism {A,B,C}=True` ; `F6_hashes.json` |

---

## 3. Verificación de coherencia pre-handoff (READ-ONLY, en HEAD `9930fc5`)

Ningún tag posterior invalidó uno previo:

| chequeo | esperado | actual en HEAD |
|---|---|---|
| F1 ground truth | `GROUND_TRUTH_SHA256 = 2f7a00dc…` ; WT = 8 secc/doc | ✅ `2f7a00dc…` ; 8/8/8 |
| F3 selfcheck | `SELFCHECK OK` (0 rutas efímeras) | ✅ OK |
| F2-r1 materialización | `DETERMINISTA canonical:True graph:True` ; graph LOGICAL `3ead7153` | ✅ True/True ; `3ead71532cf44fab` |
| F2-r1 targeted | 124 passed | ✅ **124 passed** |
| F5 fingerprints | `3fcb3ae8` / `2fdda0e2` / `235f724a` (ENFORCE) | ✅ **idénticos** |
| F4 ledger | sha256 `1b0c7cf8…` sin cambio | ✅ `1b0c7cf82ed7…` |
| working tree | solo cambios pre-sesión (D5-D/v1.2 + 4 líneas servicio + out-of-scope de F0) | ✅ sin drift nuevo introducido por F0..F6 |

**No se dispara STOP de F7** (no hay incoherencia entre fases; el arco es lineal y cada
chequeo reproduce lo suyo en HEAD).

---

## 4. Ítems abiertos CONOCIDOS (no son incoherencias del arco)

| ítem | origen | disposición |
|---|---|---|
| **3 tests de hardening con fingerprint hardcodeado stale** (`test_h4_graph_snapshot`, `test_h5f_hardening`, `test_h7_coverage_governance`: `88f15b69` / `fdc29721` / `b5196a71`) | consecuencia de la de-contaminación de RW-0012 en F2-r1 (probado que NO lo causa `build.py`) | `F5_rebaseline.md` §5 + manifest: old→new. **Corrección mecánica autorizada por Capa 9** (mismo tipo que `test_extraction_adequacy.py:214` en F2-r1). Fuera del alcance editable de F5..F7. |
| **Corrección del generador de IDs** (`decision_store_v2.next_instance_id` debe usar audit trail ∪ JSONL, o contador monótono) | F4 §1 (ID_COLLISION) | Propuesta gobernada. Código de servicio → fase/decisión propia de Capa 9. El ledger NO se reescribe. |
| **Escenario D del R-PAR** (RW-0003 SAT) | F3/F6 — `rw0003_store = NO_DISPONIBLE` (gobernanza CT-WP-D-REAL / D-4-H9) | Capacidad nueva, NO paridad (corrección 5). Para habilitar: `rw0003_store.status = AVAILABLE` + `path` a un store gobernado. NO bloquea E2/E3-A. |
| **P4 — persistir en git las 4 líneas de servicio de `decisions_v2.jsonl`** (E1-3 + E1_ACCEPTANCE, Mission Control) | F0/E1 | Con OK explícito de Capa 9. Nunca hand-edit. |
| **Out-of-scope pre-sesión** (`remediation_directive.py`, `test_r4_t1_1v2_cold_chain_validation.py`, `test_release_decision_coverage.py`) | F0 `BASELINE_PRE_REAL.md` — CODIGO_NO_GOBERNADO pre-existente | Congelados como patches en `F0_diffs/`. Ninguna fase del arco los commitea. Decisión propia de Capa 9. |

---

## 5. Manifest

`docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json` (actualizado hasta F5):
- `code_hashes`, `runtime`, `pdf_map` (6 sha256 verificados), `rw0003_store` (`NO_DISPONIBLE`)
- `canonical_store_manifest` / `graph_store_manifest` (REGENERABLE, `deterministic_over_3_runs: true`, logical hashes + counts)
- `corpus_run` / `pilot_run` / 4 `.docx` (EVIDENCIA_CONGELADA, byte + logical_text)
- `fingerprints.baseline` (F5, HEAD `6b34051`, ENFORCE + OBSERVE) + `historical_invalid_for_head_6b34051` (9) + `stale_test_baselines_for_capa9_authorization` (6 entradas)
- `graph_build_fix` (F2-r1: 3× `sorted()`, prueba de no-alteración de topología)
- `b4b_runner_bug` (RW-0012 → WFI)

`F6_hashes.json`: hashes de las salidas de `docs_plan/_r_par/` (gitignored).

---

## 6. Para Devin (F7 — auditoría acumulativa, read-only)

Re-verificar el **encadenamiento** desde clon limpio:

1. `git checkout reconc-F1-r1` → `python docs_plan/reconc/F1_measure.py` → PRE 0/8 / POST 8/8, `GROUND_TRUTH_SHA256 = 2f7a00dc…`.
2. `git checkout reconc-F2-r1` → `PYTHONHASHSEED=random python factory/scripts/ops/materialize_stores.py --runs 3` → `DETERMINISTA canonical:True graph:True` ; targeted v1.2 = 124.
3. `git checkout reconc-F3` → `python factory/scripts/ops/r_par_delta_v1_v2.py --check` (exit 0) + `--dry-run-abc` (exit 0).
4. `git checkout reconc-F4` → `sha256sum decisions_v2.jsonl` = `1b0c7cf8…` ; `grep audit trail 022..032` → 022..025 ×2 ; `sed decision_store_v2.py:179-189`.
5. `git checkout reconc-F5` → `run_v2_pipeline ×2` → `3fcb3ae8` / `2fdda0e2` / `235f724a` ; `pytest test_run_fingerprint.py` = 23.
6. `git checkout reconc-F6` (== HEAD) → `python r_par_delta_v1_v2.py` → `determinism {A,B,C}=True`, `AB_only_A/B=0`, `BC_only_C=1`, `egress=0`.
7. Confirmar que **ejecutar el paso 6 no invalida los pasos 1-5** (coherencia del conjunto).

**Matriz de veredicto:** Documento 3.
- **PASS** = cada tag reproduce lo suyo y el manifest final es coherente F0→F6.
- **STOP** = incoherencia entre fases (un cambio tardío rompió una fase previa).

Claude Code afirma (pre-handoff, §3): **coherente**. Devin confirma o refuta.

---

## REPORTE FORMATO OBLIGATORIO — F7

```
FASE            = F7 (entrega del paquete acumulado ; auditoría = Devin)
PRE_COMMIT      = 9930fc5  (reconc-F6)
POST_COMMIT     = <commit reconc-F7>
WORKTREE_PRE    = igual que reconc-F6
WORKTREE_POST   = + docs_plan/reconc/F7_PACKAGE.md
DIFF            = docs_plan/reconc/F7_PACKAGE.md (nuevo)
COMMANDS        = git tag/rev-list (inventario) ; verificación de coherencia §3 (F1_measure, materialize
                  --runs 3, targeted, run_v2 x1, sha256 ledger) — todo READ-ONLY, sin LLM
TEST_RESULTS    = coherencia §3: 7/7 chequeos OK en HEAD 9930fc5
INPUT_HASHES    = ver VALIDATION_BASELINE_MANIFEST.json + F6_hashes.json
OUTPUT_HASHES   = n/a (F7 no produce artefactos ejecutables)
FINGERPRINTS    = HEAD reproduce la baseline F5 (3fcb3ae8 / 2fdda0e2 / 235f724a)
ARTIFACTS       = docs_plan/reconc/F7_PACKAGE.md ; + todo el arco reconc-F0..F6 (tags)
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. La verificación de coherencia §3 es diligencia de entrega, no la
                  auditoría F7 (que la hace Devin).
EXPECTED_VS_ACTUAL:
  EXPECTED: paquete acumulado entregado ; cada tag reproduce lo suyo ; sin incoherencia entre fases.
  ACTUAL:   9 tags (F0..F6 + r1) en cadena lineal ; §3 = 7/7 chequeos OK en HEAD ; 5 ítems abiertos
            conocidos documentados (ninguno es incoherencia del arco) ; manifest coherente.
PROPOSED_VERDICT = PASS  (a confirmar por Devin: auditoría acumulativa read-only del encadenamiento)
```
