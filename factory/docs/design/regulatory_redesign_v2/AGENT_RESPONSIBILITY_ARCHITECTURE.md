# AGENT_RESPONSIBILITY_ARCHITECTURE

Arquitectura objetivo de 11 agentes + QA humana. Basada en
`CURRENT_AGENT_RUNTIME_AUDIT.md` (qué existe hoy) y las reglas de las
secciones 5 y 8 del plan de instrucciones.

Reglas de arquitectura (vinculantes):
- Prohibido concentrar la solución en un único agente.
- Los híbridos usan LLM SOLO cuando la tarea requiera comprensión semántica,
  comparación contextual o redacción.
- AGT-RVL nunca comparte lógica de decisión con AGT-REM ni consume sus
  conclusiones intermedias; solo compara artefactos finales contra baseline.
- AGT-RSG opera FUERA de la inferencia (descargas asíncronas aprobadas por
  humano).
- Ningún agente escribe en `source/Rockwell/`. Todo acceso a rutas vía
  `factory/core/path_policy.py` (sin superficies de path paralelas).
- Separación Reader/Executor: endpoints GET jamás escriben en la cadena de
  auditoría; POST audita exactamente un evento con `run_by` real.

## AGT-INV — Inventario, procedencia, hashes, duplicados, allowlist

- **Entradas**: árbol de `source/Rockwell/` (o equivalente por cliente).
- **Salidas**: `source_baseline_allowlist.yaml` (schema sección 9 del plan).
- **input_schema**: lista de rutas de archivo.
- **output_schema** (`schema_version: 1.0.0`): ver campos de la sección 9
  del plan (`file_id`, `path`, `sha256`, `doc_type`, `origin_class`,
  `duplicate_of`, `extraction_capability`, `processing_state`,
  `applicability`, `related_requirements`, `justification`).
- **Dependencias**: ninguna (primer eslabón del pipeline).
- **Permisos**: lectura de `source/Rockwell/` vía `path_policy.py`; escritura
  solo en `factory/regulatory/scope/`.
- **Herramientas autorizadas**: `hashlib.sha256`, extractor de texto
  determinista (reutiliza `app/extraction.py`).
- **Función determinista**: 100% — hash, conteo, comparación de nombre/ruta,
  detección de duplicado exacto por hash.
- **Función de la LLM**: ninguna.
- **Estados permitidos**: los 9 enums cerrados de la sección 9 del plan.
- **Estados prohibidos**: cualquier estado no listado; omisión silenciosa de
  archivo.
- **Validadores**: `count(find) == count(allowlist)`; 0 archivos sin estado
  terminal.
- **Eventos de auditoría**: `inventory_allowlist_generated` (payload:
  run_id, total_files, duplicates_found, docm_count).
- **Fallback**: ninguno necesario (tarea 100% determinista, no depende de
  LLM ni red).
- **Criterios de aceptación**: 100% archivos con estado terminal; 0
  omisiones; duplicados detectados y marcados, no colapsados.
- **Código reutilizable actual**: `app/inventory_agent.py`,
  `app/version_selection.py` (ver auditoría).

## AGT-APP — Aplicabilidad documento × tipo documental × requirement_id

- **Entradas**: allowlist de AGT-INV, catálogo regulatorio de AGT-RSG.
- **Salidas**: matriz de aplicabilidad (documento → requirement_id
  aplicables, con justificación si NOT_APPLICABLE).
- **input_schema**: `{file_id, doc_type, catalog_requirement_ids[]}`.
- **output_schema**: `{file_id, requirement_id, applicability:
  APPLICABLE|NOT_APPLICABLE, justification}`.
- **Dependencias**: AGT-INV, AGT-RSG.
- **Permisos**: lectura allowlist + catálogo; escritura en
  `factory/regulatory/matrix/`.
- **Herramientas autorizadas**: reglas deterministas de mapeo doc_type↔
  requirement_id; LLM SOLO para casos ambiguos de clasificación semántica de
  contenido (no de aplicabilidad regulatoria final).
- **Función determinista**: reglas fijas doc_type→requirement_id
  candidatas; decisión final de aplicabilidad.
- **Función de la LLM**: sugerir clasificación de contenido ambiguo (p.ej.
  "¿esta narrativa de control es DS o SOP?"), nunca aplicabilidad
  regulatoria en sí.
- **Estados permitidos**: `APPLICABLE`, `NOT_APPLICABLE_WITH_JUSTIFICATION`.
- **Estados prohibidos**: aplicabilidad sin justificación cuando es
  NOT_APPLICABLE.
- **Validadores**: 100% de pares documento×requisito con estado.
- **Eventos de auditoría**: `applicability_matrix_generated`.
- **Fallback**: si la LLM no está disponible, marcar
  `HUMAN_REVIEW_REQUIRED` para los pares ambiguos, continuar con los
  determinísticos.
- **Criterios de aceptación**: cambio material de aplicabilidad requiere
  aprobación humana anticipada (R-2 del plan).
- **Código reutilizable actual**: `app/classification_agent.py` (parcial,
  para tipo documental).

## AGT-RSG — Gobernanza de fuentes regulatorias

- **Entradas**: solicitud humana de nueva fuente/versión (fuera de
  inferencia).
- **Salidas**: entrada en catálogo regulatorio (schema sección 10 del plan).
- **Dependencias**: ninguna del pipeline de inferencia; sí de aprobación
  humana (`approved_by` real).
- **Permisos**: escritura SOLO en `factory/regulatory/sources/canonical/`,
  fuera del proceso de inferencia (batch asíncrono aprobado).
- **Herramientas autorizadas**: descarga controlada (fuera de esta corrida
  de diseño), hash, verificación de URL oficial.
- **Función determinista**: 100% — hash, estado, vigencia, versión.
- **Función de la LLM**: ninguna.
- **Estados permitidos**: los 6 enums de la sección 10 del plan.
- **Estados prohibidos**: sustitución automática de fuente sin aprobación
  humana.
- **Validadores**: fuente no verificada ⇒ bloquea todos los requisitos
  dependientes (`EVALUATION_INCOMPLETE`).
- **Eventos de auditoría**: `regulatory_source_registered`,
  `regulatory_source_reverified`.
- **Fallback**: `SOURCE_UNAVAILABLE` con `PENDING_DOCUMENT`, nunca fabricar
  corpus.
- **Criterios de aceptación**: 100% de fuentes con URL, versión, SHA-256.
- **Nota de desambiguación**: NO confundir con `app/risk_agent.py` actual
  (que corresponde a AGT-GAP, no a AGT-RSG). No existe código reutilizable
  directo hoy para AGT-RSG; se construye sobre `factory/regulatory/sources/`.

## AGT-REP — Construcción de Requirement Evidence Packs

- **Entradas**: catálogo regulatorio (AGT-RSG), matriz de aplicabilidad
  (AGT-APP).
- **Salidas**: Evidence Pack por requirement_id (schema sección 11 del
  plan: `canonical_text`, `context_before/after`, `evidence_min_criteria`,
  `exclusion_criteria`, `weak_keywords`, etc.).
- **Función determinista**: 100% — ensamblado de campos desde fuentes
  gobernadas.
- **Función de la LLM**: ninguna en esta etapa (el pack es insumo para la
  LLM, no producto de ella).
- **Validadores**: regla dura — un pack nunca se entrega sin
  `canonical_text` cuando `source_status = LOCAL_CANONICAL_COPY_VERIFIED`.
- **Eventos de auditoría**: `evidence_pack_built` (pack_version,
  requirement_id).
- **Código reutilizable actual**: ninguno completo; el baseline actual
  (`compliance_agents.py` checkpoints) usa descripciones breves, exactamente
  el patrón que este agente corrige (regla dura sección 11 del plan).

## AGT-EVD — Localización y contextualización de evidencia documental

- **Entradas**: documento clasificado + Evidence Pack.
- **Salidas**: fragmento candidato con ubicación exacta (página/sección).
- **Función determinista**: búsqueda textual, recuperación por índice de
  secciones, deduplicación de fragmentos.
- **Función de la LLM**: recuperación semántica cuando la búsqueda textual
  no es suficiente (comprensión contextual).
- **Validadores**: fragmento debe tener ubicación anclable (regla A).
- **Eventos de auditoría**: `evidence_located` (document_sha256,
  requirement_id, location).
- **Código reutilizable actual**: patrón de anclaje de
  `app/llm_integrity_engine.py:76-79,159-163`.

## AGT-VER — Validación de anclaje, fuente, semántica y suficiencia (A/B/C/D)

- **Entradas**: fragmento de AGT-EVD, Evidence Pack de AGT-REP.
- **Salidas**: veredicto A∧B∧C∧D con `SEMANTIC_EVIDENCE_VERIFICATION_SPEC.md`
  como contrato de schema.
- **Función determinista**: validación A (anclaje literal), B (match contra
  canonical_text), reglas de exclusión duras de C (weak_keywords, listas de
  referencias — regla ANNEX11_4).
- **Función de la LLM**: razonamiento semántico C, evaluación de suficiencia
  D por criterio.
- **Estados prohibidos**: aprobar evidencia con discrepancia regla-vs-LLM
  (⇒ `SUPPORTING_EVIDENCE_UNDER_REVIEW`, nunca aprobación).
- **Eventos de auditoría**: `evidence_verified_abcd`.
- **Fallback**: `LLM_SERVICE_UNAVAILABLE`, fail-closed (sección 18 del
  plan).
- **Código reutilizable actual**: `app/llm_integrity_engine.py` (contrato de
  anclaje), `factory/engines/gmpai_integrity/chunked_engine.py` (motor más
  maduro, no wireado a producción — candidato principal).

## AGT-GAP — Clasificación de hallazgos, gaps, desviaciones, contradicciones

- **Entradas**: veredictos de AGT-VER agregados por documento.
- **Salidas**: taxonomía sección 13.1 del plan + estado de conclusión
  (sección 13.3) + clasificación de riesgo (LOW/MEDIUM/HIGH_RISK).
- **Función determinista**: reglas de asignación de riesgo (criticidad,
  tipo documental, alcance, sección, confidence_band);
  `DOCUMENTATION_GAP` solo con las 6 condiciones exhaustivas del plan.
- **Función de la LLM**: explicación de insuficiencia (texto legible),
  nunca el estado terminal.
- **Eventos de auditoría**: `finding_classified`, `risk_assigned`.
- **Código reutilizable actual**: `app/risk_agent.py:33-49` (fórmula
  risk_score, agregación) — nombre actual coincide con este agente
  (AGT-GAP), no con AGT-RSG.

## AGT-REM — Generación de correcciones documentales trazables

- **Entradas**: gap/desviación clasificados, Evidence Pack, contexto
  documental completo.
- **Salidas**: cambio propuesto con `change_id`, texto original/corregido,
  fundamento regulatorio.
- **Función determinista**: ensamblado de metadatos de trazabilidad
  (`change_id`, `document_id`, `sha256`, requirement_id, regulación,
  numeral, URL).
- **Función de la LLM**: redacción del texto corregido, explicación de cómo
  atiende el requisito — respetando la regla anti-fabricación (URS
  expresa, FS comportamiento previsto, etc., sección 14 del plan).
- **Estados permitidos**: `AUTO_APPLIED_TO_DRAFT`, `PROPOSED_NOT_APPLIED`,
  `EXCEPTION_REQUIRED`, `REJECTED_BY_VALIDATOR`.
- **Eventos de auditoría**: `remediation_proposed`, `remediation_gate_result`.
- **Fallback**: 1 ciclo AGT-REM→AGT-QLT si falla un gate; si persiste,
  `EXCEPTION_REQUIRED`.
- **Código reutilizable actual**: ninguno (confirmado en auditoría — es la
  brecha más grande del sistema actual).

## AGT-QLT — Validación regulatoria, técnica, lógica, lingüística, terminológica

- **Entradas**: documento candidato completo (no solo fragmentos).
- **Salidas**: PASS/FAIL por dimensión de calidad (sección 14 del plan:
  coherencia global, terminología, numeración, referencias cruzadas,
  ortografía, gramática, claridad, estilo).
- **Función determinista**: chequeos estructurales (numeración,
  referencias cruzadas rotas, duplicaciones exactas).
- **Función de la LLM**: coherencia semántica global, claridad, estilo.
- **Eventos de auditoría**: `document_quality_gate_result`.
- **Código reutilizable actual**: ninguno directo; patrón de verificación
  de anclaje de `llm_integrity_engine.py` es parcialmente aplicable.

## AGT-DOC — Documento candidato completo + artefactos

- **Entradas**: cambios `AUTO_APPLIED_TO_DRAFT`, documento original.
- **Salidas**: los 9 artefactos de `PROFESSIONAL_DOCUMENT_PACKAGE_SPEC.md`.
- **Función determinista**: ensamblado de manifest, redline mecánico,
  matriz de trazabilidad.
- **Función de la LLM**: reseña narrativa de cambios (texto legible).
- **Eventos de auditoría**: `corrected_document_generated`.
- **Código reutilizable actual**: ninguno (los generadores DOCX existentes
  como `generate_fs_v1_2_draft_docx.py` son scripts ad-hoc de una corrida
  puntual, no un agente generalizado — reutilizables como referencia de
  patrón, no como componente).

## AGT-RVL — Revalidación independiente original vs. candidato

- **Entradas**: BASELINE_ORIGINAL, DOCUMENTO_CANDIDATO_COMPLETO (nunca
  conclusiones intermedias de AGT-REM).
- **Salidas**: por gap, `CLOSED|PARTIALLY_CLOSED|OPEN|NEW_GAP_INTRODUCED|
  IMPLEMENTATION_VERIFICATION_REQUIRED`.
- **Función determinista**: comparación estructural, hashes, apertura de
  archivo, coincidencia entre artefactos.
- **Función de la LLM**: re-ejecución de B/C/D sobre el texto nuevo,
  independiente del razonamiento de AGT-REM.
- **Regla dura**: nunca comparte lógica de decisión con AGT-REM.
- **Eventos de auditoría**: `candidate_revalidated`.
- **Código reutilizable actual**: patrón de "nunca aprueba automáticamente"
  de `app/final_review_agent.py`.

## QA-HUM — Rol humano final

- **Entradas**: paquete final (`QA_FINAL_PACKAGE_AND_DECISION_SPEC.md`).
- **Salidas**: decisión humana (`APPROVE_CLEAN|APPROVE_WITH_EXCEPTIONS|
  REQUEST_CHANGES|REJECT`).
- **Función determinista**: N/A — es el punto de autoridad humana.
- **Función de la LLM**: recomendación NO vinculante (input, nunca
  veredicto).
- **Eventos de auditoría**: `qa_decision_recorded` (approved_by real, 422
  para identidades genéricas, 409 doble aprobación).
- **Código reutilizable actual**: `app/final_review_agent.py` como patrón
  de gate humano explícito, y `factory/api/routes/layer9.py` como
  precedente de endpoints de aprobación/decisión.
