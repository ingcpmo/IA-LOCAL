# D5-D — PAQUETE DE APROBACIÓN HUMANA: ANALYZER REMEDIATION v1.2

**Fecha:** 2026-08-31 · **Gate humano:** `APPROVE_REMEDIATION_V1_2` (H1) · **Decisor:** Capa 9 (Cesar)
**Diseño:** `docs_plan/D5_D_ANALYZER_REMEDIATION_DESIGN_20260831.md`
**Diagnóstico origen:** `docs_plan/D5_D_DIAGNOSTIC_FAIL_20260831.md`

> Sin commit. Sin firma gobernada todavía. `technical_completeness_rules.yaml` lleva
> `pending_approval.approved: false`. Los HO-T-* son evidencia DIAGNÓSTICA contaminada — NO gate.

---

## 1. Archivos cambiados (exactos)

| archivo | tipo | resumen |
|---|---|---|
| `factory/regulatory/requirement_catalog/technical_completeness_rules.yaml` | artefacto gobernado (datos) | v1.1 → **v1.2**; `topic_anchor_patterns` (C03, C05), `additional_suppressor_families` (C04, C05, C09), `incidental_anchor_guard`, `family_signals.access_control_enforced`, C05 `topic_anchor` acotado; `pending_approval` |
| `factory/regulatory/findings/technical_findings.py` | motor | soporte `topic_anchor_patterns` (regex stdlib), `_incidental_anchor()`, `additional_suppressor_families` (generaliza el caso especial C09) |
| `factory/regulatory/requirement_catalog/technical_completeness_loader.py` | loader | pasa `incidental_anchor_guard` al detector |
| `factory/tests/test_completeness_rules_v1_2.py` | **nuevo** | 18 fixtures sintéticos independientes de HO-T (6 C03, 7 C05, 4 C04, 1 diagnóstico) |
| `factory/tests/test_technical_findings.py` | test (baseline) | `completeness_suppressed_family_present` 4 → 5 (una supresión correcta adicional; 7 emitidos y 0 FP intactos) |
| `factory/tests/test_extraction_adequacy.py` | test (baseline) | población técnica RW 24 → 26 (delta explicado, ver §4) |
| `factory/tests/test_run_fingerprint.py` | test (version pin) | `technical_completeness_rules.yaml` version `1.1` → `1.2` |

`NO se tocó:` `REQUIRED_BEHAVIOR`, `SOURCE_REQUIREMENT_ID`, `CONTROL_OBJECTIVE`, `scope_policy`,
comportamiento fail-closed, thresholds regulatorios, ground truth D5-A/B/C, labels QA40,
held-out expected original, `decisions_v2.jsonl`.

---

## 2. Reglas v1.1 → v1.2 (diff conceptual)

### 1A — C03 `BACKUP_RECOVERY_GAP` (causa raíz: topic_anchor léxico estrecho)
- **+ `topic_anchor_patterns`** (3 regex compuestas): OBJETO_DE_DATOS + COPIA/REPLICACIÓN/EXPORT/MIRROR/DUMP/SNAPSHOT + (PERIODICIDAD | DESTINO_EXTERNO/OFFSITE). Se OR-ean con el anchor literal.
- Reconoce "System data is copied to a network share periodically"; **no** activa con `copied` / `network` / `periodically` / "file copy" aislados.
- `emit_when` sin cambio semántico: `(literal OR pattern) AND family:restore_verified ausente`.

### 1B — C05 `AUTHORITY_CHECK_GAP` (causa raíz: discriminación de subtipo / anchor asimétrico)
- **NO** se implementó "C04 anclado → C05 automático" (son controles distintos).
- **+ `topic_anchor_patterns`** (6 regex): modelo de roles/niveles parafraseado ("named/defined/configured/N roles", "user/security/authorization roles|levels|groups", "roles are defined", "role based access", "security levels are defined").
- **`topic_anchor` acotado**: `["role based access", "control de acceso basado en roles"]` — se retiran `"authentication"`, `"login"`, `"electronic signature"`, `"access control"` a secas (mecanismo de auth ≠ modelo de autorización).
- **+ `additional_suppressor_families: [per_operation_authorization]`**: si el modelo por operación ya está descrito, C05 se suprime.
- Tokens aislados (`role`/`user`/`access`/`login`) **no** bastan.

### 3C — C04 `ACCESS_CONTROL_GAP` FP (causa raíz: token débil incidental)
- **+ `incidental_anchor_guard`** (declarativo): un token débil (`role`…) no ancla si TODAS sus ocurrencias van tras un conector de exclusión (` by `, ` including `, ` regardless of `…) Y la cláusula principal contiene un ancla FUERTE de otra familia (`audit trail`, `backup`, `retention period`, `electronic signature`…).
- **+ `family_signals.access_control_enforced`** (AND-groups, nunca un substring aislado) como supresor adicional de C04 — evidencia afirmativa de que el acceso se aplica a todos los roles.
- Se generaliza el caso especial hardcodeado de C09 → `additional_suppressor_families` (declarativo, con fallback en el motor).

---

## 3. Resultado de validación (Fases A–I)

| # | validación | resultado |
|---|---|---|
| A | targeted remediation tests (`test_completeness_rules_v1_2.py`) | **18/18 PASS** |
| B | technical-completeness tests (`test_technical_findings.py`) | **PASS** (15) — 1 baseline de conteo interno actualizado |
| C | `test_wp_e_measurement_independence.py` | **40/40 PASS** |
| D | QA40 regression (`score_emitted_review`) | precisión **1.0** [0.7008, 1.0] · 9 TP / 0 FP / 31 COVERAGE_LIMITED · **labels intactos, 0 nuevos FP** |
| E | D5-B/C scorer regression (`score_recall`) | recall **1.0** [0.7008, 1.0] · specificity **1.0** [0.2065, 1.0] · one-to-one · TN=1 · **sin cambio** (corre contra run H-10 congelado) |
| F | RW corpus regression (delta técnico) | ver §4 — `unexplained_deltas = 0` |
| G | rerun determinista (v2 pipeline ×2) | `input_config_fingerprint` + `findings_fingerprint` **idénticos** · **DETERMINISM=PASS** |
| H | delta v1.1 → v1.2 / R-PAR | ver §2 + §4 + §6.1 — grafo NO se mueve; `findings_fingerprint` sí (delta explicado) |
| I | full factory suite | **3021 passed · 12 failed · 82 skipped · 1 xfailed** (332s) — ver §6 |

`DOCUMENT_EGRESS_BYTES = 0` en todas las corridas. `llm_calls = 0`. `graph_snapshot_fingerprint`
**sin cambio** (`88f15b69…`, idéntico v1.1 ↔ v1.2). Determinismo: `findings_fingerprint` idéntico
entre corridas repetidas (e1 == e2).

---

## 4. Delta RW v1.1 → v1.2 (findings técnicos)

```
findings_added          = 3
findings_removed         = 1
findings_subtype_changed = 0
unexplained_deltas       = 0
net                      = +2   (24 -> 26 findings técnicos)
```

**Removido (1)** — precisión ↑:
- `AUTHORITY_CHECK_GAP` · RW-0006 · p.5 · "21CFRP11 21 CFR Part 11 Electronic Records, Electronic Signatures"
  — C05 v1.1 anclaba en una **línea de glosario** vía `"electronic signature"`. v1.2 retira ese término del anchor. En QA40 (D5-A) este finding estaba etiquetado **COVERAGE_LIMITED** (case `ADJ-2db49caa65`, `fnd-87da61c0074699cc`) — **no** era un TP. Ningún TP perdido.

**Añadido (3)** — recall del modelo de autorización ↑ (todos `MACHINE_INCONCLUSIVE` → revisión humana):
- `AUTHORITY_CHECK_GAP` · RW-0006 · p.16 · "Engineer security level privileges." (co-localizado con el C04 `fnd-1f93d95910fcc543` que en QA40 es TP)
- `AUTHORITY_CHECK_GAP` · RW-0012 · p.5 · "Only a user part of the Maintenance or Administrator security group is"
- `AUTHORITY_CHECK_GAP` · RW-0014 · p.5 · "Only a user part of the Maintenance or Administrator security group is"
  — C05 v1.2 ancla el modelo de roles/niveles/grupos parafraseado y, al no describirse verificación de autoridad en tiempo de operación ni autorización por operación en el scope, emite el candidato débil.

`0 nuevos ACCESS_CONTROL_GAP` en RW (C04 sigue en 2). `0` cambios en `BACKUP_RECOVERY_GAP` en RW (el respaldo de RW ya anclaba por literal). `0` cambios en clases regulatoria/funcional (342 / 90 sin cambio).

---

## 5. DIAGNOSTIC_REMEDIATION_CHECK (held-out contaminado — NO es gate)

Corrida del analizador con v1.2 sobre el corpus canónico held-out (`held_out_d5d_canonical_20260831`),
match estructural contra el ground truth congelado `125accf9…`:

| case | v1.1 (diagnóstico previo) | v1.2 (diagnóstico) |
|---|---|---|
| HO-T-001 AUDIT_TRAIL_INTEGRITY_GAP | TP | TP |
| HO-T-002 BACKUP_RECOVERY_GAP | **FN** | **TP** |
| HO-T-003 AUTHORITY_CHECK_GAP | **FN** | **TP** |
| HO-T-004 ACCESS_CONTROL_GAP | TP | TP |
| HO-T-N01 (negativo) | **FP** | **TN** |

`document_egress_bytes = 0`. Diagnóstico: recall 0.50 → **1.00**, FP-rate 1.0 → **0.0**, fabricated 0.
**Esto NO cierra D5-D.** El cierre formal exige `D5-D2` (held-out fresco, casos nuevos por la
autora independiente, secuencia de gate formal correcta). Los HO-T-* quedan
`CURRENT_HELD_OUT_REUSE_FOR_FINAL_GATE = PROHIBITED`.

---

## 6. Known failures / excepciones (12 failed en la suite completa)

### 6.1 — 4 baseline pins de `findings_fingerprint` (R-PAR de v1.2 — REQUIEREN esta aprobación)

| test | assert que falla | baseline v1.1 (pre) | v1.2 (post) |
|---|---|---|---|
| `test_h4_graph_snapshot::test_e2e_findings_fingerprint_matches_post_h1h2h3_baseline` | `findings_fingerprint == _FINDINGS_FP_BASELINE` | `b5196a71…` | `01926690…` |
| `test_h5f_hardening::test_h5f_does_not_move_findings_or_graph_fingerprint` | `findings_fingerprint == _FINDINGS_FP_BASELINE` | `b5196a71…` | `01926690…` |
| `test_h7_coverage_governance::test_e2e_observe_does_not_move_findings_or_graph` | `findings_fingerprint == _FINDINGS_FP_OBSERVE` | `b5196a71…` | `01926690…` |
| `test_h7_coverage_governance::test_e2e_enforce_is_the_governed_production_path_post_d2` | `findings_fingerprint == _FINDINGS_FP_ENFORCE` | `fdc29721…` | `3d898804…` |

- En los 4, la MISMA prueba verifica ADEMÁS `graph_snapshot_fingerprint == 88f15b69…` y **eso pasa** —
  el grafo NO se mueve. Solo se mueve `findings_fingerprint`, porque v1.2 cambia intencionalmente
  qué findings de completitud se emiten sobre RW (+3 / −1, §4). `input_config_fingerprint` también
  cambia (correcto: el artefacto gobernado pasó de v1.1 a v1.2 — `identity != resultado`, WP-A).
- **NO re-pineé estos hashes.** Codifican la identidad de salida del analizador ANTES de la
  remediation (baselines del arco H1-H10 y de D-2 ENFORCE). Re-pinearlos es exactamente lo que
  `APPROVE_REMEDIATION_V1_2` autoriza; se hace en Fase 6 (post-aprobación) y se re-corre la suite.
- Determinismo intacto: `findings_fingerprint` es idéntico entre corridas repetidas (e1 == e2).

### 6.2 — 8 fallos ambientales preexistentes (NO relacionados con v1.2)

- 4× `decisions_v2.jsonl ≠ HEAD` (`test_governance_endpoints::test_the_two_stores_stayed_independent`,
  `test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store`,
  `test_governance_signature_flow_g21::test_n13_…`, `test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store`)
  — el fichero ya estaba `M` al inicio de la sesión, antes de cualquier cambio.
- 1× `test_mission_evidence_readers::test_deployment_exists_and_health` — deployment `oos_hplc_investigator` :8102 no disponible en este entorno.
- 3× `test_new_managers::TestTestExecutionManager::{test_passing_tests,test_failing_tests}`,
  `test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas` — test-runner/corpus-runner dependientes de entorno.
- Evidencia reproducible: `docs_plan/D5_D_DIAGNOSTIC_FAIL_20260831.md` §3 y reportes de sesión previos
  (mismo conjunto de 8 que en la corrida baseline v1.1: 3007 passed / 8 failed).

### 6.3 — Regresiones NUEVAS de comportamiento

```
NEW_REGRESSIONS = 0
```
Los 3 tests de baseline actualizados en esta sesión (`test_technical_findings` conteo interno
4→5, `test_extraction_adequacy` población RW 24→26, `test_run_fingerprint` version pin 1.1→1.2)
reflejan comportamiento nuevo CORRECTO y NO relajan ningún validador: en `suite_c` siguen
asertados `completeness_emitted == 7`, `n_false_positives == 0`, `recall_now == 0.9` y todos los
gates en verde; la población RW +2 está explicada finding por finding (§4); el version pin es trivial.
Los 4 de §6.1 no se tocaron (decisión de gobernanza).

---

## 7. Decisión requerida

```
APPROVE_REMEDIATION_V1_2      -> se registra la firma gobernada de v1.2 (governance service:
                                 propose -> confirm -> authenticated identity; NO edición manual
                                 del ledger ni firma por prompt en el YAML). Luego: Fase 6
                                 (post-approval regression) -> Fase 7 (D5-D2 fresh held-out).
REJECT_REMEDIATION_V1_2       -> revertir a v1.1 (backup en scratchpad), rediseñar.
```

`document_egress = 0` · `AI_RUNTIME = LOCAL_ONLY` · `EXTERNAL_LLM_API = FORBIDDEN` ·
`PRODUCTION_ENABLEMENT = NOT_ENABLED` · `REGULATORY_COMPLIANCE = NOT_DETERMINED_BY_SYSTEM`.
