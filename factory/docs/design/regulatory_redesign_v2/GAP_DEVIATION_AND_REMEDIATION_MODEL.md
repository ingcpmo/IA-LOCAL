# GAP_DEVIATION_AND_REMEDIATION_MODEL

## 1. Taxonomía estricta

`HALLAZGO` (observación objetiva anclada) | `GAP` (requisito aplicable sin
evidencia suficiente) | `DESVIACIÓN` (evidencia que contradice el requisito
o el propio documento) | `RECOMENDACIÓN` (mejora no obligatoria) |
`CAMBIO_DOCUMENTAL` (modificación trazable a un gap/desviación).

## 2. Registro por documento × requisito aplicable

Campos: documento; SHA-256; ubicación; requirement_id; regulación;
numeral; cita normativa; URL; evidencia encontrada; cobertura
(procesados/total); hallazgo; gap; desviación; explicación de
insuficiencia; impacto; criticidad (CRITICAL/MAJOR/MINOR); recomendación;
corrección propuesta; limitaciones; evidencia de implementación pendiente;
estado de validación.

Regla dura: nunca declarar "no cumple" sin: requisito aplicable + evidencia
revisada + elemento faltante + razón de insuficiencia + cambio propuesto +
fuente regulatoria + evidencia de implementación pendiente.

## 3. Modelo de conclusiones (reglas deterministas)

`DOCUMENTED_AND_SUPPORTED` | `PARTIALLY_DOCUMENTED` |
`SUPPORTING_EVIDENCE_UNDER_REVIEW` | `DOCUMENTATION_GAP` |
`DEVIATION_IDENTIFIED` | `IMPLEMENTATION_EVIDENCE_MISSING` |
`EVALUATION_INCOMPLETE` | `NOT_APPLICABLE` | `COMPLIANCE_NOT_DETERMINED`

`DOCUMENTATION_GAP` solo cuando **TODAS**: fuente verificada
(`LOCAL_CANONICAL_COPY_VERIFIED`); aplicabilidad aprobada; cobertura
completa; 0 registros rechazados pendientes; 0 revisiones pendientes; 0
contradicciones abiertas; ausencia consolidada determinísticamente. El
baseline actual (25 `review_required` + 3 `rejected_by_verifier` sin
adjudicar, confirmado en la sanitización URS v2.1) es exactamente el caso
que esta regla bloquea: mientras existan esos 28 registros pendientes,
ningún requisito relacionado puede declararse `DOCUMENTATION_GAP`.

Separación permanente (nunca colapsar): `DOCUMENT_CONFORMANCE` |
`IMPLEMENTATION_VERIFICATION` | `REGULATORY_COMPLIANCE` (la última, solo
juicio humano).

## 4. Flujo automatizado con revisión humana por excepción

```
AGT-INV → AGT-APP → AGT-RSG → AGT-REP → AGT-EVD → AGT-VER → AGT-GAP
  → AGT-REM → AGT-QLT → AGT-DOC → AGT-RVL → paquete final → QA-HUM
```

NO se exige aprobación humana por cada gap ni por cada corrección (R-2 del
plan). Estado terminal de cada cambio: `AUTO_APPLIED_TO_DRAFT` |
`PROPOSED_NOT_APPLIED` | `EXCEPTION_REQUIRED` | `REJECTED_BY_VALIDATOR`.

`AUTO_APPLIED_TO_DRAFT` requiere TODAS: fuente verificada; aplicabilidad
aprobada; cobertura completa; A∧B∧C∧D; gates técnicos y lingüísticos;
trazabilidad completa; sin contradicciones; sin capacidades inventadas;
sin afirmaciones de implementación no demostradas.

Cuando falle un gate:
1. Registrar el fallo.
2. Ejecutar UN único ciclo AGT-REM → AGT-QLT.
3. Revalidar.
4. Si continúa fallando: `EXCEPTION_REQUIRED`.
5. Continuar con los demás cambios — un fallo individual recuperable nunca
   bloquea toda la corrida.

## 5. Clasificación de riesgo

- **LOW_RISK**: incorporación automática si todos los gates aprueban.
- **MEDIUM_RISK**: incorporación marcada o agrupación en lote para
  decisión final de QA.
- **HIGH_RISK**: NUNCA autoaplicar; presentar como excepción sin bloquear
  el resto.

Criterios deterministas mínimos de asignación de riesgo:
1. **Criticidad del gap** (`CRITICAL` ⇒ nunca LOW_RISK).
2. **Tipo documental** (cambios en URS/PROTOCOLO que alteran el alcance de
   requisitos ⇒ MEDIUM/HIGH; cambios editoriales en SOP ⇒ candidatos a
   LOW).
3. **Alcance del cambio** — adición vs. eliminación vs. modificación de
   requisito (eliminación de contenido ⇒ nunca LOW_RISK).
4. **Sección afectada** (portada, control de cambios, numeración de
   requisitos ⇒ MEDIUM mínimo).
5. **confidence_band** de la validación C/D (banda baja ⇒ eleva al menos
   un nivel de riesgo).

## 6. Aprobación humana anticipada (únicos 5 casos, ver R-2 del plan)

Fuente nueva/actualizada; nueva versión de Evidence Pack; cambio material
de aplicabilidad; documento sin procedencia; excepción crítica que impida
un candidato coherente.

## 7. Componentes reutilizables y brecha

`app/risk_agent.py:33-49` ya calcula `risk_score = severidad * confianza` y
agrega por severidad/estado (`:52-61`) — base directa para la mecánica de
AGT-GAP. Brecha: no existen hoy los criterios deterministas de asignación
LOW/MEDIUM/HIGH_RISK de la sección 5 de este documento (el `risk_score`
actual es continuo, no está mapeado a las 3 bandas de gobernanza que exige
la autoaplicación gobernada); tampoco existe AGT-REM (generación de
correcciones) como código — confirmado en auditoría, brecha completa.
