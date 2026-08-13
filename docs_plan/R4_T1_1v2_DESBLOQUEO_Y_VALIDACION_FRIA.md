# R4-T1.1v2 — DESBLOQUEO DE FORMATO Y VALIDACIÓN EN FRÍO DE TODA LA CADENA
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R4_T1_1v2_DESBLOQUEO_Y_VALIDACION_FRIA.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
#
# DIAGNÓSTICO: la corrida Tier-1 (49 llamadas, 8-12h) produciría hallazgos
# sobre un documento que NO se puede remediar (RW-0011 es PDF; no hay
# generador de candidato PDF). El gate se detendría igual en el paso (iv).
# ⇒ El orden estaba invertido: toda la cadena de R4 salvo el paso (i) es
# determinista y GRATIS. Se valida primero lo barato de aguas abajo; lo caro
# de aguas arriba se autoriza al final, ya sabiendo que lo demás funciona.
#
# Reglas duras: CERO llamadas LLM en toda esta corrida; no MarkItDown; no
# cambiar modelo; NO aflojar validadores; la IA nunca redacta contenido
# regulatorio; no commit sin diff + aprobación.
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. FRESCURA DE DESPLIEGUE — ANTES DE QUE CESAR FIRME O ENVÍE NADA
──────────────────────────────────────────────────────────────────────────────

Lección ya pagada: el endpoint de decisión de hallazgos estuvo un día
commiteado pero ausente del contenedor vivo ⇒ "Hallazgo no encontrado".
El endpoint nuevo de directivas (`f6607e9`) está en la misma situación
potencial.

0.1 Verificar contra el SERVIDOR VIVO (no contra el código en disco):
    `GET /openapi.json` de factory-api debe listar
    `POST /api/v1/layer9/remediation/directives` y su GET. Reportar
    presente/ausente con la evidencia.
0.2 Si está ausente: `docker compose -f docker-compose.factory.yml restart
    factory-api` (bind mount ⇒ sin rebuild), con tu autorización explícita
    antes de tocar infraestructura compartida. Verificar después: `/health`
    OK, ruta presente, colas y datos intactos.
0.3 Confirmar si el CHEQUEO DE FRESCURA pedido en R3-T1.8 §3.1 llegó a
    implementarse (comparar código montado vs. servicio vivo, o rutas
    esperadas en `/openapi.json`, como WARN en Gate 0/status). Si no
    existe, implementarlo ahora — es barato y evita repetir esto una
    tercera vez.
0.4 REGLA PERMANENTE a registrar en el skill: ninguna solicitud de firma
    se le presenta a Cesar sin haber verificado antes que el endpoint que
    esa firma necesita está vivo en el servicio.

──────────────────────────────────────────────────────────────────────────────
1. DESBLOQUEO DE FORMATO — RE-SELECCIONAR EL PILOTO POR GENERADOR
──────────────────────────────────────────────────────────────────────────────

El criterio de selección estaba mal: se eligió por tamaño (7 chunks)
cuando la restricción vinculante es TENER GENERADOR. No hay que construir
un generador de PDF para desbloquear R4.

1.1 Inventariar los documentos analizables de la allowlist con su FORMATO
    real y su tamaño (chunks): cuáles son DOCX, XLSX, PDF, otros.
1.2 Elegir el piloto con este criterio ordenado:
    (a) formato con generador de candidato YA existente y probado
        (DOCX o XLSX);
    (b) entre esos, el de menor número de chunks (costo de la corrida);
    (c) que tenga requisitos aplicables > 0 según la matriz.
    Presentar la tabla y la recomendación; la elección final es de Cesar.
1.3 Documentar la política de formato (ya definida en el diseño W5 V2 §14,
    no inventarla): PDF sin fuente editable ⇒ `DOCUMENT_GENERATION_BLOCKED`
    con la limitación registrada, NO se fuerza una reconstrucción. Dejarlo
    escrito como la respuesta permanente del sistema para PDFs, de modo que
    no vuelva a aparecer como "hallazgo nuevo".
1.4 Con el piloto nuevo, re-dimensionar la corrida Tier-1 (requisitos
    aplicables × chunks bajo H2H4 + margen de reintento por la tasa de
    violación de contrato observada) y su tiempo de pared real. Solo
    dimensionar; no proponer autorización todavía.

──────────────────────────────────────────────────────────────────────────────
2. VALIDACIÓN EN FRÍO DE LA CADENA COMPLETA (cero llamadas — el bloque clave)
──────────────────────────────────────────────────────────────────────────────

Objetivo: demostrar que TODO lo que ocurre después del hallazgo funciona,
antes de gastar una sola llamada en producir hallazgos.

2.1 Construir el caso de prueba con datos reales del documento piloto
    elegido: un hallazgo de brecha SINTÉTICO pero bien formado (marcado
    `DRY_RUN_VALIDATION`, en cola aislada, jamás mezclado con hallazgos
    reales) + una directiva de remediación redactada A MANO por un humano
    (texto propuesto, ubicación real del documento, cita regulatoria real
    del catálogo).
    NOTA: el hallazgo es sintético SOLO para probar la mecánica; queda
    marcado como tal y no puede entrar a ningún baseline ni Golden Dataset.
2.2 Ejecutar la cadena determinista completa:
    directiva → `remediation_directive_dispatch` → Ruta D →
    `RemediationChange` → `remediation_package_service.create_package` →
    generador de candidato (DOCX/XLSX) → redline → manifest →
    trazabilidad. CERO llamadas LLM en todo el trayecto.
2.3 CRITERIOS DE ACEPTACIÓN (pre-fijados, todos):
    a) el candidato se genera y ABRE desde disco;
    b) lleva la marca visible "BORRADOR — NO APROBADO — pendiente de
       revisión QA" (R4-T1.1, ahora sí implementable: hay generador);
    c) el redline refleja exactamente el cambio de la directiva;
    d) el documento ORIGINAL intacto (SHA-256 antes/después);
    e) todo cambio en el candidato es trazable a su directiva y esta a su
       hallazgo (matriz de trazabilidad completa);
    f) el manifest lista todos los artefactos con sus hashes;
    g) NUNCA se alcanza `create_release_record()` (endpoint sin exponer);
    h) un `change_type=DELETE` sigue rechazado; una directiva inválida
       (sin cita, con `original_text` que no ancla, con sha desactualizado)
       sigue rechazada.
2.4 Si algún criterio falla: corregir y repetir — sigue sin costar
    llamadas. Este es el momento barato de encontrar los defectos que
    quedan en el pipeline de generación.

>>> CHECKPOINT 2: paquete de validación en frío completo. Con esto, R4
>>> queda demostrado en todo lo que no depende del modelo.

──────────────────────────────────────────────────────────────────────────────
3. PRE-VUELO ANTES DE AUTORIZAR LA CORRIDA TIER-1 (tu condición 2)
──────────────────────────────────────────────────────────────────────────────

Ninguna corrida de 8-12h se propone sin este checklist en verde:

3.1 Cadena posterior demostrada (§2 completo, criterios a–h).
3.2 Endpoint de directivas vivo en el servicio (§0) y UI de adjudicación
    funcionando — verificado en vivo, no por código en disco.
3.3 Perfil H2H4 enforced en el runner de producto; fingerprint registrado.
3.4 Presupuesto dimensionado con margen de reintento real; hard stop de
    llamadas y de tiempo de pared configurados.
3.5 Ejecución en background desacoplada (systemd-run/tmux) con
    verificación de supervivencia a cierre de SSH ANTES de dejarla sola,
    y script de estado de solo lectura para consultarla.
3.6 Checkpoint por requisito + resume con fingerprint idéntico, fail-closed
    verificado.
3.7 Criterio de éxito de la corrida pre-fijado por escrito: qué resultado
    la hace útil (al menos un hallazgo de brecha adjudicable) y qué
    resultado la haría un fracaso diagnosticable.
3.8 Recién con 3.1–3.7 en verde: proponer la autorización a Cesar con el
    número exacto de llamadas y horas. DETENERSE para su firma.

──────────────────────────────────────────────────────────────────────────────
4. DECISIONES DE GOBERNANZA PENDIENTES (preparar, no decidir)
──────────────────────────────────────────────────────────────────────────────

4.1 Familia de gobernanza de la directiva: ¿`REMEDIATION_PACKAGE_GENERATION`
    (ya creada, `d8b8e5c`) la cubre, o necesita familia propia? Analizar el
    alcance declarado de esa familia y recomendar, con el argumento — la
    directiva es un acto humano de autoría, distinto de generar un paquete.
4.2 Política de PDF (§1.3) como decisión formal: confirmar
    `DOCUMENT_GENERATION_BLOCKED` para PDFs sin fuente editable, y que los
    documentos PDF del corpus quedan fuera del alcance de remediación
    automática hasta que exista fuente editable autorizada. Esto acota el
    producto de forma honesta y evita una fase de "generador PDF" que hoy
    no aporta.
4.3 Presentar ambas junto al pre-vuelo, para que Cesar firme en un solo
    ciclo: familia + política de PDF + autorización de la corrida.

──────────────────────────────────────────────────────────────────────────────
5. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
ENDPOINT_LIVE =               (directivas presente en /openapi.json vivo)
CONTAINER_RESTARTED =         (si hizo falta, con autorización)
FRESHNESS_CHECK =             (implementado en Gate 0/status)
PILOT_REVISED =               (documento, formato, chunks, generador disponible)
PDF_POLICY =                  (DOCUMENT_GENERATION_BLOCKED documentado)
COLD_CHAIN_VALIDATION =       criterios a–h (PASA/FALLA cada uno)
NO_APROBADO_MARK =            (estampada y verificada por reapertura)
ORIGINAL_INTACT =             (SHA-256)
RELEASE_NEVER_REACHED =       true
PILOT_RUN_SIZING_REVISED =    (llamadas × horas con el piloto nuevo)
PREFLIGHT =                   3.1–3.7 (verde/rojo cada uno)
GOVERNANCE_PACKAGE =          (familia + política PDF, listos para firma)
LLM_CALLS_THIS_RUN =          0
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: la autorización del restart (si aplica), el checkpoint 2, y
el ciclo único de firmas del §4.3. La corrida Tier-1 NO se propone hasta
que la cadena posterior esté demostrada — no tiene sentido producir
hallazgos que el sistema todavía no sabe remediar.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 — §0 y §1
──────────────────────────────────────────────────────────────────────────────

## §0 — Frescura de despliegue: VERDE

0.1 `GET /openapi.json` (factory-api, vivo, puerto 9000) lista
    `POST`/`GET /api/v1/layer9/remediation/directives`. Presente.
0.2 No aplica restart (ya presente). Contenedor `factory-api` Up.
0.3 El chequeo de frescura de R3-T1.8 §3.1 YA estaba implementado --
    `factory/tests/test_governance_ui_deploy_consistency_live.py::
    test_deploy_freshness_all_source_routes_are_live` (compara rutas de
    `factory/api/routes/*.py` contra `/openapi.json` vivo). Corrida contra
    el servidor real: 5/5 tests PASS, incluida esa prueba.
0.4 Regla permanente registrada en
    `.claude/skills/gmp-layer8-agent/SKILL.md` (sección "Regla permanente
    -- frescura antes de firma").

## §1 — Re-selección de piloto: CORRECCIÓN DE PREMISA + RW-0005 confirmado

**Hallazgo:** el diagnóstico original de este plan ("RW-0011 es PDF; no
hay generador de candidato PDF") está desactualizado. Existe y está en
producción `factory/services/governed_candidate_document_pipeline.py`
(Fase L, W5 V2) + `factory/services/document_generation_strategy.py`
(Fase J): un PDF con `extraction_capability=TEXT_NATIVE` SÍ tiene
estrategia real (`PDF_RECONSTRUCTED_DOCX_AND_PDF`, extrae estructura del
PDF y genera candidato/redline DOCX). De los 14 documentos del allowlist,
8 son `generation_ready=True` por esta vía (RW-0002/0005/0006/0009/0010/
0011/0012/0014); XLSX (RW-0013) y DOCM (RW-0007) tienen generador
construido pero **deliberadamente** `generation_ready=False` -- "sin caso
real del corpus Rockwell que lo haya ejercitado todavía" (misma disciplina
de nunca declarar listo sin caso real).

1.1-1.2 Tabla completa presentada al usuario (14 docs, formato/doc_type/
    estrategia/generation_ready/¿probado con caso real?). Único documento
    con generador **probado de punta a punta** (no solo "declarado listo"
    por código): **RW-0005** -- extractor de estructura verificado 8/8
    secciones reales (`test_document_structure_extractor.py`), pipeline
    gobernado probado E2E (`test_governed_candidate_document_pipeline.py::
    TestRealEndToEndAgainstFSv12Pdf`), y ya tiene una corrida Tier-1 real
    COMPLETA (`chunked-943a62bcbb85`, 29 chunks, 0 fallos técnicos, 5
    requisitos aplicables evaluados: 21_CFR_11.10(a/d/e/g) +
    21_CFR_11.50_11.70) cuyos hallazgos siguen `pending_human_review`.
    RW-0011/RW-0012 (5 chunks medidos, no 7 como se estimaba antes de
    correr) son `generation_ready=True` por código pero NUNCA pasaron por
    el extractor de estructura ni el generador de candidato -- elegirlos
    repetiría el error original (preferir "barato" sobre "con generador
    probado").
    **Decisión de Cesar (esta sesión): RW-0005 confirmado como piloto.**

1.3 **Política de formato PDF -- corrección del texto original de este
    plan.** La política YA definida (`factory/docs/design/
    regulatory_redesign_v2/CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md`
    §4, "Estrategia por formato") NO es "PDF ⇒ DOCUMENT_GENERATION_BLOCKED"
    (eso es lo que decía la versión original de este §1.3, y es incorrecto
    frente al diseño real). La política real, ya implementada en
    `document_generation_strategy.py`:
    - PDF con fuente editable autorizada: modificar la copia editable
      directamente (hoy: ningún PDF de Rockwell tiene fuente editable
      conocida).
    - PDF sin fuente editable, `TEXT_NATIVE` (texto extraíble confiable):
      reconstruir versión editable vía `document_structure_extractor.py`
      + `candidate_document_generator.py` -- generar DOCX y PDF
      candidatos, registrar limitaciones de fidelidad.
      `generation_ready=True` (`PDF_RECONSTRUCTED_DOCX_AND_PDF`).
    - PDF sin fuente editable, `OCR_REQUIRED`/`NOT_EXTRACTABLE` (caso del
      escaneado `SAT3 Scanned-1.pdf`, 136.8 MB, 0 chars/página): **se
      bloquea** -- `GENERATION_BLOCKED_INSUFFICIENT_FIDELITY`, nunca se
      fuerza una reconstrucción de baja fidelidad. Esta es la única rama
      que corresponde a "PDF sin fuente editable ⇒ bloqueado" del texto
      original, y aplica solo quando la extracción no es confiable, no a
      todo PDF.
    Documentos del corpus real bajo cada rama: ver tabla de 1.1-1.2 arriba.

1.4 **Redimensionamiento Tier-1 para RW-0005 bajo H2H4:**
    - Chunks medidos (corrida real completa): **29**.
    - Requisitos aplicables medidos (corrida real completa, bucket por
      requisito del informe Tier-1): **5**
      (21_CFR_11.10(a), 11.10(d), 11.10(e), 11.10(g), 11.50_11.70).
    - H2H4 "desempaqueta" a 1 `requirement_id` por llamada
      (`chunked_engine.py` líneas ~990-1025) -- a diferencia de la corrida
      BASELINE ya hecha (1 llamada/chunk, todos los requisitos juntos, la
      que midió 0/7 recall y quedó `superseded`). Llamadas base bajo
      H2H4 = 5 requisitos × 29 chunks = **145 llamadas**.
    - Margen de reintento: tasa de violación de contrato observada en vivo
      = 3/3 (100%) en la muestra de R3-T1.8 bloque 4
      (`docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md`, línea ~562-570).
      Con esa tasa, presupuestar 1 reintento por llamada como caso
      esperado, no excepcional: **tope duro recomendado = 290 llamadas**
      (145 × 2).
    - Tiempo de pared: la corrida BASELINE completa de RW-0005 (29
      llamadas, 1/chunk, prompt más grande al empaquetar los 5 requisitos
      juntos) midió 409k-2.18M ms/llamada según la muestra
      (promedio ~1.54M ms ≈ 25.7 min/llamada en la corrida completa;
      409k-611k ms ≈ 7-10 min/llamada en corridas parciales de 5 chunks) y
      un elapsed real de ~18.5h de punta a punta (con pausas/reanudaciones
      entre checkpoints). **No hay una muestra real de latencia por
      llamada bajo H2H4** (prompt más chico, 1 solo requisito, schema
      mínimo -- se espera más rápida por llamada pero son 5x más
      llamadas que la corrida BASELINE). No se fabrica un número: la
      latencia real de H2H4 debe medirse con las primeras llamadas reales
      de la corrida (mismo mecanismo de checkpoint, fail-fast) antes de
      proyectar el total, tal como exige el §3.4/3.7 de este plan (no
      autorizar tiempo de pared sin dato real).
    - Solo dimensionamiento -- no se propone autorización todavía (regla
      del plan, §1.4).

```
PILOT_REVISED =   RW-0005 confirmado (Cesar, 2026-08-13)
PDF_POLICY =      documentada arriba, corrige el texto original de §1.3
                  (TEXT_NATIVE reconstruye; OCR_REQUIRED/NOT_EXTRACTABLE
                  bloquea -- no "todo PDF bloqueado")
PILOT_RUN_SIZING_REVISED =
                  145 llamadas base (5 req x 29 chunks, H2H4) / tope duro
                  recomendado 290 con margen de reintento (100% observado)
                  / tiempo de pared: sin dato real bajo H2H4, medir con
                  las primeras llamadas de la corrida antes de proyectar
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 (cont.) — §2, CHECKPOINT 2
──────────────────────────────────────────────────────────────────────────────

## §2 — Validación en frío de la cadena completa: COMPLETA, 0 llamadas LLM

Test real: `factory/tests/test_r4_t1_1v2_cold_chain_validation.py` (7 tests,
7 passed). Aislamiento verificado: `factory/layer9/review_queue.jsonl` real
sin tocar (mtime sin cambio, 0 coincidencias del hallazgo sintético),
`factory/layer9/remediation_directives.jsonl` real nunca se creó,
`factory/remediation_packages/` real sin entradas nuevas -- todo corrió
sobre `tmp_path` vía los fixtures `isolated_review_queue` (autouse,
conftest.py) + `_isolated_directives`/`_isolated_packages_and_audit`
(locales a este archivo, mismo patrón que
`test_remediation_directive_dispatch.py`/`test_remediation_package_service.py`).

**Autoría humana real:** la directiva (`propose_remediation_directive`) usa
`authored_by_id="cesar"`, `proposed_text`/`rationale` dictados literalmente
por Cesar en esta sesión (2026-08-13) -- este código nunca generó ni alteró
ese texto (`validate_identity()` rechaza cualquier identidad no-humana,
incluida `"claude"`, por diseño).

**Hallazgo intermedio -- HIGH_RISK, no un defecto:** Ruta D clasificó el
cambio como `HIGH_RISK` (`risk_basis=['evidence_status','gxp_impact']`:
`ABSENCE_CONFIRMED` + `DIRECT_GXP_IMPACT`, correcto para una adición sobre
una regulación vinculante). Bajo BATCH_AND_EXCEPTION esto exige revisión de
excepción humana antes de `AUTO_APPLIED_TO_DRAFT`. La decisión de excepción
(`accept_dry_run_pipeline_validation`) la tomó Capa 8 -- **explícitamente
NO** como juicio de riesgo GxP real (eso sigue siendo de QA/Cesar/Capa 9,
CLAUDE.md), sino como acción mecánica para ejercitar la cadena dentro de un
paquete `DRY_RUN_VALIDATION` aislado (`PROJECT_ID=RW-0005-DRY-RUN-VALIDATION`,
`tmp_path`, nunca liberado). Queda registrado así, literal, en el campo
`justification` de la excepción. v1 (sin excepción) probó primero la ruta de
exclusión real: el cambio HIGH_RISK NO entra al candidato sin excepción
revisada (`excluded_change_ids=[change_id]`, `EXCEPTION_REQUIRED`) -- v2
(excepción aceptada) probó la ruta de inclusión.

**Gap de diseño detectado (no corregido, solo registrado):**
`remediation_package_service.create_package()` reinicializa `exceptions={}`
en cada versión nueva -- una excepción aceptada en v1 NO se hereda
automáticamente a v2; hubo que registrar la misma decisión dos veces (una
por versión). No es un defecto de este plan corregirlo; queda como nota
para quien diseñe el siguiente ciclo de versionado de paquetes.

**Artefactos reales generados (disco, no producción):**
`factory/regulatory/pilot_run/dry_run_validation_r4_t1_1v2/` --
`v1_candidate_EXCLUDED_pending_exception.docx`,
`v1_redline_EXCLUDED_pending_exception.docx`,
`v2_candidate_INCLUDED.docx`, `v2_redline_INCLUDED.docx`.

### Criterios de aceptación (§2.3) -- los 8, con datos reales

a) **PASA** -- candidato y redline v2 se generan, se guardan en disco y se
   reabren (`python-docx Document(path)`), con contenido real.
b) **PASA** -- `NO_APROBADO_MARK` ("BORRADOR — NO APROBADO — pendiente de
   revisión QA") presente, verificado por reapertura, en candidato Y
   redline.
c) **PASA** -- `verify_document_conformance()` (reapertura real desde
   disco, no el objeto en memoria) confirma `DOCUMENT_CONFORMANCE` para el
   único change_id; el texto literal de Cesar aparece verbatim en el
   candidato.
d) **PASA** -- SHA-256 de `RW-0005...FS_v1.2.pdf` idéntico antes y después
   de toda la corrida (`56095a75...`), y coincide con el registrado en la
   allowlist.
e) **PASA** -- trazabilidad completa verificada por identidad de campos:
   `insertion_manifest.change_id == RemediationChange.change_id ==
   RemediationChange.finding_id == RemediationDirective.directive_id`, y
   `RemediationDirective.finding_rc_id` resuelve al hallazgo sintético real
   en la cola aislada.
f) **PASA** -- ambos `ArtifactReference` (candidate/redline) con SHA-256 y
   tamaño reales calculados sobre los bytes en disco;
   `insertion_manifest[0].proposed_content_sha256` coincide con el
   `proposed_content` real del cambio.
g) **PASA** -- `create_release_record()` existe en
   `remediation_package_service.py` pero NO está conectado a ningún
   endpoint (`factory/api/routes/remediation_packages.py` lo declara a
   propósito); este test tampoco la invocó nunca. `package_decision=None`
   en el estado final; ningún archivo `releases*` se creó.
h) **PASA** (4 pruebas separadas, todas con la directiva real de Cesar como
   base, mutada un campo a la vez):
   - `change_type=DELETE` → `RemediationDirectiveError`.
   - `regulatory_citation=[]` (sin cita) → `RemediationDirectiveError`.
   - `original_text` que no ancla literalmente en páginas 40-44 del PDF
     real → `RemediationDirectiveError`.
   - `document_sha256` desactualizado (`"0"*64`) → `DirectiveNotDispatchable`
     en el dispatch (re-verificación de drift contra el SHA-256 vivo).

```
COLD_CHAIN_VALIDATION = a) PASA b) PASA c) PASA d) PASA e) PASA f) PASA
                         g) PASA h) PASA (4/4 sub-casos)
NO_APROBADO_MARK =       estampada y verificada por reapertura (candidato Y redline)
ORIGINAL_INTACT =        SHA-256 56095a7541fbb62e30d00e77308fde4c2ac0f4ec945adbf19a968b79debc82eb, sin cambio
RELEASE_NEVER_REACHED =  true (endpoint no conectado, función nunca invocada)
LLM_CALLS_THIS_RUN =     0
ISOLATION_VERIFIED =     review_queue.jsonl real sin tocar (mtime sin cambio) /
                         remediation_directives.jsonl real nunca creado /
                         remediation_packages/ real sin entradas nuevas
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

>>> CHECKPOINT 2: CERRADO. Paquete de validación en frío completo,
>>> 8/8 criterios PASA, cero contaminación de estado real, cero llamadas LLM.
>>> Pendiente de aprobación de Cesar antes de avanzar a §3 (pre-vuelo Tier-1).

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 (cont.) — §3, PRE-VUELO (verificación, sin implementar)
──────────────────────────────────────────────────────────────────────────────

Verificación de solo lectura (código + tests + decisiones reales en disco),
sin tocar código ni firmar nada. Resultado por punto:

**3.1 Cadena posterior demostrada — VERDE.** §2 completo, 8/8 PASA.

**3.2 Endpoint vivo (§0, VERDE) + UI de adjudicación — ROJO.** No existe
ningún panel de adjudicación humana para directivas/paquetes de remediación
en `factory/ui/js/mission_control/`. Búsqueda exhaustiva de
`remediation_directive`/`RemediationDirective`/`directive` en `*.js`: 0
resultados (la única mención de "remediation" en toda la UI es un botón de
descarga de PDF ya existente, `gmpai_artifacts.js:302`, no relacionado). Sin
esto, la corrida Tier-1 produciría directivas que nadie puede revisar ni
firmar desde Mission Control — el mismo patrón de riesgo que ya causó el
incidente "Hallazgo no encontrado" de R3-T1.7, ahora un nivel más adelante en
la cadena. **Bloqueante real para §3.8.**

**3.3 Perfil H2H4 enforced — VERDE, con precisión sobre CUÁL runner.**
`run_corpus_batch()` (el runner de corpus completo/producción, familia
`CORPUS_AUTHORIZATION`) NO pasa `evaluation_profile` a `evaluate_chunked()`
— usa el default `"BASELINE"` sin excepción; ese runner no aplica aquí
(`CORPUS_READY=false`, no es el que se usa para un piloto). El runner
correcto para esta corrida es `run_pilot_sample_batch()` (familia
`PILOT_EXECUTION`, deliberadamente aislada de `CORPUS_AUTHORIZATION`/D4-A —
`test_pilot_sample_batch_consulta_solo_pilot_execution` revienta si
consultara la familia equivocada), que sí propaga
`evaluation_profile='H2H4'` y `target_requirement_ids=[unit.requirement_id]`
por unidad — confirmado por
`test_run_pilot_sample_batch_h2h4_pasa_el_requirement_id_de_la_unidad` y el
resto de `test_evaluation_profile_h2h4.py` (9 tests, incluida la parametría
que un `evaluation_profile` distinto invalida el checkpoint y no reanuda).

**3.4 Presupuesto + hard stops — VERDE el mecanismo, PENDIENTE el número
real.** `test_hard_stop_usa_max_calls_de_pilot_execution_no_compute_d4a`
confirma que el runner del piloto lee el tope duro de `max_calls` del
payload de la `PILOT_EXECUTION` vigente y NUNCA de `compute_d4a()` (eso es
solo para el runner de corpus completo). Ya existen 18 decisiones
`PILOT_EXECUTION` `ACTIVE` para RW-0005 en `decisions_v2.jsonl`, todas de
corridas de experimentación previas (`max_calls` entre 1 y 60 según la
corrida) — **ninguna** con el tope dimensionado en §1.4 para el Tier-1 H2H4
real (145 base / 290 con reintento). Correcto que no exista todavía: esa
decisión se crea y se firma recién en §3.8, no antes.

**3.5 Ejecución en background desacoplada + supervivencia a SSH —
INFRAESTRUCTURA EXISTE, SUPERVIVENCIA NO VERIFICADA.**
`factory/scripts/ops/run_corpus_pilot.py` (entrypoint standalone, solo
importa el paquete `factory`, pensado para `systemd-run`/`tmux`) +
`factory/scripts/ops/pilot_status.sh` (lectura pura desde cualquier sesión
SSH nueva, PID + checkpoints + log) están construidos y son coherentes con
el diseño. Pero no se encontró evidencia escrita (log, reporte, docs_plan)
de una corrida real que haya sobrevivido efectivamente un cierre de SSH con
este mecanismo — ni para RW-0005 ni para otro documento. La corrida BASELINE
histórica de RW-0005 (18.5h, `chunked-943a62bcbb85`) corrió con
pausas/reanudaciones entre checkpoints, lo cual es consistente con
haber sobrevivido cortes, pero no está documentado como una verificación
deliberada de supervivencia. **Falta la prueba explícita que pide el plan
("verificación de supervivencia a cierre de SSH ANTES de dejarla sola")
antes de confiar en esto para 8-12h reales.**

**3.6 Checkpoint por requisito + resume por fingerprint, fail-closed —
VERDE.** A nivel de motor (`chunked_engine.py`, usado por ambos runners):
`test_checkpoint_from_older_prompt_version_never_resumed`,
`test_evaluate_chunked_starts_fresh_run_when_checkpoint_fingerprint_mismatches`,
`test_checkpoint_with_matching_fingerprint_resumes_normally`
(`test_checkpoint_fingerprint_invalidation.py`) + el caso específico de H2H4
(`test_cambiar_de_perfil_invalida_el_checkpoint_y_no_reanuda`,
`test_evaluation_profile_h2h4.py`): cambiar de perfil o de versión de prompt
invalida el checkpoint y fuerza una corrida nueva en vez de reanudar mal —
fail-closed real, no solo declarado.

**3.7 Criterio de éxito pre-fijado — FIRMADO por Cesar (2026-08-13).**
Versión revisada (no la primera propuesta): corrige dos defectos de la
propuesta inicial -- mezclaba tres desenlaces distintos bajo un solo
"fracaso diagnosticable" (presupuesto agotado, fallo técnico y ausencia de
hallazgos no son lo mismo ni piden la misma acción), y no calibraba contra
el único dato real ya disponible (la corrida BASELINE de RW-0005:
0 confirmados, 4 `needs_human_review`, 1 `cross_reference`).

- **ÉXITO DE INFRAESTRUCTURA (mínimo, siempre exigible):** la corrida
  completa sus 145 llamadas (o se detiene en un hard-stop bien
  diagnosticado) con auditoría íntegra y checkpoints resumibles, cero
  fallos técnicos sin recuperar.
- **ÉXITO ÚTIL (objetivo del roadmap):** al menos 1 hallazgo con evidencia
  anclada que llegue a `pending_human_review` -- calibrado contra el
  resultado real ya obtenido en BASELINE (4 `needs_human_review`,
  1 `cross_reference`, 0 confirmados); bajo H2H4 se espera igual o mejor
  por diseño (1 requisito por llamada, prompt más enfocado), pero no es una
  promesa.
- **Tres desenlaces distintos, cada uno con su propia acción -- nunca un
  solo cubo de "fracaso":**
  (a) fallo técnico no recuperado / checkpoint corrupto → corregir antes de
      reintentar;
  (b) `HARD_STOP_CALLS`/`HARD_STOP_WALL_TIME` con checkpoint sano → no es
      un fracaso, se retoma con el mismo checkpoint tras autorizar más
      presupuesto;
  (c) corrida completa (145/145) sin ningún hallazgo adjudicable → dato
      honesto sobre el recall real bajo H2H4 en este documento, exactamente
      la pregunta que R2 del roadmap existe para responder -- se registra
      tal cual, sin inflar ni descartar.

```
CRITERIO_EXITO_37 = FIRMADO (Cesar, 2026-08-13, version revisada)
```

**3.8 — NO ALCANZADO EN ESTE MOMENTO DEL DOCUMENTO.** (Snapshot original al
cerrar la primera pasada de §3; SUPERADO por las secciones fechadas
2026-08-13 más abajo -- "§3.2 CERRADO", "§3.5 CERRADO" y la firma de §3.7
justo arriba. Se deja este bloque sin reescribir para no borrar el rastro
de auditoría de cómo se cerró cada bloqueante; el estado consolidado real
está en el bloque siguiente.)

```
PREFLIGHT (snapshot en este punto, ya superado) =
  3.1 VERDE / 3.2 ROJO (sin UI) / 3.3 VERDE (vía run_pilot_sample_batch)
  / 3.4 VERDE-mecanismo, número pendiente de §3.8
  / 3.5 AMARILLO (infra existe, supervivencia SSH no verificada)
  / 3.6 VERDE / 3.7 propuesta redactada, sin firmar / 3.8 NO ALCANZADO
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
ESTADO CONSOLIDADO DE §3 TRAS 3.2/3.5/3.7 (2026-08-13)
──────────────────────────────────────────────────────────────────────────────

```
PREFLIGHT = 3.1 VERDE / 3.2 VERDE (panel de adjudicación construido y
            verificado en vivo) / 3.3 VERDE / 3.4 VERDE-mecanismo (número
            real pendiente de crearse/firmarse EN §3.8, no antes)
            / 3.5 VERDE (supervivencia SSH probada en vivo, systemd-run
            --user + linger=yes) / 3.6 VERDE / 3.7 FIRMADO (Cesar,
            version revisada) / 3.8 SIGUIENTE PASO -- aún no propuesto
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

>>> 3.1–3.7 en VERDE. Único paso pendiente antes de operar la corrida
>>> Tier-1: §3.8 -- proponer formalmente la autorización a Cesar con el
>>> número exacto de llamadas (145 base / 290 tope duro) y horas (sin dato
>>> real de latencia bajo H2H4 todavía -- §1.4), y DETENERSE para su firma.
>>> §4 (familia de gobernanza de la directiva + política PDF formal) sigue
>>> pendiente, en paralelo, para el mismo ciclo de firma.

──────────────────────────────────────────────────────────────────────────────
PROPUESTA 2026-08-13 (ARQ) — §3.8 con tres opciones + §4 preparado, SIN EJECUTAR
──────────────────────────────────────────────────────────────────────────────

Pedido explícito de Cesar: preparar §3.8 y §4 sin ejecutar ninguna corrida,
sin llamadas LLM, sin generar documentos reales, sin commit. Todo lo que
sigue es propuesta -- ninguna decisión tomada aquí.

## CALL_FORMULA

`llamadas_base = requisitos_aplicables_al_documento × chunks_del_documento`
(H2H4 desempaqueta 1 requisito por llamada -- `target_requirement_ids=
[unit.requirement_id]`, `chunked_engine.py` ~990-1025 -- a diferencia de
BASELINE, que empaqueta los 5 requisitos en una sola llamada por chunk).
`tope_duro = llamadas_base × (1 + margen_de_reintento)`.

## WHY_145_BASE

Documento: **RW-0005** (`FS_v1.2.pdf`). Formato: **PDF `TEXT_NATIVE`**,
reconstruido vía `PDF_RECONSTRUCTED_DOCX_AND_PDF` (§1.3) -- no editable en
origen, pero con extracción de estructura confiable y generador probado
E2E. Chunks: **29** (medido, no estimado -- corrida BASELINE real completa
`chunked-943a62bcbb85`). Requisitos aplicables: **5** -- `21_CFR_11.10(a)`,
`11.10(d)`, `11.10(e)`, `11.10(g)`, `11.50_11.70` (bucket real del informe
Tier-1 BASELINE, no una estimación de matriz). `5 × 29 = 145`.

## WHY_290_HARD_CAP

Margen de reintento tomado de un dato real, no supuesto: tasa de violación
de contrato observada en vivo = **3/3 (100%)** en la muestra de R3-T1.8
bloque 4 (`docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md`, ~línea
562-570). Con esa tasa, 1 reintento por llamada es el caso ESPERADO, no la
excepción → `145 × 2 = 290`.

**Tiempo de pared -- sin dato real bajo H2H4.** Único dato real disponible
es de BASELINE (1 llamada/chunk, los 5 requisitos empaquetados, prompt
mayor): 409k-2.18M ms/llamada, promedio ~1.54M ms (~25.7 min) en la corrida
completa; 409k-611k ms (~7-10 min) en corridas parciales de 5 chunks;
elapsed real ~18.5h de punta a punta (con pausas/reanudaciones). H2H4 tiene
un prompt más chico (1 solo requisito, schema mínimo) pero 5× más llamadas
-- se espera más rápido por llamada, pero **no se fabrica un número**: los
rangos de tiempo abajo usan el dato de BASELINE como cota superior no
verificada, nunca como promesa.

## OPTION_A_MINIMAL

- **Alcance:** `21_CFR_11.10(e)` -- el único requisito con patrón de señal
  REAL ya documentado en BASELINE (chunk 20, páginas 45-46,
  `SUPPORTING_EVIDENCE_UNDER_REVIEW`, `docs_plan/R3_T1_3_VIABILIDAD_F2.md`
  líneas 86-109; mismo patrón confirmado también en `11.10(d)`, línea
  182-184) -- × 3 chunks (19, 20, 21: el chunk con señal real más sus dos
  vecinos inmediatos, sin ampliar el alcance).
- **CALLS_BASE:** 3 (1 requisito × 3 chunks). **HARD_CAP:** 6.
- **TIEMPO ESTIMADO:** ~21-30 min base (proxy BASELINE parcial, no
  verificado); ~42-60 min en el peor caso con reintentos.
- **QUÉ PREGUNTA RESPONDE:** ¿el pipeline H2H4 completo (dispatch →
  `chunked_engine` con `target_requirement_ids` → `evidence_verifier` →
  checkpoint) produce, en el punto EXACTO donde ya se sabe que hay señal
  real, un hallazgo con evidencia anclada que llega a
  `pending_human_review`? Da además el PRIMER dato real de latencia por
  llamada bajo H2H4.
- **QUÉ NO DEMUESTRA:** nada sobre el recall del documento completo ni de
  los otros 4 requisitos; muestra elegida a mano (no aleatoria) -- no
  generaliza "H2H4 funciona en cualquier parte"; no ejercita el hard-stop a
  escala real; no valida checkpoint/resume bajo carga de 29 chunks.
- **CRITERIO DE ÉXITO:** ≥1 hallazgo con evidencia anclada en
  `pending_human_review` sobre `11.10(e)` en ese rango (coherente con el
  patrón ya visto en BASELINE) + auditoría/checkpoint íntegros.
- **CRITERIO DE PARADA:** al llegar a 6 llamadas (tope duro) o completar
  las 3 unidades planeadas, lo que ocurra primero; cualquier fallo técnico
  no recuperado detiene la corrida de inmediato.
- **RIESGO:** costo casi nulo; riesgo de sobregeneralizar una muestra tan
  pequeña -- mitigado porque el criterio de éxito de A es explícitamente
  solo sobre infraestructura + ese punto conocido, no sobre recall global.
- **RECOMENDACIÓN TÉCNICA:** ejecutar primero, siempre -- es la única
  opción que da un dato real de latencia H2H4 antes de comprometer
  cualquier presupuesto mayor.

## OPTION_B_INTERMEDIATE

- **Alcance:** `21_CFR_11.10(e)` completo × las 29 chunks reales del
  documento (un requisito, documento entero).
- **CALLS_BASE:** 29 (1 requisito × 29 chunks). **HARD_CAP:** 58.
- **TIEMPO ESTIMADO:** ~3.4h-12.4h base (mismo proxy no verificado);
  ~6.8h-24.8h peor caso con reintentos. Si A ya midió latencia real de
  H2H4, este rango se reemplaza por el dato real antes de autorizar B.
- **QUÉ PREGUNTA RESPONDE:** ¿cuál es el recall real medido de RW-0005 para
  UN requisito completo (`11.10(e)`) bajo H2H4, a escala real del
  documento, y se sostiene la mecánica de checkpoint/resume/hard-stop a esa
  escala?
- **QUÉ NO DEMUESTRA:** no cubre los otros 4 requisitos -- no da una foto
  completa del recall del documento; el resultado de un requisito no es
  necesariamente representativo de los otros 4 (distinta norma, distinta
  densidad de evidencia).
- **CRITERIO DE ÉXITO:** recall medido y documentado para `11.10(e)` sobre
  las 29 chunks reales (incluso 0 hallazgos confirmados es un dato válido
  si la corrida es técnicamente íntegra) + ≥1 resume real por fingerprint
  ejercitado.
- **CRITERIO DE PARADA:** `HARD_STOP_CALLS` a 58, o completar las 29
  unidades; fallo técnico no recuperado detiene de inmediato.
- **RIESGO:** costo medio (horas, no un día); mismo riesgo de
  sobregeneralizar un requisito al resto, pero como es un requisito
  COMPLETO el dato de recall en sí ya es válido (no una muestra parcial de
  ese requisito).
- **RECOMENDACIÓN TÉCNICA:** solo si A confirma que la infraestructura
  funciona y produce el hallazgo esperado en el punto conocido -- paso
  siguiente natural, no un salto directo desde cero.

## OPTION_C_FULL (145/290)

- **Alcance:** los 5 requisitos aplicables × 29 chunks -- el dimensionado
  ya calculado en §1.4.
- **CALLS_BASE:** 145. **HARD_CAP:** 290.
- **TIEMPO ESTIMADO:** ~16.9h-62h base (mismo proxy no verificado, que
  además probablemente SOBRESTIMA por llamada de H2H4 porque BASELINE
  empaqueta 5 requisitos por llamada); hasta ~124h teóricas con reintentos
  al 100% -- techo poco realista como piso operativo real (el hard-stop de
  tiempo de pared de D4-A cortaría antes), pero ilustra que sin dato real
  el rango es enorme.
- **QUÉ PREGUNTA RESPONDE:** recall real completo de RW-0005 sobre los 5
  requisitos bajo H2H4 -- comparable directamente contra la medición
  BASELINE (0/7 recall, `superseded`) para saber si desempaquetar por
  requisito mejora el recall medido.
- **QUÉ NO DEMUESTRA:** nada sobre los otros 13 documentos del corpus; no
  valida el panel de adjudicación (§3.2) a escala real de un piloto
  completo -- eso se prueba usándolo con datos reales, aparte.
- **CRITERIO DE ÉXITO / PARADA:** los ya firmados en §3.7.
- **RIESGO:** alto en costo (horas reales, ventana de supervisión larga) Y
  en que el estimado de tiempo NO está verificado -- autorizar C sin haber
  medido latencia real de H2H4 (con A o B) es autorizar un rango que hoy es
  extrapolación, no medición.
- **RECOMENDACIÓN TÉCNICA: NO autorizar todavía.** Solo se justifica
  después de que A (y probablemente B) den una medición real de latencia y
  una primera señal de hallazgos reales bajo H2H4. Ejecutar C a ciegas
  repetiría el error de dimensionamiento que motivó reabrir este plan
  (elegir alcance antes de tener el dato barato).

## RECOMMENDED_OPTION

**A**, y solo después reevaluar con Cesar si procede B; C queda fuera de
alcance hasta tener datos reales de A y, probablemente, B.

──────────────────────────────────────────────────────────────────────────────
§4 — PREPARADO, NO DECIDIDO
──────────────────────────────────────────────────────────────────────────────

**4.1 Familia de gobernanza de la directiva.** Hallazgo real (lectura de
código, no solo análisis): `propose_remediation_directive()`
(`factory/services/remediation_directive.py`) HOY no consulta NINGUNA
familia de gobernanza -- cero `resolver.resolve(...)` en ese módulo, a
diferencia de `create_package()`/dispatch. Solo está protegida por
`identity_policy` (rechaza identidades no humanas) y los validadores de
anclaje/cita. `REMEDIATION_PACKAGE_GENERATION` (`d8b8e5c`) NO la cubre
mecánicamente: `target_kind=package_id`, consumidor=
`remediation_package_creation` -- una directiva no tiene `package_id`
(existe antes del paquete, antes del dispatch). **Recomendación a firmar:**
familia nueva `REMEDIATION_DIRECTIVE_AUTHORSHIP`, `target_kind=
finding_rc_id`, consumidor `remediation_directive_creation`,
`requires_human_confirmation=true` -- mismo criterio que ya separó
`EMBED_EXECUTION` de `PILOT_EXECUTION` y D5 de
`REMEDIATION_PACKAGE_GENERATION` ("acciones semánticamente distintas no
comparten familia", comentario textual ya en
`decision_families.yaml:172-174`). **Alternativa:** si Cesar prefiere NO
añadir gobernanza formal aquí (dado que ya exige identidad humana +
validadores de contenido), dejar eso escrito como decisión de diseño
explícita, no como vacío sin decidir.

**4.2 Política PDF `DOCUMENT_GENERATION_BLOCKED`.** Ya documentada como
corrección en §1.3 de este plan y ya implementada en código
(`document_generation_strategy.py`). Hallazgo real: NO está registrada como
decisión formal en ningún lado -- 0 coincidencias del nombre del spec en
`decisions_v2.jsonl`, ninguna entrada W5. **Recomendación:** confirmarla
vía el mecanismo YA EXISTENTE `ARTIFACT_VERSION` sobre
`factory/docs/design/regulatory_redesign_v2/
CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md` §4 -- no hace falta
familia nueva, `target_kind=artifact_id` ya encaja.

**4.3** Presentar 4.1+4.2 junto al pre-vuelo (§3.8), un solo ciclo de firma
-- sin cambios sobre el texto original del plan.

```
SECTION_3_8_PROPOSAL = A/B/C detalladas arriba, ninguna autorizada
SECTION_4_GOVERNANCE_PACKAGE = 4.1 + 4.2 preparados arriba, sin decidir
EXECUTION_STATUS = NOT_EXECUTED (cero LLM, cero Tier-1, cero documentos
                    reales generados, cero decisiones nuevas creadas)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
HALLAZGO CRÍTICO 2026-08-13 — Option A YA SE EJECUTÓ (PILOT_EXECUTION-2026-018)
──────────────────────────────────────────────────────────────────────────────

Antes de redactar el borrador de autorización de Option A pedido por Cesar,
se verificó si ya existía algo equivalente -- SÍ existe:
`PILOT_EXECUTION-2026-018` (`decisions_v2.jsonl`, `status=ACTIVE`,
`approved_by_id=cesar`, firmada 2026-08-12) autorizó EXACTAMENTE el mismo
experimento (RW-0005, `21_CFR_11.10(e)`, H2H4, tope 6) y **se ejecutó por
completo el 2026-08-12** (`docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md`,
bloque 4): 6 de 6 llamadas reales usadas, sin exceder lo firmado.

**Latencia H2H4 real, extraída de los checkpoints reales en disco
(`factory/regulatory/pilot_run/checkpoints/chunked-{2678358a06b3,
e6994ea8e953,d9b5bc77c9db,c2c7dff6900c,e8208618982a}.checkpoint.json`,
campo `wall_clock_ms`, no un log narrativo):**
```
6 llamadas reales, ok=True las 6:
  886849 ms (~14.8 min), 392389 ms (~6.5 min), 376852 ms (~6.3 min),
  618177 ms (~10.3 min), 404186 ms (~6.7 min), 636999 ms (~10.6 min)
promedio = 552575 ms ≈ 9.2 min/llamada -- PRIMER DATO REAL de latencia
H2H4 que este plan pedía en §1.4/§3.4, ya existente desde ayer.
```

**Señal en el chunk ancla (páginas 45-46, el mismo que R3_T1_3 identificó
con evidencia real):** probado 3 veces de forma independiente
(`chunked-2678358a06b3`, `chunked-c2c7dff6900c` chunk 0,
`chunked-e8208618982a`) -- las 3 veces el ancla de la cita PASA
(`a_anchor=PASS`), pero el bucket final queda `EVALUATION_INCOMPLETE` /
`ABCD_D_NOT_ASSESSABLE` porque el modelo devuelve los criterios 2 y 3
(`MET` con `evidence_quote` real) con `evidence_location` VACÍO --
violación de contrato Nivel A, bloqueada correctamente por el validador
(mismo patrón ya documentado en F1, NO un defecto de Bloques 0-3). Es
decir: **el "hallazgo adjudicable" que Option A busca demostrar en ese
punto concreto ya se intentó 3 veces y las 3 veces quedó bloqueado por
esta causa** -- información real, no hipotética.

**Consecuencia para el borrador pedido:** proponer una autorización nueva
de 6 llamadas sobre el mismo requisito/documento, apuntando otra vez al
mismo ancla o a sus vecinos inmediatos, repetiría un experimento cuyo dato
principal (latencia real) YA EXISTE y cuyo resultado en el punto conocido
(bloqueo por contrato, 3/3) ya es información suficientemente robusta.
Gastar 6 llamadas reales nuevas sin una pregunta nueva que responder
contradice el principio que sostiene todo este plan ("no gastar
presupuesto real sin necesidad") y el propio precedente de Cesar en
R3-T1.8 ("decidió explícitamente NO gastar las 2-3 llamadas adicionales
propuestas, dado el cierre ya alcanzado con los datos existentes").

──────────────────────────────────────────────────────────────────────────────
DECISIÓN DE CESAR 2026-08-13 — §3.8 CERRADO: Option A satisfecha sin gasto nuevo
──────────────────────────────────────────────────────────────────────────────

Cesar decide: cerrar Option A como ya satisfecha por `PILOT_EXECUTION-
2026-018` (ejecutada 2026-08-12, R3-T1.8 bloque 4). **No autoriza** ninguna
llamada nueva -- ni la variante chica de 2 llamadas, ni B, ni C, ni 145/290.

```
OPTION_A_STATUS =            SATISFIED_BY_EXISTING_RUN
SOURCE_RUN =                 PILOT_EXECUTION-2026-018 (firmada por cesar,
                              2026-08-12; ejecutada el mismo día, R3-T1.8
                              bloque 4, 6/6 llamadas usadas, sin exceder)
NEW_LLM_CALLS_AUTHORIZED =   0
NEXT_LLM_RUN =                NOT_AUTHORIZED
```

**Datos reales que cierran Option A (extraídos de checkpoints en disco,
`wall_clock_ms`, no de un log narrativo):**
- 6 llamadas H2H4 reales, las 6 `ok=True`: 886849 / 392389 / 376852 /
  618177 / 404186 / 636999 ms.
- Promedio: 552575 ms ≈ **9.2 min/llamada** -- objetivo de latencia H2H4 de
  Option A CUMPLIDO con datos reales, no un proxy de BASELINE.
- Patrón de bloqueo consistente: 3/3 llamadas sobre el chunk ancla
  (páginas 45-46) devolvieron los criterios 2 y 3 `MET` con
  `evidence_quote` real pero `evidence_location` VACÍO -- violación de
  contrato Nivel A, bloqueada correctamente por el validador (NO aflojado
  -- mismo patrón ya documentado en F1, reproducido de forma independiente).
- Señal real en `21_CFR_11.10(e)`: `a_anchor=PASS` (match `normalized`),
  cita real UR3.3.1/UR3.3.2 -- el ancla SÍ se reconoce correctamente bajo
  H2H4; lo que bloquea el bucket final es el contrato de criterios, no la
  detección de la cita.

**Corrección de lectura sobre RW-0005 (Cesar, explícita):** RW-0005 sí
puede usarse como piloto técnico -- el flujo PDF `TEXT_NATIVE` reconstruido
ya fue probado E2E (§1 de este plan). Pero **Option A nunca fue, ni es, el
gate de generación de R4** -- es únicamente un dato de
infraestructura/latencia/señal. Que el pipeline responda en ~9.2 min/llamada
y reconozca el ancla correctamente no autoriza `remediation_directive` real
ni `create_package()` sobre ningún hallazgo de esta prueba -- esa distancia
de escala y propósito sigue intacta (5 requisitos × 29 chunks reales para
un piloto de generación real, no 1 requisito × 1-3 chunks exploratorios).

```
LATENCY_H2H4_RECORDED =              9.2 min/llamada (promedio real, 6/6),
                                      rango 6.3-14.8 min
CONTRACT_VIOLATION_PATTERN_RECORDED = evidence_location vacío en
                                      criterios MET, 3/3 en el chunk ancla,
                                      bloqueo correcto del validador
SIGNAL_21_CFR_11_10_E =              a_anchor=PASS, cita real anclada;
                                      bucket final bloqueado por contrato,
                                      no por ausencia de evidencia
R4_GENERATION_GATE =                 SIN CAMBIOS -- sigue sin alcanzarse;
                                      Option A no lo sustituye
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

>>> §3.8 CERRADO sin gastar una sola llamada nueva. Queda §4 -- los dos
>>> paquetes de gobernanza (familia de la directiva + política PDF)
>>> preparados como propuesta/diff, sin aplicar, esperando firma de Cesar.

──────────────────────────────────────────────────────────────────────────────
DECISIÓN DE CESAR 2026-08-13 — §4: aplicado 1 de 2 -- el otro BLOQUEADO
──────────────────────────────────────────────────────────────────────────────

Cesar aprobó ambos ("aplica el diff y el payload"). Antes de ejecutar el
segundo se encontró un bloqueo real que no existía en el momento de
proponerlo -- se corrige aquí en vez de forzarlo.

**4.1 REMEDIATION_DIRECTIVE_AUTHORSHIP -- APLICADO.**
`factory/registry/decision_families.yaml`: familia nueva agregada tal cual
el diff aprobado, MÁS un ajuste no anticipado en el diff original --
`known_consumers` también necesitaba `remediation_directive_creation`
(`test_t24_every_declared_consumer_is_a_known_one`, sin xfail, lo exige).
Verificado en vivo: `test_decision_resolver_no_bypass.py` +
`test_decision_model_v2.py` -- **64 passed, 1 xfailed** (el xfail es el
mismo `test_t24_declared_consumers_have_a_wired_module` que YA fallaba a
propósito antes de este cambio -- `remediation_directive_creation` queda
sin cablear al resolver, mismo estado que `package_regeneration`, deuda
declarada, no nueva).

**4.2 PDF_POLICY vía ARTIFACT_VERSION -- NO APLICADO, bloqueo real
encontrado al intentar ejecutarlo.** `factory/core/artifact_version_guard.
py::enumerate_artifacts()` gobierna EXACTAMENTE 5 clases enumerables por
código (catálogo, evidence_pack, applicability_matrix, prompt,
golden_dataset) -- `CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md` NO es
ninguna de esas cinco. El archivo tampoco tiene versión propia embebida
(a diferencia de los YAML gobernados, que sí la tienen -- `catalog_version`,
`prompt_version`, etc.). Proponer `ARTIFACT_VERSION` sobre él habría exigido
inventar un `from_version`/`to_version` sin respaldo real -- exactamente lo
que el propio comentario del guard prohíbe ("Inventarle un '1.0' sería
fabricar una trazabilidad que nadie firmó") y produciría una propuesta
huérfana que ningún reconciliador (`check_artifact`/`latest_record_for`)
podrá resolver jamás -- el mismo antipatrón que
`governance_service.propose()` documenta como ya ocurrido una vez ("32
propuestas D1 huérfanas y cero firmas"). Se detiene aquí en vez de crear
ese mismo problema una segunda vez.

```
SECTION_4_1_STATUS = APPLIED (decision_families.yaml, verificado con tests
                      reales, sin commit)
SECTION_4_2_STATUS = BLOCKED -- mecanismo ARTIFACT_VERSION no cubre este
                      artefacto; requiere decisión de Cesar sobre la
                      alternativa antes de continuar
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
DECISIÓN DE CESAR 2026-08-13 (cont.) — §4.2 vía D6 en el almacén W5
──────────────────────────────────────────────────────────────────────────────

Segunda corrección antes de ejecutar: el almacén W5 (`w5_human_decisions.
py`) tampoco es un mecanismo genérico -- `DECISION_IDS` es una tupla FIJA
de 5 valores en código, con título/contexto hardcodeados por
`decision_id`, documentado literalmente como "Superficie mínima gobernada
para las 5 decisiones humanas de W5 V2". Añadir una 6ª exige el mismo tipo
de cambio de código que la opción de `ARTIFACT_VERSION` descartada --
presentarla como "sin cambios de código" en la pregunta anterior fue un
error, corregido antes de tocar nada. `RECORD_ANNOTATION` tampoco sirve:
está diseñada deliberadamente inerte (`never_authorizes`, sin exigir
confirmación humana), para anotar defectos del propio registro, no para
decisiones reales.

Cesar eligió, con esta corrección ya sobre la mesa: **agregar
`D6_pdf_generation_policy` a `DECISION_IDS`**, mismo patrón que D1-D5.

**Aplicado en `factory/services/w5_human_decisions.py`:**
- `DECISION_IDS`: `+ "D6_pdf_generation_policy"`.
- `_TITLES["D6_pdf_generation_policy"]` = "Política de generación para PDF
  sin fuente editable".
- `_STATIC_CONTEXT["D6_pdf_generation_policy"]`: resume la política real
  (`TEXT_NATIVE` reconstruye, `OCR_REQUIRED`/`NOT_EXTRACTABLE` bloquea),
  cita la corrección explícita frente al texto original de §1.3 ("NO es
  'todo PDF bloqueado'"), y referencia
  `CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md §4` como fuente.

**Verificado con tests reales, no solo sintaxis:**
`test_w5_human_decisions.py` (35 passed) +
`test_decision_resolver_no_bypass.py` + `test_decision_model_v2.py`
(99 passed, 1 xfailed -- el mismo xfail preexistente). La UI
(`w5_decisions.js`) y el endpoint (`layer9.py POST /w5-decisions/
{decision_id}`) son genéricos por `decision_id` -- D6 se renderiza y
registra sin ningún cambio adicional de UI/API.

**Nota arquitectónica, no resuelta, para que Cesar la pese:** D1-D5 son un
conjunto cerrado de decisiones de UN proceso específico (W5 V2). D6 es la
primera decisión de un tema distinto (política de generación de
candidatos, R4-T1) metida en ese mismo almacén -- funciona, pero estira el
alcance original del módulo. No se deshace nada de esto sin instrucción
explícita; se deja constancia para que quede documentado, no para
revertirlo por cuenta propia.

**Pendiente, deliberadamente NO ejecutado:** `record_decision(
"D6_pdf_generation_policy", decision=..., approved_by=...)` -- el acto de
FIRMA real exige la identidad real de Cesar como `approved_by`
(`_validate_identity` rechaza cualquier nombre genérico o no-humano); nadie
más que Cesar puede disparar ese acto.

```
D6_DEFINED =         true (código + tests reales, sin commit)
D6_SIGNED =           false -- pendiente del acto de firma real de Cesar
LLM_CALLS_EXECUTED = 0
EXECUTION_STATUS =   PARTIALLY_EXECUTED (código de gobernanza aplicado,
                     sin firma real, sin commit, cero LLM, cero Tier-1)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 (cont.) — §3.2 CERRADO: panel mínimo de adjudicación
──────────────────────────────────────────────────────────────────────────────

Cesar pidió construir primero el panel mínimo de adjudicación (bloqueante
3.2). Alcance deliberado: SIN backend nuevo -- solo los endpoints ya reales
(`POST/GET /remediation/directives`, y los tres de
`remediation_packages.py`: excepción HIGH_RISK / lote MEDIUM_RISK / decisión
final). Nunca invoca `create_release_record()` (sigue sin conectar a ningún
endpoint) -- el panel lo dice explícitamente en su cabecera.

**Archivos:**
- `factory/ui/js/mission_control/remediation.js` (nuevo) -- lista de
  directivas de solo lectura + búsqueda manual de UN paquete por
  (project_id, package_id, version) (no existe endpoint de listado de
  paquetes todavía) + los tres formularios de adjudicación (excepción por
  `change_id` HIGH_RISK, lote MEDIUM_RISK con checkboxes, decisión final del
  paquete con `APPROVE_CLEAN/APPROVE_WITH_EXCEPTIONS/RETURN_TO_ADJUSTMENTS/
  REJECT`), cada uno con nombre real + justificación obligatoria (mismo
  patrón que `review.js`/`governance.js`).
- `factory/ui/js/mission_control/refresh.js` -- nueva vista `remediacion`
  (dispatcher + título), GET directivas al entrar a la vista.
- `factory/ui/js/mission_control/main.js` -- expone las 4 funciones nuevas
  en `window` (los `onclick` inline las necesitan globales, mismo patrón que
  el resto del archivo).
- `factory/ui/mission_control.html` -- botón de nav "Remediación —
  directivas" (grupo Gobierno) + sección `#v-remediacion` con las tres
  cajas (directivas, buscador de paquete, resultado).

**Verificación en vivo (no solo sintaxis):**
- `node --check` sobre los 3 `.js` tocados/nuevo -- sin errores.
- `GET /api/v1/layer9/remediation/directives` vía `factory-api` real
  (puerto 9000, con API key real del contenedor): `200 {"directives": []}`
  (vacío porque el store real nunca se tocó -- §2 corrió aislado en
  `tmp_path`, consistente con lo documentado ahí).
- `GET /api/v1/remediation-packages/RW-0005/nonexistent/1`: `404` (rama de
  error del panel ejercitada de verdad, no supuesta).
- `GET /ui/js/mission_control/remediation.js` a través del servidor real:
  `200` -- el archivo nuevo se sirve, no es solo un archivo en disco sin
  cablear.
- `factory/tests/test_governance_ui_deploy_consistency_live.py` (el chequeo
  de frescura real de R3-T1.8, mismo que verificó §0): 5/5 PASS después del
  cambio -- esta UI no rompe la comparación de rutas servidas vs. código.

**Lo que este panel NO hace (a propósito, fuera del alcance mínimo):**
no dispara el `remediation_directive_dispatch` (Ruta D) -- no hay endpoint
API para eso todavía, solo se invoca desde tests/código; no lista paquetes
existentes (hay que conocer el identificador); no crea paquetes (eso lo
hace `create_package()`, generación automática, fuera del alcance de
"adjudicación humana"). Si Cesar necesita cualquiera de estas tres,
son extensiones de alcance nuevas, no parte de este cierre.

```
UI_ADJUDICACION_DIRECTIVAS =  construida y servida en vivo (v-remediacion)
UI_ADJUDICACION_PAQUETE =     3 formularios reales sobre los 3 endpoints ya vivos
FRESHNESS_CHECK_POST_CAMBIO = 5/5 PASS
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

>>> §3.2 CERRADO. Queda §3.5 (verificación explícita de supervivencia a
>>> cierre de SSH) como único bloqueante real pendiente antes de §3.8.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-13 (cont.) — §3.5 CERRADO: supervivencia a cierre de SSH
──────────────────────────────────────────────────────────────────────────────

Prueba real ejecutada en el servidor, cero llamadas LLM, cero contacto con
`factory/regulatory/pilot_run/` real -- una sonda sintética
(`/tmp/.../ssh_survival/probe.py`, en el scratchpad de sesión, nunca
commiteada) que escribe el MISMO formato de estado que
`run_corpus_pilot.py` (PID + `RUNNING`/heartbeats/`COMPLETED` en un JSON),
lanzada con el mecanismo real recomendado por este plan
(`systemd-run --user`, unit `w5v2-pilot-<run_id>`, mismo prefijo que
`pilot_status.sh` ya espera).

**Diseño de la prueba:** una "sesión SSH" simulada = un `bash` puesto en su
propia sesión con `setsid` (session id propio, huérfano de la terminal,
reparentado a PID 1 -- estructuralmente idéntico a una shell de login SSH
tras perder la conexión de control), que desde adentro lanza
`systemd-run --user --unit=w5v2-pilot-<run_id> --collect -- python3
probe.py --duration 45`. Verificado ANTES del corte:
`ps` confirmó que el proceso real de la sonda (PID 80938) tiene
`PPID=565` (`systemd --user`, no la shell "SSH"), sesión propia (SID=80938)
-- ya desacoplado desde el instante del `systemd-run`, antes incluso de
cortar nada.

**Corte simulado:** `kill -HUP` + `kill -KILL` sobre la shell "SSH"
(PID 80936) ~13s después del arranque, con la sonda a mitad de sus 45s.
Verificado: la shell "SSH" queda confirmada muerta (`kill -0` -> "no such
process").

**Resultado, leído desde una invocación de shell NUEVA y separada (el
equivalente real a "reconectar por SSH y consultar", exactamente lo que
`pilot_status.sh` está diseñado para hacer):**
```
status.json final:
  "status": "COMPLETED", "pid": 80938, "ppid": 565,
  "started_at": "2026-08-13T20:02:36+00:00", "heartbeats": 9,
  "finished_at": "2026-08-13T20:03:22+00:00"
```
9 heartbeats × 5s = 45s -- la sonda corrió sus 45 segundos completos, sin
interrupción, pese a que la shell que la lanzó murió a los 13s. El PID de
la sonda solo desapareció al terminar por sí sola (no por la señal), y el
journal (`journalctl --user -u w5v2-pilot-<run_id>`) registra el arranque
real vía `systemd[565]: Started ...`. El unit desaparece de
`systemctl --user status` tras completar porque se lanzó con `--collect`
(auto-recolección de units transitorios terminados) -- comportamiento
esperado, no una pérdida de evidencia: el estado durable real es el
`status.json`, exactamente el diseño que `pilot_status.sh` ya asume (lee de
disco, nunca depende de que el unit siga listado).

**Lo que esto prueba y lo que NO prueba:** prueba el mecanismo de
desacople (`systemd-run --user` + `linger=yes` ya confirmado activo en el
usuario del proyecto, `loginctl show-user` -> `Linger=yes`) y el patrón de
lectura de estado desde disco -- la misma infraestructura que usará la
corrida Tier-1 real. NO ejercita `run_corpus_pilot.py` en sí (habría exigido
llamadas LLM reales, prohibidas en esta fase) ni corre 8-12h reales -- eso
lo prueba la corrida Tier-1 misma, no este pre-vuelo.

```
SSH_SURVIVAL_VERIFIED = true (systemd-run --user, linger=yes, probado con
                         corte real de la sesion lanzadora a los 13s de 45s)
MECHANISM = systemd-run --user --unit=w5v2-pilot-<run_id> --collect
STATUS_READ_FROM_NEW_SESSION = confirmado (status.json + journalctl)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

>>> §3.5 CERRADO. Con esto, 3.1-3.6 están en VERDE. Queda §3.7 (criterio de
>>> éxito) por firmar y luego §3.8 (proponer la autorización real con
>>> número exacto de llamadas y horas) -- ninguno de los dos se decide sin
>>> Cesar.
