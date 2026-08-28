# CIERRE FASE 10 — Validación integral (V2 LOCAL-ONLY)

**Fecha:** 2026-08-28. **Autoridad:** Capa 9 = Cesar. **Alcance:** consolida las tres
suites de validación de FASE 10 (`docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md` §2).

---

## Resumen ejecutivo

| Suite | Resultado | Contingencia aceptada |
|---|---|---|
| **REGULATORY (Suite A)** | **FAIL** (no se convierte en PASS) | Regulatory Tier-1 / **Palanca C** — contingencia determinista aceptada |
| **FUNCTIONAL (Suite B)** | **PASS** | — |
| **TECHNICAL (Suite C)** | **PASS** (benchmark) | C07 fuera del detector determinista (SEMANTIC), sin activar HYBRID/LLM |
| **Transversales** | **PASS** (LOCAL_ONLY, DOCUMENT_EGRESS=0, FABRICATED_CITATIONS=0, TRACEABILITY_COMPLETE, humano intacto) | — |

---

## 1. REGULATORY — Suite A

**Estado: FAIL. No se reinterpreta retrospectivamente como PASS.**

```
LLM regulatory benchmark  = FAIL
positive recall           = 0/7   (fixture 7P+2N, variante estricta y no-estricta)
negatives                 = 2/2   rechazados
fabricated citations      = 0
schema_valid_rate         = 100%
```

Confirmado por 6 vías independientes (H1–H4, qwen2.5:14b, fusión RRF, R2, B4b estricto,
B4b no-estricto). Fuente: `docs_plan/REPORTE_B4B_MEDICION_RECALL_V2.md`,
`docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`, ledger `PILOT_EXECUTION-2026-032/-034`.

**Interpretación (`gates.interpret_regulatory`):** `TECHO_NO_CRUZADO` (≤2/7). Contingencia
pre-acordada del ADR §10.

### Arquitectura adoptada — Regulatory Tier-1 / Palanca C

`factory/regulatory/findings/regulatory_tier1.py` (commit `9d9b4ff`). **CERO LLM.**
Por sub-criterio: eco léxico anclado (`match_citation` exacto/normalizado o
`relevance_score ≥ 0.60`) → `REGULATORY_COMPLIANT_EVIDENCE` / `MACHINE_CONFIRMED_FINDING`;
todo lo demás → `REGULATORY_INCONCLUSIVE` / `MACHINE_INCONCLUSIVE` → **revisión humana con
cobertura declarada**. Nunca auto-aprobación, nunca declaración de cumplimiento.
Es una **contingencia determinista aceptada**, no una solución al recall del 7B.

---

## 2. FUNCTIONAL — Suite B

**Estado: PASS.**

```
FUNCTIONAL_RECALL          = 16/16 = 1.00   (>= 0.90)
FUNCTIONAL_FALSE_POSITIVE  =  0/16 = 0.00   (<= 0.05)
```

- Corpus real Rockwell: análisis funcional determinista (B6a + B1.2) emite **0 findings,
  0 FP** — trazabilidad completa (1300+ aristas). `docs_plan/REPORTE_B8B_SUITE_B_DRY_RUN.md`.
- Recall medido con **fixture de inyección de defectos**
  (`factory/regulatory/validation_v2/defect_corpus.py`, 16 defectos conocidos y anclados):
  16/16 detectados, 0 FP. `docs_plan/REPORTE_B8B_SUITE_B_RECALL.md`.
- Reproducible: `pytest factory/tests/test_functional_findings.py::test_defect_corpus_suite_b_measures_functional_recall`.

### Resolución del fixture borrador de Suite B

`factory/regulatory/validation_v2/fixtures_draft/functional_suite_b.yaml` → **`status: RETIRED`**
(con `retired_by`, `retired_at`, `retired_note` y trazabilidad al instrumento vigente).
Motivo: sus 15 casos positivos eran ficción para el corpus Rockwell (todo trazado). El
gate funcional de FASE 10 es el **defect_corpus** (arriba). Decisión:
`docs_plan/DECISION_B8B_SUITE_B.md`.

---

## 3. TECHNICAL — Suite C

**Estado: PASS (benchmark controlado).**

Instrumento: `factory/regulatory/validation_v2/fixtures_draft/technical_suite_c.yaml`
**`status: SIGNED`** v1.0-benchmark (Golden Dataset fijo, 20 casos, clasificación
normativamente corregida). Runner: `technical_suite_c.run_suite_c_formal()` bajo
`network_locked()`.

```
TP        = 9      (C01 C03 C04 C05 C06 C08 C09 C10 C12)
FN        = C07    (SEMANTIC -- juicio de criticidad; fuera del detector determinista)
FP        = 0
recall    = 0.90   (>= 0.90)

TECHNICAL_RECALL           0.90  >= 0.90   -> PASS
TECHNICAL_FALSE_POSITIVE   0.00  <= 0.05   -> PASS
FABRICATED_CITATIONS       0     = 0       -> PASS
TRACEABILITY_COMPLETE      YES              -> PASS   (edges: implemented_by, designed_by, regulated_by)
LOCAL_ONLY                 YES              -> PASS
DOCUMENT_EGRESS            0                -> PASS
```

Ground truth NO modificado para forzar PASS.

Detector: B6b v1 (grafo: `INTERFACE_INCONSISTENCY`, `ORPHAN_DESIGN_ELEMENT`) + B6b v2
(reglas de completitud gobernadas `technical_completeness_rules.yaml` **v1.1 SIGNED**,
context-scoped tras OD-6: C01 C03 C04 C05 C08 C09 C10). Reproducible:
`pytest factory/tests/test_technical_findings.py factory/tests/test_validation_v2.py::test_suite_c_formal_gates_pass`.

### Validación TECHNICAL sobre el corpus real (separada del benchmark)

`docs_plan/VALIDACION_TECNICA_CORPUS_REAL_RW.md` +
`factory/regulatory/pilot_run/technical_real_corpus/rw-tech-20260828T030943Z/`.
24 findings sobre RW-0005/0006/0009/0011/0012/0014, todos `human_state=UNREVIEWED`,
`document_egress_bytes = 0`. No usa C01..C20 como obligación. OD-1..OD-5 se conservan
como observaciones; NO modifican el benchmark.

---

## 4. Transversales (FASE 10 §2 transversal)

```
LOCAL_ONLY            = YES   (network_locked() en B4b, Suite C formal y validación real)
DOCUMENT_EGRESS       = 0     bytes  (medido en cada corrida)
FABRICATED_CITATIONS  = 0     (todo finding anclado a source_text literal)
HUMAN_GATE_INTACT     = YES   (human_state nace UNREVIEWED; ninguna vía de código IA lo cambia)
TRACEABILITY_COMPLETE = YES   (grafo B2 poblado; queries trace/orphans correctas)
```

---

## 5. Veredicto FASE 10

```
REGULATORY_GATE = FAIL  (contingencia aceptada: Regulatory Tier-1 / Palanca C, determinista)
FUNCTIONAL_GATE = PASS  (16/16 recall, 0 FP -- fixture de inyección de defectos)
TECHNICAL_GATE  = PASS  (benchmark Suite C: TP=9, FN=C07 semantic, FP=0, recall 0.90; transversales PASS)
```

FASE 10 **CERRADA** con la contingencia regulatoria explícitamente aceptada. El cutover
de la clase Regulatory (FASE 11) procede **sólo** en modo Tier-1 (Palanca C) con V2
aportando Functional/Technical — decisión explícita de Capa 9, nunca automático.
