# R1.6 + R1.7 — Reporte final

**Fecha:** 2026-08-09. **Estado:** implementado, no-regresión confirmada, commiteado.
**Instrucciones origen:** `docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md` (R1.6) + `.claude/plans/sharded-riding-turing.md` (R1.7, aprobado por Cesar antes de ejecutar).

## Resumen ejecutivo

R1.5 (commit `484d103`) productizó `evaluation_profile=H2H4` y confirmó,
con una llamada real, que el modelo SÍ ancla evidencia genuina (P5, score
1.0) — pero el checkpoint final igual la reportaba como
`not_observed_in_chunk`. R1.6 encontró la causa: un pre-filtro propio de
`chunked_engine.py` (`_is_topically_relevant()`) rechazaba la cita por un
bug de idioma en labels bilingües. R1.7, autorizado por Cesar tras el
reporte de R1.6, rediseñó ese pre-filtro para el pipeline de producción,
reutilizando maquinaria ya probada del sistema en vez de relajar nada.
**Resultado verificado con datos reales, cero llamadas nuevas al
modelo**: la evidencia real de P5 deja de perderse — llega a
`chunks_observed=1` con una conclusión honesta
(`SUPPORTING_EVIDENCE_UNDER_REVIEW`, nunca una aprobación silenciosa). El
negativo real (ANNEX11_4) sigue rechazado, ahora por el mecanismo
correcto.

## R1.6 — Defecto de idioma en `_is_topically_relevant()`

### Hallazgo

`chunked_engine._is_topically_relevant()` (línea ~595) es un pre-filtro
**propio** del motor, distinto y más crudo que la validación C real y ya
probada del sistema (`semantic_evidence_verification.
verify_semantic_relevance()` + `detect_reference_list_context()`,
language-agnostic vía `requirement_terms.yaml`, que además nunca rechaza
duro por relevancia léxica — solo marca `NOT_VERIFIABLE`/`review_required`).

Compara palabras significativas del `label` del checkpoint contra la
cita. Varios labels (familia ALCOA, `alcoa_prompts.yaml`) siguen el
patrón bilingüe `"Término inglés — glosa en español"` (ej.
`"Contemporaneous — registrado en el momento"`). El código original
hacía `label.split("—", 1)[-1]`, quedándose **solo** con la glosa en
español — descartando el término inglés que ya estaba en el propio label
gobernado, justo cuando más hacía falta contra un documento fuente en
inglés (100% del corpus Rockwell actual, 14/14 archivos).

**Alcance verificado**: 9 de 20 checkpoints reales (familia ALCOA) usan
el patrón bilingüe afectado; los 11 restantes son puramente español, sin
ningún ancla inglesa que rescatar.

### Corrección aplicada

Usar ambas mitades del label bilingüe. Cero fuentes de comparación
nuevas: se evaluó explícitamente agregar `requirement_terms.yaml` como
fuente alternativa de match y se **descartó** — rompía
`test_topically_irrelevant_citation_is_rejected` (cita real, monolingüe,
ancla literal pero de otro tema: "login" del catálogo de control de
acceso matchea por accidente una cita real de audit trail).

### Límite honesto encontrado

La corrección de idioma, por sí sola, **no** era suficiente para que P5
llegara a `observed`: su evidencia real no repite ninguna palabra
gobernada, ni en inglés ni en español. La causa de fondo es más profunda
que un mismatch de idioma — exigir coincidencia léxica LITERAL es
estructuralmente demasiado estricto para validar un `cumple_parcialmente`
que el modelo infiere de forma parafraseada. Esto se reportó a Cesar
explícitamente, sin forzar un resultado que no era real, y motivó la
autorización de R1.7.

## R1.7 — Rediseño del pre-filtro para el pipeline de producción

### Diseño

El sistema ya tenía la maquinaria correcta para esto, sin usarla en este
punto:

- `evidence_verifier.verify_llm_output()` ya calcula una validación de
  relevancia (V5, `relevance_score` contra `requirement_terms.yaml`,
  language-agnostic) que degrada a `review_required` en vez de rechazar
  duro.
- `absence_consolidator.py` ya sabe tratar `review_required` de forma
  segura: nunca lo promueve a una conclusión positiva confirmada
  (`DOCUMENTED_AND_SUPPORTED`); lo enruta a
  `SUPPORTING_EVIDENCE_UNDER_REVIEW` o `EVALUATION_INCOMPLETE`+flag.

Esa maquinaria nunca llegaba a ejecutarse de verdad porque el pre-filtro
de R1.6 ya blanqueaba la evidencia antes.

**Cambio aplicado** (`factory/engines/gmpai_integrity/chunked_engine.py`,
~65 líneas, 1 función): se dividió `valid_candidate` en dos caminos.

- **Pipeline legacy** (`result["findings"]`, sin consumidor de
  producción activo detectado): sigue usando `_is_topically_relevant`
  exactamente igual — no tiene forma de manejar una señal suave, así
  que seguir rechazando duro ahí es lo correcto.
- **Pipeline verificado** (el que usa `corpus_runner`/producción): deja
  de usar `_is_topically_relevant`. El único rechazo duro adicional al
  anclaje literal pasa a ser `semantic_evidence_verification.
  detect_reference_list_context()` — el único componente
  **determinista y ya probado** (golden dataset) de la validación C
  real. La relevancia léxica deja de bloquear antes de tiempo: fluye tal
  cual a `verify_llm_output` (sin tocar ningún umbral) y de ahí a
  `absence_consolidator`.

Ningún umbral se tocó (`RELEVANCE_THRESHOLD=0.15` intacto). Ninguna
validación A/B/D se tocó. `evidence_min_criteria` sin tocar.

### Verificación — sin gastar ninguna llamada nueva al modelo

Se reconstruyó la entrada exacta que el modelo ya devolvió para P5
(`raw_response` real, persistido en
`factory/regulatory/pilot_run/r1_5_h2h4_chunked-596f70cc4520/`) y se pasó
por `evaluate_chunked()` ya corregido, vía Ollama mockeado devolviendo
exactamente esa respuesta real — mismo patrón que ya usan los tests
existentes del motor. Cero llamadas nuevas, cero gasto de presupuesto
`PILOT_EXECUTION`.

| Caso | Antes (R1.5) | Después (R1.7) |
|---|---|---|
| **P5** (evidencia real, ancla score 1.0) | `chunks_observed=0`, `not_observed_in_chunk` | `chunks_observed=1`, `conclusion="SUPPORTING_EVIDENCE_UNDER_REVIEW"`, flag `OBSERVED_ONLY_UNVERIFIED` |
| **ANNEX11_4** (GAMP5 en lista de referencias, negativo real) | `chunks_observed=0` | `chunks_observed=0` (mismo resultado, ahora por el mecanismo estructural correcto, no por accidente de idioma) |
| **Caso construido de control** (cita real, ancla, otro tema, mismo idioma) | rechazado duro (legacy) | pipeline verificado: `SUPPORTING_EVIDENCE_UNDER_REVIEW` (misma señal débil que P5, nunca `verified` en silencio) |

**Nota honesta**: `SUPPORTING_EVIDENCE_UNDER_REVIEW` es un resultado más
honesto que un "observed" pleno, no una aprobación automática — P5 sigue
necesitando confirmación humana. Esto es deliberado, no una limitación:
`CLAUDE.md` prohíbe declaración de cumplimiento final por parte del
sistema. El objetivo de R1.7 nunca fue que P5 se aprobara solo — era que
dejara de perderse silenciosamente, y eso se logró y se verificó con
datos reales.

### Tests y regresión

- `factory/tests/test_r1_6_topically_relevant_language.py` (7 tests
  nuevos): bug de idioma bilingüe, caso real de P5 (limitación
  documentada), caso real de ANNEX11_4, caso wrong-topic same-idioma
  (no regresión), casos label/doc por combinación de idioma.
- `factory/tests/test_r1_7_soft_relevance_verified_pipeline.py` (3 tests
  nuevos): P5 real vía replay offline, ANNEX11_4 real por el pipeline
  verificado, caso de control wrong-topic por el pipeline verificado.
- Suite completa `factory/tests/`: **2271 passed**, 6 failed (mismo
  patrón ya conocido y no atribuible: 3 Playwright ambientales + 1 cola
  de revisión no vacía + 2 `test_runtime_identity` que reflejaban el
  diff real y esperado de `chunked_engine.py` mientras estuvo sin
  commitear — se resuelven solos al commitear). Golden dataset: 8/8.
  Ningún fallo nuevo atribuible al cambio.

## Hallazgo abierto, no resuelto en esta corrida

`SUPPORTING_EVIDENCE_UNDER_REVIEW` llega hasta
`result["verified_conclusions"]` pero hoy **no existe** una cola o
reporte que la despache activamente a un humano para confirmación —
queda como campo consultable, no como notificación. Confirmado durante
la investigación de R1.7 (agente Explore dedicado). No es parte del
alcance autorizado de esta corrida; queda anotado en memoria como
posible siguiente paso.

## Archivos de esta corrida

| Archivo | Contenido |
|---|---|
| `factory/engines/gmpai_integrity/chunked_engine.py` | Fix de R1.6 (label bilingüe) + rediseño de R1.7 (split legacy/verificado) |
| `factory/tests/test_r1_6_topically_relevant_language.py` | 7 tests, R1.6 |
| `factory/tests/test_r1_7_soft_relevance_verified_pipeline.py` | 3 tests, R1.7 |
| `docs_plan/R1_6_VALIDADOR_RELEVANCIA_IDIOMA.md` | Instrucciones originales de R1.6 |
| `.claude/plans/sharded-riding-turing.md` | Plan de R1.7, aprobado por Cesar antes de ejecutar |
| `docs_plan/ROADMAP_ANALIZADOR_GMP.md` | Secciones R1.5 (CLOSED), R1.6, R1.7 actualizadas |
| `.claude/skills/gmp-recall-pipeline/SKILL.md` | Advertencia de idioma + patrón `SUPPORTING_EVIDENCE_UNDER_REVIEW` documentados |
| `docs_plan/R1_6_R1_7_REPORTE_FINAL.md` | Este archivo |

## Pendiente de decisión de Cesar

1. ¿Se considera R1.6+R1.7 cerrados (P5 llega a `observed`/
   `SUPPORTING_EVIDENCE_UNDER_REVIEW`, negativos intactos, verificado con
   datos reales)? ¿Eso habilita R2?
2. ¿Autorizar una cola/reporte dedicado que despache
   `SUPPORTING_EVIDENCE_UNDER_REVIEW` a revisión humana activa (hallazgo
   abierto de arriba), como corrida separada?
3. D4-2026-004 (recálculo del ritmo H2H4) sigue pendiente, sin cambios.
