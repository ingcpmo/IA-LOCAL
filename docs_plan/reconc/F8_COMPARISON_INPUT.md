# F8 — INSUMO DE CRUCE: Plan v1.1 ↔ Claude Code ↔ Devin

**Plan de reconciliación v1.1 · FASE 8.**
**F8 lo ejecuta LA MESA (Claude Web), NO Claude Code.** Este documento es el insumo:
matriz de tres columnas con las columnas **Plan** y **Claude Code** completas y la columna
**Devin** poblada con los veredictos por fase ya relevados por Capa 9 (F0..F7 = PASS). La
columna **LA MESA — adjudicación F8** y el **veredicto acumulativo** los completa Claude Web.

**HEAD = `a9567c1` (`reconc-F7`) == `origin/fix/clon-local-validacion`.**

---

## 1. Estado de los gates por fase (relevado por Capa 9)

| fase | tag → commit | Devin (clon independiente) | Capa 9 |
|---|---|---|---|
| F0 | `reconc-F0` → `3749569` | verificado | **PASS** |
| F1 | `reconc-F1-r1` → `414557f` (histórico `reconc-F1` → `09656e1`) | verificado | **PASS** (`F1_GLOBAL = PASS`) |
| F2 | `reconc-F2-r1` → `4c64a05` (histórico `reconc-F2` → `8c4e7ab`) | verificado (2ª ronda, tras F2 rechazado) | **PASS** |
| F3 | `reconc-F3` → `484abea` | verificado | **PASS** |
| F4 | `reconc-F4` → `6b34051` | verificado | **PASS** |
| F5 | `reconc-F5` → `ab8a896` | verificado | **PASS** (`F5 = PASS`) |
| F6 | `reconc-F6` → `9930fc5` | verificado | **PASS** (`F6 = PASS`) |
| F7 | `reconc-F7` → `a9567c1` | auditoría acumulativa | **PASS** (`F7 = PASS`) |

Cadena lineal, sin merges. Tags históricos `reconc-F1` / `reconc-F2` **no movidos**.

---

## 2. Matriz D1–D8 — Plan ↔ Claude Code ↔ Devin ↔ Mesa

> Columna **LA MESA — adjudicación F8**: a completar por Claude Web (ACEPTA / OBSERVA / RECHAZA + nota).

### D1 — `r_par_delta_v1_v2.py` usa rutas efímeras como fuente

| | |
|---|---|
| **Plan v1.1 exige** | Script no debe leer de `/tmp/...` ni de rutas efímeras. Fuente = manifest/corpus gobernado. Ejecutar el R-PAR completo v1↔v2. |
| **Claude Code entregó** | **F3**: eliminado `_RW0003_DET = Path("/tmp/claude-1000/.../RW-0003_ingested.sqlite3")`. Añadido `_resolve_rw0003_store(manifest)` (None si `status != AVAILABLE`), `_RW0003Unavailable`, `_skipped_scenario()` (stub seguro `status: SKIPPED_NO_STORE`), `_selfcheck()` (patrones compuestos por fragmentos para no auto-detectarse), import de `logical_hash_sqlite` desde `materialize_stores.py` (misma definición de hash). `--check` (0 rutas efímeras, exit 0) · `--dry-run-abc` (exit 0). Escenario A **fail-closed** contra el manifest. **F6**: R-PAR ejecutado — A/B/C deterministas (RUN1==RUN2), clone-drift A↔B = 0 (findings byte-idénticos `b43b548b`), B↔C = +1 `TEST_WITHOUT_REQUIREMENT` (RW-0009) + 201 `refers_to`, 0 cambios de banda. `document_egress_bytes = 0`. D = `SKIPPED_NO_STORE` (corrección 5: no bloquea E2/E3-A). |
| **Devin** | F3 = PASS · F6 = PASS (clon limpio reprodujo `determinism {A,B,C}=True`, `AB_only_A/B=0`, `BC_only_C=1`, `--check` OK). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D2 — Extractor divergente (regex `\.?` no está en HEAD)

| | |
|---|---|
| **Plan v1.1 exige** | Reconciliar el extractor contra un **ground truth humano-aprobado**. NO rediseñar. Medir HEAD-limpio vs con-cambio. |
| **Claude Code entregó** | **F1**: ground truth de los 8 encabezados de nivel 1 de RW-0011/0012/0014 leído del PDF real, **aprobado por Capa 9** (`F1_HUMAN_GROUND_TRUTH_REVIEW.md`, `GROUND_TRUTH_SHA256 = 2f7a00dc…`, subencabezados N.M fuera de alcance). Orden respetado: aprobación → commit → medición. `F1_measure.py` (monkeypatch HEAD vs WT) → **HEAD-limpio 0/8, con-cambio 8/8 exacto** en los 3 DS. Fix versionado: `_HEADING_RE` / `_TOC_ENTRY_RE` `(\d{1,2})\s+` → `(\d{1,2})\.?\s+` (punto opcional tras el número, forma "1. OBJECTIVE" de las plantillas MAVERICK). Tests: 11 passed / 1 skipped (+ guarda de regresión con ground truth). Tag histórico `reconc-F1` no movido; cierre corregido en `reconc-F1-r1`. |
| **Devin** | F1 = PASS (`F1_GLOBAL = PASS`; PRE 0/8 y POST 8/8 reproducidos desde clon limpio). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D3 — Stores no reproducibles / doble hash sin definir (+ RW-0012 contaminado)

| | |
|---|---|
| **Plan v1.1 exige** | `materialize_stores.py` desde clon limpio SIN `canonical_store` previo; doc→PDF y baseline PRE desde manifest/corpus, **nunca de stores existentes**. Definir `BYTE_HASH` vs `LOGICAL_CONTENT_HASH`. Eliminar la no-determinación de `graph_store`. RW-0012 limpio (8 secciones) = baseline. Materializar en tmpdir aislado, no sobrescribir el origen durante la prueba. |
| **Claude Code entregó** | **F2_HASH_DEFINITION.md** (commit `9ab7c2b`, ANTES de medir): BYTE = sha256 del fichero; LOGICAL = sha256 del dump canónico normalizado (SQLite: orden estable, excluye `run_id`/`agent_id`/`*_at`, rutas de entorno → `<ENV>`; JSON: `sort_keys`, excluye volátiles). Regla: BYTE distinto + LOGICAL igual = reproducible lógico, NO FAIL. **F2-r1**: `materialize_stores.py` reescrito — `_PDF_MAP` declarado en el script y verificado contra sha256 de cada PDF (`RuntimeError` on mismatch), NO leído de stores. `--runs N` (tmpdirs aislados) → `PYTHONHASHSEED=random --runs 3` = `DETERMINISTA canonical: True graph: True`, graph LOGICAL `3ead71532cf44fab`. `--apply` regenera el origen CON backup. `graph/build.py`: 3× `sorted()` sobre iteración de sets (causa raíz del `via_ref` last-write-wins) — probado que **NO** mueve la topología (`graph_snapshot` sobre el store contaminado sigue `88f15b69`). **RW-0012 des-contaminado**: causa raíz `b4b_runner._PDF_BY_DOC["RW-0012"] = "…WFI…revB.pdf"`; re-materializado limpio → 13→8 secciones, 595→258 claims; graph 3342→3000 nodos. `test_extraction_adequacy.py:214` `(342,90,26)→(342,90,25)` (el 26 era artefacto de la contaminación — cambio de baseline controlado autorizado por Capa 9). Backups `_reconc_backup_20260901T201038Z` / `…T210343Z`. |
| **Devin** | F2 (1ª ronda) = FAIL (mapa doc→PDF venía de los stores; no-determinismo de graph). Corregido. **F2-r1 = PASS** (clon limpio, cero copia manual de stores, 3 corridas deterministas, targeted 124 verde, logical hashes == manifest). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D4 — Fingerprints stale (medidos sobre store contaminado)

| | |
|---|---|
| **Plan v1.1 exige** | Rebaseline de los 3 fingerprints sobre el estado limpio post-F4. Solo docs + manifest, sin código. Marcar la evidencia previa como histórica. |
| **Claude Code entregó** | **F5**: nueva baseline HEAD `6b34051`, stores limpios F2-r1, counts 342/90/25. `INPUT_CONFIG 3fcb3ae8…` · `GRAPH_SNAPSHOT 2fdda0e2…` · `FINDINGS(ENFORCE) 235f724a…` / `(OBSERVE) 693fc746…`. Deterministas (r1==r2), **independientes de `project_id`** (verificado con 3 project_ids). `findings_fingerprint` explicitado como LÓGICO (byte ≠ entre corridas, coherente con F2). **9 digests previos → HISTÓRICOS** (medidos sobre `INPUT_CONFIG` previo y/o store contaminado). `test_run_fingerprint.py` 23 passed (no assert golden; comprueba determinismo/longitud/sensibilidad). **3 tests de hardening con baseline hardcodeado stale** (`test_h4_graph_snapshot`, `test_h5f_hardening:33-34`, `test_h7_coverage_governance:21-24`) → **listados para corrección mecánica autorizada por Capa 9** (F5 no edita código). Causa: la de-contaminación de RW-0012 (probado que NO es el `sorted()` de F2-r1). |
| **Devin** | F5 = PASS (3 fingerprints exactos reproducidos desde clon limpio en 2 corridas). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D5 — Ledger no reconciliado

| | |
|---|---|
| **Plan v1.1 exige** | Reconciliar `decisions_v2.jsonl` / audit trail. **CERO hand-edits.** No reescribir audit trail. |
| **Claude Code entregó** | **F4**: `sha256(decisions_v2.jsonl)` inicio == fin == `1b0c7cf8…` (F4 no tocó ledger / audit trail / `fork_baseline.json`). Clasificación por id: `-022..-025` (2026-09-01, E1-3 + E1_ACCEPTANCE, Mission Control) = GOBERNADA_Y_RECUPERABLE, nada que re-emitir; `-022/023, 029..032` (2026-08-31) = HISTÓRICA_SIN_PERSISTENCIA + SUPERSEDIDA; `-024..028` (2026-08-31) = **NO_RECONCILIABLE justificada** (artefacto no identificable desde el audit trail). **ID_COLLISION probado**: `-022..-025` emitidos 2×, `-024/-025` con `target_set_hash` distinto entre eventos. Causa raíz: `decision_store_v2.next_instance_id:189` acuña `max()` del **JSONL revertible**, no del audit trail append-only → `git checkout` del ledger regresa el contador. **Corrección propuesta, NO aplicada** (código de servicio → fase/decisión propia de Capa 9). |
| **Devin** | F4 = PASS (con PARTIAL residual: `-024..-028` NO_RECONCILIABLE justificada; corrección del generador pendiente). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D6 — ¿H1 (`APPROVE_REMEDIATION_V1_2`) requiere asiento gobernado?

| | |
|---|---|
| **Plan v1.1 exige** | Determinar si el registro por metadata + commit (`24549a3`) de `technical_completeness_rules.yaml` es suficiente o requiere asiento por servicio de gobernanza. |
| **Claude Code entregó** | **F4 — CERRADO por contrato.** `technical_completeness_rules.yaml` **NO** está en `ARTIFACT_CLASSES = ("catalog","applicability_matrix","evidence_pack","prompt","golden_dataset")` (`artifact_version_guard.py:76-77`) ni en `enumerate_artifacts()`. No hay servicio/panel de gobernanza para este artefacto a la medida. El registro por metadata + commit es el **mecanismo correcto**. `d5d2_gate_status` quedó `DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT` (Capa 9), aún requerido para `FINAL_QUALIFICATION` y autor independiente (Maria Torres ≠ Cesar). |
| **Devin** | F4 = PASS (D6 cerrado con cita de código). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D7 — Disposición del fork histórico

| | |
|---|---|
| **Plan v1.1 exige** | Disposición formal de `FORK-2026-06-15-001`. NO reescribir la cadena. |
| **Claude Code entregó** | **F4 — NO REQUIERE ACCIÓN.** `FORK-2026-06-15-001` **ya aceptado** por `AUDIT_EXCEPTION-2026-002` (Capa 9 / Cesar, `ACTIVE`, 2026-07-30), `accepted_by_decision` poblado, `CHAIN_CONTINUITY = ACCEPTED_WITH_DOCUMENTED_EXCEPTION` (cadena NO reescrita). El flag `frozen_by_is_human_acceptance: false` concierne al freeze del baseline, no al fork, y es correcto que siga `false` (`AUDIT_FORK_REMEDIATION_SPEC.md:442`). |
| **Devin** | F4 = PASS (`fork_baseline.json` sin tocar). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

### D8 — `E1_SIGNATURE_HISTORY.md` divergente

| | |
|---|---|
| **Plan v1.1 exige** | Alinear el doc con el estado del ledger. Append-only, sin alterar la decisión firmada. |
| **Claude Code entregó** | **F4 — ALINEADO (append-only).** Añadidos los bloques **E1-3 FIRMADA — 2026-09-01** (`verdict_set_sha256 = 4e23a146…`, `verdict_counts = {CORRECT:66, WRONG_NODE:1, SPURIOUS:0, AMBIGUOUS:0}`, ledger `-022/-023`) y **E1_ACCEPTANCE · PASS** (ledger `-024/-025`), con aviso de la colisión de `instance_id`. Counts del doc == payload del ledger. |
| **Devin** | F4 = PASS (counts doc == payload). |
| **LA MESA — adjudicación F8** | _(a completar)_ |

---

## 3. Sub-discrepancias descubiertas en F0 (arrastradas a F2)

| id | qué | disposición | fase |
|---|---|---|---|
| D-F0-01 | `graph_store` hash mismatch | resuelto — graph regenerable + determinista (`3ead7153` LOGICAL, 3 corridas) | F2-r1 |
| D-F0-02 | `pilot_run` hash mismatch | congelado como EVIDENCIA_CONGELADA en el manifest (byte + logical_text) | F2 |
| D-F0-03 | 4 `.docx` no reproducibles | congelados byte-hash en el manifest; ninguna fase los commitea (out-of-scope pre-sesión) | F0/F2 |
| D-F0-05 | logical hash subespecificado + RW-0012 contaminado | resuelto — `F2_HASH_DEFINITION.md` (pre-medición) + RW-0012 des-contaminado (8 secc) | F2-r1 |

---

## 4. Chequeo de invariantes congeladas (Plan v1.1) — a validar por la mesa

| invariante | estado al cierre de F7 | evidencia |
|---|---|---|
| `E2 = NO FIRMAR` | ✅ no firmada | F6 §7: `E2_READY` sólo *habilitable* en F9 (gate humano) |
| `E3-A = NO FIRMAR` | ✅ no firmada | F6 §7: idem |
| `PILOT_EXECUTION-2026-035 = NO EJECUTAR` | ✅ no ejecutada | propuesta en `REVISION_CIERRE_H1_H10.../03_*`, sin ejecución |
| `LLM_CALLS = 0` | ✅ 0 en todo F0..F7 | todas las corridas: `run_v2_pipeline` (0 LLM), `F1_measure.py`, `materialize_stores.py`, `r_par_delta_v1_v2.py` deterministas |
| `HYBRID FASE 3 = NO INICIAR` | ✅ no iniciada | prototipo aislado en `factory/prototypes/semantic_hybrid_poc/`, FASE 2 CERRADA = PASS/PARKED |
| `PRODUCTION_ENABLEMENT = BLOCKED` | ✅ bloqueado | sin cambios en gates de habilitación |
| `NO modificar prompts gobernados` | ✅ 0 cambios | ningún `*_prompts.yaml` tocado en F0..F7 |
| `NO relajar validadores` | ✅ | F1 = punto opcional (más estricto, no menos); F3 = fail-closed añadido; sin relajación |
| `NO editar a mano decisions_v2.jsonl` | ✅ | F4: `sha256` inicio == fin == `1b0c7cf8…`; las +4 líneas son del servicio Mission Control (pre-F0) |
| `NO reescribir audit trail` | ✅ | F4: audit trail y `fork_baseline.json` sin tocar |
| `NO usar rutas efímeras como fuente` | ✅ | F3: `_RW0003_DET` eliminado; `--check` (`SELFCHECK OK`) en F3 y F6 |
| `NO declarar QUALIFIED` | ✅ | ningún artefacto de F0..F7 lo declara |
| `NO declarar READY_FOR_PRODUCTION` | ✅ | idem |
| `NO commitear contenido de store de cliente al repo PÚBLICO IA-LOCAL` | ✅ | `docs_plan/_r_par/`, `_reconc_materialized/`, `_reconc_backup_*`, `poc_log*.jsonl`, `bakeoff_results/` en `.gitignore`; F6 sólo commitea hashes sanitizados (`F6_hashes.json`) |
| `Tags históricos no se mueven` | ✅ | `reconc-F1` (`09656e1`) y `reconc-F2` (`8c4e7ab`) intactos; cierres corregidos en `-r1` |

---

## 5. Ítems abiertos que F9 debe considerar (no bloquean F8)

| ítem | origen | requiere |
|---|---|---|
| 3 tests de hardening con fingerprint stale (`88f15b69`/`fdc29721`/`b5196a71` → `2fdda0e2`/`235f724a`/`693fc746`) | F5 §5 | corrección mecánica autorizada por Capa 9 (tipo `test_extraction_adequacy.py:214`) |
| Corrección del generador de IDs (`decision_store_v2.next_instance_id`) | F4 §1 | fase/decisión propia de Capa 9; el ledger NO se reescribe |
| `-024..-028` NO_RECONCILIABLE justificada | F4 §2 | aceptación explícita de Capa 9 |
| Escenario D del R-PAR (RW-0003 SAT) `SKIPPED_NO_STORE` | F3/F6 | `rw0003_store.status = AVAILABLE` + store gobernado; NO bloquea E2/E3-A (corrección 5) |
| Commit P4 — 4 líneas de servicio de `decisions_v2.jsonl` | F0/E1 | OK explícito de Capa 9; nunca hand-edit |
| Out-of-scope pre-sesión (`remediation_directive.py`, `test_r4_t1_1v2_*`, `test_release_decision_coverage.py`) | F0 §2 | decisión de Capa 9 aparte; congelados como patches en `F0_diffs/` |
| D5-D2 (autor independiente Maria Torres ≠ Cesar) | H1 / `d5d2_gate_status` | requerido para `FINAL_QUALIFICATION`, no para desarrollo |

---

## 6. Para LA MESA (Claude Web) — qué produce F8

1. Completar la columna **LA MESA — adjudicación F8** de cada D1–D8 (§2): `ACEPTA` / `OBSERVA` / `RECHAZA` + nota.
2. Validar el chequeo de invariantes (§4) de forma independiente.
3. Emitir el **veredicto acumulativo F8**:
   - `PASS` = Plan, Claude Code y Devin concuerdan en las 8 discrepancias + invariantes intactas → habilita F9.
   - `PARTIAL` = concordancia con salvedades acotadas → F9 con condiciones.
   - `STOP` = divergencia material entre las tres columnas.
4. Entregar a Capa 9 la recomendación para F9 (`E2_READY` / `E3A_READY` / `R2_READY_TO_RESUME`).

---

## REPORTE FORMATO OBLIGATORIO — F8

```
FASE            = F8 (cruce Plan vs Claude Code vs Devin ; ejecuta LA MESA / Claude Web)
PRE_COMMIT      = a9567c1  (reconc-F7)
POST_COMMIT     = <commit reconc-F8>  (solo este insumo ; la adjudicación la escribe la mesa)
WORKTREE_PRE    = igual que reconc-F7
WORKTREE_POST   = + docs_plan/reconc/F8_COMPARISON_INPUT.md
DIFF            = docs_plan/reconc/F8_COMPARISON_INPUT.md (nuevo)
COMMANDS        = ninguno ejecutable (F8 es adjudicación documental) ; matriz derivada de los
                  reportes por fase F0..F7 ya auditados y de los gates relevados por Capa 9
TEST_RESULTS    = n/a (F8 no ejecuta) ; refiere: targeted 124 (F2-r1), test_run_fingerprint 23 (F5),
                  test_document_structure_extractor 11/1s (F1)
INPUT_HASHES    = VALIDATION_BASELINE_MANIFEST.json ; F6_hashes.json ; ledger 1b0c7cf8…
OUTPUT_HASHES   = n/a
FINGERPRINTS    = baseline F5: 3fcb3ae8 / 2fdda0e2 / 235f724a(ENFORCE) / 693fc746(OBSERVE)
ARTIFACTS       = docs_plan/reconc/F8_COMPARISON_INPUT.md ; + arco reconc-F0..F7
GOVERNANCE_EVENTS = ninguno
DEVIATIONS      = ninguna. Claude Code entrega el insumo ; NO adjudica F8 (lo hace la mesa).
EXPECTED_VS_ACTUAL:
  EXPECTED: matriz de tres columnas lista para la mesa ; invariantes verificables ; ítems
            abiertos listados para F9.
  ACTUAL:   D1–D8 con columnas Plan + Claude Code completas y Devin poblada (F0..F7 = PASS por
            Capa 9) ; 4 sub-discrepancias F0 dispuestas ; 15 invariantes con estado + evidencia ;
            7 ítems abiertos para F9 ; columna de adjudicación de la mesa vacía por diseño.
PROPOSED_VERDICT = (lo emite LA MESA / Claude Web ; Claude Code no adjudica F8)
SIGUIENTE_GATE  = F9 (gate humano Capa 9: E2_READY / E3A_READY / R2_READY_TO_RESUME)
```

---

## 7. VEREDICTO DE LA MESA — F8 (relevado, no adjudicado por Claude Code)

Emitido por LA MESA / Claude Web sobre este insumo (arco `reconc-F0..F8`, commit `4233df7`):

| discrepancia | adjudicación de la mesa |
|---|---|
| D1 — rutas efímeras / R-PAR | **PASS** |
| D2 — extractor `\.?` | **PASS** |
| D3 — stores + doble hash / RW-0012 | **PASS** |
| D4 — rebaseline de fingerprints | **PASS** |
| D5 — reconciliación del ledger | **PASS** |
| D6 — asiento gobernado de H1 | **PASS** |
| D7 — fork histórico | **PASS** |
| D8 — `E1_SIGNATURE_HISTORY.md` | **PASS** |
| F7 acumulativa (coherencia del arco) | **PASS** |

```
ALL_CRITICAL_PASS        = YES
BLOCKING_INCONSISTENCIES = 0
VERDICT_F8               = PASS
F8_CAN_ADVANCE_TO_F9     = YES
```

Las 8 discrepancias concuerdan entre **Plan v1.1**, **Claude Code** y **Devin**; 0
inconsistencias bloqueantes; invariantes congeladas intactas (§4). Habilita **F9** (gate humano
de Capa 9). Los 7 ítems abiertos de §5 pasan a F9 como consideraciones, **no** como bloqueos de
F8.
