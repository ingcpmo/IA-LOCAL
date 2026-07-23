# ACCEPTANCE_AND_VALIDATION_GATES

Para cada gate: cómo se mide; script/test previsto; momento de ejecución;
condición PASS; condición FAIL; evento de auditoría; efecto sobre el
pipeline; integración a Gate 0 (`factory_selfcheck.sh`).

| # | Gate | Cómo se mide | Momento | PASS | FAIL | Evento de auditoría | Efecto |
|---|---|---|---|---|---|---|---|
| 1 | 100% archivos Rockwell inventariados, 0 omitidos | `count(find)==count(allowlist)` | Fin de AGT-INV | igualdad exacta | diferencia>0 | `inventory_coverage_check` | Bloquea AGT-APP |
| 2 | 100% originales con SHA-256 y procedencia, 0 sobrescritos | comparación de hash periódica vs. registro inicial | Continuo | hash inalterado | divergencia | `source_integrity_violation` | Bloqueo total del pipeline |
| 3 | 100% requisitos con fuente gobernada | estado `LOCAL_CANONICAL_COPY_VERIFIED` por requirement_id | Fin de AGT-RSG/REP | todos verificados | alguno no verificado | `source_governance_check` | Requisitos dependientes ⇒ `EVALUATION_INCOMPLETE` |
| 4 | 100% prompts con Evidence Pack completo | validación de schema del pack antes de invocar LLM | Antes de cada llamada AGT-VER | pack completo | pack incompleto | `evidence_pack_validation` | Bloquea la llamada, no la corrida |
| 5 | 100% fuentes con URL, versión, SHA-256 | validación de schema del catálogo | Fin de AGT-RSG | todos los campos presentes | campo faltante | `regulatory_source_schema_check` | Fuente marcada `REGULATORY_SOURCE_UNVERIFIED` |
| 6 | 100% evidencias con anclaje documental | validación A | Por evidencia | ancla literal encontrada | no ancla | `anchor_verification` | Evidencia descartada |
| 7 | 100% conclusiones positivas con A/B/C/D | verificación de las 4 banderas antes de estado positivo | Por requisito | A∧B∧C∧D=true | alguna falsa | `abcd_verification` | Estado degradado (PARTIALLY/UNDER_REVIEW/GAP) |
| 8 | 0 citas inventadas; 0 coincidencias léxicas aisladas aceptadas | Golden Dataset (ANNEX11_4 y afines) | Model Qualification Gate + runtime | 0 casos | >0 casos | `golden_dataset_regression` | Bloquea aceptación de modelo/perfil |
| 9 | 0 DOCUMENTATION_GAP con cobertura incompleta | verificación de las 6 condiciones de la sección 13.3 del plan | Por conclusión | condiciones cumplidas | condición faltante | `gap_classification_check` | Reclasifica a `EVALUATION_INCOMPLETE` |
| 10 | 0 cambios sin requisito/evidencia/explicación/fuente | validación de campos obligatorios del change_id | Por cambio propuesto | todos los campos | campo faltante | `change_completeness_check` | Cambio rechazado, no aplicado |
| 11 | 0 cambios con redacción inválida; 0 capacidades inventadas | AGT-QLT + regla anti-fabricación | Por cambio | pasa AGT-QLT | falla | `quality_gate_result` | 1 ciclo de reintento, luego `EXCEPTION_REQUIRED` |
| 12 | 0 afirmaciones de implementación sin evidencia | chequeo de tipo documental (URS≠implementado) | Por cambio | conforme al propósito documental | viola regla | `anti_fabrication_check` | Cambio rechazado |
| 13 | 0 dependencias runtime de Claude Code | inspección de imports/arranque del servicio | Diseño de cada agente | scripts Python autónomos | dependencia detectada | `runtime_independence_check` | Bloquea aceptación del componente |
| 14 | 100% agentes híbridos con ModelProvider | grep de imports directos de cliente Ollama | Fase D y en adelante | 0 imports directos fuera de la interfaz | import directo detectado | `model_provider_coupling_check` | Bloquea merge del componente |
| 15 | 0 llamadas LLM para tareas deterministas | revisión de qué función invoca al provider | Diseño/revisión de código | ninguna tarea de sección 8 del plan usa LLM | violación | `deterministic_authority_check` | Rechazo de diseño |
| 16 | 100% salidas LLM validadas por schema | validación JSON schema por respuesta | Por llamada | válido | inválido | `llm_output_schema_check` | 1 reintento, luego `EXCEPTION_REQUIRED` |
| 17 | 100% llamadas con run_id y task_id | inspección de logs de llamada | Por llamada | ambos presentes | ausente | `call_traceability_check` | Llamada descartada, no contabilizada |
| 18 | 0 cambios automáticos a proveedor externo | verificación de fallback_policy | Ante `LLM_SERVICE_UNAVAILABLE` | permanece en mismo provider | cambio automático detectado | `fallback_policy_check` | Rechazo de configuración |
| 19 | 0 HIGH_RISK autoaplicados | verificación de risk_band antes de `AUTO_APPLIED_TO_DRAFT` | Por cambio | risk_band≠HIGH | HIGH autoaplicado | `risk_gate_violation` | Bloqueo crítico, incidente |
| 20 | 0 fallos recuperables bloqueando toda la corrida | verificación de continuidad tras `EXCEPTION_REQUIRED` individual | Por fallo | corrida continúa con otros cambios | corrida se detiene entera | `run_continuity_check` | Ajuste de orquestación |
| 21 | 100% excepciones dentro del paquete QA | conteo de excepciones vs. paquete final | Fin de AGT-DOC | igualdad | excepción faltante en paquete | `exception_package_completeness` | Bloquea `CORRECTED_DOCUMENT_GENERATION_GATE` |
| 22 | 100% documentos remediables con candidato completo generado | verificación de existencia de artefacto 1 | Fin de AGT-DOC | existe | falta | `document_generation_check` | `DOCUMENT_GENERATION_PARTIAL`/`BLOCKED` |
| 23 | 100% candidatos con SHA-256 nuevo | comparación hash candidato vs. original | Fin de AGT-DOC | distinto y registrado | igual o ausente | `candidate_hash_check` | Bloquea gate 16 |
| 24 | 100% candidatos con redline, matriz, reseña y manifest | verificación de existencia de artefactos 2,4,5,7 | Fin de AGT-DOC | todos presentes | falta alguno | `package_completeness_check` | `DOCUMENT_PACKAGE_INCOMPLETE` |
| 25 | 100% candidatos revalidados como documento completo | verificación de ejecución de AGT-RVL | Fin de AGT-RVL | ejecutado y registrado | no ejecutado | `revalidation_execution_check` | Bloquea entrega |
| 26 | 0 diferencias no explicadas entre candidato y redline | comparación automática | Fin de AGT-RVL | 0 diferencias sin change_id | diferencia sin explicar | `redline_consistency_check` | Corrida no liberable |
| 27 | 0 cambios rechazados incorporados silenciosamente | verificación cruzada candidato vs. estado de cada change_id | Fin de AGT-RVL | ningún `REJECTED_BY_VALIDATOR` presente en el texto | encontrado | `silent_incorporation_check` | Incidente crítico, corrida no liberable |
| 28 | 0 candidatos entregados como fragmentos | verificación de estructura completa (portada, secciones, etc.) | Fin de AGT-DOC | estructura completa | fragmento | `full_document_check` | `DOCUMENT_GENERATION_BLOCKED` |
| 29 | 0 paquetes entregables sin documento candidato | verificación de artefacto 1 presente antes de ensamblar paquete | Ensamblado de paquete final | presente | ausente | `package_prerequisite_check` | Bloquea ensamblado |
| 30 | 0 divergencias entre artefactos | verificación cruzada de los 9 artefactos entre sí | Fin de AGT-DOC/AGT-RVL | consistentes | divergencia | `cross_artifact_consistency_check` | Corrida no liberable |
| 31 | 0 liberaciones automáticas; aprobación QA obligatoria | verificación de que ningún estado terminal declara liberación sin `decision_origin=human_confirmed` | Cierre de ciclo | siempre humano | liberación automática detectada | `human_release_gate_check` | Incidente crítico |

## Integración a Gate 0

Todos los gates de esta tabla son candidatos a incorporarse como checks
adicionales de `factory/scripts/ops/factory_selfcheck.sh` a medida que cada
fase del roadmap se implemente — no se modifica ese script en esta corrida
de diseño (prohibido implementar código), pero cada fase debe declarar
explícitamente qué checks de esta tabla añade a Gate 0 como criterio de
cierre.
