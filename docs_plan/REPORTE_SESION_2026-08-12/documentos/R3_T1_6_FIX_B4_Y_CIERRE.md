# R3-T1.6 — B4 (GATE DEL HEADLINE) Y CIERRE DE R3-T1
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_6_FIX_B4_Y_CIERRE.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# CONTEXTO: F2-DRY dio PARCIAL en criterios b y c. Causa: B4 — el candidato
# "headline" no ancla porque el modelo dejó `evidencia_exacta` vacía, y por
# eso el D ya corregido por B3 nunca llega al Finding. Es el ÚLTIMO eslabón
# de la cadena kerning→contrato→B3→B4: el paso final antes de la conclusión.
#
# Reglas duras: CERO llamadas LLM (todo por replay sobre datos pagados); no
# MarkItDown; no cambiar modelo; NO aflojar validadores (el fix debe
# demostrarlo); no commit sin diff + aprobación.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. HIGIENE PREVIA (barata, desbloquea señal confiable)
──────────────────────────────────────────────────────────────────────────────

0.1 Commitear el pendiente ya listo: `pendiente_bloque1_headline_gate.patch`
    (bloque 1 de R3-T1.5 + investigación de B4). Diff → tu aprobación.
0.2 ÁRBOL SUCIO: `decisions_v2.jsonl` y `review_queue.jsonl` llevan
    modificados desde antes de esta sesión, lo que mantiene 4 guardianes de
    Gate 0 en rojo permanente. Un guardián siempre rojo deja de proteger.
    Investigar qué contienen esos cambios (¿decisiones legítimas de una
    sesión previa sin commitear? ¿escrituras de prueba?), y:
    - si son datos legítimos de gobernanza ⇒ commitearlos con diff y
      motivo (son append-only; se versionan, no se descartan);
    - si son residuos de pruebas ⇒ identificar cuáles y proponer su
      tratamiento (nunca borrar registros de gobernanza reales).
    Objetivo: que los 4 guardianes vuelvan a verde y vuelvan a significar
    algo. Reportar el conteo de Gate 0 después.

──────────────────────────────────────────────────────────────────────────────
1. B4 — CARACTERIZACIÓN (leer código real, con evidencia)
──────────────────────────────────────────────────────────────────────────────

1.1 Localizar la selección del candidato "headline" en `chunked_engine.py`:
    dónde se evalúa `_is_anchored(evidencia_exacta, chunk_text)`, cómo se
    elige `best`, y en qué línea exacta el `Finding.d_sufficiency` queda
    sin poblar cuando ningún candidato ancla. Citar archivo:línea.
1.2 Confirmar el caso real con el checkpoint histórico: chunk 20,
    `21_CFR_11.10(e)` — `evidencia_exacta=''` mientras
    `criterion_assessments` trae 2 MET con cita real que SÍ ancla
    (verificado por `verify_anchor` en el mismo chunk). Mismo patrón en
    `11.10(d)`.
1.3 Cuantificar el alcance: en las 29 chunk_executions del checkpoint
    histórico (y en el de F1), ¿en cuántos casos hay citas por criterio
    ancladas mientras el headline viene vacío? Ese número dice cuánta
    evidencia real está descartando el producto hoy.

──────────────────────────────────────────────────────────────────────────────
2. DISEÑO DEL FIX — Y LA PRUEBA DE QUE NO AFLOJA
──────────────────────────────────────────────────────────────────────────────

PRINCIPIO (idéntico a B3): usar señal que el modelo YA emitió y que YA pasó
validación; nunca fabricar, nunca bajar umbrales.

2.1 Regla propuesta (evaluar y justificar la elegida):
    un candidato puede considerarse ANCLADO si:
    (a) su `evidencia_exacta` ancla (comportamiento actual, sin cambios); O
    (b) `evidencia_exacta` viene vacía PERO al menos una cita de
        `criterion_assessments` de ese mismo chunk ancla contra el texto de
        ESE chunk (verificada con el mismo `verify_anchor`/`_is_anchored`,
        el mismo umbral, sin excepciones).
    En el caso (b), la cita de nivel resumen del Finding se DERIVA de las
    citas por criterio ya ancladas (concatenación/selección determinista,
    trazable al criterio origen) — no se inventa texto, no se sintetiza
    con LLM, y queda marcado en el registro que el headline fue derivado
    (`headline_source=derived_from_criterion_quotes`) para que un revisor
    lo vea.
2.2 LO QUE NO CAMBIA: si `evidencia_exacta` está vacía y NINGUNA cita por
    criterio ancla ⇒ el candidato sigue sin ganar (ausencia honesta
    preservada). El umbral de anclaje, las validaciones A/B/C/D y la regla
    de contradicción quedan intactas. `verify_sufficiency()` de un solo
    chunk, sin cambios.
2.3 GUARDIANES OBLIGATORIOS (tests bloqueantes; sin ellos no se commitea):
    - CASO REAL B4: chunk 20 / 11.10(e) — con el fix, el candidato ancla y
      el D agregado (`PARTIALLY_MET` 2/9) SÍ llega al `Finding`;
    - AUSENCIA PRESERVADA: headline vacío + cero citas por criterio
      ancladas ⇒ no gana, conclusión de ausencia intacta;
    - CITA NO ANCLADA NO RESCATA: headline vacío + citas por criterio que
      NO anclan (inventadas o de otro chunk) ⇒ no gana. Este es el
      guardián central contra fabricación;
    - CONTRADICCIÓN GENUINA (11.10(d)) sigue bloqueando en el Finding;
    - ANNEX11_4 sigue rechazado end-to-end;
    - RETROCOMPATIBILIDAD: candidatos con headline anclado se comportan
      exactamente igual que antes (test de no-cambio).

──────────────────────────────────────────────────────────────────────────────
3. RE-EJECUCIÓN DE F2-DRY (cero llamadas) — cerrar criterios b y c
──────────────────────────────────────────────────────────────────────────────

3.1 Re-correr `replay_f2_dry.py` con B4 aplicado, sobre el mismo checkpoint
    histórico, misma cola aislada, mismas garantías de aislamiento
    (REVIEW_QUEUE_FILE redirigido; SHA-256 de original y checkpoint
    verificados antes/después).
3.2 Tabla ANTES/DESPUÉS a nivel de PRODUCTO (no solo de función):
    por requisito, `Finding.d_sufficiency` y conclusión final, antes de B4
    y después. Esperado: 11.10(e) pasa de "D descartado" a
    `PARTIALLY_MET`→SUPPORTING_EVIDENCE_UNDER_REVIEW (RAMA B ya aceptada);
    11.10(d) llega al Finding y sigue bloqueado por contradicción genuina.
3.3 Re-evaluar los 6 criterios de aceptación de F2-DRY (a–f). Objetivo:
    b y c pasan de PARCIAL a PASA. Si alguno sigue parcial, DETENERSE y
    reportar la causa — no declararlo cerrado.

──────────────────────────────────────────────────────────────────────────────
4. DESBLOQUEAR TU VALIDACIÓN DEL CICLO HUMANO (paso 1.3, sin costo LLM)
──────────────────────────────────────────────────────────────────────────────

Problema: las entradas del dry-run viven en `review_queue_dry_run.jsonl`
aislado; la UI de producción no las ve, así que no puedes registrar tu
decisión y el ciclo humano queda sin validar.

4.1 Proponer la vía más limpia (elegir y justificar):
    (i) apuntar la UI a la cola del dry-run mediante un parámetro/entorno
        explícito de solo lectura para esta validación; o
    (ii) promover deliberadamente UNA entrada del dry-run a la cola real,
        marcada `DRY_RUN_VALIDATION` en su payload (visible en la UI), de
        modo que tu decisión sea real sobre un ítem declarado de prueba —
        con su evento de auditoría normal.
    NO mezclar silenciosamente entradas de dry-run con hallazgos reales:
    cualquiera que sea la vía, el origen queda declarado en la entrada.
4.2 Verificar en la UI corregida que la entrada muestra: requisito,
    conclusión, flags, cobertura, y los candidatos con página y extracto.
    Confirmar que el campo revisor valida identidad (422 genéricas) y que
    aprobar/rechazar emite exactamente un evento.
4.3 DETENERSE aquí para que Cesar registre la decisión real. Ese clic
    cierra el criterio F2.3.d.

──────────────────────────────────────────────────────────────────────────────
5. CIERRE DE R3-T1 (acotar la deriva)
──────────────────────────────────────────────────────────────────────────────

5.1 Declarar la cadena completa de defectos encontrados y cerrados en esta
    fase: kerning (extracción) → contrato de prompt → B3 (agregación
    multi-chunk) → B4 (gate del headline). Documentar que B4 es el último
    eslabón antes del Finding: no hay capa posterior que pueda descartar
    evidencia ya validada. Si el análisis encuentra que sí la hay,
    reportarlo — pero no abrir un B5 sin evidencia.
5.2 Declarar QUÉ DEMUESTRA R3-T1 (con F2-DRY cerrado y tu decisión
    registrada): el flujo Tier-1 produce informes trazables con anclaje
    real donde la evidencia existe, estados honestos donde no, cola
    enriquecida, y decisión humana registrada — sin gastar el presupuesto
    de F2.
5.3 Declarar QUÉ NO DEMUESTRA, sin maquillar: paráfrasis automática
    (límite R2, vivo); CONFIRMED automático (B1 + cobertura real del
    documento); reproducibilidad estricta entre corridas (variabilidad B2);
    y que estos resultados provienen de un checkpoint BASELINE — una
    corrida H2H4 en vivo podría diferir a nivel de chunk.
5.4 F2-LIVE: con B3+B4 corregidos, re-evaluar si se justifica. Criterio:
    solo si responde una pregunta que cambie una decisión de producto. Si
    la respuesta esperada es la misma que el replay ya da, recomendar NO
    correrlo y decirlo con el razonamiento. Si se justifica, dimensionarlo
    al mínimo (3-5 chunks, no 29) con su firma.
5.5 Actualizar memoria/skill/roadmap: la cadena de 4 defectos y su patrón
    común (el modelo se contradice entre campos de su propia salida; el
    fix siempre es usar señal ya emitida y ya validada, nunca aflojar);
    y el patrón de replay sobre datos pagados como paso obligatorio antes
    de pedir presupuesto.
5.6 Pendientes con dueño: B1 (`positive_conclusion_eligibility`, tu
    decisión, ID `ARTIFACT_VERSION-2026-019`); prompt fantasma; tests
    ambientales de Gate 0.

──────────────────────────────────────────────────────────────────────────────
6. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
BLOQUE1_COMMITTED =            (patch pendiente, con tu aprobación)
DIRTY_TREE_RESOLVED =          (4 guardianes de Gate 0 en verde / explicado)
GATE0_COUNT =                  (passed/failed tras la limpieza)
B4_ROOT_CAUSE =                (archivo:línea del gate headline)
B4_SCOPE =                     (nº de casos con criterio anclado y headline vacío)
B4_FIX_DESIGN =                (regla (b) + headline derivado y marcado)
GUARDIANS =                    (los 6: PASA/FALLA cada uno)
UNANCHORED_QUOTE_NEVER_RESCUES = true   ← guardián central anti-fabricación
F2_DRY_RERUN =                 (tabla ANTES/DESPUÉS a nivel Finding)
F2_DRY_CRITERIA =              a..f (b y c deben pasar de PARCIAL a PASA)
HUMAN_CYCLE_PATH =             (vía elegida para tu decisión en UI)
HUMAN_DECISION_REGISTERED =    (pendiente de Cesar)
DEFECT_CHAIN_CLOSED =          kerning → contrato → B3 → B4
R3_T1_DEMOSTRADO / NO_DEMOSTRADO = (§5.2 / §5.3)
F2_LIVE_JUSTIFIED =            (sí/no + razonamiento; si sí, alcance mínimo)
OPEN_ITEMS =                   (B1/019, prompt fantasma, tests ambientales)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: el commit del pendiente, el diff de B4 con sus guardianes, y
tu decisión en la UI. B4 se descarta si cualquier guardián cae — en
particular si una cita NO anclada llegara a rescatar un candidato: eso
sería fabricar evidencia, y ningún desbloqueo de F2 lo justifica.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12
──────────────────────────────────────────────────────────────────────────────

## Bloque 0 — Higiene previa

**0.1 — Commiteado.** `pendiente_bloque1_headline_gate.patch` (bloque 1 de
R3-T1.5 + investigación del gate headline) commiteado en `98147df`.

**0.2 — Árbol sucio investigado y resuelto.** Los 4 guardianes en rojo eran
por `decisions_v2.jsonl`/`review_queue.jsonl` sin commitear desde una
sesión anterior (R3-T1.2/F1). Verificado como **gobernanza legítima, no
residuo de prueba**: par `PILOT_EXECUTION-2026-015/016` (autorización +
confirmación por `cesar`) de la micro-validación F1, y el hallazgo real
que esa corrida despachó a la cola. Checkpoint `chunked-50534e75927c`
confirmado presente en disco con timestamp coincidente. Commiteado en
`e026cdb`. **`GATE0_COUNT` tras la limpieza: los 4 guardianes vuelven a
verde** (`4 passed in 0.40s`, verificado con reintentos aislados). La
suite completa se relanzó en background para confirmar el conteo agregado
final, pero arrancó ANTES de los cambios de B4 (bloque 1-2) — no los
refleja; el objetivo de 0.2 (guardianes verdes) ya está confirmado sin
depender de esa corrida.

## Bloque 1 — B4, caracterización

**1.1 — Localización exacta** (`factory/engines/gmpai_integrity/chunked_engine.py`):
- Línea 611-614: `_is_anchored()` — substring literal exacto, sin
  tolerancia.
- Línea ~1345: `anchored = _is_anchored(evidencia, chunk["text"]) if evidencia else False`.
- Línea ~1593 (antes del fix): `all_candidates = [c for c in by_req.get(req_id, []) if c["anchored"]]`.
- Línea ~1712: `best = candidates[0]` — el primero en orden de chunk que
  cumple anclaje, no "el mejor" por ninguna métrica de calidad.
- Línea ~1729 (antes del fix): `if "a_anchor" in best:` — único punto
  donde `verify_sufficiency_aggregated()` (D, con fix B3) se adjunta al
  Finding. Si `best` no existe (rama "sin candidatos", líneas 1604-1687),
  `Finding.d_sufficiency` nunca se asigna — queda `None` por default del
  dataclass.

**1.2 — Caso real confirmado** con `raw_response` completo (chunk 20,
`21_CFR_11.10(e)`): `evidencia_exacta=''` (headline vacío, el modelo
nunca lo llenó) mientras `criterion_assessments` de la MISMA respuesta
trae 2 criterios `MET` con `evidence_quote` real que SÍ ancla
(`verify_anchor` PASS). Mismo patrón en `21_CFR_11.10(d)` (chunks 18/19/20).

**1.3 — Alcance cuantificado** (checkpoint histórico + checkpoint F1,
script ad hoc sobre `raw_response` real, cero llamadas):

```
B4_SCOPE = 3 casos en 2 chunks del checkpoint baseline (943a62bcbb85):
  chunk 19, 21_CFR_11.10(d): 1 criterio MET con cita real, headline vacío
  chunk 20, 21_CFR_11.10(e): 2 criterios MET con cita real, headline vacío
  chunk 20, 21_CFR_11.50_11.70: 1 criterio MET con cita real, headline vacío
           (este caso NO bloqueaba el Finding -- otro chunk SÍ anclaba
           para ese mismo requisito, por eso no apareció en el hallazgo
           original de R3-T1.5)
Checkpoint F1 (50534e75927c, H2H4, 5 chunks): 0 casos -- el defecto no
se manifestó en esa corrida mas pequeña.
```

## Bloque 2 — Diseño e implementación de B4

**2.1 — Regla implementada**: `_apply_headline_rescue_b4()`, función de
módulo nueva en `chunked_engine.py` (extraída, no inline, para que el
bucle en vivo Y cualquier replay sobre datos ya guardados apliquen
EXACTAMENTE la misma regla). Si `evidencia` (headline) viene vacía y
`requires_anchor=True`: toma `d_detail['met']` (ya calculado por
`verify_sufficiency()`/`verify_evidence_abcd()`, Nivel B ya aplica
`verify_anchor` por criterio), deriva el headline concatenando las citas
de esos criterios, marca `anchored=True` y `headline_source=
'derived_from_criterion_quotes'`.

**2.2 — Guardia adicional encontrada al diseñar** (no estaba en el plan
original, pero es necesaria): `_classify_criteria_for_chunk()` (la fuente
de `d_detail`) SOLO aplica `verify_anchor()` por criterio — a diferencia
del headline normal, NUNCA llama a `detect_reference_list_context()`. Sin
un chequeo explícito, una cita de una lista de referencias numeradas
(patrón real de ANNEX11_4) que ancla literalmente por criterio podría
colarse por la ruta derivada aunque el headline normal la hubiera
rechazado. Se agregó el mismo chequeo, revisando cada cita
individualmente (el texto unido con `" | "` nunca existe literalmente en
el chunk, así que revisar el texto ya unido habría dejado el chequeo
mudo para 2+ citas).

**2.3 — Los 7 guardianes** (6 del plan + 1 adicional por el hallazgo de
2.2), todos en `factory/tests/test_gmpai_chunked_engine.py`:

```
GUARDIANS:
test_b4_headline_empty_but_criterion_quotes_anchored_rescues_candidate  PASA (caso real)
test_b4_absence_preserved_when_no_criterion_anchors                    PASA (ausencia preservada)
test_b4_unanchored_criterion_quote_never_rescues                       PASA (guardián central anti-fabricación)
test_b4_reference_list_criterion_quote_never_rescues                   PASA (hallazgo 2.2, ANNEX11_4-like)
test_b4_genuine_contradiction_still_blocks_with_both_headlines_empty   PASA (contradicción genuina)
test_b4_annex11_4_reference_list_still_rejected_end_to_end             PASA (regresión end-to-end)
test_b4_anchored_headline_unchanged_behavior                           PASA (retrocompatibilidad)
UNANCHORED_QUOTE_NEVER_RESCUES = true
```

Suite completa relevante (`test_gmpai_chunked_engine.py` +
`test_semantic_evidence_verification.py` + `test_tier1_report.py`):
**125 passed, 0 failed.**

## Bloque 3 — Re-ejecución de F2-DRY (cero llamadas)

Re-corrido `replay_f2_dry.py` sobre el mismo checkpoint histórico, con
B4 aplicado. Como el checkpoint es de ANTES del fix, el script no puede
reusar el candidato ya persistido tal cual (colapsaba headline-vacío y
headline-no-anclado al mismo placeholder) — se actualizó para recuperar
el `evidencia_exacta` ORIGINAL desde el `raw_response` completo (mismo
mecanismo ya usado para `estado`) y llamar a la MISMA función
`_apply_headline_rescue_b4()` que usa el motor en vivo.

**Tabla ANTES/DESPUÉS a nivel de Finding (confirmado con datos reales):**

| Requisito | ANTES: d_sufficiency | DESPUÉS: d_sufficiency | evidencia_exacta |
|---|---|---|---|
| `21_CFR_11.10(e)` | `None` (D descartado) | **`PARTIALLY_MET`** | `[headline derivado...] UR3.3.1 Every time a criti...` |
| `21_CFR_11.10(d)` | `None` (D descartado) | **`NOT_ASSESSABLE`** (contradicción genuina, correcta) | `[headline derivado...] Both Microsoft Windows dom...` |
| `21_CFR_11.10(g)` | `None` | `None` (sin cambios — nunca tuvo criterios anclados en los chunks relevantes) | sin cambios |
| `21_CFR_11.50_11.70` | `None` | `None` (sin cambios) | sin cambios |

**B4 funciona exactamente como se diseñó** a nivel de `Finding` — D
(ya corregido por B3) ahora SÍ llega hasta ahí para 11.10(d)/(e).

## HALLAZGO NUEVO: B4 no cambia la `conclusion` final — un pipeline separado decide

**`verified_conclusions[req_id]['conclusion']` NO cambió** (sigue
`PROVISIONAL_GAP` para ambos, idéntico antes y después de B4).

Causa raíz confirmada (`chunks_observed: 0` en `verified_conclusions_DRY_RUN.json`
para ambos requisitos, antes y después): la `conclusion` la decide
`absence_consolidator.consolidate()` sobre `verified_records_by_req` — una
estructura de datos **completamente separada** de `by_req`/`Finding`, que
se construye ANTES en el bucle (líneas ~1393-1403 de `chunked_engine.py`)
vía `build_finding_record()`, usando `valid_candidate_verified` (el
chequeo de anclaje headline ORIGINAL, sin rescate). `apply_conclusion_preconditions()`
(que sí lee `d_sufficiency`) **solo puede DEGRADAR** una conclusión que
`consolidate()` ya haya decidido como "support-asserting" (línea 240:
`if c.conclusion in _SUPPORT_ASSERTING`) — nunca puede PROMOVER una
conclusión de tipo GAP/ausencia a una de tipo soporte. Como
`consolidate()` nunca vio un registro "observed" (ambos requisitos
`chunks_observed=0`), la conclusión nace GAP y se queda GAP sin importar
qué diga `d_sufficiency`.

**Esto significa**: B4, tal como está diseñado y commiteado, corrige el
`Finding` (el registro técnico/de auditoría) pero NO corrige el
`verified_conclusions` que alimenta el bucketing Tier-1 real
(`tier1_report._bucket_for_conclusion`). Para que 11.10(e) efectivamente
pase a `SUPPORTING_EVIDENCE_UNDER_REVIEW` (RAMA B), el MISMO rescate de
B4 tendría que aplicarse también a `v_candidate`/`build_finding_record()`
-- un cambio adicional, no incluido en el diseño original de B4 (que se
scopeó específicamente al gate de candidato headline para el `Finding`,
no a `verified_records_by_req`).

## Re-evaluación de criterios F2-DRY (a-f) — POR LITERAL, sin inflar

```
a) informe se genera sin error, buckets validos:                    PASA (sin cambios)
b) 11.10(e) con estado honesto, contradicted vacio, PRUEBA de que B3
   llega al producto final:
   - llega a Finding.d_sufficiency? SI (PARTIALLY_MET, contradicted
     vacio) -- MEJORA REAL respecto a R3-T1.5.
   - llega a verified_conclusions.conclusion (el bucket Tier-1 real)?
     NO -- sigue PROVISIONAL_GAP, NO SUPPORTING_EVIDENCE_UNDER_REVIEW.
   VEREDICTO: SIGUE PARCIAL. No cumple el criterio tal como esta escrito
   (que exige "llega al producto final").
c) 11.10(d) sigue bloqueado por contradiccion genuina:               PASA a
   nivel de Finding (NOT_ASSESSABLE, correcto) Y a nivel de conclusion
   (PROVISIONAL_GAP, que es coherente con "no se puede confirmar" --
   pero por razones DISTINTAS, no por la contradiccion).
d) cola de revision con candidatos/paginas/extractos:                PASA
   (sin cambios respecto a R3-T1.5, sigue funcionando)
e) ningun bucket huerfano:                                            PASA
f) original en disco intacto (SHA-256):                               PASA
   (documento y checkpoint verificados identicos antes/despues)
```

**Por instrucción explícita del plan ("Si alguno sigue parcial,
DETENERSE y reportar la causa — no declararlo cerrado"): criterio (b)
sigue PARCIAL. No se declara F2-DRY cerrado.**

## DETENERSE

```
BLOQUE1_COMMITTED =            SI (98147df)
DIRTY_TREE_RESOLVED =          SI (e026cdb) -- 4 guardianes verdes confirmados
GATE0_COUNT =                  suite completa (host, background) terminada:
                                2420 passed, 6 failed, 5 skipped, 1 xfailed,
                                2 errors (1057.21s/17:37min). Los 4 guardianes
                                de gobernanza que 0.2 arreglo YA NO aparecen
                                en rojo -- confirmado. Aparecen 2 fallos NUEVOS
                                pero autoinfligidos y esperados:
                                test_runtime_identity.py::test_engine_files_
                                on_disk_match_head y test_assert_passes_on_a_
                                reproducible_runtime -- ambos detectan
                                correctamente que chunked_engine.py esta
                                modificado en disco sin commitear (el fix B4
                                pendiente de aprobacion). Es el guardian
                                correcto haciendo su trabajo, no una
                                regresion -- se resuelve solo al commitear
                                B4. Los otros 4 fallos/2 errores restantes
                                (Playwright/live endpoint) son los mismos
                                ambientales ya caracterizados en 0.2.
B4_ROOT_CAUSE =                chunked_engine.py:1593 (all_candidates filtrado
                                por anchored), :1712 (best=candidates[0]),
                                :1729 (unico punto que adjunta D al Finding)
B4_SCOPE =                     3 casos / 2 chunks (checkpoint baseline); 0 en F1/H2H4
B4_FIX_DESIGN =                _apply_headline_rescue_b4(), funcion de modulo
                                compartida entre evaluate_chunked() y el replay
GUARDIANS =                    7/7 PASA (6 del plan + 1 hallazgo propio: cita
                                de lista de referencias no debe rescatar)
UNANCHORED_QUOTE_NEVER_RESCUES = true (confirmado, test dedicado)
F2_DRY_RERUN =                 tabla ANTES/DESPUES en bloque 3 -- Finding.
                                d_sufficiency mejora real, verified_conclusions
                                sin cambio
F2_DRY_CRITERIA =              a,c,d,e,f PASA; b SIGUE PARCIAL
HUMAN_CYCLE_PATH =             NO decidido -- bloqueado hasta resolver (b)
HUMAN_DECISION_REGISTERED =    pendiente
DEFECT_CHAIN_CLOSED =          NO -- kerning -> contrato -> B3 -> B4 (Finding)
                                -> [NUEVO, sin nombre asignado] (verified_records_
                                by_req/build_finding_record, no wireado a B4)
R3_T1_DEMOSTRADO / NO_DEMOSTRADO = pendiente de bloque 5 -- no evaluado, cierre
                                de R3-T1 bloqueado por (b)
F2_LIVE_JUSTIFIED =            no evaluado -- bloqueado por (b)
OPEN_ITEMS =                   B1/019, prompt fantasma, tests ambientales de
                                Gate 0, + el nuevo hallazgo de esta seccion
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**DETENERSE.** B4 está diseñado, implementado, commiteado-pendiente (diff
sin aprobar todavía: `factory/engines/gmpai_integrity/chunked_engine.py`
+92 líneas, `factory/tests/test_gmpai_chunked_engine.py` +198 líneas, 125
tests en verde) y demuestra una mejora real y verificada a nivel de
`Finding`. Pero el criterio (b) de F2-DRY sigue PARCIAL: el mismo rescate
tendría que extenderse a `verified_records_by_req`/`build_finding_record()`
para que la `conclusion` final (el bucket Tier-1 real) refleje el
resultado corregido. No se declara F2-DRY cerrado, no se avanza a bloque
4 (ciclo humano) ni bloque 5 (cierre de R3-T1) sin tu decisión sobre este
hallazgo nuevo.
