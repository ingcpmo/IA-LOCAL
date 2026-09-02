# REPORTE DE CIERRE — ARCO DE RECONCILIACIÓN F0..F9 (Plan v1.1)

**Rama:** `fix/clon-local-validacion` · **HEAD:** `d55694f` (`reconc-F9-r1`)
**Periodo:** 2026-09-01 → 2026-09-02 · **Ejecutor:** Claude Code (Capa 8) · **Autoridad:** Capa 9 (Cesar)
**Auditoría independiente:** Devin (clon independiente, fase a fase + acumulativa) · **Cruce final:** la mesa / Claude Web

---

## 0. Veredicto global

| | |
|---|---|
| **ARCO F0..F9** | **CERRADO — PASS** |
| Discrepancias resueltas | **D1–D8 = 8/8 PASS** (adjudicación de la mesa, `VERDICT_F8 = PASS`, `BLOCKING_INCONSISTENCIES = 0`) |
| Auditoría acumulativa (F7) | **PASS** — ningún tag posterior invalidó una fase previa |
| Gate humano (F9) | **E2 y E3-A FIRMADOS por Capa 9 vía Mission Control**; verificados READ-ONLY sin hand-edit |
| Rediseño H-1…H-10 | **NO se rediseñó** ninguno (fuera de alcance del plan, respetado) |
| Integridad del ledger | **0 hand-edits de Claude** en todo el arco; sólo apéndices del servicio gobernado |
| Estado de producción | **`PRODUCTION_ENABLEMENT = BLOCKED`** — sin cambios |

---

## 1. Alcance — las 8 discrepancias (D1–D8) + residuales F0

| id | discrepancia diseño ↔ ejecución | fase(s) | resultado |
|---|---|---|---|
| **D1** | `r_par_delta_v1_v2.py` usaba rutas efímeras (`/tmp/...`) como fuente | F3 + F6 | **PASS** — script sin rutas efímeras (`--check` OK); R-PAR ejecutado, `document_egress_bytes = 0` |
| **D2** | Extractor divergente: regex `(\d{1,2})\.?\s+` no estaba en HEAD | F1 | **PASS** — fix versionado contra **ground truth humano-aprobado** (`2f7a00dc…`); HEAD-limpio 0/8 vs con-cambio 8/8 en RW-0011/0012/0014 |
| **D3** | Stores no reproducibles; doble hash sin definir; RW-0012 contaminado | F2 / F2-r1 | **PASS** — `materialize_stores.py` determinista desde clon limpio (`--runs 3`); `F2_HASH_DEFINITION.md` (BYTE vs LOGICAL) congelado antes de medir; RW-0012 des-contaminado (13→8 secc, 595→258 claims) |
| **D4** | Fingerprints stale (medidos sobre store contaminado / `INPUT_CONFIG` previo) | F5 | **PASS** — nueva baseline HEAD `6b34051`, determinista, project-id-independiente; 9 digests previos → HISTÓRICOS |
| **D5** | Ledger no reconciliado | F4 | **PASS** — clasificación por id; `sha256` inicio == fin en el arco; **ID_COLLISION probado** (causa raíz citada) |
| **D6** | ¿H1 (`APPROVE_REMEDIATION_V1_2`) requiere asiento gobernado? | F4 | **PASS** — **cerrado por contrato**: `technical_completeness_rules.yaml` ∉ `ARTIFACT_CLASSES`; metadata + commit es el mecanismo correcto |
| **D7** | Disposición del fork histórico `FORK-2026-06-15-001` | F4 | **PASS** — **ya gobernado** por `AUDIT_EXCEPTION-2026-002` (ACTIVE); cadena no reescrita |
| **D8** | `E1_SIGNATURE_HISTORY.md` divergente del ledger | F4 | **PASS** — alineado append-only (bloques E1-3 FIRMADA + E1_ACCEPTANCE); decisión firmada no alterada |

**Sub-discrepancias descubiertas en F0** (arrastradas a F2): D-F0-01 graph_store hash mismatch → resuelto (regenerable+determinista); D-F0-02 pilot_run hash mismatch → congelado como EVIDENCIA_CONGELADA; D-F0-03 4 `.docx` no reproducibles → byte-hash congelado, out-of-scope; D-F0-05 logical hash subespecificado + RW-0012 → resuelto (`F2_HASH_DEFINITION.md` + de-contaminación).

---

## 2. Cadena de fases — tag → commit → qué estableció → veredicto

| fase | tag | commit | qué estableció | veredicto |
|---|---|---|---|---|
| **F0** | `reconc-F0` | `3749569` | HEAD real descubierto (`9096005`, no `6be0626`); working tree clasificado (patches + hashes); targeted real = 124; ledger 259 líneas `1b0c7cf8…`; STOP-F0 no disparó (sin commits de producto ocultos) | **PARTIAL_ACCEPTED** (residuales → F2..F5); `F0_RESIDUALS_RECONCILED = YES` |
| **F1** | `reconc-F1` | `09656e1` | Fix del extractor `\.?` versionado + medición mecánica HEAD vs WT | superado por r1 |
| **F1-r1** | `reconc-F1-r1` | `414557f` | Ground truth de 8 encabezados nivel 1 (RW-0011/0012/0014) **aprobado por Capa 9** (`GROUND_TRUTH_SHA256 2f7a00dc…`); orden aprobación→commit→medición respetado; PRE 0/8, POST 8/8 exacto; regresión guard | **PASS** (`F1_GLOBAL = PASS`) |
| **F2** | `reconc-F2` | `8c4e7ab` | Materialización de stores + `F2_HASH_DEFINITION.md` (BYTE vs LOGICAL, congelado antes de medir) | **PARTIAL** → r1 |
| **F2-r1** | `reconc-F2-r1` | `4c64a05` | `materialize_stores.py` con `_PDF_MAP` verificado por sha256 (no leído de stores); `--runs 3` determinista (graph LOGICAL `3ead7153…`); `graph/build.py` 3× `sorted()`; RW-0012 des-contaminado; `test_extraction_adequacy.py:214` `(342,90,26)→(342,90,25)` | **PASS** (targeted 124 verde, clon limpio) |
| **F3** | `reconc-F3` | `484abea` | `_RW0003_DET` (`/tmp/...`) eliminado; `_resolve_rw0003_store` desde manifest; escenario D → `SKIPPED_NO_STORE`; A fail-closed contra el manifest; `--check` / `--dry-run-abc` | **PASS** |
| **F4** | `reconc-F4` | `6b34051` | `sha256(decisions_v2.jsonl)` inicio == fin == `1b0c7cf8…`; **ID_COLLISION probado** (`AV-2026-022..025` emitidos 2×; causa raíz `decision_store_v2.next_instance_id:189` acuña `max()` del JSONL revertible); D6 cerrado por contrato; D7 ya gobernado; D8 alineado | **PASS** (con PARTIAL residual: `-024..-028` NO_RECONCILIABLE justificada; fix del generador → fase propia) |
| **F5** | `reconc-F5` | `ab8a896` | Nueva baseline HEAD `6b34051`: `INPUT_CONFIG 3fcb3ae8…` / `GRAPH_SNAPSHOT 2fdda0e2…` / `FINDINGS(ENFORCE) 235f724a…` / `(OBSERVE) 693fc746…`; counts 342/90/25; deterministas y project-id-independientes; 9 digests → HISTÓRICOS; `findings_fingerprint` = LÓGICO; `test_run_fingerprint.py` 23 passed | **PASS** |
| **F6** | `reconc-F6` | `9930fc5` | R-PAR completa: A/B/C deterministas (RUN1==RUN2); **clone-drift A↔B = 0** (findings byte-idénticos `b43b548b…`); B↔C = +1 `TEST_WITHOUT_REQUIREMENT` (RW-0009) + 201 `refers_to`, 0 cambios de banda; `document_egress_bytes = 0`; `human_gate_intact = True`; D = `SKIPPED_NO_STORE` (no bloquea E2/E3-A) | **PASS** |
| **F7** | `reconc-F7` | `a9567c1` | Paquete acumulado para Devin + verificación de coherencia pre-handoff (7/7 chequeos OK en HEAD): F1 ground truth, materialize `--runs 3`, targeted 124, fingerprints F5, ledger sha — todos reproducen; ningún tag posterior invalidó una fase previa | **PASS** (auditoría acumulativa) |
| **F8** | `reconc-F8` | `4233df7` | Insumo de cruce Plan ↔ Claude Code ↔ Devin (matriz D1–D8 + 15 invariantes + 7 ítems abiertos). Adjudicado por **la mesa**: `D1..D8 = PASS`, `F7 acumulativa = PASS`, `ALL_CRITICAL_PASS = YES`, `BLOCKING_INCONSISTENCIES = 0` | **`VERDICT_F8 = PASS`** |
| **F9** | `reconc-F9` | `2a5e222` | Paquete de decisión para el gate humano (3 decisiones + precondiciones cumplidas + acciones según respuesta) | entregado |
| **F9-r1** | `reconc-F9-r1` | `d55694f` | **Cierre post-firma humana**: verificación READ-ONLY de E2/E3-A en el mecanismo gobernado (ledger + audit trail); prueba de no hand-edit | **PASS** |

Cadena lineal, sin merges. Tags históricos `reconc-F1`, `reconc-F2`, `reconc-F9` **no movidos**.

---

## 3. Modelo de auditoría aplicado

| capa | quién | qué verificó |
|---|---|---|
| **Fase a fase** | Devin (clon independiente) | Cada tag `reconc-F0..F6`: reproducir mediciones/hashes desde clon limpio. Gates relevados por Capa 9: F0..F6 = PASS. |
| **Acumulativa** | Devin | F7: re-verificación del encadenamiento F0..F6; que ningún tag posterior rompió una fase previa. |
| **Cruce** | la mesa / Claude Web | F8: comparación de tres columnas (Plan v1.1 exige ↔ Claude Code entregó ↔ Devin). `VERDICT_F8 = PASS`. |
| **Gate humano** | Capa 9 / Cesar | F9: firma de E2 y E3-A vía Mission Control. Claude Code verificó READ-ONLY. |

**Provenance de las auditorías** (registrada en `F9_HUMAN_DECISION.md §3`):
- `DEVIN` — donde efectivamente participó (F0..F7).
- `CROSS_SESSION_CLAUDE_CODE / READ_ONLY / CLEAN_CLONE` — F8 y revisiones cross-session posteriores. **No se denominan "Devin".**

---

## 4. Estado final del sistema tras F9

### 4.1 Firmas de gate (mecanismo gobernado — verificación READ-ONLY)

| gate | propuesta | confirmación humana | `decision_ref` | `target_set_hash` | evidencia | estado |
|---|---|---|---|---|---|---|
| **E2** — delta R-PAR v1↔v2 | `ARTIFACT_VERSION-2026-026` (`mission_control_ui`, 2026-09-02T00:46:43Z) | `ARTIFACT_VERSION-2026-027` (`human_confirmed`, `approved_by_id=Cesar` / "cesar may", `confirms_instance_id=-026`) | `E2-RPAR-20260831` | `e10fc3a969e22cea7396286e1babb15f56637168314318af3f5ed63af57abe30` | `docs_plan/R_PAR_DELTA_V1_V2_20260831.md` (`r_par_5: 4/4 PASS`) | **`ACTIVE` · FIRMADO** |
| **E3-A** — base canónica CLEAN | `ARTIFACT_VERSION-2026-028` (`mission_control_ui`, 2026-09-02T00:47:02Z) | `ARTIFACT_VERSION-2026-029` (`human_confirmed`, `approved_by_id=Cesar` / "cesar may", `confirms_instance_id=-028`) | `E3A-CLEANBASE-20260831` | `46758dfa79fa340eb075230831f2867e813d103ddb7ff316e553725a7de542e2` | `docs_plan/PAQUETE_GATES_HUMANOS_POST_RPAR_20260831.md` (`rw0012_claims_clean: 258` vs `prod: 595`) | **`ACTIVE` · FIRMADO** |

**Cierre F9:** `E2_READY = YES` · `E3A_READY = YES` · `E2_GATE_SIGNED = YES` · `E3A_GATE_SIGNED = YES`.

**Fundamento técnico:** `E2 = F4 PASS ∧ F5 PASS ∧ F6(A/B/C) PASS` · `E3-A = F1 PASS ∧ F2-r1 PASS ∧ F6(A/B/C) PASS`.

**Eventos en el audit trail** (`event_type = layer9_decision_recorded`, cadena de hash continua):
`entry_id` `be29ee53…` → `568b5e3a…` → `982f888c…` → `21d377a8…`;
`entry_hash` `2fe77ed4…` → `f57f1a28…` → `30e5ac24…` → `88dfb1ec…` (cada `prev_entry_hash` == `entry_hash` anterior).
`21d377a8…` (E3-A human confirm) es la última entrada del audit trail completo. `side_effects_applied = false` en las 4.

### 4.2 Baseline post-reconciliación (F5, HEAD `6b34051`, vigente)

```
counts                      REGULATORY 342 · FUNCTIONAL 90 · TECHNICAL 25
INPUT_CONFIG_FINGERPRINT    3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668
GRAPH_SNAPSHOT_FINGERPRINT  2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620
FINDINGS_FINGERPRINT        235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23  (ENFORCE)
                            693fc746e645b168386537c7dbce8c6394b582fb6c031ebf62e44189b748a368  (OBSERVE)
canonical/graph store       LIMPIOS (RW-0012 = 8 secc / 258 claims) · regenerables · deterministas (3ead7153… LOGICAL graph)
```

Manifest central: `docs_plan/reconc/VALIDATION_BASELINE_MANIFEST.json`.

### 4.3 Integridad del ledger

- F4 congeló `sha256(decisions_v2.jsonl) = 1b0c7cf82ed7b2b056aade48c7e7dfa41142b108f94dfda0d0dc9836206a4af4` (259 líneas) como baseline del arco — **0 hand-edits de Claude en F0..F9**.
- Tras las firmas E2/E3-A de F9: disco = `e6d9335405c60680bfe11c561458a7a41fcaaee87526b24a5eb3fc9e0f0dceed` (263 líneas).
- `git diff HEAD -- decisions_v2.jsonl` = `@@ -253,3 +253,11 @@` — **0 líneas borradas/modificadas, 8 añadidas** (append-only): 4 de E1-3/E1_ACCEPTANCE (pre-F0, nunca commiteadas) + 4 de E2/E3-A (F9, servicio Mission Control).
- `factory/audit/factory_audit.jsonl` (101 097 líneas) — no aparece en `git status`; F9 no lo tocó.

### 4.4 Invariantes vigentes tras F9

```
R2_READY_TO_RESUME        = NO
PILOT_EXECUTION-2026-035   = HOLD
LLM_CALLS                  = 0
PRODUCTION_ENABLEMENT      = BLOCKED
HYBRID FASE 3              = NO INICIADA
```

Ninguna firma de F9 autoriza `flip`, `qa40_adjudication` ni `production` (`not_authorized` explícito en los 4 payloads). `E2/E3-A = NO FIRMAR` fue invariante **durante** el arco; F9 fue el gate autorizado donde Capa 9 sí firmó ambos. Sin contenido de cliente en el repo público IA-LOCAL. Tags históricos no movidos.

---

## 5. Carry-forward — `NON_BLOCKING_FOLLOW_UP` (registrados en F9, no bloquean el cierre)

| # | ítem | disposición |
|---|---|---|
| 1 | 3 tests de hardening con fingerprint hardcodeado stale (`88f15b69`/`fdc29721`/`b5196a71` → `2fdda0e2`/`235f724a`/`693fc746`): `test_h4_graph_snapshot`, `test_h5f_hardening:33-34`, `test_h7_coverage_governance:21-24` | Corrección mecánica pendiente de autorización de Capa 9 (mismo tipo que `test_extraction_adequacy.py:214` en F2-r1). Consecuencia de la de-contaminación de RW-0012, no de un fix. |
| 2 | Generador de IDs `decision_store_v2.next_instance_id:189` acuña `max()` del JSONL revertible → `ARTIFACT_VERSION-2026-026..029` (E2/E3-A) **colisionan** con entradas sólo-audit-trail del 2026-08-31 (otros artefactos). Distinguibles por `decision_date` (2026-09-02), `decision_ref`, `target_set_hash`, `entry_id`. | Fix del generador → fase/decisión propia (`max()` sobre JSONL ∪ audit trail, o contador monótono). El ledger **no** se reescribe. |
| 3 | `ARTIFACT_VERSION-2026-024..028` (2026-08-31, sólo-audit-trail) `NO_RECONCILIABLE` justificada | Aceptación explícita de Capa 9. Históricos quedan en el append-only. |
| 4 | Escenario D del R-PAR (RW-0003 SAT) `SKIPPED_NO_STORE` | Capacidad nueva, no paridad. Habilitar con `rw0003_store.status = AVAILABLE` + store gobernado (`CT-WP-D-REAL` / `D-4-H9`). No condicionó E2/E3-A. |
| 5 | Commit P4 — persistir en git las líneas de servicio de `decisions_v2.jsonl` | Con OK explícito de Capa 9; nunca hand-edit. |
| 6 | Out-of-scope pre-sesión: `remediation_directive.py`, `test_remediation_directive.py`, `test_r4_t1_1v2_cold_chain_validation.py`, `test_release_decision_coverage.py` | Decisión de Capa 9 aparte. Congelados como patches en `F0_diffs/`. Ninguna fase del arco los commitea. |
| 7 | D5-D2 — autor independiente (Maria Torres ≠ Cesar) para el corpus técnico held-out | Requerido para `FINAL_QUALIFICATION` y `reportable_range != SYNTHETIC_ONLY`. Ya `DEFERRED / NON_BLOCKING_FOR_DEVELOPMENT`. |

---

## 6. Cambios de código introducidos por el arco (todos gobernados / disclosed)

| archivo | cambio | fase |
|---|---|---|
| `factory/regulatory/document_structure_extractor.py` | `_HEADING_RE` / `_TOC_ENTRY_RE`: `(\d{1,2})\s+` → `(\d{1,2})\.?\s+` (punto opcional tras el número) | F1 |
| `factory/tests/test_document_structure_extractor.py` | +3 tests (período tras número, guarda de subsección, regresión 8 secciones nivel 1) | F1 |
| `factory/regulatory/graph/build.py` | 3× `sorted()` sobre iteración de sets (`_link_chain`, `_link_to_tests`, `_link_contradictions`) — fija `attrs.via_ref` (last-write-wins por `PYTHONHASHSEED`) | F2-r1 |
| `factory/scripts/ops/materialize_stores.py` | **nuevo** — regeneración determinista de stores desde `_PDF_MAP` verificado por sha256; `logical_hash_sqlite`; `--runs`/`--apply`/`--baseline-manifest` | F2 / F2-r1 |
| `factory/tests/test_extraction_adequacy.py:214` | baseline `(342,90,26)` → `(342,90,25)` (el 26 era artefacto de la contaminación de RW-0012) | F2-r1 |
| `factory/scripts/ops/r_par_delta_v1_v2.py` | eliminado `_RW0003_DET` (`/tmp/...`); `_resolve_rw0003_store` desde manifest; `_skipped_scenario`; `_selfcheck`; import de `logical_hash_sqlite`; A fail-closed; argparse `--check`/`--dry-run-abc` | F3 |
| `docs_plan/E1_SIGNATURE_HISTORY.md` | append-only — bloques E1-3 FIRMADA + E1_ACCEPTANCE PASS | F4 |
| `docs_plan/reconc/**` | 35 artefactos de fase (reportes, manifests, ground truth, scripts de medición) | F0..F9 |

**No tocado:** prompts gobernados, validadores (no relajados), `decisions_v2.jsonl` (sólo servicio), `factory_audit.jsonl`, `fork_baseline.json`, rediseño H-1…H-10.

---

## 7. Reproducibilidad (para re-auditoría desde clon limpio)

| verificación | comando | resultado esperado |
|---|---|---|
| F1 ground truth | `PYTHONPATH=. python docs_plan/reconc/F1_measure.py` | PRE 0/8 · POST 8/8 · `GROUND_TRUTH_SHA256 = 2f7a00dc…` |
| F1 tests | `pytest -q factory/tests/test_document_structure_extractor.py` | 11 passed, 1 skipped |
| F2-r1 determinismo | `PYTHONHASHSEED=random python factory/scripts/ops/materialize_stores.py --runs 3` | `DETERMINISTA canonical: True graph: True` · graph LOGICAL `3ead7153…` |
| F2-r1 targeted | targeted v1.2 (5 archivos, 124 tests) | `124 passed` |
| F3 sin rutas efímeras | `python factory/scripts/ops/r_par_delta_v1_v2.py --check` | `SELFCHECK OK`, exit 0 |
| F5 fingerprints | `run_v2_pipeline` ×2 sobre RW-6 | `3fcb3ae8…` / `2fdda0e2…` / `235f724a…` idénticos (r1==r2) · counts 342/90/25 |
| F5 tests | `pytest -q factory/tests/test_run_fingerprint.py` | 23 passed |
| F6 R-PAR | `python factory/scripts/ops/r_par_delta_v1_v2.py` | `determinism {A,B,C}=True` · `AB_only_A/B=0` · `BC_only_C=1` · `egress=0` |
| F4 ledger | `sha256sum factory/layer9/decisions/decisions_v2.jsonl` | baseline del arco `1b0c7cf8…` (259 líneas); post-F9 `e6d93354…` (263, +4 append-only servicio) |
| F9 firmas | `grep 'ARTIFACT_VERSION-2026-02[6-9]' factory/audit/factory_audit.jsonl` | 4 eventos `layer9_decision_recorded` del 2026-09-02, cadena de hash continua |

---

## 8. Qué queda para después del arco (fuera de F0..F9)

1. **Capa 9** resuelve los 7 carry-forward (§5) — en particular autorizar la corrección mecánica de los 3 tests de hardening y decidir el fix del generador de IDs.
2. **R1.5 / R2** (track de recall del modelo, `docs_plan/ROADMAP_ANALIZADOR_GMP.md`) — el presupuesto de 20 llamadas LLM locales sigue autorizado (`AI_RUNTIME=LOCAL_ONLY`, `EXTERNAL_LLM_CALLS=0`, `DOCUMENT_EGRESS=0`) pero **`R2_READY_TO_RESUME = NO`** hasta orden explícita.
3. **`PILOT_EXECUTION-2026-035`** — `HOLD`; propuesta en `docs_plan/REVISION_CIERRE_H1_H10_Y_INSTRUCCIONES_20260901/03_*`.
4. **D5-D2** — autor independiente (Maria Torres) para el corpus técnico held-out, requerido para `FINAL_QUALIFICATION`.
5. **Firma de E2 / E3-A hecha** ✅ — lo que sigue en su rama es decisión de Capa 9 (no habilita producción por sí sola).

---

*Fin del reporte de cierre del arco F0..F9. Artefactos de detalle: `docs_plan/reconc/` (35 ficheros). Este reporte no ejecuta código, no firma nada y no reabre ninguna fase.*
