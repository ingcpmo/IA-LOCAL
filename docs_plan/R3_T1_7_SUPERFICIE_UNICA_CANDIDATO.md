# R3-T1.7 — SUPERFICIE ÚNICA DE VALIDEZ DE CANDIDATO (cierra B3/B4/B5 de raíz)
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/R3_T1_7_SUPERFICIE_UNICA_CANDIDATO.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
#
# CAMBIO DE MÉTODO (instrucción central de esta corrida): B3, B4 y B5 NO
# son tres defectos — son EL MISMO defecto en tres call-sites distintos,
# descubiertos de uno en uno. Parchear un cuarto sitio repetiría el ciclo.
# Esta corrida NO parchea: audita todos los sitios de una vez y los
# centraliza en UNA superficie compartida, igual que ya se hizo con
# `path_policy.py` (sin superficies de path paralelas) y
# `decision_scope_resolver` (ningún consumidor implementa su propia
# lectura). La validez/anclaje de candidato es la tercera superficie que
# se fragmentó; se cierra con el mismo patrón.
#
# SEGUNDO CAMBIO DE MÉTODO: el criterio de aceptación se mide SOLO en la
# salida final (bucket del informe Tier-1). "Llega a la función" o "llega
# al Finding" NO cuentan como cerrado — ya nos equivocamos tres veces así.
#
# Reglas duras: CERO llamadas LLM; no MarkItDown; no cambiar modelo; NO
# aflojar validadores; no commit sin diff + aprobación.
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
0. CONSERVAR LO YA GANADO
──────────────────────────────────────────────────────────────────────────────

0.1 El fix B4 es correcto y está validado (guardianes en verde, rescate por
    criterios anclados llega al Finding). Presentar su diff pendiente y
    commitearlo con aprobación de Cesar — NO se descarta ni se rehace; se
    absorberá dentro de la superficie única del §2 sin perder su lógica ni
    sus tests.
0.2 Higiene del árbol sucio (§0.2 de R3-T1.6, si sigue pendiente): que los
    4 guardianes de Gate 0 vuelvan a verde y vuelvan a significar algo.

──────────────────────────────────────────────────────────────────────────────
1. AUDITORÍA EXHAUSTIVA — TODOS LOS SITIOS, DE UNA VEZ (cero llamadas)
──────────────────────────────────────────────────────────────────────────────

Objetivo: que al terminar este bloque NO pueda existir un B6 desconocido.

1.1 Enumerar EXHAUSTIVAMENTE cada punto del código que decide alguna de
    estas preguntas, con archivo:línea:
    - ¿este candidato/chunk cuenta como evidencia válida?
    - ¿esta cita ancla?
    - ¿este candidato "gana" para el requisito?
    - ¿qué estructura de datos recibe el resultado (Finding,
      verified_records_by_req, checkpoints, informe, cola de revisión)?
    Método: grep sistemático de `_is_anchored`, `verify_anchor`,
    `valid_candidate`, `valid_candidate_verified`, `evidencia_exacta`,
    `build_finding_record`, `chunks_observed`, y seguimiento de cada
    estructura hasta su consumidor final. No confiar en un solo grep:
    trazar el flujo de datos completo desde el raw_response hasta el
    bucket del informe.
1.2 Producir el MAPA DE RUTAS: para cada ruta (Finding / verified_records /
    cualquier otra que aparezca), qué lógica de validez aplica hoy, y en
    qué difiere de las demás. Las divergencias encontradas son el
    inventario completo del defecto — B3, B4 y B5 deben aparecer en este
    mapa como casos particulares.
1.3 Confirmar cuántas rutas independientes existen. Si son más de las 2-3
    conocidas, reportarlo: ese número es el que explica por qué el defecto
    reaparecía.

──────────────────────────────────────────────────────────────────────────────
2. CENTRALIZACIÓN EN UNA SUPERFICIE ÚNICA
──────────────────────────────────────────────────────────────────────────────

2.1 Diseñar UNA función/módulo compartido — p. ej.
    `candidate_validity.resolve_candidate_evidence(...)` — que decida, en
    un solo lugar y con una sola lógica:
    - si el candidato ancla (headline directo, o rescate por citas de
      criterio ya ancladas — la regla de B4, sin cambios);
    - qué cita representa la evidencia (con `headline_source` marcado
      cuando es derivada);
    - qué señal entrega a cada consumidor.
    TODAS las rutas del mapa §1.2 la llaman. Ninguna reimplementa nada.
2.2 REGLAS INVARIANTES (idénticas a las ya aprobadas, sin aflojar nada):
    - cita no anclada NUNCA rescata un candidato (guardián central
      anti-fabricación);
    - headline vacío + cero citas ancladas ⇒ sin evidencia (ausencia
      honesta preservada);
    - umbral de anclaje, validaciones A/B/C/D y regla de contradicción
      genuina: intactos;
    - el rescate deriva de citas YA validadas; nunca sintetiza texto.
2.3 TEST DE NO-BYPASS (el que impide un B6): un test que falle si algún
    módulo decide validez de candidato sin pasar por la superficie única
    — mismo espíritu que `test_refresh_readonly.py` para Reader/Executor.
    Integrarlo a Gate 0.
2.4 `apply_conclusion_preconditions()` solo degrada, nunca promueve (hoy
    correcto). Verificar que con la superficie única la conclusión positiva
    se origina donde corresponde y no necesita "promoción" posterior — si
    el diseño exigiera promover desde GAP, DETENERSE y reportar: eso sería
    un cambio de semántica que requiere decisión de Cesar, no un fix.

──────────────────────────────────────────────────────────────────────────────
3. VALIDACIÓN — MEDIDA SOLO EN LA SALIDA FINAL
──────────────────────────────────────────────────────────────────────────────

3.1 Re-correr `replay_f2_dry.py` (cero llamadas, checkpoint histórico,
    cola aislada, SHA-256 verificados) con la superficie única aplicada.
3.2 CRITERIO ÚNICO DE ÉXITO (nada intermedio cuenta):
    en el INFORME TIER-1 GENERADO, `21_CFR_11.10(e)` aparece en el bucket
    de revisión humana con estado SUPPORTING_EVIDENCE_UNDER_REVIEW (RAMA B
    ya aceptada por Cesar) y con su evidencia anclada visible — NO
    `PROVISIONAL_GAP`. Si sigue en PROVISIONAL_GAP, el trabajo no está
    hecho, sin importar qué muestren las capas internas.
3.3 GUARDIANES en la MISMA salida final:
    - `21_CFR_11.10(d)` sigue bloqueado por contradicción genuina;
    - ANNEX11_4 sigue rechazado end-to-end;
    - un requisito sin evidencia real sigue reportando ausencia honesta;
    - ninguna cita no anclada aparece como evidencia en el informe.
3.4 Tabla ANTES/DESPUÉS por requisito, a nivel de bucket del informe.
3.5 Suite completa desde el host + Gate 0; los 6 criterios a–f de F2-DRY
    re-evaluados. Si alguno sigue parcial: DETENERSE y reportar la causa
    exacta con el mapa §1.2 en la mano — pero ahora la causa debería estar
    YA en el mapa, no ser un descubrimiento nuevo.

──────────────────────────────────────────────────────────────────────────────
4. CIERRE (solo si §3 pasa)
──────────────────────────────────────────────────────────────────────────────

4.1 Ciclo humano en la UI (bloque 4 de R3-T1.6): ahora sí tiene sentido —
    la entrada que Cesar revisará estará en el bucket correcto. Elegir la
    vía de acceso (cola dry-run visible en modo lectura, o UNA entrada
    promovida marcada `DRY_RUN_VALIDATION`), verificar la vista de
    evidencia y la validación de identidad, y DETENERSE para su decisión.
4.2 Cierre de R3-T1 (bloque 5 de R3-T1.6): declarar demostrado /
    no-demostrado, la cadena completa de defectos, y los pendientes con
    dueño (B1 con ID `ARTIFACT_VERSION-2026-019`, prompt fantasma, tests
    ambientales).
4.3 F2-LIVE: decidir si se justifica bajo el criterio ya fijado (solo si
    cambia una decisión de producto); si no, recomendar no correrlo.

──────────────────────────────────────────────────────────────────────────────
5. LECCIÓN A MEMORIA Y SKILL (para que no se repita)
──────────────────────────────────────────────────────────────────────────────

Registrar como principio permanente del proyecto:
- "Cuando un defecto reaparece en un segundo lugar, NO se parchea el
  segundo lugar: se audita exhaustivamente y se centraliza en una
  superficie única con test de no-bypass" — igual que path_policy y
  decision_scope_resolver. La lógica de validez/anclaje de candidato es
  ahora la tercera superficie unificada.
- "El criterio de aceptación se mide en la salida final del producto, no
  en capas intermedias" — declarar cerrado en una capa intermedia produjo
  tres falsos cierres consecutivos en esta fase.
- El patrón de replay sobre datos ya pagados como paso obligatorio antes
  de pedir presupuesto (ya demostrado cuatro veces en este arco).

──────────────────────────────────────────────────────────────────────────────
6. ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
B4_COMMITTED =                (diff aprobado; lógica absorbida en §2)
DIRTY_TREE / GATE0 =          (guardianes en verde / explicado)
ROUTE_MAP =                   (nº de rutas independientes + archivo:línea c/u)
DIVERGENCES_FOUND =           (B3/B4/B5 + cualquier otra nueva)
SINGLE_SURFACE =              (módulo/función; rutas que la consumen)
NO_BYPASS_TEST =              (en Gate 0)
UNANCHORED_NEVER_RESCUES =    true
FINAL_OUTPUT_11_10_e =        (bucket real en el informe: SUPPORTING_… / GAP)
FINAL_OUTPUT_11_10_d =        (bloqueado por contradicción genuina)
ANNEX11_4_END_TO_END =        rechazado
F2_DRY_CRITERIA =             a..f (todos PASA / cuál sigue parcial y por qué)
HUMAN_CYCLE =                 (vía + pendiente de decisión de Cesar)
R3_T1_CLOSURE =               (demostrado / no demostrado)
F2_LIVE_JUSTIFIED =           (sí/no + razonamiento)
LESSON_RECORDED =             (memoria + skill)
CORPUS_READY = false
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: el commit de B4, el diff de la superficie única con sus
guardianes, y la decisión de Cesar en la UI. Si la auditoría §1 revela más
rutas de las esperadas, eso NO es un fracaso — es exactamente lo que esta
corrida existe para encontrar de una vez, en vez de descubrirlas de a una
por sesión.
