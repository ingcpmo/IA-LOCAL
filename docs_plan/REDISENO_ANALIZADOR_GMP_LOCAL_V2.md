# REDISEÑO DEL ANALIZADOR DOCUMENTAL GMP — LOCAL ONLY (V2)

**Autoridad:** Capa 9 = Cesar. Arquitecto: Capa 8.
**Fecha:** 2026-08-27.
**Naturaleza de esta corrida:** investigación + arquitectura + plan. **NO** modifica código, **NO** descarga modelos, **NO** ejecuta llamadas LLM, **NO** commitea. Entregable documental.
**Restricciones asumidas como duras:** `AI_RUNTIME = LOCAL_ONLY`, `DOCUMENT_EGRESS = FORBIDDEN`, `EXTERNAL_LLM_API = FORBIDDEN`. openFDA se mantiene sin cambios (referencia, no alimenta decisiones GMP).

Documentos hermanos: `ARQUITECTURA_OBJETIVO_ANALIZADOR_GMP_LOCAL_V2.md`, `ADR_ANALIZADOR_GMP_LOCAL_V2.md`, `MATRIZ_GAP_CURRENT_VS_V2.md`, `PLAN_IMPLEMENTACION_ANALIZADOR_GMP_LOCAL_V2.md`, `PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md`.

---

## 0. RESUMEN PARA CAPA 9

- **El sistema CURRENT no cumple el objetivo completo sin rediseño.** Cumple: análisis multiagente regulatorio, pipeline E2E, retrieval, verificador determinista, audit trail, trazabilidad de los hallazgos que sí se anclan. No cumple: recall regulatorio (1–2/7 vs gate ≥6/7), y no existen como clase `FunctionalFinding` ni `TechnicalFinding`, ni conocimiento cross-documento, ni detección de desviaciones/inconsistencias entre documentos.
- **La causa raíz del recall NO es la que "cero infra" bloquea.** No es retrieval (fusión RRF ya da 7/7 recall_at_5), no es chunking, no es el verificador, no es idioma, no es verbosidad de schema, no es tamaño del modelo en el rango probado (7B→14B sin mejora). **Es el salto semántico que se le pide al 7B en una sola llamada:** mapear un pasaje técnico a un criterio regulatorio abstracto cuando el pasaje no repite el vocabulario del requisito ("PARÁFRASIS"). 5 de 6 casos medibles del fixture son PARÁFRASIS y **fallan los 5**.
- **El rediseño ataca esa causa sin salir del servidor:** reducir la distancia semántica por llamada — estructurar el documento en claims/controles antes del LLM (modelo canónico + extracción de tablas), descomponer cada requisito en sub-criterios verificables, y partir el juicio en dos pasos (descripción operativa neutra → mapeo al criterio). Más un Critic + Adjudicator para atrapar fabricación.
- **Honestidad de resultado:** el rediseño es **necesario** pero **no demostrado suficiente**. Ninguna palanca local previa movió el recall. Ninguna, sin embargo, atacó contrato-de-juicio + estructura documental a la vez. Si la medición de FASE 10 no cruza ≥6/7 con el sistema local V2, el resultado honesto es **operar en modo Tier-1 de alcance declarado (Palanca C) de forma permanente** — nunca auto-aprobación silenciosa.

---

## FASE 0 — RECONSTRUCCIÓN LITERAL DE CURRENT (con evidencia en código)

### 0.1 Mapa de etapas

| Etapa | Archivo · función · línea | Determinista / LLM | Estado compartido |
|---|---|---|---|
| Document ingestion (texto) | `factory/regulatory/retrieval/indexer.py::extract_per_page_text` L32-39 (pypdf); `corpus_runner._default_extractor` | Determinista | No — re-extrae por corrida |
| Document ingestion (estructura) | `factory/regulatory/document_structure_extractor.py::extract_structure` L121-157 | Determinista (regex + TOC anchor) | No |
| Table extraction | **NO EXISTE** como etapa. `pdfplumber.extract_text()` aplana tablas a texto concatenado. `document_structure_extractor` solo detecta encabezados de sección nivel-1 | — | — |
| Chunking | `chunked_engine.py::build_page_chunks` L732-825; `CHUNK_MAX_CHARS=6000` L55, `CHUNK_OVERLAP_CHARS=500` L56; flush forzado por sección si `toc_anchored` | Determinista | Índice persistido `factory/regulatory/retrieval_index/{sha256}.json` |
| BM25 | `retrieval/bm25.py` (Okapi puro, stdlib) L51-66; `retrieval/indexer.py::build_index` L47-96 | Determinista | Índice JSON en disco |
| Embeddings | `retrieval/embed.py::embed_text` L?; `nomic-embed-text` vía Ollama, `context_length=2048` tokens (límite duro del modelo); `retrieval/embed_runner.py` con hard-stop `EMBED_EXECUTION` | LLM local (embeddings) | Índice `{sha256}__*.json`; gobernanza `EMBED_EXECUTION` |
| RRF fusion | `retrieval/fusion.py::rrf_fuse` L19-63; `RRF_K_DEFAULT=60` (no calibrado) | Determinista | No |
| Candidate generation | `retrieval/judgment_candidate_pool.py::build_fusion_candidate_pool` L36-104; `retrieval/query_builder.py::build_retrieval_query` L16-37 (citation_text + evidence_min_criteria + requirement_terms.yaml) | Determinista (query) + 1 embedding de consulta | `EMBED_EXECUTION` |
| Semantic judgment | `chunked_engine.py::evaluate_chunked` L1028+; llamada real L1482 `provider.generate(prompt, num_predict=...)`; prompt `build_prompt` L343-375; `output_token_budget` L133-155; `_assert_token_budget_fits` L468 | **LLM local** (`qwen2.5:7b-instruct-q4_K_M`, CPU) | `CheckpointStore` L924 (`factory/regulatory/pilot_run/checkpoints/`) |
| Evidence verifier | `factory/regulatory/evidence_verifier.py::verify_llm_output` L201-275; `match_citation` L133-163 (exact/normalized/despaced/fuzzy≥0.93/not_found); `_normalize` L123 (strip furniture + bullets) | Determinista | No |
| Relevance (validación C) | `evidence_verifier.relevance_score` L166-175; `semantic_evidence_verification.py` (515 L); `chunked_engine._is_topically_relevant` L679-729 (pre-filtro léxico, señal-suave post-R1.7) | Determinista (heurística léxica) | `requirement_terms.yaml` |
| Absence consolidation | `factory/regulatory/absence_consolidator.py::consolidate` L53-131 + `apply_conclusion_preconditions` L194-294 | Determinista, fail-closed | Matriz de aplicabilidad, ABCD |
| Findings | `chunked_engine.py` dispatchers L2416-2760 (`_dispatch_review_finding`, `_dispatch_m4_absence_review`, `_dispatch_partial_coverage_review`, …); `models.py::Finding` | Determinista (ensamblado) | — |
| Unified reports | `factory/regulatory/tier1_report.py` (orquestador + renderer, commit `4dd81ed`); salidas en `pilot_run/**/unified_reports/*.md|json` | Determinista | — |
| Remediation directives | `factory/services/remediation_directive.py` (376 L) | Determinista + plantilla | Almacén de directivas |
| Remediation packages | `factory/api/routes/remediation_packages.py`; `pilot_run/**/remediation_packages/artifacts*/` | Determinista | — |
| Human review | `factory/layer9/human_review_queue.py` (398 L); `review_queue.jsonl` (110 entradas, 71 pending); dispatch R1.8 desde `chunked_engine._dispatch_*` | Humano | `factory/layer9/review_queue.jsonl` |
| Audit | `factory/core/audit_writer.py::write_event`; `factory/audit/factory_audit.jsonl` (78 010 entradas; `hash_errors=0`; 1 fork histórico `ACCEPTED_WITH_DOCUMENTED_EXCEPTION`) | Determinista, hash-chain | Append-only Part 11 |
| Governance | `factory/regulatory/pilot_execution.py`, `model_qualification_gate.py`, `factory/core/decision_scope_resolver.py`, `decisions/decisions_v2.jsonl` | Determinista | Append-only |

### 0.2 Qué es determinista vs LLM

- **Determinista (la mayor parte):** ingestión de texto, estructura, chunking, BM25, RRF, construcción de query, verificador de citas (A/B/C/D), consolidación de ausencia, dispatch de findings, informes, directivas, audit, gobernanza.
- **LLM local:** exactamente dos puntos — (1) el **juicio** por (chunk × requisito) en `evaluate_chunked` (`qwen2.5:7b`, CPU); (2) el **embedding** de chunks y de la query (`nomic-embed-text`, CPU).
- **Ningún otro punto llama a un modelo.** No hay LLM en ingestión, ni en tablas, ni en consolidación, ni en remediación (la "recomendación" que aparece en los informes es el campo `recomendacion` que el propio modelo de juicio emite en el mismo JSON, no una segunda llamada).

### 0.3 Estado compartido y colaboración entre agentes

- **Los 4 agentes regulatorios NO colaboran.** `corpus_runner.resolve_document_agent_plan` (`corpus_plan.py::resolve_document_agent_plan` L71-113) produce un plan `{agent_id: [requirement_ids]}` y cada (documento × agente) corre como unidad **independiente** con su propio `run_id`, su propio checkpoint, su propio informe (`fase5_result.json`: 12 unidades, 12 run_ids separados). No hay bus de mensajes, no hay memoria compartida entre agentes, no hay un paso donde el resultado de un agente informe a otro.
- **No existe conocimiento cross-documento.** Cada documento se analiza contra la regulación de forma aislada. `requirements_traceability_agent` está en `agents_catalog.yaml` y produjo 6 hallazgos en el motor legacy, pero **no está cableado** en el pipeline CURRENT (`corpus_plan.AGENT_PROMPT_FILES` L36-41 solo lista los 4 regulatorios). No hay ninguna estructura que relacione URS↔FS↔DS↔SAT.
- **Dónde se comparte estado:** solo vía artefactos en disco — índices de retrieval (`retrieval_index/`), checkpoints (`pilot_run/checkpoints/`), cola de revisión (`review_queue.jsonl`), audit (`factory_audit.jsonl`), almacén de decisiones. Es estado *persistido*, no estado *colaborativo en tiempo de ejecución*.

### 0.4 Dónde se pierde información (rastreo literal)

| Punto de pérdida | Mecanismo | Evidencia |
|---|---|---|
| **Tablas → texto plano** | `pdfplumber.extract_text()` concatena celdas sin estructura; `build_page_chunks` re-concatena páginas. Una fila `"Alarm HI | OP01 | 10:35 | 100 | 120"` llega al LLM como texto corrido sin roles de columna | `document_structure_extractor.py` docstring L1-16: *"aplana deliberadamente todo a texto plano por chunk"*; R4 (skill `gmp-recall-pipeline`) confirmó dilución tabular como segundo eje independiente (P4/P6) |
| **Furniture de página** | Membrete Rockwell inyectado entre páginas del mismo chunk; se limpia con regex acotada, pero solo el patrón conocido de esa plantilla | `evidence_verifier._PAGE_FURNITURE_RE` L71-79; asimetría LLM/verificador corregida en R1.6 (`strip_page_furniture` reusado por `build_page_chunks`) |
| **Kerning del PDF** | Espacios espurios a mitad de palabra (`"retentio n"`, `"wheneve r"`) rompen tanto el retrieval BM25 (token partido) como la cita literal | `evidence_verifier` L14-39; **P3 quedó bloqueado en retrieval por esto**, nunca llegó a juicio (R2.2 §3.1) |
| **Viñetas Wingdings/Symbol** | Glifo de zona de uso privado del PDF vs guión ASCII del modelo → `SequenceMatcher` < 0.93 | `evidence_verifier._BULLET_MARKER_RE` L114-116; fix H2→H3 subió H2 de 1/7 a 2/7 |
| **Jerarquía de secciones** | Solo nivel-1 con TOC anchor; subsecciones ("Purpose", "Scope") caen como párrafos sueltos | `document_structure_extractor.py` L9-16 (límite declarado) |
| **Semántica pasaje→criterio** | El LLM recibe texto de chunk + Evidence Pack y debe cruzar de golpe de "descripción técnica operativa" a "criterio regulatorio abstracto". **Aquí es donde muere el recall** (FASE 1) | H1-H4, Palanca A 14B, V2 fusión — 2/7 en las tres |
| **Aislamiento entre agentes/documentos** | No hay etapa que compare lo que dice un documento contra otro, ni lo que dice un agente contra otro | `corpus_plan.py`, `fase5_result.json` |

---

## FASE 1 — CAUSA RAÍZ DEL RECALL (reconstrucción offline)

**Método:** reclasificación de los checkpoints y raw_responses ya persistidos (`pilot_run/checkpoints/`, `pilot_run/**/*.json`) + los resultados firmados de H1-H4 (`W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`), Palanca A (`palanca_a_14b_7p2n_20260815/`), R2.2 (`R2_2_CIERRE_Y_CAPA_SEMANTICA.md` §1.2, §3.1, §4.4), R2.3. **Cero llamadas nuevas.**

### 1.1 Matriz P1–P7 / N1 / N2 → etapa de falla

| Caso | req_id · doc · pág | Eje (R2.2 §3.1) | Etapa exacta de falla | Evidencia citada |
|---|---|---|---|---|
| **P1** | `21_CFR_11.10(e)` · RW-0005 · 45 | **LEXICAL_ECHO** | Ninguna — **RESCATADO**. El pasaje ("audit trail record shall be generated") repite el vocabulario del requisito | R2.2 §3.1; H2/H4 anclado tras fix de viñetas (`normalized 1.0`); replay `chunked-596f70cc4520` |
| **P2** | `21_CFR_11.10(g)` · RW-0005 · 39-40 | **PARAPHRASE** | `SEMANTIC_JUDGMENT_FAILURE`. Retrieval OK (fusión rank 2, R2.2 §4.4). El 7B no infiere "authority check técnico" de "F09.00 Physical Security... operator's only access" | R2.2 §3.1, §5.2; replay V6 hoy: `EVALUATION_INCOMPLETE`, quote vacío |
| **P3** | `ANNEX11_17` · RW-0005 · 44 | LEXICAL_ECHO | `RETRIEVAL_FAILURE` (por artefacto de extracción, no de ranking): kerning "retentio n" parte el token, el chunk correcto no entra al pool. **Nunca llega a juicio** | R2.2 §3.1 |
| **P4** | `ALCOA_ATTRIBUTABLE` · RW-0011 · 12 | **PARAPHRASE** + dilución tabular | `SEMANTIC_JUDGMENT_FAILURE` (confirmado independiente de `TABLE_EXTRACTION_FAILURE`: R4 aisló la tabla a mano y el juicio no cambió). El pasaje nunca dice "attributable"/"individual identity" | R2.2 §3.1; R4 (skill), checkpoints `chunked-8e2b20bfa511` (aislado) vs `chunked-5a439f3fde11` |
| **P5** | `ALCOA_CONTEMPORANEOUS` · RW-0005 · 45 | **PARAPHRASE** | `SEMANTIC_JUDGMENT_FAILURE`. **Mismo chunk exacto que P1**, mismo fix de kerning. El requisito exige inferir "contemporaneidad" de la mera presencia de timestamps. No rescatado ni con pool perfecto (`PILOT_EXECUTION-2026-012`, 0/2) | R2.2 §3.1, §5.2; replay V6 hoy |
| **P6** | `21_CFR_211.68(b)` · RW-0011 · 12 | **PARAPHRASE** | `SEMANTIC_JUDGMENT_FAILURE`. Mismo pasaje que P4; exige inferir "equipo automatizado verificado/calibrado" de una descripción operativa | R2.2 §3.1; R4 P6 |
| **P7** | `21_CFR_211.68(b)` · RW-0012 · 13 | PARAPHRASE (patrón), `OPEN_DECISION` en causa exacta | `SEMANTIC_JUDGMENT_FAILURE`. `not_observed`, `PROVISIONAL_GAP` (run `chunked-5077df33d5ae`). Lectura directa mostró eco léxico casi verbatim sin tabla — ninguna hipótesis medida lo explica del todo | R2.2 §1.2; skill `gmp-recall-pipeline` R4 |
| **N1** | `ANNEX11_4` · RW-0005 · 1 | negativo | Ninguna — **RECHAZADO correctamente** (GAMP5 en lista de referencias). 3 mecanismos deterministas: `detect_reference_list_context`, estructura, verificador | W5V2 fixture set; golden dataset 8/8 |
| **N2** | `21_CFR_11.10(e)` · RW-0005 · 3 | negativo | Ninguna — **RECHAZADO correctamente** (tabla de contenidos, mención superficial "Audit Trail ...... 45"). Fuera del top-5 en BM25/embed/fusión | W5V2 fixture set; R2.2 §4.4 |

### 1.2 Conteo por etapa de falla

```
RETRIEVAL_FAILURE            = 1  (P3, y por artefacto de kerning, no de ranking)
RANKING_FAILURE             = 0  (fusión RRF: 7/7 recall_at_5 — descartado como causa)
TABLE_EXTRACTION_FAILURE    = 0 como causa RAÍZ  (contribuye a P4/P6, pero R4 probó que aislar la tabla NO cambia el juicio)
CONTEXT_DILUTION            = 0 como causa raíz  (mismo hallazgo R4)
SEMANTIC_JUDGMENT_FAILURE   = 5  (P2, P4, P5, P6, P7)  ← LA CAUSA DOMINANTE
PROMPT_FAILURE              = 0  (H1 idioma, H4 schema — ambos descartados)
REQUIREMENT_NORMALIZATION_FAILURE = latente  (no medido aislado; hipótesis de FASE 4 — un criterio abstracto sin descomponer obliga al modelo a hacer el trabajo de normalización en caliente)
EVIDENCE_VERIFIER_FAILURE   = 0  (el verificador funcionó; los "falsos not_found" por viñetas/furniture ya están corregidos y NO relajaron el umbral)
```

### 1.3 Conclusión de FASE 1

**El 83 % de los casos medibles del fixture (5/6) mueren en `SEMANTIC_JUDGMENT_FAILURE`: el 7B local no cruza de un pasaje técnico a un criterio regulatorio abstracto sin eco léxico.** Confirmado por 4 vías independientes (H1-H4 · 14B · fusión con pool perfecto · criterio pre-fijado de Cesar 1/6 ≤ 3/6). El retrieval, el chunking, el verificador y el tamaño de modelo en el rango probado están **descartados** como causa. El único positivo que funciona (P1) es el único LEXICAL_ECHO. El único bloqueo de retrieval (P3) es un artefacto de kerning corregible, no de ranking.

**Implicación de diseño:** como no se puede agrandar el modelo (sin GPU) ni salir del servidor, la única palanca disponible es **acortar el salto semántico que se pide en cada llamada** — pre-estructurar el documento, descomponer el requisito, y partir el juicio. Es el objeto de la arquitectura V2.

---

## FASE 11 — resumen (detalle en `PLAN_IMPLEMENTACION_...`)

```
CURRENT → V2 en shadow mode (mismo input, salidas en paralelo, sin efectos) →
benchmark A/B/C (FASE 10) → comparación lado a lado → cutover controlado por Capa 9 →
CURRENT retenido para rollback (sin borrar)
```

## FASE 12 — resumen (detalle en `PLAN_IMPLEMENTACION_...` §Costo)

Hardware real del servidor: **19 GB RAM, 12 CPU, sin GPU** (`nproc`/`free -g`/`nvidia-smi`). Pipeline actual CPU-only, ~250–600 s por llamada de juicio.

- **Variante ejecutable con hardware actual (`HARDWARE_FEASIBLE = SÍ`):** 7B en juicio de 2 pasos + descomposición de requisitos **estática** (autorada una vez, cero LLM en runtime) + reranker cross-encoder **pequeño y local** (p.ej. MiniLM ms-marco, ~80 MB, CPU, decenas de ms/par) + embeddings locales ya existentes. Costo: ~2× latencia por requisito vs CURRENT; sin RAM adicional significativa (el cross-encoder y el segundo prompt caben).
- **Variante `OPTIONAL_INFRASTRUCTURE`:** modelo local ≥32B → **no cabe en 19 GB, requiere GPU**. Se marca opcional con fallback ejecutable documentado (seguir en 7B two-step).

El bloque de veredicto completo está al final de la respuesta a Capa 9, no aquí (este documento no se detiene solo).
