# F2 — MATERIALIZACIÓN DE STORES · LOG Y VEREDICTO

**Plan de reconciliación v1.1 · FASE 2 · discrepancia D3 (+ D-F0-01/02/03/05 + RW-0012 contaminado).**
**Precondición:** F1 PASS ✅ (aprobado por Capa 9 2026-09-01). Sin LLM. `network_locked()`.

---

## 0. Definición de doble hash — congelada ANTES de medir

`docs_plan/reconc/F2_HASH_DEFINITION.md`, commit **`9ab7c2b`** (resuelve **D-F0-05**).
`BYTE_HASH` (bytes tal cual) vs `LOGICAL_CONTENT_HASH` (dump SQLite ordenado, payload JSON
re-serializado con claves ordenadas, campos volátiles y rutas de entorno normalizados).
**Regla:** BYTE distinto + LOGICAL igual = reproducible lógico, **NO FAIL**.

---

## 1. Procedimiento determinista de re-materialización

`factory/scripts/ops/materialize_stores.py` (nuevo). Reutiliza el código real:
`canonical.extract_document()` + `graph.build.build_project_graph()`. Sin reimplementar nada.

- Mapeo doc→PDF tomado de `canonical_store/*.sqlite3::document.archivo` — **NO** de
  `b4b_runner._PDF_BY_DOC` (que tiene `RW-0012 → "MCCPDC WFI Control Block Narrative revB.pdf"`,
  el documento de RW-0014 → **causa raíz del store contaminado**; `b4b_runner.py` fuera del
  alcance editable de F2).
- Comando:
  ```
  PYTHONPATH=. .venv/bin/python factory/scripts/ops/materialize_stores.py --apply \
      --report docs_plan/reconc/F2_materialization_report_apply.json
  ```
  `--apply` respalda `canonical_store` + `graph_store` en
  `factory/regulatory/_reconc_backup_20260901T201038Z/` y los REGENERA in situ.

---

## 2. Resultado — reproducibilidad lógica de los stores

### canonical_store (clase REGENERABLE)

| doc | LOGICAL new == pre | secciones new / pre | claims new / pre | lectura |
|---|---|---|---|---|
| RW-0005 | **True** | 8 / 8 | 1409 / 1409 | reproducible lógico |
| RW-0006 | **True** | 8 / 8 | 515 / 515 | reproducible lógico |
| RW-0009 | **True** | 0 / 0 | 62 / 62 | reproducible lógico |
| RW-0011 | **True** | 8 / 8 | 317 / 317 | reproducible lógico |
| **RW-0012** | **False** | **8 / 13** | **258 / 595** | **el store PRE estaba CONTAMINADO** (8 secc. WFI de RW-0014 + 5 secc. PCS reales). La materialización limpia (PDF correcto `MCCPDC PCS Signal Interface Control Block Narrative.pdf`) produce las 8 reales. |
| RW-0014 | **True** | 8 / 8 | 369 / 369 | reproducible lógico |

**5/6 stores canónicos son lógicamente reproducibles.** El único que difiere es RW-0012, y
la diferencia es la **corrección de la contaminación** — el store PRE era el defectuoso.

BYTE_HASH difiere en los 6 (ruta absoluta vs relativa en `document.archivo`, VACUUM/rowid de
SQLite) → **NO es FAIL** por la regla de §0.

### graph_store (clase REGENERABLE) — resuelve **D-F0-01**

| | nodes | edges |
|---|---:|---:|
| PRE (disco, construido sobre RW-0012 contaminado) | 3342 | 1344 |
| CLEAN (sobre canonical regenerado) | **3000** | **1330** |

`LOGICAL new == pre: False`. La diferencia (**Δ 342 nodos / 14 aristas**) está **100 %
explicada** por la contaminación de RW-0012: 337 claims + 5 secciones de más en el store PRE
= 342 nodos de más. Con RW-0012 limpio, el grafo es reproducible.

### D-F0-02 / D-F0-03 (EVIDENCIA_CONGELADA)

- `corpus_run/` (983 archivos, mtime 2026-08-20): salida histórica, no regenerable sin
  re-correr, **no insumo del nº targeted v1.2**. `tree_byte_sha256` en el manifest.
- `pilot_run/` (780+ archivos): acumula dirs de salida por corrida (`run_v2_pipeline` escribe
  ahí) → `BYTE_HASH` es blanco móvil por diseño. **No insumo del nº targeted.**
- 4 `.docx` bajo `pilot_run/dry_run_validation_r4_t1_1v2/`: `.docx` = zip con mtimes → nunca
  byte-estable. Se manifiestan por `LOGICAL_CONTENT_HASH` del texto (F2_HASH_DEFINITION §2.3).

---

## 3. Targeted v1.2 sobre stores MATERIALIZADOS LIMPIOS — el hallazgo de F2

| | resultado |
|---|---|
| Pre-F2 (disco contaminado) | **124 passed** |
| Post-F2 (materialización limpia, RW-0012 des-contaminado) | **123 passed, 1 failed** |

**El 1 fallo:** `factory/tests/test_extraction_adequacy.py::test_v2_runtime_observe_effect`
(línea 214):
```
assert (len(reg), len(func), len(tech)) == (342, 90, 26)
E   assert (342, 90, 25) == (342, 90, 26)   ← At index 2 diff: 25 != 26
```
- Determinista: `(342, 90, 25)` en **2/2** corridas sobre stores limpios.
- `reg = 342` y `func = 90` **sin cambio**. Sólo `tech` baja de 26 → 25.
- El finding que desaparece: **`RW-0012 AUTHORITY_CHECK_GAP`** (p.5). El comentario del
  propio test lo cita como parte del "+3 AUTHORITY_CHECK_GAP (RW-0006 p.16, RW-0012 p.5,
  RW-0014 p.5)" de v1.2 — pero el de **RW-0012 p.5 era un artefacto de la contaminación**:
  el store PRE tenía ahí el contenido WFI de RW-0014 (por eso RW-0012 p.5 y RW-0014 p.5
  compartían `source_hash 3ebeb4b7…` en la corrida postmejoras). En el store correcto,
  RW-0012 p.5 es contenido PCS Signal Interface y no dispara AUTHORITY_CHECK_GAP.

**Lectura:** el baseline de validación v1.2 `(342, 90, 26)` fue afinado contra un corpus con
RW-0012 contaminado. **El número correcto es `(342, 90, 25)`.**

**Corrección necesaria — FUERA del alcance editable de F2** (`CLAUDE_CODE_PUEDE_TOCAR` de F2 =
`materialize_stores.py` + `docs_plan/reconc/F2_*` + manifest; **no** test-files):
`test_extraction_adequacy.py:214` → `== (342, 90, 25)` + actualizar el comentario (el
"+3" pasa a "+2": RW-0006 p.16 y RW-0014 p.5; RW-0012 p.5 se retira por contaminación).
→ **Hand a Capa 9 / F5 (rebaseline)**.

---

## 4. VALIDATION_BASELINE_MANIFEST

`docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json` — git_commit, branch, code_hashes,
runtime, comandos, PDFs del corpus (sha256, todos == canonical meta), canonical_store_manifest
(byte + logical + counts, new vs pre), graph_store_manifest, corpus_run/pilot_run
(EVIDENCIA_CONGELADA), fingerprints sobre stores limpios
(`INPUT_CONFIG e9305f45…` == referencia histórica; `GRAPH_SNAPSHOT 2fdda0e2…` y
`FINDINGS 235f724a…` NUEVOS — el `88f15b69…`/`fdc29721…` históricos eran sobre el store
contaminado; rebaseline formal = F5), expected_counts, backup, `b4b_runner_bug`.

---

## 5. VEREDICTO F2

**PROPOSED_VERDICT = PARTIAL → decisión de Capa 9.**

**Lo que F2 SÍ estableció (objetivo central cumplido):**
- Los stores **son regenerables de forma determinista** (5/6 canónicos lógicamente idénticos;
  RW-0012 des-contaminado; grafo reproducible con RW-0012 limpio).
- Doble hash definido y congelado antes de medir (D-F0-05 resuelto).
- **canonical_store/RW-0012 contaminado → causa raíz identificada** (`b4b_runner._PDF_BY_DOC`)
  **y corregida** por materialización limpia.
- D-F0-01 (graph hash) explicado al 100 % y resuelto; D-F0-02/03 clasificados EVIDENCIA_CONGELADA.

**Lo que impide un PASS limpio (requiere decisión humana):**
- El baseline de validación v1.2 `(342, 90, 26)` estaba **medido contra un store contaminado**.
  El número correcto y reproducible es **`(342, 90, 25)`**. Corregir la aserción del test
  (`test_extraction_adequacy.py:214`) está **fuera del alcance editable de F2** → Capa 9
  decide (corrección puntual ahora, o en F5).

**FAIL de F2 NO se dispara:** el nº NO se reproduce "sólo copiando stores a mano" (se
reproduce por el procedimiento `materialize_stores.py`), y no hay `LOGICAL_CONTENT_HASH` de un
store regenerable que difiera **por otra causa que la contaminación ya diagnosticada**.

---

## 6. REPORTE FORMATO OBLIGATORIO — F2

```
FASE            = F2 (reproducibilidad / materialización de stores)
PRE_COMMIT      = 414557f  (HEAD tras reconc-F1-r1)  ->  9ab7c2b (F2_HASH_DEFINITION)
POST_COMMIT     = <commit reconc-F2>
WORKTREE_PRE    = 14 M / 72 ??  + canonical_store/graph_store en disco (RW-0012 contaminado)
WORKTREE_POST   = canonical_store/graph_store REGENERADOS LIMPIOS in situ (gitignored, no van a git);
                  backup en _reconc_backup_20260901T201038Z/ (gitignored);
                  + factory/scripts/ops/materialize_stores.py + docs_plan/reconc/F2_* + .gitignore (3 líneas protectoras)
DIFF            = materialize_stores.py (nuevo) ; docs_plan/reconc/{F2_HASH_DEFINITION.md,
                  F2_materialization_log.md, VALIDATION_BASELINE_MANIFEST.json} ;
                  .gitignore (+_reconc_materialized/ +_reconc_backup_*/ +F2_materialization_report*.json)
COMMANDS        = ver §1 y VALIDATION_BASELINE_MANIFEST.commands
TEST_RESULTS    = targeted v1.2 sobre stores LIMPIOS: 123 passed, 1 failed  (número REAL)
                  fallo = test_extraction_adequacy::test_v2_runtime_observe_effect (342,90,25) vs (342,90,26)
INPUT_HASHES    = PDFs: los 6 == canonical meta (RW-0005 56095a75… … RW-0014 8a67414d…, todos verificados)
                  F2_HASH_DEFINITION commit 9ab7c2b
OUTPUT_HASHES   = canonical: 5/6 LOGICAL new==pre True ; RW-0012 False (contaminación corregida)
                  graph: LOGICAL new==pre False (Δ = contaminación RW-0012, explicado)
                  fingerprints limpios: INPUT_CONFIG e9305f45… / GRAPH_SNAPSHOT 2fdda0e2… / FINDINGS 235f724a…
FINGERPRINTS    = ver arriba ; rebaseline formal -> F5
ARTIFACTS       = factory/scripts/ops/materialize_stores.py ;
                  docs_plan/reconc/{F2_HASH_DEFINITION.md, F2_materialization_log.md,
                  VALIDATION_BASELINE_MANIFEST.json} ;
                  factory/regulatory/_reconc_backup_20260901T201038Z/ (gitignored, evidencia PRE-F2)
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = (1) .gitignore +3 líneas: protege la prohibición de F2 ("contenido de stores en git")
                  en repo público; no es scope-creep. (2) --apply regenera in situ (con backup)
                  para que los targeted lean stores materializados por el procedimiento (F2 acción 3).
EXPECTED_VS_ACTUAL:
  EXPECTED: targeted reproducible desde git+manifest+procedimiento; logical-hash coincide.
  ACTUAL:   5/6 canonical LOGICAL reproducible ; RW-0012 y graph difieren SOLO por la
            contaminación ya diagnosticada y corregida ; targeted limpio = 123p/1f, y el 1f
            revela que el baseline v1.2 (342,90,26) estaba contaminado → correcto (342,90,25).
PROPOSED_VERDICT = PARTIAL  (stores regenerables + contaminación resuelta; el baseline v1.2
                   necesita 1 corrección de aserción fuera del alcance de F2 → Capa 9).
```

Devin (F2): desde clon limpio corre `materialize_stores.py` (sin `--apply`) y reproduce:
(a) 5/6 canonical `LOGICAL new==pre True` ; (b) RW-0012 y graph difieren por la contaminación
(counts 13→8 / 3342→3000) ; (c) targeted sobre los stores limpios = 123p/1f con el fallo en
`(342,90,25)` vs `(342,90,26)`. Sin copia manual de stores.
