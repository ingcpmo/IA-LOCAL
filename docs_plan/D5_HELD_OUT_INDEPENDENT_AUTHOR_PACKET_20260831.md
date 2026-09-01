# D5-D — PAQUETE PARA AUTOR INDEPENDIENTE DEL CORPUS HELD-OUT (técnico)

**Fecha:** 2026-08-31 · **Origen:** cierre D5 del plan original (arco H-1…H-10) ·
**Autoridad de adjudicación QA40/opportunities/negatives:** Capa 9 = Cesar ·
**Autoridad de este held-out:** un autor independiente QA/Validation **distinto de Cesar**.

> Este paquete lo **estructura** Capa 8 (Claude Code). El **ground truth** (casos, expected,
> provenance, umbrales, firma) lo define y lo firma **exclusivamente** una persona real de
> QA/Validation que **no** sea Capa 9 (Cesar). La IA no decide ni firma el ground truth.

---

## 1. Por qué existe este paquete

El instrumento `factory/regulatory/requirement_catalog/held_out_technical_corpus.yaml`
elimina el acoplamiento de validez de constructo (defecto D-3): el autor del held-out debe
ser **distinto** del autor de `technical_completeness_rules.yaml` (Capa 9 / Cesar). Reglas
que **NO se relajan**:

```
independent_author_required: true
excluded_authors: ["Capa 9 (Cesar)"]
match_policy.by: [finding_class, subtype, document, page_band]   # estructural; el ground truth NO aporta texto
match_policy.page_band_tolerance: 3
thresholds (fijados ex-ante):
  TECHNICAL_RECALL_MIN: 0.90
  TECHNICAL_FALSE_POSITIVE_MAX: 0.05
  FABRICATED_CITATIONS_MAX: 0
```

## 2. Estado verificado del instrumento (2026-08-31, en vivo)

| Comprobación | Resultado |
|---|---|
| `held_out_technical_corpus.yaml` → `status` | `DRAFT_UNSIGNED` |
| `author` / `signed_at` / `rules_author` | `null` / `null` / `null` |
| Documentos `HO-FS` / `HO-FSOK` como store canónico | **NO existen** (semilla sintética placeholder de `held_out_corpus.build_seed_corpus`) |
| Corrida real del analizador sobre el held-out | **NONE** |
| `run_held_out_dry()` → `usable_as_gate` | **`false`** (`reportable_range = NOT_A_GATE`) |
| `assert_usable_as_gate()` | fail-closed: exige `status == SIGNED` **Y** `author ∉ excluded_authors` |

**Conclusión:** D5-D **NO** puede declararse COMPLETE y **NO** se calculan métricas
(`TECHNICAL_HELD_OUT_RECALL`, `TECHNICAL_FALSE_POSITIVE_RATE`, `FABRICATED_CITATIONS`)
sobre la semilla placeholder. Permanece **fail-closed** hasta la firma independiente.

## 3. Qué debe producir el autor independiente

### 3A. Ground truth (casos)

La semilla sintética actual describe 5 casos *por posición y tipo*, sin dictar redacción.
El autor independiente debe **revisar / redefinir** cada uno con evidencia real:

| case_id | provenance | expected (class / subtype) | qué debe confirmar / redefinir el autor |
|---|---|---|---|
| HO-T-001 | REG | DataIntegrityFinding / AUDIT_TRAIL_INTEGRITY_GAP | cláusula normativa citada (21 CFR 11.10(e): fecha/hora, quién, valor anterior/nuevo); `page_band` real en el FS held-out |
| HO-T-002 | REG | TechnicalFinding / BACKUP_RECOVERY_GAP | cláusula (EU GMP Annex 11 §7.2: realización regular **y** verificación de restauración); `page_band` real |
| HO-T-003 | DOM | SecurityFinding / AUTHORITY_CHECK_GAP | rationale del revisor (el FS nombra "roles" pero no describe verificación de autoridad por operación); `page_band` real |
| HO-T-004 | ADV | SecurityFinding / ACCESS_CONTROL_GAP | **aprobar o rechazar** la propuesta de máquina (`human_approved: true` solo si el autor lo aprueba); `page_band` real |
| HO-T-N01 | DOM (negativo) | `{finding: false}` | confirmar que el FS "OK" describe el control completo (audit trail completo + protección anti-modificación) → el analizador NO debe emitir nada; `page_band` real en `HO-FSOK` |

Para **cada caso positivo**: `finding_class`, `subtype`, `document`, `page_band`,
`source evidence` (cláusula/pasaje real), `provenance_tag` ∈ {REG, DOM, ADV}.
Para **el/los negativo(s)**: `document`, `page_band`, rationale de por qué el control está completo.
Puede añadir casos adicionales (positivos y negativos) si su revisión del FS lo justifica.

### 3B. Materialización del corpus real (después de 3A)

1. Crear / importar los documentos held-out (`HO-FS`, `HO-FSOK`, o los que el autor defina)
   como **corpus canónico separado** del corpus de desarrollo.
   - **No** reutilizar ningún `RW-00xx` como sustituto del held-out.
   - Mantener aislamiento respecto de desarrollo y de `technical_completeness_rules.yaml`.
2. Ejecutar el **pipeline normal de análisis** (el mismo camino de producción) sobre ese corpus.
3. Debe quedar **evidencia verificable** de:
   - `canonical input` (claims persistidos) y `source_hashes`
   - `analyzer version` + `graph/config fingerprint` (INPUT_CONFIG / GRAPH_SNAPSHOT / FINDINGS)
   - `findings` reales emitidos (`*_findings.json`) con `provenance`
   - `document_egress = 0`

### 3C. Revisión independiente y firma

El `rules_author` humano independiente revisa los `HO-T-00x` positivos y el/los negativo(s)
held-out contra los findings reales, **confirma o rechaza** el expected ground truth, y firma:

```
status: SIGNED
author: <persona real QA/Validation, != Cesar>
rules_author: <la misma persona real, != Cesar>
signed_at: <timestamp ISO-8601>
```

Solo entonces se ejecuta `assert_usable_as_gate()` y, si pasa, se calcula con el scorer
existente (sin fabricar resultados):

```
TECHNICAL_HELD_OUT_RECALL          = TP / (TP + FN)   contra thresholds.TECHNICAL_RECALL_MIN (0.90)
TECHNICAL_FALSE_POSITIVE_RATE      = FP / (FP + TN)    contra thresholds.TECHNICAL_FALSE_POSITIVE_MAX (0.05)
FABRICATED_CITATIONS               = recuento          contra thresholds.FABRICATED_CITATIONS_MAX (0)
```

## 4. Lo que NO se debe hacer

- No relajar `independent_author_required` ni `excluded_authors`.
- No usar a Cesar como `rules_author` ni como `author` del held-out
  (Cesar sí adjudica QA40 / opportunities / negative_units — familia distinta).
- No marcar D5-D COMPLETE ni calcular métricas sobre la semilla sintética.
- No reutilizar el corpus RW como held-out.

## 5. Estado de bloqueo declarado

```
D5_D_STATUS = BLOCKED_BY_INDEPENDENT_RULES_AUTHOR
HELD_OUT_CANONICAL   = NONE
HELD_OUT_ANALYZER_RUN = NONE
INDEPENDENT_RULES_AUTHOR = PENDING  (no asignado)
```

El resto de D5 (D5-A QA40, D5-B opportunities, D5-C negative_units) puede cerrarse de forma
independiente bajo la autoridad de Cesar; **D5 en su conjunto NO es COMPLETE** mientras
D5-D siga en este estado (ver criterio de completitud del plan original).

---

### NEXT_HUMAN_ACTION

Asignar un autor independiente QA/Validation (≠ Cesar) y entregarle este paquete para
ejecutar 3A → 3B → 3C. Hasta entonces, D5-D permanece fail-closed.

---

## 6. Flujo técnico posterior — PREPARADO, SIN FIRMAR, SIN GROUND TRUTH INVENTADO

Estado a 2026-08-31: D5-A y D5-B/D5-C cerrados y validados con el scorer existente
(`real_corpus_adjudication`): `QA40_SAMPLE_PRECISION = 1.0` [0.7008, 1.0] (9 TP / 0 FP /
31 COVERAGE_LIMITED); `REAL_RECALL = 1.0` [0.7008, 1.0] (9 TP / 0 FN, uno-a-uno);
`REAL_SPECIFICITY = 1.0` [0.2065, 1.0] (1 unidad negativa firmada: NEG-CAND-03).
D5-D sigue BLOQUEADO: no hay autor independiente, no hay corpus canónico held-out,
no hay corrida real. Ningún número held-out se declara.

### 6.1 Secuencia técnica (se ejecuta SOLO tras asignar el autor independiente)

```
1. independent author review        -> el autor QA/Validation (≠ Cesar) revisa/redefine
                                       el ground truth de §3A en held_out_technical_corpus.yaml
                                       (cláusulas REG, aprobación de los ADV, umbrales, casos
                                       negativos). NO lo hace Capa 8 ni Cesar.
2. materialización del corpus        -> crear HO-FS / HO-FSOK (o los documentos que el autor
   held-out canónico separado          defina) como store canónico SEPARADO de desarrollo y de
                                       technical_completeness_rules.yaml. Prohibido reutilizar
                                       cualquier RW-00xx.
3. source hashes                     -> registrar SHA-256 de cada documento fuente del held-out
                                       (source_attestation) antes de analizar.
4. ejecución real del analizador     -> pipeline de PRODUCCIÓN (mismo camino que RW), sobre el
                                       corpus held-out. Sin prompts nuevos, sin tocar reglas.
5. findings reales                   -> *_findings.json emitidos, con INPUT_CONFIG /
                                       GRAPH_SNAPSHOT / FINDINGS fingerprints.
6. provenance                        -> evidence_provenance.json + provenance por finding.
7. document_egress = 0               -> verificar `run_held_out_dry()['document_egress_bytes'] == 0`.
8. revisión / firma independiente    -> el autor confirma o rechaza el expected vs. los findings
                                       reales y firma: status: SIGNED · author: <persona ≠ Cesar> ·
                                       rules_author: <la misma persona ≠ Cesar> · signed_at: ISO-8601.
9. assert_usable_as_gate()           -> debe pasar (SIGNED Y author ∉ excluded_authors ∪ rules_author).
10. scorer                           -> con el instrumento ya usable, calcular SIN fabricar:
                                       TECHNICAL_HELD_OUT_RECALL     vs 0.90
                                       TECHNICAL_FALSE_POSITIVE_RATE vs 0.05
                                       FABRICATED_CITATIONS          vs 0
```

### 6.2 Qué queda listo para que solo falte "registrar + correr + validar"

- `held_out_technical_corpus.yaml`: esqueleto completo (5 casos semilla por posición/tipo,
  `thresholds` fijados ex-ante, `match_policy` estructural, `excluded_authors`,
  `independent_author_required: true`). **Solo faltan**: cláusulas/rationale reales,
  `page_band` reales, `human_reviewed: true`, `human_approved: true` para el ADV, y la firma.
- `held_out_corpus.assert_usable_as_gate()` / `run_held_out_dry()`: implementados y fail-closed
  (`reportable_range = NOT_A_GATE` mientras DRAFT_UNSIGNED).
- Scorer de recall/FP/citas: el mismo `real_corpus_adjudication` / `held_out_corpus` ya en uso.

### 6.3 Al recibir el nombre y las decisiones del autor independiente

```
INDEPENDENT_RULES_AUTHOR = <nombre real ≠ Cesar>     # hoy: PENDING
D5_D                     = <AWAITING_INDEPENDENT_HUMAN -> IN_PROGRESS -> COMPLETE|FAIL>
```

Pasos de Capa 8 en ese momento (mecánicos, sin decidir ground truth):
1. Escribir en `held_out_technical_corpus.yaml` EXACTAMENTE las decisiones del autor
   (expected, page_band, cláusulas, umbrales si los cambia).
2. Materializar el corpus canónico held-out (paso 6.1.2–6.1.3).
3. Ejecutar el pipeline (6.1.4–6.1.7).
4. Presentar findings reales vs. expected al autor para su firma (6.1.8).
5. Tras la firma: `assert_usable_as_gate()` + scorer (6.1.9–6.1.10) y reportar métricas.

Mientras no haya nombre:

```
INDEPENDENT_RULES_AUTHOR = PENDING
D5_D = AWAITING_INDEPENDENT_HUMAN
```

No se avanza a E5 mientras D5-D no pase.
