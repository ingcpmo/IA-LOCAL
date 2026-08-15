# CONTINUACIÓN POST-AUDITORÍA — FASE 0 + CIERRE DE P4 + FASE 1 MECÁNICA
# Archivo de instrucciones para Claude Code
# Destino: docs_plan/CONTINUACION_FASE0_P4_FASE1.md
crea esta carpeta y copia todo el texto docs_plan/CONTINUACION_FASE0_P4_FASE1.md
# Ejecutar: cd /home/ing_cpmo && claude
#
# AUTORIDAD: Capa 9 = Cesar. Claude Code = Capa 8.
# Fuente: docs_plan/AUDITORIA_ARQUITECTONICA_2026-08/ (12 documentos ya
# entregados y aceptados). Esta corrida EJECUTA lo que
# IMPLEMENTATION_PLAN.md propuso como Fase 0 + Fase 1 mecánica, más un
# diagnóstico gratis de P4 que la auditoría dejó pendiente sin costo.
#
# Reglas duras: mostrar diff y esperar aprobación ANTES de tocar
# chunked_engine.py (está en DO_NOT_TOUCH.md — requiere aprobación
# separada explícita, no la aprobación general de la auditoría); NO
# reimplementar _PAGE_FURNITURE_RE (superficie única, reutilizar la de
# evidence_verifier.py); NO modificar evidence_verifier.py como objeto de
# verificación; cero llamadas LLM salvo lo explícitamente autorizado en
# el bloque 3; N1/N2 deben seguir rechazándose en cada cambio; no commit
# sin diff + aprobación.
#
# PRODUCTION_ENABLEMENT = BLOCKED. CORPUS_READY = false.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 0 — CIERRE GRATIS DE P4 (cero LLM, antes de tocar código)
──────────────────────────────────────────────────────────────────────────────

RISK_REGISTER.md R8 declara P4 "sin investigar". Cerrarlo con el mismo
método barato ya usado para P6/P7 en BOTTLENECK_DIAGNOSIS.md:

0.1 Localizar el chunk/página real que produjo `not_observed` para P4
    (ALCOA_ATTRIBUTABLE, RW-0011) — mismo checkpoint o reporte narrativo
    ya referenciado para P6 (comparten página según
    DOCUMENT_NORMALIZATION_ARCHITECTURE.md, verificar).
0.2 Leer el texto real de esa página/chunk. Medir: ¿es paráfrasis (como
    P2/P5, mismo tipo de fallo ya confirmado como límite del modelo) o
    dilución tabular (como P6/P7, hipótesis sin confirmar)? Cuantificar
    ratio de señal/ruido si aplica, igual método que P6.
0.3 Actualizar BOTTLENECK_DIAGNOSIS.md con la fila de P4 completa (ya no
    "sin investigar") y cerrar R8 en RISK_REGISTER.md con la evidencia.
0.4 Si P4 resulta ser el mismo patrón que P6/P7 (dilución tabular),
    añadirlo como tercer caso al alcance de Fase 3 del EXPERIMENT_PLAN.md
    (mismo experimento, un caso más, sin cambiar su costo en llamadas si
    P4 puede medirse en el mismo lote que P6/P7).

──────────────────────────────────────────────────────────────────────────────
BLOQUE 1 — FASE 0: FIX DE FURNITURE SIMÉTRICO (toca DO_NOT_TOUCH)
──────────────────────────────────────────────────────────────────────────────

## 1.1 Condición dura de superficie única (verificar ANTES de escribir código)

El fix debe REUTILIZAR `_PAGE_FURNITURE_RE` (y la función que la aplica)
desde `evidence_verifier.py`, nunca reimplementarla en
`chunked_engine.py`. Verificar primero si `_PAGE_FURNITURE_RE` es privada
(prefijo `_`) — si lo es, decidir el mecanismo de reuso correcto:
(a) exportarla como utilidad compartida en un módulo común (mismo patrón
que ya existe para otras normalizaciones: `_join_kerning_split_words`,
`_strip_bullet_markers` — verificar dónde viven exactamente y si ya hay
un módulo de normalización compartido, o si esta corrida debe crear uno);
(b) importar la función directamente si el diseño del módulo lo permite
sin acoplar `chunked_engine` a lógica de verificación indebidamente.
Elegir la opción que NO cree un acoplamiento inverso extraño (chunking
importando de verificación) — si (a) y (b) son ambas incómodas,
DETENERSE y proponer a Cesar dónde debe vivir la normalización compartida
como su propia decisión de ubicación, en vez de decidirlo unilateralmente.

## 1.2 Mostrar el diff propuesto para chunked_engine.py

ANTES de aplicar: presentar el diff completo (dónde se llama la
normalización de furniture, en qué punto exacto del flujo de construcción
del prompt) y esperar aprobación EXPLÍCITA de Cesar — esta es la
aprobación separada que DO_NOT_TOUCH.md exige para este archivo,
distinta de la aprobación general que ya recibió la auditoría.

## 1.3 Tests (test-first, según TEST_PLAN.md)

- Test que hoy FALLA contra el código actual (demuestra la asimetría:
  mismo texto de entrada produce furniture presente en la ruta LLM y
  ausente en la ruta de verificación) y PASA tras el fix.
- Test de que `evidence_verifier.match_citation()` no cambia su firma ni
  comportamiento — sigue comparando contra `chunk['text']`, sin importar
  el fix.
- Regresión del fixture 7P+2N completo: mismo resultado o mejor, nunca
  peor sin explicación. N1/N2 siguen rechazados — bloqueante.
- Regresión del golden dataset de 8 negativos
  (`semantic_verification_golden_dataset.py`), cero llamadas LLM.

## 1.4 Commit

Solo tras aprobación del diff + tests verdes + Gate 0 PASS. Un commit,
causa raíz única (fix de furniture simétrico). Mensaje cita
INFORMATION_LOSS_ANALYSIS.md como origen del hallazgo.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 2 — FASE 1 DEL EXPERIMENTO: VERIFICACIÓN MECÁNICA (cero LLM)
──────────────────────────────────────────────────────────────────────────────

Según EXPERIMENT_PLAN.md, Fase 1: confirmar con `pdfplumber.extract_tables()`
si la tabla de P6/P7 (y P4 si el Bloque 0 lo sumó) se separa limpiamente
de la prosa relevante — puramente mecánico, sin LLM.

2.1 Ejecutar `extract_tables()` sobre las páginas reales de P6/P7 (y P4 si
    aplica). Verificar que la oración de prosa relevante (~110 caracteres,
    ya citada en BOTTLENECK_DIAGNOSIS.md) queda COMPLETAMENTE fuera de
    cualquier `Table.rows` extraída.
2.2 Resultado binario que decide si Fase 3 (2 llamadas LLM) tiene sentido:
    - SI la tabla se separa limpiamente: Fase 3 del experimento queda
      justificada — preparar la propuesta de PILOT_EXECUTION (verificar
      primero si ya existe una vigente seleccionable por el resolver;
      nunca proponer una nueva sin esa verificación) y DETENERSE para
      firma de Cesar antes de la primera llamada.
    - SI NO se separa limpiamente (la prosa queda parcialmente dentro de
      celdas o mezclada): Fase 3 NO se justifica con este mecanismo tal
      como está diseñado — reportar a Cesar como hallazgo, no proceder,
      y dejar la pregunta de P6/P7 abierta con esta nueva evidencia.
2.3 PRESERVAR EL CHECKPOINT esta vez (R9 del RISK_REGISTER.md): si Fase 3
    llega a ejecutarse, el checkpoint completo de esa corrida se guarda en
    `factory/regulatory/pilot_run/checkpoints/` sin excepción — cerrar la
    brecha de reproducibilidad que R9 documentó.

──────────────────────────────────────────────────────────────────────────────
BLOQUE 3 — FASE 3 (PARALELA, INDEPENDIENTE): CONTRATO FORMAL
──────────────────────────────────────────────────────────────────────────────

Puede ejecutarse en paralelo a los Bloques 1-2 (sin dependencia mutua,
según IMPLEMENTATION_PLAN.md). Cero llamadas LLM.

3.1 Formalizar `common_contract_sha256` de los 3 YAML gobernados como JSON
    Schema explícito versionado (CONTEXT_ENGINEERING_ARCHITECTURE.md
    Componente 1).
3.2 Test de contrato en Gate 0: `evidence_verifier.py` y
    `chunked_engine.py` deben construir/consumer estructuras conformes al
    mismo schema; falla deliberadamente ante un drift sintético (mismo
    patrón que `test_deploy_freshness_all_source_routes_are_live`).
3.3 Test de que cambiar el schema sin bump de `prompt_version` falla el
    gate — mecaniza la disciplina de gobernanza, no la reemplaza.
3.4 Cambiar contenido de los YAML gobernados sigue exigiendo
    `prompt_version` nuevo y aprobación explícita de Cesar — el contrato
    formal NO relaja esto, lo verifica mecánicamente.
3.5 Mostrar diff, esperar aprobación, commit separado del Bloque 1.

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
P4_DIAGNOSED =                 (paráfrasis / dilución tabular / otro, con evidencia)
R8_CLOSED =                    (RISK_REGISTER.md actualizado)
SINGLE_SURFACE_REUSE =         (mecanismo elegido para _PAGE_FURNITURE_RE)
FASE0_DIFF_APPROVED =          (pendiente de Cesar)
FASE0_TESTS =                  (asimetría demostrada→corregida; N1/N2 OK)
FASE0_GOLDEN_DATASET =         (8/8 sin regresión)
FASE0_COMMIT =                 (hash, tras aprobación)
FASE1_MECHANICAL_RESULT =      (tabla se separa limpiamente: sí/no, por caso)
FASE3_JUSTIFIED =              (sí/no según 2.2)
CHECKPOINT_PRESERVATION =      (comprometido para la próxima corrida real)
CONTRATO_FORMAL_STATUS =       (diseñado/implementado, tests, commit — Bloque 3)
GATE_0 =
CODE_CHANGED =                 (chunked_engine.py + posible módulo de
                               normalización compartido; nada más)
DEPENDENCIES_ADDED = 0
LLM_CALLS_THIS_RUN = 0 (bloques 0-2 y 3 completos) / hasta 2 si Fase 3
                       del experimento se autoriza y ejecuta aparte
PRODUCTION_ENABLEMENT = BLOCKED
```

DETENERSE en: la aprobación del diff de Fase 0 (Bloque 1.2, obligatoria
por DO_NOT_TOUCH.md), la decisión sobre dónde vive la normalización
compartida si 1.1 no resuelve limpio, y la firma de PILOT_EXECUTION si la
Fase 1 mecánica justifica la Fase 3 del experimento. Ningún bloque
posterior arranca sin que el anterior esté aprobado y con Gate 0 en
verde.
