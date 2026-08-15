# CONTINUACIÓN — CIERRE DE P7, DECISIÓN ARQUITECTÓNICA Y PAQUETE ESTRATÉGICO
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/CONTINUACION_CIERRE_ESTRATEGICO.md
 crea la carpeta docs_plan/CONTINUACION_CIERRE_ESTRATEGICO.md y copia todo este plan en la carpeta
# Ejecutar: cd /home/ing_cpmo && claude

#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Fuente: reporte de ejecución de CONTINUACION_FASE0_P4_FASE1.md
# (commits e271488, fa25c9d, 2a218b1, 5e876e5).
#
# Reglas duras: cero llamadas LLM en toda esta corrida (todo lo que
# queda es verificación textual determinista y documentación de
# decisión); no commit sin diff + aprobación; mantener los marcadores
# FACT / DESIGN / INFERENCE / OPEN_DECISION en toda afirmación nueva.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 0 — CORRECCIÓN: P7 ES INFERENCIA, NO HECHO CONFIRMADO
──────────────────────────────────────────────────────────────────────────────

El reporte trata a P7 como confirmado en el mismo nivel que P2/P4/P5/P6.
No lo está: solo se verificó mecánicamente que su página no tiene tabla
(Bloque 2). Nadie leyó su texto real. Esto reproduce, en dirección
inversa, el riesgo transversal que RISK_REGISTER.md marcó como el más
importante del documento (sobregeneralizar entre casos de causa distinta
sin medir).

0.1 Leer el texto real de la página/chunk de P7 (RW-0012, ya identificado
    en corridas previas — mismo requisito que P6, documento distinto).
    Cero llamadas LLM: es lectura determinista, mismo método que ya se
    usó para P4/P6 en el Bloque 0 de la corrida anterior.

0.2 Clasificar con evidencia textual, no por descarte:
    - ¿El pasaje relevante para 21_CFR_211.68(b) existe en esa página?
    - ¿Usa vocabulario parafraseado (como P2/P5, P4/P6) o eco léxico
      (como P1)?
    - ¿O el problema es otra cosa — página equivocada en el fixture,
      evidencia ausente del documento, límite de chunk?

0.3 Actualizar BOTTLENECK_DIAGNOSIS.md: la fila de P7 pasa a FACT si el
    texto confirma paráfrasis, o se reclasifica con su causa real si no.
    Corregir en el mismo documento y en TARGET_ARCHITECTURE.md cualquier
    frase que diga "confirmado para los 5 casos" — debe decir "4
    confirmados por experimento directo (P2, P4, P5, P6); P7 [FACT tras
    0.1-0.2, o sigue como INFERENCE si el texto no despeja la duda]".

0.4 Si 0.1-0.2 no puede despejar la clasificación de P7 con lectura
    determinista (p. ej. la ambigüedad es genuina), NO forzar una
    conclusión — registrar como OPEN_DECISION en BOTTLENECK_DIAGNOSIS.md,
    exactamente como el propio documento ya hizo con P4 antes de esta
    corrida. Es preferible un pendiente honesto que una inferencia vestida
    de hecho.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — CIERRE FORMAL DE LA DECISIÓN ARQUITECTÓNICA (Table/EvidenceUnit)
──────────────────────────────────────────────────────────────────────────────

TARGET_ARCHITECTURE.md e IMPLEMENTATION_PLAN.md dejaron la Fase 2
(Table/EvidenceUnit) "condicionada al resultado del Experimento C". El
resultado ya existe y es negativo. Cerrar la condición explícitamente,
no dejarla como condicional obsoleto:

1.1 Actualizar IMPLEMENTATION_PLAN.md: Fase 2 pasa de "condicionada" a
    "NO JUSTIFICADA — Experimento C real (2026-08-14/15) refutó la
    hipótesis de dilución tabular para P4/P6 con evidencia perfectamente
    aislada". Cita los checkpoints reales (`chunked-8e2b20bfa511`,
    `chunked-554544f4090f`) como evidencia.

1.2 Actualizar TARGET_ARCHITECTURE.md: el diagrama y el bloque de cierre
    (§25) deben reflejar el resultado real, no la condición pendiente.
    `DOM_JUSTIFIED_ENTITIES` se corrige: Table/EvidenceUnit pasan de
    "condicionadas" a "descartadas para el propósito de recall de juicio
    — reabrir solo si aparece un caso futuro con causa distinta a las ya
    medidas (paráfrasis o dilución tabular), con su propio experimento".

1.3 Esto NO invalida el resto de la Pista A: el fix de furniture (Bloque 1
    de la corrida anterior) fue una mejora real y ya está en producción,
    con beneficio colateral medido en retrieval (4/7→5/7). Documentar
    con precisión: la Pista A demostró tener valor táctico (fixes de
    representación puntuales) pero NO la palanca estratégica que se
    esperaba (arquitectura DOM completa para recall de juicio).

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — ADJUDICACIÓN HUMANA DE LOS 2 HALLAZGOS PENDIENTES (guía, no ejecución)
──────────────────────────────────────────────────────────────────────────────

Los 2 `PROVISIONAL_GAP` de P6 en `review_queue.jsonl` quedan para tu
adjudicación — con un contexto que cambia cómo deben mirarse:

2.1 Preparar para Cesar, por cada entrada: requirement_id, página,
    candidatos de fusión si existen, y una nota explícita: "el Experimento
    C acaba de demostrar que el modelo de juicio no reconoce evidencia
    real presente en esta misma zona del documento (P4/P6, mismo chunk)
    — este PROVISIONAL_GAP tiene probabilidad elevada de ser un miss del
    modelo, no una brecha documental real. Revisar el texto de la página
    directamente antes de confirmar como brecha."
2.2 NO adjudicar por Claude Code. NO sugerir una clasificación de salida
    — solo presentar el contexto que la corrida anterior generó y que
    Cesar necesita para decidir con la información completa.
2.3 Verificar higiene de gobernanza de los commits `2a218b1` (docs) y
    `5e876e5` (review_queue): confirmar que la escritura en
    `review_queue.jsonl` fue registro de estado del sistema (entradas
    `pending` generadas por las corridas reales), no una decisión humana
    fabricada — ningún `decision_origin=human_confirmed` debe aparecer en
    esas 2 entradas hasta que Cesar decida.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — PAQUETE DE DECISIÓN ESTRATÉGICA (el punto de mayor valor de esta corrida)
──────────────────────────────────────────────────────────────────────────────

Con el cuello de botella confirmado por evidencia directa en 4-5 de 7
casos del fixture, la pregunta que ha estado abierta desde el Piloto 1 ya
tiene la evidencia completa para decidirse. Preparar el paquete
(documento, no ejecutar nada) con las tres palancas ya identificadas en
el proyecto, actualizadas con el estado real de hoy:

3.1 PALANCA A — GPU local (Llama 3.1 70B u otro modelo mayor). Costo de
    hardware no estimado en esta corrida (fuera de alcance técnico);
    nota honesta: el recall resultante no es demostrable sin probar, pero
    el fixture 7P+2N queda listo como instrumento de calificación
    inmediato el día que el hardware exista.

3.2 PALANCA B — AnthropicProvider (ya en el diseño de ModelProvider,
    requiere autorización explícita de Cesar). Preparar el resumen de la
    evaluación de confidencialidad pendiente: qué fragmentos de
    documentos Rockwell viajarían por llamada (el mismo tipo de
    fragmento ya usado en el pipeline local — un chunk + Evidence Pack,
    no el corpus completo), y el circuito de gobernanza que exigiría
    (decisión formal, calificación contra el mismo fixture, fingerprint
    propio, presupuesto propio). Sin ejecutar nada — solo informar la
    decisión.

3.3 PALANCA C — Tier-1 de alcance reducido (el producto ya construido y
    probado): confirmación automática de eco léxico (P1, ya demostrado
    en producción); rechazo de falsos positivos (N1/N2, 3 mecanismos
    independientes); recuperación semántica que entrega candidatos
    enriquecidos al revisor (fusión, 7/7 at_5 medido); TODO lo demás
    (paráfrasis) a revisión humana con cobertura declarada. Esta palanca
    no requiere nada nuevo — es el sistema tal como existe hoy, con la
    honestidad de que la detección automática de paráfrasis está fuera
    de su alcance actual, documentado con evidencia definitiva.

3.4 Presentar las tres sin recomendación sesgada — mismo criterio que ya
    rigió cada decisión de rumbo anterior en este proyecto. Incluir
    explícitamente que C no bloquea A ni B: se puede operar con el
    alcance reducido HOY mientras A o B se evalúan en paralelo.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 4 — HIGIENE DE CIERRE
──────────────────────────────────────────────────────────────────────────────

4.1 Confirmar Gate 0 real (no solo "fallo propio ya resuelto" declarado):
    correr desde el host, reportar el conteo exacto pass/fail y confirmar
    que los fallos restantes son los ya caracterizados como ambientales.
4.2 Confirmar presupuesto: PILOT_EXECUTION-2026-010 con 4/25 llamadas
    usadas — reportar el remanente exacto (21) para que quede claro sin
    necesidad de proponer una autorización nueva si se retoma el
    experimento en el futuro.
4.3 Actualizar memoria y skill (gmp-recall-pipeline) con: la conclusión
    definitiva del cuello de botella (con su alcance FACT real, no
    inflado a 5/5 si el Bloque 0 no lo confirma); el patrón de proceso
    valioso de esta corrida (error de ejecución detectado y corregido a
    mitad del experimento, sin ocultarlo); y el cierre formal de la
    hipótesis de dilución tabular como lección para futuras auditorías
    (evidencia perfectamente aislada que no cambia el juicio es ahora un
    patrón confirmado 2 veces — P2/P5 y P4/P6 — con mecanismo desconocido
    del lado del modelo, no un accidente).

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
P7_CLASSIFICATION =            (FACT: paráfrasis / otra causa / OPEN_DECISION,
                               con el extracto de texto que lo sostiene)
BOTTLENECK_CONCLUSION_CORRECTED = (4 confirmados por experimento directo +
                                  P7 según 0.1-0.3 — nunca "5 confirmados"
                                  sin que P7 tenga su propia evidencia)
TABLE_EVIDENCEUNIT_STATUS =    NO_JUSTIFICADA (cerrado formalmente en
                               IMPLEMENTATION_PLAN.md y TARGET_ARCHITECTURE.md)
FURNITURE_FIX_VALUE =          confirmado en producción (retrieval 4/7→5/7)
P6_PENDING_ADJUDICATION =      (paquete de contexto listo para Cesar,
                               con la advertencia de sospecha de gap falso)
REVIEW_QUEUE_HYGIENE =         (confirmado: sin decision_origin fabricado)
STRATEGIC_DECISION_PACKAGE =   (Palancas A/B/C, sin recomendación sesgada)
GATE_0 =                       (conteo real desde el host)
PILOT_EXECUTION_2026_010_REMAINING = 21/25
MEMORY_SKILL_UPDATED =
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE con el paquete de decisión estratégica listo. La elección entre
Palanca A/B/C — o su combinación — es la decisión más importante
pendiente del proyecto en este momento, y ahora se toma con evidencia
directa de 4 casos medidos, no con una hipótesis. Ningún bloque de esta
corrida ejecuta ninguna de las tres palancas; solo las deja listas para
que Cesar decida.
