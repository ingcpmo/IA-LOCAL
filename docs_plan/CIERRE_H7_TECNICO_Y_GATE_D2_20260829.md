# H-7 — CIERRE TÉCNICO + GATE **D-2**

**Fecha:** 2026-08-29 · **Autoridad:** Capa 9 = Cesar · **Baseline de código:** HEAD `ab40f3b`.
**Diseño vigente:** `docs_plan/DISENO_H1_H10_ACTUALIZADO_R0_R5_20260829 (1).md` §H-7 (sin rediseño).
**Precede:** `docs_plan/CIERRE_H5F_H6F_20260829.md` (H-5F/H-6F = PASS).

**Estado:** `H7_TECHNICAL = PASS`. **`analysis_coverage_mode` EFECTIVO = `OBSERVE`**
(D-2 no firmado). Toda la capacidad ENFORCE está implementada y **probada**, pero **NO
activada**. Sin commit. Sin push. No se editó ningún JSONL/ledger gobernado a mano.
Marcadores mantenidos: `HUMAN_FINAL_AUTHORITY=REQUIRED`, `PRODUCTION_ENABLEMENT=NOT_ENABLED`,
`REGULATORY_COMPLIANCE=NOT_DETERMINED_BY_SYSTEM`.

---

## 1 · Qué implementa H-7 (según el diseño, sin arquitectura nueva)

| Componente | Antes | Ahora |
|---|---|---|
| **`analysis_coverage_mode`** | literal `"OBSERVE"` en 4 sitios de `v2_runtime.py` | **parámetro GOBERNADO**: `coverage_mode.resolve()` lee `requirement_catalog/analysis_coverage_mode.yaml`, lo cruza con la firma de `extraction_adequacy_thresholds.yaml`, y atestigua el modo EFECTIVO + por qué |
| **`compute_risk()` ← `evidence_basis`** | firma `(subtype, severity, gxp_impact)` | firma `(…, *, evidence_basis, coverage_status, mode)`. `mode="OBSERVE"` ⇒ salida y `as_dict()` **byte-idénticos** al histórico. `mode="ENFORCE"` ⇒ degrada la banda de los `ABSENCE_DEPENDENT` con cobertura MISSING/DEGRADED |
| **`gxp_impact` estructurado** | literal `"MEDIUM"`/`"LOW"` en 9 call-sites | `gxp_criticality.yaml` (DRAFT_UNSIGNED, 20 requisitos, LOW/MEDIUM/HIGH) + `gxp_criticality_loader.level_for()`. **Solo se consulta en ENFORCE**; en OBSERVE los literales siguen intactos |
| **Informe de dos colas** | informe único por clase | + sección "dos colas gobernadas": `ACTIONABLE_NOW` vs `BLOCKED_BY_COVERAGE_OR_EVIDENCE` (con desglose `missing_or_degraded_coverage` / `method_indeterminate` y subconjunto RW-0009). También `analysis_coverage_queues.json` + campos en `audit_metadata.json`. **Presentación aditiva en ambos modos** |

**Archivos (todos fuera del producto base):**
- Nuevos: `factory/regulatory/requirement_catalog/analysis_coverage_mode.yaml`,
  `factory/regulatory/requirement_catalog/gxp_criticality.yaml`,
  `factory/regulatory/requirement_catalog/gxp_criticality_loader.py`,
  `factory/regulatory/validation_v2/coverage_mode.py`,
  `factory/tests/test_h7_coverage_governance.py`.
- Modificados: `factory/regulatory/findings/risk.py` (params H-7 + `as_dict()` condicional),
  `factory/regulatory/validation_v2/v2_runtime.py` (resolutor de modo + `_h7_coverage_treatment` +
  sección de informe + campos de atestación),
  `factory/regulatory/validation_v2/run_fingerprint.py` (2 artefactos gobernados nuevos en `_CONSUMED`).

> **Nota de placement (no es arquitectura distinta):** la criticidad GxP va en un fichero
> gobernado *hermano* (`gxp_criticality.yaml`) en vez de un campo dentro de `requirements.yaml`,
> para no perturbar la cadena de versión/hash del catálogo. El concepto del diseño
> (criticidad estructurada → `gxp_impact`, gated por firma) se preserva íntegro.

---

## 2 · Evidencia — modo OBSERVE (lo que se envía)

Corrida E2E `run_v2_pipeline` (6 docs RW), **2 corridas idénticas**:

```
INPUT_CONFIG_FINGERPRINT   = 19d4e7d88a4d4d0ec623935e3d84b12518deaec497357f59ab8f9ab3eb8366ec   (det r1==r2)
GRAPH_SNAPSHOT_FINGERPRINT = 88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05   UNCHANGED
FINDINGS_FINGERPRINT       = b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e   UNCHANGED
findings count             = 342 reg / 90 func / 24 tech = 456                                   UNCHANGED
band distribution          = HIGH 356 · MEDIUM 72 · LOW 28                                       UNCHANGED
```

`INPUT_CONFIG_FINGERPRINT` se movió (`c5ceea38…` post-H5F → `19d4e7d8…`): módulos nuevos en
el cierre de imports del entrypoint + 2 artefactos gobernados nuevos en `_CONSUMED`. Previsto
por WP-A, determinista, ningún test fija el literal. **`FINDINGS_FINGERPRINT` y el
comportamiento analítico NO cambian** — en OBSERVE H-7 es metadata/presentación aditiva:
`compute_risk` con `mode="OBSERVE"` produce el mismo `risk` dict; `gxp_criticality.yaml` no se
consulta; las dos colas no tocan risk/severity/state.

### Dos colas (OBSERVE)

```
ACTIONABLE_NOW                     = 30
BLOCKED_BY_COVERAGE_OR_EVIDENCE    = 426
  ├─ missing_or_degraded_coverage  = 78    (== would_degrade_true; R-1 N-3, afinado en H-7)
  └─ method_indeterminate          = 348   (INDETERMINATE: juicio semántico fuera de alcance)
       └─ RW-0009 subset           = 57    (REGULATORY_INCONCLUSIVE, doc NOT_ANALYZABLE; R-5)
Total 30 + 426 = 456   → totals_coherent = true
enforce_effect.findings_degraded  = 0     (OBSERVE nunca degrada)
```

---

## 3 · Evidencia — modo ENFORCE (implementado y probado; **NO** activado)

Ejecutado con `extraction_adequacy_thresholds.yaml: status SIGNED` **y**
`analysis_coverage_mode.yaml: mode ENFORCE + firma` (ambos vía override de test; los ficheros
del repo quedaron restaurados a OBSERVE/DRAFT_UNSIGNED). 2 corridas idénticas:

```
analysis_coverage_mode (efectivo)  = ENFORCE
enforce_effect.findings_degraded   = 78    == would_degrade_true   ✓ "degrada EXACTAMENTE los 78"
enforce_effect.band_actually_lowered = 70  (los otros 8 ya estaban en banda LOW; la regla igual aplica)
FINDINGS_FINGERPRINT               = fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d   (det r1==r2)
INPUT_CONFIG_FINGERPRINT           = 9edf4bc16be22483b7d5ff55efd62eaf98fb1c5dd39b1216c49abedf1869279b
GRAPH_SNAPSHOT_FINGERPRINT         = 88f15b69…  (sin cambio — el grafo no depende del modo)
band distribution (ENFORCE)        = HIGH 354 · MEDIUM 22 · LOW 78 · CRITICAL 2
```

- **`FINDINGS_FINGERPRINT` cambia** (`b5196a71…` → `fdc29721…`): previsto por el diseño
  (`REQUALIFICATION_REQUIRED = SÍ`; `evidence_basis`/`risk` son campos semánticos). Determinista.
- **Criticidad distinta ⇒ banda distinta**: `compute_risk("REGULATORY_GAP","MAJOR","LOW")` →
  `MEDIUM`; con `"HIGH"` → `HIGH`. En ENFORCE aparecen 2 findings en `CRITICAL` (gxp HIGH sube
  el score) que en OBSERVE no existen, y 50 bajan de MEDIUM/HIGH a LOW por la degradación.
- La cola `method_indeterminate` (incl. RW-0009) **no se degrada** — INDETERMINATE ya es
  límite de método; `compute_risk` ENFORCE solo toca `ABSENCE_DEPENDENT` + MISSING/DEGRADED.

---

## 4 · Tests + regresión

- `factory/tests/test_h7_coverage_governance.py`: **17 passed** (resolutor de modo · fail-safe
  con doble firma · criticidad · `compute_risk` OBSERVE inerte / ENFORCE degrada / respeta
  PRESENCE·OK·INDETERMINATE · E2E OBSERVE fingerprint-neutral · E2E ENFORCE degrada exactamente 78).
- Regresión dirigida (H-7 + risk + validation_v2 + v2_endpoints + run_fingerprint + wp_e +
  adequacy + status_risks + release_coverage): **181 passed**.
- Regresión completa `pytest factory/tests/`: **`4 failed · 2999 passed · 79 skipped · 1 xfailed (321s)`**.
  Fallos = subconjunto de los **5 EXC históricos aceptados**. `NEW_REGRESSIONS = 0`.
  Suite exit ≠ 0 ⇒ **NO se llama GREEN**.
- `QA40_CHANGED = NO` (SHA `02b6d3d0…`, receta = `sha256('\n'.join(finding_id en orden de
  muestra))` — verificado). `AUDIT_TRAIL_CHANGED_BY_TESTS = NO`. `REVIEW_QUEUE_CHANGED_BY_TESTS = NO`.

```
H7_TECHNICAL   = PASS
NEW_REGRESSIONS = 0
```

---

## 5 · GATE **D-2** — decisión de Capa 9

**Qué se pide firmar** (habilitar ENFORCE). Requiere **las tres**:

| # | Artefacto | Cambio a firmar | Efecto |
|---|---|---|---|
| D-2.1 | `factory/regulatory/requirement_catalog/extraction_adequacy_thresholds.yaml` | `status: DRAFT_UNSIGNED` → **`SIGNED`** + firmante real | Los verdicts de adecuación (`ANALYZABLE/DEGRADED/NOT_ANALYZABLE`) pasan a ser usables como gate |
| D-2.2 | `factory/regulatory/requirement_catalog/analysis_coverage_mode.yaml` | `mode: OBSERVE` → **`ENFORCE`** + `decided_by`/`decision_ref`/`decision_date` | El runtime deja de forzar OBSERVE |
| D-2.3 | `factory/regulatory/requirement_catalog/gxp_criticality.yaml` | `status: DRAFT_UNSIGNED` → **`SIGNED`** + revisar los 20 niveles LOW/MEDIUM/HIGH propuestos (§tabla en el YAML) | `gxp_impact` se deriva de la criticidad estructurada en vez de los literales |

Si falta cualquiera, el runtime **sigue en OBSERVE** (fail-safe, atestiguado en
`analysis_coverage_mode_attestation.downgrade_reason`).

### Umbrales propuestos (para la revisión)

- **Regla de degradación (ENFORCE):** un finding se degrada **una banda** (`CRITICAL→HIGH→
  MEDIUM→LOW`, suelo LOW) **si y solo si** `evidence_basis == ABSENCE_DEPENDENT` **y**
  `coverage_status ∈ {MISSING, DEGRADED}` (es decir, exactamente `would_degrade = true`).
  No se suprime ningún finding, no se cambia `machine_state`/`human_state`, no se cierra nada.
- **`gxp_impact_weights`** (de `risk_matrix.yaml`, sin cambio): `HIGH→3 · MEDIUM→2 · LOW→1`.
- **Niveles de criticidad propuestos** (`gxp_criticality.yaml`, DRAFT): HIGH para audit trail
  (11.10(e)/ANNEX11_9), control de acceso (11.10(d)/ANNEX11_12), authority checks (11.10(g)),
  firma electrónica (11.50/11.70), validación (11.10(a)), almacenamiento/protección (ANNEX11_7.1),
  211.68(b), y ALCOA Attributable/Original/Accurate/Complete. MEDIUM para el resto. `default = MEDIUM`
  (equivalente al literal actual).

### Consecuencias

| | **APPROVE** (firmar D-2.1+D-2.2+D-2.3) | **REJECT** (mantener OBSERVE) |
|---|---|---|
| `analysis_coverage_mode` efectivo | `ENFORCE` | `OBSERVE` (sin cambio) |
| `FINDINGS_FINGERPRINT` | `b5196a71…` → **`fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d`** | `b5196a71…` (intacto) |
| `INPUT_CONFIG_FINGERPRINT` | → `9edf4bc16be22483b7d5ff55efd62eaf98fb1c5dd39b1216c49abedf1869279b` | `19d4e7d8…` (el de H-7 OBSERVE) |
| Findings degradados una banda | **78** (regla aplicada) — **70** con banda numéricamente más baja | 0 |
| Distribución de bandas | HIGH 354 · MEDIUM 22 · LOW 78 · CRITICAL 2 | HIGH 356 · MEDIUM 72 · LOW 28 |
| Re-calificación | **requerida** (cambia `findings_fingerprint`; documentar antes/después) | no aplica |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `88f15b69…` (sin cambio) | `88f15b69…` |
| Remediación / QA40 / estados | sin cambio de conteo; QA40 se re-muestrea **solo** si Capa 9 lo decide (razón gobernada) | sin cambio |
| Rollback | `mode: OBSERVE` en el YAML (o revertir la firma) — vuelve a OBSERVE sin cambios de código | n/a |

**Recomendación de ingeniería:** *sin recomendación de habilitar/no habilitar* — es una
decisión de gobernanza. Lo que ingeniería confirma: (a) la capacidad técnica funciona y es
determinista en ambos modos; (b) OBSERVE no altera nada; (c) ENFORCE degrada **exactamente**
los 78 `would_degrade`, sin suprimir findings ni tocar el gate humano; (d) los umbrales de
adecuación siguen siendo **HEURÍSTICAS DRAFT** — firmarlos es afirmar que son aptos como gate GMP.

---

## 6 · Campos de cierre

```
H7_TECHNICAL                     = PASS
NEW_REGRESSIONS                  = 0
ANALYSIS_COVERAGE_MODE_EFFECTIVE = OBSERVE   (D-2 no firmado)
ENFORCE_IMPLEMENTED_AND_TESTED   = YES  (no activado)

FINDINGS_FINGERPRINT (OBSERVE)   = b5196a7177c92a913de638637a071d2027a78eb1b9f1233d814812d3ff6dc21e   (== baseline, consistente)
GRAPH_SNAPSHOT_FINGERPRINT       = 88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05   (determinista)
INPUT_CONFIG_FINGERPRINT (OBSERVE) = 19d4e7d88a4d4d0ec623935e3d84b12518deaec497357f59ab8f9ab3eb8366ec   (movido por código en cierre de imports; determinista; no regresión)

FINDINGS_FINGERPRINT (ENFORCE, proyectado) = fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d

QA40_CHANGED                     = NO
AUDIT_TRAIL_CHANGED_BY_TESTS     = NO
REVIEW_QUEUE_CHANGED_BY_TESTS    = NO
PRODUCT_BASE_CHANGED             = NO

GATE                             = D-2  (pendiente de Capa 9)
```

**STOP en D-2.** No se activa ENFORCE. No se continúa a H-8. No se firma ningún artefacto.
No commit, no push.
