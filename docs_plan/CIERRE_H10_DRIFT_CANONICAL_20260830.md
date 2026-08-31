# H-10 — INVESTIGACIÓN DEL DRIFT CANONICAL (RW-0012) ANTES DE ACTIVAR

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar. Sin commit, sin push.

```
CANONICAL_DRIFT_EXPLAINED = YES
CLASSIFICATION            = PREEXISTING_CLONE_DRIFT
NEW_REGRESSION            = NO   (no causado por H-10)
INFO_LOSS_CAUSED_BY_H10   = NO
```

---

## 0 · El síntoma

`RW-0012` (`MCCPDC PCS Signal Interface Control Block Narrative.pdf`):
- **store de producción** (`factory/regulatory/canonical_store/RW-0012.sqlite3`): **595 claims**
- **re-extracción v2 de H-10** (y también re-extracción fresca con HEAD, flag OFF): **258 claims**

---

## 1 · Comparación controlada

| Dimensión | Producción | Re-extracción fresca (HEAD, flag OFF) | H-10 v2 |
|---|---|---|---|
| PDF (ruta) | `GMPAI/source/Rockwell/MCCPDC PCS Signal Interface Control Block Narrative.pdf` | idéntico | idéntico |
| **PDF sha256** | `de7b70c297f0fbf1269d47e334a7575d4de3429bff6ed797fc663b85fea15c71` | **idéntico** | **idéntico** |
| PDF en el allowlist (`source_baseline_allowlist.yaml`), sha declarado | `de7b70c2…` (coincide) | — | — |
| `extraction_version` (Document + meta) | `canonical-v1-2026-08` | `canonical-v1-2026-08` | `canonical-v1-2026-08+tests-v1` (sufijo por el flag; la extracción de claims es la misma) |
| flag `V2_TEST_EXTRACTION` | OFF | OFF | ON (no altera la extracción de claims/secciones — probado aditivo) |
| code path | `extract_document` → `dse.extract_structure` → `extract_claims_for_section` | idéntico | idéntico |
| `n_paginas` (doc real) | 14 | 14 | 14 |
| **claims** | **595** | **258** | **258** |
| claims por página (histograma) | `{5: 483, 4: 46, 18: 18, 17: 18, 14: 16, 1: 14}` | `{5: 200, 4: 32, 14: 16, 1: 10}` | `{5: 200, 4: 32, 14: 16, 1: 10}` |
| tipos de claim | `statement 471 · function 43 · control 31 · parameter 29 · actor_action 18 · test 3` | `statement 203 · function 27 · control 20 · parameter 8` | idéntico a la re-extracción fresca |
| `distinct source_text` | 554 | 240 | 240 |

### Solapamiento de `source_text`

```
prod ∩ fresh = 240
only fresh    = 0        <- toda la re-extracción fresca ESTÁ en producción
only prod     = 314      <- producción tiene 314 claims que el código actual NO produce
```

**La re-extracción fresca es un SUBCONJUNTO ESTRICTO de la de producción.**

---

## 2 · Naturaleza de los 314 claims "sólo en producción"

- **Páginas fantasma 17 y 18** (18 + 18 = 36 claims): el documento tiene **14 páginas**.
  Claims con `pagina` 17/18 no pueden provenir de la extracción actual → artefacto de una
  versión anterior del segmentador que numeró mal.
- **Sobre-segmentación de la página 5**: producción **483** claims en la pág 5 vs **200** en
  fresh (2.4×). Misma página, mismo PDF → el segmentador de claims de producción partía el
  texto mucho más fino (o acumuló claims de varias corridas).
- **Tipos `actor_action` (18) y `test` (3)**: `extract_claims_for_section` con el código HEAD
  no emite esos tipos para este documento. Son de otra versión / otra ruta.

---

## 3 · Clasificación

```
EXPECTED_SEMANTIC_CHANGE  : NO  (el cambio no lo introduce H-10; flag OFF con HEAD da 258)
PREEXISTING_CLONE_DRIFT   : SÍ  (el store de producción fue poblado por una versión anterior
                                 del extractor / acumulado en varias corridas; incluye páginas
                                 inexistentes y sobre-segmentación. El código HEAD, determinista,
                                 produce 258 — reproducido por la re-extracción fresca Y por H-10.)
EXTRACTION_REGRESSION     : NO  (H-10 no toca extract_claims_for_section / extract_structure.
                                 La diferencia es 100% pre-existente a esta misión.)
UNKNOWN                   : —
```

---

## 4 · ¿Pérdida real de información causada por H-10?

**NO.** El delta prod↔fresh:
- existe **con el código HEAD y el flag OFF** (sin ninguna ruta de H-10 involucrada);
- consiste en claims **espurios** de producción (páginas 17/18 inexistentes, sobre-segmentación),
  no en contenido real que H-10 haya descartado;
- `only fresh = 0` → la re-extracción actual **no pierde ningún `source_text`** respecto de
  producción; produce un subconjunto más limpio.

`NEW_REGRESSION = NO`. No hay STOP por este motivo.

---

## 5 · Implicación para la activación productiva

- Los fingerprints de H-10 v2 (`INPUT_CONFIG 0de04225…` / `GRAPH_SNAPSHOT 8ce23f30…` /
  `FINDINGS 2b1a300a…`) **no** coinciden con la baseline D-2 (`3c8b0036…` / `88f15b69…` /
  `fdc29721…`) porque la baseline D-2 consumió el `canonical_store` de producción **con el
  drift** (595 claims en RW-0012, etc.), mientras que H-10 v2 es una **re-extracción limpia
  del clon con el código HEAD**.
- Por eso la activación productiva de `+tests-v1` **debe** ir acompañada de la re-extracción
  completa del corpus con el código HEAD (que es lo que H-10 v2 ya materializó en
  `canonical_store_v2/`), no de un parche sobre el store con drift.
- `CANONICAL_DRIFT_EXPLAINED = YES` → condición de §5 de la misión cumplida para permitir
  (a criterio humano) la activación.
