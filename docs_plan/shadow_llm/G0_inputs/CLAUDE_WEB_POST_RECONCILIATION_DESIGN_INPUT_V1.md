# CLAUDE WEB — INSUMO DE DISEÑO POST-RECONCILIACIÓN (V1)

**Fecha:** 2026-09-02 · **Modo:** READ-ONLY (sin código, sin ledger, sin stores, sin config, sin
audit trail, sin LLM/embeddings, sin R2, sin PILOT-035, sin commit).
**Rama:** `fix/clon-local-validacion` · **Tag de aceptación:** `reconc-acceptance-v1` → `0e1e88a`
· **Código del cierre del arco:** `reconc-arc-closure` → `56bd36a`.

**Propósito:** documento autocontenido para la mesa de diseño de **Claude Web**. Resume el estado
REAL tras F0-F9 y la corrida diagnóstica `diag-corpus-20260902`, y aísla **lo único que queda por
diseñar**: la capa LLM (shadow) y el paso de *findings estructurados → reporte narrativo*.
**No propone arquitectura nueva. No implementa.**

Fuentes: `FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md`,
`docs_plan/agent_diagnostic/CURRENT_CORPUS_AGENT_DIAGNOSTIC.md`,
`docs_plan/agent_diagnostic/CURRENT_FINDING_AGENT_ROUTING.json`,
`docs_plan/agent_diagnostic/CURRENT_RUNTIME_AGENT_MAP.json`, y lectura de código
(`v2_runtime.py`, `regulatory_tier1.py`, `functional_findings.py`, `technical_findings.py`,
`report_v2.py`, `evidence_bundle.py`).

---

## 1 · Qué quedó cerrado y demostrado después de F0-F9

De `FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md` (recomendación **`ACCEPT_WITH_FOLLOW_UP`**):

| Cierre | Evidencia reproducida (clon limpio, solo 6 PDF + manifest) |
|---|---|
| `CODE_CHANGES_PRESENT = YES` | F1 `09656e1` (extractor `(\d{1,2})\.?\s+`), F2-r1 `4c64a05` (3× `sorted()` en `graph/build.py`, `materialize_stores.py`), F3 `484abea` (`r_par_delta_v1_v2.py` sin rutas efímeras) |
| `CLEAN_REBUILD = PASS` | stores regenerados 3× deterministas; 6/6 logical hashes canónicos + graph logical == `VALIDATION_BASELINE_MANIFEST`; **RW-0012 = 8 secciones / 258 claims** (des-contaminado de WFI) |
| Extractor | PRE `0/8` → FINAL `8/8` en RW-0011/0012/0014 (`GROUND_TRUTH_SHA256 = 2f7a00dc…`) |
| `TARGETED_RESULT = 124 passed / 0 failed` | `test_completeness_rules_v1_2` + `test_technical_findings` + `test_run_fingerprint` + `test_wp_e_measurement_independence` + `test_extraction_adequacy` |
| Fingerprints re-baselinados (F5) exactos | `INPUT_CONFIG 3fcb3ae8…` · `GRAPH_SNAPSHOT 2fdda0e2…` · `FINDINGS ENFORCE 235f724a…` / `OBSERVE 693fc746…`; counts **342 / 90 / 25**; RUN1 == RUN2 |
| `RPAR_ABC_REPRODUCIBLE = YES` | A=457, B=457, C=458; `findings_A/B/C.json` byte-idénticos a `F6_hashes.json`; `only_in_A = only_in_B = 0`; egress 0; human gate intacto; D = `SKIPPED_NO_STORE` |
| `NEW_REGRESSIONS = 0` | full suite 2978 passed / 32 failed / 95 skipped — **idéntico a Acceptance V1**; las 32 fallas = 4 stale de hardening (F5 §5) + 22 ambientales + 6 out-of-scope pre-sesión |
| Governance E2 / E3-A | **firmados por Capa 9** vía Mission Control (`AV-2026-026/027` E2, `AV-2026-028/029` E3-A, `human_confirmed`/`Cesar`/`ACTIVE`), sin hand-edit del ledger ni del audit trail |
| Bloqueos vigentes | `R2_READY_TO_RESUME = NO` · `PILOT_EXECUTION-2026-035 = HOLD` · `LLM_CALLS = 0` · `PRODUCTION_ENABLEMENT = BLOCKED` |

**Carry-forward abiertos (§13 del review), NO bloquean el diseño pero sí `FINAL_QUALIFICATION`:**
1. 4 tests de hardening stale (constante de fingerprint hardcodeada) — requieren autorización de Capa 9.
2. Bug del generador de IDs (`decision_store_v2.next_instance_id:189` acuña del JSONL revertible, no del audit trail) — IDs `AV-2026-026..029` colisionan con entradas solo-audit del 2026-08-31.
3. `ARTIFACT_VERSION-2026-024..028` `NO_RECONCILIABLE`.
4. Escenario D del R-PAR / RW-0003 (SAT) `SKIPPED_NO_STORE`.
5. P4 — 4 líneas de servicio de `decisions_v2.jsonl` sin commitear (working tree del origen).
6. Out-of-scope pre-sesión (`remediation_directive.py` +127, etc.), congelados en `F0_diffs/`.
7. D5-D2 — corpus técnico held-out necesita autor independiente (Maria ≠ Cesar).

---

## 2 · Qué arquitectura actual funciona y debe preservarse

- **Extracción → modelo canónico (B1):** `document_structure_extractor.py` +
  `canonical/extract_document.py` → `canonical_store/*.sqlite3`. Determinista, hash lógico
  gobernado (`F2_HASH_DEFINITION.md`), reconstruible desde PDF + `VALIDATION_BASELINE_MANIFEST`.
- **Grafo de evidencia (B2):** `graph/build.py::build_project_graph` → `graph_store` +
  **snapshot inmutable por `run_id`** (`graph_snapshot/graph_snapshot.json`). Determinista tras F2-r1.
- **Recuperación (B3):** `retrieval/evidence_bundle.py` — BM25 + reranker léxico, `retrieval_mode = "bm25"`.
  100 % determinista, sin LLM, sin embeddings, sin red.
- **Findings (B5/B6):** 7 clases `Finding` con invariantes duros (`taxonomy.py`): `human_state`
  nace `UNREVIEWED` y **solo `set_human_state(reviewer=...)` lo cambia**; `source_hash` debe
  corresponder a `source_text`; `machine_state` no puede ser un `FORBIDDEN_STATE`.
- **Riesgo (B5):** `findings/risk.py` + `risk_matrix.yaml`, determinista; `ENFORCE` (GATE D-2
  firmado) degrada banda de los `ABSENCE_DEPENDENT` con cobertura MISSING/DEGRADED.
- **Cobertura gobernada (H-7):** `analysis_coverage_mode` es un parámetro resuelto por
  `validation_v2/coverage_mode.py` (firma D-2 + `extraction_adequacy_thresholds.yaml` SIGNED);
  dos colas `ACTIONABLE_NOW` / `BLOCKED_BY_COVERAGE_OR_EVIDENCE`.
- **Remediación:** `findings/remediation_v2.py` + `services/candidate_document_generator.py` —
  `Finding → Directive → candidate.docx → redline.docx → manifest`, todos
  `MACHINE GENERATED -- BORRADOR, NO APROBADO` / `NOT_QA_APPROVED`. Texto por **plantilla**, CERO LLM.
- **Reporte:** `findings/report_v2.py` — transcripción estructurada por clase, sin LLM.
- **Egress:** `validation_v2/local_only.py::network_locked()` → `DOCUMENT_EGRESS_BYTES = 0` +
  `egress_control_state()` (monkeypatch de socket + sonda de red real).
- **Reproducibilidad:** `validation_v2/run_fingerprint.py` — `INPUT_CONFIG` / `GRAPH_SNAPSHOT` /
  `FINDINGS` fingerprints; whitelist `_FINDING_SEMANTIC_FIELDS` (los campos aditivos NO mueven el
  fingerprint).

**Regla de preservación:** cualquier capa nueva es **aditiva**. No puede mover
`FINDINGS_FINGERPRINT`, no puede tocar `finding_class` / `subtype` / `risk` / `requirement_id` /
`human_state`, no puede introducir egress ni no-determinismo en el camino actual.

---

## 3 · Cómo corre hoy realmente `run_v2_pipeline`

`factory/regulatory/validation_v2/v2_runtime.py::run_v2_pipeline(document_ids, *, project_id,
run_id, canon_dir, graph_dir, report_base, remediation_limit=8)`

Secuencia real (todo bajo `network_locked()`):

```
1. build_project_graph(project_id, docs_typed, canon_dir, graph_dir)          # graph/build.py
2. graph_snapshot_from_store(...) -> graph_snapshot.json  (inmutable, no se sobrescribe)
3. reg  = regulatory_tier1_findings(did, _TIER1_REQUIREMENTS, ...)  por doc   # regulatory_tier1.py
4. func = graph_functional_findings(project_id, document_ids, ...)            # functional_findings.py
5. tech = graph_technical_findings(project_id, document_ids, ...)             # technical_findings.py
6. all_findings = reg + func + tech ; _assert_no_forbidden(all_findings)
7. evidence_basis.stamp(all_findings)          # rellena SOLO f.evidence_basis (aditivo)
8. _stamp_graph_path(all_findings, snapshot_fp)                     # aditivo (provenance.graph_path)
9. coverage_mode.resolve() -> effective_mode ; _h7_coverage_treatment(...)   # 2 colas + ENFORCE
10. persist: regulatory_findings.json / functional_findings.json / technical_findings.json
             evidence_provenance.json / analysis_coverage.json / analysis_coverage_queues.json
11. remediación: hasta remediation_limit=8 findings MACHINE_*CANDIDATE/CONFIRMED
                 -> build_proposal / apply_and_redline / generate_candidate_document (docx)
12. report_v2.build_report(all_findings, ...) + render_markdown -> informe_hallazgos_v2.md
    (+ sección H-7 de 2 colas añadida por v2_runtime) ; final_report_v2.json
13. audit_metadata.json (llm_calls=0, embedding_calls=0, egress=0, fingerprints, coverage_queues)
14. manifest.json + SHA256SUMS.txt + paquete_final.zip + package_receipt.json
```

`_TIER1_REQUIREMENTS` (12): `21_CFR_11.10(d/e/g)`, `21_CFR_11.50_11.70`, `ANNEX11_7.1`,
`ANNEX11_9`, `ANNEX11_12`, `ANNEX11_17`, `ALCOA_ATTRIBUTABLE/LEGIBLE/CONTEMPORANEOUS/ORIGINAL`.

`_report_base()` resuelve dinámicamente a `…/GMPAI/reports/gmpai_document_validation/<run_id>/`
(no hay raíces nuevas). El grafo `graph_store` keyed por `project_id` SÍ se sobrescribe; el
**snapshot del paquete no**.

**Corrida diagnóstica de referencia** (`diag-corpus-20260902`, equivalente escenario-A del R-PAR):
`ACTIVE_ENGINE = V2`, `ROUTING_MODE` = Tier-1/Palanca C (regulatory) + B6a/B6b (func/tech),
`analysis_coverage_mode = ENFORCE`, `LLM_CALLS = 0`, `EMBEDDING_CALLS = 0`,
`DOCUMENT_EGRESS_BYTES = 0`, `human_gate_intact = True`, fingerprints
`3fcb3ae8… / 2fdda0e2… / 235f724a…` (== baseline F5 ENFORCE).

---

## 4 · Componentes determinísticos vs LLM presentes-pero-no-ejecutados

### Determinísticos y ACTIVOS en el runtime (producen los 457 findings)

| `agent_id` (etiqueta de provenance, NO proceso LLM) | Módulo / función | Clase producida |
|---|---|---|
| `regulatory_tier1` | `findings/regulatory_tier1.py::regulatory_tier1_findings` | `RegulatoryFinding` |
| `test_coverage_agent` | `findings/functional_findings.py::graph_functional_findings` (+ `technical_findings.py::completeness_findings`) | `TestCoverageFinding` |
| `cross_document_agent` | `findings/functional_findings.py` | `FunctionalFinding` |
| `requirements_traceability_agent` | `functional_findings.py` + `technical_findings.py` | `TraceabilityFinding` |
| `functional_consistency_agent` | `functional_findings.py` (aristas `contradicts`) | `FunctionalFinding` — **0 en el corpus** |
| `technical_design_agent` | `technical_findings.py` (grafo + completitud) | `TechnicalFinding` |
| `security_architecture_agent` | `technical_findings.py::completeness_findings` | `SecurityFinding` |
| `data_integrity_agent` | `technical_findings.py::completeness_findings` | `DataIntegrityFinding` |
| `report_v2` (composer determinista) | `findings/report_v2.py::build_report/render_markdown` | — (consumidor) |

**Ningún componente activo puede cambiar `risk` ni `human_state`.** `provenance.adjudicator_state`
vale `"TIER1"` en los 342 regulatorios y `null` en el resto. Todos los `agent_id` son **literales
de string** en `FindingProvenance(...)`.

### LLM: CÓDIGO PRESENTE, NO EJECUTADO (`v2_runtime.py` no importa ninguno)

| Componente | Ruta exacta | Estado |
|---|---|---|
| Orquestador de juicio V2 por bundle | `factory/regulatory/v2_judgment/judgment_v2.py::evaluate_bundle(bundle, *, provider: ModelProvider, ...)` | **NO EJECUTADO** — solo scripts `factory/docs/design/regulatory_redesign_v2/*` y tests |
| Adjudicador (determinista, agrega hunter+critic) | `factory/regulatory/v2_judgment/adjudicator.py::adjudicate(...)` + dataclass `Adjudication` | NO EJECUTADO |
| Crítico (LLM) | `factory/regulatory/v2_judgment/critic.py::review(...)` + dataclass `CriticResult` | NO EJECUTADO |
| Prompts de juicio (firma gobernada) | `factory/regulatory/v2_judgment/prompts.py` (`load_prompt`, `is_signed`, `assert_all_signed`, `render`, `temperature`) | NO EJECUTADO |
| Motor legacy por chunks | `factory/engines/gmpai_integrity/chunked_engine.py::evaluate_chunked(...)` (L1028) | NO EJECUTADO — requiere `PILOT_EXECUTION` firmada |
| Interfaz de modelo | `factory/engines/gmpai_integrity/model_provider.py` — `ModelProvider` (Protocol, L26), `OllamaProvider` (L101), `.generate` / `.generate_controlled` | NO EJECUTADO |
| Cliente Ollama (HTTP REST, `httpx`) | `factory/engines/gmpai_integrity/ollama_client.py` — `generate()` (L75), `generate_controlled()` (L160); timeouts reales (~1200 s piso) | NO EJECUTADO |
| Fase de JUICIO (candidate pool → LLM) | `factory/regulatory/retrieval/judgment.py::run_judgment_batch` | NO EJECUTADO — solo mediciones R2 |
| Capa semántica (embeddings + fusión RRF) | `factory/regulatory/retrieval/{embed,embed_index,embed_runner,fusion}.py` | NO EJECUTADO — `evidence_bundle` corre `retrieval_mode="bm25"`; `fusion` nunca se invoca; `embedding_calls = 0` |
| Prompts del motor (contenido gobernado) | `factory/engines/gmpai_integrity/prompts/{alcoa,annex11,cgmp211,part11,traceability}_prompts.yaml` + `common_contract_base.yaml` + `common_contract_composer.py` | presentes, **no cargados** en la corrida |
| Prompts de agentes de caso | `factory/agent_prompts/{case_analysis,dossier_review}_prompts.yaml` | presentes, no usados por `run_v2_pipeline` |
| Orquestación de piloto (batch) | `factory/regulatory/corpus_runner.py::run_pilot_sample_batch(...)` (L397), parámetro `evaluation_profile` (`BASELINE` | `H2H4`, R1.5) | NO EJECUTADO en `run_v2_pipeline` |

> La existencia de `v2_judgment/`, de prompts firmados o de `evaluate_chunked` **no demuestra
> ejecución**. `audit_metadata.json → llm_calls = 0, embedding_calls = 0`.

---

## 5 · Resultado real del diagnóstico (457 findings)

| Dimensión | Valor |
|---|---|
| Total | **457** (`RegulatoryFinding` 342 · `TestCoverageFinding` 70 · `FunctionalFinding` 20 · `TraceabilityFinding` 8 · `TechnicalFinding` 6 · `SecurityFinding` 5 · `DataIntegrityFinding` 6) |
| Por retorno de módulo | regulatory 342 / functional 90 / technical 25 |
| Por banda (post-ENFORCE) | `HIGH` 355 · `LOW` 78 · `MEDIUM` 22 · `CRITICAL` 2 |
| Por estado de máquina | `MACHINE_INCONCLUSIVE` 377 · `MACHINE_DEVIATION_CANDIDATE` 80 |
| Por estado humano | `UNREVIEWED` 457 (100 %) |
| Por documento | RW-0005 88 · RW-0006 133 · RW-0009 57 · RW-0011 58 · RW-0012 62 · RW-0014 59 |
| Colas H-7 | `ACTIONABLE_NOW` 30 · `BLOCKED` 427 (78 cobertura MISSING/DEGRADED + 349 método `INDETERMINATE`, incl. 57 de RW-0009) |
| Remediación | 8 borradores (límite) de los 80 `MACHINE_DEVIATION_CANDIDATE` |
| `LLM_CALLS` / `EMBEDDING_CALLS` / egress | 0 / 0 / 0 |

**Hecho crítico para el diseño:** los **342 regulatorios son TODOS `REGULATORY_INCONCLUSIVE`**
(`evidence_basis = INDETERMINATE`). **Cero `REGULATORY_COMPLIANT_EVIDENCE`** — el motor Tier-1
no encontró **un solo eco léxico anclado** en 6 documentos × 12 requisitos. Es la manifestación
directa del techo de recall del 7B (confirmado 4/7 casos por experimento directo; R2 CERRADO sin
alcanzar el gate ≥6/7). `functional_consistency_agent` e `INTERFACE_INCONSISTENCY` no dispararon;
`REQUIREMENT_NOT_TRACED` emitió 0 (filtro de confianza).

---

## 6 · Clasificación de findings para futura revisión LLM (determinista, sin ejecutar LLM)

Reglas explícitas (`CURRENT_FINDING_AGENT_ROUTING.json → findings[].REVIEW_CLASSIFICATION`):

| Bucket | Regla | Nº | Experto sugerido |
|---|---|---:|---|
| `HUMAN_ONLY` | `document_id == RW-0009` (`adequacy_verdict = NOT_ANALYZABLE`) | **57** | — (ninguno hasta mejor extracción; H7/MarkItDown diferido) |
| `LLM_EXPERT_REVIEW_CANDIDATE` (REGULATORY) | `agent_id == regulatory_tier1` (motor abstiene, `INDETERMINATE`) | **285** | `REGULATORY` — **solo triage de los ≤5 candidatos de recuperación**, nunca conclusión |
| `LLM_EXPERT_REVIEW_CANDIDATE` (FUNC/TECH) | `evidence_basis == ABSENCE_DEPENDENT` ∧ `machine_state == MACHINE_DEVIATION_CANDIDATE` | **87** | `FUNCTIONAL_TRACEABILITY` (70 `REQUIREMENT_NOT_TESTED`) / `TECHNICAL_VALIDATION` (17 reglas de completitud) |
| `LLM_EXPLANATION_USEFUL` | `evidence_basis == ABSENCE_DEPENDENT` ∧ `machine_state == MACHINE_INCONCLUSIVE` (LOW) | **28** | redacción para el revisor; NO cambia conclusión (20 `IMPLEMENTATION_WITHOUT_REQUIREMENT` + 8 `ORPHAN_DESIGN_ELEMENT`) |
| `DETERMINISTIC_SUFFICIENT` | resto | **0** | — |

**Carga potencial por experto (solo candidatos LLM):**

| Experto | total | by_subtype | by_risk |
|---|---:|---|---|
| `REGULATORY` | **285** | `REGULATORY_INCONCLUSIVE` 285 | `HIGH` 285 |
| `FUNCTIONAL_TRACEABILITY` | **98** | `REQUIREMENT_NOT_TESTED` 70 · `IMPLEMENTATION_WITHOUT_REQUIREMENT` 20 · `ORPHAN_DESIGN_ELEMENT` 8 | `LOW` 78 · `MEDIUM` 20 |
| `TECHNICAL_VALIDATION` | **17** | `AUTHORITY_CHECK_GAP` 3 · `ALCOA_ATTRIBUTABLE_GAP` 4 · `AUDIT_TRAIL_DESIGN_GAP` 2 · `BACKUP_RECOVERY_GAP` 2 · `ACCESS_CONTROL_GAP` 2 · `TECHNICAL_DESIGN_GAP` 2 · `AUDIT_TRAIL_INTEGRITY_GAP` 2 | `HIGH` 13 · `MEDIUM` 2 · `CRITICAL` 2 |
| `CROSS_DOMAIN` | **15** | gap técnico/seguridad/integridad cuya **regulación fuente gobernada** (`21_CFR_11.10(d/e/g)`, `ANNEX11_17`, `ALCOA_ATTRIBUTABLE`) es la misma que `regulatory_tier1` marcó `INCONCLUSIVE` **en el mismo documento** | — |
| `HUMAN_ONLY` | **57** | todos RW-0005..RW-0009? → **todos RW-0009** | `HIGH` 57 |
| `DETERMINISTIC_SUFFICIENT` | **0** | — | — |

`FINDINGS_ASSIGNED_TO_MORE_THAN_ONE_EXPERT = 15` (medida precisa; la medida gruesa por
`(document,page)` da 350 pero es ruido — los regulatorios se anclan en páginas bajas).
Detalle: `CURRENT_FINDING_AGENT_ROUTING.json → summary.cross_domain_same_requirement_family_detail`.

---

## 7 · El hueco por diseñar entre findings estructurados y reporte narrativo

**Estado actual del reporte** (`report_v2.py`): `build_report` agrupa por `finding_class`,
recomputa contadores, y `render_markdown` emite **una fila de tabla por finding** (subtipo, banda,
`machine_state`, req, página, cita **truncada a 140**, rationale **truncado a 180**). `to_json`
serializa el reporte completo. **CERO LLM · plantilla pura · cobertura factual 457/457 · 0
findings perdidos · 0 afirmaciones no respaldadas.** `finding_id` colisiona (259 únicos de 457);
`finding_record_id` es único 457/457 y es la clave de listado.

**Lo que NO existe hoy y hay que diseñar:**

1. **Agrupación por documento × regulación**, no por clase. Hoy un revisor tiene que reconstruir
   a mano "todo lo de `21_CFR_11.10(e)` en RW-0006".
2. **Priorización / triage** dentro de las colas H-7 (457 filas planas; 355 `HIGH`).
3. **Reconciliación de la contradicción técnico ↔ regulatorio** (los 15 cross-domain): una capa
   dice "gap concreto de §X", la otra "no puedo juzgar §X". No hay `related_finding_ids` entre
   clases que lo enlace; no hay narrativa que lo explique al humano.
4. **Narrativa por hallazgo** (qué está mal / por qué no cumple / requisito usado / evidencia
   anclada / riesgo / acción) — hoy el `rationale` es una frase-plantilla truncada.
5. **Triage de los ≤5 candidatos de recuperación** de cada `REGULATORY_INCONCLUSIVE` para el
   revisor (285 casos) — sin concluir cumplimiento.
6. **Separación de artefacto**: dónde vive la salida de la capa LLM sin tocar los
   `*_findings.json` ni `final_report_v2.json` ni el `FINDINGS_FINGERPRINT`.
7. **Presentación gobernada**: cómo se muestra una narrativa LLM junto a un finding
   `INCONCLUSIVE` sin inducir al revisor a aprobar sin verificar la cita.

**Invariante de diseño:** el reporte narrativo se construye a partir de
(findings estructurados **inmutables**) + (salida shadow **separada**). Nunca reescribe el
finding. El `governance_statement` / cabecera `BORRADOR ASISTIDO` de `report_v2` se conserva.

---

## 8 · Código existente reutilizable por Claude Web

| Necesidad | Reutilizar (ruta exacta) | Nota |
|---|---|---|
| Modelo de datos de finding | `factory/regulatory/findings/taxonomy.py` — `Finding` (L121), `FindingProvenance` (L110), `build_finding` (L190), `SUBTYPES`, `MACHINE_STATES`, `FORBIDDEN_STATES`, `set_human_state`, `as_dict` | invariantes duros; `human_state` inmutable desde IA |
| Findings persistidos de la corrida | `<run_dir>/regulatory_findings.json`, `functional_findings.json`, `technical_findings.json`, `evidence_provenance.json` | entrada READ-ONLY para la capa narrativa/shadow |
| Recuperación por sub-criterio | `factory/regulatory/retrieval/evidence_bundle.py::build_bundles_for_requirement(document_id, requirement_id, *, canon_dir, reranker=None, max_candidates=5)` → `EvidenceBundle` (`candidate_claims` con provenance, `retrieval_mode="bm25"`) | ya es el "candidate pool" que un experto LLM necesita; no re-inventar retrieval |
| Snapshot de grafo | `<run_dir>/graph_snapshot/graph_snapshot.json` + `factory/regulatory/graph/queries.py` | para findings `ABSENCE_DEPENDENT` (¿ausencia real o límite de extracción?) |
| Orquestación de juicio LLM ya cableada | `factory/regulatory/v2_judgment/judgment_v2.py::evaluate_bundle` → hunter (paso A/B) → `evidence_verifier.verify_llm_output` (determinista, SIN CAMBIOS) → `critic.review` (solo si SATISFIES/PARTIAL) → `adjudicator.adjudicate` → `SubcriterionVerdict` | **shadow-only**; requiere `provider` + `prompts.assert_all_signed()` |
| Interfaz de modelo / cliente | `factory/engines/gmpai_integrity/model_provider.py::OllamaProvider`; `ollama_client.py::generate/generate_controlled` (`httpx`, sin package `ollama`) | CPU, timeouts reales; egress debe quedar dentro de `network_locked` salvo la llamada explícita autorizada |
| Reporte base | `factory/regulatory/findings/report_v2.py` — `build_report`, `render_markdown`, `to_json`; `_HEADER` (cabecera GxP obligatoria) | el composer narrativo la **envuelve**, no la sustituye |
| Remediación (borrador controlado) | `factory/regulatory/findings/remediation_v2.py` (`build_proposal`, `apply_and_redline`, `RemediationChain`) + `factory/services/candidate_document_generator.py` | ya produce docx `MACHINE GENERATED / NOT_QA_APPROVED` |
| Riesgo | `factory/regulatory/findings/risk.py::compute_risk` + `risk_matrix.yaml` | determinista; la capa LLM no lo toca |
| Fingerprint / campos semánticos | `factory/regulatory/validation_v2/run_fingerprint.py` — whitelist `_FINDING_SEMANTIC_FIELDS` | los campos aditivos (`evidence_basis`, `graph_path`, `finding_record_id`) NO mueven el fingerprint — el patrón a seguir para cualquier campo shadow |
| Egress / red | `factory/regulatory/validation_v2/local_only.py` — `network_locked()`, `egress_control_state()` | |

---

## 9 · Puntos exactos de integración para una futura rama SHADOW

**Seam A — dentro de `run_v2_pipeline` (aditivo, tras el paso 6):**
`v2_runtime.py`, justo después de `all_findings = reg + func + tech` y **antes** de la
persistencia. Un hook `if shadow_enabled:` que:
- lee `all_findings` (no los muta),
- reconstruye los `EvidenceBundle` con `build_bundles_for_requirement` (ya deterministas),
- llama `v2_judgment.evaluate_bundle(bundle, provider=OllamaProvider(...))` **solo** para los
  buckets objetivo,
- escribe **exclusivamente** a `<run_dir>/shadow/…json` (raíz nueva dentro del paquete, no en
  `compliance_matrices/`),
- registra `shadow_llm_calls` / `shadow_model_digest` / `prompt_id` en un
  `shadow/shadow_audit.json` separado del `audit_metadata.json` principal.

**Seam B — post-proceso independiente (fuera de `run_v2_pipeline`):**
un script nuevo que consume `<run_dir>/*_findings.json` + `evidence_provenance.json` +
`graph_snapshot.json` y produce `<run_dir>/shadow/*` + un `informe_narrativo_v2.md` nuevo,
**sin re-ejecutar** el pipeline. Ventaja: no toca el camino gobernado ni su fingerprint.

**Seam C — composer narrativo (siempre determinista o siempre shadow, nunca mezclado sin marca):**
módulo nuevo hermano de `report_v2.py` que recibe `(report dict de build_report, shadow dict)` y
emite markdown agrupado por documento × regulación, con la narrativa marcada
`[SHADOW / NO GOBERNADO]` cuando provenga del LLM.

**Campos de enganche que YA existen (no crear estructura nueva en el `Finding`):**
- `FindingProvenance.adjudicator_state` — hoy `"TIER1"` / `null`; un registro shadow paralelo
  puede llevar su propio estado sin tocar el finding.
- `Finding.related_finding_ids` — vacío hoy; un post-pass determinista podría enlazar los 15
  cross-domain **antes** de la capa LLM (decisión de diseño, no implementada aquí).
- patrón `evidence_basis` / `graph_path` / `finding_record_id`: **campos aditivos fuera del
  fingerprint** — el molde para cualquier atributo shadow que deba viajar con el finding.

**Gobernanza obligatoria del seam:**
- Cualquier llamada real a Ollama exige **`PILOT_EXECUTION` firmada** (`human_confirmed`).
  Proponer: `factory/regulatory/pilot_execution.py::propose_pilot_execution(*, scope, max_calls,
  proposed_by_id, ...)`. **NO proponer una nueva si ya hay vigente con presupuesto.**
- Selección/validación entre múltiples vigentes:
  `factory/regulatory/corpus_runner.py::_select_pilot_execution_instance` (L298),
  `_check_pilot_execution` (L369), `_pilot_execution_budget` (L286). Regla: vigente ∧ cubre todos
  los docs del lote ∧ `max_calls > 0` ∧ `decision_date` más reciente.
- Si se activa la capa semántica: familia **`EMBED_EXECUTION`**
  (`factory/regulatory/embed_execution.py`), separada — nunca descuenta de `PILOT_EXECUTION`.
- Si se usa la fase de juicio por pool: familia **`JUDGMENT_EXECUTION`**
  (`factory/regulatory/judgment_execution.py::propose_judgment_execution`) — declara
  explícitamente que **no** autoriza `PILOT_EXECUTION` / `CORPUS_AUTHORIZATION` / `D4` / `EMBED_EXECUTION`.
- Prompts: `factory/regulatory/v2_judgment/prompts.py::assert_all_signed()` antes de cualquier
  corrida real; los prompts del motor viven en `factory/engines/gmpai_integrity/prompts/*.yaml`
  (contenido gobernado — cambiarlos = `prompt_version` nuevo + aprobación de Cesar).

---

## 10 · Restricciones y elementos fuera de alcance

**Prohibido en cualquier diseño de la capa LLM/shadow:**
- Mutar `finding_class`, `subtype`, `severity`, `risk`, `requirement_id`, `machine_state` o
  `human_state` de un `Finding`. `human_state` solo `set_human_state(reviewer=<humano real>)`.
- Mover `INPUT_CONFIG` / `GRAPH_SNAPSHOT` / `FINDINGS` fingerprint del camino gobernado.
- Declaración de cumplimiento final · aprobación automática de documentos · cierre de CAPA ·
  liberación de lote · convertir `NOT_ASSESSABLE` / `INCONCLUSIVE` en `observed` por
  interpretación (`CLAUDE.md`, sin excepción).
- Relajar el verificador de citas ancladas (validación A), aceptar `evidencia_exacta` vacía,
  bajar umbrales C/D, subir `temperature` "para encontrar más".
- Egress: toda salida de documento fuera de `network_locked()` está prohibida salvo la llamada
  LLM explícitamente autorizada por `PILOT_EXECUTION`.
- Proponer `PILOT_EXECUTION` nueva habiendo una vigente con presupuesto (generó el conflicto
  `-002/-004/-006/-007/-008`, registros append-only permanentes).

**Fuera de alcance de esta mesa (no diseñar aquí):**
- Ejecutar LLM, embeddings, R2 o `PILOT_EXECUTION-2026-035` (en `HOLD`).
- Reabrir F0-F9 o corregir los 7 carry-forward (§1) — son decisión de Capa 9.
- Corregir el bug del generador de IDs ni los 4 tests de hardening stale.
- Detección automática de evidencia parafraseada — **techo del modelo confirmado**; el objetivo
  de la capa LLM es *asistencia al revisor*, no recall automático.
- Mejorar la extracción de RW-0009 (`NOT_ANALYZABLE`) — depende de H7/MarkItDown, diferido.
- `PRODUCTION_ENABLEMENT` (BLOCKED) y `FINAL_QUALIFICATION` (pendiente D5-D2).

---

## 11 · Archivos a entregar a Claude Web

**Contexto de estado y diagnóstico:**
```
docs_plan/reconc/CLAUDE_WEB_POST_RECONCILIATION_DESIGN_INPUT_V1.md   (este documento)
docs_plan/reconc/FINAL_HUMAN_REVIEW_POST_RECONCILIATION.md
docs_plan/agent_diagnostic/CURRENT_CORPUS_AGENT_DIAGNOSTIC.md
docs_plan/agent_diagnostic/CURRENT_FINDING_AGENT_ROUTING.json
docs_plan/agent_diagnostic/CURRENT_RUNTIME_AGENT_MAP.json
CLAUDE.md
docs_plan/ROADMAP_ANALIZADOR_GMP.md
docs_plan/PAQUETE_DECISION_ESTRATEGICA.md
docs_plan/reconc/ARC_CLOSURE_F0_F9.md
```

**Runtime y productores de findings (READ-ONLY):**
```
factory/regulatory/validation_v2/v2_runtime.py
factory/regulatory/validation_v2/coverage_mode.py
factory/regulatory/validation_v2/run_fingerprint.py
factory/regulatory/validation_v2/local_only.py
factory/regulatory/findings/taxonomy.py
factory/regulatory/findings/regulatory_tier1.py
factory/regulatory/findings/functional_findings.py
factory/regulatory/findings/technical_findings.py
factory/regulatory/findings/risk.py
factory/regulatory/findings/risk_matrix.yaml
factory/regulatory/findings/evidence_basis.py
factory/regulatory/findings/remediation_v2.py
factory/regulatory/findings/report_v2.py
factory/regulatory/retrieval/evidence_bundle.py
```

**Capa LLM presente-no-ejecutada (para el diseño shadow):**
```
factory/regulatory/v2_judgment/judgment_v2.py
factory/regulatory/v2_judgment/adjudicator.py
factory/regulatory/v2_judgment/critic.py
factory/regulatory/v2_judgment/prompts.py
factory/regulatory/evidence_verifier.py
factory/engines/gmpai_integrity/model_provider.py
factory/engines/gmpai_integrity/ollama_client.py
factory/engines/gmpai_integrity/chunked_engine.py
factory/engines/gmpai_integrity/prompts/           (alcoa/annex11/cgmp211/part11/traceability _prompts.yaml + common_contract_base.yaml + common_contract_composer.py)
factory/regulatory/retrieval/judgment.py
factory/regulatory/retrieval/fusion.py
```

**Gobernanza de ejecución:**
```
factory/regulatory/pilot_execution.py
factory/regulatory/judgment_execution.py
factory/regulatory/embed_execution.py
factory/regulatory/corpus_runner.py                (_select_pilot_execution_instance L298, _check_pilot_execution L369, _pilot_execution_budget L286, run_pilot_sample_batch L397)
```

**Salida de referencia de la corrida diagnóstica** (paquete `diag-corpus-20260902`, fuera del
árbol del repo — regenerable con `run_v2_pipeline` sobre los 6 stores de producción):
`informe_hallazgos_v2.md`, `compliance_matrices/final_report_v2.json`,
`{regulatory,functional,technical}_findings.json`, `evidence_provenance.json`,
`analysis_coverage.json`, `graph_snapshot/graph_snapshot.json`, `audit_summary/audit_metadata.json`.

---

*Documento READ-ONLY. No se diseñó arquitectura nueva, no se implementó, no se modificó código,
ledger, stores, configuración ni audit trail. No se ejecutó LLM, embeddings, R2 ni PILOT-035.
Sin commit.*
