# BLOQUE 1.3 — D: P4, ¿falta de dato o decisión regulatoria pendiente?

Fecha: 2026-08-18 (re-ejecución solicitada explícitamente, tras cierre de P0)
Rol: Arquitecto Principal. Solo lectura, cero código, cero commits, cero LLM.
Origen: `docs_plan/VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md`, sección 1.3.

## Tarea tal como está definida en el plan

> Localizar la fuente real de la matriz de aplicabilidad (dónde vive el
> dato, no solo su consumidor ya identificado en
> `absence_consolidator.py:90-233`). Determinar con evidencia: ¿el par
> (ALCOA_ATTRIBUTABLE, tipo documental de RW-0011) simplemente no tiene
> entrada en esa fuente (dato faltante, arreglo técnico), o la matriz sí
> lo contempla pero de forma ambigua/contradictoria (requiere decisión
> regulatoria de Cesar)? Esto determina si la acción de cierre es "llenar
> un campo" o "presentarle una pregunta a Cesar".

## Evidencia

1. **Fuente real de la matriz**: `factory/regulatory/applicability_matrix.yaml`,
   consumida por `factory/regulatory/applicability.py:60-71`
   (`applicability(requirement_id, document_type)`), no directamente por
   `absence_consolidator.py` — este último solo recibe `applicability_value`
   ya resuelto y decide el `conclusion` final
   (`absence_consolidator.py:113-131`).

2. **Tipo documental de RW-0011**: `DS`
   (`factory/regulatory/corpus_budget_formula.py:92`, `("RW-0011", "DS", 7)`).

3. **Entrada de `ALCOA_ATTRIBUTABLE`** (`applicability_matrix.yaml:154-159`):
   ```yaml
   "ALCOA_ATTRIBUTABLE":  # PROPUESTO
     URS: expected
     FS: expected
     OQ: optional
     evidence_expected_in: [FS]
     default: review_required
   ```
   No hay clave `DS`. `applicability("ALCOA_ATTRIBUTABLE", "DS")`
   (`applicability.py:67`) hace `entry.get("DS", entry.get("default"))` →
   cae a `"review_required"`, con `reason="document_type_not_mapped_for_requirement"`
   (línea 70).

4. **Qué hace `absence_consolidator.py` con `review_required`**: no es
   ninguno de los 3 valores manejados explícitamente (`expected` →
   `DOCUMENTATION_GAP`, `cross_reference_expected` → `CROSS_REFERENCE_MISSING`,
   `optional` → `NOT_OBSERVED_OPTIONAL`) — cae al `else` (línea 128-130):
   `conclusion = "EVALUATION_INCOMPLETE"`, `review_flags += "APPLICABILITY_UNRESOLVED"`.
   Esto es exactamente el estado real de P4.

5. **Estado de aprobación de la matriz — CORRECCIÓN respecto al reporte
   previo de esta sesión** (`VERIFICACION_ACOTADA_20260818/REPORTE.md`,
   sección 1.3, que decía "incluso las entradas SÍ declaradas para otros
   tipos documentales de este mismo requisito no están aprobadas
   todavía" — **eso era impreciso**). Verificado ahora con el archivo
   completo, no solo el fragmento de la fila:
   - `applicability_matrix.yaml:62-67` — bloque `approval` GLOBAL (una
     sola aprobación para todo el archivo, no por fila):
     `status: "human_confirmed"`, `decision_id: "MC-0001"`,
     `approved_by: "Cesar"`, `approved_at_utc: "2026-07-17T16:26:33Z"`.
   - `matrix_approved()` (`applicability.py:34-42`) lee exactamente ese
     bloque global → **hoy devuelve `True`**. La matriz completa (incluida
     la fila de `ALCOA_ATTRIBUTABLE`, que ya existía en la Fase 3
     original, anterior a MC-0001) está aprobada.
   - El comentario `# PROPUESTO` en cada fila (línea 37-47 del yaml) es
     **proveniencia** ("quién/cómo se originó el valor"), no un estado de
     aprobación pendiente — el propio encabezado del archivo lo aclara
     explícitamente y distingue las filas cubiertas por MC-0001 de las
     agregadas después (v2.1 `21_CFR_211.68(b)`, v2.2 los 4
     `document_types` nuevos), que sí están marcadas "pendiente de
     confirmación humana nueva" de forma explícita en el changelog del
     propio yaml (líneas 50-61). `ALCOA_ATTRIBUTABLE` NO es una de esas
     filas post-MC-0001.

## D_ROOT_CAUSE

**No es dato faltante por descuido técnico. Es una decisión regulatoria
nunca tomada para esta celda específica — la matriz global SÍ está
aprobada, pero nadie propuso ni confirmó un valor para
`(ALCOA_ATTRIBUTABLE, DS)`.**

El sistema hace exactamente lo que debe hacer ante esa ausencia:
fail-closed a `review_required` → `EVALUATION_INCOMPLETE` +
`APPLICABILITY_UNRESOLVED`, nunca una omisión silenciosa ni una
afirmación no fundada. No hay ningún "campo por completar" en sentido
técnico — no hay bug que arreglar.

**Acción de cierre = presentarle a Cesar la pregunta exacta**, no
automatizarla:

> ¿`ALCOA_ATTRIBUTABLE` (atribuibilidad de datos, ALCOA+) aplica a
> documentos tipo `DS` (Design Specification, caso RW-0011)? Si aplica,
> ¿con qué valor: `expected`, `optional`, o `out_of_document_scope`?

Si Cesar decide un valor: agregar la fila `DS: <valor>` a
`applicability_matrix.yaml:154-159`, marcarla `# PROPUESTO` de nuevo (regla
explícita del propio archivo, línea 45-47: toda fila agregada/editada
después de MC-0001 pierde la aprobación heredada) y registrar una nueva
confirmación humana (`decision_id` nuevo en `decisions.jsonl`) antes de
que `matrix_approved()` la cubra en producción — mismo patrón ya usado
para `21_CFR_211.68(b)` (v2.1) y los `document_types` de v2.2.

```
D_ROOT_CAUSE =   decisión regulatoria pendiente (no dato faltante,
                 no defecto de código; matriz global SÍ aprobada por
                 MC-0001 -- corrige la imprecisión del reporte previo
                 de hoy sobre "entradas no aprobadas")
CODE_CHANGED =   0
```
