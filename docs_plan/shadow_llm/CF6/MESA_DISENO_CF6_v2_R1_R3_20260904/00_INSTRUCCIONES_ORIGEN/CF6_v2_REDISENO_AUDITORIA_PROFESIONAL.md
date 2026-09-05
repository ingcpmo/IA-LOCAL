# CF-6 v2.0 — REDISEÑO CONSOLIDADO: DE "BLOQUEAR SALIDAS MALAS" A "AUDITAR CORRECTAMENTE"

**Fecha:** 2026-09-04 · **Autoridad:** Capa 9 = Cesar · **Tipo:** DISEÑO. No implementa.
**Reemplaza y absorbe** CF-6 v1.3 — no es un proyecto paralelo. Todo lo de v1.2/v1.3 que funcionaba se
conserva; lo que se generaliza se generaliza, no se descarta.

**Objetivo que gobierna cada decisión de este documento** (cita directa de la revisión):
> *GMP AI Factory debe ser capaz de leer documentación técnica, entender qué exige la regulación,
> distinguir evidencia pertinente de ruido, realizar una interpretación GMP defendible, adjudicar
> dentro de una autoridad controlada y entregar un informe profesional que un experto pueda utilizar
> directamente.*

---

## 0 · DIAGNÓSTICO CONCRETO DE LA LIMITACIÓN ACTUAL

CF-6 v1.3 (Q-STATE-7) verificaba **después de que el LLM ya había redactado**: tomaba el texto libre de
`reviewer_action`/`evidence_limitation` y comprobaba si contenía términos ausentes del sub-criterio. Es
un control de salida, correcto pero tardío — protege contra la mala redacción, no ayuda a que la
redacción sea buena, porque el LLM sigue viendo **todo el `EvidenceBundle`** (hasta 5 candidatos BM25),
incluida evidencia que el retrieval recuperó pero que no responde al requisito. `sec-0016` es exactamente
eso: el candidato sobre "medición de parámetros críticos" estaba en el bundle porque BM25 lo encontró
léxicamente cercano, y el LLM lo usó porque estaba disponible, no porque fuera pertinente.

**El defecto de fondo es una capa que falta, no un gate que falta:** nunca existió una separación entre
*"evidencia recuperada"* y *"evidencia pertinente para este requisito"*. Ese es el punto de mayor
apalancamiento de todo el rediseño (§3-§4).

**Respuesta directa al punto 16:** CF-6 v1.3 **(c) debe integrarse dentro de una revisión mayor del
Composer.** El mecanismo de Q-STATE-7 (comparar contra `decomposition.yaml` firmado) **no se descarta —
se generaliza**: en vez de aplicarse una sola vez sobre el texto final, se aplica **por cada ítem de
evidencia, antes de que el LLM la vea** (§4). Q-STATE, blacklist y SAFE_MODE se conservan íntegros como
capa de seguridad — dejan de ser el centro del diseño y pasan a ser lo que siempre debieron ser: la red
que protege una evaluación que ahora se construye correctamente desde el origen, no una sustituta de esa
evaluación.

---

## 1 · QUÉ SE CONSERVA SIN TOCAR (baseline, no se reabre salvo evidencia de defecto)

```
L0/L1/L2 inmutable · routing · expert opinions · source anchoring · fingerprints
Q-STATE-1..7 existentes · fail-closed · blacklist · SAFE_MODE · 0 llamadas LLM post-Q-STATE
render determinista · governance · prompts/modelos/políticas versionados · G4d sin re-ejecutar
```

---

## 2 · CAMBIO DE CENTRO: LAS DIEZ PREGUNTAS QUE EL PIPELINE DEBE PODER RESPONDER

Por cada requisito, el flujo (no un único componente) debe poder sostener, con trazabilidad:

```
1. ¿Qué exige el requisito?                    → texto gobernado (decomposition.yaml), NO inventado
2. ¿Cuál es su intención regulatoria?          → texto gobernado, NO inventado por el LLM
3. ¿Qué evidencia documental es pertinente?    → Requirement↔Evidence Relevance Model (§4), determinista
4. ¿Qué capacidad demuestra esa evidencia?     → LLM, sobre evidencia YA filtrada (§5)
5. ¿Qué NO demuestra?                          → LLM, mismo alcance
6. ¿Hay brecha técnica/documental/procedimental? → LLM + Q-STATE
7. ¿Qué depende de tecnología?                 → LLM (technical_assessment)
8. ¿Qué depende del regulated user/SOP?        → LLM (procedural_responsibility)
9. ¿Qué estado de evaluación es sostenible?    → determinista (Q-STATE, igual que hoy)
10. ¿Cómo se explica al auditor?               → render determinista + ProfessionalAssessmentRecord (§10)
```

Puntos 1, 2 y 9 son deterministas por diseño — **el LLM nunca inventa qué exige la ley ni si el caso es
sostenible**; eso ya viene de datos gobernados y del verificador. El LLM solo hace 4, 5, 6, 7, 8: **eso
es exactamente su trabajo correcto — interpretar, no decidir el estado.**

---

## 3 · CONTRATO REQUIREMENT-CENTRIC (superset del de v1.2, retrocompatible)

```
requirement_id · regulatory_reference          (existente, de L2/provenance)
requirement_text · requirement_intent          (NUEVO — sourced de decomposition.yaml, NO autoría LLM)
applicable_context                             (NUEVO — document_type, section, jurisdiction si aplica)

candidate_evidence[]                           (NUEVO — el EvidenceBundle crudo, con relevance_state c/u)
relevant_evidence[]                            (NUEVO — subset RELEVANT|PARTIALLY_RELEVANT)
excluded_evidence[]                            (NUEVO — subset IRRELEVANT, conservado para auditoría)

observed_system_capability                     (LLM, solo sobre relevant_evidence)
evidence_basis · evidence_limitation           (existente v1.2, ahora anclado solo a relevant_evidence)

technical_assessment · procedural_responsibility   (NUEVO — separa "depende de tecnología" de "depende
                                                     de SOP/proceso", exactamente lo que pide el punto 8)
gap_or_open_question                           (sustituye/generaliza reviewer_action)

assessment_state ∈ {INCONCLUSIVE, NOT_ANALYZABLE, NOT_APPLICABLE}   (idéntico a regulatory_state v1.2)
assessment_rationale                           (LLM, resumen del razonamiento — auditable)
confidence / uncertainty                       (NUEVO — ver §8)
provenance                                     (existente — hashes, versiones, fingerprint)
```

`section_type` de v1.2 se conserva como metadato de agrupación para el render, pero **la clave primaria
pasa a ser `requirement_id`**, no la sección — es la reorganización requirement-centric que pide el
punto 3. Migrar el agrupamiento actual (por sección) a agrupamiento por requisito es trabajo de
implementación de esta fase (R1, §13), no requiere nueva capacidad de modelo.

---

## 4 · REQUIREMENT ↔ EVIDENCE RELEVANCE MODEL (la pieza central del rediseño)

**Determinista, fail-closed, trazable — igual que todo lo demás en este sistema.** Se aplica **por cada
ítem** de `candidate_evidence[]`, antes de cualquier llamada al Composer:

```
Para cada evidencia e en el EvidenceBundle del requisito r:
  decomposed_terms = decomposition.yaml[r].terms_canónicos + sinónimos gobernados (YA firmado, no nuevo)
  overlap = solapamiento léxico/lematizado entre e.source_text y decomposed_terms
  bm25_score = ya disponible del retrieval existente (sin recomputar)

  overlap alto            → relevance_state = RELEVANT
  overlap parcial         → relevance_state = PARTIALLY_RELEVANT
  overlap nulo + bm25 bajo → relevance_state = IRRELEVANT
  ambiguo                 → relevance_state = INCONCLUSIVE   (conservador: NO entra a relevant_evidence)

relevant_evidence[]  = { e : relevance_state ∈ {RELEVANT, PARTIALLY_RELEVANT} }
excluded_evidence[]  = { e : relevance_state ∈ {IRRELEVANT, INCONCLUSIVE} }   ← se registra, no se borra
```

**Regla estructural que corrige `sec-0016` en la raíz, no en el síntoma:** el Composer LLM **nunca
recibe `excluded_evidence[]`**. No es que se le pida que la ignore — no está en su prompt. El candidato de
"medición de parámetros críticos" jamás habría llegado al modelo para 21 CFR 11.10(d), porque el
solapamiento con el texto decompuesto de ese sub-criterio es bajo. Esto responde directamente al punto 5
de la revisión: el LLM interpreta mejor porque su materia prima ya está acotada, no porque se le
instruya con más cuidado sobre qué evitar.

**Fail-closed:** si `relevant_evidence[]` queda vacío, la sección se renderiza con la plantilla
determinista existente ("no se identificó evidencia pertinente"; ver v1.2 §3.3) — **sin invitar al LLM a
especular** sobre evidencia que ya se determinó irrelevante.

**Esto generaliza Q-STATE-7**, no lo sustituye: Q-STATE-7 (v1.3) verificaba el texto final contra
`decomposition.yaml`; el Relevance Model aplica la misma fuente gobernada **antes**, por evidencia. El
Q-STATE-7 original se conserva como **segunda verificación** (defensa en profundidad): si por algún
fallo del filtro previo un término fuera de alcance llegara al texto, sigue rechazándose ahí.

**Medible objetivamente (responde al punto 4, "debe ser trazable"):** a diferencia de `technical_
assessment` (que necesita rúbrica humana), `relevance_state` es una salida discreta determinista — se
puede construir un conjunto etiquetado por un humano (muestra de pares requisito×evidencia) y medir
precisión/recall del propio modelo de relevancia, **sin depender del LLM del Composer para evaluarlo**.

---

## 5 · COMPOSER REDISEÑADO — CUATRO PASOS, NO UNO

```
1. FILTRO DE RELEVANCIA (determinista, §4) — se ejecuta ANTES de cualquier llamada a modelo
2. INTERPRETACIÓN (LLM) — recibe SOLO relevant_evidence[] + requirement_text/intent gobernados;
   emite el contrato §3 (observed_capability, technical_assessment, procedural_responsibility,
   gap_or_open_question, assessment_rationale, confidence)
3. VERIFICACIÓN DE ESTADO (determinista) — Q-STATE-1..7 sobre la salida, igual que v1.2/v1.3
4. RENDER (determinista) — igual que v1.2, plantilla parametrizada, 0 LLM después de este punto
```

El punto de no-retorno de v1.2 (cero LLM tras Q-STATE) **no cambia**. Lo que cambia es que ahora también
hay un filtro determinista **antes** del paso 2 — la seguridad se refuerza en ambos extremos del único
paso LLM, que sigue siendo uno solo por sección/requisito.

---

## 6 · DOS DIMENSIONES INDEPENDIENTES (punto 13) — acceptance criteria bifurcados

```
SAFETY / GOVERNANCE (preservado íntegro de v1.2):
  L2_MUTATIONS=0 · fingerprint intacto · 0 LLM post-Q-STATE · egress=0 · human_state sin cambios ·
  G4d=0 · SAFE_MODE disparado correctamente cuando corresponde

AUDIT QUALITY (nuevo, medido por separado — SAFE_MODE=PASS NO implica calidad=suficiente):
  requirement_interpretation_accuracy   → rúbrica humana, por requisito
  evidence_relevance_accuracy           → MEDIBLE DETERMINÍSTICAMENTE: precisión/recall de
                                           relevance_state contra muestra etiquetada por humano (§4)
  gmp_assessment_accuracy               → rúbrica humana
  citation_fidelity                     → determinista (verificador de anclaje, YA existe)
  unsupported_conclusions = 0           → determinista (extiende Q-STATE)
  regulatory_overstatement = 0          → determinista (blacklist) + residual humano
  professional_clarity                  → rúbrica humana
  audit_utility / value_added vs L2     → rúbrica humana, comparativo A/B (HUMAN_QUALITY_GATE existente)
  cognitive_load_reduction              → rúbrica humana (pregunta ya en CF-6 v1.2 §4.2)
```

Un resultado puede ser `SAFE_MODE=seguro` y `professional_value=insuficiente` simultáneamente — ambas
dimensiones se reportan siempre, nunca se colapsan en un solo PASS/FAIL.

---

## 7 · ESTRATEGIA DE ESPECIALIZACIÓN DEL LLM (M0–M7, escalonada por evidencia)

```
M0  baseline 7B actual                                                    [YA EXISTE]
M1  mejor contexto/decomposición del requisito                            → §3/§4 de este documento
M2  RAG controlado + glosario + expansión semántica                       → candidato acotado (ver nota)
M3  case memory (precedentes adjudicados y validados)                     → gateado (ver nota)
M4  benchmark contra modelo local más capaz                               → gateado por evidencia de M0-M3
M5  dataset GMP especializado y versionado                                → gateado
M6  LoRA/PEFT si el benchmark demuestra necesidad                         → gateado
M7  model qualification (champion vs challenger)                         → gateado
```

**M1 se ejecuta en esta fase** — es literalmente el Relevance Model + `requirement_text`/`requirement_
intent` sourced de datos gobernados (§3-§4).

**M2, nota de alcance:** "RAG controlado" **no significa** nueva infraestructura ni acceso a Internet
(el `Regulatory Retrieval Gateway` sigue diseñado-no-habilitado, sin cambios respecto de la decisión
previa). Significa evaluar si activar el modo `fusion` (BM25 + embeddings) que **ya existe en el código**
(`retrieval/{embed,fusion}.py`) pero está apagado (`evidence_bundle` usa solo `bm25` hoy) mejora la
composición de `candidate_evidence[]` antes del filtro de relevancia. Esto es un **benchmark acotado**
(BM25-solo vs BM25+fusion sobre el mismo corpus), 100% local, sin nueva dependencia — se autoriza
**explorar la comparación**, no activar `fusion` por defecto sin ver el resultado.

**M3 en adelante quedan gateados por evidencia**, exactamente como pide la revisión: no se asume que
LoRA sea necesario, no se asume que el 7B sea suficiente. M3 requiere un volumen mínimo de precedentes
humanos adjudicados que hoy no existe (7 secciones no bastan). M4-M7 requieren que el benchmark de M0-M2
demuestre que el 7B es el cuello de botella para las dimensiones de calidad de §6 que M1/M2 no pueden
resolver estructuralmente — decisión que se toma con datos, no antes.

---

## 8 · SEPARACIÓN EXPLÍCITA: PESOS DEL MODELO vs APRENDIZAJE DEL SISTEMA

```
LLM WEIGHTS                     conocimiento/memoria del sistema
  cambian SOLO por              case memory, RAG, decomposition.yaml, políticas, precedentes
  release calificada (M6+M7)    → pueden crecer de forma continua, gobernados, versionados

NUNCA:  Internet → modelo → entrenamiento directo → producción.
```

`confidence`/`uncertainty` (nuevo campo §3) es una **calibración operativa del sistema** (umbral fijado
sobre un conjunto held-out), no un peso del modelo — vive en la capa de "aprendizaje del sistema".

---

## 9 · GMP ADJUDICATION EXPERT — DISEÑO COMPLETO, COMO `TARGET_INTENDED_USE_CANDIDATE`

**No se implementa. No se bloquea del diseño.** Se especifica por completo para que Capa 9 tenga con qué
decidir, exactamente como pide el punto 8. Es una **evolución de intended use**, no un componente de
ingeniería — la misma categoría que D-1 en la mesa de reconciliación.

### 9.1 · Arquitectura (separado del Composer, punto 9)

```
INPUT:  requirement_id, requirement_text, requirement_intent (gobernados)
        relevant_evidence[] + excluded_evidence[] (del Relevance Model — NUNCA solo la narrativa)
        interpretación estructurada del Composer (§3)
        precedentes (case_memory, cuando exista — M3+)
        AdjudicationPolicy (versionada, firmada por Capa 9)

OUTPUT: assessment_state ∈ {AUTO_ACCEPT, AUTO_INCONCLUSIVE, AUTO_NOT_APPLICABLE,
                            REQUIRES_EVIDENCE, CONFLICT_DETECTED, HUMAN_REVIEW_REQUIRED}
        confidence (calibrado) · reason_codes[] · decision_payload_sha256
        policy_version · model_version/digest · prompt_version · requirement_version ·
        evidence_bundle_hash · precedents_used[] · execution_fingerprint · timestamp
```

El Adjudicator **lee L2 y la evidencia directamente** — no aprueba la narrativa del Composer, la
contrasta de forma independiente (evita que el mismo sesgo se auto-apruebe, punto 9 de la revisión).

### 9.2 · `AdjudicationPolicy` — autoridad delegada limitada

Elegible para `AUTO_*` solo si **todas** se cumplen:
```
relevant_evidence no vacío y todo RELEVANT (no solo PARTIALLY_RELEVANT)
Q-STATE = PASS sin excepción
confidence ≥ umbral calibrado (calibrado sobre held-out, no arbitrario)
sin evidencia contradictoria detectada
risk_band ∉ {CRITICAL, HIGH}                      (configurable, default conservador)
requirement_id tiene decomposition.yaml firmado y conocido — nunca sobre regulación no gobernada
cross_domain_flag = NO                             (cross-domain SIEMPRE escala, ya es la regla hoy)
NO es de las primeras N ocurrencias de ese patrón requisito×tipo-documento (evita puntos ciegos en
  combinaciones nuevas; N conservador, configurable)
SAFE_MODE no se disparó en ningún punto de la cadena
```
Cualquier condición no cumplida → `HUMAN_REVIEW_REQUIRED`. **Escalan siempre, sin excepción de
política:** documentos `NOT_ANALYZABLE`, banda de riesgo CRITICAL/HIGH, cualquier conflicto, cualquier
patrón de primera ocurrencia.

### 9.3 · Métrica crítica: `false_autonomous_approval_rate`

Se mide por muestreo retrospectivo de decisiones `AUTO_ACCEPT` con auditoría humana — **nunca se confía
al 100% sin verificación de muestra**. Propuesta de partida: **tolerancia objetivo = 0 aprobaciones
falsas detectadas en el conjunto de calificación**, con infraestructura de escalamiento formal para
cualquier caso detectado. El nivel de tolerancia final lo fija el apetito de riesgo de Capa 9, no la
ingeniería.

### 9.4 · Trazabilidad, rollback, y advertencia regulatoria

Toda decisión reconstruible vía `decision_payload_sha256`; **nunca se presenta como firma humana** —
cualquier reporte que muestre una decisión `AUTO_*` debe distinguirla visual y estructuralmente de una
firma de Capa 9. Rollback: un flag `adjudicator_enabled=false` revierte a 100% revisión humana sin costo
de migración (los estados `AUTO_*` son metadato aditivo).

**Advertencia que Capa 9 debe sopesar, no una recomendación de ingeniería:** el borrador de EU GMP Annex
22 (dirección regulatoria emergente, no vigente — ver mesas anteriores de este arco) favorece modelos
estáticos deterministas en aplicaciones **críticas** y reserva los modelos generativos/LLM para usos
**no críticos con supervisión humana**. Un adjudicador LLM que decide cumplimiento regulatorio de forma
autónoma es, bajo esa dirección, precisamente el tipo de aplicación que se esperaría mantener con
supervisión humana. Esto no bloquea el diseño, pero **debe entrar en la decisión de Capa 9** como
factor de riesgo regulatorio, no solo técnico.

### 9.5 · Gate de habilitación

```
D-ADJ = decisión de Capa 9, separada, análoga a D-1. Requiere: tolerancia de
        false_autonomous_approval_rate explícita · alcance (qué clases de requisito son elegibles) ·
        compromiso de reversibilidad · postura frente a la dirección de Annex 22.
NO programada en las fases R1–R6 de este documento (§13).
```

---

## 10 · `ProfessionalAssessmentRecord` — objeto intermedio (más importante que la plantilla)

```
requirement_id · regulatory_reference · requirement_intent
system_response / observed_capability
evidence_basis · evidence_limitation
technical_assessment · procedural_responsibility
assessment_state · required_verification / open_item
provenance (hashes, versiones, fingerprint, y si aplica: decisión del Adjudicator con su distinción
            visual de "MACHINE ADJUDICATED")
```

Es el objeto que alimenta **tanto** el `HUMAN_QUALITY_GATE.md` interno (QA) **como**, más adelante, el
`ProfessionalReportModel` (§11) — una sola fuente de verdad estructurada, no dos generaciones libres
distintas. **Se diseña y se construye en esta fase (R1)**: es una extensión de esquema, no una nueva
capacidad de modelo, y no cambia el intended use.

---

## 11 · `ProfessionalReportModel` — diseño del documento cliente (no su renderer todavía)

Inspirado, sin copiar, en el patrón `Requirement | Reference | Answer` de la ficha Siemens ERES adjunta
(prueba de que este patrón funciona en la industria para exactamente este propósito):

```
1. Executive Summary        6. Detailed Findings
2. Scope and Methodology    7. Open Evidence / Additional Verification
3. Regulatory Framework     8. Conclusions
4. Assessment Overview      9. Governance / Provenance
5. Evaluation List         10. Technical Appendix

Fila de la Evaluation List: Requirement | Reference | System/Technical Response | Evidence Basis |
                             Procedural Responsibility | Assessment
```

**Prohibido en el cuerpo principal:** `Q-STATE`, `SAFE_MODE`, `machine_state`, jerga de mecanismos
internos — eso va al Apéndice Técnico (10), no al cuerpo que lee el auditor.

**`HUMAN_QUALITY_GATE.md` permanece interno** (QA/validación de modelo). El documento cliente se
construye desde `ProfessionalAssessmentRecord` con un **renderer determinista**, igual que el resto del
sistema — el LLM nunca genera el PDF/Markdown final libremente.

**Se diseña el modelo ahora; el renderer se implementa cuando exista contenido validado que renderizar**
(tras R5, §13) — construirlo antes sería, como se señaló en el ciclo anterior, trabajar en el orden
equivocado. Diseñar no es lo mismo que implementar: aquí solo se fija el esquema.

---

## 12 · BENCHMARK EXPANDIDO (diseño de categorías, no ejecución)

Mantener las 7 secciones actuales, especialmente `sec-0016`/`sec-0018`/`sec-0062`, como regression set.
Añadir categorías: evidencia positiva clara, evidencia ausente clara, evidencia ambigua, **evidencia
irrelevante pero semánticamente similar (exactamente el patrón de `sec-0016`)**, paráfrasis técnica,
evidencia contradictoria, requisitos cross-domain, control procedimental vs técnico, distintas
jurisdicciones, redacción adversarial.

**Nota de disciplina, aplicando el principio ya usado en el hardening (patrón `regulated-agent-
protocol` §3.4):** este fixture debería construirlo o revisarlo un autor **independiente** del autor del
prompt del Composer, para que no se contamine el instrumento de medición con el mismo sesgo que mide.
No se ejecuta en esta fase — es preparación (R4, §13).

---

## 13 · FASES INCREMENTALES Y QUÉ REQUIERE DECISIÓN DE CAPA 9

```
R0  ACEPTACIÓN DE DISEÑO (este documento) — Capa 9 revisa, sin ejecución
R1  Relevance Model (§4) + contrato requirement-centric (§3) + ProfessionalAssessmentRecord (§10)
    — implementación. Generaliza y ABSORBE Q-STATE-7 de v1.3. SIN cambio de intended use.
R2  Regenerar la muestra CF6-2.5 bajo el nuevo contrato + filtro de relevancia; HUMAN_QUALITY_GATE
    evaluado contra las dimensiones de §6 (no solo PASS/FAIL binario)
R3  Exploración M1/M2: benchmark acotado BM25-solo vs BM25+fusion (100% local); SIN cambio de
    intended use
R4  Construcción del fixture de benchmark expandido (§12), preferible con autor independiente
R5  Corrida completa CF6-3 bajo la arquitectura R1-R3, mismo régimen de gates que siempre
R6  Finalizar el esquema de ProfessionalReportModel contra contenido validado de R5 (aún interno)

DECISIONES DE CAPA 9 (NO programadas en R1–R6, requieren determinación explícita separada):
  D-ADJ         habilitar el GMP Adjudication Expert (§9) — nueva determinación de intended use
  D-M4+         iniciar benchmark de modelo mayor / dataset / LoRA / qualification — solo si R3
                demuestra que el 7B es el cuello de botella
  D-REPORT-EXT  distribución externa del ProfessionalReportModel a cliente/auditor — tras R6
```

**Lo que puede ejecutarse ahora sin cambiar intended use:** R1, R2, R3 (exploración acotada), R4, R5, y
el diseño (no la habilitación externa) de R6. **Lo que se difiere hasta tener evidencia:** M3-M7,
D-M4+. **Lo que queda bloqueado hasta decisión explícita de Capa 9:** D-ADJ, D-REPORT-EXT.

---

## 14 · RESPUESTA DIRECTA A LA RESTRICCIÓN FINAL DE LA REVISIÓN

Los gates (Q-STATE, blacklist, SAFE_MODE) **no son el objetivo — protegen una evaluación que ahora se
construye correctamente desde el origen.** El indicador de éxito deja de ser "cuántas secciones
rechazamos" y pasa a ser el conjunto de §6: precisión de interpretación, precisión de relevancia
(medible objetivamente), fidelidad de cita, cero conclusiones no sustentadas, cero sobreafirmación,
claridad, utilidad, valor añadido, reducción de carga cognitiva — con la seguridad (§6, columna
izquierda) como condición necesaria pero nunca suficiente por sí sola.

---

*CF-6 v2.0. Diseño consolidado, no proyecto paralelo. No implementa el Adjudicator ni el renderer
externo del reporte. R1–R5 son el trabajo autorizado a continuación (ver instrucciones de ejecución
adjuntas).*
