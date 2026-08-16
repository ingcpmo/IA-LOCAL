# R3-T1.5 — F2 SIN QUEMAR LLAMADAS: VALIDAR EL PRODUCTO POR REPLAY
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_5_F2_DRY.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# PRINCIPIO DE ESTA CORRIDA: agotar toda la validación gratis (replay sobre
# checkpoints ya pagados) ANTES de autorizar una sola llamada nueva. El
# replay ya demostró que sabe responder preguntas que costaban 29 llamadas.
#
# Reglas duras: CERO llamadas LLM en los bloques 0-3; no MarkItDown; no
# cambiar modelo; no aflojar validadores; no commit sin diff + aprobación.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. DOS INCONSISTENCIAS QUE SE RESUELVEN PRIMERO (cero costo)
──────────────────────────────────────────────────────────────────────────────

0.1 ESTADO REAL DEL FIX B3 — contradicción entre reportes:
    R3_T1_3 §5(ii) afirma que el fix está COMMITEADO (`e823015`).
    R3_T1_4 encabezado afirma "Sin commit — pendiente de aprobación".
    Verificar con `git log`/`git status` cuál es cierto y reportarlo:
    - si está commiteado sin tu aprobación de diff ⇒ documentar como
      desviación de proceso (no revertir; el contenido es correcto y está
      validado), reafirmar la regla, y pedir tu aprobación retroactiva;
    - si NO está commiteado ⇒ presentar el diff y commitear con tu
      aprobación (causa raíz: fix B3 + sus 5 tests).
    Corregir el documento que quedó desactualizado para que ambos digan lo
    mismo. Este tipo de divergencia entre reportes es justo lo que erosiona
    la trazabilidad; se cierra ahora, no después.

0.2 GATE 0 HONESTO: la suite completa no termina dentro del contenedor
    (falta CLI `docker`, tests que exigen Mission Control vivo). El
    argumento de "cero solapamiento por grep" es razonable pero NO
    equivale a Gate 0 verde. Resolver de forma barata:
    - correr la suite completa desde el HOST (venv del host, donde el CLI
      docker y la red sí existen) — que es como Gate 0 se corrió en F0;
    - reportar el resultado real (passed/failed) y confirmar que los 4-8
      fallos son los ambientales ya caracterizados, no regresión del fix;
    - si desde el host tampoco termina, decirlo y documentar el subconjunto
      efectivamente ejecutado, sin llamarlo "Gate 0 verde".

    **EJECUTADO 2026-08-12 — RESULTADO REAL:**
    Suite completa (`.venv` del host, `python -m pytest factory/tests/ -q`),
    terminó en 1010.90s (16:51 min) — a diferencia del contenedor, donde no
    termina. Resultado: **2434 tests → 2418 passed, 8 failed, 5 skipped,
    1 xfailed, 2 errors.**

    No es "Gate 0 verde" en sentido estricto — 10 de 2434 items fallan.
    Investigado cada uno con reintentos aislados antes de caracterizarlo:

    - **Cero solapamiento confirmado en la corrida real** (no solo por
      grep): `test_semantic_evidence_verification.py` y
      `test_gmpai_chunked_engine.py` — los dos archivos que el fix B3
      modifica — quedaron 100% en verde dentro de la corrida completa.
    - **4 fallos** (`test_no_test_in_this_file_wrote_to_the_real_store` en
      `test_artifact_version_signing.py`/`test_resignature_g2prime.py`,
      `test_the_two_stores_stayed_independent`,
      `test_n13_no_test_in_this_file_touched_the_real_store`): guardianes
      que comparan `factory/layer9/decisions/decisions_v2.jsonl` contra
      HEAD y detectan diferencia — **causa real: el archivo ya estaba
      modificado en el árbol de trabajo desde antes de esta sesión**
      (`review_queue.jsonl` también), no algo que esta corrida ni el fix
      B3 escribieron. Confirmado con `git diff --stat` antes/después.
    - **1 fallo** (`test_governance_ui_deploy_consistency_live.py::
      test_governance_state_endpoint_reachable_with_real_key`):
      `TimeoutError` real conectando a un endpoint vivo — ambiental, el
      servicio no está alcanzable así desde el host en este momento.
    - **5 fallos/errores Playwright** (`test_governance_catalog_version_
      playwright.py`, `test_review_queue_finding_ui_playwright.py`):
      reejecutados en aislamiento, siguen fallando por
      `playwright._impl._errors.TimeoutError` esperando elementos de la
      UI de Mission Control vivo (`#apikey`, `wait_for_function`) —
      coincide exactamente con la caracterización ya documentada en Gate 0
      de F0 (`docs_plan/R3_T1_2_F0_EVIDENCIA/RESUMEN.md`).

    **Conclusión**: los 10 fallos se explican íntegramente por dos
    categorías ya conocidas (estado sucio preexistente en el store de
    decisiones + timeouts contra servicios vivos/Playwright bajo carga o
    no disponibles) — ninguna categoría nueva, ninguna toca el código del
    fix B3. Se reporta así, sin llamarlo "Gate 0 verde".

──────────────────────────────────────────────────────────────────────────────
1. F2-DRY — VALIDAR EL PRODUCTO COMPLETO POR REPLAY (cero llamadas)
──────────────────────────────────────────────────────────────────────────────

Insight que rediseña F2: sus 29 llamadas perseguían dos cosas distintas.
(i) el resultado de juicio del modelo — YA respondido por el replay del
checkpoint histórico (11.10(e) → PARTIALLY_MET 2/9; CONFIRMED inalcanzable
por cobertura real del documento, no por defecto del pipeline);
(ii) que el FLUJO DE PRODUCTO funcione E2E — y eso también se valida sin
llamadas, alimentando el generador de informe con el checkpoint histórico.

1.1 Tomar el checkpoint histórico `chunked-943a62bcbb85` (29/29 chunks,
    RW-0005) y pasarlo por el pipeline de producto CORREGIDO (agregación
    con fix B3 + generador de informe con las correcciones de F0.5),
    generando en una ruta de trabajo separada (nunca sobre el informe
    supersedido):
    - informe Tier-1 completo con sus buckets;
    - entradas de cola de revisión con evidencia y candidatos;
    - manifest y trazabilidad.
    Marcar TODO el paquete como `DRY_RUN_FROM_HISTORICAL_CHECKPOINT`:
    su valor es validar el flujo, NO es un informe entregable (el
    checkpoint origen corrió con perfil BASELINE — el informe resultante
    no puede presentarse como producto, y debe decirlo en su portada).

1.2 CRITERIOS DE ACEPTACIÓN DE F2-DRY (pre-fijados, todos deben cumplirse):
    a) el informe se genera sin error, con los 5 requisitos, buckets
       correctos y `page_or_section` en el formato unificado;
    b) 11.10(e) aparece con su estado honesto (PARTIALLY_MET 2/9 →
       SUPPORTING_EVIDENCE_UNDER_REVIEW o el estado que corresponda bajo
       RAMA B), con `contradicted` vacío — la prueba de que el fix B3
       llega hasta el producto final, no solo hasta la función;
    c) 11.10(d) sigue bloqueado por contradicción genuina (el guardián
       también visible en el producto);
    d) cada requisito que necesita revisión tiene entrada en cola CON los
       candidatos, páginas y extractos (enriquecimiento del revisor);
    e) ningún bucket queda huérfano (la inconsistencia de
       NOT_OBSERVED_OPTIONAL de F0.5 corregida y verificable aquí);
    f) el original en disco intacto (SHA-256 antes/después).

1.3 CICLO HUMANO EN VIVO (el único paso que te toca a ti, sin costo LLM):
    abres la UI de revisión corregida, ves una entrada del dry-run con su
    evidencia y candidatos, y registras UNA decisión real con tu identidad.
    Eso cierra la validación del ciclo completo documento→informe→cola→
    decisión humana, que era el corazón de F2.3.d.

>>> CHECKPOINT 1: paquete dry-run + tu decisión registrada. Con esto, F2
>>> queda validado en todo lo que no requiere el modelo.

──────────────────────────────────────────────────────────────────────────────
2. QUÉ QUEDA SIN RESPONDER TRAS F2-DRY (y cuánto cuesta de verdad)
──────────────────────────────────────────────────────────────────────────────

Enumerar con precisión — sin inflar — lo que SOLO una corrida en vivo puede
responder, para dimensionar F2-LIVE al mínimo real:

2.1 ¿El perfil H2H4 sobre el documento completo produce resultados de
    chunk distintos a los del checkpoint BASELINE histórico? (F1 ya mostró
    que H2H4 ancla el chunk p.45-46; la pregunta abierta es si cambia algo
    en los otros 28 chunks para 11.10(e)).
2.2 ¿La variabilidad de muestreo (B2) altera el resultado agregado entre
    corridas del mismo documento?
2.3 Evaluar honestamente el VALOR de responder cada una:
    - si el resultado agregado esperado (PARTIALLY_MET 2/9 → revisión
      humana) es el mismo con BASELINE y con H2H4, la corrida en vivo de
      29 llamadas no cambia ninguna decisión de producto ⇒ NO se justifica
      todavía;
    - la variabilidad (B2) es una propiedad conocida del modelo ya
      documentada; medirla exigiría repeticiones (múltiplos de 29), lo que
      es claramente desproporcionado ahora.
2.4 RECOMENDACIÓN ESPERADA (que el análisis confirme o refute con datos):
    F2-LIVE completo NO se justifica hoy. Si algo debe correrse en vivo,
    que sea el mínimo que responda 2.1 sobre los chunks que importan
    (p. ej. 3-5 chunks donde BASELINE dio señal, no los 29), con el margen
    ya autorizado o una firma pequeña — no una corrida de 5 horas.

──────────────────────────────────────────────────────────────────────────────
3. CIERRE DE R3-T1 CON LO QUE YA HAY (evitar deriva de alcance)
──────────────────────────────────────────────────────────────────────────────

Riesgo real de esta fase: cada corrida encuentra un defecto más profundo
(kerning → contrato → agregación → cobertura), y el cierre se aleja. Acotar:

3.1 Declarar QUÉ demuestra R3-T1 con la evidencia disponible tras F2-DRY:
    el flujo Tier-1 produce informes trazables, con anclaje real cuando la
    evidencia existe, estados honestos cuando no, cola de revisión
    enriquecida y decisión humana registrada. Eso ES el objetivo del código
    para Tier-1 — y quedaría demostrado sin gastar el presupuesto.
3.2 Declarar QUÉ NO demuestra, sin maquillar: no demuestra detección
    automática de paráfrasis (límite R2, vivo); no demuestra CONFIRMED
    automático (bloqueado por B1 + cobertura real del documento); no
    demuestra reproducibilidad estricta entre corridas (variabilidad B2).
3.3 Pendientes que se cierran o se listan explícitamente con dueño:
    B1 (elegibilidad — tu decisión, y el ID `ARTIFACT_VERSION-2026-018`
    ya está tomado por una propuesta sin confirmar: la nueva será 019);
    prompt fantasma; tests ambientales de Gate 0.
3.4 Actualizar memoria/skill/roadmap con la lección de esta fase: el replay
    sobre checkpoints pagados resolvió DOS diagnósticos que costaban
    llamadas — establecerlo como patrón obligatorio: antes de proponer
    presupuesto, verificar si la pregunta se responde con datos ya
    existentes.

──────────────────────────────────────────────────────────────────────────────
4. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
B3_COMMIT_STATE =          (commiteado e823015 / sin commit — resuelto)
PROCESS_DEVIATION =        (si se commiteó sin aprobación: registrada)
GATE0_REAL =               (resultado desde el host, sin llamarlo verde si no lo es)
F2_DRY_REPORT =            (ruta; marcado DRY_RUN_FROM_HISTORICAL_CHECKPOINT)
F2_DRY_CRITERIA =          a..f (PASA/FALLA por literal)
B3_FIX_VISIBLE_IN_PRODUCT = (11.10(e) sin contradicted en el informe final)
GENUINE_CONTRADICTION_IN_PRODUCT = (11.10(d) sigue bloqueado)
HUMAN_CYCLE_CLOSED =       (decisión real de Cesar registrada)
ORIGINAL_INTACT =          (SHA-256)
F2_LIVE_JUSTIFIED =        (sí/no, con el razonamiento de §2.3)
F2_LIVE_MINIMAL_SCOPE =    (si aplica: chunks exactos y costo, no 29)
R3_T1_DEMOSTRADO =         (§3.1)
R3_T1_NO_DEMOSTRADO =      (§3.2)
OPEN_ITEMS =               (B1/019, prompt fantasma, tests ambientales)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE tras el CHECKPOINT 1 para tu decisión de revisión, y de nuevo
antes de proponer cualquier llamada en vivo. Ninguna corrida de 29 llamadas
se autoriza mientras el replay pueda responder la misma pregunta gratis —
esa es la regla que esta fase acaba de demostrar dos veces.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12 — BLOQUE 1 (F2-DRY)
──────────────────────────────────────────────────────────────────────────────

## Intento 1: evaluate_chunked() rehúsa reabrir un checkpoint completado

Se intentó pasar el checkpoint histórico `chunked-943a62bcbb85` por
`ce.evaluate_chunked()` directamente (con un "guard provider" que revienta
si intenta una llamada real -- cero llamadas salieron, confirmado), en la
misma configuración BASELINE del checkpoint original. El motor NO lo
reconoció como reanudable: generó un run_id nuevo e intentó ejecutar los
29 chunks desde cero (el guard los bloqueó, resultado vacío).

**Causa raíz** (`chunked_engine.py`, `CheckpointStore.find_resumable()`,
línea 853): el fingerprint coincidía exacto (verificado), pero nunca se
llegó a comprobar porque hay una barrera anterior, explícita y deliberada:
*"Un run completado SIN fallos tecnicos nunca se reabre... jamas
re-analizar contenido ya evaluado"*. `chunked-943a62bcbb85` está
`completed=True` sin fallos técnicos, así que se descarta antes de mirar
el fingerprint. **Es una guardia de gobernanza intencional, no un bug.**
Cesar decidió no bypasearla (ni siquiera en un script aislado) -- ver
"Replay acotado" abajo.

## Intento 2 (aprobado por Cesar): replay acotado sobre funciones reales

En vez de forzar `evaluate_chunked()`, se reconstruyó el tramo de
consolidación A/B/C/D llamando DIRECTAMENTE a las mismas funciones de
producción que ese tramo ya usa
(`semantic_evidence_verification.verify_sufficiency_aggregated` -- fix
B3 incluido --, `absence_consolidator.consolidate`,
`apply_conclusion_preconditions`, `evidence_pack_gate`, `Finding`,
`compute_substantive_support`, `applicability`), alimentadas con los
datos YA GUARDADOS en el checkpoint histórico
(`chunk_executions[i]['_by_req_candidates']`,
`chunk_executions[i]['_criterion_assessments_for_d']`,
`verified_records_by_req`). Ningún validador se reimplementó; solo se
reordenó la orquestación (el mismo "glue" que `evaluate_chunked()` ya
tiene). Script: `factory/regulatory/pilot_run/tier1_dry_run_20260812/
replay_f2_dry.py`.

**Gap adicional encontrado y resuelto**: este checkpoint es ANTERIOR a la
instrumentación del fix B3 (commit `e823015`) -- `_criterion_assessments_for_d`
no trae el campo `estado` (se empezó a guardar recién en ese commit). Sin
él, el fix no tenía nada que reclasificar. Se reconstruyó `estado` desde
el `raw_response` completo de cada chunk (descomprimido desde
`raw_response_full_path`, mismo mecanismo que `CheckpointStore.
load_raw_response()`) -- misma técnica que R3_T1_4 ya había usado para su
propia validación de replay.

## Resultado de la función D (validado con datos reales, cero llamadas)

| Requisito | D agregado (con fix B3) | contradicted |
|---|---|---|
| `21_CFR_11.10(e)` | **PARTIALLY_MET, 2/9** | vacío -- falsa contradicción CORREGIDA |
| `21_CFR_11.10(d)` | NOT_ASSESSABLE, "contradiccion real... 1 criterio" | `Mecanismo de control de acceso...` -- contradicción GENUINA preservada |
| `21_CFR_11.10(a)` | NOT_ASSESSABLE, incertidumbre real | vacío |
| `21_CFR_11.10(g)` | NOT_MET, ningún criterio confirmado | vacío |
| `21_CFR_11.50_11.70` | NOT_MET, ningún criterio confirmado | vacío |

Esto reproduce EXACTAMENTE lo que R3_T1_3/R3_T1_4 ya habían documentado
para 11.10(e) y 11.10(d) -- el fix B3 funciona correctamente a nivel de
función, con datos reales, cero llamadas.

## HALLAZGO NUEVO (no cubierto por B3): un gate independiente impide que D llegue al producto final para 11.10(d)/(e) en ESTE checkpoint

`Finding.d_sufficiency` (el valor que `apply_conclusion_preconditions()`
lee para decidir la conclusión final) NUNCA se puebla con el resultado de
`verify_sufficiency_aggregated()` salvo que exista un "candidato ganador"
con anclaje a nivel de headline (`by_req[req_id]` con `anchored=True`
para al menos un candidato) -- ver `chunked_engine.py` línea ~1729
(`if "a_anchor" in best:`). Es un gate TOTALMENTE INDEPENDIENTE del
defecto B3 (que vive dentro de la agregación D en sí).

Verificado con datos reales de este checkpoint:

| Requisito | candidatos headline anclados | D llega a Finding.d_sufficiency? |
|---|---|---|
| `21_CFR_11.10(e)` | **0 de 1** | NO -- D calculado (PARTIALLY_MET) pero nunca adjuntado |
| `21_CFR_11.10(d)` | **0 de 3** | NO -- D calculado (contradicción genuina) pero nunca adjuntado |
| `21_CFR_11.10(g)` | 3 de 6 | SÍ |
| `21_CFR_11.50_11.70` | 3 de 6 | SÍ |

Para 11.10(d)/(e) en este checkpoint, la conclusión final (`PROVISIONAL_GAP`
para ambos) queda decidida enteramente por `absence_consolidator.
consolidate()` sobre `verified_records_by_req` -- un canal que NUNCA
consultó D. El fix B3 es correcto y no necesita tocarse, pero **por sí
solo no cambia el bucket Tier-1 de estos dos requisitos en este documento
histórico** -- coincide con lo que R3_T1_4 §4.1 ya anticipaba
("CONFIRMED no alcanzable para 11.10(e) en este documento, por cobertura
real, no por B3"), pero aquí se ve más fino: ni siquiera se intenta,
porque el candidato ganador headline nunca ancló.

## Criterios de aceptación F2-DRY (1.2 a-f)

```
a) informe se genera sin error, 5 requisitos, buckets validos, page_or_section
   normalizado:                                                    PASA
b) 11.10(e) con estado honesto, contradicted vacio, PRUEBA de que B3
   llega al producto final:                                        PARCIAL --
   llega hasta Finding.d_sufficiency? NO (gate headline independiente,
   ver hallazgo arriba). Llega hasta la FUNCION de agregacion? SI,
   confirmado con datos reales.
c) 11.10(d) sigue bloqueado por contradiccion genuina:              PASA a nivel
   de funcion (D=NOT_ASSESSABLE, contradicted no vacio) -- el bucket final
   (PROVISIONAL_GAP) no viene de D en este caso, mismo gate que (b).
d) cada requisito NEEDS_HUMAN_REVIEW tiene entrada en cola con
   candidatos/paginas/extractos:                                   PASA --
   3 entradas en review_queue_entries_DRY_RUN.json (aislado, cola real
   NUNCA tocada -- verificado con git diff)
e) ningun bucket huerfano (NOT_OBSERVED_OPTIONAL de F0.5 verificable):
   PASA -- 21_CFR_11.50_11.70 cae correctamente en OPTIONAL_NOT_OBSERVED
f) original en disco intacto (SHA-256 antes/despues):               PASA --
   documento 56095a75... y checkpoint f4226cc8... identicos, verificados
```

## Aislamiento verificado (cero contaminación de estado compartido)

- `human_review_queue.REVIEW_QUEUE_FILE` monkeypatched a
  `review_queue_dry_run.jsonl` (mismo patrón que
  `factory/tests/conftest.py:isolated_review_queue`) -- confirmado con
  `git diff factory/layer9/review_queue.jsonl`: el único diff presente es
  el que YA existía antes de esta sesión (entrada `chunked-50534e75927c`
  de una corrida anterior, ajena a este dry-run).
- No se llamó `evaluate_chunked()` en el intento aprobado -- cero riesgo
  sobre `checkpoint_store`/`validation_evidence_writer`/`audit_writer`.
- Checkpoint original y documento fuente verificados byte-idénticos
  antes/después (SHA-256).

## Artefactos generados (ruta de trabajo separada, marcados DRY_RUN)

```
factory/regulatory/pilot_run/tier1_dry_run_20260812/
├── replay_f2_dry.py                        (script, no versionado aun)
├── chunked-943a62bcbb85.checkpoint.json     (copia, para el intento 1 fallido)
├── informe_tier1_DRY_RUN.md                 (banner DRY_RUN en portada)
├── verified_conclusions_DRY_RUN.json
├── governed_exceptions_DRY_RUN.json         (vacio -- 0 excepciones)
└── review_queue_entries_DRY_RUN.json        (3 entradas, aisladas)
```

## Pendiente: CHECKPOINT 1 -- ciclo humano en vivo (1.3)

No ejecutado en esta corrida -- requiere que TÚ abras la UI de revisión y
registres una decisión real sobre una de las 3 entradas del dry-run
(`finding-chunked-943a62bcbb85-21_CFR_11.10(d|e|g)`), con tu identidad.
Nota: estas entradas viven SOLO en `review_queue_dry_run.jsonl`, aisladas
-- la UI de producción no las verá a menos que se decida (aparte, con tu
aprobación) promoverlas a la cola real, algo que esta corrida NO hizo.

**DETENERSE.** Bloque 1 completo salvo 1.3 (tuyo). No se avanza a bloque
2 (evaluación de si F2-LIVE se justifica) sin tu revisión de este
hallazgo -- en particular, decidir si el gate de "candidato ganador
headline" (independiente de B3) merece su propia corrida de diagnóstico
antes de cerrar R3-T1.

──────────────────────────────────────────────────────────────────────────────
INVESTIGACIÓN DEL GATE HEADLINE (2026-08-12, a pedido de Cesar, antes de seguir)
──────────────────────────────────────────────────────────────────────────────

## Mecanismo exacto (código, sin ambigüedad)

`chunked_engine.py`:
- Línea 1405: un chunk con `estado == "evidencia_insuficiente"` NUNCA
  produce un candidato headline para `by_req[req_id]` (`continue` antes
  de construirlo).
- Línea 611-614 (`_is_anchored`): un candidato se marca `anchored=True`
  solo si `evidencia_exacta` (la cita RESUMEN de todo el requisito, un
  campo distinto de las citas por criterio) es substring literal exacto
  del texto del chunk. Vacío o ausente → `anchored=False` de inmediato.
- Línea ~1729 (`if "a_anchor" in best:`): `verify_sufficiency_aggregated()`
  (D, con el fix B3) solo se llama y su resultado solo se adjunta al
  `Finding` si existe un candidato `anchored=True` que gane
  (`all_candidates = [c for c in by_req.get(req_id, []) if c["anchored"]]`).
  Si NINGÚN candidato ancla, el Finding cae en la rama "sin candidatos"
  (líneas 1604-1687), donde `d_sufficiency` nunca se asigna (queda `None`
  por default del dataclass) -- D se calculó, pero nadie lo lee.

## Causa raíz confirmada con datos reales (`raw_response` completo, chunk 20, `21_CFR_11.10(e)`)

```
estado (headline)        = "cumple_parcialmente"
evidencia_exacta (headline) = ''          ← el modelo la dejó VACÍA

criterion_assessments (nivel fino, la MISMA respuesta del modelo):
  Timestamp de fecha/hora.              → MET, quote="UR3.3.1 Every time..." (real, ancla)
  Registro de entradas y acciones...    → MET, quote="UR3.3.1 Every time..." (real, ancla)
  (7 criterios más)                     → NOT_MET, quote=''
```

El modelo hizo el trabajo fino correctamente -- 2 de 9 criterios con cita
verbatim real que SÍ ancla contra el chunk -- pero dejó vacío el campo
resumen de nivel superior. `_is_anchored('', chunk_text)` devuelve `False`
de inmediato (línea 612) → el candidato nunca gana → D, ya corregido por
B3, se descarta sin usarse. Mismo patrón para `21_CFR_11.10(d)` (los 3
candidatos crudos llevan el marcador `"(no anclado en el chunk,
descartado)"` que el propio código pone cuando `anchored=False`).

## Diagnóstico: gap de diseño conocido, mismo tipo que B3, nunca cerrado

El propio código lo documenta (comentario de R2.1 Opción C, 2026-08-10,
línea ~1718): *"A/B/C siguen siendo del candidato ganador (cita/anclaje/
relevancia son propiedades de ESA cita, no se agregan)"*. Cuando se
diseñó la agregación de D entre chunks, A/B/C (el anclaje headline) se
dejó deliberadamente como propiedad de UN candidato único -- nunca se
contempló el caso donde NINGÚN chunk produce un candidato headline
anclado, aun cuando el nivel fino (`criterion_assessments`) sí tiene
evidencia real y anclada. Es, en espíritu, el mismo defecto que B3: el
modelo se contradice entre dos campos de su propia salida (aquí:
`evidencia_exacta` headline vacío vs. `criterion_assessments` con citas
reales) y el motor no reconcilia esa contradicción -- descarta todo lo
fino cuando lo grueso falla.

## Decisión de Cesar (2026-08-12)

Documentar y DETENER aquí -- sin diseñar ni implementar ningún fix en
esta corrida. Queda registrado como candidato de defecto nuevo
("gate de candidato headline", en la misma familia que B1/B2/B3, sin
letra asignada todavía) para una corrida futura, con toda la evidencia de
causa raíz ya reunida arriba -- no hace falta re-investigar desde cero.

```
HEADLINE_GATE_ROOT_CAUSE =  by_req candidate solo gana si evidencia_exacta
                             (cita headline) ancla literal -- 'evidencia_insuficiente'
                             nunca produce candidato, evidencia_exacta vacia/no
                             literal descarta el candidato aunque criterion_assessments
                             (D, ya con fix B3) tenga citas reales y ancladas
CONFIRMED_CASES =           21_CFR_11.10(e) chunk20 (evidencia_exacta='', 2/9
                             criterios MET con cita real ignorados);
                             21_CFR_11.10(d) chunks18/19/20 (mismo patron)
RELATION_TO_B3 =            gap DISTINTO e independiente -- B3 vive dentro de
                             verify_sufficiency_aggregated(); esto vive ANTES,
                             en la seleccion del candidato ganador que decide si
                             D se llama y se adjunta al Finding
STATUS =                    documentado, SIN disenar fix, SIN tocar codigo
NEXT =                      corrida futura -- decidir si amerita su propio R3-T
                             (fix + tests) antes de reintentar F2-DRY bloque 1
                             sobre este mismo checkpoint
```
