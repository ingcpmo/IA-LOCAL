# F6 — R-PAR DELTA V1 ↔ V2 — REPORTE FINAL

**Plan de reconciliación v1.1 · FASE 6 · cierra D1 en ejecución · precondición F1..F5 PASS ✅.**
Script reparado (F3) · stores limpios (F2-r1) · baseline (F5) · `docs_plan/_r_par/` regenerado (gitignored).
**Sin código de producto, sin LLM.**

---

## Declaración previa (corrección 5) — fijada ANTES de ejecutar

- El **núcleo** para **E2 (paridad v1↔v2)** y **E3-A (base limpia)** son los escenarios **A/B/C**.
  - **A↔B** = efecto de re-extracción limpia (**clone-drift**).
  - **B↔C** = efecto real de **H-10**.
- El **escenario D** (H-10 + SAT RW-0003) es **CAPACIDAD NUEVA, NO paridad**.
  `E2_READY` / `E3A_READY` dependen de **A/B/C = PASS, NO de D**. Si D queda `SKIPPED_NO_STORE`,
  F6 puede ser **PASS** para efectos de E2/E3-A. D se reporta aparte, con seguimiento propio.

---

## 1. Determinismo intra-corrida (F6 TEST)

Cada escenario corre **2 réplicas** (`reps=2` en `run_scenario`). Igualdad en los 3 fingerprints:

| escenario | RUN1 == RUN2 (input_config / graph_snapshot / findings) |
|---|---|
| **A** | ✅ True |
| **B** | ✅ True |
| **C** | ✅ True |
| D | `SKIPPED_NO_STORE` |

---

## 2. Fingerprints por escenario

| escenario | config | `input_config` | `graph_snapshot` | `findings` | n_findings |
|---|---|---|---|---|---|
| **A** | PROD state, `extract_tests=OFF` | `3fcb3ae8…` | `2fdda0e2…` | `235f724a…` | **457** |
| **B** | FRESH re-extracción, `extract_tests=OFF` | `3fcb3ae8…` | `2fdda0e2…` | `235f724a…` | **457** |
| **C** | FRESH, `extract_tests=ON` (H-10) | `3fcb3ae8…` | `530459cc…` | `9e46a1cd…` | **458** |
| D | H-10 + SAT RW-0003 | — | — | — | `SKIPPED_NO_STORE` |

- **A y B son IDÉNTICOS en los 3 fingerprints** — y `findings_A.json == findings_B.json`
  **byte a byte** (sha256 `b43b548b…`, `F6_hashes.json`).
- A/B == la **baseline ENFORCE de F5** (`3fcb3ae8` / `2fdda0e2` / `235f724a`). El R-PAR
  reproduce la baseline post-estabilización.
- C: `input_config` igual; `graph_snapshot` y `findings` cambian por H-10 (`extract_tests=ON`).

---

## 3. A ↔ B — clone-drift (emparejado por `finding_record_id`)

| métrica | valor |
|---|---|
| `only_in_A` | **0** |
| `only_in_B` | **0** |
| `in_both_same_band` | **457** |
| `in_both_band_changed` | **0** |
| clasificación de desaparición | `{CLONE_DRIFT: 0, SOURCE_STATE_DIFFERENCE: 0, IDENTITY_CHANGE: 0, UNEXPLAINED: 0}` |

**Clone-drift = 0.** El `canonical_store` de producción (A) y la re-extracción fresca (B)
producen el **mismo conjunto de findings, misma banda de riesgo, mismos `finding_record_id`**.

### Explicación de cada `only_in_A` (F6 acción 4)

**No hay ninguno** (`only_in_A = 0`). Tras la de-contaminación de RW-0012 en F2-r1, el estado
del store de producción es idéntico al de la re-extracción limpia — no queda drift que
explicar. (En la corrida contaminada previa, RW-0012 aportaba ~337 claims WFI de más; esos
findings ya no existen en ninguno de los dos lados.)

---

## 4. B ↔ C — efecto puro de H-10 (`extract_tests=ON`)

| métrica | valor |
|---|---|
| `only_in_B` | **0** |
| `only_in_C` | **1** |
| `in_both_same_band` | **457** |
| `in_both_band_changed` | **0** |

**El 1 finding `only_in_C`:**
`finding_record_id = rec-b192b0eda6e0d549` · `class = TestCoverageFinding` ·
`subtype = TEST_WITHOUT_REQUIREMENT` · `document = RW-0009` (SAT transmittal) · `page 1` ·
`band = LOW`. Es el efecto esperado de H-10: con `extract_tests=ON` el pipeline extrae un
objeto `Test` de RW-0009 y detecta que no tiene requisito aguas arriba → `TEST_WITHOUT_REQUIREMENT`.
No mueve ninguna banda de riesgo de findings preexistentes (`in_both_band_changed = 0`).

**Grafo (H-10):** `refers_to` **0 → 201** aristas (`_link_refers_to`: claim → system_component/actor
por mención literal). `tested_by` 0 → 0 (ningún `tested_by` materializa en este corpus).
`implemented_by` / `designed_by` / `regulated_by` sin cambio.

---

## 5. Invariantes de seguridad (F6 acción 5)

| escenario | `document_egress_bytes` | `human_gate_intact` |
|---|---|---|
| A | **0** | **True** |
| B | **0** | **True** |
| C | **0** | **True** |

---

## 6. Escenario D (capacidad nueva, no paridad)

`D_status = SKIPPED_NO_STORE`. RW-0003 (SAT 204 pág imagen) `NO_DISPONIBLE` — bloqueado en
gobernanza (`qualification_contract.yaml CT-WP-D-REAL` / `D-4-H9` no ejecutado; ver
`F4`/`VALIDATION_BASELINE_MANIFEST.json::rw0003_store`). `C_vs_D_rw0003_additive` y `RR1` =
`SKIPPED_NO_STORE`. **Por corrección 5, D NO bloquea E2/E3-A.** Para habilitar D: declarar
`rw0003_store.status = AVAILABLE` + `path` a un store RW-0003 gobernado.

---

## 7. Derivación de readiness (para F9)

| condición (corrección 5) | estado |
|---|---|
| `F6(A/B/C) = PASS` | ✅ (deterministas, clone-drift 0, único `only_in_C` explicado, egress 0, human gate intacto) |
| `E2_READY = YES sii F4=PASS ∧ F5=PASS ∧ F6(A/B/C)=PASS` | condiciones cumplidas → **habilitable en F9** |
| `E3A_READY = YES sii F1=PASS ∧ F2=PASS ∧ F6(A/B/C)=PASS` | condiciones cumplidas → **habilitable en F9** |

(F9 es el gate humano que fija formalmente `E2_READY`/`E3A_READY`; F6 sólo establece
`F6(A/B/C) = PASS`.)

---

## 8. VEREDICTO F6

- A/B/C **deterministas** (RUN1==RUN2 en los 3 fingerprints).
- **Clone-drift A↔B = 0** (findings byte-idénticos; `finding_A.json == finding_B.json`).
- **B↔C** caracterizado: +1 `TEST_WITHOUT_REQUIREMENT` (RW-0009) + 201 `refers_to`, 0 cambios de
  banda — efecto puro de H-10.
- `only_in_A` = 0 → nada que explicar (F6 acción 4 satisfecha trivialmente).
- `document_egress_bytes = 0`, `human_gate_intact = True` en A/B/C.
- **0 rutas efímeras** (heredado de F3; `--check` OK).
- **D = `SKIPPED_NO_STORE`**, NO bloquea E2/E3-A (corrección 5).

**`PROPOSED_VERDICT F6 = PASS`** (D no requerido). `PARTIAL` sólo aplicaría si algún `only_in_A`
quedara sin explicar — no hay ninguno. `FAIL` sólo si A/B/C no reprodujeran o reapareciera
dependencia del worktree sucio — ninguna de las dos.

---

## REPORTE FORMATO OBLIGATORIO — F6

```
FASE            = F6 (ejecución R-PAR completa)
PRE_COMMIT      = ab8a896  (reconc-F5)
POST_COMMIT     = <commit reconc-F6>
WORKTREE_PRE    = igual que reconc-F5
WORKTREE_POST   = + docs_plan/reconc/{F6_R_PAR_DELTA_FINAL.md, F6_hashes.json} ;
                  docs_plan/_r_par/ regenerado (gitignored, no va a git)
DIFF            = docs_plan/reconc/F6_R_PAR_DELTA_FINAL.md (nuevo) ; docs_plan/reconc/F6_hashes.json (nuevo)
COMMANDS        = PYTHONPATH=. .venv/bin/python factory/scripts/ops/r_par_delta_v1_v2.py
TEST_RESULTS    = determinism {A:True, B:True, C:True} ; exit 0 ; D_status=SKIPPED_NO_STORE
INPUT_HASHES    = stores limpios F2-r1 (ver VALIDATION_BASELINE_MANIFEST) ; script sha (git-tracked, F3)
OUTPUT_HASHES   = R_PAR_RAW.json 213fc6b0… ; findings_A/B.json 287193 b43b548b… (idénticos) ;
                  findings_C.json 287806 e0dd2924… ; findings_D.json 118 2ba3a8bd… (F6_hashes.json)
FINGERPRINTS    = A/B = F5 ENFORCE baseline (3fcb3ae8 / 2fdda0e2 / 235f724a) ;
                  C = 3fcb3ae8 / 530459cc / 9e46a1cd (H-10)
ARTIFACTS       = docs_plan/reconc/F6_R_PAR_DELTA_FINAL.md ; docs_plan/reconc/F6_hashes.json ;
                  docs_plan/_r_par/{R_PAR_RAW.json, findings_A/B/C.json, findings_D.json} (gitignored)
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. D SKIPPED_NO_STORE por diseño (corrección 5), no es desviación.
EXPECTED_VS_ACTUAL:
  EXPECTED: A/B/C reproducibles ; delta v1↔v2 caracterizado ; clone-drift explicado.
  ACTUAL:   A/B/C deterministas (RUN1==RUN2) ; clone-drift A↔B = 0 (findings byte-idénticos) ;
            B↔C = +1 TEST_WITHOUT_REQUIREMENT + 201 refers_to, 0 band changes ;
            0 only_in_A ; egress 0 ; human gate intacto ; D SKIPPED (no requerido).
PROPOSED_VERDICT = PASS
```

Devin (F6): desde clon limpio `reconc-F6` corre `r_par_delta_v1_v2.py` → reproduce
`determinism {A:True,B:True,C:True}`, `AB_only_A=0`, `AB_only_B=0`, `BC_only_C=1`
(TEST_WITHOUT_REQUIREMENT / RW-0009), `refers_to 0→201`, `egress=0`; verifica 0 rutas efímeras
(`--check`). D = `SKIPPED_NO_STORE`.
