# R4-T1.0v2 — DIRECTIVA DE REMEDIACIÓN: EL CONCEPTO QUE FALTABA
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R4_T1_0v2_DIRECTIVA_REMEDIACION.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
#
# DIAGNÓSTICO QUE ORIGINA ESTA CORRIDA: los 3 hallazgos que pausaron
# R4-T1.0 (falta texto propuesto, falta ubicación, disparador equivocado)
# NO son tres problemas: son un concepto faltante. El flujo de confirmación
# mezcla dos actos humanos distintos:
#   Acto 1 — ADJUDICAR el hallazgo (juicio sobre el ANÁLISIS) → ya existe
#            y funciona: la cola de revisión.
#   Acto 2 — REDACTAR la remediación (autoría sobre el DOCUMENTO) → no
#            existe en ninguna parte del sistema.
# Parchear el endpoint de confirmación con dos campos sueltos repetiría el
# error de B3/B4/B5. Se define el concepto UNA vez.
#
# Reglas duras: CERO llamadas LLM en bloques 0-3; no MarkItDown; no cambiar
# modelo; NO aflojar validadores; la IA NUNCA redacta el contenido
# regulatorio propuesto; no commit sin diff + aprobación.
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. VERIFICACIÓN PREVIA — ¿EXISTE HOY ALGÚN DISPARADOR VÁLIDO? (bloqueador)
──────────────────────────────────────────────────────────────────────────────

R4-T1.2 exige un hallazgo REAL de brecha confirmado por Cesar sobre el
documento piloto. Antes de diseñar nada, saber si existe:

0.1 Inventariar `human_review_queue.jsonl`: entradas con `status=confirmed`
    Y conclusión en {DOCUMENTATION_GAP, PROVISIONAL_GAP} (los únicos
    disparadores válidos según el hallazgo 2, ya corregido). Reportar
    cuántas hay, sobre qué documentos, y si alguna es de un run vigente
    (no supersedido por corrección de perfil).
0.2 Resultado probable: CERO — la única corrida Tier-1 real fue RW-0005
    con perfil BASELINE (supersedida), y la entrada firmada por Cesar era
    `EVALUATION_INCOMPLETE` (correctamente no disparador). Si es así,
    decirlo con claridad: **R4 no tiene hoy nada que remediar**, y el gate
    de R4-T1.2 depende de producir primero un hallazgo real.
0.3 Consecuencia a planificar (no ejecutar aquí): hace falta una corrida
    Tier-1 con perfil H2H4 sobre el documento piloto (RW-0011 o RW-0012,
    7 chunks) para generar hallazgos reales. Dimensionarla:
    - requisitos aplicables al tipo documental DS según la matriz;
    - llamadas = requisitos × 7 chunks bajo H2H4;
    - margen de reintento (la tasa de violación de contrato del modelo fue
      3/3 en la muestra chica de R3-T1.8 — no asumir 1 llamada = 1
      criterio resuelto);
    - latencia real medida ⇒ tiempo de pared.
    Presentar el número a Cesar como propuesta de fase separada. NO
    proponer la autorización todavía: primero el diseño de los bloques
    1-2, porque si el diseño cambia, el disparador cambia.

──────────────────────────────────────────────────────────────────────────────
1. DISEÑO DEL ARTEFACTO: DIRECTIVA DE REMEDIACIÓN
──────────────────────────────────────────────────────────────────────────────

1.1 CONCEPTO: una `RemediationDirective` es el registro del Acto 2 —
    autoría humana de la corrección. Referencia un hallazgo de brecha ya
    confirmado y aporta lo que ninguna adjudicación produce:
    ```
    remediation_directive:
      directive_id
      finding_rc_id            # el hallazgo de brecha confirmado que la origina
      document_id + document_sha256
      requirement_id
      change_type              # ADD | REPLACE | DELETE
      proposed_text            # REDACTADO POR HUMANO — nunca por el sistema
      target_location          # sección/página/ancla donde insertar o reemplazar
      original_text            # si REPLACE/DELETE: el texto exacto a modificar
      regulatory_citation      # ≥1 referencia (lo que RemediationChange exige)
      rationale                # por qué esta redacción atiende el requisito
      authored_by_id / display_name    # identidad real, 422 genéricas
      authored_at
      status                   # DRAFT | SUBMITTED | SUPERSEDED
    ```
1.2 REGLAS DURAS del artefacto:
    - `proposed_text` es SIEMPRE de autoría humana. Ningún agente lo
      genera, lo sugiere ni lo autocompleta (decisión ya tomada por Cesar).
      Test que lo garantice: ninguna ruta de código escribe ese campo.
    - solo se acepta si el `finding_rc_id` referenciado está `confirmed`
      Y su conclusión es DOCUMENTATION_GAP o PROVISIONAL_GAP. Cualquier
      otra (SUPPORTING_EVIDENCE_UNDER_REVIEW = no hay brecha;
      EVALUATION_INCOMPLETE = contradicción sin resolver) se rechaza con
      motivo explícito.
    - `document_sha256` debe coincidir con el documento vigente: si el
      original cambió desde el hallazgo, la directiva se invalida (guardia
      de drift, mismo principio que el resto del sistema).
    - append-only, versionada, con evento de auditoría propio.
1.3 UBICACIÓN DE INSERCIÓN (hallazgo 3 resuelto por diseño): `target_location`
    la aporta el humano al redactar. Definir el formato aceptado y su
    validación determinista (que la sección/página exista realmente en el
    documento; que si es REPLACE, el `original_text` ancle en el documento
    con el mismo verificador de siempre). `_derive_page_anchor()` de Ruta D
    consume esto en vez de exigir un ancla de evidencia que en una brecha
    no existe.
1.4 GOBERNANZA: encaja en la familia `REMEDIATION_PACKAGE_GENERATION` ya
    creada (`d8b8e5c`), o requiere su propia familia — analizar y
    proponer, no decidir. La directiva es un acto humano firmado: debe
    quedar registrado como tal.

──────────────────────────────────────────────────────────────────────────────
2. WIRING (con el concepto ya definido)
──────────────────────────────────────────────────────────────────────────────

2.1 La cadena queda: hallazgo de brecha confirmado (Acto 1, ya existe) →
    `RemediationDirective` (Acto 2, nuevo) → `gap_assessment_finding_mapper`
    (Ruta D, ya activada) → `RemediationChange` →
    `remediation_package_service.create_package` (ya existe).
    La directiva es la ÚNICA entrada a Ruta D — nada más la alimenta.
2.2 Ruta D consume `proposed_text`, `target_location`, `original_text` y
    `regulatory_citation` de la directiva. Si algo falta o no valida:
    `NOT_MAPPABLE` con motivo, encolado para el humano, sin bloquear el
    lote.
2.3 Superficie única respetada: Ruta D sigue consumiendo
    `candidate_validity` para lo que le corresponde; no reimplementa
    anclaje. El test de no-bypass cubre esta ruta.
2.4 Tests end-to-end en frío (cero LLM): directiva sintética válida →
    RemediationChange → paquete en estado esperado; y los guardianes:
    - directiva sobre SUPPORTING_EVIDENCE_UNDER_REVIEW ⇒ rechazada;
    - directiva sobre EVALUATION_INCOMPLETE ⇒ rechazada;
    - directiva sin cita regulatoria ⇒ rechazada;
    - directiva con `original_text` que no ancla (REPLACE) ⇒ rechazada;
    - `document_sha256` desactualizado ⇒ rechazada;
    - ningún código de agente escribe `proposed_text`.

──────────────────────────────────────────────────────────────────────────────
3. INTERFAZ PARA EL ACTO 2 (mínima, pero real)
──────────────────────────────────────────────────────────────────────────────

3.1 El humano necesita ver el documento para decir dónde va el texto.
    Diseñar la vista mínima: desde una entrada de brecha confirmada,
    un formulario que capture los campos de 1.1, mostrando el contexto
    del documento (secciones/páginas disponibles) para elegir ubicación.
3.2 Cero fallos silenciosos (estándar ya establecido): cada validación
    rechazada muestra motivo; identidad validada (422 genéricas); un
    evento por directiva enviada; idempotencia 409.
3.3 Si la UI completa resulta grande, entregar primero el endpoint +
    validación (probado con tests) y una vía mínima de captura, y
    proponer la UI rica como fase aparte — no bloquear R4 por pulido.

>>> CHECKPOINT: bloques 0-3 con diffs y tests, cero llamadas. DETENERSE
>>> para aprobación de Cesar y para las dos decisiones de gobernanza
>>> (familia de la directiva; y si autoriza la corrida Tier-1 del piloto).

──────────────────────────────────────────────────────────────────────────────
4. MARCA NO-APROBADO (R4-T1.1, sin cambios; barato, hacerlo aquí si cabe)
──────────────────────────────────────────────────────────────────────────────

Estampar "BORRADOR — NO APROBADO — pendiente de revisión QA" visible en el
candidato generado (encabezado/pie según formato), verificado reabriendo
el archivo desde disco (mismo patrón de `test_xlsx_candidate_generator`).
Cero LLM.

──────────────────────────────────────────────────────────────────────────────
5. GATE DE ACEPTACIÓN (R4-T1.2) — SECUENCIA REAL
──────────────────────────────────────────────────────────────────────────────

Con el diseño cerrado, la secuencia para el gate es:
  (i)   corrida Tier-1 H2H4 sobre el documento piloto (autorización y
        presupuesto propios, dimensionados en 0.3) ⇒ produce hallazgos;
  (ii)  Cesar adjudica en la cola: confirma al menos una brecha real;
  (iii) Cesar redacta la directiva de remediación para esa brecha;
  (iv)  el pipeline determinista genera candidato + redline + manifest +
        trazabilidad (CERO llamadas LLM — la remediación no usa el modelo);
  (v)   verificación: original intacto (SHA-256), marca NO-APROBADO
        presente, todo cambio trazable a su directiva y a su hallazgo,
        nunca se llega a `create_release_record()`.
Documentar esta secuencia como el gate, y que (i) es la única parte con
costo de inferencia.

──────────────────────────────────────────────────────────────────────────────
6. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
VALID_TRIGGERS_TODAY =        (nº de brechas confirmadas vigentes; probable 0)
PILOT_RUN_SIZING =            (requisitos × 7 chunks + margen; horas de pared)
DIRECTIVE_SCHEMA =            (definido; campos de 1.1)
HUMAN_AUTHORSHIP_ENFORCED =   (test: ningún agente escribe proposed_text)
TRIGGER_GUARDS =              (6 guardianes de 2.4: PASA/FALLA)
RUTA_D_CONSUMES_DIRECTIVE =   (única entrada)
NO_BYPASS_COVERS_RUTA_D =     true
DIRECTIVE_GOVERNANCE_FAMILY = (propuesta; decisión de Cesar)
UI_ACTO2 =                    (endpoint+validación listos / UI rica diferida)
NO_APROBADO_MARK =            (estampada y verificada por reapertura)
GATE_SEQUENCE =               (i–v documentada)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE tras el checkpoint. Dos decisiones esperan a Cesar: la familia
de gobernanza de la directiva, y si autoriza la corrida Tier-1 del
documento piloto (la única con costo de inferencia en todo R4). El resto
del pipeline de remediación es determinista: una vez que exista una brecha
confirmada y su directiva, generar el borrador controlado no cuesta ni una
llamada al modelo.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 — BLOQUES 0-3 (cero llamadas LLM)
──────────────────────────────────────────────────────────────────────────────

## Bloque 0 — verificación previa

**0.1-0.2**: inventariado `human_review_queue.jsonl` (34 entradas
totales). Confirmadas hoy: exactamente 2 -- `SUPPORTING_EVIDENCE_UNDER_REVIEW`
(RW-0005) y `EVALUATION_INCOMPLETE` (dry-run ya anotado). **Cero** con
conclusión en `{DOCUMENTATION_GAP, PROVISIONAL_GAP}`. Predicción del plan
confirmada exacta: **R4 no tiene hoy nada que remediar**. Las 12 entradas
`PROVISIONAL_GAP`/`DOCUMENTATION_GAP` que existen están todas
`superseded` (perfil BASELINE, corrida histórica) o `pending` sin
confirmar (2 de ellas, subproductos de las corridas de contraste de
bloque 4 de R3-T1.8 -- no evaluaciones completas de documento, no deben
tratarse como hallazgos reales confirmables). RW-0011/RW-0012 (candidatos
a piloto) solo tienen 1 entrada cada uno, `pending`,
`EVIDENCE_NOT_LOCATED_IN_CANDIDATES` (otro tipo de conclusión, de una
corrida diagnóstica anterior).

**0.3**: de los 20 requisitos del catálogo, solo 7 son aplicables a tipo
documental `DS` sin ser `review_required` (terminal, sin llamada) --
`expected`/`optional`/`cross_reference_expected`. Bajo H2H4 (1
requisito/llamada, configuración congelada de F1): **7 requisitos × 7
chunks = 49 llamadas**. Latencia real medida (bloque 4 de R3-T1.8):
p50≈600s, p95≈850s ⇒ **~8.2h de pared en el mejor caso, ~11.6h en el
peor**, secuencial. Número presentado, autorización NO propuesta todavía
(per instrucción explícita del bloque).

## Bloque 1 — `RemediationDirective` (Acto 2)

Implementado en `factory/services/remediation_directive.py` (nuevo):
- `propose_remediation_directive()`: única función de creación real.
  Exige hallazgo `confirmed` con conclusión en `VALID_TRIGGER_CONCLUSIONS`
  (`DOCUMENTATION_GAP`/`PROVISIONAL_GAP`); `document_sha256` recalculado
  y comparado contra el documento real (`_resolve_document_path`, mismo
  guardián de drift que usa el resto de la fábrica); `original_text`
  anclado literalmente contra el texto real de `target_location` para
  `REPLACE`/`DELETE` (`verify_anchor`, rechaza `fuzzy`); cita regulatoria
  verificada contra el catálogo real (`known_entry_ids()`); identidad
  real (`validate_identity`).
- `validate_remediation_directive()`: validación de forma, mismo estilo
  fail-closed que `remediation_package_schemas.py`.
- Nuevo evento de auditoría `remediation_directive_authored`
  (`factory/core/audit_writer.py`, lista cerrada).
- `factory/tests/test_remediation_directive.py`: 20 tests -- incluye
  guardián estático (`ast`) que confirma que `proposed_text` en el dict
  de la directiva es SIEMPRE el parámetro tal cual, nunca una expresión
  calculada; y que el módulo no referencia ningún símbolo de
  generación/LLM.

## Bloque 2 — wiring (directiva → Ruta D)

Implementado en `factory/services/remediation_directive_dispatch.py`
(nuevo): traduce una `RemediationDirective` ya validada al formato
narrativo que `map_finding_to_remediation_change()` exige.

Decisiones de Cesar aplicadas:
- `page_start` como proxy de `chunk_id` en el `paginas` sintetizado
  (`"pag X-Y (chunk X)"`) -- mismo principio que el proxy ya documentado
  y aceptado de `chunk_sha256` en Ruta D.
- `change_type=DELETE` rechazado explícitamente
  (`DirectiveNotDispatchable`, nunca silencioso) -- Ruta D no tiene verbo
  mapeado para eliminación.

**Hallazgo real encontrado y corregido durante la implementación** (no
anticipado en el diseño): `clasificacion_brecha` no puede ser la misma
para `ADD` y `REPLACE` -- `ADD` es una ausencia real (`DOCUMENTATION_GAP`
→ `ABSENCE_CONFIRMED`, exige que `evidencia` describa ausencia sobre
"todas las secciones evaluadas"), pero `REPLACE` es una cita REAL que
hay que reemplazar (`NOT_DEMONSTRATED_IN_DOSSIER` → `PARTIAL_EVIDENCE`).
Usar `DOCUMENTATION_GAP` para ambos rechazaba todo `REPLACE` real
(`evidencia` era una cita real, nunca la frase de ausencia exigida).
Corregido mapeando `clasificacion_brecha` por `change_type`, no por la
conclusión que disparó el hallazgo.

También se descubrió que Ruta D exige un veredicto sustantivo transportado
(deuda I-1, `finding_substantive_adapter.py`) -- se agregó
`estado_agente_original="evidencia_insuficiente"` (real: el finding
SIEMPRE describe una ausencia confirmada, nunca una afirmación positiva
del modelo) para que `compute_substantive_support()` resuelva
`NOT_APPLICABLE` (dentro de `PERMITS_COVERAGE_EVALUATION`).

`factory/tests/test_remediation_directive_dispatch.py`: 6 tests --
`ADD`/`REPLACE` dispatchan a un `RemediationChange` válido
(`validate_remediation_change()` real), `DELETE` rechazado, drift de
documento rechazado, `requirement_id` desconocido rechazado.

## Bloque 3 — interfaz mínima (Acto 2)

`POST /api/v1/layer9/remediation/directives` +
`GET /api/v1/layer9/remediation/directives` (`factory/api/routes/layer9.py`):
vía mínima de captura, sin UI rica (per 3.3, "no bloquear R4 por
pulido"). 422 con motivo explícito para cada rechazo (identidad
reservada, disparador inválido, campos vacíos). `factory/tests/
test_remediation_directive_endpoint.py`: 5 tests.

## Bloque 4 (R4-T1.1, marca NO-APROBADO) — BLOQUEADO por un hallazgo nuevo

Antes de estampar la marca se revisaron los generadores de candidato
reales: `xlsx_candidate_generator.py` (celdas de un workbook) y
`candidate_document_generator.py` (párrafos DOCX). **Ninguno de los dos
aplica al documento piloto real** -- RW-0011 (y por extensión RW-0012,
misma convención) es un **PDF** (`MCCPDC EMS Control Block Narrative
revB.pdf`), confirmado leyendo el `archivo` real de su checkpoint
histórico. No existe un generador de candidato para PDF hoy. Estampar
NO-APROBADO en un formato que no tiene generador de candidato no es
"barato" como asumía el plan -- es un cuarto hallazgo de diseño, de la
misma familia que los tres que pausaron R4-T1.0 la vez anterior.
**No implementado en esta corrida** -- documentado para que Cesar decida
antes de escribir código nuevo, en vez de descubrirlo sobre la marcha.

## Verificación

Suite dirigida (`test_remediation_directive*.py`): 31 tests, todos
verdes. No-bypass (`test_candidate_validity_no_bypass.py`,
`test_gap_assessment_finding_mapper.py`, `test_decision_resolver_no_bypass.py`):
70 passed, 1 xfailed -- sin regresión. Gate 0 completo corriendo en
background al cierre de este documento.

```
VALID_TRIGGERS_TODAY =        0 (confirmado, bloque 0)
PILOT_RUN_SIZING =            49 llamadas (7 req x 7 chunks), ~8.2-11.6h
                               de pared, NO autorizado en esta corrida
DIRECTIVE_SCHEMA =            implementado y probado (20 tests)
HUMAN_AUTHORSHIP_ENFORCED =   SI -- guardian estatico (ast), proposed_text
                               es siempre el parametro, nunca calculado
TRIGGER_GUARDS =              6/6 PASA (remediation_directive.py)
RUTA_D_CONSUMES_DIRECTIVE =   SI -- unica entrada (remediation_directive_dispatch.py)
NO_BYPASS_COVERS_RUTA_D =     ya cubierto (test_candidate_validity_no_bypass.py,
                               sin cambios necesarios -- la directiva no
                               reimplementa anclaje, reusa verify_anchor real)
DIRECTIVE_GOVERNANCE_FAMILY = PENDIENTE -- no decidido en esta corrida
                               (REMEDIATION_PACKAGE_GENERATION existente
                               podria cubrir la directiva, o merece la suya
                               propia -- analisis pendiente)
UI_ACTO2 =                    endpoint + validacion listos (5 tests);
                               UI rica diferida, per 3.3
NO_APROBADO_MARK =            BLOQUEADO -- hallazgo nuevo: no existe
                               generador de candidato para PDF (documento
                               piloto real), solo XLSX/DOCX
GATE_SEQUENCE =                (i) corrida Tier-1 (ii) adjudicar (iii)
                               redactar directiva (iv) generar candidato
                               -- (iv) bloqueado por el hallazgo de arriba
                               (v) verificar
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**CHECKPOINT.** Bloques 0-3 completos, con diffs y tests, cero llamadas
LLM. Nada commiteado todavía. DETENERSE para tu revisión y aprobación, y
para dos decisiones tuyas: familia de gobernanza de la directiva, y qué
hacer con el hallazgo del generador de candidato PDF antes de que
R4-T1.1 pueda avanzar.
