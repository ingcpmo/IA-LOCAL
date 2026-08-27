# PLAN DE IMPLEMENTACIÓN — ANALIZADOR GMP LOCAL V2

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar. Arquitecto: Capa 8.
**Estado:** propuesta. Nada de esto se ejecuta sin firma de Capa 9 sobre `ADR_ANALIZADOR_GMP_LOCAL_V2.md` y sobre los artefactos gobernados nuevos.
**Prerrequisitos de firma:** (1) ADR; (2) `decomposition[]` de `requirements.yaml` como contenido gobernado; (3) fixtures B (funcional) y C (técnico) como Golden Dataset; (4) `PILOT_EXECUTION` para las corridas de medición de FASE 10; (5) autorización de pull del reranker cross-encoder (`OPTIONAL`).

---

## 1. Principios de ejecución

1. **Nunca destruir CURRENT.** Ni código, ni prompts, ni índices, ni checkpoints, ni cola. V2 se construye al lado.
2. **Shadow mode antes de cualquier cutover.** V2 produce salidas a rutas separadas, sin efectos (no encola real, no emite directivas reales, no escribe audit de producción).
3. **Cada bloque cierra con sus tests + Gate 0 sin regresión** antes de empezar el siguiente.
4. **Determinista primero.** Todo lo que pueda hacerse sin LLM se hace sin LLM (modelo canónico, grafo, decomposition, Risk).
5. **Sin llamadas LLM nuevas hasta B4**, y ahí solo bajo `PILOT_EXECUTION` firmada.
6. **Diff + aprobación de Capa 9 antes de cada commit** (regla de oro del proyecto; esta corrida es doc+diseño, no commitea nada).

---

## 2. Bloques

### B1 — Modelo canónico documental + tablas (determinista, 0 LLM salvo normalización opcional)

**Entregables de código**
- `factory/regulatory/canonical/model.py` — dataclasses `Document/Section/Table/Claim/Control/Actor/SystemComponent/Test/Evidence` con validación de provenance obligatorio (rechazo si falta `document_id·page·source_text·source_hash·extraction_version`).
- `factory/regulatory/canonical/persistence.py` — SQLite (archivo local en `factory/regulatory/canonical_store/`) o tablas en `gmp-postgres`. Decisión de almacenamiento: SQLite para v1 (cero dependencia de esquema en Postgres; migrable).
- `factory/regulatory/canonical/extract_document.py` — orquesta pypdf (texto) + `document_structure_extractor` (secciones) + `table_structure_extractor` (nuevo) → puebla `Document/Section/Table`.
- `factory/regulatory/table_structure_extractor.py` — `pdfplumber.extract_tables()` → objeto `Table` (headers, rows, merged_cells). Mapeo columna→rol por heurística determinista (headers conocidos + tipo de dato); ambigüedad → marca `columns_unmapped`, no inventa.
- `factory/regulatory/canonical/normalize_claims.py` — extrae `Claim` de secciones y produce `normalized_statement`. v1: heurística (split por frase + patrón sujeto-verbo-objeto). v1.1 opcional: 1 llamada LLM local corta por sección relevante (prompt "describe en términos operativos, sin norma"). Guardián: `Claim.source_text` es el literal, `normalized_statement` nunca se usa como cita.

**Tests**
- `test_canonical_model.py` — provenance obligatorio, rechazo de objetos incompletos.
- `test_table_structure_extractor.py` — sobre una tabla real de un control narrative de `GMPAI/source/Rockwell/` (p.ej. `MCCPDC PCS-CP01 Alarms Hard Soft IO Listing revH.xlsx` convertido, o una tabla de un PDF SAT): headers/rows correctos, merged cells, provenance.
- `test_normalize_claims.py` — el `source_text` se preserva byte a byte; `normalized_statement` no filtra vocabulario regulatorio inventado.

**Gate B1:** extracción de RW-0005, RW-0011, RW-0012 poblando el store; `Table` count > 0 para los control narratives; Gate 0 factory PASS.

### B2 — Evidence / Knowledge graph (determinista, 0 LLM)

**Entregables**
- `factory/regulatory/graph/store.py` — nodos = ids del modelo canónico; aristas tipadas (`implemented_by`, `designed_by`, `tested_by`, `regulated_by`, `verifies`, `supports`, `contradicts`, `refers_to`, `supersedes`). SQLite (2 tablas: `nodes`, `edges`) o JSON adjacency-list. **No Neo4j.**
- `factory/regulatory/graph/build.py` — puebla aristas: `regulated_by` desde el catálogo; `implemented_by`/`designed_by`/`tested_by` por matching de identificadores (URn.n.n, F-codes, SAT-nnn) entre documentos + similitud de embeddings de `normalized_statement` sobre el mismo cliente/proyecto.
- `factory/regulatory/graph/queries.py` — `trace(requirement_id)`, `orphans(document_id)`, `contradictions(control_id)`, joins recursivos.

**Tests**
- `test_graph_store.py` — CRUD, aristas tipadas, sin aristas colgantes.
- `test_graph_trace.py` — sobre un caso URS↔FS↔SAT conocido de Rockwell: la traza devuelve el camino completo; un requisito sin test aparece como huérfano.

**Gate B2:** grafo poblado para el set Rockwell; `trace()` y `orphans()` correctos contra 3 casos verificados a mano; Gate 0 PASS.

### B3 — Retrieval V2: decomposition + reranker + EvidenceBundle

**Entregables**
- `requirement_catalog/requirements.yaml` — campo `decomposition[]` por requisito (sub-criterios atómicos). **Contenido gobernado — autoría + firma de Capa 9, no se implementa el código que lo consume hasta que esté firmado.**
- `factory/regulatory/retrieval/rerank.py` — cross-encoder local (modelo `OPTIONAL`, pull propuesto: p.ej. `cross-encoder/ms-marco-MiniLM-L-6-v2` vía sentence-transformers CPU, o equivalente servible por Ollama). Reordena top-20 de fusión → top-5 por (sub-criterio × chunk). Fallback si no se autoriza el pull: sin reranker, top-5 de fusión directa (peor, medible).
- `factory/regulatory/retrieval/evidence_bundle.py` — construye `EvidenceBundle {requirement_id, sub_criterion, candidate_claims[≤5], candidate_tables[], provenance}` reusando `build_fusion_candidate_pool` + `rerank`.

**Tests**
- `test_requirement_decomposition.py` — todo requisito con `decomposition` no vacía; cada sub-criterio es texto, no referencia.
- `test_rerank.py` — determinismo (mismo input → mismo orden); el reranker no reordena peor que fusión sola en el fixture de retrieval (regresión).
- `test_evidence_bundle.py` — bundle acotado a ≤5, provenance completo, sin texto crudo grande.

**Gate B3:** `retrieval_recall_at_5` con reranker ≥ el de fusión sola (7/7 actual) sobre el fixture 7P+2N; Gate 0 PASS.

### B4 — Juicio V2 (2 pasos) + Critic + Adjudicator  ← primera llamada LLM nueva, bajo PILOT_EXECUTION

**Entregables**
- `factory/engines/gmpai_integrity/prompts/` — 2 prompts nuevos versionados (paso A: descripción operativa neutra; paso B: mapeo descripción→sub-criterio) + prompt del Critic. **Contenido gobernado — firma de Capa 9.**
- `chunked_engine.evaluate_chunked` — modo `judgment_v2`: consume `EvidenceBundle`, ejecuta paso A → paso B por sub-criterio; **no re-chunkea**. Flag; el modo actual queda intacto.
- `factory/regulatory/critic.py` — 2º prompt adversarial (temp 0), `{AGREE|DISAGREE|CANNOT_CONFIRM}`.
- `factory/regulatory/adjudicator.py` — determinista; combina Hunter + Critic + `evidence_verifier` (sin cambios) → estados `MACHINE_CONFIRMED | MACHINE_REJECTED | INCONCLUSIVE | EVIDENCE_NOT_FOUND | CONTRADICTORY_EVIDENCE`. Regla dura de ausencia: M4 (cobertura) ∧ `_lexical_evidence_absent` ∧ Critic=ausencia ∧ aplicabilidad `expected`; cualquier fallo → `EVALUATION_INCOMPLETE` → cola humana.

**Tests**
- `test_judgment_v2_replay.py` — replay offline: reusa los raw_payloads persistidos de P1/P5 (fixtures ya en `factory/tests/fixtures/`) para el paso B, con paso A mockeado; verifica que el guardián (cita = source_text) se respeta y que P-negativos no se promueven.
- `test_critic.py` — el Critic rechaza un veredicto positivo con cita fuera de tema (caso `_is_topically_relevant` real).
- `test_adjudicator.py` — tabla de verdad completa Hunter×Critic×Verifier; `EVIDENCE_NOT_FOUND` nunca cierra `DOCUMENTATION_GAP` sin las 4 condiciones.

**Gate B4:** `test_gmpai_chunked_engine.py` sin regresión; medición real bajo `PILOT_EXECUTION` firmada contra el fixture 7P+2N → registrar recall (ver FASE 10). **Este es el gate que decide si V2 resuelve el recall.**

### B5 — Taxonomía de findings + riesgo

**Entregables**
- `factory/regulatory/findings/taxonomy.py` — 7 clases con campos mínimos; `machine_state` / `human_state` separados; `human_state` inicia `UNREVIEWED` y ningún código de IA lo cambia.
- `factory/regulatory/findings/risk.py` — `Risk` determinista, tabla RPN gobernada (`findings/risk_matrix.yaml`).
- `tier1_report.py` — render por clase; secciones Regulatory / Functional / Technical.

**Tests**
- `test_findings_taxonomy.py` — todo Finding con provenance; `human_state` inmutable desde código de IA (test que intenta cambiarlo y falla).
- `test_risk.py` — determinismo, sin dependencia de LLM.

**Gate B5:** informe unificado V2 sobre una corrida shadow con las 3 secciones; Gate 0 PASS.

### B6 — Agentes FUNCTIONAL + TECHNICAL

**Entregables** (por `gmp-agent-design`: perfil derivado donde el agente base cubre 70-80%, agente nuevo si dominio/corpus/salida distintos)
- FUNCTIONAL: `requirements_traceability_agent` (cablear el existente), `functional_consistency_agent`, `test_coverage_agent`, `cross_document_agent` — operan sobre el grafo (B2), no sobre texto.
- TECHNICAL: `technical_design_agent`, `data_integrity_agent` (perfil de `integrity`), `security_architecture_agent`, `automation_controls_agent` (perfil de `automation`).
- Cada uno: `agent_id`, system_prompt, corpus ≥60 chunks citables, ≥5 (agente) / ≥3 (perfil) preguntas de prueba con criterios, entrada en `agents_catalog.yaml`, evidencia de validación archivada, aprobación humana registrada.
- `corpus_runner.py` — plan por CLASE con dependencia: REGULATORY + extracción canónica primero (pueblan grafo), luego FUNCTIONAL/TECHNICAL.

**Tests**
- Suite B (funcional, 20 casos) y suite C (técnica, 20 casos) — ver `PLAN_VALIDACION_...`.
- `test_corpus_runner_v2.py` — orden de clases, dependencia respetada, unidades no arrancan sin grafo poblado.

**Gate B6:** suites B y C firmadas por Capa 9; `FUNCTIONAL_RECALL ≥ 90%`, `TECHNICAL_RECALL ≥ 90%`, falsos positivos ≤5% cada una.

### B7 — Remediación con cadena verificada

**Entregables**
- `remediation_directive.py` — exige `finding → RemediationDirective → candidate document → redline → manifest`; manifest no se emite sin la cadena completa; marca obligatoria "MACHINE GENERATED — BORRADOR, NO APROBADO".
- Reusa el docx tooling de `pilot_run/` (candidate + redline ya existen como formato).

**Tests**
- `test_remediation_chain.py` — cadena completa o error; original nunca se toca; ningún artefacto llega a `QA_APPROVED`.

**Gate B7:** paquete de remediación end-to-end sobre un `MACHINE_CONFIRMED` real de shadow; Gate 0 PASS.

### B8 — Validación integral (FASE 10)

Suites A (regulatoria, fixture conservado), B (funcional), C (técnica) + test `LOCAL_ONLY` (corrida completa con egress bloqueado). Detalle en `PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md`.

### B9 — Migración (FASE 11)

```
1. V2 en SHADOW: corpus_runner ejecuta CURRENT y V2 sobre el mismo input.
   V2 escribe a pilot_run/v2_shadow/… ; NO encola, NO emite directivas, NO audita producción.
2. Comparación lado a lado: por (documento × requisito), CURRENT.conclusion vs V2.machine_state,
   con foco en: nuevos MACHINE_CONFIRMED reales, nuevos falsos positivos, casos que V2 manda a
   humano y CURRENT cerraba (o viceversa).
3. Reporte de comparación a Capa 9. Gates A/B/C en verde.
4. CUTOVER: flag de routing en corpus_runner (1 commit, reversible). CURRENT permanece como
   fallback seleccionable.
5. CURRENT retenido para rollback mientras exista un incidente V2 abierto.
```

**Criterio de cutover (decisión de Capa 9):** `REGULATORY_POSITIVE ≥ 6/7` **o** decisión explícita de operar la clase Regulatory en modo Tier-1 (Palanca C) con V2 aportando Functional/Technical. Ningún cutover automático.

---

## 3. FASE 12 — COSTO COMPUTACIONAL LOCAL

### 3.1 Hardware disponible (medido 2026-08-27)

```
CPU     : 12 núcleos          (nproc)
RAM     : 19 GB total, ~13 GB disponible en reposo   (free -g)
GPU     : ninguna              (nvidia-smi: N/A)
Ollama  : CPU-only, confirmado por el pipeline actual completo corriendo en CPU
Modelos : qwen2.5:7b-instruct-q4_K_M (~4.7 GB), nomic-embed-text (~275 MB), mistral:7b (base, no analizador)
Latencia juicio actual: ~250–600 s por llamada (CPU, qwen2.5:7b)
```

### 3.2 Proyección V2 — variante EJECUTABLE con hardware actual

| Recurso | CURRENT | V2 ejecutable | Delta |
|---|---|---|---|
| Modelos en RAM | 7B (~5 GB) + embed (~0.3 GB) | igual + cross-encoder (~0.1–0.3 GB) | +~0.3 GB — cabe |
| Llamadas LLM de juicio por requisito | 1 (o N chunks) | 2 (paso A + paso B) × nº sub-criterios que llegan a paso B; Critic solo sobre positivos/parciales | ~2–3× llamadas |
| Latencia por requisito | ~250–600 s | ~500–1500 s (2 pasos + Critic condicional) | ~2–3× |
| Llamadas de embedding | 1 query/req | 1 query/req + 1/sub-criterio (multi-query) | +N sub-criterios (baratas, ~1–2 s c/u) |
| Reranker | — | decenas de ms por par, top-20 → ~1 s/req | +~1 s/req (despreciable) |
| Descomposición de requisitos | — | **0 en runtime** (estática) | 0 |
| Normalización de Claims | — | 1 LLM corto por sección relevante, **cacheada** (una vez por documento, reutilizada por todos los agentes/requisitos) | amortizada — ~10–30 llamadas cortas por documento, una sola vez |
| Grafo | — | joins SQLite, ms | despreciable |
| Disco | índices + checkpoints | + canonical_store + graph_store (~decenas de MB por proyecto) | despreciable |

**Conclusión FASE 12:** `HARDWARE_FEASIBLE = SÍ` para la variante ejecutable. El costo dominante es **latencia** (~2–3× por requisito), aceptable para un analizador batch que ya corre en horas. Un corpus completo (referencia: 232 llamadas en la corrida W5 diferida) pasaría a ~500–700 llamadas de juicio — sigue siendo una corrida de background de días, gobernada por `PILOT_EXECUTION`.

### 3.3 Variante `OPTIONAL_INFRASTRUCTURE`

| Opción | Requiere | Fallback ejecutable |
|---|---|---|
| Modelo local ≥32B en juicio | GPU (≥24–48 GB VRAM) — **no cabe en 19 GB RAM CPU** | seguir con 7B two-step (variante ejecutable de 3.2) |
| Reranker cross-encoder mayor | pull adicional (~400 MB) | MiniLM-L-6 (~80 MB) o sin reranker (fusión directa) |
| Servicio de grafo (Neo4j) | contenedor + ~1–2 GB RAM | SQLite / JSON (variante ejecutable) |

Ninguna variante `OPTIONAL` es prerrequisito. Cada una tiene su fallback ejecutable con el hardware actual, marcado arriba.

### 3.4 Descargas propuestas (NO ejecutadas — requieren autorización de Capa 9)

```
1. cross-encoder/ms-marco-MiniLM-L-6-v2  (~80 MB)  — reranker local, CPU
   Alternativa servible por Ollama a evaluar para no añadir sentence-transformers.
```

Nada más se descarga. `qwen2.5:7b` y `nomic-embed-text` ya están instalados.

---

## 4. Secuencia y dependencias

```
B1 (canónico + tablas) ──┬─→ B2 (grafo) ──────────────┐
                         └─→ B3 (retrieval V2) ─→ B4 (juicio V2) ─→ B5 (findings) ─┬─→ B6 (agentes F/T) ─→ B8 (validación) ─→ B9 (migración)
                                                                                   └─→ B7 (remediación) ─┘
```

B1–B3 son deterministas, sin LLM nuevo, sin gobernanza extra — se pueden construir y probar de inmediato tras la firma del ADR.
B4 es el primer gasto de llamadas y el gate que decide el recall regulatorio.
B6 es independiente del resultado de B4 para las clases Functional/Technical (sus gates son propios).
