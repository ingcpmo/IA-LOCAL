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
R1_STATUS = CLOSED (2026-08-09, cerrado por Cesar) — bloqueo de gobernanza resuelto (selección determinista en corpus_runner.py), smoke E2E corrido con resultado real negativo (no ancló), cadena completa ensambló. Ver sección R1 "Cierre" y R1.5 "Productización de H2+H4" (siguiente prioridad)
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

### Estado de ejecución del smoke — 2026-08-09: BLOQUEADO (hallazgo de gobernanza, no de código)

Spec aprobada (`docs_plan/R1_SPEC_CONTRATO_ANALIZADOR.md`). Se intentó el
smoke E2E (§ criterio 2) sobre el caso P5 del fixture set (`RW-0005` /
`alcoa_plus_agent` / `ALCOA_CONTEMPORANEOUS` / página 45), vía el mecanismo
real de producción `factory/regulatory/corpus_runner.run_pilot_sample_batch`
— **cero llamadas a Ollama llegaron a hacerse.**

**Secuencia real de lo ocurrido:**

1. Se propuso y confirmó `PILOT_EXECUTION-2026-005`/`-006` (1 llamada,
   alcance acotado a P5), firmada con identidad `Cesar May` tras
   confirmación explícita en chat — mecanismo correcto, igual patrón que
   H1-H4.
2. Al invocar `run_pilot_sample_batch`, `decision_scope_resolver.resolve()`
   rechazó la corrida: **`PILOT_EXECUTION-2026-002`** (Piloto 1 original,
   `human_confirmed`) y **`PILOT_EXECUTION-2026-004`** (autorización de
   H1-H4, `human_confirmed`) están **ambas `ACTIVE`** y **ambas cubren
   `RW-0005`** — el resolver exige una única instancia vigente por
   documento y falló cerrado (`CorpusRunNotAuthorizedError`), sumando mi
   `-006` como tercera capa de la misma ambigüedad.
3. Investigado: `-002` nunca se cerró/superseded cuando `-004` la
   reemplazó. Nadie lo había notado porque los scripts de H1-H4
   (`h1_experiment.py`...`h4_experiment.py`) corrieron **fuera** de
   `corpus_runner` (ad hoc, según sus propios docs en
   `docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md`) — es la **primera vez
   que este resolver se ejerce de verdad** contra el estado real de
   `factory/layer9/decisions/decisions_v2.jsonl`.
4. Se intentó retirar `-005`/`-006` (redundantes, `-004` ya autorizaba
   exactamente esta misma unidad con presupuesto disponible) vía
   `governance_service.abandon()` — **rechazado**: `abandon()` solo opera
   sobre propuestas sin resolver, y `-005` ya había sido resuelta por `-006`
   (`DecisionConflictError`). El almacén es append-only por diseño Part 11;
   no existe una vía de "deshacer" una decisión `human_confirmed`, solo una
   decisión superseding nueva — acto de gobernanza que no le corresponde
   tomar a Capa 8 por su cuenta.
5. Por instrucción explícita de Cesar: no se tocaron `-002` ni `-004`. `-005`
   y `-006` quedan como registros permanentes en `decisions_v2.jsonl` (no
   otorgan nada que `-004` no otorgara ya).

**Resultado:** smoke E2E **no ejecutado**, `max_calls=1` de `-006` sigue
sin consumir, cero llamadas de inferencia realizadas. El criterio de cierre
2 de R1 sigue pendiente.

**Hallazgo de gobernanza (independiente de este roadmap, preexistente):**
`PILOT_EXECUTION-2026-002` debió cerrarse (rechazo/superseding formal)
cuando `-004` la reemplazó como autorización vigente para el trabajo sobre
`RW-0005`/`RW-0011`/`RW-0012`. Mientras seis instancias de `PILOT_EXECUTION`
sigan `ACTIVE` sobre los mismos documentos (`001`-`006`, de las cuales
`002`/`004`/`006` son `human_confirmed`), **cualquier caller real que pase
por `corpus_runner` sobre esos documentos fallará cerrado igual que este
smoke** — no es un problema exclusivo de R1, bloquea también cualquier
futura corrida piloto sobre `RW-0005`/`RW-0011`/`RW-0012` hasta que se
resuelva.

**Pendiente de decisión de Cesar (fuera de esta sesión):** emitir la
decisión superseding que deje una única `PILOT_EXECUTION` vigente sobre
`RW-0005` (candidata natural: conservar `-004`, cerrar `-002` y `-006` con
motivo explícito). Hasta entonces, el smoke de cierre de R1 permanece
`BLOCKED` y R1 no puede declararse cerrado.

### Intento de corrección — 2026-08-09: EMPEORÓ el conflicto, no lo resolvió

Con aprobación explícita de Cesar en chat, se intentó cerrar
`PILOT_EXECUTION-2026-002` vía `governance_service.propose()` +
`confirm()` con `decision_type='CORRECTION'`,
`supersedes_instance_id='PILOT_EXECUTION-2026-002'`, `decision='REJECT'`
(intención: retirar `-002` **sin** otorgar cobertura nueva, ya que
`-004` ya cubre lo mismo). Resultado: `PILOT_EXECUTION-2026-007`
(propuesta) → `PILOT_EXECUTION-2026-008` (confirmación, `Cesar May`,
2026-08-09T03:44:40Z).

**Defecto de comprensión detectado DESPUÉS de firmar, no antes:**
`governance_service.confirm()` escribe **siempre** `decision="APPROVE"`
en el registro de confirmación (`_closing_record(instance_id,
decision="APPROVE", decision_type=None, ...)` —
`factory/services/governance_service.py` líneas ~975-983), sin importar
qué `decision` llevaba la propuesta. El `decision='REJECT'` puesto en
`-007` se descartó silenciosamente al confirmar; `-008` quedó con
`decision=APPROVE`, `decision_type=CORRECTION`, sobre los mismos
`target_ids` que `-002` (`RW-0005`, `RW-0011`, `RW-0012`).

Efecto verificado con `decision_scope_resolver.resolve()` en vivo, antes
y después:

| Documento | Antes | Después de `-008` |
|---|---|---|
| `RW-0005` | `-002`, `-004`, `-006` (3 instancias) | `-004`, `-006`, **`-008`** (3 instancias) |
| `RW-0011` / `RW-0012` | `-002`, `-004` | `-004`, **`-008`** |

`-008` sí cerró `-002` (`status` proyectado pasa a `SUPERSEDED`, vía
`project_status()` — eso funciona como se esperaba), pero al confirmarse
se convirtió él mismo en una **tercera fuente de cobertura activa** sobre
`RW-0005`. El conflicto no se redujo: se movió de `-002` a `-008`. `RW-0011`
y `RW-0012` pasaron de 2 instancias cubridoras a 2 instancias distintas
(mismo conteo, contenido distinto) — sin mejora tampoco ahí.

**Por qué se detuvo ahí:** no se intentó una segunda corrección para cerrar
`-008` (ni se tocó `-006`). Repetir el mismo mecanismo produciría el mismo
resultado (`-00N` reemplazando a `-008` como tercera fuente) — no es un
error de ejecución sino un límite del **modelo de datos**: en este sistema,
`CORRECTION` no tiene una forma de "retirar sin volver a otorgar cobertura
sobre el mismo target_set", porque `confirm()` fuerza `decision=APPROVE`
en toda confirmación. Las dos herramientas que sí retiran sin otorgar
(`reject()` sobre una propuesta sin resolver, o `REVOCATION` sobre un
`target_id` completo) no encajan: `reject()` ya no aplica sobre `-005`
(resuelta por `-006`), y `REVOCATION` retiraría también la cobertura
legítima de `-004` para esos documentos (domina sobre todo el `target_id`,
no sobre una instancia específica).

**`PILOT_EXECUTION-2026-007`/`-008` quedan como registros permanentes**
(append-only, Part 11 — no se pueden borrar ni deshacer). No otorgan nada
que no estuviera ya cubierto por `-004`, pero tampoco reducen la
ambigüedad que bloquea el smoke.

**Hallazgo escalado (además del de arriba):** esto ya no es solo una
decisión de gobernanza pendiente de firma — es una pregunta de **diseño**
sobre `factory/core/decision_scope_resolver.py` /
`factory/services/governance_service.py` /
`factory/regulatory/corpus_runner._check_pilot_execution`: el modelo actual
no tiene un mecanismo limpio para retirar una instancia `human_confirmed`
redundante sin generar una nueva instancia otorgante equivalente. Resolver
esto probablemente requiere una de:
(a) una forma de CORRECTION/SUPERSESSION que pueda confirmarse con
`decision` distinto de `APPROVE` cuando la intención es cerrar sin
reemplazar;
(b) que `_check_pilot_execution` (o el resolver) tolere múltiples
instancias vigentes sobre el mismo documento y elija de forma determinista
(p. ej. la más reciente, o la de mayor `max_calls` restante) en vez de
fallar cerrado por ambigüedad;
(c) una limpieza manual fuera de banda del almacén de decisiones (fuera de
alcance de Capa 8 sin instrucción explícita).

Ninguna se implementa aquí — queda para que Cesar decida el camino. El
smoke de R1 y cualquier corrida sobre `RW-0005`/`RW-0011`/`RW-0012` vía
`corpus_runner` siguen `BLOCKED`.

**Actualización 2026-08-09 (más tarde, misma fecha):** el bloqueo se
resolvió por diseño — ver `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md` y la
implementación real en `factory/regulatory/corpus_runner.py`
(`_select_pilot_execution_instance`, opción (b) de la lista de arriba).
El punto (c) de este hallazgo (limpieza superseding formal de
`PILOT_EXECUTION-2026-002/-007/-008`) sigue sin ejecutarse — ya no es
urgente porque el resolver no se bloquea más por ella, sigue siendo
decisión pendiente de Cesar sin fecha.

### Cierre de R1 — 2026-08-09 (decisión de Cesar)

**R1 = CLOSED.** Cerrado explícitamente por Cesar tras revisar el
resultado real del smoke (chat, 2026-08-09), no por alcanzar un
resultado positivo — el criterio de cierre de R1 nunca fue "el smoke
ancla evidencia", fue "la cadena localización→juicio→informe→cola humana
ensambla y produce artefactos trazables", y eso se cumplió.

Resumen ejecutivo (detalle completo en `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md`
y en la carpeta del smoke, ver R1.5 más abajo):
- Bloqueo de gobernanza resuelto mediante selección determinista
  (`corpus_runner._select_pilot_execution_instance`), sin escribir
  decisiones nuevas — 6 tests nuevos, Gate 0 verde (2244 passed, 4 failed
  pre-existentes y no relacionados — guardas de `git diff HEAD` sobre
  `decisions_v2.jsonl`, ya modificado por las firmas de gobernanza
  aprobadas por Cesar en la sesión anterior).
- Smoke E2E real ejecutado (1 llamada, run_id `chunked-2ef3d38d2538`,
  1660.8s): caso P5 (`ALCOA_CONTEMPORANEOUS` sobre `RW-0005`) resultó
  `sin_evidencia_localizada` — **no ancló**, sin maquillar.
- Causa del resultado negativo: no fue un fallo del smoke ni del
  resolver — fue la confirmación de que la configuración H2+H4 (la única
  que había medido 2/7 de recall en los experimentos, incluido ese mismo
  caso P5) **nunca se incorporó** a `run_pilot_sample_batch`/
  `chunked_engine`, que sigue corriendo la configuración baseline
  (0/7 medido). Ver R1.5 abajo — es la siguiente prioridad, por decisión
  de Cesar.
- Artefactos generados (informe de hallazgos, borrador/sin-cambios,
  trazabilidad, cola de revisión humana): ver R1.5 §"Dónde queda todo
  documentado".

---

## R1.5 — Productización de la configuración H2+H4 (siguiente prioridad, por decisión de Cesar 2026-08-09)

**No estaba en el roadmap original — se agrega aquí porque el cierre de
R1 lo reveló como bloqueante real, más urgente que empezar R2.**

**Por qué es más urgente que R2:** R2 (recuperación determinista) mejora
QUÉ pasajes le llegan al modelo para juzgar, pero la fase de JUICIO en sí
—la llamada real a `chunked_engine`/Ollama— sigue corriendo hoy en la
configuración que midió **0/7** de recall (`W5V2_RECALL_EXPERIMENTS_
RESULTADOS.md`, baseline), no en H2+H4 (**2/7**, la única configuración
que superó el baseline en cualquier experimento). Construir R2 encima del
juicio sin productizar primero heredaría el mismo techo de recall en la
fase de juicio, aunque la recuperación mejore — el smoke de R1 lo
demostró en vivo: P5, el caso que SÍ ancló en H2+H4, no ancló corriendo
por el camino de producción real porque ese camino sigue en baseline.

**Objetivo:** llevar la configuración H2+H4 (1 requirement_id por
llamada + schema de salida mínimo — ver `docs_plan/
W5V2_RECALL_EXPERIMENTS_RESULTADOS.md` §H2/§H4) desde los scripts de
diagnóstico aislados (`h2_experiment.py`/`h4_experiment.py`, scratchpad
de sesión, nunca versionados) a `factory/engines/gmpai_integrity/
chunked_engine.py` / `factory/regulatory/corpus_runner.py`, como
configuración real y por defecto de `run_pilot_sample_batch` (y,
eventualmente, `run_corpus_batch`).

**Componentes reutilizados:** `chunked_engine.evaluate_chunked()` (el
contrato de chunk/checkpoint no cambia, solo el empaquetado
requirement/llamada); `evidence_verifier.py` (validación A sin cambios);
`_PROMPT_PATH_BY_AGENT`/`AGENT_PROMPT_FILES` (catálogo de prompts, mismo
patrón, ahora por requirement_id en vez de por agente completo).

**Componentes nuevos:** modo de empaquetado 1-requirement/llamada dentro
de `evaluate_chunked` (o una función hermana que lo envuelva sin romper
el contrato de llamadores existentes — decisión de diseño detallada,
pendiente); schema de salida mínimo (H4) como variante configurable, no
hardcodeada.

**Tests:** repetir contra el fixture set 7P+2N (`W5V2_RECALL_FIXTURE_SET_
DRAFT.md`) para confirmar que la productización reproduce el 2/7 ya
medido en el script de diagnóstico — antes de tocar nada de R2. Regresión
sobre los llamadores existentes de `evaluate_chunked` (no deben cambiar
de comportamiento si no piden explícitamente el modo H2+H4).

**Criterio de aceptación MEDIBLE:** `run_pilot_sample_batch` sobre el
mismo caso P5 (RW-0005/alcoa_plus_agent/ALCOA_CONTEMPORANEOUS/p.45), con
la configuración productizada, ancla la cita — reproduce en producción lo
que hoy solo existe en un script de diagnóstico.

**Riesgos:** cambiar el empaquetado de llamadas cambia el fingerprint del
prompt/schema — invalida cachés de checkpoints previos por diseño (mismo
principio que cualquier cambio de `prompt_version`/schema documentado en
`W5V2_REMEDIACION_RECALL_MODELO.md` §4.3); recalcular D4-A con el nuevo
ritmo de llamadas (más llamadas, cada una más corta — H2 midió 60 min
para 9 fixtures vs ~2h10m del baseline).

**Dependencias:** ninguna sobre R2 — al contrario, R2 depende de esto.

**Firma Cesar:** aprueba la productización y el nuevo resultado del
smoke (reintento de R1 con la config productizada, opcional, para cerrar
el ciclo con un resultado positivo real).

### Impacto en D4-A (nota, no ejecutado — 2026-08-09)

El perfil `H2H4` cambia el ritmo de llamadas frente al baseline: más
llamadas (1 por requirement_id en vez de 1 por agente completo), cada una
más corta. Medido en los experimentos: H2 tomó 60 min para 9 fixtures
(~6.7 min/llamada) vs. ~2h10m del baseline (9 fixtures) para el mismo
lote — y H4 sobre H2 fue 2.4x más rápido aún (24.6 min/9 fixtures). **Sin
recalcular ni proponer nada aquí**: cuando se retome cualquier corrida
presupuestada (`D4-2026-004`, propuesta sin confirmar — ver sección
"Reenfoque..." en `project_w5_v2_regulatory_redesign.md`), `compute_d4a()`
debe recalcularse con el ritmo real medido del perfil `H2H4` en el
Bloque 3 (la validación por flujo real de R1.5), no con el ritmo del
baseline que sostiene `D4-2026-003`/`D4-2026-004` actuales. Queda como
nota para no perder de vista, no como acción de esta corrida.

### Dónde queda todo documentado (para descarga/análisis)

| Qué | Ruta |
|---|---|
| Este roadmap (estado, cierre de R1, R1.5) | `docs_plan/ROADMAP_ANALIZADOR_GMP.md` (este archivo) |
| Instrucciones de la corrida que resolvió el bloqueo y corrió el smoke (referenciada, **no respaldada en disco todavía** — deuda de documentación, ver `project_w5_v2_regulatory_redesign.md` sección "Reenfoque...") | `docs_plan/ARQ_RESOLVER_BLOQUEO_R1.md` |
| Instrucciones de la productización de H2+H4 (R1.5) — **sí guardada** | `docs_plan/R1_5_PRODUCTIZACION_H2H4.md` |
| Spec del contrato de R1 (aprobada) | `docs_plan/R1_SPEC_CONTRATO_ANALIZADOR.md` |
| Código real de la selección determinista | `factory/regulatory/corpus_runner.py` (`_select_pilot_execution_instance`, `_pilot_execution_budget`) |
| Código real de `evaluation_profile` (R1.5) | `factory/engines/gmpai_integrity/chunked_engine.py` (`evaluate_chunked`, `build_run_fingerprint`), `factory/regulatory/corpus_runner.py` (`run_pilot_sample_batch`) |
| Tests de la selección determinista | `factory/tests/test_pilot_execution_selection.py` |
| Tests de `evaluation_profile` | `factory/tests/test_evaluation_profile_h2h4.py` |
| Skill operativo del pipeline de recall | `.claude/skills/gmp-recall-pipeline/SKILL.md` |
| Resultados de los experimentos H1-H4 (base de R1.5) | `docs_plan/W5V2_RECALL_EXPERIMENTS_RESULTADOS.md` |
| Plan de remediación de recall (ON_HOLD, contiene H5/H6/H7 diferidos) | `docs_plan/W5V2_REMEDIACION_RECALL_MODELO.md` |
| **Artefactos reales del smoke de R1** (informe de hallazgos, borrador/sin-cambios, trazabilidad, checkpoint/manifest/raw_response) | `factory/regulatory/pilot_run/r1_smoke_chunked-2ef3d38d2538/` |
| Empaquetado descargable de la carpeta anterior | `/tmp/claude-1001/-home-ing-cpmo/549de419-b424-4cee-b5f2-9b8f3895a865/scratchpad/r1_smoke_chunked-2ef3d38d2538.tar.gz` |
| Entrada en cola de revisión humana | `factory/layer9/review_queue.jsonl`, rc_id `r1-smoke-chunked-2ef3d38d2538` |
| Evento de auditoría de la corrida | `factory/audit/factory_audit.jsonl`, entry_id `80796d46-223b-42c9-992b-355616c03bcd` |

---

## R1.5 — CLOSED (decisión de Cesar, 2026-08-09)

La productización de `evaluation_profile=H2H4` funciona y quedó probada
(10/10 tests, plumbing correcto por flujo real, P5 ancló de verdad con
cita verificada a score 1.0 vía `evidence_verifier.match_citation`).
Commiteado en `484d103`. El hallazgo de que el checkpoint final igual
reportaba `not_observed_in_chunk` pese al anclaje genuino se separa como
R1.6 (abajo) — no era un defecto de la productización.

## R1.6 — Defecto de validador de relevancia (mismatch de idioma) — investigado y PARCIALMENTE corregido, sin cerrar (2026-08-09)

Instrucciones completas: `docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md`.
R2 permanece **EN ESPERA** — no arranca hasta que R1.6 cierre (P5 llegue a
`observed` de punta a punta con los negativos intactos).

**Defecto confirmado**: `chunked_engine._is_topically_relevant()`
(línea ~595) es un pre-filtro propio de esta pieza, distinto y más crudo
que la validación C real y ya probada del sistema
(`semantic_evidence_verification.verify_semantic_relevance()` /
`detect_reference_list_context()` + `evidence_verifier.relevance_score()`,
que SÍ es language-agnostic vía `requirement_terms.yaml` y degrada a
`review_required` en vez de rechazar duro). El pre-filtro compara palabras
significativas del `label` del checkpoint contra la cita — y varios
labels (familia ALCOA, `alcoa_prompts.yaml`) siguen el patrón bilingüe
"Término inglés — glosa en español" (ej. `"Contemporaneous — registrado
en el momento"`). El código original hacía `label.split("—", 1)[-1]`,
quedándose SOLO con la glosa en español y descartando el término inglés
que ya estaba en el propio label gobernado.

**Alcance del defecto (verificado, no puntual de P5)**: de los 20
checkpoints reales (`part11`+`annex11`+`alcoa`+`cgmp211`), 9 (familia
ALCOA) usan el patrón bilingüe con guion largo; los 11 restantes tienen
label puramente en español, sin ningún término inglés embebido en
absoluto. Los 14 documentos de la allowlist Rockwell son ingleses. Es
decir: el pre-filtro nunca podía aceptar una cita genuina en inglés para
NINGUNO de los 20 checkpoints salvo que la cita repitiera, letra por
letra, la glosa en español — estructuralmente casi imposible contra
prosa técnica en inglés.

**Corrección aplicada (segura, acotada, ver
`R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md` sección 3 para el análisis
completo de por qué NO es una relajación)**: se dejan de descartar las
palabras en inglés de un label bilingüe — se usan ambas mitades. Cero
fuentes de comparación nuevas (se evaluó agregar `requirement_terms.yaml`
como fuente alternativa y se descartó: rompe
`test_topically_irrelevant_citation_is_rejected`, un caso real y
monolingüe de cita anclada pero fuera de tema que debe seguir
rechazado). Tests nuevos: `factory/tests/test_r1_6_topically_relevant_language.py`
(7 tests, incluida N1/ANNEX11_4 con datos reales y la cita real
persistida de P5). Suite completa + Gate 0 sin fallos atribuibles al
cambio (los únicos fallos son el mismo patrón ya conocido de
`chunked_engine.py`/`decisions_v2.jsonl` sin commitear, que desaparece al
commitear).

**P5 NO llega a `observed` incluso después de este fix — verificado
explícitamente, no maquillado**: la evidencia real que citó el modelo
para P5 (persistida en
`factory/regulatory/pilot_run/r1_5_h2h4_chunked-596f70cc4520/`) no repite
NINGUNA palabra gobernada, ni en inglés ("Contemporaneous", ahora
disponible tras el fix) ni en español ("registrado"/"momento"). El
defecto de idioma era real y se corrigió, pero no es la única causa: la
heurística de coincidencia léxica LITERAL es, en sí misma, demasiado
estricta para validar un `cumple_parcialmente` que el modelo infiere de
forma parafraseada — el mismo patrón que el sistema ya resuelve en otro
lugar (`verify_llm_output` V5) degradando a `review_required` en vez de
rechazar duro, pero que el pre-filtro de `chunked_engine.py` nunca
adoptó. Corregir esto de raíz (mover el pre-filtro de rechazo-duro a
señal-suave, reutilizando `verify_semantic_relevance`) es un cambio de
diseño más grande, no autorizado en el alcance de esta corrida —
**decisión nueva pendiente de Cesar**.

**Estado**: R1.6 investigado, con una corrección real y segura aplicada.
El rediseño mayor queda como R1.7 (abajo) — R1.6 en sí no cierra
independientemente, se resuelve junto con R1.7.

## R1.7 — Rediseño del pre-filtro de relevancia del pipeline verificado (autorizado por Cesar, 2026-08-09)

Plan completo: `.claude/plans/sharded-riding-turing.md`. Cesar autorizó
el rediseño mayor que R1.6 dejó pendiente: convertir el pre-filtro de
rechazo-duro (`_is_topically_relevant`) en señal-suave para el pipeline
VERIFICADO (el que usa `corpus_runner`/producción), reutilizando
maquinaria ya probada del sistema en vez de inventar lógica nueva.

**Diseño aplicado**: el pipeline verificado deja de usar
`_is_topically_relevant` (queda intacto para el pipeline legacy, que no
tiene consumidor downstream capaz de manejar una señal suave). En su
lugar usa solo `semantic_evidence_verification.detect_reference_list_context()`
(el único componente determinista y ya probado de la validación C real,
golden dataset case 1) como rechazo duro adicional al anclaje literal.
La relevancia léxica deja de bloquear antes de tiempo y fluye tal cual a
`evidence_verifier.verify_llm_output()` (V5, sin tocar ningún umbral),
que ya la traduce a `status='review_required'` cuando es débil —
`absence_consolidator.py` ya sabe tratar eso de forma segura
(`SUPPORTING_EVIDENCE_UNDER_REVIEW`, nunca promovido a una conclusión
positiva confirmada como `DOCUMENTED_AND_SUPPORTED`).

**Verificado con datos reales, sin gastar ninguna llamada nueva al
modelo (replay offline de la respuesta ya persistida de P5,
`chunked-596f70cc4520`)**:
- **P5**: `chunks_observed` pasa de 0 a **1**. `conclusion =
  "SUPPORTING_EVIDENCE_UNDER_REVIEW"` (nunca `DOCUMENTED_AND_SUPPORTED`
  ni `PROVISIONALLY_DOCUMENTED` — la relevancia léxica es débil, queda
  flageada para revisión humana, no aprobada en silencio).
  `review_flags` incluye `OBSERVED_ONLY_UNVERIFIED`. Esto es lo que "P5
  llega a observed" significa en la práctica: visible y trazable, con
  bandera de revisión humana explícita — consistente con "sin
  declaración de cumplimiento final" (`CLAUDE.md`).
- **ANNEX11_4** (negativo real, GAMP5 en lista de referencias), por el
  pipeline verificado (no solo el golden dataset sintético):
  `chunks_observed = 0`, nunca ninguna conclusión positiva. Mismo
  resultado de siempre, ahora por el mecanismo estructural correcto.
- **Caso construido de control** (cita real, ancla, pero de otro tema,
  mismo idioma — equivalente verificado de
  `test_topically_irrelevant_citation_is_rejected`): tampoco se vuelve
  `verified` silenciosamente — cae en el mismo
  `SUPPORTING_EVIDENCE_UNDER_REVIEW` que P5 (misma naturaleza de señal
  débil), nunca una conclusión positiva confirmada.

Tests nuevos: `factory/tests/test_r1_7_soft_relevance_verified_pipeline.py`
(3 tests, incluido el replay real de P5). Regresión dirigida (129 tests:
`test_gmpai_chunked_engine.py`, `test_r1_6_*`, `test_verified_pipeline.py`,
`test_evaluation_profile_h2h4.py`, `test_pilot_execution_selection.py`,
golden dataset, `test_corpus_runner.py`) verde. Suite completa +
Gate 0: ver resultado en el checkpoint de cierre de esta corrida.

**Alcance**: solo el pipeline verificado. `RELEVANCE_THRESHOLD` (0.15)
sin tocar. Validaciones A/B/D sin tocar. `evidence_min_criteria` sin
tocar.

**Estado**: **CLOSED** (commit `761d875`, 2026-08-09). P5 confirmado
`SUPPORTING_EVIDENCE_UNDER_REVIEW` (chunks_observed=1, nunca aprobación
silenciosa), ANNEX11_4 confirmado rechazado (chunks_observed=0) por el
mecanismo estructural correcto, N2 (segundo negativo, tabla de
contenidos) confirmado sin llegar a conclusión positiva en el escenario
realista — ver R1.8 para el hallazgo adversarial relacionado (gap
preexistente de D, no de R1.6/R1.7).

## R1.8 — Despacho de SUPPORTING_EVIDENCE_UNDER_REVIEW a revisión humana (2026-08-09)

Hallazgo abierto que R1.7 dejó documentado: la conclusión quedaba en
`result["verified_conclusions"]` como campo consultable, pero nada la
despachaba activamente a un humano — un fallo silencioso de nueva especie
(la evidencia no se pierde, pero muere en un campo que nadie mira).

**Diseño e implementación**: `chunked_engine.evaluate_chunked()` encola
toda conclusión `SUPPORTING_EVIDENCE_UNDER_REVIEW` en la cola de revisión
humana YA EXISTENTE (`factory/layer9/human_review_queue.py`,
`review_queue.jsonl`) — función nueva `enqueue_finding_for_review()`,
mismo almacén append-only, mismo locking, mismo patrón de evento de
auditoría que ya usan los Release Candidates (`enqueue()`). Item
sintético (`finding-{run_id}-{requirement_id}`) distinguido con
`entry_type="finding_review"` para no mezclarse con RCs reales. El
encolado ocurre en el camino de escritura del run (dentro de
`evaluate_chunked()`, no en un GET), y un fallo de encolado nunca tumba
el run — se registra en `governed_exceptions`, nunca se traga en
silencio. Nunca cambia la conclusión ni la promueve.

**Alcance deliberadamente acotado**: solo `SUPPORTING_EVIDENCE_UNDER_REVIEW`
(siempre trae evidencia observada real, flag `OBSERVED_ONLY_UNVERIFIED`).
`EVALUATION_INCOMPLETE` queda fuera — cubre motivos heterogéneos (D no
evaluado, requisito duplicado, excepción de consolidación) que no
siempre implican evidencia esperando revisión, y ya tienen su propio
registro en `governed_exceptions`.

**Aislamiento de test agregado** (hallazgo colateral real, necesario
para no romper gobernanza): se descubrió que `evaluate_chunked()` YA
escribía al audit log real (`factory/audit/factory_audit.jsonl`, 36k+
líneas) en CUALQUIER test de la suite que lo ejercitara, sin aislar —
preexistente, no introducido por R1.6/R1.7/R1.8, fuera de este alcance
para corregir en el audit log, pero se evitó repetir el mismo problema
con la cola de revisión: `factory/tests/conftest.py` gana un fixture
`autouse=True` (`isolated_review_queue`) que redirige
`REVIEW_QUEUE_FILE` a un temporal para TODA la suite.

Tests nuevos: `factory/tests/test_r1_8_review_queue_dispatch.py` (3
tests: P5 real genera exactamente una entrada con todos los campos;
ANNEX11_4 no genera ninguna; el caso wrong-topic también se despacha).
Test N2 agregado a `test_r1_7_soft_relevance_verified_pipeline.py`
(escenario realista, sin `criterion_assessments` — seguro, confirmado).

**Hallazgo adversarial encontrado, preexistente, NO introducido ni
corregido por esta corrida (fuera de alcance — territorio del validador
D)**: si el modelo alucinara `criterion_assessments` consistentes (todos
`MET`, citando la misma línea de tabla de contenidos como
`evidence_quote` para los 9 criterios), la conclusión llegaría a
`PROVISIONALLY_DOCUMENTED` — un falso positivo real. Confirmado que este
gap ya existía ANTES de R1.6/R1.7 (el label "Audit trail seguro con
timestamp" ya contenía "audit"/"trail" literalmente, así que incluso
`_is_topically_relevant` original habría dejado pasar esta cita). No es
un escenario observado empíricamente (el P5 real SÍ auto-reportó
`NOT_MET`/`NOT_ASSESSABLE` cuando la evidencia era débil) — es un límite
teórico del contrato de `criterion_assessments`/`verify_sufficiency` que
no verifica si `evidence_quote` se repite idéntico entre criterios
distintos. Registrado como hallazgo abierto, dueño: futura corrida sobre
`semantic_evidence_verification.verify_sufficiency`, requiere su propia
autorización.

**Estado**: **COMMITEADO** (commit `bc1d8b0`, 2026-08-09). Tests verdes,
sin fallos atribuibles.

---

## R2 — Localización de evidencia por recuperación determinista (la apuesta)

**PREPARACIÓN EN CURSO (2026-08-09)**: diseño detallado completo en
`docs_plan/R2_DESIGN_DETALLADO.md` — módulo
`factory/regulatory/retrieval/` (indexer/query_builder/retriever),
reutiliza `chunked_engine.build_page_chunks()` (no el chunking de
`knowledge/retriever.py`, que pierde el número de página), query
construida desde `citation_text`+`evidence_min_criteria`+
`requirement_terms.yaml` (nunca `weak_keywords` solas), métrica de
recuperación pura (cero LLM) contra el fixture 7P+2N. **NO implementado
todavía** — pendiente de que Cesar decida sobre la dependencia nueva
(`chromadb` en `factory/`, o alternativa TF-IDF/BM25 sin dependencia
nueva) antes de autorizar la implementación real. La fase de JUICIO (LLM
sobre los top-k) sigue bloqueada sin `PILOT_EXECUTION` nueva firmada.

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

**Dependencias:** R1 cerrado (contrato del producto define qué
`requirement_id`s entran en el smoke de R2) **y R1.5 productizado**
(agregado 2026-08-09 — sin H2+H4 en producción, R2 mediría recuperación
sobre un juicio que todavía usa la configuración baseline de 0/7, no la
de 2/7 que motivó la apuesta de R2).

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
