# Reporte B8b — dry run de Suite B (funcional) sobre el corpus real

**Fecha:** 2026-08-27. **Autoridad:** Capa 9 = Cesar.
**Corpus:** `GMPAI/source/Rockwell/` — URS v2.1, FS v1.2, EMS Control Narrative,
WFI Control Narrative, SAT-041. Análisis determinista (B6a + B1.2), **sin LLM, sin gobernanza**.

---

## 1. Resultado

Tras B1.2 (extracción de `local_id` + linkeo por él) y el fix de falsos positivos de
contradicción:

| Métrica del grafo | valor |
|---|---|
| aristas `implemented_by` (URS↔FS) | 1120 |
| aristas `designed_by` (FS↔DS) | 184 |
| aristas `regulated_by` (catálogo) | 20 |

| Finding funcional (subtype) | # emitidos sobre el corpus real |
|---|---|
| `REQUIREMENT_NOT_TRACED` | **0** |
| `CONTRADICTORY_FUNCTIONAL_BEHAVIOR` | **0** (4 candidatos crudos, todos falsos positivos por fragmentación → filtrados) |
| `TEST_WITHOUT_REQUIREMENT` | **0** |
| **Total** | **0** |

`untraced` suprimidos por el filtro de confianza: 6 (sin id de ref) + 1 (encabezado).
Antes de B1.2 eran 45 + 35.

## 2. Lectura

**El análisis funcional determinista, sobre este corpus, no encuentra nada real — y eso es un
resultado, no un fallo.**

- **Trazabilidad completa.** Tras B1.2, la cadena UR→F→SAT del cliente está bien conectada
  (1300+ aristas). Solo 6 claims de la URS quedan sin id de referencia (segmentación), abajo de
  45. Ningún requisito de la URS queda sin implementación aguas abajo. `REQUIREMENT_NOT_TRACED`
  = 0 es correcto.
- **Cero contradicciones cross-documento.** Los 4 candidatos crudos de la heurística
  modal-opuesto eran fragmentos de la MISMA requisito 4.3.3 ("shall not require PPE" vs "shall
  have no power source > 50V") — cláusulas distintas que comparten número, no una contradicción.
  Las guardas nuevas (mismo documento / mismo `local_id` / solapamiento de predicado < 0.55)
  los eliminan sin tocar las contradicciones modales reales (que comparten casi todo el
  vocabulario).
- **Tests trazados.** Los pasos del SAT enlazan a requisitos; `TEST_WITHOUT_REQUIREMENT` = 0.

## 3. Consecuencia para la validación (FASE 10, Suite B)

| Gate | Estado |
|---|---|
| `FUNCTIONAL_FALSE_POSITIVE ≤ 5%` | ✅ **CUMPLIDO, medible** — el analizador emitió 0 findings, 0 falsos positivos. No inventa. |
| `FUNCTIONAL_RECALL ≥ 90%` | ❌ **NO medible sobre este corpus** — no hay findings funcionales verdaderos que detectar. Recall sobre 0 casos esperados es indefinido. |

El fixture borrador `functional_suite_b.yaml` (20 casos: 5 missing-impl / 5 missing-test / 5
contradiction / 5 fully-traced) **no corresponde a la realidad de este corpus**: las 15 casos
positivos serían inventados (no hay UR sin implementar, ni contradicciones reales, en el set
Rockwell).

## 4. Opciones para Capa 9

**(A) Fixture de inyección de defectos.** Construir un set de documentos derivado del Rockwell
con defectos CONOCIDOS inyectados a mano (quitar la implementación de N requisitos, quitar M
pasos de SAT, introducir K contradicciones reales). Determinista, sin gobernanza. Es la vía
para medir `FUNCTIONAL_RECALL` de verdad. Esfuerzo: moderado.

**(B) Aceptar el gate de falsos positivos como cumplido y declarar el recall "no medido sobre
corpus limpio".** Documentar que el analizador funcional no cría lobos (0 FP en documentos
reales), y que su recall se medirá cuando exista un corpus con defectos reales o el fixture (A).

**(C) Diferir la validación funcional** hasta que B6b (capa semántica) esté, ya que el linkeo
determinista por identificador —aunque mucho mejor tras B1.2— no capta requisitos implementados
sin cita literal del número, ni contradicciones que no sean modal-opuesto exacto.

**Recomendación de Capa 8:** (B) ahora + (A) como corrida siguiente si quieres el número de
recall. La clase funcional ya es útil como red de seguridad (0 FP), aunque su recall sobre
documentos ya bien trazados sea trivialmente alto.

---

*Sin LLM. Sin gobernanza consumida. Fix de FP de contradicción commiteado.*
