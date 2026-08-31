# CIERRE D-2 + TRANSICIÓN GOBERNADA DE H-7 A ENFORCE

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Baseline de código:** HEAD `ab40f3b`.
**Alcance:** exclusivamente cerrar **D-2** y la transición de H-7 a `ENFORCE`. No se re-hace
H-1…H-7 técnico. Sin commit, sin push, sin tocar producto base. Marcadores mantenidos:
`HUMAN_FINAL_AUTHORITY=REQUIRED` · `PRODUCTION_ENABLEMENT=NOT_ENABLED` ·
`REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM`.

---

## 0 · Inspección de tests (contenido EFECTIVO, no diff visual)

### `factory/tests/test_h7_coverage_governance.py`

| Comprobación | Resultado |
|---|---|
| ¿Algún test de **configuración productiva** asevera a la vez `requested_mode == OBSERVE` y `== ENFORCE`? | **NO.** `test_mode_defaults_to_observe` opera sobre un YAML **temporal** (`cm.resolve(p)` con `p` en `tmp_path`) — es un test de MECANISMO del resolutor. `test_production_mode_config_is_enforce_post_d2` opera sobre la **config real** (`cm.resolve()` sin argumento) y asevera `ENFORCE`. Blancos distintos, sin contradicción. |
| `test_e2e_enforce_is_the_governed_production_path_post_d2` | **Sin `tmp_path`, sin `monkeypatch`** (firma `def …()` vacía). Asevera `cm.resolve()["effective_mode"] == "ENFORCE"` sobre la config REAL del repo, sin simular. Usa `tempfile.mkdtemp` sólo como `report_base` (directorio de salida, no override de config). ✔ correcto. |
| Tests históricos de OBSERVE (`_observe_audit`) | Usan `pytest.MonkeyPatch()` + YAML temporal `mode: OBSERVE` **sólo** para reproducir la baseline histórica `b5196a71…`, con `mp.undo()` en `finally`. Permitido por la instrucción. |

**Sin inconsistencias.** No se modificó este fichero en esta pasada.

### `factory/tests/test_h4_graph_snapshot.py`

| Comprobación | Resultado |
|---|---|
| Fixture `_two_runs` fuerza OBSERVE para la baseline H-4 `b5196a71…` (H-4 se aceptó en OBSERVE; su criterio grafo↔findings no depende del modo) | Correcto en intención. **Defecto corregido:** `_mp.undo()` estaba **fuera** de `try/finally` → si `run_v2_pipeline` lanzaba, el override OBSERVE se filtraba a toda la sesión. **Fix aplicado:** las 2 corridas van dentro de `try:` y `_mp.undo()` en `finally:`. (Es la única corrección introducida por esta transición.) |

---

## 1 · D-2 registrado por el mecanismo gobernado

`decision_store_v2.append_record` (NO edición manual de `decisions_v2.jsonl`):

| Registro | Detalle |
|---|---|
| **`ARTIFACT_VERSION-2026-019`** (ORIGINAL) | `family=ARTIFACT_VERSION` · `type=ORIGINAL` · `decision=APPROVE` · `decision_origin=human_confirmed` · `resolved_target_ids` = los 3 YAML · `target_set_hash=b5072546…` · `provenance=NATIVE` · `payload.decision_ref=D-2-H7-20260830` |
| **`ARTIFACT_VERSION-2026-020`** (CORRECTION, `seq=1`, `supersedes=…-019`) | **corrige la identidad del decisor**: `approved_by_id "cesar"` (texto libre) → **`"Cesar"`** — forma canónica del `identity_registry` (`load_registry().values() = {Andrea_Reviewer, Cesar}`), validada por `identity_policy.validate_identity`. El acto de gobernanza y su alcance **no cambian**. |

`project_status`: `…-019 = SUPERSEDED`, `…-020 = ACTIVE`. Cadena de decisión válida
(`validate_record` sin violaciones en la cadena D-2). Cada `append_record` emitió su evento
`layer9_decision_recorded` en la cadena de auditoría (`side_effects_applied=false`).

### Artefactos firmados (D-2.1 / D-2.2 / D-2.3)

| Artefacto | Estado |
|---|---|
| `extraction_adequacy_thresholds.yaml` | `status: SIGNED` |
| `analysis_coverage_mode.yaml` | `mode: ENFORCE` + `decided_by/decision_ref/decision_date` |
| `gxp_criticality.yaml` | `status: SIGNED` + `decided_by/decision_ref/decision_date` |

---

## 2 · Verificación directa desde loaders/runtime (sin monkeypatch)

```
requested_mode          = ENFORCE
effective_mode          = ENFORCE
thresholds_signed       = true          (extraction_adequacy.is_signed())
mode_config_signed      = true          (coverage_mode.resolve())
gxp_criticality_signed  = true          (gxp_criticality_loader.is_signed())
decision_ref            = D-2-H7-20260830
downgrade_reason        = None
```

---

## 3 · Validación H-7 ENFORCE — 2 corridas frescas independientes del corpus RW-6 (sin monkeypatch del modo)

| | D2V1 | D2V2 |
|---|---|---|
| `analysis_coverage_mode` (efectivo) | ENFORCE | ENFORCE |
| `findings_degraded` | **78** | **78** |
| `findings_suppressed` | **0** | **0** |
| `total_findings` | **456** (342/90/24) | **456** |
| `human_gate_intact` | **true** | **true** |
| `forbidden_states_present` | false | false |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05` | idéntico |
| `FINDINGS_FINGERPRINT` | `fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d` | idéntico |
| `INPUT_CONFIG_FINGERPRINT` | `3c8b0036107b824f0919dafba3bc7ebb12f3ec9af62be973e934cc8cc889fcaf` | idéntico |

`DETERMINISTIC_RUNS = PASS` (los tres fingerprints idénticos entre D2V1 y D2V2).
`GRAPH_SNAPSHOT_FINGERPRINT` y `FINDINGS_FINGERPRINT` **coinciden con los valores comprometidos**
en el paquete D-2.

---

## 4 · Tests y regresión

- Dirigidos (`test_h7_coverage_governance` · `test_h4_graph_snapshot` · `test_findings_risk` ·
  `test_run_fingerprint` · `test_extraction_adequacy` · `test_validation_v2` ·
  `test_wp_e_measurement_independence` · `test_wp_g_mission_control_panel` ·
  `test_decision_migration` · `test_decision_model_v2`): **224 passed**.
- `pytest factory/tests/` completo: **`8 failed · 2995 passed · 79 skipped · 1 xfailed (322s)`**.

### EXC históricas aceptadas (reportadas por separado)

```
EXC-1..5 (entorno / servicios en vivo):
  test_corpus_runner::test_plan_corpus_units_real_reproduce_d4a_232_llamadas
  test_governance_ui_deploy_consistency_live::test_deploy_freshness_all_source_routes_are_live
  test_mission_evidence_readers::test_deployment_exists_and_health
  test_new_managers::TestTestExecutionManager::{test_passing_tests, test_failing_tests}
EXC-6..9 (registro D-2 en decisions_v2.jsonl sin commit -> guards `store == git HEAD`; AUTO-CLEAR al commitear):
  test_governance_endpoints::test_the_two_stores_stayed_independent
  test_artifact_version_signing::test_no_test_in_this_file_wrote_to_the_real_store
  test_governance_signature_flow_g21::test_n13_no_test_in_this_file_touched_the_real_store
  test_resignature_g2prime::test_no_test_in_this_file_wrote_to_the_real_store
```

```
NEW_REGRESSIONS               = 0   (vs baseline aceptada 9-EXC)
QA40_CHANGED                  = NO   (SHA 02b6d3d0…; el direccionamiento por finding_id/finding_record_id no depende de la banda de riesgo)
AUDIT_TRAIL_CHANGED_BY_TESTS  = NO   (los eventos layer9_decision_recorded son de la DECISIÓN real, no de tests)
REVIEW_QUEUE_CHANGED_BY_TESTS = NO
```

La suite completa termina con **exit code ≠ 0** (EXC aceptadas) → **NO se llama GREEN/PASS**.

---

## 5 · Campos de cierre

```
D2                          = PASS
D2_GOVERNED_RECORD          = YES   (ARTIFACT_VERSION-2026-019 ORIGINAL + -2026-020 CORRECTION; decisor 'Cesar' del identity_registry)

THRESHOLDS_SIGNED           = true
COVERAGE_MODE               = ENFORCE
GXP_CRITICALITY_SIGNED      = true
DECISION_REF                = D-2-H7-20260830

FINDINGS_DEGRADED           = 78
FINDINGS_SUPPRESSED         = 0

INPUT_CONFIG_FINGERPRINT    = 3c8b0036107b824f0919dafba3bc7ebb12f3ec9af62be973e934cc8cc889fcaf   (baseline post-D-2, determinista)
GRAPH_SNAPSHOT_FINGERPRINT  = 88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05
FINDINGS_FINGERPRINT        = fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d

DETERMINISTIC_RUNS          = PASS
NEW_REGRESSIONS             = 0

H7                          = CLOSED
READY_FOR_H8                = YES
```

Referencia OBSERVE preservada (rollback): con `mode: OBSERVE` en el YAML el runtime vuelve a
`FINDINGS_FINGERPRINT = b5196a71…` sin cambios de código.

Continúa automáticamente a **H-8** (instrumento de evidencia real). STOP obligatorio en **D-5**.
