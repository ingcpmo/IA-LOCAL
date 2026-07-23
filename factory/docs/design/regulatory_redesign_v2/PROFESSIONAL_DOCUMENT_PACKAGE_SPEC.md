# PROFESSIONAL_DOCUMENT_PACKAGE_SPEC

## 1. Artefactos obligatorios por documento (generados simultáneamente por AGT-DOC)

1. `DOCUMENTO_CANDIDATO_COMPLETO`
2. `DOCUMENTO_REDLINE`
3. `REPORTE_DE_HALLAZGOS_GAPS_Y_DESVIACIONES`
4. `MATRIZ_DE_TRAZABILIDAD`
5. `RESEÑA_DE_CAMBIOS_Y_FUNDAMENTO_REGULATORIO`
6. `PAQUETE_DE_EXCEPCIONES`
7. `MANIFEST` (todos los artefactos + SHA-256 + run_id + fingerprint)
8. `REPORTE_DE_REVALIDACIÓN`
9. `REPORTE_DE_CALIDAD_FINAL`

Estos 9, más el paquete final para decisión humana de QA (10º elemento,
ver `QA_FINAL_PACKAGE_AND_DECISION_SPEC.md`), forman el conjunto completo
exigido por el objetivo de la sección 1 del plan de instrucciones.

## 2. Matriz de trazabilidad

`requirement_id → evidencia → hallazgo → gap/desviación → change_id →
sección → revalidación`

Cada fila debe ser reconstruible hacia atrás: dado un `change_id`, debe
poder identificarse sin ambigüedad qué requisito lo originó y qué
resultado de revalidación lo cerró (o no).

## 3. Reseña de cambios

Por cambio: `change_id`; sección; contenido anterior; contenido nuevo;
hallazgo; gap/desviación; motivo; regulación; numeral; cita; URL;
evidencia; resultado de revalidación; implementación pendiente.

Narrativa obligatoria por cambio: qué estaba incompleto → por qué era
insuficiente → qué se modificó → cómo atiende el requisito → fuente
oficial → qué queda pendiente.

Ubicación de la reseña: puede ir al final del candidato o como anexo
controlado, según formato y política documental. Regla de decisión
propuesta: si el formato es DOCX/PDF con estructura de control de cambios
nativa (como los documentos SOP/protocolo de Rockwell), la reseña va como
anexo controlado numerado; si el formato es XLSX, va como hoja adicional
`Change_Log` al final del libro, nunca mezclada con hojas de datos
operativos.

## 4. Manifest

Incluye SHA-256 de cada uno de los 9 artefactos, `run_id`, fingerprint
completo de la corrida (ver
`PERFORMANCE_AND_INFERENCE_ORCHESTRATION_SPEC.md`), y referencia cruzada a
la matriz de trazabilidad. El manifest es el artefacto que
`CORRECTED_DOCUMENT_GENERATION_GATE` valida para confirmar que "todos los
artefactos" existen y son consistentes entre sí.

## 5. Paquete de excepciones

Contiene todo cambio `PROPOSED_NOT_APPLIED`, `EXCEPTION_REQUIRED` o
`REJECTED_BY_VALIDATOR`, con el mismo nivel de detalle que un cambio
aplicado (change_id, motivo, evidencia, fuente), de modo que QA-HUM vea el
panorama completo, no solo lo automatizado.

## 6. Dependencias entre artefactos

El redline (2) debe coincidir exactamente con las diferencias entre
`DOCUMENTO_CANDIDATO_COMPLETO` (1) y el original — 0 diferencias no
explicadas es un gate de aceptación (`ACCEPTANCE_AND_VALIDATION_GATES.md`).
El reporte de calidad (9) y el reporte de revalidación (8) son producidos
por agentes distintos (AGT-QLT y AGT-RVL respectivamente) para preservar la
independencia exigida en la sección 5 del plan (AGT-RVL nunca comparte
lógica de decisión con AGT-REM).

## 7. Estado actual y brecha

Ninguno de los 9 artefactos existe hoy de forma generalizada y automática
para un ciclo de remediación completo. El precedente más cercano es el
ciclo real FS_v1.2 (v1.0→v1.4 aprobado por Cesar, ver memoria de proyecto
`project_gmpai_document_validation.md`), que produjo manualmente/con
scripts ad-hoc algunos de estos artefactos (informe, paquete v5) pero no
como un pipeline de 9 artefactos estandarizado y reutilizable para
cualquier documento del inventario Rockwell. Brecha completa — gated a
Fase M del roadmap.
