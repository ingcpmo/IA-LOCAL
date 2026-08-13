# R4-T1 — Plan por fases (DISEÑO, sin ejecutar)

Preparado en cumplimiento del Bloque 5 de
`docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md` ("preparar R4-T1,
diseño, sin ejecutar — NO iniciar R4 en esta corrida"). Este documento
es un plan, no una autorización — ninguna fase arranca sin que Cesar lo
apruebe explícitamente, fase por fase.

**Objetivo de R4-T1**: producir un **borrador corregido controlado**
(`CANDIDATE_DRAFT` + `REDLINE` + `REPORT` + `MANIFEST`) para un documento,
basado ÚNICAMENTE en hallazgos con decisión humana confirmada — nunca el
documento original se toca, nunca hay aprobación automática, nunca se
libera nada (`PRODUCTION_ENABLEMENT` sigue `BLOCKED`).

## 0. Lo que YA EXISTE — no reinventar (leído antes de diseñar, regla de oro)

Antes de diseñar una sola línea nueva se auditó el código real:

- **`factory/services/remediation_package_service.py`** (656 líneas):
  máquina de estados completa y REAL, no un stub —
  `create_package()` → `AWAITING_HUMAN_EXCEPTION_REVIEW`/
  `AWAITING_PACKAGE_DECISION` → `record_exception_review()` (solo
  `HIGH_RISK`) → `record_medium_risk_batch_decision()` →
  `record_package_decision()` (`APPROVE_CLEAN`/`APPROVE_WITH_EXCEPTIONS`/
  `RETURN_TO_ADJUSTMENTS`/`REJECT`) → `PACKAGE_READY_FOR_RELEASE` →
  `create_release_record()`. Escrituras atómicas (temp+fsync+rename),
  `fcntl` por paquete, `releases.jsonl`/`release_supersessions.jsonl`
  append-only.
- **`remediation_package_schemas.py`**: `RemediationChange` (exige ≥1
  `RegulatoryCitationReference`), `ArtifactReference.classification` ∈
  {`SOURCE_IMMUTABLE`, `CANDIDATE_DRAFT`, `REPORT`, `REDLINE`, `MANIFEST`}
  — el formato de salida YA está definido, no hay que inventarlo.
  `decision_origin: "human_confirmed"` se estampa en cada
  `package_decision` (línea 559).
- **`factory/api/routes/remediation_packages.py`**: el endpoint de
  RELEASE está deliberadamente SIN exponer — `PRODUCTION_ENABLEMENT`
  sigue `BLOCKED` para todo lo que pase por esta capa. R4-T1 no debe
  cruzar esa línea.
- **`factory/services/xlsx_candidate_generator.py`** y
  **`candidate_document_generator.py`** (DOCX): YA generan candidato
  limpio + versión redline (fuente verde + comentario `[change_id]`),
  reabriendo el archivo desde disco para verificar conformidad. Probados
  (`test_xlsx_candidate_generator.py`, verde).
- **`remediation_traceability_and_manifest.py`**: construye matriz de
  trazabilidad, narrativa de cambios y manifest desde datos upstream
  reales — nunca texto inventado.
- **`remediation_change_application_resolver.py`**: decide qué cambios
  llegan al candidato (`AUTO_APPLIED_TO_DRAFT`) vs. cuáles van a un
  paquete de excepciones.
- **`factory/services/gap_assessment_finding_mapper.py`** ("Ruta D"):
  mapper determinista hallazgo→`RemediationChange` (o rechazo explícito
  `NOT_MAPPABLE_TO_CURRENT_SCHEMA`). Activado defensivamente en R3-T1.8
  bloque 2 (commit `17c41d0`) precisamente porque **R4-T1 es la fase que
  lo activa** — sigue sin llamador de producción hoy.
- **Diseño ya escrito, no duplicar**:
  `factory/docs/design/regulatory_redesign_v2/CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md`,
  `GAP_DEVIATION_AND_REMEDIATION_MODEL.md`,
  `QA_FINAL_PACKAGE_AND_DECISION_SPEC.md`,
  `PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md`, `AUDIT_FORK_REMEDIATION_SPEC.md`.

### Lo que falta (esto SÍ es R4-T1)

1. **Wiring**: nada hoy lee una entrada `status=confirmed` de
   `human_review_queue.jsonl` y la empuja hacia `gap_assessment_finding_mapper`
   → `remediation_package_service.create_package`. La cola es un
   callejón sin salida — conectarla es el trabajo real de R4-T1.0.
2. **Marca NO-APROBADO explícita**: no se encontró ninguna marca de agua
   / texto "BORRADOR — NO APROBADO" en el candidato generado — falta.
3. **Gate de aceptación real** (Piloto 2 original) nunca corrió con este
   pipeline de remediación conectado extremo a extremo.
4. **Decisión de gobernanza**: ¿`D5` ("Regeneracion de paquetes QA",
   `decision_families.yaml` líneas 153-161) cubre la PRIMERA generación
   de un paquete, o solo su regeneración? — **pregunta abierta para
   Cesar**, no decidida por el agente. Si no cubre, hace falta una
   familia nueva o una ampliación de alcance de D5, firmada.

## Restricciones ya fijadas (no negociables, heredadas del plan original)

- SOLO hallazgos con decisión humana **confirmada** generan cambios —
  nunca un `PROVISIONAL_GAP`/`DOCUMENTATION_GAP`/`EVALUATION_INCOMPLETE`
  sin revisar, nunca un `CONFIRMED` de Tier-1 que sea en realidad
  `PROVISIONALLY_*` sin que B1 (`positive_conclusion_eligibility`)
  esté promovido (mismo invariante fijado y testeado en R3-T1.8 bloque 0:
  `test_b1_provisional_eligibility_survives_headline_rescue`).
- De los tipos de conclusión de `human_review_queue`, **solo
  `SUPPORTING_EVIDENCE_UNDER_REVIEW` confirmado** representa evidencia
  real confirmable (ver `_FINDING_QUOTE_REQUIRED_CONCLUSIONS`,
  `factory/api/routes/layer9.py`, R3-T1.8 bloque 1) — un `confirmed` sobre
  `EVALUATION_INCOMPLETE`/`PROVISIONAL_GAP`/etc. significa "acepto el
  bloqueo", NUNCA "genera un cambio en el documento". R4-T1.0 debe
  filtrar por esto explícitamente, no asumir que "confirmed" alcanza.
- Ruta D (bloque 2, ya cerrada) es prerequisito técnico — consume
  `candidate_validity.is_derived_headline()`/`split_derived_quotes()`,
  nunca reimplementa el marcador.
- Original intacto siempre; marca NO-APROBADO; redline; trazabilidad
  hallazgo→cambio.
- Gate de aceptación: Piloto 2 original sobre el documento más pequeño.
- Presupuesto dimensionado con latencias reales (no estimadas) y mismo
  método de fases (barato primero, completo solo si pasa).

## Fases

### R4-T1.0 — Wiring en frío (cero llamadas LLM)

- Función `dispatch_confirmed_finding_to_remediation(entry)`:
  1. Lee entrada `status=confirmed` de `human_review_queue`.
  2. Filtra por conclusión: solo `SUPPORTING_EVIDENCE_UNDER_REVIEW` con
     `human_confirmed_evidence.quote` no vacío continúa; cualquier otra
     conclusión confirmada (bloqueo/ausencia) se ignora explícitamente
     (log, nunca error silencioso).
  3. Llama `gap_assessment_finding_mapper` (Ruta D) → `RemediationChange`
     o `NOT_MAPPABLE_TO_CURRENT_SCHEMA` (si no mapeable: encola para
     revisión humana adicional, nunca bloquea el resto del lote).
  4. Adjunta el `RemediationChange` a un paquete
     (`remediation_package_service.create_package` o el paquete en
     progreso del documento).
- Tests unitarios end-to-end (entrada confirmada sintética →
  `RemediationChange` → paquete en el estado esperado), cero llamadas
  LLM, mismo patrón que Bloques 0-3 de R3-T1.8.
- Guardián explícito: test que confirme que una entrada confirmada sobre
  `EVALUATION_INCOMPLETE`/`PROVISIONAL_GAP`/`DOCUMENTATION_GAP`/
  `CROSS_REFERENCE_MISSING` NUNCA produce un `RemediationChange`.
- Entregable: diff + tests, checkpoint para aprobación de Cesar antes de
  R4-T1.1.

### R4-T1.1 — Marca NO-APROBADO explícita

- Extender `xlsx_candidate_generator.py`/`candidate_document_generator.py`
  (o el manifest, según qué capa sea más robusta) para estampar
  "BORRADOR — NO APROBADO — pendiente de revisión QA" visible en el
  documento generado (encabezado/pie según formato).
- Test: el candidato generado, reabierto desde disco, contiene la marca
  visible — mismo patrón de verificación por reapertura que ya usa
  `test_xlsx_candidate_generator.py`.

### R4-T1.2 — Gate de aceptación: Piloto 2 original, documento más pequeño

- Documento candidato: el de menor `total_chunks` medido en
  `corpus_budget_formula.CORPUS_PLAN_DOCUMENTS` — hoy un empate entre
  `RW-0011` y `RW-0012` (7 chunks cada uno, `DS`). Confirmar con Cesar
  cuál usar (o si prefiere otro por disponibilidad real del hallazgo
  confirmado).
- Requiere **hallazgos reales ya confirmados por Cesar** sobre ESE
  documento — nunca findings sintéticos fabricados para poder probar el
  pipeline (violaría "sin evidencia vacía ni citas no ancladas" aplicado
  a la prueba misma).
- Corre el flujo extremo a extremo: cola confirmada → Ruta D → paquete →
  candidato con marca NO-APROBADO + redline + manifest +
  trazabilidad — nunca hasta `create_release_record()` (ese endpoint
  sigue sin exponerse).
- Presupuesto de llamadas LLM: **cero en esta fase** si los hallazgos ya
  están confirmados (el pipeline de remediación es determinista, no LLM)
  — la única razón para gastar llamadas nuevas sería si el documento
  piloto NO tiene aún hallazgos confirmados reales, en cuyo caso hace
  falta una corrida de evaluación previa (fuera del alcance de R4-T1,
  gobernada por su propia `PILOT_EXECUTION`/`CORPUS_AUTHORIZATION`, con
  el presupuesto ajustado por el hallazgo de R3-T1.8 bloque 4: la tasa de
  violación de contrato del modelo fue 3/3 en la muestra chica —
  dimensionar con margen de reintento, no 1 llamada = 1 criterio
  resuelto).

### R4-T1.3 — Autorización y ejecución (fuera de alcance de esta corrida)

No arranca hasta que:
1. R4-T1.0 y R4-T1.1 estén commiteados y aprobados (diff + aprobación,
   mismo patrón que Bloques 0-3).
2. Exista al menos un hallazgo real confirmado por Cesar sobre el
   documento piloto elegido (R4-T1.2).
3. La pregunta abierta de gobernanza (D5 vs. familia nueva) esté resuelta
   y firmada por Cesar.
4. Cesar autorice explícitamente esta fase — DETENERSE aquí, como en
   todas las fases anteriores del arco R3-T1/R3-T1.8.

──────────────────────────────────────────────────────────────────────────────
INTENTO 2026-08-12 — R4-T1.0, PAUSADO (3 hallazgos de diseño, sin código
pendiente sin commitear)
──────────────────────────────────────────────────────────────────────────────

D5 resuelto y commiteado (`d8b8e5c`): familia nueva
`REMEDIATION_PACKAGE_GENERATION`, distinta de D5, para primera generación
de un paquete -- ver sección 0 arriba (actualizada).

Al intentar implementar R4-T1.0 (wiring cola confirmada -> Ruta D ->
paquete) aparecieron 3 preguntas de diseño reales, cada una descubierta
al tratar de escribir el código, no anticipada en el diseño original.
**Ninguna requirió tocar producción -- la única línea de código escrita
(una regla nueva de `coverage_status` para `SUPPORTING_EVIDENCE_UNDER_REVIEW`
en `gap_assessment_finding_mapper.py`) se revirtió limpia sin commitear**
al descubrirse el hallazgo 2.

**Hallazgo 1 -- autoría del texto propuesto.** `map_finding_to_remediation_change()`
exige `cambio_documental_propuesto` (el texto a agregar/reemplazar en el
documento) -- la cola confirmada de hoy nunca genera ese texto.
**Decisión de Cesar**: lo escribe un humano al confirmar, nunca el
sistema. Pendiente: extender el flujo de confirmación (UI + endpoint +
schema) con ese campo nuevo.

**Hallazgo 2 -- conclusión equivocada como disparador (error de
razonamiento propio, corregido).** El diseño inicial apuntaba a
`SUPPORTING_EVIDENCE_UNDER_REVIEW` confirmado como disparador de una
remediación -- pero confirmar esa conclusión significa "esta cita SÍ
sustenta el requisito", es decir, **no hay brecha**. Un `RemediationChange`
corrige brechas, no confirma cumplimiento. El disparador correcto son las
conclusiones de brecha (`DOCUMENTATION_GAP`/`PROVISIONAL_GAP`) confirmadas
("acepto que esto es una brecha real"). Buena noticia parcial: esas dos
YA están soportadas por `_COVERAGE_STATUS_BY_VERIFIED_CONCLUSION` en Ruta
D, sin necesitar extensión -- la falsa alarma del hallazgo original
(que Ruta D no tenía regla) aplicaba solo a la conclusión equivocada.
`EVALUATION_INCOMPLETE` sigue -- correctamente -- sin regla: una
contradicción bloqueada exige que un humano decida QUÉ sección es la
vigente, no solo "acepto el bloqueo".

**Hallazgo 3 -- falta ubicación de inserción para brechas.** Una entrada
`DOCUMENTATION_GAP`/`PROVISIONAL_GAP` tiene `evidence_quote` vacío,
`page: null`, `candidates: []` -- no hay ubicación que anclar. Pero
`_derive_page_anchor()` de Ruta D siempre exige una (rango de página +
chunk, o auto-marcador en el texto citado). Falta que el humano indique,
al escribir el texto propuesto (hallazgo 1), TAMBIÉN dónde insertarlo --
un campo más sobre el mismo flujo de confirmación extendido.

**Pausado aquí, decisión explícita de Cesar** -- 3 correcciones de diseño
seguidas en la misma corrida es la señal de detenerse, no de seguir
empujando. R4-T1.0 retoma con los 3 puntos ya resueltos de antemano, no
descubiertos sobre la marcha.

## Resumen de estado

```
R4_T1_PREREQS_AUDITADOS =      SI -- infraestructura real ya existe,
                                 documentado arriba (seccion 0)
D5_RESUELTO =                   SI -- REMEDIATION_PACKAGE_GENERATION,
                                 commiteado d8b8e5c
R4_T1_0_INTENTADO =              SI, 2026-08-12 -- pausado, 3 hallazgos de
                                 diseño (ver arriba), CERO codigo sin
                                 commitear pendiente
R4_T1_0_PENDIENTE_DE_DISEÑO =    (a) campo de texto propuesto en el flujo
                                 de confirmacion (autoria humana, no
                                 sistema) (b) disparador correcto =
                                 DOCUMENTATION_GAP/PROVISIONAL_GAP
                                 confirmados, NUNCA SUPPORTING_EVIDENCE_
                                 UNDER_REVIEW (c) campo de ubicacion de
                                 insercion para brechas sin candidato
R4_T1_MISSING =                 wiring cola->RutaD->paquete (con los 3
                                 puntos resueltos), marca NO-APROBADO,
                                 gate real end-to-end
R4_T1_FASES =                   R4-T1.0 (wiring, 0 LLM, PAUSADO) ->
                                 R4-T1.1 (marca, 0 LLM) -> R4-T1.2 (gate
                                 real, 0 LLM si hay hallazgos confirmados)
                                 -> R4-T1.3 (ejecucion, requiere firma)
R4_T1_INICIADO =                PARCIAL -- D5 resuelto, R4-T1.0 pausado
                                 en diseño, sin codigo de produccion
                                 tocado
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```
