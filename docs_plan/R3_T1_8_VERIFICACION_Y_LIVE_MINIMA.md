# R3-T1.8 — VERIFICACIÓN DE CIERRE Y VALIDACIÓN MÍNIMA EN VIVO (previo a R4)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_8_VERIFICACION_Y_LIVE_MINIMA.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# R3-T1 quedó CERRADO con firma humana real. Esta corrida NO reabre lo
# cerrado: verifica tres puntos que salieron "mejor de lo esperado" o
# quedaron sueltos, prepara el terreno para R4, y ejecuta la ÚNICA
# validación en vivo que falta — mínima (3-5 llamadas), no las 29.
#
# Reglas duras: bloques 0-3 con CERO llamadas LLM; el bloque 4 solo tras
# firma; no MarkItDown; no cambiar modelo; NO aflojar validadores; no
# commit sin diff + aprobación.
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. VERIFICACIÓN DE B1 — ¿EL BUCKET `CONFIRMED` RESPETA LA ELEGIBILIDAD?
──────────────────────────────────────────────────────────────────────────────

El criterio acordado de RAMA B era SUPPORTING_EVIDENCE_UNDER_REVIEW.
El resultado fue `CONFIRMED` / `PROVISIONALLY_PARTIALLY_DOCUMENTED`, con
`positive_conclusion_eligibility` todavía en `PROVISIONAL_ONLY`. Salió
mejor de lo esperado — y por eso hay que probarlo, no celebrarlo.

0.1 Trazar en código cómo se decide el bucket `CONFIRMED` y confirmar con
    evidencia (archivo:línea) si respeta `positive_conclusion_eligibility`:
    - HIPÓTESIS A (esperada): el prefijo `PROVISIONALLY_` ES el mecanismo
      de respeto — la conclusión positiva existe pero marcada provisional
      porque B1 no está promovido. ⇒ correcto, documentarlo explícitamente
      para que nadie lo confunda con un cumplimiento declarado.
    - HIPÓTESIS B (grave): el bucket `CONFIRMED` se emite sin consultar la
      elegibilidad ⇒ es un BYPASS del gate B1 introducido por la
      superficie única. ⇒ DETENERSE, reportar, y corregir antes de nada
      más. El informe estaría afirmando más de lo que la gobernanza
      autoriza.
0.2 Test bloqueante en cualquiera de los dos casos: con
    `positive_conclusion_eligibility=PROVISIONAL_ONLY`, ningún requisito
    puede alcanzar una conclusión positiva NO provisional. Que el
    invariante quede fijado por test, no por lectura.
0.3 Verificar que el informe Tier-1 comunica al lector la diferencia:
    "CONFIRMED provisional (anclado, pendiente de elegibilidad + sign-off)"
    no puede leerse como "cumple". Ajustar el texto del informe si induce
    a error — un QA leyendo `CONFIRMED` a secas puede interpretarlo mal.

──────────────────────────────────────────────────────────────────────────────
1. CALIDAD DE LA FIRMA HUMANA Y SEMÁNTICA DE LA DECISIÓN
──────────────────────────────────────────────────────────────────────────────

La firma quedó con `human_confirmed_evidence.quote: "mejora"` — válida
como acto, pobre como dato. Ese campo alimentará el Golden Dataset.

1.1 Definir la SEMÁNTICA de decidir sobre cada tipo de entrada, y
    documentarla en la UI y en el schema:
    - hallazgo con evidencia anclada ⇒ "confirmar" significa: la evidencia
      citada sustenta el requisito ⇒ `quote` DEBE ser la cita real (o la
      referencia al candidato que el revisor validó);
    - hallazgo bloqueado por contradicción genuina (el caso firmado)
      ⇒ "confirmar" ¿qué significa exactamente? Definirlo: probablemente
      "acepto el bloqueo y la necesidad de revisión adicional", que NO es
      una confirmación de evidencia ⇒ el campo `quote` no aplica y no
      debería exigirse ni rellenarse con texto libre.
1.2 VALIDACIÓN del campo: cuando el tipo de decisión requiere cita, el
    endpoint la valida (no vacía, y preferiblemente que corresponda a un
    candidato mostrado); cuando no aplica, el campo se omite. Nada de
    aceptar cualquier string.
1.3 El registro existente NO se reescribe (append-only). Se anota una
    corrección/aclaración enlazada explicando que fue una validación de
    ciclo (`DRY_RUN_VALIDATION`) y que el `quote` no constituye evidencia
    confirmada. Y que no entre al Golden Dataset.

──────────────────────────────────────────────────────────────────────────────
2. CERRAR LAS MINAS ANTES DE R4 (Ruta D y código muerto)
──────────────────────────────────────────────────────────────────────────────

La auditoría documentó que la Ruta D (remediación) está LATENTE y se
rompería si se activa sin la superficie única. **R4-T1 es exactamente la
fase que la activa** — así que esto se cierra ahora, no después.

2.1 Ruta D: hacerla consumir `candidate_validity.resolve_candidate_evidence()`
    igual que A y B, o —si aún no tiene llamador— dejarla explícitamente
    bloqueada con un fail-closed que impida activarla sin pasar por la
    superficie única. Test que lo demuestre.
2.2 Código muerto (`verified_pipeline.py` sin llamadores): proponer su
    retiro o su marca `DEPRECATED` con nota — decisión de Cesar. Riesgo
    real: que una fase futura lo reviva creyéndolo vigente.
2.3 Divergencia interna de la Ruta B (dos algoritmos de anclaje apilados:
    `_is_anchored` vs `match_citation`): confirmar si la superficie única
    ya la resolvió; si queda algún resto, unificarlo ahora.
2.4 Extender el test de no-bypass para cubrir las 4 rutas (A, B, C según
    corresponda, y D), no solo las dos vivas.

──────────────────────────────────────────────────────────────────────────────
3. CHEQUEO DE FRESCURA DE DESPLIEGUE (lección del incidente)
──────────────────────────────────────────────────────────────────────────────

El endpoint estuvo un día entero commiteado pero ausente del contenedor
vivo. "Commiteado" ≠ "corriendo".

3.1 Añadir a Gate 0 (o a `factory_status.sh`) una verificación barata:
    comparar el commit/hash del código montado contra el que el servicio
    vivo reporta (o verificar que las rutas esperadas existen en
    `/openapi.json`). Que un desfase se vea como WARN explícito.
3.2 Documentar en el skill/memoria: tras commitear endpoints nuevos,
    `docker compose restart` del servicio afectado (bind mount ⇒ sin
    rebuild) es parte del ciclo, no un extra.
3.3 Tests ambientales de Gate 0 (Playwright/endpoint vivo, 6 fallos + 2
    errores caracterizados): asignarles dueño y tratamiento — aislarlos
    con marca (`@pytest.mark.requires_live_ui`) para que Gate 0 dé señal
    limpia y no se normalice el rojo. Proponer, no imponer.

>>> CHECKPOINT: bloques 0-3 entregados con diffs, sin llamadas LLM.
>>> DETENERSE para aprobación de Cesar antes del bloque 4.

──────────────────────────────────────────────────────────────────────────────
4. VALIDACIÓN MÍNIMA EN VIVO (3-5 llamadas) — EL ÚLTIMO RIESGO ABIERTO
──────────────────────────────────────────────────────────────────────────────

Riesgo residual declarado por el propio cierre de R3-T1: TODO se validó
sobre un checkpoint BASELINE — un perfil que ya no se usa. Falta confirmar
que las correcciones se sostienen con H2H4 real, que es el perfil de
producto. Es barato y cierra la única incógnita que queda.

4.1 Alcance MÍNIMO: `21_CFR_11.10(e)` sobre 3-5 chunks (el chunk ancla
    p.45-46 + 2-4 de contraste, incluyendo idealmente uno que en el
    replay aportó `NOT_MET` off-topic — para ver el fix B3 operar con
    datos nuevos, no históricos). Perfil H2H4, pipeline completo con la
    superficie única, hasta el bucket del informe.
4.2 Proponer autorización con tope 6 y DETENERSE para firma. Ejecutar en
    background (systemd-run/tmux, verificación de supervivencia a SSH).
    Costo esperado: ~50-60 min de pared a la latencia medida en F1.
4.3 CRITERIO PRE-FIJADO (fijado ahora, antes de correr):
    a) el chunk ancla ancla de nuevo bajo H2H4 con pipeline corregido;
    b) el bucket final coincide con lo que el replay predijo para
       `11.10(e)` (o si difiere, la diferencia se explica — no se maquilla);
    c) los NOT_MET off-topic no producen falsa contradicción (B3 vivo);
    d) si el modelo deja el headline vacío, el rescate por criterios
       ancladados opera (B4/superficie única vivos);
    e) ninguna cita no anclada aparece como evidencia;
    f) la entrada de cola se genera con sus candidatos si corresponde.
4.4 Si CUMPLE: el pipeline queda validado en vivo con el perfil de
    producto ⇒ R4-T1 habilitado. Si NO cumple: el replay no era
    representativo del perfil real ⇒ DETENERSE y reportar; sería un
    hallazgo importante y barato de haber encontrado ahora.

──────────────────────────────────────────────────────────────────────────────
5. PREPARAR R4-T1 (diseño, sin ejecutar)
──────────────────────────────────────────────────────────────────────────────

Con el bloque 4 en verde, dejar listo el plan de R4-T1 (borrador corregido
controlado), con estas restricciones ya conocidas:
- SOLO hallazgos con decisión humana confirmada generan cambios (nunca un
  PROVISIONAL_GAP sin revisar, nunca un CONFIRMED provisional sin B1);
- la Ruta D ya cerrada (bloque 2) es su prerequisito técnico;
- original intacto, marca NO-APROBADO, redline, trazabilidad
  hallazgo→cambio;
- gate de aceptación: el Piloto 2 original sobre el documento más pequeño;
- presupuesto dimensionado con las latencias reales, y el mismo método de
  fases (barato primero, completo solo si pasa).
NO iniciar R4 en esta corrida.

──────────────────────────────────────────────────────────────────────────────
6. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
B1_BUCKET_CONSISTENCY =        (HIPÓTESIS A confirmada / B = bypass corregido)
PROVISIONAL_INVARIANT_TEST =   (fijado por test)
REPORT_WORDING =               (CONFIRMED provisional no inducible a error)
SIGNATURE_SEMANTICS =          (definida por tipo de entrada)
QUOTE_FIELD_VALIDATED =        (exigida cuando aplica / omitida cuando no)
DRY_RUN_ENTRY_ANNOTATED =      (no entra al Golden Dataset)
ROUTE_D =                      (unificada / fail-closed hasta unificar)
DEAD_CODE =                    (retirado / DEPRECATED — decisión de Cesar)
NO_BYPASS_TEST_SCOPE =         (4 rutas)
DEPLOY_FRESHNESS_CHECK =       (en Gate 0/status)
AMBIENT_TESTS =                (marcados / dueño propuesto)
LIVE_MIN_AUTHORIZATION =       (tope 6, firmada / pendiente)
LIVE_MIN_RESULT =              (criterios a–f)
REPLAY_WAS_REPRESENTATIVE =    (sí/no — el hallazgo clave del bloque 4)
R4_PLAN =                      (listo, no iniciado)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: la aprobación de los bloques 0-3, la firma de la
autorización mínima, y la revisión del resultado en vivo. Ninguna corrida
mayor se autoriza hasta que el bloque 4 demuestre que lo validado por
replay se sostiene con el perfil real de producto — es la última pieza
que separa "funciona en los datos que teníamos" de "funciona".

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12 — BLOQUES 0-3 (cero llamadas LLM)
──────────────────────────────────────────────────────────────────────────────

## Bloque 0 — B1: HIPÓTESIS A confirmada, más un bug real corregido

**0.1 — Trazado en código**: `absence_consolidator.py` líneas 263-293
(`apply_conclusion_preconditions()`, paso 4 "§10 Gobernanza de fuente").
Con `positive_conclusion_eligibility="PROVISIONAL_ONLY"`, `_PROVISIONAL_
EQUIVALENT` (líneas 173-178) mapea `PARTIALLY_DOCUMENTED →
PROVISIONALLY_PARTIALLY_DOCUMENTED` + flag `SOURCE_PENDING_REVERIFICATION`,
y `validate_result_status_allowed()` (línea 290, `provisional_evidence_
model.py`) es un segundo gate duro: `PROVISIONALLY_PARTIALLY_DOCUMENTED`
está en `ALLOWED_RESULTS_WHILE_PENDING_REVERIFICATION`, cualquier
resultado final "pelado" está en `PROHIBITED_FINAL_RESULTS_WHILE_PENDING`.
**HIPÓTESIS A confirmada** — el prefijo `PROVISIONALLY_` ES el mecanismo
de respeto, no un bypass. Este archivo nunca lo toca `candidate_validity.py`.

**0.2 — Bug real encontrado, no solo verificación**: al fijar el
invariante con un test end-to-end que ejercita específicamente la ruta
de rescate B4/B5 (headline vacío, 5/5 criterios `MET`), la conclusión
caía en `EVALUATION_INCOMPLETE/ABCD_NOT_EVALUATED` en vez de
`PROVISIONALLY_DOCUMENTED`. Causa raíz: `abcd.a_anchor` (y por lo tanto
`substantive_evidence_accepted`, que `apply_conclusion_preconditions()`
usa como gate real) se calculaba sobre `evidencia` ORIGINAL (`''` para
un candidato rescatado) -- `verify_anchor('', ...)` es `FAIL`
incondicional, así que `substantive_evidence_accepted` quedaba `False`
pese a `D=MET` real. Con `PARTIALLY_MET` este bug era invisible (esa
rama de `apply_conclusion_preconditions` no depende de
`substantive_evidence_accepted`); solo se manifestaba con `D=MET`
completo -- un caso que el checkpoint histórico de R3-T1.5-7 nunca tuvo
(11.10(e) ahí es 2/9, parcial), así que nunca se había visto.

**Fix** (`chunked_engine.py`): cuando `resolved.headline_source ==
"derived_from_criterion_quotes"`, se recalcula `abcd` (A/B/C, nunca D)
sobre `resolved.verifiable_quote` -- la misma cita única y literal que
la superficie única ya usó para decidir que el candidato ganó. Nunca
cambia D, nunca inventa evidencia -- solo hace que A sea consistente con
el candidato que realmente ganó, no con el headline vacío que perdió.

**0.3 — Wording del informe**: `_BUCKET_LABELS[CONFIRMED]` ("Confirmado
(anclado, pendiente de sign-off humano)") no distinguía visualmente un
resultado `PROVISIONALLY_` de uno final. Nueva función `_estado_label()`
en `tier1_report.py`: cuando `r.conclusion.startswith("PROVISIONALLY_")`,
la columna "Estado" del markdown muestra **"Confirmado PROVISIONAL
(fuente sin reverificar -- NO es declaración de cumplimiento)"** en vez
del genérico -- refuerza la misma señal que ya existía en la columna
"Conclusión" y en el detalle, en la columna que un lector mira primero.

**Guardianes**: `test_b1_provisional_eligibility_survives_headline_rescue`
(chunked_engine, fija el fix del bug real) +
`test_confirmed_requirement_includes_anchored_quote_and_source_caveat`
extendido (tier1_report, fija el wording). 225 tests en verde.

**Replay real re-verificado**: sin cambios en el resultado ya firmado
(11.10(e) sigue `CONFIRMED`/`PROVISIONALLY_PARTIALLY_DOCUMENTED`) -- el
bug solo afectaba el caso `D=MET` completo, que ese checkpoint no tiene.

## Bloque 1 — Semántica de la firma humana

**1.1-1.2 — Validación por tipo de conclusión** (`factory/api/routes/
layer9.py`, endpoint `/review/findings/{rc_id}/decide`): dos conjuntos
nuevos, `_FINDING_QUOTE_REQUIRED_CONCLUSIONS = {SUPPORTING_EVIDENCE_
UNDER_REVIEW}` (confirmar exige `confirmed_quote` real, 422 si vacío) y
`_FINDING_QUOTE_NOT_APPLICABLE_CONCLUSIONS = {EVALUATION_INCOMPLETE,
PROVISIONAL_GAP, DOCUMENTATION_GAP, CROSS_REFERENCE_MISSING}` (confirmar
NUNCA acepta texto libre en `confirmed_quote`, 422 si se envía). UI
(`review.js`) actualizada en paralelo: oculta los campos página/cita y
cambia el botón a "Confirmar bloqueo/ausencia" cuando la conclusión no
admite cita; marca la cita como obligatoria (no "opcional") cuando sí
aplica.

**1.3 — Anotación del registro ya firmado** (append-only, nunca
reescrito): `RECORD_ANNOTATION-2026-007` en `decisions_v2.jsonl`
(mecanismo real ya existente en el proyecto, `never_authorizes: true`),
apuntando a `finding-chunked-943a62bcbb85-r3t17-dryrun-validation-
21_CFR_11.10(d)` -- declara explícitamente que `human_confirmed_evidence.
quote="mejora"` NO es una cita de evidencia real (la conclusión de esa
entrada era `EVALUATION_INCOMPLETE`, donde la validación nueva ahora
habría rechazado ese texto) y que **no debe entrar al Golden Dataset**.

**Guardianes**: 5 tests nuevos en `test_finding_review_decision_endpoint.py`
(exige cita cuando aplica, rechaza texto libre cuando no aplica, permite
confirmar sin cita cuando corresponde, rechazar nunca exige cita). 13
tests en verde en ese archivo.

**Incidente propio, corregido en el camino**: dos veces en esta sesión
(bloque 0 y ahora) un script de depuración manual (`python3 -c ...`,
fuera de pytest) escribió por accidente en la cola real de producción --
mismo patrón exacto que R3-T1.7 ya había encontrado y corregido.
Corregido con el mismo mecanismo (`supersede_finding()`, motivo
explícito, nunca borrado). **Lección para mí mismo**: cualquier
`python3 -c` de depuración que llame `evaluate_chunked(use_verified_
pipeline=True)` debe monkeypatchear `REVIEW_QUEUE_FILE` manualmente --
el fixture autouse solo protege corridas de pytest.

## Bloque 2 — Cerrar las minas antes de R4

**2.1 — Ruta D activada de forma segura**: `gap_assessment_finding_
mapper.py::_derive_citation_anchor_status()` ahora detecta un headline
derivado (`candidate_validity.is_derived_headline()`, nueva función
pública) y re-verifica CADA cita individual (`split_derived_quotes()`)
contra el texto fuente -- `VERIFIED` solo si TODAS anclan; una sola cita
fabricada invalida el conjunto. Sin esto, esta ruta (hoy sin llamador de
producción, pero prerequisito técnico de R4-T1) habría reventado con el
MISMO defecto (texto compuesto que nunca existe literalmente en el
documento) por un quinto sitio -- el mismo patrón B3→B4→B5 apareciendo
de nuevo si no se cierra ahora.

**2.2 — Código muerto marcado**: `verified_pipeline.py` (sin llamadores
de producción, confirmado por grep) ahora lleva un docstring `DEPRECATED`
explícito con el riesgo real (una fase futura podría revivirlo creyéndolo
vigente, reintroduciendo una tercera implementación de la misma lógica).
No se borra -- decisión de retiro definitivo pendiente de Cesar.

**2.3 — Divergencia interna de la Ruta B, evaluada**: `_is_anchored`
(estricto, sin fuzzy) vs `match_citation` (con fuzzy, dentro de
`verify_llm_output`) siguen siendo dos implementaciones distintas, pero
ya NO son una fuente de defecto: Ruta B solo alimenta a `match_citation`
con `resolved.verifiable_quote`, que `is_literally_anchored` YA garantizó
como literal -- `match_citation` siempre encontrará al menos "exact".
Divergencia estructural documentada, benigna, no requiere unificación
adicional en esta corrida.

**2.4 — Guardián de no-bypass extendido**: 2 tests nuevos en
`test_candidate_validity_no_bypass.py` -- confirman que la Ruta D importa
`is_derived_headline`/`split_derived_quotes` (nunca reimplementa el
marcador) y que esas funciones existen como accesores públicos únicos.

**Guardianes**: 3 tests nuevos en `test_gap_assessment_finding_mapper.py`
+ 2 en `test_candidate_validity_no_bypass.py`. 43+2 tests en verde.

## Bloque 3 — Frescura de despliegue (lección directa del incidente 4.4 de R3-T1.7)

**3.1 — Chequeo de frescura agregado**: nuevo test
`test_deploy_freshness_all_source_routes_are_live()` en
`test_governance_ui_deploy_consistency_live.py` (mismo archivo que YA
tenía el patrón equivalente para JS estático, `RC-5`, nunca extendido al
backend). Extrae TODAS las rutas (`@router.<método>(...)` + `prefix=` de
cada `APIRouter`) de `factory/api/routes/*.py` por análisis estático, las
compara contra `/openapi.json` del servidor VIVO. Detectó y confirmó
correctamente el estado real tras el restart (0 rutas faltantes) --
habría detectado el incidente real un día antes si hubiera existido.

**3.2 — Lección registrada en memoria**: `feedback_technical.md` --
"Commiteado no es corriendo — factory-api (uvicorn) no tiene --reload",
con el incidente real como motivo y el procedimiento (`docker compose
restart`, ~15s, seguro por bind mount) como aplicación.

**3.3 — Tests ambientales marcados**: nuevo marker `requires_live_ui`
(`factory/tests/conftest.py:pytest_configure`), aplicado a los 3
archivos 100% dependientes de servidor/navegador vivo
(`test_governance_catalog_version_playwright.py`,
`test_review_queue_finding_ui_playwright.py`,
`test_governance_ui_deploy_consistency_live.py`, este último además
conserva su `skipif` fino ya existente). `pytest -m "not requires_live_ui"`
da Gate 0 limpio sin normalizar el rojo; correr con el marker sigue
siendo la única forma de detectar incidentes de despliegue reales.

## Suite completa tras bloques 0-3

```
Suite relevante (targeted): 225+43+13+... tests, 0 fallos
Gate 0 limpio (-m "not requires_live_ui"): corriendo en background al
  cierre de este documento -- ver resultado agregado antes de bloque 4
```

## Entrega parcial (bloques 0-3)

```
B1_BUCKET_CONSISTENCY =        HIPOTESIS A confirmada (absence_consolidator.py
                                263-293) + bug real encontrado y corregido
                                (A stale en candidato rescatado con D=MET)
PROVISIONAL_INVARIANT_TEST =   test_b1_provisional_eligibility_survives_
                                headline_rescue, fijado
REPORT_WORDING =                _estado_label() -- "Confirmado PROVISIONAL"
                                explicito para conclusiones PROVISIONALLY_
SIGNATURE_SEMANTICS =          definida por conclusion (2 conjuntos,
                                factory/api/routes/layer9.py)
QUOTE_FIELD_VALIDATED =        exigida (SUPPORTING_EVIDENCE_UNDER_REVIEW) /
                                rechazada si no aplica (422 en ambos casos)
DRY_RUN_ENTRY_ANNOTATED =      RECORD_ANNOTATION-2026-007, no entra al
                                Golden Dataset (declarado explicito)
ROUTE_D =                      activada de forma segura (is_derived_headline
                                + verificacion por cita individual)
DEAD_CODE =                    verified_pipeline.py marcado DEPRECATED,
                                retiro pendiente de decision de Cesar
NO_BYPASS_TEST_SCOPE =         extendido a Ruta D (Ruta C fuera de familia,
                                sin cambios necesarios)
DEPLOY_FRESHNESS_CHECK =       test_deploy_freshness_all_source_routes_are_live,
                                en test_governance_ui_deploy_consistency_live.py
AMBIENT_TESTS =                marcados con requires_live_ui (3 archivos),
                                dueño no asignado (propuesto, no impuesto)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

**CHECKPOINT.** Bloques 0-3 completos, cero llamadas LLM, con diffs
pendientes de tu revisión y aprobación antes de commitear. DETENERSE
aquí -- el bloque 4 (validación mínima en vivo, 3-5 llamadas) requiere
tu firma explícita de autorización antes de ejecutarse.

Bloques 0-3 commiteados en `17c41d0` (2026-08-12), con aprobación explícita
de Cesar tras revisión del diff completo.

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12 — BLOQUE 4 (validación mínima en vivo)
──────────────────────────────────────────────────────────────────────────────

## Autorización

`PILOT_EXECUTION-2026-017` (`agent_proposed`) → `PILOT_EXECUTION-2026-018`
(`human_confirmed` por `cesar`, 2026-08-12T21:xx, citando explícitamente el
mensaje de chat "continua con lo pendiente ya se firmo 21_CFR_11.10(e) valida
y continua" como acto de firma). Tope: 6 llamadas. Alcance: `21_CFR_11.10(e)`
sobre `RW-0005`, perfil H2H4.

## Ejecución (2 corridas, 5 de 6 llamadas usadas)

**Corrida 1** (3 llamadas, `PILOT_EXECUTION-2026-018`): 3 `PilotSampleUnit`
separadas (ancla p.45-46, contraste p.9, contraste p.13) -- **defecto de
diseño propio**: cada unidad genera su PROPIO `run_id` independiente
(`chunked-2678358a06b3`, `chunked-e6994ea8e953`, `chunked-d9b5bc77c9db`),
así que nunca se agregan entre sí -- el bucket final y el fix B3
(contradicción entre chunks del MISMO run) no quedaron ejercitados como
pedía el plan.

**Corrida 2** (2 llamadas, mismo `PILOT_EXECUTION-2026-018`, presupuesto
acumulado exacto 3+2=5 de 6 firmadas, sin exceder): corregido -- UNA sola
`PilotSampleUnit` con `page_indices=(44,45,12)` (ancla + contraste en el
MISMO run), `run_id` único `chunked-c2c7dff6900c`, 2 chunks reales
agregados en `verified_records_by_req`.

## Resultado contra los criterios pre-fijados (a-f)

**a) El chunk ancla ancla de nuevo bajo H2H4: CUMPLE.** `a_anchor=PASS`
(match_type `normalized`), cita real UR3.3.1/UR3.3.2 idéntica en esencia a
la del checkpoint histórico `chunked-943a62bcbb85`.

**b) El bucket final coincide con lo que el replay predijo (o si difiere,
se explica): DIFIERE, EXPLICADO -- no coincide literal.** El replay
histórico predijo `CONFIRMED`/`PROVISIONALLY_PARTIALLY_DOCUMENTED`; esta
corrida dio `EVALUATION_INCOMPLETE`/`ABCD_D_NOT_ASSESSABLE`. Causa raíz
verificada en el propio candidato: `d_reason: "contrato de
criterion_assessments violado: 2 problema(s)"` -- los criterios 2 y 3
(timestamp, registro de acciones) vinieron `status=MET` con
`evidence_quote` real pero `evidence_location` VACÍO, violación de
contrato NIVEL A (`_find_contract_violations`, rechazo atómico del array
completo). **Es la MISMA clase de incumplimiento de instrucción del
modelo (`qwen2.5:7b`) ya documentada como hallazgo secundario en
`docs_plan/R3_T1_2_F1_EVIDENCIA/RESUMEN.md`** ("es esperable que esta
clase de violación aparezca de nuevo... no es necesario ni deseable
arreglarla aflojando el validador") -- reproducida de forma independiente
en esta llamada nueva, no causada por ningún fix de Bloques 0-3. El
guardián (capa D / contrato) actuó correctamente: bloqueó la conclusión
positiva en vez de aceptar un MET sin evidencia completa.

**c) Los NOT_MET off-topic no producen falsa contradicción (B3 vivo):
CUMPLE -- corregido tras reanálisis.** Verificación inicial incompleta:
el primer reporte miró `candidate["d_reason"]` (valor POR CHUNK, previo a
la agregación) y confundió el "contrato violado" del chunk ancla con la
causa del bloqueo agregado. Recomputado con los datos reales exactos
(`criterion_assessments`, `chunk_estado`, texto real de página vía
`_extract_pilot_excerpt`) llamando directamente a la función real
`verify_sufficiency_aggregated()`: `detail["contradicted"] = []` --
**nunca hubo contradicción real entre chunks** (`all_met & all_not_met`
vacío). El chunk de contraste (p.13, `chunk_estado="evidencia_insuficiente"`)
fue correctamente reclasificado por B3 (`_classify_criteria_for_chunk`,
`off_topic_chunk=True`) de NOT_MET a NOT_ASSESSABLE para sus 9 criterios
-- nunca colisionó en falso con los criterios MET del chunk ancla. El
bloqueo final (D=NOT_ASSESSABLE) vino de que el chunk ancla quedó
EXCLUIDO de la agregación por su propia violación de contrato (mismo
hallazgo de (b)), dejando la cobertura incompleta -- causa distinta de
(b), pero tampoco B3. **B3 funciona correctamente en vivo, bajo datos
reales nuevos.**

**d) Rescate por criterios anclados si el headline queda vacío (B4/B5
vivo): NO APLICABLE esta corrida.** El modelo devolvió headline
(`evidencia_exacta`) directamente no vacío -- el camino de rescate B4/B5
no se activó (nada que ejercitar).

**e) Ninguna cita no anclada aparece como evidencia: CUMPLE.** La cita
aceptada como headline está literalmente anclada (`a_anchor=PASS`); el
MET con evidencia incompleta (criterios 2/3) fue BLOQUEADO por el
contrato, nunca se coló como evidencia aceptada.

**f) La entrada de cola se genera con sus candidatos si corresponde:
CUMPLE (con nota).** Las 4 entradas (una por `run_id`) se generaron
correctamente en `review_queue.jsonl` (`EVALUATION_INCOMPLETE` para las 2
corridas con contradicción bloqueada, `PROVISIONAL_GAP` para las 2
corridas de solo-contraste sin evidencia). `candidates: []` en todas --
consistente con el path de despacho real (`_dispatch_contradiction_blocked_review`/
`_dispatch_baseline_gap_review` no pasan lista de candidatos), no un
defecto nuevo.

## Veredicto

**MIXTO, no un PASA limpio, pero con la mayoría de los criterios
cerrados.** (a), (c) y (e) confirman que el pipeline H2H4 + superficie
única (incluido el fix B3) siguen funcionando correctamente en vivo, con
datos nuevos, no históricos. (b) difiere del replay, pero con una causa
raíz identificada, verificada, y ya documentada como comportamiento
conocido y aceptado del modelo (no un defecto introducido por Bloques
0-3). (d) no quedó ejercitado -- 0/3 llamadas reales activó el camino de
rescate B4/B5 (headline siempre no vacío en este caso puntual). Presupuesto
agotado, 6 de 6 usadas, sin exceder lo firmado.

`REPLAY_WAS_REPRESENTATIVE = PARCIAL` -- el replay predice bien el caso
"feliz" (modelo cumple contrato), pero el pipeline real bajo H2H4 tiene
una tasa no despreciable de violación de contrato por llamada (ya vista en
F1 y de nuevo aquí) que el replay histórico (una sola corrida ya
"limpia") no capturó como variable. Esto no es un defecto de código --
es información real sobre el comportamiento del modelo que **condiciona
el presupuesto de R4-T1** (esperar reintentos/exclusiones por este motivo
con más frecuencia de la que el replay sugería).

Decisión de Cesar (chat, 2026-08-12): usar la última llamada solo para (d)
(fenómeno de un chunk, no requiere agregación) -- (c) quedó pospuesto en
ese momento por creerse sin respuesta con los datos existentes.

## Corrida 3 (1 llamada, `PILOT_EXECUTION-2026-018`, 5+1=6 de 6 exacto)

Una sola `PilotSampleUnit`, `page_indices=(44,)` (solo página 45, nunca 2
índices, para garantizar exactamente 1 llamada real bajo ninguna
circunstancia). `run_id` `chunked-e8208618982a`.

**Resultado**: `evidencia_exacta` (headline) de nuevo NO vacío -- B4/B5 NO
se activó (nada que rescatar). Mismo patrón de contrato violado:
`d_reason: "contrato de criterion_assessments violado: 2 problema(s)"` --
criterios 2 y 3 otra vez `MET` con `evidence_quote` real pero
`evidence_location` vacío.

**Hallazgo relevante para R4-T1** (más significativo que "fluke
ocasional"): en las 3 llamadas reales independientes de bloque 4 que
tocaron el chunk ancla (`chunked-2678358a06b3`, `chunked-c2c7dff6900c`
chunk 0, `chunked-e8208618982a`) -- 3 de 3 -- el modelo devolvió
`evidence_location` vacío para los criterios MET, y 0 de 3 devolvió el
headline top-level vacío. Esto sugiere que, para este documento/prompt/
perfil H2H4, el patrón "MET sin `evidence_location`" es **consistente y
esperable en la mayoría de las llamadas**, no un evento raro como sugería
la caracterización original de F1 ("es esperable que reaparezca") --
información directamente accionable para dimensionar el presupuesto de
R4-T1 (esperar reintentos/exclusiones por esta causa con más frecuencia
de la que el replay de un solo run históricamente limpio sugería). (d)
queda **NO EJERCITADO por agotamiento de presupuesto** (0/3 intentos
reales activó el camino de rescate) -- no refutado, solo sin datos con
headline vacío bajo H2H4 para este caso puntual.

## Reanálisis de (c) — cerrado sin gastar presupuesto nuevo

Al preparar la autorización para cerrar (c) con llamadas nuevas, se
detectó que el primer reporte de (c) se basó en el campo
`candidate["d_reason"]` (valor POR CHUNK, calculado antes de la
agregación) en vez del resultado agregado real. Recomputado llamando
directamente a `verify_sufficiency_aggregated()` con los datos exactos de
la corrida 2 (`criterion_assessments`, `chunk_estado`, texto real de
página vía `_extract_pilot_excerpt`): `detail["contradicted"] = []` --
nunca hubo contradicción real entre chunks. B3 reclasificó correctamente
el contraste off-topic. (c) queda **CUMPLE**, con los datos ya existentes
-- Cesar decidió explícitamente NO gastar las 2-3 llamadas adicionales
propuestas, dado este cierre.

```
LIVE_MIN_AUTHORIZATION =       PILOT_EXECUTION-2026-018, tope 6, firmada
                                por cesar (chat, 2026-08-12)
LIVE_MIN_RESULT =               a) CUMPLE  b) DIFIERE-EXPLICADO
                                c) CUMPLE (reanalisis, sin gasto nuevo)
                                d) NO EJERCITADO (0/3, presupuesto agotado)
                                e) CUMPLE  f) CUMPLE
REPLAY_WAS_REPRESENTATIVE =    PARCIAL -- caso feliz si, B3 confirmado en
                                vivo, tasa de violacion de contrato del
                                modelo mas alta y mas consistente de lo
                                que el replay sugeria (3/3 llamadas reales)
CALLS_USED =                   6 de 6 (presupuesto agotado, sin exceder)
R4_PLAN =                      NO iniciado -- pendiente de decision de
                                Cesar sobre bloque 5, considerando el
                                dimensionamiento de presupuesto de R4-T1
                                a la luz de la tasa real de violacion de
                                contrato (~3/3 en esta muestra)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

──────────────────────────────────────────────────────────────────────────────
EJECUCIÓN 2026-08-12 — BLOQUE 5 (diseño de R4-T1, sin ejecutar)
──────────────────────────────────────────────────────────────────────────────

Diseño completo en `docs_plan/R4_T1_PLAN_POR_FASES.md` -- se auditó
primero la infraestructura REAL ya existente (`remediation_package_service.py`,
schemas, generadores XLSX/DOCX, traceability/manifest, Ruta D) antes de
diseñar una sola línea nueva. R4-T1 resulta más acotado de lo esperado:
la máquina de estados de paquetes, los formatos de artefacto
(`CANDIDATE_DRAFT`/`REDLINE`/`REPORT`/`MANIFEST`) y los generadores de
documento YA existen y están probados -- lo que falta es (1) el wiring
cola-confirmada→Ruta D→paquete (hoy la cola es un callejón sin salida),
(2) la marca explícita NO-APROBADO en el candidato generado, (3) correr
el gate de aceptación (Piloto 2 original) con el pipeline conectado
extremo a extremo sobre hallazgos REALES confirmados (nunca sintéticos),
y (4) una decisión de gobernanza pendiente (si D5 cubre primera
generación o hace falta familia nueva). 3 de las 4 fases del plan
(R4-T1.0 a R4-T1.2) no requieren ninguna llamada LLM. `R4_T1_INICIADO = NO`
-- diseño únicamente, per este bloque.

```
BLOQUE_5_ENTREGA =              docs_plan/R4_T1_PLAN_POR_FASES.md
R4_T1_INICIADO =                NO
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```
