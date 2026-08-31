# R-PAR — VALIDACIÓN DE PARIDAD E IMPACTO ANALÍTICO V1 ↔ V2

**Fecha:** 2026-08-31 · **Autoridad:** Capa 9 = Cesar · **Tipo:** validación **READ-ONLY**.
**Baseline de código:** HEAD `ab40f3b` (working tree actual, con los cambios de H-10).
**Sin commit, sin push, sin flip de `_EXT_VER`/`_CANON`/`_GRAPH`, sin activar producción.**
Ningún store real modificado (verificado, §10). Evidencia cruda: `docs_plan/_r_par/R_PAR_RAW.json`
+ `docs_plan/_r_par/findings_{A,B,C,D}.json`. Script: `factory/scripts/ops/r_par_delta_v1_v2.py`.

**R-PAR es únicamente evidencia para decisión humana.** No decide activación, no declara
qualification, no produce recomendaciones GMP.

---

## 0 · Los cuatro escenarios (config común, §2)

Corpus de paridad (6 documentos, idéntico en A/B/C): `RW-0005 · RW-0006 · RW-0009 · RW-0011 ·
RW-0012 · RW-0014`. `SAME_CURRENT_HEAD=YES` · `SAME_GOVERNED_CONFIG=YES` ·
`SAME_COVERAGE_MODE=ENFORCE` · `SAME_REQUIREMENT_CATALOG=YES` · `SAME_RISK_CONFIG=YES`.

| Esc. | Fuente canonical | `V2_TEST_EXTRACTION` | RW-0003 | n_findings | INPUT_CONFIG_FP | GRAPH_SNAPSHOT_FP | FINDINGS_FP |
|---|---|---|---|---|---|---|---|
| **A** V1 PROD | `canonical_store/` de producción (copiado a /tmp, READ-ONLY) | OFF | no | **456** | `f5ed21cf…` | `88f15b69bf2cea9a09d5a179300496d3685b18c58c1adb1dfa601f191b73ae05` | `fdc29721e9566dfea6f4969c74c2324f348fc00827ccbd36e35730deb512f08d` |
| **B** V1 CLEAN | re-extracción fresca HEAD | OFF | no | **456** | `f5ed21cf…` | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` | `926986c5f17c9bfb223522d295c53fb335964f9f8f951b612aa7044ba1d6d847` |
| **C** H10 CLEAN | re-extracción fresca HEAD | **ON** | no | **457** | `f5ed21cf…` | `547157d6447fbefa3ccffdde3d809d57266c2e90cc20d0a12d748fbbed2d7732` | `ec4c5a7dd39cac9a35baa2961469687ecdfd537b8fcceef86b10b9755c0d9cb3` |
| **D** H10 + SAT | C + `RW-0003` (canonical ingerido determinista, copiado) | **ON** | **sí** | **674** | `0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f` | `8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4` | `2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f` |

> **Hallazgo de reconciliación (§8):** el escenario **A** (canonical de producción + código HEAD
> actual, corrida FRESCA) reproduce **EXACTAMENTE** los fingerprints de la **baseline D-2**
> (`GRAPH_SNAPSHOT 88f15b69…`, `FINDINGS fdc29721…`). → La baseline D-2 **no estaba obsoleta ni
> era incorrecta**: es lo que el código HEAD produce sobre el `canonical_store` de producción.
> Toda la diferencia D-2 ↔ H-10-v2 se descompone limpiamente en A→B (clone-drift) + B→C (H-10
> puro) + C→D (RW-0003).

> **`INPUT_CONFIG_FINGERPRINT` A = B = C** (`f5ed21cf…`): sólo depende de los sha de los PDFs
> de entrada + identidad estática del código + `_EXT_VER` literal. **No ve el contenido del
> canonical** — por eso A y B lo comparten pese a 3 267 vs 2 930 claims. D difiere porque
> añade un documento (RW-0003).

### 4 · Determinismo

```
A_DETERMINISTIC = YES   (input_config / graph_snapshot / findings / n_findings idénticos entre rep 1 y rep 2)
B_DETERMINISTIC = YES
C_DETERMINISTIC = YES
D_DETERMINISTIC = YES
```
(D: el canonical de RW-0003 es un artefacto determinista ya verificado; no se re-OCR-izó.)

---

## 1 · A ↔ B — CLONE DRIFT (efecto del estado histórico del canonical)

```
n_A = 456        n_B = 456                       (conteo TOTAL idéntico)
matched_by_finding_record_id = 418
matched_by_semantic_fallback = 3   (document + class/subtype + criterion + requirement_id + source_hash)
only_in_A = 35     only_in_B = 35
in_both_same_band = 418     in_both_band_changed = 0
evidence_basis_changed = 0     coverage_status_changed = 0
```

**Localización del drift — 100 % en RW-0012:**

| | A (V1 PROD) | B (V1 CLEAN) |
|---|---|---|
| RW-0012 claims | **595** | **258** |
| claims totales (6 docs) | 3 267 | 2 930 |
| `section` (nodos) | 45 | 40 |
| `designed_by` (aristas) | 204 | 190 |
| páginas de los `only_in_*` | pág 5 (24) + **pág 18 (1, inexistente)** | pág 5 (18) + pág 1 (4) + pág 14 (2) + pág 4 (1) |

Los otros 5 documentos (RW-0005/0006/0009/0011/0014) tienen **claims idénticos** en A y B.

**`disappearance_reason` de los 35 (38 por `finding_record_id` puro, 35 tras fallback semántico):**

```
CLONE_DRIFT            = 38  (clasificación conservadora: RW-0012 prod tiene 595 claims — con
                              páginas fantasma 17/18 en un doc de 14 y sobre-segmentación de la
                              pág 5 — que anclan las MISMAS ~35 conclusiones regulatorias en
                              claims distintos; al menos 1 finding de A está en la pág 18 inexistente)
SOURCE_STATE_DIFFERENCE = 0
IDENTITY_CHANGE         = 0
UNEXPLAINED             = 0     -> NO STOP (§5)
```

**Interpretación (conservadora):** el clone-drift es un **re-anclaje de provenance** sobre la
página 5 de RW-0012, **no una divergencia analítica**. El conjunto de conclusiones se
preserva: mismo número (35), mismo documento, misma familia de subtipos
(`REGULATORY_INCONCLUSIVE` ×34 + `ALCOA_ATTRIBUTABLE_GAP` ×1), **misma banda (HIGH) en los 35**,
0 cambios de banda / evidence_basis / coverage_status en los 418 emparejados. La re-extracción
LIMPIA ancla en páginas reales (la de producción ancla parcialmente en la pág 18 inexistente),
i.e. la ruta limpia es **más correcta**, no peor.

`A_vs_B_CLONE_DRIFT` : **caracterizado**. `MATERIAL_REGRESSION (A↔B) = NO`.

---

## 2 · B ↔ C — EFECTO PURO DE H-10 (mismo canonical limpio, sólo cambia el flag)

```
n_B = 456     n_C = 457
only_in_B = 0
only_in_C = 1     -> RW-0009 · TEST_WITHOUT_REQUIREMENT · band LOW · evidence_basis=ABSENCE_DEPENDENT ·
                     coverage_status=MISSING · machine_state=MACHINE_DEVIATION_CANDIDATE · human_state=UNREVIEWED ·
                     anclado (source_hash 42032c59…) — hallazgo legítimo: el único Test de RW-0009 no traza a requisito
in_both_same_band     = 456
in_both_band_changed  = 0
evidence_basis_changed = 0
coverage_status_changed = 0
```

**Grafo (B → C):**

| relación / nodo | B | C |
|---|---|---|
| `implemented_by` | 1120 | **1120** (0 regresión) |
| `designed_by` | 190 | **190** (0 regresión) |
| `tested_by` | 0 | 0 *(RW-6 no tiene SAT analizable; RW-0009 es transmittal)* |
| `verifies` | 0 | 0 |
| `refers_to` | 0 | **348** |
| `contradicts` / `supports` | 0 / — | 0 / — *(NO modificados)* |
| nodos `system_component` | 0 | **45** |
| nodos `actor` | 0 | **13** |
| nodos `test` | 0 | **1** |
| tablas con rol semántico | 97 (28/29/0/10/16/14 por doc) | **97 (idéntico)** |

`system_component`/`actor` por documento (C): RW-0005 17/4 · RW-0006 11/4 · RW-0009 2/0 ·
RW-0011 7/2 · RW-0012 5/1 · RW-0014 3/2. Todos por mención literal + diccionario cerrado + provenance.

**Interpretación:** el efecto puro de H-10 sobre el corpus de paridad es **estrictamente
ADITIVO**: +1 hallazgo legítimo, +348 aristas `refers_to`, +58 nodos de entidad, +1 nodo test.
**0 hallazgos eliminados · 0 cambios de banda · 0 cambios de evidence_basis · 0 cambios de
coverage_status · 0 regresión en `implemented_by`/`designed_by` · `contradicts`/`supports`
intactos.** El clone-drift (§1, sólo RW-0012 pág 5) y el efecto H-10 (§2, aditivo, no toca
RW-0012) están **completamente separados**.

`B_vs_C_H10_EFFECT` : **caracterizado**. `MATERIAL_REGRESSION (B↔C) = NO`.

---

## 3 · C ↔ D — BENEFICIO ADITIVO DE RW-0003 (SAT real)

**Esta comparación NO se usa para declarar paridad. Cuantifica el beneficio adicional del SAT real.**

```
TEST_OBJECTS_ADDED   = 165    (todos de RW-0003, tablas de ejecución, provenance completa)
TESTED_BY_ADDED      = 17     (RW-0006→RW-0003: 6 · RW-0005→RW-0003: 11 · via refs reales 3.2.3 y F05.05)
VERIFIES_ADDED       = 0      (N/A: el SAT cita refs de proyecto/función, no ids del catálogo regulatorio)
REFERS_TO_ADDED      = 2      (350 total en D vs 348 en C — 2 entidades más ancladas desde RW-0003)
TABLES_ADDED         = 199    (docling)
TABLE_ROLES_ADDED    = 194    (map_column_roles determinista sobre las tablas docling)
```

**Findings C → D:**

```
n_C = 457     n_D = 674
only_in_C  = 2     -> RW-0006 · REQUIREMENT_NOT_TESTED · band LOW   (rec-738efaf1… , rec-c4eb93ac…)
                     === RESUELTOS: al añadir RW-0003, sus casos de prueba trazan a 2 requisitos
                     URS previamente marcados como NO PROBADOS (via las aristas tested_by).
only_in_D  = 219  (TODOS en RW-0003):
                     57  REGULATORY_INCONCLUSIVE   (band HIGH)   -> análisis Tier-1 del SAT (documento antes NO analizado)
                     162 TEST_WITHOUT_REQUIREMENT  (band LOW)    -> casos SAT sin id de requisito recuperable en el OCR
in_both_band_changed = 0
```

**REQUIREMENT_NOT_TESTED (RW-6):**  B = 70 · C = 70 · **D (sólo RW-6) = 68**  → **−2 RESUELTOS**.
**ORPHAN_DESIGN_ELEMENT (RW-6):**   C = 8 · D (sólo RW-6) = 8  → sin cambio.

**Colas de cobertura (`analysis_coverage`, ENFORCE):**

| | A | B | C | D |
|---|---|---|---|---|
| `ACTIONABLE_NOW` | 30 | 30 | 30 | **38** (+8) |
| `BLOCKED_BY_COVERAGE_OR_EVIDENCE` | 426 | 426 | 427 | **636** |
| ├ `missing_or_degraded_coverage` | 78 | 78 | 79 | 231 |
| └ `method_indeterminate` | 348 | 348 | 348 | 405 |
| `rw0009_subset_count` | 57 | 57 | 58 | 58 |

**Cada cambio, con causa y evidencia:**

| CHANGE | CHANGE_REASON | SOURCE_EVIDENCE |
|---|---|---|
| `only_in_C` −2 (RW-0006 REQUIREMENT_NOT_TESTED resueltos) | El SAT real aporta casos de prueba que citan `3.2.3` / `F05.05`, generando `tested_by` hacia esos requisitos → dejan de emitirse como no probados | `tested_by` RW-0006/RW-0005 → RW-0003 ; RW-0003 págs 157/158/192 ; `finding_record_id` rec-738efaf1…, rec-c4eb93ac… |
| `only_in_D` +57 `REGULATORY_INCONCLUSIVE` | RW-0003 pasa de `NOT_ANALYZABLE` (100 % imagen) a analizado (OCR docling) → Tier-1 emite sus sub-criterios inconcluyentes como en cualquier documento nuevo | `regulatory_tier1` sobre RW-0003 ; 57 findings HIGH con ancla + página + source_hash |
| `only_in_D` +162 `TEST_WITHOUT_REQUIREMENT` (LOW) | 162 de los 165 casos SAT recuperados no contienen un id de requisito recuperable en el texto OCR → el analizador los hace VISIBLES como cobertura de prueba sin traza | `functional` sobre los 165 Test de RW-0003 ; `evidence_basis=ABSENCE_DEPENDENT`, `coverage_status` degradado |
| `ACTIONABLE_NOW` +8 | 8 findings de RW-0003 no dependen de cobertura ni de evidencia ausente | cola `ACTIONABLE_NOW` de D |
| `BLOCKED` +209 | 162 TEST_WITHOUT_REQUIREMENT (ABSENCE_DEPENDENT) + 57 REGULATORY_INCONCLUSIVE de RW-0003 | `by_reason` de D: +152 missing/degraded, +57 method_indeterminate |

**NO se llama automáticamente "mejora" al aumento de findings.** Desglose:
- **Mejora analítica real (pequeña, verificable):** −2 `REQUIREMENT_NOT_TESTED` resueltos con
  evidencia de prueba real.
- **Extensión de cobertura:** RW-0003 pasa de no analizado a analizado (57 findings regulatorios).
- **Nueva visibilidad (requiere juicio humano):** 162 `TEST_WITHOUT_REQUIREMENT` — puede ser
  limitación del OCR, o el SAT referenciando tags/funciones y no ids de catálogo. `RR-1` aplica.

`C_vs_D_RW0003_ADDITIVE` : **caracterizado**. `MATERIAL_REGRESSION (C↔D) = NO`.

---

## 5 · ANALYSIS_DIFF / REPORT_DIFF (mismos artefactos en A/B/C/D)

Los 4 escenarios generaron los mismos artefactos: `regulatory_findings.json` ·
`functional_findings.json` · `technical_findings.json` · `analysis_coverage.json` ·
`analysis_coverage_queues.json` · `evidence_provenance.json` · `audit_summary/audit_metadata.json` ·
`graph_snapshot/graph_snapshot.json` · `informe_hallazgos_v2.md` · `manifest.json` + `SHA256SUMS`.

```
REPORT_A_V1_PROD       : 456 findings · ACTIONABLE_NOW 30 · BLOCKED 426 · REQUIREMENT_NOT_TESTED 70 · ORPHAN_DESIGN_ELEMENT 8
REPORT_B_V1_CLEAN      : 456 findings · ACTIONABLE_NOW 30 · BLOCKED 426 · REQUIREMENT_NOT_TESTED 70 · ORPHAN_DESIGN_ELEMENT 8
REPORT_C_H10_CLEAN     : 457 findings · ACTIONABLE_NOW 30 · BLOCKED 427 · REQUIREMENT_NOT_TESTED 70 · ORPHAN_DESIGN_ELEMENT 8
                         + refers_to 348 · +45 system_component · +13 actor · +1 test
REPORT_D_H10_PLUS_SAT  : 674 findings · ACTIONABLE_NOW 38 · BLOCKED 636 · REQUIREMENT_NOT_TESTED (RW-6) 68 · ORPHAN_DESIGN_ELEMENT 8
                         + tested_by 17 · TEST_OBJECTS 165 · TABLES 199 (194 con rol)
```

### FINDINGS_DELTA

| | A→B | B→C | C→D |
|---|---|---|---|
| added | 35 (re-ancladas RW-0012) | 1 (`TEST_WITHOUT_REQUIREMENT` RW-0009) | 219 (todas RW-0003) |
| removed | 35 (re-ancladas RW-0012) | 0 | 2 (`REQUIREMENT_NOT_TESTED` RW-0006 RESUELTOS) |
| band changed | 0 | 0 | 0 |
| class de las added | RegulatoryFinding 34 / DataIntegrityFinding 1 | TestCoverageFinding 1 | RegulatoryFinding 57 / TestCoverageFinding 162 |

### RISK_DELTA

`band_changed = 0` en A→B, B→C y C→D. `enforced_degraded` / `band_pre_enforce` sin novedad
(ENFORCE efectivo en los 4; `findings_suppressed = 0` en todos). H-10 **no altera ninguna
banda de riesgo** de findings preexistentes.

### COVERAGE_DELTA

`effective_mode = ENFORCE` en A/B/C/D. A=B en las colas. B→C: `BLOCKED +1`
(`missing_or_degraded_coverage 78→79`, el nuevo finding RW-0009). C→D: `ACTIONABLE_NOW 30→38`
(+8 de RW-0003), `BLOCKED 427→636` (+152 missing/degraded, +57 method_indeterminate, de RW-0003).

### TRACEABILITY_DELTA

| | A/B | C | D |
|---|---|---|---|
| `Test` (nodos) | 0 | 1 | **166** |
| `tested_by` | 0 | 0 | **17** |
| `verifies` | 0 | 0 | 0 (N/A) |
| `refers_to` | 0 | 348 | **350** |
| `system_component` | 0 | 45 | 47 |
| `actor` | 0 | 13 | 13 |
| `implemented_by` | 1120 | 1120 | 1120 |
| `designed_by` | 190 (B) / 204 (A, drift) | 190 | 190 |

### PROVENANCE_DELTA

| Escenario | findings | con ancla exacta | con página válida | con `source_hash` |
|---|---|---|---|---|
| A | 456 | **456 (100 %)** | **456 (100 %)** | **456 (100 %)** |
| B | 456 | 456 (100 %) | 456 (100 %) | 456 (100 %) |
| C | 457 | 457 (100 %) | 457 (100 %) | 457 (100 %) |
| D | 674 | 674 (100 %) | 674 (100 %) | 674 (100 %) |

`provenance.graph_path` se fija a `None` en el paquete por diseño H-4 (su identidad vive en
`GRAPH_SNAPSHOT_FINGERPRINT`); no es una carencia. **0 findings sin ancla / sin página /
sin source_hash en ningún escenario.**

---

## 9 · RR-1 — NO SOBREINTERPRETAR 3/165

```
TEST_OBJECTS_RW0003                          = 165
TESTS_WITH_EXPLICIT_REQUIREMENT_REF          = 3     (F05.05 · UR3.2.3 / 3.2.3)
TESTED_BY                                    = 17
EXPLICIT_TEST_REQUIREMENT_REFERENCE_RECOVERY = 3/165
DO_NOT_LABEL_AS_TEST_TRACEABILITY_COVERAGE_PERCENT = TRUE
INTERPRETATION_REQUIRES_HUMAN_REVIEW               = YES
```

El denominador (165) es el número de casos de prueba **recuperados por OCR**, no el número
real de casos del SAT ni el número que *debería* trazar a un requisito. Los 162 sin ref pueden
deberse a (a) límite del OCR sobre un documento escaneado, (b) el SAT referenciando tags de
equipo / funciones y no ids de catálogo, (c) casos que legítimamente no trazan. **La revisión
humana del denominador es obligatoria antes de convertir 3/165 en cualquier métrica de
cobertura de trazabilidad.**

---

## 10 · CONSISTENCY CHECK

```
production canonical_store  UNCHANGED   (md5 de árbol antes/después idéntico)
production graph_store       UNCHANGED
canonical_store_v2 / graph_store_v2  UNCHANGED   (R-PAR no los tocó)
ledger (decisions_v2.jsonl)  UNCHANGED   (los 3 registros D-2/D-4 son de misiones previas)
RW-0012 clean extraction claims  = 258            ✔ (coincide con lo comprometido)
RW-0012 prod extraction claims   = 595            (clone-drift, §1)
D fingerprints:
  INPUT_CONFIG   = 0de04225362a6f863617d63717e5da82a7e829a2594f95e53f8f36cd5d07598f   ✔ reproduce
  GRAPH_SNAPSHOT = 8ce23f30202991d87f6d867525306e50be1cdf191a40d57b6bd191a2d7b327f4   ✔ reproduce
  FINDINGS       = 2b1a300ae26f76cbf09c6c7fac84053c7edf8603e893bcf75244e161127c834f   ✔ reproduce
A fingerprints reproducen la baseline D-2:
  GRAPH_SNAPSHOT = 88f15b69…   ✔    FINDINGS = fdc29721…   ✔
DOCUMENT_EGRESS = 0   en A, B, C y D (medido)
human_gate_intact = true   en A, B, C y D
MATERIAL_CONTRADICTION = NO   -> NO STOP
```

---

## 11 · CONCLUSIONES

```
A_vs_B_CLONE_DRIFT                      : el drift está 100 % en RW-0012 (595 vs 258 claims, con
                                          páginas fantasma 17/18 y sobre-segmentación de la pág 5).
                                          Efecto: 35 findings regulatorios de la pág 5 re-anclados
                                          a claims distintos ; conteo total, distribución y bandas
                                          IDÉNTICOS ; 0 cambios de banda/evidence_basis/coverage en
                                          los 418 emparejados. La ruta limpia es MÁS correcta.
B_vs_C_H10_EFFECT                       : estrictamente ADITIVO. +1 finding legítimo, +348 refers_to,
                                          +45 system_component, +13 actor, +1 test. 0 eliminados,
                                          0 cambios, 0 regresión implemented_by/designed_by,
                                          contradicts/supports intactos.
C_vs_D_RW0003_ADDITIVE_EFFECT           : +165 Test, +17 tested_by (via 3.2.3 / F05.05), +199 tablas
                                          (194 con rol). −2 REQUIREMENT_NOT_TESTED (RW-0006) RESUELTOS
                                          con evidencia de prueba real. +57 REGULATORY_INCONCLUSIVE
                                          (RW-0003 pasa de NO analizado a analizado). +162
                                          TEST_WITHOUT_REQUIREMENT (nueva visibilidad ; RR-1).
                                          +8 ACTIONABLE_NOW. band_changed 0.

CLONE_DRIFT_CHARACTERIZED               = YES
H10_EFFECT_CHARACTERIZED                = YES
RW0003_ADDITIVE_EFFECT_CHARACTERIZED    = YES

EXTRACTION_IMPROVEMENT_EVIDENCE         = RW-0003 (SAT real 100 % imagen) pasa de 0 texto usable a
                                          186 claims + 199 tablas estructuradas (194 con rol semántico)
                                          + 165 casos de prueba, todo con provenance y DOCUMENT_EGRESS=0.
                                          Para RW-6 la extracción NO cambia (B ≡ C en claims/tablas/secciones).
TRACEABILITY_IMPROVEMENT_EVIDENCE       = de 0 aristas tested_by en TODA la historia del corpus a
                                          17 aristas cross-documento (URS/FS → SAT) por referencias
                                          reales ; −2 REQUIREMENT_NOT_TESTED resueltos. refers_to
                                          de 0 a 350 (deterministas, ancladas, 0 fabricadas).
ANALYSIS_IMPROVEMENT_EVIDENCE           = ninguna banda de riesgo alterada ; 0 findings preexistentes
                                          eliminados o degradados por H-10 ; cobertura extendida a
                                          RW-0003 (+8 ACTIONABLE_NOW). El aumento de findings NO se
                                          etiqueta como mejora salvo los −2 REQUIREMENT_NOT_TESTED
                                          resueltos (verificables) y la extensión de cobertura.
REPORTING_IMPROVEMENT_EVIDENCE          = provenance al 100 % (ancla + página + source_hash) en los
                                          4 escenarios ; mismos artefactos ; colas ACTIONABLE_NOW /
                                          BLOCKED_BY_COVERAGE_OR_EVIDENCE con by_reason íntegro ;
                                          graph_snapshot inmutable por corrida.

UNEXPLAINED_DELTAS                      = 0
MATERIAL_REGRESSION                     = NO
ALL_MATERIAL_DELTAS_EXPLAINED           = YES
READY_FOR_HUMAN_E2_E3_REVIEW            = YES
```

**R-PAR no decide activación, no declara qualification, no produce recomendaciones GMP finales.**
Los blockers de qualification (H-8 sin ground truth humano D-5 ; verificación humana de la
muestra H-10 ; commit del ledger ; firmas) siguen abiertos y no los toca esta validación.
