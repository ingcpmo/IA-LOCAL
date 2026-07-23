# CORRECTED_DOCUMENT_GENERATION_AND_FORMAT_SPEC

## 1. Regla de completitud

El pipeline operativo futuro NO está completo hasta generar una nueva
versión ÍNTEGRA del documento remediado. El original **nunca** se
sobrescribe (consistente con `ORIGINAL_DOCUMENTS_IMMUTABLE = true` y con la
prohibición de escritura en `source/Rockwell/`).

Ruta objetivo (a integrar a `path_policy.py` en implementación):
`factory/generated_documents/<run_id>/<document_id>/`

## 2. Metadatos conservados

SHA-256 original y candidato; versión original y candidata; `run_id`;
fingerprint; fecha; agentes participantes; modelo y digest; fuentes
regulatorias utilizadas.

## 3. Elementos conservados del formato original

El candidato conserva, según formato: portada; título; código; versión;
control de cambios; índice; estructura; numeración; encabezados; secciones;
subsecciones; tablas; figuras; notas; referencias cruzadas; terminología;
idioma; estilo técnico; formato general.

**No es válido** entregar únicamente: resumen; listado de sugerencias;
fragmentos; Markdown; reporte sin documento corregido; instrucciones
manuales de modificación.

## 4. Estrategia por formato (aplicada a los formatos reales de Rockwell inventariados)

| Formato en inventario real | Estrategia |
|---|---|
| DOCX (ninguno detectado en Rockwell hoy — 12 PDF, 1 XLSX, 1 DOCM) | DOCX candidato + PDF de revisión + redline |
| PDF con fuente editable autorizada (a confirmar por documento en Fase A/N — ninguno de los 12 PDF de Rockwell tiene fuente editable conocida hoy) | Modificar copia editable; generar candidato editable y PDF |
| PDF sin fuente editable (caso probable para los 12 PDF de Rockwell, incluyendo el escaneado `SAT3 Scanned-1.pdf`) | Reconstruir versión editable cuando sea técnicamente seguro; generar DOCX y PDF candidatos; registrar limitaciones de fidelidad; **bloquear** la generación cuando no pueda conservarse el contenido con confiabilidad suficiente (caso más probable para el PDF escaneado de 136.8 MB) |
| XLSX (`MCCPDC PCS-CP01 Alarms Hard Soft IO Listing revH.xlsx`) | XLSX nuevo; preservar hojas, fórmulas, tablas y rangos; registrar cambios por hoja y celda (redline celda a celda) |
| DOCM (`215115305-T-039 Design Docs for ASantiago.docm`) | NO ejecutar macros (confirmado prohibido en esta corrida y en producción); preservar original; documentar limitaciones y método seguro de generación (extracción vía XML de Office sin invocar VBA) |
| Formatos no soportados | `DOCUMENT_GENERATION_BLOCKED`; continuar con otros documentos; registrar la excepción |

## 5. Reglas de incorporación de cambios

El candidato limpio incorpora SOLO cambios `AUTO_APPLIED_TO_DRAFT`. Los
cambios `PROPOSED_NOT_APPLIED` / `EXCEPTION_REQUIRED` /
`REJECTED_BY_VALIDATOR` van al paquete de excepciones; **jamás** se
incorporan silenciosamente.

## 6. Registro por corrección aplicada

`change_id`; `document_id`; SHA-256 original; ubicación; texto original;
texto corregido; tipo de cambio; hallazgo; gap o desviación;
`requirement_id`; regulación; versión; numeral; cita normativa; URL;
SHA-256 regulatorio; explicación de insuficiencia; explicación de cómo el
cambio atiende el requisito; agente redactor; agente validador; resultado
de gates; resultado de revalidación; evidencia de implementación
pendiente.

## 7. Regla anti-fabricación (respeto del propósito documental)

URS expresa requisitos; FS comportamiento funcional previsto; DS diseño;
SOP procedimientos; PROTOCOLO pruebas planificadas; REPORTE resultados
observados. **PROHIBIDO** convertir una capacidad requerida en una
capacidad supuestamente implementada. Esta regla es especialmente relevante
para el inventario real: el URS v2.1 y el FS v1.2 de Rockwell son
documentos de requisito/diseño previsto — cualquier corrección debe
mantenerse dentro de ese registro documental, nunca afirmar que algo "ya
está implementado" en el sistema físico.

## 8. AGT-QLT sobre el documento completo

Revisa el DOCUMENTO COMPLETO (no solo fragmentos): coherencia global;
consistencia; terminología; numeración; referencias cruzadas; tablas;
abreviaturas; definiciones; duplicaciones; contradicciones; ortografía;
gramática; claridad; precisión; estilo profesional.

## 9. Nota de contenido obligatoria

En todo candidato/reporte: los agentes no reemplazan decisiones de QA/QC y
no liberan lotes ni documentos automáticamente. `sanitize_for_report()`
aplica a todo render.

## 10. Estado actual y brecha

No existe hoy un generador de documentos corregidos generalizado. Los
scripts existentes (`generate_fs_v1_2_draft_docx.py`,
`generate_fs_v1_2_draft_v2.py`) son ad-hoc para una corrida puntual del FS
v1.2 (ya llegó a v1.4 aprobado por Cesar, según memoria de proyecto) — útil
como referencia de patrón real de generación DOCX/PDF, pero no como
componente generalizable a los 14 archivos del inventario Rockwell ni a
otros clientes de la fábrica. Brecha completa para PDF sin fuente editable,
XLSX celda-a-celda y DOCM sin macros — gated a Fases J-M del roadmap.
