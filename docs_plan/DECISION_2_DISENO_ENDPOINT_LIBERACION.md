# DECISIÓN 2 — DISEÑO DEL MECANISMO DE LIBERACIÓN
Diseño puro. Cero código escrito, cero endpoint conectado, cero cambio de
`remediation_packages.py`. Basado en lectura completa de
`create_release_record()`, `record_package_decision()`, el router actual,
y la UI de Mission Control ya existente para este flujo.

──────────────────────────────────────────────────────────────────────────────
HALLAZGO QUE CAMBIA EL ALCANCE DEL DISEÑO
──────────────────────────────────────────────────────────────────────────────

Esto NO es "construir liberación desde cero" — la gobernanza real de
liberación **ya existe y está más madura de lo que la Decisión 1 hacía
suponer**. Para que un paquete llegue a `PACKAGE_READY_FOR_RELEASE`, YA
tiene que haber pasado, con evidencia real, por:

1. `automatic_evaluation_complete` — evaluación automática cerrada.
2. `human_exception_review_complete` — **todo** cambio `HIGH_RISK` con su
   `ExceptionReviewRecord` humano (`.../exceptions/{change_id}`), sin
   excepción.
3. `_artifacts_integrity_ok` — integridad de artefactos verificada.
4. Un `PackageDecisionRecord` humano real (`.../decision`), con:
   - identidad resuelta server-side vía `Depends(require_identity)`
     (`X-Identity-Key`) — **nunca** un string que el cliente mande en el
     body (cerrado en "Paquete 2, hallazgo M", ya está así hoy);
   - `decision in (APPROVE_CLEAN, APPROVE_WITH_EXCEPTIONS)`;
   - `justification` obligatoria y no vacía;
   - cobertura EXACTA de excepciones `HIGH_RISK` si aplica
     (`IncompleteExceptionCoverageError` si falta o sobra una).

`create_release_record()` en sí mismo es casi una formalidad sobre una
decisión que ya está tomada, justificada y firmada — verifica estado
`PACKAGE_READY_FOR_RELEASE`, es append-only, con lock, invariante de "como
mucho un release vigente", auto-supersesión registrada, evento de
auditoría (`document_released`) ya emitido.

**El único gap real de diseño es más pequeño y más preciso de lo que
parecía:** conectar el endpoint, y cerrar la MISMA brecha de identidad que
ya se cerró en `/decision` — hoy `create_release_record()` acepta
`released_by: str` como parámetro de función sin ninguna garantía de que
venga de una identidad real autenticada.

──────────────────────────────────────────────────────────────────────────────
DISEÑO PROPUESTO
──────────────────────────────────────────────────────────────────────────────

**Endpoint nuevo**, mismo router, mismo prefijo, mismo patrón de auth que
`/decision`:

```
POST /api/v1/remediation-packages/{project_id}/{package_id}/{version}/release
    Depends(require_identity) -> identity
    body: {} (vacío -- NADA que el cliente pueda inyectar; released_by
              SIEMPRE viene de `identity`, nunca del body, mismo criterio
              que decided_by desde "Paquete 2, hallazgo M")
    -> create_release_record(..., released_by=identity)
    201 si crea el ReleaseRecord
    404 RemediationPackageNotFound
    400 InvalidTransitionError (no está PACKAGE_READY_FOR_RELEASE)
    409 DuplicateReleaseError (ya existe release para esa version)
```

**Sin decision_family nueva en `decision_store_v2`.** La liberación de un
documento YA tiene su propio mecanismo de gobernanza dedicado
(`PackageDecisionRecord` + `ReleaseRecord`, con lock y append-only propios,
scoped a `(project_id, package_id, version)`) — es una superficie distinta
de las autorizaciones operativas de la fábrica (D1-D5, CORPUS_AUTHORIZATION,
etc.) que sí viven en `decision_store_v2`. Forzarlo a esa familia sería
duplicar gobernanza que ya existe y funciona, mismo criterio que ya se
aplicó para no mezclar `RECORD_ANNOTATION` con autorizaciones reales.

**UI de Mission Control:** `remediation.js` hoy muestra explícitamente el
texto *"Nunca ejecuta ni libera nada -- create_release_record() no está
conectado"* junto al panel de decisión final — ese mensaje deja de ser
cierto en cuanto se conecte el endpoint. Se necesita:
- Actualizar ese texto (deja de ser una garantía de "no hace nada").
- Agregar un botón "Liberar documento" visible SOLO cuando
  `pkg.status === 'PACKAGE_READY_FOR_RELEASE'` — nunca antes.

──────────────────────────────────────────────────────────────────────────────
DOS DECISIONES DE POLÍTICA REGULATORIA — SOLO CESAR PUEDE RESOLVERLAS
──────────────────────────────────────────────────────────────────────────────

**1. ¿Cuatro ojos (dual control) para liberar?** Hoy, la MISMA persona que
firma el `PackageDecisionRecord` (`APPROVE_CLEAN`/`APPROVE_WITH_EXCEPTIONS`)
podría, con este diseño, ser también quien dispare `create_release_record()`
un segundo después — una sola identidad cubre todo el ciclo. Muchos
entornos GMP/21 CFR Part 11 exigen que la persona que aprueba y la persona
que libera sean distintas (segregación de funciones). El código no exige
esto hoy en ningún punto de la cadena. Opciones:
   - (a) Permitir que la misma identidad decida Y libere (más simple, sin
     cambios adicionales de esquema).
   - (b) Exigir `released_by != package_decision.decided_by` en
     `create_release_record()` (un chequeo nuevo y pequeño, fail-closed si
     coinciden) — segregación de funciones real, verificable en código.

**2. ¿Se construye el botón de UI en esta misma pasada, o el endpoint
primero y la UI en una fase separada?** El backend es autocontenido y
testeable sin la UI; la UI es una superficie humana visible que conviene
revisar con más calma (mensaje de confirmación, qué se muestra tras
liberar, etc.).

──────────────────────────────────────────────────────────────────────────────
ENTREGA
──────────────────────────────────────────────────────────────────────────────

```
RELEASE_MECHANISM_ALREADY_BUILT = create_release_record() completo,
    append-only, con lock, invariantes de version unica/release vigente
    unico, evento de auditoria ya emitido -- SOLO falta conectar
GOVERNANCE_PRECONDITIONS_ALREADY_ENFORCED = automatic_evaluation_complete,
    human_exception_review_complete (cobertura exacta HIGH_RISK),
    integridad de artefactos, PackageDecisionRecord humano con identidad
    real + justificacion obligatoria -- TODO esto ya existe, no se disena
    de nuevo
NEW_ENDPOINT = POST /api/v1/remediation-packages/{project_id}/{package_id}/
    {version}/release, Depends(require_identity), body vacio
IDENTITY_GAP_CLOSED_BY_DESIGN = released_by SIEMPRE desde require_identity,
    nunca del body -- mismo patron ya usado en /decision
DECISION_FAMILY_NEW_REQUIRED = NO -- reusa el mecanismo dedicado ya
    existente de PackageDecisionRecord/ReleaseRecord
UI_CHANGE_REQUIRED = SI -- boton condicional a PACKAGE_READY_FOR_RELEASE +
    actualizar el texto que hoy garantiza que nada se libera
OPEN_POLICY_QUESTIONS = (1) cuatro ojos si/no, (2) UI en esta pasada o
    separada -- ambas pendientes de tu respuesta antes de implementar
READY_TO_IMPLEMENT = NO -- bloqueado por las 2 preguntas de politica de
    arriba, no por nada tecnico
```

Detenido para tu decisión sobre los dos puntos de política antes de
diseñar el detalle final ejecutable.
