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
