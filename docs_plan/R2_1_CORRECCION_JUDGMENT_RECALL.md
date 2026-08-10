# R2.1 — CORRECCIÓN DE LAS TRES CAUSAS DE judgment_recall=0/6 (ORDENADA)

**Fecha de la orden:** 2026-08-10. **Autoridad:** Capa 9 = Cesar. Claude
Code = Capa 8. Corrida de CORRECCIÓN DE EXTRACCIÓN + CONTRATO DE PROMPT +
RE-MEDICIÓN, en orden estricto para no contaminar el diagnóstico del techo
real.

**Reglas duras:** no R3/R4/R5; no corpus formal; no Piloto 2; no
MarkItDown; no cambiar modelo; no borrar artefactos ni decisiones; no
aflojar validadores; no commit sin diff + aprobación de Cesar.

**PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.**

Este archivo preserva la orden de Cesar tal como fue dada, como fuente de
verdad de la corrida R2.1. El estado de ejecución real (qué se hizo, qué
sigue pendiente de firma) se registra en `docs_plan/R2_DESIGN_DETALLADO.md`
y en memoria (`project-w5-v2-regulatory-redesign`), no se reescribe este
archivo salvo para corregir un error de transcripción.

---

## 0. PRINCIPIO RECTOR (leer antes de todo)

R2 falló su hipótesis (candidate pool chico NO subió el recall del juicio)
pero separó tres causas distintas. Antes de concluir NADA sobre el techo
del modelo, hay que limpiar las dos causas que NO son del modelo — porque
mientras existan, contaminan la medición de la que SÍ lo es.

**DISTINCIÓN CRÍTICA (Causa 1)**: el artefacto de kerning del PDF
("wheneve r", "retentio n") NO se corrige aflojando `_is_anchored`.
Aflojar el anclaje para tolerar fuzzy-match es relajar el control que
impide citas inventadas — prohibido por la regla central. La corrección
ataca el RUIDO DE EXTRACCIÓN: normalizar el kerning espurio ANTES del
anclaje, igual que `_strip_bullet_markers` normalizó las viñetas. El
anclaje sigue exigiendo match exacto; solo compara contra texto ya
limpio. Si al final el fix de extracción no basta, la decisión sobre el
validador es de Cesar, nunca implícita.

Primero commitear R2 tal como está (§1), luego corregir en orden
§2→§3→§4.

## 1. CONSOLIDAR R2 ANTES DE TOCAR NADA

1.1 `judgment.py` + `test_r2_judgment.py` están sin commitear (`??`).
    Mostrar diff y, con aprobación de Cesar, commitear como MEDICIÓN
    DIAGNÓSTICA COMPLETA (su valor es el diagnóstico de las 3 causas, no
    un pipeline productivo). El commit preserva evidencia; no implica que
    `judgment.py` quede como está — se corrige en los bloques siguientes.
1.2 Registrar en memoria/roadmap: `retrieval_recall_at_5=4/7` (válido,
    sin cambios); `judgment_recall=0/6` con las 3 causas; P3 excluido por
    diseño (su página no entra al pool — no fabricar el dato).
1.3 Reafirmar: `retrieve_top_k`/`bm25`/`query_builder`/`indexer` NO se
    tocan en esta corrida — las 3 causas están en la fase de juicio y en
    extracción, no en recuperación.

## 2. CAUSA 1 — NORMALIZACIÓN DE KERNING EN EXTRACCIÓN (prioridad; NO aflojar anclaje)

2.1 Localizar dónde se extrae el texto del PDF que alimenta
    `build_page_chunks`/`_is_anchored` (la ruta real que produjo
    "wheneve r" / "retentio n"). Caracterizar el artefacto: ¿es un espacio
    espurio insertado por el extractor entre caracteres de una misma
    palabra por kerning/fuente del PDF? ¿patrón reconocible (letra +
    espacio + letra minúscula sin frontera de palabra real)?
2.2 Diseñar la normalización determinista, en el MISMO punto y con el
    mismo principio que `_strip_bullet_markers` (remoción de ruido de
    formato, nunca de contenido):
    - unir tokens partidos por kerning SOLO con evidencia fuerte de que
      son una sola palabra (p. ej. la reunión forma una palabra del
      léxico/término conocido, o el patrón es inequívocamente
      intra-palabra) — NUNCA fusionar dos palabras legítimamente
      separadas;
    - el riesgo inverso (fusionar "data base" en "database" cuando eran
      dos palabras) debe tener su test negativo, igual que el
      guion-compuesto tuvo el suyo en el fix de viñetas.
2.3 Aplicar la normalización de forma que beneficie a AMBOS lados de la
    comparación de anclaje (el chunk y, si aplica, la cita), para que el
    match exacto opere sobre texto limpio en ambos. `_is_anchored` en sí
    NO cambia su lógica de exactitud — sigue siendo substring exacto tras
    normalizar espacios; solo se le suma la normalización de kerning al
    pipeline de limpieza que ya existe.
2.4 Tests (sin llamadas nuevas, usar los `raw_responses` reales ya
    persistidos):
    - P1 real: la cita de 913 chars que hoy da `_is_anchored=False`, tras
      la normalización da `True` (reproducir el caso exacto del
      diagnóstico);
    - P3 real ("retentio n"): la página deja de perder el token
      "retention" (`term_counts["retention"] > 0` tras normalizar) — esto
      además puede cambiar su rank BM25, RE-MEDIR `retrieval_recall` tras
      el fix;
    - NEGATIVO: ANNEX11_4 sigue rechazado (la normalización de kerning no
      debe hacer pasar el falso positivo); test bloqueante;
    - test negativo de fusión indebida (dos palabras reales separadas no
      se unen).

>>> CHECKPOINT 2: diff extracción + tests + tabla ANTES/DESPUÉS de P1/P3.
>>> Re-medir `retrieval_recall` (puede subir si P3 mejora). Sin commit
>>> hasta aprobación.

## 3. CAUSA 2 — POSITIVO SIN CITA (contrato del prompt)

3.1 Leer el prompt/formato real enviado en el chunk de P2 donde el
    modelo devolvió `cumple_parcialmente` con `evidencia_exacta` vacía
    (raw_response ya persistido). Determinar si el prompt
    permite/invita esa violación de contrato (afirmar estado sin citar).
3.2 Corrección del CONTRATO DEL PROMPT (no del validador — el gate ya
    hizo lo correcto tratando cita vacía como no anclada): reforzar la
    instrucción de que todo estado != `no_cumple`/`evidencia_insuficiente`
    EXIGE una cita literal no vacía; si el modelo no puede citar, debe
    devolver `evidencia_insuficiente`, no un positivo sin cita. Esto es
    cambio de contenido gobernado (prompts YAML) — mostrar el diff y
    requerir aprobación de Cesar; cambia `prompt_version` ⇒ fingerprint
    nuevo.
3.3 Esta corrección se valida en la re-medición §4 (no en aislado — su
    efecto solo se ve con llamada real), así que aquí solo se deja
    preparado el cambio de prompt, no se mide todavía.

## 4. RE-MEDICIÓN AISLANDO EL TECHO REAL (Causa 3)

Solo tras §2 y §3 aprobados y con Causa 1/2 corregidas: re-medir el
`judgment_recall` para saber cuánto del 0/6 era ruido (Causa 1/2) y
cuánto es el modelo de verdad (Causa 3).

4.1 Presupuesto: la re-medición necesita llamadas LLM. Usar la
    PILOT_EXECUTION seleccionada determinísticamente con presupuesto
    (‑004/‑006). Verificar el remanente real (el batch anterior consumió
    50 de 60 de ‑004 — quedan ~10; probablemente NO alcanza para
    re-medir las 6 unidades). Si no alcanza: proponer
    PILOT_EXECUTION-2026-00X con tope calculado y DETENERSE para firma
    de Cesar antes de la primera llamada.
4.2 Re-medir SOLO las unidades cuya causa era corregible: P1 (Causa 1),
    P2 (Causa 2). P4/P5/P6/P7 eran Causa 3 (modelo no reconoce) —
    re-medir al menos una (P6 o P7, evidencia tabular) para confirmar que
    el fix de kerning no las rescató por sorpresa; si el presupuesto es
    escaso, priorizar P1 (el caso más claro de Causa 1) como prueba de
    que la corrección funciona de punta a punta.
4.3 Resultado esperado y su lectura:
    - si P1 (y P2) ahora llegan a `observed`/`SUPPORTING_EVIDENCE_UNDER_REVIEW`:
      confirma que parte del 0/6 (y probablemente del 2/7 histórico) era
      Causa 1/2, no el modelo — el techo real es MÁS ALTO de lo medido;
    - si P4/P6/P7 siguen en `evidencia_insuficiente` tras el fix: confirma
      Causa 3 como límite genuino del modelo sobre evidencia
      tabular/parafraseada — y ahí R2 (BM25 + pool curado) queda cerrado
      como insuficiente, con evidencia limpia.

## 5. DECISIÓN DEL RAQ REENFOQUE (qué corregir antes de seguir)

El resultado de §4 define si el roadmap del Analizador GMP continúa como
está o pivota. Preparar para Cesar (sin ejecutar):

**ESCENARIO A** — el fix de Causa 1/2 rescata varios positivos (recall
real sube notablemente sobre 2/7): el techo del modelo era artificial. El
RAQ reenfoque CONTINÚA; R2 se re-evalúa con el pipeline limpio;
posiblemente el criterio ≥6/7 se acerca sin cambiar modelo. Camino más
optimista.

**ESCENARIO B** — Causa 3 domina (el modelo genuinamente no reconoce
evidencia tabular/parafraseada incluso con pool curado y extracción
limpia): R2 por recuperación léxica queda cerrado como insuficiente. Las
opciones reales (ya documentadas, no reabiertas aquí, para decisión de
Cesar) vuelven a la mesa: embeddings semánticos (diferido en R1.6),
cambio de modelo (H5), o alcance reducido del analizador (verificación
negativa + detección humana asistida, que el modelo SÍ hace bien — N1
siempre correcto).

En AMBOS escenarios queda resuelto el hallazgo transversal más valioso:
la fragilidad de `_is_anchored` ante kerning, que contaminaba TODA
medición previa de recall. Ese solo hallazgo justifica esta corrida.

Anotar además, sin resolver (hallazgos abiertos del reporte R2):
- P1 y "N2" comparten candidate pool (`query_builder` depende solo de
  `req_id`) — no midieron nada independiente; registrar como limitación
  de diseño del arnés de medición, no de producción;
- P1 aparece dos veces en el batch con mismo target — investigar el
  porqué del arnés de `JudgmentUnit` si Cesar lo pide;
- corrección del `req_id` de P3 (`ANNEX11_12`→`ANNEX11_17`) ya aplicada
  en fixture (commit `1633216`) — confirmar que quedó consistente.

## 6. ENTREGA

Mostrar diffs (extracción + prompt + tests + memoria/roadmap/skill), sin
commit salvo el de consolidación §1 (con aprobación). Reportar SOLO:

```
R2_CONSOLIDATION_COMMIT =        (judgment.py medición diagnóstica)
CAUSA1_KERNING_FIX =             (diseño + P1/P3 antes/después)
ANNEX11_4_STILL_REJECTED =       true (test bloqueante)
UNDUE_MERGE_TEST =               (dos palabras reales no se fusionan)
RETRIEVAL_RECALL_AFTER_KERNING = (¿P3 mejora de rank? re-medido)
CAUSA2_PROMPT_FIX =              (contrato reforzado, prompt_version nueva)
BUDGET_FOR_REMEASURE =           (remanente ‑004 / nueva PILOT firmada)
JUDGMENT_REMEASURE =             (P1/P2 tras fix; al menos 1 de Causa 3)
MODEL_CEILING_READING =          (ESCENARIO A / B con evidencia)
RAQ_REENFOQUE_DECISION =         (continúa / pivota — para Cesar)
OPEN_FINDINGS =                  (P1/N2 pool compartido, P1 duplicado, etc.)
D4_2026_004_STATUS =             PROPOSED (sin cambios)
R2_JUDGMENT_HYPOTHESIS =         (confirmada insuficiente / rescatada por fix)
PENDIENTE_DE_APROBACIÓN =        (commits, prompt gobernado, PILOT nueva)
```

DETENERSE en cada punto de firma (prompt gobernado, PILOT_EXECUTION
nueva). El techo real del modelo NO se declara hasta que Causa 1 y Causa
2 estén corregidas y re-medidas — declararlo antes sería repetir el
error que R2 mismo expuso: confundir ruido de pipeline con límite del
modelo.
