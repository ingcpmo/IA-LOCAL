# DIAGNÓSTICO DEL CORPUS + MAPA REAL DE PARTICIPACIÓN DE AGENTES

**Fecha:** 2026-09-02 · **Modo:** READ-ONLY · sin fixes, sin commits, sin PILOT-035, sin R2, sin habilitar producción.
**Base:** rama `fix/clon-local-validacion`, HEAD `0e1e88a` (tag de aceptación `reconc-acceptance-v1`).
**Corrida diagnóstica:** `RUN_ID = diag-corpus-20260902` — una (1) ejecución real de `run_v2_pipeline`
equivalente al **escenario A** del R-PAR (stores de producción, config gobernada `ENFORCE`).
Ningún store, grafo, audit trail ni fichero del repo fue modificado; los artefactos de la corrida
viven fuera del árbol del repo (`/tmp/.../scratchpad/diag_out/`).

Los datos por-hallazgo están en `CURRENT_FINDING_AGENT_ROUTING.json`; el mapa de runtime en
`CURRENT_RUNTIME_AGENT_MAP.json`. Este documento los interpreta.

---

## 1 · Executive Summary

- El **runtime V2 actual es 100 % determinista y CERO LLM**. `LLM_CALLS = 0`,
  `EMBEDDING_CALLS = 0`, `DOCUMENT_EGRESS_BYTES = 0`, `human_gate_intact = True`
  (los 457 hallazgos nacen y quedan `human_state = UNREVIEWED`).
- La corrida reproduce **exactamente** la baseline aceptada:
  `findings_fingerprint = 235f724a…` (= F5 ENFORCE = escenario A de la Acceptance V1),
  `input_config = 3fcb3ae8…`, `graph_snapshot = 2fdda0e2…`, `457` hallazgos
  (`342` regulatorios / `90` funcionales / `25` técnicos por módulo).
- **Ningún `agent_id` corresponde a una LLM ejecutada.** Los 8 `agent_id` que aparecen en
  `provenance` son **etiquetas de propiedad lógica** puestas por código determinista. El
  `AGENT_TYPE` real de los 457 hallazgos es `DETERMINISTIC_LOGIC`; `LLM_ACTUALLY_EXECUTED_FOR_THIS_FINDING = NO`
  en el 100 %.
- Existe código de **juicio LLM presente pero NO ejecutado** (`factory/regulatory/v2_judgment/*`,
  `chunked_engine.evaluate_chunked`, `retrieval/judgment.py`, capa semántica `retrieval/embed*`).
  `v2_runtime.py` no importa ninguno.
- **La clase Regulatory colapsó al peor caso**: los 342 hallazgos regulatorios son **todos
  `REGULATORY_INCONCLUSIVE`** — cero `REGULATORY_COMPLIANT_EVIDENCE`. El motor Tier-1 no encontró
  **un solo eco léxico anclado** en los 6 documentos × 12 sub-criterios. Es la manifestación
  directa del techo de recall del modelo (declarado en `CLAUDE.md` y `ROADMAP_ANALIZADOR_GMP.md`).
- El **reporte final NO usa LLM**: `report_v2.build_report/render_markdown` copia datos
  estructurados a una tabla por plantilla. **Cobertura factual 457/457 (0 hallazgos perdidos,
  0 afirmaciones no respaldadas).**
- `MULTI_AGENT_RUNTIME_CURRENTLY_ACTIVE = NO`.

---

## 2 · Runtime ejecutado

| Campo | Valor |
|---|---|
| `RUN_ID` | `diag-corpus-20260902` |
| `ACTIVE_ENGINE` | `V2` — `factory/regulatory/validation_v2/v2_runtime.py::run_v2_pipeline` |
| `ROUTING_MODE` | Regulatory = **Tier-1 / Palanca C** (determinista); Functional = B6a determinista; Technical = B6b v1 (grafo) + v2 (reglas de completitud gobernadas firmadas). `analysis_coverage_mode` **EFECTIVO = `ENFORCE`** (parámetro gobernado, D-2 firmado + thresholds SIGNED) |
| `INPUT_DOCUMENTS` | RW-0005, RW-0006, RW-0009, RW-0011, RW-0012, RW-0014 |
| `INPUT_SHA256` (canonical_store sqlite3, bytes) | RW-0005 `6e7378f6…` · RW-0006 `f583f5e2…` · RW-0009 `ccbe49e7…` · RW-0011 `38f6e71a…` · RW-0012 `8427216c…` · RW-0014 `3e318b5c…` |
| `INPUT` verificado | `LOGICAL_CONTENT_HASH` de los 6 stores == `VALIDATION_BASELINE_MANIFEST` (**6/6 match**, fail-closed si drift). PDFs origen: ver `docs_plan/reconc/POST_CLOSURE_ACCEPTANCE_RUN.md §5` |
| `TOTAL_FINDINGS` | **457** |
| `REGULATORY_FINDINGS` | **342** — 100 % `REGULATORY_INCONCLUSIVE` |
| `FUNCTIONAL_FINDINGS` | **90** (retorno del módulo) → por clase: `TestCoverageFinding` 70 (`REQUIREMENT_NOT_TESTED`) + `FunctionalFinding` 20 (`IMPLEMENTATION_WITHOUT_REQUIREMENT`). `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` = 0, `REQUIREMENT_NOT_TRACED` = 0 |
| `TECHNICAL_FINDINGS` | **25** (retorno del módulo) → `TechnicalFinding` 6, `SecurityFinding` 5, `DataIntegrityFinding` 6, `TraceabilityFinding` 8 (`ORPHAN_DESIGN_ELEMENT`). `INTERFACE_INCONSISTENCY` = 0 |
| `OTHER_FINDING_CLASSES` (agregado real por clase) | `RegulatoryFinding` 342 · `TestCoverageFinding` 70 · `FunctionalFinding` 20 · `TraceabilityFinding` 8 · `TechnicalFinding` 6 · `SecurityFinding` 5 · `DataIntegrityFinding` 6 |
| `LLM_CALLS` | **0** |
| `EMBEDDING_CALLS` | **0** |
| `DOCUMENT_EGRESS_BYTES` | **0** (bajo `network_locked()`) |
| `HUMAN_GATE_INTACT` | **True** — 457/457 `human_state = UNREVIEWED`, 0 estados prohibidos |
| Fingerprints | `input_config 3fcb3ae859091000…` · `graph_snapshot 2fdda0e2ce513bc4…` · `findings 235f724a738ce783…` (idénticos a la Acceptance V1 escenario A) |
| Grafo | aristas: `implemented_by` 1120 · `designed_by` 190 · `regulated_by` 20. Snapshot inmutable congelado en el paquete |
| Wall clock | ~6.7 s (6 docs, sin re-extracción; stores de producción reutilizados) |
| Egress controls | `egress_controls` registrado en `audit_metadata.json` (monkeypatch de socket + sonda de red) |

Outputs conservados: `informe_hallazgos_v2.md` (156 KB), `compliance_matrices/final_report_v2.json`,
`{regulatory,functional,technical}_findings.json`, `evidence_provenance.json`,
`analysis_coverage.json` + `_queues.json`, `graph_snapshot/graph_snapshot.json`,
`remediation/rem-*.json` (8), `corrected_documents/*.docx`, `audit_summary/audit_metadata.json`,
`manifest.json`, `SHA256SUMS.txt`, `package_receipt.json` (`zip_sha256 cc46aab4…`).

---

## 3 · Resultados GMP actuales

**Por banda de riesgo (post-ENFORCE):** `HIGH` 355 · `LOW` 78 · `MEDIUM` 22 · `CRITICAL` 2.
**Por estado de máquina:** `MACHINE_INCONCLUSIVE` 377 · `MACHINE_DEVIATION_CANDIDATE` 80.
**Por estado humano:** `UNREVIEWED` 457 (100 %).
**Por documento:** RW-0005 88 · RW-0006 133 · RW-0009 57 · RW-0011 58 · RW-0012 62 · RW-0014 59.

**Adecuación de extracción:** RW-0009 = `NOT_ANALYZABLE` (SAT escaneado); los otros 5 = `ANALYZABLE`.

**Cobertura del análisis — dos colas gobernadas (modo `ENFORCE`):**

| Cola | Findings | Desglose |
|---|---|---|
| `ACTIONABLE_NOW` | 30 | cobertura suficiente; no depende de capacidad ausente |
| `BLOCKED_BY_COVERAGE_OR_EVIDENCE` | 427 | 78 por cobertura MISSING/DEGRADED (`would_degrade=true`) · 349 por método `INDETERMINATE` (juicio semántico fuera de alcance), incl. **57 anclados en RW-0009** |
| Total | 457 | coherente = `True` |

**Efecto ENFORCE:** regla aplicada a 78 hallazgos (`would_degrade_true`); banda numéricamente
bajada en 70 (el resto ya estaba en `LOW`). En `OBSERVE` habría sido 0.

**Remediación:** 8 borradores (límite `remediation_limit=8`) de los 80
`MACHINE_DEVIATION_CANDIDATE`. Cada uno: `Finding → Directive → candidate.docx → redline.docx →
manifest`, todos `MACHINE GENERATED / NOT_QA_APPROVED`. Texto de remediación **por plantilla
determinista** (`_proposed_text_for`), **CERO LLM** — nombra el comportamiento requerido, no lo
redacta a medida.

---

## 4 · Arquitectura efectiva (`CODE_PATH_EXECUTED`)

```
PDF (no en este run)
  └─ [PRE-EXISTENTE] extract_document → canonical_store/*.sqlite3        DET · sin LLM · sin embeddings
        (en este run se reusaron los 6 stores de producción, hash lógico == baseline)
  ▼
graph/build.py::build_project_graph → graph_store + snapshot inmutable   DET · sin LLM
  ▼
retrieval/evidence_bundle.py::build_bundles_for_requirement             DET · BM25 + rerank léxico
   (retrieval_mode = "bm25"; el modo "fusion" con embeddings NO se invoca)
  ▼
findings/regulatory_tier1.py::regulatory_tier1_findings                 DET · Palanca C · sin LLM
   eco léxico anclado (evidence_verifier, validación A) → COMPLIANT      [0 en este corpus]
   todo lo demás → REGULATORY_INCONCLUSIVE + candidatos de recuperación  [342]
  ▼
findings/functional_findings.py::graph_functional_findings              DET · recorrido de grafo
  ▼
findings/technical_findings.py::graph_technical_findings                DET · grafo (B6b v1)
   + completeness_findings (B6b v2, technical_completeness_rules.yaml SIGNED, fail-closed)
  ▼
findings/risk.py::compute_risk + risk_matrix.yaml                       DET · ENFORCE degrada 78
  ▼
findings/remediation_v2.py + services/candidate_document_generator.py   DET · plantilla · sin LLM
  ▼
findings/report_v2.py::build_report / render_markdown                   DET · plantilla · sin LLM
```

Detalle etapa-por-etapa (SOURCE_FILE / FUNCTION / INPUT / OUTPUT / DETERMINISTIC / LLM_USED /
EMBEDDINGS_USED / MODEL / PROVIDER) en `CURRENT_RUNTIME_AGENT_MAP.json → pipeline_stages`.
**Todas las etapas:** `DETERMINISTIC = YES`, `LLM_USED = NO`, `EMBEDDINGS_USED = NO`,
`MODEL = null`, `PROVIDER = null`.

---

## 5 · Participación real de cada componente / "agente"

Inventario de todo componente que el código llama `agent` / `critic` / `adjudicator` /
`reviewer` / `reporter` / `composer` (detalle completo en `CURRENT_RUNTIME_AGENT_MAP.json →
components`):

| AGENT_OR_COMPONENT_ID | SOURCE_FILE | LLM_BACKED | ACTIVE_IN_RUNTIME | Nº findings este run | CAN_CHANGE_FINDING / RISK / HUMAN_STATE |
|---|---|---|---|---:|---|
| `regulatory_tier1` | `findings/regulatory_tier1.py` | **NO** | **SÍ** | 342 | produce el finding / NO / NO |
| `test_coverage_agent` | `findings/functional_findings.py` (+ `technical_findings.py`) | **NO** | **SÍ** | 70 | produce / NO / NO |
| `cross_document_agent` | `findings/functional_findings.py` | **NO** | **SÍ** | 20 | produce / NO / NO |
| `requirements_traceability_agent` | `findings/functional_findings.py` + `technical_findings.py` | **NO** | **SÍ** | 8 | produce / NO / NO |
| `technical_design_agent` | `findings/technical_findings.py` | **NO** | **SÍ** | 6 | produce / NO / NO |
| `security_architecture_agent` | `findings/technical_findings.py::completeness_findings` | **NO** | **SÍ** | 5 | produce / NO / NO |
| `data_integrity_agent` | `findings/technical_findings.py::completeness_findings` | **NO** | **SÍ** | 6 | produce / NO / NO |
| `functional_consistency_agent` | `findings/functional_findings.py` | **NO** | **SÍ** (código activo) | **0** (sin `contradicts` en el corpus) | produce / NO / NO |
| `report_v2` (`build_report`/`render_markdown`) | `findings/report_v2.py` | **NO** | **SÍ** | n/a (consumidor) | **NO / NO / NO** |

**Ningún componente activo puede cambiar `risk` ni `human_state`.** `risk` sale de `compute_risk`
determinista; `human_state` nace `UNREVIEWED` y ningún path del runtime lo toca (solo un revisor
humano con nombre real, `CLAUDE.md`).

**Los `agent_id` NO son agentes LLM.** Son literales de string asignados en `FindingProvenance(...)`
para clasificar ownership. `provenance.adjudicator_state` vale `"TIER1"` en los 342 regulatorios
y `null` en el resto — no hay adjudicador LLM en curso.

---

## 6 · LLM activa vs presente-en-código

| Componente | `CODE_PATH_PRESENT` | `CODE_PATH_EXECUTED` | Evidencia |
|---|---|---|---|
| `v2_judgment/judgment_v2.py` (hunter → verifier → critic → adjudicator) | SÍ | **NO** | `v2_runtime.py` no lo importa; solo lo usan scripts de `factory/docs/design/regulatory_redesign_v2/*` y tests |
| `v2_judgment/adjudicator.py`, `critic.py`, `prompts.py` | SÍ | **NO** | idem |
| `engines/gmpai_integrity/chunked_engine.py::evaluate_chunked` + `ollama_client.py` + `model_provider.py` | SÍ | **NO** | no en `v2_runtime`; requiere `PILOT_EXECUTION` firmada (`human_confirmed`) |
| `retrieval/judgment.py::run_judgment_batch` | SÍ | **NO** | solo scripts de medición R2 |
| `retrieval/{embed,embed_index,embed_runner,fusion}.py` (capa semántica) | SÍ | **NO** | `evidence_bundle` corre en modo `bm25`; nunca llama `fusion`. `embedding_calls = 0` |
| `engines/gmpai_integrity/prompts/*.yaml` (contenido gobernado) | SÍ | **NO** (no cargado) | ninguna llamada de juicio en el run |

> La existencia de `v2_judgment/`, prompts firmados o `evaluate_chunked` **no demuestra
> ejecución**. En esta corrida: `audit_metadata.json → llm_calls = 0`, `embedding_calls = 0`.

---

## 7 · Findings por productor

| PRODUCED_BY_MODULE | FUNCTION | agent_id | subtype | Nº |
|---|---|---|---|---:|
| `findings/regulatory_tier1.py` | `regulatory_tier1_findings` | `regulatory_tier1` | `REGULATORY_INCONCLUSIVE` | **342** |
| `findings/functional_findings.py` | `graph_functional_findings` | `test_coverage_agent` | `REQUIREMENT_NOT_TESTED` | 70 |
| `findings/functional_findings.py` | `graph_functional_findings` | `cross_document_agent` | `IMPLEMENTATION_WITHOUT_REQUIREMENT` | 20 |
| `findings/technical_findings.py` | `graph_technical_findings` (B6b v1) | `requirements_traceability_agent` | `ORPHAN_DESIGN_ELEMENT` | 8 |
| `findings/technical_findings.py` | `completeness_findings` (B6b v2) | `technical_design_agent` | `AUDIT_TRAIL_DESIGN_GAP` | 2 |
| `findings/technical_findings.py` | `completeness_findings` | `technical_design_agent` | `BACKUP_RECOVERY_GAP` | 2 |
| `findings/technical_findings.py` | `completeness_findings` | `technical_design_agent` | `TECHNICAL_DESIGN_GAP` | 2 |
| `findings/technical_findings.py` | `completeness_findings` | `security_architecture_agent` | `ACCESS_CONTROL_GAP` | 2 |
| `findings/technical_findings.py` | `completeness_findings` | `security_architecture_agent` | `AUTHORITY_CHECK_GAP` | 3 |
| `findings/technical_findings.py` | `completeness_findings` | `data_integrity_agent` | `AUDIT_TRAIL_INTEGRITY_GAP` | 2 |
| `findings/technical_findings.py` | `completeness_findings` | `data_integrity_agent` | `ALCOA_ATTRIBUTABLE_GAP` | 4 |

Los 25 técnicos = 8 `ORPHAN_DESIGN_ELEMENT` (grafo) + 17 reglas de completitud gobernadas.
`INTERFACE_INCONSISTENCY` (grafo) no disparó en este corpus.

`LLM_ACTUALLY_EXECUTED_FOR_THIS_FINDING = NO` · `LLM_MODEL = NOT_EXECUTED` ·
`PROMPT_ID = NOT_EXECUTED` · `LLM_CALL_ID = NOT_EXECUTED` para **los 457**.

---

## 8 · Findings candidatos a revisión LLM (clasificación determinista, sin ejecutar LLM)

Reglas explícitas (código: `gen_artifacts.py::classify`; resultado por-hallazgo en
`CURRENT_FINDING_AGENT_ROUTING.json → findings[].REVIEW_CLASSIFICATION`):

| Regla (en orden) | Clasificación | Nº |
|---|---|---:|
| `document_id == RW-0009` (NOT_ANALYZABLE) | `HUMAN_ONLY` | **57** |
| `agent_id == regulatory_tier1` (motor declina el juicio de paráfrasis, `evidence_basis=INDETERMINATE`) | `LLM_EXPERT_REVIEW_CANDIDATE` (REGULATORY) | **285** |
| `evidence_basis == ABSENCE_DEPENDENT` ∧ `machine_state == MACHINE_DEVIATION_CANDIDATE` | `LLM_EXPERT_REVIEW_CANDIDATE` (FUNCTIONAL_TRACEABILITY / TECHNICAL_VALIDATION) | **87** |
| `evidence_basis == ABSENCE_DEPENDENT` ∧ `machine_state == MACHINE_INCONCLUSIVE` (LOW) | `LLM_EXPLANATION_USEFUL` | **28** |
| `technical_basis` presente (regla de completitud gobernada) | `LLM_EXPERT_REVIEW_CANDIDATE` (TECHNICAL_VALIDATION) | (incluidos arriba) |
| resto | `DETERMINISTIC_SUFFICIENT` | **0** |

Totales: `LLM_EXPERT_REVIEW_CANDIDATE` **372** · `LLM_EXPLANATION_USEFUL` **28** ·
`HUMAN_ONLY` **57** · `DETERMINISTIC_SUFFICIENT` **0**.

Para cada candidato el JSON lleva `RECOMMENDED_EXPERT`, `WHY_LLM_MAY_ADD_VALUE` y
`REQUIRED_CONTEXT`. Resumen de por qué:

- **REGULATORY (285):** el motor determinista **explícitamente abstiene** (Palanca C). Un experto
  LLM podría **triar** los ≤5 candidatos BM25 de recuperación para el revisor humano.
  **Nota honesta:** la detección automática de evidencia parafraseada tiene techo **medido 1–2/7**
  (R2 CERRADO sin alcanzar el gate; confirmado 4/7 casos por experimento directo). El valor es
  asistencia al humano, **nunca** una conclusión de cumplimiento.
  `REQUIRED_CONTEXT`: sub-criterio firmado + `EvidenceBundle` con provenance + `requirement_terms.yaml` + página/sección ancladas.
- **FUNCTIONAL_TRACEABILITY (98):** la conclusión es "falta una arista del grafo". El LLM podría
  juzgar si la ausencia es **real** o un **límite de extracción** (id presente sin arista).
  `REQUIRED_CONTEXT`: `source_text` ancla + `graph_path` + claims vecinos por id + documentos aguas abajo.
- **TECHNICAL_VALIDATION (17):** regla "tema obligatorio presente + comportamiento requerido
  ausente en el alcance". El LLM podría verificar si el comportamiento **sí está, parafraseado**,
  dentro del alcance context-scoped → reduciría falsos gaps.
  `REQUIRED_CONTEXT`: `CASE_ID` + `REQUIRED_BEHAVIOR` + `CONTROL_OBJECTIVE` + `scope_recs` + `family_signals`.

---

## 9 · Carga potencial por experto (solo candidatos LLM)

| Experto | total_candidate_findings | by_subtype | by_risk |
|---|---:|---|---|
| `REGULATORY_EXPERT` | **285** | `REGULATORY_INCONCLUSIVE` 285 | `HIGH` 285 |
| `FUNCTIONAL_TRACEABILITY_EXPERT` | **98** | `REQUIREMENT_NOT_TESTED` 70 · `IMPLEMENTATION_WITHOUT_REQUIREMENT` 20 · `ORPHAN_DESIGN_ELEMENT` 8 | `LOW` 78 · `MEDIUM` 20 |
| `TECHNICAL_VALIDATION_EXPERT` | **17** | `AUTHORITY_CHECK_GAP` 3 · `ALCOA_ATTRIBUTABLE_GAP` 4 · `AUDIT_TRAIL_DESIGN_GAP` 2 · `BACKUP_RECOVERY_GAP` 2 · `ACCESS_CONTROL_GAP` 2 · `TECHNICAL_DESIGN_GAP` 2 · `AUDIT_TRAIL_INTEGRITY_GAP` 2 | `HIGH` 13 · `MEDIUM` 2 · `CRITICAL` 2 |
| `CROSS_DOMAIN` | **15** | ver §10 | — |
| `DETERMINISTIC_ONLY` | **0** | — | — |
| `HUMAN_ONLY` | **57** | todos RW-0009 (`REGULATORY_INCONCLUSIVE` 57 anclados en documento NOT_ANALYZABLE) | `HIGH` 57 |

Reparto por documento en `CURRENT_FINDING_AGENT_ROUTING.json → expert_potential_load[*].by_document`.

---

## 10 · Overlap / cross-domain

`FINDINGS_ASSIGNED_TO_MORE_THAN_ONE_EXPERT = 15` (medida precisa).

**Medida gruesa** (celda `(document, page)` tocada por ≥2 dominios de experto): 350 — **baja
señal**, dominada por los `REGULATORY_INCONCLUSIVE` que se anclan en páginas bajas (1, 2) donde
también caen hallazgos funcionales/técnicos. No es overlap real de contenido.

**Medida precisa (15):** un hallazgo **técnico/seguridad/integridad de datos** de regla de
completitud cuya **regulación fuente gobernada** es *la misma regulación* que `regulatory_tier1`
marcó `INCONCLUSIVE` **en el mismo documento**. Es decir: una capa afirma un *gap concreto*, la
otra *se declara incapaz de juzgar*, sobre la **regla idéntica**:

| Documento | Hallazgo técnico | Regulación compartida (también INCONCLUSIVE en el mismo doc) |
|---|---|---|
| RW-0005, RW-0006 | `AUDIT_TRAIL_DESIGN_GAP` | `21_CFR_11.10(e)` |
| RW-0005, RW-0006 | `AUDIT_TRAIL_INTEGRITY_GAP` | `21_CFR_11.10(e)` |
| RW-0005, RW-0006 | `ACCESS_CONTROL_GAP` | `21_CFR_11.10(g)` |
| RW-0005, RW-0006, RW-0014 | `AUTHORITY_CHECK_GAP` | `21_CFR_11.10(g)` |
| RW-0005, RW-0006 | `TECHNICAL_DESIGN_GAP` | `ANNEX11_17` |
| RW-0005, RW-0011, RW-0012, RW-0014 | `ALCOA_ATTRIBUTABLE_GAP` | `21_CFR_11.10(d)` + `ALCOA_ATTRIBUTABLE` |

**Explicación de cada caso:** el revisor (o un experto cross-domain) necesita **reconciliar** las
dos señales: el hallazgo técnico dice "el comportamiento requerido por §X no aparece en el
alcance"; el hallazgo regulatorio dice "no puedo confirmar/negar §X por paráfrasis". Un experto
cross-domain aportaría al **cerrar esa contradicción aparente** para el humano — nunca
resolviéndola automáticamente.

Lista completa con `finding_record_id` en
`CURRENT_FINDING_AGENT_ROUTING.json → summary.cross_domain_same_requirement_family_detail`.

---

## 11 · Funcionamiento del reporte actual

| Campo | Valor |
|---|---|
| `REPORT_GENERATOR` | `report_v2.build_report` + `report_v2.render_markdown` (+ sección H-7 de 2 colas añadida por `v2_runtime`) |
| `SOURCE_FILE` | `factory/regulatory/findings/report_v2.py` |
| `USES_LLM` | **NO** |
| `LLM_CALLS_FOR_REPORT` | **0** |
| `INPUT_TO_REPORT` | las **457** instancias `Finding` en memoria (`reg + func + tech`) |
| `OUTPUT_REPORT` | `informe_hallazgos_v2.md` (457 filas de tabla + resumen + sección de 2 colas) · `compliance_matrices/final_report_v2.json` |

**Qué hace el reporte:**

| ¿…? | Respuesta |
|---|---|
| copia datos estructurados | **SÍ** — `as_dict(f)` por hallazgo |
| utiliza templates | **SÍ** — f-strings, tabla markdown fija por clase |
| genera narrativa | **NO** |
| interpreta findings | **NO** |
| utiliza LLM | **NO** |
| modifica rationale | **NO** — solo **trunca** a 180 caracteres *en la celda markdown*; el `rationale` íntegro queda en el JSON |
| agrupa findings | solo para **presentación** (por `finding_class`); no fusiona ni deduplica |
| pierde findings | **NO** |

| Métrica | Valor |
|---|---|
| `REPORT_FINDINGS_INPUT_COUNT` | 457 |
| `REPORT_FINDINGS_REFERENCED_COUNT` | 457 (342+70+20+8+6+5+6 filas, verificado) |
| `MISSING_FROM_REPORT` | **0** |
| `UNSUPPORTED_REPORT_CLAIMS` | **0** — los conteos del resumen se recomputan de la lista; la cabecera es un disclaimer estático (`BORRADOR ASISTIDO, NO es declaración de cumplimiento…`) |

**Observación menor (no es pérdida de hallazgo):** `finding_id` colisiona (259 únicos de 457 —
varios sub-criterios comparten `source_text`); `finding_record_id` es único 457/457. El reporte
lista por `finding_record_id`, así que ninguna fila se pisa.

---

## 12 · Vacíos detectados

1. **Recall regulatorio = 0 en el corpus real.** 342/342 regulatorios `INCONCLUSIVE`, cero eco
   léxico anclado. El analizador **no confirma cumplimiento de ningún sub-criterio Part 11 /
   Annex 11 / ALCOA** en los 6 documentos. Es coherente con el techo del modelo — pero significa
   que, hoy, toda la carga regulatoria cae en el revisor humano.
2. **RW-0009 no aporta análisis útil** (57 hallazgos, todos bloqueados, documento
   `NOT_ANALYZABLE`). Sin mejor extracción (H7/MarkItDown, diferido) es ruido para el humano.
3. **`functional_consistency_agent` y `INTERFACE_INCONSISTENCY` nunca dispararon** — 0 aristas
   `contradicts` y 0 divergencias de interfaz en el corpus. No se puede afirmar que funcionen
   sobre datos reales; solo que no producen falsos positivos aquí.
4. **`REQUIREMENT_NOT_TRACED` = 0 emitidos** — el filtro de confianza (claim "parece requisito" +
   lleva id de referencia) suprime todo en este corpus. Es una decisión de precisión declarada,
   pero deja la trazabilidad URS→abajo sin señal automática.
5. **La contradicción técnica↔regulatoria (§10, 15 casos) no se reconcilia en ningún lado** —
   dos hallazgos sobre la misma regla y el mismo documento llegan al humano por separado, sin
   enlace `related_finding_ids` entre clases.
6. **El reporte no prioriza ni agrupa por documento/regulación** — 457 filas planas por clase;
   un revisor humano tiene que reconstruir "todo lo de §11.10(e) en RW-0006" a mano.

---

## 13 · Recomendación para SHADOW AGENT PILOT

**`SHADOW_AGENT_PILOT_RECOMMENDED = YES`**, con estas condiciones duras:

- **Shadow estricto:** el/los agente(s) LLM corren **en paralelo**, escriben a un artefacto
  separado (`shadow/*.json`), y **no tienen path de escritura** a `finding_class`, `subtype`,
  `risk`, `requirement_id` ni `human_state`. Se mide contra la adjudicación humana.
- **Alcance inicial = las señales pequeñas y concretas**, no las 285 regulatorias:
  - los **17 `TECHNICAL_VALIDATION`** (regla de completitud: ¿el comportamiento está parafraseado
    en el alcance?) — verificable, `REQUIRED_CONTEXT` acotado, alto valor;
  - los **15 cross-domain** (§10) — reconciliar la contradicción técnica↔regulatoria para el humano;
  - opcionalmente los **87 `FUNCTIONAL_TRACEABILITY` `MACHINE_DEVIATION_CANDIDATE`** (¿ausencia
    de arista real o límite de extracción?).
- **Los 285 `REGULATORY` van al final y solo como triage**, nunca como juicio: el objetivo de
  medición es "¿el shadow ordena bien los ≤5 candidatos para el humano?", con criterio de éxito
  pre-fijado. El techo de paráfrasis está confirmado; no se re-abre esa expectativa.
- **Gobernanza:** cualquier llamada real a Ollama exige `PILOT_EXECUTION` firmada
  (`human_confirmed`); usar la vigente que seleccione `_select_pilot_execution_instance`, **no
  proponer una nueva**. `EMBED_EXECUTION` separada si se activa la capa semántica.
- **Instrumento de medición:** el fixture set 7P+2N sigue siendo el único para recall; el pilot
  shadow añade métricas de *asistencia* (orden de candidatos, tasa de falsos gaps reducidos), no
  sustituye la medición de recall.

---

## 14 · Riesgos de activar LLM

1. **NCRs falsos por bajo recall** (riesgo central declarado en `CLAUDE.md`): un analizador que
   no encuentra evidencia presente produce desviaciones inexistentes. Medido: recall de juicio
   1–2/7, techo del modelo 7B confirmado 4/7 por experimento directo.
2. **Paráfrasis:** evidencia perfectamente aislada que no cambia el juicio del 7B — patrón
   confirmado **dos veces** por vías independientes (R2 paráfrasis, R4 dilución tabular).
   Activar LLM para "encontrar más" no mueve el recall y sí añade coste/latencia.
3. **Egress:** hoy `DOCUMENT_EGRESS_BYTES = 0` bajo `network_locked()`. Toda llamada LLM debe
   quedar dentro del guard de red + monkeypatch de socket; una fuga expone documento de cliente.
4. **No-determinismo:** `temperature=0.0` no garantiza salida idéntica (hallazgo H6 documentado).
   Rompe la reproducibilidad byte-a-byte que hoy tiene el runtime (`findings_fingerprint` estable).
5. **Gobernanza append-only (Part 11):** proponer `PILOT_EXECUTION` de más deja registros
   permanentes que no se pueden retirar (conflicto real ya documentado, `-002/-004/-006/-007/-008`).
6. **Scope creep:** un agente que "explica" se desliza a un agente que "concluye". `CLAUDE.md`
   prohíbe declaración de cumplimiento final, aprobación automática, cierre de CAPA y liberación
   de lote — el shadow no puede tener ningún path que los toque.
7. **Sobre-confianza del revisor:** una narrativa LLM fluida junto a un hallazgo `INCONCLUSIVE`
   puede inducir al humano a aprobar sin verificar la cita. Mitigación: el shadow nunca se
   muestra en el mismo panel que el finding hasta que su precisión esté medida y firmada.

---

## 15 · Conclusión

El runtime V2 que corre hoy sobre los 6 documentos reales es un **analizador documental
determinista**: recorre el modelo canónico y el grafo, aplica reglas gobernadas y de recuperación
léxica, y emite 457 hallazgos **todos** en estado `UNREVIEWED`, sin una sola llamada a modelo ni
byte de egress. Los "agentes" que aparecen en la provenance son **etiquetas de propiedad
lógica**, no procesos LLM. El código de juicio LLM existe en el árbol pero **no está cableado** a
este runtime. El reporte final es una **transcripción estructurada fiel** (457/457, 0 pérdidas, 0
interpretación).

El hueco real no es de arquitectura de agentes: es que **la clase Regulatory no confirma nada**
sobre el corpus real (recall 0), y toda la interpretación cae en el humano. Un **SHADOW AGENT
PILOT acotado** (técnico + cross-domain primero, regulatorio solo como triage, shadow estricto,
`PILOT_EXECUTION`-gated) es la vía razonable para medir si un experto LLM aporta *asistencia*
sin tocar nunca el gate humano — y sin re-abrir la expectativa, ya cerrada, de detección
automática de paráfrasis.

---

```
CORPUS_RUN_EXECUTED = YES  (RUN_ID = diag-corpus-20260902, escenario-A equivalente, READ-ONLY)
TOTAL_FINDINGS      = 457

DETERMINISTIC_FINDINGS = 457
LLM_GENERATED_FINDINGS = 0

ACTIVE_LLM_AGENTS          = 0
ACTIVE_DETERMINISTIC_AGENTS = 8  (regulatory_tier1, test_coverage_agent, cross_document_agent,
                                  requirements_traceability_agent, technical_design_agent,
                                  security_architecture_agent, data_integrity_agent,
                                  functional_consistency_agent[0 findings])  + report_v2 (composer determinista)

LLM_CALLS       = 0
EMBEDDING_CALLS = 0

REGULATORY_EXPERT_CANDIDATES  = 285
FUNCTIONAL_EXPERT_CANDIDATES   = 98
TECHNICAL_EXPERT_CANDIDATES    = 17
CROSS_DOMAIN_CANDIDATES        = 15
DETERMINISTIC_SUFFICIENT       = 0
HUMAN_ONLY                     = 57

CURRENT_REPORT_USES_LLM        = NO
CURRENT_REPORT_FACTUAL_COVERAGE = 457/457 (100% — 0 findings perdidos, 0 afirmaciones no respaldadas)

MULTI_AGENT_RUNTIME_CURRENTLY_ACTIVE = NO

SHADOW_AGENT_PILOT_RECOMMENDED = YES  (shadow estricto, alcance técnico + cross-domain primero,
                                      regulatorio solo como triage, PILOT_EXECUTION-gated,
                                      sin path de escritura a finding/risk/human_state)
```

*No se implementó el pilot. No se hizo commit. DETENIDO.*
