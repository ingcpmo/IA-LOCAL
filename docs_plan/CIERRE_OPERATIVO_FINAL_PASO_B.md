# CIERRE OPERATIVO FINAL — COMMIT DE PASO B + VERIFICACIONES PENDIENTES + GATE
# Archivo de instrucciones para Claude Code
# Destino: crea esta carpeta y copia todo el texto de la instruccion en esta ubicacion  docs_plan/CIERRE_OPERATIVO_FINAL_PASO_B.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# Autoridad: Capa 9 = Cesar.
# Paso B = PASS, confirmado con evidencia real. Esta corrida: (1) asegura
# ese trabajo en el repositorio antes de que se pierda, (2) cierra dos
# verificaciones menores pendientes, (3) presenta el gate final separando
# con claridad "motor de análisis validado" de "capacidad de liberar
# documentos" — son decisiones distintas.
#
# Cero llamadas LLM. No commit sin diff + aprobación explícita.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — ASEGURAR EL TRABAJO DE PASO B (prioridad máxima, primero)
──────────────────────────────────────────────────────────────────────────────

1.1 Mostrar diff completo de `factory/layer9/decisions/decisions_v2.jsonl`
    y `factory/layer9/review_queue.jsonl` — confirmar que el contenido
    corresponde exactamente a las firmas y resultados ya reportados
    (`JUDGMENT_EXECUTION-2026-004`, `EMBED_EXECUTION-2026-011`, los 30
    registros de Paso B) y nada más.
1.2 Mostrar el contenido de
    `factory/regulatory/pilot_run/paso_b_bloque4_20260822/` a incluir.
1.3 Esperar aprobación explícita de Cesar sobre este diff específico.
    Commit único, causa raíz: "resultado real de Paso B + firmas de
    gobernanza asociadas".
1.4 NO tocar en este commit: los 4 `.docx` de
    `dry_run_validation_r4_t1_1v2/`, ni los directorios sueltos de
    `pilot_run/` de sesiones previas (`fase2_2_...`, `fase2_3_...`, etc.)
    — quedan exactamente como el reporte los dejó, fuera de este alcance.
1.5 Tras el commit: confirmar que los 5 tests "canario" mencionados en el
    reporte (`test_no_test_in_this_file_wrote_to_the_real_store`, etc.)
    vuelven a PASS — es la prueba de que el diagnóstico era correcto.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — DOS VERIFICACIONES MENORES (0 LLM, con datos ya persistidos)
──────────────────────────────────────────────────────────────────────────────

2.1 N2: releer directamente su checkpoint/registro persistido (no citar
    memoria del proyecto) y confirmar `chunk_observation` /
    `not_observed_in_chunk` con evidencia real, con la ruta exacta del
    archivo verificado. Si algo no coincide con lo que memoria decía:
    reportarlo explícitamente, no reconciliar en silencio.
2.2 Discrepancia `log_count=68688` / `verified_count=68687`: identificar
    el `event_id` exacto que queda sin verificar y confirmar que
    corresponde al fork histórico ya documentado y aceptado (mismo
    `event_id`/posición ya citado en auditorías previas) — no un fork
    nuevo. Si el `event_id` no coincide con el fork conocido: es un
    hallazgo nuevo, deteniendo el gate hasta explicarlo.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — GATE FINAL, CON LA DISTINCIÓN EXPLÍCITA
──────────────────────────────────────────────────────────────────────────────

Presentar a Cesar dos decisiones SEPARADAS, no una:

**Decisión 1 — Motor de análisis (demostrado, listo para su palabra):**
```
ANALYSIS_ENGINE_VALIDATED = 12/12 unidades, 0 citas fabricadas,
    0 gaps falsos, negativos rechazados sin excepción (N1 en Paso B,
    N2 re-confirmado en Bloque 2.1), audit trail íntegro (fork histórico
    conocido, 0 forks nuevos), gobernanza con controles reales y
    testeados (JUDGMENT_EXECUTION, EMBED_EXECUTION, D4-A con alcance
    correcto, fail-closed de configuración, preservación de evidencia
    en reintentos).
RECOMENDACIÓN = el motor que LEE, JUZGA y ENCOLA hallazgos para revisión
    humana está validado de punta a punta con llamadas reales. Listo
    para que Cesar decida si lo declara operativo para uso regular.
```

**Decisión 2 — Capacidad de liberar documentos (NO existe todavía, es
otra conversación, no una activación):**
```
RELEASE_MECHANISM = create_release_record() sigue sin ningún endpoint
    que lo invoque — no está deshabilitado, NO EXISTE la ruta.
ACLARACIÓN = "entrar a producción" del motor de análisis (Decisión 1)
    NO habilita, ni implica, ni se acerca a que el sistema pueda liberar
    un documento GMP por sí mismo. Esa es una capacidad completamente
    distinta, que requeriría su propio diseño, su propio ciclo de
    aprobación y su propia decisión explícita de Cesar — separada de
    esta, y no incluida en el alcance de nada de lo cerrado hasta hoy.
```

No mezclar ambas decisiones en una sola pregunta a Cesar. No sugerir que
aprobar la Decisión 1 implica nada sobre la Decisión 2.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
PASO_B_COMMITTED = (hash del commit, tras aprobación)
CANARY_TESTS_BACK_TO_PASS = (5/5)
N2_REVERIFIED_FROM_ARTIFACT = (ruta + resultado, no memoria)
AUDIT_GAP_RECONCILED = (event_id confirmado como fork conocido / hallazgo nuevo)
DECISION_1_ANALYSIS_ENGINE = READY_FOR_CESAR
DECISION_2_RELEASE_CAPABILITY = NOT_BUILT — separate future decision
```

DETENERSE tras el Bloque 1 (aprobación de commit) y de nuevo al presentar
el Bloque 3. Ninguna de las dos decisiones se toma sin la palabra
explícita de Cesar, y no se presentan como una sola.
