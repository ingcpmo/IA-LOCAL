# R2.1 §5 — DECISIÓN DE RUMBO: TRIAGE DE EVIDENCIA ANTES DE MÁS INFERENCIA

**Fecha de la orden:** 2026-08-10. **Autoridad:** Capa 9 = Cesar. Claude
Code = Capa 8. Corrida de ANÁLISIS SIN LLM + PREPARACIÓN DE DECISIÓN. Cero
llamadas de inferencia (`PILOT_EXECUTION-2026-004` agotada 60/60; ninguna
nueva se propone hasta que el rumbo esté decidido).

**Reglas duras:** no R3/R4/R5; no corpus formal; no Piloto 2; no
MarkItDown; no cambiar modelo; no aflojar validadores; no proponer
`PILOT_EXECUTION` nueva en esta corrida; no commit sin diff + aprobación.

**PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.**

Este archivo preserva la orden de Cesar tal como fue dada. El estado de
ejecución real se registra en `docs_plan/R2_1_DECISION_PACKAGE.md` y en
memoria, no se reescribe este archivo salvo para corregir un error de
transcripción.

---

## 0. POR QUÉ ESTA CORRIDA NO GASTA INFERENCIA

El veredicto A/B descansa hoy sobre 2 unidades re-medidas de 6 (P1 Causa
1, P6 Causa 3) — una por escenario. Eso NO es un empate: es una muestra
insuficiente para decidir el rumbo del roadmap. Antes de firmar más
presupuesto de inferencia para re-medir P2/P4/P5/P7, hay que responder
una pregunta más barata y más determinante, sin gastar una sola llamada:

  ¿De qué TIPO es la evidencia en el corpus real, y qué fracción cae en
  el tipo que el modelo YA demostró que NO reconoce (Causa 3,
  tabular/densa)?

Si la mayoría de la evidencia GMP real es tabular/densa, el escenario B
domina aunque más re-mediciones salieran bien en los casos fáciles. Si es
mayoritariamente prosa estructurada (como P1), el escenario A es viable
sin cambiar modelo. Ese triage decide si gastar presupuesto tiene
sentido y en qué unidades.

## 1. CONSOLIDAR EL ESTADO REAL (lectura, sin LLM)

1.1 Commits: `dddfbb2` (§1), `d42d919` (§2+§3), `f5a8034` (§4) presentes
    en HEAD; árbol limpio salvo lo esperado. Reportar `git status` real.
1.2 Estado de causas: Causa 1 CORREGIDA+CONFIRMADA (P1 `observed`); Causa
    2 CORREGIDA, efecto sin confirmar (P2 no re-medido); Causa 3
    RECONFIRMADA como límite real (P6). `retrieval_recall_at_10=7/7`,
    `at_5=4/7`.
1.3 EL BLOQUEADOR ESTRUCTURAL que emergió y no debe perderse: P1 ancló
    `observed` pero cerró `EVALUATION_INCOMPLETE` porque la validación D
    (`evidence_min_criteria`) NUNCA recibió interpretación humana desde
    la Fase C de W5 V2. Verificar en el catálogo real cuántos
    `requirement_id` del fixture (y del corpus analizable) tienen
    `evidence_min_criteria` interpretados vs. pendientes. Esto es
    CRÍTICO: aunque el recall fuera perfecto, el pipeline no consolida
    conclusión sin este trabajo humano. Puede ser el verdadero cuello de
    botella, por encima del recall.

## 2. TRIAGE DE TIPO DE EVIDENCIA (cero LLM, el análisis central)

Para cada uno de los 7 positivos del fixture, clasificar el pasaje real
(ya verificado a mano, ya conocido) por TIPO DE EVIDENCIA, con evidencia
del texto extraído:

- `PROSE_STRUCTURED`: requisito en prosa/lista tipo "UR3.3.1 ... shall
  ..." (como P1) — el modelo demostró que SÍ lo reconoce cuando ancla
  limpio.
- `TABULAR_DENSE`: evidencia embebida en tablas de I/O, señales, tags
  (como P6/P7) — el modelo demostró que NO lo reconoce (Causa 3).
- `MIXED/OTHER`: caracterizar.

Producir la tabla: fixture → tipo de evidencia → ¿el modelo lo reconoció
en las re-mediciones reales disponibles? → confianza de la
clasificación.

Extender el triage (sin LLM, muestreo) al corpus analizable completo: de
los documentos Rockwell en scope, ¿qué proporción de la evidencia
esperada por requisito es tabular vs. prosa? No exhaustivo — una muestra
representativa que permita estimar el peso de Causa 3 en el objetivo
real del analizador. Declarar el método de muestreo y su incertidumbre.

Salida: `EVIDENCE_TYPE_DISTRIBUTION` — qué fracción del trabajo real cae
en el tipo que el modelo ya falló. Este número, no dos re-mediciones, es
lo que debe pesar la decisión A/B.

## 3. COMPLETAR LO CORREGIBLE SIN INFERENCIA

3.1 Causa 2: el fix de prompt está aplicado pero su efecto sobre P2 no
    se confirmó por presupuesto. NO se puede confirmar sin LLM —
    dejarlo explícitamente como "corregido, pendiente de confirmación
    en la próxima ventana de inferencia", no como cerrado. No maquillar.
3.2 Hallazgos abiertos del reporte R2 que SÍ se pueden resolver sin LLM:
    - P1 y "N2" comparten candidate pool (`query_builder` depende solo
      de `req_id`): confirmar el defecto de diseño del ARNÉS de
      medición y proponer la corrección (el fixture N2 debe medir algo
      independiente de P1) — es corrección de instrumento, no de
      producción;
    - P1 duplicado en el batch (dos `JudgmentUnit` con mismo target):
      investigar el porqué en el arnés, documentar;
    - consistencia del fixture tras la corrección de P3
      (`ANNEX11_12`→`ANNEX11_17`, commit `1633216`): verificar que
      quedó coherente.
3.3 Estos arreglos de instrumento hacen que la PRÓXIMA re-medición
    (cuando se autorice) mida limpio — vale la pena hacerlos ahora,
    gratis, antes de gastar presupuesto sobre un arnés con defectos
    conocidos.

## 4. PLAN DE RE-MEDICIÓN CORRECTAMENTE DIMENSIONADO (diseño, no ejecución)

Diseñar (sin ejecutar) la re-medición que SÍ produciría un veredicto,
para que Cesar decida si la autoriza:
- unidades faltantes: P2 (confirmar Causa 2), P4, P5, P7 (completar la
  muestra de los 6 positivos + validar Causa 3 en más de un caso);
- k por unidad y por qué (recordar: P3 necesita k que lo incluya o
  queda fuera por construcción — decidir si entra);
- costo total en llamadas y el tope de la `PILOT_EXECUTION` nueva que
  requeriría (‑004 agotada);
- criterio de decisión explícito: con la muestra completa (6-7 de 7),
  qué resultado significa A (recall recuperable sin cambiar modelo) y
  qué significa B (Causa 3 domina). Fijarlo ANTES de medir, no después.

## 5. PAQUETE DE DECISIÓN PARA CESAR

Entregable: `R2_1_DECISION_PACKAGE.md`. Presentar SIN recomendación
sesgada, con los datos para que Cesar decida el rumbo del RAQ reenfoque:

**OPCIÓN A — CONTINUAR con el modelo actual**: viable SI el triage
muestra que la evidencia GMP real es mayoritariamente prosa estructurada
(Causa 1 corregida rescata ese tipo). Requiere: completar validación D
humana (Fase C pendiente — el bloqueador estructural del §1.3),
re-medición dimensionada del §4, y aceptar que la evidencia tabular
quedará como "sin evidencia localizada → revisión humana" (que es
honesto, no un fallo).

**OPCIÓN B — PIVOTAR**: si el triage muestra que la evidencia
tabular/densa es una fracción grande del corpus real, el modelo actual
no alcanza el objetivo del analizador. Las palancas ya documentadas
vuelven a la mesa: embeddings semánticos (diferido R1.6), cambio de
modelo (H5, requiere GPU o proveedor externo con su evaluación de
confidencialidad), o REDEFINIR el alcance del analizador hacia lo que el
modelo SÍ hace bien (rechazo de falsos positivos — N1 siempre correcto —
+ detección de evidencia en prosa + enrutamiento del resto a revisión
humana). Esta última no es una derrota: es un producto honesto y
entregable HOY.

**OPCIÓN C — DESACOPLAR**: notar que el bloqueador de validación D
(Fase C humana) es independiente del recall. Quizás el siguiente
trabajo de mayor valor NO es recall sino completar la interpretación
humana de `evidence_min_criteria` — sin la cual ninguna conclusión
consolida, tenga el recall que tenga. Presentar esto como posible
reordenamiento del roadmap.

## 6. ENTREGA

Mostrar diffs (arreglos de instrumento §3 + memoria/roadmap + paquete de
decisión), sin commit hasta aprobación. Reportar SOLO:

```
COMMITS_CONFIRMED =            (dddfbb2, d42d919, f5a8034 en HEAD)
CAUSA1 = CORREGIDA_CONFIRMADA (P1 observed)
CAUSA2 = CORREGIDA_SIN_CONFIRMAR (P2 pendiente de LLM)
CAUSA3 = LIMITE_REAL_RECONFIRMADO (P6)
VALIDATION_D_STATUS =          (cuántos req tienen evidence_min_criteria
                               interpretados vs. Fase C pendiente)
STRUCTURAL_BLOCKER =           (EVALUATION_INCOMPLETE por D humana pendiente)
EVIDENCE_TYPE_DISTRIBUTION =   (prosa vs. tabular en el corpus real, muestreado)
INSTRUMENT_FIXES =             (P1/N2 pool, P1 duplicado, fixture coherente)
REMEASURE_PLAN =               (unidades, k, costo, criterio A/B pre-fijado)
DECISION_PACKAGE =             (A / B / C con datos, sin sesgo)
SAMPLE_SUFFICIENCY_NOTE =      (2/6 re-medidas ≠ veredicto)
D4_2026_004_STATUS =           PROPOSED (sin cambios)
NEXT_HUMAN_DECISION =          (rumbo A/B/C; y si autoriza PILOT nueva)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE con el paquete de decisión listo. NO proponer
`PILOT_EXECUTION` nueva hasta que Cesar decida el rumbo — gastar
inferencia antes de saber el tipo de evidencia dominante sería medir
sin hipótesis. La decisión A/B/C es de Cesar; esta corrida le da los
datos que hoy faltan para tomarla bien.
