# F2-r1 — REPORTE CORRECTIVO (auditoría externa: F2.1 = FAIL, F2.2 = PARTIAL)

**Plan de reconciliación v1.1 · FASE 2 · corrección de las 5 exigencias de la auditoría.**
**NO se ejecuta F3.** Tag histórico `reconc-F2` **no se mueve**. Cierre corregido → `reconc-F2-r1`.

---

## §1 — `materialize_stores.py` funciona desde CLON LIMPIO sin canonical_store previo

**Antes (F2.1 = FAIL):** el mapeo doc_id→PDF y el baseline PRE se leían de
`canonical_store/*.sqlite3::document.archivo` → imposible en un clon sin stores.

**Ahora:**
- `_PDF_MAP` **declarado en el script**: `{doc_id: (pdf_filename, sha256_esperado, tipo)}`.
  El `sha256` se **verifica** contra el PDF real (`RuntimeError` si no coincide). Cero lectura
  de stores existentes. `RW-0012 → "MCCPDC PCS Signal Interface Control Block Narrative.pdf"`
  (el correcto; `b4b_runner._PDF_BY_DOC` lo tiene mal → WFI = doc de RW-0014).
- La comparación de reproducibilidad se hace **entre corridas aisladas** (`--runs N`) y/o
  contra un **manifest previo** (`--baseline-manifest`), **nunca** contra stores del origen.
- Materialización por defecto en **directorios temporales aislados** (`tempfile.mkdtemp`).

---

## §2 — No-determinación de `graph_store` ELIMINADA (causa mínima)

**Causa raíz (auditoría):** `build_project_graph` producía aristas / `attrs` distintos por
iteración. **Causa exacta:** iteración sobre **sets de strings** (`shared = set(a) & set(b)`)
→ orden por proceso (aleatorización de hash). Cuando un par `(src, dst, rel)` se produce vía
varios `ref`, el `ON CONFLICT DO UPDATE SET attrs` deja el **último** → `attrs.via_ref`
dependía del orden aleatorio.

**Fix mínimo — `factory/regulatory/graph/build.py`, 3 `sorted()`:**

| línea | función | cambio |
|---|---|---|
| ~246 | `_link_chain` | `for ref in sorted(shared):` (era `for ref in shared:`) — **este es el que causaba las `implemented_by` distintas** |
| ~368 | `_link_to_tests` | `for ref in sorted(trefs & set(...)):` |
| ~520 | `_link_contradictions` | `for ref, items in sorted(ref_claims.items()):` (mismo patrón; 0 aristas en este corpus, defensa) |

**Prueba de determinismo — 3 corridas `PYTHONHASHSEED=random`, directorios aislados:**

```
DETERMINISTA canonical: True     DETERMINISTA graph: True
graph LOGICAL_CONTENT_HASH (3/3 idéntico) = 3ead71532cf44fab...   (store limpio)
```

**Prueba de que el fix NO altera la topología (solo elimina la no-determinación):**
con el store **contaminado** (backup), `build.py` fijado produce
`graph_snapshot_fingerprint = 88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05`
— **idéntico al baseline previo**. El fix no mueve el grafo; lo hace reproducible.

---

## §3 — `VALIDATION_BASELINE_MANIFEST.json` COMPLETO

`docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json` ahora incluye, para **todos** los
artefactos exigidos por F2:

| artefacto | clase | evidencia en el manifest |
|---|---|---|
| `canonical_store` (6 docs) | REGENERABLE | `logical_hash_clean` + `counts_clean` por doc; `deterministic_over_3_runs: true` |
| `graph_store` | REGENERABLE | `logical_hash_clean` + `build_counts_clean`; `deterministic_over_3_runs: true` |
| `corpus_run` | EVIDENCIA_CONGELADA | `files` + `tree_byte_sha256` (método F2_HASH_DEFINITION §1) |
| `pilot_run` | EVIDENCIA_CONGELADA | `files` + `tree_byte_sha256` |
| 4 `.docx` (dry_run_validation_r4_t1_1v2) | EVIDENCIA_CONGELADA | `byte_hash` + `logical_text_hash` (texto, §2.3) |
| fingerprints (contaminado vs limpio) | — | `input_config` / `graph_snapshot` / `findings_ENFORCE`, ambos estados; rebaseline formal = F5 |
| `pdf_map` | — | doc_id → (pdf, sha256, tipo) declarado y verificado |
| `code_hashes` | — | extractor + extract_document + normalize_claims + build.py (byte) |
| runtime, comandos, backups, b4b_runner_bug | — | completos |

`graph_store` ya **no** queda parcial; `corpus_run` / `pilot_run` tienen la evidencia
requerida (D-F0-01/02/03 cubiertos).

---

## §4 — RW-0012 limpio (8 secciones) = baseline correcto · técnico 26 → 25

- `canonical_store/RW-0012` en el origen actualizado de forma **controlada y separada**
  (`materialize_stores.py --apply`, con backup `_reconc_backup_20260901T210343Z`):
  **13 secciones / 595 claims → 8 secciones / 258 claims** (contenido PCS Signal Interface real).
- `graph_store`: 3342 nodos / 1344 aristas → **3000 / 1330**.
- **`factory/tests/test_extraction_adequacy.py:214`**:
  `assert (len(reg), len(func), len(tech)) == (342, 90, 26)` → **`== (342, 90, 25)`**
  + comentario actualizado ("+3 → +2 AUTHORITY_CHECK_GAP: RW-0006 p.16, RW-0014 p.5; el de
  RW-0012 p.5 era artefacto de la contaminación"). `reg = 342` y `func = 90` sin cambio.
- **Targeted v1.2 completo = `124 passed`** (verde de nuevo). Determinista: `(342, 90, 25)`
  en 2/2 corridas.

---

## §5 — No se sobrescribieron los stores del origen durante la prueba

- Las 3 corridas de determinismo (`--runs 3`) y toda la validación de hashes corrieron en
  **directorios temporales aislados** (`tempfile.mkdtemp`). Verificado: durante `--runs 3` el
  `canonical_store/RW-0012` del origen siguió en 13/595 (contaminado).
- La actualización del baseline del origen (§4) fue un **paso posterior, explícito y con
  backup** (`--apply`), no un efecto colateral de la prueba.

---

## Hallazgo nuevo → F5 (fuera del alcance de F2-r1)

3 tests de **hardening** (NO "los targeted") tienen `graph_snapshot_fingerprint` /
`findings_fingerprint` **hardcodeados contra el store CONTAMINADO**:

| test | assert |
|---|---|
| `test_h4_graph_snapshot.py::test_e2e_findings_fingerprint_matches_post_h1h2h3_baseline` | graph `88f15b69…` |
| `test_h5f_hardening.py::test_h5f_does_not_move_findings_or_graph_fingerprint` | graph `88f15b69…` |
| `test_h7_coverage_governance.py::test_e2e_observe_does_not_move_findings_or_graph` | graph `88f15b69…` |

Valores limpios: `graph_snapshot = 2fdda0e2…`, `findings_ENFORCE = 235f724a…`.
**Rebaseline de estos 3 fingerprints = F5** (el plan lo define: "Baseline de los 3
fingerprints válida para el HEAD estabilizado post-F1..F4; marcar histórica toda evidencia
previa"). Registrado en `VALIDATION_BASELINE_MANIFEST.json::other_tests_needing_F5_rebaseline`.
El fix de `build.py` **no** los rompe (probado en §2); los rompe la de-contaminación de RW-0012.

---

## REPORTE FORMATO OBLIGATORIO — F2-r1

```
FASE            = F2-r1 (correctivo de F2.1=FAIL / F2.2=PARTIAL)
PRE_COMMIT      = 8c4e7ab  (reconc-F2)
POST_COMMIT     = <commit reconc-F2-r1>
WORKTREE_PRE    = origen con canonical_store contaminado (RW-0012 13/595)
WORKTREE_POST   = origen con canonical_store LIMPIO (RW-0012 8/258) + graph 3000/1330 (gitignored) ;
                  build.py +3 sorted() ; test_extraction_adequacy.py:214 -> (342,90,25) ;
                  materialize_stores.py reescrito ; docs_plan/reconc/F2_* + manifest completos ;
                  2 backups (gitignored)
DIFF            = factory/regulatory/graph/build.py (3 líneas: sorted) ;
                  factory/tests/test_extraction_adequacy.py (assert + comentario) ;
                  factory/scripts/ops/materialize_stores.py (reescrito: _PDF_MAP, --runs, aislado) ;
                  docs_plan/reconc/{F2_R1_CORRECTIVE_REPORT.md, VALIDATION_BASELINE_MANIFEST.json}
COMMANDS        = ver §2, §4 y VALIDATION_BASELINE_MANIFEST.commands
TEST_RESULTS    = targeted v1.2 (5 archivos) = 124 passed  (número REAL)
                  materialize_stores --runs 3 (PYTHONHASHSEED=random) = DETERMINISTA canonical:True graph:True
                  regresión grafo (-k "graph or build_project or link") = 71 passed, 3 failed*, 1 skipped
                  * los 3 = fingerprint hardcodeado contra store contaminado -> F5 (no F2-r1)
INPUT_HASHES    = _PDF_MAP (6 sha256 verificados) ; F2_HASH_DEFINITION commit 9ab7c2b
OUTPUT_HASHES   = canonical LIMPIO (3/3 runs idéntico): RW-0005 8e7196a0… RW-0006 7da433b4…
                  RW-0009 4922562d… RW-0011 1f267630… RW-0012 155eb281… RW-0014 a180fdc1…
                  graph LIMPIO (3/3 runs idéntico): RW-TECH-REAL 3ead7153…
                  fingerprints limpios: graph_snapshot 2fdda0e2… findings_ENFORCE 235f724a…
FINGERPRINTS    = contaminado graph 88f15b69 (== baseline previo, prueba de que build.py fix no lo mueve) ;
                  limpio graph 2fdda0e2 -> F5 rebaseline
ARTIFACTS       = factory/scripts/ops/materialize_stores.py ; factory/regulatory/graph/build.py ;
                  factory/tests/test_extraction_adequacy.py ;
                  docs_plan/reconc/{F2_HASH_DEFINITION.md, F2_materialization_log.md,
                  F2_R1_CORRECTIVE_REPORT.md, VALIDATION_BASELINE_MANIFEST.json} ;
                  _reconc_backup_20260901T{201038,210343}Z/ (gitignored)
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = F2-r1 amplió el alcance editable de F2 por instrucción explícita de Capa 9:
                  graph/build.py (fix mínimo de determinismo) y test_extraction_adequacy.py
                  (corrección controlada del baseline 26->25).
EXPECTED_VS_ACTUAL:
  EXPECTED: script desde clon limpio sin stores ; graph determinista (3 runs idénticos) ;
            manifest completo ; RW-0012 8 secc = baseline ; targeted verde ; validación aislada.
  ACTUAL:   _PDF_MAP declarado+verificado (sin leer stores) ; 3 runs PYTHONHASHSEED=random
            idénticos (canonical y graph) ; manifest con los 6 grupos de artefactos ;
            RW-0012 8/258 en origen (controlado, con backup) ; targeted 124 passed ;
            3-run validation 100% en tmp aislado, origen intacto durante la prueba.
            + hallazgo: 3 tests de hardening con fingerprint contaminado -> F5.
PROPOSED_VERDICT = PASS para F2 (los 5 problemas obligatorios resueltos y demostrados).
                   El rebaseline de los 3 fingerprints de hardening es F5, no F2.
```

Devin (F2-r1): desde clon limpio SIN `canonical_store`, corre
`PYTHONHASHSEED=random materialize_stores.py --runs 3` → reproduce
`DETERMINISTA canonical:True graph:True` y los LOGICAL hashes de OUTPUT_HASHES; corre el
targeted v1.2 → 124 passed. Cero copia manual de stores.
