# F5 — REBASELINE DE LOS 3 FINGERPRINTS

**Plan de reconciliación v1.1 · FASE 5 · discrepancia D4 · precondición F1..F4 PASS ✅.**
**Solo docs + `VALIDATION_BASELINE_MANIFEST.json` (sección fingerprints). Sin código, sin LLM.**

---

## 1. Determinismo intra-corrida (F5 acción 1)

`run_v2_pipeline` sobre RW-6 (RW-0005/0006/0009/0011/0012/0014) desde el **estado post-F4**
(HEAD `6b34051`, stores limpios de F2-r1 — RW-0012 des-contaminado, `build.py` con el fix de
determinismo del grafo).

| | RUN 1 | RUN 2 | ¿igual? |
|---|---|---|---|
| `input_config_fingerprint` | `3fcb3ae8…` | `3fcb3ae8…` | ✅ |
| `graph_snapshot_fingerprint` | `2fdda0e2…` | `2fdda0e2…` | ✅ |
| `findings_fingerprint` | `235f724a…` | `235f724a…` | ✅ |
| counts (reg / func / tech) | 342 / 90 / 25 | 342 / 90 / 25 | ✅ |

**DETERMINISTA intra-corrida: SÍ** (r1 == r2, byte a byte en los 3 digests y los counts).

---

## 2. NUEVA BASELINE (F5 acción 2)

```
HEAD                        = 6b34051   (rama fix/clon-local-validacion, post reconc-F4)
stores                      = canonical_store + graph_store LIMPIOS (F2-r1: RW-0012 8 secc / 258 claims)
código                     = document_structure_extractor.py \.? (F1) ; graph/build.py 3x sorted() (F2-r1)
counts                      = REGULATORY 342 · FUNCTIONAL 90 · TECHNICAL 25
```

| fingerprint | ENFORCE (modo gobernado por defecto, post D-2) | OBSERVE (contingencia) |
|---|---|---|
| **`INPUT_CONFIG_FINGERPRINT`** | `3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668` | idéntico |
| **`GRAPH_SNAPSHOT_FINGERPRINT`** | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` | idéntico |
| **`FINDINGS_FINGERPRINT`** | `235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` | `693fc746e645b168386537c7dbce8c6394b582fb6c031ebf62e44189b748a368` |

Notas:
- `INPUT_CONFIG` y `GRAPH_SNAPSHOT` son **independientes del `project_id`** (verificado: `V2-E2E`,
  `QC-CONTRACT`, `F5-REBASE` → los 3 idénticos). El modo (ENFORCE/OBSERVE) sólo mueve
  `FINDINGS_FINGERPRINT` (stamping de `evidence_basis`/`risk`), no `INPUT_CONFIG` ni el grafo.
- `run_fingerprint.py` NO incorpora `timestamp` ni `project_id` a `INPUT_CONFIG`; sí
  `extraction_version`, `routing_source`, python minor, source attestation.

---

## 3. Evidencia HISTÓRICA — NO válida para HEAD `6b34051` (F5 acción 3)

Toda evidencia con estos digests fue medida sobre un `INPUT_CONFIG` previo y/o el
`canonical_store` **contaminado** (RW-0012 con contenido WFI). **Se marca HISTÓRICA.**

| fingerprint | valor histórico | de qué corrida |
|---|---|---|
| `input_config` | `8f1fe9bbd9199949…` | PRE v1.1 (`REPORTE_COMPARATIVO_PRE_POST_MEJORAS_20260831.md`) |
| `input_config` | `df76bebf74981ced…` | POST v1.2, store contaminado (mismo reporte) |
| `input_config` | `0de04225362a6f86…` | escenario D del R-PAR (`r_par_delta_v1_v2.py`, RW-0003) |
| `graph_snapshot` | `88f15b69bf2cea9a…` | store RW-0012 **CONTAMINADO** — decisión D-2, tests `test_h4/h5f/h7` |
| `graph_snapshot` | `8ce23f30202991d8…` | escenario D del R-PAR |
| `findings` | `fdc29721e9566dfe…` | ENFORCE, store contaminado — decisión D-2, `test_h7` |
| `findings` | `3d8988045f856550…` | ENFORCE, store contaminado (F2, corrida `--apply` intermedia) |
| `findings` | `b5196a7177c92a91…` | OBSERVE, "post-H1/H2/H3", store contaminado — `test_h5f/h7` |
| `findings` | `2b1a300ae26f76cb…` | escenario D del R-PAR |

**Regla:** cualquier reporte, gate o test que asserte uno de estos valores está midiendo un
estado que ya no es el HEAD. No se re-ejecutan; se anotan como históricos.

---

## 4. `findings_fingerprint` es LÓGICO, no byte (F5 acción 4)

`run_fingerprint.findings_fingerprint()` hashea el **contenido lógico canónico** de los
findings (independiente del orden — verificado en `test_run_fingerprint.py`:
`findings_fingerprint([f1,f2]) == findings_fingerprint([f2,f1])`), NO los bytes de
`*_findings.json`. Los ficheros `regulatory_findings.json` / `functional_findings.json` /
`technical_findings.json` tienen **BYTE_HASH distinto entre corridas** (orden de serialización,
`generated_at`, rutas). **La baseline F5 fija el hash LÓGICO, no el byte** — coherente con la
definición de F2 (`F2_HASH_DEFINITION.md` §2.2).

---

## 5. Tests con baseline HARDCODEADO stale → autorización de Capa 9

3 tests de hardening asertan fingerprints históricos (medidos sobre el store contaminado).
**F5 NO los edita** (`ARCHIVOS_PROHIBIDOS = código`). Se listan para una **corrección
controlada autorizada por Capa 9** (mecánica, mismo tipo que `test_extraction_adequacy.py:214`
en F2-r1):

| archivo:línea | constante | valor stale | valor nuevo (F5) |
|---|---|---|---|
| `test_h5f_hardening.py:33` | `_FINDINGS_FP_BASELINE` | `b5196a7177c92a91…` | `693fc746e645b168…` (OBSERVE) |
| `test_h5f_hardening.py:34` | `_GRAPH_FP_BASELINE` | `88f15b69bf2cea9a…` | `2fdda0e2ce513bc4…` |
| `test_h7_coverage_governance.py:21` | `_FINDINGS_FP_OBSERVE` | `b5196a7177c92a91…` | `693fc746e645b168…` |
| `test_h7_coverage_governance.py:23` | `_FINDINGS_FP_ENFORCE` | `fdc29721e9566dfe…` | `235f724a738ce783…` |
| `test_h7_coverage_governance.py:24` | `_GRAPH_FP` | `88f15b69bf2cea9a…` | `2fdda0e2ce513bc4…` |
| `test_h4_graph_snapshot.py` | (comentario/const de baseline) | graph `88f15b69…`, findings `b5196a71…` | graph `2fdda0e2…`, findings `693fc746…`/`235f724a…` |

Estos fallos NO los causa ningún fix de F1..F4 sino la **de-contaminación de RW-0012** (F2-r1
probó que el `sorted()` de `build.py` NO mueve el `graph_snapshot`: con el store contaminado
sigue dando `88f15b69…`). Al usar el store CORRECTO, el grafo tiene 342 nodos menos → nuevo
hash.

---

## 6. `test_run_fingerprint.py` — F5 TESTS_CLAUDE

```
PYTHONPATH=. .venv/bin/python -m pytest -q factory/tests/test_run_fingerprint.py
  -> 23 passed
```
`test_run_fingerprint.py` **no asserta un valor golden**: comprueba determinismo (`a==b`),
longitud 64, sensibilidad a mutaciones, e independencia de orden en `findings_fingerprint`.
Pasa sobre la nueva baseline sin cambios.

---

## 7. VEREDICTO F5

- 3 fingerprints nuevos registrados, **deterministas** (r1==r2), **independientes de
  `project_id`**, con commit exacto (`6b34051`) y counts (342/90/25).
- Evidencia previa marcada **HISTÓRICA** (9 digests).
- `findings_fingerprint` explicitado como LÓGICO (byte ≠ entre corridas, coherente con F2).
- `test_run_fingerprint.py` verde (23).
- 3 tests de hardening con baseline stale → **listados para corrección autorizada por Capa 9**
  (fuera del alcance editable de F5).

**`PROPOSED_VERDICT F5 = PASS`** (Devin debe reproducir los 3 fingerprints exactos desde clon
limpio `reconc-F5` en 2 corridas). **PARTIAL** aplicable sólo si el `input_config` difiere por
runtime no fijado en el entorno de Devin — en ese caso se añade el componente al manifest.

---

## REPORTE FORMATO OBLIGATORIO — F5

```
FASE            = F5 (rebaseline de fingerprints)
PRE_COMMIT      = 6b34051  (reconc-F4)
POST_COMMIT     = <commit reconc-F5>
WORKTREE_PRE    = 3 tests de hardening con fingerprint hardcodeado stale (88f15b69 / fdc29721 / b5196a71)
WORKTREE_POST   = idéntico (F5 no toca tests) + docs_plan/reconc/F5_rebaseline.md +
                  VALIDATION_BASELINE_MANIFEST.json (sección fingerprints reescrita)
DIFF            = docs_plan/reconc/F5_rebaseline.md (nuevo) ;
                  docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json (fingerprints: baseline + historical)
COMMANDS        = PYTHONPATH=. python (run_v2_pipeline x2 ENFORCE + 1 OBSERVE) ;
                  pytest -q factory/tests/test_run_fingerprint.py
TEST_RESULTS    = test_run_fingerprint.py: 23 passed
                  run_v2_pipeline x2: DETERMINISTA (r1==r2) en los 3 digests y counts
INPUT_HASHES    = stores limpios F2-r1 (canonical logical: RW-0005 8e7196a0… … RW-0014 a180fdc1… ;
                  graph 3ead7153…) ; ver VALIDATION_BASELINE_MANIFEST.json
OUTPUT_HASHES   = INPUT_CONFIG 3fcb3ae8… · GRAPH_SNAPSHOT 2fdda0e2… ·
                  FINDINGS(ENFORCE) 235f724a… · FINDINGS(OBSERVE) 693fc746…
FINGERPRINTS    = los de OUTPUT_HASHES = NUEVA BASELINE (HEAD 6b34051). 9 digests previos -> HISTÓRICOS.
ARTIFACTS       = docs_plan/reconc/F5_rebaseline.md ; VALIDATION_BASELINE_MANIFEST.json
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. Los 3 tests con baseline stale se LISTAN (§5), no se editan (fuera de alcance F5).
EXPECTED_VS_ACTUAL:
  EXPECTED: 3 fingerprints nuevos + commit + counts ; evidencia previa marcada histórica ;
            findings = lógico ; test_run_fingerprint verde.
  ACTUAL:   3 fingerprints (ENFORCE + OBSERVE) deterministas y project-id-independientes,
            HEAD 6b34051, counts 342/90/25 ; 9 digests históricos ; findings LÓGICO explicitado ;
            test_run_fingerprint 23 passed ; 3 tests de hardening stale listados para Capa 9.
PROPOSED_VERDICT = PASS
```
