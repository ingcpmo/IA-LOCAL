# ROADMAP — Analizador Documental GMP (R0-R5)

**Autoridad:** Capa 9 = Cesar. Claude Code = Capa 8.
**Origen:** `docs_plan/ARQ_REENFOQUE_ANALIZADOR_GMP.md` (Parte B).
**Estado del documento:** DISEÑO — ninguna fase de código arranca sin
aprobación explícita de Cesar sobre spec (R1) o autorización de llamadas
(R2 en adelante).

```
PRODUCTION_ENABLEMENT = BLOCKED
REGULATORY_COMPLIANCE = NOT_DETERMINED
CORPUS_READY = false
```

## Riesgo central (portada)

**El recall del modelo actual es 2/7** sobre el fixture set de 7 positivos
+ 2 negativos (`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md`), medido en la
configuración ganadora hasta ahora (H2+H4: 1 requirement/llamada, schema
mínimo — ver `docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`). Un
analizador que no encuentra evidencia presente en el documento produce
**NCRs falsos** — el peor tipo de error para un sistema que alimenta
decisiones de calidad. **R2 existe para resolver esto y es gate
bloqueante de R3, R4 y R5.** Ninguna fase posterior arranca sobre un
detector que fabrica brechas.

---

## R0 — Verdad documental (esta corrida, Parte A)

**Objetivo:** que la documentación del proyecto refleje el estado real
verificado, antes de diseñar nada más encima de supuestos desactualizados.

**Componentes reutilizados:** ninguno (es trabajo documental).

**Componentes nuevos:** `CLAUDE.md` y `CONTEXT_FOR_CLAUDE.md` actualizados;
cabecera ON_HOLD en `docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md`; este
roadmap.

**Tests:** N/A (documental).

**Criterio de aceptación medible:** diff de los 3 documentos mostrado a
Cesar y aprobado; commit realizado solo tras esa aprobación.

**Riesgos:** ninguno técnico — riesgo de proceso si se commitea sin
aprobación (violaría la regla de oro del proyecto).

**Dependencias:** ninguna.

**Firma Cesar:** aprobación de los diffs (checkpoint A de la corrida
`ARQ_REENFOQUE_ANALIZADOR_GMP.md`).

**Cierre:** docs actualizados y commiteados con aprobación.

---

## R1 — Especificación y baseline del analizador

**Objetivo:** auditar qué ya existe del analizador y proponer la
arquitectura del producto respetando la separación 8000/9000, sin escribir
código de producto todavía.

**Componentes reutilizados (con archivo real):**

| Capacidad | Archivo | Vive en |
|---|---|---|
| Detección de agente / orquestación de prompt | `app/orchestrator.py` | gmp-api :8000 |
| Reglas determinísticas (Capa 3) | `app/rules.py` | gmp-api :8000 |
| Registro de agentes GMP (6 especialistas) | `app/agents/base.py` | gmp-api :8000 |
| Audit trail 21 CFR Part 11 | `app/audit.py` | gmp-api :8000 |
| RAG / ChromaDB (chunking, colecciones) | `knowledge/retriever.py` | gmp-api :8000 |
| Motor de evaluación chunked contra Ollama (config H2+H4) | `factory/engines/gmpai_integrity/chunked_engine.py` | factory :9000 |
| Verificación determinista de citas ancladas | `factory/regulatory/evidence_verifier.py` | factory :9000 |
| Catálogo de requisitos (evidence packs) | `factory/regulatory/requirement_catalog/requirements.yaml` | factory :9000 |
| Gobernanza de evidence packs | `factory/regulatory/evidence_pack_governance.py` | factory :9000 |
| Orquestación de corridas sobre corpus | `factory/regulatory/corpus_runner.py` | factory :9000 |
| Cola de revisión humana | `factory/layer9/human_review_queue.py` | factory :9000 |
| Bitácora de decisiones (Part 11) | `factory/layer9/decision_log.py` + `factory/layer9/decisions/decisions_v2.jsonl` | factory :9000 |
| Fixture set de recall (instrumento de medición) | `docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md` | — |
| Diseño de agentes de remediación (AGT-REM/QLT/DOC/RVL) | `factory/docs/design/regulatory_redesign_v2/AGENT_RESPONSIBILITY_ARCHITECTURE.md` | factory :9000 |

**Componentes nuevos:**
- Documento de arquitectura del analizador (parte de este R1) que fije la
  **recomendación**: el analizador vive como capacidad de **factory**
  (usa `evidence_verifier`, `chunked_engine`, `evidence_pack_governance`,
  la cola de revisión de Capa 9), reutilizando el patrón ChromaDB del
  copiloto base (`knowledge/retriever.py`) **sin tocar `gmp-api`**.
- Contrato del producto:
  - **Entrada:** documento + tipo documental (mismo concepto que
    `document_type` ya usado por `corpus_plan.resolve_document_agent_plan`
    para filtrar aplicabilidad).
  - **Salida:** informe de hallazgos con los 6 campos de Cesar (qué está
    mal, por qué no cumple, requisito/regulación/gobernanza usada,
    evidencia anclada, riesgo, acción recomendada) **más** un estado
    honesto por criterio: `hallazgo con evidencia` /
    `sin evidencia localizada con cobertura declarada` / `no evaluable`.
  - **Flujo de revisión humana:** reutiliza `human_review_queue.py` y el
    patrón de aprobación de Capa 9 (`approval_matrix.py`), sin estados
    nuevos de aprobación automática.

**Tests:** ninguno de código todavía — el criterio de cierre es un smoke
manual, no una suite automatizada.

**Criterio de aceptación MEDIBLE:**
1. Spec del contrato (entrada/salida/flujo) aprobada por Cesar.
2. Smoke E2E de **una página** de un documento real, con el pipeline
   actual (`chunked_engine.evaluate_chunked()` + `evidence_verifier`),
   documentando la capacidad presente **sin maquillar** la limitación de
   recall (2/7) — el smoke reporta el estado real del criterio evaluado,
   incluidos los `NOT_ASSESSABLE`/sin evidencia.

**Riesgos:** que la spec subestime la limitación de recall y prometa un
informe más completo de lo que el pipeline actual puede sostener — mitigado
exigiendo que el smoke de cierre use datos reales, no un caso favorable
elegido a mano.

**Dependencias:** R0 cerrado (documentación veraz de base).

**Firma Cesar:** aprueba la spec del contrato y el resultado del smoke.

---

## R2 — Localización de evidencia por recuperación determinista (la apuesta)

**Objetivo:** invertir la arquitectura de búsqueda. La lección de los
pilotos (`docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`, H1-H4): el
modelo juzga aceptablemente pasajes bien delimitados que tiene delante
(P1/P5 anclaron en H2/H4), pero es malo **buscando** (H3 empeoró el recall
al pedirle extracción libre) y frágil con páginas ruidosas.

**Diseño:**
- Indexar el documento objetivo en una colección propia de ChromaDB
  (mismo patrón de `knowledge/retriever.py` / `_split_text`, con mapeo
  chunk→página), más una segunda vía textual/BM25 para candidatos que el
  embedding semántico pueda perder.
- Por `requirement_id`: construir la consulta de recuperación **desde el
  Evidence Pack** (`canonical_text` + `evidence_min_criteria` +
  sinónimos gobernados del catálogo, `factory/regulatory/requirement_catalog/requirements.yaml`)
  — **nunca `weak_keywords` solas** como consulta (ese es justamente el
  patrón que ya se prohibió aflojar en la Sección 0 de
  `W5V2_REMEDIACION_RECALL_MODELO.md`).
- Recuperar top-k pasajes candidatos (k pequeño, con umbral); el LLM
  (configuración H2+H4, la ganadora medida) **solo juzga esos pasajes** —
  tarea de juicio, no de búsqueda. Validación A (`evidence_verifier`) ancla
  igual que siempre; C/D intactas.
- **Cobertura honesta:** si la recuperación no localiza candidatos, el
  estado es `sin evidencia localizada (cobertura de recuperación
  declarada)` — alimenta la cola de revisión humana, **no** se convierte
  en un gap firme automático.

**Componentes reutilizados:** `chunked_engine.py` (config H2+H4, sin
tocar su contrato de juicio), `evidence_verifier.py` (validación A sin
cambios), `requirement_catalog/requirements.yaml` (fuente de la consulta),
`knowledge/retriever.py` (patrón de chunking/ChromaDB).

**Componentes nuevos:** módulo de recuperación determinista por
`requirement_id` (nombre y ubicación exacta a definir en el diseño
detallado de R2, dentro de `factory/regulatory/` para mantener la
separación 8000/9000); lógica de construcción de query desde Evidence Pack.

**Tests:** suite de recuperación contra el fixture set 7P+2N — para cada
positivo, verificar que el pasaje verificado a mano esté entre los top-k
candidatos (métrica de recuperación, separada de la métrica de recall del
LLM); regresión de que el negativo (ANNEX11_4) no arrastre candidatos que
disparen un `cumple` falso.

**MEDICIÓN:** contra el fixture set 7P+2N. **Criterio de éxito idéntico al
de siempre:** `recall ≥ 6/7` positivos anclados ∧ `2/2` negativos
rechazados ∧ `schema_valid_rate = 100%`. Las llamadas LLM de esta medición
requieren autorización de Cesar — proponer `PILOT_EXECUTION-2026-00X` con
tope de llamadas (la parte de recuperación pura es determinista y no
consume presupuesto LLM, solo la fase de juicio final sobre los top-k).

**GATE BLOQUEANTE:** si R2 no alcanza 6/7, **DETENERSE** y presentar a
Cesar la disyuntiva: reactivar `W5V2_REMEDIACION_RECALL_MODELO.md`
(H5 modelo alternativo, H7 MarkItDown), o las salidas del Escenario B ya
documentadas. **R3-R5 no arrancan** sobre un detector que fabrica brechas.

**Riesgos:** que la recuperación determinista introduzca sus propios
falsos negativos (documento indexado con chunking distinto al que ancló
en H2/H4) — mitigado midiendo recuperación y recall del LLM por separado.

**Dependencias:** R1 aprobado (contrato del producto define qué
`requirement_id`s entran en el smoke de R2).

**Firma Cesar:** autoriza `PILOT_EXECUTION-2026-00X` antes de la primera
llamada de medición; decide sobre el gate si R2 no alcanza 6/7.

---

## R3 — Generador de informe de hallazgos

**Objetivo:** ensamblar el informe final de forma determinista a partir de
los registros ya verificados por R2 — el LLM no decide qué entra al
informe, solo redacta prosa sobre datos ya anclados.

**Diseño:**
- Ensamblado determinista desde los checkpoints verificados: los 6 campos
  de Cesar por hallazgo.
- Clasificación **NCR potencial** / **CAPA candidate** / **change control
  candidate** con reglas explícitas (por criticidad del requisito, tipo de
  brecha detectada, y tipo documental) — no una decisión del LLM.
- Riesgo y acción recomendada, derivados de las mismas reglas.
- **Cobertura y limitaciones siempre visibles** en el informe: qué
  porcentaje de requisitos aplicables tuvo evidencia localizada, cuántos
  quedaron en `sin evidencia localizada`, cuántos `no evaluable`.
- El LLM solo redacta prosa explicativa sobre datos ya verificados; nada
  entra al informe sin un registro anclado (checkpoint + validación A)
  detrás.

**Componentes reutilizados:** salida de R2 (checkpoints verificados),
`evidence_pack_governance.py` (criticidad por requisito),
`decision_log.py` / `decisions_v2.jsonl` (patrón de registro auditable).

**Componentes nuevos:** módulo generador de informe; reglas de
clasificación NCR/CAPA/change-control (documento de reglas explícito,
revisable por Cesar antes de codificarse).

**Tests:** informe generado a partir de checkpoints sintéticos con
cobertura mixta (algunos anclados, algunos sin evidencia, algunos no
evaluables) — verificar que el informe nunca omite la sección de
limitaciones y que ningún hallazgo aparece sin checkpoint verificado
detrás.

**Criterio de aceptación MEDIBLE:** informe E2E de un documento real del
fixture, revisado por Cesar contra su expectativa de QA.

**Riesgos:** que las reglas de clasificación NCR/CAPA/change-control
codifiquen un juicio de QA que en realidad requiere criterio humano caso
por caso — mitigado dejando esas reglas como propuesta clasificatoria
(no vinculante) que la cola de revisión humana puede corregir.

**Dependencias:** R2 pasó el gate de recall (≥6/7).

**Firma Cesar:** aprueba las reglas de clasificación NCR/CAPA/change-control
y el informe E2E de cierre.

---

## R4 — Borrador corregido controlado

**Objetivo:** generar una versión corregida del documento como borrador
controlado, nunca aprobado automáticamente, reutilizando el diseño W5 V2
ya especificado.

**Diseño:**
- Reutilizar la cadena de agentes ya diseñada
  (`factory/docs/design/regulatory_redesign_v2/AGENT_RESPONSIBILITY_ARCHITECTURE.md`):
  AGT-REM → AGT-QLT → AGT-DOC → AGT-RVL, con sus 9 artefactos y el
  generation gate ya definido.
- Acotado a: **borrador controlado**, marca de agua / nota de
  "no-aprobado" visible en el documento generado, **solo cambios con
  hallazgo anclado detrás** (ningún cambio "porque se ve mejor"),
  excepciones documentales separadas del cuerpo corregido, **original
  intacto** (nunca se sobrescribe).

**Componentes reutilizados:** diseño AGT-REM/QLT/DOC/RVL y sus 9
artefactos (spec ya existente, no se rediseña); informe de R3 como
entrada (los hallazgos anclados son la única fuente de cambios).

**Componentes nuevos:** ninguno de arquitectura — es la ejecución del
diseño ya especificado, ahora acotada por los hallazgos reales de R2/R3
en vez de datos sintéticos.

**Tests:** verificar que todo cambio en el borrador tenga un hallazgo
anclado trazable; verificar que el documento original en disco no se
modifica (solo se genera un artefacto nuevo).

**Criterio de aceptación MEDIBLE:** el **Piloto 2** original (cadena
completa sobre el documento más pequeño del corpus) ejecutado con la
configuración que pasó R2. Piloto 2 deja de estar en espera
(`PILOT2_STATUS = ON_HOLD` en `W5V2_REMEDIACION_RECALL_MODELO.md`) y se
convierte en el test de aceptación de R4.

**Riesgos:** que el borrador introduzca cambios no trazables a un hallazgo
anclado — mitigado por el test de trazabilidad y por la marca de
"no-aprobado" obligatoria.

**Dependencias:** R3 aprobado; Piloto 2 desbloqueado explícitamente por
Cesar (hoy `ON_HOLD`).

**Firma Cesar:** autoriza la ejecución de Piloto 2 y aprueba (o rechaza)
su resultado como criterio de cierre de R4.

---

## R5 — Paquete QA y endurecimiento

**Objetivo:** cerrar el ciclo con trazabilidad extremo a extremo y
convertir el analizador en algo operable de forma repetible.

**Diseño:**
- Cola de revisión humana completa, reutilizando los paneles existentes de
  decisiones (`factory/layer9/human_review_queue.py`,
  `factory/layer9/mission_control.py`).
- Paquete QA por documento (mismo patrón que `qa_packages/` en factory).
- Métricas de operación (recall sostenido, cobertura, latencia p50/p95 —
  mismo tipo de medición que ya se usó en H1-H4).
- **Golden Dataset del analizador**: fixture set ampliado
  (`docs_plan/W5V2_RECALL_FIXTURE_SET_DRAFT.md` como base, con nuevos
  documentos fuera del corpus piloto).
- Suite de regresión que fija todo lo anterior en **Gate 0** (mismo
  concepto que el Gate 0 ya usado en la fábrica — ver
  `project_gmp_factory.md`: 163 passed, Gate 0 PASS).

**Componentes reutilizados:** `human_review_queue.py`,
`mission_control.py`, patrón `qa_packages/`, Gate 0 existente.

**Componentes nuevos:** Golden Dataset ampliado del analizador; suite de
regresión específica del pipeline R2→R3→R4.

**Tests:** la propia suite de regresión es el entregable de tests de esta
fase.

**Criterio de aceptación MEDIBLE:** un ciclo completo
documento→informe→borrador→revisión de Cesar, con **cero fallos
silenciosos** y trazabilidad extremo a extremo (cada afirmación del
informe final rastreable hasta un checkpoint verificado y, de ahí, hasta
el pasaje literal del documento original).

**Riesgos:** deuda de mantenimiento del Golden Dataset ampliado si no se
versiona con la misma disciplina que el fixture set original — mitigado
exigiendo el mismo proceso de aprobación de Cesar para cada versión.

**Dependencias:** R4 cerrado (Piloto 2 aprobado).

**Firma Cesar:** aprueba el Golden Dataset ampliado, la suite de
regresión, y declara el analizador listo para el siguiente nivel de
decisión (que sigue siendo de Cesar: alcance de producción, corpus real,
etc. — fuera de este roadmap).

---

## Diferidos (reactivables, no muertos)

- **MarkItDown / H7** — si R2 muestra que el ruido de entrada documental
  sigue pesando incluso con recuperación determinista.
- **H5 (modelo alternativo) / H6 (no-determinismo)** — si el juicio del
  modelo sigue siendo el cuello de botella incluso con pasajes servidos
  por R2.
- **Corpus formal W5** — cuando el analizador esté consolidado (R5
  cerrado) y Cesar decida retomar el baseline Rockwell completo con la
  configuración que pasó R2.

Todos referenciados y clasificados en la cabecera ON_HOLD de
`docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md`.
