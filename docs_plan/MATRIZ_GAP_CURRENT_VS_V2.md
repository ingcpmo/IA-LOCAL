# MATRIZ GAP — CURRENT vs ANALIZADOR GMP LOCAL V2

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar.
**Fuentes:** `REDISENO_ANALIZADOR_GMP_LOCAL_V2.md` (FASE 0/1), `ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md` (FASE 2-9).
Leyenda estado: ✅ cumple · 🟡 parcial · ❌ ausente/no cumple.

---

## 1. Gap por cláusula del objetivo

| Cláusula del objetivo | CURRENT | V2 (diseño) | Gap principal |
|---|---|---|---|
| Analizar documentación GMP mediante **IA local** | ✅ | ✅ | Ninguno — ya es local (qwen2.5:7b + nomic-embed-text vía Ollama) |
| Identificar hallazgos **regulatorios** | 🟡 recall 1–2/7 | 🎯 objetivo ≥6/7, **no garantizado** | `SEMANTIC_JUDGMENT_FAILURE` (5/6 casos). V2: modelo canónico + decomposition + juicio 2-pasos + Critic |
| Identificar hallazgos **funcionales** | ❌ no existe la clase | ✅ `FunctionalFinding` + 4 agentes (traceability, consistency, test_coverage, cross_document) | Sin clase, sin agentes, sin grafo cross-documento |
| Identificar hallazgos **técnicos** | ❌ no existe la clase | ✅ `TechnicalFinding` + 4 agentes (design, data_integrity, security_arch, automation_controls) | Sin clase, sin agentes, sin modelo de `Control`/`SystemComponent` |
| Detectar **desviaciones e inconsistencias entre documentos** | ❌ cada (doc×agente) corre aislado | ✅ Evidence graph (URS↔FS↔DS↔SAT) + `contradicts` | No hay estado cross-documento en runtime; `requirements_traceability_agent` desconectado |
| Mantener **evidencia y trazabilidad completas** | 🟡 solo para hallazgos anclados | ✅ provenance obligatorio en todo objeto derivado; `graph_path` en findings | Objetos sin provenance no rechazados hoy en todas las rutas; sin traza cross-documento |
| **Calcular riesgo** | 🟡 campo `highest_risk`/`severidad` propuesto por el LLM | ✅ `Risk` determinista (tabla RPN gobernada) | Riesgo hoy es número del modelo, no cálculo reglado |
| Generar **recomendaciones y correcciones** | 🟡 campo `recomendacion` del mismo JSON de juicio | ✅ `RemediationProposal` con rationale + traceability | Recomendación acoplada al juicio, sin cadena causal verificada |
| Producir **borradores corregidos / redline / manifest** | 🟡 existe tooling (`remediation_directive.py`, docx en `pilot_run/`) | ✅ cadena `finding→directive→candidate→redline→manifest` verificada estructuralmente | Cadena no exigida end-to-end; manifest sin verificación de completitud |
| **Sin enviar documentos a proveedores externos** | ✅ análisis air-gapped | ✅ invariante de diseño + test `DOCUMENT_EGRESS = 0` | Ninguno — se refuerza con test explícito |

---

## 2. Gap por componente técnico

| Componente | CURRENT (archivo·función) | V2 | Acción | Riesgo de la acción |
|---|---|---|---|---|
| Ingestión de texto | `retrieval/indexer.py::extract_per_page_text` (pypdf) | igual + alimenta modelo canónico | KEEP + wrap | Bajo |
| Estructura de documento | `document_structure_extractor.py::extract_structure` (nivel-1, TOC anchor) | igual + `Section` con jerarquía parcial | KEEP + extender | Bajo — límite de subsecciones ya declarado |
| **Extracción de tablas** | ❌ no existe (pdfplumber aplana) | `table_structure_extractor.py` → objeto `Table` | **CREATE** | Medio — mapeo columna→rol; heurística + 1 LLM corto opcional |
| Chunking | `chunked_engine.build_page_chunks` (6000 chars, overlap 500, flush por sección) | KEEP para retrieval; el juicio ya no chunkea | KEEP | Bajo |
| BM25 | `retrieval/bm25.py` (Okapi stdlib) | KEEP | KEEP | Nulo |
| Embeddings | `retrieval/embed*.py` (nomic-embed-text, ctx 2048) | KEEP | KEEP | Nulo |
| RRF fusion | `retrieval/fusion.py::rrf_fuse` (k=60) | KEEP | KEEP | Nulo |
| **Reranker** | ❌ no existe | cross-encoder local (MiniLM ms-marco ~80 MB, CPU) | **CREATE** (`OPTIONAL` download) | Medio — requiere pull autorizado por Capa 9; fallback: sin reranker, solo fusión |
| Candidate pool | `retrieval/judgment_candidate_pool.py::build_fusion_candidate_pool` | → `EvidenceBundle` por sub-criterio | MODIFY | Bajo |
| **Requirement decomposition** | ❌ no existe | `requirements.yaml` + `decomposition[]` estática gobernada | **CREATE** (contenido gobernado) | Medio — autoría + firma por versión |
| **Modelo canónico** | ❌ (`document_structure_extractor` docstring: "aplana deliberadamente") | `Document/Section/Table/Claim/Control/Actor/SystemComponent/Test/Evidence` | **CREATE** | Alto — superficie nueva grande |
| Normalización de Claims | ❌ | 1 LLM local corto por sección relevante, reutilizable | **CREATE** | Medio — guardián: cita = source_text siempre |
| **Evidence graph** | ❌ | SQLite (Postgres existente) o JSON adjacency-list | **CREATE** — **NO Neo4j** | Medio — modelado de aristas; volumen pequeño |
| Juicio | `chunked_engine.evaluate_chunked` → `provider.generate` (1 llamada/chunk) | 2 pasos (descripción neutra → mapeo sub-criterio) | MODIFY (= Palanca V2b) | Alto — 0 llamadas reales ejecutadas jamás; ~2× costo |
| **Critic** | ❌ | 2º prompt local adversarial (temp 0) | **CREATE** | Medio |
| **Adjudicator** | 🟡 lógica dispersa en `_dispatch_*` de `chunked_engine` | módulo determinista único, estados MACHINE_* | **CREATE** (consolidar) | Bajo |
| Verificador de citas | `evidence_verifier.py` (A/B/C/D, fuzzy 0.93) | KEEP sin cambios | KEEP | Nulo — es lo que funcionó |
| Consolidación de ausencia | `absence_consolidator.py` (fail-closed §2/§13.3) | KEEP + Critic como barrera extra | KEEP + extender | Bajo |
| Relevancia (val. C) | `semantic_evidence_verification.py`, `_is_topically_relevant` | KEEP (señal suave post-R1.7) | KEEP | Bajo |
| Taxonomía de Finding | `models.py::Finding` (una clase, orientada a regulatorio) | 7 clases con campos mínimos + machine_state/human_state | MODIFY/CREATE | Medio |
| Cálculo de riesgo | campo del LLM | `Risk` calculator (tabla RPN) | **CREATE** | Bajo |
| Informes unificados | `tier1_report.py` | + 3 clases de finding, + secciones funcional/técnica | MODIFY | Bajo |
| Remediación | `remediation_directive.py` + docx tooling en `pilot_run/` | cadena `finding→directive→candidate→redline→manifest` exigida | MODIFY | Medio |
| Cola de revisión humana | `layer9/human_review_queue.py` (R1.8) | KEEP — `human_state` inicia UNREVIEWED siempre | KEEP | Nulo — no se elimina |
| Audit | `core/audit_writer.py` (hash-chain, append-only) | KEEP + eventos nuevos de V2 | KEEP + extender | Nulo |
| Gobernanza | `pilot_execution.py`, `model_qualification_gate.py`, `decision_scope_resolver.py` | KEEP + `MODEL_QUALIFICATION` extendido al reranker; `decomposition` como artefacto gobernado | KEEP + extender | Bajo |
| Orquestación | `corpus_runner.py` (plan por agente, unidades aisladas) | plan por CLASE con dependencia (REGULATORY+canónico → FUNCTIONAL/TECHNICAL) | MODIFY | Medio — primera dependencia real entre agentes |
| Provider | `model_provider.py` (Protocol + OllamaProvider) | KEEP — `AnthropicProvider` **NO se implementa** (prohibido) | KEEP | Nulo |

---

## 3. Gap de datos / conocimiento

| Elemento | CURRENT | V2 | Acción |
|---|---|---|---|
| Corpus regulatorio (eCFR Part 11/211) | ✅ `sources/incoming/`, `sources/sha256/`, `registry.json` | igual | KEEP |
| Catálogo de requisitos | ✅ `requirement_catalog/requirements.yaml` (con `evidence_min_criteria`) | + `decomposition[]` por requisito | EXTEND (gobernado) |
| `requirement_terms.yaml` | ✅ (validación C) | igual | KEEP |
| Fixture regulatorio 7P+2N | ✅ `W5V2_RECALL_FIXTURE_SET_DRAFT.md` | igual — instrumento único de recall regulatorio | KEEP |
| **Fixture funcional (URS↔FS, FS↔SAT)** | ❌ | 20 casos: 5 fully-traced, 5 missing-impl, 5 missing-test, 5 contradictions | **CREATE** (Golden Dataset, firma Capa 9) |
| **Fixture técnico** | ❌ | 20 casos conocidos (audit trail, access control, timestamp, backup/recovery, interfaces, redundancy, data retention, security) | **CREATE** (Golden Dataset, firma Capa 9) |
| Corpus RAG para agentes técnicos | 🟡 colecciones base (`gmp_automation`, `gmp_data_integrity`, …) del producto base | ≥60 chunks citables por agente nuevo (skill `gmp-agent-design`) | CREATE/REUSE |
| Documentos bajo análisis | ✅ `GMPAI/source/Rockwell/`, `GMPAI/source/SCADA/` (fuera de git) | igual | KEEP (nota: B9 — rutas `/home/ing_cpmo` hardcodeadas en tests, deuda operativa separada) |

---

## 4. Gap de gobernanza / proceso

| Elemento | CURRENT | V2 | Acción |
|---|---|---|---|
| Revisión humana | Obligatoria, 100 % de findings | Obligatoria; `human_state` inicia UNREVIEWED | KEEP — **no se elimina** |
| Auto-aprobación / cierre CAPA / liberación | Prohibido | Prohibido | KEEP |
| `PILOT_EXECUTION` para llamadas reales | ✅ | ✅ + cubre las corridas de FASE 10 | KEEP |
| `MODEL_QUALIFICATION` contra fixture | ✅ para qwen2.5:7b | + reranker (calificación propia) + juicio 2-pasos re-calificado | EXTEND |
| Descarga de modelos | Requiere autorización Capa 9 | reranker cross-encoder = pull `OPTIONAL`, **propuesto, no ejecutado** | PROPONER |
| `decomposition[]` como artefacto | — | contenido gobernado, firma por versión (como `evidence_min_criteria`) | CREATE |
| Suites B/C como Golden Dataset | — | firma de Capa 9 antes de considerar operables Functional/Technical | CREATE |

---

## 5. Resumen de esfuerzo (orientativo, no compromiso)

| Bloque | Componentes CREATE | Componentes MODIFY | Dependencia |
|---|---|---|---|
| **B1 — Estructura** | modelo canónico, `table_structure_extractor`, normalización de Claims | `document_structure_extractor` (extender) | — |
| **B2 — Grafo** | evidence graph (SQLite/JSON) | — | B1 |
| **B3 — Retrieval V2** | reranker local, `decomposition[]` | `judgment_candidate_pool`, `query_builder` | B1 |
| **B4 — Juicio V2** | Critic, Adjudicator | `evaluate_chunked`, `build_prompt` | B3 |
| **B5 — Findings** | taxonomía 7 clases, `Risk` calculator | `models.Finding`, `tier1_report` | B4 |
| **B6 — Agentes FUNCTIONAL/TECHNICAL** | 8 agentes + corpus + fixtures B/C | `corpus_runner` (plan por clase) | B2, B5 |
| **B7 — Remediación** | — | `remediation_directive` (cadena exigida) | B5 |
| **B8 — Validación** | suites A/B/C, test LOCAL_ONLY | — | todos |
| **B9 — Migración** | routing shadow/cutover | `corpus_runner` (flag) | B8 |

---

## ADDENDUM — Cierre del plan original V2 (2026-08-28)

El plan original del Analizador GMP LOCAL V2 se completó de FASE 0 a FASE 12.
Acta consolidada fase por fase, con evidencia:
**`docs_plan/ACTA_CIERRE_ANALIZADOR_GMP_LOCAL_V2.md`**.

Puntos firmes:
- Arquitectura V2 **congelada** en su diseño actual.
- REGULATORY_GATE = **FAIL** (recall LLM 0/7) — contingencia determinista aceptada:
  **Regulatory Tier-1 / Palanca C**. NO se reinterpreta como PASS.
- FUNCTIONAL_GATE = **PASS** (16/16 recall, 0 FP — fixture de inyección de defectos).
- TECHNICAL_GATE = **PASS** (benchmark Suite C: TP=9, FN=C07 semántico, FP=0, recall 0.90;
  transversales LOCAL_ONLY / DOCUMENT_EGRESS=0 / FABRICATED_CITATIONS=0 / TRACEABILITY=YES).
- `technical_completeness_rules.yaml` **v1.1 SIGNED** (OD-6: alcance context-scoped).
- REPORTING_GAP **cerrado**: runtime V2 E2E (`v2_runtime.py`) persiste bajo
  `GMPAI/reports/gmpai_document_validation/<run_id>/`; Mission Control lo expone vía `/api/v1/v2-analyzer/*` (API). La UI
  `mission_control.html` aún NO consume esos endpoints (no se construye UI nueva). Shadow mode ejecutado, CURRENT retenido, cutover NO ejecutado.
- Regresión: 2779 passed / **5 failed** (deuda de clon/servicio-en-vivo, EXC-1..EXC-5,
  0 tocan V2) — `docs_plan/DEUDA_REGRESION_EXCEPCION_CAPA9.md`. **pytest exit code real = 1.**
