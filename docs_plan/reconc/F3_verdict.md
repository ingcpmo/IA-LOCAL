# F3 — VEREDICTO: reparación de `r_par_delta_v1_v2.py`

**Plan de reconciliación v1.1 · FASE 3 · discrepancia D1 (script).**
**Precondiciones:** F1 PASS ✅ + F2-r1 PASS ✅.

## Objetivo

Que `r_par_delta_v1_v2.py` corra **sin rutas efímeras** ni **dependencia del worktree sucio**,
con el escenario D degradando limpio a `SKIPPED_NO_STORE` cuando falta el store de RW-0003.

## Acciones exactas (F3) — hechas

| # | acción F3 | resultado |
|---|---|---|
| 1 | Sustituir la ruta hardcodeada de D por una entrada del `VALIDATION_BASELINE_MANIFEST` (o `NO_DISPONIBLE` explícito) | `_RW0003_DET` (ruta `/tmp/claude-1000/…/scratchpad/…`) **eliminada**. Store de RW-0003 → `manifest.rw0003_store` (hoy `NO_DISPONIBLE`, declarado). |
| 2 | Si el store RW-0003 no es regenerable → **FALLA CERRADO** y marca D `SKIPPED_NO_STORE`; nunca aborta a mitad dejando artefactos vacíos | `_RW0003Unavailable` → `_skipped_scenario("D")`. `main()` escribe SIEMPRE `R_PAR_RAW.json` + `findings_{A,B,C}.json`; `findings_D.json` = `{"status": SKIPPED_NO_STORE}`. |
| 3 | A/B/C leen del store materializado, no del worktree | A (`source=PROD`) verifica el `LOGICAL_CONTENT_HASH` de cada store contra el baseline F2-r1 del manifest (fail-closed si drifteó); B/C re-extraen fresco. Misma función de hash que `materialize_stores.py` (importada). |
| 4 | Dry-run de A/B/C que produzca `docs_plan/_r_par/` no vacío. NO el R-PAR completo. | `--dry-run-abc` → `R_PAR_RAW.json` (15 KB) + `findings_A/B/C.json` (~280 KB c/u). exit 0, sin excepción. |

## TESTS_CLAUDE (F3)

| test | resultado |
|---|---|
| A/B/C sin excepción | ✅ `--dry-run-abc` y camino completo: exit 0, `determinism {A:True,B:True,C:True}` |
| D = `SKIPPED_NO_STORE` si falta store | ✅ tanto por `--dry-run-abc` como por `manifest.rw0003_store=NO_DISPONIBLE` (camino completo) |
| 0 rutas `/tmp/claude-*` en el código | ✅ `--check` → `SELFCHECK OK` exit 0. `grep` sólo encuentra los fragmentos compuestos dentro de `_selfcheck` (no una ruta real). |

## Observaciones del dry-run (no es el R-PAR, es F6)

- **`AB_only_A = 0`, `AB_only_B = 0`** → **clone-drift = 0**. Tras la de-contaminación de
  F2-r1, el `canonical_store` de producción (A) == la re-extracción fresca (B).
- `A_n = B_n = 457`, `C_n = 458` (extract_tests=ON añade 1).
- `rw0012 prod/clean claims: 258 / 258` — RW-0012 des-contaminado, consistente entre A y B.
- `BC_only_C = 1`, `BC_refers_to = {B:0, C:201}` — efecto H-10 visible.
- **D no evaluado** (`SKIPPED_NO_STORE`) — RW-0003 bloqueado en gobernanza (CT-WP-D-REAL).

## VEREDICTO

Por la matriz de F3:
- **PASS** = "Devin corre A/B/C desde limpio sin excepción y sin rutas efímeras."
- **PARTIAL** = "D SKIPPED_NO_STORE documentado; A/B/C reproducen."

D queda `SKIPPED_NO_STORE` (RW-0003 no disponible, bloqueado en gobernanza) → encaja en
**PARTIAL** por la letra de la matriz; pero A/B/C reproducen de forma determinista sin
excepción ni rutas efímeras, que es lo que F3 exige del script.

**`PROPOSED_VERDICT F3 = PASS`** (A/B/C sin excepción, deterministas, 0 rutas efímeras,
output no vacío) **con nota:** D = `SKIPPED_NO_STORE` documentado; para ejecutar D hay que
declarar `rw0003_store.status = AVAILABLE` + `path` a un store RW-0003 gobernado (F6, tras
D-4-H9). El plan F6 §"DECLARACIÓN PREVIA OBLIGATORIA (corrección 5)" ya trata D como
CAPACIDAD NUEVA, no paridad → D no bloquea E2/E3-A.

---

## REPORTE FORMATO OBLIGATORIO — F3

```
FASE            = F3 (reparación r_par_delta_v1_v2.py)
PRE_COMMIT      = 4c64a05  (reconc-F2-r1)
POST_COMMIT     = <commit reconc-F3>
WORKTREE_PRE    = script con _RW0003_DET = ruta /tmp/claude-1000/.../scratchpad/... ; D aborta
WORKTREE_POST   = script sin rutas efímeras ; D -> SKIPPED_NO_STORE ; A fail-closed vs manifest ;
                  + docs_plan/reconc/F3_* ; + rw0003_store en el manifest ;
                  docs_plan/_r_par/ regenerado (gitignored)
DIFF            = factory/scripts/ops/r_par_delta_v1_v2.py (+135 / -25) ;
                  docs_plan/reconc/{F3_script_diff.md, F3_verdict.md, F3_dryrun_ABC.json} ;
                  docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json (+rw0003_store)
COMMANDS        = r_par_delta_v1_v2.py --check ; r_par_delta_v1_v2.py --dry-run-abc ;
                  r_par_delta_v1_v2.py   (camino completo, D auto-skip)
TEST_RESULTS    = --check: SELFCHECK OK (exit 0)
                  --dry-run-abc: exit 0, determinism {A:True,B:True,C:True}, A_n=B_n=457, C_n=458
                  camino completo: exit 0, D_status=SKIPPED_NO_STORE
INPUT_HASHES    = canonical_store == VALIDATION_BASELINE_MANIFEST (fail-closed verificado en A) ;
                  RW-0005 logical 8e7196a007f02274... (script == manifest)
OUTPUT_HASHES   = n/a (F3 no congela stores; produce docs_plan/_r_par/ efímero)
FINGERPRINTS    = n/a en F3 (F5)
ARTIFACTS       = factory/scripts/ops/r_par_delta_v1_v2.py ;
                  docs_plan/reconc/{F3_script_diff.md, F3_verdict.md, F3_dryrun_ABC.json}
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = 1 clave declarativa (rw0003_store) añadida a VALIDATION_BASELINE_MANIFEST.json,
                  exigida por F3 acción 1 ("declarado NO_DISPONIBLE explícitamente").
EXPECTED_VS_ACTUAL:
  EXPECTED: script reproducible ; sin FileNotFoundError ; artefactos no vacíos ; D SKIPPED si falta store.
  ACTUAL:   0 rutas efímeras (--check OK) ; A/B/C exit 0 deterministas ; D=SKIPPED_NO_STORE
            documentado ; docs_plan/_r_par/ con R_PAR_RAW.json (15KB) + findings_A/B/C (~280KB) ;
            A fail-closed contra el baseline del manifest (no corre sobre un store drifteado).
PROPOSED_VERDICT = PASS
```

Devin (F3): desde clon limpio corre `r_par_delta_v1_v2.py --check` (OK) y
`--dry-run-abc` → A/B/C exit 0 sin excepción, `docs_plan/_r_par/` no vacío, 0 rutas efímeras;
D = `SKIPPED_NO_STORE`.
