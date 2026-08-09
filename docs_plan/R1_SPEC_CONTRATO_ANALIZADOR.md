# R1 — Spec del contrato del Analizador Documental GMP

**Origen:** `docs_plan/ROADMAP_ANALIZADOR_GMP.md`, fase R1.
**Autoridad:** Capa 9 = Cesar. Claude Code = Capa 8.
**Estado del documento:** DISEÑO, para revisión — ningún código se escribe
hasta que Cesar apruebe esta spec.

```
PRODUCTION_ENABLEMENT = BLOCKED
CORPUS_READY = false
```

---

## 1. Dónde vive el analizador

**Recomendación: capacidad de `factory` (:9000), no de `gmp-api` (:8000).**

Razón: el analizador necesita `evidence_verifier.py`, `chunked_engine.py`,
`evidence_pack_governance.py`, el catálogo de requisitos
(`requirement_catalog/requirements.yaml`) y la cola de revisión de Capa 9
(`human_review_queue.py`) — todo eso vive en `factory/regulatory/` y
`factory/layer9/`. `gmp-api` no tiene ninguna de estas piezas y no debe
adquirirlas: es el producto base de consulta conversacional (Auth →
Orchestrator → Rules → RAG → LLM → Audit), un producto distinto.

Único punto de contacto reutilizado de `gmp-api`: el **patrón** de chunking
ChromaDB de `knowledge/retriever.py` (`_split_text`, tamaño de chunk,
overlap) — se replica como código nuevo dentro de `factory/regulatory/`,
no se importa cruzando el límite 8000/9000.

Esto no es una decisión nueva: ya está en `CLAUDE.md` como regla
permanente ("Separación arquitectónica"). Este punto de la spec es la
confirmación explícita aplicada al analizador.

---

## 2. Entrada

```yaml
analyzer_request:
  document:
    file: <PDF o texto ya extraído>
    sha256: <hash de la copia exacta analizada>          # mismo principio que source_sha256 del evidence pack
  document_type: <URS|FS|SOP|...>                         # mismo enum que expected_doc_types del evidence pack
  regulatory_scope: [<ids de body/regulation aplicables>] # ej. 21CFR11, EU_ANNEX11 — filtra qué agentes/requirement_ids corren
  run_context: pilot | production                         # mismo campo que ya usa corpus_runner / require_inference_authorized
```

- `document_type` decide, vía `corpus_plan.resolve_document_agent_plan`
  (patrón ya existente), **qué agentes/`requirement_id`s son aplicables**
  — el analizador nunca evalúa un documento contra requisitos fuera de su
  matriz de aplicabilidad.
- `sha256` es obligatorio y se propaga a cada hallazgo del informe (trazable
  hasta la copia exacta analizada, mismo principio que `source_sha256` en
  el Evidence Pack).
- No hay entrada de "URL" ni de documento sin hash — el documento original
  es la fuente maestra y su identidad se fija antes de analizar nada.

---

## 3. Salida — informe de hallazgos

### 3.1 Los 6 campos de Cesar, por hallazgo

```yaml
finding:
  requirement_id: <id del catálogo>
  what_is_wrong: <qué está mal>                    # 1
  why_noncompliant: <por qué no cumple>             # 2
  regulatory_basis:                                 # 3
    body: <organismo emisor>
    regulation: <nombre + versión>
    clause: <numeral>
    governance_reference: <evidence_pack.pack_version usado>
  anchored_evidence:                                # 4
    quote: <cita literal>
    page: <página real del documento>
    match_type: <literal|normalized>                 # mismo vocabulario que evidence_verifier.match_citation
    match_score: <float>
  risk: <CRITICAL|HIGH|MEDIUM|LOW>                  # 5, mismo enum que app/rules.py SEVERITY_ORDER
  recommended_action: <acción recomendada>           # 6
```

### 3.2 Estado honesto por criterio evaluado (no solo por hallazgo positivo)

El informe cubre **todos** los `requirement_id` aplicables al
`document_type`, no solo los que dieron positivo. Tres estados, ninguno
oculta a los otros:

| Estado | Cuándo | Origen |
|---|---|---|
| `hallazgo_con_evidencia` | el hallazgo tiene `anchored_evidence` verificada (validación A pasó) | `_VALID_ESTADOS` positivos de `chunked_engine.py` (`cumple`, `cumple_parcialmente`) tras pasar `evidence_verifier` |
| `sin_evidencia_localizada` | la recuperación (R2) no encontró candidatos, o el LLM no ancló ninguna cita sobre los candidatos servidos | nuevo — reemplaza el antiguo "gap firme" automático; ver §4 |
| `no_evaluable` | el fragmento disponible es insuficiente para juzgar, o technical_execution_failure | `evidencia_insuficiente` / `NOT_ASSESSABLE` ya existentes en `chunked_engine.py` |

Nunca hay un cuarto estado "cumple sin evidencia" — eso violaría la regla
permanente de `CLAUDE.md` ("sin evidencia vacía ni citas no ancladas").

### 3.3 Clasificación NCR / CAPA / change control

Se define en detalle en R3 del roadmap (reglas explícitas por criticidad +
tipo de brecha + tipo documental). En esta spec de R1 solo se fija el
principio: **la clasificación es una propuesta determinista, no vinculante**
— la cola de revisión humana puede corregirla. El LLM nunca clasifica por
su cuenta.

### 3.4 Cobertura y limitaciones (obligatorio, siempre visible)

```yaml
coverage_summary:
  requirements_applicable: <N>
  hallazgo_con_evidencia: <n>
  sin_evidencia_localizada: <n>
  no_evaluable: <n>
  recall_config_used: <hash de prompt_version + modelo>   # ej. H2+H4
  known_limitation: "recall del modelo medido en 2/7 sobre fixture set 7P+2N; ver W5V2_RECALL_EXPERIMENTS_RESULTADOS.md"
```

Este bloque va en la portada del informe, no al final — nadie debe leer un
informe del analizador sin ver primero cuánta cobertura real tuvo.

### 3.5 Borrador corregido

Fuera de alcance de R1 (se especifica en R4). R1 solo produce el informe de
hallazgos, no el borrador.

---

## 4. Flujo de revisión humana

```
documento + document_type
   │
   ▼
recuperación determinista (R2) + juicio LLM sobre candidatos (chunked_engine, H2+H4)
   │
   ▼
evidence_verifier (validación A) ── ancla o no ancla
   │
   ▼
ensamblado determinista del informe (R3)
   │
   ▼
factory/layer9/human_review_queue.py  ──  status: pending
   │
   ├── approved  → informe queda como registro auditable final
   ├── rejected  → vuelve a análisis / se descarta con motivo
   └── returned  → corrección solicitada, re-entra al flujo
```

- Reutiliza el `status` ya existente en `human_review_queue.py`
  (`pending`/`approved`/`rejected`/`returned`) — **no se inventan estados
  nuevos de aprobación**.
- El panel de revisión ya existente en `mission_control.py` /
  `approval_matrix.py` es el punto de decisión de Cesar/QA — el analizador
  no tiene ruta de aprobación automática, consistente con la regla
  permanente "sin aprobación automática de documentos".
- Cada entrada en la cola lleva el `sha256` del documento y el
  `coverage_summary` visibles, para que quien revise vea la limitación de
  cobertura antes de decidir.

---

## 5. Qué NO cubre esta spec (diferido a fases posteriores)

- Mecanismo exacto de recuperación determinista (top-k, umbral, query desde
  Evidence Pack) → R2.
- Reglas de clasificación NCR/CAPA/change control → R3.
- Generación del borrador controlado → R4.
- Golden Dataset ampliado y suite de regresión → R5.

---

## 6. Smoke E2E de cierre de R1 (criterio de aceptación del roadmap)

Una página de un documento real, con el pipeline **actual** (sin R2
todavía): `chunked_engine.evaluate_chunked()` + `evidence_verifier`, contra
un `requirement_id` del fixture set. El smoke produce un `finding` (o un
`sin_evidencia_localizada`/`no_evaluable`) con el formato de §3.1-3.4
exacto, **sin maquillar** el recall real — si el criterio evaluado cae en
el 5/7 que hoy no ancla, el informe lo muestra como tal, no como "cumple"
optimista.

---

## Bloque de estado

```
R1_SPEC_STATUS = DRAFT_FOR_REVIEW
ANALYZER_HOME = factory (:9000), NOT gmp-api (:8000)
INPUT_CONTRACT_DEFINED = true
OUTPUT_CONTRACT_DEFINED = true (6 campos + 3 estados honestos + cobertura obligatoria)
REVIEW_FLOW_DEFINED = true (reutiliza human_review_queue.py sin estados nuevos)
NCR_CAPA_CHANGECONTROL_RULES = DEFERRED_TO_R3
DRAFT_GENERATION = DEFERRED_TO_R4
SMOKE_PENDING = true (1 página, pipeline actual, sin maquillar recall)
PENDIENTE_DE_APROBACIÓN = spec completa (secciones 1-6) antes de correr el smoke
```
