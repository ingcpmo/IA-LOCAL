# Reporte B8b — medición de FUNCTIONAL_RECALL por fixture de inyección de defectos

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar.
**Base:** `docs_plan/DECISION_B8B_SUITE_B.md` (opción A) y
`docs_plan/REPORTE_B8B_SUITE_B_DRY_RUN.md`.
**Instrumento:** `factory/regulatory/validation_v2/defect_corpus.py`.
**Naturaleza:** DETERMINISTA — sin LLM, sin PDF, sin gobernanza consumida.

---

## 1. Por qué este fixture

El dry run sobre el corpus real Rockwell (`REPORTE_B8B_SUITE_B_DRY_RUN.md`)
mostró trazabilidad completa: 0 findings funcionales verdaderos que detectar.
`FUNCTIONAL_RECALL` sobre 0 casos esperados es **indefinido** — no se puede
medir recall sin defectos reales. La opción A adoptada por Capa 9: construir
un proyecto sintético con **defectos CONOCIDOS y anclados** y medir cuántos
detecta el analizador funcional determinista (B6a + B1.2).

## 2. Composición del corpus de defectos

Cuatro documentos (`DB-URS`, `DB-FS`, `DB-DS`, `DB-SAT`), verdad-terreno en
`GROUND_TRUTH` (16 hallazgos esperados) + 3 requisitos completamente
trazados como control negativo (`UR-DB-001..003`, URS→FS→SAT).

| # casos | familia de defecto | subtype esperado | disparador en el grafo |
|---|---|---|---|
| 4 (`NI1-4`) | requisito de la URS sin implementación (`UR-DB-011..014`) | `REQUIREMENT_NOT_TRACED` | claim de doc fuente sin `implemented_by`/`tested_by` saliente |
| 4 (`NT1-4`) | requisito implementado pero sin prueba (`UR-DB-005..008`) | `REQUIREMENT_NOT_TESTED` | claim CON `implemented_by` pero sin `test` transitivo |
| 2 (`IW1-2`) | claim del FS sin requisito aguas arriba (`FX-DB-101..102`) | `IMPLEMENTATION_WITHOUT_REQUIREMENT` | claim de FS/DS sin `implemented_by`/`designed_by` entrante y sin citar un id de requisito existente |
| 3 (`CT1-3`) | contradicción cross-doc modal-opuesta (`UR-DB-021..023`, URS vs DS) | `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` | par cross-doc `shall` / `shall not` sobre el mismo predicado, `_predicate_overlap ≥ 0.55` |
| 3 (`CT1b-3b`) | los 3 requisitos contradichos tampoco tienen implementación | `REQUIREMENT_NOT_TRACED` | idem `NI` — el defecto de contradicción y el de trazabilidad coexisten |

## 3. Resultado medido

```
graph edges         : implemented_by=7  tested_by=6  contradicts=3  regulated_by=20
FUNCTIONAL_RECALL   : 16 / 16  = 1.00     (umbral ≥ 0.90)  -> PASS
FUNCTIONAL_FALSE_POSITIVE : 0 / 16 = 0.00 (umbral ≤ 0.05)  -> PASS
findings emitidos   : 16   (todos casan con un ExpectedFinding, ninguno sobra)
gate funcional      : all_passed = True
```

Detección por caso — **16/16**:

| grupo | casos | detectados |
|---|---|---|
| `REQUIREMENT_NOT_TRACED` (sin impl) | NI1-4 | 4/4 |
| `REQUIREMENT_NOT_TESTED` (impl sin test) | NT1-4 | 4/4 |
| `IMPLEMENTATION_WITHOUT_REQUIREMENT` | IW1-2 | 2/2 |
| `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` | CT1-3 | 3/3 |
| `REQUIREMENT_NOT_TRACED` (contradicho + sin impl) | CT1b-3b | 3/3 |

Criterio de match: mismo `subtype` **y** `anchor_substring` (el id del
requisito) presente en el `source_text` literal del finding, sin
doble-conteo. Cada uno de los 16 findings emitidos casa exactamente con un
`ExpectedFinding` — **0 findings sobrantes = 0 falsos positivos**. Los 3
requisitos de control (`UR-DB-001..003`, trazados de punta a punta) no
produjeron ningún finding.

## 4. Qué se ejercitó nuevo en el analizador

Este fixture obligó a implementar dos loops de finding que el dry run no
ejercía (el corpus real no tenía casos):

- **`REQUIREMENT_NOT_TESTED`** (`TestCoverageFinding`, MAJOR /
  `MACHINE_DEVIATION_CANDIDATE`): claim de doc fuente CON `implemented_by`
  pero para el que `_reaches_test()` (BFS por `implemented_by` /
  `designed_by` / `tested_by`, profundidad ≤ 8) no alcanza ningún nodo
  `test`. Sujeto al mismo filtro de confianza que `REQUIREMENT_NOT_TRACED`
  (parece requisito + lleva id).
- **`IMPLEMENTATION_WITHOUT_REQUIREMENT`** (`FunctionalFinding`, MINOR /
  `MACHINE_INCONCLUSIVE`): claim de un doc `FS`/`DS`/`SAT`/… sin
  `implemented_by`/`designed_by` entrante. **Guarda anti-falso-positivo:**
  si el claim cita un id de requisito que existe en algún doc fuente, se
  omite — es límite de extracción de la arista, no un hueco real. Sin esta
  guarda el fixture producía 3 FP (los lados DS de las contradicciones
  citan `UR-DB-021..023`).

## 5. Alcance y límite honesto

**Lo que esta medición demuestra:** el analizador funcional determinista,
sobre defectos estructurales bien formados (id de requisito presente,
contradicción modal-opuesta exacta), tiene **recall alto y 0 falsos
positivos**. Es una red de seguridad fiable para trazabilidad rota,
cobertura de prueba faltante e implementación huérfana **cuando el
identificador del requisito está citado literalmente**.

**Lo que NO demuestra** (sigue fuera de alcance determinista, necesita
B6b semántico):

- requisito implementado **por paráfrasis** sin citar el número — el
  linkeo determinista no lo ata, y el fixture no lo prueba (todos sus
  defectos llevan id explícito);
- contradicciones que **no** sean `shall` / `shall not` modal-opuesto
  sobre el mismo predicado;
- `PARTIAL_TEST_COVERAGE` graduada (cobertura parcial, no binaria).

El recall medido (1.00) es sobre el **espacio de defectos que el analizador
determinista está diseñado para cubrir**, no sobre el universo de defectos
funcionales posibles. Ese universo mayor queda para B6b, que sigue
bloqueado por gobernanza (LLM) — y cuyo techo de juicio del 7B ya está
confirmado por 6 vías independientes (`gmp-recall-pipeline` skill).

## 6. Registro

```
FUNCTIONAL_RECALL          = 1.00 (16/16, fixture de inyección de defectos) -> PASS
FUNCTIONAL_FALSE_POSITIVE  = 0.00 (0/16)                                    -> PASS
  · sobre corpus real Rockwell: 0 findings, 0 FP (dry run) -> también PASS
Suite B (funcional)        = CERRADA para el alcance determinista
Suite C (técnica)          = sigue bloqueada por B6b
B6b / B8b Suite C / B9b    = pendientes de gobernanza (Cesar)
```

Instrumento reproducible:
`pytest factory/tests/test_functional_findings.py::test_defect_corpus_suite_b_measures_functional_recall`

---

*Sin LLM. Sin gobernanza consumida. Determinista y reproducible.*
