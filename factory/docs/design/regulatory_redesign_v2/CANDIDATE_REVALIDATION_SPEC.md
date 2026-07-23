# CANDIDATE_REVALIDATION_SPEC

## 1. Independencia de AGT-RVL

AGT-RVL analiza `BASELINE_ORIGINAL` vs. `DOCUMENTO_CANDIDATO_COMPLETO`. No
se limita a fragmentos modificados — revisa el documento completo. Nunca
comparte lógica de decisión con AGT-REM ni consume sus conclusiones
intermedias; solo compara artefactos finales contra baseline. Esta
independencia es la garantía de que un cambio mal aplicado no se
"autoconfirma" por el mismo razonamiento que lo generó.

## 2. Estados por gap

`CLOSED` | `PARTIALLY_CLOSED` | `OPEN` | `NEW_GAP_INTRODUCED` |
`IMPLEMENTATION_VERIFICATION_REQUIRED`

## 3. Comprobaciones obligatorias

- Cada cambio incorporado (existe realmente en el candidato, no solo en el
  registro de cambios).
- Ubicación correcta (coincide con la sección declarada en el change_id).
- Sin truncamiento del documento.
- Responde al requisito — re-ejecuta B/C/D sobre el texto **nuevo**
  (independiente del veredicto original de AGT-VER durante la remediación).
- Referencia regulatoria correcta.
- Coherencia global del documento.
- Sin nuevos gaps introducidos por el cambio.
- Sin eliminación de contenido requerido.
- Sin capacidades inventadas (regla anti-fabricación, ver
  `CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC.md` sección 7).
- Redline, matriz, reseña, reporte y manifest coinciden entre sí.
- El archivo final abre correctamente.
- Todos los hashes son válidos.

## 4. Regla dura de cierre de gap

Un gap **NO** puede clasificarse `CLOSED` por la sola existencia de una
propuesta: el texto debe estar incorporado y validado dentro del
candidato. Cualquier inconsistencia entre lo propuesto y lo efectivamente
incorporado ⇒ la corrida completa **NO es liberable**, no solo el gap
individual.

## 5. Relación con el patrón actual de "nunca autoaprobar"

El precedente real más cercano en código es `app/final_review_agent.py`
(`:21-30` texto de gobernanza fijo, `:37-49` bloqueadores si hay
`version_conflicts_count>0` o hallazgos críticos) — nunca produce
"aprobado", siempre remite a decisión humana. AGT-RVL hereda ese principio
pero opera a nivel de documento completo con re-ejecución real de B/C/D,
no solo agregación de conteos.

## 6. Estado actual y brecha

No existe hoy ningún componente que compare BASELINE_ORIGINAL vs.
candidato de forma independiente y re-ejecute validación semántica sobre
el texto nuevo. Esta es una brecha completa — no hay siquiera un precedente
parcial en el motor `chunked_engine.py` (que valida evidencia dentro de un
documento, no candidato-vs-original). Gated a Fase O del roadmap,
dependiente de que Fases D-N (ModelProvider, Evidence Pack, validación
A/B/C/D, generación de documento) estén cerradas primero.
