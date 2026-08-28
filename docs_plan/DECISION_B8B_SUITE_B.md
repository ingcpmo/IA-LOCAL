# DECISIÓN — B8b Suite B (funcional): gate de falsos positivos aceptado, recall por fixture de inyección

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar. **Estado:** ADOPTADA (opción B + A).
**Base:** `docs_plan/REPORTE_B8B_SUITE_B_DRY_RUN.md`.

---

## 1. Qué se decidió

Sobre el corpus real Rockwell, el análisis funcional determinista (B6a + B1.2) emite **0
findings** — trazabilidad completa (1300+ aristas), 0 contradicciones reales, tests trazados.

**(B) — ACEPTADO:**
- `FUNCTIONAL_FALSE_POSITIVE ≤ 5%` → **CUMPLIDO** sobre corpus real: 0 findings emitidos, 0
  falsos positivos. El analizador funcional no inventa hallazgos.
- `FUNCTIONAL_RECALL ≥ 90%` → **NO medido sobre corpus limpio**. Un corpus ya bien trazado no
  tiene findings funcionales verdaderos que detectar; el recall sobre 0 casos esperados es
  indefinido. Se declara explícitamente, sin maquillar.

**(A) — EN CURSO:** se construye un **fixture de inyección de defectos** — un set de documentos
sintético con defectos CONOCIDOS (requisitos sin implementar, requisitos sin probar,
implementaciones sin requisito, contradicciones cross-documento reales) — para medir
`FUNCTIONAL_RECALL` de verdad. Determinista, sin gobernanza, sin LLM.
Ver `factory/regulatory/validation_v2/defect_corpus.py` + `REPORTE_B8B_SUITE_B_RECALL.md`.

## 2. Alcance real del análisis funcional determinista

Subtypes que el analizador SÍ produce (sin LLM, solo grafo):

| subtype | disparador |
|---|---|
| `REQUIREMENT_NOT_TRACED` (Traceability) | claim de doc fuente sin `implemented_by`/`tested_by` saliente |
| `REQUIREMENT_NOT_TESTED` (TestCoverage) | claim de doc fuente CON implementación pero sin `test` transitivo |
| `IMPLEMENTATION_WITHOUT_REQUIREMENT` (Functional) | claim de FS/DS sin requisito aguas arriba |
| `TEST_WITHOUT_REQUIREMENT` (TestCoverage) | test sin `verifies`/`tested_by` entrante |
| `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` (Functional) | par cross-doc modal-opuesto sobre el mismo predicado |

Fuera de alcance determinista (necesitan B6b semántico): detección de paráfrasis en
implementación/prueba, `PARTIAL_TEST_COVERAGE` graduada, contradicciones no modal-opuesto.

## 3. Registro

```
FUNCTIONAL_FALSE_POSITIVE  = CUMPLIDO (0 FP sobre corpus real Rockwell)
FUNCTIONAL_RECALL          = medido por fixture de inyección de defectos (opción A)
FIXTURE_BORRADOR_20        = obsoleto para el corpus Rockwell (15 casos positivos eran ficción)
Suite_C (técnica)          = sigue bloqueada por B6b
```
