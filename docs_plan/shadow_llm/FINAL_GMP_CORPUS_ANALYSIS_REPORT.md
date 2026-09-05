# FINAL GMP CORPUS — ANALYSIS REPORT (FORMALIZACIÓN DE BASELINE · G0)

**Arco:** Capa LLM de interpretación sobre findings deterministas (diseño v1.1).
**Fase:** G0 — **CONSOLIDACIÓN / FORMALIZACIÓN**.
**Rama:** `shadow/llm-interpretation-layer` · **Baseline:** `reconc-acceptance-v1` → `0e1e88a`.
**Fecha:** 2026-09-02.

---

## 0 · Naturaleza de este documento (declaración explícita)

Este reporte es la **formalización de una baseline ya existente**. NO es:

- **NO** una re-extracción del corpus (no se re-parsearon PDFs, no se regeneró `canonical_store`
  ni `graph_store`; se reutilizaron los stores de producción con `LOGICAL_CONTENT_HASH` ==
  `VALIDATION_BASELINE_MANIFEST`, 6/6);
- **NO** una nueva caracterización (la caracterización ya se produjo en la corrida diagnóstica
  `diag-corpus-20260902`, `docs_plan/agent_diagnostic/CURRENT_CORPUS_AGENT_DIAGNOSTIC.md`);
- **NO** un re-juicio ni una re-clasificación de findings (no se tocó `finding_class`, `subtype`,
  `risk`, `requirement_id`, `machine_state`, `human_state` de ningún registro).

Lo que G0 hace: **congelar** los 457 findings deterministas L2 y su atestación de reproducibilidad
como punto de partida verificable e inmutable del arco SHADOW.

---

## 1 · Origen y reproducibilidad

`run_v2_pipeline(["RW-0005","RW-0006","RW-0009","RW-0011","RW-0012","RW-0014"])` ejecutado sobre el
código de `0e1e88a` (worktree = checkout principal, byte-idéntico en toda la ruta del pipeline —
`git diff --stat HEAD` vacío + `md5sum` iguales para `v2_runtime.py`, `regulatory_tier1.py`,
`functional_findings.py`, `technical_findings.py`, `report_v2.py`, `evidence_bundle.py`,
`graph/build.py`).

| Atestación | Valor | vs baseline F5 |
|---|---|---|
| `RUN_ID` | `diag-corpus-20260902` | — |
| `INPUT_CONFIG_FINGERPRINT` | `3fcb3ae859091000b0e6c6cf2b4f51515e74665d658451b753c723d6e6e51668` | ✅ idéntico |
| `GRAPH_SNAPSHOT_FINGERPRINT` | `2fdda0e2ce513bc48b54038c5890a0b060e87a6e5c0d6d98b3d31fb149be3620` | ✅ idéntico |
| `FINDINGS_FINGERPRINT` (ENFORCE) | `235f724a738ce783e2d0152991f6165c5ee075037e7d0fe6a66c8f16c96f2c23` | ✅ idéntico — **ancla inmutable del arco** |
| Counts por módulo (reg / func / tech) | 342 / 90 / 25 | ✅ idéntico |
| `analysis_coverage_mode` efectivo | `ENFORCE` (D-2 `D-2-H7-20260830` + thresholds SIGNED) | ✅ |
| `LLM_CALLS` / `EMBEDDING_CALLS` | 0 / 0 | ✅ |
| `DOCUMENT_EGRESS_BYTES` | 0 (bajo `network_locked()`) | ✅ |
| `human_gate_intact` | True | ✅ |
| `canonical_store` LOGICAL vs `VALIDATION_BASELINE_MANIFEST` | 6/6 match | ✅ |

---

## 2 · Contenido congelado — `FINAL_GMP_CORPUS_FINDINGS.json`

Unión de `regulatory_findings.json + functional_findings.json + technical_findings.json` de la
corrida, en el mismo orden que `run_v2_pipeline` construye `all_findings = reg + func + tech`.

| Métrica | Valor | Criterio G0 |
|---|---|---|
| `total_records` | **457** | **457/457 ✅** |
| `unique_finding_record_id` | **457** | **457 únicos ✅** |
| `unique_finding_id` | 259 | esperado (H-3: `finding_id` colisiona cuando varios sub-criterios comparten `source_text`; `finding_record_id` es la clave única) |
| `by_human_state` | `UNREVIEWED` 457 | **100 % ✅** (ningún path del pipeline cambia `human_state`) |
| `by_machine_state` | `MACHINE_INCONCLUSIVE` 377 · `MACHINE_DEVIATION_CANDIDATE` 80 | — |
| `by_class` | `RegulatoryFinding` 342 · `TestCoverageFinding` 70 · `FunctionalFinding` 20 · `TraceabilityFinding` 8 · `TechnicalFinding` 6 · `SecurityFinding` 5 · `DataIntegrityFinding` 6 | — |
| `by_document` | RW-0005 88 · RW-0006 133 · RW-0009 57 · RW-0011 58 · RW-0012 62 · RW-0014 59 | — |

`FINAL_GMP_CORPUS_FINDINGS.json` sha256: `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c`.

---

## 3 · Atribución de los 342 `REGULATORY_INCONCLUSIVE` (redacción obligatoria §5 del diseño v1.1)

```
HECHO (de la corrida diag-corpus-20260902):
  Los 342 REGULATORY_INCONCLUSIVE los produjo el MOTOR DETERMINISTA Tier-1 (Palanca C).
  En esa corrida: LLM_CALLS = 0, MODEL = null, PROVIDER = null.
  Tier-1 no encontró eco léxico anclado en 6 docs × 12 requisitos → todos INCONCLUSIVE.

RIESGO (de experimentos previos, NO de esta corrida):
  El juicio semántico del 7B sobre paráfrasis tiene techo medido (1–2/7; 4/7 confirmado por
  experimento directo; R2 CERRADO sin alcanzar el gate >= 6/7).

Ambos respaldan precaución. NO se afirma que "el 7B produjo recall 0 en esta corrida": el 7B no se
ejecutó. La precaución sobre el bloque regulatorio (triage, no juicio) se sostiene en el RIESGO
histórico, no en atribuir al 7B un resultado de una corrida determinista.
```

**Verificación en los datos congelados** (`FINAL_GMP_CORPUS_FINDINGS.json → regulatory_inconclusive_attribution`):

| Campo | Valor |
|---|---|
| `count` | 342 |
| `producer` | `regulatory_tier1` (motor DETERMINISTA Tier-1 / Palanca C) |
| `all_agent_id_regulatory_tier1` | **True** — los 342 tienen `provenance.agent_id == "regulatory_tier1"` |
| `by_adjudicator_state` | `{ "TIER1": 342 }` — ningún `adjudicator_state` de juicio LLM |
| `llm_involved` | **False** |

Ninguno de los 342 registros tiene `MODEL`, `PROVIDER`, `PROMPT_ID` ni `LLM_CALL_ID`: no hubo
llamada a modelo. La producción es 100 % determinista (`regulatory_tier1.py::regulatory_tier1_findings`
→ `evidence_bundle` BM25 + `evidence_verifier` sobre eco léxico).

---

## 4 · Routing primario congelado (para G1) — reconciliado con el diagnóstico

Suma exacta **457** (routing primario exclusivo); `cross_domain_flag` es atributo secundario, **no** un 5º bucket.

| Bucket primario | Nº | Composición | Regla determinista |
|---|---:|---|---|
| REGULATORY | 285 | `REGULATORY_INCONCLUSIVE` 285 | `agent_id == regulatory_tier1` ∧ `document != RW-0009` → **triage de ≤5 candidatos, NO juicio** |
| FUNCTIONAL / TRACEABILITY | 98 | `REQUIREMENT_NOT_TESTED` 70 · `IMPLEMENTATION_WITHOUT_REQUIREMENT` 20 · `ORPHAN_DESIGN_ELEMENT` 8 | `evidence_basis == ABSENCE_DEPENDENT` ∧ `agent_id ∈ {test_coverage_agent, cross_document_agent, requirements_traceability_agent, functional_consistency_agent}` |
| TECHNICAL | 17 | `AUTHORITY_CHECK_GAP` 3 · `ALCOA_ATTRIBUTABLE_GAP` 4 · `AUDIT_TRAIL_DESIGN_GAP` 2 · `BACKUP_RECOVERY_GAP` 2 · `ACCESS_CONTROL_GAP` 2 · `TECHNICAL_DESIGN_GAP` 2 · `AUDIT_TRAIL_INTEGRITY_GAP` 2 | `technical_basis` presente (regla de completitud gobernada) |
| HUMAN_ONLY | 57 | `REGULATORY_INCONCLUSIVE` 57 (todos RW-0009) | `document == RW-0009` (`NOT_ANALYZABLE`) → **NUNCA al LLM** |
| **TOTAL** | **457** | | |

`cross_domain_flag = YES` sobre **15 relaciones** (gap técnico + `INCONCLUSIVE` regulatorio sobre
la misma regla y el mismo documento; `21_CFR_11.10(d/e/g)`, `ANNEX11_17`, `ALCOA_ATTRIBUTABLE`).
Detalle en `CURRENT_FINDING_AGENT_ROUTING.json → summary.cross_domain_same_requirement_family_detail`.

Reconciliación con el bucket epistémico del diagnóstico: `LLM_EXPERT_REVIEW_CANDIDATE` 372 +
`LLM_EXPLANATION_USEFUL` 28 + `HUMAN_ONLY` 57 = 457. Los 28 "explanation-only" (20
`IMPLEMENTATION_WITHOUT_REQUIREMENT` + 8 `ORPHAN_DESIGN_ELEMENT`) quedan bajo el experto
FUNCTIONAL/TRACEABILITY. `285 + (70+20+8) + 17 + 57 = 457`.

---

## 5 · Frontera dura L2 (recordatorio para todo el arco)

Los 457 registros de `FINAL_GMP_CORPUS_FINDINGS.json` son **L2 inmutable**. La capa LLM (L3/L4) es
aditiva y vive bajo `<run_dir>/shadow/` o `docs_plan/shadow_llm/`. No puede tocar
`class/subtype/severity/risk/requirement_id/machine_state/human_state/related_finding_ids`, no
puede mover `FINDINGS_FINGERPRINT` (`235f724a…`), y `human_state` solo lo cambia un humano vía
`set_human_state(reviewer=<nombre real>)` (L5).

---

## 6 · Artefactos G0 (bajo `docs_plan/shadow_llm/`)

| Fichero | sha256 |
|---|---|
| `FINAL_GMP_CORPUS_FINDINGS.json` | `95a79f9b6276ff2a7972100764b308fa4b09f0027c6679ea831b441eb880f02c` |
| `FINAL_GMP_CORPUS_ANALYSIS_REPORT.md` | (este fichero — ver `git show`) |
| `DESIGN_LLM_INTERPRETATION_LAYER_v1.1.md` | (diseño v1.1 congelado verbatim) |
| `G0_BASELINE_CONSOLIDATION.md` | (registro de ejecución de fase + reporte formato v1.1 + criterios del gate) |
| `G0_inputs/CLAUDE_WEB_POST_RECONCILIATION_DESIGN_INPUT_V1.md` | `b28bbdcc634cd8310c033615f49b0224c3755491afe58ff11f0db37c0d727ecc` |
| `G0_inputs/CURRENT_CORPUS_AGENT_DIAGNOSTIC.md` | `079f5ba385bd4d7d4755687f3a77ab84b293dcd7755e93dc81bf36d1379ae2fa` |
| `G0_inputs/CURRENT_FINDING_AGENT_ROUTING.json` | `490a26b55e2d9f3538d49349a3181d68e33452c6aac9b66088136d4500e68ba6` |
| `G0_inputs/CURRENT_RUNTIME_AGENT_MAP.json` | `49e7a58340e7cb3905d88ad61b61e1cd1cbf7d5429509cfd4ef5d1837f29c6f4` |
| `G0_inputs/FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md` | `c389e831b232e495a8c4f7b98e4cf9e623a0f9f263529561dbe1ec2a16713ce0` |

---

*G0 · formalización de baseline. Sin re-extracción, sin nueva caracterización, sin re-juicio, sin
LLM, sin mover el fingerprint, sin tocar L0/L1/L2. La decisión final es humana.*
