# REPORTE — Verificación acotada (Bloque 1 completo, 1.1–1.4)

Fecha: 2026-08-18 (segunda corrida de la sesión, confirma y extiende la
corrida previa de las 18:17 que se detuvo en 1.1)
Rol: Arquitecto Principal (solo lectura, sin código, sin commits, cero LLM)
Origen: `docs_plan/VERIFICACION_ACOTADA_Y_PAQUETES_CIERRE.md`

**Resultado: se reconfirma I_BYPASS_FOUND = YES de forma independiente.**
Por la regla del propio documento origen ("Si 1.1 encuentra bypass real:
I pasa a P0, se detiene todo lo demás, se reporta a Cesar de inmediato
sin esperar el resto del documento"), el Bloque 2 (reclasificación) y el
Bloque 3 (paquetes de implementación) **NO se ejecutan** — quedan
bloqueados pendientes de la decisión de Cesar sobre el P0.

1.2/1.3/1.4 sí se investigaron (solo lectura, sin riesgo, información útil
para cuando Cesar decida cómo tratar el P0) y se documentan abajo con el
mismo nivel de evidencia.

---

## 1.1 — I: ¿existe bypass de RemediationDirective?

### I_BYPASS_FOUND = YES (reconfirmado)

Mismo hallazgo que la corrida anterior de hoy
(`docs_plan/VERIFICACION_ACOTADA_20260818/REPORTE.md`, versión previa):
`POST /api/v1/remediation-packages/{project_id}/{package_id}/{version}`
(`factory/api/routes/remediation_packages.py:50-90`) acepta
`CreatePackageBody.changes: list[dict]` **directamente del body HTTP**,
sin exigir ningún vínculo a una `RemediationDirective`.

Verificación adicional de esta corrida — confirma que el bypass no es
solo teórico sino que **no hay ningún llamador de producción** que até
los dos flujos:

```
grep de importadores reales de map_finding_to_remediation_change:
  factory/services/gap_assessment_finding_mapper.py   (definición propia)
  factory/services/remediation_directive_dispatch.py:169  (camino gobernado)

grep de llamadores de dispatch_directive_to_remediation():
  NINGUNO en factory/ fuera de su propia definición
  (solo aparece en factory/tests/test_remediation_directive_dispatch.py
  y factory/tests/test_r4_t1_1v2_cold_chain_validation.py)

grep de llamadores de svc.create_package():
  factory/api/routes/remediation_packages.py:83  (ÚNICO llamador real)
```

Es decir: `dispatch_directive_to_remediation()` — el adaptador que
traduce una `RemediationDirective` SUBMITTED de autoría humana a un
`RemediationChange` — **existe pero está desconectado**. Nada en
producción llama a `svc.create_package()` con `changes` derivados de él.
El único llamador real de `create_package()` es el endpoint HTTP, que
acepta `changes` arbitrarios del body. El "camino correcto" documentado
(`remediation_directive.py` → `remediation_directive_dispatch.py` →
`gap_assessment_finding_mapper.py` → `create_package()`) es una
convención documentada en comentarios, no una invariante de código.

`RemediationChange` (`factory/services/remediation_package_schemas.py:161-166`,
`_CHANGE_REQUIRED_FIELDS`) no tiene ningún campo `directive_id` — no hay
forma, ni siquiera opcional, de declarar de qué directiva viene un
cambio, ni de validarlo.

**Sin cambios respecto al hallazgo P0 ya reportado. Pendiente de decisión
de Cesar antes de continuar con Bloque 2/3.**

---

## 1.2 — J: Trazabilidad end-to-end hasta la generación final

### J_TRACEABILITY_CONFIRMED = NO (con matices)

- `remediation_package_schemas.py` (`_CHANGE_REQUIRED_FIELDS`, líneas
  161-166) NO tiene `directive_id` ni `finding_rc_id` como campos de
  `RemediationChange`. Solo existe `finding_id` (str libre).
- `remediation_traceability_and_manifest.py` — grep de
  `finding_id|directive_id|finding_rc_id` sobre el archivo completo:
  **cero resultados**. La matriz de trazabilidad y el manifest final
  (Fase M) construyen su trazabilidad con `change_id`, `requirement_id`
  y `citation_ids` (líneas 93-129, 147-151) — nunca con `finding_id` ni
  `directive_id`.
- En el único camino donde `directive_id` "viaja" —
  `remediation_directive_dispatch.py:113,123` — lo hace de forma
  implícita: `finding["finding_id"] = directive["directive_id"]` y
  `finding["cambio_documental_propuesto"] = directive["directive_id"]`,
  que luego `gap_assessment_finding_mapper.py:530` usa como
  `change["change_id"]`. O sea: `directive_id` sobrevive solo porque
  reutiliza el campo `change_id`/`finding_id` como contenedor, sin un
  campo propio ni una relación declarada — y esto solo ocurre si se pasa
  por `dispatch_directive_to_remediation()`, que (1.1) no tiene llamador
  de producción hoy.

**Conclusión:** la cadena `finding_rc_id → directive_id → change_id` es
reconstruible manualmente en el camino gobernado, pero no es un campo de
trazabilidad explícito ni aparece en el manifest final como tal. Si el
bypass de 1.1 se cierra exigiendo `directive_id`, este mismo hallazgo
(J) exige agregar el campo explícitamente al schema y al manifest —
no basta con "ya viaja disfrazado de `change_id`".

---

## 1.3 — D: P4 — ¿falta de dato o decisión regulatoria pendiente?

### D_ROOT_CAUSE = decisión regulatoria pendiente (no dato faltante)

Fuente real de la matriz: `factory/regulatory/applicability_matrix.yaml`
(consumida vía `factory/regulatory/applicability.py`, no directamente por
`absence_consolidator.py`, que solo recibe `applicability_value` ya
resuelto).

- `RW-0011` es tipo documental `DS`
  (`factory/regulatory/corpus_budget_formula.py:92`).
- La entrada `ALCOA_ATTRIBUTABLE` (`applicability_matrix.yaml:154-159`)
  declara explícitamente `URS: expected`, `FS: expected`, `OQ: optional`
  y `default: review_required` — **`DS` no tiene entrada propia**, así
  que cae al `default`.
- Esto NO es un bug ni un campo vacío por omisión accidental:
  `applicability.py:20-31` (`load_matrix()`) **exige** que todo
  requisito declare `default: review_required` y lo valida al cargar
  (`ValueError` si falta) — es el diseño fail-closed documentado ("P1:
  lo no contemplado va a revisión, nunca a omisión silenciosa").
  `applicability()` (líneas 60-65) confirma el mismo patrón para
  requisitos no listados en absoluto.
- Además, la entrada completa está marcada `# PROPUESTO` en el YAML
  (línea 154) y la matriz tiene un mecanismo de aprobación separado
  (`matrix_approved()`, `applicability.py:34-42`, exige
  `approval.status == "human_confirmed"`) — es decir, incluso las
  entradas SÍ declaradas para otros tipos documentales de este mismo
  requisito no están aprobadas todavía.

**Interpretación:** el sistema ya hace exactamente lo que debe hacer
ante la ausencia de una entrada (`review_required`, conservador,
fail-closed) — no hay ningún "campo por completar" en sentido técnico.
La pregunta real y pendiente es de juicio regulatorio: ¿debe
`ALCOA_ATTRIBUTABLE` aplicar a documentos `DS` (Design Specification) —
como `expected`, `optional`, o `out_of_document_scope` — en vez de
quedarse en el default conservador? Esa es una pregunta para Cesar, no
un fix de una línea. Cierre del paquete 3 = "presentarle a Cesar la
pregunta exacta", como ya preveía el documento origen para este caso.

---

## 1.4 — H: Consumidores de decisions_v2.jsonl

### H_CONSUMERS_VERIFIED = lista completa, ninguno actúa sobre agent_proposed sin human_confirmed

Grep de todos los módulos no-test que leen `decisions_v2.jsonl`
(`factory/layer9/decisions/decisions_v2.jsonl` vía
`decision_store_v2.STORE_FILE`):

1. **`factory/services/decision_store_v2.py`** (el propio almacén —
   lector/escritor canónico). `project_status()` (líneas 322-363) es el
   consumidor con más consecuencia: proyecta el estado vigente
   (`ACTIVE`/`SUPERSEDED`) de cada decisión. Verificado línea por línea:
   - Línea 335: una supersesión (`CORRECTION`/`SUPERSESSION`) solo
     surte efecto si `r["decision_origin"] == "human_confirmed"` — un
     registro `agent_proposed` con `supersedes_instance_id` se ignora
     explícitamente (comentario líneas 336-345: "DEFECTO REAL cerrado
     en G2" — antes un agente podía revocar una decisión de Cesar solo
     proponiéndolo; corregido).
   - Línea 356-357: el barrido completo de familia por `SUPERSESSION`
     también exige `human_confirmed`.

2. **`factory/services/artifact_version_signing.py`** — expone
   propuestas (`list_artifact_version_proposals()`, líneas 79-122) con
   estado derivado explícito: `PROPOSED` (docstring línea 16) mientras
   solo exista el registro `agent_proposed`; pasa a `SIGNED` únicamente
   cuando existe un registro `human_confirmed` que lo confirma (línea
   17); pasa a `APPLIED` (líneas 74-76) solo si `approved_by_decision`
   de un `version_record` coincide con el `confirm_id` humano. Ningún
   camino en este archivo aplica un `agent_proposed` sin la confirmación.

3. **`factory/regulatory/corpus_runner.py`** — grep confirma uso
   read-only: comentario explícito en línea 840, *"LECTURA en el log del
   run, nunca una decisión nueva en decisions_v2"*. No escribe ni actúa
   sobre registros sin confirmar; solo consulta decisiones ya vigentes
   (`human_confirmed`/`ACTIVE`) para resolver qué lote de documentos
   aplica.

4. **`factory/scripts/ops/migrate_decisions_to_v2.py`** — script de
   migración one-shot (legacy → v2), no es un consumidor productivo en
   el sentido de la pregunta (no actúa condicionalmente sobre el
   `decision_origin`, solo traslada registros). Se cita por completitud
   del grep, sin riesgo asociado.

**Conclusión: sin hallazgos en H.** Los dos consumidores con
consecuencias productivas reales (`decision_store_v2.project_status`,
`artifact_version_signing`) tienen la guardia `human_confirmed`
verificada en código, con comentarios que documentan un defecto similar
ya cerrado (G2) — buena señal de que el patrón ya fue auditado antes.

---

## Resultado consolidado

```
I_BYPASS_FOUND =              YES (reconfirmado, ver 1.1)
J_TRACEABILITY_CONFIRMED =    NO — directive_id no es campo explícito de
                               RemediationChange ni del manifest; solo
                               sobrevive disfrazado de change_id en el
                               camino gobernado (que además está
                               desconectado en producción, ver 1.1)
D_ROOT_CAUSE =                decisión regulatoria pendiente (matriz
                               fail-closed funciona como debe; falta que
                               Cesar decida si ALCOA_ATTRIBUTABLE aplica
                               a documentos DS, y aprobar la matriz)
H_CONSUMERS_VERIFIED =        decision_store_v2.project_status (líneas
                               322-363), artifact_version_signing.py
                               (líneas 74-122), corpus_runner.py (read-only,
                               línea 840) — ninguno actúa sobre
                               agent_proposed sin human_confirmed

P0_COUNT =                    1 (I — bypass de RemediationDirective)
P1_COUNT =                    NO RECLASIFICADO — Bloque 2 bloqueado por P0
PACKAGES_READY =              0 — Bloque 3 bloqueado por P0
CODE_CHANGED =                0
PRODUCTION_ENABLEMENT =       BLOCKED
```

## Pendiente de decisión de Cesar (sin lo cual no se continúa)

1. Cómo cerrar el bypass P0 (I) — opciones ya enumeradas en la corrida
   previa de hoy (exigir `directive_id` en el endpoint / restringir el
   endpoint al camino gobernado / recalcular gates server-side).
2. Si se cierra I exigiendo `directive_id`: aceptar que J (1.2) requiere
   agregar ese campo explícitamente al schema/manifest, no solo
   reutilizar `change_id`.
3. La pregunta regulatoria de D (1.3): ¿`ALCOA_ATTRIBUTABLE` aplica a
   documentos `DS`, y con qué valor (`expected`/`optional`/
   `out_of_document_scope`)? Y, por separado, aprobar formalmente
   `applicability_matrix.yaml` (hoy `# PROPUESTO`, sin
   `approval.status = human_confirmed`).

Ninguna implementación de código se realiza sin aprobación explícita de
Cesar, uno a la vez, empezando por el punto 1 (P0).
