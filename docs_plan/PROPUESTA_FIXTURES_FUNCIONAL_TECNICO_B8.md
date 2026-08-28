# PROPUESTA — Fixtures Suite B (funcional) y Suite C (técnica) — B8

**Estado:** PROPUESTA de Golden Dataset. **Pendiente de firma de Capa 9 (Cesar).**
Los fixtures se implementan como **borrador**
(`factory/regulatory/validation_v2/fixtures_draft/{functional_suite_b,technical_suite_c}.yaml`,
`status: DRAFT_UNSIGNED`). `fixtures.assert_signed()` es fail-closed — **ningún gate de FASE 10
(B8b) usa estas suites hasta la firma**.
**Fecha:** 2026-08-27. **Autor:** Capa 8.
**Contexto:** `docs_plan/PLAN_VALIDACION_ANALIZADOR_GMP_LOCAL_V2.md` FASE 10 §1 (Suites B y C).

---

## 1. Qué son y por qué necesitan tu firma

La **Suite A** (regulatoria, 7P+2N) ya existe y no se toca — es el instrumento de medición del
recall regulatorio, con 4 vías históricas de comparación.

**No existe** ninguna medición de las clases **funcional** ni **técnica** de findings (FASE 1
lo confirmó: no están implementadas como clase). Los gates `FUNCTIONAL_RECALL ≥ 90%` y
`TECHNICAL_RECALL ≥ 90%` (PLAN_VALIDACION §2) **no son proyecciones — son objetivos de diseño
que se validan contra un Golden Dataset construido a mano y firmado por Capa 9**, mismo régimen
que el fixture 7P+2N o los `evidence_min_criteria`.

**Los `evidence_locator` de cada caso son PROPUESTOS por Capa 8 a partir de una lectura de los
PDFs reales de `GMPAI/source/Rockwell/`; tú los confirmas (o corriges) contra los documentos
antes de firmar.** Cada caso lleva `evidence_locator: "confirmar ..."` por eso.

## 2. Suite B — Functional (20 casos)

| Bloque | # | Finding esperado |
|---|---|---|
| **fully-traced** (URS req → FS claim → SAT step completo) | 5 | ninguno |
| **missing-implementation** (URS req sin `implemented_by` en FS) | 5 | `FunctionalFinding: REQUIREMENT_NOT_IMPLEMENTED` |
| **missing-test** (req implementado, sin `Test` transitivo) | 5 | `TestCoverageFinding: REQUIREMENT_NOT_TESTED` |
| **contradiction** (dos docs afirman comportamiento funcional opuesto sobre el mismo control) | 5 | `FunctionalFinding: CONTRADICTORY_FUNCTIONAL_BEHAVIOR` |

Casos `B01`–`B20` en `functional_suite_b.yaml`. Ejemplos concretos ya anclados a identificadores
reales del corpus: `B01` (UR3.3.1 audit trail de cambio de umbral → FS → SAT-039), `B16`
(F09.00: FS permite acceso del operador a reset de alarma / narrativa de control lo restringe).

## 3. Suite C — Technical (20 casos)

| Distribución | # |
|---|---|
| positivos (hueco técnico presente y evidenciado) | 13 |
| negativos (control técnico descrito adecuadamente, o fuera de alcance) | 7 |

Temas cubiertos: `AUDIT_TRAIL_DESIGN_GAP`, `TIME_SYNC_GAP`, `BACKUP_RECOVERY_GAP`,
`ACCESS_CONTROL_GAP`, `AUTHORITY_CHECK_GAP`, `INTERFACE_INCONSISTENCY`, `REDUNDANCY_GAP`,
`AUDIT_TRAIL_INTEGRITY_GAP`, `ALCOA_ATTRIBUTABLE_GAP`, `PHYSICAL_SECURITY_GAP`,
`TECHNICAL_DESIGN_GAP`. Casos `C01`–`C20` en `technical_suite_c.yaml`.

Los negativos `C14`/`C15` reutilizan a propósito pasajes que el fixture regulatorio ya trató
como positivos (P1/P5 audit trail completo, FactoryTalk roles) — el sistema no debe emitir un
`TechnicalFinding` de hueco donde el control sí está descrito.

## 4. Gates que estas suites habilitan (PLAN_VALIDACION §2)

```
FUNCTIONAL_RECALL          >= 90%     (findings esperados detectados / total esperados)
FUNCTIONAL_FALSE_POSITIVE  <= 5%      (findings emitidos no esperados / total emitidos)
TECHNICAL_RECALL           >= 90%
TECHNICAL_FALSE_POSITIVE   <= 5%
```

Evaluadores deterministas ya implementados: `validation_v2/gates.py`
(`evaluate_functional` / `evaluate_technical`). El chequeo `LOCAL_ONLY` /
`DOCUMENT_EGRESS = 0` también (`validation_v2/local_only.py`).

## 5. Preguntas para tu firma

1. ¿La distribución de la Suite B (5/5/5/5) y de la Suite C (13 pos / 7 neg) es la correcta, o
   quieres reponderar (p. ej. más negativos técnicos)?
2. ¿Confirmas los `evidence_locator` contra los PDFs reales — o prefieres que Capa 8 haga una
   pasada de anclaje exacto (documento·página·pasaje literal) antes de que los revises?
3. ¿Los subtipos esperados por caso son los correctos según tu criterio regulatorio?
4. ¿Firmas ambas suites como Golden Dataset (`status: SIGNED`, versión 1.0), habilitando B8b —
   la corrida real de FASE 10 — cuando además estén firmados los prompts de juicio V2 y exista
   una `PILOT_EXECUTION`?

Hasta tu firma: las suites quedan `DRAFT_UNSIGNED`, los gates funcional/técnico **no se pueden
evaluar como criterio de aceptación**, y B8b no arranca.
