# R-PAR — DELTA DE FINDINGS v1 ↔ v2 (corpus compartido)

**Fecha:** 2026-08-30 · **Autoridad:** Capa 9 = Cesar · **Tipo:** verificación **READ-ONLY**, insumo
para **E-2 / E-3** (decisión humana de activación). **Ninguna conclusión de activación en este
documento.**

Cumple la tarea única de `REVISIÓN DE CIERRE H-1…H-10` §3 / INSTRUCCIONES PARA CLAUDE CODE: la
comparación lado a lado v1 vs v2 sobre los mismos 6 documentos, a nivel de **findings** (no sólo
conteo de aristas), que el informe maestro implicaba pero no demostraba.

**Fuente de datos:** artefactos ya materializados de la corrida R-PAR previa —
`docs_plan/_r_par/R_PAR_RAW.json` + `docs_plan/_r_par/findings_{A,B,C}.json`. **No se re-ejecutó
ningún pipeline.** No se tocó `canonical_store/`, `graph_store/`, los `_v2`, el flag, `_EXT_VER`,
el ledger, QA40 ni la muestra H-10.

```
NO commit · NO push · NO flip · NO activación · NO adjudicación · sin implementación nueva
```

---

## R-PAR.1 · Corpus

Delta de paridad sobre **los 6 documentos RW que ya existían en v1**:
`RW-0005 · RW-0006 · RW-0009 · RW-0011 · RW-0012 · RW-0014`.

**RW-0003 (SAT real) se reporta APARTE** (§RW-0003) — es capacidad nueva y **no tiene contraparte
v1**, por lo que no entra en el delta de paridad.

---

## R-PAR.2 · Tres conjuntos de findings

| | Definición | Origen (read-only) |
|---|---|---|
| **A** | findings de **producción v1 vigente** | `canonical_store/` + `graph_store/` tal como están (con clone-drift preexistente) · código HEAD |
| **B** | findings de **re-extracción limpia v1** | `V2_TEST_EXTRACTION=OFF` · código HEAD · store temporal en `/tmp` (producción NO sobrescrita) |
| **C** | findings de **v2 `+tests-v1`** | `canonical_store_v2/` + `graph_store_v2/` ya existentes · corpus RW-6 (sin RW-0003) |

```
n_A = 456      n_B = 456      n_C = 457
```

- **Par A ↔ B** aísla el **clone-drift** (mismo código, mismo flag OFF; distinto estado de store).
- **Par B ↔ C** aísla el **efecto real de H-10** (misma extracción limpia; con y sin capacidad nueva).

Clave de emparejamiento en ambos pares: **`finding_record_id`** (no `finding_id`).

---

## R-PAR.3 · Métrica del delta

### Par A ↔ B — CLONE-DRIFT

```
matched_by_finding_record_id = 418
findings_in_both_same_band   = 418
findings_in_both_band_changed = 0        (evidence_basis / ENFORCE: sin cambio)
findings_only_in_A            = 38        (v1 prod los emite ; la base limpia NO)
findings_only_in_B (clean)   = 38        (la base limpia los emite ; v1 prod NO)
```

| Documento | `only_in_A` | `only_in_B` (clean) | `in_both_same_band` (contrib.) | `band_changed` |
|---|---|---|---|---|
| RW-0005 | 0 | 0 | (paridad exacta) | 0 |
| RW-0006 | 0 | 0 | (paridad exacta) | 0 |
| RW-0009 | 0 | 0 | (paridad exacta) | 0 |
| RW-0011 | 0 | 0 | (paridad exacta) | 0 |
| **RW-0012** | **38** | **38** | resto en paridad | 0 |
| RW-0014 | 0 | 0 | (paridad exacta) | 0 |
| **AGREGADO** | **38** | **38** | **418** | **0** |

`only_in_A` (38): `REGULATORY_INCONCLUSIVE` ×37 + `ALCOA_ATTRIBUTABLE_GAP` ×1 — **todos RW-0012,
página 5, banda HIGH**.
`only_in_B` (38): mismo desglose exacto (`REGULATORY_INCONCLUSIVE` ×37 + `ALCOA_ATTRIBUTABLE_GAP`
×1, RW-0012 pág 5, HIGH).

> **Emparejamiento semántico (conservador):** 3 de los 38 `only_in_A` sí emparejan con `only_in_B`
> por `(document, class/subtype, criterion, requirement_id, source_hash)` → quedan **35**
> verdaderamente únicos. `38 = sin emparejar por finding_record_id` · `35 = sin emparejar ni por
> id ni por semántica`. No es contradicción: `38 − 3 = 35`.

### Par B ↔ C — EFECTO H-10

```
matched_by_finding_record_id = 456
findings_in_both_same_band   = 456
findings_in_both_band_changed = 0
findings_only_in_B           = 0        (H-10 NO elimina ningún finding)
findings_only_in_C           = 1
```

| Documento | `only_in_B` | `only_in_C` | `in_both_same_band` | `band_changed` |
|---|---|---|---|---|
| RW-0005/0006/0011/0012/0014 | 0 | 0 | (paridad exacta) | 0 |
| **RW-0009** | 0 | **1** | resto en paridad | 0 |
| **AGREGADO** | **0** | **1** | **456** | **0** |

`only_in_C` (1): `RW-0009 · TEST_WITHOUT_REQUIREMENT · banda LOW · finding_record_id
rec-b192b0eda6e0d549 · evidence_basis=ABSENCE_DEPENDENT · coverage_status=MISSING · anclado ·
source_hash real`. Es el único objeto `Test` que la extracción recupera de RW-0009 (transmittal de
2 páginas), que no traza a ningún requisito → hallazgo legítimo nuevo.

### Calidad de provenance (los 3 conjuntos)

| | findings | con ancla exacta | con página válida | con `source_hash` |
|---|---|---|---|---|
| A | 456 | 456 (100 %) | 456 (100 %) | 456 (100 %) |
| B | 456 | 456 (100 %) | 456 (100 %) | 456 (100 %) |
| C | 457 | 457 (100 %) | 457 (100 %) | 457 (100 %) |

---

## R-PAR.4 · Explicación de cada `findings_only_in_A`

Los **38** `only_in_A` están **100 % localizados en RW-0012**. Causa:

```
RW-0012 · canonical_store de producción = 595 claims   vs   re-extracción limpia = 258 claims
   mismo PDF (sha de7b70c2…) · misma extraction_version (canonical-v1-2026-08) · mismo code path (flag OFF)
   El store de producción sobre-segmenta la página 5 y contiene claims en páginas 17-18 (el documento tiene 14).
```

**Frase por cada `findings_only_in_A` (los 38 comparten la misma):**

> Desaparece de la base limpia por **CLONE-DRIFT (esperado, RR-2)**: el finding regulatorio de la
> página 5 de RW-0012 estaba anclado en un claim que sólo existe en el store de producción
> sobre-segmentado. La re-extracción limpia produce la **misma conclusión regulatoria** (mismo
> requisito, misma banda HIGH, mismo subtipo) anclada en un claim distinto → distinto
> `source_hash` → distinto `finding_record_id`. Es re-anclaje de provenance, **no pérdida
> analítica**: el conjunto `only_in_B` es idéntico en número (38), documento (RW-0012), subtipos
> (37 `REGULATORY_INCONCLUSIVE` + 1 `ALCOA_ATTRIBUTABLE_GAP`) y banda (HIGH). Al menos 1 de los
> `only_in_A` está anclado en la página 18 inexistente → la ruta limpia es **más correcta**.

**Ningún `findings_only_in_A` desaparece por otra causa.** `UNEXPLAINED = 0`. No hay nada a
investigar.

**`findings_only_in_C` (1):** el `TEST_WITHOUT_REQUIREMENT` de RW-0009 — aparece porque H-10
habilita la extracción de `Test`; es aditivo y legítimo, no toca nada preexistente.

---

## RW-0003 (SAT real) — REPORTADO APARTE (no es delta de paridad)

RW-0003 no tiene contraparte v1. Su ingesta con OCR docling (capacidad nueva de H-10) añade, sobre
el corpus de 6 → 7 documentos:

```
+165 objetos Test        +17 aristas tested_by (RW-0006/RW-0005 → RW-0003, via 3.2.3 / F05.05)
+199 tablas (194 con rol semántico)      +2 aristas refers_to
+57 REGULATORY_INCONCLUSIVE (RW-0003 pasa de NOT_ANALYZABLE a analizado)
+162 TEST_WITHOUT_REQUIREMENT (RR-1: casos SAT sin id de requisito recuperable en el OCR)
−2 REQUIREMENT_NOT_TESTED (RW-0006: casos SAT trazan a 2 requisitos previamente marcados no probados)
ACTIONABLE_NOW: 30 → 38 (+8)      band_changed = 0
```

Detalle completo: `docs_plan/R_PAR_DELTA_V1_V2_20260831.md` §3 y `docs_plan/_r_par/R_PAR_RAW.json`
(`C_vs_D_rw0003_additive`).

---

## R-PAR.5 · Verificaciones de consistencia del informe (READ-ONLY, PASS/FAIL)

| # | Verificación | Resultado |
|---|---|---|
| 1 | `canonical_store/RW-*` byte-idéntico al md5 citado en el informe (producción intacta) | **PASS** — `RW-0005 d9138be2… · RW-0006 0b03b0ec… · RW-0009 28c42646… · RW-0011 3db1e795… · RW-0012 b1a46a63… · RW-0014 07cda6bb…` idénticos al snapshot pre-misión |
| 2 | flag `V2_TEST_EXTRACTION=OFF` sobre HEAD reproduce `implemented_by=1120` / `designed_by=190` y `0` test / `0` refers_to | **PASS** — escenario B: `implemented_by=1120 · designed_by=190 · test=0 · refers_to=0` |
| 3 | los 3 fingerprints v2 (`0de04225… / 8ce23f30… / 2b1a300a…`) se reproducen desde `canonical_store_v2/`+`graph_store_v2/` | **PASS** — 2 fuentes independientes coinciden: `H10_VERSION_JUMP_RESULT.json` (run1 == run2) y `R_PAR_RAW.json` escenario D |
| 4 | RW-0012 re-extracción limpia = 258 claims (confirma el clone-drift declarado) | **PASS** — B: RW-0012 = **258** ; A (prod) = **595** |

```
R_PAR_5_ALL_PASS = YES     -> no hay primera contradicción material ; el veredicto del punto 2 de la revisión NO cambia
```

---

## SÍNTESIS (insumo para E-2 / E-3 — no decisión)

```
CORPUS_COMPARTIDO (6 docs)
  A vs B (CLONE-DRIFT)   : 38 findings de RW-0012 pág 5 re-anclados ; conteo/subtipos/bandas IDÉNTICOS ;
                           0 band_changed ; 0 UNEXPLAINED ; los otros 5 docs en paridad exacta.
  B vs C (EFECTO H-10)   : +1 finding legítimo (RW-0009 TEST_WITHOUT_REQUIREMENT, LOW) ;
                           0 findings eliminados ; 0 band_changed ; provenance 100% en A/B/C.

  => Al activar v2 (+tests-v1, re-extracción limpia) sobre el corpus compartido:
       - NINGÚN finding que v1 emite se pierde por causa distinta al clone-drift (RR-2, esperado).
       - NINGUNA banda de riesgo cambia.
       - Se añade 1 finding legítimo por la capacidad nueva.
     El "delta visible" es el re-anclaje de 38 findings de RW-0012 (misma conclusión, mejor ancla)
     + 1 finding nuevo. Es lo que E-2 debe ver ; E-3 debe aceptar que la base limpia (258 claims en
     RW-0012 vs 595) es la base deseada.

RW-0003 (aparte)          : capacidad nueva ; +165 Test / +17 tested_by / −2 REQUIREMENT_NOT_TESTED / +8 ACTIONABLE_NOW.

R_PAR_5                    = 4/4 PASS
RETURN_TO_DESIGN_REQUIRED  = NO (sin cambio)
PRODUCTION_ACTIVATION      = NOT_AUTHORIZED (sin cambio ; E-1/E-2/E-3 son humanas)
```

Este documento es insumo de decisión humana. No se ejecuta E-1…E-6. No se prepara el flip.
