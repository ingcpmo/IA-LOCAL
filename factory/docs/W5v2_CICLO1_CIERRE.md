# W5 Ciclo 1 (v2) — Informe de cierre

Fecha: 2026-07-17. Ejecutor: Claude Code (Capa 8), bajo autorización de
Capa 9 (Cesar). Sustituye a `W5_CICLO1_ENDURECIMIENTO_DETERMINISTA.md` v1.

**Estado al cierre: código completo, tests en verde, evidencia real
capturada. Comiteado en un único commit (`feat(w5): add fail-closed
regulatory validation pipeline`) tras verificación pre-commit explícita.**

## Estado final registrado (machine-readable, ver también `STATUS.json`)

```
W5_VALIDATION            = PARTIAL       # Bloque 4.3: 2/29 chunks, 3/19 requisitos, un solo documento
PRODUCTION_ENABLEMENT    = BLOCKED       # generate_controlled() rechaza run_context != 'validation'; prompts YAML de produccion no reescritos
regulatory_approval      = pending       # aprobacion QA/regulatoria para HABILITAR PRODUCCION -- distinta de la aprobacion de gobernanza de la matriz (Checkpoint B, MC-0001, SI human_confirmed)
chain_continuity         = WARN          # fork de auditoria preexistente desde 2026-06-15, sin cambios, hash_errors=0
C1                       = complete=true,  regresion PASS (review_required + RELEVANCE_REVIEW_REQUIRED)
C3                       = complete=true,  regresion PASS (review_required + RELEVANCE_REVIEW_REQUIRED)
C2                       = complete=false  (llm_output_original no recuperable del motor v1)
C4                       = complete=false  (llm_output_original no recuperable del motor v1)
```

**Nota importante sobre `regulatory_approval` vs. la aprobación de la
matriz**: son dos gates distintos. Cesar aprobó la **matriz de
aplicabilidad en sí** (`applicability_matrix.yaml.approval.status =
human_confirmed`, `decision_id MC-0001`, Checkpoint B) — eso gobierna qué
valores son válidos dentro de la matriz. `regulatory_approval=pending`
aquí se refiere a un gate SEPARADO y aún no otorgado: la autorización para
**habilitar el pipeline v2 completo en producción** (lo que requeriría,
como mínimo, reescribir los prompts YAML de producción — ver
recomendación #1 más abajo). `PRODUCTION_ENABLEMENT=BLOCKED` es la
consecuencia técnica de que ese segundo gate siga pendiente:
`generate_controlled()` rechaza explícitamente cualquier
`run_context` distinto de `'validation'` (ver
`factory/tests/test_w5v2_governance_gates.py`), sin importar el estado de
la matriz.

## Resumen ejecutivo

Los 4 defectos regulatorios reales que motivaron este ciclo (C1-C4:
contradicciones internas falsas detectadas en FS_v1.2, resueltas por
decisión humana `ff640643`) tenían una causa raíz estructural: el motor
v1 no distinguía observación de conclusión, ni relevancia temática de
anclaje literal. El pipeline v2 (Fases 1-3) corrige esa causa raíz de
forma general, no solo para estos 4 casos — confirmado con evidencia real
(Bloque 4.3, inferencia real contra Ollama) y con regresión determinista
sobre los 2 casos reconstruibles desde registros reales (C1, C3 — Bloque
4.4): **ambos pasan de "hallazgo verificado limpio" (el defecto original)
a `review_required` + `RELEVANCE_REVIEW_REQUIRED`**, sin necesidad de que
un humano detecte la contradicción manualmente después del hecho.

## Cambios por fase

### Fase 0 — Inventario (solo lectura)
Confirmó el sistema objetivo real: `factory/engines/gmpai_integrity/`
dentro de `factory-api` (puerto 9000), no 8101/8102. Documentó 6
discrepancias reales entre el plan y el código vigente — la más relevante:
el LLM v1 emite `estado` (conclusión) directamente a nivel de chunk, no
una observación pura. `jsonschema` no estaba instalado en ningún entorno.

### Fase 1 — Schemas en dos capas + ejecución controlada
`finding_llm_v1.json` (contrato estricto del LLM, sin conclusiones de
ausencia ni `no_aplica`) + `finding_record_v1.json` (sobre del pipeline).
`schema_loader.py` fail-closed. `generate_controlled()` aditivo en
`ollama_client.py` — no reemplazó `generate()` (usada por el motor v1 en
producción).

### Fase 2 — Verificador v2 + consolidador de ausencias
`evidence_verifier.py`: checks ternarios, taxonomía de cita
exact/normalized/fuzzy≥0.93/not_found, relevancia temática heurística
(flag, nunca auto-rechazo). `absence_consolidator.py`:
`DOCUMENTATION_GAP` solo si TODOS los chunks relevantes son
`not_observed_in_chunk` Y la matriz marca `expected`. `verified_pipeline.py`
orquesta ambos + `generate_controlled`, con `generate_fn` inyectable.

### Fase 3 — Matriz de aplicabilidad v2
19 requisitos × 9 tipos documentales, `default=review_required`
obligatorio (validado al cargar). `pre_inference_filter()` corta la
inferencia antes de gastar una llamada a Ollama para
`out_of_document_scope`/`review_required`. Guardia de tipo documental
(`document_type_guard`): clasificación dudosa propaga
`DOCUMENT_TYPE_UNCONFIRMED` a todo el documento.

**Checkpoint B**: Cesar aprobó la matriz completa (`decision_id MC-0001`,
`approved_by Cesar`, `approver_role project_lead`, registrado en
`factory/layer9/decisions/decisions.jsonl`). `approval.status` →
`human_confirmed`.

### Fase 4 — Cierre: contexto de auditoría, evidencia real, Golden Dataset

**Bloque 4.1**: `run_context` (`production` default | `validation`) en el
evento auditado de `evaluate_chunked()` (`chunked_engine.py`). Filtro
`?context=` en `GET /missions/{project_id}/audit` (read-only, confirmado
sin escrituras — ver Bloque 4.2). Nuevo `event_type` registrado en
`audit_writer.VALID_EVENTS`: `w5v2_validation_evidence_run` (el enum de
eventos es fail-closed por diseño — un tipo no registrado lanza
`ValueError`, comportamiento correcto que detectó la necesidad de este
registro durante el propio Bloque 4.3).

**Bloque 4.3**: ejecución de evidencia real — ver métricas abajo.

**Bloque 4.4**: Golden Dataset con C1-C4 reales — ver resultado abajo.

## Bloque 4.3 — Métricas de la ejecución de evidencia real

Ejecutado contra Ollama REAL (`qwen2.5:7b-instruct-q4_K_M`,
`model_digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`,
`ollama_version 0.21.2`), documento real (`215115305 SCADA-PCS Misc PLC
System FS_v1.2.pdf`, 58 páginas, 29 chunks reales vía
`build_page_chunks()`). `run_id
w5v2-validation-e7c251ef7fc0`, `run_context=validation`,
`run_by="Cesar (autorizado via instrucción explícita de ejecutar Fase 4,
sesión 2026-07-17)"`. Script y resultado completo persistidos en
`factory/docs/gmpai_reanalysis/w5v2_evidence/`.

**Cobertura: `partial`** — 2/29 chunks reales, 3 de los 19 requisitos
(`21_CFR_11.10(d)`, `ANNEX11_9`, `ALCOA_ATTRIBUTABLE`), declarado
explícitamente (no se presenta como cobertura completa).

| Métrica | Valor |
|---|---|
| Registros totales | 6 (3 requisitos × 2 chunks) |
| `verified` | 3 |
| `verified_with_deviation` | 0 |
| `review_required` | 0 |
| `rejected_by_verifier` | 3 |
| `manifest_incomplete` | 0/6 (0.0%) — `model_digest` obtenido en todas las llamadas |
| Llamadas a Ollama evitadas por el filtro de aplicabilidad | 1 (`21_CFR_11.10(d)` × `IQ` → `OUT_OF_DOCUMENT_SCOPE`, demostrado sin inferencia) |
| Eventos de auditoría nuevos | Exactamente 1, `event_type=w5v2_validation_evidence_run`, `data.run_context=validation` (verificado: `?context=production` NO lo incluye, `?context=validation` sí) |

**Conclusiones documento-nivel (parciales, coherentes con `coverage=partial`)**:
- `21_CFR_11.10(d)`: `DOCUMENTATION_GAP` (2/2 chunks `not_observed_in_chunk`
  reales, `applicability=expected` para FS) — consistente con el
  requisito real: ninguno de los 2 primeros chunks (páginas 1-4
  aproximadamente) trata control de acceso.
- `ANNEX11_9`: **`EVALUATION_INCOMPLETE` + `NO_VALID_RECORDS`** — los 2
  registros de este requisito fueron `rejected_by_verifier`
  (`schema_validation_failed` en uno; **`page_out_of_range` en el otro: el
  modelo citó "F12.00: Audit Trail" real pero declaró `evidence_page=45`
  cuando el chunk real cubre páginas 1-3** — un hallazgo real de que el
  check de página V2 funciona: atrapó una cita de página incoherente en
  vivo, contra un modelo real, no en un mock).
- `ALCOA_ATTRIBUTABLE`: `DOCUMENTATION_GAP` (1 registro válido
  `not_observed_in_chunk`; el otro `rejected_by_verifier` por
  `schema_validation_failed`).

**Hallazgo no anticipado real**: 3/6 registros (50%) fueron
`rejected_by_verifier` en esta muestra pequeña — 1 por respuesta que no
cumplió `finding_llm_v1` (el modelo no siempre respeta el `format` JSON
Schema con este tamaño de modelo/documento) y 1 por página fuera de rango
(alucinación de página). Con `coverage=partial` (n=6) esta tasa NO debe
generalizarse como la tasa de rechazo esperada en producción — se declara
como limitación, no como conclusión (ver sección de limitaciones).

## Bloque 4.4 — Resultado de la regresión Golden Dataset

`factory/eval/golden_dataset/cases/{C1,C2,C3,C4}.json` +
`factory/tests/test_golden_regression.py` (5 tests, todos en Gate 0):

| Caso | `complete` | Resultado |
|---|---|---|
| **C1** (`21_CFR_11.10(d)`, cita real trasladada de audit trail) | `true` | **`verified` → `review_required` + `RELEVANCE_REVIEW_REQUIRED`** (confirmado, `test_golden_case_matches_expected_v2_behavior[C1]` PASS) |
| **C3** (`ANNEX11_12`, cita real trasladada de consistencia UTC) | `true` | **`verified` → `review_required` + `RELEVANCE_REVIEW_REQUIRED`** (confirmado, PASS) |
| C2 (`ANNEX11_7.1`, diferencia de alcance) | `false` | No ejecutable — `llm_output_original` por-chunk no recuperable de los registros persistidos (`chunked_engine.py` excluye `_by_req_candidates` del JSON de salida por diseño) |
| C4 (`ALCOA_AVAILABLE`, diferencia de alcance) | `false` | Mismo motivo que C2 |

**Demostración explícita del Checkpoint C** (cita real, ANCLADA
literalmente — confirmado con `match_citation()` sobre el texto real
extraído del PDF — pero temáticamente irrelevante al requisito):
- C1: la cita real "UR5.2.3 [URS-PCS-SR-009] Logins, logouts, and login
  attempts must be recorded in the Audit Trail." (pág 46-47, real, de
  `changelog_FS_v1_2_v3.json`) fue aceptada en v1 como evidencia de
  `21_CFR_11.10(d)` (control de acceso). En v2: `match_citation()` la
  reconoce como `exact` (SÍ está en el chunk, no es una alucinación) pero
  `relevance_score` contra los términos de control de acceso es
  insuficiente → `review_required`, nunca `verified` limpio.
- C3: la cita real "The alarm and events service saves all alarms and
  events in Universal Coordinated Time (UTC)..." (pág 20-21, real) fue
  aceptada en v1 como evidencia de `ANNEX11_12` (seguridad física/lógica).
  En v2: mismo patrón — `exact` pero irrelevante → `review_required`.

## Adaptaciones respecto al plan (justificadas)

1. **P3 tiene alcance mayor al descrito**: aplicar la separación
   observación/conclusión requeriría reescribir los prompts YAML de
   producción (piden `estado` directo). No se hizo — fuera de alcance de
   este ciclo, `generate_controlled()` queda como capa aditiva no cableada.
2. **Bloque 1.5 (`format` como JSON Schema completo)**: implementado
   literalmente y confirmado funcional contra Ollama real (`format` acepta
   un objeto JSON Schema en Ollama ≥0.5; confirmado versión real 0.21.2).
3. **Bloque 4.3, chunk field name**: `source_text` (plan) → `text` (campo
   real de `build_page_chunks()`), documentado desde Fase 0.
4. **Bloque 4.3, "POST de ejecución"**: no existe un POST HTTP que dispare
   `evaluate_chunked()` en producción (se invoca vía script ad-hoc,
   confirmado en Fase 0) — `run_context` se añadió directamente a la
   función y a su evento de auditoría, punto de verdad real de la
   ejecución, en vez de a un endpoint que no existe.
5. **Conectividad Ollama**: `FACTORY_OLLAMA_BASE_URL` no está seteada en
   el contenedor `factory-api` (default `localhost:11434`, incorrecto
   dentro del contenedor). Se confirmó que `http://host.docker.internal:11434`
   SÍ es alcanzable (mismo Ollama real, mismos 3 modelos) — usado como
   override de proceso para el script de evidencia (variable de entorno
   de ESE proceso únicamente), sin tocar `docker-compose` ni la
   configuración persistente del contenedor.
6. **`w5v2_validation_evidence_run` no estaba en `VALID_EVENTS`**: el
   primer intento de escribir el evento de auditoría falló (fail-closed,
   comportamiento correcto del sistema existente) — se registró el nuevo
   `event_type` en `audit_writer.py` antes de reintentar la escritura
   (sin re-ejecutar la inferencia real, ya capturada).
7. **Bloque 4.2, "169 tests previos"**: el número literal del plan no
   coincide con el baseline real de este repo (490 antes de Fase 1, 558
   antes de Fase 4, 563 al cierre) — se interpreta el criterio como "todos
   los tests previos + todos los nuevos en verde", cumplido.

## Limitaciones declaradas

- **Cobertura de chunks en Bloque 4.3**: 2/29 (7%) de un solo documento,
  3/19 requisitos. Suficiente para demostrar el mecanismo end-to-end
  (schema-gate real, verificador real, consolidador real, filtro de
  aplicabilidad real, auditoría real), **insuficiente para estimar tasas
  de rechazo/verificación esperadas en producción**.
- **% de `MANIFEST_INCOMPLETE`**: 0% en esta muestra (n=6) — no
  representativo; en producción, `model_digest` puede fallar si Ollama no
  está alcanzable (ver histórico TE-02).
- **Casos Golden incompletos**: C2 y C4 (50% del dataset) no son
  ejecutables como regresión determinista — el dato de origen
  (`llm_output_original` por chunk) no está recuperable de los registros
  persistidos del motor v1. Esto es una limitación DEL MOTOR v1 (nunca
  persistió `_by_req_candidates`), no de este ciclo.
- **Tasa de rechazo real observada (50%, n=6) no debe generalizarse.**
- **Prompts de producción no reescritos**: el pipeline v2 completo
  (schema-gate + verificador + consolidador + matriz) no está cableado en
  el flujo real de `evaluate_chunked()`. Esta decisión se mantiene
  deliberadamente desde Fase 1 (ver adaptación #1).
- **Conectividad Ollama vía `host.docker.internal`** no está en
  `FACTORY_OLLAMA_BASE_URL` del contenedor de forma persistente — cada
  ejecución de evidencia futura necesita el mismo override manual hasta
  que se decida (fuera de alcance de este ciclo) si conviene fijarlo en
  la configuración del contenedor.

## Recomendaciones para W5.3

1. Decidir si se reescriben los prompts YAML de producción para pedir
   `chunk_observation` en vez de `estado` — es el paso que realmente
   activaría P3 en producción. Sin esto, el pipeline v2 sigue siendo una
   capa de validación paralela, no el camino real de análisis.
2. Ejecutar una muestra de evidencia mayor (ej. los 19 requisitos × los
   29 chunks reales de FS_v1.2 completos) para obtener una tasa de
   rechazo/verificación estadísticamente representativa antes de decidir
   umbrales de producción.
3. Resolver la persistencia de `_by_req_candidates` en el motor (aunque
   sea solo para runs `run_context=validation`) para que futuros Golden
   Dataset cases no queden `complete: false` por diseño.
4. Persistir `FACTORY_OLLAMA_BASE_URL=http://host.docker.internal:11434`
   en la configuración del contenedor `factory-api` si se decide que
   ejecuciones de validación recurrentes son parte del flujo de trabajo
   (fuera de alcance de este ciclo — cambio de configuración de
   contenedor, requiere autorización explícita).
5. Ingesta real de las fuentes `PENDING_DOCUMENT` (FDA OOS/DI, USP, ICH,
   GAMP5) antes de ampliar la matriz de aplicabilidad más allá de los 19
   requisitos actuales.
