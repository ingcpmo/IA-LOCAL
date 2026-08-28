# ARQUITECTURA OBJETIVO — ANALIZADOR DOCUMENTAL GMP LOCAL V2

**Autoridad:** Capa 9 = Cesar. Arquitecto: Capa 8. **Fecha:** 2026-08-27.
**Contexto:** ver `REDISENO_ANALIZADOR_GMP_LOCAL_V2.md` (FASE 0 + FASE 1). Causa raíz confirmada: `SEMANTIC_JUDGMENT_FAILURE` en 5/6 casos medibles. Restricciones duras: `LOCAL_ONLY`, `DOCUMENT_EGRESS = FORBIDDEN`, `EXTERNAL_LLM_API = FORBIDDEN`.

**Principio rector del rediseño:** *el LLM local de 7B no razona bien sobre paráfrasis; entonces se le pide el mínimo salto semántico posible, y todo lo demás lo hace código determinista o trabajo autorado una sola vez.*

---

## FASE 2 — MODELO CANÓNICO DOCUMENTAL

### 2.1 Objetos

Modelo común de conocimiento documental, persistido local (SQLite sobre el Postgres ya existente o JSON en disco — **nunca un servicio nuevo**, ver FASE 3 y criterio FASE 12).

```
Document        {document_id, sha256, tipo (URS|FS|DS|SAT|OQ|IQ|...), titulo, cliente, n_paginas, extraction_version}
Section         {section_id, document_id, numero, titulo, pagina_inicio, pagina_fin, nivel, parent_section_id?}
Table           {table_id, document_id, section_id?, pagina, headers[], rows[[cell,...]], merged_cells[], caption?}
Requirement     {requirement_id, source_id, citation_text, evidence_min_criteria[], jurisdiction, decomposition[] (FASE 4)}
Claim           {claim_id, document_id, section_id, pagina, source_text, source_hash, tipo (control|function|test|parameter|actor_action), normalized_statement}
Control         {control_id, document_id, claim_ids[], categoria (access|audit_trail|backup|time_sync|integrity|...), descripcion_operativa}
Actor           {actor_id, document_id, nombre_rol, tipo (human|system|role)}
SystemComponent {component_id, document_id, nombre, tipo (PLC|SCADA|HMI|Historian|DB|...), version?}
Test            {test_id, document_id, section_id, identificador (SAT-039...), descripcion, resultado?, verifies_requirement_ids[]}
Evidence        {evidence_id, claim_id|table_id, document_id, pagina, source_text, source_hash, extraction_version, anchor_status}
Regulation      {= Requirement.source_id + snapshot gobernado en sources/registry.json}
Risk            {risk_id, finding_id, severidad, gxp_impact, probabilidad, detectabilidad, score}
Finding         {ver FASE 7}
Remediation     {ver FASE 8}
```

### 2.2 Provenance obligatorio

Todo objeto derivado (`Claim`, `Control`, `Evidence`, `Table`, `Test`, `Finding`) lleva **sin excepción**:

```
document_id · page · section (numero+titulo o null explícito) · source_text (literal) ·
source_hash (sha256 del source_text) · extraction_version (versión del extractor que lo produjo)
```

Un objeto sin provenance completo **no se persiste** (fail-closed, mismo criterio que `evidence_pack_gate` actual). Esto hace que la trazabilidad sea una propiedad estructural, no algo que se reconstruye después.

### 2.3 Cómo esto ataca la causa raíz

Hoy el LLM recibe un chunk de ~6000 caracteres de texto plano y debe (a) localizar la frase relevante, (b) entender qué hace el sistema, (c) mapearlo al criterio. Con el modelo canónico, (a) y (b) ya están hechos por extracción determinista + una pasada de normalización: el LLM de juicio recibe un `Claim.normalized_statement` corto y un `Requirement.decomposition[i]` concreto, y solo hace (c) sobre un par acotado. El salto pasa de "página → criterio abstracto" a "afirmación normalizada → sub-criterio concreto".

### 2.4 Etapa de normalización de Claims

`Claim.normalized_statement` se produce por **una llamada LLM local corta y acotada** por sección relevante (no por requisito): *"reescribe esta afirmación en términos operativos: qué hace, qué registra, qué controla, quién actúa, sobre qué componente — sin mencionar ninguna norma"*. Salida: 1-3 frases. Es barata (prompt corto, salida corta) y **reutilizable por todos los agentes y requisitos** (se calcula una vez por Claim, no N veces). El texto citable **siempre** es `Claim.source_text`, nunca `normalized_statement` (guardián idéntico al de V2b).

---

## FASE 3 — EVIDENCE / KNOWLEDGE GRAPH (local)

### 3.1 Relaciones

```
URS.Requirement  --implemented_by-->  FS.Claim/Section
FS.Claim         --designed_by-->     DS.Claim/Section
DS.Claim         --tested_by-->       SAT.Test / OQ.Test
Requirement      --regulated_by-->    Regulation
Test             --verifies-->        URS.Requirement (transitivo vía FS/DS)
Evidence         --supports-->        Control
Evidence         --contradicts-->     Claim
Claim            --refers_to-->       SystemComponent / Actor
Document         --supersedes-->      Document (versión anterior)
```

### 3.2 Infraestructura — evaluación de lo que YA existe

| Opción | Veredicto | Motivo |
|---|---|---|
| **SQLite (archivo local) o tablas nuevas en el `gmp-postgres` ya levantado** | **ELEGIDA** | Cero servicio nuevo. Postgres ya está `Up, healthy`. El grafo es pequeño (miles de nodos/aristas por proyecto), no necesita motor de grafos. Consultas de traza = joins recursivos (`WITH RECURSIVE`) o BFS en memoria |
| JSON adjacency-list en disco (como `retrieval_index/`) | Alternativa válida para v1 | Mismo patrón que los índices actuales; sin dependencia. Se puede migrar a SQLite si el volumen crece |
| Neo4j u otro motor de grafos | **RECHAZADA** | `OPTIONAL_INFRASTRUCTURE` — servicio nuevo, RAM adicional (Neo4j pide ~1-2 GB mínimos), viola el criterio de FASE 12. El beneficio (consultas de camino) no justifica el costo en un grafo de este tamaño |

### 3.3 Qué habilita el grafo

- **Desviaciones e inconsistencias cross-documento** (objetivo explícito): `Requirement` en URS sin `implemented_by` en FS → `FunctionalFinding: REQUIREMENT_NOT_IMPLEMENTED`. `FS.Claim` sin `Requirement` que la origine → `IMPLEMENTATION_WITHOUT_REQUIREMENT`. `URS.Requirement` sin `Test` transitivo → `REQUIREMENT_NOT_TESTED`.
- **Contradicciones:** dos `Claim` de documentos distintos con `normalized_statement` que se oponen sobre el mismo `Control`/`SystemComponent` → `Evidence --contradicts--> Claim` → adjudicación (FASE 6).
- **Trazabilidad completa** como consulta, no como reporte manual.

---

## FASE 4 — RETRIEVAL V2

### 4.1 Requirement decomposition (estática, gobernada)

Cada `Requirement` gana un campo `decomposition[]` en `requirement_catalog/requirements.yaml` — lista de sub-criterios atómicos verificables, **autorada una vez** (contenido gobernado, firma de Capa 9, mismo régimen que `evidence_min_criteria`). Ejemplo:

```yaml
21_CFR_11.10(e):
  decomposition:
    - "existe un audit trail generado por el sistema (no manual)"
    - "cada entrada lleva fecha y hora"
    - "cada entrada identifica al operador/actor"
    - "se registran las acciones de crear/modificar/borrar registros"
    - "el valor previo se preserva al modificar"
    - "el audit trail es exportable / revisable"
    - "el acceso a modificar el audit trail está restringido"
```

**Cero LLM en runtime.** La descomposición convierte "¿cumple 21 CFR 11.10(e)?" (un salto grande) en 7 preguntas de eco casi léxico contra `Claim.normalized_statement`.

### 4.2 Multi-query retrieval + reranker

```
build_retrieval_query(req_id)  →  además: una query por sub-criterio de decomposition[]
  ↓
BM25 (indexer.py, sin cambios)  +  embeddings (nomic-embed-text, sin cambios)  →  RRF fuse (fusion.py, sin cambios)
  ↓
local cross-encoder reranker  (NUEVO — MiniLM ms-marco o similar, ~80 MB, CPU)
  reordena top-20 de fusión → top-5 de alta probabilidad por (sub-criterio × chunk)
  ↓
EvidenceBundle  {requirement_id, sub_criterion, candidate_claims[≤5], candidate_tables[], provenance completo}
```

### 4.3 Contrato con el juicio

El LLM de juicio **nunca busca dentro de texto grande**. Recibe un `EvidenceBundle` ya acotado (≤5 claims + tablas estructuradas relevantes) y juzga sub-criterio por sub-criterio. `evaluate_chunked` deja de re-chunkear el pool (hoy lo hace, `judgment.expected_calls_for_unit` L90-99) y consume el bundle directamente.

---

## FASE 5 — ARQUITECTURA MULTIAGENTE V2

Rol + contrato + datos + reglas + herramientas. **Todos corren sobre el mismo `qwen2.5:7b` local** — "agente" = configuración gobernada, no instancia de modelo. Todos operan contra el modelo canónico (FASE 2) y el grafo (FASE 3), nunca contra texto crudo.

### 5.1 Clase REGULATORY (conservar, adaptar contrato)

| agent_id | Conservar | Cambio V2 |
|---|---|---|
| `fda_part11_agent` | sí | contrato de juicio 2-pasos; consume EvidenceBundle por sub-criterio |
| `fda_cgmp_211_agent` | sí | idem |
| `eu_annex11_agent` | sí | idem |
| `alcoa_plus_agent` | sí | idem — es el que más PARÁFRASIS tiene (P4/P5/P6), el que más se beneficia de decomposition |

### 5.2 Clase FUNCTIONAL (nueva — no existe hoy)

| agent_id | Rol | Datos | Salida |
|---|---|---|---|
| `requirements_traceability_agent` | Cablear el que ya está en catálogo pero desconectado | grafo URS↔FS↔DS↔SAT | `TraceabilityFinding` |
| `functional_consistency_agent` | Detectar comportamiento funcional contradictorio entre secciones/documentos | `Claim.normalized_statement` + grafo `contradicts` | `FunctionalFinding: CONTRADICTORY_FUNCTIONAL_BEHAVIOR` |
| `test_coverage_agent` | Mapear Test→Requirement, detectar huecos | `Test.verifies_requirement_ids`, grafo | `TestCoverageFinding: REQUIREMENT_NOT_TESTED / PARTIAL_TEST_COVERAGE / TEST_WITHOUT_REQUIREMENT` |
| `cross_document_agent` | Desviaciones URS↔FS↔DS (requisito no implementado, implementación sin requisito) | grafo | `FunctionalFinding: REQUIREMENT_NOT_IMPLEMENTED / IMPLEMENTATION_WITHOUT_REQUIREMENT` |

### 5.3 Clase TECHNICAL (nueva — no existe hoy)

| agent_id | Rol | Base |
|---|---|---|
| `technical_design_agent` | Huecos de diseño técnico (redundancia, recuperación, sincronización de tiempo, interfaces) | `Control`, `SystemComponent`, `Claim` |
| `data_integrity_agent` | Perfil de `alcoa_plus` orientado a arquitectura de datos (no a cumplimiento ALCOA per se): dónde vive el dato crudo, hybrid systems, metadata | `Control(categoria=integrity)` |
| `security_architecture_agent` | Controles de acceso, autenticación, segregación de funciones a nivel de arquitectura | `Control(categoria=access)`, `Actor` |
| `automation_controls_agent` | ISA-88/95, GAMP5 Cat 4/5, lógica de alarmas, PLC/SCADA | `SystemComponent`, `Table` (listas de I/O, alarmas) |

**Regla anti-redundancia:** `technical_design_agent` y `security_architecture_agent` no re-evalúan requisitos regulatorios; emiten `TechnicalFinding` sobre diseño. Si un hueco técnico también incumple una norma, el `RegulatoryFinding` lo cubre y el `TechnicalFinding` lo referencia (`related_finding_ids`), no lo duplica.

### 5.4 Orquestación

`corpus_runner` V2 resuelve un plan por **clase**: primero REGULATORY y la extracción del modelo canónico (poblan el grafo), luego FUNCTIONAL y TECHNICAL (consumen el grafo ya poblado). Es la primera vez que hay dependencia real entre agentes — secuencial, determinista, declarada.

---

## FASE 6 — CRITIC + ADJUDICATOR

Evaluación multipaso por (sub-criterio × EvidenceBundle):

```
1. Evidence Hunter (LLM local, 2 pasos)
     paso A: descripción operativa neutra del/los Claim candidatos (sin norma)
     paso B: ¿la descripción neutra satisface este sub-criterio? → {SATISFIES|PARTIAL|NO|UNCLEAR} + claim_id citado
2. Independent Critic (LLM local, prompt distinto, temperatura 0)
     recibe: sub-criterio + Claim.source_text + veredicto del Hunter
     tarea: intentar REFUTAR el veredicto. "¿hay una lectura en la que esta evidencia NO satisface el sub-criterio? ¿la cita es sobre otro tema?"
     salida: {AGREE|DISAGREE|CANNOT_CONFIRM} + razón
3. Deterministic Evidence Verification (evidence_verifier.py — SIN CAMBIOS)
     match_citation sobre Claim.source_text; relevance_score; A/B/C/D
4. Adjudicator (determinista, NO LLM)
     combina Hunter + Critic + Verifier con reglas fijas fail-closed
```

### 6.1 Estados de salida

```
MACHINE_CONFIRMED        Hunter=SATISFIES ∧ Critic=AGREE ∧ Verifier=verified/verified_with_deviation ∧ A∧B∧C∧D
MACHINE_REJECTED         Verifier=rejected_by_verifier  ∨  (negativo estructural: reference list, TOC)
INCONCLUSIVE             Hunter y Critic no coinciden, o Verifier=review_required
EVIDENCE_NOT_FOUND       ningún Claim del bundle es citable para el sub-criterio  (NUNCA "gap confirmado" por sí solo)
CONTRADICTORY_EVIDENCE   grafo tiene Evidence --contradicts--> Claim para este control
```

### 6.2 Regla dura

`EVIDENCE_NOT_FOUND` → `DOCUMENTATION_GAP` **solo** si: (a) cobertura del retrieval completa (todos los chunks del índice fusionados antes de truncar — mecanismo M4 ya existente, `M4_ABSENCE_RANK_THRESHOLD`), **y** (b) segunda señal `_lexical_evidence_absent` (ya existente), **y** (c) Critic confirma ausencia, **y** (d) la matriz de aplicabilidad marca `expected`. Cualquier fallo → `EVALUATION_INCOMPLETE` → cola humana. Idéntico al fail-closed de `absence_consolidator.consolidate` + `apply_conclusion_preconditions` actuales, extendido con el Critic.

---

## FASE 7 — TAXONOMÍA DE FINDINGS

### 7.1 Clases independientes

```
RegulatoryFinding · FunctionalFinding · TechnicalFinding · TraceabilityFinding ·
DataIntegrityFinding · SecurityFinding · TestCoverageFinding
```

### 7.2 Campos mínimos (todas las clases)

```
finding_id · class · subtype · severity · document · page · section · source_text · source_hash ·
evidence (Evidence[]) · requirement_id? · regulatory_basis? · technical_basis? · risk (Risk) ·
rationale · confidence (HIGH|MEDIUM|LOW) · provenance (extraction_version, run_id, agent_id, adjudicator_state) ·
machine_state (MACHINE_CONFIRMED|MACHINE_DEVIATION_CANDIDATE|MACHINE_REMEDIATION_PROPOSAL|EVIDENCE_NOT_FOUND|...) ·
human_state (UNREVIEWED|... )  ← SIEMPRE inicia UNREVIEWED; nunca lo toca la IA
related_finding_ids[]
```

### 7.3 Subtipos por familia

```
Regulatory:  REGULATORY_GAP · REGULATORY_PARTIAL · REGULATORY_COMPLIANT_EVIDENCE
Functional:  REQUIREMENT_NOT_IMPLEMENTED · IMPLEMENTATION_WITHOUT_REQUIREMENT ·
             REQUIREMENT_NOT_TESTED · TEST_WITHOUT_REQUIREMENT ·
             CONTRADICTORY_FUNCTIONAL_BEHAVIOR · PARTIAL_TEST_COVERAGE
Technical:   TECHNICAL_DESIGN_GAP · SECURITY_CONTROL_GAP · AUDIT_TRAIL_DESIGN_GAP ·
             BACKUP_RECOVERY_GAP · TIME_SYNC_GAP · ACCESS_CONTROL_GAP · INTERFACE_INCONSISTENCY
```

### 7.4 Cálculo de riesgo

`Risk` determinista: `score = f(severity, gxp_impact, probabilidad, detectabilidad)` con tabla fija gobernada (estilo RPN, sin LLM). `severity` la propone el agente; `gxp_impact` sale de la criticidad del `Requirement`/`Control` en el catálogo; `probabilidad`/`detectabilidad` de reglas por subtipo. Nunca un número inventado por el modelo.

---

## FASE 8 — REMEDIATION

Todo `Finding` en `MACHINE_CONFIRMED` (o `MACHINE_DEVIATION_CANDIDATE` con evidencia suficiente) puede producir:

```
RemediationProposal {
  finding_id · target_document · target_section · proposed_text ·
  rationale · traceability (requirement_id, evidence_ids, graph_path) ·
  marca OBLIGATORIA: "MACHINE GENERATED — BORRADOR, NO APROBADO"
}
  ↓ (determinista, plantilla + docx surgery, reusa remediation_directive.py + regulatory/pilot_run docx tooling)
candidate corrected document  (nunca sobrescribe el original)
  ↓
redline  (diff estructurado original vs candidate)
  ↓
manifest {finding_ids, remediation_ids, source_hashes, generated_at, model_digest, run_id, "NOT QA APPROVED"}
```

**Cadena causal exigida y verificada estructuralmente:** `finding → RemediationDirective → candidate document → redline → manifest`. Un manifest sin la cadena completa no se emite.

**Prohibido, sin excepción:** convertir automáticamente cualquiera de estos artefactos en `QA_APPROVED`, `RELEASED`, `CAPA_CLOSED`, `FINAL_GMP_APPROVAL`. `human_state` solo lo cambia un humano vía `human_review_queue`.

---

## FASE 9 — TABLAS

### 9.1 Diagnóstico

R4 (skill `gmp-recall-pipeline`) ya probó que **aislar la tabla a mano no cambia el juicio del 7B** — la extracción de tablas **no es la causa raíz del recall**. Pero sí es causa de pérdida de información estructural que los agentes FUNCTIONAL/TECHNICAL necesitan (listas de I/O, tablas de alarmas, matrices de trazabilidad, tablas de parámetros de SAT).

### 9.2 Diseño

`table_structure_extractor.py` (nuevo) sobre `pdfplumber.extract_tables()` (ya dependencia): produce el objeto `Table` de FASE 2 con `headers`, `rows`, `merged_cells`. Ejemplo objetivo:

```
"Alarm HI | OP01 | 10:35 | 100 | 120"
  →  {event_type: parameter_change, parameter: "Alarm HI", actor: "OP01",
      timestamp: "10:35", old_value: "100", new_value: "120",
      provenance: {document_id, page, table_id, source_text, source_hash}}
```

El mapeo columna→rol (`actor`, `timestamp`, `old_value`, `new_value`) se hace con **heurística determinista** (nombres de header conocidos + tipo de dato) y, solo si es ambiguo, **una llamada LLM local corta** de clasificación de headers (no de juicio). Las celdas alimentan `Claim`/`Evidence` con provenance de tabla.

### 9.3 Beneficio medido esperado

Retrieval: el fix de furniture simétrico de R4 ya subió `retrieval_recall_at_5` 4/7→5/7 como efecto colateral. Tablas estructuradas deberían ayudar a los agentes FUNCTIONAL (matrices de trazabilidad son tablas) más que al recall regulatorio — se mide en la suite B/C de FASE 10, no se asume.

---

## Resumen de componentes

| | Componente |
|---|---|
| **KEEP sin cambios** | `evidence_verifier.py` (A/B/C/D), `absence_consolidator.py` (fail-closed), `bm25.py`, `fusion.py`, `indexer.py`, `embed*.py`, `document_structure_extractor.py`, `CheckpointStore`, `audit_writer.py`, `human_review_queue.py`, `model_provider.py` (Protocol), `pilot_execution.py`, `model_qualification_gate.py`, prompts YAML de los 4 agentes regulatorios (como base) |
| **MODIFY** | `chunked_engine.evaluate_chunked` (juicio 2-pasos; consumir EvidenceBundle), `build_prompt` (recibir Claim normalizado + sub-criterio), `retrieval/judgment.py` (+ reranker, EvidenceBundle), `corpus_runner.py` (orquestar 3 clases con dependencia), `requirement_catalog/requirements.yaml` (+ `decomposition[]`), `tier1_report.py` (3 clases de finding) |
| **CREATE** | modelo canónico (persistencia + extractores), `table_structure_extractor.py`, evidence graph (SQLite/JSON), reranker cross-encoder local, Critic + Adjudicator, taxonomía de 7 clases de Finding, 4 agentes FUNCTIONAL + 4 TECHNICAL (perfiles/agentes con corpus + fixtures), suites de benchmark B y C, `Risk` calculator determinista |

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
